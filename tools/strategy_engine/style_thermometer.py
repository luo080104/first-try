# -*- coding: utf-8 -*-
"""风格温度计（Q8——风格轮动双驱动——季度低频）

定案（docs/观复落地实施方案.md Q8）：
- 底层驱动 = 利率趋势（10 年国债方向——Q1 接口复用）
- 确认信号 = RS 12 月动量（红利/沪深300 比值动量——转负 + 利率回升 → 减红利）
- 频率：季度（低频——简单偏离轮动会卖飞——Q8 教训）
- 输出：风格状态（红利占优/成长占优/均衡）+ 配置建议 ±5-10%

参数 v0 先验（Q11 待校准）。运行：python -m tools.strategy_engine.style_thermometer
"""

from __future__ import annotations

import statistics
from typing import Any

from tools.strategy_engine import data


def _rate_trend() -> str | None:
    """10 年国债利率趋势（近 90 日均值 vs 前 90 日均值——下行/上行/走平）"""
    import akshare as ak

    try:
        df = ak.bond_zh_us_rate(start_date="20260101")
        r = df["中国国债收益率10年"].dropna().tolist()
        if len(r) < 40:
            return None
        recent = statistics.mean(r[-20:])
        earlier = statistics.mean(r[-60:-20])
        diff = recent - earlier
        if diff < -0.05:
            return "下行"
        if diff > 0.05:
            return "上行"
        return "走平"
    except Exception:
        return None


def _rs_momentum() -> float | None:
    """RS 12 月动量：红利/沪深300 相对强度（现比值 vs 12 月前比值——%变化）"""
    try:
        h = data.tencent_kline("sh000015", days=260)
        c = data.tencent_kline("sh000300", days=260)
        if not h or not c or len(h) < 250 or len(c) < 250:
            return None
        now = h[-1]["close"] / c[-1]["close"]
        prev = h[-250]["close"] / c[-250]["close"]
        return round((now - prev) / prev * 100, 1)
    except Exception:
        return None


def style_status() -> dict[str, Any]:
    """风格状态（Q8——利率趋势 + RS 动量双驱动）"""
    rate = _rate_trend()
    rs = _rs_momentum()
    evidence: list[str] = []
    if rate:
        evidence.append(f"利率趋势：{rate}（10 年国债 90 日均值对比）")
    if rs is not None:
        evidence.append(f"RS 12 月动量：{rs:+.1f}%（红利/沪深300 相对强度）")

    # 判定（Q8 定案：利率底层驱动 + RS 确认）
    if rate == "下行" and (rs is None or rs > 0):
        style = "红利占优"
        advice = "红利配置 +5-10%（利率下行+RS 走强——低利率资产荒主线）"
    elif rate == "上行" and rs is not None and rs < 0:
        style = "成长占优"
        advice = "减红利 5-10%（利率回升+RS 转负——风格切换信号）"
    elif rate == "上行" or (rs is not None and rs < -5):
        style = "均衡偏成长"
        advice = "关注成长——红利谨慎（单一信号——季度再确认）"
    elif rate == "下行" or (rs is not None and rs > 5):
        style = "均衡偏红利"
        advice = "红利底仓可留（单一信号——季度再确认）"
    else:
        style = "均衡"
        advice = "维持当前配置（无风格极端信号——低频验证）"
    return {"style": style, "rate_trend": rate, "rs_12m": rs,
            "advice": advice, "evidence": evidence,
            "note": "季度频率——简单偏离轮动会卖飞（Q8 教训）——v0 参数待校准"}


def main():
    s = style_status()
    print(f"风格温度计: {s['style']}")
    print(f"建议: {s['advice']}")
    for e in s["evidence"]:
        print("  -", e)


if __name__ == "__main__":
    main()
