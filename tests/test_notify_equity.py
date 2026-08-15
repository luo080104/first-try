"""notify_gf 晨报入口单测（2026-08-15——晨报顺带 record_equity 修复）"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import notify_gf as ng


def test_push_brief_records_equity(monkeypatch, tmp_path):
    """晨报入口必须顺带 record_equity（净值序列积累——gate_check 判定依赖）"""
    from tools.strategy_engine import portfolio as pf

    # 隔离数据文件（不污染真实虚拟盘）
    test_portfolio = tmp_path / "portfolio.json"
    pf.PORTFOLIO_FILE = str(test_portfolio)
    p = pf.Portfolio()
    p.data = {"init_cash": 100000, "cash": 100000, "holdings": {}, "track": {}}
    p.save()

    recorded = []

    def _fake_push(text):
        return True

    def _fake_record(self, quotes=None):
        recorded.append(quotes)
        return 100000.0
    monkeypatch.setattr("tools.strategy_engine.notify_gf.push_wechat", _fake_push)
    monkeypatch.setattr("tools.strategy_engine.notify_gf._throttled", lambda text: True)
    monkeypatch.setattr(pf.Portfolio, "record_equity", _fake_record)
    monkeypatch.setattr(ng, "mb", type("MB", (), {"build_brief": lambda self: "test"})())
    ok = ng.push_brief()
    assert ok is True
    assert len(recorded) == 1  # record_equity 被调用了一次


def test_push_brief_equity_failure_does_not_block(monkeypatch):
    """record_equity 失败（网络）→ 晨报照常推送（红线③容错）"""
    from tools.strategy_engine import portfolio as pf

    def _boom_record(self, quotes=None):
        raise ConnectionError("quotes api down")

    def _fake_push(text):
        return True

    monkeypatch.setattr("tools.strategy_engine.notify_gf.push_wechat", _fake_push)
    monkeypatch.setattr("tools.strategy_engine.notify_gf._throttled", lambda text: True)
    monkeypatch.setattr(pf.Portfolio, "record_equity", _boom_record)
    monkeypatch.setattr(ng, "mb", type("MB", (), {"build_brief": lambda self: "test"})())
    assert ng.push_brief() is True  # 净值失败不阻塞晨报
