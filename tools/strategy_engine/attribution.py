# -*- coding: utf-8 -*-
"""Beta/Alpha 归因拆解（attribution.py——2026-08-15 整改①——防"押对板块"运气误判）

背景：虚拟盘 3 持仓全金融板块——4 周跑赢沪深300 可能是市场风格（Beta）贡献
而非策略选择（Alpha）贡献——归因不分离 → 策略被错误验证 → 提前进真钱（红线）。
本模块：组合日收益序列 → 市场 Beta（沪深300）+ 残差 Alpha——
gate_check 通过判定加"Alpha 必须为正"条件。

方法：单因子线性回归（纯 Python 最小二乘——不引入新依赖——红线⑥）
  r_port = beta × r_market + alpha + ε
  beta = Cov(r_port, r_market) / Var(r_market)
  alpha = E[r_port] - beta × E[r_market]（日频——年化×252）

数据对齐：组合净值日序列 vs 沪深300 日线（baostock "d" 频率）——按日期对齐——
缺失日跳过（数据失误不静默：对齐点数不足返回缺口标注——红线⑤）
"""

from __future__ import annotations

from typing import Any

# 年化系数（日频收益 → 年化——A 股 ~250 交易日）
_DAYS_PER_YEAR = 250


def _ols_beta_alpha(
    port_rets: list[float], market_rets: list[float]
) -> dict[str, float] | None:
    """单因子 OLS：beta/alpha（纯 Python——最小二乘闭式解）

    port_rets/market_rets: 等长日收益序列（小数——0.01=1%）
    返回 {beta, alpha_daily, alpha_annual, r2}——数据不足返回 None
    """
    n = len(port_rets)
    if n < 10 or n != len(market_rets):
        return None
    m_mean = sum(market_rets) / n
    p_mean = sum(port_rets) / n
    # beta = Cov / Var
    cov = sum((m - m_mean) * (p - p_mean) for m, p in zip(market_rets, port_rets))
    var_m = sum((m - m_mean) ** 2 for m in market_rets)
    if var_m < 1e-12:
        return None  # 市场无波动——无法估计
    beta = cov / var_m
    alpha_daily = p_mean - beta * m_mean
    # R²（拟合优度）
    ss_tot = sum((p - p_mean) ** 2 for p in port_rets)
    if ss_tot < 1e-12:
        r2 = 0.0
    else:
        resid = [p - (alpha_daily + beta * m) for p, m in zip(port_rets, market_rets)]
        ss_res = sum(r * r for r in resid)
        r2 = max(0.0, min(1.0, 1 - ss_res / ss_tot))
    return {
        "beta": round(beta, 3),
        "alpha_daily": round(alpha_daily, 6),
        "alpha_annual": round(alpha_daily * _DAYS_PER_YEAR * 100, 2),  # %
        "r2": round(r2, 3),
    }


def attribution(
    equity_curve: list[dict[str, Any]],
    bench_daily: list[dict[str, Any]],
) -> dict[str, Any]:
    """组合归因拆解（整改①入口）

    equity_curve: [{date, total}]——组合净值日序列（升序）
    bench_daily: [{date, close}]——沪深300 日线（升序——baostock "d"）
    返回 {beta_market, alpha_annual, alpha_positive, n_points, note}
    - n_points < 10 → 数据不足（note 标注——不判定——红线⑤不静默）
    - 对齐失败（无重叠日期）→ 显式缺口标注
    """
    if len(equity_curve) < 11 or not bench_daily:
        return {
            "beta_market": None,
            "alpha_annual": None,
            "alpha_positive": None,
            "n_points": 0,
            "note": "净值/基准数据不足（需 ≥10 个对齐日点）——归因跳过",
        }
    bench_map = {b["date"][:10]: b["close"] for b in bench_daily}
    # 对齐：取净值序列与基准重叠的日期——逐日收益
    port_rets: list[float] = []
    market_rets: list[float] = []
    prev_total = None
    prev_date = None
    for pt in equity_curve:
        d = (pt.get("date") or "")[:10]
        if d not in bench_map:
            continue  # 基准无此日（非交易日/缺口）——跳过
        bc = bench_map[d]
        if bc is None or bc <= 0:
            continue
        t = pt.get("total")
        if t is None or t <= 0:
            continue
        if prev_total is not None and prev_date is not None:
            # 组合日收益（净值差分）——基准前日存在才可算差
            prev_bc = bench_map.get(prev_date)
            if prev_bc:
                port_rets.append((t - prev_total) / prev_total)
                market_rets.append((bc - prev_bc) / prev_bc)
        prev_total, prev_date = t, d
    if len(port_rets) < 10:
        return {
            "beta_market": None,
            "alpha_annual": None,
            "alpha_positive": None,
            "n_points": len(port_rets),
            "note": f"对齐后仅 {len(port_rets)} 个日点（需 ≥10）——归因跳过（数据缺口显式标注——红线⑤）",
        }
    ols = _ols_beta_alpha(port_rets, market_rets)
    if ols is None:
        return {
            "beta_market": None,
            "alpha_annual": None,
            "alpha_positive": None,
            "n_points": len(port_rets),
            "note": "OLS 估计失败（市场无波动）——归因跳过",
        }
    return {
        "beta_market": ols["beta"],
        "alpha_annual": ols["alpha_annual"],
        "alpha_positive": ols["alpha_annual"] > 0,
        "n_points": len(port_rets),
        "r2": ols["r2"],
        "note": (
            f"Beta={ols['beta']} 年化Alpha={ols['alpha_annual']}% "
            f"R²={ols['r2']}（{len(port_rets)} 日点）"
        ),
    }
