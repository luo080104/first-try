# -*- coding: utf-8 -*-
"""textsnap 批量 OCR v2（进程内 API——模型只加载一次——无子进程编码问题）

用法: python textsnap_batch2.py <原照目录> <输出目录>
"""
import os
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
    files = sorted(f for f in os.listdir(src)
                   if f.startswith('微信图片') and f.lower().endswith('.jpg'))
    print(f'共 {len(files)} 张 → {out}', flush=True)

    import textsnap
    model_dir = textsnap.get_model_dir()
    print(f'模型: {model_dir}', flush=True)

    done, empty = 0, []
    for i, f in enumerate(files, 1):
        base = os.path.splitext(f)[0]
        out_txt = os.path.join(out, f'{base}.txt')
        if os.path.exists(out_txt) and os.path.getsize(out_txt) > 50:
            done += 1
            continue  # 断点续跑
        try:
            img = textsnap.load_from_file(os.path.join(src, f))
            md = textsnap.run_ocr(img, model_dir)
            txt = textsnap.to_plaintext(md)
            with open(out_txt, 'w', encoding='utf-8') as t:
                t.write(txt)
            if len(txt) < 50:
                empty.append(f)
        except Exception as e:
            print(f'  ! 失败: {f} {str(e)[:80]}', flush=True)
            continue
        done += 1
        if i % 10 == 0:
            print(f'  {i}/{len(files)} (空 {len(empty)})', flush=True)
    print(f'完成: {done}/{len(files)}  空输出 {len(empty)}: {empty[:5]}', flush=True)


if __name__ == '__main__':
    main()
