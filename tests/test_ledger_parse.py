"""ledger_parse 单测（P1-3——对话式记账解析——规则兜底路径）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tools.strategy_engine.ledger_parse import confirm_text, parse_trade


def test_buy_amount():
    """'买了 5000 茅台' → 买入/5000元/茅台"""
    r = parse_trade("买了 5000 茅台")
    assert r["action"] == "买入"
    assert r["amount"] == 5000
    assert r["stock"] == "茅台"


def test_sell_shares_price():
    """'卖出 200 股 平安 @ 51.7' → 卖出/200股/@51.7——金额不误抓价格"""
    r = parse_trade("卖出 200 股 平安 @ 51.7")
    assert r["action"] == "卖出"
    assert r["shares"] == 200
    assert r["price"] == 51.7
    assert r["amount"] == 0


def test_wan_unit():
    """'买入 2万 神华' → 20000 元（万单位换算）"""
    r = parse_trade("买入 2万 神华")
    assert r["amount"] == 20000


def test_unrelated_text():
    """无关内容 → 忽略/空（不猜——回问确认）——LLM 返回'忽略'或规则兜底空"""
    r = parse_trade("今天天气不错")
    assert r["action"] in ("", "忽略")
    assert r["amount"] == 0 and r["shares"] == 0


def test_add_position_synonym():
    """同义词归一：加仓/减仓"""
    assert parse_trade("加仓 5000元 招行")["action"] == "加仓"
    assert parse_trade("减仓 100 股中信证券")["action"] == "减仓"


def test_confirm_text():
    """确认回显：'确认：买入 茅台 5000元？'"""
    r = parse_trade("买了 5000 茅台")
    assert confirm_text(r) == "确认：买入 茅台 5000元？"
