# llm_parse.py - 对话式意图解析（DeepSeek）
# 输入："帮我看看石头岛的外套多少钱" → {"keyword": "石头岛 外套", "category": "服饰"}
import json
import os
import urllib.request

API_KEY = os.environ.get('DEEPSEEK_API_KEY', 'sk-edf4d1c70edf43708a8904bee4935297')
API_URL = 'https://api.deepseek.com/chat/completions'

def parse_intent(text: str) -> dict:
    """解析用户自然语言 → 搜索意图"""
    prompt = f"""你是购物比价助手的意图解析器。从用户输入中提取：
1. keyword：搜索关键词（品牌+品类，如"石头岛 外套"）
2. category：品类，只能从 服饰/食品/日用百货/数码家电 选，无法判断则为空
只输出 JSON 格式：{{"keyword": "...", "category": "..."}}
用户输入：{text}"""

    body = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': '你只输出 JSON，不输出其他内容。'},
            {'role': 'user', 'content': prompt},
        ],
        'max_tokens': 100,
        'temperature': 0,
    }).encode('utf-8')

    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode('utf-8'))
        content = data['choices'][0]['message']['content'].strip()
        # 兼容 markdown 代码块
        if content.startswith('```'):
            content = content.split('\n', 1)[1].rsplit('```', 1)[0]
        result = json.loads(content)
        return {
            'keyword': result.get('keyword', text.strip())[:50],
            'category': result.get('category', ''),
        }
    except Exception as e:
        print(f'[llm] 解析失败: {str(e)[:80]}，回退为原文')
        return {'keyword': text.strip()[:50], 'category': ''}

if __name__ == '__main__':
    import sys
    text = sys.argv[1] if len(sys.argv) > 1 else '帮我看看石头岛的外套多少钱'
    print(parse_intent(text))
