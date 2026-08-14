# -*- coding: utf-8 -*-
"""textsnap 批量 OCR（整图直读四合一——CPU 零 token）

用法: python textsnap_batch.py <原照目录> <输出目录>
"""
import os
import subprocess
import sys


def main():
    src = sys.argv[1]
    out = sys.argv[2]
    try:
        os.makedirs(out, exist_ok=True)
    except OSError as e:
        print(f'输出目录创建失败: {e}')
        sys.exit(1)
    if not os.path.isdir(src):
        print(f'目录不存在: {src}')
        sys.exit(1)
    try:
        files = sorted(f for f in os.listdir(src)
                       if f.startswith('微信图片') and f.lower().endswith('.jpg'))
    except OSError as e:
        print(f'读取目录失败: {e}')
        sys.exit(1)
    print(f'共 {len(files)} 张 → {out}', flush=True)
    done, empty = 0, []
    for i, f in enumerate(files, 1):
        base = os.path.splitext(f)[0]
        out_txt = os.path.join(out, f'{base}.txt')
        if os.path.exists(out_txt) and os.path.getsize(out_txt) > 50:
            done += 1
            continue  # 已跑过（断点续跑）
        r = subprocess.run(
            ['textsnap', os.path.join(src, f), '-o', out_txt],
            capture_output=True, timeout=300,
        )
        if r.returncode != 0 or not os.path.exists(out_txt):
            err = r.stderr.decode('utf-8', errors='replace')[-100:]
            print(f'  ! 失败: {f} {err}', flush=True)
            continue
        size = os.path.getsize(out_txt)
        if size < 50:
            empty.append(f)
        done += 1
        if i % 10 == 0:
            print(f'  {i}/{len(files)} (空页 {len(empty)})', flush=True)
    print(f'完成: {done}/{len(files)}  空输出 {len(empty)}: {empty[:5]}', flush=True)


if __name__ == '__main__':
    main()
