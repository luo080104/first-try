# main.py - Go购命令行入口 v2.0（阶段 2 雏形）
# 用法: python src/main.py "羽绒服" [品类]
# 流程: 双平台搜索 → SKU 分组 → 比价展示 → 存入 SQLite
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from api_client import search_goods, search_pdd
from matcher import parse_items, group_by_sku, ADAPTERS
from db import init_db, get_conn, save_search_result, recent_prices

def show_sku_comparison(groups: dict, max_groups: int = 5):
    """按 SKU 组展示比价：每组列出各平台最低价"""
    print('─' * 60)
    shown = 0
    for key, items in groups.items():
        if not key or key == '未解析':
            continue
        shown += 1
        if shown > max_groups:
            break
        # 组内各平台最低价
        by_platform = {}
        for it in items:
            p = it.get('platform', '?')
            if p not in by_platform or it['actualPrice'] < by_platform[p]['actualPrice']:
                by_platform[p] = it
        print(f'\n📦 SKU: {key}（{len(items)} 个候选）')
        for p, best in sorted(by_platform.items(), key=lambda x: x[1]['actualPrice']):
            mark = '⭐' if best is min(by_platform.values(), key=lambda x: x['actualPrice']) else '  '
            coupon = best.get('coupon_amount') or best.get('couponPrice') or 0
            print(f'  {mark} [{p}] ¥{best["actualPrice"]:>8} | 券¥{coupon:<5} | {best["title"][:32]}')
    if shown == 0:
        print('\n⚠️ 品类未适配（暂无适配器），显示原始列表')

def main():
    if len(sys.argv) < 2:
        print('用法: python src/main.py "商品关键词" [品类]')
        print('品类可选: 服饰 / 食品 / 日用百货 / 数码家电')
        return

    keywords = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None

    init_db()

    # 双平台搜索（缓存命中则不调 API）
    print(f'\n🔍 比价「{keywords}」' + (f'（品类: {category}）' if category else '') + '...')
    tb_items = search_goods(keywords, category)
    pdd_items = search_pdd(keywords)
    all_items = tb_items + pdd_items
    print(f'✅ 淘宝 {len(tb_items)} 条 + 拼多多 {len(pdd_items)} 条 = {len(all_items)} 条候选')

    if not all_items:
        print('❌ 没有搜到结果（该商品可能未设佣金）')
        return

    # SKU 分组比价（有适配器时）
    if category and category in ADAPTERS and ADAPTERS[category]:
        parsed = parse_items(all_items, category)
        groups = group_by_sku(parsed, category)
        print(f'\n📊 按 SKU 分组：{len(groups)} 组')
        show_sku_comparison(groups)
    else:
        print('\n📋 原始列表（未分组）：')
        for i, it in enumerate(all_items[:10], 1):
            print(f'{i:2d}. [{it["platform"]}] ¥{it["actualPrice"]:>8} | {it["title"][:36]}')

    # 存库
    conn = get_conn()
    for it in all_items:
        save_search_result(conn, it, category or '未分类')
    conn.close()
    print(f'\n💾 已存入数据库 {len(all_items)} 条价格记录')
    print('✅ 比价完成')

if __name__ == '__main__':
    main()
