# -*- coding: utf-8 -*-
"""观复晨报雏形（9:00——书体系：大盘状态+估值百分位+策略信号）

MVP 内容组装：大盘状态（M 系列）+ 龙头股池估值扫描（B5 过滤）+ 候选讲解
Q1 落地：利率隐含合理 PE 对比
Q5 落地：建议现金比例（状态 → 仓位映射——低潮满仓/高潮防守）
推送：输出文本——企业微信通道复用 Go购 notify（后续接入——MVP 先出内容）
"""

from __future__ import annotations

import datetime

from tools.strategy_engine import data
from tools.strategy_engine import market_status as ms

# 龙头股池（B2 票源——书 A股龙头池——MVP 前 12 只）
LEADER_POOL = [
    "600519",
    "600036",
    "601088",
    "601857",
    "600900",
    "601988",
    "601398",
    "600028",
    "601318",
    "600030",
]


def _valuation_scan(codes: list[str], top_n: int = 5) -> list[dict]:
    """龙头池估值扫描（B5——PE<15 或 PB<2——返回达标候选）"""
    quotes = data.tencent_quote(codes)
    candidates = []
    for code, q in quotes.items():
        pe, pb = q.get("pe_ttm") or 0, q.get("pb") or 0
        if pe <= 0 or pb <= 0:
            continue
        if pe < 15 or pb < 2:
            candidates.append(
                {
                    "code": code,
                    "name": q["name"],
                    "pe": pe,
                    "pb": pb,
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "mcap_yi": q["mcap_yi"],
                }
            )
    candidates.sort(key=lambda x: (x["pe"] > 0, x["pe"]))
    return candidates[:top_n]


def _data_source_status() -> list[str]:
    """数据源健康探测（2026-08-15 UZI data_gap_acknowledged 落地——
    数据缺口显式承认——不静默降级）

    探测：fund_flow 双源（东财/同花顺）+ 估值源（baostock）——
    失败标注为数据缺口（讲解模式/晨报告知用户——而非悄悄缺失）
    """
    notes: list[str] = []
    # ① 主力资金流（东财主源 → 同花顺 fallback——2026-08-15 加）
    try:
        from tools.strategy_engine import fund_flow as ff

        f = ff.main_force_flow(LEADER_POOL[0])  # 用茅台探测
        if not f:
            notes.append("⚠️ 主力资金流：双源均不可用（东财封锁+同花顺失败）")
        elif "同花顺源" in f.get("verdict", ""):
            notes.append("ℹ️ 主力资金流：东财封锁——已降级同花顺（当日快照）")
    except Exception:
        notes.append("⚠️ 主力资金流：探测失败")
    # ② 估值历史源（baostock——估值百分位依赖）
    try:
        p = data.valuation_percentile(LEADER_POOL[0])
        if p.get("pe_percentile", 50.0) == 50.0:
            notes.append("⚠️ 估值百分位：数据不足或源异常（返回中性 50%）")
    except Exception:
        notes.append("⚠️ 估值百分位：探测失败")
    return notes or ["✅ 数据源正常"]


def build_brief() -> str:
    """组装晨报文本（大盘+利率校准+现金纪律+估值候选+讲解）"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %A")
    lines = [f"📋 观复晨报 {now}", "=" * 30]
    # 大盘状态（M 系列 + Q1 利率校准 + Q5 现金纪律）
    m = ms.market_status()
    lines.append(f"\n【大盘状态】{m['status']}")
    lines.append(f"沪深300 PE={m.get('pe')}（百分位≈{m.get('pe_percentile_approx')}%）")
    fp = m.get("fair_pe_rate_calibrated")
    if fp:
        verdict = "便宜" if (m.get("pe") or 0) < fp else "偏贵"
        lines.append(f"Q1 利率校准: 隐含合理PE≈{fp}——当前{verdict}")
    sens = ms._fair_pe_sensitivity_text()
    if sens:
        lines.append(f"  {sens}")
    for e in m.get("evidence", []):
        lines.append(f"  • {e}")
    if not m.get("evidence"):
        lines.append("  • 无极端信号（估值/技术均中性）")
    g = m.get("cash_guidance", {})
    lo, hi = g.get("cash_range", (0, 0))
    hint = g.get("hint", "")
    lines.append(f"Q5 现金纪律: 建议现金 {lo}-{hi}%（{hint}）")
    # 虚拟盘通过判定进度（2026-08-15 加——微信端可视化进度）
    try:
        from tools.strategy_engine.gate_check import check as _gate_check

        gate = _gate_check()
        lines.append(f"\n【虚拟盘进度】{gate.get('reason', '')}")
    except Exception:
        pass  # 判定失败不阻塞晨报（红线③容错）
    # 数据源健康（2026-08-15 UZI data_gap 落地——缺口显式承认——不静默）
    lines.append("\n【数据源】" + "；".join(_data_source_status()))
    # 龙头池估值候选（B5）
    lines.append("\n【龙头池低估候选（B5：PE<15 或 PB<2）】")
    cands = _valuation_scan(LEADER_POOL)
    if cands:
        for c in cands:
            mark = "✅" if (c["pe"] < 15 and c["pb"] < 2) else "🟡"
            lines.append(
                f"  {mark} {c['name']}({c['code']}) PE={c['pe']} "
                f"PB={c['pb']} 今{c['change_pct']:+.1f}%"
            )
        lines.append(
            "\n【讲解】低估只是第一关——还需价值 8 标准（ROE>10%/现金流/负债率）"
            "和基本面检查（不买清单）——观复会继续过滤"
        )
    else:
        lines.append("  今日龙头池无达标候选（市场整体不便宜——持币等待是纪律）")
    lines.append("\n—— 观复 · 书体系执行器（半自动：信号需你确认）")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_brief())
