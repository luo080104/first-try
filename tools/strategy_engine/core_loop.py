# -*- coding: utf-8 -*-
"""观复核心循环（agent loop 骨架——agents-best-practices 视角补缺）

每日闭环：数据 → 打分 → 信号 → 确认 → 执行 → 反馈
闭环状态：①-⑤ 真实运行（数据/打分/信号/入队/记账——半自动确认）——
⑥ 反馈（Q11 账本 3/6/12 月回填——signal_ledger）——推送 = M3 vpush 阶段
调用已有模块：market_status / strategy_score / data / indicators / confirm
"""

from __future__ import annotations

import datetime
import os
from typing import Any

from tools.strategy_engine import data
from tools.strategy_engine import indicators as ind
from tools.strategy_engine import market_status as ms
from tools.strategy_engine import strategy_score as ss

# 龙头股池（书 B2——A股龙头池——MVP 前 12 只——待建静态 YAML 全量清单）
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

# 金融豁免（银行/保险/券商——负债率天然高——书"电力/金融除外"）
_FINANCIAL_EXEMPT = {"600036", "601318", "600030", "601398", "601988", "601601",
                     "601288", "601939", "300059", "601766", "600941"}


def load_leader_pool() -> list[str]:
    """读龙头池 YAML（书 B2 全量——A股启用/港股二期）——缺失时 fallback MVP 池"""
    try:
        import yaml
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leader_pool.yaml")
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        codes = [code for grp in d.get("a_share", {}).values() for code, _ in grp]
        return codes if codes else LEADER_POOL
    except Exception:
        return LEADER_POOL


def technical_signals(code: str) -> dict[str, Any]:
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


def valuation_input(code: str, quote: dict[str, Any]) -> dict[str, Any]:
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

    # ① 龙头池行情 + 打分（YAML 全量——fallback MVP 池）
    pool = load_leader_pool()
    quotes = data.tencent_quote(pool)
    candidates = []
    for code, q in quotes.items():
        if (q.get("pe_ttm") or 0) <= 0:
            continue
        v = valuation_input(code, q)
        if fair_pe:
            v["fair_pe"] = fair_pe
        t = technical_signals(code)
        # 基本面真实数据（fundamentals 管线——价值面 40 分）
        from tools.strategy_engine import fundamentals as fd

        f = fd.get_fundamentals(
            code, q.get("price") or 0, debt_exempt=code in _FINANCIAL_EXEMPT
        )
        s = {"is_leader": True, "bigv_holding": False}
        score = ss.score_stock(f, v, t, s, quote=q, market_status=status)
        candidates.append(
            {
                "code": code,
                "name": q["name"],
                "price": q["price"],
                "pe": q.get("pe_ttm"),
                "pb": q.get("pb"),
                "score": score.total,
                "threshold": threshold,
                "passed": score.passed,
                "vetoed": score.vetoed,
                "parts": score.parts[-4:],  # 四维小计
                "tech": t,
            }
        )
    candidates.sort(key=lambda x: -x["score"])
    signals = [c for c in candidates if c["passed"] and not c["vetoed"]]

    # ⑤ 达标信号自动入待确认队列（半自动——confirm 交互消费——1确认/2改/3忽略）
    from tools.strategy_engine import confirm as cf

    for sig in signals:
        try:
            cf.append_pending(sig)
        except Exception:
            pass  # 入队失败不阻塞循环（红线：不因边缘错误中断每日闭环）

    # 自检段（每日健康检查——数据源命中/打分分布/异常）
    scores = [x["score"] for x in candidates]
    anomalies = []
    if not quotes:
        anomalies.append("行情源 0 命中（数据源可能挂了）")
    if not candidates:
        anomalies.append("打分 0 只（估值源或过滤异常）")
    elif max(scores) == 0:
        anomalies.append("全部 0 分（打分异常）")
    self_check = {"quotes_hit": len(quotes), "pool_size": len(pool),
                  "scored": len(candidates),
                  "score_range": [min(scores), max(scores)] if scores else [0, 0],
                  "anomalies": anomalies}

    return {
        "date": now,
        "market_status": status,
        "pe": m.get("pe"),
        "fair_pe": fair_pe,
        "threshold": threshold,
        "candidates": candidates,
        "signals": signals,
        "self_check": self_check,
        "note": "MVP：基本面真实（新浪三表）——技术面日线近似（书用周线）——"
        "确认交互已接（confirm）——Q11 账本采集已开（signal_ledger）——"
        "企业微信推送 = M3 vpush 阶段",
    }


def format_report(r: dict[str, Any]) -> str:
    """循环报告文本（晨报衔接——讲解模式三阶原则）"""
    lines = [f"📋 观复每日循环 {r['date']}", "=" * 30]
    lines.append(
        f"\n【大盘】{r['market_status']}（PE={r.get('pe')}——"
        f"利率隐含合理≈{r.get('fair_pe')}）——门槛 {r['threshold']}"
    )
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
