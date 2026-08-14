"""观复行为金融诊断引擎（tools/behavioral_diagnosis.py）

来源：Vibe-Trading (github.com/HKUDS/Vibe-Trading, MIT)
- shadow_account/extractor.py — 交易记录→特征→规则提取思路
- skills/behavioral-finance/SKILL.md — A股行为偏差检测表

用途：观复虚拟盘"纪律达标"维度诊断 + 周报"行为画像"段
输入：交易记录 DataFrame（日期/标的/方向/价格/数量）
输出：行为偏误诊断报告（6维度评分 + 偏误类型 + 改进建议）

检测维度（来自 behavioral-finance SKILL.md）：
1. 处置效应（损失厌恶）：持有亏损>盈利 2-3倍
2. 过度交易（过度自信）：月换手>100% / 单股>30%
3. 锚定效应：入场价附近异常放量
4. 确认偏误：单信息源
5. 近期偏误：近期盈亏影响仓位过大
6. 框架效应：收益vs绝对盈亏决策差异
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import pandas as pd
import numpy as np


@dataclass
class DiagnosisResult:
    """行为诊断结果"""
    # 6维度评分（0=无偏误, 100=严重偏误）
    disposition_effect: float = 0.0       # 处置效应
    overtrading: float = 0.0              # 过度交易
    anchoring: float = 0.0                 # 锚定效应
    confirmation_bias: float = 0.0        # 确认偏误
    recency_bias: float = 0.0             # 近期偏误
    framing_effect: float = 0.0           # 框架效应
    overall_score: float = 0.0            # 综合纪律分（100-偏误分，越高越好）

    # 偏误类型列表
    detected_biases: list[str] = field(default_factory=list)
    # 改进建议
    suggestions: list[str] = field(default_factory=list)
    # 统计摘要
    stats: dict[str, Any] = field(default_factory=dict)


def diagnose_trades(trades_df: pd.DataFrame) -> DiagnosisResult:
    """诊断交易记录的行为偏误

    trades_df 需要列：
        date (datetime): 交易日期
        symbol (str): 标的
        direction (str): 'buy' 或 'sell'
        price (float): 成交价
        quantity (float): 数量
    """
    result = DiagnosisResult()

    if trades_df.empty:
        result.suggestions.append("无交易记录，无法诊断")
        return result

    df = trades_df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    # 配对买卖（FIFO）
    roundtrips = _pair_trades_fifo(df)
    if not roundtrips:
        result.suggestions.append("无完整买卖配对，无法诊断处置效应")
        return result

    # 统计摘要
    result.stats = _compute_stats(df, roundtrips)

    # 1. 处置效应
    result.disposition_effect = _detect_disposition(roundtrips)
    if result.disposition_effect > 50:
        result.detected_biases.append("处置效应（卖盈持亏）")
        result.suggestions.append("预设止损线并机械执行，别让亏损仓位持有太久")

    # 2. 过度交易
    result.overtrading = _detect_overtrading(df)
    if result.overtrading > 50:
        result.detected_biases.append("过度交易（频繁操作）")
        result.suggestions.append("限制每月交易次数，频繁操作拉高费用却无超额收益")

    # 3. 锚定效应（简化：检查是否在特定价格附近反复操作）
    result.anchoring = _detect_anchoring(df)
    if result.anchoring > 50:
        result.detected_biases.append("锚定效应（依赖某价格参考）")
        result.suggestions.append("用相对估值（PE分位数）替代绝对价格做决策")

    # 4. 确认偏误（简化：单标的集中度）
    result.confirmation_bias = _detect_concentration(df)
    if result.confirmation_bias > 50:
        result.detected_biases.append("集中度过高（可能确认偏误）")
        result.suggestions.append("强制阅读对立观点，单股权重控制在20%以内")

    # 5. 近期偏误（检查近期盈亏对仓位影响）
    result.recency_bias = _detect_recency(df, roundtrips)
    if result.recency_bias > 50:
        result.detected_biases.append("近期偏误（近期盈亏影响过大）")
        result.suggestions.append("延长评估窗口到60天以上，别被近期涨跌牵着走")

    # 6. 框架效应（简化：检查买卖是否受绝对金额而非收益率驱动）
    result.framing_effect = _detect_framing(roundtrips)
    if result.framing_effect > 50:
        result.detected_biases.append("框架效应（绝对金额驱动决策）")
        result.suggestions.append("统一用收益率空间评估，别看绝对盈亏金额")

    # 综合分（100 - 偏误平均分）
    biases = [result.disposition_effect, result.overtrading, result.anchoring,
              result.confirmation_bias, result.recency_bias, result.framing_effect]
    result.overall_score = round(100 - np.mean(biases), 1)

    return result


def _pair_trades_fifo(df: pd.DataFrame) -> list[dict]:
    """FIFO 配对买卖，计算每笔完整交易"""
    roundtrips = []
    holdings: dict[str, list] = {}  # symbol -> [(date, price, qty)]

    for _, row in df.iterrows():
        sym = row["symbol"]
        direction = str(row["direction"]).lower()
        price = float(row["price"])
        qty = float(row["quantity"])

        if direction == "buy":
            if sym not in holdings:
                holdings[sym] = []
            holdings[sym].append((row["date"], price, qty))
        elif direction == "sell":
            if sym not in holdings:
                continue
            remaining = qty
            while remaining > 0 and holdings[sym]:
                buy_date, buy_price, buy_qty = holdings[sym][0]
                matched = min(remaining, buy_qty)
                pnl = (price - buy_price) * matched
                pnl_pct = (price / buy_price - 1) * 100 if buy_price > 0 else 0
                holding_days = (row["date"] - buy_date).days
                roundtrips.append({
                    "symbol": sym,
                    "buy_date": buy_date,
                    "sell_date": row["date"],
                    "buy_price": buy_price,
                    "sell_price": price,
                    "quantity": matched,
                    "pnl": pnl,
                    "pnl_pct": pnl_pct,
                    "holding_days": holding_days,
                })
                remaining -= matched
                if matched >= buy_qty:
                    holdings[sym].pop(0)
                else:
                    holdings[sym][0] = (buy_date, buy_price, buy_qty - matched)

    return roundtrips


def _compute_stats(df: pd.DataFrame, roundtrips: list[dict]) -> dict:
    """计算统计摘要"""
    profitable = [rt for rt in roundtrips if rt["pnl"] > 0]
    losing = [rt for rt in roundtrips if rt["pnl"] <= 0]
    hold_profit = [rt["holding_days"] for rt in profitable] or [0]
    hold_loss = [rt["holding_days"] for rt in losing] or [0]

    date_range = (df["date"].min(), df["date"].max())
    months = max(1, (date_range[1] - date_range[0]).days / 30)
    total_trades = len(df)

    return {
        "总交易笔数": total_trades,
        "完整配对数": len(roundtrips),
        "盈利笔数": len(profitable),
        "亏损笔数": len(losing),
        "胜率": f"{len(profitable)/len(roundtrips)*100:.1f}%" if roundtrips else "N/A",
        "盈利平均持有天数": round(np.mean(hold_profit), 1),
        "亏损平均持有天数": round(np.mean(hold_loss), 1),
        "月均交易笔数": round(total_trades / months, 1),
        "总盈亏": round(sum(rt["pnl"] for rt in roundtrips), 2),
        "盈亏比": round(
            np.mean([rt["pnl"] for rt in profitable]) / abs(np.mean([rt["pnl"] for rt in losing]))
            if losing and profitable else 0, 2
        ),
    }


def _detect_disposition(roundtrips: list[dict]) -> float:
    """处置效应：持有亏损仓位的时间 > 盈利仓位 2-3倍"""
    profitable = [rt["holding_days"] for rt in roundtrips if rt["pnl"] > 0]
    losing = [rt["holding_days"] for rt in roundtrips if rt["pnl"] <= 0]
    if not profitable or not losing:
        return 0.0
    avg_profit_hold = np.mean(profitable)
    avg_loss_hold = np.mean(losing)
    ratio = avg_loss_hold / avg_profit_hold if avg_profit_hold > 0 else 1
    # ratio > 2 开始有处置效应，> 3 严重
    if ratio >= 3:
        return 100.0
    elif ratio >= 2:
        return round((ratio - 2) * 100, 1)
    return 0.0


def _detect_overtrading(df: pd.DataFrame) -> float:
    """过度交易：月换手率>100%"""
    date_range = (df["date"].min(), df["date"].max())
    months = max(1, (date_range[1] - date_range[0]).days / 30)
    total_trades = len(df)
    monthly = total_trades / months
    # 月交易>15笔算偏多，>30严重
    if monthly >= 30:
        return 100.0
    elif monthly >= 15:
        return round((monthly - 15) / 15 * 100, 1)
    return 0.0


def _detect_anchoring(df: pd.DataFrame) -> float:
    """锚定效应：同一标的在相近价格反复买卖"""
    sym_prices = df.groupby("symbol")["price"].apply(list)
    anchoring_count = 0
    for prices in sym_prices:
        if len(prices) < 3:
            continue
        prices_arr = np.array(prices)
        mean_p = np.mean(prices_arr)
        if mean_p > 0:
            cv = np.std(prices_arr) / mean_p  # 变异系数
            if cv < 0.05:  # 价格波动<5%，说明在同一价位反复操作
                anchoring_count += 1
    total_syms = len(sym_prices[sym_prices.apply(len) >= 3])
    if total_syms == 0:
        return 0.0
    ratio = anchoring_count / total_syms
    return round(ratio * 100, 1)


def _detect_concentration(df: pd.DataFrame) -> float:
    """集中度：单标的交易占比"""
    sym_counts = df.groupby("symbol").size()
    total = len(df)
    if total == 0:
        return 0.0
    max_ratio = sym_counts.max() / total
    # 单标的>30%算集中
    if max_ratio >= 0.5:
        return 100.0
    elif max_ratio >= 0.3:
        return round((max_ratio - 0.3) / 0.2 * 100, 1)
    return 0.0


def _detect_recency(df: pd.DataFrame, roundtrips: list[dict]) -> float:
    """近期偏误：近期盈亏影响后续仓位"""
    if len(roundtrips) < 4:
        return 0.0
    # 看后半段交易量是否跟前半段盈亏强相关
    mid = len(roundtrips) // 2
    early_pnl = np.mean([abs(rt["pnl"]) for rt in roundtrips[:mid]])
    late_trades = len([rt for rt in roundtrips[mid:]])
    early_trades = mid
    if early_trades == 0:
        return 0.0
    ratio = late_trades / early_trades
    # 后半段交易明显增多（追涨杀跌）
    if ratio >= 2:
        return 100.0
    elif ratio >= 1.5:
        return round((ratio - 1.5) * 100, 1)
    return 0.0


def _detect_framing(roundtrips: list[dict]) -> float:
    """框架效应：看绝对盈亏金额是否影响持有时间"""
    if len(roundtrips) < 4:
        return 0.0
    pnls = [rt["pnl"] for rt in roundtrips]
    holds = [rt["holding_days"] for rt in roundtrips]
    # 如果绝对盈亏金额和持有时间相关性高，说明受绝对金额驱动
    if np.std(pnls) == 0:
        return 0.0
    corr = abs(np.corrcoef(pnls, holds)[0, 1]) if np.std(holds) > 0 else 0
    # corr > 0.5 有框架效应
    if corr >= 0.7:
        return 100.0
    elif corr >= 0.5:
        return round((corr - 0.5) * 250, 1)
    return 0.0


def format_report(result: DiagnosisResult) -> str:
    """格式化诊断报告（周报用）"""
    lines = ["## 行为画像诊断报告", ""]
    lines.append(f"**综合纪律分：{result.overall_score}/100**")
    lines.append("")
    lines.append("### 6维度偏误评分")
    lines.append(f"| 维度 | 评分 | 状态 |")
    lines.append(f"|------|------|------|")
    for name, score in [
        ("处置效应", result.disposition_effect),
        ("过度交易", result.overtrading),
        ("锚定效应", result.anchoring),
        ("确认偏误", result.confirmation_bias),
        ("近期偏误", result.recency_bias),
        ("框架效应", result.framing_effect),
    ]:
        status = "✅ 正常" if score < 30 else ("⚠️ 偏重" if score < 60 else "🔴 严重")
        lines.append(f"| {name} | {score} | {status} |")
    lines.append("")
    if result.detected_biases:
        lines.append("### 检出偏误")
        for b in result.detected_biases:
            lines.append(f"- {b}")
        lines.append("")
    if result.suggestions:
        lines.append("### 改进建议")
        for s in result.suggestions:
            lines.append(f"- {s}")
        lines.append("")
    if result.stats:
        lines.append("### 交易统计")
        for k, v in result.stats.items():
            lines.append(f"- {k}：{v}")
    return "\n".join(lines)


if __name__ == "__main__":
    # 测试：构造模拟交易记录
    dates = pd.date_range("2026-01-01", periods=20, freq="5D")
    test_data = []
    for i, d in enumerate(dates):
        sym = "茅台" if i % 2 == 0 else "腾讯"
        direction = "buy" if i % 2 == 0 else "sell"
        price = 1500 + i * 10
        test_data.append({"date": d, "symbol": sym, "direction": direction,
                          "price": price, "quantity": 100})
    df = pd.DataFrame(test_data)
    result = diagnose_trades(df)
    print(format_report(result))
