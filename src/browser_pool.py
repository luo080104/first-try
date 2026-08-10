# browser_pool.py - 浏览器常驻池（WorkBuddy 方案：服务启动时开好藏好，搜索复用，不新建不销毁）
# 解决：每次搜索新建+销毁浏览器 → 窗口闪现弹窗
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

PROFILES = {
    'tb': ('data/tb_profile', 9300),
    'jd': ('data/jd_profile', 9301),
    'vip': ('data/vip_profile', 9302),
    'pdd': ('data/pdd_profile', 9303),
}
_pool = {}


def _new_browser(platform: str):
    """新建浏览器并立即隐藏（启动间隙尽量短）"""
    from DrissionPage import Chromium, ChromiumOptions
    prof, port = PROFILES[platform]
    co = ChromiumOptions()
    co.set_browser_path(EDGE)
    co.set_local_port(port)
    co.set_user_data_path(os.path.join(os.path.dirname(__file__), '..', prof))
    b = Chromium(co)
    try:
        b.latest_tab.set.window.hide()
    except Exception:
        pass
    return b


def get_browser(platform: str):
    """从池取常驻浏览器；不存在/已死则新建"""
    b = _pool.get(platform)
    if b is not None:
        try:
            b.latest_tab.url  # 探活
            return b
        except Exception:
            try:
                b.quit()
            except Exception:
                pass
            _pool.pop(platform, None)
    b = _new_browser(platform)
    _pool[platform] = b
    return b


def warmup():
    """服务启动时预热 4 个浏览器（后台线程调用，不阻塞启动）"""
    import threading
    def _w():
        for plat in PROFILES:
            try:
                get_browser(plat)
                print(f'[pool] 预热 {plat} OK')
            except Exception as e:
                print(f'[pool] 预热 {plat} 失败: {str(e)[:50]}')
            time.sleep(1)
    threading.Thread(target=_w, daemon=True).start()


if __name__ == '__main__':
    p = sys.argv[1] if len(sys.argv) > 1 else 'tb'
    b = get_browser(p)
    print(f'{p} 浏览器就绪（隐藏）:', b.latest_tab.url[:50])
