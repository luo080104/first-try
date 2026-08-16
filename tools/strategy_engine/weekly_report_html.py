# -*- coding: utf-8 -*-
"""观复周报 HTML 版（weekly_report_html.py——2026-08-16 界面美化升级）

Bento 卡片布局（UZI Bloomberg 风格借鉴——观复品牌化）
- 深色主题（OLED 黑 + 观复金/蓝 accent）
- KPI 面板（总资产/盈亏/现金/持仓）
- 净值曲线（ECharts——网页交互）
- 持仓明细 / 操作流 / 策略表现 / 行为画像 / 下周关注

用法：python -m tools.strategy_engine.weekly_report_html → data/weekly_report.html
（gf_web 网页端可内嵌/链接）
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import portfolio as pf

OUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "weekly_report.html"
)

# 观复品牌色（金=价值/蓝=技术/绿=盈利/红=亏损）
_CSS = """
:root {
  --bg: #0d1117; --card: #161b22; --border: #30363d;
  --gold: #d4a72c; --blue: #58a6ff; --green: #3fb950; --red: #f85149;
  --text: #e6edf3; --muted: #8b949e;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--text); font-family:'Segoe UI','Microsoft YaHei',sans-serif; padding:24px; max-width:900px; margin:0 auto; }
h1 { font-size:24px; display:flex; align-items:center; gap:10px; }
h1 .logo { color:var(--gold); font-size:28px; }
.sub { color:var(--muted); font-size:13px; margin:6px 0 18px; }
.grid { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:16px 0; }
.kpi { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:14px; }
.kpi .label { color:var(--muted); font-size:12px; }
.kpi .value { font-size:20px; font-weight:700; margin-top:4px; }
.kpi .value.pos { color:var(--green); } .kpi .value.neg { color:var(--red); }
.card { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; margin:14px 0; }
.card h2 { font-size:15px; color:var(--gold); margin-bottom:12px; display:flex; align-items:center; gap:8px; }
table { width:100%; border-collapse:collapse; font-size:14px; }
td,th { padding:8px 10px; text-align:left; border-bottom:1px solid var(--border); }
th { color:var(--muted); font-weight:500; font-size:12px; }
.pos { color:var(--green); } .neg { color:var(--red); }
.tag { display:inline-block; padding:2px 10px; border-radius:20px; font-size:12px; }
.tag.buy { background:#1f6feb33; color:var(--blue); }
.tag.sell { background:#f8514933; color:var(--red); }
.footer { color:var(--muted); font-size:12px; text-align:center; margin-top:24px; }
#chart { height:240px; }
"""


def _kpis(s: dict[str, Any]) -> str:
    """KPI 面板（4 卡）"""
    total = s.get("total", 0)
    pnl = total - s.get("init_cash", 0)
    pct = pnl / s.get("init_cash", 1) * 100
    cls = "pos" if pnl >= 0 else "neg"
    return f"""
<div class="grid">
  <div class="kpi"><div class="label">总资产</div><div class="value">{total:,.0f}</div></div>
  <div class="kpi"><div class="label">累计盈亏</div><div class="value {cls}">{pnl:+,.0f}（{pct:+.1f}%）</div></div>
  <div class="kpi"><div class="label">现金占比</div><div class="value">{s.get("cash_pct", 0):.0f}%</div></div>
  <div class="kpi"><div class="label">持仓</div><div class="value">{s.get("n_holdings", 0)} 只</div></div>
</div>"""


def _equity_chart() -> str:
    """净值曲线（ECharts——交互）"""
    curve = pf.Portfolio().equity_series()
    if len(curve) < 2:
        return f'<div class="card"><h2>📈 净值曲线</h2><p style="color:var(--muted)">积累中（{len(curve)} 点——每日 9:00 自动记录）</p></div>'
    dates = json.dumps([c["date"] for c in curve], ensure_ascii=False)
    totals = json.dumps([c["total"] for c in curve])
    return f"""
<div class="card"><h2>📈 净值曲线（{len(curve)} 点）</h2>
<div id="chart"></div></div>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
const ch = echarts.init(document.getElementById('chart'));
ch.setOption({{
  grid: {{left:70, right:20, top:20, bottom:30}},
  xAxis: {{type:'category', data:{dates}, axisLabel:{{color:'#8b949e'}}}},
  yAxis: {{type:'value', scale:true, splitLine:{{lineStyle:{{color:'#30363d'}}}}, axisLabel:{{color:'#8b949e'}}}},
  series: [{{type:'line', data:{totals}, smooth:true, lineStyle:{{color:'#d4a72c', width:2}},
    areaStyle:{{color:'#d4a72c22'}}, itemStyle:{{color:'#d4a72c'}}}}]
}});
</script>"""


def _positions(s: dict[str, Any]) -> str:
    rows = ""
    for pos in s.get("positions", []):
        pp = pos.get("pnl_pct", 0)
        cls = "pos" if pp >= 0 else "neg"
        rows += (
            f"<tr><td>{pos.get('name', '')}</td><td>{pos.get('code', '')}</td>"
            f"<td>{pos.get('shares', 0)}</td>"
            f"<td class='{cls}'>{pp:+.1f}%</td></tr>"
        )
    return f"""
<div class="card"><h2>📦 持仓明细</h2>
<table><tr><th>名称</th><th>代码</th><th>股数</th><th>盈亏</th></tr>{rows}</table></div>"""


def _operations(events: list[dict[str, Any]]) -> str:
    ops = [e for e in events if e.get("action") in ("buy", "sell")]
    if not ops:
        return '<div class="card"><h2>📋 本周操作</h2><p style="color:var(--muted)">🤝 无操作——持有不动（纪律）</p></div>'
    rows = ""
    for e in ops:
        tag = "buy" if e["action"] == "buy" else "sell"
        label = "买入" if e["action"] == "buy" else "卖出"
        rows += (
            f"<tr><td><span class='tag {tag}'>{label}</span></td>"
            f"<td>{e.get('name', '')}</td><td>{e.get('code', '')}</td>"
            f"<td>{e.get('shares', 0)} 股</td><td>@{e.get('price', 0)}</td></tr>"
        )
    return f'<div class="card"><h2>📋 本周操作（{len(ops)} 笔）</h2><table><tr><th></th><th>名称</th><th>代码</th><th>数量</th><th>价格</th></tr>{rows}</table></div>'


def _strategy() -> str:
    """策略表现（信号账本）"""
    try:
        from tools.strategy_engine import signal_ledger as sl

        rep = sl.report()
        total = rep.get("total", 0) if isinstance(rep, dict) else 0
        return (
            f'<div class="card"><h2>🎯 策略表现</h2>'
            f"<p>📒 累计信号 {total} 笔——回填验证随 Q11 积累</p></div>"
        )
    except Exception:
        return '<div class="card"><h2>🎯 策略表现</h2><p style="color:var(--muted)">账本采集中</p></div>'


def build_html() -> str:
    """组装完整 HTML 周报"""
    from tools.strategy_engine.weekly_report import _behavior_check, _week_events

    p = pf.Portfolio()
    s = p.summary()
    events = _week_events()
    today = datetime.date.today()
    week_no = today.isocalendar()[1]
    behavior = "".join(f"<p>{n}</p>" for n in _behavior_check(events))
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>观复周报 · 第 {week_no} 周</title>
<style>{_CSS}</style></head><body>
<h1><span class="logo">观</span>观复周报 · 第 {week_no} 周</h1>
<div class="sub">🗓️ {today.isoformat()} · 书体系执行器 · 吴老师书体系</div>
{_kpis(s)}
{_equity_chart()}
{_operations(events)}
{_positions(s)}
{_strategy()}
<div class="card"><h2>🧭 行为画像</h2>{behavior}</div>
<div class="footer">观复 · 一生项目 · 半自动（信号需人工确认）</div>
</body></html>"""


if __name__ == "__main__":
    html = build_html()
    try:
        os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
        with open(OUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ 周报 HTML 已生成: {OUT_FILE}（{len(html) // 1024}KB）")
    except OSError as e:
        print(f"❌ 周报 HTML 写入失败: {e}")
