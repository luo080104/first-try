"""可转债数据获取模块 — 基于 AKShare bond_zh_cov (东方财富, 稳定)"""

from __future__ import annotations

import time

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
    """获取全市场可转债数据——2026-08-15 数据核验修复（第三批案例精读发现）

    来源链（多源 fallback——P0 交叉验证精神）：
      ① bond_cov_comparison（东财 push2——321 只真实交易中转债——字段全含强赎触发价）
      ② bond_zh_cov（东财主接口——1049 条含未上市——过滤 100 占位后 310 只真实成交）
    问题记录：bond_zh_cov 当前 70% 价格=100 占位（无成交/未上市）——案例时代是真实价格
    修复：占位过滤（价=100 且无成交 → 剔除）+ 统一字段映射到策略需要的列名
    """
    if not force_refresh:
        cached = _cached("comparison")
        if cached is not None:
            return cached

    df = _fetch_comparison_primary()
    if df.empty:
        df = _fetch_comparison_fallback()
    if df.empty:
        return pd.DataFrame()
    df = df.copy()  # 独立副本（避免下游修改污染缓存源）

    # 过滤 100 占位（无成交/未上市债——价格=100 且溢价率空的剔除）
    if "债现价" in df.columns:
        df = df.loc[df["债现价"] != 100.0].copy()
    if "转股溢价率" in df.columns:
        df = df.loc[df["转股溢价率"].notna()].copy()

    # 计算衍生字段 (标准合约条款)
    if "转股价" in df.columns and "强赎触发价" not in df.columns:
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

    _set_cache("comparison", df)
    return df


def _fetch_comparison_primary() -> pd.DataFrame:
    """主源：bond_cov_comparison（东财 push2——真实交易中转债——字段最全）

    失败返回空 DataFrame（push2 间歇不可达——2026-08-15 实测）——调用方切备用
    """
    try:
        import os

        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        raw = ak.bond_cov_comparison()
        if raw is None or raw.empty:
            return pd.DataFrame()
        # type: ignore[arg-type]——akshare 返回 Any——pandas stub 构造重载返回联合（运行时确认 DataFrame）
        df: pd.DataFrame = pd.DataFrame(raw)  # type: ignore[arg-type]
        # 列名映射（push2 列名 → 策略统一列名）
        rename = {
            "转债代码": "债券代码",
            "转债名称": "债券简称",
            "转债最新价": "债现价",
            "正股最新价": "正股价",
            "转债涨跌幅": "涨跌幅",
        }
        df = df.rename(columns=rename)
        if "债现价" not in df.columns or "转股溢价率" not in df.columns:
            return pd.DataFrame()
        return df
    except Exception:
        return pd.DataFrame()


def _fetch_comparison_fallback() -> pd.DataFrame:
    """备用：bond_zh_cov（主接口——1049 条——过滤 100 占位后 ~310 真实成交）"""
    try:
        import os

        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        raw = ak.bond_zh_cov()
        if raw is None or raw.empty:
            return pd.DataFrame()
        # type: ignore[arg-type]——同上（akshare 无类型标注）
        df: pd.DataFrame = pd.DataFrame(raw)  # type: ignore[arg-type]
        df = _ensure_numeric(df, ["正股价", "转股价", "转股价值", "债现价", "转股溢价率", "发行规模"])
        return df
    except Exception:
        return pd.DataFrame()


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
    return df  # 后续可细化筛选（打新日历 Q15 待接入）
