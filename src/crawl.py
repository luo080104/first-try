# crawl.py - v5 采集引擎（一键采集，WorkBuddy 审核版）
# 流程：种子词/失败词 → API 快通道 + 浏览器慢通道 → 入库 → 状态记账 → 自动扩展新词
# 断点续跑：done 跳过 / failed 重试 / 中断后可恢复
import os
import re
import sys
import time
import asyncio
import threading
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

# ========== 全局进度状态（跨请求共享） ==========

_progress = {
    'running': False,
    'current': '',        # 正在采集的词
    'done': 0,            # 已完成词数
    'total': 0,           # 本轮总词数
    'new_items': 0,       # 新入库件数
    'started': '',        # 开始时间
    'elapsed': 0,         # 已耗时（秒）
    'errors': [],         # 失败词列表
    'round': 0,           # 第几轮
}
_lock = threading.Lock()


def get_progress() -> dict:
    with _lock:
        return dict(_progress)


def _set_progress(**kw):
    with _lock:
        _progress.update(kw)


# ========== 自动扩展：从新入库标题提取新词 ==========

def _exclude_short(w: str) -> bool:
    """排除纯数字/纯英文短词（WorkBuddy：5080/RTX 不收，RTX 5080 可收）"""
    return not re.fullmatch(r'[\dA-Za-z]{1,6}', w or '')

# 常见营销/通用噪音词（不当作品牌收）
_NOISE = {'新款', '官方', '旗舰', '包邮', '正品', '特价', '促销', '热卖', '爆款', '同款', '通用',
          '专用', '家用', '便携', '简约', '加厚', '升级', '经典', '限量', '预售', '自营',
          '京东', '淘宝', '拼多多', '正装', '试用', '清仓', '秒杀', '直降', '现货'}


def _extract_candidates(title: str) -> set:
    """从单条标题提取候选词：品牌表 + 【】内 + 标题开头 2-4 字"""
    from matcher import BRAND_TABLE, DigitalMatcher
    cands = set()
    for b in BRAND_TABLE:
        if b in title:
            cands.add(b)
    for b in DigitalMatcher.BRANDS:
        if b in title:
            cands.add(b)
    m = re.search(r'【([^】]{2,6})】', title)
    if m:
        cands.add(m.group(1))
    head = re.match(r'^([\u4e00-\u9fa5]{2,4})', title.strip())
    if head:
        h = head.group(1)
        # 剥掉噪音前缀（如"新款卫衣"→"卫衣"）
        for n in sorted(_NOISE, key=len, reverse=True):
            if h.startswith(n):
                h = h[len(n):]
                break
        if len(h) >= 2:
            cands.add(h)
    return cands


def find_new_words(items: list) -> list:
    """从商品标题提取新品牌/系列词，出现 >= CRAWL_NEWWORD_MIN 次才收（可配）
    策略：品牌表 + 【】内词 + 标题开头词，排除噪音/短词"""
    min_count = int(os.environ.get('CRAWL_NEWWORD_MIN', '3'))
    counter = Counter()
    for it in items:
        title = str(it.get('title') or '')
        if not title:
            continue
        for w in _extract_candidates(title):
            counter[w] += 1
    words = [w for w, cnt in counter.items()
             if cnt >= min_count and _exclude_short(w) and w not in _NOISE]
    return words


# ========== 单个关键词采集 ==========

async def _crawl_one_keyword(keyword: str, category: str, pages: int) -> tuple:
    """采集一个词：API 快通道 + 浏览器慢通道翻页 → 返回 (入库件数, items)"""
    from api_client import search_goods, search_pdd, search_vip
    from db import get_conn, upsert_product_item
    from app import search_taobao_full, search_vip_full, search_pdd_full

    all_items = []
    # 快通道：API（走 24h 缓存，秒级；新鲜度靠慢通道）
    tb_items = await asyncio.to_thread(search_goods, keyword, category or None)
    pdd_items = await asyncio.to_thread(search_pdd, keyword)
    vip_items = await asyncio.to_thread(search_vip, keyword)
    all_items += tb_items + pdd_items + vip_items

    # 慢通道：浏览器翻页（串行，频率受限：tb 30s / vip 12-20s / pdd 12-20s）
    # 注：京东不走浏览器（搜索页验证码多，案例启发）→ 改为采集轮次的全局榜单通道 crawl_jd_by_elite
    tb_full, vip_full, pdd_full = [], [], []
    for p in range(1, pages + 1):
        batch = await asyncio.to_thread(search_taobao_full, keyword, p, 8, True)
        tb_full += batch
        if len(batch) < 8:
            break
        await asyncio.sleep(2)
    for p in range(1, pages + 1):
        batch = await asyncio.to_thread(search_vip_full, keyword, p)
        vip_full += batch
        if len(batch) < 8:
            break
        await asyncio.sleep(2)
    for p in range(1, 6):  # 2026-08-11 小布斧1：PDD 独立翻 5 页（补浏览器通道短板）
        batch = await asyncio.to_thread(search_pdd_full, keyword, p, 8, True)
        pdd_full += batch
        if len(batch) < 8:
            break
        await asyncio.sleep(2)
    all_items += tb_full + vip_full + pdd_full

    # 入库（platform+item_id 去重；try/finally 保证连接不泄漏——无人值守 8 小时关键）
    conn = None
    try:
        conn = get_conn()
        added = 0
        for it in all_items:
            it['_source'] = 'browser' if it.get('_source') == 'browser' else 'api'
            if upsert_product_item(conn, it, category or ''):
                added += 1
        conn.commit()
    finally:
        if conn:
            conn.close()
    return added, all_items


_instance_lock = threading.Lock()
_instance_holder = False  # P1-2：实例锁覆盖 API/__main__ 双路径


def _crawl_single(fn):
    """采集单实例装饰器：任何入口同时只能跑一个"""
    from functools import wraps

    @wraps(fn)
    async def wrapper(*a, **kw):
        global _instance_holder
        with _instance_lock:
            if _instance_holder:
                return {'ok': False, 'msg': '已有采集实例在运行'}
            _instance_holder = True
        try:
            return await fn(*a, **kw)
        finally:
            with _instance_lock:
                _instance_holder = False
    return wrapper


@_crawl_single
async def run_crawl_round(pages: int = 2, max_seconds: int = 72000) -> dict:  # 20h兜底（小骆：不要设限，词跑完自然停）
    """跑一轮采集：pending+failed 词 → 报告。
    max_seconds: 硬性时长上限（默认 8 小时），到点自动停止，未完成词保持 pending 下轮继续。
    进度含 avg_per_word/eta 精准预估（实测均值 × 剩余量）。"""
    from db import (ensure_crawl_tasks, get_pending_tasks,
                    mark_crawl_task, add_auto_keywords, get_conn,
                    upsert_product_item)

    ensure_crawl_tasks()
    tasks = get_pending_tasks(500)  # 一轮取全部（310+ 词），避免 100 上限截断
    if not tasks:
        return {'ok': False, 'msg': '没有待采集的关键词（全部已完成）'}

    _set_progress(running=True, total=len(tasks), done=0, new_items=0,
                  current='', errors=[], started=time.strftime('%H:%M:%S'),
                  round=_progress['round'] + 1)
    t0 = time.time()
    ok_count = fail_count = new_total = 0
    jd_added = 0
    all_new_items = []
    word_times = []  # 每词耗时（秒），用于 ETA 精准预估

    try:
        # 京东榜单通道（无需 token/浏览器/验证码）：每轮开始先全局拉一批京东商品入库
        try:
            from jd_api import crawl_jd_by_elite
            jd_items = await asyncio.to_thread(crawl_jd_by_elite, 2, 20)
            if jd_items:
                conn = None
                try:
                    conn = get_conn()
                    for it in jd_items:
                        if upsert_product_item(conn, it, ''):
                            jd_added += 1
                    conn.commit()
                finally:
                    if conn:
                        conn.close()
                print(f'[crawl] 🛡️ 京东榜单通道: +{jd_added} 件（无浏览器无验证码）')
        except Exception as e:
            print(f'[crawl] ⚠️ 京东榜单通道失败: {str(e)[:80]}')

        for task in tasks:
            # 硬性时长上限：到点即停（当前词跑完才停，不中断进行中操作）
            elapsed_now = time.time() - t0
            if elapsed_now > max_seconds:
                print(f'[crawl] ⏰ 已达时长上限 {max_seconds//3600} 小时，停止（剩余 {len(tasks) - (ok_count + fail_count)} 词下轮继续）')
                with _lock:
                    _progress['errors'].append(f'[时长上限] 跑满 {max_seconds//3600} 小时自动停止，剩余词下轮继续')
                break
            kw, cat = task['keyword'], task.get('category') or ''
            _set_progress(current=f'{kw}（{cat or "未分类"}）')
            w0 = time.time()
            try:
                added, items = await _crawl_one_keyword(kw, cat, pages)
                mark_crawl_task(kw, 'done', added)
                ok_count += 1
                new_total += added
                all_new_items += items
                word_times.append(time.time() - w0)
                print(f'[crawl] ✅ {kw}: +{added} 件（累计 {len(items)} 条，耗时 {time.time()-w0:.0f}s）')
            except Exception as e:
                # WorkBuddy 失败分类：验证码立即停 / 网络超时不计数 / 其他正常计数
                msg = str(e)
                if '验证码' in msg or 'captcha' in msg.lower():
                    mark_crawl_task(kw, 'paused', 0)
                    with _lock:
                        _progress['errors'].append(f'{kw}: 验证码拦截，已暂停')
                    print(f'[crawl] 🛑 {kw}: 验证码，立即暂停（不计数）')
                elif any(k in msg for k in ('超时', 'timeout', 'timed out', '连接', '网络', 'Name or service', 'timed')):
                    mark_crawl_task(kw, 'failed', 0, count_fail=False)
                    fail_count += 1
                    with _lock:
                        _progress['errors'].append(f'{kw}: 网络超时（不计数）')
                    print(f'[crawl] ⚠️ {kw}: 网络超时（不计数）: {msg[:60]}')
                else:
                    mark_crawl_task(kw, 'failed', 0)
                    fail_count += 1
                    with _lock:
                        _progress['errors'].append(f'{kw}: {msg[:60]}')
                    print(f'[crawl] ❌ {kw}: {msg[:80]}')
                word_times.append(time.time() - w0)
            # 进度 + ETA（实测均值 × 剩余量，越跑越准）
            done_now = ok_count + fail_count
            avg = sum(word_times) / len(word_times) if word_times else 0
            eta = avg * (len(tasks) - done_now) if avg else 0
            _set_progress(done=done_now,
                          new_items=new_total,
                          elapsed=int(elapsed_now),
                          avg_per_word=int(avg) if avg else 0,
                          eta=int(eta))

        # 2026-08-11 关闭自动扩展（小骆：不要漫无边际——只采现有词，跑完自然停）
        new_words = []
        added_words = 0
    except Exception as e:
        # 无人值守兜底：任何非词级异常都不能让 running 卡死
        with _lock:
            _progress['errors'].append(f'[轮次异常] {str(e)[:100]}')
        print(f'[crawl] ⚠️ 轮次异常（已恢复）: {str(e)[:120]}')
        new_words, added_words = [], 0
    finally:
        _set_progress(running=False, current='', elapsed=int(time.time() - t0))
    return {
        'ok': True,
        'total': len(tasks), 'done': ok_count, 'failed': fail_count,
        'new_items': new_total + jd_added, 'new_words': new_words[:20],
        'added_words': added_words,
        'elapsed': int(time.time() - t0),
        'stopped_by_timeout': (ok_count + fail_count) < len(tasks) and time.time() - t0 > max_seconds,
    }


if __name__ == '__main__':
    # 2026-08-11 单实例保护（弹窗事故教训：fill_shop 双进程循环）
    import socket as _sock
    try:
        _s = _sock.socket()
        _s.bind(('127.0.0.1', 9331))
    except OSError:
        print('[crawl] 已有采集实例在运行，退出')
        sys.exit(0)
    # 自测：单轮（1 页，快）
    import sys
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(asyncio.run(run_crawl_round(pages)))
