# -*- coding: utf-8 -*-
"""回测市场状态覆盖度（regime_coverage.py——2026-08-15 第二批案例精读落地）

借鉴：WealthAgent regime_detector（滚动波动率聚类分状态——250 行精读）
修复：原实现年化系数 bug（固定 ×√252——周线数据失真 5 倍）——周期参数化
用途：回测结论的"覆盖度警告"——B3 验证段 N=11 胜率 81.8%——若 11 笔全在
     单一波动状态，结论脆弱（书："过去20年有效不代表未来"的量化版）

方法：周收益率 → 26 周滚动年化波动率 → z-score 三态（高/正常/低波动）
     → 短状态合并（<8 周并入相邻）→ 每段年化收益/波动/夏普
     → 交易分布检查（每笔交易落在哪个状态）
运行：python -m tools.strategy_engine.regime_coverage
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from tools.strategy_engine import data as d

# 周期参数（修复原实现：日线 252/周线 52——年化系数按数据频率）
PERIODS_PER_YEAR = 52  # 周线（回测统一周线——数据边界定案）
VOL_WINDOW = 26  # 滚动波动率窗口（周——约半年）
Z_HIGH = 1.5  # 高波动阈值（标准差倍数）
Z_LOW = 1.0  # 低波动阈值
MIN_DAYS = 8  # 短状态合并阈值（周）


def _rolling_vol(returns: list[float], window: int = VOL_WINDOW) -> list[float]:
    """滚动年化波动率（周线——×√52——修复原实现 ×√252 bug）

    边界处理：前 window-1 个值（小样本）用第一个满窗值填充——避免开头伪状态
    """
    out: list[float] = []
    for i in range(len(returns)):
        seg = returns[max(0, i - window + 1) : i + 1]
        if len(seg) < 2:
            out.append(0.0)
            continue
        m = mean(seg)
        var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
        out.append(var**0.5 * (PERIODS_PER_YEAR**0.5))
    # 前 window-1 个小样本值 → 第一个满窗值（消除开头伪状态）
    if len(out) >= window:
        first_valid = out[window - 1]
        for i in range(window - 1):
            out[i] = first_valid
    return out


def _classify(vol: list[float]) -> list[str]:
    """z-score 三态分类（高波动/正常/低波动）"""
    valid = [v for v in vol if v > 0]
    if not valid:
        return ["normal"] * len(vol)
    mv = mean(valid)
    sd = (sum((v - mv) ** 2 for v in valid) / (len(valid) - 1)) ** 0.5
    if sd == 0:
        return ["normal"] * len(vol)
    labels = []
    for v in vol:
        if v > mv + Z_HIGH * sd:
            labels.append("high_volatility")
        elif v < mv - Z_LOW * sd:
            labels.append("low_volatility")
        else:
            labels.append("normal")
    return labels


def _merge_short(labels: list[str], min_days: int = MIN_DAYS) -> list[str]:
    """短状态合并（<min_days 周并入相邻——两侧取更长者）"""
    out = list(labels)
    while True:
        groups: list[tuple[int, int, str]] = []
        i = 0
        while i < len(out):
            j = i
            while j < len(out) and out[j] == out[i]:
                j += 1
            groups.append((i, j, out[i]))
            i = j
        if len(groups) <= 1:
            break
        merged = False
        for idx, (s, e, _) in enumerate(groups):
            if e - s >= min_days:
                continue
            if idx == 0:
                new_label = groups[1][2]
            elif idx == len(groups) - 1:
                new_label = groups[idx - 1][2]
            else:
                left_dur = groups[idx - 1][1] - groups[idx - 1][0]
                right_dur = groups[idx + 1][1] - groups[idx + 1][0]
                new_label = groups[idx - 1][2] if left_dur >= right_dur else groups[idx + 1][2]
            for k in range(s, e):
                out[k] = new_label
            merged = True
            break
        if not merged:
            break
    return out


def detect_regimes(closes: list[float]) -> list[dict[str, Any]]:
    """市场状态分段（周线收盘 → 状态段列表）"""
    if len(closes) < VOL_WINDOW + 2:
        return []
    returns = [(closes[i] - closes[i - 1]) / closes[i - 1] for i in range(1, len(closes))]
    vol = _rolling_vol(returns)
    labels = _merge_short(_classify(vol))
    # 分段
    regimes: list[dict[str, Any]] = []
    i = 0
    while i < len(labels):
        j = i
        while j < len(labels) and labels[j] == labels[i]:
            j += 1
        seg_rets = returns[i:j]
        m = mean(seg_rets) if seg_rets else 0.0
        # 年化（周线——修复原实现：日线系数错用）
        ann_ret = ((1 + m) ** PERIODS_PER_YEAR - 1) * 100 if m > -1 else -100.0
        sd = (
            (sum((x - m) ** 2 for x in seg_rets) / (len(seg_rets) - 1)) ** 0.5
            if len(seg_rets) > 1
            else 0.0
        )
        ann_vol = sd * (PERIODS_PER_YEAR**0.5) * 100
        sharpe = (ann_ret / 100 - 0.02) / (ann_vol / 100) if ann_vol > 0.01 else 0.0
        regimes.append(
            {
                "label": labels[i],
                "start_idx": i + 1,  # 对应 returns 索引（closes 错一位）
                "end_idx": j,
                "weeks": j - i,
                "ann_return": round(ann_ret, 1),
                "ann_vol": round(ann_vol, 1),
                "sharpe": round(sharpe, 2),
            }
        )
        i = j
    return regimes


def coverage_report(
    closes: list[float], trade_indices: list[int] | None = None
) -> dict[str, Any]:
    """覆盖度报告：状态分段 + 交易分布 + 警告

    trade_indices：回测交易发生的位置（closes 索引）——检查是否覆盖多状态
    """
    regimes = detect_regimes(closes)
    if not regimes:
        return {"n_regimes": 0, "regimes": [], "warning": "数据不足——无法检测市场状态"}
    n = len(regimes)
    warning = (
        ""
        if n >= 2
        else "⚠️ 回测区间仅覆盖 1 个市场状态——结论脆弱（样本单态）"
    )
    trade_dist: dict[str, int] = {}
    if trade_indices:
        for ti in trade_indices:
            for r in regimes:
                if r["start_idx"] <= ti <= r["end_idx"]:
                    trade_dist[r["label"]] = trade_dist.get(r["label"], 0) + 1
                    break
        # 交易集中度警告（>80% 在单一状态）
        if trade_dist:
            top = max(trade_dist.values())
            total = sum(trade_dist.values())
            if total >= 5 and top / total > 0.8:
                warning += f"｜🔴 交易 {top}/{total} 集中在单一状态——结论可能仅适用于该状态"
    return {
        "n_regimes": n,
        "regimes": regimes,
        "trade_dist": trade_dist,
        "warning": warning,
    }


if __name__ == "__main__":
    weeks = d.bs_kline_weekly("000300", 10)
    closes = [w["close"] for w in weeks]
    r = coverage_report(closes)
    print(f"沪深300 近 10 年: {r['n_regimes']} 个市场状态")
    for rg in r["regimes"]:
        print(
            f"  {rg['label']:<16} {rg['weeks']:>3} 周 | 年化 {rg['ann_return']:>7.1f}% | "
            f"波动 {rg['ann_vol']:>5.1f}% | 夏普 {rg['sharpe']:>6.2f}"
        )
    if r.get("trade_dist"):
        print(f"交易分布: {r['trade_dist']}")
    print(f"警告: {r['warning'] or '✅ 覆盖多状态——结论稳健'}")
