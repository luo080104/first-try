# -*- coding: utf-8 -*-
"""观复数据适配层（strategy_engine 数据入口——a-stock-data 思路落地）

数据源优先级（书内/落地实施方案）：腾讯行情（不封 IP）→ mootdx（未装——HTTP 兜底）
→ akshare（已装——东财节流规则）
指数代码显式前缀（sh000300——避免自动 sz 前缀坑——findings 记录）
"""
from __future__ import annotations

import time
import urllib.request
from typing import Any


# 腾讯行情（a-stock-data tencent_quote 端点——已验证）
def tencent_quote(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量实时行情（个股/指数/ETF——含 PE/PB/市值）——指数必须显式 sh/sz 前缀"""
    prefixed = []
    for c in codes:
        if c.startswith(('sh', 'sz', 'bj')) or c.startswith(('6', '9')):
            prefixed.append(c if c.startswith(('sh', 'sz', 'bj')) else f"sh{c}")
        elif c.startswith('8'):
            prefixed.append(f"bj{c}")
        else:
            prefixed.append(f"sz{c}")
    url = "https://qt.gtimg.cn/q=" + ",".join(prefixed)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=10)
    data = resp.read().decode("gbk")
    result: dict[str, dict[str, Any]] = {}
    for line in data.strip().split(";"):
        if not line.strip() or "=" not in line or '"' not in line:
            continue
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            continue
        code = key[2:]
        result[code] = {
            "name": vals[1],
            "price": float(vals[3]) if vals[3] else 0,
            "change_pct": float(vals[32]) if vals[32] else 0,
            "pe_ttm": float(vals[39]) if vals[39] else 0,
            "mcap_yi": float(vals[44]) if vals[44] else 0,
            "pb": float(vals[46]) if vals[46] else 0,
        }
    return result


# 腾讯日 K 线（HTTP——mootdx 未装时的兜底——指数/个股通用）
def tencent_kline(code: str, days: int = 250) -> list[dict[str, Any]]:
    """日 K 线（最近 days 根——用于布林/RSI/九转计算）

    code 需显式前缀（sh600519/sz000001/sh000300）
    返回 [{date, open, close, high, low, volume}]——按时间升序
    """
    if not code.startswith(('sh', 'sz', 'bj')):
        code = f"sh{code}" if code.startswith('6') else f"sz{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=15)
    import json
    d = json.loads(resp.read().decode("utf-8"))
    node = d.get("data", {}).get(code, {})
    rows = node.get("day") or node.get("qfqday") or []
    out = []
    for r in rows:
        if len(r) < 6:
            continue
        out.append({
            "date": r[0],
            "open": float(r[1]), "close": float(r[2]),
            "high": float(r[3]), "low": float(r[4]),
            "volume": float(r[5]),
        })
    return out


# 大盘指数快照（晨报 M 系列数据源）
def market_index_snapshot() -> dict[str, dict[str, Any]]:
    """沪深300/上证指数快照（价格/涨跌/PE）——指数显式前缀"""
    return tencent_quote(["sh000300", "sh000001"])


# akshare 估值（东财——节流）——V1 估值百分位的数据基础
_em_last_call = [0.0]
_EM_MIN_INTERVAL = 1.0


def _em_throttle() -> None:
    """东财节流（≥1s + 随机抖动——a-stock-data 防封铁律）"""
    import random
    wait = _EM_MIN_INTERVAL - (time.time() - _em_last_call[0])
    if wait > 0:
        time.sleep(wait + random.uniform(0.1, 0.5))
    _em_last_call[0] = time.time()


def _baidu_valuation_series(code: str, indicator: str) -> list[tuple[str, float]]:
    """百度估值单指标历史（akshare stock_zh_valuation_baidu——PE/PB）

    indicator: "市盈率(TTM)" / "市净率"——返回 [(date, value)] 升序
    """
    _em_throttle()
    import akshare as ak
    df = ak.stock_zh_valuation_baidu(symbol=code, indicator=indicator)
    return [(str(r["date"])[:10], float(r["value"]))
            for _, r in df.iterrows() if r.get("value") is not None]


def pe_pb_history(code: str, days: int = 2500) -> list[dict[str, Any]]:
    """PE/PB 历史（百度估值）——估值百分位 V1 数据源

    code 六位数字（600519）——返回 [{date, pe, pb}] 升序
    注：百度接口历史约 1-3 年（非书内十年）——MVP 先用——随时间积累变准
    """
    pes = _baidu_valuation_series(code, "市盈率(TTM)")
    pbs = _baidu_valuation_series(code, "市净率")
    by_date = {}
    for d, v in pes:
        by_date.setdefault(d, {})["pe"] = v
    for d, v in pbs:
        by_date.setdefault(d, {})["pb"] = v
    out = [{"date": d, "pe": v.get("pe"), "pb": v.get("pb")}
           for d, v in sorted(by_date.items()) if "pe" in v and "pb" in v]
    return out[-days:]


def valuation_percentile(code: str) -> dict[str, float]:
    """当前 PE/PB 的历史百分位（0-100——书 V1 体系：<10 便宜/>80 贵）

    返回 {pe_percentile, pb_percentile}——数据不足返回 50.0（中性）
    """
    hist = pe_pb_history(code)
    if len(hist) < 60:
        return {"pe_percentile": 50.0, "pb_percentile": 50.0}
    cur_pe, cur_pb = hist[-1]["pe"], hist[-1]["pb"]
    pes = sorted(h["pe"] for h in hist)
    pbs = sorted(h["pb"] for h in hist)
    import bisect
    i = bisect.bisect_left(pes, cur_pe)
    j = bisect.bisect_left(pbs, cur_pb)
    return {
        "pe_percentile": round(i / len(pes) * 100, 1),
        "pb_percentile": round(j / len(pbs) * 100, 1),
    }
