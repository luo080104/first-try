# login_vip_m.py - 唯品会移动站登录引导（m.vip.com，搜索页需要 m 站登录态）
# 用法: python src/login_vip_m.py
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
    if not edge:
        print('[错误] 未找到 Edge 浏览器')
        return False
    co.set_browser_path(edge)
    co.set_local_port(9302)
    co.set_user_data_path(profile)
    browser = Chromium(co)
    tab = browser.latest_tab

    # 打开 m 站首页，点击登录或直接开登录页
    tab.get('https://m.vip.com/index.html')
    tab.wait.doc_loaded()
    time.sleep(4)
    print('[提示] 正在打开移动站登录...')
    # 尝试点击"请登录"按钮
    try:
        login_btns = tab.eles('xpath://*[contains(text(),"登录")]', timeout=3)
        for b in login_btns[:3]:
            try:
                b.click()
                print('[提示] 已点击登录按钮')
                break
            except Exception:
                continue
    except Exception:
        pass
    if 'login' not in tab.url.lower():
        try:
            tab.get('https://m.vip.com/login.html')
            time.sleep(3)
        except Exception:
            pass
    print('[提示] 请用手机唯品会 APP 扫二维码（或手机号登录）')
    print('[提示] 登录成功后脚本自动检测并退出。')

    # m 站登录标志（mars_cid 游客也有，不算）
    LOGIN_KEYS = ['sn', 'vip_account', 'skey', 'VIP_TOKEN', 'uid', 'wc']
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            cookies = browser.cookies()
            names = [str(c.get('name', '')) for c in cookies]
            if any(k in names for k in LOGIN_KEYS):
                print(f'[OK] 检测到 m 站登录态（{next(k for k in LOGIN_KEYS if k in names)}），登录成功！')
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
