"""tushare 通道单测（data_tushare——2026-08-15 已购——mock 不依赖网络）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import data_tushare as dt


def test_to_ts_code():
    """六位代码 → TS 代码（沪/深/北/指数）"""
    assert dt.to_ts_code("600519") == "600519.SH"
    assert dt.to_ts_code("000001") == "000001.SZ"
    assert dt.to_ts_code("300059") == "300059.SZ"
    assert dt.to_ts_code("832000") == "832000.BJ"
    assert dt.to_ts_code("000300") == "000300.SH"


def test_no_token_returns_empty(monkeypatch):
    """无 token → 空（不抛——红线③容错——免费源降级路径不变）"""
    monkeypatch.setattr(dt, "_get_token", lambda: "")
    assert dt.kline_daily("600519") == []
    assert dt.daily_basic("600519") == {}


def test_kline_daily_parses(monkeypatch):
    """日线解析（trade_date 格式 → ISO 日期 + 升序）"""
    import pandas as pd

    class _FakePro:
        def daily(self, ts_code, start_date, end_date):
            return pd.DataFrame(
                [
                    {"trade_date": "20260814", "open": 1355.0, "close": 1341.99, "high": 1359.0, "low": 1338.14},
                    {"trade_date": "20260813", "open": 1338.0, "close": 1350.0, "high": 1360.0, "low": 1330.0},
                ]
            )

        def weekly(self, ts_code, start_date, end_date):
            return pd.DataFrame()

    monkeypatch.setattr(dt, "_pro", lambda: _FakePro())
    k = dt.kline_daily("600519.SH")
    assert len(k) == 2
    assert k[0]["date"] == "2026-08-13"  # 升序
    assert k[1]["date"] == "2026-08-14"
    assert k[1]["close"] == 1341.99


def test_ts_failure_returns_empty(monkeypatch):
    """接口异常 → 空（不抛）"""
    class _Boom:
        def daily(self, **kw):
            raise ConnectionError("tushare down")

    monkeypatch.setattr(dt, "_pro", lambda: _Boom())
    assert dt.kline_daily("600519.SH") == []
