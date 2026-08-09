# probe_pdd.py - 探测拼多多 H5 搜索页可行性（一次性开发脚本）
import sys, os, time, re
sys.path.insert(0, os.path.dirname(__file__))

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'
PROFILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'pdd_profile')

from DrissionPage import Chromium, ChromiumOptions

co = ChromiumOptions()
co.set_browser_path(EDGE)
co.set_local_port(9303)  # 拼多多专属端口
co.set_user_data_path(PROFILE)
browser = Chromium(co)
tab = browser.latest_tab

try:
    # 拼多多 H5 搜索页
    url = 'https://mobile.yangkeduo.com/search_result.html?search_key=' + '球鞋'
    print('访问:', url)
    tab.listen.start()
    tab.get(url)
    n = 0
    hits = []
    for i in range(20):
        try:
            p = tab.listen.wait(timeout=6)
        except Exception:
            break
        if p is None or isinstance(p, bool):
            continue
        n += 1
        u = str(getattr(p, 'url', ''))
        if any(k in u.lower() for k in ['search', 'goods', 'list', 'query', 'api', 'mall']):
            body = str(p.response.body)
            hits.append((u[:110], len(body)))
    print(f'共 {n} 个请求, 数据请求 {len(hits)} 个:')
    for u, blen in hits[:8]:
        print(f'  {u}  body={blen}字')
    html = tab.html
    print(f'HTML: {len(html)}字, 标题: {tab.title[:40]}')
    text = re.sub(r'<[^>]+>', ' ', html)
    prices = re.findall(r'[¥￥]\s*(\d+\.?\d*)', html)
    print(f'页面价格数: {len(prices)}, 样例: {prices[:8]}')
    for kw in ['登录', '验证', '滑块']:
        if kw in html:
            print(f'⚠️ 页面包含: {kw}')
finally:
    try: tab.listen.stop()
    except Exception: pass
    browser.quit()
