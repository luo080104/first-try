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
    assert p.data["cash"] == pf.INIT_CASH == 80000
    assert p.data["holdings"] == {}


def test_buy_and_sell():
    p = pf.Portfolio(os.path.join(TMP, "t2.json"))
    ok, _ = p.buy("600036", 38.46, 1300, track="base", name="招商银行", force=True)  # F1 硬约束上线——记账测试显式越过（约束另有专门用例）
    assert ok
    assert p.data["cash"] == round(80000 - 38.46 * 1300, 2)
    assert p.data["holdings"]["600036"]["shares"] == 1300
    assert p.data["holdings"]["600036"]["track"] == "base"
    # 卖出
    ok, _ = p.sell("600036", 500, 39.5)
    assert ok
    assert p.data["holdings"]["600036"]["shares"] == 800
    assert p.data["cash"] == round(80000 - 38.46 * 1300 + 39.5 * 500, 2)
    # 事件日志（实例跟随——临时目录——不污染真实事件流——2026-08-15 修复）
    events = [json.loads(l) for l in open(p.events_file, encoding="utf-8")]
    assert [e["action"] for e in events[-2:]] == ["buy", "sell"]
    assert events[-2]["track"] == "base"


def test_track_accounting():
    p = pf.Portfolio(os.path.join(TMP, "t3.json"))
    p.buy(
        "600036", 38.46, 500, track="base", name="招行", force=True
    )  # 500 股 19230——F1 硬约束上线——记账测试显式越过
    p.buy(
        "600519", 1341.99, 40, track="swing", name="茅台", force=True
    )  # 40 股 53679.6——F1 硬约束上线——记账测试显式越过
    assert p.data["track"]["base"] == 19230
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
    p.buy("600036", 38.46, 1300, track="base", name="招商银行", force=True)  # F1 硬约束——记账测试显式越过
    s = p.summary()  # 无行情——按成本价估值
    assert s["n_holdings"] == 1
    assert s["total"] == pf.INIT_CASH
    assert not s["cash_ok"]  # 现金 50%——超出 15% 上限


def test_hard_constraint_f1():
    """F1 硬约束（2026-08-17 审核）：超限拒绝——force 显式越过"""
    p = pf.Portfolio(os.path.join(TMP, "t6.json"))
    # 建仓 500 股招行（19230=24%——超 10% 上限）→ 拒绝
    ok, msg = p.buy("600036", 38.46, 500, track="base", name="招行")
    assert not ok and "约束未过" in msg and "P1" in msg
    # force 显式越过 → 成功
    ok2, _ = p.buy("600036", 38.46, 500, track="base", name="招行", force=True)
    assert ok2
    # 再买同股（24%+24%=48%——超限拒绝——即使 force=False 正常路径）
    ok3, msg3 = p.buy("600036", 38.46, 100, track="base", name="招行")
    assert not ok3 and "P1" in msg3
