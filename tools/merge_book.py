# -*- coding: utf-8 -*-
"""吴老师书 OCR 结果合并（textsnap_out → 单文档 + 网址清单）

用法: python merge_book.py <textsnap_out目录> [输出md路径]
输出: 合并文档（按拍照顺序=页码顺序）+ 网址清单（文档末尾）
"""

import os
import re
import sys


def extract_urls(text: str) -> list:
    return re.findall(r'https?://[^\s，。；、）)】」"\']+', text)


def main():
    src = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else "docs/爸妈投资理念.md"
    try:
        files = sorted(f for f in os.listdir(src) if f.endswith(".txt"))
    except OSError as e:
        print(f"读取目录失败: {e}")
        sys.exit(1)
    if not files:
        print("无 txt 文件")
        return

    all_urls: list[str] = []
    total_chars = 0
    empty = []
    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as md:
            md.write("# 爸妈投资理念（吴老师书 OCR 数字化）\n\n")
            md.write(
                f"> 来源：{len(files)} 张四合一照片——textsnap 整图直读——按拍照顺序排列\n\n"
            )
            for f in files:
                try:
                    with open(os.path.join(src, f), encoding="utf-8") as t:
                        txt = t.read().strip()
                except OSError:
                    continue
                if not txt:
                    empty.append(f)
                    continue
                total_chars += len(txt)
                all_urls.extend(extract_urls(txt))
                md.write(f"## [{f}]\n\n{txt}\n\n")
            md.write("\n---\n\n## 网址清单\n\n")
            for u in dict.fromkeys(all_urls):
                md.write(f"- {u}\n")
    except OSError as e:
        print(f"写文件失败: {e}")
        sys.exit(1)

    print(f"合并完成: {len(files)} 张 → {out_path}")
    print(f"总字符: {total_chars} | 空页: {len(empty)} {empty[:3]}")
    print(f"网址 {len(dict.fromkeys(all_urls))} 个:")
    for u in dict.fromkeys(all_urls):
        print("  ", u)


if __name__ == "__main__":
    main()
