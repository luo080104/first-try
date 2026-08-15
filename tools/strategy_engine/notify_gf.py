# -*- coding: utf-8 -*-
"""观复推送层（notify_gf.py——P3 前置——第一版验收：虚拟盘信号推送）

复用 Go购 src/notify.py（Server酱/PushPlus/企业微信 webhook 多渠道——任一成功即 True）
- 晨报：build_brief() → 推送（9:00 定时——调度由外部 vbs/任务计划）
- 信号：确认队列有信号 → 推送
- 低频合并：一天最多 3 条——多的并晚报（定案——M3 阶段实现细节）
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import morning_brief as mb

try:
    from src.notify import push_wechat
except ImportError:
    push_wechat = None  # type: ignore[assignment]


def push_brief() -> bool:
    """晨报推送（9:00——大盘状态+估值百分位+策略信号——书体系）"""
    if push_wechat is None:
        return False
    text = mb.build_brief()
    return push_wechat(f"📊 观复晨报\n\n{text}")


def push_signal(signal_text: str) -> bool:
    """信号推送（达标信号 → 待确认——半自动红线：AI 提示带理由）"""
    if push_wechat is None:
        return False
    return push_wechat(f"🎯 观复信号\n\n{signal_text}")


if __name__ == "__main__":
    ok = push_brief()
    print(f"晨报推送: {'✅' if ok else '❌（未配置推送渠道或失败）'}")
