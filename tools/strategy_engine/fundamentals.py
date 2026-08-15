# -*- coding: utf-8 -*-
"""观复基本面数据管线（价值面 40 分输入——a-stock-data 接口内嵌）

字段：roe / sales_margin / debt_ratio / ocf_gt_profit / dividend_yield / growth_ok
数据源：新浪三表（sina_financial_report）+ 东财分红（dividend_history）+ akshare 财务指标
缓存：日级（code-reviewer 性能视角——每日一次拉取）
"""

from __future__ import annotations

import time
from typing import Any

import requests

_UA = {"User-Agent": "Mozilla/5.0"}
_cache: dict[str, tuple[float, dict[str, Any]]] = {}  # code -> (拉取时间, 数据)
_CACHE_TTL = 86400  # 日级


def _sina_report(code: str, report_type: str, num: int = 4) -> list[dict]:
    """新浪财报三表（lrb 利润表/fzb 资产负债表/llb 现金流量表）"""
    prefix = "sh" if code.startswith("6") else "sz"
    url = (
        "https://quotes.sina.cn/cn/api/openapi.php/"
        "CompanyFinanceService.getFinanceReport2022"
    )
    params = {
        "paperCode": f"{prefix}{code}",
        "source": report_type,
        "type": "0",
        "page": "1",
        "num": str(num),
    }
    r = requests.get(url, params=params, headers=_UA, timeout=15)
    report_list = (
        r.json().get("result", {}).get("data", {}).get("report_list", {}) or {}
    )
    rows = []
    for period in sorted(report_list.keys(), reverse=True)[:num]:
        obj = report_list[period]
        rec: dict[str, Any] = {"报告期": f"{period[:4]}-{period[4:6]}-{period[6:8]}"}
        for it in obj.get("data", []) or []:
            title = it.get("item_title", "")
            if not title or it.get("item_value") is None:
                continue
            rec[title] = it.get("item_value")
            if it.get("item_tongbi") not in (None, ""):
                rec[title + "_同比"] = it.get("item_tongbi")
        rows.append(rec)
    return rows


def _dividend_history(code: str, page_size: int = 8) -> list[dict]:
    """东财分红历史（每股派息）"""
    url = (
        "https://datacenter-web.eastmoney.com/api/data/v1/get?"
        "reportName=RPT_SHAREBONUS_DET&columns=ALL&pageSize=%d&pageNumber=1&"
        "filter=(SECURITY_CODE%%3D%%22%s%%22)&sortColumns=EX_DIVIDEND_DATE&sortTypes=-1"
        % (page_size, code)
    )
    r = requests.get(url, headers=_UA, timeout=15)
    rows = []
    for row in r.json().get("result", {}).get("data") or []:
        rows.append(
            {
                "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
                "bonus_rmb": row.get("PRETAX_BONUS_RMB") or 0,
            }
        )
    return rows


def _roe_akshare(code: str) -> float | None:
    """ROE（东财财务指标——akshare——跳过 nan 取首个有效行）"""
    try:
        import akshare as ak

        df = ak.stock_financial_analysis_indicator(symbol=code)
        if df is not None and len(df):
            for _, row in df.iterrows():
                val = row.get("净资产收益率(%)")
                if val is not None and val == val:  # 跳过 nan
                    return float(val)
    except Exception:
        pass
    return None


def _to_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def get_fundamentals(
    code: str, price: float = 0.0, debt_exempt: bool = False
) -> dict[str, Any]:
    """基本面字段（日级缓存）——价值面 40 分输入"""
    now = time.time()
    if code in _cache and now - _cache[code][0] < _CACHE_TTL:
        return _cache[code][1]

    f: dict[str, Any] = {
        "roe": 0,
        "sales_margin": 0,
        "debt_ratio": 0,
        "ocf_gt_profit": False,
        "dividend_yield": 0,
        "payout_ratio": 0,  # 分红率%（书 L2761：40-75% 诚信区域——H）
        "growth_ok": False,
        "debt_exempt": debt_exempt,
    }
    try:
        lrb = _sina_report(code, "lrb") or []
        fzb = _sina_report(code, "fzb") or []
        llb = _sina_report(code, "llb") or []
        if lrb:
            rev = _to_float(lrb[0].get("营业总收入") or lrb[0].get("营业收入"))
            profit = _to_float(
                lrb[0].get("净利润") or lrb[0].get("归属于母公司所有者的净利润")
            )
            if rev > 0:
                f["sales_margin"] = round(profit / rev * 100, 1)
            growth = _to_float(
                lrb[0].get("营业总收入_同比") or lrb[0].get("营业收入_同比")
            )
            if growth > 5:
                f["growth_ok"] = True
        if fzb:
            assets = _to_float(fzb[0].get("资产总计"))
            debt = _to_float(fzb[0].get("负债合计"))
            if assets > 0:
                f["debt_ratio"] = round(debt / assets * 100, 1)
        if lrb and llb:
            ocf = _to_float(llb[0].get("经营活动产生的现金流量净额"))
            f["ocf_gt_profit"] = ocf > _to_float(lrb[0].get("净利润"))
        # ROE 自算（净利润/归母净资产——三表可控——akshare 接口值异常时不采信）
        equity = (
            _to_float(
                fzb[0].get("归属于母公司股东权益合计")
                or fzb[0].get("归属于母公司所有者权益合计")
                or fzb[0].get("所有者权益合计")
            )
            if fzb
            else 0
        )
        if lrb and equity > 0:
            # 新浪三表净利为单季口径——×4 年化近似（v0——Q11 参数学习化校准）
            f["roe"] = round(_to_float(lrb[0].get("净利润")) / equity * 100 * 4, 1)
        else:
            roe = _roe_akshare(code)  # 兜底（自算失败才用接口）
            if roe is not None:
                f["roe"] = roe
        divs = _dividend_history(code)
        if divs and price > 0:
            # PRETAX_BONUS_RMB 单位=每10股——/10 为每股；最近 2 期（当年）求和
            per_share = [d["bonus_rmb"] / 10 for d in divs[:2] if d["bonus_rmb"]]
            if per_share:
                f["dividend_yield"] = round(sum(per_share) / price * 100, 2)
            # 分红率 = 每股分红 / 基本每股收益（书 L2761：40-75% 区域——H）
            eps = _to_float(lrb[0].get("基本每股收益")) if lrb else 0
            if per_share and eps > 0:
                f["payout_ratio"] = round(sum(per_share) / eps * 100, 1)
    except Exception:
        pass  # 数据源失败——保留 0 值（打分自然偏低——安全方向）

    _cache[code] = (now, f)
    return f
