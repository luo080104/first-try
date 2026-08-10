# wander.py - 购物漫游（v7，多案例融合：多路召回+六因子排序+MMR多样性+反馈闭环）
# 召回四路：画像品类 60% / 关联(相似) 25% / 探索新品类 15% / 热门兜底
# 排序：匹配度0.40 + 价格适配0.20 + 性价比0.15 + 新颖度0.10 + 店铺信誉0.10 - 重复0.15
import os
import sys
import json
import random
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _profile_categories(user_name: str) -> list:
    """用户画像关注的品类（大品类：服饰/食品/日用百货/数码家电）"""
    from guide import get_profile
    cats = get_profile(user_name).get('categories') or []
    # 画像里可能是细品类词，映射到大品类
    MAP = {'数码家电': '数码家电', '游戏': '数码家电'}
    return [MAP.get(c, c) for c in cats if c]


def _recent_categories(user_name: str) -> list:
    """最近搜索的品类（search_history 兜底）"""
    try:
        conn = _get_conn()
        rows = conn.execute('''SELECT category, COUNT(*) n FROM search_history
            WHERE user_name=? AND category != '' GROUP BY category ORDER BY n DESC LIMIT 3''',
                            (user_name or '',)).fetchall()
        conn.close()
        return [r['category'] for r in rows]
    except Exception:
        return []


def wander_recommend(user_name: str = '', size: int = 12, exclude_ids: list = None) -> list:
    """购物漫游：四路召回 + 六因子排序 + 品类多样性 + 价格带降权（不过滤）。返回推荐卡片列表。"""
    exclude_ids = exclude_ids or []
    cats = _profile_categories(user_name) + _recent_categories(user_name)
    cats = list(dict.fromkeys(cats))  # 去重保序
    # 价格带适配（WorkBuddy：降权不过滤——漫游精髓是发现意外）：
    # 用户预算档（低/中/高）→ 匹配的价格带商品加分，其他价格带不减分
    from guide import get_profile
    budget_tier = get_profile(user_name).get('budget_tier') or ''
    conn = _get_conn()

    def pick(category: str, limit: int):
        if not category:
            return []
        rows = conn.execute('''SELECT * FROM product_items
            WHERE category=? AND price > 0 ORDER BY sales DESC LIMIT ?''', (category, limit)).fetchall()
        return [dict(r) for r in rows]

    candidates = []
    # ① 画像品类召回（60%）
    quota = int(size * 0.6)
    if cats:
        per = max(quota // len(cats), 3)
        for c in cats:
            candidates += pick(c, per)
    # ② 关联召回（25%）：最近搜索词的商品
    quota2 = int(size * 0.25)
    try:
        rows = conn.execute('''SELECT keyword FROM search_history WHERE user_name=? ORDER BY searched_at DESC LIMIT 3''',
                            (user_name or '',)).fetchall()
        kws = [r['keyword'] for r in rows]
        for kw in kws[:2]:
            got = conn.execute('''SELECT * FROM product_items WHERE title LIKE ? AND price > 0 ORDER BY sales DESC LIMIT ?''',
                               (f'%{kw}%', quota2)).fetchall()
            candidates += [dict(r) for r in got]
    except Exception:
        pass
    # ③ 探索召回（15%）：未关注的品类随机
    quota3 = max(int(size * 0.15), 2)
    all_cats = [r['category'] for r in conn.execute(
        "SELECT DISTINCT category FROM product_items WHERE category != '' AND category NOT IN (SELECT DISTINCT category FROM product_items WHERE category IN ('服饰','食品','日用百货','数码家电'))").fetchall()] if False else None
    explore_cats = [c for c in ['服饰', '食品', '日用百货', '数码家电'] if c not in cats]
    if explore_cats:
        ec = random.choice(explore_cats)
        candidates += pick(ec, quota3)
    # ④ 热门兜底（补满）
    if len(candidates) < size:
        got = conn.execute('''SELECT * FROM product_items WHERE price > 0 ORDER BY sales DESC LIMIT ?''',
                           (size * 2,)).fetchall()
        candidates += [dict(r) for r in got]

    # 去重 + 排除不感兴趣
    seen, pool = set(), []
    for it in candidates:
        k = f"{it['platform']}|{it['item_id']}"
        if k not in seen and it['item_id'] not in exclude_ids:
            seen.add(k)
            pool.append(it)

    # 六因子排序
    def rank(it):
        price = it['price'] or 0
        s = 0.0
        # 匹配度（品类命中画像 +0.4）
        if it['category'] in cats:
            s += 0.40
        else:
            s += 0.15
        # 价格适配（50-500 大众区间 +0.2，其他递减）
        if 10 <= price <= 1000:
            s += 0.20
        elif price > 0:
            s += 0.10
        # 价格带适配降权（WorkBuddy：加但不过滤——发现意外）
        # 预算档低：低价商品 +0.10；预算档高：高价商品 +0.10；其他价格带不扣分
        if budget_tier:
            if budget_tier == '低' and 0 < price <= 300:
                s += 0.10
            elif budget_tier == '高' and price >= 3000:
                s += 0.10
            elif budget_tier == '中' and 300 <= price <= 3000:
                s += 0.05
        # 性价比（销量归一 +0.15）
        s += min(it['sales'] or 0, 50000) / 50000 * 0.15
        # 新颖度（随机 +0.10）
        s += random.uniform(0.05, 0.10)
        # 店铺信誉（无数据给中值 +0.10）
        try:
            from shop_rating import shop_rating_of
            sr = shop_rating_of({'platform': it['platform'], 'shopName': it['shop_name']})
            s += sr['rating'] / 5.0 * 0.10
        except Exception:
            s += 0.08
        return s

    pool.sort(key=rank, reverse=True)

    # MMR 多样性：同一品类最多 40%
    max_per_cat = max(int(size * 0.4), 1)
    cat_count, final = {}, []
    for it in pool:
        c = it['category'] or '未分类'
        if cat_count.get(c, 0) >= max_per_cat:
            continue
        cat_count[c] = cat_count.get(c, 0) + 1
        final.append(it)
        if len(final) >= size:
            break

    conn.close()
    return final


if __name__ == '__main__':
    items = wander_recommend('嘉铭', 12)
    print(f'漫游推荐 {len(items)} 个:')
    for it in items:
        print(f"  ¥{it['price']:>8} | {it['category'] or '未分类':<6} | {it['title'][:30]}")
