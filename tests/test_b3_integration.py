"""B3 集成测试（core_loop._b3_signal_for + confirm 兼容——回测达标 2026-08-15）"""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import core_loop as cl  # pyright: ignore

TMP = tempfile.mkdtemp()


def _fake_kline(days=260):
    """假日 K（长度足够重采样周线）"""
    return [{"close": 35.0 + i * 0.01, "volume": 1000} for i in range(days)]


def test_b3_signal_struct():
    """B3 触发 → 波段仓建议（swing/score=None/reason 标注）"""
    with patch.object(cl.data, "tencent_kline", lambda c, days=260: _fake_kline()), \
            patch.object(cl.sg, "b3_triple_confirm", lambda wk: {"signal": True, "reasons": ["x", "y"]}):
        sig = cl._b3_signal_for("600036", 38.0, "招商银行")
        assert sig is not None
        assert sig["track"] == "swing"  # Q16 波段轨
        assert sig["score"] is None  # B3 无打分维度
        assert "B3" in sig["reason"]
        assert sig["price"] == 38.0


def test_b3_no_signal_returns_none():
    """B3 未触发 → None（不入队）"""
    with patch.object(cl.data, "tencent_kline", lambda c, days=260: _fake_kline()), \
            patch.object(cl.sg, "b3_triple_confirm", lambda wk: {"signal": False, "reasons": []}):
        assert cl._b3_signal_for("600036", 38.0, "招商银行") is None


def test_b3_kline_failure_safe():
    """K 线获取失败 → None（红线③：不阻塞循环）"""
    with patch.object(cl.data, "tencent_kline", side_effect=Exception("行情失败")):
        assert cl._b3_signal_for("600036", 38.0, "招商银行") is None


def test_confirm_accepts_b3_signal():
    """confirm 兼容 B3 信号（score=None 入队正常——shares 正常计算）"""
    import tools.strategy_engine.confirm as cf

    cf.PENDING_FILE = os.path.join(TMP, "pending_b3.json")
    b3 = {"code": "600036", "name": "招商银行", "price": 38.0, "score": None,
          "threshold": None, "track": "swing", "reason": "B3 低潮买入"}
    ok, _ = cf.append_pending(b3, total_assets=100000)
    assert ok
    item = cf.list_pending()[0]
    assert item["score"] is None
    assert item["track"] == "swing"
    assert item["shares"] > 0  # 10万×10%/38 = 260 → 整百 200
