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


def _equity_curve_png() -> str | None:
    """净值曲线图 → base64 data URL（2026-08-15——周报图——Server酱 pics 内嵌）

    matplotlib Agg 无头渲染——失败返回 None（文本周报降级——红线③容错）
    """
    try:
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 中文字体（Windows 微软雅黑——matplotlib 默认 DejaVu 无 CJK 字形）
        plt.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        curve = pf.Portfolio().equity_series()
        if len(curve) < 2:
            return None
        dates = [c["date"] for c in curve]
        totals = [c["total"] for c in curve]
        # 沪深300 对比（同窗口——baostock 周线）
        bench: list[float] = []
        try:
            from tools.strategy_engine import data as d

            bw = d.bs_kline_weekly("000300", 10)
            bd = {w["date"][:10]: w["close"] for w in bw}
            init_b = None
            for dt in dates:
                if dt in bd:
                    if init_b is None:
                        init_b = bd[dt]
                    if init_b:
                        bench.append(round((bd[dt] / init_b - 1) * 100, 2))
        except Exception:
            pass  # 基准失败——只有净值线
        fig, ax = plt.subplots(figsize=(7, 3.5))
        init = totals[0] or 1
        norm = [(t / init - 1) * 100 for t in totals]
        ax.plot(dates, norm, label="观复组合", color="#2563eb", linewidth=2)
        if len(bench) == len(norm):
            ax.plot(
                dates, bench, label="沪深300", color="#d97706", linewidth=1.5, alpha=0.8
            )
        ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")
        ax.set_title("观复虚拟盘净值（相对初始 %）")
        ax.legend(fontsize=9)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def push_weekly_with_chart() -> bool:
    """周报推送（含净值图——Server酱 pics 内嵌——2026-08-15）

    无图（净值点不足/渲染失败）→ 纯文本周报降级
    """
    from tools.strategy_engine import notify_gf as ng

    if ng.push_wechat is None:
        return False
    text = build_report()
    pic = _equity_curve_png()
    return ng.push_with_pic(f"📊 观复周报（含净值图）\n\n{text}", pic)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--push":
        ok = push_weekly_with_chart()
        print(f"周报推送（含图）: {'✅' if ok else '❌'}")
    else:
        print(build_report())
