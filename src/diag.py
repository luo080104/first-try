# -*- coding: utf-8 -*-
"""失败显式记录（2026-08-18 老师规范三：禁止静默吞错）

为什么存在：静默 `except: pass` 让失败无迹可循——排查只能靠猜。
统一走本模块写 data/diag.jsonl（行格式对齐观复已建立的记录：
ts/component/fn/exc_type/exc_msg/hint），失败可审计、可统计、可熔断。

为什么 append-only + 不抛：记录失败本身不能引入新失败——写盘失败就放弃
（fast fail 决策由调用方做，这里只负责留证据）。
"""
import json
import os
import time

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_FILE = os.path.join(_DATA_DIR, "diag.jsonl")


def diag(component: str, fn: str, exc: BaseException, hint: str = "") -> None:
    """记录一次异常到 data/diag.jsonl（失败证据，不抛错）"""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_FILE, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "component": component,
                        "fn": fn,
                        "exc_type": type(exc).__name__,
                        "exc_msg": str(exc)[:300],
                        "hint": hint,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass  # 为什么：写盘已不可能——绝不能让记录本身抛错拖垮主流程
