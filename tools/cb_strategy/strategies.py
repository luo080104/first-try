"""可转债高级策略引擎"""

from __future__ import annotations

from typing import Any

import pandas as pd

from . import data

# 字段映射 (与 data.py 输出一致)
_COL_CODE = "债券代码"
_COL_NAME = "债券简称"
_COL_PRICE = "债现价"
_COL_STOCK = "正股价"
_COL_CONV_PRICE = "转股价"
_COL_CONV_VALUE = "转股价值"
_COL_PREMIUM = "转股溢价率"
_COL_ISSUE_AMT = "发行规模"
_COL_REDEEM_TRIG = "强赎触发价"
_COL_PUT_TRIG = "回售触发价"
_COL_BOND_VALUE = "纯债价值_估"
_COL_BOND_PREMIUM = "纯债溢价率_估"


def _ensure_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _to_float(val: Any) -> float:
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.0


def dual_low_strategy(
    top_n: int = 20,
    min_price: float = 90.0,
    max_price: float = 130.0,
    max_premium: float = 50.0,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """双低策略 — 转股溢价率 + 价格双低排序

    双低值 = 转股溢价率 + (债现价 / 100) × 10
    筛选范围: 90-130元, 溢价率 ≤ 50%, 发行规模 > 0.3亿
    """
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [_COL_PRICE, _COL_PREMIUM, _COL_ISSUE_AMT])

    # 过滤退市债
    df = df.loc[~df[_COL_NAME].str.contains("退", na=False)]

    mask = (
        (df[_COL_PRICE] >= min_price)
        & (df[_COL_PRICE] <= max_price)
        & (df[_COL_PREMIUM] <= max_premium)
        & (df[_COL_ISSUE_AMT].fillna(0) > 0.3)
    )

    filtered = df.loc[mask].copy()
    if filtered.empty:
        return []

    # 经典双低值 ≈ 转股溢价率 + (债现价 / 100) × 10
    filtered["双低值"] = (
        filtered[_COL_PREMIUM] * 0.5
        + (filtered[_COL_PRICE] / 100) * 50
    )
    filtered = filtered.sort_values("双低值", ascending=True).head(top_n)

    results = []
    for _, row in filtered.iterrows():
        results.append({
            "代码": str(row.get(_COL_CODE, "")),
            "名称": str(row.get(_COL_NAME, "")),
            "现价": _to_float(row.get(_COL_PRICE)),
            "转股溢价率": _to_float(row.get(_COL_PREMIUM)),
            "双低值": _to_float(row.get("双低值")),
            "转股价值": _to_float(row.get(_COL_CONV_VALUE)),
            "发行规模": f"{_to_float(row.get(_COL_ISSUE_AMT))}亿",
            "正股价": _to_float(row.get(_COL_STOCK)),
            "强赎触发价": _to_float(row.get(_COL_REDEEM_TRIG)),
        })
    return results


def triple_low_strategy(
    top_n: int = 20,
    min_price: float = 90.0,
    max_price: float = 130.0,
    max_premium: float = 50.0,
    max_balance: float = 10.0,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """三低策略 — 双低 + 发行规模小

    小型转债弹性更大, 容易受游资关注
    条件: 发行规模 ≤ max_balance (亿)
    """
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [
        _COL_PRICE, _COL_PREMIUM, _COL_ISSUE_AMT,
    ])

    # 过滤退市债
    df = df.loc[~df[_COL_NAME].str.contains("退", na=False)]

    mask = (
        (df[_COL_PRICE] >= min_price)
        & (df[_COL_PRICE] <= max_price)
        & (df[_COL_PREMIUM] <= max_premium)
        & (df[_COL_ISSUE_AMT].fillna(0) > 0.3)
        & (df[_COL_ISSUE_AMT].fillna(0) <= max_balance)
    )

    filtered = df.loc[mask].copy()
    if filtered.empty:
        return []

    # 双低值
    filtered["双低值"] = (
        filtered[_COL_PREMIUM] * 0.5
        + (filtered[_COL_PRICE] / 100) * 50
    )
    # 规模越小分越高 (0~10)
    max_s = filtered[_COL_ISSUE_AMT].max()
    min_s = filtered[_COL_ISSUE_AMT].min()
    range_s = max_s - min_s if max_s > min_s else 1
    filtered["规模得分"] = (max_s - filtered[_COL_ISSUE_AMT]) / range_s * 10
    # 三低值 = 双低 × 0.7 - 规模得分 × 0.3
    filtered["三低值"] = filtered["双低值"] * 0.7 - filtered["规模得分"] * 3

    filtered = filtered.sort_values("三低值", ascending=True).head(top_n)

    results = []
    for _, row in filtered.iterrows():
        results.append({
            "代码": str(row.get(_COL_CODE, "")),
            "名称": str(row.get(_COL_NAME, "")),
            "现价": _to_float(row.get(_COL_PRICE)),
            "转股溢价率": _to_float(row.get(_COL_PREMIUM)),
            "双低值": _to_float(row.get("双低值")),
            "三低值": _to_float(row.get("三低值")),
            "发行规模": f"{_to_float(row.get(_COL_ISSUE_AMT))}亿",
            "正股价": _to_float(row.get(_COL_STOCK)),
        })
    return results


def ytm_ranking(
    top_n: int = 30,
    min_ytm: float = 0.0,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """到期收益率估算排名

    用 (100 - 债现价) / 到期年限 作为 YTM 代理指标
    加上价格越接近面值 YTM 越高的逻辑
    """
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [_COL_PRICE, _COL_PREMIUM, _COL_ISSUE_AMT])

    # 过滤退市债
    df = df.loc[~df[_COL_NAME].str.contains("退", na=False)]

    # YTM proxy: 现价越低, YTM 越高
    mask = (df[_COL_PRICE] > 80) & (df[_COL_PRICE] < 115) & (df[_COL_ISSUE_AMT].fillna(0) > 0.3)
    filtered = df.loc[mask].copy()
    if filtered.empty:
        return []

    # 简单YTM估算: (110 - 现价) / 6 (假设6年到期, 赎回价110)
    filtered["预估YTM"] = ((110 - filtered[_COL_PRICE]) / 6 * 100 / filtered[_COL_PRICE] * 100).round(2)
    # YTM封顶 50%
    filtered["预估YTM"] = filtered["预估YTM"].clip(upper=50.0)

    # 同时要求溢价率不要太高的 (> -5% 且 < 80%)
    filtered = filtered[(filtered[_COL_PREMIUM] > -5) & (filtered[_COL_PREMIUM] < 80)]
    filtered = filtered.sort_values("预估YTM", ascending=False).head(top_n)

    results = []
    for _, row in filtered.iterrows():
        results.append({
            "代码": str(row.get(_COL_CODE, "")),
            "名称": str(row.get(_COL_NAME, "")),
            "现价": _to_float(row.get(_COL_PRICE)),
            "预估YTM": f"{_to_float(row.get('预估YTM'))}%",
            "转股溢价率": _to_float(row.get(_COL_PREMIUM)),
            "发行规模": f"{_to_float(row.get(_COL_ISSUE_AMT))}亿",
            "转股价值": _to_float(row.get(_COL_CONV_VALUE)),
        })
    return results


def early_redemption_monitor(
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """强赎监控 — 正股价接近或超过强赎触发价

    强赎触发价 = 转股价 × 130%
    判断: 正股价 / 强赎触发价 比例
    """
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [_COL_STOCK, _COL_REDEEM_TRIG, _COL_PRICE, _COL_ISSUE_AMT])

    # 过滤退市债
    df = df.loc[~df[_COL_NAME].str.contains("退", na=False)]

    results = []
    for _, row in df.iterrows():
        stock = _to_float(row.get(_COL_STOCK))
        trig = _to_float(row.get(_COL_REDEEM_TRIG))
        code = str(row.get(_COL_CODE, ""))
        name = str(row.get(_COL_NAME, ""))

        if stock <= 0 or trig <= 0:
            continue
        if code in ("nan", ""):
            continue

        ratio = round((stock / trig) * 100, 2)

        if ratio < 80:
            continue  # 太远的不展示

        status = "安全"
        if ratio >= 130:
            status = "🔥 已触发强赎"
        elif ratio >= 100:
            status = "⚠️ 接近强赎"

        pct_display = f"{ratio}%" if not pd.isna(ratio) and ratio != float("inf") else "N/A"

        results.append({
            "代码": code,
            "名称": name,
            "正股价": stock,
            "强赎触发价": trig,
            "正股/触发价": pct_display,
            "债现价": _to_float(row.get(_COL_PRICE)),
            "状态": status,
        })

    results.sort(
        key=lambda x: _to_float(x["正股/触发价"].replace("%", ""))
        if "N/A" not in x["正股/触发价"]
        else 0.0,
        reverse=True,
    )
    return results


def revision_arbitrage_analysis(
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """下修博弈分析 — 正股价低于回售触发价, 公司有下修动力

    回售触发价 = 转股价 × 70%
    博弈评分 = 回售压力分 + 下修空间分
    """
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [
        _COL_STOCK, _COL_PUT_TRIG, _COL_PREMIUM, _COL_PRICE, _COL_ISSUE_AMT,
    ])

    # 过滤退市债
    df = df.loc[~df[_COL_NAME].str.contains("退", na=False)]

    results = []
    for _, row in df.iterrows():
        stock = _to_float(row.get(_COL_STOCK))
        trig = _to_float(row.get(_COL_PUT_TRIG))
        premium = _to_float(row.get(_COL_PREMIUM))
        price = _to_float(row.get(_COL_PRICE))
        issue = _to_float(row.get(_COL_ISSUE_AMT))
        code = str(row.get(_COL_CODE, ""))
        name = str(row.get(_COL_NAME, ""))

        if stock <= 0 or trig <= 0:
            continue
        if code in ("nan", ""):
            continue

        ratio = round((stock / trig) * 100, 2)
        if ratio >= 100:
            continue  # 未接近回售

        # 博弈评分
        score = 0
        # 回售压力: 正股价越低, 压力越大
        if ratio < 100:
            score += (100 - ratio) * 0.4
        # 下修空间: 溢价率高好操作
        if premium > 30:
            score += (premium - 30) * 0.3
        # 规模小的更容易操作
        if 0 < issue < 5:
            score += 5

        if score < 10:
            continue

        results.append({
            "代码": code,
            "名称": name,
            "现价": price,
            "正股价": stock,
            "回售触发价": trig,
            "正股/回售价": f"{ratio}%",
            "转股溢价率": premium,
            "博弈评分": round(score, 1),
        })

    results.sort(key=lambda x: x["博弈评分"], reverse=True)
    return results


def market_overview(force_refresh: bool = False) -> dict[str, Any]:
    """市场概览"""
    df: pd.DataFrame = data.get_bond_comparison(force_refresh=force_refresh)
    df = _ensure_numeric(df, [_COL_PRICE, _COL_PREMIUM, _COL_ISSUE_AMT])

    # .loc[:, col] 明确列访问（pandas-stub：df[col] 返回 DataFrame|Series 联合——float() 会误报）
    prices = df.loc[:, _COL_PRICE].dropna()
    premiums = df.loc[:, _COL_PREMIUM].dropna()

    below_100 = int((prices < 100).sum())
    btwn_100_120 = int(((prices >= 100) & (prices < 120)).sum())
    btwn_120_130 = int(((prices >= 120) & (prices < 130)).sum())
    above_130 = int((prices >= 130).sum())

    return {
        "转债总数": len(df),
        "平均价格": round(float(prices.mean()), 2),
        "中位数价格": round(float(prices.median()), 2),
        "最高价": round(float(prices.max()), 2),
        "最低价": round(float(prices.min()), 2),
        "平均转股溢价率": round(float(premiums.mean()), 2),
        "价格分布": {
            "<100元": below_100,
            "100-120元": btwn_100_120,
            "120-130元": btwn_120_130,
            "≥130元": above_130,
        },
        "更新时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
    }
