# -*- coding: utf-8 -*-
"""观复核心循环（agent loop 骨架——agents-best-practices 视角补缺）

每日闭环：数据 → 打分 → 信号 → 确认 → 执行 → 反馈
MVP：①-③ 真实运行（数据/打分/信号）——④-⑥ 骨架（推送/记账/账本——后接）
调用已有模块：market_status / strategy_score / data / indicators
"""
from __future__ import annotations

import datetime
from typing import Any

from tools.strategy_engine import data
from tools.strategy_engine import indicators as ind
from tools.strategy_engine import market_status as ms
from tools.strategy_engine import strategy_score as ss

# 龙头股池（书 B2——A股龙头池——MVP 前 12 只——待建静态 YAML 全量清单）
LEADER_POOL = ["600519", "600036", "601088", "601857", "600900",
               "601988", "601398", "600028", "601318", "600030"]


def _technical_signals(code: str) -> dict[str, Any]:
    """个股技术信号（布林/RSI/九转——从日 K 计算——MVP 近似）"""
    k = data.tencent_kline(code, days=120)
    if not k or len(k) < 25:
        return {}
    closes = [x["close"] for x in k]
    vols = [x["volume"] for x in k]
    out: dict[str, Any] = {}
    b = ind.bollinger(closes, 20, 2)
    if b["lower"]:
        out["boll_lower"] = closes[-1] <= b["lower"]
    r = ind.rsi(closes, 6)
    if r is not None:
        out["rsi_bottom"] = r < 30  # 日线近似（书用周线——MVP 标注）
    td = ind.td_sequential(closes)
    if td.get("setup") == "buy" and td.get("completed"):
        out["td_buy"] = True
    vd = ind.volume_divergence(closes, vols, window=15)
    if vd.get("type") == "bullish":
        out["vol_bottom"] = True
    return out


def _valuation_input(code: str, quote: dict[str, Any]) -> dict[str, Any]:
    """估值面输入（PE/PB + 历史百分位）"""
    v = {"pe_ttm": quote.get("pe_ttm") or 0, "pb": quote.get("pb") or 0}
    try:
        pct = data.valuation_percentile(code)
        v["pe_percentile"] = pct["pe_percentile"]
    except Exception:
        v["pe_percentile"] = 50.0
    return v


def run_daily_loop() -> dict[str, Any]:
    """每日核心循环（MVP）——返回报告"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %A")
    m = ms.market_status()
    fair_pe = m.get("fair_pe_rate_calibrated")
    status = m["status"]
    threshold = ss.THRESHOLD_MAP.get(status, 80)

    # ① 龙头池行情 + 打分
    quotes = data.tencent_quote(LEADER_POOL)
    candidates = []
    for code, q in quotes.items():
        if (q.get("pe_ttm") or 0) <= 0:
            continue
        v = _valuation_input(code, q)
        if fair_pe:
            v["fair_pe"] = fair_pe
        t = _technical_signals(code)
        # 基本面 MVP 占位（待财务数据管线——a-stock-data 三表后接）
        f = {"roe": 0, "sales_margin": 0, "debt_ratio": 0, "ocf_gt_profit": False,
             "dividend_yield": 0, "growth_ok": False}
        s = {"is_leader": True, "bigv_holding": False}
        score = ss.score_stock(f, v, t, s, quote=q, market_status=status)
        candidates.append({
            "code": code, "name": q["name"], "price": q["price"],
            "pe": q.get("pe_ttm"), "pb": q.get("pb"),
            "score": score.total, "threshold": threshold,
            "passed": score.passed, "vetoed": score.vetoed,
            "parts": score.parts[-4:],  # 四维小计
            "tech": t,
        })
    candidates.sort(key=lambda x: -x["score"])

    return {
        "date": now,
        "market_status": status,
        "pe": m.get("pe"),
        "fair_pe": fair_pe,
        "threshold": threshold,
        "candidates": candidates,
        "signals": [c for c in candidates if c["passed"] and not c["vetoed"]],
        "note": "MVP：基本面占位（待财务管线）——技术面日线近似（书用周线）——"
                "确认/记账/账本环节后接（半自动交互）",
    }


def format_report(r: dict[str, Any]) -> str:
    """循环报告文本（晨报衔接——讲解模式三阶原则）"""
    lines = [f"📋 观复每日循环 {r['date']}", "=" * 30]
    lines.append(f"\n【大盘】{r['market_status']}（PE={r.get('pe')}——"
                 f"利率隐含合理≈{r.get('fair_pe')}）——门槛 {r['threshold']}")
    lines.append("\n【候选打分 Top5】（四维：价值/估值/技术/票源）")
    for c in r["candidates"][:5]:
        parts = " | ".join(f"{p[0].split(':')[0]}:{p[1]:.0f}" for p in c["parts"])
        mark = "✅" if c["passed"] else ("⛔" if c["vetoed"] else "—")
        lines.append(f"  {mark} {c['name']}({c['code']}) {c['score']}分 [{parts}]")
    sig = r["signals"]
    if sig:
        lines.append(f"\n【信号】{len(sig)} 个待确认：")
        for c in sig:
            lines.append(f"  🔔 {c['name']} {c['score']}分——确认？")
    else:
        lines.append("\n【信号】今日无达标候选（低于门槛——持币等待是纪律）")
    lines.append(f"\n（{r['note']}）")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_daily_loop()))
