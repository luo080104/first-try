"""龙头池 YAML 单测（书 B2 全量——防八进制/前导零解析回归）"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import core_loop as cl  # pyright: ignore


def test_full_pool_from_yaml():
    pool = cl.load_leader_pool()
    assert len(pool) >= 40  # 书 B2 A股全量
    # 全部 6 位字符串（YAML 八进制 bug 回归——000543 曾变 355）
    assert all(isinstance(c, str) and len(c) == 6 for c in pool)
    assert "000543" in pool  # 皖能电力（前导零）
    assert "600036" in pool  # 招商银行


def test_fallback_when_yaml_missing():
    # YAML 读取失败（open 抛错）→ 函数内 try/except → fallback MVP 池
    with patch("builtins.open", side_effect=OSError("yaml 缺失")):
        pool = cl.load_leader_pool()
        assert len(pool) == len(cl.LEADER_POOL)  # fallback MVP 池
