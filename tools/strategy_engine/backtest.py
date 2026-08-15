# -*- coding: utf-8 -*-
"""回测框架（backtest.py——战术层验证——方案红线：回测达标才启用）

红线（Vibe-Trading 三条——直接抄）：
- 纯本地（akshare 数据）｜不碰真钱｜严格防未来函数（T 日收盘决策、T+1 开盘成交）
- 强制交易成本（佣金万 2.5 + 卖出印花税 0.05%）

方法：walk-forward（2005-2020 训练 / 2021-2025 验证——样本外）——分段报告
指标：交易数/胜率/平均收益/总收益/最大回撤/卡玛比率

策略：信号函数注入（B3/S2/S3——signals.py）——买入=信号触发 T+1 开盘——
卖出=S2 上轨 / 持有超 52 周强制（周期保护）——v0 简化（Q11 校准）

运行：python -m tools.strategy_engine.backtest --code sh000300 --years 20
"""

from __future__ import annotations

import argparse
from typing import Any, Callable

from tools.strategy_engine import signals as sg  # pyright: ignore

SPLIT_DATE = "2021-01-01"   # walk-forward 分界（训练/验证）


def _f(x) -> float:
    """安全浮点转换（数据异常 → 0——不阻塞回测——红线③容错）"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0
COMMISSION = 0.00025        # 佣金万 2.5
STAMP_TAX = 0.0005          # 卖出印花税 0.05%
MAX_HOLD_WEEKS = 52         # 周期保护（v0）
LOT = 100                   # 一手（A股整手交易）


def _fetch_daily(symbol: str, years: int, retries: int = 2) -> Any:
    """日线多源重试（新浪 → 东财节流——限流/反爬时切换——红线③）"""
    import time

    import akshare as ak

    start = f"{2026 - years}0101"
    for attempt in range(retries + 1):
        try:
            df = ak.stock_zh_a_daily(symbol=symbol, start_date=start,
                                     end_date="20261231", adjust="qfq")
            if df is not None and "date" in df.columns and len(df) > 100:
                return df
        except Exception:
            pass
        try:
            df = ak.stock_zh_a_hist(symbol=symbol.replace("sh", "").replace("sz", ""),
                                    period="daily", start_date=start,
                                    end_date="20261231", adjust="qfq")
            if df is not None and "日期" in df.columns and len(df) > 100:
                df = df.rename(columns={"日期": "date", "开盘": "open", "收盘": "close",
                                        "最高": "high", "最低": "low", "成交量": "volume"})
                return df
        except Exception:
            pass
        time.sleep(1 + attempt)  # 节流（东财反爬）
    raise RuntimeError(f"多源获取失败: {symbol}（新浪/东财均不可用）")


def load_weekly(code: str, years: int = 20) -> list[dict[str, Any]]:
    """历史周线（日线重采样——2006 起——多源重试链）"""
    import os

    # 绕过代理/直连（东财源被反爬拒——腾讯源不封 IP）
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    symbol = code if code.startswith(("sh", "sz", "bj")) else ("sh" + code if code.startswith("6") else "sz" + code)
    df = _fetch_daily(symbol, years)  # 多源重试链（红线③：数据失误真实风险）
    weeks: list[dict[str, Any]] = []
    cur = None
    for _, row in df.iterrows():
        d = str(row["date"])
        if cur is None or d[:10] != cur["date"][:10]:
            if cur:
                weeks.append(cur)
            cur = {"date": d, "open": _f(row["open"]), "close": _f(row["close"]),
                   "high": _f(row["high"]), "low": _f(row["low"]),
                   "volume": _f(row["volume"])}
        else:
            cur["close"] = _f(row["close"])
            cur["high"] = max(cur["high"], _f(row["high"]))
            cur["low"] = min(cur["low"], _f(row["low"]))
            cur["volume"] += _f(row["volume"])
    if cur:
        weeks.append(cur)
    return weeks


def run_backtest(weeks: list[dict[str, Any]],
                 buy_fn: Callable[[list[float]], bool],
                 sell_fn: Callable[[list[float]], bool],
                 split_date: str = SPLIT_DATE) -> dict[str, Any]:
    """事件循环回测：信号（T 收盘）→ T+1 开盘成交——分段统计"""
    closes = [w["close"] for w in weeks]
    opens = [w["open"] for w in weeks]
    segments = {"训练": [], "验证": []}
    for i in range(30, len(weeks)):
        seg = "训练" if weeks[i]["date"][:10] < split_date else "验证"
        hist = closes[max(0, i - 250):i]  # 防未来：只用 T 日及之前
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
                trades.append({"entry": pos["entry_px"], "exit": px,
                               "ret_pct": round(ret, 2),
                               "weeks": i - pos["entry_i"],
                               "reason": "S2/估值" if exit_sig else "周期保护"})
                pos = None
                if exit_sig:
                    s_idx += 1
    if not trades:
        return {"trades": 0, "win_rate": 0.0, "avg_ret": 0.0,
                "total_ret": 0.0, "max_dd": 0.0, "calmar": 0.0}
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
    return {"trades": len(trades), "win_rate": round(wins / len(trades) * 100, 1),
            "avg_ret": round(avg, 2), "total_ret": round((total - 1) * 100, 1),
            "max_dd": round(max_dd, 1),
            "calmar": round(avg * len(trades) / max_dd, 2) if max_dd > 0 else 0.0}


def main():
    ap = argparse.ArgumentParser(description="观复战术层回测（walk-forward）")
    ap.add_argument("--code", default="600036", help="标的（默认招行——个股——指数二期）")
    ap.add_argument("--years", type=int, default=20)
    args = ap.parse_args()
    weeks = load_weekly(args.code, args.years)
    print(f"加载 {len(weeks)} 根周线（{weeks[0]['date'][:10]} → {weeks[-1]['date'][:10]}）")
    buy = lambda hist: sg.b3_triple_confirm(hist)["signal"]
    sell = lambda hist: sg.s2_weekly_upper_exit(hist)["signal"]
    res = run_backtest(weeks, buy, sell)
    for seg, m in res.items():
        print(f"\n【{seg}段】{SPLIT_DATE} 分界——交易 {m['trades']} 笔 | "
              f"胜率 {m['win_rate']}% | 均收益 {m['avg_ret']}% | "
              f"累计 {m['total_ret']}% | 最大回撤 {m['max_dd']}% | 卡玛 {m['calmar']}")


if __name__ == "__main__":
    main()
