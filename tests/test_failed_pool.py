"""失败票纪律测试（书 L2540：不到周布林下轨不买回——2026-08-17）"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import failed_pool as fp

TMP = os.path.join(os.path.dirname(__file__), "_tmp_failed.jsonl")


@pytest.fixture(autouse=True)
def _tmp_file(monkeypatch):
    if os.path.exists(TMP):
        os.remove(TMP)
    monkeypatch.setattr(fp, "FILE", TMP)
    yield
    if os.path.exists(TMP):
        os.remove(TMP)


def test_record_and_load():
    """卖出记录 → 黑名单可加载（书 L2540 数据链）"""
    fp.record_sell("600036", "招行", 38.5, "S1 止损")
    fp.record_sell("600036", "招行", 36.0, "S2 上轨")
    f = fp.load_failed()
    assert len(f) == 2
    assert f[0]["code"] == "600036"
    assert f[0]["sell_price"] == 38.5
    assert f[-1]["reason"] == "S2 上轨"  # 取最新记录


def test_check_rebuy():
    """买回前检查三态：不在黑名单放行 / 价未到下轨拦截 / 已到下轨放行"""
    fp.record_sell("601318", "平安", 52.0, "S1 止损")
    # 不在黑名单 → 放行
    assert not fp.check_rebuy("600036", 35.0, 33.0)["block"]
    # 黑名单 + 现价 ≥ 下轨 → 拦截
    r = fp.check_rebuy("601318", 50.0, 33.0)
    assert r["block"] and "L2540" in r["reason"]
    # 黑名单 + 现价 < 下轨 → 放行（可买回）
    r2 = fp.check_rebuy("601318", 30.0, 33.0)
    assert not r2["block"] and "可买回" in r2.get("ok", "")


def test_build_alert_empty():
    """无黑名单 → 无告警段"""
    assert fp.build_alert_section() == ""
