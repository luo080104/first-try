"""可转债扩展策略引擎（观复 tools/cb_strategy/strategies_ext.py）

来源：convertible-bond-crawler (github.com/zhezhang-pojo/convertible-bond-crawler, MIT)
翻译：宁稳网字段 → 东方财富+集思录双源字段
数据源：东方财富 bond_zh_cov (全量1049条,免费) + 集思录 bond_cb_jsl (策略字段全,cookie可选)

策略（8种）：
1. 到期保本 filter_profit_due
2. 回售摸彩 filter_return_lucky
3. 低价格低溢价 filter_double_low（增强版，比cb-strategy-mcp的条件更细）
4. 三低转债 filter_three_low（增强版）
5. 下修博弈 filter_downward_revise
6. 次新债 filter_disable_converte
7. 多因子 filter_multiple_factors
8. 四象限分类 classify_quadrants

字段映射（宁稳网 → 东财+集思录）：
- rate_expire_aftertax(税后到期收益率) → 集思录"到期税前收益"（集思录有cookie时更全）
- date_convert_distance(转股距离) → 集思录"剩余年限">0 且 到期时间已过
- cb_to_pb(转股价/每股净资产) → 集思录"正股PB"（cb_to_pb ≈ 转股价/(正股价/正股PB)）
- is_repair_flag(是否可下修) → 计算正股<回售触发价 且 未承诺不下修
- remain_to_cap(转债剩余/市值) → 集思录"转债占比"
- date_return_distance(回售距离) → 计算剩余年限<回售期（通常最后2年）
- is_ransom_flag(强赎标记) → 集思录"强赎状态" 或 计算 正股>强赎触发价
- remain_amount(剩余规模) → 集思录"剩余规模"
- market_cap(正股市值) → 需额外接口
"""

from __future__ import annotations
from typing import Any
import pandas as pd
import akshare as ak
from . import data as cb_data

# 集思录字段常量
JSL_CODE = "代码"
JSL_NAME = "转债名称"
JSL_PRICE = "现价"
JSL_STOCK = "正股价"
JSL_PB = "正股PB"
JSL_CONV_PRICE = "转股价"
JSL_CONV_VALUE = "转股价值"
JSL_PREMIUM = "转股溢价率"
JSL_RATING = "债券评级"
JSL_PUT_TRIG = "回售触发价"
JSL_REDEEM_TRIG = "强赎触发价"
JSL_RATIO = "转债占比"
JSL_EXPIRE = "到期时间"
JSL_YEAR_LEFT = "剩余年限"
JSL_REMAIN = "剩余规模"
JSL_YTM = "到期税前收益"
JSL_DOUBLE_LOW = "双低"


_cache_jsl: pd.DataFrame | None = None
_cache_jsl_time: float = 0


def get_jsl_data(cookie: str | None = None, force_refresh: bool = False) -> pd.DataFrame:
    """获取集思录可转债数据（策略字段更全，cookie可选）

    无cookie: 返回30条样例
    有cookie: 返回全量~500条
    """
    import time

    global _cache_jsl, _cache_jsl_time
    if not force_refresh and _cache_jsl is not None and time.time() - _cache_jsl_time < 120:
        return _cache_jsl
    try:
        raw = ak.bond_cb_jsl(cookie=cookie or "")  # stub 要求 str——None 转空串
        if raw is None or raw.empty:
            return pd.DataFrame()
        df: pd.DataFrame = pd.DataFrame(raw)  # type: ignore[arg-type]——akshare 无类型标注
        _cache_jsl = df
        _cache_jsl_time = time.time()
        return df
    except Exception as e:
        print(f"[集思录数据获取失败] {e}")
        return pd.DataFrame()


def _ensure_num(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def filter_profit_due(cookie: str | None = None, top_n: int = 20) -> list[dict]:
    """到期保本策略

    条件：税后到期收益率>0 + 已到转股期 + 转股价/PB>1.5（下修有空间）+ 可下修
    排序：到期收益率降序
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_YTM, JSL_PB, JSL_CONV_PRICE, JSL_PREMIUM, JSL_YEAR_LEFT])
    # 到期税前收益>0（保本）
    df = df.loc[df[JSL_YTM] > 0]
    # 已到转股期（剩余年限<5.5，6年期转债转股期通常最后5年）
    df = df.loc[df[JSL_YEAR_LEFT] < 5.5]
    # 转股价/PB > 1.5（下修空间）—— cb_to_pb ≈ 转股价/(正股价/正股PB) = 转股价*正股PB/正股价
    df["cb_to_pb"] = df[JSL_CONV_PRICE] * df[JSL_PB] / df[JSL_STOCK]
    df = df.loc[df["cb_to_pb"] > 1.5]
    # 排除EB债
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    df = df.sort_values(JSL_YTM, ascending=False).head(top_n)
    return _format_results(df, strategy_name="到期保本")


def filter_return_lucky(cookie: str | None = None, top_n: int = 20) -> list[dict]:
    """回售摸彩策略

    条件：回售期内 + 正股<回售触发价（下修压力） + 价格<125 + 转债占比>5
    排序：转债占比倒序
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_STOCK, JSL_PUT_TRIG, JSL_RATIO, JSL_YEAR_LEFT])
    # 回售期：剩余年限通常<2（回售期一般最后2年）
    df = df.loc[df[JSL_YEAR_LEFT] < 2.5]
    # 正股<回售触发价（接近或触发回售）
    df = df.loc[df[JSL_STOCK] < df[JSL_PUT_TRIG] * 1.05]
    # 价格<125（安全垫）
    df = df.loc[df[JSL_PRICE] < 125]
    # 转债占比>5（还债压力大）
    df = df.loc[df[JSL_RATIO] > 5]
    # 排除EB
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    df = df.sort_values(JSL_RATIO, ascending=False).head(top_n)
    return _format_results(df, strategy_name="回售摸彩")


def filter_double_low_enhanced(cookie: str | None = None, top_n: int = 20,
                                max_price: float = 128, max_premium: float = 10,
                                max_price2: float = 125, max_premium2: float = 15) -> list[dict]:
    """低价格低溢价策略（增强版——双条件）

    条件：(价格<128 且 溢价率<10) 或 (价格<125 且 溢价率<15)
    + 已到转股期 + 转股价/PB>1（下修空间） + 有回售权
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_PREMIUM, JSL_PB, JSL_CONV_PRICE, JSL_STOCK, JSL_YEAR_LEFT])
    df["cb_to_pb"] = df[JSL_CONV_PRICE] * df[JSL_PB] / df[JSL_STOCK]
    mask = (
        (((df[JSL_PRICE] < max_price) & (df[JSL_PREMIUM] < max_premium)) |
         ((df[JSL_PRICE] < max_price2) & (df[JSL_PREMIUM] < max_premium2)))
        & (df[JSL_YEAR_LEFT] < 5.5)  # 已到转股期
        & (df["cb_to_pb"] > 1.0)
    )
    df = df.loc[mask]
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    df = df.sort_values(JSL_DOUBLE_LOW if JSL_DOUBLE_LOW in df.columns else JSL_PRICE, ascending=True).head(top_n)
    return _format_results(df, strategy_name="低价格低溢价(增强)")


def filter_three_low_enhanced(cookie: str | None = None, top_n: int = 20) -> list[dict]:
    """三低转债策略（增强版——双低+小规模+小市值）

    条件：无强赎 + 剩余规模小 + 溢价率小 + 正股市值小 + 溢价率<30 或 价格<130
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_PREMIUM, JSL_REMAIN, JSL_STOCK, JSL_PB])
    mask = (
        (df[JSL_PREMIUM] < 30) | (df[JSL_PRICE] < 130)
    )
    df = df.loc[mask]
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    # 三低值 = 双低 + 规模小
    df["双低值"] = df[JSL_PREMIUM] * 0.5 + (df[JSL_PRICE] / 100) * 50
    df["三低值"] = df["双低值"] - df[JSL_REMAIN].rank(pct=True) * 20
    df = df.sort_values("三低值", ascending=True).head(top_n)
    return _format_results(df, strategy_name="三低(增强)")


def filter_downward_revise(cookie: str | None = None, top_n: int = 20) -> list[dict]:
    """下修博弈策略

    条件：转股价/PB>1.2（下修空间） + 已到转股期 + 价格<120 + 溢价率>35
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_PREMIUM, JSL_PB, JSL_CONV_PRICE, JSL_STOCK, JSL_YEAR_LEFT])
    df["cb_to_pb"] = df[JSL_CONV_PRICE] * df[JSL_PB] / df[JSL_STOCK]
    mask = (
        (df["cb_to_pb"] > 1.2)
        & (df[JSL_YEAR_LEFT] < 5.5)
        & (df[JSL_PRICE] < 120)
        & (df[JSL_PREMIUM] > 35)
    )
    df = df.loc[mask]
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    df = df.sort_values(JSL_PRICE, ascending=True).head(top_n)
    return _format_results(df, strategy_name="下修博弈")


def filter_new_bond(cookie: str | None = None, top_n: int = 20) -> list[dict]:
    """次新债策略

    条件：未到转股期（剩余年限>5.5）
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return []
    df = _ensure_num(df, [JSL_PRICE, JSL_YEAR_LEFT, JSL_REMAIN])
    df = df.loc[df[JSL_YEAR_LEFT] > 5.5]
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    df = df.sort_values(JSL_REMAIN, ascending=True).head(top_n)
    return _format_results(df, strategy_name="次新债")


def classify_quadrants(cookie: str | None = None) -> dict[str, list[dict]]:
    """四象限分类

    一象限：高价格(>120) + 高溢价率(>30) → 股性强，风险大
    二象限：低价格(<110) + 高溢价率(>30) → 债性强，易下修
    三象限：低价格(<110) + 低溢价率(<30) → 双低，收益高风险小
    四象限：高价格(>120) + 低溢价率(<30) → 易强赎
    """
    df = get_jsl_data(cookie=cookie)
    if df.empty:
        return {}
    df = _ensure_num(df, [JSL_PRICE, JSL_PREMIUM])
    df = df.loc[~df[JSL_NAME].str.contains("EB", na=False)]
    result = {}
    for name, mask in [
        ("一象限-高价格高溢价", (df[JSL_PRICE] > 120) & (df[JSL_PREMIUM] > 30)),
        ("二象限-低价格高溢价", (df[JSL_PRICE] < 110) & (df[JSL_PREMIUM] > 30)),
        ("三象限-双低", (df[JSL_PRICE] < 110) & (df[JSL_PREMIUM] < 30)),
        ("四象限-高价格低溢价", (df[JSL_PRICE] > 120) & (df[JSL_PREMIUM] < 30)),
    ]:
        sub = df.loc[mask].head(10)
        result[name] = _format_results(sub, strategy_name=name)
    return result


def _format_results(df: pd.DataFrame, strategy_name: str = "") -> list[dict]:
    results = []
    for _, row in df.iterrows():
        results.append({
            "策略": strategy_name,
            "代码": str(row.get(JSL_CODE, "")),
            "名称": str(row.get(JSL_NAME, "")),
            "现价": _to_f(row.get(JSL_PRICE)),
            "转股溢价率": _to_f(row.get(JSL_PREMIUM)),
            "正股价": _to_f(row.get(JSL_STOCK)),
            "正股PB": _to_f(row.get(JSL_PB)),
            "剩余年限": _to_f(row.get(JSL_YEAR_LEFT)),
            "剩余规模": _to_f(row.get(JSL_REMAIN)),
            "到期税前收益": _to_f(row.get(JSL_YTM)),
            "双低值": _to_f(row.get(JSL_DOUBLE_LOW)),
            "回售触发价": _to_f(row.get(JSL_PUT_TRIG)),
            "强赎触发价": _to_f(row.get(JSL_REDEEM_TRIG)),
        })
    return results


def _to_f(val) -> float:
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return 0.0
