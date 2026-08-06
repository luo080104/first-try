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
