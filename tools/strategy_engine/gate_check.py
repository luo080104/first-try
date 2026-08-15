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
    """组合周度净值序列（简化：用持仓事件日 + 最新行情——v0 近似）

    说明：真实周度净值需每日记账（虚拟盘运行中积累）——MVP 阶段用
    portfolio 事件（buy 日 cost 基准）+ 当前市值对比——Q11 账本完善后替换
    """
    p = pf.Portfolio()
    s = p.summary()
    if not s.get("n_holdings"):
        return []
    # 最早建仓日 → 距今周数（从 buy_date 起算——事件日志）
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
            pass  # 事件日志读不了——用持仓 fallback
    buys = [e for e in events if e.get("action") == "buy"]
    if not buys:
        return []
    start = min((e.get("ts") or e.get("date") or "")[:10] for e in buys)
    if not start:
        return []
    return [{"start": start, "days": (datetime.date.today() - datetime.date.fromisoformat(start)).days}]


def check() -> dict[str, Any]:
    """通过判定——返回 {passed, reason, days, weeks_beat}"""
    p = pf.Portfolio()
    s = p.summary()
    if not s.get("n_holdings"):
        return {"passed": False, "reason": "虚拟盘空仓（未开跑或已清仓）", "days": 0, "weeks_beat": 0}
    info = _portfolio_weeks()
    if not info:
        return {"passed": False, "reason": "无建仓事件（数据不足）", "days": 0, "weeks_beat": 0}
    days = info[0]["days"]
    # 满 3 个月（先到为准）
    if days >= MAX_DAYS:
        return {
            "passed": True,
            "reason": f"满 {MAX_DAYS} 天（{days} 天）——先到为准通过",
            "days": days,
            "weeks_beat": 0,
        }
    # 连续 4 周跑赢：需要周度净值数据——MVP 用最新市值 vs 建仓成本近似
    # （真实周度对比——Q11 账本积累后启用——此处标注近似）
    total = s.get("total") or 0
    init = s.get("init_cash") or 100000
    pnl = (total / init - 1) * 100 if init else 0
    weeks_beat = 1 if pnl > 0 else 0  # v0 近似：当前为正收益视为跑赢起步
    if weeks_beat >= CONSECUTIVE_WEEKS:
        return {
            "passed": True,
            "reason": f"连续 {weeks_beat} 周跑赢基准（v0 近似——Q11 账本完善后精确化）",
            "days": days,
            "weeks_beat": weeks_beat,
        }
    return {
        "passed": False,
        "reason": f"运行 {days} 天（{CONSECUTIVE_WEEKS} 周连胜需周度数据积累——当前 {pnl:+.1f}%）",
        "days": days,
        "weeks_beat": weeks_beat,
    }


if __name__ == "__main__":
    print(check())
