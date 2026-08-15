# -*- coding: utf-8 -*-
"""回测框架（backtest.py——战术层验证——方案红线：回测达标才启用）

红线（Vibe-Trading 三条——直接抄）：
- 纯本地数据｜不碰真钱｜严格防未来函数（T 日收盘决策、T+1 开盘成交）
- 强制交易成本（佣金万 2.5 + 卖出印花税 0.05%）

方法：walk-forward（2016-2020 训练 / 2021-2025 验证——样本外）——分段报告
数据边界（2026-08-15 定案）：10 年（2016 起——制度可比性——覆盖 1.5 轮牛熊）
指标：交易数/胜率/平均收益/总收益/最大回撤/卡玛比率

策略：信号函数注入（B3/S2/S3——signals.py）——买入=信号触发 T+1 开盘——
卖出=S2 上轨 / 持有超 52 周强制（周期保护）——v0 简化（Q11 校准）

运行：python -m tools.strategy_engine.backtest --code 600036
"""

from __future__ import annotations

import argparse
from typing import Any, Callable

from tools.strategy_engine import data as d
from tools.strategy_engine import indicators as ind
from tools.strategy_engine import signals as sg  # pyright: ignore

SPLIT_DATE = "2021-01-01"  # walk-forward 分界（训练/验证）
DEFAULT_YEARS = 10  # 数据边界定案（2026-08-15）


def _f(x) -> float:
    """安全浮点转换（数据异常 → 0——不阻塞回测——红线③容错）"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


COMMISSION = 0.00025  # 佣金万 2.5
STAMP_TAX = 0.0005  # 卖出印花税 0.05%
MAX_HOLD_WEEKS = 52  # 周期保护（v0）
LOT = 100  # 一手（A股整手交易）


def _fetch_daily(symbol: str, years: int, retries: int = 2) -> Any:
    """日线多源重试（新浪 → 东财节流——限流/反爬时切换——红线③）"""
    import time

    import akshare as ak

    start = f"{2026 - years}0101"
    for attempt in range(retries + 1):
        try:
            df = ak.stock_zh_a_daily(
                symbol=symbol, start_date=start, end_date="20261231", adjust="qfq"
            )
            if df is not None and "date" in df.columns and len(df) > 100:
                return df
        except Exception:
            pass
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol.replace("sh", "").replace("sz", ""),
                period="daily",
                start_date=start,
                end_date="20261231",
                adjust="qfq",
            )
            if df is not None and "日期" in df.columns and len(df) > 100:
                df = df.rename(
                    columns={
                        "日期": "date",
                        "开盘": "open",
                        "收盘": "close",
                        "最高": "high",
                        "最低": "low",
                        "成交量": "volume",
                    }
                )
                return df
        except Exception:
            pass
        time.sleep(1 + attempt)  # 节流（东财反爬）
    raise RuntimeError(f"多源获取失败: {symbol}（新浪/东财均不可用）")


def load_weekly(code: str, years: int = DEFAULT_YEARS) -> list[dict[str, Any]]:
    """历史周线（baostock 主源 → akshare 多源重试链兜底——红线③）

    10 年窗口（数据边界定案）——baostock 免费无限流（2006 起）——新浪常限流
    """
    # 主源：baostock（P0-1 已接——SQLite 缓存——稳定）
    wk = d.bs_kline_weekly(code, years)
    if len(wk) >= 100:
        return wk
    # 兜底：akshare 日线重采样（多源重试链）
    import os

    # 绕过代理/直连（东财源被反爬拒——腾讯源不封 IP）
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    symbol = (
        code
        if code.startswith(("sh", "sz", "bj"))
        else ("sh" + code if code.startswith("6") else "sz" + code)
    )
    df = _fetch_daily(symbol, years)  # 多源重试链（红线③：数据失误真实风险）
    weeks: list[dict[str, Any]] = []
    cur = None
    for _, row in df.iterrows():
        dstr = str(row["date"])
        if cur is None or dstr[:10] != cur["date"][:10]:
            if cur:
                weeks.append(cur)
            cur = {
                "date": dstr,
                "open": _f(row["open"]),
                "close": _f(row["close"]),
                "high": _f(row["high"]),
                "low": _f(row["low"]),
                "volume": _f(row["volume"]),
            }
        else:
            cur["close"] = _f(row["close"])
            cur["high"] = max(cur["high"], _f(row["high"]))
            cur["low"] = min(cur["low"], _f(row["low"]))
            cur["volume"] += _f(row["volume"])
    if cur:
        weeks.append(cur)
    return weeks


def run_backtest(
    weeks: list[dict[str, Any]],
    buy_fn: Callable[[list[float]], bool],
    sell_fn: Callable[[list[float]], bool],
    split_date: str = SPLIT_DATE,
) -> dict[str, Any]:
    """事件循环回测：信号（T 收盘）→ T+1 开盘成交——分段统计"""
    closes = [w["close"] for w in weeks]
    opens = [w["open"] for w in weeks]
    segments = {"训练": [], "验证": []}
    for i in range(30, len(weeks)):
        seg = "训练" if weeks[i]["date"][:10] < split_date else "验证"
        hist = closes[max(0, i - 250) : i]  # 防未来：只用 T 日及之前
        if buy_fn(hist):
            segments[seg].append({"i": i, "type": "buy"})
        if sell_fn(hist):
            segments[seg].append({"i": i, "type": "sell"})
    out = {}
    for seg, events in segments.items():
        out[seg] = _simulate(weeks, opens, events)
    return out


def _simulate(weeks, opens, events) -> dict[str, Any]:
    """按买卖事件模拟（T+1 开盘成交——含成本）——返回交易统计"""
    trades: list[dict] = []
    pos = None  # {"entry_i": i, "entry_px": p}
    buys = [e for e in events if e["type"] == "buy"]
    sells = [e for e in events if e["type"] == "sell"]
    b_idx, s_idx = 0, 0
    for i in range(30, len(weeks)):
        if pos is None and b_idx < len(buys) and buys[b_idx]["i"] == i:
            px = opens[i] * (1 + COMMISSION)
            pos = {"entry_i": i, "entry_px": px}
            b_idx += 1
        elif pos is not None:
            exit_sig = s_idx < len(sells) and sells[s_idx]["i"] == i
            over_hold = i - pos["entry_i"] >= MAX_HOLD_WEEKS
            if exit_sig or over_hold:
                px = opens[i] * (1 - COMMISSION - STAMP_TAX)
                ret = (px - pos["entry_px"]) / pos["entry_px"] * 100
                trades.append(
                    {
                        "entry": pos["entry_px"],
                        "exit": px,
                        "ret_pct": round(ret, 2),
                        "weeks": i - pos["entry_i"],
                        "reason": "S2/估值" if exit_sig else "周期保护",
                    }
                )
                pos = None
                if exit_sig:
                    s_idx += 1
    if not trades:
        return {
            "trades": 0,
            "win_rate": 0.0,
            "avg_ret": 0.0,
            "total_ret": 0.0,
            "max_dd": 0.0,
            "calmar": 0.0,
        }
    rets = [t["ret_pct"] for t in trades]
    wins = sum(1 for r in rets if r > 0)
    total = 1.0
    peak = 1.0
    max_dd = 0.0
    for r in rets:
        total *= 1 + r / 100
        peak = max(peak, total)
        max_dd = max(max_dd, (peak - total) / peak * 100)
    avg = sum(rets) / len(rets)
    return {
        "trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_ret": round(avg, 2),
        "total_ret": round((total - 1) * 100, 1),
        "max_dd": round(max_dd, 1),
        "calmar": round(avg * len(trades) / max_dd, 2) if max_dd > 0 else 0.0,
    }


def make_buy(variant):
    """B3 变体工厂（网格调参——三重/两重/放宽——回测工具）"""

    def buy(hist):
        b = ind.bollinger(hist, 20, 2)
        r = ind.rsi(hist, 6)
        td = ind.td_sequential(hist)
        lower = bool(b["lower"] and hist[-1] <= b["lower"])
        rsi30 = r is not None and r < 30
        rsi40 = r is not None and r < 40
        td9 = td.get("setup") == "buy" and td.get("completed")
        return {
            "b+r+t": lower and rsi30 and td9,
            "b+r": lower and rsi30,
            "r+t": rsi30 and td9,
            "b+t": lower and td9,
            "b+r40+t": lower and rsi40 and td9,
        }[variant]

    return buy


POOL_DEFAULT = [
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


SELL_VARIANTS: dict[str, Any] = {
    "A_书式S2上轨": lambda h: sg.s2_weekly_upper_exit(h)["signal"],
    "B_MA交叉": lambda h: sg.ma_cross_exit(h)["signal"],
    "C_MA拐点确认": lambda h: sg.ma_trend_confirm_exit(h)["signal"],
}


def run_pool(
    codes: list[str],
    years: int = DEFAULT_YEARS,
    variants: tuple[str, ...] = ("b+r+t", "b+r"),
    sell_variants: tuple[str, ...] = ("A_书式S2上轨",),
) -> dict:
    """多股聚合回测：每只 load_weekly+run_backtest——按段聚合交易（N 提升到可统计）

    sell_variants：卖出变体对比（A 书式/B MA交叉/C MA拐点——候选进回测池——红线）
    """
    import time

    agg = {seg: {} for seg in ("训练", "验证")}
    for code in codes:
        try:
            weeks = load_weekly(code, years)
        except Exception as e:
            print(f"  {code} 数据失败: {str(e)[:60]}")
            continue
        for v in variants:
            for sv in sell_variants:
                key = f"{v}+{sv}"
                res = run_backtest(weeks, make_buy(v), SELL_VARIANTS[sv])
                for seg, m in res.items():
                    a = agg[seg].setdefault(key, {"n": 0, "wins": 0, "sum": 0.0})
                    a["n"] += m["trades"]
                    a["wins"] += m["trades"] * m["win_rate"] / 100
                    a["sum"] += m["avg_ret"] * m["trades"]
        time.sleep(1.5)  # 节流（新浪限流——红线③）
    out = {}
    for seg, vstats in agg.items():
        out[seg] = {}
        for v, a in vstats.items():
            wr = round(a["wins"] / a["n"] * 100, 1) if a["n"] else 0.0
            avg = round(a["sum"] / a["n"], 2) if a["n"] else 0.0
            out[seg][v] = {"n": a["n"], "win_rate": wr, "avg_ret": avg}
    return out


def main():
    ap = argparse.ArgumentParser(description="观复战术层回测（walk-forward）")
    ap.add_argument("--code", default="600036", help="标的（默认招行——个股——指数二期）")
    ap.add_argument("--years", type=int, default=DEFAULT_YEARS)
    ap.add_argument(
        "--pool",
        nargs="*",
        default=None,
        help="聚合回测（龙头池代码列表——不传用默认 10 只）",
    )
    ap.add_argument(
        "--sells",
        nargs="*",
        default=None,
        help="卖出变体对比（A_书式S2上轨 / B_MA交叉 / C_MA拐点确认——默认只 A）",
    )
    args = ap.parse_args()
    if args.pool is not None:
        codes = args.pool or POOL_DEFAULT
        sells: tuple[str, ...] = (
            tuple(args.sells) if args.sells else ("A_书式S2上轨",)
        )
        print(
            f"聚合回测 {len(codes)} 只 × {args.years} 年（买入: b+r 两重——卖出: {sells}）"
        )
        agg = run_pool(codes, args.years, variants=("b+r",), sell_variants=sells)
        for seg, vstats in agg.items():
            print(f"\n【{seg}段】")
            for v, m in vstats.items():
                print(
                    f"  {v}: N={m['n']} 笔 | 胜率 {m['win_rate']}% | 均收益 {m['avg_ret']}%"
                )
        return
    weeks = load_weekly(args.code, args.years)
    print(
        f"加载 {len(weeks)} 根周线（{weeks[0]['date'][:10]} → {weeks[-1]['date'][:10]}）"
    )
    buy = lambda hist: sg.b3_triple_confirm(hist)["signal"]
    sell = lambda hist: sg.s2_weekly_upper_exit(hist)["signal"]
    res = run_backtest(weeks, buy, sell)
    for seg, m in res.items():
        print(
            f"\n【{seg}段】{SPLIT_DATE} 分界——交易 {m['trades']} 笔 | "
            f"胜率 {m['win_rate']}% | 均收益 {m['avg_ret']}% | "
            f"累计 {m['total_ret']}% | 最大回撤 {m['max_dd']}% | 卡玛 {m['calmar']}"
        )


if __name__ == "__main__":
    main()
