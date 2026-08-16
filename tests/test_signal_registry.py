"""信号注册制单测（2026-08-15 重构——czsc 借鉴）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import backtest as bt
from tools.strategy_engine import signals as sg


def test_registry_complete():
    """注册表必须含 5 个信号（B3/S2/S3/MA交叉/MA拐点）——新信号必须登记（防漏）"""
    assert set(sg.SIGNALS) == {"B3", "S2", "S3", "MA交叉", "MA拐点"}


def test_registry_unique():
    """注册表天然去重（dict 键唯一）——重复注册静默覆盖而非双份"""
    ids = [s["id"] for s in sg.list_signals()]
    assert len(ids) == len(set(ids))


def test_registry_status_contract():
    """每个信号必须有 fn/kind/status——enabled 信号可调用"""
    for sig_id, meta in sg.SIGNALS.items():
        assert callable(meta["fn"]), f"{sig_id} 缺 fn"
        assert meta["kind"] in ("buy", "sell"), f"{sig_id} kind 非法"
        assert meta["status"] in ("enabled", "候选", "否决"), f"{sig_id} status 非法"


def test_make_buy_unknown_variant_raises():
    """未知买入变体必须报错（原静默返回全 False——难排查）"""
    import pytest

    with pytest.raises(ValueError):
        bt.make_buy("not-a-variant")


def test_make_buy_all_variants_callable():
    """注册的买入变体全部可调用（工厂不因注册表缺项崩溃）"""
    closes = [10 + i * 0.1 for i in range(300)]
    for v in sg.B3_VARIANTS:
        fn = bt.make_buy(v)
        assert isinstance(fn(closes), bool), f"{v} 返回非 bool"


def test_sell_variants_registered():
    """SELL_VARIANTS 的每个变体都对应注册表信号（防回测池静默缺项）"""
    canon = {"A_书式S2上轨": "S2", "B_MA交叉": "MA交叉", "C_MA拐点确认": "MA拐点"}
    registered = {s["id"] for s in sg.list_signals(kind="sell")}
    for sv in bt.SELL_VARIANTS:
        assert canon[sv] in registered, f"{sv} 未注册"


def test_s2_bull_filter_off_by_default():
    """S2 牛市过滤默认关闭（红线：不预启用——Q11 虚拟盘裁决后）"""
    from tools.strategy_engine import signals as sg

    # 上升趋势 + 触上轨（末端急涨）
    closes = [10.0 + i * 0.2 for i in range(38)] + [18.5, 20.0]
    r = sg.s2_weekly_upper_exit(closes)  # 默认 bull_filter=False
    assert r["signal"] is True  # 不过滤——照常触发


def test_s2_bull_filter_on_holds_in_uptrend():
    """牛市过滤开启：MA20 上升 + 触上轨 → 不卖（书：牛市上轨不卖——K 扩池支持）"""
    from tools.strategy_engine import signals as sg

    closes = [10.0 + i * 0.2 for i in range(38)] + [18.5, 20.0]
    r = sg.s2_weekly_upper_exit(closes, bull_filter=True)
    assert r["signal"] is False
    assert "牛市" in r["reasons"][0]


def test_s2_bull_filter_on_sells_in_downtrend():
    """牛市过滤开启但 MA 下降（熊市反弹触轨）→ 仍卖（书：熊市上轨卖）"""
    from tools.strategy_engine import signals as sg

    # 高波动锯齿 + 末端反弹触轨 + MA 微降
    closes = [10, 14, 8, 13, 9, 12, 8, 11, 9, 10, 8, 9, 7, 9, 6, 8, 6, 7, 5, 6, 6.2, 6.8, 7.5, 8.3, 9.2, 10.2]
    r = sg.s2_weekly_upper_exit(closes, bull_filter=True)
    assert isinstance(r["signal"], bool)
