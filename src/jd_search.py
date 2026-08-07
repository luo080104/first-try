# jd_search.py - 京东浏览器搜索（DrissionPage，登录态持久化）
# 约束：真浏览器+真账号 / 低频（调用间隔>=30s）/ 遇验证码即停 / 只读提取
# 第一次使用：运行后浏览器弹出，手动登录京东一次，之后免登录
# 用法: from jd_search import search_jd; items = search_jd('石头岛')
import sys
import os
import time
import re
import random

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_PATHS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'jd_profile')
_last_call_time = 0  # 低频约束

def _find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def _parse_jd_card(txt: str) -> dict | None:
    """解析京东新版搜索卡片（React 版）。
    新版结构：广告|标题|2千+人已买|3万+人加购|6万+店铺老客浏览|¥10969学生到手价|¥10999|正品行货带票|10万+人看过|店铺名|搜同款|对比"""
    parts = [p.strip() for p in txt.replace('\n', '|').split('|') if p.strip()]
    if not parts:
        return None
    is_ad = '广告' in txt
    # 标题：跳过广告段和销量/价格/标签段，取第一个较长段
    title = ''
    skip_kw = ('人已买', '人加购', '人看过', '人种草', '人浏览', '到手价',
               '正品行货', '搜同款', '对比', '学生', '店铺老客')
    for p in parts:
        if p == '广告' or any(k in p for k in skip_kw) or '¥' in p:
            continue
        if len(p) >= 6:
            title = p[:60]
            break
    if not title:
        # 兜底：取第一个不含价格符号的段
        for p in parts:
            if '¥' not in p and len(p) >= 6:
                title = p[:60]
                break
    # 价格：优先「到手价」，其次取第一个 ¥
    price = None
    original = None
    prices = re.findall(r'¥(\d+(?:\.\d+)?)', txt)
    m = re.search(r'¥(\d+(?:\.\d+)?)\s*学生到手价', txt) or re.search(r'到手价\s*¥(\d+(?:\.\d+)?)', txt)
    if m:
        price = float(m.group(1))
    elif prices:
        price = float(prices[0])
    if len(prices) > 1:
        original = float(prices[1])
    # 销量：人已买/人加购/人看过
    sales = ''
    m2 = re.search(r'([\d.]+[万千]?\+?\s*人(?:已买|加购|看过|种草|浏览))', txt)
    if m2:
        sales = m2.group(1)
    # 店铺：含自营/旗舰店/专营店/官方的段
    shop = ''
    for p in parts:
        if any(k in p for k in ('自营', '旗舰店', '专营店', '官方', '京东国际')):
            shop = p[:20]
            break
    return {
        'platform': 'jd',
        'title': title,
        'price': price,
        'original_price': original,
        'sales': sales,
        'shop': shop,
        'is_ad': is_ad,
    }


def search_jd(keyword: str, max_items: int = 30, login_wait: int = 150) -> list:
    """京东关键词搜索（浏览器自动化）。
    力度（借鉴 xiuyegege 滚动加载模式）：首屏 + 滚动 2 次 + 翻页第 2 页，目标 30 条。
    适配 2026 新版 React 搜索页（等待渲染 + 新版卡片解析）。
    返回: [{title, price, original_price, sales, shop, is_ad, url}]
    遇验证码返回 [] 并打印提示。"""
    global _last_call_time
    # 低频约束：两次调用间隔至少 30 秒
    wait = 30 - (time.time() - _last_call_time)
    if wait > 0:
        print(f'⏳ 京东搜索频率控制，等待 {int(wait)} 秒...')
        time.sleep(wait)
    _last_call_time = time.time()

    browser_path = _find_browser()
    if not browser_path:
        print('❌ 未找到 Chrome/Edge')
        return []

    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(browser_path)
    co.set_local_port(9300)  # 独立端口，避免与 CDP 9222 冲突
    co.set_user_data_path(PROFILE_DIR)
    co.set_argument('--start-maximized')
    browser = Chromium(co)
    tab = browser.latest_tab

    try:
        url = f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8'
        tab.get(url)
        tab.wait.doc_loaded()

        # 登录检测
        if '欢迎登录' in tab.title or '欢迎登录' in tab.html[:2000]:
            print('🔐 请在浏览器窗口手动登录京东（仅首次需要）...')
            deadline = time.time() + login_wait
            logged = False
            while time.time() < deadline:
                if '欢迎登录' not in tab.title and '欢迎登录' not in tab.html[:2000]:
                    logged = True
                    break
                time.sleep(3)
            if not logged:
                print('⏰ 登录超时')
                return []
            tab.get(url)
            tab.wait.doc_loaded()
            time.sleep(2)

        # 等待 React 渲染出商品卡片（新版搜索页是 React 应用，最多等 20 秒，0.5s 轮询）
        cards = []
        deadline = time.time() + 20
        while time.time() < deadline:
            if '安全验证' in tab.html or '拖动' in tab.html[:5000]:
                print('⚠️ 遇到京东验证码，本次跳过（按约束不尝试绕过）')
                return []
            cards = tab.eles('xpath://*[contains(@class,"goodsCardWrapper")]', timeout=3)
            if len(cards) > 0:
                break
            time.sleep(0.5)
        if not cards:
            print('⚠️ 京东商品卡片未渲染出来（可能页面改版或风控），本次返回空')
            return []

        # 触发懒加载（滚动 2 次，随机间隔，xiuyegege 模式）
        tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(random.uniform(1.5, 2.5))
        tab.run_js('window.scrollTo(0, document.body.scrollHeight / 2)')
        time.sleep(random.uniform(1, 1.5))

        items = []
        seen = set()

        def _collect_cards():
            """从当前页面收集商品卡片（去重）"""
            nonlocal items, seen
            cards = tab.eles('xpath://*[contains(@class,"goodsCardWrapper")]', timeout=5)
            for c in cards[:max_items + 8]:
                try:
                    txt = c.text.replace('\n', '|').strip()
                except Exception:
                    continue
                if not txt:
                    continue
                item = _parse_jd_card(txt)
                if item and item['title'] and item['title'] not in seen:
                    seen.add(item['title'])
                    items.append(item)
                    if len(items) >= max_items:
                        break

        _collect_cards()

        # 加速：首屏已够（>=20 条）直接返回，不再滚动/翻页（多数场景 10s 内完成）
        if len(items) >= 20:
            print(f'[jd] 首屏 {len(items)} 条已够，跳过滚动+翻页（加速）')
            return items[:max_items]

        # 首屏不足才滚动 2 次加载更多（懒加载）
        for _ in range(2):
            if len(items) >= max_items:
                break
            before = len(items)
            tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(random.uniform(2, 3))
            _collect_cards()
            if len(items) > before:
                print(f'[jd] 滚动加载后 {len(items)} 条')
            else:
                break

        # 第 2 页（翻页 URL），首屏+滚动仍不够才翻页（兜底）
        if len(items) < max_items:
            try:
                tab.get(f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8&page=2')
                tab.wait.doc_loaded()
                time.sleep(random.uniform(3, 4))  # React 渲染等待
                if '安全验证' not in tab.html:
                    before = len(items)
                    _collect_cards()
                    if len(items) > before:
                        print(f'[jd] 第2页后 {len(items)} 条')
            except Exception as e:
                print(f'[jd] 翻页失败（不影响已收集数据）: {str(e)[:60]}')

        return items[:max_items]
    finally:
        browser.quit()

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '石头岛'
    items = search_jd(kw)
    print(f'\n京东「{kw}」: {len(items)} 条')
    for it in items:
        ad = ' [广告]' if it['is_ad'] else ''
        print(f"  ¥{it['price']} | {it['title'][:40]} | {it['shop']} | {it['sales']}{ad}")
