# -*- coding: utf-8 -*-
"""PPT 打印书切图工具（2×2 四合一 → 四张独立页）

用法: python ppt_splitter.py <照片目录> [输出目录]
输入: 每张照片是 2×2 排版（左上=第1页 右上=第2页 左下=第3页 右下=第4页）
输出: <输出目录>/IMG_001_1.jpg ... _4.jpg（按阅读顺序命名——页码=照片序号×4+N）
"""
import os
import sys

from PIL import Image


def split_quad(path_in: str, out_dir: str, idx: int) -> None:
    img = Image.open(path_in)
    w, h = img.size
    # 2×2 四等分（切掉边缘 1% 防黑边/装订）
    cw, ch = int(w * 0.49), int(h * 0.49)
    quadrants = [
        (0, 0),          # 左上 = 第1页
        (cw, 0),         # 右上 = 第2页
        (0, ch),         # 左下 = 第3页
        (cw, ch),        # 右下 = 第4页
    ]
    for i, (x, y) in enumerate(quadrants, 1):
        crop = img.crop((x, y, x + cw, y + ch))
        base = int(idx * 4 + i)
        crop.save(os.path.join(out_dir, f'page_{base:04d}.jpg'), quality=95)
    print(f'  {os.path.basename(path_in)} → 第 {idx*4+1}-{idx*4+4} 页')


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else '.'
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, 'split')
    os.makedirs(out, exist_ok=True)
    files = sorted(f for f in os.listdir(src)
                   if f.lower().endswith(('.jpg', '.jpeg', '.png')))
    print(f'共 {len(files)} 张照片 → {out}')
    for idx, f in enumerate(files):
        split_quad(os.path.join(src, f), out, idx)


if __name__ == '__main__':
    main()
