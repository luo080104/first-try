"""动态打分单测（strategy_score——Q12：四维/门槛/否决/金融豁免/估值边界）"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import strategy_score as ss


def _good_f():
    """优质底仓基本面（茅台类——非金融）"""
    return {
        "roe": 30.0,
        "sales_margin": 50.0,
        "debt_ratio": 15.0,
        "ocf_gt_profit": True,
        "dividend_yield": 3.0,
        "growth_ok": True,
        "debt_exempt": False,
    }


def _good_v():
    return {"pe_ttm": 20.0, "pb": 5.0, "pe_percentile": 20.0, "fair_pe": 25.0}


def _good_t():
    return {"boll_lower": True, "rsi_bottom": True, "td_buy": True, "vol_bottom": True}


def test_full_score_high():
    """四维全优 → 高分（价值 40 满分附近 + 估值 + 技术 + 票源）"""
    r = ss.score_stock(
        _good_f(),
        _good_v(),
        _good_t(),
        {"bigv_holding": True, "is_leader": True},
        quote={"pe_ttm": 20.0, "pb": 5.0},
        market_status="正常",
    )
    assert not r.vetoed
    assert r.total >= 80  # 高分通过正常门槛


def test_threshold_dynamic():
    """动态门槛：低潮 70 / 正常 80 / 高潮 88"""
    assert ss.THRESHOLD_MAP == {"低潮": 70, "正常": 80, "高潮": 88}
    r = ss.score_stock(_good_f(), _good_v(), {}, {}, quote={}, market_status="低潮")
    assert r.threshold == 70


def test_veto_no_buy():
    """硬否决：不买清单命中（N2 三高）→ 0 分（烂票永远不买）"""
    r = ss.score_stock(
        {}, {}, {}, {}, quote={"pe_ttm": 40, "pb": 6, "ps": 12}, market_status="正常"
    )
    assert r.vetoed and r.total == 0.0
    assert any("N2" in v for v in r.veto_reasons)


def test_financial_exempt_value():
    """金融豁免（审查修复 2026-08-15）：银行负债率 90% 但 exempt → 负债 5 分不惩罚"""
    f = _good_f()
    f["debt_ratio"] = 90.0
    f["debt_exempt"] = True
    r = ss.score_stock(
        f, _good_v(), {}, {}, quote={"pe_ttm": 20, "pb": 5}, market_status="正常"
    )
    labels = [p[0] for p in r.parts if len(p) == 2]
    assert any("金融豁免" in l for l in labels)  # 豁免标注在分项 label
    # 负债分贡献 5 分（对比非豁免同数据为 0）
    f2 = _good_f()
    f2["debt_ratio"] = 90.0
    f2["debt_exempt"] = False
    r2 = ss.score_stock(
        f2, _good_v(), {}, {}, quote={"pe_ttm": 20, "pb": 5}, market_status="正常"
    )
    assert (
        r.total - r2.total == 4.0
    )  # 豁免 = 多 4 分（负债权重 5→4——v2 分红率 5 分新增）


def _flat_parts(r):
    """parts 归一（tuple 结构 (name, p) 或 (name, p, note)）"""
    out = []
    for p in r.parts:
        if len(p) == 2:
            out.append((p[0], p[1], ""))
        else:
            out.append(p)
    return out


def test_valuation_band_fix():
    """估值边界（2026-08-15 分段线性化）：PE 30 → 3.3 分（25-40 线性段——原 5 分档）"""
    v = _good_v()
    v["pe_ttm"] = 30.0  # 25-40 区间
    v["pb"] = 6.0
    r = ss.score_stock(
        _good_f(), v, {}, {}, quote={"pe_ttm": 30.0, "pb": 6.0}, market_status="正常"
    )
    parts = _flat_parts(r)
    # 分段线性：PE30 → 5-(30-25)/15*5 = 3.33（原 5 分档——线性后更连续）
    pe_part = next(p for name, p, _ in parts if "PE=" in name)
    assert abs(pe_part - 3.33) < 0.1


def test_industry_face():
    """行业面（书 L3098——2026-08-17）：传入真实行业分 / 缺失给中性不惩罚"""
    from tools.strategy_engine.strategy_score import _score_industry

    # 缺失/失败 → 中性 10 分（Q6：不因数据失败惩罚）
    r = _score_industry(None)
    assert abs(r[0][0] - 10.0) < 0.01
    r2 = _score_industry({"error": "行业映射失败"})
    assert abs(r2[0][0] - 10.0) < 0.01
    # 真实行业分（公用——格局 8 满）
    ind = {"total": 17.5, "parts": [(8.0, "格局公用"), (5.5, "行业PE 18"), (2.0, "3年波动率"), (2.0, "政策面")]}
    r3 = _score_industry(ind)
    assert abs(sum(p for p, _ in r3) - 17.5) < 0.01
    # score_stock 总入口：industry 参数透传——传入真实行业分比中性多 7.5（17.5-10）
    s0 = ss.score_stock(_good_f(), _good_v(), {}, {}, quote={}, market_status="正常", industry=None)
    s1 = ss.score_stock(_good_f(), _good_v(), {}, {}, quote={}, market_status="正常", industry=ind)
    assert abs(s1.total - s0.total - 7.5) < 0.01


def test_industry_position_danjuan():
    """行业位置 v1（蛋卷百分位——2026-08-17）：高位扣分/低位加分"""
    from tools.strategy_engine import industry as ind

    # 金融（中证银行 81% 高位）→ 位置 1.5
    ind._eva_cache = {"SZ399986": {"pe_percentile": 0.81, "pe": 6.5}}
    r = ind.score_industry("sh.600036")
    pos = [p for p in r["parts"] if "百分位" in p[1]]
    assert pos and abs(pos[0][0] - 1.5) < 0.01
    # 低位（20%）→ 6 分满分
    ind._eva_cache = {"SZ399986": {"pe_percentile": 0.2, "pe": 6.5}}
    r2 = ind.score_industry("sh.600036")
    pos2 = [p for p in r2["parts"] if "百分位" in p[1]]
    assert pos2 and abs(pos2[0][0] - 6.0) < 0.01
    ind._eva_cache = None
