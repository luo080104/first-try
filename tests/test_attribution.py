"""归因拆解单测（attribution.py——2026-08-15 整改①——合成数据验证）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import attribution as att


def _synthetic(beta: float, alpha_daily: float, n: int = 60, seed: int = 42) -> tuple[list, list]:
    """构造合成数据：市场收益 + 组合收益 = beta×市场 + alpha + 噪声

    返回 (equity_curve, bench_daily)——净值从 100 开始累计
    """
    import random

    rng = random.Random(seed)
    market = [rng.uniform(-0.02, 0.02) for _ in range(n)]
    noise = [rng.uniform(-0.005, 0.005) for _ in range(n)]
    port = [beta * m + alpha_daily + e for m, e in zip(market, noise)]

    # 净值序列（从 100 累计）——日期连续（2026-06-01 起）
    eq = []
    total = 100.0
    bench = []
    bclose = 4000.0
    import datetime

    d0 = datetime.date(2026, 6, 1)
    for i, (p, m) in enumerate(zip(port, market)):
        d = (d0 + datetime.timedelta(days=i)).isoformat()
        total *= 1 + p
        bclose *= 1 + m
        eq.append({"date": d, "total": round(total, 4)})
        bench.append({"date": d, "close": round(bclose, 4)})
    return eq, bench


def test_beta_1_2_positive_alpha():
    """已知 Beta=1.2 + 正 Alpha → 还原 Beta 误差 <5% + Alpha 符号正确"""
    eq, bench = _synthetic(beta=1.2, alpha_daily=0.001)  # 0.1%/日 ≈ +25%/年
    r = att.attribution(eq, bench)
    assert r["beta_market"] is not None
    assert abs(r["beta_market"] - 1.2) / 1.2 < 0.05, f"Beta 还原误差过大: {r['beta_market']}"
    assert r["alpha_positive"] is True
    assert r["alpha_annual"] > 10  # 年化 >10%


def test_beta_0_8_negative_alpha():
    """Beta=0.8 + 负 Alpha → alpha_positive=False（判定不通过的关键条件）"""
    eq, bench = _synthetic(beta=0.8, alpha_daily=-0.001)
    r = att.attribution(eq, bench)
    assert abs(r["beta_market"] - 0.8) / 0.8 < 0.05
    assert r["alpha_positive"] is False


def test_insufficient_points():
    """不足 10 个对齐点 → 数据不足（显式标注——红线⑤不静默）"""
    eq = [{"date": f"2026-06-{i:02d}", "total": 100 + i} for i in range(1, 6)]
    bench = [{"date": f"2026-06-{i:02d}", "close": 4000 + i} for i in range(1, 6)]
    r = att.attribution(eq, bench)
    assert r["beta_market"] is None
    assert "数据不足" in r["note"] or "不足" in r["note"]


def test_no_overlap_dates():
    """零重叠日期 → 显式缺口标注（不静默）"""
    eq = [{"date": "2026-07-01", "total": 100}, {"date": "2026-07-02", "total": 101}]
    bench = [{"date": "2026-06-01", "close": 4000}, {"date": "2026-06-02", "close": 4001}]
    r = att.attribution(eq, bench)
    assert r["beta_market"] is None
    assert "对齐" in r["note"] or "不足" in r["note"]
