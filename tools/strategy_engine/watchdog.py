# -*- coding: utf-8 -*-
"""观复定时任务看门狗（watchdog.py——2026-08-17 甲方 Q11 应询）

独立于日报/周报的监控任务——解决 A5 自指环缺陷（日报死了没人报日报死）：
- 每 30 分钟由独立定时任务触发（GFWatchdog）
- 检查 4 个任务 LastRunTime——超时（任务应跑未跑）→ 微信告警
- 与 notify_gf 解耦：看门狗自己失败不影响业务推送（反之亦然）

任务表（应跑时点——工作日）：
- GFBrief   17:00 收盘日报（周五跳过——周报覆盖）
- GFXQTrack 16:00 雪球大V 跟踪
- GFWBTrack 16:05 微博鹿鼎公
- GFWeekly  周五 15:30 周报

判定规则：距"应跑时点"超过 TOLERANCE 小时仍未跑 → 告警。
非应跑日（周末/盘前）不告警。
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

# 任务 → (应跑时点 [时,分], 容忍小时, 周五例外)
TASKS = {
    "GFBrief": (17, 0, 3, False),   # 17:00 日报——容忍 3h（含数据拉取+网络重试）
    "GFXQTrack": (16, 0, 3, False), # 16:00 雪球——容忍 3h
    "GFWBTrack": (16, 5, 3, False), # 16:05 微博——容忍 3h
    "GFWeekly": (15, 30, 6, True),  # 周五 15:30 周报——容忍 6h——周五例外（only 周五应跑）
}

_POWERSHELL_SCRIPT = (
    "$i = Get-ScheduledTaskInfo -TaskName '{name}'; "
    "Write-Output ($i.LastRunTime.ToString('yyyy-MM-dd HH:mm:ss') + '|' + $i.LastTaskResult)"
)

# 任务名白名单（防注入——name 只能来自 TASKS 键）
_ALLOWED = set(TASKS.keys())


def _last_run(name: str) -> tuple[datetime.datetime | None, int]:
    """查任务上次运行时间+结果（LastRunTime/LastTaskResult——任务计划服务权威数据）"""
    if name not in _ALLOWED:
        return None, -2  # 非白名单任务名——拒绝
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", _POWERSHELL_SCRIPT.format(name=name)],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        out = (r.stdout or "").strip().split("|")
        if len(out) == 2 and out[0] and out[0] != "12/30/1899 00:00:00":
            # PowerShell 区域设置可能是 MM/dd/yyyy——统一按多种格式解析
            for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    return datetime.datetime.strptime(out[0].strip(), fmt), int(out[1] or 0)
                except ValueError:
                    continue
        return None, 0  # 从未运行
    except Exception:
        return None, -1  # 查询失败


def _should_run_today(name: str) -> bool:
    """今天是否应跑该任务（GFWeekly 仅周五——其余工作日）"""
    weekday = datetime.date.today().weekday()
    if name == "GFWeekly":
        return weekday == 4  # 周五
    if weekday == 4:
        return name != "GFWeekly" and not name == "GFBrief"  # 周五日报跳过（周报覆盖）
    return weekday < 5  # 周一~周四（含周五非周报任务）


def check() -> list[str]:
    """检查全部任务——返回告警清单（空=健康）"""
    now = datetime.datetime.now()
    alerts = []
    for name, (hh, mm, tol_h, friday_skip) in TASKS.items():
        if not _should_run_today(name):
            continue
        due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        last, result = _last_run(name)
        if last is None:
            # 从未运行——若已过应跑时点即告警
            if now > due:
                alerts.append(f"⚠️ {name} 从未运行——应于今日 {hh:02d}:{mm:02d} 触发——请查任务计划")
            continue
        # 上次运行是否覆盖本次应跑时点（容忍窗口内）
        window_start = due - datetime.timedelta(hours=tol_h)
        if last < window_start:
            alerts.append(
                f"⚠️ {name} 可能漏跑——上次运行 {last:%m-%d %H:%M}（应在 {hh:02d}:{mm:02d} 后 {tol_h}h 内）"
                f"——结果码 {result}"
            )
        elif result != 0 and result != 267011:
            # 267011 = 任务从未运行（计划任务默认）——其余非 0 需注意
            alerts.append(f"⚠️ {name} 上次运行结果异常——结果码 {result}（{last:%m-%d %H:%M}）")
    return alerts


def main() -> int:
    alerts = check()
    if not alerts:
        print(f"[watchdog] {datetime.datetime.now():%H:%M} 全部任务健康 ✅")
        return 0
    msg = "\n".join(alerts)
    print(f"[watchdog] {datetime.datetime.now():%H:%M} 告警 {len(alerts)} 条:\n{msg}")
    # 微信告警（独立推送——不走 notify_gf 的日报节流——看门狗独立配额）
    try:
        from src.notify import push_wechat

        if push_wechat:
            ok = push_wechat(f"🛡️ 观复看门狗\n\n{msg}")
            print(f"[watchdog] 微信告警推送: {'✅' if ok else '❌'}")
    except Exception as e:
        print(f"[watchdog] 微信推送失败（不阻塞）: {str(e)[:80]}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
