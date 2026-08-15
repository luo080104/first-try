# -*- coding: utf-8 -*-
"""Q11 前向验证账本（signal_ledger——参数学习化的数据采集器）

每个信号记录一行：日期/代码/类型/方向/触发价/原因/track
3/6/12 月后回填实际价格 → 计算结果 → 分组胜率统计 → 校准依据。

校准规则（Q11 定案——观复落地实施方案.md）：
- 参数变更需 N≥50 且胜率差>10 点（平滑：新权重 = 初始×0.5 + 实测×0.5）
- 降权自动+周报说明；停用/参数变更需甲方确认（半自动红线延伸）

运行：python -m tools.strategy_engine.signal_ledger report
"""

import json
import os
import sys
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
LEDGER_FILE = os.path.join(DATA_DIR, "signal_ledger.jsonl")
VERIFY_WINDOWS = (90, 180, 365)  # 3/6/12 月验证窗（天）

# 信号类型（与观复信号体系对应）
TYPES = ("score_pass",     # Q12 动态打分达标（建仓信号）
         "grid_add",       # Q13 抄底网格（跌 3/6/10% 加仓）
         "swing_exit",     # Q16 波段技术止损
         "base_exit")      # Q16 底仓逻辑止损（季度体检）


def record(code, name="", sig_type="score_pass", direction="buy", price=0.0,
           reason="", track="base", threshold=None, grid=None, verify_at=None):
    """记录一个信号（事件流——Q11 账本）。verify_at 可覆盖（测试/手动回填用）"""
    assert sig_type in TYPES, f"未知信号类型: {sig_type}"
    ev = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "code": code, "name": name, "type": sig_type, "direction": direction,
        "price": price, "reason": reason, "track": track,
        "threshold": threshold, "grid": grid,
        "verify_at": verify_at or (datetime.now() + timedelta(days=VERIFY_WINDOWS[0])).strftime("%Y-%m-%d"),
    }
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(LEDGER_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[signal_ledger] 写入失败: {e}")
    return ev


def backfill(quotes_provider=None):
    """回填到期信号的实盘结果（价格来自 quotes_provider(code)->float 或腾讯行情）"""
    if not os.path.exists(LEDGER_FILE):
        return 0
    try:
        lines = open(LEDGER_FILE, encoding="utf-8").readlines()
    except OSError as e:
        print(f"[signal_ledger] 读取失败: {e}")
        return 0
    backfilled = 0
    for i, line in enumerate(lines):
        try:
            ev = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # 坏行跳过
        if ev.get("result_pct") is not None or not ev.get("verify_at"):
            continue
        if ev["verify_at"] > datetime.now().strftime("%Y-%m-%d"):
            continue
        px = None
        if quotes_provider:
            px = quotes_provider(ev["code"])
        else:
            try:
                from tools.strategy_engine import data
                q = data.tencent_quote([ev["code"]])
                px = (q.get(ev["code"]) or {}).get("price")
            except Exception:
                pass
        if px:
            ev["result_pct"] = round((px - ev["price"]) / ev["price"] * 100, 2) \
                if ev["price"] else 0.0
            ev["result_price"] = px
            ev["verified_at"] = datetime.now().strftime("%Y-%m-%d")
            lines[i] = json.dumps(ev, ensure_ascii=False) + "\n"
            backfilled += 1
    if backfilled:
        try:
            with open(LEDGER_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except OSError as e:
            print(f"[signal_ledger] 回填保存失败: {e}")
    return backfilled


def report():
    """分组统计（按类型——N/胜率/平均幅度）——校准依据"""
    if not os.path.exists(LEDGER_FILE):
        return {"groups": {}, "total": 0, "note": "账本为空"}
    try:
        raw = open(LEDGER_FILE, encoding="utf-8").readlines()
    except OSError as e:
        print(f"[signal_ledger] 读取失败: {e}")
        return {"groups": {}, "total": 0, "note": f"读取失败: {e}"}
    rows = []
    for l in raw:
        try:
            rows.append(json.loads(l))
        except (json.JSONDecodeError, ValueError):
            continue  # 坏行跳过
    groups = {}
    for ev in rows:
        r = ev.get("result_pct")
        if r is None:
            continue
        g = groups.setdefault(ev["type"], {"n": 0, "wins": 0, "sum": 0.0, "rows": []})
        g["n"] += 1
        if ev.get("direction") == "buy":
            g["wins"] += 1 if r > 0 else 0
        else:  # sell 信号——下跌为胜
            g["wins"] += 1 if r < 0 else 0
        g["sum"] += r
        g["rows"].append({"code": ev["code"], "pct": r, "verify": ev.get("verified_at")})
    out = {}
    for t, g in groups.items():
        out[t] = {"n": g["n"], "win_rate": round(g["wins"] / g["n"] * 100, 1),
                  "avg_pct": round(g["sum"] / g["n"], 2)}
    return {"groups": out, "total": len(rows),
            "verified": sum(1 for r in rows if r.get("result_pct") is not None),
            "pending": sum(1 for r in rows if r.get("result_pct") is None)}


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        n = backfill()
        print(f"回填 {n} 个到期信号")
    r = report()
    print(f"账本: 总信号 {r['total']} | 已验证 {r['verified']} | 待验证 {r['pending']}")
    for t, g in r["groups"].items():
        print(f"  {t}: N={g['n']} 胜率 {g['win_rate']}% 平均 {g['avg_pct']}%")


if __name__ == "__main__":
    main()
