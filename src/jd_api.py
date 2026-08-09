# jd_api.py - 京东联盟 API 通道（v6，案例启发：不走搜索页硬扛验证码）
# 能力：
#   1. jingfen.query  京粉精选（按 eliteId 分类拉取，无需 token）→ 采集通道
#   2. material.query 猜你喜欢（eliteId + 可选 keyword，无需 token）→ 采集补充
#   3. goods.query    关键词搜索（需 token + 权限，可选）→ 实时搜索（授权后启用）
# 参考：yichahucha/go-jd/jd-autobuy 案例 + test_jd_api.py 既有实现
import hashlib
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))


def _load_env():
    env = {}
    path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env


ENV = _load_env()
APP_KEY = os.environ.get('JD_APP_KEY', '') or ENV.get('JD_APP_KEY', '')
APP_SECRET = os.environ.get('JD_APP_SECRET', '') or ENV.get('JD_APP_SECRET', '')
ACCESS_TOKEN = os.environ.get('JD_ACCESS_TOKEN', '') or ENV.get('JD_ACCESS_TOKEN', '')
API_URL = 'https://api.jd.com/routerjson'

# 京粉精选常用 eliteId（无 token 可用的京东分类榜单）
JINGFEN_ELITE_IDS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10']


def _sign(params: dict, secret: str) -> str:
    s = secret
    for k in sorted(params):
        s += f'{k}{params[k]}'
    s += secret
    return hashlib.md5(s.encode('utf-8')).hexdigest().upper()


def _call(method: str, biz_params: dict, use_token: bool = False) -> dict:
    if not APP_KEY or not APP_SECRET:
        return {}
    params = {
        'method': method,
        'app_key': APP_KEY,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'format': 'json',
        'v': '1.0',
        'sign_method': 'md5',
        '360buy_param_json': json.dumps(biz_params, ensure_ascii=False),
    }
    if use_token and ACCESS_TOKEN:
        params['access_token'] = ACCESS_TOKEN
    params['sign'] = _sign(params, APP_SECRET)
    try:
        import requests
        resp = requests.post(API_URL, data=params, timeout=15, headers={
            'User-Agent': random.choice(['Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
                                          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
                                          'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'])
        })
        return resp.json()
    except Exception:
        return {}


def _unwrap(result: dict, resp_key: str) -> list:
    """解包京东联盟响应 → 商品列表"""
    rd = result.get(resp_key) or {}
    if rd.get('code') != '0':
        return []
    qr = rd.get('queryResult')
    if isinstance(qr, str):
        try:
            qr = json.loads(qr)
        except Exception:
            return []
    if not qr or qr.get('code') != 200:
        return []
    data = qr.get('data') or []
    return data if isinstance(data, list) else []


def _to_item(g: dict) -> dict:
    """京东商品字段 → 统一结构（京东联盟用 itemId 字段，链接用 materialUrl 京粉短链）"""
    price = g.get('priceInfo') or {}
    shop = g.get('shopInfo') or {}
    sku = str(g.get('skuId') or g.get('itemId') or '')
    url = str(g.get('materialUrl') or '')
    if url and not url.startswith('http'):
        url = 'https://' + url
    return {
        'platform': 'jd',
        'goodsId': sku,
        'item_id': sku,
        'title': (g.get('skuName') or '')[:120],
        'actualPrice': float(price.get('lowestPrice') or price.get('price') or 0),
        'originalPrice': float(price.get('originPrice') or 0) or None,
        'coupon_amount': float(price.get('couponPrice') or 0),
        'monthSales': g.get('inOrderCount30Days') or 0,
        'shopName': shop.get('shopName') or '',
        'brand': g.get('brandName') or '',
        'url': url or (f'https://item.jd.com/{sku}.html' if sku else ''),
        'img': ((g.get('imageInfo') or {}).get('imageList') or [{}])[0].get('url', '') if g.get('imageInfo') else '',
        '_source': 'jd_api',
    }


def search_jd_by_api(keyword: str, page: int = 1, size: int = 20) -> list:
    """京东关键词搜索（goods.query，需 token）。无 token/失败返回 []"""
    if not ACCESS_TOKEN:
        return []
    result = _call('jd.union.open.goods.query',
                   {'goodsReqDTO': {'keyword': keyword, 'pageIndex': str(page), 'pageSize': str(size)}},
                   use_token=True)
    goods = _unwrap(result, 'jd_union_open_goods_query_responce')
    return [_to_item(g) for g in goods if g.get('skuId')]


def crawl_jd_by_elite(pages_per_elite: int = 2, size: int = 20) -> list:
    """京东榜单通道：京粉精选按 eliteId 拉取（无需 token，无验证码，无人值守友好）。
    返回全部商品（调用方负责入库）。"""
    all_items = []
    for elite in JINGFEN_ELITE_IDS:
        for p in range(1, pages_per_elite + 1):
            result = _call('jd.union.open.goods.jingfen.query',
                           {'goodsReq': {'eliteId': elite, 'pageIndex': str(p), 'pageSize': str(size)}})
            goods = _unwrap(result, 'jd_union_open_goods_jingfen_query_responce')
            items = [_to_item(g) for g in goods if g.get('skuId') or g.get('itemId')]
            all_items += items
            if len(goods) < size:
                break
            time.sleep(1.5)  # 低频，防限流
    return all_items


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '手机'
    print(f'=== 关键词搜索（需 token）: {kw} ===')
    items = search_jd_by_api(kw)
    print(f'返回 {len(items)} 条（token 未配置则 0）')
    print('=== 京粉精选榜单（无需 token） ===')
    items2 = crawl_jd_by_elite(pages_per_elite=1)
    print(f'返回 {len(items2)} 条')
    for it in items2[:5]:
        print(f"  ¥{it['actualPrice']} | {it['title'][:35]} | {it['shopName']}")
