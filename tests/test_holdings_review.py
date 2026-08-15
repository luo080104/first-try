"""持仓季度体检单测（holdings_review——Q14：观察标记/连续两季换仓/拿住）"""

import os
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from contextlib import contextmanager

from tools.strategy_engine import holdings_review as hr  # pyright: ignore

TMP = tempfile.mkdtemp()
hr.REVIEW_FILE = os.path.join(TMP, "review.json")


def _mk_portfolio_with_holding():
    """临时账本：现金 5 万 + 招行 1300 股 @ 38.46"""
    import json
    d = {"init_cash": 100000, "cash": 50000,
         "holdings": {"600036": {"code": "600036", "name": "招商银行",
                                 "shares": 1300, "avg_cost": 38.46,
                                 "track": "base"}},
         "track": {"base": 50000, "swing": 0.0}}
    path = os.path.join(TMP, "portfolio.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(d, f)
    return path


@contextmanager
def _patch_env(score_total):
    """模拟环境：假行情 + 假打分（只测 Q14 判定逻辑——不测打分本身）"""
    import uuid
    hr.REVIEW_FILE = os.path.join(TMP, f"review_{uuid.uuid4().hex[:8]}.json")  # 每测独立——防顺序污染
    path = _mk_portfolio_with_holding()
    real_portfolio = hr.pf.Portfolio  # patch 前保存原类（避免 lambda 自递归）
    patches = [
        patch("tools.strategy_engine.portfolio.Portfolio",
              lambda p=path: real_portfolio(p)),
        patch("tools.strategy_engine.holdings_review.data.tencent_quote",
              lambda codes: {"600036": {"code": "600036", "name": "招商银行",
                                        "price": 38.0}}),
        patch("tools.strategy_engine.holdings_review._score_position",
              lambda code, q: SimpleNamespace(total=score_total)),
        patch("tools.strategy_engine.holdings_review.ms.market_status",
              lambda: {"status": "正常"}),
        patch.object(hr.ss, "THRESHOLD_MAP", {"正常": 80}),
    ]
    for p in patches:
        p.start()
    try:
        yield
    finally:
        for p in patches:
            p.stop()


def test_below_threshold_first_review():
    with _patch_env(63.0):
        results = hr.review_positions()
        r = results[0]
        assert r["score"] == 63.0 and r["below"]
        assert r["observe_streak"] == 1  # 首季观察标记
        assert not r["suggest_exit"]


def test_two_seasons_suggest_exit():
    with _patch_env(63.0):
        hr.review_positions()  # 第 1 季（观察 1）
        results = hr.review_positions()  # 第 2 季（仍跌破 → 换仓建议）
        r = results[0]
        assert r["observe_streak"] == 2
        assert r["suggest_exit"]  # 连续两季 → 建议换仓（甲方确认）


def test_recovery_keeps_holding():
    with _patch_env(85.0):
        hr.review_positions()  # 第 1 季观察后……
        results = hr.review_positions()  # 回升 85（≥80）→ 拿住
        r = results[0]
        assert not r["below"]
        assert r["observe_streak"] == 0
