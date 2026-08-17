# -*- coding: utf-8 -*-
"""鹿鼎公微博全量归档（wb_archive.py——2026-08-17 正式档上线后）

一次性全量拉取（甲方充值 23000 Credits）：
  ① 全部历史微博（7109 条——翻页 count=100）→ wb_statuses.jsonl（幂等）
  ② 他收到的评论 → wb_comments.jsonl
  ③ 原创微博图片（含月末实盘 PS 图）→ data/wb_pics/（二期视觉读）

用法：
  python -m tools.strategy_engine.wb_archive all     # 全量（预计 3-5 分钟）
  python -m tools.strategy_engine.wb_archive pics    # 只补图片下载
  python -m tools.strategy_engine.wb_archive status  # 归档进度
"""

from __future__ import annotations

import json
import os
import sys
import time

import requests

from tools.strategy_engine.wb_track import LUDING_UID, STATUSES_FILE, _run_cli

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
COMMENTS_FILE = os.path.join(DATA_DIR, "wb_comments.jsonl")
PICS_DIR = os.path.join(DATA_DIR, "wb_pics")

PAGE_SIZE = 20  # 接口实际上限（help 虚标 100——实测 25 超限 COUNT_EXCEEDS_MAX）


def _append_unique(path: str, rec: dict, key_field: str) -> bool:
    """按 key 去重追加——返回是否新增"""
    seen = set()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        seen.add(json.loads(line)[key_field])
                    except (ValueError, KeyError):
                        continue
        except OSError:
            pass
    if str(rec.get(key_field, "")) in seen:
        return False
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def fetch_all(max_pages: int = 400, only_original: bool = True) -> dict:
    """翻页拉历史微博——幂等

    2026-08-17 预算策略（甲方拍板 X）：只拉原创（feature=1——转发=舆情
    低价值）——原创 39% ≈ 2800 条——8.4kC vs 全量 21.4kC
    """
    got = new = 0
    for page in range(1, max_pages + 1):
        args = [
            "statuses",
            "user_timeline/other",
            "--uid",
            str(LUDING_UID),
            "--page",
            str(page),
            "--count",
            str(PAGE_SIZE),
        ]
        if only_original:
            args += ["--feature", "1"]  # 1=原创（不含转发）
        d = _run_cli(args)
        statuses = (d or {}).get("statuses") or []
        if not statuses:
            break  # 拉完
        for st in statuses:
            sid = str(st.get("id", ""))
            text = (st.get("text") or "").replace("\n", " ").strip()
            rt = st.get("retweeted_status") or {}
            pics = st.get("pic_ids") or []
            rec = {
                "id": sid,
                "ts": st.get("created_at", ""),
                "text": text[:500],
                "retweeted": bool(rt),
                "retweet_text": ((rt.get("text") or "")[:300] if rt else ""),
                "pics": pics[:9],  # 最多 9 图
                "reposts": st.get("reposts_count"),
                "comments": st.get("comments_count"),
                "attitudes": st.get("attitudes_count"),
                "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            got += 1
            if _append_unique(STATUSES_FILE, rec, "id"):
                new += 1
        if page % 10 == 0:
            print(f"  页 {page}：累计 {got} 条（新增 {new}）")
        time.sleep(1.0)  # 节流（防限流）
    return {"pages": page, "got": got, "new": new}


def fetch_comments(max_pages: int = 50, max_total: int = 1000) -> dict:
    """他收到的评论——分页——预算限制（2026-08-17：3C/条——限 1000 条=3kC）"""
    got = new = 0
    for page in range(1, max_pages + 1):
        if got >= max_total:
            break  # 预算上限（防止评论区上万条烧爆）
        d = _run_cli(
            ["comments", "to_me/other", "--uid", str(LUDING_UID), "--page", str(page)]
        )
        comments = (d or {}).get("comments") or []
        if not comments:
            break
        for c in comments:
            cid = str(c.get("id", ""))
            rec = {
                "id": cid,
                "ts": c.get("created_at", ""),
                "user": ((c.get("user") or {}).get("screen_name") or ""),
                "text": (c.get("text") or "")[:300],
                "status_id": str(((c.get("status") or {}).get("id") or "")),
                "fetched_at": time.strftime("%Y-%m-%d %H:%M"),
            }
            got += 1
            if _append_unique(COMMENTS_FILE, rec, "id"):
                new += 1
        time.sleep(1.0)
    return {"pages": page, "got": got, "new": new}


def download_pics() -> dict:
    """原创微博图片下载（含月末实盘 PS 图——二期视觉读）"""
    try:
        os.makedirs(PICS_DIR, exist_ok=True)
    except OSError:
        pass
    # wb_statuses.jsonl 逐行读
    statuses = []
    if os.path.exists(STATUSES_FILE):
        try:
            with open(STATUSES_FILE, encoding="utf-8") as f:
                for line in f:
                    try:
                        statuses.append(json.loads(line))
                    except ValueError:
                        continue
        except OSError:
            pass
    dl = skip = 0
    for st in statuses:
        if st.get("retweeted"):
            continue  # 只下原创（转发图信息量低）
        for i, pid in enumerate(st.get("pics") or []):
            fname = os.path.join(PICS_DIR, f"{st['id']}_{i}.jpg")
            if os.path.exists(fname):
                skip += 1
                continue
            url = f"https://wx1.sinaimg.cn/large/{pid}.jpg"
            try:
                r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://weibo.com/"})
                if r.status_code == 200 and len(r.content) > 1000:
                    with open(fname, "wb") as f:
                        f.write(r.content)
                    dl += 1
                else:
                    skip += 1
            except Exception:
                skip += 1  # 单图下载失败跳过（红线③容错——不中断归档）
            time.sleep(0.3)
    return {"downloaded": dl, "skipped": skip}


def archive_status() -> str:
    try:
        n_wb = (
            sum(1 for _ in open(STATUSES_FILE, encoding="utf-8"))
            if os.path.exists(STATUSES_FILE)
            else 0
        )
    except OSError:
        n_wb = 0
    try:
        n_cm = (
            sum(1 for _ in open(COMMENTS_FILE, encoding="utf-8"))
            if os.path.exists(COMMENTS_FILE)
            else 0
        )
    except OSError:
        n_cm = 0
    try:
        n_pics = sum(1 for _ in os.listdir(PICS_DIR)) if os.path.isdir(PICS_DIR) else 0
    except OSError:
        n_pics = 0
    return f"微博 {n_wb}/7109 | 评论 {n_cm} | 图片 {n_pics}"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "all":
        print("① 微博全量翻页…")
        print(fetch_all())
        print("② 评论拉取…")
        print(fetch_comments())
        print("③ 图片下载…")
        print(download_pics())
    elif cmd == "pics":
        print(download_pics())
    else:
        print(archive_status())


if __name__ == "__main__":
    main()
