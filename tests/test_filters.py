# -*- coding: utf-8 -*-
"""filters 战略层过滤器单测（真实数据样本 + 合成否决样本）"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.strategy_engine import filters as fl


def _good_fundamentals():
    """符合 B4 的优质标的（招行特征）"""
    return {
        "dividend_yield": 5.0,
        "growth_ok": True,
        "roe": 16.0,
        "ocf_gt_profit": True,
        "sales_margin": 45.0,
        "debt_ratio": 35.0,
        "debt_exempt": True,
        "is_leader": True,
        "future_ok": True,
    }


def _good_valuation():
    """符合 B5 的低估标的（招行特征——PE 6.43/PB 0.88）"""
    return {
        "pe_ttm": 6.43,
        "pb": 0.88,
        "pe_percentile": 5.0,
        "extreme_pe_ok": True,
        "dividend_safety": True,
    }


def _good_quote():
    return {
        "pe_ttm": 6.43,
        "pb": 0.88,
        "ps": 2.0,
        "price_from_low": 10.0,
        "listing_years": 20,
        "holder_reduce": False,
        "recent_surge": False,
        "pe_gt30_recommended": False,
    }


def _no_redlines():
    return {}


def test_good_stock_passes():
    """招行特征 → 全通过"""
    r = fl.filter_stock(
        _good_fundamentals(), _good_valuation(), _good_quote(), _no_redlines()
    )
    assert r.passed is True
    assert len(r.reasons) == 4


def test_moutai_blocked_by_valuation():
    """茅台特征（PE=20.28/PB=7.2——绝对估值高）→ 估值否决"""
    f = _good_fundamentals()
    v = _good_valuation()
    v["pe_ttm"], v["pb"] = 20.28, 7.2
    v["pe_percentile"] = 60.0
    r = fl.filter_stock(f, v, _good_quote(), _no_redlines())
    assert r.passed is False
    assert any("B5" in b for b in r.blocked_by)


def test_no_buy_n13():
    """大V强推+PE>30 → N13 否决"""
    q = _good_quote()
    q["pe_ttm"], q["pe_gt30_recommended"] = 35.0, True
    r = fl.filter_stock(_good_fundamentals(), _good_valuation(), q, _no_redlines())
    assert r.passed is False
    assert any("N13" in b for b in r.blocked_by)


def test_redline_borrowing():
    """借钱（R1）→ 否决"""
    r = fl.filter_stock(
        _good_fundamentals(), _good_valuation(), _good_quote(), {"borrowing": True}
    )
    assert r.passed is False
    assert any("R1" in b for b in r.blocked_by)


def test_new_stock_n9():
    """上市 1 年 → N9 否决"""
    q = _good_quote()
    q["listing_years"] = 1
    r = fl.filter_stock(_good_fundamentals(), _good_valuation(), q, _no_redlines())
    assert r.passed is False
    assert any("N9" in b for b in r.blocked_by)


def test_value_8_roe_fail():
    """ROE=8% → B4-3 否决"""
    f = _good_fundamentals()
    f["roe"] = 8.0
    r = fl.filter_stock(f, _good_valuation(), _good_quote(), _no_redlines())
    assert r.passed is False
    assert any("B4-3" in b for b in r.blocked_by)


def test_explainable_reasons():
    """否决理由可解释（讲解模式联动）"""
    f = _good_fundamentals()
    f["roe"] = 8.0
    f["sales_margin"] = 5.0
    r = fl.filter_stock(f, _good_valuation(), _good_quote(), _no_redlines())
    texts = "；".join(r.blocked_by)
    assert "ROE" in texts and "销售利润率" in texts


if __name__ == "__main__":
    test_good_stock_passes()
    test_moutai_blocked_by_valuation()
    test_no_buy_n13()
    test_redline_borrowing()
    test_new_stock_n9()
    test_value_8_roe_fail()
    test_explainable_reasons()
    print("✅ 过滤器单测全过")
