"""重试熔断器（书 8.3 验证发布协议——2026-08-17：当日失败 N 次→跳过当日）

防"反复重试烧钱/刷接口"循环：xq_track/wb_track 等外部调用当日失败达阈值
→ 当日剩余工作跳过（次日自动重置）——失败原因进 diag.jsonl。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)
FILE = os.path.join(DATA_DIR, "breaker.json")


def _load() -> dict[str, Any]:
    if not os.path.exists(FILE):
        return {}
    try:
        return json.load(open(FILE, encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(d: dict[str, Any]) -> None:
    try:
        with open(FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass


def record_fail(name: str) -> int:
    """记录一次失败——返回当日累计失败次数"""
    d = _load()
    today = time.strftime("%Y-%m-%d")
    st = d.get(name)
    if not st or st.get("date") != today:
        st = {"date": today, "fails": 0}
    st["fails"] += 1
    d[name] = st
    _save(d)
    return st["fails"]


def is_tripped(name: str, limit: int = 5) -> bool:
    """当日失败 ≥ limit → 熔断（跳过剩余工作）——次日自动重置"""
    d = _load()
    st = d.get(name)
    if not st or st.get("date") != time.strftime("%Y-%m-%d"):
        return False
    return st["fails"] >= limit


def breaker_state() -> list[dict[str, Any]]:
    """当前熔断状态——晨报【数据源】段可引用"""
    out = []
    for name, st in _load().items():
        out.append({"name": name, "date": st.get("date"), "fails": st.get("fails")})
    return out
