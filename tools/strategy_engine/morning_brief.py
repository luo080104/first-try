# -*- coding: utf-8 -*-
"""观复晨报雏形（9:00——书体系：大盘状态+估值百分位+策略信号）

MVP 内容组装：大盘状态（M 系列）+ 龙头股池估值扫描（B5 过滤）+ 候选讲解
Q1 落地：利率隐含合理 PE 对比
Q5 落地：建议现金比例（状态 → 仓位映射——低潮满仓/高潮防守）
推送：输出文本——企业微信通道复用 Go购 notify（后续接入——MVP 先出内容）
"""

from __future__ import annotations

import datetime

from tools.strategy_engine import data
from tools.strategy_engine import market_status as ms

# 龙头股池（B2 票源——书 A股龙头池——MVP 前 12 只）
LEADER_POOL = [
    "600519",
    "600036",
    "601088",
    "601857",
    "600900",
    "601988",
    "601398",
    "600028",
    "601318",
    "600030",
]


def _valuation_scan(codes: list[str], top_n: int = 5) -> list[dict]:
    """龙头池估值扫描（B5——PE<15 或 PB<2——返回达标候选）"""
    quotes = data.tencent_quote(codes)
    candidates = []
    for code, q in quotes.items():
        pe, pb = q.get("pe_ttm") or 0, q.get("pb") or 0
        if pe <= 0 or pb <= 0:
            continue
        if pe < 15 or pb < 2:
            candidates.append(
                {
                    "code": code,
                    "name": q["name"],
                    "pe": pe,
                    "pb": pb,
                    "price": q["price"],
                    "change_pct": q["change_pct"],
                    "mcap_yi": q["mcap_yi"],
                }
            )
    candidates.sort(key=lambda x: (x["pe"] > 0, x["pe"]))
    return candidates[:top_n]


def _data_source_status() -> list[str]:
    """数据源健康探测（2026-08-15 UZI data_gap_acknowledged 落地——
    数据缺口显式承认——不静默降级）

    探测：fund_flow 双源（东财/同花顺）+ 估值源（baostock）——
    失败标注为数据缺口（讲解模式/晨报告知用户——而非悄悄缺失）
    """
    notes: list[str] = []
    # ① 主力资金流（东财主源 → 同花顺 fallback——2026-08-15 加）
    try:
        from tools.strategy_engine import fund_flow as ff

        f = ff.main_force_flow(LEADER_POOL[0])  # 用茅台探测
        if not f:
            notes.append("⚠️ 主力资金流：双源均不可用（东财封锁+同花顺失败）")
        elif "同花顺源" in f.get("verdict", ""):
            notes.append("ℹ️ 主力资金流：东财封锁——已降级同花顺（当日快照）")
    except Exception:
        notes.append("⚠️ 主力资金流：探测失败")
    # ② 估值历史源（baostock——估值百分位依赖）
    try:
        p = data.valuation_percentile(LEADER_POOL[0])
        if p.get("pe_percentile", 50.0) == 50.0:
            notes.append("⚠️ 估值百分位：数据不足或源异常（返回中性 50%）")
    except Exception:
        notes.append("⚠️ 估值百分位：探测失败")
    # ③ 数据新鲜度（2026-08-16 架构师 P2 落地——静默停更检测）
    try:
        import json as _json
        import os as _os

        pj = _os.path.join(
            _os.path.dirname(_os.path.abspath(data.__file__)),
            "..",
            "..",
            "data",
            "portfolio.json",
        )
        with open(pj, encoding="utf-8") as _f:
            eq = _json.load(_f).get("equity_curve", [])
        if eq:
            last_eq = eq[-1]["date"]
            days = (datetime.date.today() - datetime.date.fromisoformat(last_eq)).days
            if days > 5:
                notes.append(
                    f"⚠️ 净值记录停更 {days} 天（最后 {last_eq}——晨报 record_equity 异常？）"
                )
        xq_nav = _os.path.join(
            _os.path.dirname(_os.path.abspath(data.__file__)),
            "..",
            "..",
            "data",
            "xq_nav.json",
        )
        if _os.path.exists(xq_nav):
            with open(xq_nav, encoding="utf-8") as _f:
                navs = _json.load(_f)
            if navs:
                last_ts = max(v.get("ts", "") for v in navs.values())
                if last_ts[:10] != datetime.date.today().isoformat():
                    notes.append(f"ℹ️ 大V 净值快照：{last_ts[:10]}（每日 16:00 更新）")
    except Exception:
        pass  # 新鲜度探测失败不阻塞晨报（红线③）
    return notes or ["✅ 数据源正常"]


def build_brief() -> str:
    """组装收盘日报（2026-08-17 重构——9:00 盘前晨报改 17:00 收盘总结）

    变更原因（甲方拍板 A）：9:00 盘前发的全是昨日旧数据——改为收盘后
    发当日总结（大盘今日走势/持仓当日盈亏/当日公告/当日大V）——
    净值记录同步迁移（收盘后记当日真实净值——gate_check 语义修正）
    """
    now = datetime.datetime.now().strftime("%Y-%m-%d %A")
    lines = [f"📋 观复日报 · 收盘总结 {now}", "=" * 30]
    # 大盘状态（M 系列 + Q1 利率校准 + Q5 现金纪律——收盘后为当日数据）
    m = ms.market_status()
    lines.append(f"\n【大盘今日】{m['status']}")
    lines.append(f"沪深300 PE={m.get('pe')}（百分位≈{m.get('pe_percentile_approx')}%）")
    fp = m.get("fair_pe_rate_calibrated")
    if fp:
        verdict = "便宜" if (m.get("pe") or 0) < fp else "偏贵"
        lines.append(f"Q1 利率校准: 隐含合理PE≈{fp}——当前{verdict}")
    sens = ms._fair_pe_sensitivity_text()
    if sens:
        lines.append(f"  {sens}")
    for e in m.get("evidence", []):
        lines.append(f"  • {e}")
    if not m.get("evidence"):
        lines.append("  • 无极端信号（估值/技术均中性）")
    g = m.get("cash_guidance", {})
    lo, hi = g.get("cash_range", (0, 0))
    hint = g.get("hint", "")
    lines.append(f"Q5 现金纪律: 建议现金 {lo}-{hi}%（{hint}）")
    # 持仓当日盈亏（2026-08-17 加——收盘日报核心段——当日真实数据）
    try:
        from tools.strategy_engine import data as _data
        from tools.strategy_engine import portfolio as _pf2

        _p2 = _pf2.Portfolio()
        _hold_codes = list(_p2.data.get("holdings", {}).keys())
        _quotes = {}
        if _hold_codes:
            try:
                _q = _data.tencent_quote(_hold_codes)  # 实时行情（腾讯——不封 IP）
                _quotes = {k: v.get("price", 0) for k, v in _q.items()}
            except Exception:
                pass  # 行情拉取失败→按成本价（标注）
        _s2 = _p2.summary(quotes=_quotes)
        _pnl = _s2.get("total", 0) - _s2.get("init_cash", 0)
        _pct = _pnl / _s2.get("init_cash", 1) * 100
        _note = "" if _quotes else "（行情未拉取——按成本价）"
        lines.append(
            f"\n【持仓今日】总资产 {_s2.get('total', 0):,.0f} ｜ "
            f"累计盈亏 {_pnl:+,.0f}（{_pct:+.1f}%）｜ 现金 {_s2.get('cash_pct', 0):.0f}%{_note}"
        )
        for _pos in _s2.get("positions", [])[:5]:
            _pp = _pos.get("pnl_pct", 0)
            lines.append(
                f"  {'🟢' if _pp >= 0 else '🔴'} {_pos['name']}({_pos['code']}) "
                f"{_pp:+.1f}%"
            )
    except Exception:
        pass  # 持仓盈亏失败不阻塞日报（红线③容错）
    # 虚拟盘通过判定进度（2026-08-15 加——微信端可视化进度）
    try:
        from tools.strategy_engine.gate_check import check as _gate_check

        gate = _gate_check()
        lines.append(f"\n【虚拟盘进度】{gate.get('reason', '')}")
    except Exception:
        pass  # 判定失败不阻塞晨报（红线③容错）
    # 数据源健康（2026-08-15 UZI data_gap 落地——缺口显式承认——不静默）
    lines.append("\n【数据源】" + "；".join(_data_source_status()))
    # S4 逻辑变化监测（2026-08-16 架构师 B3 落地——减持/暴雷公告——只提醒不自动卖）
    try:
        from tools.strategy_engine.s4_monitor import build_alert_section

        s4 = build_alert_section()
        if s4:
            lines.append("\n" + s4)
    except Exception:
        pass  # S4 监测失败不阻塞晨报（红线③容错）
    # 行为提醒（2026-08-16 A3 落地——Q10 过早卖出模式——连续 3 次才提醒）
    try:
        from tools.strategy_engine.weekly_report import behavior_alert

        ba = behavior_alert()
        if ba:
            lines.append("\n" + ba)
    except Exception:
        pass  # 行为提醒失败不阻塞晨报（红线③容错）
    # 持仓估值温度（2026-08-16 B5 落地——PE/PB 历史百分位——书 V1：<10 便宜 />80 贵）
    try:
        from tools.strategy_engine import portfolio as _pf

        _p = _pf.Portfolio()
        _positions, _ = _p.positions()
        if _positions:
            lines.append("\n【持仓估值温度】")
            for _pos in _positions[:5]:
                _vp = data.valuation_percentile(_pos["code"])
                _pe, _pb = _vp.get("pe_percentile", 50), _vp.get("pb_percentile", 50)
                _mark = (
                    "🟢"
                    if (_pe < 30 and _pb < 30)
                    else ("🔴" if (_pe > 80 or _pb > 80) else "🟡")
                )
                lines.append(
                    f"  {_mark} {_pos['name']}: PE百分位 {_pe:.0f}% / PB百分位 {_pb:.0f}%"
                )
    except Exception:
        pass  # 估值温度失败不阻塞晨报（红线③容错）
    # S3 估值减仓 v2（2026-08-17 十年回测定案：PE/PB 百分位>80 且跌破 6 月均线 → 建议减仓 1/3）
    try:
        from tools.strategy_engine import portfolio as _pf2
        from tools.strategy_engine.signals import s3_valuation_exit

        _p2 = _pf2.Portfolio()
        _pos2, _ = _p2.positions()
        s3_hits = []
        for _pos in _pos2[:5]:
            _vp = data.valuation_percentile(_pos["code"])
            _wk = data.bs_kline_weekly(_pos["code"], years=2)[:24]
            if len(_wk) < 12:
                continue
            _ma24 = sum(_w["close"] for _w in _wk) / len(_wk)
            _last = _wk[0]["close"]
            _sig = s3_valuation_exit(
                _vp.get("pe_percentile"), _vp.get("pb_percentile"), _last, _ma24
            )
            if _sig["signal"]:
                s3_hits.append(f"  ⚠️ {_pos['name']}({_pos['code']})：{_sig['reasons'][0]}")
        if s3_hits:
            lines.append(
                "\n【S3 估值减仓提示（书L5524——建议级——不自动卖）】\n"
                + "\n".join(s3_hits)
                + "\n  规则：PE/PB 百分位>80 且跌破6月均线——十年回测定案——减仓执行需你拍板"
            )
    except Exception:
        pass  # S3 检查失败不阻塞晨报（红线③容错）
    # 龙头池估值候选（B5）
    lines.append("\n【龙头池低估候选（B5：PE<15 或 PB<2）】")
    cands = _valuation_scan(LEADER_POOL)
    if cands:
        for c in cands:
            mark = "✅" if (c["pe"] < 15 and c["pb"] < 2) else "🟡"
            lines.append(
                f"  {mark} {c['name']}({c['code']}) PE={c['pe']} "
                f"PB={c['pb']} 今{c['change_pct']:+.1f}%"
            )
        lines.append(
            "\n【讲解】低估只是第一关——还需价值 8 标准（ROE>10%/现金流/负债率）"
            "和基本面检查（不买清单）——观复会继续过滤"
        )
    else:
        lines.append("  今日龙头池无达标候选（市场整体不便宜——持币等待是纪律）")
    # 明日关注（2026-08-17 加——收盘日报行动项——收盘后看明天）
    lines.append("\n【明日关注】")
    _n_hold = _s2.get("n_holdings", 0) if "_s2" in dir() else 0
    _cash = _s2.get("cash_pct", 0) if "_s2" in dir() else 0
    if not _n_hold:
        lines.append("  🈳 空仓——等待达标信号（B3 低潮/打分达标）")
    elif _cash > 15:
        lines.append("  💰 现金偏高——关注买入信号（B3 低潮/打分达标）")
    else:
        lines.append("  🔍 持仓观察——跌破门槛→观察标记（Q14）")
    lines.append("\n—— 观复 · 书体系执行器（半自动：信号需你确认）")
    return "\n".join(lines)


if __name__ == "__main__":
    print(build_brief())
