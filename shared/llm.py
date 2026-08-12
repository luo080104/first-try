# shared/llm.py - DeepSeek 调用封装（规则十一 + 成本护栏 budget_ok）
# 从 Go购 compare.py _call_llm_retry 提炼通用版——三 Agent 共用
import json
import os
import urllib.parse
import urllib.request

API_URL = 'https://api.deepseek.com/chat/completions'


def call(user_text: str, system: str = '', max_tokens: int = 800,
         model: str = 'deepseek-chat', timeout: int = 120) -> str:
    """调 DeepSeek 返回文本。失败/超预算返回空串（调用方自行回退）。"""
    from llm_usage import budget_ok
    if not budget_ok():
        return ''
    api_key = os.environ.get('DEEPSEEK_API_KEY', '')
    if not api_key:
        return ''
    body = json.dumps({
        'model': model, 'max_tokens': max_tokens, 'temperature': 0.7,
        'messages': [{'role': 'system', 'content': system},
                     {'role': 'user', 'content': user_text}],
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('choices', [{}])[0].get('message', {}).get('content', '')
    except Exception:
        return ''
