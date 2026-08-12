# jd_debug2.py - 京东搜索页数据源探测
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'jd_profile')

def main():
    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe')
    co.set_user_data_path(PROFILE_DIR)
    browser = Chromium(co)
    tab = browser.latest_tab
    tab.get('https://search.jd.com/Search?keyword=石头岛&enc=utf-8')
    tab.wait.doc_loaded()
    time.sleep(4)

    html = tab.html

    # 1. 找商品 JSON 数据源
    print('=== 数据源探测 ===')
    for key in ['pageConfig', 'wareId', 'skuid', 'searchData', 'result', 'product']:
        idxs = [m.start() for m in re.finditer(key, html)][:3]
        print(f'  {key}: {len(idxs)} 处')

    # 2. 提取 a[title]（商品标题通常在这里）
    print('\n=== a 标签 title 属性 ===')
    try:
        links = tab.eles('tag:a@title', timeout=5)
        print(f'  找到 {len(links)} 个带 title 的链接')
        for l in links[:10]:
            print(f'  - {l.attr("title")[:45]}')
    except Exception as e:
        print('  失败:', str(e)[:80])

    # 3. 打印含"石头岛"文本的 span/div 数量
    print('\n=== 含关键词文本元素 ===')
    try:
        kws = tab.eles('xpath://*[contains(text(),"石头岛")]', timeout=5)
        print(f'  找到 {len(kws)} 个，前5个:')
        for k in kws[:5]:
            print(f'  - tag={k.tag} text={k.text[:40]}')
    except Exception as e:
        print('  失败:', str(e)[:80])

    browser.quit()

if __name__ == '__main__':
    main()
