import re
# app.py - Go购网页版 v1.0（雏形）
# 运行: python src/app.py  → 浏览器打开 http://localhost:8000
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
import asyncio
from fastapi.responses import StreamingResponse
import json as _json

from api_client import search_goods, search_pdd, value_score
from llm_parse import parse_intent, generate_options
from content_reader import read_content_items

def search_taobao_full(keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False) -> list:
    """淘宝全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import tb_search
        items = tb_search.search_taobao(keyword, max_items=max_items, page=page)
        for it in items:
            if 'actualPrice' not in it and it.get('price') is not None:
                it['actualPrice'] = it['price']
            it['monthSales'] = it.get('sales') or it.get('real_sales') or 0
            it['shopName'] = it.get('shop_name') or it.get('shop') or ''
            it['title'] = it.get('title', '')
            # platform 已由 tb_search 统一返回 'tb'（WorkBuddy P2-1：删除死代码覆写）
            it['_source'] = 'browser'
        return items
    except Exception as e:
        from errors import CaptchaError
        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f'[tb_full] 验证码，跳过（{str(e)[:40]}）')
            return []
        print(f'[tb_full] 失败: {str(e)[:80]}')
        return []

def search_jd_full(keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False) -> list:
    """京东全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import jd_search
        items = jd_search.search_jd(keyword, max_items=max_items, page=page)
        for it in items:
            if 'actualPrice' not in it and it.get('price') is not None:
                it['actualPrice'] = it['price']
            it['monthSales'] = it.get('sales') or 0
            it['shopName'] = it.get('shop') or ''
            it['title'] = it.get('title', '')
            it['platform'] = 'jd'
            it['_source'] = 'browser'
        return items
    except Exception as e:
        from errors import CaptchaError
        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f'[jd_full] 验证码，跳过（{str(e)[:40]}）')
            return []
        print(f'[jd_full] 失败: {str(e)[:80]}')
        return []

def search_vip_full(keyword: str, page: int = 1, max_items: int = 8) -> list:
    """唯品会全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice"""
    try:
        import vip_search
        items = vip_search.search_vip(keyword, max_items=max_items, page=page)
        for it in items:
            if 'actualPrice' not in it and it.get('price') is not None:
                it['actualPrice'] = it['price']
            it['monthSales'] = it.get('sales') or 0
            it['shopName'] = it.get('shop') or ''
            it['title'] = it.get('title', '')
            it['platform'] = 'vip'
            it['_source'] = 'browser'
        return items
    except Exception as e:
        print(f'[vip_full] 失败: {str(e)[:80]}')
        return []

def search_pdd_full(keyword: str, page: int = 1, max_items: int = 8, propagate_captcha: bool = False) -> list:
    """拼多多全量搜索（慢通道，浏览器 H5），失败返回空；字段统一 actualPrice
    propagate_captcha=True：验证码异常向上抛（采集层用于暂停该词）"""
    try:
        import pdd_search
        items = pdd_search.search_pdd(keyword, max_items=max_items, page=page)
        for it in items:
            if 'actualPrice' not in it and it.get('price') is not None:
                it['actualPrice'] = it['price']
            it['monthSales'] = it.get('sales') or 0
            it['shopName'] = it.get('shop') or ''
            it['title'] = it.get('title', '')
            it['platform'] = 'pdd'
            it['_source'] = 'browser'
        return items
    except Exception as e:
        from errors import CaptchaError
        if isinstance(e, CaptchaError):
            if propagate_captcha:
                raise
            print(f'[pdd_full] 验证码，跳过（{str(e)[:40]}）')
            return []
        print(f'[pdd_full] 失败: {str(e)[:80]}')
        return []
from score import score_content
from price_trap import detect_trap
from matcher import parse_items, group_by_sku, ADAPTERS
from db import init_db, get_conn, save_search_result, save_manual_price, find_manual_prices, add_watch, list_watches, check_watches, find_subsidies, upsert_product_item, query_items, stats_items, list_recommendations

app = FastAPI(title='Go购')
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
app.mount('/static', StaticFiles(directory=os.path.join(templates_dir, 'static')), name='static')

@app.middleware('http')
async def no_cache(request, call_next):
    resp = await call_next(request)
    if request.url.path.endswith(('.html', '/')) or not request.url.path:
        resp.headers['Cache-Control'] = 'no-store'
    return resp
templates = Jinja2Templates(directory=templates_dir)

CATEGORIES = ['', '服饰', '食品', '日用百货', '数码家电']

@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, 'index.html', {'categories': CATEGORIES})

@app.get('/search_bili')
def search_bili_api(keyword: str = ''):
    import subprocess, glob, json, os, time

    # 1. 确保 Edge CDP 在跑（9222）
    import urllib.request
    cdp_ok = False
    try:
        urllib.request.urlopen('http://127.0.0.1:9222/json/version', timeout=3)
        cdp_ok = True
    except Exception:
        pass
    if not cdp_ok:
        edge = next((p for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                                   r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
                      if os.path.exists(p)), None)
        subprocess.Popen([edge,
                          '--remote-debugging-port=9222',
                          '--user-data-dir=' + os.path.expanduser('~/mc_edge_profile'),
                          'about:blank'], creationflags=0x08000000)
        time.sleep(5)

    # 2. 先读已有 jsonl（复用 read_content_items：过滤+均衡+可信度打分+套路检测）
    mc_dir = os.path.expanduser('~/mc_ref')
    cached = read_content_items(keyword)
    if len(cached.get('items', [])) >= 5:
        return cached

    # 3. 缓存不足才调 MediaCrawler（uv 路径）
    uv = os.path.expanduser(r'~/AppData/Local/Programs/Python/Python314/Scripts/uv.exe')
    env = dict(os.environ, PATH=os.path.dirname(uv) + ';' + os.environ.get('PATH', ''))
    try:
        subprocess.run([uv, 'run', 'main.py', '--platform', 'bili', '--type', 'search',
                        '--keywords', keyword],
                       cwd=mc_dir, env=env, timeout=150,
                       capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pass

    # 4. 抓取后重读（含三平台 + 打分）
    return read_content_items(keyword)

@app.get('/search_tb')
def search_tb_api(keyword: str = ''):
    import tb_search
    items = tb_search.search_taobao(keyword, max_items=10)
    return {'items': items}

@app.get('/search_jd')
def search_jd_api(keyword: str = ''):
    import jd_search
    items = jd_search.search_jd(keyword, max_items=8)
    return {'items': items}

@app.get('/search_pdd')
def search_pdd_api(keyword: str = ''):
    """拼多多浏览器补搜（v6.1 打通）"""
    import pdd_search
    items = pdd_search.search_pdd(keyword, max_items=10)
    return {'items': items}

@app.get('/history')
def history(platform: str = 'tb', item_id: str = ''):
    import sqlite3
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db'))
    conn.row_factory = sqlite3.Row
    rows = conn.execute('''
        SELECT title, price, coupon_amount, queried_at FROM price_history
        WHERE platform=? AND item_id=? ORDER BY queried_at DESC LIMIT 30
    ''', (platform, item_id)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if result:
        prices = [r['price'] for r in result]
        result.append({'summary': {'lowest': min(prices), 'current': result[0]['price'],
                                   'count': len(result)}})
    return result

@app.get('/submit', response_class=HTMLResponse)
def submit_page(request: Request):
    return templates.TemplateResponse(request, 'submit.html', {})

@app.post('/submit', response_class=HTMLResponse)
def submit_post(request: Request,
                keyword: str = Form(...), title: str = Form(...),
                platform: str = Form('other'), shop_name: str = Form(''),
                price: float = Form(...), url: str = Form(''), note: str = Form('')):
    if price <= 0 or price > 9999999:  # AI审查建议：输入验证
        return templates.TemplateResponse(request, 'submit.html', {'success': False, 'keyword': keyword, 'msg': '价格需为正数'})
    init_db()
    save_manual_price(keyword.strip(), title.strip(), platform, shop_name.strip(), price, url.strip(), note.strip())
    return templates.TemplateResponse(request, 'submit.html', {'success': True, 'keyword': keyword})

@app.post('/watch')
def watch_add(title: str = Form(...), platform: str = Form(''), item_id: str = Form(''),
              current_price: float = Form(...), target_price: float = Form(...)):
    init_db()
    add_watch(title[:80], platform, item_id, current_price, target_price)
    return {'ok': True}

@app.get('/watches', response_class=HTMLResponse)
def watches_page(request: Request):
    init_db()
    rows = list_watches()
    hits = check_watches()
    return templates.TemplateResponse(request, 'watches.html',
                                      {'watches': rows, 'hits': hits})

# ========== v4 商品库 ==========

@app.get('/api/items')
def api_items(keyword: str = '', category: str = '', platform: str = '',
             min_price: float = 0, max_price: float = 0,
             sort: str = 'price_asc', page: int = 1, size: int = 30):
    """商品库查询接口"""
    init_db()
    return query_items(keyword.strip(), category, platform, min_price, max_price,
                       sort, max(1, page), min(max(1, size), 100))

@app.get('/api/stats')
def api_stats():
    """商品库统计接口"""
    init_db()
    return stats_items()

@app.get('/items', response_class=HTMLResponse)
def items_page(request: Request):
    """商品库浏览页"""
    init_db()
    stats = stats_items()
    return templates.TemplateResponse(request, 'items.html', {'stats': stats, 'categories': CATEGORIES})

@app.post('/api/extract')
async def api_extract(keyword: str = Form('')):
    """内容→商品抽取（DeepSeek）→ recommendations 入库"""
    from extract_products import run_extract
    result = await asyncio.to_thread(run_extract, keyword.strip())
    return result

@app.get('/api/recommendations')
def api_recommendations(limit: int = 50):
    """博主推荐列表（按商品聚合）"""
    init_db()
    return {'items': list_recommendations(limit)}

@app.post('/api/deep_crawl')
async def api_deep_crawl(keyword: str = Form(...), category: str = Form(''), pages: int = Form(3)):
    """深度采集：淘宝+京东浏览器翻页采集（用户主动触发，低频约束）→ 沉淀入库"""
    keyword = keyword.strip()
    if not keyword:
        return {'ok': False, 'msg': '请输入关键词'}
    pages = min(max(pages, 1), 5)
    results = {'tb': [], 'jd': [], 'vip': []}
    # 淘宝翻页（tb_search 已支持 page）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_taobao_full, keyword, p)
            results['tb'] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f'[deep_crawl tb] {str(e)[:80]}')
    # 京东翻页（含 30s 低频约束，3 页约 1.5 分钟）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_jd_full, keyword, p)
            results['jd'] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f'[deep_crawl jd] {str(e)[:80]}')
    # 唯品会翻页（12-20s 随机抖动）
    try:
        for p in range(1, pages + 1):
            items = await asyncio.to_thread(search_vip_full, keyword, p)
            results['vip'] += items
            if len(items) < 8:
                break
    except Exception as e:
        print(f'[deep_crawl vip] {str(e)[:80]}')
    # 入库
    conn = get_conn()
    added = 0
    for plat, items in results.items():
        for it in items:
            it['_source'] = 'browser'
            if upsert_product_item(conn, it, category or ''):
                added += 1
    conn.commit()
    conn.close()
    total = sum(len(v) for v in results.values())
    return {'ok': True, 'msg': f'采集完成：淘宝 {len(results["tb"])} + 京东 {len(results["jd"])} + 唯品会 {len(results["vip"])} = {total} 条，入库 {added} 条'}

@app.get('/search_sse')
async def search_sse(keyword: str = '', category: str = '', guide_round: int = 0, mode: str = 'live', user_name: str = ''):
    """搜索 SSE。mode=history 看以往数据（读库秒出）；mode=live 实时报告（绕过缓存现场抓）"""
    async def gen():
        nonlocal keyword, category
        def sse(data):
            return 'data: ' + _json.dumps(data, ensure_ascii=False) + chr(10) + chr(10)
        def step(name, status):
            # 步骤可视化（Agent Part 借鉴：pending/running/completed）
            return sse({'type': 'step', 'step': name, 'status': status})
        try:
            # v6 用户记忆：记录本次搜索（教材3章）
            try:
                from db import log_search
                log_search(user_name.strip(), keyword.strip(), category)
            except Exception:
                pass
            # ===== 📚 历史模式：只读商品库，零 API 零爬虫 =====
            if mode == 'history':
                yield step('查询商品库', 'running')
                yield sse({'type': 'progress', 'msg': '📚 历史模式：正在查询商品库...'})
                from db import query_items
                init_db()
                data = await asyncio.to_thread(query_items, keyword.strip(), category, '', 0, 0, 'price_asc', 1, 30)
                items = data.get('items', [])
                groups = []
                for it in items:
                    groups.append({'key': (it.get('title') or '')[:30], 'count': 1,
                                   'platforms': [{'platform': it.get('platform'), 'title': it.get('title'),
                                                  'actualPrice': it.get('price'), 'shopName': it.get('shop_name'),
                                                  'url': it.get('url'), 'goodsId': it.get('item_id'),
                                                  'monthSales': it.get('sales')}],
                                   'best': {'actualPrice': it.get('price')}})
                content = await asyncio.to_thread(read_content_items, keyword)
                subsidies = await asyncio.to_thread(find_subsidies, keyword, category)
                yield step('查询商品库', 'done')
                yield sse({'type': 'done', 'keyword': keyword, 'category': category,
                           'groups': groups, 'total': len(items),
                           'tb_count': 0, 'pdd_count': 0, 'manual_count': 0,
                           'content': content, 'slow_count': 0, 'options': [],
                           'subsidies': subsidies, 'mode': 'history'})
                return

            # ===== ⚡ 实时模式：现场抓取 =====
            yield sse({'type': 'progress', 'msg': '⚡ 实时模式：绕过缓存现场抓取...'})
            # 意图解析（对话式输入支持）
            yield step('理解需求', 'running')
            intent = await asyncio.to_thread(parse_intent, keyword)
            yield step('理解需求', 'done')
            search_kw = intent.get('keyword') or keyword
            search_cat = intent.get('category') or category
            if search_kw != keyword or search_cat != category:
                yield sse({'type': 'progress', 'msg': f'🤖 明白了：搜索「{search_kw}」' + (f'（{search_cat}）' if search_cat else '')})
            keyword, category = search_kw, search_cat
            # 快通道：API 并行（v5.2 加唯品会）
            yield step('搜索淘宝/拼多多/唯品会', 'running')
            yield sse({'type': 'progress', 'msg': f'⏳ 正在并行搜索淘宝 + 拼多多 + 唯品会（实时抓取）...'})
            from api_client import search_vip
            tb_items, pdd_items, vip_items = await asyncio.gather(
                asyncio.to_thread(search_goods, keyword, category or None, 1, 20, False),
                asyncio.to_thread(search_pdd, keyword, 1, 20, False),
                asyncio.to_thread(search_vip, keyword, 1, 20, False),
            )
            # v5.2 偏好：排除平台过滤（"不要拼多多"自动记住）
            from db import get_excluded_platforms
            excluded = get_excluded_platforms()
            if excluded:
                before = len(tb_items) + len(pdd_items) + len(vip_items)
                tb_items = [i for i in tb_items if i.get('platform') not in excluded]
                pdd_items = [i for i in pdd_items if i.get('platform') not in excluded]
                vip_items = [i for i in vip_items if i.get('platform') not in excluded]
                after = len(tb_items) + len(pdd_items) + len(vip_items)
                if after != before:
                    yield sse({'type': 'progress', 'msg': f'🔕 已按你的偏好排除：{"、".join(excluded)}'})
            all_items = tb_items + pdd_items + vip_items

            # 慢通道自动补搜：快通道结果少（<5 条）→ 全网补搜；或拼多多 API 被限（返回空）→ 拼多多浏览器兜底
            slow_items = []
            if len(all_items) < 5:
                yield sse({'type': 'progress', 'msg': f'快通道结果少（{len(all_items)} 条），正在全网补搜（淘宝全量+京东+唯品会+拼多多）...'})
                tb_full, jd_full, vip_full, pdd_full = await asyncio.gather(
                    asyncio.to_thread(search_taobao_full, keyword, 15),
                    asyncio.to_thread(search_jd_full, keyword, 15),
                    asyncio.to_thread(search_vip_full, keyword, 15),
                    asyncio.to_thread(search_pdd_full, keyword, 15),
                )
                slow_items = tb_full + jd_full + vip_full + pdd_full
                all_items = all_items + slow_items
                # 2026-08-10 过滤服务类/租赁类商品（云渲染/远程渲染/出租/小时计费等非实物）
                service_kw = ('远程渲染', '云渲染', '渲染农场', '云电脑', '出租', '租用', '小时计费',
                              '显卡租赁', 'gpu租赁', '云服务', '按小时', '代练', '充值', '会员')
                before = len(all_items)
                all_items = [it for it in all_items
                             if not any(k in (it.get('title') or '') for k in service_kw)]
                if len(all_items) != before:
                    yield sse({'type': 'progress', 'msg': f'🧹 已过滤 {before-len(all_items)} 条服务/租赁类商品'})
                yield sse({'type': 'progress', 'msg': f'✅ 全网补搜完成（+{len(slow_items)} 条），正在合并比价...'})
            elif not pdd_items:
                # 拼多多 API 被限流/失败 → 浏览器通道兜底（2026-08-10 实测 duoId 被限）
                yield sse({'type': 'progress', 'msg': '拼多多 API 暂时受限，改用浏览器补拼多多...'})
                slow_items = await asyncio.to_thread(search_pdd_full, keyword)
                all_items = tb_items + pdd_items + vip_items + slow_items
                yield sse({'type': 'progress', 'msg': f'✅ 全网补搜完成（+{len(slow_items)} 条），正在合并比价...'})
            else:
                yield sse({'type': 'progress', 'msg': f'✅ 淘宝 {len(tb_items)} 条 + 拼多多 {len(pdd_items)} 条 + 唯品会 {len(vip_items)} 条，正在 SKU 分组...'})

            yield step('搜索平台', 'done')
            yield step('比价合并', 'running')
            init_db()
            groups = []
            if category and category in ADAPTERS and ADAPTERS[category]:
                parsed = parse_items(all_items, category)
                grouped = group_by_sku(parsed, category)
                for key, items in grouped.items():
                    if not key or key == '未解析':
                        continue
                    by_platform = {}
                    for it in items:
                        it['value_score'] = value_score(it)
                        p = it.get('platform', '?')
                        if p not in by_platform or it['actualPrice'] < by_platform[p]['actualPrice']:
                            by_platform[p] = it
                    best = min(by_platform.values(), key=lambda x: x['actualPrice'])
                    groups.append({'key': key, 'count': len(items),
                                   'platforms': sorted(by_platform.values(), key=lambda x: x['actualPrice']),
                                   'best': best})
                groups.sort(key=lambda g: g['best']['actualPrice'])
            else:
                for it in all_items[:20]:
                    groups.append({'key': it['title'][:30], 'count': 1, 'platforms': [it], 'best': it})

            # v5.2 低价警示（WorkBuddy 提级 P0）：组内最低价 < 均价 70% → 防二手/仿品/单只
            from matcher import annotate_group
            for g in groups:
                annotate_group(g, category or '')
                plats = g.get('platforms') or []
                if isinstance(plats, list) and len(plats) >= 2:
                    ps = [p['actualPrice'] for p in plats if p.get('actualPrice')]
                    if len(ps) >= 2 and min(ps) < (sum(ps) / len(ps)) * 0.7:
                        g['low_price_warning'] = True

            manual_items = find_manual_prices(keyword)
            for m in manual_items:
                groups.append({'key': f'人工录入: {m["title"][:20]}', 'count': 1,
                               'platforms': [{'platform': m['platform'], 'title': m['title'],
                                              'actualPrice': m['price'], 'originalPrice': None,
                                              'shopName': m['shop_name'] + '（人工录入）', 'url': m['url']}],
                               'best': None})

            conn = get_conn()
            for it in all_items:
                save_search_result(conn, it, category or '未分类')
                upsert_product_item(conn, it, category or '')
            conn.commit()
            conn.close()

            # 对话式导购：触发条件（WorkBuddy 审核）——先导购后补搜
            options = []
            prices = [g['best']['actualPrice'] for g in groups if g.get('best') and g['best'].get('actualPrice')]
            has_model_num = bool(re.search(r'\d{2,}', keyword))
            # v5.2 需求三要素追问（WorkBuddy P1）：宽泛品类词才问，带"直接搜→"跳过
            if (guide_round == 0 and search_cat and not has_model_num and len(groups) >= 3):
                yield sse({'type': 'need', 'q': '💸 大概什么预算？（可跳过）',
                           'options': [
                               {'label': '💸 ≤3000', 'value': '3000'},
                               {'label': '💸 3000-8000', 'value': '8000'},
                               {'label': '💸 8000+', 'value': '99999'},
                               {'label': '⚡ 直接搜→', 'value': 'skip'},
                           ]})
            if (guide_round < 1 and len(groups) > 3 and len(all_items) >= 8
                    and prices and max(prices) / max(min(prices), 1) > 2.0
                    and not has_model_num):
                yield sse({'type': 'progress', 'msg': '📋 结果较多，正在生成导购选项...'})
                options = await asyncio.to_thread(generate_options, keyword, groups)
                if options:
                    yield sse({'type': 'guide', 'options': options})

            yield step('比价合并', 'done')
            yield step('内容联动', 'running')
            content = await asyncio.to_thread(read_content_items, keyword)
            # v5.2 来源受限标注（购物研究助手案例）：内容数据 <5 条时诚实标注
            content_limited = len(content.get('items', [])) < 5
            subsidies = await asyncio.to_thread(find_subsidies, keyword, search_cat)
            yield step('内容联动', 'done')
            yield sse({'type': 'done', 'keyword': keyword, 'category': category,
                       'groups': groups, 'total': len(all_items),
                       'tb_count': len(tb_items), 'pdd_count': len(pdd_items),
                       'vip_count': len(vip_items),
                       'manual_count': len(manual_items), 'content': content,
                       'content_limited': content_limited,
                       'slow_count': len(slow_items), 'options': options,
                       'subsidies': subsidies, 'mode': 'live'})
        except Exception as e:
            yield sse({'type': 'error', 'msg': str(e)[:200]})

    return StreamingResponse(gen(), media_type='text/event-stream')

# ===== 遗留入口：前端已全部改走 /search_sse（SSE 版含慢通道补搜/导购/内容联动）=====
# 此 POST /search 保留供直接调用/测试，逻辑与 SSE 版存在分叉，改动优先改 SSE 版
@app.post('/search', response_class=HTMLResponse)
def search(request: Request, keyword: str = Form(...), category: str = Form('')):
    keyword = keyword.strip()
    if not keyword:
        return templates.TemplateResponse(request, 'index.html', {'categories': CATEGORIES, 'error': '请输入商品名称'})

    # 意图解析（对话式输入支持）
    intent = parse_intent(keyword)
    keyword = intent.get('keyword') or keyword
    category = intent.get('category') or category

    init_db()
    # 双平台搜索（带缓存）
    tb_items = search_goods(keyword, category or None)
    pdd_items = search_pdd(keyword)
    all_items = tb_items + pdd_items

    # SKU 分组
    groups = []
    if category and category in ADAPTERS and ADAPTERS[category]:
        parsed = parse_items(all_items, category)
        grouped = group_by_sku(parsed, category)
        for key, items in grouped.items():
            if not key or key == '未解析':
                continue
            by_platform = {}
            for it in items:
                it['value_score'] = value_score(it)
                p = it.get('platform', '?')
                if p not in by_platform or it['actualPrice'] < by_platform[p]['actualPrice']:
                    by_platform[p] = it
            best = min(by_platform.values(), key=lambda x: x['actualPrice'])
            groups.append({'key': key, 'count': len(items),
                           'platforms': sorted(by_platform.values(), key=lambda x: x['actualPrice']),
                           'best': best})
        groups.sort(key=lambda g: g['best']['actualPrice'])
    else:
        for it in all_items[:20]:
            groups.append({'key': it['title'][:30], 'count': 1, 'platforms': [it], 'best': it})

    # 人工录入结果合并（众包补盲区）
    manual_items = find_manual_prices(keyword)
    for m in manual_items:
        groups.append({'key': f'人工录入: {m["title"][:20]}', 'count': 1,
                       'platforms': [{'platform': m['platform'], 'title': m['title'],
                                      'actualPrice': m['price'], 'originalPrice': None,
                                      'shopName': m['shop_name'] + '（人工录入）', 'url': m['url']}],
                       'best': None})

    # 存库
    conn = get_conn()
    for it in all_items:
        save_search_result(conn, it, category or '未分类')
        upsert_product_item(conn, it, category or '')
    conn.commit()
    conn.close()

    # 国补/优惠标注
    subsidies = find_subsidies(keyword, category)

    return templates.TemplateResponse(request, 'result.html', {
        'keyword': keyword, 'category': category,
        'groups': groups[:10], 'total': len(all_items),
        'tb_count': len(tb_items), 'pdd_count': len(pdd_items), 'manual_count': len(manual_items),
        'subsidies': subsidies,
    })

# ========== v6 多用户（角色切换，WorkBuddy 定案：不登录，localStorage）==========

@app.get('/api/family')
def api_family():
    """家庭品类库（15 细品类 → 大品类 + 采集词）"""
    from db import FAMILY_CATEGORIES
    return {'categories': [{'name': sub, 'big': big, 'words': words}
                           for sub, big, words in FAMILY_CATEGORIES]}

@app.post('/api/family_tasks')
async def api_family_tasks(categories: str = Form('')):
    """把用户勾选的品类的采集词加入采集计划（幂等）
    categories: 逗号分隔的细品类名，如 '女士服装,护肤品'；空=全部"""
    from db import FAMILY_CATEGORIES, get_conn
    conn = get_conn()
    added = 0
    pick = [c.strip() for c in categories.replace('，', ',').split(',') if c.strip()] if categories.strip() else []
    for sub, big, words in FAMILY_CATEGORIES:
        if pick and sub not in pick:
            continue
        for w in words:
            cur = conn.execute('''
                INSERT OR IGNORE INTO crawl_tasks (keyword, category, source) VALUES (?,?, 'family')
            ''', (w, big))
            added += cur.rowcount
    conn.commit(); conn.close()
    return {'ok': True, 'msg': f'已把 {len(pick) if pick else 15} 个品类的采集词加入计划（+{added} 个新词）'}

@app.post('/api/search_log')
async def api_search_log(user_name: str = Form(''), keyword: str = Form(''), category: str = Form('')):
    """v6 用户记忆：记录一次搜索（教材3章）"""
    from db import log_search
    if keyword.strip():
        log_search(user_name.strip(), keyword.strip(), category)
    return {'ok': True}

@app.get('/api/profile')
def api_profile(user: str = ''):
    """v6 用户画像：最近搜索词 + 品类分布"""
    from db import user_profile
    return user_profile(user.strip())

@app.post('/api/resume_tasks')
async def api_resume_tasks():
    """经验学习：手动恢复暂停的采集任务"""
    from db import resume_crawl_tasks
    n = resume_crawl_tasks()
    return {'ok': True, 'msg': f'已恢复 {n} 个暂停任务'}

# ========== v7 陪你出发（AI 购物向导）==========

@app.get('/guide', response_class=HTMLResponse)
def guide_page(request: Request):
    """陪你出发：聊天式购物向导"""
    return templates.TemplateResponse(request, 'guide.html', {'categories': CATEGORIES})

@app.get('/wander', response_class=HTMLResponse)
def wander_page(request: Request):
    """购物漫游：无目标浏览（多路召回推荐流）"""
    return templates.TemplateResponse(request, 'wander.html', {})

@app.post('/api/chat')
async def api_chat(session_id: str = Form(''), user_name: str = Form(''), message: str = Form('')):
    """陪你出发：一轮聊天"""
    import uuid
    from guide import chat
    sid = session_id.strip() or str(uuid.uuid4())
    if not message.strip():
        return {'ok': False, 'msg': '说点什么吧'}
    result = await asyncio.to_thread(chat, sid, message.strip(), user_name.strip())
    return {'ok': True, 'session_id': sid, **result}

# ========== v7 AI 费用统计（Agent Part 借鉴）==========

@app.get('/api/usage')
def api_usage():
    """本月 AI 费用统计"""
    from llm_usage import month_cost
    return month_cost()

# ========== v7 购物漫游（推荐闭环）==========

@app.get('/api/wander')
def api_wander(user: str = '', size: int = 12):
    """购物漫游：按画像推荐（返回卡片 + 推荐理由）"""
    from wander import wander_recommend
    from db import get_conn
    # 已不喜欢/已收藏的排除
    conn = get_conn()
    rows = conn.execute("SELECT item_id FROM wander_feedback WHERE user_name=? AND action IN ('dislike','fav')", (user or '',)).fetchall()
    conn.close()
    exclude = [r['item_id'] for r in rows if r['item_id']]
    items = wander_recommend(user or '', min(max(size, 6), 30), exclude)
    cards = []
    for it in items:
        cards.append({
            'item_id': it.get('item_id'), 'platform': it.get('platform'),
            'title': (it.get('title') or '')[:80], 'price': it.get('price'),
            'original_price': it.get('original_price'), 'shop': it.get('shop_name'),
            'sales': it.get('sales'), 'category': it.get('category'), 'url': it.get('url'),
            'img': it.get('img'),
            'reason': _wander_reason(it, user or ''),
        })
    return {'ok': True, 'cards': cards}


def _wander_reason(it: dict, user: str) -> str:
    """漫游卡片推荐理由（可解释性）"""
    from guide import get_profile
    cats = get_profile(user).get('categories') or []
    cat = it.get('category') or ''
    if cat and cat in cats:
        return f'因为你最近在看{cat}'
    if it.get('sales') and it['sales'] > 10000:
        return '🔥 大家都在买'
    return '✨ 发现一个你可能没看过的'

@app.post('/api/wander_feedback')
async def api_wander_feedback(user: str = Form(''), item_id: str = Form(''), action: str = Form('dislike')):
    """漫游反馈：dislike=不感兴趣 / fav=收藏"""
    from db import get_conn
    conn = get_conn()
    conn.execute("DELETE FROM wander_feedback WHERE user_name=? AND item_id=? AND action=?",
                 (user or '', item_id, action))
    conn.execute('INSERT INTO wander_feedback (user_name, item_id, action) VALUES (?,?,?)',
                 (user or '', item_id, action))
    conn.commit(); conn.close()
    return {'ok': True}

@app.get('/api/wander_favs')
def api_wander_favs(user: str = ''):
    """我的收藏列表"""
    from db import get_conn
    conn = get_conn()
    rows = conn.execute('''SELECT f.item_id, p.title, p.price, p.platform, p.shop_name, p.url
        FROM wander_feedback f LEFT JOIN product_items p ON p.item_id = f.item_id
        WHERE f.user_name=? AND f.action='fav' ORDER BY f.id DESC''', (user or '',)).fetchall()
    conn.close()
    return {'items': [dict(r) for r in rows]}

# ========== v7 评估埋点（建议采纳率闭环）==========

@app.post('/api/event')
async def api_event(scene: str = Form(''), keyword: str = Form(''), action: str = Form('shown'), user_name: str = Form(''), variant: str = Form('a')):
    """记录行为事件：shown=展示 / adopt=采纳（点击去购买/去比价），variant 供 A-B 统计"""
    from db import get_conn, init_db
    init_db()  # 确保表存在
    conn = get_conn()
    conn.execute('INSERT INTO advice_events (scene, keyword, action, user_name, variant) VALUES (?,?,?,?,?)',
                 (scene[:20], (keyword or '')[:60], action, user_name[:30], variant[:4]))
    conn.commit(); conn.close()
    return {'ok': True}

@app.get('/api/advice_stats')
def api_advice_stats():
    """建议采纳率统计：adopt/shown（纯行为数据，零 LLM 成本）"""
    from db import get_conn, init_db
    init_db()  # 确保表存在
    conn = get_conn()
    shown = conn.execute("SELECT COUNT(*) FROM advice_events WHERE action='shown'").fetchone()[0]
    adopt = conn.execute("SELECT COUNT(*) FROM advice_events WHERE action='adopt'").fetchone()[0]
    by_scene = conn.execute('''SELECT scene, COUNT(*) n FROM advice_events WHERE action='adopt'
        GROUP BY scene ORDER BY n DESC''').fetchall()
    # v1.0 A-B：按 variant 分别统计采纳率
    by_variant = conn.execute('''SELECT variant,
        SUM(CASE WHEN action='shown' THEN 1 ELSE 0 END) shown,
        SUM(CASE WHEN action='adopt' THEN 1 ELSE 0 END) adopt
        FROM advice_events GROUP BY variant''').fetchall()
    conn.close()
    rate = round(adopt / shown * 100, 1) if shown else 0
    ab = {}
    for r in by_variant:
        s, a = r['shown'], r['adopt']
        ab[r['variant']] = {'shown': s, 'adopt': a, 'rate': round(a / s * 100, 1) if s else 0}
    return {'shown': shown, 'adopt': adopt, 'adopt_rate': rate,
            'by_scene': [dict(r) for r in by_scene], 'ab': ab}

@app.get('/api/price_prediction')
def api_price_prediction(platform: str = '', item_id: str = ''):
    """降价预测（纯规则：斜率+低点+波动，零 LLM，小布方案）"""
    from db import get_conn
    from price_trap import predict_price
    if not item_id:
        return {'ok': False, 'msg': '缺少商品 ID'}
    conn = get_conn()
    rows = conn.execute('''SELECT price FROM price_history
        WHERE platform=? AND item_id=? ORDER BY queried_at ASC''', (platform, str(item_id))).fetchall()
    conn.close()
    prices = [r['price'] for r in rows if r['price'] and r['price'] > 1]
    return {'ok': True, **predict_price(prices)}

@app.get('/api/detail')
def api_detail(platform: str = '', id: str = ''):
    """商品详情（淘宝 get-goods-details；PDD/京东暂无详情接口则返回基本信息）"""
    from db import get_conn
    if not id:
        return {'ok': False, 'msg': '缺少商品 ID'}
    if platform == 'tb':
        from api_client import get_goods_details
        d = get_goods_details(id)
        if d:
            return {'ok': True, **d}
    if platform == 'pdd':
        from api_client import get_pdd_details
        d = get_pdd_details(id)
        if d:
            return {'ok': True, **d}
    # API 失败/不可用 → 回退商品库已有信息（保证详情总能用）
    conn = get_conn()
    row = conn.execute('SELECT title, shop_name, price, sales, url, img FROM product_items WHERE item_id=? LIMIT 1', (id,)).fetchone()
    conn.close()
    if row:
        return {'ok': True, 'title': row['title'], 'shop': row['shop_name'], 'img': row['img'],
                'sales': row['sales'], 'desc': '', 'fallback': True}
    return {'ok': False, 'msg': '未找到商品'}

@app.post('/api/spec_compare')
async def api_spec_compare(keyword: str = Form(''), category: str = Form(''), group_key: str = Form('')):
    """数码参数对比：同组商品用 DigitalMatcher 提取参数并排"""
    from compare import search_compare_slow
    from matcher import DigitalMatcher
    data = await search_compare_slow(keyword, category)
    group = next((g for g in data['groups'] if g['key'] == group_key), None)
    if not group:
        return {'ok': False, 'msg': '未找到该商品组'}
    items = []
    for p, it in group['platforms'].items():
        spec = DigitalMatcher.parse(str(it.get('title') or ''))
        cfg = spec.get('config') or {}
        items.append({'platform': p, 'price': it.get('actualPrice'), 'title': (it.get('title') or '')[:40],
                      'spec': {'型号': spec.get('series') or '-', 'GPU': cfg.get('gpu') or '-',
                               'CPU': cfg.get('cpu') or '-', '内存': cfg.get('ram') or '-',
                               '存储': cfg.get('storage') or '-'}})
    return {'ok': True, 'keyword': keyword, 'items': items[:4]}

@app.post('/api/debate')
async def api_debate(keyword: str = Form(''), category: str = Form(''), group_key: str = Form('')):
    """多视角辩论：三派各自点评（分角色 prompt）"""
    from compare import search_compare_slow, gen_debate
    data = await search_compare_slow(keyword, category)
    group = next((g for g in data['groups'] if g['key'] == group_key), None)
    if not group:
        return {'ok': False, 'msg': '未找到该商品组'}
    views = await asyncio.to_thread(gen_debate, keyword, group)
    return {'ok': True, 'views': views}

# ========== v8.5 热搜联想 + 相似推荐（大淘客现成接口）==========

@app.get('/api/hotwords')
def api_hotwords():
    """热搜榜（首页'大家正在搜'）"""
    from api_client import get_hot_words
    return {'words': get_hot_words()}

@app.get('/api/similar')
def api_similar(id: str = ''):
    """相似商品（猜你喜欢）"""
    from api_client import get_similar_goods
    items = get_similar_goods(id, 8) if id else []
    return {'items': items}

# ========== v8 邀请码（WorkBuddy 极简设计：一张表+两个页面）==========

@app.post('/api/invite_gen')
async def api_invite_gen(user_name: str = Form(''), categories: str = Form('')):
    """生成邀请码（管理员）：Go-xxxx 6 位，绑定角色名+品类"""
    import secrets
    from db import get_conn, init_db
    init_db()
    if not user_name.strip():
        return {'ok': False, 'msg': '请填角色名（如：妈妈）'}
    code = 'Go-' + secrets.token_hex(2).lower()
    conn = get_conn()
    conn.execute('INSERT INTO invite_codes (code, user_name, categories) VALUES (?,?,?)',
                 (code, user_name.strip()[:30], categories or '[]'))
    conn.commit(); conn.close()
    return {'ok': True, 'code': code, 'user_name': user_name.strip()}

@app.post('/api/invite_use')
async def api_invite_use(code: str = Form(''), device_id: str = Form('')):
    """亲戚端：输入邀请码 → 校验未用 → 返回角色信息 + 标记已用"""
    from db import get_conn, init_db
    init_db()
    code = code.strip()
    conn = get_conn()
    row = conn.execute('SELECT * FROM invite_codes WHERE code=?', (code,)).fetchone()
    if not row:
        conn.close()
        return {'ok': False, 'msg': '邀请码不存在，检查一下？'}
    if row['used_at']:
        conn.close()
        return {'ok': False, 'msg': '这个邀请码已被使用过了'}
    conn.execute("UPDATE invite_codes SET used_at=datetime('now','localtime'), used_by=? WHERE id=?",
                 (device_id[:50], row['id']))
    conn.commit(); conn.close()
    return {'ok': True, 'user_name': row['user_name'], 'categories': row['categories']}

@app.get('/api/invite_list')
def api_invite_list():
    """邀请码列表（管理页）"""
    from db import get_conn, init_db
    init_db()
    conn = get_conn()
    rows = conn.execute('SELECT code, user_name, categories, used_at, created_at FROM invite_codes ORDER BY id DESC LIMIT 20').fetchall()
    conn.close()
    return {'items': [dict(r) for r in rows]}

# ========== v5 采集引擎接口 ==========

@app.post('/api/crawl')
async def api_crawl(pages: int = Form(2), max_minutes: int = Form(480)):
    """启动一轮采集（后台任务，进度查 /api/crawl_status）。
    max_minutes: 硬性时长上限（默认 480 分钟 = 8 小时），到点自动停"""
    from crawl import run_crawl_round, get_progress
    if get_progress().get('running'):
        return {'ok': False, 'msg': '采集已在运行中，请稍候'}
    pages = min(max(pages, 1), 5)
    max_minutes = min(max(max_minutes, 10), 720)  # 10 分钟 ~ 12 小时
    asyncio.create_task(run_crawl_round(pages, max_seconds=max_minutes * 60))
    return {'ok': True, 'msg': f'采集已启动（每词翻 {pages} 页，最长跑 {max_minutes} 分钟，到点自动停）'}

@app.get('/api/crawl_status')
def api_crawl_status():
    """采集进度（前端轮询）"""
    from crawl import get_progress
    return get_progress()

@app.get('/api/crawl_tasks')
def api_crawl_tasks():
    """任务表（采集中心页）"""
    from db import list_crawl_tasks, crawl_stats
    init_db()
    return {'tasks': list_crawl_tasks(), 'stats': crawl_stats()}

@app.post('/api/crawl_add')
async def api_crawl_add(keyword: str = Form(''), category: str = Form('')):
    """手动加采集词（小白友好：只填词）"""
    from db import get_conn
    kw = keyword.strip()
    if not kw:
        return {'ok': False, 'msg': '请输入关键词'}
    conn = get_conn()
    cur = conn.execute('INSERT OR IGNORE INTO crawl_tasks (keyword, category, source) VALUES (?,?,?)',
                       (kw[:30], category or '', 'manual'))
    conn.commit(); conn.close()
    return {'ok': True, 'msg': '已加入采集计划' if cur.rowcount else '这个词已在计划里了'}

@app.post('/api/prefs')
async def api_prefs(prefs: str = Form('')):
    """偏好设置（v5.2）：逗号分隔排除平台，空=清除"""
    from db import set_user_pref, PREF_EXCLUDE_PLATFORMS
    PLAT_MAP = {'拼多多': 'pdd', '京东': 'jd', '淘宝': 'tb', '唯品会': 'vip',
                'pdd': 'pdd', 'jd': 'jd', 'tb': 'tb', 'vip': 'vip'}
    if not prefs.strip():
        set_user_pref(PREF_EXCLUDE_PLATFORMS, [])
        return {'ok': True, 'msg': '已清除排除平台'}
    plats = []
    for w in prefs.replace('，', ',').split(','):
        w = w.strip()
        if w in PLAT_MAP and PLAT_MAP[w] not in plats:
            plats.append(PLAT_MAP[w])
    if not plats:
        return {'ok': False, 'msg': '没认出来平台名，试试：拼多多/京东/淘宝/唯品会'}
    set_user_pref(PREF_EXCLUDE_PLATFORMS, plats)
    return {'ok': True, 'msg': '已记住：排除 ' + '、'.join(plats) + '（对话里说"不要拼多多"也能自动记住）'}

@app.get('/crawl', response_class=HTMLResponse)
def crawl_page(request: Request):
    """采集中心页"""
    return templates.TemplateResponse(request, 'crawl.html', {})

# ========== v3.5 对比页（Mode 2「帮我比」）==========

@app.get('/compare', response_class=HTMLResponse)
def compare_page(request: Request):
    """对比页入口"""
    return templates.TemplateResponse(request, 'compare.html', {'categories': CATEGORIES})

@app.post('/api/compare')
async def api_compare(keyword: str = Form(''), category: str = Form('')):
    """四平台搜索（快通道 + 京东/唯品会慢通道）+ SKU 合并 + 内容摘要"""
    from compare import search_compare_slow, parse_link, content_summary
    kw = keyword.strip()
    link_info = parse_link(kw)
    # 链接输入：提取平台+ID，用 ID 查不到详情就回退为关键词搜索
    if link_info:
        kw = re.sub(r'https?://\S+', '', kw).strip() or kw
    if not kw:
        return {'ok': False, 'msg': '请输入商品关键词或链接'}
    data = await search_compare_slow(kw, category)
    content = await asyncio.to_thread(content_summary, kw)
    return {'ok': True, 'keyword': kw, 'groups': [
        {'key': g['key'],
         'platforms': [{'platform': p, 'title': it.get('title', ''), 'price': it.get('actualPrice'),
                        'original': it.get('originalPrice'), 'coupon': it.get('couponPrice') or it.get('coupon_amount') or 0,
                        'shop': it.get('shopName') or '', 'url': it.get('url') or '',
                        'goodsId': it.get('goodsId') or '', 'sales': it.get('monthSales') or 0,
                        'shop_type': it.get('shop_type') or '', 'unit_price': it.get('unit_price'),
                        'shop_rating': it.get('shop_rating'), 'shop_signals': it.get('shop_signals')}
                       for p, it in g['platforms'].items()],
         'best_price': g['best']['actualPrice'],
         'low_price_warning': g.get('low_price_warning', False),
         'genuine': g.get('genuine')}
        for g in data['groups'][:6]],
        'subsidies': data['subsidies'], 'content': content,
        'tb_count': data['tb_count'], 'pdd_count': data['pdd_count'],
        'jd_count': data.get('jd_count', 0), 'vip_count': data.get('vip_count', 0)}

@app.post('/api/advice')
async def api_advice(keyword: str = Form(''), category: str = Form(''), group_key: str = Form('')):
    """AI 建议面板（V4-Pro，异步加载 + 6h 缓存，WorkBuddy P1-3）"""
    from compare import search_compare_slow, gen_advice
    from db import get_conn, get_advice_cache, save_advice_cache
    cache_key = f'{keyword.strip()}|{group_key.strip()}'
    cached = get_advice_cache(cache_key)
    if cached:
        return {'ok': True, 'advice': cached, 'cached': True}
    data = await search_compare_slow(keyword, category)
    group = next((g for g in data['groups'] if g['key'] == group_key), None)
    if not group:
        return {'ok': False, 'msg': '未找到该商品组'}
    # 查历史（取组内第一个有 goodsId 的商品）
    history = []
    conn = get_conn()
    for p, it in group['platforms'].items():
        gid = it.get('goodsId') or ''
        if gid:
            rows = conn.execute('''
                SELECT price, queried_at FROM price_history
                WHERE platform=? AND item_id=? ORDER BY queried_at DESC LIMIT 30
            ''', (p, str(gid))).fetchall()
            history += [dict(r) for r in rows]
            break
    conn.close()
    # v1.0 A-B 实验分流：按 user_name 稳定 hash → variant（a=新版prompt / b=旧版）
    uname = ''  # api_advice 无 user 参数，用 keyword hash 稳定分流
    variant = 'a' if (sum(ord(c) for c in keyword) % 2 == 0) else 'b'
    advice = await asyncio.to_thread(gen_advice, keyword, group, data['subsidies'], history, variant)
    if not advice.startswith('【当前位】AI 建议暂时不可用'):
        save_advice_cache(cache_key, advice)
    # v7 评估埋点：建议展示记录（shown，带 variant 供 A-B 统计）
    try:
        from db import get_conn
        conn = get_conn()
        conn.execute('INSERT INTO advice_events (scene, keyword, action, variant) VALUES (?,?,?,?)',
                     ('compare', keyword[:60], 'shown', variant))
        conn.commit(); conn.close()
    except Exception:
        pass
    return {'ok': True, 'advice': advice, 'cached': False, 'variant': variant}

# ========== v7 商品库分析（Taobao_Spider 可视化看板借鉴，ECharts 版）==========

@app.get('/api/analysis')
def api_analysis():
    """商品库分析：价格分布 + 品牌占比 + 价格销量散点（供看板图表）"""
    from db import get_conn
    conn = get_conn()
    # 价格区间分布
    bins = [(0, 100), (100, 300), (300, 1000), (1000, 3000), (3000, 999999)]
    labels = ['0-100', '100-300', '300-1000', '1000-3000', '3000+']
    price_hist = []
    for (lo, hi), lb in zip(bins, labels):
        n = conn.execute('SELECT COUNT(*) FROM product_items WHERE price >= ? AND price < ?', (lo, hi)).fetchone()[0]
        price_hist.append({'range': lb, 'n': n})
    # 品牌 TOP8 占比
    brands = conn.execute('''SELECT brand, COUNT(*) n FROM product_items
        WHERE brand != '' GROUP BY brand ORDER BY n DESC LIMIT 8''').fetchall()
    total = conn.execute("SELECT COUNT(*) FROM product_items WHERE brand != ''").fetchone()[0] or 1
    brand_share = [{'name': r['brand'], 'value': r['n']} for r in brands]
    # 价格 vs 销量散点（样本 300 条）
    scatter = [{'price': r['price'], 'sales': r['sales']} for r in conn.execute(
        "SELECT price, sales FROM product_items WHERE price > 0 AND sales > 0 ORDER BY id DESC LIMIT 300")]
    conn.close()
    return {'price_hist': price_hist, 'brand_share': brand_share, 'brand_total': total,
            'scatter': scatter, 'total': total}

if __name__ == '__main__':
    import uvicorn

    async def _watch_loop():
        """盯价定时检查（v6 最后一环）：启动时跑一次 + 每 6 小时一次"""
        import asyncio
        while True:
            try:
                from notify import check_and_notify
                stat = await asyncio.to_thread(check_and_notify)
                print(f'[watch] 盯价检查: {stat}')
            except Exception as e:
                print(f'[watch] 检查异常: {str(e)[:80]}')
            await asyncio.sleep(6 * 3600)  # 6 小时

    import threading
    threading.Thread(target=lambda: asyncio.run(_watch_loop()), daemon=True).start()
    uvicorn.run(app, host='0.0.0.0', port=8001)

