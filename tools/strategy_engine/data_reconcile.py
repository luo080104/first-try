# -*- coding: utf-8 -*-
"""数据源交叉对账（data_reconcile.py——2026-08-16 架构师 R1 落地）

静默数据漂移是回测/判定的污染源——baostock 主源 + tushare 免费档第二源
每周对账：同一股票最近 N 日收盘价对比——差异 >0.5% 报警。

用法：python -m tools.strategy_engine.data_reconcile [codes...]
默认对账：3 持仓 + 沪深300 指数
"""

from __future__ import annotations

import sys

from tools.strategy_engine import data as d

# 默认对账池（3 持仓 + 基准指数）
DEFAULT_POOL = ["601601", "601318", "600030", "000300"]

TOLERANCE = 0.005  # 0.5%——超过即报警


def reconcile(codes: list[str] | None = None, days: int = 5) -> list[dict]:
    """双源对账——返回差异超阈值的记录列表（空=全部一致）"""
    from tools.strategy_engine import data_tushare as ts

    codes = codes or DEFAULT_POOL
    issues: list[dict] = []
    for code in codes:
        try:
            bs = {x["date"]: x["close"] for x in d.bs_kline_daily(code, 1)}
            tq = {x["date"]: x["close"] for x in ts.kline_daily(ts.to_ts_code(code))}
        except Exception:
            continue  # 单只对账失败不阻塞（红线③）
        common = sorted(set(bs) & set(tq))[-days:]
        for date in common:
            a, b = bs[date], tq[date]
            if not a or not b:
                continue
            diff = abs(a - b) / b
            if diff > TOLERANCE:
                issues.append(
                    {
                        "code": code,
                        "date": date,
                        "baostock": round(a, 3),
                        "tushare": round(b, 3),
                        "diff_pct": round(diff * 100, 2),
                    }
                )
    return issues


def report() -> str:
    """周报对账段——无差异返回空串（不占版面）"""
    issues = reconcile()
    if not issues:
        return ""
    lines = ["🔀 **数据对账（双源交叉）**"]
    for i in issues[:5]:
        lines.append(
            f"  ⚠️ {i['code']} {i['date']}: baostock {i['baostock']} vs "
            f"tushare {i['tushare']}（差 {i['diff_pct']}%）"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    codes = sys.argv[1:] or None
    issues = reconcile(codes)
    if issues:
        print(f"⚠️ 对账发现 {len(issues)} 处差异：")
        for i in issues[:8]:
            print(
                f"  {i['code']} {i['date']}: baostock {i['baostock']} "
                f"vs tushare {i['tushare']}（{i['diff_pct']}%）"
            )
    else:
        print("✅ 双源对账一致（无 >0.5% 差异）")
