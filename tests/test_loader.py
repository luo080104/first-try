"""loader 单测（P1-1/P1-2——卖出规则 YAML + 加载器）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from tools.strategy_engine import loader


def test_sell_rules_loaded_seven():
    """卖出规则 S1-S7 全在（策略库 v2 卖出 7 条——不漏）"""
    data = loader.load_rules("sell_rules")
    ids = [r["id"] for r in data.get("rules", [])]
    assert ids == ["S1", "S2", "S3", "S4", "S5", "S6", "S7"]


def test_sell_rules_required_fields():
    """每条规则有 id/name/category/source/core_rules（书原文可追溯）"""
    for r in loader.load_rules("sell_rules").get("rules", []):
        assert r["id"].startswith("S")
        assert r["name"]
        assert r["category"] == "sell"
        assert r["source"]
        assert r["core_rules"]


def test_only_backtested_enabled():
    """未验证不落地红线：只有回测达标的 S2 enabled"""
    enabled = [r["id"] for r in loader.enabled_exits()]
    assert enabled == ["S2"]


def test_rule_by_id():
    """按 id 查询——命中/未命中"""
    s3 = loader.rule_by_id("S3")
    assert s3 is not None and s3["name"] == "valuation_premium_sell"
    assert loader.rule_by_id("S9") is None


def test_missing_yaml_returns_empty():
    """缺失 YAML 不抛异常（红线③容错）"""
    assert loader.load_rules("not_exist") == {}
