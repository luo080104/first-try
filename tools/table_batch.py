# -*- coding: utf-8 -*-
"""表格批量识别（rapid_table——恢复表格结构 HTML/Markdown）

用法: python table_batch.py <照片目录> <表格页清单txt> <输出md>
清单格式: 每行一个照片文件名（无扩展名或带 .txt 均可）
"""

import os
import re
import sys


def html_to_markdown(html: str) -> str:
    """简单 HTML 表格 → Markdown 表格（tr/td 结构）"""
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.S)
    lines = []
    for r in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in cells]
        lines.append("| " + " | ".join(cells) + " |")
    if not lines:
        return ""
    # 表头分隔行（第二行起加分隔）
    sep = "|" + "---|" * len(lines[0].split("|")[1:-1])
    return "\n".join([lines[0], sep, *lines[1:]])


def main():
    src = sys.argv[1]
    list_file = sys.argv[2]
    out_md = sys.argv[3]
    try:
        names = [
            l.strip().replace(".txt", "").replace(".jpg", "")
            for l in open(list_file, encoding="utf-8")
            if l.strip()
        ]
    except OSError as e:
        print(f"读清单失败: {e}")
        sys.exit(1)
    if not names:
        print("清单为空")
        return

    import cv2
    import numpy as np

    def imread_utf8(path):
        data = np.fromfile(path, np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    from rapid_table import RapidTable

    engine = RapidTable()

    try:
        os.makedirs(os.path.dirname(out_md), exist_ok=True)
        with open(out_md, "w", encoding="utf-8") as md:
            md.write("# 爸妈投资理念——表格识别结果\n\n")
            md.write(f"> rapid_table 结构恢复——{len(names)} 张疑似表格页\n\n")
            for i, name in enumerate(names, 1):
                img = imread_utf8(os.path.join(src, name + ".jpg"))
                if img is None:
                    print(f"  ! 读不了: {name}")
                    continue
                try:
                    result = engine(img)
                    htmls = result.pred_htmls
                except Exception as e:
                    print(f"  ! 识别失败: {name} {str(e)[:60]}")
                    continue
                md.write(f"## [{name}]\n\n")
                if not htmls:
                    md.write("（未检出表格）\n\n")
                    continue
                for j, h in enumerate(htmls, 1):
                    md.write(f"### 表格{j}\n\n")
                    md.write(html_to_markdown(h) + "\n\n")
                if i % 10 == 0:
                    print(f"  {i}/{len(names)}", flush=True)
    except OSError as e:
        print(f"写文件失败: {e}")
        sys.exit(1)
    print(f"完成: {len(names)} 张 → {out_md}", flush=True)


if __name__ == "__main__":
    main()
