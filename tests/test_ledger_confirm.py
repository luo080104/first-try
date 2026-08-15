"""Q11 账本 + 确认交互单测（signal_ledger/confirm——用临时文件不污染真实数据）"""

import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import (
    confirm as cf,  # pyright: ignore 假阴性（pytest 实测通过）
)
from tools.strategy_engine import signal_ledger as sl

TMP = tempfile.mkdtemp()
sl.LEDGER_FILE = os.path.join(TMP, "ledger.jsonl")


def test_record_event():
    ev = sl.record("600036", name="招商银行", sig_type="score_pass",
                   price=38.46, reason="Q12 达标", track="base")
    assert ev["type"] == "score_pass" and ev["code"] == "600036"
    assert ev["direction"] == "buy" and ev["track"] == "base"
    assert ev["verify_at"] > "2026-01-01"  # 3 个月验证窗


def test_record_unknown_type():
    try:
        sl.record("600036", sig_type="nope")
        assert False, "应拒绝未知类型"
    except AssertionError:
        pass


def test_backfill_and_report():
    for code, px in [("600036", 40.0), ("600519", 1300.0)]:
        sl.record(code, sig_type="score_pass", price=px, reason="t",
                  verify_at="2020-01-01")  # 强制到期（verify_at 覆盖）
    # 用 provider mock 回填已到期行
    # 手动构造：直接改文件太麻烦——用 provider mock 回填已到期行
    sl.backfill(quotes_provider=lambda code: 42.0 if code == "600036" else 1200.0)
    r = sl.report()
    assert r["verified"] >= 2
    g = r["groups"]["score_pass"]
    assert g["n"] >= 2
    # 600036 买 40 → 42 = +5%；600519 1300 → 1200 = -7.7% → 1 胜 1 负
    assert 0 < g["win_rate"] < 100


def test_append_pending_and_dedup():
    cf.PENDING_FILE = os.path.join(TMP, "pending.json")
    sig = {"code": "600036", "name": "招商银行", "price": 38.46,
           "score": 94.5, "threshold": 80, "track": "base"}
    ok, _ = cf.append_pending(sig, total_assets=100000)
    assert ok
    items = cf.list_pending()
    assert items[0]["shares"] == 200  # 10万×10%/38.46=260→整百200
    # 去重
    ok2, msg = cf.append_pending(sig, total_assets=100000)
    assert not ok2 and "已" in msg


def test_execute_calls_portfolio():
    cf.PENDING_FILE = os.path.join(TMP, "pending2.json")
    sig = {"code": "600036", "name": "招商银行", "price": 38.46,
           "score": 94.5, "threshold": 80, "track": "base"}
    cf.append_pending(sig, total_assets=100000)
    item = cf.list_pending()[0]
    with patch("tools.strategy_engine.portfolio.Portfolio") as mock_pf:
        mock_pf().buy.return_value = (True, "ok")
        cf._execute(item)
        mock_pf().buy.assert_called_once()
    assert item["status"] == "confirmed"
