# -*- coding: utf-8 -*-
"""雪球跟踪单测（test_xq_track.py——2026-08-16 大V 自动跟踪）

覆盖：调仓去重幂等（核心不变量——防重复入库）
     JSON 读写容错（红线③）
     status 摘要不崩
不依赖网络（mock 数据 + 临时目录）
"""

import sys

sys.path.insert(0, ".")

from tools.strategy_engine import xq_track as xq


def test_append_dedup(tmp_path):
    """同一 (bigv, code, ts, action) 只写一次——重跑不重复"""
    f = tmp_path / "trades.jsonl"
    xq.TRADES_FILE = str(f)
    ev = {"ts": "2026-08-16", "bigv": "管我财", "code": "广和通", "action": "买"}
    assert xq._append_trade_if_new(ev) is True
    assert xq._append_trade_if_new(ev) is False  # 幂等
    assert xq._append_trade_if_new(ev) is False
    assert sum(1 for _ in f.open(encoding="utf-8")) == 1
    # 不同 action 是另一条
    ev2 = dict(ev, action="卖")
    assert xq._append_trade_if_new(ev2) is True
    assert sum(1 for _ in f.open(encoding="utf-8")) == 2


def test_empty_code_rejected(tmp_path):
    """空股票代码不写（组合里可能有无代码条目）"""
    f = tmp_path / "trades.jsonl"
    xq.TRADES_FILE = str(f)
    ev = {"ts": "2026-08-16", "bigv": "某人", "code": "", "action": "买"}
    assert xq._append_trade_if_new(ev) is False
    assert not f.exists()


def test_json_io_fallback(tmp_path):
    """JSON 读写容错：损坏文件返回默认值、写失败不抛"""
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    assert xq._load_json(str(bad), {"k": 1}) == {"k": 1}
    assert xq._load_json(str(tmp_path / "missing.json"), []) == []
    assert xq._write_json(str(tmp_path / "ok" / "x.json"), {"a": 1}) is True
    assert xq._load_json(str(tmp_path / "ok" / "x.json")) == {"a": 1}


def test_status_smoke(tmp_path):
    """status 摘要不崩（无数据时也输出）"""
    xq.CUBES_FILE = str(tmp_path / "cubes.json")
    xq.NAV_FILE = str(tmp_path / "nav.json")
    xq.TRADES_FILE = str(tmp_path / "trades.jsonl")
    s = xq.status()
    assert "组合映射" in s and "调仓记录" in s
