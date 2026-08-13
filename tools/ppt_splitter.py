# -*- coding: utf-8 -*-
"""PPT 打印书切图工具 v2（自动检测页面边界 + 倾斜矫正 + 2×2 切分 + 预览确认）

用法:
    python ppt_splitter.py <照片目录> [输出目录] [--preview]
流程:
    1. 自动检测每张照片里的页面矩形（去桌面背景——页面不必占满）
    2. 透视矫正（页面拍斜 → 拉正成矩形）
    3. 页面区域内 2×2 切分（左上/右上/左下/右下 = 第1/2/3/4页）
    4. --preview: 输出拼接预览图（每张原图一行 4 页缩略图——供人工确认）
"""

import os
import sys

import cv2
import numpy as np


def detect_page(img):
    """检测页面矩形（最大轮廓）。返回四点（左上/右上/右下/左下）或 None"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 自适应阈值：纸张在背景上通常是亮的
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 15
    )
    # 形态学闭运算连接纸张边缘
    kernel = np.ones((9, 9), np.uint8)
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    # 取最大轮廓，近似为四边形
    c = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(c)
    h, w = img.shape[:2]
    if area < 0.2 * w * h:  # 页面至少占 20%（防止误检小物体）
        return None
    peri = cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
    if len(approx) == 4:
        return approx.reshape(4, 2)
    # 非四边形 → 用最小外接矩形
    rect = cv2.minAreaRect(c)
    box = cv2.boxPoints(rect)
    return box


def order_points(pts):
    """四点排序：左上/右上/右下/左下"""
    pts = np.array(pts, dtype="float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1)
    return np.array(
        [
            pts[np.argmin(s)],  # 左上（和最小）
            pts[np.argmin(diff)],  # 右上
            pts[np.argmax(s)],  # 右下
            pts[np.argmax(diff)],  # 左下
        ],
        dtype="float32",
    )


def warp_page(img, pts):
    """透视矫正为矩形"""
    pts = order_points(pts)
    (tl, tr, br, bl) = pts
    w1 = np.linalg.norm(br - bl)
    w2 = np.linalg.norm(tr - tl)
    h1 = np.linalg.norm(tr - br)
    h2 = np.linalg.norm(tl - bl)
    max_w = max(int(w1), int(w2))
    max_h = max(int(h1), int(h2))
    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype="float32",
    )
    m = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(img, m, (max_w, max_h))


def normalize_orientation(page):
    """方向归一化：页面统一为横向（宽>高）——竖向页面旋转 90°

    PPT 打印的页面通常横向（16:9/4:3）——手机拍照横竖混合时统一方向再切"""
    h, w = page.shape[:2]
    if h > w:  # 竖向 → 顺时针旋转成横向
        page = cv2.rotate(page, cv2.ROTATE_90_CLOCKWISE)
        return page, '竖向→横向'
    return page, '横向'


def split_quad(page, out_dir, idx):
    """矫正后的页面 → 2×2 切分（按阅读顺序命名）"""
    h, w = page.shape[:2]
    cw, ch = w // 2, h // 2
    quads = [(0, 0), (cw, 0), (0, ch), (cw, ch)]  # 左上/右上/左下/右下
    saved = []
    for i, (x, y) in enumerate(quads, 1):
        crop = page[y : y + ch, x : x + cw]
        p = os.path.join(out_dir, f"page_{idx * 4 + i:04d}.jpg")
        cv2.imwrite(p, crop, [cv2.IMWRITE_JPEG_QUALITY, 95])
        saved.append(p)
    return saved


def make_preview(pages, out_dir, idx):
    """每张原图 → 一行 4 页缩略图（预览确认用）"""
    th = 300
    thumbs = []
    for p in pages:
        im = cv2.imread(p)
        if im is None:
            continue
        tw = int(im.shape[1] * th / im.shape[0])
        thumbs.append(cv2.resize(im, (tw, th)))
    row = np.hstack(thumbs)
    out = os.path.join(out_dir, f"preview_{idx:03d}.jpg")
    cv2.imwrite(out, row, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return out


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "."
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(src, "split")
    preview = "--preview" in sys.argv
    os.makedirs(out, exist_ok=True)
    files = sorted(
        f for f in os.listdir(src) if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    print(f"共 {len(files)} 张照片 → 输出 {out}")
    ok, warn = 0, 0
    for idx, f in enumerate(files):
        img = cv2.imread(os.path.join(src, f))
        if img is None:
            print(f"  ⚠️ 读不了: {f}")
            continue
        assert img is not None
        pts = detect_page(img)
        if pts is None:
            print(f"  ⚠️ 未检测到页面: {f}（照片可能没拍全/背景复杂）——按全图 2×2 切")
            page = img
            warn += 1
        else:
            page = warp_page(img, pts)
        pages = split_quad(page, out, idx)
        if preview:
            pv = make_preview(pages, out, idx)
            print(
                f"  {f} → 第 {idx * 4 + 1}-{idx * 4 + 4} 页（预览: {os.path.basename(pv)}）"
            )
        else:
            print(f"  {f} → 第 {idx * 4 + 1}-{idx * 4 + 4} 页")
        ok += 1
    print(f"完成: {ok} 张处理, {warn} 张降级（全图切）——先看 preview 确认再批量 OCR")


if __name__ == "__main__":
    main()
