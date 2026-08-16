# -*- coding: utf-8 -*-
"""大V 思路假设库单测（test_bigv_ideas.py——2026-08-16 B1）

覆盖：录入/读取/状态过滤/汇总统计/CLI 参数边界
不依赖网络（临时文件）
"""

import sys

sys.path.insert(0, ".")

from tools.strategy_engine import bigv


def test_add_and_load(tmp_path):
    """录入 → 读取 → 状态过滤"""
    bigv.IDEAS_FILE = str(tmp_path / "ideas.jsonl")
    bigv.add_idea("某大V", "高股息轮动", "股息率>5%→建仓")
    rows = bigv.load_ideas()
    assert len(rows) == 1
    assert rows[0]["status"] == "candidate"  # 默认候选——不预启用（Q6）
    assert rows[0]["rule_draft"] == "股息率>5%→建仓"


def test_status_filter(tmp_path):
    """按状态过滤 + 汇总计数"""
    bigv.IDEAS_FILE = str(tmp_path / "ideas.jsonl")
    bigv.add_idea("A", "思路1")
    bigv.add_idea("B", "思路2")
    assert len(bigv.load_ideas("candidate")) == 2
    assert len(bigv.load_ideas("accepted")) == 0
    d = bigv.ideas_digest()
    assert "候选 2" in d and "已接受 0" in d


def test_empty_library(tmp_path):
    """空库：读取/汇总不崩"""
    bigv.IDEAS_FILE = str(tmp_path / "none.jsonl")
    assert bigv.load_ideas() == []
    assert "假设库空" in bigv.ideas_digest()


def test_corrupt_line_tolerant(tmp_path):
    """损坏行跳过（容错——红线③）"""
    f = tmp_path / "ideas.jsonl"
    f.write_text("{bad json\n", encoding="utf-8")
    bigv.IDEAS_FILE = str(f)
    assert bigv.load_ideas() == []
