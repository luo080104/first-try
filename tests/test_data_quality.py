"""data_quality 单测（第六批收官——MAD 异常值/数据延迟/质量等级）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import data_quality as dq


def _normal_series(n: int = 100) -> list[float]:
    """正常价格序列（小幅振荡）"""
    import math

    closes = [100.0]
    for i in range(1, n):
        closes.append(closes[-1] * (1 + 0.005 * math.sin(i / 4)))
    return closes


def test_normal_series_clean():
    """正常序列 → 无异常"""
    issues = dq.check_price_series(_normal_series())
    assert issues == []


def test_mad_outlier_detected():
    """插入跳空（+20%——超 A 股涨跌停）→ MAD 检出"""
    prices = _normal_series()
    prices[50] = prices[49] * 1.20  # 单日 +20% 跳空
    issues = dq.check_price_series(prices)
    assert any(i["test"] == "MAD异常值" for i in issues)


def test_missing_gap_detected():
    """日期缺口（>5 天）→ 连续缺失警告"""
    dates = [f"2026-08-{i:02d}" for i in range(1, 41)]
    dates = [*dates[:10], "2026-08-20", *dates[11:]]  # 8/11→8/20 缺口 9 天
    issues = dq.check_price_series(_normal_series(40), dates)
    assert any(i["test"] == "连续缺失" for i in issues)


def test_holiday_gap_exempt(monkeypatch):
    """节假日缺口（春节 11 天——0 交易日）→ 不误报（2026-08-15 修复）"""
    # 春节 2/13→2/24（2026 春节 2/16-2/23 休市——0 交易日缺失）
    dates = ["2026-02-13", "2026-02-24", "2026-02-25", "2026-02-26", "2026-02-27"]
    prices = [100.0, 101.0, 102.0, 103.0, 104.0]
    issues = dq.check_price_series(prices, dates)
    assert not any(i["test"] == "连续缺失" for i in issues)


def test_calendar_failure_skips_gap_check(monkeypatch):
    """日历拉取失败 → 缺失检查跳过（不误报——宁可不查不可误报）"""
    monkeypatch.setattr(dq, "_trade_dates", lambda: set())
    dates = [f"2026-08-{i:02d}" for i in range(1, 41)]
    dates = [*dates[:10], "2026-08-20", *dates[11:]]  # 有 9 天缺口
    issues = dq.check_price_series(_normal_series(40), dates)
    assert not any(i["test"] == "连续缺失" for i in issues)


def test_data_delay():
    """最新数据 10 天前 → 延迟警告"""
    import datetime

    old = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    r = dq.check_data_delay(old)
    assert r is not None and r["test"] == "数据延迟"
    assert dq.check_data_delay(datetime.date.today().isoformat()) is None


def test_quality_levels():
    """等级汇总：critical→ERROR / warning→SUSPICIOUS / 空→GOOD"""
    assert dq.quality_level([]) == "GOOD"
    assert dq.quality_level([{"severity": "warning"}]) == "SUSPICIOUS"
    assert dq.quality_level([{"severity": "critical"}]) == "ERROR"


def test_quality_summary_shape():
    """摘要结构完整"""
    s = dq.quality_summary(_normal_series(), last_date="2026-08-14")
    assert s["level"] in ("GOOD", "SUSPICIOUS", "ERROR")
    assert isinstance(s["issues"], list)
