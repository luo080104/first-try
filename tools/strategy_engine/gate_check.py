# -*- coding: utf-8 -*-
"""虚拟盘通过判定（gate_check.py——v2——F5b：90 天保底废除=观察期）

需求 v1.1 定案：连续 N 周跑赢基准（N=4 默认）——基准沪深300 默认
- 数据：portfolio 事件日志（Q11——buy_date 记录）
- 判定：有持仓 → 周度对比（组合净值 vs 沪深300）——4 周连续超额 → 通过
- F5b（2026-08-17 用户拍板）：满 90 天=观察期——不自动通过——须真实超额
- 附加闸门：累计超额≥10% + Alpha 非负 + 二项符号检验 p<0.05（甲方 Q4）
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
MAX_DAYS = 90  # 观察期（F5b 2026-08-17：保底条款废除——满 90 天不自动通过）
EXCESS_TARGET = 0.10  # 超额目标 ≥10%（2026-08-17 用户拍板：跑赢不够——要 10% 超额）


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
    _skipped = 0
    for pt in curve:
        d = pt.get("date", "")[:10]
        if not d:
            continue
        # 甲方 Q6（2026-08-17）：只统计真实行情点——fallback/missing 判定时不计
        if pt.get("data_state") not in (None, "real"):
            _skipped += 1
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
    if _skipped:
        print(f"[gate_check] 跳过 {_skipped} 个失真净值点（非 real 态——判定不计）")
    return [{"week": k, "total": v} for k, v in sorted(weekly.items())]


def significance(weekly: list[dict[str, Any]], bench: dict[str, float], n_boot: int = 2000) -> dict[str, Any]:
    """显著性检验（2026-08-17 甲方 Q4 应询——'硬币也能连续4周跑赢'）

    主检验：二项符号检验（精确）——正超额周数 k vs H0：胜率=50%。
    p = P(X>=k | X~Bin(n, 0.5))——胜率显著高于随机=连续跑赢非运气。
    辅检验：Bootstrap 置换（保留符号分布——与二项互补）。
    """
    import math
    import random

    pairs = []
    for i in range(1, len(weekly)):
        prev_t, cur_t = weekly[i - 1]["total"], weekly[i]["total"]
        if prev_t <= 0:
            continue
        port_ret = (cur_t - prev_t) / prev_t
        cur_date = _week_last_day(weekly[i]["week"])
        prev_date = _week_last_day(weekly[i - 1]["week"])
        bc, bp = _bench_get(bench, cur_date), _bench_get(bench, prev_date)
        if not bc or not bp or bp <= 0:
            continue
        bench_ret = (bc - bp) / bp
        pairs.append(port_ret - bench_ret)  # 超额收益序列
    n = len(pairs)
    if n < 6:
        return {"n_weeks": n, "p_value": None, "significant": None,
                "note": "周样本<6——显著性不可判（等积累）"}

    k = sum(1 for x in pairs if x > 0)  # 正超额周数
    # 二项符号检验（单侧：胜率>50%）——精确尾概率
    p_binom = 0.0
    for j in range(k, n + 1):
        p_binom += math.comb(n, j) * (0.5 ** n)
    p_binom = min(p_binom, 1.0)

    # Bootstrap 置换（辅助——连续跑赢长度）
    obs_max_streak = _max_streak(pairs)
    rng = random.Random(42)
    ge_streak = 0
    for _ in range(n_boot):
        shuffled = pairs[:]
        rng.shuffle(shuffled)
        if _max_streak(shuffled) >= obs_max_streak:
            ge_streak += 1
    p_streak = ge_streak / n_boot

    return {
        "n_weeks": n,
        "obs_win_weeks": k,
        "win_rate": round(k / n * 100, 1),
        "obs_max_streak": obs_max_streak,
        "p_binom": round(p_binom, 4),  # 主检验：胜率显著性（精确二项）
        "p_streak": round(p_streak, 4),  # 辅检验：连赢长度（置换）
        "significant": p_binom < 0.05,
        "note": "p_binom<0.05=胜率显著>50%（二项符号检验——硬币序列 p≈0.5 不显著）",
    }


def _max_streak(seq: list[float]) -> int:
    """连续正收益最大长度（超额序列中 >0 视为'跑赢'）"""
    best = cur = 0
    for x in seq:
        if x > 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


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
    # F5b 落地（2026-08-17 审核+用户拍板 A+10%）：90 天保底条款废除——
    # 满 90 天=观察期（不自动通过——继续积累）——通过必须真实超额
    if days >= MAX_DAYS:
        return {
            "passed": False,
            "reason": (
                f"观察期满 {MAX_DAYS} 天（{days} 天）——F5b：保底条款废除——"
                "不自动通过——继续观察至真实超额（4 周跑赢+Alpha>0+超额≥10%）"
            ),
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
    # 沪深300 周线（动态窗口——盲审修复：10 周固定会截断早期跑赢周——取组合周数+2 冗余）
    bench_weeks = d.bs_kline_weekly("000300", max(10, len(weekly) + 2))
    bench = {w["date"][:10]: w["close"] for w in bench_weeks}
    # 风格对照（2026-08-16 架构师 P1 落地——观测先行——判定不变）：
    # 中证红利 000922 周线——组合超额 vs 红利——若连续跑赢沪深300 但对红利无超额
    # → 说明超额可能只是红利风格 Beta（vs 风格基准 归因污染警示）
    style_beat = 0  # 组合 vs 红利指数 连续超额周数
    style_max = 0
    try:
        div_weeks = d.bs_kline_weekly("000922", max(10, len(weekly) + 2))
        div_bench = {w["date"][:10]: w["close"] for w in div_weeks}
        for i in range(1, len(weekly)):
            prev_t, cur_t = weekly[i - 1]["total"], weekly[i]["total"]
            if prev_t <= 0:
                continue
            port_ret = (cur_t - prev_t) / prev_t
            cur_date = _week_last_day(weekly[i]["week"])
            prev_date = _week_last_day(weekly[i - 1]["week"])
            dc, dp = _bench_get(div_bench, cur_date), _bench_get(div_bench, prev_date)
            if not dc or not dp or dp <= 0:
                continue
            div_ret = (dc - dp) / dp
            style_beat = style_beat + 1 if port_ret > div_ret else 0
            style_max = max(style_max, style_beat)
    except Exception:
        style_max = -1  # 红利数据不可用——标注（不阻塞判定）
    # 逐周对比：组合周收益 vs 基准周收益（F5b 加累计超额——目标 ≥10%）
    wins = 0
    max_wins = 0
    excess_sum = 0.0  # 建仓以来累计超额收益（组合累计 - 基准累计——F5b 2026-08-17）
    n_excess = 0
    for i in range(1, len(weekly)):
        prev_t, cur_t = weekly[i - 1]["total"], weekly[i]["total"]
        if prev_t <= 0:
            continue
        port_ret = (cur_t - prev_t) / prev_t
        # 基准同期收益（用该周最后一天近似）
        cur_date = _week_last_day(weekly[i]["week"])
        prev_date = _week_last_day(weekly[i - 1]["week"])
        bc, bp = _bench_get(bench, cur_date), _bench_get(bench, prev_date)
        if not bc or not bp or bp <= 0:
            continue
        bench_ret = (bc - bp) / bp
        # 累计超额（几何累计近似：逐周相加——口径标注 Q11 可校准）
        excess_sum += port_ret - bench_ret
        n_excess += 1
        wins = wins + 1 if port_ret > bench_ret else 0
        max_wins = max(max_wins, wins)
    style_txt = ""
    if style_max >= 0:
        style_txt = f"——风格对照：vs 中证红利连续跑赢 {style_max} 周" + (
            "⚠️ 对红利无持续超额——超额可能含红利风格 Beta（观测提示）"
            if style_max < max_wins
            else "（对红利亦有超额——风格 Beta 嫌疑低）"
        )
    if max_wins >= CONSECUTIVE_WEEKS:
        # F5b（2026-08-17 用户拍板 A+10%）：4 周跑赢 **且** 累计超额 ≥10% 双条件
        excess_ok = excess_sum >= EXCESS_TARGET
        if not excess_ok:
            return {
                "passed": False,
                "reason": (
                    f"连续 {max_wins} 周跑赢沪深300——但累计超额 {excess_sum * 100:.1f}%"
                    f" < 目标 {EXCESS_TARGET * 100:.0f}%（F5b 用户拍板）——继续观察"
                ),
                "days": days,
                "weeks_beat": max_wins,
                "alpha_positive": att.get("alpha_positive"),
                "attribution_note": att.get("attribution_note", ""),
            }
        # 整改①：4 周跑赢 + Alpha 必须为正（归因数据不足时保留原判定——标注待确认）
        # 盲审修复（2026-08-17）：三态显式判断——None=数据不足≠负（原实现塌缩为 False 误阻断）
        alpha_val = att.get("alpha_positive")
        if alpha_val == False:  # 显式为负——只有这一种情况阻断（None=数据不足不阻断）
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
        alpha_ok = alpha_val == True
        alpha_txt = (
            "——Alpha 为正（策略贡献确认）"
            if alpha_ok
            else "——归因数据不足（Alpha 待确认——红线⑤——不阻断）"
        )
        # 甲方 Q4（2026-08-17）：显著性检验——连续跑赢须异于随机（硬币检验）
        sig = significance(weekly, bench)
        if sig.get("significant") == False:  # p>=0.05——运气不能排除
            return {
                "passed": False,
                "reason": (
                    f"连续 {max_wins} 周跑赢 + 超额 {excess_sum * 100:.1f}%≥10%——但显著性检验 p="
                    f"{sig['p_binom']}≥0.05（二项符号检验——胜率 {sig.get('win_rate')}%——可能只是运气——甲方 Q4）"
                ),
                "days": days,
                "weeks_beat": max_wins,
                "alpha_positive": att.get("alpha_positive"),
                "attribution_note": att.get("attribution_note", ""),
                "significance": sig,
            }
        sig_txt = (
            f"——显著性 p={sig.get('p_binom')}<0.05（胜率 {sig.get('win_rate')}%——非运气）"
            if sig.get("p_binom") is not None
            else "——显著性待样本（周数不足）"
        )
        return {
            "passed": True,
            "reason": f"连续 {max_wins} 周跑赢沪深300 + 累计超额 {excess_sum * 100:.1f}%≥10%（F5b）{alpha_txt}{sig_txt}",
            "days": days,
            "weeks_beat": max_wins,
            "alpha_positive": att.get("alpha_positive"),
            "attribution_note": att.get("attribution_note", ""),
            "significance": sig,
        }
    return {
        "passed": False,
        "reason": f"运行 {days} 天——最高连续跑赢 {max_wins} 周（需 {CONSECUTIVE_WEEKS} 周——F5b：满 90 天不自动通过——观察期继续）{style_txt}",
        "days": days,
        "weeks_beat": max_wins,
        "style_beat": style_max,
        "alpha_positive": att.get("alpha_positive"),
        "attribution_note": att.get("attribution_note", ""),
    }


def _bench_get(bench: dict[str, float], date_key: str) -> float | None:
    """基准查表——精确命中失败时向前找最近交易日（周五休市兜底——盲审修复 2026-08-17）"""
    if not date_key:
        return None
    import datetime as dt

    d = bench.get(date_key)
    if d is not None:
        return d
    try:
        cur = dt.date.fromisoformat(date_key)
    except ValueError:
        return None
    for back in range(1, 5):  # 最多回退 4 天（周一周二也能找到上周五）
        d = bench.get((cur - dt.timedelta(days=back)).isoformat())
        if d is not None:
            return d
    return None


def _week_last_day(week_key: str) -> str:
    """ISO 周键（2026-W33）→ 当周最后交易日（周五——A 股交易日历近似）

    2026-08-17 盲审修复：原实现返回周日——与 baostock 周线日期（周五）
    永不匹配——'4 周跑赢'判定不可达（wins 恒 0）。周五若休市（节假日），
    查表时用'前一个可用交易日'兜底（_nearest_bench）。
    """
    try:
        y, w = int(week_key[:4]), int(week_key.split("W")[1])
        import datetime as dt

        # ISO 周: 周一为第 1 天——周五 = 周一 + 4 天
        jan4 = dt.date(y, 1, 4)
        monday = (
            jan4
            - dt.timedelta(days=jan4.isocalendar()[2] - 1)
            + dt.timedelta(weeks=w - 1)
        )
        friday = monday + dt.timedelta(days=4)
        return friday.isoformat()
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
