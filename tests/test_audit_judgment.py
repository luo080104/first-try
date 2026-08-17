# -*- coding: utf-8 -*-
"""判定审计脚本测试（audit_judgment——2026-08-17 甲方 9/5 交付提前）"""
import sys

sys.path.insert(0, ".")

from tools.strategy_engine import audit_judgment as aj


def test_audit_rule_version():
    """规则版本审计：门槛 120 制 + 信号接线状态"""
    rv = aj.audit_rule_version()
    assert rv["打分 schema"] == "v2.1-120制（价值40+估值30+技术20+票源10+行业20）"
    assert rv["门槛（120 制）"]["正常"] == 96
    assert "B3" in rv["已接线信号"]
    assert "判定闸门" in rv and len(rv["判定闸门"]) >= 5


def test_audit_equity_curve_states():
    """净值三态审计——无标记旧数据正确识别"""
    # 用真实账本（或临时——此处直接测函数形状）
    eq = aj.audit_equity_curve()
    assert "总净值点" in eq
    assert "三态分布" in eq
    assert eq["判定可用性"].startswith(("✅", "⚠️"))


def test_run_audit_json(tmp_path, monkeypatch):
    """完整审计 JSON 结构 + 落盘"""
    import os

    import tools.strategy_engine.portfolio as pf

    monkeypatch.setattr(pf, "PORTFOLIO_FILE", str(tmp_path / "pf.json"))
    monkeypatch.setattr(pf, "EVENTS_FILE", str(tmp_path / "events.jsonl"))
    # 空账本也能审计（不崩）
    r = aj.run_audit(include_judgment=False)
    assert r["净值审计"]["总净值点"] == 0
    assert "规则版本" in r
    assert os.path.exists(r["审计文件"])
