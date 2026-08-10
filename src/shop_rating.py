# shop_rating.py - 店铺信誉评分（v6.1，用户核心需求：识别"假旗舰店"）
# 原则：不看名字看数据——评分/等级/好评率/成立时间综合，新店小铺自动降权
import os
import re
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')


def shop_rating_of(item: dict) -> dict:
    """计算店铺信誉分（0-5，基础 4.0）：
    名称信号 + 平台评分(DSR/服务/物流/好评率) + 店铺等级 + 成立年限（来自 shop_profiles 表）
    返回 {'rating': float, 'label': str, 'founded': int|None}"""
    plat = item.get('platform', '')
    shop_name = str(item.get('shopName') or '')
    rating = 4.0
    signals = []

    # 1) 名称信号（仅参考，不迷信——名字可以造假，所以只给少量分）
    st = str(item.get('shop_type') or '')
    if plat == 'jd' and ('自营' in shop_name or st == '自营'):
        rating += 0.6; signals.append('京东自营')
    elif plat == 'tb' and st == '天猫':
        rating += 0.6; signals.append('天猫')
    elif '旗舰店' in shop_name:
        rating += 0.3; signals.append('旗舰店')
    elif st == '百亿补贴' or '百亿补贴' in shop_name:
        rating += 0.3; signals.append('百亿补贴')

    # 2) 平台评分数据（硬指标）
    dsr = _num(item.get('dsr_score'))
    if dsr:
        if dsr >= 4.8: rating += 0.3; signals.append(f'DSR {dsr}')
        elif dsr >= 4.5: rating += 0.1
        elif dsr < 4.2: rating -= 0.4; signals.append(f'⚠️DSR低 {dsr}')
    svc = _num(item.get('service_score'))
    if svc and svc < 4.2: rating -= 0.3
    ship = _num(item.get('ship_score'))
    if ship and ship < 4.2: rating -= 0.2
    gcr = _num(item.get('good_comment_rate'))
    if gcr:
        if gcr >= 98: rating += 0.3; signals.append(f'好评{gcr}%')
        elif gcr < 90: rating -= 0.5; signals.append(f'⚠️好评{gcr}%')

    # 3) 店铺等级（淘宝 shopLevel / 京东 shopLevel）
    lv = _num(item.get('shop_level'))
    if lv:
        if lv >= 15: rating += 0.2; signals.append(f'等级{lv}')
        elif lv <= 5: rating -= 0.2

    # 4) 金牌卖家
    if item.get('gold_seller') in (1, '1', True):
        rating += 0.2; signals.append('金牌卖家')

    # 5) 成立年限（shop_profiles 表，爬店铺页积累；无数据不评分）
    founded = None
    shop_key = f'{plat}|{shop_name}'
    frow = _get_founded(shop_key)
    if frow:
        founded = frow
        age = _current_year() - founded
        if age >= 5: rating += 0.5; signals.append(f'{age}年老店')
        elif age >= 3: rating += 0.3; signals.append(f'{age}年店')
        elif age >= 2: signals.append(f'{age}年店')
        else:
            # 2 年内：新店降权（用户核心需求：识别创立没几天的小店）
            rating -= 0.8 if age <= 0 else 0.5
            signals.append(f'⚠️新店({founded}年开)')

    rating = round(max(1.0, min(5.0, rating)), 1)
    return {'rating': rating, 'label': '、'.join(signals[:4]), 'founded': founded}


# ========== 成立时间（shop_profiles 表缓存）==========

def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_shop_table():
    conn = _get_conn()
    conn.execute('''CREATE TABLE IF NOT EXISTS shop_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        shop_key TEXT NOT NULL UNIQUE,     -- 'platform|shopName'
        platform TEXT,
        shop_name TEXT,
        shop_id TEXT DEFAULT '',
        founded_year INTEGER,              -- 成立年份
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    conn.commit()
    conn.close()


def _get_founded(shop_key: str):
    init_shop_table()
    try:
        conn = _get_conn()
        row = conn.execute('SELECT founded_year FROM shop_profiles WHERE shop_key=?', (shop_key,)).fetchone()
        conn.close()
        return row['founded_year'] if row and row['founded_year'] else None
    except Exception:
        return None


def save_shop_founded(shop_key: str, platform: str, shop_name: str, shop_id: str, founded_year: int):
    """保存店铺成立年份（爬店铺页后调用）"""
    init_shop_table()
    conn = _get_conn()
    conn.execute('''INSERT INTO shop_profiles (shop_key, platform, shop_name, shop_id, founded_year)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(shop_key) DO UPDATE SET
                        founded_year=excluded.founded_year, shop_id=excluded.shop_id,
                        updated_at=datetime('now','localtime')''',
                 (shop_key, platform, shop_name[:60], str(shop_id)[:40], founded_year))
    conn.commit()
    conn.close()


# ========== 京东店铺页爬成立时间（mall.jd.com/index-{shopId}.html）==========

def fetch_jd_shop_founded(shop_id: str, shop_name: str = '') -> int:
    """爬京东店铺页提取开店年份；失败返回 None。低频只读。"""
    import time as _t
    if not shop_id:
        return None
    try:
        import urllib.request
        url = f'https://mall.jd.com/index-{shop_id}.html'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36'})
        html = urllib.request.urlopen(req, timeout=12).read().decode('utf-8', errors='ignore')
        # 常见模式：'开店时间：2014-05-20' / '2014年' / '开店于2014'
        for pat in [r'开店时间[:：]?\s*(\d{4})', r'开店于\s*(\d{4})', r'(\d{4})年开[店设]']:
            m = re.search(pat, html)
            if m:
                year = int(m.group(1))
                if 1990 < year <= _t.localtime().tm_year:
                    return year
        return None
    except Exception:
        return None


def _num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return 0


def _current_year():
    import time as _t
    return _t.localtime().tm_year


if __name__ == '__main__':
    # 自测
    tests = [
        # 真自营：高评分
        {'platform': 'jd', 'shopName': '京喜自营官方店', 'good_comment_rate': 98, 'shop_level': 20},
        # 假旗舰店：低评分新店（founded 模拟）
        {'platform': 'tb', 'shopName': '某某品牌旗舰店', 'dsr_score': 4.1, 'shop_level': 3, 'shop_type': '天猫'},
    ]
    for t in tests:
        print(shop_rating_of(t))
