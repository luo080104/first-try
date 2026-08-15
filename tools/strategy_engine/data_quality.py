# -*- coding: utf-8 -*-
"""数据质量检查（data_quality.py——2026-08-15 第六批案例精读收官落地）

借鉴：WealthAgent DataQualityChecker（365 行全读——8 项检查——借 3 项纯 Python 可实现）
定位：数据核验自动化（我们已遇 3 次数据错误：占位/错位/截断——靠人工核验发现——现在系统化）
检查项：
  1. MAD 异常值（滚动 MAD 截断——修正 Z>5——抓错价/跳空）
  2. 数据延迟（最新日期距今>5 天——接口静默挂掉告警）
  3. 质量等级（critical/warning → ERROR/SUSPICIOUS/GOOD——讲解模式标注数据可信度）
接入：core_loop 自检段（每日循环——anomalies 并入）
"""

from __future__ import annotations

import datetime
from statistics import median
from typing import Any

MAX_CONSECUTIVE_MISSING = 5  # 连续缺失阈值（交易日）
MAX_DAILY_CHANGE = 0.15  # 单日涨跌幅异常阈值 15%（A 股涨跌停 10%/20%——15% 覆盖）
MAX_DELAY_DAYS = 5  # 数据最大延迟（日）

# 交易日历缓存（akshare tool_trade_date_hist_sina——免费——2026-08-15 实测 8797 条）
_TRADE_DATES: set[str] | None = None


def _trade_dates() -> set[str]:
    """A 股交易日集合（首次拉取缓存——失败不缓存——下次重试）"""
    global _TRADE_DATES
    if _TRADE_DATES is not None:
        return _TRADE_DATES
    try:
        import os

        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        _TRADE_DATES = {str(d)[:10] for d in df["trade_date"]}
    except Exception:
        pass  # 失败不缓存——下次调用重试（缓存空 set 会导致节假日误报——2026-08-15 修复）
    return _TRADE_DATES or set()


def _is_trade_day(d: str) -> bool | None:
    """是否交易日——日历不可用返回 None（调用方跳过检查——不误报）

    2026-08-15 修复：日历拉取失败时不再降级到周末近似——
    否则春节/国庆长假被误报为数据缺失（网络失败→误报比不报更糟）
    """
    td = _trade_dates()
    if not td:
        return None
    return d in td


def _modified_z(values: list[float]) -> list[float]:
    """修正 Z 分数（MAD 截断——0.6745 系数——WealthAgent 同款）"""
    if len(values) < 10:
        return []
    med = median(values)
    mad = median(abs(v - med) for v in values)
    if mad < 1e-8:
        return []
    return [0.6745 * (v - med) / mad for v in values]


def check_price_series(
    prices: list[float], dates: list[str] | None = None
) -> list[dict[str, Any]]:
    """K 线/价格序列质量检查（MAD 异常值 + 连续缺失）

    prices: 收盘价序列（升序）——dates: 对应日期（可选——用于缺失检查）
    返回 [{test, issue, severity, value}]——空=正常
    """
    issues: list[dict[str, Any]] = []
    if len(prices) < 30:
        return issues
    # ① MAD 异常值（收益率序列——修正 Z>5）
    rets = [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] > 0
    ]
    zs = _modified_z(rets)
    for i, z in enumerate(zs):
        if abs(z) > 5.0:
            d = dates[i + 1] if dates and i + 1 < len(dates) else f"#{i + 1}"
            issues.append(
                {
                    "test": "MAD异常值",
                    "issue": f"单日涨跌幅异常 {rets[i]:.2%}（修正Z={z:.1f}）@{d}",
                    "severity": "warning",
                    "value": round(rets[i], 4),
                }
            )
    # ② 连续缺失（缺失【交易日】数——节假日豁免——2026-08-15 修复误报）
    # 原实现按自然日计数——春节/国庆长假被误报为数据缺失（腾讯 K 线只返回交易日）
    if dates and len(dates) > 1:
        max_gap = 0
        cur = 0
        for i in range(1, len(dates)):
            try:
                d1 = datetime.date.fromisoformat(dates[i - 1])
                d2 = datetime.date.fromisoformat(dates[i])
            except ValueError:
                continue
            # 缺口期间的交易日数（跳过周末/节假日）
            missing = 0
            d = d1 + datetime.timedelta(days=1)
            while d < d2:
                is_td = _is_trade_day(d.isoformat())
                if is_td is None:
                    return issues  # 日历不可用——跳过缺失检查（不误报）
                if is_td:
                    missing += 1
                d += datetime.timedelta(days=1)
            if missing > 0:
                cur += missing
            else:
                max_gap = max(max_gap, cur)
                cur = 0
        max_gap = max(max_gap, cur)
        if max_gap > MAX_CONSECUTIVE_MISSING:
            issues.append(
                {
                    "test": "连续缺失",
                    "issue": f"最大连续缺失 {max_gap} 个交易日",
                    "severity": "warning" if max_gap <= 10 else "critical",
                    "value": max_gap,
                }
            )
    return issues


def check_data_delay(last_date: str | None) -> dict[str, Any] | None:
    """数据延迟检查（最新数据日期 vs 今天——>5 天告警——接口静默挂掉）"""
    if not last_date:
        return None
    try:
        delay = (datetime.date.today() - datetime.date.fromisoformat(last_date)).days
    except ValueError:
        return None
    if delay > MAX_DELAY_DAYS:
        return {
            "test": "数据延迟",
            "issue": f"数据延迟 {delay} 天（最新 {last_date}——接口可能挂了）",
            "severity": "warning" if delay <= 10 else "critical",
            "value": delay,
        }
    return None


def quality_level(issues: list[dict[str, Any]]) -> str:
    """质量等级汇总（critical→ERROR / warning→SUSPICIOUS / 无→GOOD）"""
    sevs = {i.get("severity") for i in issues}
    if "critical" in sevs:
        return "ERROR"
    if "warning" in sevs:
        return "SUSPICIOUS"
    return "GOOD"


def classify_missingness(
    mask: list[bool], other_masks: list[list[bool]] | None = None
) -> str:
    """缺失机制分类（2026-08-15 claude-skills data-quality-auditor 借鉴）

    - MCAR（随机缺失）：null 与其他列/位置无相关性——重试有效
    - MAR（条件缺失）：null 与其他列的缺失共现（Jaccard>0.5）——需观察关联列
    - MNAR（系统性缺失）：null 连续成块（时间聚类）——重试无效（接口封锁类）

    用途：诊断"重试无效"类问题（东财 push2 封锁=MNAR——重试 3 次无效是必然）
    mask: 布尔列表（True=缺失）——other_masks: 其他序列的缺失掩码（可选）
    """
    null_idx = {i for i, v in enumerate(mask) if v}
    if not null_idx:
        return "无缺失"
    if len(mask) < 10:
        return "样本不足"
    # ① 与其他列缺失共现（Jaccard>0.5 → MAR）
    if other_masks:
        for om in other_masks:
            other_null = {i for i, v in enumerate(om) if v}
            if not other_null:
                continue
            inter = len(null_idx & other_null)
            union = len(null_idx | other_null)
            if union and inter / union > 0.5:
                return "MAR（缺失与其他列共现）"
    # ② 缺失聚类（时间连续成块 → MNAR——系统性）
    sorted_idx = sorted(null_idx)
    if len(sorted_idx) > 2:
        max_run = 1
        cur = 1
        for i in range(1, len(sorted_idx)):
            if sorted_idx[i] - sorted_idx[i - 1] == 1:
                cur += 1
                max_run = max(max_run, cur)
            else:
                cur = 1
        if max_run >= 3:
            return "MNAR（系统性缺失——连续成块——重试无效）"
    return "MCAR（随机缺失——重试可能有效）"


def quality_summary(
    prices: list[float], dates: list[str] | None = None, last_date: str | None = None
) -> dict[str, Any]:
    """完整数据质量摘要（core_loop 自检段接入点）"""
    issues: list[dict[str, Any]] = []
    issues.extend(check_price_series(prices, dates))
    delay = check_data_delay(last_date)
    if delay:
        issues.append(delay)
    return {
        "level": quality_level(issues),
        "total_issues": len(issues),
        "issues": issues,
    }
