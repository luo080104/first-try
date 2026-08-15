"""书规则验证器（2026-08-15——用户要求：每个书观点先验证数据支撑再落地）

验证对象（书个股方法——可量化项）：
  A 打五折（L3486：PE < 合理 PE/2 买入）vs 普通低估 vs 无条件
  M 66% 分段（L486：百分位 <66% 不动——66-80/80+ 分级）
  C 底线思维（L2684：极端 PE 低 + 股息保障）
方法：龙头池 10 只 × 10 年（数据边界定案：2016 起——制度可比性）——按条件分组——后 12 月相对收益胜率/均值对比
数据：baostock 周线（价格）+ baostock 估值日线（PE——asof 对齐周线——2026-08-15 修复索引错位）
局限标注：财务类规则（F/H）需历史财务——用当前特征×历史收益近似（第二轮）
运行：python -m tools.strategy_engine.verify_book_rules
"""

from __future__ import annotations

import bisect
import os
import sys
from statistics import mean
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tools.strategy_engine import data as d

YEARS = 10  # 数据边界定案（2026-08-15：10 年——2016 起——覆盖 1.5 轮牛熊）

POOL = [
    "600036",
    "600519",
    "601318",
    "601088",
    "600900",
    "600028",
    "601857",
    "601398",
    "600030",
    "000651",
]


_BENCH: list[float] = []  # 沪深300 周线（相对收益基准——防市场状态污染）


def _load_bench() -> list[float]:
    """基准（沪深300——10 年周线——baostock 主源，失败退 akshare）"""
    global _BENCH
    if not _BENCH:
        wk = d.bs_kline_weekly("000300", YEARS)
        if not wk:
            from tools.strategy_engine import backtest as bt

            wk = bt.load_weekly("sh000300", YEARS)
        _BENCH = [w["close"] for w in wk]
    return _BENCH


def _align_weekly(
    weeks: list[dict[str, Any]], hist: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """估值日线 → 周线对齐（每行附该周最新 PE——asof：date ≤ 周线日期的最近估值）

    修复 2026-08-15：原实现 hist[i] 日线索引直接对应 closes[i] 周线索引——错位
    """
    dates = [h["date"] for h in hist]
    pes = [h.get("pe") for h in hist]
    out = []
    for w in weeks:
        idx = bisect.bisect_right(dates, w["date"]) - 1
        out.append(
            {
                "date": w["date"],
                "close": w["close"],
                "pe": pes[idx] if idx >= 0 else None,
            }
        )
    return out


def _fwd_return(closes: list[float], i: int, weeks: int = 52) -> float | None:
    """第 i 周买入——weeks 周后【相对收益】%（个股 − 沪深300 同期——防市场状态污染）"""
    bench = _load_bench()
    if i + weeks >= len(closes) or i + weeks >= len(bench) or i >= len(bench):
        return None
    ret = closes[i + weeks] / closes[i] - 1
    bref = bench[i + weeks] / bench[i] - 1
    return (ret - bref) * 100


def verify_valuation_rules() -> dict[str, Any]:
    """A/M/C 验证（全历史 PE——数据可信）"""
    stats = {
        "A_打五折": {"n": 0, "wins": 0, "rets": []},
        "A_普通低估": {"n": 0, "wins": 0, "rets": []},
        "A_无条件": {"n": 0, "wins": 0, "rets": []},
        "M_<66": {"n": 0, "wins": 0, "rets": []},
        "M_66-80": {"n": 0, "wins": 0, "rets": []},
        "M_>80": {"n": 0, "wins": 0, "rets": []},
        "C_极端低估": {"n": 0, "wins": 0, "rets": []},
        "C_普通低估": {"n": 0, "wins": 0, "rets": []},
    }
    for code in POOL:
        try:
            # 价格：10 年周线（baostock 主源）——PE：baostock 估值日线（asof 对齐）
            weeks = d.bs_kline_weekly(code, YEARS)
            hist = d.bs_pe_pb_history(code, YEARS)
        except Exception:
            continue
        if not weeks or not hist or len(weeks) < 120:
            continue
        # 对齐：估值日线 asof → 周线（修复：原 hist[i] 日线索引与 closes[i] 周线索引错位）
        aligned = _align_weekly(weeks, hist)
        closes = [w["close"] for w in aligned]
        pes = [w["pe"] for w in aligned if w.get("pe")]
        if not pes:
            continue
        median = sorted(pes)[len(pes) // 2]  # 合理 PE ≈ 历史中位数（书 B：长期平均 PE）
        n = len(aligned)
        for i in range(30, n - 52):
            pe = aligned[i].get("pe") or 0
            if pe <= 0:
                continue
            pct = sum(1 for p in pes if p < pe) / len(pes) * 100
            r = _fwd_return(closes, i)
            if r is None:
                continue
            # A：打五折 vs 普通低估 vs 无条件
            if pe < median / 2:
                stats["A_打五折"]["n"] += 1
                stats["A_打五折"]["rets"].append(r)
                if r > 0:
                    stats["A_打五折"]["wins"] += 1
            elif pe < median:
                stats["A_普通低估"]["n"] += 1
                stats["A_普通低估"]["rets"].append(r)
                if r > 0:
                    stats["A_普通低估"]["wins"] += 1
            stats["A_无条件"]["n"] += 1
            stats["A_无条件"]["rets"].append(r)
            if r > 0:
                stats["A_无条件"]["wins"] += 1
            # M：66% 分段
            group = "M_<66" if pct < 66 else ("M_66-80" if pct < 80 else "M_>80")
            stats[group]["n"] += 1
            stats[group]["rets"].append(r)
            if r > 0:
                stats[group]["wins"] += 1
            # C：极端低估（PE 百分位 <10）vs 普通（10-40）
            if pct < 10:
                stats["C_极端低估"]["n"] += 1
                stats["C_极端低估"]["rets"].append(r)
                if r > 0:
                    stats["C_极端低估"]["wins"] += 1
            elif pct < 40:
                stats["C_普通低估"]["n"] += 1
                stats["C_普通低估"]["rets"].append(r)
                if r > 0:
                    stats["C_普通低估"]["wins"] += 1
    out = {}
    for name, s in stats.items():
        if s["n"]:
            out[name] = {
                "n": s["n"],
                "win_rate": round(s["wins"] / s["n"] * 100, 1),
                "avg_ret": round(mean(s["rets"]), 2),
            }
        else:
            out[name] = {"n": 0, "win_rate": 0.0, "avg_ret": 0.0}
    return out


def main():
    print(f"书规则验证（10 只 × {YEARS} 年——后 12 月相对收益分组对比）")
    print("=" * 56)
    r = verify_valuation_rules()
    for name, s in r.items():
        print(
            f"  {name:<12} N={s['n']:>5} 胜率 {s['win_rate']:>5}% 均收益 {s['avg_ret']:>6}%"
        )
    print("  --- 第二轮：财务特征 × 近 5 年收益（当前特征近似——方向参考）---")
    r2 = verify_financial_rules()
    for name, s in r2.items():
        print(
            f"  {name:<16} N={s['n']:>3} 胜率 {s['win_rate']:>5}% 均收益 {s['avg_ret']:>6}%"
        )
    print("  --- 第二轮：K 牛熊分境（S2 卖出限定——招行 20 年回测）---")
    r3 = verify_s2_bull_market()
    for name, s in r3.items():
        print(
            f"  {name:<18} 交易 {s['n']:>3} 胜率 {s['win_rate']:>5}% 均收益 {s['avg_ret']:>6}% 回撤 {s['max_dd']:>5}%"
        )


def verify_financial_rules() -> dict[str, Any]:
    """F/H 验证（书 L3399/L2761）：当前财务特征 × 近 5 年收益——42 只全池
    局限标注：当前特征近似历史（财务特征相对稳定——但非精确——方向参考）
    """
    from tools.strategy_engine import fundamentals as fd
    from tools.strategy_engine.core_loop import load_leader_pool

    groups = {
        "F_高ROE低负债": {"n": 0, "wins": 0, "rets": []},
        "F_高ROE高负债(杠杆)": {"n": 0, "wins": 0, "rets": []},
        "F_低ROE": {"n": 0, "wins": 0, "rets": []},
        "H_分红率40-75": {"n": 0, "wins": 0, "rets": []},
        "H_分红率<40": {"n": 0, "wins": 0, "rets": []},
        "H_分红率>75": {"n": 0, "wins": 0, "rets": []},
    }
    for code in load_leader_pool():
        try:
            f = fd.get_fundamentals(code, 10.0)
            k = d.tencent_kline(code, days=260)
        except Exception:
            continue
        if not k or len(k) < 60:
            continue
        closes = [x["close"] for x in k]
        # 近 5 年周线收益（52 周持有）
        r = (closes[-1] / closes[-52] - 1) * 100 if len(closes) > 52 else None
        if r is None:
            continue
        roe = f.get("roe") or 0
        debt = f.get("debt_ratio") or 0
        exempt = f.get("debt_exempt", False)
        payout = f.get("payout_ratio") or 0
        # F 分组（非金融——金融负债天然高不参与杠杆判定）
        if not exempt:
            if roe > 15 and debt < 60:
                g = "F_高ROE低负债"
            elif roe > 15:
                g = "F_高ROE高负债(杠杆)"
            else:
                g = "F_低ROE"
            groups[g]["n"] += 1
            groups[g]["rets"].append(r)
            if r > 0:
                groups[g]["wins"] += 1
        # H 分组（有分红率数据才判）
        if payout > 0:
            g2 = (
                "H_分红率40-75"
                if 40 <= payout <= 75
                else ("H_分红率<40" if payout < 40 else "H_分红率>75")
            )
            groups[g2]["n"] += 1
            groups[g2]["rets"].append(r)
            if r > 0:
                groups[g2]["wins"] += 1
    out = {}
    for name, s in groups.items():
        if s["n"]:
            out[name] = {
                "n": s["n"],
                "win_rate": round(s["wins"] / s["n"] * 100, 1),
                "avg_ret": round(mean(s["rets"]), 2),
            }
        else:
            out[name] = {"n": 0, "win_rate": 0.0, "avg_ret": 0.0}
    return out


def verify_s2_bull_market() -> dict[str, Any]:
    """K 验证（书 L290-300：牛市布林上轨卖出无效——S2 限定）——回测对比
    沪深300 {YEARS} 年——机械上轨卖出 vs 牛市（周 MA20 上升）不卖
    """
    from tools.strategy_engine import backtest as bt
    from tools.strategy_engine import indicators as ind

    weeks = bt.load_weekly("600036", YEARS)

    def sell_mechanical(hist):
        b = ind.bollinger(hist, 20, 2)
        return bool(b["upper"] and hist[-1] > b["upper"])

    def sell_bullaware(hist):
        # 书：牛市（周布林中轨上升趋势）上轨不是好卖出指标——不卖；熊市/震荡才卖
        b = ind.bollinger(hist, 20, 2)
        if not (b["upper"] and hist[-1] > b["upper"]):
            return False
        if len(hist) >= 22:
            # 审查 R7 修复：中轨上升 = MA20 本周 > 上周（趋势方向）——
            # 原 hist[-21] < ma 是"价格穿越 MA"（熊市反弹也成立）——与书"中轨上升趋势"不符
            ma_now = sum(hist[-20:]) / 20
            ma_prev = sum(hist[-21:-1]) / 20
            if ma_now > ma_prev:
                return False  # 中轨上升（牛市）——不卖
        return True

    buy = lambda h: bt.make_buy("b+r")(h)
    r1 = bt.run_backtest(weeks, buy, sell_mechanical)
    r2 = bt.run_backtest(weeks, buy, sell_bullaware)
    out = {}
    for seg in ("训练", "验证"):
        m1, m2 = r1[seg], r2[seg]
        out[f"K_机械卖出_{seg}"] = {
            "n": m1["trades"],
            "win_rate": m1["win_rate"],
            "avg_ret": m1["avg_ret"],
            "max_dd": m1["max_dd"],
        }
        out[f"K_牛熊限定_{seg}"] = {
            "n": m2["trades"],
            "win_rate": m2["win_rate"],
            "avg_ret": m2["avg_ret"],
            "max_dd": m2["max_dd"],
        }
    return out


if __name__ == "__main__":
    main()
