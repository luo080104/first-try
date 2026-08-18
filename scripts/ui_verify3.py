# -*- coding: utf-8 -*-
"""最终验证：搜索全链路 + quest 完成态 + result.html 静态类检查（2026-08-18）"""
import re
import time

from DrissionPage import ChromiumOptions, ChromiumPage

co = ChromiumOptions()
co.set_browser_path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")
co.headless(True)
co.set_argument("--no-sandbox")
page = ChromiumPage(co)

page.get("http://127.0.0.1:8001/")
time.sleep(2)
page.run_js("localStorage.setItem('gobuy_pin','1234');")
page.run_js("var i=document.getElementById('kw'); i.value='雷士'; doSearch();")
time.sleep(10)
print("quest done:", page.run_js(
    "return document.querySelectorAll('.quest.done').length + ' 个完成 / 总 ' + document.querySelectorAll('.quest').length;"))
print("sse 结果:", page.run_js(
    "var b=document.getElementById('sse-result'); return b ? b.innerText.slice(0,80) : 'NO';").replace("\n", "|"))

try:
    html = open("src/templates/result.html", encoding="utf-8").read()
except OSError:
    html = ""
m = re.search(r'id="bili-btn"[\s\S]{0,120}?class="([^"]+)"', html)
print("result bili-btn:", m.group(1) if m else "MISSING")
print("result 含 pi-lens-ignore:", html.count("pi-lens-ignore"), "处")
page.quit()
