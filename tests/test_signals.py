"""战术层信号单测（signals——B3/S2/S3 组合逻辑——指标 mock）"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import signals as sg  # pyright: ignore


def test_b3_requires_all_three():
    """B3 三重确认：缺一不可（两重满足不触发——纪律）"""
    with patch.object(sg.ind, "bollinger", lambda c, n, k: {"lower": 10.0, "upper": 20.0, "mid": 15.0}), \
            patch.object(sg.ind, "rsi", lambda c, n: 25.0), \
            patch.object(sg.ind, "td_sequential", lambda c: {"setup": "buy", "completed": False}):
        r = sg.b3_triple_confirm([9.5] * 40, None)  # 收盘 9.5 < 下轨 10
        assert not r["signal"]  # 九转未完成——不触发
        assert len(r["reasons"]) == 2  # 布林+RSI 两重


def test_b3_trigger():
    with patch.object(sg.ind, "bollinger", lambda c, n, k: {"lower": 10.0, "upper": 20.0, "mid": 15.0}), \
            patch.object(sg.ind, "rsi", lambda c, n: 20.0), \
            patch.object(sg.ind, "td_sequential", lambda c: {"setup": "buy", "completed": True}):
        r = sg.b3_triple_confirm([9.5] * 40, None)  # 收盘 9.5 < 下轨 10
        assert r["signal"] and len(r["reasons"]) == 3


def test_s2_upper_exit():
    """S2 周布林：收盘 > 上轨 → 波段卖出"""
    with patch.object(sg.ind, "bollinger", lambda c, n, k: {"upper": 20.0, "lower": 10.0, "mid": 15.0}):
        assert sg.s2_weekly_upper_exit([21.0] * 25)["signal"]
        assert not sg.s2_weekly_upper_exit([15.0] * 25)["signal"]


def test_s3_valuation_exit():
    """S3 估值溢价：PE > fair_pe×1.5 触发；fair_pe 缺失不触发（Q6 失效条件）"""
    assert sg.s3_valuation_exit(30.0, 15.0)["signal"]
    assert not sg.s3_valuation_exit(20.0, 15.0)["signal"]
    assert not sg.s3_valuation_exit(30.0, None)["signal"]  # 数据缺失——不触发
