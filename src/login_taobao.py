# login_taobao.py - 淘宝登录引导（DrissionPage tb_profile）
# 用法: python src/login_taobao.py
# 流程: 弹出浏览器 → 请扫码/账号登录淘宝 → 检测登录成功后自动退出
import os
import sys
import time


def main():
    from DrissionPage import Chromium, ChromiumOptions

    profile = os.path.join(os.path.dirname(__file__), '..', 'data', 'tb_profile')
    co = ChromiumOptions()
    import os as _os
    edge = next((p for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
                 if _os.path.exists(p)), None)
    if not edge:
        print('[错误] 未找到 Edge 浏览器')
        return
    co.set_browser_path(edge)
    co.set_user_data_path(profile)
    browser = Chromium(co)
    tab = browser.latest_tab

    tab.get('https://www.taobao.com')
    tab.wait.doc_loaded()
    print('[提示] 浏览器已打开淘宝首页，请登录（扫码最快）。')
    print('[提示] 登录成功后脚本自动检测并退出，无需按键。')

    # 登录检测：cookie 出现有效登录标志
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            cookies = browser.cookies()
            names = [c['name'] for c in cookies]
            # 淘宝登录标志：cookie2 / sg / unb / _nk_ 等
            if any(k in names for k in ['cookie2', 'sg', 'unb', '_nk_', 'uc1']):
                print('[OK] 检测到登录态，登录成功！')
                time.sleep(2)
                browser.quit()
                return True
        except Exception:
            pass
        time.sleep(3)

    print('[TIME OUT] 5 分钟未检测到登录，退出')
    browser.quit()
    return False

if __name__ == '__main__':
    sys.exit(0 if main() else 1)
