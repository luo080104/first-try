"""风格温度计单测（style_thermometer——Q8 双驱动判定——mock 数据源）"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import style_thermometer as st  # pyright: ignore


def _status(rate, rs):
    with (
        patch.object(st, "_rate_trend", lambda: rate),
        patch.object(st, "_rs_momentum", lambda: rs),
    ):
        return st.style_status()


def test_red_dividend_wins():
    """利率下行 + RS 走强 → 红利占优（+5-10%）"""
    s = _status("下行", 8.0)
    assert s["style"] == "红利占优"
    assert "红利配置 +5-10%" in s["advice"]


def test_growth_wins():
    """利率回升 + RS 转负 → 成长占优（减红利）"""
    s = _status("上行", -8.0)
    assert s["style"] == "成长占优"
    assert "减红利 5-10%" in s["advice"]


def test_single_signal_cautious():
    """单一信号 → 均衡偏方向（季度再确认——不急着动）"""
    s = _status("上行", 0.0)
    assert s["style"] == "均衡偏成长"
    s = _status("下行", -3.0)
    assert s["style"] == "均衡偏红利"


def test_neutral():
    """无极端信号 → 均衡（维持配置）"""
    s = _status("走平", 0.0)
    assert s["style"] == "均衡"
    assert "维持当前配置" in s["advice"]
