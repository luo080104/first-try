# -*- coding: utf-8 -*-
"""简历口径检查器（防露馅——自动化敏感表述扫描）

用法:
    python resume_policy_check.py <简历文件.txt|.md>
输出: 命中清单（表述 + 说明）——无命中 = 口径安全

词表来源：简历 v5→v6 防露馅修订记录（docs/archive/SYNC_简历记录_0813.md）
"""

import re
import sys

# 敏感表述（命中即风险——按简历修订经验积累）
RISK_PATTERNS = [
    (r"独立完成", '建议改"AI 协作开发"口径——"独立完成"暴露 AI 辅助程度'),
    (r"后训练.{0,10}(雏形|探索|研究)", '删除"LLM 后训练"相关表述——防止被追问超出能力'),
    (r"深度使用\s*Pi|深度使用 pi", '避免"深度使用 Pi"——老师偏好"底层问题自解"表述'),
    (
        r"AI 协作.{0,10}(开发|完成)",
        "✅ 安全口径（AI 协作开发——允许）——确认上下文无贬损",
    ),
    (
        r"230\+?\s*commits|230\s*个提交",
        'commit 数量表述——确认是否想暴露（建议用"持续迭代"代替）',
    ),
    (r"导师|老师[^，。]{0,10}(教|指导)", '避免提"导师/老师"——简历是个人能力展示'),
    (r"1\.5\s*万|1\.5万|15k\s*行", "代码量表述——确认是否真实可辩护"),
    (r"全栈|精通|资深", '慎用"精通/资深"——被面试追问的风险词'),
    (r"奖学金|获奖|竞赛", "无实际奖项时勿写——有则保留"),
]


def check(text: str) -> list:
    hits = []
    for pattern, note in RISK_PATTERNS:
        for m in re.finditer(pattern, text):
            start = max(0, m.start() - 15)
            end = min(len(text), m.end() + 15)
            hits.append((m.group(0), note, text[start:end].replace("\n", " ")))
    return hits


def main():
    src = sys.argv[1]
    try:
        with open(src, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(f"读文件失败: {e}")
        sys.exit(1)
    hits = check(text)
    if not hits:
        print("✅ 口径安全——未命中敏感表述")
        return
    print(f"⚠️ 命中 {len(hits)} 处——建议逐一确认:")
    for i, (kw, note, ctx) in enumerate(hits, 1):
        print(f'\n{i}. "{kw}"')
        print(f"   说明: {note}")
        print(f"   上下文: …{ctx}…")


if __name__ == "__main__":
    main()
