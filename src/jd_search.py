# jd_search.py - 京东浏览器搜索（DrissionPage，登录态持久化）
# 约束：真浏览器+真账号 / 低频（调用间隔>=30s）/ 遇验证码即停 / 只读提取
# 第一次使用：运行后浏览器弹出，手动登录京东一次，之后免登录
# 用法: from jd_search import search_jd; items = search_jd('石头岛')
import sys
import os
import time
import re

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

# 端口 9301：与淘宝（9300）分开，避免 SSE 并行补搜时抢同一个调试端口
LOCAL_PORT = 9301

def _find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def search_jd(keyword: str, max_items: int = 8, login_wait: int = 150, page: int = 1) -> list:
    """京东关键词搜索（浏览器自动化）。
    返回: [{platform, title, price, original_price, sales, shop, is_ad, url}]
    遇验证码返回 [] 并打印提示。page=1 首页，2/3 翻页。"""
    global _last_call_time
    # 低频约束：随机抖动 12-20s（WorkBuddy 建议：避免固定间隔被识别）
    import random as _random
    wait = _random.uniform(12, 20) - (time.time() - _last_call_time)
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
    co.set_local_port(LOCAL_PORT)  # 9301：避免与 CDP 9222 / 淘宝 9300 冲突
    co.set_user_data_path(PROFILE_DIR)
    co.set_argument('--window-position=-32000,-32000')  # 窗口移出屏幕：不打扰用户且保持真实渲染
    co.set_argument('--start-maximized')
    browser = Chromium(co)
    tab = browser.latest_tab

    try:
        url = f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8'
        if page > 1:
            url += f'&page={page}'
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

        # 触发懒加载
        tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
        time.sleep(2)
        tab.run_js('window.scrollTo(0, document.body.scrollHeight / 2)')
        time.sleep(1)

        # 验证码检测（按约束不绕过；抛异常让采集层识别并暂停该词）
        if '安全验证' in tab.html or '拖动' in tab.html[:5000]:
            from errors import CaptchaError
            raise CaptchaError('京东验证码拦截')

        cards = tab.eles('xpath://*[contains(@class,"goodsCardWrapper")]', timeout=5)
        items = []
        # WorkBuddy debug：cards=0 → 登录态假死/页面失败；cards>0 → 解析问题
        print(f"[JD debug] '{keyword}' page={page}: cards={len(cards)}")
        for c in cards[:max_items + 4]:
            try:
                txt = c.text.replace('\n', '|').strip()
            except Exception:
                continue
            # 提取 skuId：优先 li 的 data-sku 属性，兜底从卡片内链接 item.jd.com/XXX.html 提取
            sku_id = ''
            try:
                sku_id = str(c.attr('data-sku') or '').strip()
            except Exception:
                pass
            if not sku_id:
                try:
                    href = c.link or ''
                    m = re.search(r'item\.jd\.com/(\d{6,15})', href)
                    if m:
                        sku_id = m.group(1)
                except Exception:
                    pass
            is_ad = '广告' in txt
            # 价格：取 ¥ 后面的数字（第二个通常是原价）
            prices = re.findall(r'¥(\d+(?:\.\d+)?)', txt)
            price = float(prices[0]) if prices else None
            original = float(prices[1]) if len(prices) > 1 else None
            # 标题：第一个 | 前的文本
            parts = txt.split('|')
            title = parts[0].strip()[:60] if parts else ''
            # 销量：已售/人看过
            sales = ''
            m = re.search(r'(已售[\d万.]+|[\d.]+人(?:看过|浏览|种草))', txt)
            if m:
                sales = m.group(1)
            # 店铺：含"旗舰店/专营店/自营"的段
            shop = ''
            for p in parts:
                if '旗舰店' in p or '专营店' in p or '自营' in p or '海外' in p:
                    shop = p.strip()[:20]
                    break
            items.append({
                'platform': 'jd',
                'title': title,
                'price': price,
                'original_price': original,
                'sales': sales,
                'shop': shop,
                'is_ad': is_ad,
                'item_id': sku_id,  # 京东 skuId（入库/盯价/历史价的关键）
                'goodsId': sku_id,
                'url': f'https://item.jd.com/{sku_id}.html' if sku_id else '',
            })
        print(f"[JD debug] '{keyword}' page={page}: cards={len(cards)}, items={len(items)}")
        return items[:max_items]
    finally:
        browser.quit()

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '石头岛'
    items = search_jd(kw)
    print(f'\n京东「{kw}」: {len(items)} 条')
    for it in items:
        ad = ' [广告]' if it['is_ad'] else ''
        print(f"  ¥{it['price']} | {it['title'][:35]} | {it['shop']} | {it['sales']}{ad}")
