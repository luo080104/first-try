# extract_products.py - 内容→商品抽取（DeepSeek，WorkBuddy 审核的设计）
# 流程：读 mc_ref jsonl → DeepSeek 抽取商品 → recommendations 表入库（content_id 去重）
# 用法: python src/extract_products.py [关键词]   不带参数 = 全量抽取
import json
import os
import sys
import urllib.request

API_URL = 'https://api.deepseek.com/chat/completions'
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# WorkBuddy 审核通过的抽取 prompt（system 静态 → KV Cache 命中）
EXTRACT_SYSTEM = """你是购物助手的商品提取器。从内容平台（B站/小红书/贴吧）的文本中提取被提及的商品。
规则：
1. 只提取明确提及的商品名（品牌+品类/型号），不猜测
2. 排除泛指词（"这个东西""那个牌子"）
3. 输出 JSON 数组：[{"product": "石头岛外套", "content_id": "xxx", "platform": "bili"}]
4. 没有商品则输出空数组 []
只输出 JSON，不要其他文字。"""

MC_DIR = os.path.expanduser('~/mc_ref')
PLATFORMS = {
    'bili': {'file': 'search_contents', 'id_key': 'video_id', 'url_key': 'video_url',
             'title_key': 'title', 'time_key': 'create_time'},
    'tieba': {'file': 'search_contents', 'id_key': 'note_id', 'url_key': 'url',
              'title_key': 'title', 'time_key': 'publish_time'},
    'xhs': {'file': 'search_contents', 'id_key': 'note_id', 'url_key': 'note_url',
            'title_key': 'title', 'time_key': 'time'},
}

def read_content_all(keyword: str = '') -> list:
    """读三平台 jsonl 内容（可选关键词过滤），返回统一结构"""
    import glob  # WorkBuddy P2-2：函数内导入
    out = []
    for plat, cfg in PLATFORMS.items():
        files = sorted(glob.glob(os.path.join(MC_DIR, 'data', plat, 'jsonl', cfg['file'] + '_*.jsonl')))
        if not files:
            continue
        with open(files[-1], encoding='utf-8') as f:
            for line in f:
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                title = (d.get('title') or d.get('desc') or d.get('content') or '')
                if keyword and keyword not in title:
                    continue
                out.append({
                    'platform': plat,
                    'content_id': str(d.get(cfg['id_key'], '')),
                    'title': title[:120],
                    'url': d.get(cfg['url_key'], ''),
                    'published_at': str(d.get(cfg['time_key'], ''))[:19],
                })
    return out

def _call_llm(content_texts: list, batch_keywords: str) -> list:
    """DeepSeek 抽取一批（最多 15 条内容）"""
    if not API_KEY:
        print('❌ 未设置 DEEPSEEK_API_KEY 环境变量')
        return []
    user_text = json.dumps([{'content_id': c['content_id'], 'platform': c['platform'],
                             'text': c['title']} for c in content_texts], ensure_ascii=False)
    body = json.dumps({
        'model': 'deepseek-v4-flash',
        'messages': [
            {'role': 'system', 'content': EXTRACT_SYSTEM},
            {'role': 'user', 'content': user_text},
        ],
        'max_tokens': 800,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    })
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    raw = data['choices'][0]['message']['content']
    try:
        return json.loads(raw)
    except Exception:
        # 容错：提取 JSON 数组部分
        m = raw[raw.find('['):raw.rfind(']') + 1]
        return json.loads(m) if m.startswith('[') else []

def run_extract(keyword: str = '') -> dict:
    """主入口：抽取 + 入库。返回统计"""
    sys.path.insert(0, os.path.dirname(__file__))
    from db import get_conn, init_db, save_recommendation
    init_db()  # 确保表结构/迁移就绪
    contents = read_content_all(keyword)
    if not contents:
        return {'ok': False, 'msg': '没有可抽取的内容（先跑 MediaCrawler 抓取）'}
    # 分批（每批 15 条，避免超长）
    batches = [contents[i:i + 15] for i in range(0, len(contents), 15)]
    conn = get_conn()
    # 已入库的 content_id 集合（幂等：跳过已抽取的）
    done_ids = set(r[0] for r in conn.execute(
        'SELECT DISTINCT content_id FROM recommendations WHERE content_id != ""').fetchall())
    total_extracted, new_items = 0, 0
    for batch in batches:
        pending = [c for c in batch if c['content_id'] not in done_ids]
        if not pending:
            continue
        try:
            results = _call_llm(pending, keyword)
        except Exception as e:
            print(f'⚠️ 抽取失败: {str(e)[:80]}')
            continue
        if not isinstance(results, list):
            continue
        for r in results:
            if not isinstance(r, dict) or not r.get('product'):
                continue
            total_extracted += 1
            src = next((c for c in pending if c['content_id'] == str(r.get('content_id', ''))), None)
            if src:
                save_recommendation(conn, r['product'], src['platform'], src['content_id'],
                                    src['title'], src['url'], src['published_at'])
                new_items += 1
    conn.commit()
    conn.close()
    return {'ok': True, 'msg': f'扫描 {len(contents)} 条内容，抽取 {total_extracted} 个商品提及，新增入库 {new_items} 条'}

if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else ''
    print(run_extract(kw))
