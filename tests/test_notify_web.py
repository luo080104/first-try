# -*- coding: utf-8 -*-
"""推送/网页/晨报快测（test_notify_web.py——2026-08-16 R3 落地）

背景：/weekly 路由曾在 __main__ 块后永不注册（TestClient 测不出——
python -m 启动时 uvicorn.run 阻塞）。推送层是"静默失败高发区"。
锁住：①gf_web 全部路由可达 ②晨报构建不崩 ③推送节流上限
"""

import sys

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from tools.strategy_engine.gf_web import app
from tools.strategy_engine.morning_brief import build_brief
from tools.strategy_engine.notify_gf import DAILY_CAP, _throttled, _today_count


def test_all_web_routes(monkeypatch):
    """gf_web 全部路由可达（防 __main__ 块后路由不注册的历史坑）

    注意：/brief 路由会触发真实微信推送——monkeypatch 防误推（2026-08-16 发现）
    """
    from tools.strategy_engine import notify_gf

    monkeypatch.setattr(notify_gf, "push_brief", lambda: True)
    c = TestClient(app)
    for path in ["/", "/watch", "/history", "/weekly", "/brief"]:
        r = c.get(path)
        assert r.status_code in {200, 302}, f"{path} → {r.status_code}"


def test_brief_builds(monkeypatch):
    """晨报构建不崩且含核心段（网络监测段 mock——防慢/防外部依赖）"""
    monkeypatch.setattr(
        "tools.strategy_engine.s4_monitor.build_alert_section", lambda: ""
    )
    monkeypatch.setattr(
        "tools.strategy_engine.weekly_report.behavior_alert", lambda: ""
    )
    b = build_brief()
    assert "观复晨报" in b
    assert "【大盘状态】" in b
    assert "【数据源】" in b


def test_throttle_cap(tmp_path, monkeypatch):
    """推送节流：达上限拒绝（低频合并≤3 条/天——push_state 跨进程计数）"""
    from tools.strategy_engine import notify_gf as ng

    state = tmp_path / "push_state.json"
    monkeypatch.setattr(ng, "_STATE_PATH", str(state))
    ng._bump_count()  # 1
    ng._bump_count()  # 2
    ng._bump_count()  # 3
    assert _throttled("测试") == False  # 第 4 条拒绝（显式比较——避 is 字面量规则）
    assert _today_count() <= DAILY_CAP
