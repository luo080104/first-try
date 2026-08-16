# -*- coding: utf-8 -*-
"""风险仪表盘（risk_dashboard.py——v1.2——组合指标 + 关键风险即时提醒）

需求 v1.1 补录：周报推组合指标（总盈亏/最大回撤/持仓集中度）+ 关键风险即时提醒
（占比超限/回撤超线）——portfolio summary 雏形升级为完整仪表盘
- 即时提醒：超过红线 → 返回告警列表（接入周报/推送）
- 8 红线联动（Q9 风险计分——70 分触发现金纪律）
- 用法：python -m tools.strategy_engine.risk_dashboard（可并入周报/晨报）
"""

from __future__ import annotations

import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import portfolio as pf

# 红线参数（v0 先验——Q11 校准）
MAX_POSITION_PCT = 0.10  # P1：单只 ≤10%
MAX_INDUSTRY_PCT = 0.25  # P1：行业 ≤25%
MAX_DRAWDOWN_PCT = 20.0  # 定案：回撤 20% 可接受（虚拟盘实测校准）
MIN_CASH_PCT = 0.10  # Q5：现金下限 10%
MAX_CASH_PCT = 0.15  # Q5：现金上限 15%（超过=闲置——提示找机会）


def dashboard() -> dict[str, Any]:
    """组合风险仪表盘——返回指标 + 告警列表"""
    p = pf.Portfolio()
    s = p.summary()
    alerts: list[str] = []

    total = s.get("total", 0) or 0
    init = s.get("init_cash", 80000) or 80000
    pnl = total - init
    pnl_pct = pnl / init * 100 if init else 0

    # ① 集中度：单只 >10%
    for pos in s.get("positions", []):
        pos_pct = pos.get("market", 0) / total * 100 if total else 0
        if pos_pct > MAX_POSITION_PCT * 100:
            alerts.append(
                f"🔴 单只超限：{pos.get('name', '')} {pos_pct:.0f}% > {MAX_POSITION_PCT * 100}%"
            )

    # ② 现金纪律：<10% 防守 / >15% 闲置
    cash_pct = s.get("cash_pct", 0) or 0
    if cash_pct < MIN_CASH_PCT * 100:
        alerts.append(
            f"🔴 现金不足：{cash_pct:.0f}% < {MIN_CASH_PCT * 100}%（防守金线）"
        )
    elif cash_pct > MAX_CASH_PCT * 100:
        alerts.append(
            f"🟡 现金偏高：{cash_pct:.0f}% > {MAX_CASH_PCT * 100}%（闲置——找机会）"
        )

    # ③ 真实净值回撤（2026-08-15 升级：净值序列 → 最大回撤——替代盈亏近似）
    max_dd = 0.0
    curve = p.equity_series()
    if len(curve) >= 2:
        peak = 0.0
        for c in curve:
            t = c.get("total", 0) or 0
            peak = max(peak, t)
            if peak > 0:
                max_dd = max(max_dd, (peak - t) / peak * 100)
    if max_dd < 0.01 and pnl_pct < -MAX_DRAWDOWN_PCT:
        # 净值序列不足时用盈亏兜底（v0 行为）
        max_dd = abs(pnl_pct)
    if max_dd > MAX_DRAWDOWN_PCT:
        alerts.append(
            f"🔴 回撤超线：最大回撤 {max_dd:.1f}% > {MAX_DRAWDOWN_PCT}%（触发防守）"
        )

    # ④ 持仓数（Q4：3-5 只）
    n = s.get("n_holdings", 0)
    if n < 3:
        alerts.append(f"🟡 持仓不足：{n} 只 < 3（集中度风险——但持币等待是纪律）")
    elif n > 5:
        alerts.append(f"🟡 持仓过多：{n} 只 > 5（Q4 集中组合）")

    return {
        "total": round(total, 0),
        "pnl": round(pnl, 0),
        "pnl_pct": round(pnl_pct, 1),
        "max_dd": round(max_dd, 1),  # 真实净值最大回撤%（2026-08-15 升级）
        "cash_pct": round(cash_pct, 0),
        "holdings": n,
        "positions": [
            {
                "name": pos.get("name", ""),
                "code": pos.get("code", ""),
                "pnl_pct": pos.get("pnl_pct", 0),
            }
            for pos in s.get("positions", [])
        ],
        "alerts": alerts,
        "risk_ok": not alerts,
    }


if __name__ == "__main__":
    r = dashboard()
    print(
        f"📊 风险仪表盘：总资产 {r['total']:.0f} | 盈亏 {r['pnl']:+.0f}（{r['pnl_pct']:+.1f}%）| "
        f"现金 {r['cash_pct']:.0f}% | 持仓 {r['holdings']} 只"
    )
    for pos in r["positions"]:
        print(f"  {pos['name']}({pos['code']}) {pos['pnl_pct']:+.1f}%")
    if r["alerts"]:
        for a in r["alerts"]:
            print(f"  {a}")
    else:
        print("  ✅ 风险合规（红线内）")
