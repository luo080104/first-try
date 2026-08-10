# vip_search.py - 唯品会搜索（DrissionPage，category.vip.com/suggest.php）
# 约束：真浏览器+登录态(vip_profile) / 低频(12-20s随机) / 只读提取
# 入口：category.vip.com/suggest.php?keyword=xxx&ff=235|12|页码|1（PC 搜索页，2026-08 实测可用）
import sys
import os
import time
import re
import random

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'vip_profile')
_last_call_time = 0  # 低频约束
LOCAL_PORT = 9302  # 唯品会专属端口（淘宝9300/京东9301/CDP 9222）


def _find_browser():
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return p
    return None


def search_vip(keyword: str, max_items: int = 20, login_wait: int = 150, page: int = 1) -> list:
    """唯品会关键词搜索（浏览器）。
    返回: [{platform, title, price, original_price, sales, shop, url, item_id, goodsId}]
    未登录时返回 [] 并提示。"""
    global _last_call_time
    # 低频约束：12-20s 随机抖动
    wait = random.uniform(12, 20) - (time.time() - _last_call_time)
    if wait > 0:
        print(f'⏳ 唯品会频率控制，等待 {int(wait)} 秒...')
        time.sleep(wait)
    _last_call_time = time.time()

    browser_path = _find_browser()
    if not browser_path:
        print('❌ 未找到 Chrome/Edge')
        return []

    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(browser_path)
    co.set_local_port(LOCAL_PORT)
    co.set_user_data_path(PROFILE_DIR)
    co.set_argument('--window-position=-32000,-32000')  # 窗口移出屏幕：不打扰用户且保持真实渲染
    co.set_argument('--start-maximized')
    browser = Chromium(co)
    tab = browser.latest_tab

    try:
        # 搜索入口（ff=品牌|分类|页码|排序，页码位可翻页）
        url = f'https://category.vip.com/suggest.php?keyword={keyword}&ff=235%7C12%7C{page}%7C1'
        tab.get(url)
        tab.wait.doc_loaded()
        time.sleep(3)

        # 触发懒加载
        tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(2)
        tab.run_js('window.scrollTo(0, 0)')
        time.sleep(1)

        cards = tab.eles('css:.c-goods-item', timeout=6)
        items = []
        for c in cards[:max_items + 4]:
            try:
                # 商品链接 → goodsId（productId 是最后一段数字）
                link_ele = c.ele('tag:a', timeout=2)
                href = link_ele.attr('href') or '' if link_ele else ''
                m = re.search(r'detail-(\d+)-(\d+)\.html', href)
                if not m:
                    continue
                brand_id, product_id = m.group(1), m.group(2)

                # 商品名
                title = ''
                try:
                    title = c.ele('css:.c-goods-item__name', timeout=2).text.strip()[:100]
                except Exception:
                    pass

                # 价格：价格区文本（特卖价 ¥227 ¥328 6.9折 60天低价）
                price = None
                original = None
                try:
                    ptext = c.ele('css:.c-goods-item__price', timeout=2).text
                    nums = re.findall(r'¥\s*(\d+(?:\.\d+)?)', ptext)
                    if nums:
                        price = float(nums[0])
                        original = float(nums[1]) if len(nums) > 1 else None
                except Exception:
                    pass
                if not price:
                    continue

                # 品牌：页面顶部品牌区（每页同一品牌居多）
                brand = ''
                try:
                    brand_ele = tab.ele('css:.brand-title', timeout=1)
                    brand = brand_ele.text.strip() if brand_ele else ''
                except Exception:
                    pass

                items.append({
                    'platform': 'vip',
                    'title': title,
                    'price': price,
                    'original_price': original if original and original > price else None,
                    'sales': '',
                    'shop': '唯品会',
                    'is_ad': False,
                    'item_id': product_id,
                    'goodsId': product_id,
                    'brand': brand,
                    'url': f'https://detail.vip.com/detail-{brand_id}-{product_id}.html',
                })
            except Exception:
                continue
        return items[:max_items]
    finally:
        browser.quit()


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '球鞋'
    items = search_vip(kw)
    print(f'\n唯品会「{kw}」: {len(items)} 条')
    for it in items:
        print(f"  ¥{it['price']} | {it['title'][:35]} | 原价{it['original_price']} | {it['url'][:50]}")
