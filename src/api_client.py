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
    """淘宝系商品搜索（大淘客），返回解析后的商品列表"""
    params = {'keyWords': keywords, 'pageId': str(page), 'pageSize': str(size)}
    if category and category in CATEGORY_CIDS:
        params['cids'] = CATEGORY_CIDS[category]
    result = get('goods/get-dtk-search-goods', params)
    if result.get('code') != 0:
        print(f'⚠️ API 错误: {result.get("msg")}')
        return []
    return parse_goods_list(result.get('data', {}).get('list', []), platform='tb')

def search_pdd(keywords: str, page: int = 1, size: int = 20) -> list:
    """拼多多商品搜索（大淘客 dels/pdd/goods/search）"""
    params = {'keyword': keywords, 'page': str(page), 'pageSize': str(size)}
    result = get('dels/pdd/goods/search', params)
    if result.get('code') != 0:
        print(f'⚠️ PDD API 错误: {result.get("msg")}')
        return []
    data = result.get('data', {})
    if isinstance(data, dict):
        lst = data.get('list', data.get('goodsList', []))
    elif isinstance(data, list):
        lst = data
    else:
        lst = []
    items = parse_pdd_list(lst)
    return sort_by_relevance(items, keywords)

def sort_by_relevance(items: list, keyword: str) -> list:
    """按标题相关性排序：含完整关键词的排前，含部分词的次之（解决 PDD 匹配松散问题）"""
    def score(it):
        title = it.get('title', '')
        s = 0
        if keyword in title:
            s += 100
        # 关键词拆词（中英文都拆）：品牌词命中加权
        for w in [keyword[i:i+2] for i in range(len(keyword)-1)]:
            if w in title:
                s += 3
        return s
    return sorted(items, key=score, reverse=True)

def parse_pdd_list(raw_list: list) -> list:
    """解析拼多多返回字段 → 统一结构"""
    items = []
    for g in raw_list:
        items.append({
            'goodsId': g.get('goodsSign') or g.get('goods_id'),
            'title': g.get('goodsName') or g.get('goods_name', ''),
            'actualPrice': g.get('minGroupPrice') or g.get('min_on_sale_group_price', 0) / 100,
            'originalPrice': g.get('marketPrice'),
            'couponPrice': (g.get('couponDiscount') or g.get('coupon_discount', 0)) / 100,
            'monthSales': g.get('salesTip') or g.get('sales_tip', 0),
            'shopName': g.get('mallName') or g.get('mall_name', ''),
            'brand': g.get('brandName', ''),
            'platform': 'pdd',
            'url': None,
        })
    return items

def parse_goods_list(raw_list: list, platform: str = 'tb') -> list:
    """解析大淘客淘宝系字段 → 统一结构"""
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
            'platform': platform,
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
