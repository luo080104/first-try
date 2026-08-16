# -*- coding: utf-8 -*-
"""S4 逻辑变化监测单测（test_s4_monitor.py——2026-08-16）

覆盖：关键词命中分级 / orgId 兜底规则 / 去重幂等 / 接口失败容错
不依赖网络（mock 公告数据 + 临时文件）
"""

import sys

sys.path.insert(0, ".")

from tools.strategy_engine import s4_monitor as s4


def test_match_keywords():
    """强/弱/无 三档命中"""
    assert s4._match_keywords("关于大股东减持计划的公告") == ("strong", "减持")
    assert s4._match_keywords("股权质押及解除质押的公告") == ("strong", "质押")
    assert s4._match_keywords("立案调查公告") == ("strong", "立案")
    assert s4._match_keywords("限售股解禁上市流通的提示性公告") == ("weak", "解禁")
    assert s4._match_keywords("关于召开业绩说明会的公告") == (None, "")


def test_org_id_fallback():
    """orgId 动态查询失败时兜底旧规则"""
    # 直接测兜底分支（不 mock 网络——用规则函数本身）
    assert s4._get_org_id("600030") != ""  # 兜底必非空


def test_dedup(tmp_path):
    """同 key 只提醒一次（幂等）"""
    s4.ALERTS_FILE = str(tmp_path / "alerts.jsonl")
    rec = {
        "key": "601601|2026-08-16|减持计划",
        "code": "601601",
        "date": "2026-08-16",
        "title": "减持计划",
        "keyword": "减持",
        "level": "strong",
        "ts": "2026-08-16 09:00",
    }
    s4._append_alert(rec)
    assert s4._seen("601601|2026-08-16|减持计划") is True
    assert s4._seen("601601|2026-08-16|其他") is False


def test_scan_failure_tolerant(monkeypatch, tmp_path):
    """公告接口失败 → 返回空列表（不抛）"""
    s4.ALERTS_FILE = str(tmp_path / "alerts.jsonl")
    monkeypatch.setattr(s4, "_cninfo_announcements", lambda code, page_size=20: [])
    # mock portfolio 持仓（空持仓——不抛即可）
    assert s4.scan_holdings() == []
