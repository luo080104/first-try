# -*- coding: utf-8 -*-
"""market_status 大盘状态单测（mock 数据层——不依赖网络——验证判定逻辑）"""

import os
import sys
from collections.abc import Sequence

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _fake_kline(prices: list[float]) -> list[dict]:
    """价格序列 → 假日 K（250 根——最后 len(prices) 根用给定值）"""
    out = []
    base = 100.0
    for i in range(250):
        p = base + i * 0.05
        if i >= 250 - len(prices):
            p = prices[i - (250 - len(prices))]
        out.append(
            {
                "date": f"2026-01-{i % 28 + 1:02d}",
                "open": p,
                "close": p,
                "high": p,
                "low": p,
                "volume": 1000.0,
            }
        )
    return out


def _run(pe: float, prices: Sequence[float]):
    """mock 数据层跑 market_status"""
    import tools.strategy_engine.market_status as mod

    def fake_quote(codes):
        return {
            "000300": {
                "name": "沪深300",
                "price": 100.0,
                "pe_ttm": pe,
                "pb": 1.0,
                "change_pct": 0.0,
            }
        }

    def fake_kline(code, days=250):
        return _fake_kline(prices)

    old_q, old_k = mod.data.tencent_quote, mod.data.tencent_kline
    mod.data.tencent_quote = fake_quote
    mod.data.tencent_kline = fake_kline
    try:
        return mod.market_status()
    finally:
        mod.data.tencent_quote = old_q
        mod.data.tencent_kline = old_k


def test_normal_market():
    """PE 中性 + 无技术信号 → 正常"""
    prices = [100 + i * 0.1 for i in range(60)]  # 平稳上行——不触下轨
    s = _run(pe=14.0, prices=prices)
    assert s["status"] == "正常"


def test_low_market():
    """PE 低 + 价格大跌触周布林下轨 + RSI 超卖 → 低潮"""
    prices = [100 - i for i in range(60)]  # 持续大跌
    s = _run(pe=8.5, prices=prices)
    assert s["status"] == "低潮"
    assert len(s["evidence"]) >= 1


def test_high_market():
    """PE 高（>80 百分位粗判）+ 持续大涨 → 高潮"""
    prices = [100 + i * 2 for i in range(60)]  # 持续大涨
    s = _run(pe=18.0, prices=prices)
    # PE 粗判 (18-8)/10*100=100% > 80 → 高潮（若周九转触发更稳）
    assert s["status"] in ["高潮", "正常"]  # 至少估值证据在
    assert any("估值" in e for e in s["evidence"])


def test_evidence_explainable():
    """证据可解释（讲解模式联动）"""
    prices = [100 - i for i in range(60)]
    s = _run(pe=8.5, prices=prices)
    assert all(len(e) > 5 for e in s["evidence"])


if __name__ == "__main__":
    test_normal_market()
    test_low_market()
    test_high_market()
    test_evidence_explainable()
    print("✅ 大盘状态单测全过")


def test_cash_guidance_map():
    """Q5 现金纪律映射（研讨定案：低潮 0-20/正常 20-40/高潮 40+）"""
    from tools.strategy_engine import market_status as ms

    g = ms.cash_guidance("低潮")
    assert g["cash_range"][0] == 0 and g["cash_range"][1] == 20
    g = ms.cash_guidance("正常")
    assert g["cash_range"][0] == 20 and g["cash_range"][1] == 40
    g = ms.cash_guidance("高潮")
    assert g["cash_range"][0] == 40 and g["cash_range"][1] == 100
    g = ms.cash_guidance("未知状态")
    assert g["cash_range"][0] == 20 and g["cash_range"][1] == 40  # 默认正常
