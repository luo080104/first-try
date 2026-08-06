# api_client.py - 大淘客 API 客户端 v1.1（阶段 1）
# 支持：商品搜索 + 字段解析
import hashlib
import time
import random
import json
import os
import urllib.request
import urllib.parse

def load_env():
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

ENV = load_env()
APP_KEY = ENV.get('DTK_APP_KEY', '')
APP_SECRET = ENV.get('DTK_APP_SECRET', '')
VERSION = 'v1.3.1'
BASE_URL = 'https://openapi.dataoke.com/api/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/68.0.3440.84 Safari/537.36',
    'Client-Sdk-Type': 'python',
}

# 品类 → 大淘客 cids（1-女装 2-母婴 3-美妆 4-居家日用 5-鞋品 6-美食 7-文娱车品 8-数码家电 9-男装 10-内衣 11-箱包 12-配饰 13-户外运动 14-家装家纺）
CATEGORY_CIDS = {
    '服饰': '1,9,10,11,12',
    '食品': '6',
    '日用百货': '4',
    '数码家电': '8',
}

def make_sign(params: dict) -> str:
    """老式签名（字典序 + &key=secret，实测可用）"""
    sorted_str = '&'.join(f'{k}={params[k]}' for k in sorted(params))
    return hashlib.md5((sorted_str + f'&key={APP_SECRET}').encode('utf-8')).hexdigest().upper()

def get(api_url: str, biz_params: dict) -> dict:
    params = {'appKey': APP_KEY, 'version': VERSION}
    params.update(biz_params)
    params['sign'] = make_sign(params)
    url = BASE_URL + api_url + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))

def search_goods(keywords: str, category: str = None, page: int = 1, size: int = 20) -> list:
    """商品搜索，返回解析后的商品列表"""
    params = {'keyWords': keywords, 'pageId': str(page), 'pageSize': str(size)}
    if category and category in CATEGORY_CIDS:
        params['cids'] = CATEGORY_CIDS[category]
    result = get('goods/get-dtk-search-goods', params)
    if result.get('code') != 0:
        print(f'⚠️ API 错误: {result.get("msg")}')
        return []
    return parse_goods_list(result.get('data', {}).get('list', []))

def parse_goods_list(raw_list: list) -> list:
    """解析大淘客原始字段 → 统一结构"""
    items = []
    for g in raw_list:
        items.append({
            'goodsId': g.get('goodsId'),
            'title': g.get('dtitle') or g.get('title', ''),
            'actualPrice': g.get('actualPrice', 0),
            'originalPrice': g.get('originalPrice'),
            'couponPrice': g.get('couponPrice', 0),
            'monthSales': g.get('monthSales', 0),
            'shopName': g.get('shopName', ''),
            'brand': g.get('brandName') or g.get('brand', ''),  # brandName 才是品牌名，brand=1/0 是是否品牌商品
            'platform': 'tb',  # 大淘客默认淘宝系；阶段 2 扩展多平台
            'url': g.get('itemLink'),
        })
    return items

if __name__ == '__main__':
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else '羽绒服'
    items = search_goods(kw)
    print(f'「{kw}」返回 {len(items)} 条：')
    for i, it in enumerate(items[:5], 1):
        print(f'  {i}. {it["title"][:35]} | ¥{it["actualPrice"]} | 券¥{it["couponPrice"]} | 月销{it["monthSales"]}')
