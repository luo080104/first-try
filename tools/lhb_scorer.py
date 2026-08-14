# -*- coding: utf-8 -*-
"""龙虎榜 5 维评分模块（观复信号层——aiagents-stock 框架 + akshare 真实字段适配）

用法:
    python lhb_scorer.py [start_date] [end_date]   # 默认近 5 个交易日
输出: Top10 评分表（含每维分数+理由）+ 上榜后 1/2 日验证对照

5 维评分（100 分制——可解释——观复讲解模式联动）:
    资金含金量 0-30: 净买额占总成交比（占比高=资金坚决）
    净买强度   0-25: 净买额/龙虎榜成交额（买卖力量比）
    卖出压力   0-20: 卖出额占成交额（越低越好——反向）
    活跃度     0-15: 换手率 5-20% 最佳（活跃但不过热）
    上榜原因   0-10: 涨幅偏离/涨停类加分 + 解读中机构买入加分
"""

import sys


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def score_row(r) -> dict:  # r: pandas Series 或 dict
    """单只股票 5 维评分——返回 {score, parts:[(名称,分数,理由)]}"""
    parts = []

    # 1. 资金含金量 0-30（净买额占总成交比——3% 以上满分）
    ratio = float(r.get("净买额占总成交比") or 0)
    s1 = _clamp(ratio / 3.0 * 30, 0, 30)
    parts.append(("资金含金量", round(s1, 1), f"净买占市场成交 {ratio:.1f}%"))

    # 2. 净买强度 0-25（净买额/龙虎榜成交额——全净买=满分）
    net = float(r.get("龙虎榜净买额") or 0)
    amt = float(r.get("龙虎榜成交额") or 0)
    strength = net / amt if amt else 0
    s2 = _clamp((strength + 1) / 2 * 25, 0, 25)
    parts.append(("净买强度", round(s2, 1), f"净买/成交 {strength:.0%}"))

    # 3. 卖出压力 0-20（卖出额占成交额反向）
    sell = float(r.get("龙虎榜卖出额") or 0)
    sell_ratio = sell / amt if amt else 1
    s3 = (1 - _clamp(sell_ratio, 0, 1)) * 20
    parts.append(("卖出压力", round(s3, 1), f"卖出占成交 {sell_ratio:.0%}"))

    # 4. 活跃度 0-15（换手率 5-20% 最佳）
    tr = float(r.get("换手率") or 0)
    if 5 <= tr <= 20:
        s4 = 15
    elif tr < 5:
        s4 = tr / 5 * 10
    else:
        s4 = max(15 - (tr - 20) * 0.5, 5)
    parts.append(("活跃度", round(s4, 1), f"换手 {tr:.1f}%"))

    # 5. 上榜原因 0-10
    reason = str(r.get("上榜原因") or "")
    s5 = 10 if any(k in reason for k in ("涨幅偏离", "涨停", "换手")) else 5
    note = f"原因: {reason[:20]}"
    # 解读中机构买入加分
    jd = str(r.get("解读") or "")
    if "机构买入" in jd:
        s5 = min(s5 + 3, 10)
        note += f" | {jd[:15]}"
    parts.append(("上榜原因", round(s5, 1), note))

    total = round(sum(p[1] for p in parts), 1)
    return {"total": total, "parts": parts}


def fetch_lhb(start_date: str, end_date: str):
    """拉取东财龙虎榜明细（akshare）"""
    import akshare as ak

    return ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else ""
    end = sys.argv[2] if len(sys.argv) > 2 else ""
    if not start or not end:
        from datetime import datetime, timedelta

        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")

    df = fetch_lhb(start, end)
    if df is None or df.empty:
        print(f"无数据（{start}-{end}）")
        return

    rows = [r for _, r in df.iterrows()]
    scored = [(score_row(r), r) for r in rows]
    scored.sort(key=lambda x: -x[0]["total"])

    print(f"龙虎榜 {len(rows)} 条（{start}-{end}）——Top10 评分:")
    print(
        f"{'排名':<4}{'代码':<8}{'名称':<10}{'总分':<7}{'涨跌幅%':<9}{'上榜后1日%':<10}{'上榜后2日%'}"
    )
    print("-" * 62)
    for i, (s, r) in enumerate(scored[:10], 1):
        d1 = r.get("上榜后1日")
        d2 = r.get("上榜后2日")
        print(
            f"{i:<4}{r['代码']:<8}{r['名称']:<10}{s['total']:<7}{r['涨跌幅']:<9}"
            f"{(f'{d1:.1f}' if d1 == d1 else '-'):<10}{(f'{d2:.1f}' if d2 == d2 else '-')}"
        )
    print()
    print("Top3 评分明细:")
    for i, (s, r) in enumerate(scored[:3], 1):
        print(f"\n#{i} {r['代码']} {r['名称']}（总分 {s['total']}）")
        for name, score, reason in s["parts"]:
            print(f"  {name}: {score} — {reason}")

    # 评分有效性粗验：高分 vs 低分 上榜后1日 平均
    highs = [
        r["上榜后1日"]
        for s, r in scored[:10]
        if r.get("上榜后1日") == r.get("上榜后1日")
    ]
    lows = [
        r["上榜后1日"]
        for s, r in scored[-10:]
        if r.get("上榜后1日") == r.get("上榜后1日")
    ]
    if highs and lows:
        print(
            f"\n评分有效性粗验（上榜后1日均涨跌）: Top10 {sum(highs) / len(highs):.2f}% vs 末10 {sum(lows) / len(lows):.2f}%"
        )


if __name__ == "__main__":
    main()
