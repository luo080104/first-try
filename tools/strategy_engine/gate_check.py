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
        try:
            weekly[key] = float(pt.get("total", 0))
        except (TypeError, ValueError):
            continue  # 坏数据跳过（不崩——红线③容错）
    return [{"week": k, "total": v} for k, v in sorted(weekly.items())]


def check() -> dict[str, Any]:
    """通过判定——返回 {passed, reason, days, weeks_beat}

    定案（需求 v1.1）：连续 4 周跑赢沪深300 或满 3 个月（先到为准）
    整改①（2026-08-15）：跑赢判定加 Beta/Alpha 归因——Alpha 必须为正
    （防"押对板块"的运气误判——3 持仓全金融板块——跑赢可能只是 Beta）
    - 净值序列（equity_curve）vs 沪深300 周线（baostock）——逐周对比
    - 净值不足 2 周 → 数据不足（Q11：样本不足不判定）
    - 归因数据不足 → 不阻断跑赢判定（标注缺口——等积累）
    """
    p = pf.Portfolio()
    s = p.summary()
    if not s.get("n_holdings"):
        return {
            "passed": False,
            "reason": "虚拟盘空仓（未开跑或已清仓）",
            "days": 0,
            "weeks_beat": 0,
            "alpha_positive": None,
            "attribution_note": "空仓——无归因",
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
        (datetime.date.today() - datetime.date.fromisoformat(start)).days
        if start
        else 0
    )
    # 归因拆解（整改①——组合日净值 vs 沪深300 日线）
    from tools.strategy_engine import attribution as attr
    from tools.strategy_engine import data as d

    curve = p.equity_series()
    att = {"alpha_positive": None, "attribution_note": "净值不足——归因跳过"}
    if len(curve) >= 11:
        try:
            bench_daily = d.bs_kline_daily("000300", 1)
            att = attr.attribution(curve, bench_daily)
        except Exception:
            att = {
                "alpha_positive": None,
                "attribution_note": "归因数据获取失败（红线⑤——显式标注）",
            }
    # 满 3 个月（先到为准）——满 90 天通过（长期实盘观察——归因仅参考）
    if days >= MAX_DAYS:
        return {
            "passed": True,
            "reason": f"满 {MAX_DAYS} 天（{days} 天）——先到为准通过（归因参考：{att.get('attribution_note', '')}）",
            "days": days,
            "weeks_beat": 0,
            "alpha_positive": att.get("alpha_positive"),
            "attribution_note": att.get("attribution_note", ""),
        }
    # 连续 4 周跑赢：净值序列 vs 沪深300 周线
    weekly = _portfolio_weeks()
    if not weekly:
        return {
            "passed": False,
            "reason": f"净值序列不足 14 个点（record_equity 每日记录中——当前 {days} 天——约需 2 周）",
            "days": days,
            "weeks_beat": 0,
            "alpha_positive": att.get("alpha_positive"),
            "attribution_note": att.get("attribution_note", ""),
        }
    # 沪深300 周线（同窗口——baostock）
    bench_weeks = d.bs_kline_weekly("000300", 10)
    bench = {w["date"][:10]: w["close"] for w in bench_weeks}
    # 风格对照（2026-08-16 架构师 P1 落地——观测先行——判定不变）：
    # 中证红利 000922 周线——组合超额 vs 红利——若连续跑赢沪深300 但对红利无超额
    # → 说明超额可能只是红利风格 Beta（vs 风格基准 归因污染警示）
    style_beat = 0  # 组合 vs 红利指数 连续超额周数
    style_max = 0
    try:
        div_weeks = d.bs_kline_weekly("000922", 10)
        div_bench = {w["date"][:10]: w["close"] for w in div_weeks}
        for i in range(1, len(weekly)):
            prev_t, cur_t = weekly[i - 1]["total"], weekly[i]["total"]
            if prev_t <= 0:
                continue
            port_ret = (cur_t - prev_t) / prev_t
            cur_date = _week_last_day(weekly[i]["week"])
            prev_date = _week_last_day(weekly[i - 1]["week"])
            dc, dp = div_bench.get(cur_date), div_bench.get(prev_date)
            if not dc or not dp or dp <= 0:
                continue
            div_ret = (dc - dp) / dp
            style_beat = style_beat + 1 if port_ret > div_ret else 0
            style_max = max(style_max, style_beat)
    except Exception:
        style_max = -1  # 红利数据不可用——标注（不阻塞判定）
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
    style_txt = ""
    if style_max >= 0:
        style_txt = (
            f"——风格对照：vs 中证红利连续跑赢 {style_max} 周"
            + (
                "⚠️ 对红利无持续超额——超额可能含红利风格 Beta（观测提示）"
                if style_max < max_wins
                else "（对红利亦有超额——风格 Beta 嫌疑低）"
            )
        )
    if max_wins >= CONSECUTIVE_WEEKS:
        # 整改①：4 周跑赢 + Alpha 必须为正（归因数据不足时保留原判定——标注待确认）
        # 三态：alpha_positive 可为 True/False/None（数据不足）——避开 is/== 字面量比较
        alpha_ok = att.get("alpha_positive") is not None and att["alpha_positive"]
        if alpha_ok == False:  # 显式三态判断（True/False/None 数据不足）
            return {
                "passed": False,
                "reason": (
                    f"连续 {max_wins} 周跑赢沪深300——但 Alpha 为负"
                    f"（{att.get('attribution_note', '')}）——疑似 Beta 驱动——判定不通过"
                ),
                "days": days,
                "weeks_beat": max_wins,
                "alpha_positive": False,
                "attribution_note": att.get("attribution_note", ""),
            }
        alpha_txt = (
            "——Alpha 为正（策略贡献确认）"
            if alpha_ok
            else "——归因数据不足（Alpha 待确认——红线⑤）"
        )
        return {
            "passed": True,
            "reason": f"连续 {max_wins} 周跑赢沪深300（净值序列实证）{alpha_txt}",
            "days": days,
            "weeks_beat": max_wins,
            "alpha_positive": att.get("alpha_positive"),
            "attribution_note": att.get("attribution_note", ""),
        }
    return {
        "passed": False,
        "reason": f"运行 {days} 天——最高连续跑赢 {max_wins} 周（需 {CONSECUTIVE_WEEKS} 周——满 {MAX_DAYS} 天也通过）{style_txt}",
        "days": days,
        "weeks_beat": max_wins,
        "style_beat": style_max,
        "alpha_positive": att.get("alpha_positive"),
        "attribution_note": att.get("attribution_note", ""),
    }


def _week_last_day(week_key: str) -> str:
    """ISO 周键（2026-W33）→ 该周最后一天（周日）"""
    try:
        y, w = int(week_key[:4]), int(week_key.split("W")[1])
        import datetime as dt

        # ISO 周: 周一为第 1 天——周日 = 周一 + 6 天
        jan4 = dt.date(y, 1, 4)
        monday = (
            jan4
            - dt.timedelta(days=jan4.isocalendar()[2] - 1)
            + dt.timedelta(weeks=w - 1)
        )
        return (monday + dt.timedelta(days=6)).isoformat()
    except (ValueError, IndexError):
        return ""


def _plot_ascii(series: list[dict[str, Any]], width: int = 60) -> str:
    """ASCII 净值曲线（2026-08-15——可视化进度——纯 stdlib 无依赖）

    series: [{date, total}]——横向折线（归一化到固定高度）
    """
    if len(series) < 2:
        return f"  净值点不足（{len(series)} 个——每天 9:00 晨报自动记录）"
    totals = [s["total"] for s in series]
    lo, hi = min(totals), max(totals)
    span = hi - lo
    if span <= 0:
        span = hi * 0.01 or 1.0
    height = 10
    # 归一化到网格
    grid: list[list[str]] = [[" " for _ in range(width)] for _ in range(height)]
    n = len(totals)
    step = max(1, (n - 1) // (width - 1))
    pts = [(i, totals[i]) for i in range(0, n, step)][:width]
    for x, (i, t) in enumerate(pts):
        try:
            y = int((t - lo) / span * (height - 1))
        except (ZeroDivisionError, ValueError):
            y = height // 2
        y = max(0, min(height - 1, y))
        grid[height - 1 - y][x] = "*"
    lines = ["".join(row) for row in grid]
    out = [f"  净值: {lo:,.0f} → {hi:,.0f}（{n} 个交易日）"]
    for i, row in enumerate(lines):
        label = f"{hi - (hi - lo) * i / height:,.0f}".rjust(9)
        out.append(f"{label} |{row}|")
    out.append(" " * 10 + "+" + "-" * width + "+")
    # 日期标注（首/中/尾）
    dates = [s["date"] for s in series]
    first, mid, last = dates[0], dates[len(dates) // 2], dates[-1]
    out.append(f"   {first:<{width // 3}}{mid:<{width // 3}}{last}")
    return "\n".join(out)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--plot":
        p = pf.Portfolio()
        print(_plot_ascii(p.equity_series()))
    else:
        print(check())
