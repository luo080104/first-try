"""战术层信号单测（signals——B3/S2/S3 组合逻辑——指标 mock）"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import signals as sg  # pyright: ignore


def test_b3_requires_both():
    """B3 两重定案（回测 2026-08-15）：布林+RSI 缺一不可（九转已否决）"""
    with (
        patch.object(
            sg.ind,
            "bollinger",
            lambda c, n, k: {"lower": 10.0, "upper": 20.0, "mid": 15.0},
        ),
        patch.object(sg.ind, "rsi", lambda c, n: 35.0),
    ):
        r = sg.b3_triple_confirm([9.5] * 40, None)  # 布林触发（9.5<10）但 RSI 35 未超卖
        assert not r["signal"]  # 只有布林——不触发
        assert len(r["reasons"]) == 1


def test_b3_trigger():
    with (
        patch.object(
            sg.ind,
            "bollinger",
            lambda c, n, k: {"lower": 10.0, "upper": 20.0, "mid": 15.0},
        ),
        patch.object(sg.ind, "rsi", lambda c, n: 20.0),
    ):
        r = sg.b3_triple_confirm([9.5] * 40, None)  # 布林（9.5<10）+ RSI（20<30）双触发
        assert r["signal"] and len(r["reasons"]) == 2


def test_s2_upper_exit():
    """S2 周布林：收盘 > 上轨 → 波段卖出"""
    with patch.object(
        sg.ind, "bollinger", lambda c, n, k: {"upper": 20.0, "lower": 10.0, "mid": 15.0}
    ):
        assert sg.s2_weekly_upper_exit([21.0] * 25)["signal"]
        assert not sg.s2_weekly_upper_exit([15.0] * 25)["signal"]


def test_s3_valuation_exit():
    """S3 v2（2026-08-17 十年回测定案）：百分位>80 且跌破MA6 触发；单条件不触发；数据缺失不触发"""
    # 双条件齐：PE/PB 百分位高 + 跌破 6 月均线 → 触发
    assert sg.s3_valuation_exit(90.0, 85.0, 10.0, 11.0)["signal"]
    # 只高估不破位 → 不触发（v2 双条件——趋势确认）
    assert not sg.s3_valuation_exit(90.0, 85.0, 11.5, 11.0)["signal"]
    # 只破位不高估 → 不触发
    assert not sg.s3_valuation_exit(50.0, 40.0, 10.0, 11.0)["signal"]
    # 数据缺失 → 不触发（Q6 失效条件）
    assert not sg.s3_valuation_exit(None, None, 10.0, 11.0)["signal"]
    assert not sg.s3_valuation_exit(90.0, 85.0, 0.0, 11.0)["signal"]
    assert not sg.s3_valuation_exit(90.0, None, 10.0, 11.0)[
        "signal"
    ]  # 单数据缺失——不触发
