# -*- coding: utf-8 -*-
"""持仓季度体检（Q14——重打分+观察标记+连续两季换仓建议）

定案（docs/观复落地实施方案.md Q14）：
- 财报季后 1-2 周执行（财务数据更新后）
- 持仓重打分（strategy_score——Q12）→ 打分变化报告（上季 vs 本季）
- 跌破门槛 → 观察标记（不自动卖——半自动红线）——连续两季度 → 换仓建议（甲方确认）
- 打分回升/持平 → 继续持有（Q10 拿住支持联动）

打分复用 core_loop 组装（同包私有函数——避免重复实现）。

运行：python -m tools.strategy_engine.holdings_review
"""

import json
import os
from datetime import datetime

from tools.strategy_engine import core_loop as cl
from tools.strategy_engine import data
from tools.strategy_engine import market_status as ms
from tools.strategy_engine import portfolio as pf
from tools.strategy_engine import strategy_score as ss

REVIEW_FILE = os.path.join(pf.DATA_DIR, "review_history.json")


def _load_history():
    if os.path.exists(REVIEW_FILE):
        try:
            with open(REVIEW_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_history(h):
    try:
        os.makedirs(pf.DATA_DIR, exist_ok=True)
        with open(REVIEW_FILE, "w", encoding="utf-8") as f:
            json.dump(h, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[review] 历史保存失败: {e}")


def _score_position(code, quote):
    """单只持仓重打分（复用 core_loop 组装——价值/估值/技术/票源）"""
    from tools.strategy_engine import fundamentals as fd

    v = cl.valuation_input(code, quote)
    m = ms.market_status()
    if m.get("fair_pe_rate_calibrated"):
        v["fair_pe"] = m["fair_pe_rate_calibrated"]
    t = cl.technical_signals(code)
    f = fd.get_fundamentals(
        code, quote.get("price") or 0, debt_exempt=code in cl._FINANCIAL_EXEMPT
    )
    # C4 修复（2026-08-17 审核）：is_leader 实查龙头池——不再白送 5 分
    try:
        from tools.strategy_engine.core_loop import load_leader_pool

        _pool = load_leader_pool()
        _c = code.split(".")[-1]
        s = {"is_leader": _c in _pool, "bigv_holding": False}
    except Exception:
        s = {"is_leader": False, "bigv_holding": False}
    # C3 修复（2026-08-17 审核）：行业面预计算传入——不再白送中性 10
    try:
        from tools.strategy_engine.industry import score_industry

        ind = score_industry(code)
    except Exception:
        ind = None
    result = ss.score_stock(
        f, v, t, s, quote=quote, market_status=m["status"], industry=ind
    )
    # F3 接线（2026-08-17 审核：B4/B5 过滤器零调用者——书纪律恢复——并入 parts 显示）
    try:
        from tools.strategy_engine import filters as fl

        fr = fl.filter_stock(f, v, quote, {})
        for note in fr.blocked_by:
            result.parts.append((f"B4/B5:{note}", 0.0))
    except Exception:
        pass
    return result


def review_positions() -> list[dict]:
    """体检所有持仓——返回逐只报告（含观察标记/换仓建议）"""
    p = pf.Portfolio()
    hist = _load_history()
    status = ms.market_status()["status"]
    threshold = ss.THRESHOLD_MAP.get(status, 80)
    quotes = data.tencent_quote(list(p.data["holdings"].keys()))
    results = []
    for code in list(p.data["holdings"].keys()):
        q = quotes.get(code)
        if not q:
            continue
        score = _score_position(code, q)
        prev = hist.get(code, {})
        prev_score = prev.get("score")
        observe = prev.get("observe_streak", 0)
        dropped = prev_score is not None and score.total < prev_score
        below = score.total < threshold
        if below:
            observe += 1
        else:
            observe = 0
        rec = {
            "code": code,
            "name": q.get("name", ""),
            "score": score.total,
            "prev_score": prev_score,
            "threshold": threshold,
            "market": status,
            "dropped": dropped,
            "below": below,
            "observe_streak": observe,
            "suggest_exit": observe >= 2,  # 连续两季观察 → 换仓建议（甲方确认）
        }
        hist[code] = {
            "score": score.total,
            "observe_streak": observe,
            "reviewed_at": datetime.now().strftime("%Y-%m-%d"),
        }
        results.append(rec)
    _save_history(hist)
    return results


def main():
    results = review_positions()
    print(
        f"📋 持仓季度体检 {datetime.now().strftime('%Y-%m-%d')}（门槛 "
        f"{results[0]['threshold'] if results else '—'}——{results[0]['market'] if results else ''}）"
    )
    print("=" * 30)
    for r in results:
        delta = ""
        if r["prev_score"] is not None:
            d = r["score"] - r["prev_score"]
            delta = f"（上季 {r['prev_score']}——{'↓' if d < 0 else '↑'} {abs(d):.0f}）"
        line = f"{r['name']}({r['code']}) {r['score']} 分 {delta}"
        if r["suggest_exit"]:
            line += " 🔴 连续两季跌破——建议换仓（等你确认）"
        elif r["below"]:
            line += f" ⚠️ 观察标记（第 {r['observe_streak']} 季）——不自动卖"
        elif r["dropped"]:
            line += " ⚠️ 降分但未破门槛——留意"
        else:
            line += " ✅ 继续持有（Q10 拿住支持）"
        print("  " + line)


if __name__ == "__main__":
    main()


def eval_buy(code: str) -> dict:
    """买入评估强制入口（2026-08-17 甲方要求——任何买入建议必须走全体系）

    机制：代码强制"下意识"——只看估值就出建议的路径从根上堵死。
    输出：完整打分 + 技术信号明细（布林位置/RSI/九转/量能）+ 估值百分位
    + 价值 8 标准 + 否决 + 结论（达标/观察/否决）
    """
    from tools.strategy_engine import fundamentals as fd

    q = data.tencent_quote([code]).get(code, {})
    if not q:
        return {"code": code, "error": "无行情"}
    v = cl.valuation_input(code, q)
    m = ms.market_status()
    if m.get("fair_pe_rate_calibrated"):
        v["fair_pe"] = m["fair_pe_rate_calibrated"]
    t = cl.technical_signals(code)
    k = data.tencent_kline(code, days=260)  # C5：K 线复用——price_from_low 数据生产者
    f = fd.get_fundamentals(
        code, q.get("price") or 0, debt_exempt=code in cl._FINANCIAL_EXEMPT
    )
    s = {"is_leader": True, "bigv_holding": False}
    # 行业面（书 L3098——2026-08-17：预计算传入——失败给中性不阻塞）
    try:
        from tools.strategy_engine.industry import score_industry

        ind = score_industry(code)
    except Exception:
        ind = None
    from tools.strategy_engine.core_loop import _enrich_quote

    score = ss.score_stock(
        f,
        v,
        t,
        s,
        quote=_enrich_quote(q, f, k),
        market_status=m["status"],
        industry=ind,
    )
    # F3 接线（2026-08-17 审核：B4/B5 过滤器零调用者——书纪律恢复——Q6 候选态：报告级不硬拦）
    b4b5 = []
    try:
        from tools.strategy_engine import filters as fl

        fr = fl.filter_stock(f, v, q, {})
        b4b5 = fr.blocked_by
    except Exception:
        pass
    # 技术明细（布林位置/RSI——可读——直接取 technical_signals 字段）
    tech_detail = {k: t[k] for k in ("boll", "rsi", "td", "vol_div") if k in t}
    threshold = ss.THRESHOLD_MAP.get(m["status"], 96)
    if score.vetoed:
        conclusion = "⛔ 否决（不买清单/红线）"
    elif b4b5:
        conclusion = "⛔ B4/B5 未过（书纪律——Q6 候选态待回测）"
    elif score.total >= threshold:
        conclusion = "✅ 达标（可入候选池——仍需 B3 时机信号）"
    else:
        conclusion = f"❌ 未达门槛（{score.total} < {threshold}——等待）"
    return {
        "code": code,
        "name": q.get("name", ""),
        "score": score.total,
        "threshold": threshold,
        "market": m["status"],
        "parts": score.parts,
        "veto": score.veto_reasons,
        "b4b5": b4b5,
        "tech": tech_detail,
        "conclusion": conclusion,
    }
