# -*- coding: utf-8 -*-
"""indicators 指标库单测（合成数据——与手工计算对照）"""

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.strategy_engine import indicators as ind


def test_bollinger_basic():
    # 20 个相同值 → SD=0 → 三轨重合
    closes = [10.0] * 20
    b = ind.bollinger(closes)
    assert b["mid"] == 10.0 and b["upper"] == 10.0 and b["lower"] == 10.0
    # 数据不足
    b2 = ind.bollinger([1, 2, 3], period=20)
    assert b2["mid"] is None


def test_bollinger_known():
    # 手工验证：1..20 → mean=10.5, var=33.25, sd≈5.766
    closes = list(range(1, 21))
    b = ind.bollinger(closes)
    assert abs(b["mid"] - 10.5) < 0.01
    assert abs(b["sd"] - math.sqrt(33.25)) < 0.01
    assert abs(b["upper"] - (10.5 + 2 * math.sqrt(33.25))) < 0.01
    assert abs(b["lower"] - (10.5 - 2 * math.sqrt(33.25))) < 0.01


def test_rsi_known():
    # 全涨 → RSI=100；全跌 → RSI=0
    up = list(range(1, 15))
    assert ind.rsi(up, 6) == 100.0
    down = list(range(15, 1, -1))
    assert ind.rsi(down, 6) == 0.0
    # 数据不足
    assert ind.rsi([1, 2, 3], 6) is None


def test_rsi_mixed():
    # 涨跌交替 → RSI 在 50 附近（非 100/0）
    mixed = [10, 11, 10, 12, 11, 13, 12, 14, 13, 15]
    r = ind.rsi(mixed, 6)
    assert r is not None and 0 < r < 100


def test_td_sequential_buy():
    # 连续下跌 9+ 根（每根比 4 根前低）→ 下九转完成
    closes = [100 - i for i in range(0, 15)]  # 严格递减
    t = ind.td_sequential(closes)
    assert t["setup"] == "buy" and t["completed"] == True


def test_td_sequential_sell():
    closes = [100 + i for i in range(0, 15)]  # 严格递增
    t = ind.td_sequential(closes)
    assert t["setup"] == "sell" and t["completed"] == True


def test_volume_divergence():
    # 顶背离：价格新高 + 量能萎缩
    prices = [
        10,
        11,
        12,
        13,
        14,
        15,
        16,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        36,
        37,
        38,
        39,
        40,
        41,
        42,
        43,
        44,
        45,
        46,
        47,
        48,
        49,
        50,
    ]
    vols = [100] * 30 + [60] * 11  # 后段量能整体萎缩（峰值 60 < 前段 100*0.8）
    d = ind.volume_divergence(prices, vols, window=10)
    assert d["type"] == "bearish"


if __name__ == "__main__":
    test_bollinger_basic()
    test_bollinger_known()
    test_rsi_known()
    test_rsi_mixed()
    test_td_sequential_buy()
    test_td_sequential_sell()
    test_volume_divergence()
    print("✅ 全部指标单测通过")
