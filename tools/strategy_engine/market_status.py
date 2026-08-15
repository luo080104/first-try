# -*- coding: utf-8 -*-
"""观复大盘状态模块（书 M 系列——晨报核心段）

来源：策略库 v2 大盘信号（操作手册 47/主书 143——A股大盘大熊市判定指标）
输出：{status: 低潮/正常/高潮, evidence[]}——证据可解释（讲解模式联动）
Q1 落地：利率隐含合理 PE（10年国债 + ERP 3%——待校准）
MVP 简化：日 K 重采样周线（书用周/月级别）——估值温度用沪深300 PE 百分位近似
"""

from __future__ import annotations

from typing import Any

from tools.strategy_engine import data
from tools.strategy_engine import indicators as ind


def _resample_weekly(kline: list[dict[str, Any]]) -> list[float]:
    """日 K → 周线收盘价序列（每 5 日取最后收盘）"""
    closes = []
    for i in range(0, len(kline), 5):
        week = kline[i : i + 5]
        if week:
            closes.append(week[-1]["close"])
    return closes


def _rate_fair_pe() -> float | None:
    """Q1 利率校准：利率隐含合理 PE（1/(10年国债+3% ERP)——ERP 待校准标注）"""
    import akshare as ak

    try:
        df = ak.bond_zh_us_rate(start_date="20260801")
        r10 = float(df["中国国债收益率10年"].iloc[-1])
        return round(1 / (r10 / 100 + 0.03), 1)
    except Exception:
        return None


def fair_pe_grid(
    rates: tuple[float, ...] = (0.017, 0.022, 0.028),
    erps: tuple[float, ...] = (0.02, 0.03, 0.04),
) -> list[dict[str, Any]]:
    """Q1 敏感性网格升级（Vibe-Trading DCF 3x3 网格借鉴——2026-08-15）

    合理 PE = 1/(利率 + ERP)——利率×股权风险溢价二维网格
    - 原 Q1：3 利率情景（1.7/2.2/2.8%——ERP 固定 3%）
    - 升级：利率 3 档 × ERP 3 档 = 9 格——讲解模式展示'估值对什么最敏感'
    返回 [{rate, erp, fair_pe}]——利率升/ERP 升 → 合理 PE 降（估值中枢下移）
    """
    out = []
    for r in rates:
        for erp in erps:
            fp = 1 / (r + erp)
            out.append({"rate": round(r * 100, 1), "erp": round(erp * 100, 0), "fair_pe": round(fp, 1)})
    return out


def _fair_pe_sensitivity_text() -> str:
    """讲解模式文本：9 格网格 → 一句话结论（哪个维度敏感）"""
    g = fair_pe_grid()
    if not g:
        return ""
    by_rate = {r: [x["fair_pe"] for x in g if x["rate"] == r] for r in (1.7, 2.2, 2.8)}
    by_erp = {e: [x["fair_pe"] for x in g if x["erp"] == e] for e in (2, 3, 4)}
    # 利率 1.7→2.8 的影响（ERP 固定 3）vs ERP 2→4 的影响（利率固定 1.7）
    rate_span = by_rate[1.7][1] - by_rate[2.8][1]
    erp_span = by_erp[2][0] - by_erp[4][0]
    dom = "利率" if rate_span > erp_span else "风险溢价(ERP)"
    return (
        f"敏感性网格：利率 1.7→2.8% 使合理PE变化约 {rate_span:.0f} 点；"
        f"ERP 2→4% 约 {erp_span:.0f} 点——当前主要敏感于{dom}"
    )


def cash_guidance(status: str) -> dict[str, Any]:
    """Q5 现金纪律：现金比例 = f(大盘状态)——研讨定案（书的最大空白）

    低潮 0-20% / 正常 20-40% / 高潮 40%+（v0 先验——Q11 待校准）
    晨报直接给"建议现金比例"（Q5 定案原文）
    注：与 5-10 万方案的组合现金 10-15%（portfolio Q5 检查）是两个维度——
    此处是"状态→现金比例"映射——组合配置按方案 v1.1
    """
    m = {"低潮": (0, 20), "正常": (20, 40), "高潮": (40, 100)}
    lo, hi = m.get(status, (20, 40))
    center = (lo + hi) // 2
    hint = {
        "低潮": "钱可以多入场——左侧网格/建仓窗口",
        "正常": "维持标准仓位——现金留底",
        "高潮": "现金为王——防守优先——等极端信号",
    }.get(status, "维持标准仓位——现金留底")
    return {"status": status, "cash_range": (lo, hi), "cash_pct": center, "hint": hint}


def market_status() -> dict[str, Any]:
    """大盘状态（沪深300——书 M 系列判定指标）

    证据：估值（PE 百分位粗判）+ 周布林下轨 + 周 RSI(6) + 周九转
    """
    fair_pe = _rate_fair_pe()

    # 估值证据
    q = data.tencent_quote(["sh000300"])
    idx = q.get("000300", {})
    pe = idx.get("pe_ttm") or 0
    pe_pct = 50.0
    if pe > 0:
        # 粗判：沪深300 PE 历史区间约 8-18（近十年）——线性映射百分位
        pe_pct = round(max(0.0, min(100.0, (pe - 8) / 10 * 100)), 1)

    # 技术证据（周线——重采样）
    kline = data.tencent_kline("sh000300", days=250)
    closes = _resample_weekly(kline) if kline else []
    tech = {}
    if len(closes) >= 20:
        b = ind.bollinger(closes, 20, 2)
        tech["boll"] = b
        tech["boll_lower_touch"] = closes[-1] <= b["lower"] if b["lower"] else False
    if len(closes) >= 8:
        tech["rsi6"] = ind.rsi(closes, 6)
        tech["rsi_oversold"] = (tech["rsi6"] or 100) < 20
        tech["td"] = ind.td_sequential(closes)

    # 综合判定（书：满足多数指标确认低潮/高潮）
    evidence: list[str] = []
    status = "正常"
    low_hits, high_hits = 0, 0
    if pe_pct < 10:
        low_hits += 1
        evidence.append(f"估值低潮（PE 百分位≈{pe_pct}%——书：<10% 便宜）")
    elif pe_pct > 80:
        high_hits += 1
        evidence.append(f"估值高潮（PE 百分位≈{pe_pct}%——书：>80% 贵）")
    if tech.get("boll_lower_touch"):
        low_hits += 1
        evidence.append("周布林踩下轨（书：低潮买点——长期）")
    if tech.get("rsi_oversold"):
        low_hits += 1
        evidence.append(f"周 RSI(6)={tech['rsi6']} 超卖（书：<20——中期买点）")
    if (
        tech.get("td")
        and tech["td"].get("setup") == "sell"
        and tech["td"].get("completed")
    ):
        high_hits += 1
        evidence.append("周九转上九转完成（书：趋势终结拐点）")
    if low_hits >= 2:
        status = "低潮"
    elif high_hits >= 2:
        status = "高潮"
    return {
        "status": status,
        "pe": pe,
        "fair_pe_rate_calibrated": fair_pe,  # Q1：利率隐含合理PE（ERP=3%——待校准）
        "pe_percentile_approx": pe_pct,
        "cash_guidance": cash_guidance(status),  # Q5：现金比例=f(大盘状态)
        "evidence": evidence,
        "note": "M 系列判定：估值+周布林+周RSI(6)+周九转——MVP 为日K重采样近似——周/月级别精确化后续",
    }


if __name__ == "__main__":
    s = market_status()
    print(f"大盘状态: {s['status']}（沪深300 PE={s['pe']}）")
    if s.get("fair_pe_rate_calibrated"):
        fp = s["fair_pe_rate_calibrated"]
        verdict = "便宜" if s["pe"] < fp else "偏贵"
        print(f"Q1 利率校准: 合理PE≈{fp}——当前{'便宜' if s['pe'] < fp else '偏贵'}")
    g = s.get("cash_guidance", {})
    if g:
        lo, hi = g.get("cash_range", (0, 0))
        print(f"Q5 现金纪律: 建议现金 {lo}-{hi}%（{g.get('hint', '')}）")
    for e in s["evidence"]:
        print("  -", e)
