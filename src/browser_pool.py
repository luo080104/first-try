# browser_pool.py - 浏览器常驻池（WorkBuddy 方案：服务启动时开好藏好，搜索复用，不新建不销毁）
# 解决：每次搜索新建+销毁浏览器 → 窗口闪现弹窗
# v2: 双重隐藏（DrissionPage hide 重试 + ctypes ShowWindow 按 PID 强制隐藏 + 验证）
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(__file__))

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

PROFILES = {
    # 2026-08-11 小布方案：淘宝切 headless。
    # tb_profile_h = headless 专用副本（原 tb_profile 与 headless 不兼容——保留原目录做备份，回退有头时改回 data/tb_profile 即可）
    'tb': ('data/tb_profile_h', 9300),
    'jd': ('data/jd_profile', 9301),
    'vip': ('data/vip_profile', 9302),
    'pdd': ('data/pdd_profile', 9303),
}
HEADLESS = {'tb'}  # 已验证 headless 通的平台；其余保留有头隐藏（逐个验证逐个切）
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
    """新建浏览器并立即隐藏；headless 平台无窗口无任务栏"""
    from DrissionPage import Chromium, ChromiumOptions
    prof, port = PROFILES[platform]
    co = ChromiumOptions()
    co.set_browser_path(EDGE)
    co.set_local_port(port)
    co.set_user_data_path(os.path.join(os.path.dirname(__file__), '..', prof))
    if platform in HEADLESS:
        co.headless()  # 无窗口无任务栏（小布方案：逐个验证逐个切）
    else:
        # 有头隐藏：窗口移出屏幕 + 极小尺寸 + 禁会话恢复
        co.set_argument('--window-position=-32000,-32000')
        co.set_argument('--window-size=1,1')
        co.set_argument('--disable-session-crashed-bubble')
        co.set_argument('--no-first-run')
    b = Chromium(co)
    if platform not in HEADLESS:
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
    """预热后补一轮强制隐藏（等窗口全部创建后）；headless 跳过（审查员建议）"""
    for plat, b in list(_pool.items()):
        if plat in HEADLESS:
            continue
        try:
            _force_hide_windows(b.process_id)
        except Exception:
            pass


def rehide(platform: str):
    """搜索完成后强制隐藏兜底（小布方案）；headless 无窗可藏直接跳过（审查员建议）"""
    if platform in HEADLESS:
        return
    b = _pool.get(platform)
    if b is not None:
        try:
            _force_hide_windows(b.process_id)
        except Exception:
            pass


_rehiding = set()  # 防抖：同平台不重复启动隐藏循环


def rehide_loop(platform: str, rounds: int = 6, interval: float = 4.0):
    """循环隐藏：导航/详情页加载全程每 4s 补一刀（覆盖窗口复现；防抖防重复线程）"""
    if platform in _rehiding:
        return
    _rehiding.add(platform)

    def _r():
        try:
            for _ in range(rounds):
                rehide(platform)
                time.sleep(interval)
        finally:
            _rehiding.discard(platform)
    threading.Thread(target=_r, daemon=True).start()


_WARMED = False  # 防双 init（uvicorn reload 场景）


def warmup():
    """服务启动时预热 4 个浏览器（后台线程调用，不阻塞启动）"""
    global _WARMED
    if _WARMED:
        return
    _WARMED = True

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
