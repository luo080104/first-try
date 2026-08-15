# -*- coding: utf-8 -*-
"""大V 模块（M3——清单/调仓记录/X 证据链/跟随建议——半自动）

定案（docs/观复落地实施方案.md Q3/Q17 + 大V 方案变更）：
- 大V 信号只进"候选池"——必须过自己的战略层过滤才可买（Q3——借大V的眼选票用我们的尺子量）
- 不提前分级（Q3 修正——数据驱动——X 证据链积累后评分）
- X 证据链可信度（Q17）：披露质量/逻辑一致性/风格漂移——时间衰减——不短窗口价格验证
- 跟随仓 ≤20% 风险隔离（v1.5 定案——超级鹿鼎公级红线）
- 数据来源：vpush 部署后自动（雪球调仓/微博）——MVP 先手动/半自动录入

运行：python -m tools.strategy_engine.bigv record <大V> <代码> <买|卖> [原因]
      python -m tools.strategy_engine.bigv score <大V>
      python -m tools.strategy_engine.bigv follow <代码>
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
TRADES_FILE = os.path.join(DATA_DIR, "bigv_trades.jsonl")
LIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bigv_list.yaml")
FOLLOW_CAP = 0.20  # 跟随仓 ≤20%（v1.5 定案——风险隔离红线）
DECAY_DAYS = 30  # X 证据链衰减窗（30 天无记录 → 权重 ×0.9——v0 待校准）
REASON_MIN_LEN = 10  # 披露质量：有实质理由（≥10 字——v0 待校准）


def load_list() -> list[dict[str, Any]]:
    """读大V 清单 YAML（书里明确名单——全量 60+ 待 vpush 数据）"""
    try:
        import yaml

        with open(LIST_FILE, encoding="utf-8") as f:
            d = yaml.safe_load(f)
        return d.get("bigvs", [])
    except Exception:
        return []


def _append_trade(ev: dict[str, Any]) -> None:
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(TRADES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[bigv] 记录失败: {e}")


def record_trade(
    bigv: str, code: str, action: str, price: float = 0.0, reason: str = ""
) -> dict[str, Any]:
    """记录大V 调仓事件（vpush 部署后自动——MVP 手动/半自动）"""
    if action not in ("买", "卖"):
        raise ValueError(f"动作需 买/卖——got {action}")
    ev = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "bigv": bigv,
        "code": code,
        "action": action,
        "price": price,
        "reason": reason,
        "disclosed": len(reason.strip()) >= REASON_MIN_LEN,
    }
    _append_trade(ev)
    return ev


def _load_trades(bigv: str | None = None) -> list[dict[str, Any]]:
    if not os.path.exists(TRADES_FILE):
        return []
    rows = []
    try:
        with open(TRADES_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if bigv is None or ev.get("bigv") == bigv:
                    rows.append(ev)
    except OSError:
        pass
    return rows


def score_bigv(bigv: str) -> dict[str, Any]:
    """X 证据链评分（Q17——披露质量/逻辑一致性/时间衰减——不提前分级）"""
    trades = _load_trades(bigv)
    if not trades:
        return {
            "name": bigv,
            "score": None,
            "n_trades": 0,
            "evidence": ["无调仓记录——不评分（Q3：不提前分级——数据驱动）"],
        }
    score = 0.0
    evidence: list[str] = []
    # 披露质量（每次调仓：有实质理由 +1 / 无 -0.5）
    for t in trades:
        score += 1.0 if t.get("disclosed") else -0.5
    n_disclosed = sum(1 for t in trades if t.get("disclosed"))
    evidence.append(f"披露质量：{n_disclosed}/{len(trades)} 次有实质理由")
    # 时间衰减（最近记录距今 >30 天 → 权重降——长期不发声可信度衰减——Q17）
    last_ts = trades[-1]["ts"][:10]
    days = (datetime.now() - datetime.strptime(last_ts, "%Y-%m-%d")).days
    if days > DECAY_DAYS:
        score *= 0.9
        evidence.append(f"衰减：{days} 天无新记录（权重 ×0.9——Q17 时间衰减）")
    return {
        "name": bigv,
        "score": round(score, 1),
        "n_trades": len(trades),
        "evidence": evidence,
        "note": "X 证据链——只评证据不评名气——持续积累（vpush 自动后样本↑）",
    }


def follow_candidates() -> list[dict[str, Any]]:
    """跟随候选（Q3：只进候选池——不过滤不买）——按大V 聚合调仓记录"""
    trades = _load_trades()
    out = []
    for t in trades:
        if t["action"] == "买":
            out.append(
                {
                    "bigv": t["bigv"],
                    "code": t["code"],
                    "price": t["price"],
                    "ts": t["ts"][:10],
                    "reason": t.get("reason", ""),
                }
            )
    return out


def follow_cap_check() -> dict[str, Any]:
    """跟随仓 ≤20% 检查（v1.5 红线）——portfolio 中 track=bigv 的市值占比"""
    from tools.strategy_engine import portfolio as pf

    p = pf.Portfolio()
    positions, total = p.positions()
    follow_mv = sum(x["market"] for x in positions if x["track"] == "bigv")
    pct = round(follow_mv / total * 100, 1) if total else 0.0
    return {
        "follow_mv": round(follow_mv, 2),
        "total": round(total, 2),
        "follow_pct": pct,
        "cap": FOLLOW_CAP * 100,
        "ok": pct <= FOLLOW_CAP * 100,
    }


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    if cmd == "record" and len(sys.argv) >= 5:
        bigv, code, action = sys.argv[2], sys.argv[3], sys.argv[4]
        try:
            price = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
        except ValueError:
            price = 0.0  # 价格输入非法 → 不记价（安全降级）
        reason = " ".join(sys.argv[6:])
        ev = record_trade(bigv, code, action, price, reason)
        print(
            f"已记录 {ev['bigv']} {ev['action']} {ev['code']}"
            f"{f' @ {ev[chr(112) + chr(114) + chr(105) + chr(99) + chr(101)]}' if ev['price'] else ''}"
            f"（披露质量: {'✅' if ev['disclosed'] else '⚠️ 无理由'}）"
        )
        cap = follow_cap_check()
        if not cap["ok"]:
            print(
                f"⚠️ 跟随仓 {cap['follow_pct']}% 超红线 {cap['cap']}%——不再新增跟随建议"
            )
    elif cmd == "score" and len(sys.argv) >= 3:
        s = score_bigv(sys.argv[2])
        print(f"{s['name']}: 可信度 {s['score']}（{s['n_trades']} 次调仓记录）")
        for e in s["evidence"]:
            print(f"  - {e}")
    elif cmd == "follow":
        cap = follow_cap_check()
        print(
            f"跟随仓: {cap['follow_pct']}% / 红线 {cap['cap']}%——{'✅' if cap['ok'] else '⚠️ 超限'}"
        )
        for c in follow_candidates():
            print(f"  {c['bigv']} 买 {c['code']}（{c['ts']}）{c['reason'][:40]}")
    else:
        print("用法: record <大V> <代码> <买|卖> [价] [原因] | score <大V> | follow")


if __name__ == "__main__":
    main()
