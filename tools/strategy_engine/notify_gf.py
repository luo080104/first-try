# -*- coding: utf-8 -*-
"""观复推送层（notify_gf.py——P3 前置——第一版验收：虚拟盘信号推送）

复用 Go购 src/notify.py（Server酱/PushPlus/企业微信 webhook 多渠道——任一成功即 True）
- 晨报：build_brief() → 推送（9:00 定时——调度由外部 vbs/任务计划）
- 信号：确认队列有信号 → 推送
- 低频合并：一天最多 3 条——多的并晚报（定案——M3 阶段实现细节）
"""

from __future__ import annotations

import datetime
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from tools.strategy_engine import morning_brief as mb

try:
    from src.notify import push_wechat
except ImportError:
    push_wechat = None  # type: ignore[assignment]

# 低频合并（定案：一天最多 3 条——多的并晚报）——本地状态文件记录当日已推条数
_STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "push_state.json"
)
DAILY_CAP = 3

# 原子领取锁（跨进程互斥——防并发竞态绕过 cap——8/17 count=24 事故根因）
_LOCK_PATH = _STATE_PATH + ".lock"
_LOCK_TTL = 60  # 秒——进程崩溃残留锁自动过期


def _claim_slot() -> bool:
    """原子领取当日推送名额（检查+计数一体——跨进程互斥）

    锁文件 O_EXCL 保证同一时刻只有一个进程能通过检查；
    崩溃残留锁超过 TTL 视为过期可抢。领取成功即计数（推送失败也占名额
    ——低频合并语义：少推比多推安全）。
    """
    fd = None
    try:
        try:
            fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                _age = time.time() - os.path.getmtime(_LOCK_PATH)
            except OSError:
                return False
            if _age <= _LOCK_TTL:
                return False  # 锁被其他进程持有
            try:
                os.remove(_LOCK_PATH)
            except OSError:
                return False
            try:
                fd = os.open(_LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except OSError:
                return False
        if _today_count() >= DAILY_CAP:
            return False
        _bump_count()
        return True
    finally:
        if fd is not None:
            os.close(fd)
            try:
                os.remove(_LOCK_PATH)
            except OSError:
                pass


def _today_count() -> int:
    """今日已推送条数（状态文件——跨进程共享）"""
    try:
        import json

        with open(_STATE_PATH, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("date") == datetime.date.today().isoformat():
            return int(d.get("count", 0))
    except (OSError, ValueError):
        pass
    return 0


def _bump_count() -> None:
    """今日计数 +1（读当前值再写——跨进程安全：先读后写）"""
    try:
        import json

        new_count = _today_count() + 1
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(
                {"date": datetime.date.today().isoformat(), "count": new_count},
                f,
            )
    except OSError:
        pass  # 状态写失败不阻塞推送


def _throttled(text: str) -> bool:
    """低频合并：当日已满 3 条 → 拒绝（并入晚报——M3 完整实现）"""
    if _today_count() >= DAILY_CAP:
        print(f"[notify_gf] ⏸ 今日已达 {DAILY_CAP} 条上限——本条并入晚报")
        return False
    return True


def push_brief() -> bool:
    """收盘日报推送（2026-08-17 改：9:00 盘前晨报 → 工作日 17:00 收盘总结）

    变更（甲方拍板 A）：盘前发昨日旧数据无意义——收盘后发当日总结——
    净值记录同步迁移（收盘后记当日真实净值——gate_check 语义修正）
    周五跳过推送（周报 15:30 已覆盖——净值照记）
    """
    import datetime as _dt

    # 先记净值（幂等——同一日覆盖——gate_check 判定依赖此序列）
    try:
        from tools.strategy_engine.portfolio import Portfolio

        Portfolio().record_equity()
    except Exception:
        pass  # 净值记录失败不阻塞日报（红线③容错）
    # 每日备份（A1 完善——2026-08-16——数据保险——失败不阻塞）
    try:
        from tools.strategy_engine import backup

        backup.daily_backup()
    except Exception:
        pass
    # 周五跳过推送（周报 15:30 覆盖——净值已记）
    if _dt.date.today().weekday() == 4:
        print("[notify_gf] 周五——日报跳过（周报 15:30 已覆盖）")
        return True
    if push_wechat is None:
        return False
    text = mb.build_brief()
    if not _claim_slot():
        return False
    ok = push_wechat(f"📊 观复日报 · 收盘总结\n\n{text}")
    return ok


def push_with_pic(text: str, pic_data_url: str | None = None) -> bool:
    """推送（带图片——Server酱 pics 参数——2026-08-15 周报图用）

    pic_data_url: data:image/png;base64,...——None 时降级纯文本
    Server酱³ 实测支持 pics=base64（2026-08-15 验证 code=0）——无需图床
    """
    if push_wechat is None:
        return False
    if not pic_data_url:
        # 无图 → 普通文本推送
        if not _claim_slot():
            return False
        return push_wechat(text)
    if not _claim_slot():
        return False
    try:
        import urllib.parse
        import urllib.request

        env = {}
        _env_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"
        )
        try:
            for _line in open(_env_path, encoding="utf-8"):
                _line = _line.strip()
                if "=" in _line and not _line.startswith("#"):
                    k, v = _line.split("=", 1)
                    env[k.strip()] = v.strip()
        except OSError:
            pass
        sendkey = os.environ.get("SERVERCHAN_SENDKEY", "") or env.get(
            "SERVERCHAN_SENDKEY", ""
        )
        if not sendkey:
            # 无 Server酱 → 纯文本降级
            return push_wechat(text)
        body = urllib.parse.urlencode(
            {"title": "📊 观复周报", "desp": text, "pics": pic_data_url}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"https://sctapi.ftqq.com/{sendkey}.send", data=body
        )
        resp = json.loads(
            urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        )
        ok = resp.get("code") == 0
        if not ok:
            print(f"[notify_gf] Server酱图文失败: {resp.get('message', resp)}")
        return ok
    except Exception as e:
        print(f"[notify_gf] 图文推送异常: {str(e)[:60]}")
        return False


def push_signal(signal_text: str) -> bool:
    """信号推送（达标信号 → 待确认——半自动红线：AI 提示带理由）"""
    if push_wechat is None:
        return False
    if not _claim_slot():
        return False
    return push_wechat(f"🎯 观复信号\n\n{signal_text}")


if __name__ == "__main__":
    ok = push_brief()
    print(f"晨报推送: {'✅' if ok else '❌（未配置推送渠道或失败）'}")
