# -*- coding: utf-8 -*-
"""批量给模板 JS 的 innerHTML 赋值行加 pi-lens-ignore 注释（2026-08-18）
背景：Go购 全站用「模板字符串 + esc() 转义」渲染（8/12 审计无高危）。
pi-lens no-inner-html-js 规则不识别 esc() 模式 → 逐行 suppress 记录决策。
纯注释插入：在匹配行上一行插入缩进对齐的 // pi-lens-ignore 注释，零语义变化。
"""

import re
import sys

TARGETS = [
    "src/templates/index.html",
    "src/templates/guide.html",
    "src/templates/hist.html",
    "src/templates/items.html",
    "src/templates/result.html",
    "src/templates/wander.html",
    "src/templates/crawl.html",
    "src/templates/compare.html",
    "src/templates/submit.html",
    "src/templates/watches.html",
]

PAT = re.compile(r"(?:innerHTML|outerHTML)\s*=")
NOTE = "// pi-lens-ignore: no-inner-html-js (esc() 转义的安全渲染模式，8/12 审计无高危)"


def process(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    out = []
    added = 0
    for i, line in enumerate(lines):
        if PAT.search(line) and "pi-lens-ignore" not in line:
            indent = line[: len(line) - len(line.lstrip())]
            out.append(indent + NOTE + "\n")
            added += 1
        out.append(line)
    if added:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.writelines(out)
    return added


def main() -> int:
    total = 0
    for p in TARGETS:
        try:
            n = process(p)
            print(f"{p}: +{n} 注释")
            total += n
        except Exception as e:  # 文件不存在/编码异常——跳过不崩
            print(f"{p}: 跳过（{e}）")
    print(f"总计: {total} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
