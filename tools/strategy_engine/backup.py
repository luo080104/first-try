# -*- coding: utf-8 -*-
"""观复关键数据每日备份（backup.py——2026-08-16 A1 完善项）

虚拟盘数据（净值/事件/信号账本）无自动备份——一次误删/磁盘故障=判定周期
白跑。每日快照 → data/backup/YYYYMMDD/，保留 30 天（自动清理过期）。

挂载点：晨报入口 push_brief（每日 9:00 定时任务）——幂等、失败不阻塞。
手动：python -m tools.strategy_engine.backup
"""

from __future__ import annotations

import os
import shutil
import time

# 观复关键运行数据（data/ 下）——新增关键文件需加进此清单
BACKUP_FILES = [
    "portfolio.json",  # 虚拟盘持仓/现金/净值曲线
    "portfolio_events.jsonl",  # 事件流（买卖/原因——行为画像源）
    "push_state.json",  # 推送节流状态（每日 3 条上限）
    "pending_trades.json",  # 待确认交易队列
    "price_watch.json",  # 盯价清单
    "valuation_cache.db",  # 估值缓存（PE/PB 历史积累）
]

KEEP_DAYS = 30

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
BACKUP_DIR = os.path.join(DATA_DIR, "backup")


def daily_backup(keep_days: int = KEEP_DAYS) -> str:
    """快照关键文件 → backup/YYYYMMDD/；清理超过 keep_days 的旧备份

    返回备份目录路径（失败返回 ""——不抛异常——红线③容错）
    """
    try:
        dst = os.path.join(BACKUP_DIR, time.strftime("%Y%m%d"))
        os.makedirs(dst, exist_ok=True)
        n = 0
        for f in BACKUP_FILES:
            src = os.path.join(DATA_DIR, f)
            if os.path.exists(src):
                shutil.copy2(src, os.path.join(dst, f))
                n += 1
        # 清理过期备份（按目录 mtime——同一天重复备份幂等）
        cutoff = time.time() - keep_days * 86400
        for d in os.listdir(BACKUP_DIR):
            dp = os.path.join(BACKUP_DIR, d)
            if os.path.isdir(dp) and os.path.getmtime(dp) < cutoff:
                shutil.rmtree(dp, ignore_errors=True)
        return dst if n else ""
    except OSError:
        return ""


if __name__ == "__main__":
    p = daily_backup()
    print(f"✅ 备份完成: {p}" if p else "⚠️ 备份失败（无文件被复制）")
