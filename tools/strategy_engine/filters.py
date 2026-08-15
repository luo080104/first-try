# -*- coding: utf-8 -*-
"""观复战略层过滤器（策略库 v2——父母理念纪律层——无需回测直接启用）

规则来源：docs/观复策略库_父母样例.md
- B4 价值选股 8 标准（3-8 项都要满足，1-2 至少满足一项）
- B5 估值筛选（PE<15 或 PB<2 + 相对历史低潮 10% + 底线思维）
- N 不买清单（可量化部分）
- R 风控红线（输入标记）
输出：FilterResult{passed, reasons, blocked_by}——否决带理由（讲解模式联动）
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FilterResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)  # 通过的依据
    blocked_by: list[str] = field(default_factory=list)  # 否决的理由（命中哪条规则）


def check_value_8(f: dict[str, Any]) -> list[str]:
    """B4 价值选股 8 标准——返回未满足项清单（空=全满足）

    输入字段: dividend_yield(股息率), growth_ok(成长性), roe, ocf_gt_profit(现金流>利润),
              sales_margin(销售利润率), debt_ratio(负债率), is_leader(龙头), future_ok(前景)
    规则: 3-8 项都要满足；1-2 至少满足一项
    """
    fails = []
    # 1. 分红率高（股息率 >= 2% 视为"高"——书内"每年股息率最好能大于 4%"但高息股为特定策略——基础标准放 2%）
    if (f.get("dividend_yield") or 0) < 2.0:
        fails.append("B4-1 分红率不足（股息率<2%）")
    # 2. 成长性好
    if not f.get("growth_ok", False):
        fails.append("B4-2 成长性不足")
    # 3. ROE > 10%
    if (f.get("roe") or 0) <= 10.0:
        fails.append("B4-3 ROE 未达 10%")
    # 4. 现金流充沛（经营性现金流 > 利润）
    if not f.get("ocf_gt_profit", False):
        fails.append("B4-4 经营性现金流未大于利润")
    # 5. 销售利润率 > 10%
    if (f.get("sales_margin") or 0) <= 10.0:
        fails.append("B4-5 销售利润率未达 10%")
    # 6. 资产负债率 < 50%（电力/金融除外——最高 60%）
    debt = f.get("debt_ratio") or 0
    exempt = f.get("debt_exempt", False)  # 电力/金融豁免
    limit = 60.0 if exempt else 50.0
    if debt > limit:
        fails.append(f"B4-6 资产负债率 {debt}% 超限（{limit}%）")
    # 7. 一线龙头
    if not f.get("is_leader", False):
        fails.append("B4-7 非一线龙头")
    # 8. 未来前景向好
    if not f.get("future_ok", False):
        fails.append("B4-8 未来前景不明")
    return fails


def check_valuation(v: dict[str, Any]) -> list[str]:
    """B5 估值筛选——返回未满足项

    输入: pe_ttm, pb, pe_percentile(历史百分位——0-100), extreme_pe_ok(极端情况 PE 仍低),
          dividend_safety(股息率保障)
    规则: 绝对低（PE<15 或 PB<2）+ 相对低（百分位<10%）+ 底线思维
    """
    fails = []
    pe = v.get("pe_ttm") or 0
    pb = v.get("pb") or 0
    if pe <= 0 or pb <= 0:
        fails.append("B5 估值数据缺失")
        return fails
    if not (pe < 15 or pb < 2):
        fails.append(f"B5 绝对估值不低（PE={pe} PB={pb}——需 PE<15 或 PB<2）")
    if (v.get("pe_percentile") or 100) > 10.0:
        fails.append(
            f"B5 相对估值未到历史低潮（百分位 {v.get('pe_percentile')}% > 10%）"
        )
    if not v.get("extreme_pe_ok", True):
        fails.append("B5 极端情况 PE 无保障（底线思维）")
    if not v.get("dividend_safety", True):
        fails.append("B5 股息率无保障（底线思维）")
    return fails


def check_no_buy(q: dict[str, Any]) -> list[str]:
    """N 不买清单（可量化部分——N2/N3/N9/N13/N8/N11/N10）

    输入: pe_ttm, pb, ps(市销率), price_from_low(距低点涨幅%), listing_years(上市年数),
          holder_reduce(大股东减持), recent_surge(连续巨量阳线——最近 3 根量能异常),
          pe_gt30_recommended(大V强推且 PE>30——外部传入), sw_code(申万行业代码——N10 可选)
    """
    blocked = []
    pe = q.get("pe_ttm") or 0
    pb = q.get("pb") or 0
    ps = q.get("ps") or 0
    # N2 三高（PE/PB/PS 齐高）
    if pe > 30 and pb > 5 and ps > 10:
        blocked.append("N2 高PE+高PB+高PS 三高（纯泡沫）")
    # N3 低 PE 但大幅飙高的周期股（距低点涨幅 >100% 且 PE<15）
    if 0 < pe < 15 and (q.get("price_from_low") or 0) > 100:
        blocked.append("N3 低PE周期股大幅飙高（看位置和PB）")
    # N8 大股东减持
    if q.get("holder_reduce", False):
        blocked.append("N8 大股东减持（无条件清空/不买）")
    # N9 新股前 3 年
    if (q.get("listing_years") or 99) < 3:
        blocked.append("N9 新股上市未满 3 年")
    # N10 板块连续逆势 2 年以上走牛（申万行业指数近 2 年涨幅 >100%——书："基本后面都会走输大盘"）
    if q.get("sw_code"):
        chg = _sector_2y_surge(q["sw_code"])
        if chg is not None and chg > 100:
            blocked.append(
                f"N10 板块连逆 2 年走牛（行业指数 2 年 +{chg:.0f}%——走输大盘风险）"
            )
    # N11 平台连拉 3 根巨量阳线
    if q.get("recent_surge", False):
        blocked.append("N11 连续小阳后 3 根巨量阳线（90% 套）")
    # N13 大V 强推 + PE>30
    if q.get("pe_gt30_recommended", False) and pe > 30:
        blocked.append("N13 大V强推成长股且 PE>30（80% 顶）")
    # N14 荐股引流/杀猪盘信号（2026-08-15 UZI trap-detector 借鉴——8 信号精简为 4 个可输入标记）
    # 外部传入（讲解模式/大V 数据流）：pump_keywords(必涨/翻倍/稳赚话术),
    #          paid_group(付费群/直播间引流), cross_platform(多平台联动), fake_report(虚假研报)
    pump_hits = sum(
        1
        for k in ("pump_keywords", "paid_group", "cross_platform", "fake_report")
        if q.get(k, False)
    )
    if pump_hits >= 2:
        blocked.append(
            f"N14 荐股引流信号 {pump_hits}/4（必涨话术/付费群/多平台/虚假研报——杀猪盘风险）"
        )
    return blocked


def _sector_2y_surge(sw_code: str) -> float | None:
    """申万行业指数近 2 年涨幅%（N10 用——书"连逆 2 年走牛板块不能买"）

    akshare index_hist_sw（实测 6434 日——1999 起可用）——失败返回 None（降级不阻塞）
    """
    try:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        import akshare as ak

        df = ak.index_hist_sw(symbol=sw_code, period="day")
        if df is None or len(df) < 250:
            return None
        closes = df["收盘"].astype(float)
        last = closes.iloc[-1]
        # 约 2 年前（250 交易日×2）
        two_years_ago = closes.iloc[-500] if len(closes) >= 500 else closes.iloc[0]
        if two_years_ago <= 0:
            return None
        return round((last / two_years_ago - 1) * 100, 1)
    except Exception:
        return None


def check_redlines(r: dict[str, bool]) -> list[str]:
    """R1-R8 风控红线——输入为违规标记（True=违规）

    输入: borrowing(借钱), shorting(做空), gambling(投机不懂的), front_run(抢跑),
          over_concentrated(过度集中), holding_deteriorated(基本面恶化持仓), easy_cover(轻易补仓)
    """
    violated = []
    mapping = {
        "borrowing": "R1 借钱投资（红线——闲钱投资）",
        "shorting": "R2 做空/衍生品（红线——远离期权期货）",
        "gambling": "R3 投机不懂的标的（红线——不懂不做）",
        "front_run": "R4 抢跑（红线——新钱只在大盘低潮入市）",
        "over_concentrated": "R5 过度集中（红线——个股≤10%/行业≤25%）",
        "holding_deteriorated": "R6 基本面恶化持仓未卖（红线——择机卖出）",
        "easy_cover": "R7 轻易补仓（红线——拉开差距才补）",
    }
    for key, msg in mapping.items():
        if r.get(key, False):
            violated.append(msg)
    return violated


def filter_stock(
    f: dict[str, Any], v: dict[str, Any], q: dict[str, Any], r: dict[str, bool]
) -> FilterResult:
    """战略层总过滤器——通过/否决+理由

    任一清单命中 → 否决（blocked_by 列全部理由——讲解模式联动）
    """
    result = FilterResult(passed=True)
    # 不买清单（最优先——排除法）
    result.blocked_by.extend(check_no_buy(q))
    # 风控红线
    result.blocked_by.extend(check_redlines(r))
    # 价值 8 标准（B4——3-8 都要满足：1/2 至少一项——返回的是未满足项——全部列出）
    value_fails = check_value_8(f)
    first_two = [x for x in value_fails if x.startswith(("B4-1", "B4-2"))]
    rest = [x for x in value_fails if not x.startswith(("B4-1", "B4-2"))]
    # 1-2 至少满足一项（1-2 都在 fail 列表=都不满足）
    if len(first_two) == 2:
        result.blocked_by.extend(first_two)
    # 3-8 必须全满足（任一 fail 即否决）
    result.blocked_by.extend(rest)
    # 估值筛选（B5）
    result.blocked_by.extend(check_valuation(v))
    # 汇总
    if result.blocked_by:
        result.passed = False
    else:
        result.reasons = [
            "B4 价值 8 标准通过",
            "B5 估值筛选通过",
            "N 不买清单未命中",
            "R 红线未违反",
        ]
    return result
