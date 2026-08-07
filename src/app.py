# app.py - 购物助手网页版 v1.0（雏形）
# 运行: python src/app.py  → 浏览器打开 http://localhost:8000
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import asyncio
from fastapi.responses import StreamingResponse
import json as _json

from api_client import search_goods, search_pdd, value_score
from matcher import parse_items, group_by_sku, ADAPTERS
from db import init_db, get_conn, save_search_result, save_manual_price, find_manual_prices, add_watch, list_watches, check_watches

app = FastAPI(title='购物助手')
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

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
        subprocess.Popen([r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                          '--remote-debugging-port=9222',
                          '--user-data-dir=' + os.path.expanduser('~/mc_edge_profile'),
                          'about:blank'], creationflags=0x08000000)
        time.sleep(5)

    # 2. 先读已有 jsonl（有匹配数据就不重爬）
    mc_dir = os.path.expanduser('~/mc_ref')
    def read_jsonl(plat):
        out = []
        files = sorted(glob.glob(os.path.join(mc_dir, 'data', plat, 'jsonl', 'search_contents_*.jsonl')))
        if files:
            with open(files[-1], encoding='utf-8') as f:
                for line in f:
                    try:
                        d = json.loads(line)
                        t = d.get('title', '') or d.get('content', '') or d.get('desc', '') or ''
                        tl = t.lower()
                        if keyword in t or (keyword in ('石头岛', 'stone island') and ('石头岛' in t or 'stone island' in tl or 'stoneisland' in tl)):
                            out.append((d, plat))
                    except Exception:
                        continue
        return out
    cached = read_jsonl('bili') + read_jsonl('tieba') + read_jsonl('xhs')
    if len(cached) >= 5:
        # 按类型均衡：每类最多 10 条，避免单一平台占满
        by_type = {'bili': [], 'tieba': [], 'xhs': []}
        for d, plat in cached:
            if plat in by_type and len(by_type[plat]) < 10:
                by_type[plat].append((d, plat))
        cached = by_type['bili'] + by_type['tieba'] + by_type['xhs']
        items = []
        for d, plat in cached:
            if plat == 'bili':
                items.append({'type': 'bili', 'title': (d.get('title','') or '')[:60],
                              'author': d.get('nickname',''), 'play': d.get('video_play_count',0),
                              'like': d.get('liked_count',0), 'comment': d.get('video_comment',0),
                              'url': d.get('video_url',''), 'desc': (d.get('desc','') or '')[:80]})
            elif plat == 'tieba':
                items.append({'type': 'tieba', 'title': (d.get('title','') or d.get('content',''))[:60],
                              'author': d.get('author',''), 'play': 0, 'like': 0,
                              'comment': d.get('comment_count',0), 'url': d.get('url',''),
                              'desc': d.get('tieba_name','')})
            else:
                items.append({'type': 'xhs', 'title': (d.get('title','') or '')[:60],
                              'author': d.get('nickname',''), 'play': 0,
                              'like': d.get('liked_count',0), 'comment': d.get('comment_count',0),
                              'url': d.get('note_url',''), 'desc': (d.get('desc','') or '')[:60]})
        return {'items': items[:30]}

    # 3. 缓存不足才调 MediaCrawler（uv 路径）
    uv = os.path.expanduser(r'~/AppData/Roaming/Python/Python314/Scripts/uv.exe')
    env = dict(os.environ, PATH=os.path.dirname(uv) + ';' + os.environ.get('PATH', ''))
    try:
        subprocess.run([uv, 'run', 'main.py', '--platform', 'bili', '--type', 'search',
                        '--keywords', keyword],
                       cwd=mc_dir, env=env, timeout=150,
                       capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        pass

    # 3. 读最新 jsonl（B站 + 贴吧）
    items = []
    for plat, path in [('bili', 'search_contents'), ('tieba', 'search_contents')]:
        files = sorted(glob.glob(os.path.join(mc_dir, 'data', plat, 'jsonl', path + '_*.jsonl')))
        if not files:
            continue
        with open(files[-1], encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                    title = d.get('title', '') or d.get('content', '') or ''
                    if keyword in title:
                        if plat == 'bili':
                            items.append({
                                'type': 'bili', 'title': title[:60],
                                'author': d.get('nickname', ''),
                                'play': d.get('video_play_count', 0),
                                'like': d.get('liked_count', 0),
                                'comment': d.get('video_comment', 0),
                                'url': d.get('video_url', ''),
                                'desc': (d.get('desc', '') or '')[:80],
                            })
                        else:
                            items.append({
                                'type': 'tieba', 'title': title[:60],
                                'author': d.get('author', ''),
                                'play': 0, 'like': 0,
                                'comment': d.get('comment_count', 0),
                                'url': d.get('url', ''),
                                'desc': d.get('tieba_name', ''),
                            })
                except Exception:
                    continue
    return {'items': items[:15]}

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

@app.get('/search_sse')
async def search_sse(keyword: str = '', category: str = ''):
    async def gen():
        def sse(data):
            return 'data: ' + _json.dumps(data, ensure_ascii=False) + chr(10) + chr(10)
        try:
            yield sse({'type': 'progress', 'msg': f'正在淘宝搜索「{keyword}」...'})
            tb_items = await asyncio.to_thread(search_goods, keyword, category or None)
            yield sse({'type': 'progress', 'msg': f'✅ 淘宝完成（{len(tb_items)} 条），正在拼多多...'})
            pdd_items = await asyncio.to_thread(search_pdd, keyword)
            yield sse({'type': 'progress', 'msg': f'✅ 拼多多完成（{len(pdd_items)} 条），正在 SKU 分组...'})
            all_items = tb_items + pdd_items

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
            conn.close()

            yield sse({'type': 'done', 'keyword': keyword, 'category': category,
                       'groups': groups, 'total': len(all_items),
                       'tb_count': len(tb_items), 'pdd_count': len(pdd_items),
                       'manual_count': len(manual_items)})
        except Exception as e:
            yield sse({'type': 'error', 'msg': str(e)[:200]})

    return StreamingResponse(gen(), media_type='text/event-stream')

@app.post('/search', response_class=HTMLResponse)
def search(request: Request, keyword: str = Form(...), category: str = Form('')):
    keyword = keyword.strip()
    if not keyword:
        return templates.TemplateResponse(request, 'index.html', {'categories': CATEGORIES, 'error': '请输入商品名称'})

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
    conn.close()

    return templates.TemplateResponse(request, 'result.html', {
        'keyword': keyword, 'category': category,
        'groups': groups[:10], 'total': len(all_items),
        'tb_count': len(tb_items), 'pdd_count': len(pdd_items), 'manual_count': len(manual_items),
    })

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8001)
