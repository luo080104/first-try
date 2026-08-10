# pdd_search.py - 拼多多 H5 搜索（DrissionPage，登录态 pdd_profile）
# 约束：真浏览器+登录态 / 低频(12-20s随机) / 遇验证码抛 CaptchaError（按合规原则不绕）
# 入口：mobile.yangkeduo.com/search_result.html?search_key=xxx（2026-08-10 实测：等 10s 数据注入页面 JSON）
import sys
import os
import time
import re
import random

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'pdd_profile')
_last_call_time = 0
LOCAL_PORT = 9303  # 拼多多专属端口（tb9300/jd9301/vip9302/pdd9303）


def _find_browser():
    for p in EDGE_PATHS:
        if os.path.exists(p):
            return p
    return None


def search_pdd(keyword: str, max_items: int = 20, login_wait: int = 150, page: int = 1) -> list:
    """拼多多关键词搜索（浏览器 H5）。
    返回: [{platform, title, price, original_price, sales, shop, url, item_id, goodsId}]
    未登录返回 []；遇验证码抛 CaptchaError（采集层会暂停该词）。"""
    global _last_call_time
    # 低频约束：12-20s 随机抖动
    wait = random.uniform(12, 20) - (time.time() - _last_call_time)
    if wait > 0:
        print(f'⏳ 拼多多频率控制，等待 {int(wait)} 秒...')
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
    co.headless()
    browser = Chromium(co)
    tab = browser.latest_tab

    try:
        # 搜索入口（H5 搜索页）
        url = f'https://mobile.yangkeduo.com/search_result.html?search_key={keyword}'
        tab.get(url)
        tab.wait.doc_loaded()
        time.sleep(10)  # 关键：等 SPA 数据注入页面（实测 6s 不够，10s 出数据）

        # 登录检测（未登录会跳登录页）
        if 'login' in tab.url.lower() or tab.title.strip() == '登录':
            print('⚠️ 拼多多未登录，请先运行 login_pdd.py 扫码')
            return []

        # 验证码检测（按约束不绕，抛异常让采集层暂停该词）
        html_head = tab.html[:5000]
        if '验证' in html_head and ('安全' in html_head or '滑动' in html_head):
            from errors import CaptchaError
            raise CaptchaError('拼多多验证码拦截')

        html = tab.html
        items = _parse_search_html(html)
        if not items:
            # 再等 5 秒重试一次（慢网络）
            time.sleep(5)
            html = tab.html
            items = _parse_search_html(html)
        return items[:max_items]
    finally:
        browser.quit()


def _parse_search_html(html: str) -> list:
    """从搜索页 HTML 提取商品（数据注入在页面 JSON：goodsName/price(分)/goods_id）"""
    items = []
    # 商品 ID：goods.html?goods_id=xxx 形式（40 个 = 一页商品数）
    ids = re.findall(r'goods\.html\?goods_id=(\d+)', html)
    if not ids:
        return []
    # 用 goods_id 位置切分商品块，每块提取字段
    for gid in ids:
        idx = html.find(f'goods_id={gid}')
        if idx < 0:
            continue
        block = html[max(0, idx - 3000):idx + 200]  # 商品对象在链接前
        # 商品名（JSON 里是直接 UTF-8 中文，部分含 \uXXXX 转义如 \u002F）
        m = re.search(r'"goodsName":"((?:[^"\\]|\\.)*)"', block)
        title = m.group(1) if m else ''
        title = re.sub(r'\\u([0-9a-fA-F]{4})', lambda x: chr(int(x.group(1), 16)), title)
        # 价格（分 → 元）
        m2 = re.search(r'"price":(\d+)', block)
        price = int(m2.group(1)) / 100 if m2 else 0
        # 销量文案
        m3 = re.search(r'"salesTip":"((?:[^"\\]|\\.)*)"', block)
        sales = m3.group(1) if m3 else ''
        if title and price:
            items.append({
                'platform': 'pdd',
                'title': title[:100],
                'price': price,
                'original_price': None,
                'sales': sales,
                'shop': '',
                'is_ad': False,
                'item_id': gid,
                'goodsId': gid,
                'url': f'https://mobile.yangkeduo.com/goods.html?goods_id={gid}',
            })
    # 去重（同一商品可能出现多次）
    seen, uniq = set(), []
    for it in items:
        if it['goodsId'] not in seen:
            seen.add(it['goodsId'])
            uniq.append(it)
    return uniq


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '球鞋'
    items = search_pdd(kw)
    print(f'\n拼多多「{kw}」: {len(items)} 条')
    for it in items[:8]:
        print(f"  ¥{it['price']} | {it['title'][:32]} | {it['sales']} | {it['url'][:50]}")
