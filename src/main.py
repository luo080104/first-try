# main.py - 购物助手命令行入口（阶段 1 MVP）
# 用法: python src/main.py "羽绒服" [品类]
# 流程: 搜索 → 展示 → 存入 SQLite
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from api_client import search_goods
from db import init_db, get_conn, save_search_result, recent_prices

def main():
    if len(sys.argv) < 2:
        print('用法: python src/main.py "商品关键词" [品类]')
        print('品类可选: 服饰 / 食品 / 日用百货 / 数码家电')
        return

    keywords = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None

    # 1. 初始化数据库
    init_db()

    # 2. 搜索
    print(f'\n🔍 搜索「{keywords}」' + (f'（品类: {category}）' if category else '') + '...')
    items = search_goods(keywords, category)

    if not items:
        print('❌ 没有搜到结果（该商品可能未设佣金）')
        return

    # 3. 展示
    print(f'\n✅ 找到 {len(items)} 个结果：')
    print('─' * 60)
    for i, it in enumerate(items[:10], 1):
        print(f'{i:2d}. {it["title"][:38]}')
        print(f'     💰 ¥{it["actualPrice"]}  | 券 ¥{it["couponPrice"]} | 原价 ¥{it["originalPrice"] or "-"} | 月销 {it["monthSales"]}')
        print(f'     店铺: {it["shopName"]}  | 品牌: {it["brand"] or "-"}')
    print('─' * 60)

    # 4. 存库（方案 B：商品+SKU+价格全链路）
    conn = get_conn()
    saved = 0
    for it in items:
        save_search_result(conn, it, category or '未分类')
        saved += 1
    conn.close()
    print(f'💾 已存入数据库: {saved} 条价格记录')

    # 5. 展示库里最近的记录（验证闭环）
    print('\n📊 数据库最近记录：')
    conn = get_conn()
    for row in recent_prices(conn, 5):
        print(f'   [{row["queried_at"][11:19]}] {row["brand"] or "?"} {row["series"][:15]} | ¥{row["price"]} | 券¥{row["coupon_amount"]}')
    conn.close()
    print('\n✅ 阶段 1 闭环完成：搜索 → 展示 → 存库')

if __name__ == '__main__':
    main()
