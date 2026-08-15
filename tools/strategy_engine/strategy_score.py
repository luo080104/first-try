# -*- coding: utf-8 -*-
"""观复动态打分系统（Q12 定案——核心环节——strategy_score 0-100）

打分维度（v0 权重——Q11 参数学习化待校准）：
  价值面 40（ROE10/利润率5/负债5/现金流5/股息10/成长5）
  估值面 30（绝对10/百分位10/利率校准10——Q1 联动）
  技术面 20（布林5/RSI背离5/九转5/量能5）
  票源面 10（大V重仓5/龙头池5）
动态门槛（大盘状态 → 买入门槛）：低潮 70 / 正常 80 / 高潮 88
硬否决（不买清单 N + 红线 R——filters 复用）→ 直接 0 分（烂票永远不买）
输出：ScoreResult{total, parts[], vetoed, veto_reasons, threshold, pass}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tools.strategy_engine import filters as fl

# Q12 定案：动态门槛（大盘状态 → 买入门槛）——v0 待校准
THRESHOLD_MAP = {"低潮": 70, "正常": 80, "高潮": 88}


@dataclass
class ScoreResult:
    total: float
    parts: list[tuple[str, float, str]] = field(default_factory=list)
    vetoed: bool = False
    veto_reasons: list[str] = field(default_factory=list)
    threshold: float = 80.0
    market_status: str = "正常"

    @property
    def passed(self) -> bool:  # pass 是关键字——用 passed
        return not self.vetoed and self.total >= self.threshold


def _score_value(f: dict[str, Any]) -> list[tuple[float, str]]:
    """价值面 0-40（B4 八标准——分项加权）"""
    parts = []
    roe = f.get("roe") or 0
    s1 = min(10.0, roe / 10 * 10) if roe > 0 else 0
    parts.append((s1, f"ROE={roe}%"))
    s2 = 5.0 if (f.get("sales_margin") or 0) > 10 else 0
    parts.append((s2, f"利润率{(f.get('sales_margin') or 0):.0f}%"))
    debt = f.get("debt_ratio") or 0
    # 金融豁免（银行/保险/券商——负债率天然高——书"电力/金融除外"——exempt 时不惩罚）
    s3 = 5.0 if (f.get("debt_exempt", False) or debt < 50) else 0
    parts.append(
        (s3, f"负债率{debt:.0f}%" + ("（金融豁免）" if f.get("debt_exempt") else ""))
    )
    s4 = 5.0 if f.get("ocf_gt_profit", False) else 0
    parts.append((s4, "现金流"))
    dy = f.get("dividend_yield") or 0
    s5 = min(10.0, dy / 4 * 10)
    parts.append((s5, f"股息率{dy:.1f}%"))
    s6 = 5.0 if f.get("growth_ok", False) else 0
    parts.append((s6, "成长性"))
    return parts


def _score_valuation(v: dict[str, Any]) -> list[tuple[float, str]]:
    """估值面 0-30（B5 + Q1 利率校准）"""
    parts = []
    pe, pb = v.get("pe_ttm") or 0, v.get("pb") or 0
    # 绝对估值（PE<15 或 PB<2 满分；PE 25-40 半分——修复死代码：pe<25 分支不可达）
    s1 = 10.0 if (0 < pe < 15) or (0 < pb < 2) else (5.0 if pe < 40 else 0)
    parts.append((s1, f"PE={pe} PB={pb}"))
    pct = v.get("pe_percentile") or 50
    s2 = max(0.0, 10.0 - pct / 10)
    parts.append((s2, f"百分位{pct:.0f}%"))
    fair = v.get("fair_pe")
    if fair and pe > 0:
        s3 = 10.0 if pe < fair else max(0.0, 5.0 - (pe - fair) / fair * 5)
        parts.append((s3, f"利率校准合理PE≈{fair}"))
    else:
        parts.append((5.0, "利率校准数据缺——中性"))
    return parts


def _score_technical(t: dict[str, Any]) -> list[tuple[float, str]]:
    """技术面 0-20（布林/RSI/九转/量能——每项 5 分）

    注：九转 5 分与 B3 回测否决的关系（2026-08-15 审查标注）：
    回测否决的是"九转买入信号"（B3 组合——急跌接刀）——此处九转是打分"加分项"
    （5/100 小权重——非信号）——暂保留——虚拟盘数据后 Q11 校准再判
    """
    parts = []
    parts.append((5.0 if t.get("boll_lower", False) else 0.0, "布林下轨"))
    parts.append((5.0 if t.get("rsi_bottom", False) else 0.0, "RSI底背离/超卖"))
    parts.append((5.0 if t.get("td_buy", False) else 0.0, "九转"))
    parts.append((5.0 if t.get("vol_bottom", False) else 0.0, "量能底背离"))
    return parts


def _score_source(s: dict[str, Any]) -> list[tuple[float, str]]:
    """票源面 0-10（B2）"""
    parts = []
    parts.append((5.0 if s.get("bigv_holding", False) else 0.0, "大V重仓"))
    parts.append((5.0 if s.get("is_leader", False) else 0.0, "龙头股池"))
    return parts


def score_stock(
    f: dict[str, Any],
    v: dict[str, Any],
    t: dict[str, Any],
    s: dict[str, Any],
    quote: dict[str, Any] | None = None,
    market_status: str = "正常",
    redlines: dict[str, bool] | None = None,
) -> ScoreResult:
    """动态打分总入口——输出 0-100 总分 + 分项 + 否决 + 门槛判定"""
    result = ScoreResult(total=0.0, market_status=market_status)
    result.threshold = THRESHOLD_MAP.get(market_status, 80)

    # 硬否决（不买清单 N + 红线 R——filters 复用——烂票永远 0 分）
    result.veto_reasons.extend(fl.check_no_buy(quote or {}))
    # 红线检查（传入真实状态——持仓/资金推导——不再空跑桩）
    result.veto_reasons.extend(fl.check_redlines(redlines or {}))
    if result.veto_reasons:
        result.vetoed = True
        result.total = 0.0
        return result

    all_parts, total_parts = [], []
    for name, parts in [
        ("价值", _score_value(f)),
        ("估值", _score_valuation(v)),
        ("技术", _score_technical(t)),
        ("票源", _score_source(s)),
    ]:
        sub_total = sum(p for p, _ in parts)
        for p, note in parts:
            if p > 0:
                all_parts.append((f"{name}:{note}", p))
                total_parts.append(p)
        all_parts.append((f"{name}小计", sub_total))
    result.total = round(sum(total_parts), 1)
    result.parts = all_parts
    return result
