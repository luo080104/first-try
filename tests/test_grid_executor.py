"""抄底执行器单测（grid_executor——Q13 网格：3/6/10% + 4周间隔）"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import grid_executor as ge  # pyright: ignore

TMP = tempfile.mkdtemp()
ge.GRID_STATE_FILE = os.path.join(TMP, "grid_state.json")


def test_register_and_trigger():
    ge.register_position("600036", 38.46)
    # 价格未到位（跌不足 3%）
    assert ge.check_grid("600036", 38.0) is None
    # 跌 3% 触发第一批（38.46*0.97 = 37.31）
    hit = ge.check_grid("600036", 37.0, total_assets=100000)
    assert hit is not None and hit["grid"] == 1
    assert hit["step_pct"] == 3.0
    # 跌 6% 触发第二批（但第一批未标记——所以还是第一批）
    hit2 = ge.check_grid("600036", 35.0, total_assets=100000)
    assert hit2["grid"] == 1  # 未标记前不推进


def test_batch_progression():
    ge.register_position("600519", 1341.99)
    ge.mark_triggered("600519", 1, add_date="2026-07-01")  # 45 天前——间隔通过
    # 跌 6% 触发第二批（36 天前加的——时间保险通过）
    hit = ge.check_grid("600519", 1250.0, total_assets=100000)
    assert hit is not None and hit["grid"] == 2


def test_time_insurance():
    ge.register_position("600028", 6.0)
    ge.mark_triggered("600028", 1, add_date="2026-08-14")  # 昨天加的
    # 价格已到位（跌 3%）——但间隔 <4 周 → 不触发（防阴跌接飞刀）
    assert ge.check_grid("600028", 5.5, total_assets=100000) is None


def test_all_batches_done():
    ge.register_position("601857", 8.0)
    ge.mark_triggered("601857", 1, add_date="2026-01-01")
    ge.mark_triggered("601857", 2, add_date="2026-02-01")
    ge.mark_triggered("601857", 3, add_date="2026-03-01")
    # 三批全触发——跌再多也不加
    assert ge.check_grid("601857", 4.0, total_assets=100000) is None
