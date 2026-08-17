"""重试熔断器测试（书 8.3——2026-08-17）"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import breaker

TMP = os.path.join(os.path.dirname(__file__), "_tmp_breaker.json")


@pytest.fixture(autouse=True)
def _tmp(monkeypatch):
    if os.path.exists(TMP):
        os.remove(TMP)
    monkeypatch.setattr(breaker, "FILE", TMP)
    yield
    if os.path.exists(TMP):
        os.remove(TMP)


def test_fail_count_and_trip():
    """当日失败计数 → 达阈值熔断 → 次日自动重置"""
    # 5 次失败内不熔断（limit=5）
    for i in range(4):
        assert breaker.record_fail("xq") == i + 1
        assert not breaker.is_tripped("xq")
    # 第 5 次达阈值
    assert breaker.record_fail("xq") == 5
    assert breaker.is_tripped("xq")
    # 其他组件不受影响
    assert not breaker.is_tripped("wb")
    # 次日重置（模拟日期推进）
    d = breaker._load()
    d["xq"]["date"] = "2000-01-01"
    breaker._save(d)
    assert not breaker.is_tripped("xq")


def test_breaker_state():
    """状态输出（晨报数据源段可引用）"""
    breaker.record_fail("wb")
    st = breaker.breaker_state()
    assert any(s["name"] == "wb" and s["fails"] == 1 for s in st)
