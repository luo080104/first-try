# api_client.py - 大淘客 API 客户端 v1.1（阶段 1）
# 支持：商品搜索 + 字段解析
import datetime
import hashlib
import json
import os
import random
import sqlite3
import time
import urllib.parse
import urllib.request
from typing import Optional


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

# v5.2：折淘客（唯品会通道；未配置 key 时 search_vip 返回空，不报错）
ZTK_APPKEY = os.environ.get('ZTK_APPKEY', '') or ENV.get('ZTK_APPKEY', '')
ZTK_VIP_SID = os.environ.get('ZTK_VIP_SID', '') or ENV.get('ZTK_VIP_SID', '')

# v6 优化（CrawlerTutorial 启发）：UA 池随机轮换，降低 API 限流识别
UA_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
]


def _random_ua() -> str:
    return random.choice(UA_POOL)


def _headers() -> dict:
    return {'User-Agent': _random_ua(), 'Client-Sdk-Type': 'python'}
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

# ===== 缓存层（24h 内同关键词不重复调 API）=====
CACHE_DB = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')
CACHE_HOURS = 24

def _ensure_cache_table():
    conn = sqlite3.connect(CACHE_DB)
    conn.execute('''CREATE TABLE IF NOT EXISTS search_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        keyword TEXT NOT NULL,
        platform TEXT NOT NULL,
        cids TEXT,
        result TEXT NOT NULL,
        cached_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_cache ON search_cache(keyword, platform)')
    conn.commit()
    conn.close()

def _cache_get(keyword: str, platform: str, cids=None):
    _ensure_cache_table()
    conn = sqlite3.connect(CACHE_DB)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        'SELECT result, cached_at FROM search_cache WHERE keyword=? AND platform=? AND cids IS ? ORDER BY cached_at DESC LIMIT 1',
        (keyword, platform, cids)).fetchone()
    conn.close()
    if row:
        cached_at = datetime.datetime.strptime(row['cached_at'], '%Y-%m-%d %H:%M:%S')
        if datetime.datetime.now() - cached_at < datetime.timedelta(hours=CACHE_HOURS):
            return json.loads(row['result'])
    return None

def _cache_set(keyword: str, platform: str, cids, items: list):
    _ensure_cache_table()
    conn = sqlite3.connect(CACHE_DB)
    conn.execute('INSERT INTO search_cache (keyword, platform, cids, result) VALUES (?,?,?,?)',
                 (keyword, platform, cids, json.dumps(items, ensure_ascii=False)))
    conn.commit()
    conn.close()

def make_sign(params: dict) -> str:
    """老式签名（字典序 + &key=secret，实测可用）"""
    sorted_str = '&'.join(f'{k}={params[k]}' for k in sorted(params))
    return hashlib.md5((sorted_str + f'&key={APP_SECRET}').encode('utf-8')).hexdigest().upper()

def get(api_url: str, biz_params: dict) -> dict:
    params = {'appKey': APP_KEY, 'version': VERSION}
    params.update(biz_params)
    params['sign'] = make_sign(params)
    url = BASE_URL + api_url + '?' + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=_headers()), timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))

def search_goods(keywords: str, category: Optional[str] = None, page: int = 1, size: int = 20, use_cache: bool = True) -> list:
    """淘宝系商品搜索（大淘客），带 24h 缓存"""
    cids = CATEGORY_CIDS.get(category) if category else None
    if use_cache:
        cached = _cache_get(keywords, 'tb', cids)
        if cached is not None:
            print(f'💾 淘宝「{keywords}」命中缓存（24h 内）')
            return cached
    params = {'keyWords': keywords, 'pageId': str(page), 'pageSize': str(size)}
    if cids:
        params['cids'] = cids
    result = get('goods/get-dtk-search-goods', params)
    if result.get('code') != 0:
        print(f'⚠️ API 错误: {result.get("msg")}')
        return []
    items = parse_goods_list(result.get('data', {}).get('list', []), platform='tb')
    _cache_set(keywords, 'tb', cids, items)
    return items

def search_pdd(keywords: str, page: int = 1, size: int = 20, use_cache: bool = True) -> list:
    """拼多多商品搜索（大淘客 dels/pdd/goods/search），带 24h 缓存"""
    if use_cache:
        cached = _cache_get(keywords, 'pdd', None)
        if cached is not None:
            print(f'💾 拼多多「{keywords}」命中缓存（24h 内）')
            return cached
    params = {'keyword': keywords, 'page': str(page), 'pageSize': str(size)}
    result = get('dels/pdd/goods/search', params)
    if result.get('code') != 0:
        # 2026-08-11 小布斧3：限流降频重试一次（等 5s 再试，避免连打限流）
        print(f'⚠️ PDD API 错误: {result.get("msg")}（5s 后重试一次）')
        time.sleep(5)
        result = get('dels/pdd/goods/search', params)
        if result.get('code') != 0:
            print(f'⚠️ PDD API 重试仍失败: {result.get("msg")}')
            return []
    data = result.get('data', {})
    if isinstance(data, dict):
        lst = data.get('list', data.get('goodsList', []))
    elif isinstance(data, list):
        lst = data
    else:
        lst = []
    items = parse_pdd_list(lst)
    items = sort_by_relevance(items, keywords)
    _cache_set(keywords, 'pdd', None, items)
    return items

# ===== v5.2 唯品会搜索（折淘客 API，省柴柴案例同源）=====

def search_vip(keywords: str, page: int = 1, size: int = 20, use_cache: bool = True,
               sort: str = '') -> list:
    """唯品会搜索（折淘客 open_vip_queryWithOauth，按官方文档 2026-08-09 校准）。
    未配置 ZTK key 返回 []。sort: PRICE价格/DISCOUNT折扣/SALES销量（空=综合）"""
    if not ZTK_APPKEY or not ZTK_VIP_SID:
        print('⚠️ 未配置 ZTK_APPKEY/ZTK_VIP_SID，唯品会通道跳过')
        return []
    if use_cache:
        cached = _cache_get(keywords, 'vip', None)
        if cached is not None:
            print(f'💾 唯品会「{keywords}」命中缓存（24h 内）')
            return cached
    params = {'appkey': ZTK_APPKEY, 'sid': ZTK_VIP_SID,
              'keyword': keywords, 'page': str(page), 'pageSize': str(size)}
    if sort in ('PRICE', 'DISCOUNT', 'SALES'):
        params['fieldName'] = sort
        params['order'] = '1'  # 逆序：价格从低到高/销量从高到低
    url = 'https://api.zhetaoke.com:10001/api/open_vip_queryWithOauth.ashx?' + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=_headers()), timeout=15) as r:
            res = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f'⚠️ 唯品会 API 错误: {str(e)[:80]}')
        return []
    if str(res.get('returnCode', '0')) != '0':
        print(f"⚠️ 唯品会 API 错误: {res.get('returnMessage', res.get('returnCode'))}")
        return []
    rows = ((res.get('result') or {}).get('goodsInfoList')) or []
    items = []
    for g in rows:
        gid = str(g.get('goodsId') or '')
        title = str(g.get('goodsName') or '').strip()
        if not gid or not title:
            continue
        carousel = g.get('goodsCarouselPictures') or []
        # 店铺名：storeInfo.storeName（如"唯品自营"）优先，兜底品牌名；sourceType 0=自营 1=MP
        store = (g.get('storeInfo') or {}).get('storeName') or ''
        shop = store if store else (g.get('brandName') or '')
        items.append({
            'goodsId': gid,
            'title': title[:100],
            'actualPrice': float(g.get('vipPrice') or g.get('estimatePrice') or 0),
            'originalPrice': float(g.get('marketPrice') or 0) or None,
            'coupon_amount': 0,
            'monthSales': g.get('productSales') or 0,
            'shopName': shop[:60],
            'brand': g.get('brandName') or '',
            'platform': 'vip',
            'url': g.get('destUrl') or '',
            'img': (g.get('goodsThumbUrl') or g.get('goodsMainPicture') or (carousel[0] if carousel else '')) or '',
            'shop_type': '自营' if str(g.get('sourceType')) == '0' else '',  # P2 店铺类型铺路
            'category': g.get('categoryName') or '',
        })
    items = sort_by_relevance(items, keywords)
    _cache_set(keywords, 'vip', None, items)
    return items


def get_hot_words() -> list:
    """大淘客热搜榜（无参数，内存缓存 1h）"""
    import time as _t
    if not hasattr(get_hot_words, '_cache') or _t.time() - get_hot_words._cache_ts > 3600:
        try:
            r = get('etc/search/list-hot-words', {})
            data = r.get('data') or {}
            words = []
            hot = data.get('hotWords') or data.get('list') or [] if isinstance(data, dict) else (data or [])
            if isinstance(hot, list):
                for w in hot:
                    if isinstance(w, dict):
                        words.append(str(w.get('words') or w.get('word') or w.get('hotWords') or ''))
                    else:
                        words.append(str(w))
            get_hot_words._cache = [w for w in words if w][:12]
            get_hot_words._cache_ts = _t.time()
        except Exception as e:
            print(f'⚠️ 热搜获取失败: {str(e)[:60]}')
            get_hot_words._cache = []
            get_hot_words._cache_ts = _t.time()
    return get_hot_words._cache


def get_goods_details(goods_id: str) -> dict:
    """淘宝商品详情（大淘客 get-goods-details）：DSR三围/主图/描述/销量"""
    try:
        r = get('goods/get-goods-details', {'goodsId': str(goods_id)})
        d = r.get('data') or {}
        if not isinstance(d, dict) or not d.get('goodsId'):
            return {}
        return {
            'title': d.get('dtitle') or d.get('title') or '',
            'shop': d.get('shopName') or '',
            'dsr': d.get('dsrScore'), 'service': d.get('serviceScore'), 'ship': d.get('shipScore'),
            'desc': (d.get('desc') or '')[:200],
            'img': d.get('mainPic') or '',
            'sales': d.get('monthSales'),
            'brand': d.get('brandName') or '',
        }
    except Exception as e:
        print(f'⚠️ 详情失败: {str(e)[:60]}')
        return {}


def get_pdd_details(goods_sign: str) -> dict:
    """拼多多商品详情（dels/pdd/goods/detail，goodsSign=商品库 item_id）"""
    try:
        r = get('dels/pdd/goods/detail', {'goodsSign': str(goods_sign)})
        d = r.get('data') or {}
        if not isinstance(d, dict) or not d.get('goodsSign'):
            return {}
        return {
            'title': d.get('goodsName') or '',
            'shop': d.get('mallName') or '',
            'dsr': None, 'service': None, 'ship': None,
            'desc': (d.get('goodsDesc') or '')[:200],
            'img': d.get('goodsImageUrl') or d.get('goodsThumbnailUrl') or '',
            'sales': d.get('salesTip') or '',
            'brand': d.get('brandName') or '',
        }
    except Exception as e:
        print(f'⚠️ PDD详情失败: {str(e)[:60]}')
        return {}


def get_similar_goods(goods_id: str, size: int = 8) -> list:
    """大淘客相似商品（猜你喜欢，需大淘客商品 id）"""
    try:
        r = get('goods/list-similer-goods-by-open', {'id': str(goods_id), 'size': str(size)})
        data = r.get('data') or {}
        lst = data.get('list') if isinstance(data, dict) else data
        if not isinstance(lst, list):
            return []
        return parse_goods_list(lst, platform='tb')
    except Exception as e:
        print(f'⚠️ 相似商品失败: {str(e)[:60]}')
        return []


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
    """解析拼多多返回字段 → 统一结构（券金额单位=元，实测大淘客返回元；>100 时按分兜底）"""
    items = []
    for g in raw_list:
        coupon = g.get('couponDiscount') or g.get('coupon_discount', 0)
        try:
            coupon = float(coupon)
            if coupon > 100:  # 个别接口返回分（如 500=5 元），容错转换
                coupon = coupon / 100
        except (TypeError, ValueError):
            coupon = 0
        items.append({
            'goodsId': g.get('goodsSign') or g.get('goods_id'),
            'title': g.get('goodsName') or g.get('goods_name', ''),
            'actualPrice': g.get('minGroupPrice') or g.get('min_on_sale_group_price', 0) / 100,
            'originalPrice': g.get('marketPrice'),
            'coupon_amount': coupon,
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
            'coupon_amount': g.get('couponPrice', 0),
            'monthSales': g.get('monthSales', 0),
            'shopName': g.get('shopName', ''),
            'brand': g.get('brandName') or g.get('brand', ''),  # brandName 才是品牌名，brand=1/0 是是否品牌商品
            'platform': platform,
            'url': g.get('itemLink'),
            'coupon_end': g.get('couponEndTime'),
            'coupon_link': g.get('couponLink'),
            'coupon_cond': g.get('couponConditions'),
            # v6.1 店铺信誉字段（大淘客现成：DSR/服务/发货分 + 店铺等级 + 金牌卖家）
            'shop_level': g.get('shopLevel'),
            'dsr_score': g.get('dsrScore') or g.get('descScore'),
            'service_score': g.get('serviceScore'),
            'ship_score': g.get('shipScore'),
            'gold_seller': g.get('goldSellers'),
            'seller_id': g.get('sellerId'),
            'shop_type': '天猫' if g.get('shopType') == 1 else '',
        })
    return items

if __name__ == '__main__':
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else '羽绒服'
    items = search_goods(kw)
    print(f'「{kw}」返回 {len(items)} 条：')
    for i, it in enumerate(items[:5], 1):
        print(f'  {i}. {it["title"][:35]} | ¥{it["actualPrice"]} | 券¥{it["coupon_amount"]} | 月销{it["monthSales"]}')


def value_score(item: dict) -> float:
    """性价比评分（用户需求：按物品贵重程度动态调权重）
    贵重物（≥500元）：店铺 0.5 主导 —— 买电脑必须看店铺靠不靠谱
    普通品（50-500）：店铺 0.3 + 销量 0.4
    小件（<50元）：店铺 0.15 + 价格销量主导 —— 买螺丝便宜就行"""
    try:
        sales = float(item.get('monthSales', 0) or 0)
        price = float(item.get('actualPrice', 0) or 0)
    except (TypeError, ValueError):
        sales, price = 0, 0
    sales_score = min(sales / 10000, 1.0)
    price_score = 1.0 / (1.0 + price / 1000)
    try:
        from shop_rating import shop_rating_of
        shop_score = shop_rating_of(item)['rating'] / 5.0
    except Exception:
        shop_score = 0.8
    # 动态权重：按价格分档（贵重物店铺权重高，小件价格销量权重高）
    if price >= 500:
        w_shop, w_sales, w_price = 0.5, 0.2, 0.3
    elif price >= 50:
        w_shop, w_sales, w_price = 0.3, 0.4, 0.3
    else:
        w_shop, w_sales, w_price = 0.15, 0.5, 0.35
    return round((sales_score * w_sales + shop_score * w_shop + price_score * w_price) * 100, 1)
