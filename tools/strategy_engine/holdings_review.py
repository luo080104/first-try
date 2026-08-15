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
    v = cl._valuation_input(code, quote)
    m = ms.market_status()
    if m.get("fair_pe_rate_calibrated"):
        v["fair_pe"] = m["fair_pe_rate_calibrated"]
    t = cl._technical_signals(code)
    f = fd.get_fundamentals(code, quote.get("price") or 0,
                            debt_exempt=code in cl._FINANCIAL_EXEMPT)
    s = {"is_leader": True, "bigv_holding": False}
    return ss.score_stock(f, v, t, s, quote=quote, market_status=m["status"])


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
            "code": code, "name": q.get("name", ""),
            "score": score.total, "prev_score": prev_score,
            "threshold": threshold, "market": status,
            "dropped": dropped, "below": below,
            "observe_streak": observe,
            "suggest_exit": observe >= 2,  # 连续两季观察 → 换仓建议（甲方确认）
        }
        hist[code] = {"score": score.total,
                      "observe_streak": observe,
                      "reviewed_at": datetime.now().strftime("%Y-%m-%d")}
        results.append(rec)
    _save_history(hist)
    return results


def main():
    results = review_positions()
    print(f"📋 持仓季度体检 {datetime.now().strftime('%Y-%m-%d')}（门槛 "
          f"{results[0]['threshold'] if results else '—'}——{results[0]['market'] if results else ''}）")
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
