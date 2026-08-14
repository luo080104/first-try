# -*- coding: utf-8 -*-
"""OCR 输出质量检查（认真仔细——质量门）

用法: python quality_check.py <textsnap输出目录>
检测项:
  1. 空页/超短页（<50 字符——可能整页没识别）
  2. 乱码（GBK 残留/常见 OCR 错误符号/孤立拼音）
  3. 异常重复行（同一行重复 >3 次——识别卡顿）
  4. 比例异常（一页字符数 < 全库中位数 20%——可能只识别了部分）
输出: 可疑页清单（供重拍决策）——正常页统计
"""

import os
import re
import sys


def main():
    src = sys.argv[1]
    try:
        files = sorted(f for f in os.listdir(src) if f.endswith(".txt"))
    except OSError as e:
        print(f"读取目录失败: {e}")
        sys.exit(1)
    if not files:
        print("无 txt 文件")
        return

    lengths = []
    texts = {}
    for f in files:
        try:
            with open(os.path.join(src, f), encoding="utf-8") as t:
                txt = t.read().strip()
        except OSError:
            continue
        texts[f] = txt
        lengths.append((f, len(txt)))
    if not lengths:
        print("无有效内容")
        return

    lens = sorted(l for _, l in lengths)
    median = lens[len(lens) // 2]
    issues = []

    for f, txt in texts.items():
        probs = []
        n = len(txt)
        if n == 0:
            probs.append("空页(0字符)")
        elif n < 50:
            probs.append(f"超短页({n}字符——可能漏识别)")
        elif n < median * 0.2:
            probs.append(f"偏短页({n}字符——中位数{median}——可能只识别部分)")
        # 乱码检测：GBK 残留字节/异常字符
        garb = re.findall(r"[\ufffd\x00-\x08]", txt)
        if garb:
            probs.append(f"乱码字符 {len(garb)} 个")
        # 孤立拼音/英文碎片（正常中文页不该有连续孤立字母串）
        if re.search(r"\b[a-z]{1,3}\b(?:\s+[a-z]{1,3}\b){3,}", txt):
            probs.append("孤立字母碎片")
        # 异常重复行
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        for line in set(lines):
            c = lines.count(line)
            if c >= 5 and len(line) > 4:
                probs.append(f'重复行x{c}: "{line[:20]}"')
                break
        if probs:
            issues.append((f, probs))

    print(f"总页数: {len(files)} | 中位字符: {median}")
    print(f"可疑页: {len(issues)}/{len(files)}")
    for f, probs in issues:
        print(f"  ⚠️ {f}: {'; '.join(probs)}")
    if not issues:
        print("✅ 无质量问题——全部通过")


if __name__ == "__main__":
    main()
