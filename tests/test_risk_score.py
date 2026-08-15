"""风险计分单测（risk_score——Q9：计分公式 + 70 分触发现金纪律）"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import risk_score as rs  # pyright: ignore


def _score(pe_pct, rsi=None, td_sell=False, months=5.0):
    """构造环境：估值分位 + 技术过热 + 距重估月数——测计分公式"""
    with patch.object(rs.ms, "market_status",
                      lambda: {"pe_percentile_approx": pe_pct}), \
            patch.object(rs, "_months_to_review", lambda: months), \
            patch.object(rs, "_tech_overheat",
                         lambda: (30 if (rsi and rsi > 80) else 15 if td_sell else 0,
                                  ["过热" if (rsi and rsi > 80) or td_sell else ""])):
        return rs.risk_score()


def test_high_risk_triggers_cash_discipline():
    """估值 90 分位 + 技术过热 + 临近重估 → 高分 → 触发现金纪律"""
    r = _score(90, rsi=85, months=5.0)
    # 估值 36 + 技术 30 + 时间 30*(1-5/24)=23.75 → ≈90
    assert r["score"] >= 70
    assert r["triggered"] and r["level"] == "高"
    assert "现金" in r["advice"]


def test_low_risk_normal():
    """估值 20 分位 + 无过热 + 距重估远 → 低分 → 正常"""
    r = _score(20, rsi=50, months=20.0)
    # 估值 8 + 技术 0 + 时间 30*(1-20/24)=5 → ≈13
    assert r["score"] < 40
    assert not r["triggered"] and r["level"] == "低"


def test_review_point_anchor():
    """2027-01 重估点锚定（时间因子随临近升高）"""
    assert rs.REVIEW_POINT == "2027-01-01"
    m = rs._months_to_review()
    assert 0 <= m <= 24  # 当前（2026-08）距重估 4-6 个月区间
