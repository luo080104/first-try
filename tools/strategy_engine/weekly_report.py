# -*- coding: utf-8 -*-
"""周报（weekly_report.py——v1.2——每周自动复盘：操作/盈亏/策略表现/下周关注）

需求 v1.1 补录：周报=每周自动（操作/盈亏/策略表现/下周关注）——行为画像段（Q10）
数据源：portfolio 事件日志（本周操作）+ 当前持仓（盈亏）+ signal_ledger（信号表现）
- 行为画像（Q10）：本周操作 vs 纪律检查（追涨/杀跌/频繁交易/偏离计划）
- 推送：复用 notify_gf（低频合并节流——周报算 1 条）
- 用法：python -m tools.strategy_engine.weekly_report（每周五收盘后任务计划）
"""

from __future__ import annotations

import datetime
import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import portfolio as pf

_WEEK_START = datetime.timedelta(days=7)


def _week_events() -> list[dict[str, Any]]:
    """本周事件（portfolio_events.jsonl——近 7 天）"""
    out = []
    try:
        with open(pf.EVENTS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                ts = (e.get("ts") or "")[:10]
                if (
                    ts
                    and (datetime.date.today() - datetime.date.fromisoformat(ts)).days
                    <= 7
                ):
                    out.append(e)
    except OSError:
        pass
    return out


def behavior_alert() -> str:
    """过早卖出行为提醒（2026-08-16 A3 落地——Q10 主动干预）

    判定：卖出事件后 20 日最高价 > 卖出价 ×1.1 → 记一次过早卖出
    累计 ≥3 次 → 返回提醒文本（晨报显示）——连续 3 次过早卖出是行为模式
    而非偶发——提醒而非命令（红线：卖出决策始终归甲方）
    """
    import json as _json
    import os as _os

    events = []
    try:
        ev_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(pf.__file__)),
            "..",
            "..",
            "data",
            "portfolio_events.jsonl",
        )
        with open(ev_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(_json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return ""
    sells = [e for e in events if e.get("action") == "sell" and e.get("price")]
    if not sells:
        return ""
    from tools.strategy_engine import data as d

    early = 0
    details: list[str] = []
    for e in sells[-10:]:  # 最近 10 次卖出
        code = e.get("code", "")
        sold_at = (e.get("ts") or "")[:10]
        try:
            price = float(e.get("price", 0))
        except (TypeError, ValueError):
            continue
        if not code or not sold_at or price <= 0:
            continue
        try:
            days = d.bs_kline_daily(code, 1)
        except Exception:
            continue
        after = [x for x in days if x["date"] >= sold_at][:20]
        if len(after) < 5:
            continue  # 卖出后数据不足（太近）——不算
        hi = max(x["close"] for x in after)
        if hi > price * 1.10:
            early += 1
            details.append(
                f"{e.get('name', code)} 卖出 {price} 后 20 日最高 {hi:.2f}（+{(hi / price - 1) * 100:.0f}%）"
            )
    if early >= 3:
        return (
            "🧭 **行为提醒（Q10）：过早卖出模式**\n"
            + "\n".join(f"  · {x}" for x in details)
            + "\n  连续 3 次过早卖出——书：拿住是纪律——卖出前重查 S2/S3/S4 是否真触发"
        )
    return ""


def _behavior_check(events: list[dict[str, Any]]) -> list[str]:
    """行为画像（Q10——纪律检查——Q7 教训：拿住是纪律）"""
    notes: list[str] = []
    buys = [e for e in events if e.get("action") in ("buy", "加仓", "加仓")]
    sells = [e for e in events if e.get("action") in ("sell", "减仓", "减仓")]
    if len(buys) + len(sells) > 5:
        notes.append(
            f"⚠️ 本周操作 {len(buys) + len(sells)} 笔——偏频繁（书：低频合并——计划外不动）"
        )
    if buys and not sells:
        notes.append("✅ 本周只加仓未减仓——拿住纪律（Q10）")
    if sells and not buys:
        notes.append("ℹ️ 本周只减仓——检查是否触发卖出规则（S2 上轨/止损）")
    if not events:
        notes.append("✅ 本周无操作——持有不动是纪律（Q10——最不坏路径）")
    return notes or ["✅ 操作符合计划"]


def build_report() -> str:
    """组装周报文本 v2（2026-08-16——界面美化升级——UZI Bento 布局借鉴）

    结构（微信 Markdown 友好）：
    ① 头部（品牌+日期+周次）
    ② 数据面板（总资产/盈亏/现金/持仓数——一行 KPI）
    ③ 本周操作（事件流）
    ④ 持仓明细（逐只盈亏）
    ⑤ 策略表现（信号/在线评分/漂移）
    ⑥ 行为画像（Q10）
    ⑦ 下周关注（行动项）
    ⑧ 尾注（数据源状态/净值图提示）
    """
    p = pf.Portfolio()
    s = p.summary()
    events = _week_events()
    today = datetime.date.today()
    week_no = today.isocalendar()[1]
    lines = [
        f"📊 **观复周报** · 第 {week_no} 周",
        f"🗓️ {today.isoformat()} · 书体系执行器",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    # ① KPI 数据面板（Bento 头卡——一行看全）
    pnl = s.get("total", 0) - s.get("init_cash", 0)
    pnl_pct = pnl / s.get("init_cash", 1) * 100
    pnl_icon = "📈" if pnl >= 0 else "📉"
    n_hold = s.get("n_holdings", 0)
    cash_pct = s.get("cash_pct", 0)
    lines.append(
        f"{pnl_icon} **总资产 {s.get('total', 0):,.0f}** ｜ "
        f"盈亏 {pnl:+,.0f}（{pnl_pct:+.1f}%）\n"
        f"🏦 持仓 {n_hold} 只 ｜ 💰 现金 {cash_pct:.0f}% ｜ 建仓 {_days_since_start()} 天"
    )

    # ② 本周操作（事件流）
    ops = [e for e in events if e.get("action") in ("buy", "sell")]
    lines.append("\n**📋 本周操作**")
    if ops:
        for e in ops:
            icon = "🟢" if e["action"] == "buy" else "🔴"
            lines.append(
                f"{icon} {'买入' if e['action'] == 'buy' else '卖出'} "
                f"**{e.get('name', '')}**({e.get('code', '')}) "
                f"{e.get('shares', 0)}股 @ {e.get('price', 0)}"
            )
    else:
        lines.append("🤝 无操作——持有不动（纪律）")

    # ③ 持仓明细（逐只盈亏）
    lines.append("\n**📦 持仓明细**")
    positions = s.get("positions", [])
    if positions:
        for pos in positions:
            pp = pos.get("pnl_pct", 0)
            icon = "🟢" if pp >= 0 else "🔴"
            lines.append(
                f"{icon} {pos.get('name', '')}({pos.get('code', '')}) "
                f"{pos.get('shares', 0)}股 {pp:+.1f}%"
            )
    else:
        lines.append("🈳 空仓——持币等待是纪律")

    # ④ 策略表现（信号账本 + 在线评分——整改②）
    lines.append("\n**🎯 策略表现**")
    try:
        from tools.strategy_engine import signal_ledger as sl

        rep = sl.report()
        if isinstance(rep, dict) and rep.get("total"):
            lines.append(f"📒 累计信号 {rep['total']} 笔")
        else:
            lines.append("📒 账本采集中（3/6/12 月后回填验证）")
        try:
            oscore = sl.online_score(window=20)
            if oscore.get("monthly"):
                for m, st in list(oscore["monthly"].items())[-3:]:
                    lines.append(
                        f"📊 {m}: N={st['n']} 胜率 {st['win_rate']}% "
                        f"均{st['avg']:+.1f}%"
                    )
            if oscore.get("drift"):
                lines.append(f"⚠️ {oscore['note']}")
        except Exception:
            pass  # 在线评分失败不阻塞周报（红线③容错）
    except Exception:
        lines.append("📒 账本采集中（3/6/12 月后回填验证）")

    # ⑤ 行为画像（Q10）
    lines.append("\n**🧭 行为画像**")
    lines.extend(f"{n}" for n in _behavior_check(events))

    # ⑥ 下周关注（行动项）
    lines.append("\n**🎯 下周关注**")
    if not n_hold:
        lines.append("🈳 空仓中——等待达标信号（持币等待是纪律）")
    elif cash_pct > 15:
        lines.append("💰 现金偏高——关注买入信号（B3 低潮/打分达标）")
    else:
        lines.append("🔍 持仓观察——跌破门槛→观察标记，连续两季→换仓建议（Q14）")

    # ⑦ 大V 观察（2026-08-16 B2 落地——高贴近度组合 + 鹿鼎公微博）
    lines.append("\n**📡 大V 观察**")
    try:
        import json as _json
        import os as _os

        _data_dir = _os.path.join(
            _os.path.dirname(_os.path.abspath(pf.__file__)), "..", "..", "data"
        )
        _navs = {}
        _nav_path = _os.path.join(_data_dir, "xq_nav.json")
        if _os.path.exists(_nav_path):
            with open(_nav_path, encoding="utf-8") as _f:
                _navs = _json.load(_f)
        _descs = {}
        _desc_path = _os.path.join(_data_dir, "xq_cube_desc.json")
        if _os.path.exists(_desc_path):
            with open(_desc_path, encoding="utf-8") as _f:
                _descs = _json.load(_f)
        if _navs:
            # 高贴近度过滤（trust_level——实盘自述优先）
            from tools.strategy_engine.xq_track import _latest_trade_ts, trust_level

            _high = [
                k
                for k, v in _navs.items()
                if trust_level(
                    k, _descs.get(k, {}).get("desc", ""), _latest_trade_ts(k)
                )["level"]
                == "高"
            ]
            _top = sorted(_high, key=lambda k: _navs[k].get("gain") or 0, reverse=True)[
                :5
            ]
            if _top:
                lines.append("👀 高贴近度组合（实盘自述）前 5：")
                for k in _top:
                    v = _navs[k]
                    lines.append(
                        f"  · {v.get('name', k)}: 净值 {v.get('nav')} "
                        f"总收益 {v.get('gain')}%（{v.get('ts', '')[:10]}）"
                    )
            else:
                lines.append("👀 暂无高贴近度组合（分级积累中）")
        # 鹿鼎公微博（本周）
        try:
            from tools.strategy_engine.wb_track import digest as _wb_digest

            _wb = _wb_digest()
            if "暂无数据" not in _wb:
                lines.append(_wb)
        except Exception:
            pass  # 微博摘要失败不阻塞周报（红线③容错）
        if not _navs:
            lines.append("📡 大V 数据采集中（16:00 后自动积累）")
    except Exception:
        lines.append("📡 大V 数据采集中（16:00 后自动积累）")

    # ⑦ 尾注（数据源状态）
    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📌 数据源：东财封锁→同花顺降级（当日快照）｜净值图见网页版")
    # 双源对账（2026-08-16 架构师 R1——静默数据漂移检测——无差异不显示）
    try:
        from tools.strategy_engine.data_reconcile import report as _rec_report

        rec = _rec_report()
        if rec:
            lines.append("\n" + rec)
    except Exception:
        pass  # 对账失败不阻塞周报（红线③容错）
    return "\n".join(lines)


def _days_since_start() -> int:
    """建仓天数（事件日志最早 buy——与 gate_check 同逻辑——健壮版）"""
    try:
        import json as _json
        import os as _os

        events_path = _os.path.join(
            _os.path.dirname(_os.path.abspath(pf.__file__)),
            "..",
            "..",
            "data",
            "portfolio_events.jsonl",
        )
        buys = []
        with open(events_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = _json.loads(line)
                except ValueError:
                    continue
                if e.get("action") == "buy" and e.get("ts"):
                    buys.append(e["ts"][:10])
        if buys:
            start = min(buys)
            return (datetime.date.today() - datetime.date.fromisoformat(start)).days
    except Exception:
        pass
    return 0


def _equity_curve_png() -> str | None:
    """净值曲线图 → base64 data URL（2026-08-15——周报图——Server酱 pics 内嵌）

    matplotlib Agg 无头渲染——失败返回 None（文本周报降级——红线③容错）
    """
    try:
        import base64
        import io

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 中文字体（Windows 微软雅黑——matplotlib 默认 DejaVu 无 CJK 字形）
        plt.rcParams["font.sans-serif"] = [
            "Microsoft YaHei",
            "SimHei",
            "DejaVu Sans",
        ]
        plt.rcParams["axes.unicode_minus"] = False

        curve = pf.Portfolio().equity_series()
        if len(curve) < 2:
            return None
        dates = [c["date"] for c in curve]
        totals = [c["total"] for c in curve]
        # 沪深300 对比（同窗口——baostock 周线）
        bench: list[float] = []
        try:
            from tools.strategy_engine import data as d

            bw = d.bs_kline_weekly("000300", 10)
            bd = {w["date"][:10]: w["close"] for w in bw}
            init_b = None
            for dt in dates:
                if dt in bd:
                    if init_b is None:
                        init_b = bd[dt]
                    if init_b:
                        bench.append(round((bd[dt] / init_b - 1) * 100, 2))
        except Exception:
            pass  # 基准失败——只有净值线
        fig, ax = plt.subplots(figsize=(7, 3.5))
        init = totals[0] or 1
        norm = [(t / init - 1) * 100 for t in totals]
        ax.plot(dates, norm, label="观复组合", color="#2563eb", linewidth=2)
        if len(bench) == len(norm):
            ax.plot(
                dates, bench, label="沪深300", color="#d97706", linewidth=1.5, alpha=0.8
            )
        ax.axhline(0, color="#999", linewidth=0.8, linestyle="--")
        ax.set_title("观复虚拟盘净值（相对初始 %）")
        ax.legend(fontsize=9)
        ax.tick_params(axis="x", rotation=30, labelsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=100)
        plt.close(fig)
        return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def push_weekly_with_chart() -> bool:
    """周报推送（含净值图——Server酱 pics 内嵌——2026-08-15）

    无图（净值点不足/渲染失败）→ 纯文本周报降级
    """
    from tools.strategy_engine import notify_gf as ng

    if ng.push_wechat is None:
        return False
    text = build_report()
    pic = _equity_curve_png()
    return ng.push_with_pic(f"📊 观复周报（含净值图）\n\n{text}", pic)


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--push":
        ok = push_weekly_with_chart()
        print(f"周报推送（含图）: {'✅' if ok else '❌'}")
    else:
        print(build_report())
