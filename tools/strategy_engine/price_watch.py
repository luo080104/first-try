# -*- coding: utf-8 -*-
"""盘中盯价（price_watch.py——v1.2——心理价位→到价推送——双通道：策略信号+盯价）

定案（需求 v1.1 补录）：盘中盯价=核心功能（Go购 盯价模式复用——心理价位到价即时推送）
- 清单：data/price_watch.json（{code, name, target, direction, note}——手动/聊天添加）
- 检查：实时行情（腾讯——不封 IP）→ 命中目标价 → 推送（低频合并节流复用 notify_gf）
- 防重复：同一条目命中后标记 alerted——用户改目标价后重置
- 用法：python -m tools.strategy_engine.price_watch check（定时任务每分钟盘中调用）
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import data as d

_WATCH_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "price_watch.json"
)

DEFAULT = {"items": []}


def _load() -> dict[str, Any]:
    """读盯价清单——失败返回副本（防共享可变对象污染——2026-08-15 修复）"""
    try:
        with open(_WATCH_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "items" in data:
            return data
    except (OSError, ValueError):
        pass
    return {"items": []}


def _save(data: dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_WATCH_FILE), exist_ok=True)
        with open(_WATCH_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[price_watch] 保存失败: {e}")


def add(code: str, target: float, direction: str = "below", note: str = "") -> bool:
    """添加盯价条目（direction: below=跌破提醒 / above=涨破提醒）"""
    try:
        target = float(target)
    except (TypeError, ValueError):
        return False
    data = _load()
    for it in data["items"]:
        if it["code"] == code and it.get("direction") == direction:
            return False  # 同方向已存在——不重复
    data["items"].append(
        {
            "code": code,
            "name": note or code,
            "target": target,
            "direction": direction,
            "alerted": False,
            "note": note,
        }
    )
    _save(data)
    return True


def remove(code: str, direction: str = "below") -> bool:
    """移除盯价条目"""
    data = _load()
    before = len(data["items"])
    data["items"] = [
        it
        for it in data["items"]
        if not (it["code"] == code and it.get("direction") == direction)
    ]
    if len(data["items"]) != before:
        _save(data)
        return True
    return False


def check(retries: int = 2) -> list[dict[str, Any]]:
    """检查所有活跃盯价——命中 → 推送 + 标记 alerted——返回命中列表

    retries：行情源偶发失败重试（红线③：数据失误真实风险——不静默）
    """
    data = _load()
    if not data["items"]:
        return []
    codes = [it["code"] for it in data["items"] if not it.get("alerted")]
    if not codes:
        return []
    quotes: dict[str, Any] = {}
    import time

    for attempt in range(retries + 1):
        quotes = d.tencent_quote(codes)
        if quotes:
            break
        time.sleep(1 + attempt)
    hits = []
    for it in data["items"]:
        if it.get("alerted"):
            continue
        q = quotes.get(it["code"])
        if not q or not q.get("price"):
            continue
        price = q["price"]
        hit = (
            price <= it["target"]
            if it["direction"] == "below"
            else price >= it["target"]
        )
        if hit:
            it["alerted"] = True
            hits.append({**it, "price": price})
    if hits:
        _save(data)
    return hits


def push_hits(hits: list[dict[str, Any]]) -> None:
    """命中推送（复用低频合并节流——notify_gf）"""
    if not hits:
        return
    try:
        from tools.strategy_engine.notify_gf import push_signal

        lines = ["⚡ 盘中盯价命中："]
        for h in hits:
            arrow = "跌破" if h["direction"] == "below" else "涨破"
            lines.append(
                f"  {h['name']}({h['code']}) {arrow} {h['target']}（现价 {h['price']}）"
            )
        push_signal("\n".join(lines))
    except Exception:
        pass  # 推送失败不阻塞（红线③）


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="观复盘中盯价")
    ap.add_argument(
        "cmd", choices=["add", "remove", "check"], default="check", nargs="?"
    )
    ap.add_argument("--code", default="")
    ap.add_argument("--target", type=float, default=0)
    ap.add_argument("--direction", default="below", choices=["below", "above"])
    ap.add_argument("--note", default="")
    args = ap.parse_args()
    if args.cmd == "add":
        print(
            "已添加"
            if add(args.code, args.target, args.direction, args.note)
            else "添加失败/已存在"
        )
    elif args.cmd == "remove":
        print("已移除" if remove(args.code, args.direction) else "未找到")
    else:
        hits = check()
        push_hits(hits)
        print(
            f"检查完成——命中 {len(hits)} 条"
            + (f": {[h['name'] for h in hits]}" if hits else "")
        )
