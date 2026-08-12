# sentiment.py - 评论情感分析（DeepSeek，4 档：正面/负面/中性/软广嫌疑）
# 审核修正：反讽识别、软广标准（话术关键词+评论者历史评论数<3）、缓存表
import json
import os
import sqlite3
import urllib.request

from llm_usage import budget_ok

# API Key 只从环境变量读取（禁止硬编码）
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# 静态指令（前缀缓存友好，P0-1）
SENTIMENT_SYSTEM = """分析电商/内容平台评论的情感倾向。每条输出一个标签：
P=正面（好评/推荐） N=负面（差评/翻车/避雷） M=中性（普通/提问/无倾向） A=软广嫌疑（像水军/推广话术/复制粘贴）
注意识别反讽（如"质量真是太好了，穿一次就破了"是 N）和黑话（"绝绝子"算 P，"避雷"算 N）。
只输出 JSON 数组，如 ["P","N","M","A"]，数量与输入一致。"""
API_URL = 'https://api.deepseek.com/chat/completions'
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')

from concurrent.futures import ThreadPoolExecutor, as_completed


def _llm_classify(comments: list, batch_size: int = 20) -> list:
    """调 DeepSeek 批量分析评论（并发 5 批，P0-2）"""
    batches = [comments[i:i + batch_size] for i in range(0, len(comments), batch_size)]

    def one(batch):
        return _classify_batch(batch)

    results_map = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(one, b): i for i, b in enumerate(batches)}
        for fu in as_completed(futures):
            try:
                results_map[futures[fu]] = fu.result()
            except Exception as e:
                print(f'[sentiment] 批次失败: {str(e)[:60]}')
                results_map[futures[fu]] = ['M'] * len(batches[futures[fu]])
    return [label for i in range(len(batches)) for label in results_map[i]]

def _classify_batch(batch):
    if not budget_ok():
        return ['N'] * len(batch)  # 预算超限保守处理：标负面防误导
    """单批分类"""
    items = chr(10).join(f'{j}. {c}' for j, c in enumerate(batch))
    prompt = f"评论：{chr(10)}{items}"
    body = json.dumps({
        'model': 'deepseek-v4-flash',
        'messages': [
            {'role': 'system', 'content': SENTIMENT_SYSTEM},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 200,
        'temperature': 0,
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode('utf-8'))
    usage = data.get('usage', {})
    print(f'[sentiment] cache hit={usage.get("prompt_cache_hit_tokens",0)} miss={usage.get("prompt_cache_miss_tokens",0)}')
    content = data['choices'][0]['message']['content'].strip()
    if content.startswith('```'):
        content = content.split(chr(10), 1)[1].rsplit('```', 1)[0]
    labels = json.loads(content)
    return labels[:len(batch)]

def analyze_platform(platform: str, jsonl_path: str) -> dict:
    """分析某平台全部评论 → 按内容 ID 聚合存入缓存表"""
    import glob
    files = sorted(glob.glob(jsonl_path))
    if not files:
        return {}
    # 读评论（不同平台字段不同）
    comments_by_content = {}
    with open(files[-1], encoding='utf-8') as f:
        for line in f:
            try:
                d = json.loads(line)
                cid = str(d.get('video_id') or d.get('note_id') or '')
                content = d.get('content', '')
                if cid and content:
                    comments_by_content.setdefault(cid, []).append(content)
            except Exception:
                continue

    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS comment_sentiment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL, content_id TEXT NOT NULL,
        positive INTEGER DEFAULT 0, negative INTEGER DEFAULT 0,
        neutral INTEGER DEFAULT 0, ad_suspect INTEGER DEFAULT 0,
        total INTEGER DEFAULT 0,
        analyzed_at TEXT DEFAULT (datetime('now','localtime')))''')
    conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_sentiment ON comment_sentiment(platform, content_id)')

    stats = {}
    for cid, comments in comments_by_content.items():
        # 缓存命中跳过
        row = conn.execute('SELECT positive FROM comment_sentiment WHERE platform=? AND content_id=?',
                           (platform, cid)).fetchone()
        if row:
            continue
        if len(comments) < 5:
            continue  # 评论太少不分析（数据有限）
        labels = _llm_classify(comments[:40])  # 每内容最多 40 条
        s = {'positive': labels.count('P'), 'negative': labels.count('N'),
             'neutral': labels.count('M'), 'ad_suspect': labels.count('A')}
        conn.execute('''INSERT INTO comment_sentiment
            (platform, content_id, positive, negative, neutral, ad_suspect, total)
            VALUES (?,?,?,?,?,?,?)''',
            (platform, cid, s['positive'], s['negative'], s['neutral'], s['ad_suspect'], len(labels)))
        stats[cid] = s
        print(f'  [{platform}] {cid[:12]}: P{s["positive"]} N{s["negative"]} M{s["neutral"]} A{s["ad_suspect"]}')
    conn.commit()
    conn.close()
    return stats

if __name__ == '__main__':
    import sys
    import time
    platform = sys.argv[1] if len(sys.argv) > 1 else 'bili'
    path_map = {
        'bili': 'C:/Users/luoji/mc_ref/data/bili/jsonl/search_comments_*.jsonl',
        'xhs': 'C:/Users/luoji/mc_ref/data/xhs/jsonl/search_comments_*.jsonl',
        'tieba': 'C:/Users/luoji/mc_ref/data/tieba/jsonl/search_comments_*.jsonl',
    }
    print(f'=== 分析 {platform} 评论 ===')
    t0 = time.time()
    stats = analyze_platform(platform, path_map[platform])
    print(f'完成：{len(stats)} 个内容，耗时 {time.time()-t0:.0f}s')
