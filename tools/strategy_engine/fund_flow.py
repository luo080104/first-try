# -*- coding: utf-8 -*-
"""主力资金流辅助（fund_flow.py——2026-08-15 第四批案例精读落地）

来源：aiagents-stock fund_flow_akshare（344 行精读——akshare 接口现成可用——2026-08-15 实测）
定位：**辅助确认，不做选股**（书体系=价值+趋势——资金流非主线——"未验证不落地"红线）
用途：讲解模式"主力也在买吗？"——B5 低估候选 + 主力净流入 = 更强信号（弱化版确认）
数据源：akshare stock_individual_fund_flow（免费——无需浏览器——代理绕过）
"""

from __future__ import annotations

import os
from typing import Any


def _ths_fallback(code: str) -> dict[str, Any] | None:
    """同花顺资金流 fallback（2026-08-15——东财 push2 间歇封锁的免费替代）

    实测：stock_fund_flow_individual 可用（5205 只全市场——同花顺后端不受东财封锁影响）
    限制：仅当日即时快照（无 5 日历史）——降级为当日净流入；全市场拉取较慢（~10s）
    code 六位数字——股票代码列是整数——需 int 匹配
    """
    try:
        import akshare as ak

        df = ak.stock_fund_flow_individual(symbol="即时")
        if df is None or df.empty:
            return None
        row = df[df["股票代码"] == int(code)]
        if row.empty:
            return None
        r = row.iloc[0]

        # 列：流入资金/流出资金/净额/成交额——值为字符串带单位（"17.20亿"）
        def _to_yi(v: str) -> float:
            s = str(v).strip().replace("+", "")
            try:
                if s.endswith("亿"):
                    return float(s[:-1])
                if s.endswith("万"):
                    return float(s[:-1]) / 10000
                return float(s) / 1e8
            except ValueError:
                return 0.0

        net_yi = _to_yi(r["净额"])
        inflow_yi = _to_yi(r["流入资金"])
        total_yi = inflow_yi + _to_yi(r["流出资金"])
        pct = round(net_yi / total_yi * 100, 1) if total_yi > 0 else 0.0
        trend = "持续流入" if net_yi > 0 else ("流出为主" if net_yi < 0 else "持平")
        return {
            "net_inflow": round(net_yi, 2),
            "net_pct": pct,
            "positive_days": 1 if net_yi > 0 else 0,
            "trend": trend,
            "verdict": f"主力今日净流入 {net_yi:+.2f} 亿（占比 {pct:.1f}%——{trend}——同花顺源）",
        }
    except Exception:
        return None


def main_force_flow(code: str, days: int = 5) -> dict[str, Any]:
    """个股主力资金流（近 N 日——净流入/占比）

    code 六位数字（600519）——返回 {net_inflow, net_pct, trend, verdict}
    trend: 近 N 日主力净流入趋势（正=持续流入）
    verdict: 讲解用一句话（"主力近5日净流入 X 亿"）
    数据源：东财主源（5 日历史）→ 失败自动切同花顺（当日快照——降级标注）
    失败返回空 dict（不抛——红线③容错——讲解模式降级跳过）
    """
    try:
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        import time

        import akshare as ak

        market = "sh" if code.startswith("6") else "sz"
        df = None
        for attempt in range(
            3
        ):  # 东财高频接口间歇封锁（2026-08-15 实测）——重试提高命中
            try:
                df = ak.stock_individual_fund_flow(stock=code, market=market)
                if df is not None and not df.empty:
                    break
            except Exception:
                df = None
            time.sleep(1 + attempt)
        if df is None or df.empty:
            # 东财不可用 → 同花顺 fallback（2026-08-15——免费解封锁）
            fb = _ths_fallback(code)
            if fb:
                return fb
            return {}
        recent = df.tail(days)
        net = recent["主力净流入-净额"].sum()
        pct = recent["主力净流入-净占比"].mean()
        # 趋势：最近 5 日逐日净流入方向（正数天数）
        positive_days = int((recent["主力净流入-净额"] > 0).sum())
        trend = (
            "持续流入"
            if positive_days >= days * 0.8
            else ("流入为主" if positive_days >= days * 0.5 else "流出为主")
        )
        return {
            "net_inflow": round(net / 1e8, 2),  # 亿元
            "net_pct": round(pct, 1),  # 净占比 %
            "positive_days": positive_days,
            "trend": trend,
            "verdict": f"主力近{days}日净流入 {net / 1e8:+.2f} 亿（占比 {pct:.1f}%——{trend}）",
        }
    except Exception:
        return {}


def format_flow_hint(code: str, name: str = "") -> str:
    """讲解模式一句话（无数据时返回空——降级跳过）"""
    f = main_force_flow(code)
    if not f:
        return ""
    tag = f"{name}({code})" if name else code
    return f"【主力动向】{tag}：{f['verdict']}"


if __name__ == "__main__":
    print(format_flow_hint("600519", "贵州茅台"))
