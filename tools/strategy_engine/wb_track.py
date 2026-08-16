# -*- coding: utf-8 -*-
"""微博大V跟踪（wb_track.py——2026-08-16 超级鹿鼎公微博自动抓取）

定案回顾（SYNC 08-13/08-14）：微博要抓——但范围只有超级鹿鼎公
（书里唯一微博大V——"抄微博超级鹿鼎公的作业"）——其余 71 位在雪球。
路径：微博官方 weibo-cli（2026-06-22 上线——OAuth——体验包验证中）。

用法：
  python -m tools.strategy_engine.wb_track fetch   # 抓最新微博 → data/wb_statuses.jsonl
  python -m tools.strategy_engine.wb_track digest  # 汇总（今日/本周新增）

合规：官方开放平台 API（OAuth 授权——用户已授权）。跟踪≠跟随（Q3）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
STATUSES_FILE = os.path.join(DATA_DIR, "wb_statuses.jsonl")

# 超级鹿鼎公（书：挖地瓜的超级鹿鼎公——微博 uid 实测 2026-08-16）
LUDING_UID = 3962719063


def _load_token() -> str:
    """WEIBO_CLI_TOKEN：环境变量优先 → .env 兜底（定时任务场景——不依赖 shell）"""
    t = os.environ.get("WEIBO_CLI_TOKEN", "")
    if t:
        return t
    env_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"
    )
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("WEIBO_CLI_TOKEN=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


TOKEN = _load_token()


def _run_cli(args: list[str]) -> dict | None:
    """调 weibo-cli——失败返回 None（不抛——红线③容错）"""
    env = dict(os.environ)
    if TOKEN:
        env["WEIBO_CLI_TOKEN"] = TOKEN
    # Windows 下 npm 全局安装是 .cmd shim——subprocess 需显式后缀（08-16 实测）
    cli = "weibo-cli.cmd" if os.name == "nt" else "weibo-cli"
    try:
        r = subprocess.run(
            [cli, *args, "--output", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )
        if r.returncode != 0:
            # 体验包配额耗尽（免费档总配额有限——08-16 实测 TRIAL_API_QUOTA_EXCEEDED）
            if "QUOTA" in r.stderr.upper():
                print("⚠️ 微博体验包配额耗尽——今日额度已用完（免费档总配额有限——明日自动恢复或考虑正式档）")
            return None
        return json.loads(r.stdout)
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


def fetch(page: int = 1, count: int = 20) -> int:
    """抓超级鹿鼎公微博 → wb_statuses.jsonl（幂等——按 id 去重）

    返回新增条数。保留原文（text 字段）——思路提取后续做。
    注意：体验包配额有限——每日 1 次（count=20 已够——鹿鼎公日更几条）
    """
    d = _run_cli(
        ["statuses", "user_timeline/other", "--uid", str(LUDING_UID), "--page", str(page), "--count", str(count)]
    )
    if not d:
        print("⚠️ 微博抓取失败（token 失效/接口限流/体验包过期？）")
        return 0
    statuses = d.get("statuses") or []
    # 已见 id 集合
    seen: set[str] = set()
    if os.path.exists(STATUSES_FILE):
        try:
            with open(STATUSES_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        seen.add(json.loads(line)["id"])
                    except (ValueError, KeyError):
                        continue
        except OSError:
            pass
    new = 0
    try:
        f_out = open(STATUSES_FILE, "a", encoding="utf-8")
    except OSError:
        print("⚠️ 微博记录文件写入失败")
        return 0
    with f_out:
        for st in statuses:
            sid = str(st.get("id", ""))
            if sid in seen:
                continue
            created = st.get("created_at", "")
            # 转存核心字段（正文/时间/转发/点赞——长文截断 500 字）
            text = (st.get("text") or "").replace("\n", " ").strip()
            retweet = ""
            rt = st.get("retweeted_status") or {}
            if rt:
                retweet = (rt.get("text") or "")[:300]
            rec = {
                "id": sid,
                "ts": created,
                "text": text[:500],
                "retweeted": bool(rt),
                "retweet_text": retweet[:300],
                "reposts": st.get("reposts_count"),
                "comments": st.get("comments_count"),
                "attitudes": st.get("attitudes_count"),
                "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            new += 1
    print(f"✅ 微博抓取: 新增 {new} 条（已存 {len(seen) + new} 条累计）")
    return new


def digest() -> str:
    """周度/当日汇总——本周新增微博（供周报/晨报引用）"""
    rows = []
    if os.path.exists(STATUSES_FILE):
        try:
            with open(STATUSES_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        rows.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            pass
    if not rows:
        return "微博跟踪：暂无数据（首次抓取后可见）"
    # 本周（ISO 周相同）
    this_week = [r for r in rows if r.get("fetched_at", "")[:10] >= time.strftime("%Y-%m-%d", time.localtime(time.time() - 7 * 86400))]
    n_repost = sum(1 for r in this_week if r.get("retweeted"))
    lines = [
        f"📣 超级鹿鼎公微博（本周 {len(this_week)} 条——转发 {n_repost}）",
    ]
    for r in this_week[-3:]:
        txt = r.get("retweet_text") or r.get("text") or ""
        lines.append(f"  · {r.get('ts', '')[:16]} {txt[:60]}")
    return "\n".join(lines)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "digest"
    if cmd == "fetch":
        fetch()
    else:
        print(digest())


if __name__ == "__main__":
    main()
