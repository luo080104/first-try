"""失败票纪律（书 L2540：'失败的票，不到周布林线下轨不买回'——2026-08-17 落地）

机制：卖出 → 记入黑名单（data/failed_track.jsonl）→ 买回前检查：
现价 ≥ 周布林线下轨 才允许买回——否则晨报提醒拦截（纪律层——不硬拦交易）。

数据：{code, name, sell_price, sell_reason, ts}——append-only
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data"
)
FILE = os.path.join(DATA_DIR, "failed_track.jsonl")


def record_sell(code: str, name: str, price: float, reason: str = "") -> None:
    """卖出时记录（portfolio.sell 挂钩）——失败不阻塞交易（容错红线）"""
    try:
        with open(FILE, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "code": code,
                        "name": name,
                        "sell_price": price,
                        "reason": reason,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except OSError:
        pass  # 黑名单写入失败不影响卖出执行


def load_failed() -> list[dict[str, Any]]:
    if not os.path.exists(FILE):
        return []
    out = []
    try:
        lines = open(FILE, encoding="utf-8").read().split("\n")
    except OSError:
        return []
    for line in lines:
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
    return out


def check_rebuy(code: str, price: float, weekly_lower: float) -> dict[str, Any]:
    """买回前检查（书 L2540）：黑名单票现价未到周线下轨 → 拦截提醒

    weekly_lower: 周布林线下轨（调用方从周线算——data.bs_kline_weekly + boll）
    不在黑名单 → 放行（{"block": False}）
    """
    failed = [f for f in load_failed() if f["code"] == code]
    if not failed:
        return {"block": False}
    latest = failed[-1]
    if price >= weekly_lower:
        return {
            "block": True,
            "reason": (
                f"书L2540：{latest['name']}({code})是失败票（{latest.get('sell_price', '?')}卖出"
                f"/{latest.get('reason', '')}）——现价{price:.2f}未到周线下轨{weekly_lower:.2f}"
                "——不到下轨不买回"
            ),
        }
    return {"block": False, "ok": f"已回落至周线下轨{weekly_lower:.2f}下方——可买回"}


def build_alert_section() -> str:
    """晨报段：黑名单内票若现价仍高于周线下轨 → 提醒（数据缺失票跳过）"""
    failed = load_failed()
    if not failed:
        return ""
    from tools.strategy_engine import data

    lines = []
    for f in failed:
        try:
            wk = data.bs_kline_weekly(f["code"], years=2)[:24]
            if len(wk) < 12:
                continue
            closes = [w["close"] for w in reversed(wk)]
            mid = sum(closes) / len(closes)
            # 简化布林下轨（20 周——std 近似）
            import statistics

            std = statistics.pstdev(closes) if len(closes) > 1 else 0
            lower = mid - 2 * std
            cur = wk[0]["close"]
            if cur >= lower:
                lines.append(
                    f"  ⛔ {f['name']}({f['code']})：现价{cur:.2f}未到周线下轨"
                    f"{lower:.2f}——书L2540不到下轨不买回"
                )
        except Exception:
            continue
    if not lines:
        return ""
    return "\n【失败票纪律（书L2540）】\n" + "\n".join(lines)
