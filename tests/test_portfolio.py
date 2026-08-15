"""虚拟盘记账单测（portfolio.py——建仓/卖出/约束——用临时文件不污染真实账本）"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import portfolio as pf

TMP = tempfile.mkdtemp()


def test_init_cash():
    p = pf.Portfolio(os.path.join(TMP, "t1.json"))
    assert p.data["cash"] == pf.INIT_CASH == 100000
    assert p.data["holdings"] == {}


def test_buy_and_sell():
    p = pf.Portfolio(os.path.join(TMP, "t2.json"))
    ok, _ = p.buy("600036", 38.46, 1300, track="base", name="招商银行")
    assert ok
    assert p.data["cash"] == round(100000 - 38.46 * 1300, 2)
    assert p.data["holdings"]["600036"]["shares"] == 1300
    assert p.data["holdings"]["600036"]["track"] == "base"
    # 卖出
    ok, _ = p.sell("600036", 500, 39.5)
    assert ok
    assert p.data["holdings"]["600036"]["shares"] == 800
    assert p.data["cash"] == round(100000 - 38.46 * 1300 + 39.5 * 500, 2)
    # 事件日志（全局文件——断言最后两个事件）
    events = [json.loads(l) for l in open(pf.EVENTS_FILE, encoding="utf-8")]
    assert [e["action"] for e in events[-2:]] == ["buy", "sell"]
    assert events[-2]["track"] == "base"


def test_track_accounting():
    p = pf.Portfolio(os.path.join(TMP, "t3.json"))
    p.buy("600036", 38.46, 1000, track="base", name="招行")
    p.buy(
        "600519", 1341.99, 40, track="swing", name="茅台"
    )  # 40 股 53679.6 < 剩余 61540
    assert p.data["track"]["base"] == 38460
    assert p.data["track"]["swing"] == 53679.6


def test_constraints():
    p = pf.Portfolio(os.path.join(TMP, "t4.json"))
    # P1：单只超限（13 万一股买 1 股 = 10 万全仓 >10% 上限）
    issues = p.check_constraints("600519", 100000, 1)
    assert any("P1" in i for i in issues)
    # 现金不足
    ok, msg = p.buy("600519", 100000, 2, track="base")
    assert not ok and "现金不足" in msg
    # Q4：5 只上限
    for i, code in enumerate(
        ["600036", "600519", "601318", "600028", "601088", "600900"]
    ):
        p.buy(code, 10 + i, 100, track="base")
    issues = p.check_constraints("601857", 10, 100)
    assert any("Q4" in i for i in issues)


def test_summary():
    p = pf.Portfolio(os.path.join(TMP, "t5.json"))
    p.buy("600036", 38.46, 1300, track="base", name="招商银行")
    s = p.summary()  # 无行情——按成本价估值
    assert s["n_holdings"] == 1
    assert s["total"] == pf.INIT_CASH
    assert not s["cash_ok"]  # 现金 50%——超出 15% 上限
