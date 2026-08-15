"""strategy_score 分段线性 + market_status 敏感性网格单测（第一批 ②⑤）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine.market_status import fair_pe_grid
from tools.strategy_engine.strategy_score import _score_valuation


def _val_score(pe: float) -> float:
    """绝对估值分（PE 单变量——PB 设高不干扰）"""
    s = _score_valuation({"pe_ttm": pe, "pb": 5, "pe_percentile": 50, "fair_pe": 20})
    return s[0][0]


def test_absolute_low_full():
    """书纪律线内满分：PE<15 → 10 分"""
    assert _val_score(14.9) == 10.0


def test_no_cliff():
    """无悬崖：PE 14.9 与 15.1 分差 < 0.5（分段线性——原 5 分跳变）"""
    assert abs(_val_score(14.9) - _val_score(15.1)) < 0.5


def test_linear_descend():
    """15→25 线性递减（10→5）——中间值≈7.5"""
    assert abs(_val_score(20) - 7.5) < 0.1
    assert abs(_val_score(25) - 5.0) < 0.1


def test_over_40_zero():
    """PE>40 → 0 分"""
    assert _val_score(45) == 0.0


def test_grid_nine():
    """敏感性网格 9 格（利率 3 × ERP 3）——利率/ERP 升 → 合理 PE 降"""
    g = fair_pe_grid()
    assert len(g) == 9
    low = next(x for x in g if x["rate"] == 1.7 and x["erp"] == 2)
    high = next(x for x in g if x["rate"] == 2.8 and x["erp"] == 4)
    assert low["fair_pe"] > high["fair_pe"]
