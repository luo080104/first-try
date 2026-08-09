# content_reader.py - 内容联动读取（从 app.py 抽出，消除 compare.py ↔ app.py 循环引用）
# 职责：读 mc_ref jsonl 缓存 → 均衡三平台 → 可信度评分 → 套路检测
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from score import score_content
from price_trap import detect_trap

def read_content_items(keyword: str) -> dict:
    """读内容联动数据（jsonl 缓存，秒回）——B站/贴吧/小红书均衡 10 条 + 评分 + 套路检测"""
    import glob
    import json as _j
    mc_dir = os.path.expanduser('~/mc_ref')

    def read_jsonl(plat):
        out = []
        files = sorted(glob.glob(os.path.join(mc_dir, 'data', plat, 'jsonl', 'search_contents_*.jsonl')))
        if files:
            with open(files[-1], encoding='utf-8') as f:
                for line in f:
                    try:
                        d = _j.loads(line)
                        t = d.get('title', '') or d.get('content', '') or d.get('desc', '') or ''
                        tl = t.lower()
                        if keyword in t or (keyword in ('石头岛', 'stone island') and ('石头岛' in t or 'stone island' in tl or 'stoneisland' in tl)):
                            out.append((d, plat))
                    except Exception:
                        continue
        return out

    cached = read_jsonl('bili') + read_jsonl('tieba') + read_jsonl('xhs')
    by_type = {'bili': [], 'tieba': [], 'xhs': []}
    for d, plat in cached:
        if plat in by_type and len(by_type[plat]) < 10:
            by_type[plat].append((d, plat))
    items = []
    for d, plat in (by_type['bili'] + by_type['tieba'] + by_type['xhs']):
        if plat == 'bili':
            items.append({'type': 'bili', 'title': (d.get('title', '') or '')[:60],
                          'author': d.get('nickname', ''), 'play': d.get('video_play_count', 0),
                          'like': d.get('liked_count', 0), 'comment': d.get('video_comment', 0),
                          'url': d.get('video_url', ''), 'desc': (d.get('desc', '') or '')[:80],
                          'content_id': str(d.get('video_id', '')), 'pub_ts': d.get('create_time', '')})
        elif plat == 'tieba':
            items.append({'type': 'tieba', 'title': (d.get('title', '') or d.get('content', ''))[:60],
                          'author': d.get('author', ''), 'play': 0, 'like': 0,
                          'comment': d.get('comment_count', 0), 'url': d.get('url', ''),
                          'desc': d.get('tieba_name', ''),
                          'content_id': str(d.get('note_id', '')), 'pub_ts': d.get('publish_time', '')})
        else:
            items.append({'type': 'xhs', 'title': (d.get('title', '') or '')[:60],
                          'author': d.get('nickname', ''), 'play': 0,
                          'like': d.get('liked_count', 0), 'comment': d.get('comment_count', 0),
                          'url': d.get('note_url', ''), 'desc': (d.get('desc', '') or '')[:60],
                          'content_id': str(d.get('note_id', '')), 'pub_ts': d.get('time', '')})
    for it in items:
        sc = score_content(it, keyword)
        it['score'] = sc['score']
        it['flags'] = sc['flags']
        it['sent'] = sc['sentiment']
    trap = detect_trap(keyword)
    result = {'items': items[:30]}
    if trap.get('has_trap') or trap.get('has_fake_original'):
        result['trap'] = {'trap': trap.get('trap_msg'), 'fake': trap.get('fake_msg')}
    return result
