# 大淘客 API 客户端 v1.0（官方签名方式，2026-08-06 调通）
# 用法: python src/api_test.py
import hashlib
import json
import os
import random
import time
import urllib.parse
import urllib.request
from typing import Optional


def load_env():
    env = {}
    path = os.path.join(os.path.dirname(__file__), '..', '.env')
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip()
    return env

ENV = load_env()
APP_KEY = ENV['DTK_APP_KEY']
APP_SECRET = ENV['DTK_APP_SECRET']
VERSION = 'v1.0.0'
BASE_URL = 'https://openapi.dataoke.com/api/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/68.0.3440.84 Safari/537.36',
    'Client-Sdk-Type': 'python',
}

def sign_params(biz_params: dict) -> dict:
    """官方签名：signRan = MD5(appKey=..&timer=..&nonce=..&key=secret).upper()"""
    timer = int(time.time() * 1000)
    nonce = random.randint(100000, 999999)
    sign = hashlib.md5(
        f'appKey={APP_KEY}&timer={timer}&nonce={nonce}&key={APP_SECRET}'.encode('utf-8')
    ).hexdigest().upper()
    params = {'appKey': APP_KEY, 'version': VERSION, 'timer': timer, 'nonce': nonce, 'signRan': sign}
    params.update(biz_params)
    return params

def get(api_url: str, biz_params: dict) -> dict:
    """GET 请求（大淘客搜索类接口都是 GET）"""
    params = sign_params(biz_params)
    url = BASE_URL + api_url + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))

def search_goods(keywords: str, cids: Optional[str] = None, page: int = 1, size: int = 10) -> dict:
    """商品搜索。cids: 1-女装 2-母婴 3-美妆 4-居家日用 5-鞋品 6-美食 7-文娱车品 8-数码家电 9-男装 10-内衣 11-箱包 12-配饰 13-户外运动 14-家装家纺"""
    params = {'keyWords': keywords, 'pageId': str(page), 'pageSize': str(size)}
    if cids:
        params['cids'] = cids
    return get('goods/get-dtk-search-goods', params)

if __name__ == '__main__':
    print('=== 大淘客 API 调通测试 ===')
    for kw, cids in [('羽绒服', '1'), ('机械革命耀世16 Ultra 5080', None)]:
        result = search_goods(kw, cids)
        lst = result.get('data', {}).get('list', [])
        print(f'\n搜索「{kw}」: {len(lst)} 条返回, totalNum={result.get("data",{}).get("totalNum",0)}')
        for item in lst[:3]:
            print(f'  - {item.get("title","")[:40]} | ¥{item.get("actualPrice")} | 券¥{item.get("couponPrice",0)}')
