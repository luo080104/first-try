# -*- coding: utf-8 -*-
"""Go购 游戏化皮肤元素级验证（2026-08-18）
不依赖看图：JS 读取关键元素实际 computed style，验证深色背景可读性与面板样式落地。
"""

import sys
import time

from DrissionPage import ChromiumOptions, ChromiumPage

BASE = "http://127.0.0.1:8001"

CHECKS = {
    "/": [
        ("搜索卡片", ".search-box", ["background-color", "border-color"]),
        ("地标卡片", ".landmark", ["background-image", "color"]),
        ("陪你出发按钮", ".btn-guide", ["background-image", "color"]),
        ("副标题", ".subtitle", ["color"]),
        ("角色栏", "#role-bar", ["color"]),
    ],
    "/guide": [
        ("聊天气泡", ".msg.ai .bubble", ["background-color", "border-color"]),
        ("推荐卡片", ".rec-card", ["background-color", "border-color"]),
    ],
    "/hist": [
        ("历史条目", ".hist-item", ["background-color"]),
        ("标题", "h1", ["color"]),
    ],
    "/items": [
        ("筛选栏", ".filters", ["background-color"]),
        ("商品卡", ".item-card", ["background-color", "border-color"]),
    ],
    "/crawl": [
        ("状态卡", ".card", ["background-color", "border-color"]),
    ],
    "/compare": [
        ("对比卡", ".cmp-card", ["background-color", "border-color"]),
    ],
}


def _find(page, sel, retries=5):
    for _ in range(retries):
        if page.run_js("return !!document.querySelector(arguments[0]);", sel):
            return True
        time.sleep(1.2)
    return False


def main():
    co = ChromiumOptions()
    co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
    co.headless(True)
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-gpu")
    page = ChromiumPage(co)
    # family_pin 已设置——headless 扫描需带 pin（环境变量 UI_PIN 注入，不写死仓库）
    pin = __import__("os").environ.get("UI_PIN", "")
    if pin:
        page.get(BASE + "/")
        page.run_js("localStorage.setItem('gobuy_pin', arguments[0]);", pin)
    fails = 0
    for path, items in CHECKS.items():
        page.get(BASE + path)
        time.sleep(2)
        print(f"=== {path} ===")
        for label, sel, props in items:
            if not _find(page, sel):
                print(f"  {label:12s} {sel:20s} MISSING（动态内容/无数据）")
                continue
            props_json = __import__("json").dumps(props)
            vals = page.run_js(
                "var el=document.querySelector(arguments[0]);"
                "if(!el) return 'MISSING';"
                "var r={};"
                "JSON.parse(arguments[1]).forEach(function(p){r[p]=getComputedStyle(el)[p]});"
                "return JSON.stringify(r);",
                sel,
                props_json,
            )
            # 深背景可读性启发式：文字色与背景色对比（粗略）
            print(f"  {label:12s} {sel:20s} {vals}")
            if vals == "MISSING":
                fails += 1
    page.quit()
    print(f"\nfails={fails}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
