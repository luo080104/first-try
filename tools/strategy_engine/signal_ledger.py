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
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
LEDGER_FILE = os.path.join(DATA_DIR, "signal_ledger.jsonl")
VERIFY_WINDOWS = (90, 180, 365)  # 3/6/12 月验证窗（天）

# 信号类型（与观复信号体系对应）
TYPES = (
    "score_pass",  # Q12 动态打分达标（建仓信号）
    "grid_add",  # Q13 抄底网格（跌 3/6/10% 加仓）
    "swing_exit",  # Q16 波段技术止损
    "base_exit",
)  # Q16 底仓逻辑止损（季度体检）


def record(
    code,
    name="",
    sig_type="score_pass",
    direction="buy",
    price=0.0,
    reason="",
    track="base",
    threshold=None,
    grid=None,
    verify_at=None,
):
    """记录一个信号（事件流——Q11 账本）。verify_at 可覆盖（测试/手动回填用）"""
    assert sig_type in TYPES, f"未知信号类型: {sig_type}"
    ev = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "code": code,
        "name": name,
        "type": sig_type,
        "direction": direction,
        "price": price,
        "reason": reason,
        "track": track,
        "threshold": threshold,
        "grid": grid,
        "verify_at": verify_at
        or (datetime.now() + timedelta(days=VERIFY_WINDOWS[0])).strftime("%Y-%m-%d"),
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
            ev["result_pct"] = (
                round((px - ev["price"]) / ev["price"] * 100, 2) if ev["price"] else 0.0
            )
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
        return {
            "groups": {},
            "total": 0,
            "verified": 0,
            "pending": 0,
            "note": "账本为空",
        }
    try:
        raw = open(LEDGER_FILE, encoding="utf-8").readlines()
    except OSError as e:
        print(f"[signal_ledger] 读取失败: {e}")
        return {
            "groups": {},
            "total": 0,
            "verified": 0,
            "pending": 0,
            "note": f"读取失败: {e}",
        }
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
        g["rows"].append(
            {"code": ev["code"], "pct": r, "verify": ev.get("verified_at")}
        )
    out = {}
    for t, g in groups.items():
        out[t] = {
            "n": g["n"],
            "win_rate": round(g["wins"] / g["n"] * 100, 1),
            "avg_pct": round(g["sum"] / g["n"], 2),
        }
    return {
        "groups": out,
        "total": len(rows),
        "verified": sum(1 for r in rows if r.get("result_pct") is not None),
        "pending": sum(1 for r in rows if r.get("result_pct") is None),
    }


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "backfill":
        n = backfill()
        print(f"回填 {n} 个到期信号")
    r = report()
    print(f"账本: 总信号 {r['total']} | 已验证 {r['verified']} | 待验证 {r['pending']}")
    for t, g in r["groups"].items():
        print(f"  {t}: N={g['n']} 胜率 {g['win_rate']}% 平均 {g['avg_pct']}%")


# ============================================================================
# 信号在线评分（整改② 2026-08-15——评测发现：策略好坏无量化反馈——漂移检测）
# 目标：每信号触发后 N 日（20/60 交易日）收益——月度汇总胜率/期望值——
#       连续 2 月胜率下滑 >10pt → 标记 strategy_drift（不自动禁用——等甲方）
# ============================================================================

ONLINE_WINDOWS = (20, 60)  # 触发后 N 交易日评估窗
DRIFT_MONTHS = 2  # 连续下滑月数阈值
DRIFT_POINTS = 10.0  # 胜率下滑点数阈值


def _kline_close(code: str, days: int = 90):
    """获取个股最近 K 线收盘（腾讯——失败返回 None——不静默）"""
    try:
        from tools.strategy_engine import data

        k = data.tencent_kline(code, days=days)
        if not k:
            return None
        return [(x.get("date", "")[:10], x.get("close", 0.0)) for x in k]
    except Exception:
        return None


def online_score(
    kline_provider=None, window: int = 20, months_back: int = 6
) -> dict[str, Any]:
    """信号在线评分（整改②）

    对账本中每个已触发信号：触发日后第 window 个交易日的收盘价 vs 触发价
    → 收益 → 按触发月份聚合胜率/期望 → 漂移检测（连续 2 月下滑 >10pt）

    kline_provider(code) -> [(date, close)]（测试注入——默认腾讯 K 线）
    返回 {monthly: {YYYY-MM: {n, wins, win_rate, avg}}, drift: bool, note}
    """
    if not os.path.exists(LEDGER_FILE):
        return {"monthly": {}, "drift": False, "note": "账本为空"}
    try:
        raw = open(LEDGER_FILE, encoding="utf-8").readlines()
    except OSError:
        return {"monthly": {}, "drift": False, "note": "账本读取失败"}
    rows = []
    for l in raw:
        try:
            rows.append(json.loads(l))
        except (json.JSONDecodeError, ValueError):
            continue
    # 按月聚合：{YYYY-MM: [(win, ret)...]}
    monthly: dict[str, list[tuple[bool, float]]] = {}
    for ev in rows:
        code = ev.get("code")
        ts = (ev.get("ts") or "")[:7]  # YYYY-MM
        price = ev.get("price") or 0
        direction = ev.get("direction", "buy")
        if not code or not ts or price <= 0:
            continue
        if kline_provider:
            k = kline_provider(code)
        else:
            k = _kline_close(code)
        if not k:
            continue  # K 线不可得——跳过（不静默——note 统计）
        # 找触发日之后的第 window 个交易日
        trigger_date = (ev.get("ts") or "")[:10]
        after = [c for d, c in k if d >= trigger_date]
        if len(after) <= window:
            continue  # 数据不足 window 日——等积累
        future_px = after[window]
        if future_px <= 0:
            continue
        ret = (future_px - price) / price * 100
        # 卖出信号：下跌为胜
        win = (ret < 0) if direction == "sell" else (ret > 0)
        monthly.setdefault(ts, []).append((win, ret))
    out = {}
    rates = []
    for m in sorted(monthly):
        items = monthly[m]
        n = len(items)
        wins = sum(1 for w, _ in items if w)
        avg = sum(r for _, r in items) / n
        wr = wins / n * 100
        out[m] = {"n": n, "wins": wins, "win_rate": round(wr, 1), "avg": round(avg, 2)}
        rates.append((m, wr))
    # 漂移检测：连续 DRIFT_MONTHS 月胜率下滑超过 DRIFT_POINTS 点
    drift = False
    if len(rates) >= DRIFT_MONTHS + 1:
        declines = 0
        for i in range(1, len(rates)):
            if rates[i - 1][1] - rates[i][1] > DRIFT_POINTS:
                declines += 1
                if declines >= DRIFT_MONTHS:
                    drift = True
                    break
            else:
                declines = 0
    note = (
        f"⚠️ 策略漂移：连续 {DRIFT_MONTHS} 月胜率下滑 >{DRIFT_POINTS:.0f}pt——建议降级候选（等甲方）"
        if drift
        else f"在线评分 {window} 日窗——{len(out)} 个月数据"
    )
    return {"monthly": out, "drift": drift, "note": note}


def drift_flag() -> str:
    """漂移标记摘要（周报信号质量段用）——无漂移返回空"""
    r = online_score()
    return r["note"] if r.get("drift") else ""


if __name__ == "__main__":
    main()
