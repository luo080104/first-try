# login_tb.py - 淘宝登录引导（详情页需要）
import sys, os, time
def main():
    from DrissionPage import Chromium, ChromiumOptions
    profile = os.path.join(os.path.dirname(__file__), '..', 'data', 'tb_profile')
    co = ChromiumOptions()
    edge = next((p for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
                 if os.path.exists(p)), None)
    co.set_browser_path(edge)
    co.set_local_port(9300)
    co.set_user_data_path(profile)
    browser = Chromium(co)
    tab = browser.latest_tab
    tab.get('https://login.taobao.com/member/login.jhtml')
    tab.wait.doc_loaded()
    time.sleep(3)
    print('[提示] 请扫码登录淘宝（APP扫码），登录后自动检测退出')
    LOGIN_KEYS = ['unb', '_nk_']  # 仅真正登录态（cookie2 游客也有，已排除）
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            names = [str(c.get('name', '')) for c in browser.cookies()]
            if any(k in names for k in LOGIN_KEYS):
                print(f'[OK] 淘宝登录成功（{next(k for k in LOGIN_KEYS if k in names)}）')
                time.sleep(2)
                browser.quit()
                return True
        except Exception:
            pass
        time.sleep(3)
    print('[TIME OUT] 超时')
    browser.quit()
    return False
if __name__ == '__main__':
    sys.exit(0 if main() else 1)
