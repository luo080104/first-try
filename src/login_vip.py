# login_vip.py - 唯品会登录引导（9302 独立实例，扫码用）
import os
import sys
import time


def main():
    from DrissionPage import Chromium, ChromiumOptions
    profile = os.path.join(os.path.dirname(__file__), '..', 'data', 'vip_profile')
    co = ChromiumOptions()
    edge = next((p for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
                 if os.path.exists(p)), None)
    co.set_browser_path(edge)
    co.set_local_port(9302)
    co.set_user_data_path(profile)
    co.set_argument('--window-position=100,100')  # 覆盖 profile 记住的屏幕外位置
    browser = Chromium(co)
    tab = browser.latest_tab
    try:
        tab.set.window.location(100, 100)  # 双保险：CDP 再设一次
    except Exception:
        pass
    tab.get('https://passport.vip.com/login')
    tab.wait.doc_loaded()
    time.sleep(3)
    print('[提示] 请扫码登录唯品会，登录成功后本窗口自动关闭')
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            tab.get('https://category.vip.com/suggest.php?keyword=测试&ff=235%7C12%7C1%7C1', timeout=10)
            time.sleep(2)
            if 'login' not in tab.url.lower():
                print('[OK] 唯品会登录成功（搜索页不再跳登录）')
                time.sleep(2)
                browser.quit()
                return True
        except Exception:
            pass
        time.sleep(5)
    print('[TIME OUT] 超时')
    browser.quit()
    return False
if __name__ == '__main__':
    sys.exit(0 if main() else 1)
