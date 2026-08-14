# -*- coding: utf-8 -*-
"""吴老师书正文 OCR 批量提取（RapidOCR 本地免费）

用法: python book_ocr.py <页目录> <输出目录>
输入: 切图后的 page_XXXX.jpg（或整图——直接指原照目录也行）
输出: 每页一个 .txt（按页顺序）+ 汇总 .md
"""
import os
import re
import sys


def enhance(imread_fn, path):
    """放大 2x + CLAHE 对比度（小字 OCR 预处理）"""
    import cv2
    im = imread_fn(path)
    im = cv2.resize(im, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)


def extract_urls(text):
    return re.findall(r'https?://[^\s，。；、）)】」]+', text)


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    os.makedirs(out, exist_ok=True)

    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()

    # 中文路径安全 IO（复制自 ppt_splitter）
    import cv2

    def imread_utf8(path):
        import numpy as np
        data = np.fromfile(path, np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)

    if not os.path.isdir(src):
        print(f'目录不存在: {src}')
        sys.exit(1)
    files = sorted(f for f in os.listdir(src) if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    print(f'共 {len(files)} 页 → {out}')
    all_urls, empty = [], []
    try:
        md = open(os.path.join(out, '汇总.md'), 'w', encoding='utf-8')
    except OSError as e:
        print(f'写汇总失败: {e}')
        sys.exit(1)
        for i, f in enumerate(files, 1):
            g = enhance(imread_utf8, os.path.join(src, f))
            result, _ = ocr(g)
            lines = [r[1] for r in result] if result else []
            txt = '\n'.join(lines)
            base = os.path.splitext(f)[0]
            try:
                with open(os.path.join(out, f'{base}.txt'), 'w', encoding='utf-8') as t:
                    t.write(txt)
            except OSError as e:
                print(f'写 {base}.txt 失败: {e}')
                continue
            urls = extract_urls(txt)
            all_urls.extend(urls)
            if not lines:
                empty.append(f)
            md.write(f'## {base}\n\n{txt}\n\n')
            if i % 20 == 0:
                print(f'  {i}/{len(files)} ...')
    print(f'完成: {len(files)} 页（空页 {len(empty)}: {empty[:5]}）')
    print(f'网址共 {len(all_urls)} 个:')
    for u in dict.fromkeys(all_urls):
        print('  ', u)


if __name__ == '__main__':
    main()
