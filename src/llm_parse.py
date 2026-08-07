# llm_parse.py - 对话式意图解析（DeepSeek Reasoner + 思维链日志）
# 输入："帮我看看石头岛的外套多少钱" → {"keyword": "石头岛 外套", "category": "服饰"}
# 调试：reasoning_content（思维链）记录到 data/agent_trace.log
import json
import os
import urllib.request
from datetime import datetime

API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-edf4d1c70edf43708a8904bee4935297')
API_URL = 'https://api.deepseek.com/chat/completions'
TRACE_LOG = os.path.join(os.path.dirname(__file__), '..', 'data', 'agent_trace.log')

def _log_trace(text: str, reasoning: str, result: dict):
    """思维链日志（调试用）"""
    try:
        os.makedirs(os.path.dirname(TRACE_LOG), exist_ok=True)
        with open(TRACE_LOG, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*60}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 输入: {text}\n")
            if reasoning:
                f.write(f"[思维链] {reasoning[:500]}\n")
            f.write(f"[结果] {json.dumps(result, ensure_ascii=False)}\n")
    except Exception:
        pass

def parse_intent(text: str, use_reasoner: bool = True) -> dict:
    """解析用户自然语言 → 搜索意图（use_reasoner=True 时记录思维链）"""
    prompt = f"""你是购物比价助手的意图解析器。从用户输入中提取：
1. keyword：搜索关键词（品牌+品类，如"石头岛 外套"）
2. category：品类，只能从 服饰/食品/日用百货/数码家电 选，无法判断则为空
只输出 JSON 格式：{{"keyword": "...", "category": "..."}}
用户输入：{text}"""

    body = json.dumps({
        'model': 'deepseek-reasoner' if use_reasoner else 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': '你只输出 JSON，不输出其他内容。'},
            {'role': 'user', 'content': prompt},
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
        reasoning = (msg.get('reasoning_content') or '').strip()  # 思维链
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(content)
        result = {
            'keyword': result.get('keyword', text.strip())[:50],
            'category': result.get('category', ''),
        }
        _log_trace(text, reasoning, result)
        return result
    except Exception as e:
        print(f'[llm] 解析失败: {str(e)[:80]}，回退为原文')
        return {'keyword': text.strip()[:50], 'category': ''}

if __name__ == '__main__':
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else '帮我看看石头岛的外套多少钱'
    r = parse_intent(text)
    print(r)
    # 打印思维链
    log = open(TRACE_LOG, encoding='utf-8').read()
    tail = log[log.rfind('='):]
    print(tail[:400])
