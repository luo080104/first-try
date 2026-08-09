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

def read_content_items(keyword: str) -> dict:
    """读内容联动数据（jsonl 缓存，秒回）——B站/贴吧/小红书均衡 10 条 + 评分 + 套路检测"""
    import glob
    import json as _j
    mc_dir = os.path.expanduser('~/mc_ref')

    def read_jsonl(plat):
        out = []
        files = sorted(glob.glob(os.path.join(mc_dir, 'data', plat, 'jsonl', 'search_contents_*.jsonl')))
        if files:
            with open(files[-1], encoding='utf-8') as f:
                for line in f:
                    try:
                        d = _j.loads(line)
                        t = d.get('title', '') or d.get('content', '') or d.get('desc', '') or ''
                        tl = t.lower()
                        if keyword in t or (keyword in ('石头岛', 'stone island') and ('石头岛' in t or 'stone island' in tl or 'stoneisland' in tl)):
                            out.append((d, plat))
                    except Exception:
                        continue
        return out

    cached = read_jsonl('bili') + read_jsonl('tieba') + read_jsonl('xhs')
    by_type = {'bili': [], 'tieba': [], 'xhs': []}
    for d, plat in cached:
        if plat in by_type and len(by_type[plat]) < 10:
            by_type[plat].append((d, plat))
    items = []
    for d, plat in (by_type['bili'] + by_type['tieba'] + by_type['xhs']):
        if plat == 'bili':
            items.append({'type': 'bili', 'title': (d.get('title', '') or '')[:60],
                          'author': d.get('nickname', ''), 'play': d.get('video_play_count', 0),
                          'like': d.get('liked_count', 0), 'comment': d.get('video_comment', 0),
                          'url': d.get('video_url', ''), 'desc': (d.get('desc', '') or '')[:80],
                          'content_id': str(d.get('video_id', '')), 'pub_ts': d.get('create_time', '')})
        elif plat == 'tieba':
            items.append({'type': 'tieba', 'title': (d.get('title', '') or d.get('content', ''))[:60],
                          'author': d.get('author', ''), 'play': 0, 'like': 0,
                          'comment': d.get('comment_count', 0), 'url': d.get('url', ''),
                          'desc': d.get('tieba_name', ''),
                          'content_id': str(d.get('note_id', '')), 'pub_ts': d.get('publish_time', '')})
        else:
            items.append({'type': 'xhs', 'title': (d.get('title', '') or '')[:60],
                          'author': d.get('nickname', ''), 'play': 0,
                          'like': d.get('liked_count', 0), 'comment': d.get('comment_count', 0),
                          'url': d.get('note_url', ''), 'desc': (d.get('desc', '') or '')[:60],
                          'content_id': str(d.get('note_id', '')), 'pub_ts': d.get('time', '')})
    for it in items:
        sc = score_content(it, keyword)
        it['score'] = sc['score']
        it['flags'] = sc['flags']
        it['sent'] = sc['sentiment']
    trap = detect_trap(keyword)
    result = {'items': items[:30]}
    if trap.get('has_trap') or trap.get('has_fake_original'):
        result['trap'] = {'trap': trap.get('trap_msg'), 'fake': trap.get('fake_msg')}
    return result

def search_taobao_full(keyword: str, page: int = 1, max_items: int = 8) -> list:
    """淘宝全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice"""
    try:
        import tb_search
        items = tb_search.search_taobao(keyword, max_items=max_items, page=page)
        for it in items:
            if 'actualPrice' not in it and it.get('price') is not None:
                it['actualPrice'] = it['price']
            it['monthSales'] = it.get('sales') or it.get('real_sales') or 0
            it['shopName'] = it.get('shop_name') or it.get('shop') or ''
            it['title'] = it.get('title', '')
            it['platform'] = 'tb'
            it['_source'] = 'browser'
        return items
    except Exception as e:
        print(f'[tb_full] 失败: {str(e)[:80]}')
        return []

def search_jd_full(keyword: str, page: int = 1, max_items: int = 8) -> list:
    """京东全量搜索（慢通道，浏览器），失败返回空；字段统一 actualPrice"""
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
        print(f'[jd_full] 失败: {str(e)[:80]}')
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
    results = {'tb': [], 'jd': []}
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
    return {'ok': True, 'msg': f'采集完成：淘宝 {len(results["tb"])} + 京东 {len(results["jd"])} = {total} 条，入库 {added} 条'}

@app.get('/search_sse')
async def search_sse(keyword: str = '', category: str = '', guide_round: int = 0):
    async def gen():
        nonlocal keyword, category
        def sse(data):
            return 'data: ' + _json.dumps(data, ensure_ascii=False) + chr(10) + chr(10)
        try:
            # 意图解析（对话式输入支持）
            intent = await asyncio.to_thread(parse_intent, keyword)
            search_kw = intent.get('keyword') or keyword
            search_cat = intent.get('category') or category
            if search_kw != keyword or search_cat != category:
                yield sse({'type': 'progress', 'msg': f'🤖 明白了：搜索「{search_kw}」' + (f'（{search_cat}）' if search_cat else '')})
            keyword, category = search_kw, search_cat
            # 快通道：API 并行（教材：无依赖子任务并行执行）
            yield sse({'type': 'progress', 'msg': f'⏳ 正在并行搜索淘宝 + 拼多多...'})
            tb_items, pdd_items = await asyncio.gather(
                asyncio.to_thread(search_goods, keyword, category or None),
                asyncio.to_thread(search_pdd, keyword),
            )
            all_items = tb_items + pdd_items

            # 慢通道自动补搜：快通道结果少（<5 条）→ 自动跑淘宝全量 + 京东（用户要求：默认所有，不分平台）
            slow_items = []
            if len(all_items) < 5:
                yield sse({'type': 'progress', 'msg': f'快通道结果少（{len(all_items)} 条），正在全网补搜（淘宝全量+京东）...'})
                tb_full, jd_full = await asyncio.gather(
                    asyncio.to_thread(search_taobao_full, keyword),
                    asyncio.to_thread(search_jd_full, keyword),
                )
                slow_items = tb_full + jd_full
                all_items = tb_items + pdd_items + slow_items
                yield sse({'type': 'progress', 'msg': f'✅ 全网补搜完成（+{len(slow_items)} 条），正在合并比价...'})
            else:
                yield sse({'type': 'progress', 'msg': f'✅ 淘宝 {len(tb_items)} 条 + 拼多多 {len(pdd_items)} 条，正在 SKU 分组...'})

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
            if (guide_round < 1 and len(groups) > 3 and len(all_items) >= 8
                    and prices and max(prices) / max(min(prices), 1) > 2.0
                    and not has_model_num):
                yield sse({'type': 'progress', 'msg': '📋 结果较多，正在生成导购选项...'})
                options = await asyncio.to_thread(generate_options, keyword, groups)
                if options:
                    yield sse({'type': 'guide', 'options': options})

            content = await asyncio.to_thread(read_content_items, keyword)
            subsidies = await asyncio.to_thread(find_subsidies, keyword, search_cat)
            yield sse({'type': 'done', 'keyword': keyword, 'category': category,
                       'groups': groups, 'total': len(all_items),
                       'tb_count': len(tb_items), 'pdd_count': len(pdd_items),
                       'manual_count': len(manual_items), 'content': content,
                       'slow_count': len(slow_items), 'options': options,
                       'subsidies': subsidies})
        except Exception as e:
            yield sse({'type': 'error', 'msg': str(e)[:200]})

    return StreamingResponse(gen(), media_type='text/event-stream')

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

# ========== v3.5 对比页（Mode 2「帮我比」）==========

@app.get('/compare', response_class=HTMLResponse)
def compare_page(request: Request):
    """对比页入口"""
    return templates.TemplateResponse(request, 'compare.html', {'categories': CATEGORIES})

@app.post('/api/compare')
async def api_compare(keyword: str = Form(''), category: str = Form('')):
    """三平台搜索 + SKU 合并 + 内容摘要（快路径，不调 R1）"""
    from compare import search_compare, parse_link, content_summary
    kw = keyword.strip()
    link_info = parse_link(kw)
    # 链接输入：提取平台+ID，用 ID 查不到详情就回退为关键词搜索
    if link_info:
        kw = re.sub(r'https?://\S+', '', kw).strip() or kw
    if not kw:
        return {'ok': False, 'msg': '请输入商品关键词或链接'}
    data = await asyncio.to_thread(search_compare, kw, category)
    content = await asyncio.to_thread(content_summary, kw)
    return {'ok': True, 'keyword': kw, 'groups': [
        {'key': g['key'],
         'platforms': [{'platform': p, 'title': it.get('title', ''), 'price': it.get('actualPrice'),
                        'original': it.get('originalPrice'), 'coupon': it.get('couponPrice') or it.get('coupon_amount') or 0,
                        'shop': it.get('shopName') or '', 'url': it.get('url') or '',
                        'goodsId': it.get('goodsId') or '', 'sales': it.get('monthSales') or 0}
                       for p, it in g['platforms'].items()],
         'best_price': g['best']['actualPrice']}
        for g in data['groups'][:6]],
        'subsidies': data['subsidies'], 'content': content,
        'tb_count': data['tb_count'], 'pdd_count': data['pdd_count']}

@app.post('/api/advice')
async def api_advice(keyword: str = Form(''), category: str = Form(''), group_key: str = Form('')):
    """AI 建议面板（R1，异步加载）"""
    from compare import search_compare, gen_advice
    from db import get_conn
    data = await asyncio.to_thread(search_compare, keyword, category)
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
    advice = await asyncio.to_thread(gen_advice, keyword, group, data['subsidies'], history)
    return {'ok': True, 'advice': advice}

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8001)
