# -*- coding: utf-8 -*-
"""战术层信号（signals.py——B3/S2/S3——回测验证后启用）

定案（docs/观复落地实施方案.md——战术层）：
- B3 三重确认买入（布林下轨 + RSI 超卖/背离 + 九转买入——全部满足才发信号）
- S2 周布林降本（波段仓——周线上轨全卖——Q16 swing 轨）
- S3 估值溢价卖出（PE 超出个股 fair_pe 溢价阈值——Q1 个股级）

红线：战术层信号必须回测验证后才启用（方案原则：战略层直接启用/战术层回测后启用）——
本模块=信号定义（纯函数——无网络）——回测框架（backtest.py）验证通过后接入 core_loop。

参数 v0 先验（Q11 校准清单）：
- B3 组合窗口（周线——连续 N 周内共振）
- S2 上轨触发（周线收盘 > 上轨）
- S3 溢价阈值（PE > fair_pe × 1.5）
"""

from __future__ import annotations

from typing import Any

from tools.strategy_engine import indicators as ind


def b3_triple_confirm(
    closes: list[float], vols: list[float] | None = None
) -> dict[str, Any]:
    """B3 低潮买入（周线——回测定案 2026-08-15：两重版）

    定案（10 只 × 20 年聚合回测——数据裁决）：
    - 两重（布林下轨触 + RSI(6)<30）：训练 76.9% 胜率 / 验证 81.8%——达标启用
    - 九转被否决（三重版训练段 -7.56%——急跌接刀——Q6 印证：九转低位/急跌失效 44% 场景）

    返回 {"signal": bool, "reasons": [...]}——两重全满足才 True
    """
    reasons: list[str] = []
    if len(closes) < 30:
        return {"signal": False, "reasons": ["数据不足"]}
    b = ind.bollinger(closes, 20, 2)
    if b["lower"] and closes[-1] <= b["lower"]:
        reasons.append("布林下轨触")
    r = ind.rsi(closes, 6)
    if r is not None and r < 30:
        reasons.append(f"RSI 超卖({r:.0f})")
    signal = len(reasons) == 2
    return {"signal": signal, "reasons": reasons}


def s2_weekly_upper_exit(closes: list[float]) -> dict[str, Any]:
    """S2 周布林降本（波段仓）：周线收盘 > 布林上轨 → 波段仓卖出信号（Q16 swing 轨）"""
    if len(closes) < 21:
        return {"signal": False, "reasons": ["数据不足"]}
    b = ind.bollinger(closes, 20, 2)
    if b["upper"] and closes[-1] > b["upper"]:
        return {
            "signal": True,
            "reasons": [f"周线收盘 {closes[-1]:.2f} > 上轨 {b['upper']:.2f}"],
        }
    return {"signal": False, "reasons": []}


def s3_valuation_exit(
    pe: float, fair_pe: float | None, premium: float = 1.5
) -> dict[str, Any]:
    """S3 估值溢价卖出（底仓逻辑轨联动）：PE > 个股 fair_pe × 溢价阈值（v0=1.5）

    fair_pe 缺失（接口失败）→ 不触发（宁可不卖不可乱卖——Q6 失效条件）
    """
    if not fair_pe or fair_pe <= 0 or pe <= 0:
        return {"signal": False, "reasons": ["fair_pe 缺失——不触发（Q6 失效条件）"]}
    if pe > fair_pe * premium:
        return {
            "signal": True,
            "reasons": [f"PE {pe:.1f} > fair_pe {fair_pe:.1f} × {premium}"],
        }
    return {"signal": False, "reasons": []}


def evaluate_tactical(
    closes: list[float],
    vols: list[float] | None,
    pe: float = 0.0,
    fair_pe: float | None = None,
) -> dict[str, Any]:
    """战术层综合评估（B3 买入 / S2 波段卖出 / S3 估值卖出）——core_loop 接入点"""
    b3 = b3_triple_confirm(closes, vols)
    s2 = s2_weekly_upper_exit(closes)
    s3 = s3_valuation_exit(pe, fair_pe)
    return {
        "b3": b3,
        "s2": s2,
        "s3": s3,
        "note": "战术层——回测验证后启用（方案红线）——当前仅记录不决策",
    }
