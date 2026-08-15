"""信号在线评分单测（signal_ledger.online_score——2026-08-15 整改②——mock K 线）"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tools.strategy_engine import signal_ledger as sl


def _write_ledger(tmp_path, rows):
    """写入合成账本（JSONL）——返回账本路径"""
    path = tmp_path / "signal_ledger.jsonl"
    try:
        f = open(path, "w", encoding="utf-8")
    except OSError:
        return path
    with f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


def _mk_rows(months: list[str], results: list[float]):
    """构造信号行：months[i] 触发月 + results[i] 触发后 20 日收益

    code 按收益正负分配：正→'win'（K 线未来 10.5=+5%）、负→'loss'（9.7=-3%）
    """
    rows = []
    for i, (m, r) in enumerate(zip(months, results)):
        code = "win" if r > 0 else "loss"
        rows.append(
            {
                "ts": f"{m}-15T09:30:00",
                "code": code,
                "type": "score_pass",
                "direction": "buy",
                "price": 10.0,
                "reason": "test",
            }
        )
    return rows


_RESULTS: dict[int, tuple[bool, float]] = {}


def _fake_kline(code, days=90):
    """合成 K 线：60 天覆盖 2026-01 至 2026-03 信号——价格固定 10（收益由
    信号价格与 K 线关系决定——但本测试信号 price=10、K 线 close=10 → 收益 0——
    需按信号注入收益：K 线第 20 日后价格 = 10 × (1 + 对应信号收益/100)
    简化：所有信号同 code——K 线统一 10——收益全 0——用 direction 判定胜负会失真——
    改为：每个信号独立 code——K 线按 code 返回不同未来价"""
    import datetime

    d0 = datetime.date(2026, 1, 1)
    k = []
    for i in range(60):
        k.append(((d0 + datetime.timedelta(days=i)).isoformat(), 10.0))
    return k


def _fake_kline_by_code(code, days=90):
    """按 code 注入收益：code=win → 未来价 10.5（+5%）；code=loss → 9.7（-3%）
    120 天覆盖 2026-01 至 2026-04（触发日 01/02/03-15 后均有 ≥20 日）"""
    import datetime

    d0 = datetime.date(2026, 1, 1)
    future = 10.5 if code == "win" else 9.7
    k = []
    for i in range(120):
        k.append(((d0 + datetime.timedelta(days=i)).isoformat(), future))
    return k


def test_online_score_winrate(monkeypatch, tmp_path):
    """30 条信号（18 胜 12 负——均匀分布）→ 胜率 60% + 月度聚合正确"""
    # 3 个月各 10 条——每月 6 胜 4 负（均匀——不触发漂移）
    months = []
    results = []
    for m in ("2026-01", "2026-02", "2026-03"):
        months += [m] * 10
        results += [5.0] * 6 + [-3.0] * 4
    rows = _mk_rows(months, results)
    path = _write_ledger(tmp_path, rows)
    monkeypatch.setattr(sl, "LEDGER_FILE", str(path))

    r = sl.online_score(kline_provider=_fake_kline_by_code)
    assert r["drift"] == False
    total_n = sum(m["n"] for m in r["monthly"].values())
    assert total_n == 30
    # 整体胜率 60%（18/30）
    wr_sum = sum(m["n"] * m["win_rate"] for m in r["monthly"].values())
    assert abs(wr_sum / 30 - 60.0) < 1.0


def test_online_score_drift_detection(monkeypatch, tmp_path):
    """连续 2 月胜率下滑 >10pt → 漂移标记（不自动禁用——仅标记）"""
    months = ["2026-01"] * 10 + ["2026-02"] * 10 + ["2026-03"] * 10
    results = [5.0] * 9 + [-3.0] * 1 + [5.0] * 5 + [-3.0] * 5 + [-3.0] * 10
    # 01 月 90% → 02 月 50% → 03 月 0%——连续下滑 >10pt
    rows = _mk_rows(months, results)
    path = _write_ledger(tmp_path, rows)
    monkeypatch.setattr(sl, "LEDGER_FILE", str(path))

    r = sl.online_score(kline_provider=_fake_kline_by_code)
    assert r["drift"] == True
    assert "漂移" in r["note"]


def test_online_score_empty_ledger(monkeypatch, tmp_path):
    """空账本 → 空结果（不崩）"""
    path = _write_ledger(tmp_path, [])
    monkeypatch.setattr(sl, "LEDGER_FILE", str(path))
    r = sl.online_score(kline_provider=lambda code: [])
    assert r["monthly"] == {}
    assert r["drift"] == False
