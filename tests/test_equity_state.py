# -*- coding: utf-8 -*-
"""净值三态标记测试（2026-08-17 甲方 Q6 硬要求——判定只统计 real 点）"""
import json
import sys

sys.path.insert(0, ".")

from tools.strategy_engine.portfolio import Portfolio


def _mk(path, cash=10000, holdings=None):
    d = {
        "init_cash": 80000,
        "cash": cash,
        "holdings": holdings or {},
        "track": "base",
        "equity_curve": [],
    }
    json.dump(d, open(path, "w", encoding="utf-8"))
    return path


def test_all_real(tmp_path):
    """全部持仓真实行情 → real"""
    p = Portfolio(str(tmp_path / "pf.json"))
    _mk(p.path, holdings={"600036": {"name": "招行", "shares": 1000, "avg_cost": 38.2, "track": "base"}})
    p.data = p._load()
    quotes = {"600036": {"price": 39.5, "data_state": "real"}}
    p.record_equity(quotes)
    assert p.data["equity_curve"][-1]["data_state"] == "real"


def test_fallback(tmp_path):
    """行情失败回退成本价 → fallback（判定不计）"""
    p = Portfolio(str(tmp_path / "pf.json"))
    _mk(p.path, holdings={"600036": {"name": "招行", "shares": 1000, "avg_cost": 38.2, "track": "base"}})
    p.data = p._load()
    quotes = {"600036": {"price": 0, "data_state": "fallback"}}
    p.record_equity(quotes)
    assert p.data["equity_curve"][-1]["data_state"] == "fallback"


def test_missing(tmp_path):
    """无行情传入（旧调用方没改）→ missing"""
    p = Portfolio(str(tmp_path / "pf.json"))
    _mk(p.path, holdings={"600036": {"name": "招行", "shares": 1000, "avg_cost": 38.2, "track": "base"}})
    p.data = p._load()
    p.record_equity(None)
    assert p.data["equity_curve"][-1]["data_state"] == "missing"


def test_empty_cash_real(tmp_path):
    """纯现金无持仓 → real（无估值失真问题）"""
    p = Portfolio(str(tmp_path / "pf.json"))
    _mk(p.path, holdings={})
    p.data = p._load()
    p.record_equity({})
    assert p.data["equity_curve"][-1]["data_state"] == "real"
