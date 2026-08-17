# -*- coding: utf-8 -*-
"""观复数据适配层（strategy_engine 数据入口——a-stock-data 思路落地）

数据源优先级（书内/落地实施方案）：腾讯行情（不封 IP）→ mootdx（未装——HTTP 兜底）
→ akshare（已装——东财节流规则）
指数代码显式前缀（sh000300——避免自动 sz 前缀坑——findings 记录）
"""

from __future__ import annotations

import os
import sqlite3
import time
import urllib.request
from typing import Any

# baostock 估值/历史主源（2026-08-13 方案定稿——数据层升级：AkShare 统一层 + baostock 历史主源）
# Sequoia-X 验证方案：免费/无需注册/无限流/后复权——彻底规避东财反爬
# SQLite 本地缓存（Sequoia-X 架构：日增量拉取 → 本地库 → 估值随积累变准）
_DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "valuation_cache.db"
)


def _bs_prefix(code: str) -> str:
    """六位数字/指数 → baostock 前缀格式（sh.600036/sz.000001/sh.000300）"""
    if code.startswith("000"):  # 指数（sh.000300 等）——先于个股判断
        return f"sh.{code}"
    if code.startswith("6"):
        return f"sh.{code}"
    if code.startswith(("0", "3")):
        return f"sz.{code}"
    return f"sh.{code}"  # 兜底（ETF 等）


def _bs_conn() -> sqlite3.Connection:
    try:
        os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    except OSError:
        pass  # 缓存目录建不了不致命——网络源继续
    conn = sqlite3.connect(_DB_PATH)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS valuation ("
        "code TEXT, date TEXT, pe REAL, pb REAL, source TEXT, "
        "PRIMARY KEY(code, date))"
    )
    return conn


def _bs_fetch(
    code: str, fields: str, start: str, end: str, freq: str, adj: str
) -> list[list[str]]:
    """baostock 查询封装（返回行列表——失败/无结果返回 []）

    start/end 需 YYYY-MM-DD 格式（baostock 要求横线分隔）
    """
    try:
        import baostock as bs
    except ImportError:
        return []
    try:
        bs.login()
        rs = bs.query_history_k_data_plus(
            _bs_prefix(code),
            fields,
            start_date=start,
            end_date=end,
            frequency=freq,
            adjustflag=adj,
        )
        if rs is None:
            bs.logout()
            return []
        out = []
        while rs.error_code == "0" and rs.next():
            out.append(rs.get_row_data())
        bs.logout()
        return out
    except Exception:
        return []


def bs_kline_daily(code: str, years: int = 1) -> list[dict[str, Any]]:
    """baostock 日线（后复权——归因拆解用——2026-08-15 整改①）

    code 六位数字（指数 000300 自动加 sh. 前缀）——返回 [{date, close}] 升序
    失败返回 []（不抛异常——源链自动降级）
    """
    rows = _bs_fetch(
        code,
        "date,close",
        f"{time.localtime().tm_year - years}-01-01",
        time.strftime("%Y-%m-%d"),  # 数据边界=今天（防前视——2026-08-16 吴老师质疑）
        "d",
        "2",
    )
    out = []
    for r in rows:
        try:
            out.append({"date": r[0], "close": float(r[1])})
        except (ValueError, IndexError):
            continue
    return out


def bs_kline_weekly(code: str, years: int = 10) -> list[dict[str, Any]]:
    """baostock 周线（后复权——历史主源——回测/验证统一用）

    code 六位数字——返回 [{date, close, high, low}] 升序
    失败返回 []（不抛异常——源链自动降级）
    """
    rows = _bs_fetch(
        code,
        "date,open,close,high,low",
        f"{time.localtime().tm_year - years}-01-01",
        time.strftime("%Y-%m-%d"),  # 数据边界=今天
        "w",
        "2",
    )
    out = []
    for r in rows:
        try:
            out.append(
                {
                    "date": r[0],
                    "open": float(r[1]),
                    "close": float(r[2]),
                    "high": float(r[3]),
                    "low": float(r[4]),
                }
            )
        except (ValueError, IndexError):
            continue
    return out


def bs_pe_pb_history(code: str, years: int = 10) -> list[dict[str, Any]]:
    """baostock 日线 PE/PB 历史（主源——免费无限流）→ SQLite 缓存

    注：baostock 接口历史到 2006（龙头股）——远超百度 1-3 年——书内十年百分位可满足
    缓存：首次全量拉 → 之后日增量（当天已缓存则直接读）
    """
    conn = _bs_conn()
    start = f"{time.localtime().tm_year - years}-01-01"
    min_d: str | None = None
    max_d: str | None = None
    try:
        rng = conn.execute(
            "SELECT MIN(date), MAX(date) FROM valuation WHERE code=? AND source='baostock'",
            (code,),
        ).fetchone()
        min_d, max_d = (rng[0], rng[1]) if rng else (None, None)
        today = time.strftime("%Y-%m-%d")
        # 缓存覆盖完整（起点 ≤ 要求起点 且 终点 = 今天）——直接读
        if min_d and max_d and min_d <= start and max_d >= today:
            rows = conn.execute(
                "SELECT date, pe, pb FROM valuation WHERE code=? AND source='baostock' ORDER BY date",
                (code,),
            ).fetchall()
            conn.close()
            return [{"date": d, "pe": pe, "pb": pb} for d, pe, pb in rows][
                -years * 250 :
            ]
    except sqlite3.Error as e:
        print(f"[data] ⚠️ 缓存读取失败（{e}——网络源继续）")
    # 缓存缺失/覆盖不足 → 拉取（起点取更早者——补历史缺口；终点到今天——补新数据）
    fetch_start = min(
        min_d or start, start
    )  # 缺历史往前补，缺新数据靠 INSERT OR REPLACE
    rows = _bs_fetch(
        code,
        "date,peTTM,pbMRQ",
        fetch_start,
        time.strftime("%Y-%m-%d"),  # 数据边界=今天（防前视）
        "d",
        "3",
    )
    new_rows = []
    for r in rows:
        try:
            pe, pb = float(r[1]), float(r[2])
            if pe > 0 and pb > 0:
                new_rows.append((code, r[0], pe, pb, "baostock"))
        except (ValueError, IndexError):
            continue
    if new_rows:
        try:
            conn.executemany(
                "INSERT OR REPLACE INTO valuation VALUES (?,?,?,?,?)", new_rows
            )
            conn.commit()
        except sqlite3.Error as e:
            print(f"[data] ⚠️ 缓存写入失败（{e}——本次不持久化）")
    rows = conn.execute(
        "SELECT date, pe, pb FROM valuation WHERE code=? AND source='baostock' ORDER BY date",
        (code,),
    ).fetchall()
    conn.close()
    return [{"date": d, "pe": pe, "pb": pb} for d, pe, pb in rows][-years * 250 :]


# 腾讯行情（a-stock-data tencent_quote 端点——已验证）
def tencent_quote(codes: list[str]) -> dict[str, dict[str, Any]]:
    """批量实时行情（个股/指数/ETF——含 PE/PB/市值）——指数必须显式 sh/sz 前缀"""
    prefixed = []
    for c in codes:
        if c.startswith(("sh", "sz", "bj")) or c.startswith(("6", "9")):
            prefixed.append(c if c.startswith(("sh", "sz", "bj")) else f"sh{c}")
        elif c.startswith("8"):
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
            "price": _safe_float(vals[3]) if vals[3] else 0,
            "change_pct": _safe_float(vals[32]) if vals[32] else 0,
            "pe_ttm": _safe_float(vals[39]) if vals[39] else 0,
            "mcap_yi": _safe_float(vals[44]) if vals[44] else 0,
            "pb": _safe_float(vals[46]) if vals[46] else 0,
        }
    return result


# 腾讯日 K 线（HTTP——mootdx 未装时的兜底——指数/个股通用）
def tencent_kline(code: str, days: int = 250) -> list[dict[str, Any]]:
    """日 K 线（最近 days 根——用于布林/RSI/九转计算）

    code 需显式前缀（sh600519/sz000001/sh000300）
    返回 [{date, open, close, high, low, volume}]——按时间升序
    """
    if not code.startswith(("sh", "sz", "bj")):
        code = f"sh{code}" if code.startswith("6") else f"sz{code}"
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    resp = urllib.request.urlopen(req, timeout=15)
    try:
        import json

        d = json.loads(resp.read().decode("utf-8"))
    except (ValueError, OSError, UnicodeDecodeError):
        return []
    node = d.get("data", {}).get(code, {})
    rows = node.get("day") or node.get("qfqday") or []
    out = []
    for r in rows:
        if len(r) < 6:
            continue
        out.append(
            {
                "date": r[0],
                "open": _safe_float(r[1]),
                "close": _safe_float(r[2]),
                "high": _safe_float(r[3]),
                "low": _safe_float(r[4]),
                "volume": _safe_float(r[5]),
            }
        )
    return out


# 大盘指数快照（晨报 M 系列数据源）
def market_index_snapshot() -> dict[str, dict[str, Any]]:
    """沪深300/上证指数快照（价格/涨跌/PE）——指数显式前缀"""
    return tencent_quote(["sh000300", "sh000001"])


# akshare 估值（东财——节流）——V1 估值百分位的数据基础
_em_last_call = [0.0]
_EM_MIN_INTERVAL = 1.0


def _safe_float(x: Any, default: float = 0.0) -> float:
    """安全浮点转换（数据异常 → default——不抛——红线③容错）"""
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


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
    return [
        (str(r["date"])[:10], _safe_float(r["value"]))
        for _, r in df.iterrows()
        if r.get("value") is not None
    ]


def _bs_cached_only(code: str) -> list[dict[str, Any]]:
    """只读 baostock 估值缓存（C7 2026-08-17：交叉验证降频——不触发全量拉取）

    缓存覆盖不足（<60 条）返回 []——跳过本次交叉（标注即可）
    """
    try:
        conn = _bs_conn()
        rows = conn.execute(
            "SELECT date, pe, pb FROM valuation WHERE code=? AND source='baostock' ORDER BY date",
            (code,),
        ).fetchall()
        conn.close()
        if len(rows) < 60:
            return []
        return [{"date": d, "pe": pe, "pb": pb} for d, pe, pb in rows]
    except sqlite3.Error:
        return []


def pe_pb_history(code: str, days: int = 2500) -> list[dict[str, Any]]:
    """PE/PB 历史（tushare 主源 2005 起 + baostock fallback——2026-08-17 主源切换）

    code 六位数字（600519）——返回 [{date, pe, pb, source}] 升序
    主源：tushare daily_basic（200 元/年已购——2005 起全量——根治 baostock 挂起）
    fallback：baostock（免费无限流——历史到 2006）——百度兜底（1-3 年）
    交叉验证：双源重叠期 PE 差异 >20% 标记 source='conflict'（AI Berkshire 纪律）
    """
    # 主源：tushare（2026-08-17——付费已购——2000 分）
    try:
        from tools.strategy_engine.data_tushare import ts_pe_pb_history as _ts_h

        ts_rows = _ts_h(code, days)
        if len(ts_rows) >= 60:
            rows = [dict(r, source="tushare") for r in ts_rows]
            # C7 修复（2026-08-17 审核）：交叉验证降频——只读 baostock 已有缓存
            # （冷缓存=10 年全量拉=主源切换想规避的挂起风险——不再每次触发）
            try:
                bs_rows = _bs_cached_only(code)
                if len(bs_rows) >= 60:
                    rows = _cross_check(rows, bs_rows)
            except Exception:
                pass  # 交叉验证失败不阻塞主源（红线③）
            return rows[-days:]
    except Exception:
        pass  # tushare 失败 → baostock fallback
    # fallback：baostock（原主源——免费）
    bs = bs_pe_pb_history(code)
    if len(bs) >= 60:
        # 交叉验证：百度重叠期对比（节流——不阻塞）
        try:
            bd = [
                {"date": d, "pe": v.get("pe"), "pb": v.get("pb")}
                for d, v in (_baidu_series_merged(code) or {}).items()
                if v.get("pe") and v.get("pb")
            ]
            if bd:
                bs = _cross_check(bs, bd)
        except Exception:
            pass  # 百度失败不阻塞主源（红线③）
        return bs[-days:]
    # 主源失败 → 百度兜底（原逻辑）
    bd = _baidu_series_merged(code) or {}
    out = [
        {"date": d, "pe": v.get("pe"), "pb": v.get("pb")}
        for d, v in sorted(bd.items())
        if v.get("pe") and v.get("pb")
    ]
    return out[-days:]


def _baidu_series_merged(code: str) -> dict[str, dict[str, float]]:
    """百度 PE/PB 合并（按日期）——交叉验证/兜底用"""
    pes = _baidu_valuation_series(code, "市盈率(TTM)")
    pbs = _baidu_valuation_series(code, "市净率")
    by_date: dict[str, dict[str, float]] = {}
    for d, v in pes:
        by_date.setdefault(d, {})["pe"] = v
    for d, v in pbs:
        by_date.setdefault(d, {})["pb"] = v
    return {d: v for d, v in by_date.items() if "pe" in v and "pb" in v}


def _cross_check(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """2 源交叉验证：重叠日 PE 差异 >20% → source='conflict'（人工确认标记）

    AI Berkshire 纪律（方案红线③）：关键数据至少 2 源对比——不一致标记不静默
    """
    sec = {h["date"]: h for h in secondary}
    out = []
    conflicts = 0
    for h in primary:
        h = dict(h)
        h.setdefault("source", "baostock")
        s = sec.get(h["date"])
        if s and s.get("pe") and h.get("pe"):
            diff = abs(s["pe"] - h["pe"]) / h["pe"]
            if diff > 0.2:
                h["source"] = "conflict"
                conflicts += 1
        out.append(h)
    if conflicts:
        print(
            f"[data] ⚠️ 2 源冲突 {conflicts} 日（{primary[0].get('date', '')[:7]} 段——人工确认）"
        )
    return out


def _bs_pe_series(code: str) -> list[dict[str, Any]]:
    """兼容入口：纯 baostock 估值（不过交叉验证——回测内部用）"""
    return bs_pe_pb_history(code)


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
        "pe_median": round(
            pes[len(pes) // 2], 1
        ),  # 个股 PE 历史中位数（Q1 个股 fair_pe）
    }
