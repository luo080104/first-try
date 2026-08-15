"""大V 模块单测（bigv——调仓记录/X 证据链评分/跟随≤20% 红线）"""

import json
import os
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import bigv as bv  # pyright: ignore
from tools.strategy_engine import portfolio as pf

TMP = tempfile.mkdtemp()
bv.TRADES_FILE = os.path.join(TMP, "trades.jsonl")


def test_record_and_disclosure():
    """记录调仓：有实质理由（≥20 字）= 披露 ✅；无理由 = ⚠️"""
    ev = bv.record_trade("超级鹿鼎公", "600036", "买", 38.0,
                         "高息股逻辑未变——银行低估加仓")
    assert ev["disclosed"]
    ev2 = bv.record_trade("超级鹿鼎公", "600519", "卖")
    assert not ev2["disclosed"]


def test_score_evidence_chain():
    """X 证据链：披露质量累计——无记录不评分（Q3 不提前分级）"""
    bv.record_trade("管我财", "600900", "买", 25.0, "长江电力——稳定现金流低估")
    bv.record_trade("管我财", "601088", "买", 30.0, "神华——高息低估值")
    s = bv.score_bigv("管我财")
    assert s["n_trades"] == 2 and s["score"] == 2.0  # 2 次披露 +1+1
    s0 = bv.score_bigv("山湖水")
    assert s0["score"] is None  # 无记录——不评分


def test_follow_candidates_only_buys():
    """跟随候选：只收买入（Q3——候选池）"""
    bv.record_trade("超级鹿鼎公", "600028", "买", 6.0, "石化——低估值高息")
    bv.record_trade("超级鹿鼎公", "600028", "卖", 6.5, "波段降本")
    cands = bv.follow_candidates()
    assert len(cands) == 1 and cands[0]["code"] == "600028"


def test_follow_cap_check():
    """跟随仓 ≤20% 红线（组合 10 万——跟随 1.5 万 = 15% ✅）"""
    with open(os.path.join(TMP, "portfolio.json"), "w", encoding="utf-8") as f:
        json.dump({"init_cash": 100000, "cash": 85000,
                   "holdings": {"600028": {"code": "600028", "name": "中国石化",
                                           "shares": 3000, "avg_cost": 5.0,
                                           "track": "bigv"}},
                   "track": {"base": 0.0, "swing": 0.0, "bigv": 15000}}, f)
    with patch("tools.strategy_engine.portfolio.Portfolio",
               lambda p=None: pf.Portfolio(os.path.join(TMP, "portfolio.json"))):
        cap = bv.follow_cap_check()
        assert cap["ok"] and cap["follow_pct"] <= 20.0
