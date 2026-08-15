"""v1.2 模块单测（price_watch / risk_dashboard / weekly_report）"""

import os
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import price_watch as pw
from tools.strategy_engine import risk_dashboard as rd


@pytest.fixture(autouse=True)
def _isolate_watch_file():
    """每个测试独立盯价文件（uuid 唯一——防跨测试污染）"""
    pw._WATCH_FILE = os.path.join(
        tempfile.mkdtemp(), f"watch_{uuid.uuid4().hex[:8]}.json"
    )
    yield
    if os.path.exists(pw._WATCH_FILE):
        try:
            os.remove(pw._WATCH_FILE)
        except OSError:
            pass


def test_price_watch_add_remove():
    """盯价添加/去重/移除"""
    assert pw.add("600036", 30.0, "below", "招行心理位")
    assert pw.add("600519", 1500.0, "above", "茅台冲高")
    assert not pw.add("600036", 28.0, "below")  # 同方向去重
    assert pw.remove("600036", "below")
    assert not pw.remove("600999", "below")  # 不存在


def test_price_watch_check_hit_and_dedupe():
    """命中→alerted 标记→防重复推送"""
    pw.add("600036", 999999, "below")  # 必跌破
    hits = pw.check()
    assert len(hits) == 1
    assert hits[0]["code"] == "600036"
    assert hits[0]["alerted"]
    assert pw.check() == []  # 防重复


def test_dashboard_shape():
    """仪表盘结构完整"""
    r = rd.dashboard()
    for k in ("total", "pnl", "cash_pct", "holdings", "positions", "alerts", "risk_ok"):
        assert k in r
    assert isinstance(r["alerts"], list)


def test_dashboard_alert_on_cash():
    """现金偏高 → 告警（当前 78% > 15%——闲置提示）"""
    r = rd.dashboard()
    assert any("现金" in a for a in r["alerts"])


def test_plot_ascii_curve():
    """ASCII 净值曲线渲染（纯 stdlib——进度可视化）"""
    from tools.strategy_engine.gate_check import _plot_ascii

    series = [
        {"date": f"2026-08-{d:02d}", "total": 100000 + i * 500}
        for i, d in enumerate(range(1, 16))
    ]
    out = _plot_ascii(series, width=30)
    assert "100,000" in out or "101" in out  # 起点标签
    assert "2026-08-01" in out and "2026-08-15" in out  # 首尾日期
    assert "*" in out  # 有点


def test_plot_ascii_too_few_points():
    """不足 2 个点 → 提示（不崩）"""
    from tools.strategy_engine.gate_check import _plot_ascii

    out = _plot_ascii([{"date": "2026-08-15", "total": 100000}])
    assert "不足" in out
