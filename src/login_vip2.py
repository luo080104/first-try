# login_vip2.py - 唯品会登录（纯静默：只弹登录页，不检测不跳转，等用户说好后退出）
import os
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
    co.set_argument('--window-position=200,150')
    co.set_argument('--window-size=900,700')
    browser = Chromium(co)
    tab = browser.latest_tab
    tab.get('https://passport.vip.com/login')
    tab.wait.doc_loaded()
    time.sleep(3)
    print('[READY] 登录页已就绪——请扫码，完成后由用户通知退出')
    # 完全静默等待：最多 10 分钟，期间不操作页面
    time.sleep(600)
    browser.quit()
    print('[DONE] 已退出（cookie 已保存）')
    return True
if __name__ == '__main__':
    main()
