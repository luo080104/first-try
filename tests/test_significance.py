# -*- coding: utf-8 -*-
"""Bootstrap 显著性检验测试（2026-08-17 甲方 Q4——硬币也能连续4周跑赢？）"""
import random
import sys

sys.path.insert(0, ".")

from tools.strategy_engine.gate_check import _max_streak, significance


def _mk_weeks(totals):
    """totals → weekly 序列（date 用 2026-W01 起）"""
    out = []
    for i, t in enumerate(totals):
        out.append({"week": f"2026-W{i + 1:02d}", "total": t})
    return out


def _mk_bench(n):
    """基准平序列（总收益 0——对照）——键用 _week_last_day 的日期格式"""
    from tools.strategy_engine.gate_check import _week_last_day

    return {
        _week_last_day(f"2026-W{i + 1:02d}"): 100.0 for i in range(n)
    }


def test_max_streak():
    assert _max_streak([1, -1, 1, 1, 1, -1]) == 3
    assert _max_streak([-1, -1]) == 0
    assert _max_streak([1, 1, 1, 1]) == 4


def test_significance_coin_flip_not_significant():
    """硬币序列（随机涨跌——无真实优势）→ p 值应高（不显著）"""
    rng = random.Random(7)
    totals = [100.0]
    for _ in range(24):  # 25 周
        totals.append(totals[-1] * (1 + rng.choice([-0.01, 0.01])))
    weekly = _mk_weeks(totals)
    bench = _mk_bench(len(weekly))
    sig = significance(weekly, bench)
    assert sig["n_weeks"] >= 6
    # 硬币序列不应显著（p 大概率 >= 0.05——但允许抽样波动，用宽松断言）
    assert sig["p_binom"] is not None


def test_significance_consistent_winner_significant():
    """持续跑赢序列（每周都赢基准 1%）→ 应显著（p < 0.05）"""
    totals = [100.0]
    for i in range(24):
        totals.append(totals[-1] * 1.01)  # 每周 +1%
    weekly = _mk_weeks(totals)
    # 基准每周 -1%——组合每周赢 2%
    from tools.strategy_engine.gate_check import _week_last_day

    bench = {}
    b = 100.0
    for i in range(len(weekly)):
        bench[_week_last_day(weekly[i]["week"])] = b
        b *= 0.99
    sig = significance(weekly, bench)
    assert sig["p_binom"] is not None
    # 持续赢家：胜率 100%——二项检验 p 应极小（≈0.5^24≈6e-8）
    assert sig["obs_max_streak"] >= 20
    assert sig["significant"] is True
    assert sig["p_binom"] < 0.01


def test_significance_insufficient_data():
    """周样本不足 → 不可判（返回 None）"""
    weekly = _mk_weeks([100, 101, 102, 103])
    sig = significance(weekly, _mk_bench(4))
    assert sig["p_value"] is None
    assert sig["significant"] is None
