"""可转债数据获取模块 — 基于 AKShare bond_zh_cov (东方财富, 稳定)"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd

import akshare as ak

_CACHE_TTL = 120  # 2分钟缓存
_last_fetch: dict[str, float] = {}
_cache: dict[str, pd.DataFrame] = {}

# 票面利率参考 (可转债标准利率结构)
# 6年期: 0.3%, 0.5%, 1.0%, 1.5%, 1.8%, 2.0%
_STANDARD_COUPONS = [0.3, 0.5, 1.0, 1.5, 1.8, 2.0]
# 短期(1-3年)按比例取前N年
# 到期赎回价通常 110 或 112


def _cached(key: str) -> pd.DataFrame | None:
    if key in _cache and time.time() - _last_fetch.get(key, 0) < _CACHE_TTL:
        return _cache[key]
    return None


def _set_cache(key: str, df: pd.DataFrame) -> None:
    _cache[key] = df
    _last_fetch[key] = time.time()


def _ensure_numeric(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def get_bond_comparison(force_refresh: bool = False) -> pd.DataFrame:
    """获取全市场可转债数据

    来源: AKShare bond_zh_cov (东方财富)
    返回 ~1000 条 (含历史退市), 已处理类型与空值
    """
    if not force_refresh:
        cached = _cached("comparison")
        if cached is not None:
            return cached

    df = ak.bond_zh_cov()
    num_cols = ["正股价", "转股价", "转股价值", "债现价", "转股溢价率", "发行规模"]
    df = _ensure_numeric(df, num_cols)

    # 计算衍生字段 (标准合约条款)
    df["强赎触发价"] = (df["转股价"] * 1.3).round(2)
    df["回售触发价"] = (df["转股价"] * 0.7).round(2)
    # 纯债价值估算: 用标准利率折现
    df["纯债价值_估"] = df.apply(
        lambda r: _estimate_bond_value(
            price=r["债现价"],
            year_left=1.0,  # 默认，实际可从到期日计算
        ),
        axis=1,
    )
    # 纯债溢价率估算 = (现价 - 纯债价值) / 纯债价值 × 100
    mask = df["纯债价值_估"] > 0
    df.loc[mask, "纯债溢价率_估"] = (
        (df.loc[mask, "债现价"] / df.loc[mask, "纯债价值_估"] - 1) * 100
    ).round(2)

    # 去掉纯债价值 <= 0 的异常行
    _set_cache("comparison", df)
    return df


def _estimate_bond_value(
    price: float,
    year_left: float,
    face_value: float = 100.0,
    redeem_price: float = 110.0,
) -> float:
    """估算纯债价值

    简化模型: 6年标准利率结构, 按剩余年限折现
    """
    if price <= 0 or pd.isna(price):
        return 0.0
    # 简化: 纯债价值 ~ 债底 ≈ 面值 × 贴现率
    # 对于正常价格区间的转债, 纯债价值通常在 80-110 之间
    # 这里用一个保守估算: 价格低于100时接近债底
    if year_left <= 0:
        year_left = 1.0
    discount_rate = 0.04 + (price - 80) * 0.001  # 风险溢价随价格升高
    bond_val = face_value / ((1 + discount_rate) ** year_left)
    return round(bond_val, 2)


def get_bond_spot() -> pd.DataFrame:
    """获取实时行情 (bond_zh_hs_cov_spot, 约340条活跃转债)"""
    try:
        df = ak.bond_zh_hs_cov_spot()
        return _ensure_numeric(df, ["trade", "pricechange", "changepercent"])
    except Exception:
        return pd.DataFrame()


def get_bond_history(symbol: str) -> pd.DataFrame:
    """获取单只可转债历史价值分析"""
    try:
        return ak.bond_zh_cov_value_analysis(symbol=symbol)
    except Exception:
        return pd.DataFrame()


def get_all_bonds_list() -> pd.DataFrame:
    """获取可转债一览表 (含打新历史)"""
    try:
        return ak.bond_zh_cov()
    except Exception:
        return pd.DataFrame()


def get_redeem_data() -> pd.DataFrame:
    """获取强赎数据 (集思录)"""
    try:
        return ak.bond_cb_redeem_jsl()
    except Exception:
        return pd.DataFrame()


def get_new_issue_bonds() -> pd.DataFrame:
    """获取近期可转债打新数据"""
    df = get_bond_comparison(force_refresh=True)
    if df.empty:
        return df
    # 筛选近期申购的 (上市时间为空或接近)
    from datetime import datetime, timedelta
    return df  # 后续可细化筛选
