# fill_shop_founded.py - 店铺成立时间回填（v1.0-⑥，小布方案：500家×15s≈2小时，通宵跑）
# 流程：商品库淘宝商品（数字ID）→ 详情页提取 shop_user_id → 店铺页爬成立时间 → 存 shop_profiles
# 低频 15-20s；断点续跑（已处理的 item_id 跳过）；失败重试下轮
import sys
import os
import time
import re
import random
import sqlite3

sys.path.insert(0, os.path.dirname(__file__))

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

DONE_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'shop_fill_done.txt')


def load_done():
    try:
        return set(open(DONE_FILE, encoding='utf-8').read().splitlines())
    except Exception:
        return set()


def save_done(done, iid):
    done.add(iid)
    with open(DONE_FILE, 'a', encoding='utf-8') as f:
        f.write(iid + '\n')


def crawl_shop_founded(user_id: str, shop_name: str) -> int:
    """爬淘宝店铺页（shop{userId}.taobao.com）拿成立年份"""
    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(EDGE)
    co.set_local_port(9300)
    co.set_user_data_path(os.path.join(os.path.dirname(__file__), '..', 'data', 'tb_profile'))
    browser = Chromium(co)
    tab = browser.latest_tab
    try:
        tab.get('https://www.taobao.com/')
        tab.wait.doc_loaded()
        time.sleep(4)
        tab.get(f'https://shop{user_id}.taobao.com/')
        tab.wait.doc_loaded()
        time.sleep(6)
        html = tab.html
        for pat in [r'创店时间[：:]\s*([\d-]{7,10})', r'开店时间[：:]\s*([\d-]{7,10})',
                    r'(\d{4})年[\d-]*月[\d-]*日开店', r'店铺创建[：:]\s*(\d{4})']:
            m = re.search(pat, html)
            if m:
                year = int(m.group(1)[:4])
                if 1990 < year <= time.localtime().tm_year:
                    return year
        return 0
    except Exception as e:
        print(f'[fill] 店铺页失败 {user_id}: {str(e)[:50]}')
        return 0
    finally:
        browser.quit()


def main(limit: int = 500):
    from shop_rating import save_shop_founded
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 淘宝商品（数字 ID：source=browser 或 url 含纯数字 id）
    rows = conn.execute('''SELECT item_id, shop_name FROM product_items
        WHERE platform='tb' AND item_id != '' AND shop_name != ''
        AND item_id GLOB '*[0-9]*' AND item_id NOT GLOB '*[a-zA-Z]*'
        LIMIT 2000''').fetchall()
    conn.close()
    done = load_done()
    candidates = [(r['item_id'], r['shop_name']) for r in rows if r['item_id'] not in done]
    print(f'候选: {len(candidates)} 个（已处理 {len(done)}）')
    filled = 0
    for iid, shop in candidates[:limit]:
        # 详情页提取 shop_user_id
        try:
            from detail_crawler import crawl_tb_detail
            detail = crawl_tb_detail(iid)
            uid = detail.get('shop_user_id', '')
        except Exception as e:
            print(f'[fill] 详情失败 {iid}: {str(e)[:40]}')
            uid = ''
        if uid:
            year = crawl_shop_founded(uid, shop)
            if year:
                save_shop_founded(f'tb|{shop[:60]}', 'tb', shop, uid, year)
                filled += 1
                print(f'✅ {shop[:15]}: 成立 {year} 年')
        save_done(done, iid)
        # 低频
        time.sleep(random.uniform(15, 20))
    print(f'完成: 本次 {filled} 家（累计已处理 {len(done)}）')


if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    print('=== 店铺成立时间回填（通宵任务，Ctrl+C 可停，断点续跑）===')
    while True:
        main(n)
        print('一轮完成，10 分钟后下一轮（断点续跑）')
        time.sleep(600)
