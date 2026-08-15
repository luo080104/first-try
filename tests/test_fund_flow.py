"""fund_flow 单测（第四批落地——主力资金流辅助——mock 不依赖网络）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import fund_flow as ff


def _fake_df():
    """合成资金流 DataFrame（5 日——3 正 2 负）"""
    import pandas as pd

    return pd.DataFrame(
        {
            "日期": [f"2026-08-{10+i}" for i in range(5)],
            "主力净流入-净额": [2.0e8, 1.5e8, -0.5e8, 1.0e8, -0.2e8],
            "主力净流入-净占比": [5.0, 3.5, -1.0, 2.5, -0.5],
        }
    )


def test_main_force_flow(monkeypatch):
    """正常数据 → 汇总/趋势/讲解"""
    monkeypatch.setattr("akshare.stock_individual_fund_flow", lambda stock, market: _fake_df())
    r = ff.main_force_flow("600519")
    assert r["net_inflow"] > 0  # 净流入 3.8 亿
    assert r["positive_days"] == 3
    assert r["trend"] == "流入为主"
    assert "主力近5日净流入" in r["verdict"]


def test_flow_failure_returns_empty(monkeypatch):
    """接口失败 → 空 dict（红线③容错——讲解降级跳过）"""

    def _boom(stock, market):
        raise ConnectionError("proxy")

    monkeypatch.setattr("akshare.stock_individual_fund_flow", _boom)
    assert ff.main_force_flow("600519") == {}


def test_format_flow_hint_empty():
    """无数据 → 空字符串（讲解模式跳过）"""
    assert ff.format_flow_hint("000000") == ""


def test_sz_market_prefix(monkeypatch):
    """深市 → sz 前缀"""
    captured = {}

    def _fake(stock, market):
        captured["market"] = market
        return _fake_df()

    monkeypatch.setattr("akshare.stock_individual_fund_flow", _fake)
    ff.main_force_flow("000651")
    assert captured["market"] == "sz"
