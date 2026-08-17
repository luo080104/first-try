# -*- coding: utf-8 -*-
"""大V 假设回测裁决（idea_backtest.py——2026-08-17 B2 落地）

甲方拍板：A 标准（验证段胜率 ≥55% 且跑赢沪深300）+ 数据为王（书同权）
首验：小七滚雪球"股息率>5% 且 PE<10 → 持有；跌破卖出；年换手<1"

规则实现（小七组合自述 4 条——可量化 3 条）：
  ① 股息率 > 5%（最近年度每股分红 ÷ 当前价）
  ② PE(TTM) < 10
  ③ 央企/派息稳定 → 用"连续 5 年分红"近似（软性）
  ④ 每年 6 月底体检调仓（年换手 < 1——低频）

股票池：30 只高股息候选（银行/电力/煤炭/高速/运营商——标注局限：
非全市场扫描——二期可扩）。训练段 2016-2020 / 验证段 2021-2026。

用法：python -m tools.strategy_engine.idea_backtest
输出：裁决排行榜（胜率/超额/卡玛——A 标准判定）
"""

from __future__ import annotations

import baostock as bs

# 高股息候选池（30 只——银行/电力/煤炭/高速/运营商/周期）
POOL = [
    "601398",
    "601939",
    "601288",
    "601988",
    "601328",  # 工建农中交
    "600036",
    "601166",
    "600000",  # 招行/兴业/浦发
    "600900",
    "600025",
    "601985",
    "600886",
    "600674",
    "600795",  # 长电/华能水电/中核/国投/川投/国电
    "601088",
    "601898",
    "601225",
    "600188",  # 神华/中煤/陕煤/兖矿
    "600377",
    "600548",
    "600350",  # 宁沪/深高速/山东高速
    "600941",
    "601728",
    "600050",  # 移动/电信/联通
    "601006",
    "600019",
    "601668",
    "600585",
    "601857",
    "600028",  # 大秦/宝钢/中建/海螺/中石油/中石化
]

BASE = "000300"  # 沪深300 基准
TRAIN_END = "2020-12-31"  # 训练段 2016-2020
CHECK_MONTH = 6  # 每年 6 月底体检

_cache: dict[str, list] = {}


def _daily(code: str, start: str, end: str) -> list[dict]:
    """日线（后复权——缓存）——指数（000 开头）用 sh 前缀（2026-08-17 修）"""
    key = f"{code}|{start}|{end}"
    if key in _cache:
        return _cache[key]
    prefix = "sh." if code.startswith(("6", "000")) else "sz."
    rs = bs.query_history_k_data_plus(
        prefix + code,
        "date,close,peTTM,pbMRQ",
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="2",  # 后复权
    )
    rows = []
    while rs is not None and rs.error_code == "0" and rs.next():
        d = rs.get_row_data()
        try:
            rows.append(
                {
                    "date": d[0],
                    "close": float(d[1]),
                    "pe": float(d[2]) if d[2] else None,
                }
            )
        except ValueError:
            continue
    _cache[key] = rows
    return rows


def _dividends(code: str, years: list[int]) -> dict[int, float]:
    """每年每股分红（元）——baostock query_dividend_data

    字段 9 = 每股分红（10派3.064 → 0.3064——已是每股）
    去重：按 (除权日, 金额)——中期/年度同笔可能重复出现（2026-08-17 实测）
    """
    out: dict[int, float] = {}
    for y in years:
        prefix = "sh." if code.startswith(("6", "000")) else "sz."
        rs = bs.query_dividend_data(
            code=prefix + code,
            year=str(y),
            yearType="report",
        )
        total = 0.0
        seen: set[tuple] = set()
        while rs is not None and rs.error_code == "0" and rs.next():
            d = rs.get_row_data()
            try:
                v = float(d[9]) if d[9] else 0.0  # 每股分红
                ex_date = d[5] if len(d) > 5 else ""  # 除权日
                key = (ex_date, v)
                if v > 0 and key not in seen:
                    seen.add(key)
                    total += v  # 每股直接累加（年度+中期）
            except (ValueError, IndexError):
                continue
        if total > 0:
            out[y] = round(total, 4)
    return out


def _yield_at(divs: dict[int, float], year: int, price: float) -> float:
    """某年股息率（该年分红 ÷ 价格）——派息稳定检查：近 3 年都有分红"""
    recent = [divs.get(y, 0) for y in range(year - 2, year + 1)]
    if any(v <= 0 for v in recent):
        return 0.0  # 派息不稳定 → 股息率按 0（规则②）
    return recent[-1] / price if price > 0 else 0.0


def _year(s: str) -> int:
    """日期字符串前 4 位 → 年份（容错——红线③）"""
    try:
        return int(s[:4])
    except (TypeError, ValueError):
        return 0


def run_idea(symbols: list[str], start: str, end: str) -> dict:
    """跑小七规则：每年 6 月底体检——股息率>5% 且 PE<10 → 等权持有

    返回 {years: [{year, n_hold, port_ret, bench_ret}], ...}
    """
    years = list(range(_year(start), _year(end) + 1))
    div_cache: dict[str, dict[int, float]] = {}
    # 年度体检
    results = []
    port = 1.0  # 组合净值（年初=1）
    bench = 1.0
    for i, year in enumerate(years):
        check_date = f"{year}-{CHECK_MONTH:02d}-30"
        if year == _year(start):
            check_date = start  # 起始年用起始日
        # 选股：体检日满足 股息率>5% 且 PE<10
        holdings: list[str] = []
        for code in symbols:
            if code not in div_cache:
                div_cache[code] = _dividends(code, years)
            rows = _daily(code, start, end)
            # 找体检日当天或之前最近一行
            snap = next((r for r in reversed(rows) if r["date"] <= check_date), None)
            if not snap or snap["pe"] is None:
                continue
            yld = _yield_at(div_cache[code], year, snap["close"])
            if yld > 0.05 and snap["pe"] < 10:
                holdings.append(code)
        # 年内收益：体检日 → 次年体检日（后复权——直接用价格比）
        nxt = f"{year + 1}-{CHECK_MONTH:02d}-30"
        if year == years[-1]:
            nxt = end
        port_ret = 0.0
        if holdings:
            rets = []
            for code in holdings:
                rows = _daily(code, start, end)
                p0 = next((r for r in reversed(rows) if r["date"] <= check_date), None)
                p1 = next((r for r in reversed(rows) if r["date"] <= nxt), None)
                if p0 and p1 and p0["close"] > 0:
                    rets.append(p1["close"] / p0["close"] - 1)
            port_ret = sum(rets) / len(rets) if rets else 0.0
        # 基准同期
        brows = _daily(BASE, start, end)
        b0 = next((r for r in reversed(brows) if r["date"] <= check_date), None)
        b1 = next((r for r in reversed(brows) if r["date"] <= nxt), None)
        bench_ret = (
            (b1["close"] / b0["close"] - 1) if b0 and b1 and b0["close"] else 0.0
        )
        port *= 1 + port_ret
        bench *= 1 + bench_ret
        results.append(
            {
                "year": year,
                "n_hold": len(holdings),
                "port_ret": round(port_ret * 100, 2),
                "bench_ret": round(bench_ret * 100, 2),
                "port_nav": round(port, 3),
                "bench_nav": round(bench, 3),
            }
        )
    return {"results": results, "port_final": port, "bench_final": bench}


def _judge(results: list[dict], train_end: str) -> dict:
    """A 标准裁决：训练段/验证段——胜率（月度近似=年度跑赢比例）+ 超额"""
    train = [r for r in results if r["year"] <= _year(train_end)]
    valid = [r for r in results if r["year"] > _year(train_end)]

    def _stats(seg: list[dict]) -> dict:
        if not seg:
            return {"win_rate": 0, "excess": 0}
        wins = sum(1 for r in seg if r["port_ret"] > r["bench_ret"])
        excess = sum(r["port_ret"] - r["bench_ret"] for r in seg) / len(seg)
        return {
            "win_rate": round(wins / len(seg) * 100, 1),
            "excess": round(excess, 2),
            "n_years": len(seg),
        }

    ts, vs = _stats(train), _stats(valid)
    passed = vs["win_rate"] >= 55 and vs["excess"] > 0
    return {
        "train": ts,
        "valid": vs,
        "passed": passed,
        "verdict": "✅ 通过——入策略候选池" if passed else "❌ 未通过——归档",
    }


def main():
    start, end = "2016-01-01", "2026-06-30"
    bs.login()
    try:
        print("⏳ 拉取数据（30 只 × 10 年——约 2 分钟）…")
        r = run_idea(POOL, start, end)
        j = _judge(r["results"], TRAIN_END)
        print("\n🏆 裁决榜：小七滚雪球『股息率>5% 且 PE<10』（A 标准）")
        print(
            f"{'年份':<6}{'持仓':<6}{'组合%':<10}{'基准%':<10}{'组合净值':<10}{'基准净值'}"
        )
        for x in r["results"]:
            print(
                f"{x['year']:<6}{x['n_hold']:<6}{x['port_ret']:<10}"
                f"{x['bench_ret']:<10}{x['port_nav']:<10}{x['bench_nav']}"
            )
        print(f"\n训练段 {j['train']}")
        print(f"验证段 {j['valid']}")
        print(f"裁决：{j['verdict']}")
    finally:
        bs.logout()


if __name__ == "__main__":
    main()
