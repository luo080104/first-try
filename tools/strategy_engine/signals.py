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


def s2_weekly_upper_exit(
    closes: list[float], bull_filter: bool = False
) -> dict[str, Any]:
    """S2 周布林降本（波段仓）：周线收盘 > 布林上轨 → 波段仓卖出信号（Q16 swing 轨）

    bull_filter（2026-08-16 Q11 预研——默认关闭）：书自限"牛市（周布林中轨上升）
    时上轨不是好卖出指标"——K 扩池已支持书（牛熊限定训练 +20.8% vs 机械 +8.1%）——
    启用需虚拟盘数据裁决（红线——不预启用）。开启后：MA20 上升（牛市）→ 不触发卖出。
    """
    if len(closes) < 22:
        return {"signal": False, "reasons": ["数据不足"]}
    b = ind.bollinger(closes, 20, 2)
    if b["upper"] and closes[-1] > b["upper"]:
        if bull_filter:
            # 牛市过滤（Q11 预研）：中轨上升 = MA20 本周 > 上周——不卖
            ma_now = sum(closes[-20:]) / 20
            ma_prev = sum(closes[-21:-1]) / 20
            if ma_now > ma_prev:
                return {
                    "signal": False,
                    "reasons": [
                        "触上轨但牛市（MA20 上升）——书：牛市上轨不卖（Q11 待裁决）"
                    ],
                }
        return {
            "signal": True,
            "reasons": [f"周线收盘 {closes[-1]:.2f} > 上轨 {b['upper']:.2f}"],
        }
    return {"signal": False, "reasons": []}


def _ma(closes: list[float], n: int) -> float | None:
    """简单均线（最近 n 周收盘——数据不足 None）"""
    if len(closes) < n:
        return None
    return sum(closes[-n:]) / n


def ma_cross_exit(closes: list[float], fast: int = 5, slow: int = 20) -> dict[str, Any]:
    """卖出候选-变体B：MA 交叉触发（fast 下穿 slow → 卖出）

    来源：aiagents-stock low_price_bull_strategy（MA5 下穿 MA20 卖）
    状态：候选——未回测不启用（红线）——进三变体对比池
    预期问题（投资视角）：震荡市反复交叉——假信号——回测裁决
    """
    if len(closes) < slow + 2:
        return {"signal": False, "reasons": ["数据不足"]}
    f_prev = _ma(closes[:-1], fast)
    s_prev = _ma(closes[:-1], slow)
    f_now = _ma(closes, fast)
    s_now = _ma(closes, slow)
    if None in (f_prev, s_prev, f_now, s_now):
        return {"signal": False, "reasons": ["数据不足"]}
    # 交叉事件：前周 fast>slow，本周 fast<=slow（None 已排除）
    if (
        f_prev is not None
        and s_prev is not None
        and f_now is not None
        and s_now is not None
        and f_prev > s_prev
        and f_now <= s_now
    ):
        return {
            "signal": True,
            "reasons": [f"MA{fast} 下穿 MA{slow}（{f_now:.2f} vs {s_now:.2f}）"],
        }
    return {"signal": False, "reasons": []}


def ma_trend_confirm_exit(closes: list[float], slow: int = 20) -> dict[str, Any]:
    """卖出候选-变体C：融合版——MA 交叉确认趋势转熊 → 启用 S1 熊市规则

    设计（2026-08-15 探讨——甲方认可进回测池）：
    - 书的盲区：S1 依赖"周布林中轨下跌趋势"——但趋势拐点无机械触发器（Q7 滞后）
    - 本变体：MA20 走平转下（前周上升→本周下降）= 拐点确认 → 触发卖出
    - 与书不冲突：不替代布林/九转——只补"何时算熊市开始"的判定
    """
    if len(closes) < slow + 2:
        return {"signal": False, "reasons": ["数据不足"]}
    ma_prev2 = _ma(closes[:-2], slow)
    ma_prev1 = _ma(closes[:-1], slow)
    ma_now = _ma(closes, slow)
    if None in (ma_prev2, ma_prev1, ma_now):
        return {"signal": False, "reasons": ["数据不足"]}
    # 拐点：前周上升（prev2<prev1）→ 本周转下（prev1>now）（None 已排除）
    if (
        ma_prev2 is not None
        and ma_prev1 is not None
        and ma_now is not None
        and ma_prev2 < ma_prev1
        and ma_prev1 > ma_now
    ):
        return {
            "signal": True,
            "reasons": [f"MA{slow} 走平转下（拐点——趋势转熊确认）"],
        }
    return {"signal": False, "reasons": []}


def s3_valuation_exit(
    pe_pct: float | None, pb_pct: float | None, close: float, ma6: float
) -> dict[str, Any]:
    """S3 估值减仓 v2（2026-08-17 十年回测定案——书 L5524+L3906 融合）：

    规则：PE 或 PB 百分位（十年滚动）>80 且 现价 < 6 月均线 → 建议减仓 1/3
    （v1 为 PE>fair_pe×1.5——十年回测收益灾难（-50~-90%）——数据裁决弃用）
    回测：招行收益 99%（12.25 vs 12.34）且回撤减半——书目标股有效；
    强票（茅台）收益换防守——可接受（书体系本就避开强票）
    数据缺失（接口失败）→ 不触发（宁可不卖不可乱卖——Q6 失效条件）
    """
    if pe_pct is None or pb_pct is None or close <= 0 or ma6 <= 0:
        return {"signal": False, "reasons": ["数据缺失——不触发（Q6 失效条件）"]}
    high = max(pe_pct, pb_pct) > 80
    trend_break = close < ma6
    if high and trend_break:
        return {
            "signal": True,
            "reasons": [
                f"PE百分位{pe_pct:.0f}%/PB百分位{pb_pct:.0f}% >80 且跌破6月均线"
                f"（{close:.2f}<{ma6:.2f}）——建议减仓1/3（书L5524——十年回测v2）"
            ],
        }
    if high and not trend_break:
        return {
            "signal": False,
            "reasons": ["高估但趋势未破（>MA6）——持有（v2 双条件）"],
        }
    return {"signal": False, "reasons": []}


def evaluate_tactical(
    closes: list[float],
    vols: list[float] | None,
    pe_pct: float | None = None,
    pb_pct: float | None = None,
) -> dict[str, Any]:
    """战术层综合评估（B3 买入 / S2 波段卖出 / S3 估值减仓）——core_loop 接入点"""
    b3 = b3_triple_confirm(closes, vols)
    s2 = s2_weekly_upper_exit(closes)
    ma6 = sum(closes[-120:]) / len(closes[-120:]) if len(closes) >= 20 else 0
    s3 = s3_valuation_exit(pe_pct, pb_pct, closes[-1] if closes else 0, ma6)
    return {
        "b3": b3,
        "s2": s2,
        "s3": s3,
        "note": "战术层——S3 v2 十年回测定案（2026-08-17）——建议级不自动卖",
    }


# ============================================================================
# 信号注册表（2026-08-15——czsc 借鉴——信号注册制重构）
# 目标：新信号 = 写函数 + 注册一行——回测/核心循环/文档按注册表遍历——自动去重
# 结构：id → {kind: buy/sell, fn, desc, status: enabled/候选/否决, source}
# 用法：signals.SIGNALS[key] / signals.list_signals(kind=...)
# ============================================================================

SIGNALS: dict[str, dict[str, Any]] = {
    # ---- 买入（战术层——B3 两重定案 2026-08-15） ----
    "B3": {
        "kind": "buy",
        "fn": b3_triple_confirm,
        "desc": "B3 低潮买入：布林下轨触 + RSI(6)<30（两重——定案启用）",
        "status": "enabled",
        "source": "主书低潮买入——回测定案",
        "wired": True,  # 生产接线：core_loop B3 信号（2026-08-17 A4 审计）
        "min_cash": 8000,  # 最小资金约束（2026-08-16 架构师 B1：单只 10% 仓位下限——8 万可执行）
    },
    # ---- 卖出（战术层） ----
    "S2": {
        "kind": "sell",
        "fn": s2_weekly_upper_exit,
        "desc": "S2 周布林降本：周线收盘 > 布林上轨 → 波段仓卖出（启用）",
        "status": "enabled",
        "source": "主书64/95/手册62",
        "wired": False,  # A4（2026-08-17）：生产路径零调用——仅回测使用——待接波段仓卖出
    },
    "S3": {
        "kind": "sell",
        "fn": s3_valuation_exit,
        "desc": "S3 估值减仓 v2：PE/PB 百分位>80 且跌破6月均线 → 建议减仓1/3（候选——2026-08-17 扩池 35 只样本外：达标仅 9%——收益代价高——防守属性保留）",
        "status": "候选",
        "source": "主书46/95/98（L5524）+L3906——训练回测 v2 定案被样本外推翻",
        "wired": True,  # 生产接线：日报 S3 估值减仓提示段（建议级——不自动卖）
    },
    "MA交叉": {
        "kind": "sell",
        "fn": ma_cross_exit,
        "desc": "卖出变体B：MA5 下穿 MA20（回测 p=0.49 不显著——否决）",
        "status": "否决",
        "source": "aiagents-stock low_price_bull_strategy",
    },
    "MA拐点": {
        "kind": "sell",
        "fn": ma_trend_confirm_exit,
        "desc": "卖出变体C：MA20 拐点确认（回测低于书式——否决）",
        "status": "否决",
        "source": "设计 2026-08-15 进池对比",
    },
}

# 买入变体（B3 网格调参——make_buy 工厂用——回测工具）
B3_VARIANTS: dict[str, dict[str, Any]] = {
    "b+r+t": {"note": "三重（含九转）——回测否决——不进核心", "status": "否决"},
    "b+r": {"note": "两重——定案启用", "status": "enabled"},
    "r+t": {"note": "RSI+九转——网格调参候选", "status": "候选"},
    "b+t": {"note": "布林+九转——网格调参候选", "status": "候选"},
    "b+r40+t": {"note": "布林+RSI40+九转——放宽候选", "status": "候选"},
}


def list_signals(kind: str | None = None) -> list[dict[str, Any]]:
    """列出注册表（按 kind 过滤 buy/sell）——自动去重（注册表本身 dict——天然去重）"""
    out = []
    for sig_id, meta in SIGNALS.items():
        if kind and meta["kind"] != kind:
            continue
        out.append({"id": sig_id, **meta})
    return out


def wiring_status() -> list[dict[str, str]]:
    """A4 审计（2026-08-17）：注册表接线状态——enabled 但 wired=False = 目录非开关

    core_loop/日报按此输出——新信号忘接有兜底（不再无声无息）
    """
    return [
        {"id": s["id"], "status": s["status"], "wired": str(s.get("wired", False))}
        for s in list_signals()
        if s["status"] == "enabled"
    ]


def get_signal(sig_id: str) -> dict[str, Any] | None:
    """按 id 查信号（S1-S7/MA交叉——未找到 None）——core_loop/backtest 统一入口"""
    return SIGNALS.get(sig_id)
