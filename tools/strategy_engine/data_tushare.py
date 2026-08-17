# -*- coding: utf-8 -*-
"""tushare 数据通道（data_tushare.py——2026-08-15 已购 2000 积分——数据 SLA 保险）

定位：免费源的**同级替代/交叉验证源**（不是主源替换）——
- 日线/周线：替代 baostock 做第二源交叉验证（价格/估值）
- moneyflow：资金流第三源（东财/同花顺/tushare 三源）——⚠️ 需 2000 分（2026-08-15 实测未解锁——待付费）
- fina_indicator：财务指标（新浪三表第二源）——⚠️ 需 2000 分（未解锁——待付费）
- 当前免费积分（~120 分）实测可用：daily/weekly/daily_basic/index_daily

用法：token 从 .env 读取（TUSHARE_TOKEN——勿硬编码/勿公开）
失败返回 []/None（不抛——红线③容错——免费源降级路径不变）
"""

from __future__ import annotations

import os
import time
from typing import Any

_TOKEN: str | None = None
_ts = None


def _get_token() -> str:
    """读取 token（.env——首次调用加载）"""
    global _TOKEN
    if _TOKEN:
        return _TOKEN
    # 环境变量优先——其次项目 .env
    _TOKEN = os.environ.get("TUSHARE_TOKEN", "")
    if not _TOKEN:
        env_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"
        )
        try:
            for line in open(env_path, encoding="utf-8"):
                line = line.strip()
                if line.startswith("TUSHARE_TOKEN="):
                    _TOKEN = line.split("=", 1)[1].strip()
                    break
        except OSError:
            pass
    return _TOKEN


def _pro():
    """tushare pro API 实例（懒加载——失败返回 None）"""
    global _ts
    token = _get_token()
    if not token:
        return None
    if _ts is None:
        try:
            import tushare as ts

            ts.set_token(token)
            _ts = ts.pro_api()
        except Exception:
            _ts = None
    return _ts


def kline_daily(code: str, start: str = "", end: str = "") -> list[dict[str, Any]]:
    """日线（tushare daily——2000 积分权限）——返回 [{date, close, open, high, low}] 升序

    code 需 TS 代码（600519.SH/000001.SZ/000300.SH）——失败返回 []（不抛）
    start/end 默认动态（一年前→今天——数据边界防前视）
    """
    if not end:
        end = time.strftime("%Y%m%d")
    if not start:
        start = f"{time.localtime().tm_year - 1}0101"
    pro = _pro()
    if pro is None:
        return []
    try:
        df = pro.daily(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return []
        df = df.sort_values("trade_date")
        return [
            {
                "date": f"{r['trade_date'][:4]}-{r['trade_date'][4:6]}-{r['trade_date'][6:]}",
                "open": float(r.get("open") or 0),
                "close": float(r.get("close") or 0),
                "high": float(r.get("high") or 0),
                "low": float(r.get("low") or 0),
            }
            for _, r in df.iterrows()
        ]
    except Exception:
        return []


def kline_weekly(code: str, start: str = "", end: str = "") -> list[dict[str, Any]]:
    """周线（tushare weekly——2000 积分）——与 baostock 周线同构（交叉验证用）

    start/end 默认动态（十年→今天——防前视）
    """
    if not end:
        end = time.strftime("%Y%m%d")
    if not start:
        start = f"{time.localtime().tm_year - 10}0101"
    pro = _pro()
    if pro is None:
        return []
    try:
        df = pro.weekly(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return []
        df = df.sort_values("trade_date")
        return [
            {
                "date": f"{r['trade_date'][:4]}-{r['trade_date'][4:6]}-{r['trade_date'][6:]}",
                "open": float(r.get("open") or 0),
                "close": float(r.get("close") or 0),
                "high": float(r.get("high") or 0),
                "low": float(r.get("low") or 0),
            }
            for _, r in df.iterrows()
        ]
    except Exception:
        return []


def daily_basic(code: str, trade_date: str = "") -> dict[str, Any]:
    """每日指标（PE/PB/总市值——tushare daily_basic）——单日快照

    返回 {pe_ttm, pb, total_mv, turnover_rate}——失败返回 {}（不抛）
    """
    pro = _pro()
    if pro is None:
        return {}
    try:
        if trade_date:
            df = pro.daily_basic(ts_code=code, trade_date=trade_date)
        else:
            df = pro.daily_basic(ts_code=code)
        if df is None or df.empty:
            return {}
        r = df.iloc[0]
        return {
            "pe_ttm": float(r.get("pe_ttm") or 0),
            "pb": float(r.get("pb") or 0),
            "total_mv": float(r.get("total_mv") or 0),  # 万元
            "turnover_rate": float(r.get("turnover_rate") or 0),
        }
    except Exception:
        return {}


def moneyflow(code: str, start: str = "", end: str = "") -> list[dict[str, Any]]:
    """个股资金流（tushare moneyflow——东财/同花顺第三源）——返回 [{date, net}]"""
    if not end:
        end = time.strftime("%Y%m%d")
    if not start:
        start = f"{time.localtime().tm_year - 1}0101"
    pro = _pro()
    if pro is None:
        return []
    try:
        df = pro.moneyflow(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            return []
        df = df.sort_values("trade_date")
        out = []
        for _, r in df.iterrows():
            # 主力净流入 = 大单+特大单净额（手——×100 股）
            net = (
                float(r.get("buy_lg_amount") or 0) + float(r.get("buy_elg_amount") or 0)
            ) - (
                float(r.get("sell_lg_amount") or 0)
                + float(r.get("sell_elg_amount") or 0)
            )
            out.append(
                {
                    "date": f"{r['trade_date'][:4]}-{r['trade_date'][4:6]}-{r['trade_date'][6:]}",
                    "net": net * 100,  # 手→股→金额近似（元）——主源精确度由东财保持
                }
            )
        return out
    except Exception:
        return []


def to_ts_code(code: str) -> str:
    """六位代码 → TS 代码（600519→600519.SH / 000001→000001.SZ / 000300→000300.SH）

    指数约定（观复 data.py _bs_prefix 同规则）：000 开头三位数以内指数默认 SH
    （000300=沪深300 / 000905=中证500——SH）；000001/000002 等个股是 SZ
    """
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code in ("000300", "000905", "000852", "000016", "000688"):
        return f"{code}.SH"  # 常见宽基指数（SH）
    if code.startswith(("0", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SH"  # 默认 SH


if __name__ == "__main__":
    test = kline_daily(to_ts_code("600519"), "20260801", "20260815")
    if test:
        print(f"✅ tushare 日线可用：茅台 {len(test)} 行——最新 {test[-1]}")
    else:
        print("❌ tushare 日线不可用（检查 token/权限）")


def ts_pe_pb_history(code: str, days: int = 2500) -> list[dict[str, Any]]:
    """个股 PE/PB 全历史（daily_basic——2005 起——2026-08-17 主源切换）

    替代 baostock 估值主源（baostock 长区间/指数查询多次挂起——SLA 脆弱）
    返回 [{date, pe, pb}] 升序——失败返回 []（调用方 fallback baostock）
    """
    ts_code = to_ts_code(code)
    pro = _pro()
    if not pro:
        return []
    try:
        df = pro.daily_basic(
            ts_code=ts_code, fields="trade_date,pe_ttm,pb", limit=10000
        )
        if df is None or df.empty:
            return []
        out = []
        for _, r in df.iterrows():
            try:
                pe_val: Any = r["pe_ttm"]
                pb_val: Any = r["pb"]
                pe, pb = float(pe_val), float(pb_val)
            except (TypeError, ValueError):
                continue
            if pe > 0 and pb > 0:
                out.append(
                    {
                        "date": str(r["trade_date"])[:4]
                        + "-"
                        + str(r["trade_date"])[4:6]
                        + "-"
                        + str(r["trade_date"])[6:8],
                        "pe": pe,
                        "pb": pb,
                    }
                )
        out.sort(key=lambda x: x["date"])
        return out[-days:]
    except Exception:
        return []
