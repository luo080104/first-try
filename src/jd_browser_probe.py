# jd_browser_probe.py - 京东浏览器搜索 v2（登录态持久化）
# 约束：真浏览器+真账号 / 低频 / 遇验证码即停 / 只读提取
# 第一次运行：会自动打开浏览器 → 请手动登录京东（60-120秒内）→ 登录后自动继续
# 之后运行：登录态保持，直接搜索
# 用法: python src/jd_browser_probe.py "石头岛"
import os
import sys
import time

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_PATHS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'jd_profile')

def find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def is_login_page(tab) -> bool:
    try:
        return '欢迎登录' in tab.title or '欢迎登录' in tab.html[:3000]
    except Exception:
        return True

def wait_for_login(tab, timeout=150):
    """等待用户手动登录，返回是否成功"""
    print('🔐 请在浏览器窗口手动登录京东（扫码或账号密码）...')
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not is_login_page(tab):
            print('✅ 登录成功！')
            return True
        time.sleep(3)
    print('⏰ 登录超时，请重试')
    return False

def main():
    keyword = sys.argv[1] if len(sys.argv) > 1 else '石头岛'
    browser_path = find_browser()
    if not browser_path:
        print('❌ 未找到 Chrome/Edge')
        return

    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(browser_path)
    co.set_user_data_path(PROFILE_DIR)   # 持久化登录态
    co.set_argument('--start-maximized')

    browser = Chromium(co)
    tab = browser.latest_tab

    url = f'https://search.jd.com/Search?keyword={keyword}&enc=utf-8'
    print(f'🔍 打开京东搜索: {keyword}')
    tab.get(url)
    tab.wait.doc_loaded()

    # 需要登录则等待
    if is_login_page(tab):
        if not wait_for_login(tab):
            browser.quit()
            return
        tab.get(url)
        tab.wait.doc_loaded()
        time.sleep(2)

    # 验证码检测
    page_text = tab.html
    if '验证' in page_text and ('拖动' in page_text or '安全验证' in page_text):
        print('⚠️ 遇到验证码，按约束停止（不尝试绕过）')
        browser.quit()
        return

    # 提取商品
    items = []
    for sel in ['.gl-item', '.J_goodsList li', '[class*="gl-item"]']:
        eles = tab.eles(sel)
        if eles:
            items = eles
            print(f'  选择器 {sel}: {len(eles)} 个商品')
            break

    if not items:
        print('⚠️ 未找到商品元素（可能页面改版）。页面标题:', tab.title)
        browser.quit()
        return

    print(f'\n📦 京东「{keyword}」结果：')
    for item in items[:8]:
        try:
            title = item.ele('.p-name a', timeout=2).text.strip()[:40]
        except Exception:
            title = '?'
        try:
            price = item.ele('.p-price i', timeout=2).text.strip()
        except Exception:
            price = '?'
        try:
            shop = item.ele('.p-shop a', timeout=2).text.strip()[:15]
        except Exception:
            shop = '?'
        print(f'  ¥{price:>10} | {title} | {shop}')

    browser.quit()
    print('\n✅ 完成（登录态已保存，下次不用再登录）')

if __name__ == '__main__':
    main()
