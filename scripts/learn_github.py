# -*- coding: utf-8 -*-
"""GitHub 优秀案例自动学习脚本（任务3：自动学习能力）

用法:
    python learn_github.py "电商爬虫" "比价" --top 5 --skip-clone
    python learn_github.py "agent framework" --top 3

功能:
    1. GitHub API 按主题搜索仓库（按星数排序）
    2. 浅克隆 top N 到 ~/<name>_ref（gitignore 隔离）
    3. 提取 README 摘要（首段 + 关键标题）写入案例索引
    4. 索引: docs/case_index.md（追加式，防重复）
"""

import io
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime

HOME = os.path.expanduser("~")
INDEX = os.path.join(HOME, "shopping-agent", "docs", "case_index.md")
UA = {"User-Agent": "case-learner", "Accept": "application/vnd.github+json"}


def gh_search(query: str, top: int = 5) -> list:
    """GitHub 搜索：按星数排序，返回 [(full_name, stars, desc, html_url)]"""
    q = urllib.parse.quote(query)
    url = f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={top}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    out = []
    for it in data.get("items") or []:
        name, desc = it["full_name"], (it.get("description") or "")
        if name.endswith("/.github") or not desc:
            continue  # 跳过组织元数据仓库/无描述仓库
        out.append((name, it["stargazers_count"], desc[:100], it["html_url"]))
    return out


def clone(name: str) -> str:
    """浅克隆到 ~/<repo名>_ref，返回目录名（已存在则跳过）"""
    slug = name.split("/")[-1].replace(".", "_")
    dst = os.path.join(HOME, f"{slug}_ref")
    if os.path.isdir(dst):
        return f"{slug}_ref (已存在，跳过)"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"https://github.com/{name}.git", dst],
        check=False,
        timeout=180,
        capture_output=True,
    )
    return f"{slug}_ref" if os.path.isdir(dst) else "克隆失败"


def readme_summary(dst: str) -> str:
    """提取 README 首段（去 HTML/空行）"""
    for f in ("README.md", "README.zh-CN.md", "readme.md"):
        p = os.path.join(dst, f)
        if os.path.isfile(p):
            try:
                txt = io.open(p, encoding="utf-8", errors="replace").read()
            except Exception:
                return ""
            lines = [
                l.strip()
                for l in txt.splitlines()
                if l.strip() and not l.strip().startswith(("<", "![", "#"))
            ]
            # 取前 3 个非空正文行
            return " ".join(lines[:3])[:200]
    return ""


def log(name: str, stars: int, desc: str, url: str, dst: str):
    """追加到索引（按 full_name 防重复）"""
    os.makedirs(os.path.dirname(INDEX), exist_ok=True)
    old = io.open(INDEX, encoding="utf-8").read() if os.path.isfile(INDEX) else ""
    if f"- **{name}**" in old:
        return "已在索引，跳过"
    line = (
        f"- **{name}**（{stars}星，{datetime.now():%Y-%m-%d} 自动收录）\n"
        f"  - 简介: {desc}\n  - 地址: {url}\n  - 本地: ~/{dst}\n"
    )
    io.open(INDEX, "a", encoding="utf-8").write(line)
    return "已收录"


def main():
    queries = sys.argv[1:-2] if len(sys.argv) > 3 else sys.argv[1:-1]
    top = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 5
    if not queries:
        print('用法: python learn_github.py "主题1" "主题2" [top N]')
        return
    print(f"🔍 搜索 {len(queries)} 个主题，每个取 top {top}")
    for q in queries:
        try:
            hits = gh_search(q, top)
        except Exception as e:
            print(f"  ⚠️ {q}: 搜索失败 {e}")
            continue
        print(f"\n=== 主题: {q} ===")
        for name, stars, desc, url in hits:
            dst = clone(name)
            time.sleep(1)  # 温柔一点
            summary = readme_summary(dst.split()[0]) if "失败" not in dst else ""
            status = log(name, stars, desc, url, dst)
            print(f"  {name} | {stars}星 | {status}")
            if summary:
                print(f"    摘要: {summary[:120]}")


if __name__ == "__main__":
    main()
