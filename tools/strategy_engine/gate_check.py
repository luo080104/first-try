# -*- coding: utf-8 -*-
"""虚拟盘通过判定（gate_check.py——v1.1——定案：连续 4 周跑赢基准 或 满 3 个月）

需求 v1.1 定案：连续 N 周跑赢基准（N=4 默认）或满 3 个月（先到为准）——基准沪深300 默认
- 数据：portfolio 事件日志（Q11——buy_date 记录）
- 判定：有持仓 → 周度对比（组合净值 vs 沪深300）——4 周连续超额 → 通过
- 满 3 个月（90 天）未 4 周连胜 → 也通过（先到为准）
- 通过后 → 通知甲方（真钱阶段决策：2-3 万起步——乙方提问 5 定案）
"""

from __future__ import annotations

import datetime
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import portfolio as pf

CONSECUTIVE_WEEKS = 4  # 连续跑赢周数（需求 v1.1——默认 4）
MAX_DAYS = 90  # 满 3 个月（先到为准）


def _portfolio_weeks() -> list[dict[str, Any]]:
    """组合周度净值序列（equity_curve——record_equity 每日记录——2026-08-15 升级）

    说明：净值点按周聚合（取每周最后一点）——与沪深300 周线对齐——算连续跑赢
    净值数据不足（<2 周）→ 返回空——等积累（Q11 精神：样本不足不判定）
    """
    p = pf.Portfolio()
    s = p.summary()
    if not s.get("n_holdings"):
        return []
    curve = p.equity_series()
    if len(curve) < 14:  # 至少 2 周净值点（7 天/周）
        return []
    # 按 ISO 周聚合（取每周最后一点）
    weekly: dict[str, float] = {}
    for pt in curve:
        d = pt.get("date", "")[:10]
        if not d:
            continue
        try:
            iso = datetime.date.fromisoformat(d).isocalendar()
        except ValueError:
            continue
        key = f"{iso[0]}-W{iso[1]:02d}"
        weekly[key] = float(pt.get("total", 0))
    return [{"week": k, "total": v} for k, v in sorted(weekly.items())]


def check() -> dict[str, Any]:
    """通过判定——返回 {passed, reason, days, weeks_beat}

    定案（需求 v1.1）：连续 4 周跑赢沪深300 或满 3 个月（先到为准）
    - 净值序列（equity_curve）vs 沪深300 周线（baostock）——逐周对比
    - 净值不足 2 周 → 数据不足（Q11：样本不足不判定）
    """
    p = pf.Portfolio()
    s = p.summary()
    if not s.get("n_holdings"):
        return {
            "passed": False,
            "reason": "虚拟盘空仓（未开跑或已清仓）",
            "days": 0,
            "weeks_beat": 0,
        }
    # 建仓日起算天数（事件日志最早 buy）
    events = []
    path = os.path.join(os.path.dirname(pf.PORTFOLIO_FILE), "portfolio_events.jsonl")
    if os.path.exists(path):
        import json

        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            pass
    buys = [e for e in events if e.get("action") == "buy"]
    start = min((e.get("ts") or e.get("date") or "")[:10] for e in buys) if buys else ""
    days = (
        (datetime.date.today() - datetime.date.fromisoformat(start)).days if start else 0
    )
    # 满 3 个月（先到为准）
    if days >= MAX_DAYS:
        return {
            "passed": True,
            "reason": f"满 {MAX_DAYS} 天（{days} 天）——先到为准通过",
            "days": days,
            "weeks_beat": 0,
        }
    # 连续 4 周跑赢：净值序列 vs 沪深300 周线
    weekly = _portfolio_weeks()
    if not weekly:
        return {
            "passed": False,
            "reason": f"净值序列不足 2 周（record_equity 每日记录中——当前 {days} 天）",
            "days": days,
            "weeks_beat": 0,
        }
    # 沪深300 周线（同窗口——baostock）
    from tools.strategy_engine import data as d

    bench_weeks = d.bs_kline_weekly("000300", 10)
    bench = {w["date"][:10]: w["close"] for w in bench_weeks}
    # 逐周对比：组合周收益 vs 基准周收益
    wins = 0
    max_wins = 0
    for i in range(1, len(weekly)):
        prev_t, cur_t = weekly[i - 1]["total"], weekly[i]["total"]
        if prev_t <= 0:
            continue
        port_ret = (cur_t - prev_t) / prev_t
        # 基准同期收益（用该周最后一天近似）
        cur_date = _week_last_day(weekly[i]["week"])
        prev_date = _week_last_day(weekly[i - 1]["week"])
        bc, bp = bench.get(cur_date), bench.get(prev_date)
        if not bc or not bp or bp <= 0:
            continue
        bench_ret = (bc - bp) / bp
        wins = wins + 1 if port_ret > bench_ret else 0
        max_wins = max(max_wins, wins)
    if max_wins >= CONSECUTIVE_WEEKS:
        return {
            "passed": True,
            "reason": f"连续 {max_wins} 周跑赢沪深300（净值序列实证）",
            "days": days,
            "weeks_beat": max_wins,
        }
    return {
        "passed": False,
        "reason": f"运行 {days} 天——最高连续跑赢 {max_wins} 周（需 {CONSECUTIVE_WEEKS} 周——满 {MAX_DAYS} 天也通过）",
        "days": days,
        "weeks_beat": max_wins,
    }


def _week_last_day(week_key: str) -> str:
    """ISO 周键（2026-W33）→ 该周最后一天（周日）"""
    try:
        y, w = int(week_key[:4]), int(week_key.split("W")[1])
        import datetime as dt

        # ISO 周: 周一为第 1 天——周日 = 周一 + 6 天
        jan4 = dt.date(y, 1, 4)
        monday = jan4 - dt.timedelta(days=jan4.isocalendar()[2] - 1) + dt.timedelta(weeks=w - 1)
        return (monday + dt.timedelta(days=6)).isoformat()
    except (ValueError, IndexError):
        return ""


if __name__ == "__main__":
    print(check())
