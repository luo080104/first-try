"""backtest 事件配对 + 涨跌停单测（2026-08-15 回测真实性修复）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import backtest as bt


def _weeks_with(opens: list[float], closes: list[float]) -> list[dict]:
    """构造周线数据（open/close）"""
    return [
        {"date": f"2026-01-{i + 1:02d}", "open": o, "close": c}
        for i, (o, c) in enumerate(zip(opens, closes))
    ]


def test_limit_blocked_buy():
    """涨停封板买单拦截（前收 10 → 开 11.2 = +12%）"""
    weeks = _weeks_with([11.2], [11.0])
    weeks.insert(0, {"date": "2026-01-00", "open": 10.0, "close": 10.0})
    assert bt._limit_blocked(weeks, 1, is_buy=True)
    assert not bt._limit_blocked(weeks, 1, is_buy=False)


def test_limit_blocked_sell():
    """跌停封板卖单拦截（前收 10 → 开 8.8 = -12%）"""
    weeks = _weeks_with([8.8], [9.0])
    weeks.insert(0, {"date": "2026-01-00", "open": 10.0, "close": 10.0})
    assert bt._limit_blocked(weeks, 1, is_buy=False)
    assert not bt._limit_blocked(weeks, 1, is_buy=True)


def test_limit_blocked_normal():
    """正常波动不拦截（前收 10 → 开 10.5 = +5%）"""
    weeks = _weeks_with([10.5], [10.5])
    weeks.insert(0, {"date": "2026-01-00", "open": 10.0, "close": 10.0})
    assert not bt._limit_blocked(weeks, 1, is_buy=True)
    assert not bt._limit_blocked(weeks, 1, is_buy=False)


def test_simulate_signal_pairing():
    """信号配对：买入前的老卖点不挡新持仓的卖点（2026-08-15 修复）"""
    # 40+ 周数据：早期有个卖点信号，之后买点→卖点应正常配对
    n = 60
    closes = [10.0 + i * 0.1 for i in range(n)]
    opens = closes[:]
    weeks = _weeks_with(opens, closes)
    # 买点 @35，卖点 @40（在买点之后）；另有一个老卖点 @32（买点之前）
    events = [
        {"i": 35, "type": "buy"},
        {"i": 32, "type": "sell"},  # 老卖点（应在建仓时跳过）
        {"i": 40, "type": "sell"},
    ]
    res = bt._simulate(weeks, opens, events)
    # 应成交 1 笔（@35 买 → @40 卖）——老卖点 @32 被跳过
    assert res["trades"] == 1, f"应 1 笔（老卖点被跳过）——实际 {res['trades']}"


def test_simulate_buy_retry_on_limit():
    """涨停日买入顺延（信号不丢——下一周成交）"""
    n = 60
    closes = [10.0 + i * 0.1 for i in range(n)]
    opens = closes[:]
    weeks = _weeks_with(opens, closes)
    # 买点 @35——但 @35 是涨停（前收 10 开 12）→ 顺延到 @36 成交
    weeks[34]["close"] = 10.0
    weeks[35]["open"] = 12.0  # +20% 涨停
    # 买点 @35 + 卖点 @40（平仓才能记交易——2026-08-15 测试修正）
    events = [{"i": 35, "type": "buy"}, {"i": 40, "type": "sell"}]
    res = bt._simulate(weeks, opens, events)
    assert res["trades"] == 1  # 顺延后成交（不丢单）
    assert res["avg_ret"] > 0  # 买 @36 卖 @40——上涨段——正收益


def test_buy_signal_not_expired_during_limit_chain():
    """R1 审查修复：触板顺延中信号不因有效期丢弃（5周涨停后第6周应成交）"""
    n = 60
    closes = [10.0 + i * 0.1 for i in range(n)]
    opens = closes[:]
    weeks = _weeks_with(opens, closes)
    # 买点 @35——35-39 连续 5 周涨停 → 40 周恢复可成交
    weeks[34]["close"] = 10.0
    for i in range(35, 40):
        weeks[i]["open"] = 12.0
        weeks[i - 1]["close"] = 10.0
    events = [{"i": 35, "type": "buy"}, {"i": 45, "type": "sell"}]
    res = bt._simulate(weeks, opens, events)
    assert res["trades"] == 1  # 顺延 5 周后第 6 周成交（不丢弃）


def test_buy_signal_expires_when_holding_blocked():
    """有效期语义保持：持仓期间信号未成交——卖出后超期丢弃"""
    n = 60
    closes = [10.0 + i * 0.1 for i in range(n)]
    opens = closes[:]
    weeks = _weeks_with(opens, closes)
    # 买@30 成交 → 买@31 被持仓挡住 → 卖@45 → 买@31 已过 14 周 → 丢弃
    events = [{"i": 30, "type": "buy"}, {"i": 31, "type": "buy"}, {"i": 45, "type": "sell"}]
    res = bt._simulate(weeks, opens, events)
    assert res["trades"] == 1  # 只成交 30→45 一笔
