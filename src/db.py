# db.py - SQLite 数据层（阶段 1）
# 职责：建库建表 + 商品/SKU/价格历史保存
import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema.sql')

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """建库建表（幂等：已存在则跳过）"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    with open(SCHEMA_PATH, encoding='utf-8') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f'✅ 数据库就绪: {DB_PATH}')

def find_product(conn, brand: str, series: str):
    """按 品牌+系列 查找已有商品"""
    cur = conn.execute('SELECT * FROM products WHERE brand=? AND series=?', (brand, series))
    return cur.fetchone()

def upsert_product(conn, brand: str, series: str, category: str) -> int:
    """插入商品，已存在则返回现有 id"""
    row = find_product(conn, brand, series)
    if row:
        return row['id']
    cur = conn.execute('INSERT INTO products (brand, series, category) VALUES (?,?,?)',
                       (brand, series, category))
    conn.commit()
    return cur.lastrowid

def find_sku(conn, product_id: int, raw_title: str):
    cur = conn.execute('SELECT * FROM skus WHERE product_id=? AND raw_title=?', (product_id, raw_title))
    return cur.fetchone()

def upsert_sku(conn, product_id: int, specs: dict, raw_title: str) -> int:
    """插入 SKU（同标题视为同 SKU）"""
    row = find_sku(conn, product_id, raw_title)
    if row:
        return row['id']
    cur = conn.execute('INSERT INTO skus (product_id, specs, raw_title) VALUES (?,?,?)',
                       (product_id, json.dumps(specs, ensure_ascii=False), raw_title))
    conn.commit()
    return cur.lastrowid

def save_price(conn, sku_id, platform, item_id, title, price, original_price,
               coupon_amount, coupon_expire, url):
    """保存价格历史（每次查询都记录）"""
    cur = conn.execute('''
        INSERT INTO price_history
        (sku_id, platform, item_id, title, price, original_price, coupon_amount, coupon_expire, url)
        VALUES (?,?,?,?,?,?,?,?,?)
    ''', (sku_id, platform, item_id, title, price, original_price, coupon_amount, coupon_expire, url))
    conn.commit()
    return cur.lastrowid

def save_search_result(conn, item: dict, category: str):
    """保存一条搜索结果：商品 → SKU → 价格历史（方案 B：全链路）"""
    # 商品归一化：阶段 1 先用"品牌 + 关键词前缀"做最简匹配，阶段 2 完善
    brand = item.get('brand') or '未知品牌'
    series = item.get('series') or item.get('title', '')[:20]
    product_id = upsert_product(conn, brand, series, category)
    specs = {}  # 阶段 1 先留空，阶段 2 做参数提取
    sku_id = upsert_sku(conn, product_id, specs, item.get('title', ''))
    save_price(
        conn, sku_id,
        platform=item.get('platform', 'tb'),
        item_id=str(item.get('goodsId', '')),
        title=item.get('title', ''),
        price=item.get('actualPrice', 0),
        original_price=item.get('originalPrice'),
        coupon_amount=item.get('couponPrice', 0),
        coupon_expire=None,
        url=item.get('goodsId', '') and f"https://detail.tmall.com/item.htm?id={item.get('goodsId')}" or None,
    )

def recent_prices(conn, limit=10):
    """最近价格记录（验证用）"""
    cur = conn.execute('''
        SELECT p.brand, p.series, ph.platform, ph.title, ph.price, ph.coupon_amount, ph.queried_at
        FROM price_history ph
        JOIN skus s ON s.id = ph.sku_id
        JOIN products p ON p.id = s.product_id
        ORDER BY ph.queried_at DESC LIMIT ?
    ''', (limit,))
    return cur.fetchall()

def save_manual_price(keyword, title, platform, shop_name, price, url, note=''):
    """保存人工录入价格"""
    conn = get_conn()
    cur = conn.execute('''
        INSERT INTO manual_prices (keyword, title, platform, shop_name, price, url, note)
        VALUES (?,?,?,?,?,?,?)
    ''', (keyword, title, platform, shop_name, price, url, note))
    conn.commit()
    conn.close()
    return cur.lastrowid

def find_manual_prices(keyword, limit=10):
    """按关键词匹配人工录入价（模糊匹配）"""
    conn = get_conn()
    cur = conn.execute('''
        SELECT * FROM manual_prices
        WHERE keyword LIKE ? OR title LIKE ?
        ORDER BY price ASC LIMIT ?
    ''', (f'%{keyword}%', f'%{keyword}%', limit))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== 盯价功能 ==========

def add_watch(title, platform, item_id, current_price, target_price):
    """添加盯价"""
    conn = get_conn()
    cur = conn.execute('''
        INSERT INTO watched_items (title, platform, item_id, current_price, target_price, is_active)
        VALUES (?,?,?,?,?,1)
    ''', (title, platform, item_id, current_price, target_price))
    conn.commit()
    conn.close()
    return cur.lastrowid

def list_watches():
    """盯价列表（含最近价格历史）"""
    conn = get_conn()
    cur = conn.execute('''
        SELECT id, title, platform, item_id, current_price, target_price, is_active, created_at
        FROM watched_items ORDER BY created_at DESC LIMIT 20
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def check_watches():
    """检查盯价是否达标（当前价 <= 目标价）"""
    watches = list_watches()
    hits = []
    for w in watches:
        if w.get('current_price') and w.get('target_price'):
            if w['current_price'] <= w['target_price']:
                hits.append(w)
    return hits

# ========== 国补/优惠政策 ==========

# 关键词 → 品类映射（用于政策匹配商品标题/搜索词）
SUBSIDY_KEYWORDS = {
    '数码家电': ['笔记本', '电脑', '手机', '平板', '电视', '冰箱', '空调', '洗衣机', '相机', '耳机',
                '显示器', '显卡', '游戏本', '轻薄本', '电竞', 'mate', 'iphone', 'ipad', 'redmi', '荣耀', '小米'],
    '食品': ['牛奶', '纯奶', '酸奶', '坚果', '零食', '粮油', '咖啡', '茶叶', '礼盒'],
    '服饰': ['羽绒服', '外套', '鞋', '运动鞋', '卫衣', '裤'],
}

def add_subsidy(region, category, amount, requirements, valid_from='', valid_to='', source_url=''):
    """人工维护国补/优惠政策"""
    conn = get_conn()
    cur = conn.execute('''
        INSERT INTO subsidy_policies (region, category, amount, requirements, valid_from, valid_to, source_url)
        VALUES (?,?,?,?,?,?,?)
    ''', (region, category, amount, requirements, valid_from, valid_to, source_url))
    conn.commit()
    conn.close()
    return cur.lastrowid

def list_subsidies():
    """全部政策（管理用）"""
    conn = get_conn()
    cur = conn.execute('''
        SELECT * FROM subsidy_policies
        WHERE (valid_to = '' OR valid_to >= date('now','localtime'))
        ORDER BY updated_at DESC
    ''')
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def find_subsidies(keyword: str, category: str = '') -> list:
    """按搜索词/品类匹配生效中的政策"""
    conn = get_conn()
    kw = (keyword or '').lower()
    rows = conn.execute('''
        SELECT * FROM subsidy_policies
        WHERE (valid_to = '' OR valid_to >= date('now','localtime'))
    ''').fetchall()
    conn.close()
    hits = []
    for r in rows:
        d = dict(r)
        # 1) 品类直接命中；2) 政策要求文本含搜索词；3) 品类关键词映射命中
        req = (d.get('requirements') or '').lower()
        if category and d.get('category') == category:
            hits.append(d); continue
        if kw and kw in req:
            hits.append(d); continue
        for c, words in SUBSIDY_KEYWORDS.items():
            if any(w in kw for w in words):
                if d.get('category') == c:
                    hits.append(d)
                    break
    return hits
