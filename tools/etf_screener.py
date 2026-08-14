# -*- coding: utf-8 -*-
"""
ETF/基金多维对比工具（fund-risk-analyzer，2026-08-13 精读落地）
来源：skillsbot fund-risk-analyzer skill 思路，纯 Python 标准库实现，零依赖。

用法：
  python etf_screener.py --input nav.csv                    # 基础对比
  python etf_screener.py --input nav.csv --risk-free 0.02   # 自定义无风险利率
  python etf_screener.py --input nav.csv --json             # JSON 输出

输入 CSV：第一列日期，后续列为各 ETF 净值。
  date,沪深300ETF,中证500ETF,纳指ETF
  2023-01-03,1.0000,1.0000,1.0000
"""
import argparse
import csv
import json
import math
import sys
from datetime import datetime


def load_nav(path):
    """读取净值 CSV → (dates, {name: [nav...]})"""
    dates, series = [], {}
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        names = header[1:]
        for name in names:
            series[name] = []
        for row in reader:
            if not row or len(row) < 2:
                continue
            dates.append(row[0])
            for i, name in enumerate(names):
                try:
                    val = float(row[i + 1])
                except (ValueError, IndexError):
                    val = float("nan")
                series[name].append(val)
    # 剔除全 NaN 的日期行（缺失值跳过）
    keep = []
    for idx in range(len(dates)):
        if any(not math.isnan(series[n][idx]) for n in names):
            keep.append(idx)
    dates = [dates[i] for i in keep]
    for n in names:
        series[n] = [series[n][i] for i in keep]
    return dates, names, series


def annualized_return(nav, trading_days=252):
    """年化收益率 = (期末/期初)^(交易日数/持有天数) - 1"""
    valid = [x for x in nav if not math.isnan(x)]
    if len(valid) < 2 or valid[0] <= 0:
        return None
    total = valid[-1] / valid[0]
    days = len(valid) - 1
    if days <= 0 or total <= 0:
        return None
    return total ** (trading_days / days) - 1


def max_drawdown(nav):
    """最大回撤 = max((峰值-谷底)/峰值)"""
    peak, mdd = float("-inf"), 0.0
    for x in nav:
        if math.isnan(x):
            continue
        if x > peak:
            peak = x
        if peak > 0:
            dd = (peak - x) / peak
            if dd > mdd:
                mdd = dd
    return mdd


def daily_returns(nav):
    """日收益率序列"""
    out = []
    prev = None
    for x in nav:
        if math.isnan(x):
            prev = None
            continue
        if prev is not None and prev > 0:
            out.append(x / prev - 1)
        prev = x
    return out


def sharpe_ratio(nav, risk_free=0.02, trading_days=252):
    """夏普 = (年化收益 - 无风险利率) / 年化波动率"""
    rets = daily_returns(nav)
    if len(rets) < 2:
        return None
    ann = annualized_return(nav, trading_days) or 0.0
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    vol = math.sqrt(var) * math.sqrt(trading_days)
    if vol == 0:
        return None
    return (ann - risk_free) / vol


def correlation(name_a, nav_a, name_b, nav_b):
    """Pearson 相关系数（基于日收益率）"""
    ra, rb = daily_returns(nav_a), daily_returns(nav_b)
    n = min(len(ra), len(rb))
    if n < 2:
        return None
    ra, rb = ra[:n], rb[:n]
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((ra[i] - ma) * (rb[i] - mb) for i in range(n)) / (n - 1)
    va = sum((r - ma) ** 2 for r in ra) / (n - 1)
    vb = sum((r - mb) ** 2 for r in rb) / (n - 1)
    if va == 0 or vb == 0:
        return None
    return cov / math.sqrt(va * vb)


def fmt(x, digits=4):
    return "—" if x is None else f"{x:.{digits}f}"


def main():
    ap = argparse.ArgumentParser(description="ETF 多维对比工具")
    ap.add_argument("--input", "-i", required=True, help="净值 CSV 文件")
    ap.add_argument("--risk-free", "-rf", type=float, default=0.02, help="无风险利率（默认 0.02=2%）")
    ap.add_argument("--trading-days", type=int, default=252, help="每年交易日数（默认 252）")
    ap.add_argument("--output", "-o", help="输出文件（.csv 或 .json）")
    ap.add_argument("--json", action="store_true", help="JSON 输出到 stdout")
    args = ap.parse_args()

    dates, names, series = load_nav(args.input)
    if len(names) < 1:
        print("错误：CSV 没有数据列", file=sys.stderr)
        return 1

    # 单只指标
    metrics = {}
    for n in names:
        nav = series[n]
        metrics[n] = {
            "年化收益率": annualized_return(nav, args.trading_days),
            "最大回撤": max_drawdown(nav),
            "夏普比率": sharpe_ratio(nav, args.risk_free, args.trading_days),
        }

    # 相关性矩阵
    corr = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            corr[f"{a}×{b}"] = correlation(a, series[a], b, series[b])

    if args.json:
        print(json.dumps({
            "区间": [dates[0], dates[-1]] if dates else [],
            "指标": {n: {k: v for k, v in m.items()} for n, m in metrics.items()},
            "相关性": corr,
        }, ensure_ascii=False, indent=2))
        return 0

    # 表格输出
    print(f"区间: {dates[0]} → {dates[-1]}   无风险利率: {args.risk_free:.2%}")
    print(f"{'ETF':<16}{'年化收益率':>12}{'最大回撤':>12}{'夏普比率':>12}")
    for n in names:
        m = metrics[n]
        print(f"{n:<16}{fmt(m['年化收益率'], 4):>12}{fmt(m['最大回撤'], 4):>12}{fmt(m['夏普比率'], 4):>12}")

    if corr:
        print("\n相关性矩阵（基于日收益率，1=同涨同跌，0=无关，-1=反向）:")
        for pair, c in corr.items():
            print(f"  {pair:<30}{fmt(c, 3)}")

    if args.output:
        ext = args.output.rsplit(".", 1)[-1].lower()
        if ext == "json":
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump({"区间": [dates[0], dates[-1]] if dates else [],
                           "指标": metrics, "相关性": corr}, f,
                          ensure_ascii=False, indent=2)
        else:
            with open(args.output, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["ETF", "年化收益率", "最大回撤", "夏普比率"])
                for n in names:
                    m = metrics[n]
                    w.writerow([n, m["年化收益率"], m["最大回撤"], m["夏普比率"]])
                for pair, c in corr.items():
                    w.writerow([pair, c])
        print(f"\n已保存: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
