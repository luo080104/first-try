# -*- coding: utf-8 -*-
"""分页 + 步骤条 + result 页面验证（2026-08-18）"""

import time

from DrissionPage import ChromiumOptions, ChromiumPage

co = ChromiumOptions()
co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
co.headless(True)
co.set_argument("--no-sandbox")
page = ChromiumPage(co)

# 1. items 分页
page.get("http://127.0.0.1:8001/items")
time.sleep(5)
print(
    "pager:",
    page.run_js(
        "var p=document.querySelector('.pager'); return p ? p.innerText.split('\\n').join('|') : 'NOP';"
    ),
)
print("cards20:", page.run_js("return document.querySelectorAll('.item-card').length;"))
page.run_js("document.getElementById('pg-size').value='50'; loadItems(1);")
time.sleep(4)
print("cards50:", page.run_js("return document.querySelectorAll('.item-card').length;"))
page.run_js("loadItems(3);")
time.sleep(4)
print(
    "page3:",
    page.run_js(
        "var n=document.getElementById('pg-now'); return n ? n.innerText : 'NO';"
    ),
)
print(
    "input3:",
    page.run_js(
        "var i=document.getElementById('pg-input'); return i ? i.value : 'NO';"
    ),
)

# 2. 首页搜索 → 步骤条游戏化
page.get("http://127.0.0.1:8001/")
time.sleep(2)
page.run_js("localStorage.setItem('gobuy_pin','1234');")
page.run_js("var i=document.getElementById('kw'); i.value='雷士'; doSearch();")
time.sleep(6)
print("quest items:", page.run_js("return document.querySelectorAll('.quest').length;"))
print(
    "quest sample:",
    page.run_js(
        "var q=document.querySelector('.quest'); return q ? q.className + '|' + q.innerText : 'NO';"
    ),
)

# 3. result 页静态渲染（用已知 keyword 走 result 路由）
page.get("http://127.0.0.1:8001/result?keyword=%E9%9B%B7%E5%A3%AB")
time.sleep(3)
print(
    "result groups:", page.run_js("return document.querySelectorAll('.group').length;")
)
print(
    "result bili-btn class:",
    page.run_js(
        "var b=document.getElementById('bili-btn'); return b ? b.className : 'NO';"
    ),
)
page.quit()
