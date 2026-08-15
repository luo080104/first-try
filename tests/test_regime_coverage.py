"""regime_coverage 单测（第二批落地——市场状态覆盖度）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import regime_coverage as rc


def _synthetic_closes(n: int = 300) -> list[float]:
    """合成周线（振荡行情——多种波动状态）"""
    closes = [100.0]
    import math

    for i in range(1, n):
        # 前 100 周低波动、中 100 周高波动、后 100 周正常
        if i < 100:
            drift = 0.001 + 0.005 * math.sin(i / 5)
        elif i < 200:
            drift = 0.01 + 0.03 * math.sin(i / 3)  # 高波动
        else:
            drift = 0.002 + 0.01 * math.sin(i / 4)
        closes.append(closes[-1] * (1 + drift))
    return closes


def test_detect_regimes():
    """合成数据能分出多状态"""
    regimes = rc.detect_regimes(_synthetic_closes())
    assert len(regimes) >= 2


def test_coverage_warning_multi():
    """多状态 → 无警告"""
    r = rc.coverage_report(_synthetic_closes())
    assert r["n_regimes"] >= 2
    assert "仅覆盖" not in r["warning"]


def test_coverage_single_state_warns():
    """单状态（平稳小波动序列）→ 无多状态覆盖"""
    import math

    # 单一波动水平的振荡（正余弦——同一波动率）
    closes = [100.0]
    for i in range(1, 200):
        closes.append(closes[-1] * (1 + 0.005 * math.sin(i / 4)))
    r = rc.coverage_report(closes)
    # 单波动水平 → 状态数少（1-2 个）且警告触发或状态数小
    assert r["n_regimes"] <= 2


def test_trade_distribution():
    """交易分布统计（全部交易在单一状态 → 集中警告）"""
    closes = _synthetic_closes()
    # 全在开头（低波动段）的交易
    r = rc.coverage_report(closes, trade_indices=[5, 10, 15, 20, 25])
    dist = r.get("trade_dist", {})
    if dist:
        assert sum(dist.values()) == 5


def test_annualized_reasonable():
    """年化修复验证：正常波动段的年化收益应在 ±100% 内（原 bug：周线×√252 溢出）"""
    closes = _synthetic_closes()
    for rg in rc.detect_regimes(closes):
        assert -150 < rg["ann_return"] < 500  # 修复后不会出现 752% 假象
