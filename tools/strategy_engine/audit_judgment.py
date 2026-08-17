# -*- coding: utf-8 -*-
"""判定审计脚本（audit_judgment.py——甲方应询书 9/5 交付，提前至 8/17 深夜）

甲方要求："判定审计脚本（输入净值+规则版本→结论，可复跑）"

用途：
1. 审计判定链数据完整性——净值点三态分布（real/fallback/missing 各多少）
2. 审计规则版本——本次判定用的打分 schema/门槛/信号接线
3. 输出判定结论（与 gate_check.check() 一致）——**可复跑**（固定输入→固定输出）
4. 生成审计报告（JSON + 人读文本）——9/12 判定时作为独立证据

用法：
    python -m tools.strategy_engine.audit_judgment          # 完整审计
    python -m tools.strategy_engine.audit_judgment --json   # 仅 JSON 输出
    python -m tools.strategy_engine.audit_judgment --history # 审计历史净值点（不跑判定）
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import gate_check as gc
from tools.strategy_engine import portfolio as pf
from tools.strategy_engine import strategy_score as ss


def audit_equity_curve() -> dict:
    """净值序列三态审计（甲方 Q6：判定只统计 real 点——失真点占比是判定可信度指标）"""
    p = pf.Portfolio()
    curve = p.equity_series()
    states = {"real": 0, "fallback": 0, "missing": 0, "无标记(旧数据)": 0}
    for pt in curve:
        st = pt.get("data_state")
        if st is None:
            states["无标记(旧数据)"] += 1
        else:
            states[st] = states.get(st, 0) + 1
    real_cnt = states.get("real", 0)
    total = len(curve)
    return {
        "总净值点": total,
        "三态分布": states,
        "real 占比": round(real_cnt / total * 100, 1) if total else 0,
        "判定可用性": (
            "✅ 可判定（real 占比高）"
            if total and real_cnt / total >= 0.8
            else "⚠️ 失真点占比高——判定窗口应从数据可信首日起算（甲方 Q6 定案）"
        ),
    }


def audit_rule_version() -> dict:
    """规则版本审计（甲方 Q7：决策时点规则可追溯）"""
    from tools.strategy_engine import signals as sg

    return {
        "打分 schema": "v2.1-120制（价值40+估值30+技术20+票源10+行业20）",
        "门槛（120 制）": ss.THRESHOLD_MAP,
        "已接线信号": sorted(s["id"] for s in sg.wiring_status() if s["wired"] == "True"),
        "未接线信号": sorted(s["id"] for s in sg.wiring_status() if s["wired"] == "False"),
        "判定闸门": [
            "连续 4 周跑赢沪深300",
            "累计超额 ≥10%（F5b）",
            "Alpha 非负（显式 False 才阻断——盲审修复）",
            "二项符号检验 p<0.05（甲方 Q4）",
            "净值点只统计 real 态（甲方 Q6）",
            "90 天=观察期不自动通过（F5b）",
        ],
        "审计时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def run_audit(include_judgment: bool = True) -> dict:
    """完整审计——固定输入（当前账本+规则版本）→ 固定输出（可复跑）"""
    report = {
        "审计类型": "判定链完整性审计",
        "审计时间": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "账本": pf.PORTFOLIO_FILE,
        "净值审计": audit_equity_curve(),
        "规则版本": audit_rule_version(),
    }
    if include_judgment:
        try:
            j = gc.check()
            report["判定结论"] = {
                "passed": j.get("passed"),
                "reason": j.get("reason"),
                "days": j.get("days"),
                "weeks_beat": j.get("weeks_beat"),
                "alpha_positive": j.get("alpha_positive"),
                "significance": j.get("significance"),
            }
        except Exception as e:
            report["判定结论"] = {"error": str(e)[:200]}
    # 落盘（data/audit/ 目录——可复跑对比）——失败不阻塞审计输出（容错红线）
    out_dir = os.path.join(os.path.dirname(pf.PORTFOLIO_FILE), "audit")
    out_path = ""
    try:
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(
            out_dir, f"audit_{datetime.datetime.now():%Y%m%d_%H%M%S}.json"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        report["审计文件"] = out_path
    except OSError as e:
        report["审计文件"] = f"落盘失败: {str(e)[:80]}（审计结果仍返回）"
    return report


def _fmt(report: dict) -> str:
    """人读格式"""
    lines = []
    lines.append("=" * 60)
    lines.append(f"📋 观复判定链审计  {report['审计时间']}")
    lines.append("=" * 60)
    eq = report["净值审计"]
    lines.append(f"\n【净值序列】{eq['总净值点']} 点——real 占比 {eq['real 占比']}%")
    for k, v in eq["三态分布"].items():
        lines.append(f"  {k}: {v}")
    lines.append(f"  可用性: {eq['判定可用性']}")
    rv = report["规则版本"]
    lines.append(f"\n【规则版本】schema={rv['打分 schema']}")
    lines.append(f"  门槛: {rv['门槛（120 制）']}")
    lines.append(f"  已接线信号: {rv['已接线信号']}")
    if rv["未接线信号"]:
        lines.append(f"  ⚠️ 未接线: {rv['未接线信号']}")
    lines.append("  判定闸门:")
    for g in rv["判定闸门"]:
        lines.append(f"    - {g}")
    if "判定结论" in report:
        j = report["判定结论"]
        lines.append(f"\n【判定结论】passed={j.get('passed')}")
        lines.append(f"  {j.get('reason', '')}")
        if j.get("significance"):
            s = j["significance"]
            lines.append(
                f"  显著性: n={s.get('n_weeks')} 胜率 {s.get('win_rate')}% p={s.get('p_binom')}"
            )
    lines.append(f"\n审计文件: {report.get('审计文件', '')}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="观复判定链审计（可复跑）")
    ap.add_argument("--json", action="store_true", help="仅 JSON 输出")
    ap.add_argument("--history", action="store_true", help="只审计净值历史（不跑判定）")
    args = ap.parse_args()
    report = run_audit(include_judgment=not args.history)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_fmt(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
