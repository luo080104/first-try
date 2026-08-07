# llm_parse.py - 对话式意图解析（Reasoner + 思维链日志 + 前缀缓存优化）
# P0-1：静态指令移 system message（命中 DeepSeek 前缀缓存）
import json
import os
import urllib.request
from datetime import datetime

API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-edf4d1c70edf43708a8904bee4935297')
API_URL = 'https://api.deepseek.com/chat/completions'
TRACE_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'agent_trace.log')

# 静态指令（system message，前缀缓存友好）
SYSTEM_PROMPT = """你是购物比价助手的意图解析器。提取规则：
1. keyword：搜索关键词（品牌+品类，如"石头岛 外套"）
2. category：品类，只能从 服饰/食品/日用百货/数码家电 选，无法判断则为空
只输出 JSON 格式：{"keyword": "...", "category": "..."}"""

def _log_trace(text: str, reasoning: str, result: dict, cache_hit: int = 0, cache_miss: int = 0):
    try:
        os.makedirs(os.path.dirname(TRACE_LOG), exist_ok=True)
        with open(TRACE_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 输入: {text}\n")
            if reasoning:
                f.write(f"[思维链] {reasoning[:500]}\n")
            f.write(f"[结果] {json.dumps(result, ensure_ascii=False)}\n")
            if cache_hit or cache_miss:
                f.write(f"[缓存] hit={cache_hit} miss={cache_miss}\n")
    except Exception:
        pass

def parse_intent(text: str, use_reasoner: bool = True) -> dict:
    body = json.dumps({
        'model': 'deepseek-reasoner' if use_reasoner else 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': text},   # 只放可变内容
        ],
        'max_tokens': 200,
        'temperature': 0,
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
        msg = data['choices'][0]['message']
        content = (msg.get('content') or '').strip()
        reasoning = (msg.get('reasoning_content') or '').strip()
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(content)
        result = {
            'keyword': result.get('keyword', text.strip())[:50],
            'category': result.get('category', ''),
        }
        # P1：缓存命中指标
        usage = data.get('usage', {})
        hit = usage.get('prompt_cache_hit_tokens', 0)
        miss = usage.get('prompt_cache_miss_tokens', 0)
        _log_trace(text, reasoning, result, hit, miss)
        return result
    except Exception as e:
        print(f'[llm] 解析失败: {str(e)[:80]}，回退为原文')
        return {'keyword': text.strip()[:50], 'category': ''}

if __name__ == '__main__':
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else '帮我看看石头岛的外套多少钱'
    print(parse_intent(text))
    log = open(TRACE_LOG, encoding='utf-8').read()
    print(log[log.rfind('='):][:300])


# ========== 对话式导购（WorkBuddy 审核版）==========

OPTIONS_SYSTEM = """你是购物导购助手。根据搜索结果标题，将商品聚类为3-5个选项。
规则：
1. 按产品系列或价格区间聚类，不要按平台聚类
2. 每个选项：label（≤15字简洁名称）、search_kw（品牌+型号，可直接搜索）、price_hint（从输入标题提取的价格区间字符串）
3. search_kw 不要带价格/配置/促销词，只保留品牌和型号系列
4. price_hint 必须从输入数据中提取真实价格，严禁编造
5. 最后一个选项固定为：{"label":"都不是，我自己描述","search_kw":"__custom__","price_hint":""}
只输出JSON数组，不要其他文字。"""

def generate_options(keyword: str, groups: list) -> list:
    """从搜索结果生成导购选项（deepseek-chat，聚类/摘要任务不需要 reasoner）"""
    lines = []
    for i, g in enumerate(groups[:15], 1):
        best = g.get('best') or g['platforms'][0]
        title = str(best.get('title', ''))[:60]
        price = best.get('actualPrice', 0)
        lines.append(f"{i}. {title} ¥{price}")

    user_msg = "关键词：" + keyword + chr(10) + "结果标题：" + chr(10) + chr(10).join(lines)
    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': OPTIONS_SYSTEM},
            {'role': 'user', 'content': user_msg},
        ],
        'max_tokens': 500,
        'temperature': 0,
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode('utf-8'))
        content = data['choices'][0]['message']['content'].strip()
        if content.startswith('```'):
            content = content.split(chr(10), 1)[1].rsplit('```', 1)[0]
        options = json.loads(content)
        # 防幻觉：过滤异常价格
        for opt in options:
            ph = opt.get('price_hint', '')
            if not ph or '¥0' in ph or len(str(ph)) > 30:
                opt['price_hint'] = ''
        return options if isinstance(options, list) else []
    except Exception as e:
        print(f'[guide] 选项生成失败: {str(e)[:80]}')
        return []
