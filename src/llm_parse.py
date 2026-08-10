# llm_parse.py - 对话式意图解析（Reasoner + 思维链日志 + 前缀缓存优化）
# P0-1：静态指令移 system message（命中 DeepSeek 前缀缓存）
import json
import os
import time
import urllib.request
from datetime import datetime

# API Key 只从环境变量读取（禁止硬编码；部署见 docs/上下文清单.md 一、凭证与环境）
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
API_URL = 'https://api.deepseek.com/chat/completions'
TRACE_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'agent_trace.log')

# 意图解析缓存（内存 24h：同关键词不重复调 LLM，提速 + 省钱）
_intent_cache = {}  # text -> (timestamp, result)
INTENT_CACHE_SECONDS = 24 * 3600


def _cache_get(text: str):
    hit = _intent_cache.get(text)
    if hit and time.time() - hit[0] < INTENT_CACHE_SECONDS:
        return hit[1]
    return None


def _cache_set(text: str, result: dict):
    _intent_cache[text] = (time.time(), result)
    if len(_intent_cache) > 500:  # 防内存膨胀：超 500 条清一半
        keys = list(_intent_cache)
        for k in keys[:250]:
            _intent_cache.pop(k, None)

# 静态指令（system message，前缀缓存友好）
SYSTEM_PROMPT = """你是Go购的意图解析器。提取规则：
1. keyword：搜索关键词（品牌+品类，如"石头岛 外套"）
2. category：品类，只能从 服饰/食品/日用百货/数码家电 选，无法判断则为空
3. exclude_platform：用户明确排除某平台时填平台代码（拼多多=pdd/京东=jd/淘宝=tb/唯品会=vip），没有则空
4. pref_word：用户表达的偏好词（如"纯棉""白色""看重销量""旗舰店"），没有则空
5. pref_category：偏好词适用的品类（服饰/食品/日用百货/数码家电），无法判断则空
只输出 JSON 格式：{"keyword": "...", "category": "...", "exclude_platform": "", "pref_word": "", "pref_category": ""}"""

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

def parse_intent(text: str, use_reasoner: bool = False) -> dict:  # 意图解析用 V4-Flash（简单任务），R1 留给 AI 建议面板
    # 缓存命中：同关键词 24h 内秒回（优化：省 LLM 调用）
    cached = _cache_get(text)
    if cached:
        return cached
    body = json.dumps({
        'model': 'deepseek-v4-pro' if use_reasoner else 'deepseek-v4-flash',
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
            'exclude_platform': result.get('exclude_platform', ''),
            'pref_word': result.get('pref_word', ''),
            'pref_category': result.get('pref_category', ''),
        }
        _cache_set(text, result)
        # v5.2：偏好自动记忆（"不要拼多多"→排除平台；"要纯棉"→品类偏好）
        try:
            from db import add_excluded_platform, add_category_pref, add_global_pref
            if result['exclude_platform']:
                add_excluded_platform(result['exclude_platform'])
            if result['pref_word']:
                if result['pref_category']:
                    add_category_pref(result['pref_category'], result['pref_word'])
                else:
                    add_global_pref(result['pref_word'])
        except Exception:
            pass
        # P1：缓存命中指标
        usage = data.get('usage', {})
        hit = usage.get('prompt_cache_hit_tokens', 0)
        miss = usage.get('prompt_cache_miss_tokens', 0)
        _log_trace(text, reasoning, result, hit, miss)
        # v7 费用统计
        try:
            from llm_usage import record_usage
            record_usage('deepseek-v4-flash', usage.get('prompt_tokens', 0), usage.get('completion_tokens', 0), '意图解析')
        except Exception:
            pass
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

OPTIONS_SYSTEM = """你是Go购的导购助手。根据搜索结果标题，将商品聚类为3-5个选项。
规则：
1. 按产品系列或价格区间聚类，不要按平台聚类
2. 每个选项：label（≤15字简洁名称）、search_kw（品牌+型号，可直接搜索）、price_hint（从输入标题提取的价格区间字符串）
3. search_kw 不要带价格/配置/促销词，只保留品牌和型号系列
4. price_hint 必须从输入数据中提取真实价格，严禁编造
5. 最后一个选项固定为：{"label":"都不是，我自己描述","search_kw":"__custom__","price_hint":""}
只输出JSON数组，不要其他文字。"""

def generate_options(keyword: str, groups: list) -> list:
    """从搜索结果生成导购选项（V4-Flash，聚类/摘要任务不需要 Pro）"""
    lines = []
    for i, g in enumerate(groups[:15], 1):
        best = g.get('best') or g['platforms'][0]
        title = str(best.get('title', ''))[:60]
        price = best.get('actualPrice', 0)
        lines.append(f"{i}. {title} ¥{price}")

    user_msg = "关键词：" + keyword + chr(10) + "结果标题：" + chr(10) + chr(10).join(lines)
    body = json.dumps({
        'model': 'deepseek-v4-flash',
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
        # v7 费用统计
        try:
            from llm_usage import record_usage
            u = data.get('usage', {})
            record_usage('deepseek-v4-flash', u.get('prompt_tokens', 0), u.get('completion_tokens', 0), '导购选项')
        except Exception:
            pass
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
