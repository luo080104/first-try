# login_pdd.py - 拼多多 H5 登录引导（DrissionPage pdd_profile）
# 用法: python src/login_pdd.py
# 流程: 弹出浏览器 → 请扫码/手机号登录拼多多 → 检测登录成功后自动退出
import os
import sys
import time


def main():
    from DrissionPage import Chromium, ChromiumOptions

    profile = os.path.join(os.path.dirname(__file__), '..', 'data', 'pdd_profile')
    co = ChromiumOptions()
    edge = next((p for p in [r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
                              r'C:\Program Files\Microsoft\Edge\Application\msedge.exe']
                 if os.path.exists(p)), None)
    if not edge:
        print('[错误] 未找到 Edge 浏览器')
        return False
    co.set_browser_path(edge)
    co.set_local_port(9303)  # 拼多多专属端口（tb9300/jd9301/vip9302/pdd9303）
    co.set_user_data_path(profile)
    browser = Chromium(co)
    tab = browser.latest_tab

    tab.get('https://mobile.yangkeduo.com/login.html')
    tab.wait.doc_loaded()
    time.sleep(4)
    print('[提示] 浏览器已打开拼多多登录页，请扫码登录（拼多多APP扫码 或 微信扫码）。')
    print('[提示] 登录成功后脚本自动检测并退出，无需按键。')

    # 拼多多 H5 登录标志 cookie（游客只有 api_uid，登录后有 pdd_user_id / PDDAccessToken）
    LOGIN_KEYS = ['pdd_user_id', 'PDDAccessToken', 'pdd_user_uin']
    deadline = time.time() + 300
    while time.time() < deadline:
        try:
            cookies = browser.cookies()
            names = [str(c.get('name', '')) for c in cookies]
            if any(k in names for k in LOGIN_KEYS):
                print(f'[OK] 检测到拼多多登录态（{next(k for k in LOGIN_KEYS if k in names)}），登录成功！')
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
