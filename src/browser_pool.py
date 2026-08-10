# browser_pool.py - 浏览器常驻池（WorkBuddy 方案：服务启动时开好藏好，搜索复用，不新建不销毁）
# 解决：每次搜索新建+销毁浏览器 → 窗口闪现弹窗
# v2: 双重隐藏（DrissionPage hide 重试 + ctypes ShowWindow 按 PID 强制隐藏 + 验证）
import os
import sys
import time
import threading

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
_lock = threading.Lock()
_serial_locks = {p: threading.Lock() for p in PROFILES}  # 同平台搜索串行锁


def serialize(platform: str):
    """装饰器：同平台搜索串行（避免并发抢同一 tab → 探活误判重建）"""
    def deco(fn):
        def wrapper(*a, **kw):
            with _serial_locks[platform]:
                return fn(*a, **kw)
        return wrapper
    return deco


def _force_hide_windows(pid: int):
    """ctypes 强制隐藏指定 PID 的所有可见窗口（终极手段，等窗口出现）"""
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            wpid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                user32.ShowWindow(hwnd, 0)  # SW_HIDE
        return True

    for _ in range(10):
        user32.EnumWindows(cb, 0)
        time.sleep(0.3)


def _hide_browser(b):
    """三重隐藏：dp hide 重试 → ctypes 按 PID 强制 → 返回是否已隐藏"""
    # 1) DrissionPage 原生 hide（等窗口就绪重试）
    for _ in range(5):
        try:
            b.latest_tab.set.window.hide()
        except Exception:
            pass
        time.sleep(0.5)
    # 2) ctypes 按 PID 强制隐藏（终极手段）
    try:
        pid = b.process_id
        _force_hide_windows(pid)
    except Exception:
        pass


def _new_browser(platform: str):
    """新建浏览器并立即隐藏"""
    from DrissionPage import Chromium, ChromiumOptions
    prof, port = PROFILES[platform]
    co = ChromiumOptions()
    co.set_browser_path(EDGE)
    co.set_local_port(port)
    co.set_user_data_path(os.path.join(os.path.dirname(__file__), '..', prof))
    # 终极组合：启动参数层面窗口就不可见（即使 ShowWindow 失效也不打扰）
    co.set_argument('--window-position=-32000,-32000')
    co.set_argument('--window-size=1,1')
    co.set_argument('--disable-session-crashed-bubble')  # 禁恢复会话弹窗
    co.set_argument('--no-first-run')
    b = Chromium(co)
    _hide_browser(b)
    return b


def get_browser(platform: str):
    """从池取常驻浏览器；不存在/已死则新建（线程安全）"""
    with _lock:
        b = _pool.get(platform)
        if b is not None:
            try:
                b.run_cdp('Browser.getVersion')  # 小布方案：只测CDP不碰tab（导航期不误判）
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


def _sweep_hide():
    """预热后补一轮强制隐藏（等窗口全部创建后）"""
    for plat, b in list(_pool.items()):
        try:
            _force_hide_windows(b.process_id)
        except Exception:
            pass


def rehide(platform: str):
    """搜索完成后强制隐藏兜底（小布方案）"""
    b = _pool.get(platform)
    if b is not None:
        try:
            _force_hide_windows(b.process_id)
        except Exception:
            pass


def rehide_later(platform: str, delay: float = 2.0):
    """延迟隐藏：导航异步加载完成后窗口可能复现，延迟再补一刀"""
    threading.Timer(delay, rehide, args=[platform]).start()


def warmup():
    """服务启动时预热 4 个浏览器（后台线程调用，不阻塞启动）"""
    def _w():
        for plat in PROFILES:
            try:
                get_browser(plat)
                print(f'[pool] 预热 {plat} OK')
            except Exception as e:
                print(f'[pool] 预热 {plat} 失败: {str(e)[:50]}')
            time.sleep(1)
        time.sleep(3)  # 等窗口全部创建
        _sweep_hide()  # 补一轮隐藏（首次隐藏可能漏掉启动慢的窗口）
    threading.Thread(target=_w, daemon=True).start()


if __name__ == '__main__':
    p = sys.argv[1] if len(sys.argv) > 1 else 'tb'
    b = get_browser(p)
    print(f'{p} 浏览器就绪:', b.latest_tab.url[:50])
