"""结构化诊断日志（书 6.5 失败归因——2026-08-17：except:pass 不再静默）

关键路径（晨报/周报/回测/大V 跟踪）失败时写一条结构化记录：
{ts, component, fn, exc_type, exc_msg, hint}
→ data/diag.jsonl（append-only——backup.py 覆盖）——人可读可查
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)
FILE = os.path.join(DATA_DIR, "diag.jsonl")


def log_diag(component: str, fn: str, exc: BaseException, hint: str = "") -> None:
    """写一条诊断记录——失败不阻塞（诊断本身失败静默——最后一层）"""
    try:
        with open(FILE, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "component": component,
                        "fn": fn,
                        "exc_type": type(exc).__name__,
                        "exc_msg": str(exc)[:200],
                        "hint": hint,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass


def load_diag(n: int = 20) -> list[dict[str, Any]]:
    """最近 n 条诊断——排障入口"""
    if not os.path.exists(FILE):
        return []
    out = []
    try:
        lines = open(FILE, encoding="utf-8").read().strip().split("\n")
    except OSError:
        return []
    for line in lines[-n:]:
        try:
            out.append(json.loads(line))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
    return out


def recent_hints(component: str, days: int = 7) -> list[dict[str, Any]]:
    """近 N 天某组件的诊断——晨报/周报可引用（数据源健康段）"""
    out = []
    for d in load_diag(200):
        if d.get("component") == component and d.get("ts", "")[:10] >= time.strftime(
            "%Y-%m-%d", time.localtime(time.time() - days * 86400)
        ):
            out.append(d)
    return out
