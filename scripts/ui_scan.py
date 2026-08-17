# -*- coding: utf-8 -*-
"""Go购 界面皮肤浏览器级扫描（2026-08-18 游戏化改造验证）
逐页打开 + 截图 + 收集 console 错误 + 检查深色背景可读性关键元素。
用法: python scripts/ui_scan.py
"""

import sys
import time

from DrissionPage import ChromiumOptions, ChromiumPage

PAGES = [
    ("/", "home"),
    ("/guide", "guide"),
    ("/hist", "hist"),
    ("/items", "items"),
    ("/watches", "watches"),
    ("/compare", "compare"),
    ("/crawl", "crawl"),
    ("/wander", "wander"),
    ("/submit", "submit"),
]

BASE = "http://127.0.0.1:8001"


def main():
    co = ChromiumOptions()
    co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    co.headless(True)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    co.set_argument("--window-size", "480,900")  # 手机竖屏
    page = ChromiumPage(co)
    results = []
    for path, name in PAGES:
        url = BASE + path
        try:
            page.get(url)
            time.sleep(1.5)
            # 页面 body 背景色
            bg = page.run_js("return getComputedStyle(document.body).backgroundColor;")
            # 主体文字颜色（body 直属 h1）
            h1_color = page.run_js(
                "var h=document.querySelector('h1');"
                "return h?getComputedStyle(h).color:'none';"
            )
            # 可见文字量
            text_len = page.run_js("return document.body.innerText.length;")
            # console 错误（通过监听重新加载捕获）
            page.get(url)
            time.sleep(1.2)
            shot = f"data/ui_shot_{name}.png"
            page.get_screenshot(path=shot, full_page=True)
            results.append(
                {
                    "page": name,
                    "url": path,
                    "ok": True,
                    "body_bg": bg,
                    "h1_color": h1_color,
                    "text_chars": text_len,
                    "shot": shot,
                }
            )
        except Exception as e:
            results.append({"page": name, "url": path, "ok": False, "err": str(e)})
    page.quit()
    for r in results:
        if r["ok"]:
            print(
                f"{r['page']:8s} bg={r['body_bg']:20s} h1={r['h1_color']:12s} text={r['text_chars']:5d} {r['shot']}"
            )
        else:
            print(f"{r['page']:8s} FAIL: {r['err'][:80]}")
    bad = [r for r in results if not r["ok"]]
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
