# -*- coding: utf-8 -*-
"""策略加载器（loader.py——YAML 策略库 → 引擎可执行结构——P1-2 落地）

策略库 v2 分离原则（方案红线）：core_rules 与策略分离——规则可复用/回测可追溯
- 卖出规则：sell_rules.yaml（S1-S7——父母理念翻译——"开工第一道坎"）
- 战略层（filters.py）直接启用（理念纪律无需回测）
- 战术层（signals.py）回测验证后启用（红线）

enabled 标记：已回测达标才 true（Q11 校准清单同步）
"""

from __future__ import annotations

import os
from typing import Any

import yaml

_DIR = os.path.dirname(os.path.abspath(__file__))

_cache: dict[str, Any] = {}


def load_rules(name: str) -> dict[str, Any]:
    """加载规则 YAML（缓存——重复调用不重读）——失败返回空结构（不抛——红线③）"""
    if name in _cache:
        return _cache[name]
    path = os.path.join(_DIR, f"{name}.yaml")
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        _cache[name] = data or {}
    except (OSError, yaml.YAMLError):
        _cache[name] = {}
    return _cache[name]


def enabled_exits() -> list[dict[str, Any]]:
    """已启用（回测达标）的卖出规则列表——core_loop 卖出检查用"""
    data = load_rules("sell_rules")
    return [
        {**r, "engine_params": r.get("engine_params", {})}
        for r in data.get("rules", [])
        if r.get("engine_params", {}).get("enabled")
    ]


def rule_by_id(rule_id: str) -> dict[str, Any] | None:
    """按 id 查规则（S1-S7）——未找到返回 None"""
    data = load_rules("sell_rules")
    for r in data.get("rules", []):
        if r.get("id") == rule_id:
            return r
    return None
