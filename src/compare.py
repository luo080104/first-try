# compare.py - v3.5 对比页后端（Mode 2「帮我比」）
# 职责：链接解析 + 三平台搜索 + SKU 合并 + 对比数据组装 + R1 AI 建议
import os
import re
import sys
import json
import time
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(__file__))

from api_client import search_goods, search_pdd
from matcher import parse_items, group_by_sku, ADAPTERS
from db import find_subsidies, get_conn
from content_reader import read_content_items

API_URL = 'https://api.deepseek.com/chat/completions'
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# ========== 链接解析（WorkBuddy 确认的平台格式）==========

PLATFORM_URL_PATTERNS = [
    # 淘宝：item.taobao.com/item.htm?id=XXX
    ('tb', re.compile(r'item\.taobao\.com/item\.htm\?[^"\' ]*id=([\w]+)', re.I)),
    ('tb', re.compile(r'detail\.tmall\.com/item\.htm\?[^"\' ]*id=([\w]+)', re.I)),
    # 京东：item.jd.com/XXX.html
    ('jd', re.compile(r'item\.jd\.com/(\d{6,15})', re.I)),
    # 拼多多：mobile.yangkeduo.com/goods.html?goods_id=XXX
    ('pdd', re.compile(r'(?:yangkeduo|pinduoduo)\.com/goods\.html\?[^"\' ]*goods_id=([\w]+)', re.I)),
]

def parse_link(url: str) -> dict:
    """解析商品链接 → {platform, item_id}；不是链接返回空"""
    if not url or not re.match(r'^https?://', url):
        return {}
    for plat, pat in PLATFORM_URL_PATTERNS:
        m = pat.search(url)
        if m:
            return {'platform': plat, 'item_id': m.group(1)}
    return {}

# ========== 三平台搜索 + 合并 ==========

# 慢通道结果缓存（6h，避免每次对比都等浏览器）
_slow_cache = {}  # keyword -> (timestamp, items)
SLOW_CACHE_HOURS = 6


def _slow_cache_get(keyword: str):
    import time as _t
    hit = _slow_cache.get(keyword)
    if hit and _t.time() - hit[0] < SLOW_CACHE_HOURS * 3600:
        return hit[1]
    return None


def _slow_cache_set(keyword: str, items: list):
    import time as _t
    _slow_cache[keyword] = (_t.time(), items)


def _search_fast(keyword: str, category: str = '') -> tuple:
    """快通道：API 三平台（淘宝+拼多多+唯品会API）"""
    from api_client import search_vip
    tb_items = search_goods(keyword, category or None)
    pdd_items = search_pdd(keyword)
    vip_items = search_vip(keyword)
    return tb_items + pdd_items + vip_items, tb_items, pdd_items, vip_items


def _group_items(all_items: list, category: str) -> list:
    """SKU 合并分组（有品类适配器用适配器，否则按品牌粗分组）"""
    groups = []
    if category and category in ADAPTERS and ADAPTERS[category]:
        parsed = parse_items(all_items, category)
        grouped = group_by_sku(parsed, category)
        for key, items in grouped.items():
            if not key or key == '未解析':
                continue
            by_platform = {}
            for it in items:
                p = it.get('platform', '?')
                if p not in by_platform or it['actualPrice'] < by_platform[p]['actualPrice']:
                    by_platform[p] = it
            best = min(by_platform.values(), key=lambda x: x['actualPrice'])
            groups.append({'key': key, 'platforms': by_platform, 'best': best})
        groups.sort(key=lambda g: g['best']['actualPrice'])
    else:
        # 无适配器：按"品牌+前8字"粗分组，避免同商品散落
        seen = {}
        for it in all_items:
            brand = (it.get('brand') or it.get('title', '')[:8])
            k = brand
            if k not in seen:
                seen[k] = {'key': brand, 'platforms': {}, 'best': None}
            p = it.get('platform', '?')
            if p not in seen[k]['platforms'] or it['actualPrice'] < seen[k]['platforms'][p]['actualPrice']:
                seen[k]['platforms'][p] = it
        groups = list(seen.values())
        for g in groups:
            g['best'] = min(g['platforms'].values(), key=lambda x: x['actualPrice'])
        groups.sort(key=lambda g: g['best']['actualPrice'])
    return groups


def search_compare(keyword: str, category: str = '') -> dict:
    """对比页搜索：快通道 API（同步，供 advice 等秒回场景）"""
    all_items, tb_items, pdd_items, vip_items = _search_fast(keyword, category)
    groups = _group_items(all_items, category)
    subsidies = find_subsidies(keyword, category)
    return {'keyword': keyword, 'category': category, 'groups': groups,
            'tb_count': len(tb_items), 'pdd_count': len(pdd_items), 'subsidies': subsidies}


async def search_compare_slow(keyword: str, category: str = '', pages: int = 1) -> dict:
    """对比页搜索：快通道 + 京东/唯品会浏览器慢通道（异步调用方负责 to_thread）
    慢通道结果 6h 内存缓存。"""
    import asyncio
    from app import search_jd_full, search_vip_full, search_taobao_full as search_tb_full

    all_items, tb_items, pdd_items, vip_api_items = _search_fast(keyword, category)

    # 慢通道：淘宝 + 京东 + 唯品会浏览器（并行，端口 9300/9301/9302 不冲突）
    slow_key = f'{keyword}|{category}'
    cached = _slow_cache_get(slow_key)
    if cached is not None:
        tb_full, jd_items, vip_items = cached
    else:
        tb_full, jd_items, vip_items = [], [], []
        try:
            tb_full2, jd_full, vip_full = await asyncio.gather(
                asyncio.to_thread(search_tb_full, keyword, pages),
                asyncio.to_thread(search_jd_full, keyword, pages),
                asyncio.to_thread(search_vip_full, keyword, pages),
            )
            tb_full, jd_items, vip_items = tb_full2, jd_full, vip_full
            _slow_cache_set(slow_key, (tb_full, jd_items, vip_items))
        except Exception as e:
            print(f'[compare_slow] 慢通道失败: {str(e)[:80]}')

    all_items += tb_full + jd_items + vip_items
    groups = _group_items(all_items, category)

    # 低价警示（与搜索页同规则）
    for g in groups:
        plats = g.get('platforms') or {}
        ps = [p['actualPrice'] for p in plats.values() if p.get('actualPrice')]
        if len(ps) >= 2 and min(ps) < (sum(ps) / len(ps)) * 0.7:
            g['low_price_warning'] = True

    subsidies = find_subsidies(keyword, category)
    return {'keyword': keyword, 'category': category, 'groups': groups,
            'tb_count': len(tb_items) + len(tb_full), 'pdd_count': len(pdd_items),
            'jd_count': len(jd_items), 'vip_count': len(vip_items),
            'subsidies': subsidies}

# ========== AI 建议面板（R1，WorkBuddy 4 段模板）==========

ADVICE_SYSTEM = """你是购物比价顾问。根据给定的商品对比数据，输出 4 段建议：
【当前位】当前各平台价格（含券/国补后）
【历史】数据积累期内的最低价（注意：如果记录天数很少，要说明"数据积累中"）
【判断】偏低位 / 绝对低点 / 偏高位 / 高位
【行动】刚需→建议平台+价格；不急→心理价位建议+到价提醒
要求：只输出这 4 段，简洁大白话，每段 1-2 行。"""

def build_advice_input(keyword: str, group: dict, subsidies: list, history_rows: list) -> str:
    """组装给 R1 的结构化数据"""
    lines = [f'商品: {keyword}']
    for p, it in group.get('platforms', {}).items():
        lines.append(f'- {p}: ¥{it.get("actualPrice")}'
                     + (f'（券¥{it.get("couponPrice") or it.get("coupon_amount") or 0}）' if it.get('couponPrice') or it.get('coupon_amount') else '')
                     + (f' 原价¥{it.get("originalPrice")}' if it.get('originalPrice') else ''))
    if subsidies:
        for s in subsidies:
            lines.append(f'- 政策[{s["category"]}]: {s["requirements"]}'
                         + (f'（限价{s["max_price"]}内）' if s.get('max_price') else ''))
    if history_rows:
        prices = [h['price'] for h in history_rows]
        lines.append(f'- 历史记录: {len(prices)} 次，最低 ¥{min(prices)}，当前价 ¥{prices[0]}，最早记录 {history_rows[-1]["queried_at"][:10]}')
    else:
        lines.append('- 历史记录: 暂无（价格随查询自动积累）')
    return '\n'.join(lines)

def _call_llm_retry(user_text: str, model: str, system: str, max_tokens: int, timeout: int = 120, retries: int = 2) -> str:
    """调 DeepSeek，带指数退避重试（WorkBuddy P1-2）"""
    body = json.dumps({
        'model': model,
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user_text},
        ],
        'max_tokens': max_tokens,
        'temperature': 0.3,
        'reasoning_effort': 'max' if model == 'deepseek-v4-pro' else None,
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    })
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return data['choices'][0]['message']['content']
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(5 * (2 ** attempt))  # 指数退避：5s → 10s
    raise last_err


def gen_advice(keyword: str, group: dict, subsidies: list, history_rows: list) -> str:
    """AI 建议面板（V4-Pro 思考模式；失败给降级文案不崩，WorkBuddy P1-2）"""
    if not API_KEY:
        return '【当前位】无法分析（未配置 API Key）\n【历史】-\n【判断】-\n【行动】-'
    user_text = build_advice_input(keyword, group, subsidies, history_rows)
    try:
        return _call_llm_retry(user_text, 'deepseek-v4-pro', ADVICE_SYSTEM, 800)
    except Exception as e:
        print(f'[advice] 生成失败: {str(e)[:80]}')
        return f'【当前位】AI 建议暂时不可用（{str(e)[:40]}），请稍后再试\n【历史】-\n【判断】-\n【行动】-'

# ========== 内容摘要（博主评测一句话）==========

def content_summary(keyword: str) -> dict:
    """相关内容摘要：条数 + 平均可信度 + 高频词（简单规则，不调 LLM）"""
    try:
        r = read_content_items(keyword)
    except Exception:
        return {'count': 0, 'avg_score': 0, 'platforms': ''}
    items = r.get('items', [])
    if not items:
        return {'count': 0, 'avg_score': 0, 'platforms': ''}
    plats = {}
    for it in items:
        plats[it['type']] = plats.get(it['type'], 0) + 1
    avg = sum(it.get('score') or 0 for it in items) / len(items)
    names = {'bili': 'B站', 'xhs': '小红书', 'tieba': '贴吧'}
    plat_str = '｜'.join(f"{names.get(k, k)} {v}条" for k, v in plats.items())
    return {'count': len(items), 'avg_score': round(avg, 1), 'platforms': plat_str}
