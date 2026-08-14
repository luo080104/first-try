# -*- coding: utf-8 -*-
"""观复策略引擎——指标计算库（布林/RSI/九转/量能背离）

来源：策略库 v2（父母理念）——布林 20,2 / RSI(6)（书内参数——待回测对比 14）/
九转 TD Sequential（N+4 与 N 比——月线准确率 90%+ 为书内统计）
全部纯计算——无网络依赖——可单测
"""

from __future__ import annotations

import math
from typing import Sequence


def bollinger(closes: Sequence[float], period: int = 20, k: float = 2.0) -> dict:
    """布林带（中轨=MA，上/下轨=MA±k*SD）

    书内参数：布林(20,2)——95% 概率落在 Mean±2SD 内
    返回 {mid, upper, lower, sd}——数据不足返回 None 值
    """
    if len(closes) < period:
        return {"mid": None, "upper": None, "lower": None, "sd": None}
    window = closes[-period:]
    mid = sum(window) / period
    var = sum((x - mid) ** 2 for x in window) / period
    sd = math.sqrt(var)
    return {
        "mid": round(mid, 4),
        "upper": round(mid + k * sd, 4),
        "lower": round(mid - k * sd, 4),
        "sd": round(sd, 4),
    }


def rsi(closes: Sequence[float], period: int = 6) -> float | None:
    """RSI（相对强弱指数）

    书内参数：RSI(6)（A股/港股经验——20 超卖/80 超买）——标准 14 待回测对比
    RSI = 100 - 100/(1+RS)，RS=平均上涨/平均下跌（Wilder 平滑）
    """
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - 100.0 / (1.0 + rs), 2)


def td_sequential(closes: Sequence[float]) -> dict:
    """九转指标（TD Sequential——书内原理）

    规则：连续 K 线满足 N+4 收盘价 < N 收盘价（下跌九转）
    或 N+4 收盘价 > N 收盘价（上涨九转）——计数 1-9——第 6 根起显示——
    第 9 根 = 趋势大概率终结的拐点信号（月线准确率 90%+ 为书内统计）
    返回 {count, setup: 'buy'(下九转)/'sell'(上九转)/None, completed}
    """
    if len(closes) < 5:
        return {"count": 0, "setup": None, "completed": False}
    # 下跌九转（下九转——买入信号）：连续 9 根 N+4 < N
    down_count = 0
    i = len(closes) - 1
    while i >= 4:
        if closes[i] < closes[i - 4]:
            down_count += 1
            i -= 1
        else:
            break
    # 上涨九转（上九转——卖出信号）：连续 9 根 N+4 > N
    up_count = 0
    i = len(closes) - 1
    while i >= 4:
        if closes[i] > closes[i - 4]:
            up_count += 1
            i -= 1
        else:
            break
    if down_count >= 9:
        return {"count": down_count, "setup": "buy", "completed": True}
    if up_count >= 9:
        return {"count": up_count, "setup": "sell", "completed": True}
    if down_count >= 6:
        return {"count": down_count, "setup": "buy", "completed": False}
    if up_count >= 6:
        return {"count": up_count, "setup": "sell", "completed": False}
    return {"count": 0, "setup": None, "completed": False}


def volume_divergence(
    closes: Sequence[float], volumes: Sequence[float], window: int = 20
) -> dict:
    """量价背离检测（书内：量为价先——背离常反转）

    - 底背离（买入信号）：价格创新低但量能未同步新低（缩无可缩=地量地价）
      或价格新低但量显著放大（恐慌性见底）
    - 顶背离（卖出信号）：价格创新高但量能未同步新高（价高量缩=烟花尾声）
    返回 {type: 'bullish'/'bearish'/None, note}
    """
    if len(closes) < window + 5 or len(volumes) < window + 5:
        return {"type": None, "note": "数据不足"}
    price_low_2 = min(closes[-window * 2 : -window])
    price_low_1 = min(closes[-window:])
    vol_low_2 = min(volumes[-window * 2 : -window])
    vol_low_1 = min(volumes[-window:])
    price_high_2 = max(closes[-window * 2 : -window])
    price_high_1 = max(closes[-window:])
    vol_high_2 = max(volumes[-window * 2 : -window])
    vol_high_1 = max(volumes[-window:])
    # 底背离：新低但量不低（缩量见底）
    if price_low_1 < price_low_2 and vol_low_1 < vol_low_2 * 0.8:
        return {"type": "bullish", "note": "价格新低+量能萎缩（地量地价）"}
    # 顶背离：新高但量不高
    if price_high_1 > price_high_2 and vol_high_1 < vol_high_2 * 0.8:
        return {"type": "bearish", "note": "价格新高+量能萎缩（价高量缩）"}
    return {"type": None, "note": "无背离"}
