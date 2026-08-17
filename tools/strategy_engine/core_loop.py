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
from tools.strategy_engine import signals as sg  # pyright: ignore
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
_FINANCIAL_EXEMPT = {
    "600036",
    "601318",
    "600030",
    "601398",
    "601988",
    "601601",
    "601288",
    "601939",
    "300059",
    "601766",
    "600941",
}


def load_leader_pool() -> list[str]:
    """读龙头池 YAML（书 B2 全量——A股启用/港股二期）——缺失时 fallback MVP 池"""
    try:
        import yaml

        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "leader_pool.yaml"
        )
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        codes = [code for grp in d.get("a_share", {}).values() for code, _ in grp]
        return codes if codes else LEADER_POOL
    except Exception as _e:
        from tools.strategy_engine.diag import log_diag
        log_diag("core_loop", "load_leader_pool", _e, "龙头池加载失败——回退内置池")
        return LEADER_POOL


def technical_signals(code: str) -> dict[str, Any]:
    """个股技术信号（布林/RSI/九转——从日 K 计算——MVP 近似）"""
    k = data.tencent_kline(code, days=120)
    return _technical_from_kline(k)


def _technical_from_kline(k: list[dict[str, Any]] | None) -> dict[str, Any]:
    """从 K 线算技术信号（审查 R6：与 B3 共用一次拉取——不重复网络请求）"""
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


def _b3_from_kline(
    code: str, price: float, name: str, k: list[dict[str, Any]] | None
) -> dict[str, Any] | None:
    """从 K 线算 B3 信号（审查 R6：与 technical 共用一次拉取——不重复网络请求）"""
    try:
        if not k or len(k) < 130:
            return None
        closes = [x["close"] for x in k]
        wk: list[float] = []
        for i in range(0, len(closes), 5):
            seg = closes[i : i + 5]
            if seg:
                wk.append(seg[-1])
        if len(wk) < 30:
            return None
        r = sg.b3_triple_confirm(wk)
        if not r["signal"]:
            return None
        return {
            "code": code,
            "name": name,
            "price": price,
            "score": None,
            "threshold": None,
            "track": "swing",
            "reason": "B3 低潮买入（布林下轨+RSI30——回测达标）",
        }
    except Exception as _e:
        from tools.strategy_engine.diag import log_diag
        log_diag("core_loop", "_b3_from_kline", _e, "B3 计算失败——当日无 B3 信号（diag 留档）")
        return None  # B3 计算失败不阻塞循环（红线③容错）


def valuation_input(code: str, quote: dict[str, Any]) -> dict[str, Any]:
    """估值面输入（PE/PB + 历史百分位 + 个股 fair_pe——Q1 分层）

    Q1 定案：利率管总量时机（指数 fair_pe——market_status）/ 百分位管个股筛选
    个股 fair_pe = 个股 PE 历史中位数（质量已内含——数据驱动——Q11 校准）
    """
    v = {"pe_ttm": quote.get("pe_ttm") or 0, "pb": quote.get("pb") or 0}
    try:
        pct = data.valuation_percentile(code)
        v["pe_percentile"] = pct["pe_percentile"]
        v["fair_pe"] = pct["pe_median"]  # 个股级（覆盖外部传入的指数级）
    except Exception as _e:
        from tools.strategy_engine.diag import log_diag
        log_diag("core_loop", "valuation_pct", _e, "估值百分位失败——中性 50 继续")
        v["pe_percentile"] = 50.0
    return v


def _b3_signal_for(code: str, price: float, name: str) -> dict[str, Any] | None:
    """B3 战术信号（两重版——回测达标 2026-08-15——周线布林下轨+RSI30）

    触发 → 波段仓买入建议（swing——Q16 技术轨——机械止损）——score=None（无打分维度）
    独立入口（单只拉取 260 天）——核心循环走 _b3_from_kline（共用 K 线——审查 R6）
    """
    try:
        k = data.tencent_kline(code, days=260)
        return _b3_from_kline(code, price, name, k)
    except Exception as _e:
        from tools.strategy_engine.diag import log_diag
        log_diag("core_loop", "tencent_kline_b3", _e, "K 线 B3 失败——跳过当日 B3")
        return None  # B3 计算失败不阻塞循环（红线③容错）


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
        # 一次 K 线拉取，两处使用（审查 R6：原 technical_signals 拉 120 天 +
        # B3 单独再拉 260 天——每只 2 次网络请求——合并为 1 次 260 天）
        try:
            k = data.tencent_kline(code, days=260)
        except Exception as _e:
            from tools.strategy_engine.diag import log_diag
            log_diag("core_loop", "tencent_kline", _e, "K 线失败——跳过技术/B3 信号")
            k = None  # K 线失败不阻塞单只打分（红线③容错——跳过技术/B3 信号）
        t = _technical_from_kline(k)
        b3 = _b3_from_kline(code, q.get("price") or 0, q["name"], k)
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
                "parts": score.parts,  # 完整分项（修复截断：原 parts[-4:] 只留技术/票源段）
                "tech": t,
                "b3": b3,
            }
        )
    candidates.sort(key=lambda x: -x["score"])
    signals = [c for c in candidates if c["passed"] and not c["vetoed"]]

    # ② B3 战术信号（两重版——回测达标）——打分未达标但 B3 触发 → 独立入队（波段仓）
    scored = {c["code"] for c in signals}
    for c in candidates:
        if c["code"] in scored:
            continue  # 打分已入队——B3 不重复（去重）
        if c.get("b3"):
            signals.append(c["b3"])

    # ⑤ 达标信号自动入待确认队列（半自动——confirm 交互消费——1确认/2改/3忽略）
    from tools.strategy_engine import confirm as cf

    for sig in signals:
        try:
            cf.append_pending(sig)
        except Exception as _e:
            from tools.strategy_engine.diag import log_diag
            log_diag("core_loop", "append_pending", _e, "信号入队失败——该信号丢失（重要！）")
            pass  # 入队失败不阻塞循环（红线：不因边缘错误中断每日闭环）

    # ⑥ 信号推送（v1.1——达标信号即时推微信——半自动红线：AI 提示带理由）
    if signals:
        try:
            from tools.strategy_engine.notify_gf import push_signal

            lines = [f"{len(signals)} 个达标信号待确认（门槛 {threshold}）："]
            for c in signals:
                tag = f"{c['score']}分" if c.get("score") is not None else "B3战术"
                lines.append(f"  🔔 {c['name']}({c['code']}) {tag}——{c['reason']}")
            push_signal("\n".join(lines))
        except Exception as _e:
            from tools.strategy_engine.diag import log_diag
            log_diag("core_loop", "push_signal", _e, "信号推送失败——见 diag 详情")
            pass  # 推送失败不阻塞（红线③：数据失误不静默但也不中断）

    # 自检段（每日健康检查——数据源命中/打分分布/异常/数据质量）
    scores = [x["score"] for x in candidates]
    anomalies = []
    if not quotes:
        anomalies.append("行情源 0 命中（数据源可能挂了）")
    if not candidates:
        anomalies.append("打分 0 只（估值源或过滤异常）")
    elif max(scores) == 0:
        anomalies.append("全部 0 分（打分异常）")
    # 数据质量检查（第六批落地——MAD 异常值/延迟——WealthAgent 借鉴）
    dq: dict[str, Any] = {"level": "GOOD", "issues": []}
    try:
        from tools.strategy_engine import data_quality as dq_mod

        kline = data.tencent_kline("sh000300", days=120)
        if kline and len(kline) >= 30:
            closes = [x["close"] for x in kline]
            d_dates = [x["date"] for x in kline]
            dq = dq_mod.quality_summary(closes, d_dates, last_date=d_dates[-1])
            for i in dq["issues"]:
                anomalies.append(f"[数据质量] {i['issue']}")
    except Exception as _e:
        from tools.strategy_engine.diag import log_diag
        log_diag("core_loop", "data_quality", _e, "质量检查失败——本日无质量段")
        pass  # 质量检查失败不阻塞（红线③）
    self_check = {
        "quotes_hit": len(quotes),
        "pool_size": len(pool),
        "scored": len(candidates),
        "score_range": [min(scores), max(scores)] if scores else [0, 0],
        "data_quality": dq["level"],
        "anomalies": anomalies,
    }

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
    lines.append("\n【候选打分 Top5】（四维小计：价值/估值/技术/票源）")
    for c in r["candidates"][:5]:
        # 四维小计（parts 里 label 含"小计"的项——显示修复）
        subs = {p[0].replace("小计", ""): p[1] for p in c["parts"] if "小计" in p[0]}
        parts = " | ".join(f"{k}:{v:.0f}" for k, v in subs.items())
        mark = "✅" if c["passed"] else ("⛔" if c["vetoed"] else "—")
        lines.append(f"  {mark} {c['name']}({c['code']}) {c['score']}分 [{parts}]")
    sig = r["signals"]
    if sig:
        lines.append(f"\n【信号】{len(sig)} 个待确认：")
        for c in sig:
            tag = f"{c['score']}分" if c.get("score") is not None else "B3战术"
            lines.append(f"  🔔 {c['name']} {tag}——确认？")
    else:
        lines.append("\n【信号】今日无达标候选（低于门槛——持币等待是纪律）")
    lines.append(f"\n（{r['note']}）")
    return "\n".join(lines)


if __name__ == "__main__":
    print(format_report(run_daily_loop()))
