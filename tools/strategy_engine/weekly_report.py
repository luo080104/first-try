# -*- coding: utf-8 -*-
"""周报（weekly_report.py——v1.2——每周自动复盘：操作/盈亏/策略表现/下周关注）

需求 v1.1 补录：周报=每周自动（操作/盈亏/策略表现/下周关注）——行为画像段（Q10）
数据源：portfolio 事件日志（本周操作）+ 当前持仓（盈亏）+ signal_ledger（信号表现）
- 行为画像（Q10）：本周操作 vs 纪律检查（追涨/杀跌/频繁交易/偏离计划）
- 推送：复用 notify_gf（低频合并节流——周报算 1 条）
- 用法：python -m tools.strategy_engine.weekly_report（每周五收盘后任务计划）
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import portfolio as pf

_WEEK_START = datetime.timedelta(days=7)


def _week_events() -> list[dict[str, Any]]:
    """本周事件（portfolio_events.jsonl——近 7 天）"""
    out = []
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
                ts = (e.get("ts") or "")[:10]
                if (
                    ts
                    and (datetime.date.today() - datetime.date.fromisoformat(ts)).days
                    <= 7
                ):
                    out.append(e)
    except OSError:
        pass
    return out


def _behavior_check(events: list[dict[str, Any]]) -> list[str]:
    """行为画像（Q10——纪律检查——Q7 教训：拿住是纪律）"""
    notes: list[str] = []
    buys = [e for e in events if e.get("action") in ("buy", "加仓", "加仓")]
    sells = [e for e in events if e.get("action") in ("sell", "减仓", "减仓")]
    if len(buys) + len(sells) > 5:
        notes.append(
            f"⚠️ 本周操作 {len(buys) + len(sells)} 笔——偏频繁（书：低频合并——计划外不动）"
        )
    if buys and not sells:
        notes.append("✅ 本周只加仓未减仓——拿住纪律（Q10）")
    if sells and not buys:
        notes.append("ℹ️ 本周只减仓——检查是否触发卖出规则（S2 上轨/止损）")
    if not events:
        notes.append("✅ 本周无操作——持有不动是纪律（Q10——最不坏路径）")
    return notes or ["✅ 操作符合计划"]


def build_report() -> str:
    """组装周报文本"""
    p = pf.Portfolio()
    s = p.summary()
    events = _week_events()
    lines = [f"📋 观复周报（{datetime.date.today().isoformat()}）", "=" * 30]

    # ① 操作
    ops = [e for e in events if e.get("action") in ("buy", "sell")]
    lines.append(f"\n【本周操作】{len(ops)} 笔")
    for e in ops:
        lines.append(
            f"  {e['action']} {e.get('name', '')}({e.get('code', '')}) "
            f"{e.get('shares', 0)}股 @{e.get('price', 0)}"
        )
    if not ops:
        lines.append("  （无操作——持有不动）")

    # ② 盈亏
    pnl = s.get("total", 0) - s.get("init_cash", 0)
    lines.append(
        f"\n【持仓】{s.get('n_holdings', 0)} 只 | 总资产 {s.get('total', 0):.0f} | "
        f"现金 {s.get('cash_pct', 0):.0f}% | 浮动 {pnl:+.0f} 元（{pnl / s.get('init_cash', 1) * 100:+.1f}%）"
    )
    for pos in s.get("positions", []):
        lines.append(
            f"  {pos.get('name', '')}({pos.get('code', '')}) "
            f"{pos.get('shares', 0)}股 盈亏 {pos.get('pnl', 0):+.0f}（{pos.get('pnl_pct', 0):+.1f}%）"
        )

    # ③ 策略表现（signal_ledger 信号回顾）
    lines.append("\n【信号表现】本周信号记录：")
    try:
        from tools.strategy_engine import signal_ledger as sl

        rep = sl.report()
        if isinstance(rep, dict) and rep.get("total"):
            lines.append(f"  累计信号 {rep['total']} 笔——回填验证随 Q11 积累")
        else:
            lines.append("  （账本采集中——3/6/12 月后回填验证）")
    except Exception:
        lines.append("  （账本采集中——3/6/12 月后回填验证）")

    # ④ 行为画像（Q10）
    lines.append("\n【行为画像】")
    lines.extend(f"  {n}" for n in _behavior_check(events))

    # ⑤ 下周关注
    lines.append("\n【下周关注】")
    if not s.get("n_holdings"):
        lines.append("  空仓中——等待达标信号（持币等待是纪律）")
    elif s.get("cash_pct", 0) > 15:
        lines.append("  现金偏高——关注买入信号（B3 低潮/打分达标）")
    else:
        lines.append("  持仓观察——跌破门槛→观察标记，连续两季→换仓建议（Q14）")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_report())
