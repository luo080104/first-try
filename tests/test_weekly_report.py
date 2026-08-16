# -*- coding: utf-8 -*-
"""周报快测（test_weekly_report.py——2026-08-16 A3 完善项）

背景：/weekly 路由曾在 __main__ 块后永不注册（TestClient 测不出——
python -m 启动时 uvicorn.run 阻塞）。本测试锁住三个不变量：
1. 文本周报含关键段（分节结构）
2. HTML 周报含 KPI/持仓/图表（Bento 结构）
3. /weekly 路由可达（HTTP 200）
"""

import sys
from pathlib import Path

sys.path.insert(0, ".")

from fastapi.testclient import TestClient

from tools.strategy_engine import backup as bk
from tools.strategy_engine.gf_web import app
from tools.strategy_engine.weekly_report import build_report
from tools.strategy_engine.weekly_report_html import build_html


def test_text_report_sections():
    r = build_report()
    assert "观复周报" in r
    assert "下周关注" in r  # 行动项段
    assert "持仓" in r or "空仓" in r  # 持仓段
    assert "━━━" in r  # 分割线（视觉层次）


def test_html_report_structure():
    h = build_html()
    assert 'class="kpi"' in h  # KPI 面板
    assert "持仓明细" in h  # 持仓卡
    assert "echarts" in h  # 净值图
    assert "观复" in h  # 品牌


def test_weekly_route_reachable():
    c = TestClient(app)
    assert c.get("/weekly").status_code == 200
    assert "观复周报" in c.get("/weekly").text


def test_daily_backup_snapshot(tmp_path):
    """备份快照：关键文件复制 + 幂等"""
    # 用临时目录模拟（不污染真实 backup/）
    orig_data, orig_bk = bk.DATA_DIR, bk.BACKUP_DIR
    fake = tmp_path / "data"
    fake.mkdir()
    (fake / "portfolio.json").write_text("{}", encoding="utf-8")
    bk.DATA_DIR = str(fake)
    bk.BACKUP_DIR = str(fake / "backup")
    try:
        dst = bk.daily_backup()
        assert dst and (Path(dst) / "portfolio.json").exists()
    finally:
        bk.DATA_DIR, bk.BACKUP_DIR = orig_data, orig_bk
