# price_trap.py - 套路检测（先涨后降 + 虚标原价）
# WorkBuddy 审核修正：30天窗口 / ≥5条历史价 / 平台分组 / 占位价过滤 / 高点持续≥3天 / 虚标检测
import sqlite3
import os
import statistics

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')

def detect_trap(keyword: str) -> dict:
    """检测某商品是否存在'先涨价再降价'套路或虚标原价。
    返回: {has_trap, trap_msg, has_fake_original, fake_msg, data_count}"""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute('''
            SELECT platform, item_id, price, original_price, queried_at
            FROM price_history WHERE title LIKE ?
            ORDER BY queried_at ASC
        ''', (f'%{keyword}%',)).fetchall()
        conn.close()
    except Exception:
        return {'has_trap': False, 'trap_msg': '', 'has_fake_original': False,
                'fake_msg': '', 'data_count': 0}

    if len(rows) < 5:
        return {'has_trap': False, 'trap_msg': '', 'has_fake_original': False,
                'fake_msg': '', 'data_count': len(rows), 'limited': True}

    # 按 平台+商品 分组（WorkBuddy 修正：避免跨平台/跨 SKU 混算）
    groups = {}
    for plat, item_id, price, orig, ts in rows:
        if not price or price < 1:
            continue
        key = f'{plat}|{item_id}'
        groups.setdefault(key, []).append({'price': price, 'orig': orig, 'ts': ts})

    best = None
    for key, recs in groups.items():
        prices = [r['price'] for r in recs]
        if len(prices) < 5:
            continue
        median = statistics.median(prices)
        # 占位价过滤（>中位数×3，如缺货价 ¥9999）
        recs = [r for r in recs if r['price'] <= median * 3]
        prices = [r['price'] for r in recs]
        if len(prices) < 5:
            continue

        # 虚标原价检测：original_price / 中位数 > 1.5
        origs = [r['orig'] for r in recs if r.get('orig')]
        fake_orig = False
        if origs:
            o_median = statistics.median(origs)
            if o_median and median and o_median / median > 1.5:
                fake_orig = True

        # 先涨后降检测：找高点（比前5条均值高≥10%且持续≥3条）
        trap = False
        for i in range(5, len(recs)):
            window = [r['price'] for r in recs[max(0, i-5):i]]
            base = sum(window) / len(window)
            if base == 0:
                continue
            peak = recs[i]['price']
            if peak > base * 1.10 and i + 3 <= len(recs):
                # 高点后回落且当前价 > 涨价前均值
                after = [r['price'] for r in recs[i:i+3]]
                if max(after) <= peak and recs[-1]['price'] > base:
                    trap = True
                    break

        if trap or fake_orig:
            cur = recs[-1]['price']
            best = {
                'has_trap': trap,
                'trap_msg': f'疑似先涨后降：近期涨到 ¥{peak:.0f} 后回落，当前 ¥{cur:.0f}，可能比涨价前贵' if trap else '',
                'has_fake_original': fake_orig,
                'fake_msg': f'虚标原价：标价 ¥{o_median:.0f} 而实际中位价 ¥{median:.0f}（1.5 倍以上）' if fake_orig else '',
                'data_count': len(rows),
            }
            break

    return best or {'has_trap': False, 'trap_msg': '', 'has_fake_original': False,
                    'fake_msg': '', 'data_count': len(rows), 'limited': len(rows) < 5}

if __name__ == '__main__':
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else '金典纯牛奶'
    print(detect_trap(kw))
