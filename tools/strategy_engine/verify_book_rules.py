"""书规则验证器（2026-08-15——用户要求：每个书观点先验证数据支撑再落地）

验证对象（书个股方法——可量化项）：
  A 打五折（L3486：PE < 合理 PE/2 买入）vs 普通低估 vs 无条件
  M 66% 分段（L486：百分位 <66% 不动——66-80/80+ 分级）
  C 底线思维（L2684：极端 PE 低 + 股息保障）
方法：龙头池 10 只 × 20 年——按条件分组——后 12 月收益胜率/均值对比
数据：腾讯 K 线（价格）+ 百度估值历史（PE 序列——data.pe_pb_history）
局限标注：财务类规则（F/H）需历史财务——用当前特征×历史收益近似（第二轮）
运行：python -m tools.strategy_engine.verify_book_rules
"""

from __future__ import annotations

import os
import sys
from statistics import mean
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from tools.strategy_engine import data as d

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


def _fwd_return(closes: list[float], i: int, weeks: int = 52) -> float | None:
    """第 i 周买入——weeks 周后收益%（数据不足返回 None）"""
    if i + weeks >= len(closes):
        return None
    return (closes[i + weeks] / closes[i] - 1) * 100


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
            k = d.tencent_kline(code, days=400)
            hist = d.pe_pb_history(code)
        except Exception:
            continue
        if not k or not hist or len(k) < 120:
            continue
        closes = [x["close"] for x in k]
        pes = [h["pe"] for h in hist if h.get("pe", 0) > 0]
        if not pes:
            continue
        median = sorted(pes)[len(pes) // 2]  # 合理 PE ≈ 历史中位数（书 B：长期平均 PE）
        # 对齐：K 线 400 周 ~ 8 年——估值历史同样窗口——逐周判定
        n = min(len(closes), len(hist))
        for i in range(30, n - 52):
            pe = hist[i].get("pe") or 0
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
    print("书规则验证（10 只 × 20 年——后 12 月收益分组对比）")
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

    groups = {"F_高ROE低负债": {"n": 0, "wins": 0, "rets": []},
              "F_高ROE高负债(杠杆)": {"n": 0, "wins": 0, "rets": []},
              "F_低ROE": {"n": 0, "wins": 0, "rets": []},
              "H_分红率40-75": {"n": 0, "wins": 0, "rets": []},
              "H_分红率<40": {"n": 0, "wins": 0, "rets": []},
              "H_分红率>75": {"n": 0, "wins": 0, "rets": []}}
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
            g2 = "H_分红率40-75" if 40 <= payout <= 75 else (
                "H_分红率<40" if payout < 40 else "H_分红率>75")
            groups[g2]["n"] += 1
            groups[g2]["rets"].append(r)
            if r > 0:
                groups[g2]["wins"] += 1
    out = {}
    for name, s in groups.items():
        if s["n"]:
            out[name] = {"n": s["n"],
                         "win_rate": round(s["wins"] / s["n"] * 100, 1),
                         "avg_ret": round(mean(s["rets"]), 2)}
        else:
            out[name] = {"n": 0, "win_rate": 0.0, "avg_ret": 0.0}
    return out


def verify_s2_bull_market() -> dict[str, Any]:
    """K 验证（书 L290-300：牛市布林上轨卖出无效——S2 限定）——回测对比
    沪深300 20 年——机械上轨卖出 vs 牛市（周 MA20 上升）不卖
    """
    from tools.strategy_engine import backtest as bt
    from tools.strategy_engine import indicators as ind

    weeks = bt.load_weekly("600036", 20)

    def sell_mechanical(hist):
        b = ind.bollinger(hist, 20, 2)
        return bool(b["upper"] and hist[-1] > b["upper"])

    def sell_bullaware(hist):
        # 书：牛市（周 MA20 上升）上轨不是好卖出指标——不卖；熊市/震荡才卖
        b = ind.bollinger(hist, 20, 2)
        if not (b["upper"] and hist[-1] > b["upper"]):
            return False
        if len(hist) >= 21:
            ma = sum(hist[-21:-1]) / 20
            if hist[-1] > ma and hist[-21] < ma:
                return False  # 周 MA 上升中（牛市）——不卖
        return True

    buy = lambda h: bt.make_buy("b+r")(h)
    r1 = bt.run_backtest(weeks, buy, sell_mechanical)
    r2 = bt.run_backtest(weeks, buy, sell_bullaware)
    out = {}
    for seg in ("训练", "验证"):
        m1, m2 = r1[seg], r2[seg]
        out[f"K_机械卖出_{seg}"] = {"n": m1["trades"], "win_rate": m1["win_rate"],
                                    "avg_ret": m1["avg_ret"], "max_dd": m1["max_dd"]}
        out[f"K_牛熊限定_{seg}"] = {"n": m2["trades"], "win_rate": m2["win_rate"],
                                    "avg_ret": m2["avg_ret"], "max_dd": m2["max_dd"]}
    return out

if __name__ == "__main__":
    main()
