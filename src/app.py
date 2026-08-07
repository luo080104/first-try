# app.py - 购物助手网页版 v1.0（雏形）
# 运行: python src/app.py  → 浏览器打开 http://localhost:8000
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from api_client import search_goods, search_pdd
from matcher import parse_items, group_by_sku, ADAPTERS
from db import init_db, get_conn, save_search_result, save_manual_price, find_manual_prices

app = FastAPI(title='购物助手')
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

CATEGORIES = ['', '服饰', '食品', '日用百货', '数码家电']

@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request, 'index.html', {'categories': CATEGORIES})

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
