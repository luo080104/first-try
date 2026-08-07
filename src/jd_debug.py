# jd_debug.py - 京东搜索页结构探测（一次性调试）
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

EDGE_PATHS = [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'jd_profile')

def main():
    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(EDGE_PATHS[0])
    co.set_user_data_path(PROFILE_DIR)
    browser = Chromium(co)
    tab = browser.latest_tab

    tab.get('https://search.jd.com/Search?keyword=石头岛&enc=utf-8')
    tab.wait.doc_loaded()
    time.sleep(4)

    # 1. 找所有含 ¥ 的元素
    print('=== 含 ¥ 的元素（前10个）===')
    try:
        price_eles = tab.eles('xpath://*[contains(text(),"¥")]', timeout=5)
        print(f'找到 {len(price_eles)} 个')
        for e in price_eles[:10]:
            print(f'  tag={e.tag} class={e.attr("class")} text={e.text[:50]}')
    except Exception as ex:
        print('xpath 失败:', str(ex)[:100])

    # 2. 常见容器类名探测
    print('\n=== 容器类探测 ===')
    for sel in ['.gl-i-wrap', '.goods-list-li', '#J_goodsList li', '.J_goodsList',
                '[class*="goods"]', '[class*="item"]', 'li[data-sku]']:
        try:
            n = len(tab.eles(sel, timeout=2))
            print(f'  {sel}: {n} 个')
        except Exception:
            print(f'  {sel}: 错误')

    # 3. 页面文本采样
    print('\n=== 页面文本采样 ===')
    t = tab.html
    print(t[:300].replace('\n', ' '))
    browser.quit()

if __name__ == '__main__':
    main()
