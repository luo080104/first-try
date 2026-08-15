# -*- coding: utf-8 -*-
"""统计检验工具（stats_tools.py——2026-08-15——WealthAgent significance 借鉴——简化版）

用途（Q11 精神：样本不足不判定 / 未验证不落地红线的量化工具）：
- bootstrap_winrate：胜率是否显著高于基准（如 50%）——重采样 p 值
- bootstrap_diff：两组胜率差异是否显著（如 A 卖出 vs B 卖出）
- min_samples：给定目标差异，估算所需样本量（MinBTL 简化版——Bailey 2014 思想）

纯 Python 实现（不引 scipy——零依赖——A 股场景够用）
"""

from __future__ import annotations

import random

random.seed(42)  # 可复现（观测序列固定——重采样随机性可控）


def bootstrap_winrate(
    wins: int, n: int, baseline: float = 0.5, iters: int = 10000
) -> dict:
    """胜率显著性检验：观测胜率 vs 基准（默认 50% 随机）——H0: 无优势

    返回 {win_rate, p_value, significant}——p<0.05 才显著（WealthAgent 同标准）
    """
    if n <= 0:
        return {"win_rate": 0.0, "p_value": 1.0, "significant": False}
    obs = wins / n
    # H0 下：每笔独立 Bernoulli(baseline)——观测胜率的出现概率
    cnt = 0
    for _ in range(iters):
        sample = [1 if random.random() < baseline else 0 for _ in range(n)]
        if sum(sample) / n >= obs:
            cnt += 1
    p = cnt / iters
    return {
        "win_rate": round(obs * 100, 1),
        "p_value": round(p, 3),
        "significant": p < 0.05,
    }


def bootstrap_diff(
    n1: int, w1: float, n2: int, w2: float, iters: int = 10000
) -> dict:
    """两组胜率差异显著性：H0 无差异——置换检验（合并重采样）

    返回 {diff, p_value, significant}——p<0.05 才显著
    """
    if n1 <= 0 or n2 <= 0:
        return {"diff": 0.0, "p_value": 1.0, "significant": False}
    g1 = [1] * round(n1 * w1) + [0] * (n1 - round(n1 * w1))
    g2 = [1] * round(n2 * w2) + [0] * (n2 - round(n2 * w2))
    obs_diff = w1 - w2
    pooled = g1 + g2
    cnt = 0
    for _ in range(iters):
        random.shuffle(pooled)
        a = pooled[:n1]
        b = pooled[n1:]
        if sum(a) / n1 - sum(b) / n2 >= obs_diff:
            cnt += 1
    p = cnt / iters
    return {
        "diff": round(obs_diff * 100, 1),
        "p_value": round(p, 3),
        "significant": p < 0.05,
    }


def min_samples(target_diff: float, iters: int = 2000) -> int:
    """估算所需样本量（每组）：给定胜率差（如 10 点）——p<0.05 需要多少样本

    MinBTL 思想简化版（Bailey 2014——样本太少结果不可信——给量化门槛）
    """
    n = 20
    while n <= 500:
        p = bootstrap_diff(n, 0.6, n, 0.6 - target_diff, iters=iters)["p_value"]
        if p < 0.05:
            return n
        n += 10
    return 500


def check_rule(
    rule_name: str, wins: int, n: int, baseline: float = 0.5
) -> dict:
    """规则验证入口：胜率显著性检查——'未验证不落地'红线的量化关卡

    用法：verify_book_rules / 回测结论——N 小且不显著 → 标'待积累'（Q11）
    """
    r = bootstrap_winrate(wins, n, baseline)
    verdict = "✅ 显著" if r["significant"] else "⏳ 待积累（样本不足——不落地）"
    return {
        "rule": rule_name,
        **r,
        "verdict": verdict,
    }
