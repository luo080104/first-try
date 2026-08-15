# -*- coding: utf-8 -*-
"""观复网页配置页（gf_web.py——v1.2——设规则/看持仓/查历史）

定案：手机推送为主 + 网页配置页（简单即可）——FastAPI 独立端口 8201
页面：
  /           总览（持仓+风险仪表盘）
  /watch      盯价清单管理（添加/移除）
  /history    事件日志（本周操作）
  /brief      手动触发晨报推送
安全：仅监听 127.0.0.1（内网——不暴露公网——Go购 同策略）
运行：python -m tools.strategy_engine.gf_web
"""

from __future__ import annotations

import json
import os
import sys

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import price_watch as pw
from tools.strategy_engine import portfolio as pf
from tools.strategy_engine import risk_dashboard as rd

app = FastAPI(title="观复配置页")

_PAGE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>观复 · 配置页</title>
<style>
body{{font-family:system-ui;max-width:640px;margin:0 auto;padding:16px;background:#fafafa}}
h1{{font-size:20px}} h2{{font-size:16px;margin-top:24px}}
.card{{background:#fff;border-radius:8px;padding:12px 16px;margin:8px 0;box-shadow:0 1px 3px #0002}}
.ok{{color:#16a34a}} .warn{{color:#d97706}} .bad{{color:#dc2626}}
nav a{{margin-right:12px;color:#2563eb;text-decoration:none}}
input,select{{padding:6px;margin:2px 0}} button{{padding:6px 12px;background:#2563eb;color:#fff;border:none;border-radius:6px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:6px;text-align:left;border-bottom:1px solid #eee}}
</style></head><body>
<h1>📊 观复</h1>
<nav><a href="/">总览</a><a href="/watch">盯价</a><a href="/history">历史</a><a href="/brief">晨报</a></nav>
{content}
</body></html>"""


def _fmt(items: list[dict]) -> str:
    """格式化行情/持仓行"""
    return "".join(
        f"<tr><td>{it.get('name', '')}</td><td>{it.get('code', '')}</td>"
        f"<td>{it.get('price', it.get('target', ''))}</td>"
        f"<td>{it.get('pnl', '')}</td></tr>"
        for it in items
    )


@app.get("/", response_class=HTMLResponse)
def overview():
    r = rd.dashboard()
    cls = "ok" if r["risk_ok"] else "warn"
    pos_rows = "".join(
        f"<tr><td>{p['name']}</td><td>{p['code']}</td><td>{p['pnl_pct']:+.1f}%</td></tr>"
        for p in r["positions"]
    )
    alerts = (
        "".join(f"<div class='{cls}'>{a}</div>" for a in r["alerts"])
        or "<div class='ok'>✅ 风险合规</div>"
    )
    content = f"""
<h2>总览</h2>
<div class='card'>总资产 {r["total"]:.0f} ｜ 盈亏 {r["pnl"]:+.0f}（{r["pnl_pct"]:+.1f}%）
｜ 现金 {r["cash_pct"]:.0f}% ｜ 持仓 {r["holdings"]} 只</div>
{alerts}
<h2>持仓</h2><div class='card'><table><tr><th>名称</th><th>代码</th><th>盈亏</th></tr>{pos_rows}</table></div>
"""
    return _PAGE.format(content=content)


@app.get("/watch", response_class=HTMLResponse)
def watch_page():
    items = pw._load()["items"]
    rows = (
        "".join(
            f"<tr><td>{it['name']}</td><td>{it['code']}</td><td>{it['target']}</td>"
            f"<td>{'跌破' if it['direction'] == 'below' else '涨破'}</td>"
            f"<td>{'🔔已提醒' if it.get('alerted') else '监视中'}</td>"
            f"<td><a href='/watch/del?code={it['code']}&d={it['direction']}'>删</a></td></tr>"
            for it in items
        )
        or "<tr><td colspan='6'>暂无盯价</td></tr>"
    )
    content = f"""
<h2>盘中盯价</h2>
<div class='card'><table><tr><th>名称</th><th>代码</th><th>目标价</th><th>方向</th><th>状态</th><th></th></tr>{rows}</table></div>
<h2>添加</h2>
<div class='card'><form method='post' action='/watch/add'>
名称/备注 <input name='note' placeholder='招行心理位'>
代码 <input name='code' placeholder='600036' required>
目标价 <input name='target' type='number' step='0.01' required>
方向 <select name='direction'><option value='below'>跌破提醒</option><option value='above'>涨破提醒</option></select>
<button>添加</button></form></div>
"""
    return _PAGE.format(content=content)


@app.post("/watch/add")
def watch_add(
    note: str = Form(""),
    code: str = Form(...),
    target: float = Form(...),
    direction: str = Form("below"),
):
    pw.add(code, target, direction, note)
    return RedirectResponse("/watch", status_code=303)


@app.get("/watch/del")
def watch_del(code: str = Query(...), d: str = Query("below")):
    pw.remove(code, d)
    return RedirectResponse("/watch", status_code=303)


@app.get("/history", response_class=HTMLResponse)
def history():
    rows = ""
    try:
        with open(pf.EVENTS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                rows += (
                    f"<tr><td>{e.get('ts', '')[:16]}</td><td>{e.get('action', '')}</td>"
                    f"<td>{e.get('name', '')}</td><td>{e.get('shares', '')}</td>"
                    f"<td>{e.get('price', '')}</td></tr>"
                )
    except OSError:
        pass
    content = f"<h2>事件历史</h2><div class='card'><table><tr><th>时间</th><th>操作</th><th>名称</th><th>数量</th><th>价格</th></tr>{rows}</table></div>"
    return _PAGE.format(content=content)


@app.get("/brief", response_class=HTMLResponse)
def brief_page():
    try:
        from tools.strategy_engine.notify_gf import push_brief

        ok = push_brief()
        msg = "✅ 晨报已推送（看微信）" if ok else "⚠️ 推送失败/达上限（今日≤3条）"
    except Exception:
        msg = "⚠️ 推送异常"
    return _PAGE.format(
        content=f"<h2>晨报</h2><div class='card'>{msg}</div><a href='/'>返回</a>"
    )


if __name__ == "__main__":
    import uvicorn

    print("观复配置页：http://127.0.0.1:8201")
    uvicorn.run(app, host="127.0.0.1", port=8201, log_level="warning")
