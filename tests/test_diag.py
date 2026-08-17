"""结构化诊断日志测试（书 6.5——2026-08-17）"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import diag

TMP = os.path.join(os.path.dirname(__file__), "_tmp_diag.jsonl")


def _rm(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


@pytest.fixture(autouse=True)
def _tmp(monkeypatch):
    _rm(TMP)
    monkeypatch.setattr(diag, "FILE", TMP)
    yield
    _rm(TMP)


def test_log_and_load():
    """写入结构化记录 → 可加载（类型/组件/hint 完整）"""
    diag.log_diag("晨报", "持仓盈亏", ValueError("bad quote"), "查 diag.jsonl")
    diag.log_diag("晨报", "S4", KeyError("x"), "查 diag.jsonl")
    d = diag.load_diag()
    assert len(d) == 2
    assert d[0]["component"] == "晨报"
    assert d[0]["exc_type"] == "ValueError"
    assert d[0]["fn"] == "持仓盈亏"


def test_recent_hints():
    """近 N 天组件过滤"""
    diag.log_diag("晨报", "A", ValueError(), "")
    diag.log_diag("周报", "B", ValueError(), "")
    r = diag.recent_hints("晨报")
    assert len(r) == 1 and r[0]["fn"] == "A"
