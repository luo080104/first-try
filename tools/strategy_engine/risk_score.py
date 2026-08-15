# -*- coding: utf-8 -*-
"""风险计分（Q9——牛市后期风险——周度）

定案（docs/观复落地实施方案.md Q9）：
- 风险计分 = 估值分位 × 技术信号 × 时间剩余度（2027-01 重估点锚定）
- 到阈值（70 分）触发 Q5 现金纪律（防守联动）
- 2027-01 = 重估点（不是判决日）——届时用估值/涨幅数据判定书框架兑现与否

计分（v0 先验——Q11 待校准）：
- 估值分位 0-40（沪深300 PE 百分位）
- 技术过热 0-30（周 RSI>80 / 周九转卖出完成）
- 时间因子 0-30（距 2027-01 剩余月数——越近越高——临近重估谨慎）

运行：python -m tools.strategy_engine.risk_score
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tools.strategy_engine import data
from tools.strategy_engine import indicators as ind
from tools.strategy_engine import market_status as ms

REVIEW_POINT = "2027-01-01"   # Q9：重估点（不是判决日）
TRIGGER = 70                  # Q9：阈值——触发 Q5 现金纪律
TIME_FACTOR_MONTHS = 24       # v0：24 个月内线性逼近重估点


def _months_to_review() -> float:
    """距 2027-01 重估点的剩余月数"""
    now = datetime.now()
    target = datetime.strptime(REVIEW_POINT, "%Y-%m-%d")
    return max(0.0, (target - now).days / 30.0)


def _tech_overheat() -> tuple[int, list[str]]:
    """技术过热贡献（0-30）：周 RSI>80 / 周九转卖出完成"""
    score = 0
    notes: list[str] = []
    try:
        k = data.tencent_kline("sh000300", days=250)
        closes = []
        for i in range(0, len(k), 5):
            week = k[i : i + 5]
            if week:
                closes.append(week[-1]["close"])
        if len(closes) >= 8:
            r = ind.rsi(closes, 6)
            if r and r > 80:
                score += 15
                notes.append(f"周 RSI(6)={r:.0f} > 80（过热）")
            td = ind.td_sequential(closes)
            if td.get("setup") == "sell" and td.get("completed"):
                score += 15
                notes.append("周九转卖出完成（趋势拐点）")
    except Exception:
        pass
    return score, notes


def risk_score() -> dict[str, Any]:
    """风险计分（周度——Q9）"""
    m = ms.market_status()
    pe_pct = m.get("pe_percentile_approx", 50.0)
    val = round(pe_pct / 100 * 40, 1)          # 估值 0-40
    tech, tnotes = _tech_overheat()            # 技术 0-30
    months = _months_to_review()
    time_f = round(max(0.0, 30 * (1 - months / TIME_FACTOR_MONTHS)), 1)  # 时间 0-30
    total = round(val + tech + time_f)
    level = "低" if total < 40 else ("中" if total < TRIGGER else "高")
    return {
        "score": total, "level": level,
        "val_part": val, "tech_part": tech, "time_part": time_f,
        "months_to_review": round(months, 1),
        "tech_notes": tnotes,
        "triggered": total >= TRIGGER,
        "advice": ("⚠️ 高风险——触发 Q5 现金纪律：现金 40%+（高潮防守——等极端信号）"
                   if total >= TRIGGER else
                   "现金纪律维持正常（低-中风险——季度复核）"),
        "note": f"重估点 {REVIEW_POINT}（不是判决日）——届时用估值/涨幅数据判定——v0 参数待校准",
    }


def main():
    r = risk_score()
    print(f"风险计分: {r['score']}/100（{r['level']}风险——估值 {r['val_part']}"
          f" + 技术 {r['tech_part']} + 时间 {r['time_part']}）")
    for n in r["tech_notes"]:
        print("  -", n)
    print(f"距重估点: {r['months_to_review']} 个月（{REVIEW_POINT}）")
    print(f"建议: {r['advice']}")


if __name__ == "__main__":
    main()
