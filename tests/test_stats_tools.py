"""stats_tools 单测（统计检验——Bootstrap 胜率/差异/样本量）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import stats_tools as st


def test_winrate_significant():
    """9/11 胜率显著（B3 验证段实测——p<0.05）"""
    r = st.bootstrap_winrate(wins=9, n=11, baseline=0.5)
    assert r["significant"]
    assert r["p_value"] < 0.05


def test_winrate_insignificant_small():
    """小样本不显著（5/10 胜率——p 应 >0.05）"""
    r = st.bootstrap_winrate(wins=5, n=10, baseline=0.5)
    assert not r["significant"]


def test_diff_insignificant():
    """10 点差异 N=10 不显著（MA 三变体实测——p≈0.49）"""
    r = st.bootstrap_diff(n1=10, w1=0.70, n2=10, w2=0.60)
    assert not r["significant"]


def test_min_samples():
    """10 点差异需要大量样本（>100）——样本不足不判定的量化依据"""
    n = st.min_samples(0.10)
    assert n >= 100


def test_check_rule_verdict():
    """规则验证入口——显著/待积累判定"""
    r = st.check_rule("测试", wins=9, n=11)
    assert "✅" in r["verdict"]
    r2 = st.check_rule("测试2", wins=5, n=10)
    assert "⏳" in r2["verdict"]
