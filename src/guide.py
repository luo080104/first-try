# guide.py - 陪你出发（v7 AI 购物向导，WorkBuddy 确认：DeepSeek 直连 + SQLite 会话）
# 融合：ShopAgent-X（多轮收敛/排除词/防幻觉）+ MindPeek（购物画像）
# 流程：用户消息 → 读会话+需求卡 → LLM 回复+更新需求卡 → 需求齐则搜推荐 → 卡片带防幻觉校验
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))

API_URL = 'https://api.deepseek.com/chat/completions'
API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')

# ========== 会话存取 ==========

def get_session(session_id: str) -> dict:
    from db import get_conn
    conn = get_conn()
    row = conn.execute('SELECT * FROM chat_sessions WHERE session_id=?', (session_id,)).fetchone()
    if row:
        s = dict(row)
        conn.close()
        return {'history': json.loads(s.get('history') or '[]'),
                'need_card': json.loads(s.get('need_card') or '{}'),
                'user_name': s.get('user_name', '')}
    # 新会话
    conn.execute('INSERT INTO chat_sessions (session_id, user_name) VALUES (?,?)', (session_id, ''))
    conn.commit()
    conn.close()
    return {'history': [], 'need_card': {}, 'user_name': ''}


def save_session(session_id: str, history: list, need_card: dict, user_name: str = ''):
    from db import get_conn
    conn = get_conn()
    conn.execute('''UPDATE chat_sessions SET history=?, need_card=?, user_name=?, updated_at=datetime('now','localtime')
                    WHERE session_id=?''',
                 (json.dumps(history, ensure_ascii=False), json.dumps(need_card, ensure_ascii=False),
                  user_name or '', session_id))
    conn.commit()
    conn.close()


# ========== 画像存取 ==========

def get_profile(user_name: str) -> dict:
    from db import get_conn
    conn = get_conn()
    row = conn.execute('SELECT * FROM user_profiles WHERE user_name=?', (user_name or '',)).fetchone()
    conn.close()
    if not row:
        return {'budget_tier': '', 'price_sensitive': 0, 'brands': [], 'concerns': [], 'categories': []}
    p = dict(row)
    return {'budget_tier': p.get('budget_tier', ''), 'price_sensitive': p.get('price_sensitive', 0),
            'brands': json.loads(p.get('brands') or '[]'), 'concerns': json.loads(p.get('concerns') or '[]'),
            'categories': json.loads(p.get('categories') or '[]')}


def merge_profile(user_name: str, need_card: dict):
    """把需求卡里的稳定特征合并进画像（MindPeek 思路：持续进化）"""
    if not user_name:
        return
    from db import get_conn
    p = get_profile(user_name)
    if need_card.get('budget'):
        tier = '低' if need_card['budget'] == '3000' else ('中' if need_card['budget'] == '8000' else '高')
        if not p['budget_tier']:
            p['budget_tier'] = tier
    if need_card.get('brand') and need_card['brand'] not in p['brands']:
        p['brands'].append(need_card['brand'])
    if need_card.get('purpose'):
        cats = {'游戏': '数码家电', '办公': '数码家电', '学习': '数码家电'}.get(need_card['purpose'], '')
        if cats and cats not in p['categories']:
            p['categories'].append(cats)
    conn = get_conn()
    # UPSERT：不存在则插入（首次画像）
    conn.execute('''INSERT INTO user_profiles (user_name, budget_tier, price_sensitive, brands, concerns, categories, updated_at)
        VALUES (?,?,?,?,?,?,datetime('now','localtime'))
        ON CONFLICT(user_name) DO UPDATE SET
            budget_tier=excluded.budget_tier, brands=excluded.brands,
            concerns=excluded.concerns, categories=excluded.categories,
            updated_at=datetime('now','localtime')''',
                 (user_name or '', p['budget_tier'], p['price_sensitive'],
                  json.dumps(p['brands'], ensure_ascii=False),
                  json.dumps(p['concerns'], ensure_ascii=False),
                  json.dumps(p['categories'], ensure_ascii=False)))
    conn.commit()
    conn.close()


# ========== LLM 调用 ==========

GUIDE_SYSTEM = """你是「陪你出发」购物向导。帮用户从零开始找到想买的商品。
规则：
1. 每轮回复都输出 JSON：{"reply": "对用户说的话", "need_card": {更新后的需求卡}, "action": "ask"|"recommend"}
2. need_card 字段：budget(预算档:3000/8000/99999/空)、purpose(用途:游戏/办公/学习/家用/空)、brand(品牌偏好)、exclude(排除词数组)、keyword(商品关键词)
3. keyword 必须具体：写"游戏本""羽绒服""纯牛奶"这类具体词，不要写"电脑""衣服""吃的"这类泛称
4. 需求卡未齐时 action=ask，最多问 2-3 个关键问题（预算、用途），不要问太多
5. 需求卡齐了（有 keyword+budget 或 purpose）→ action=recommend，reply 简短说明推荐方向
只输出 JSON，不要其他文字"""


def _call_llm(messages: list, max_tokens: int = 800, retries: int = 2) -> str:
    """调 DeepSeek，空返回/异常自动重试（实测偶发空 content，2026-08-10）"""
    if not API_KEY:
        return json.dumps({'reply': 'AI 未配置，请检查 DEEPSEEK_API_KEY', 'need_card': {}, 'action': 'ask'}, ensure_ascii=False)
    body = json.dumps({
        'model': 'deepseek-v4-flash',
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.7,
    }).encode('utf-8')
    req = urllib.request.Request(API_URL, data=body, headers={
        'Content-Type': 'application/json', 'Authorization': f'Bearer {API_KEY}'})
    last = ''
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            content = data['choices'][0]['message'].get('content') or ''
            if content.strip():
                return content
            last = ''
            print(f'[guide] 空返回，重试 {attempt + 1}/{retries}')
        except Exception as e:
            last = str(e)[:60]
            print(f'[guide] 调用异常，重试 {attempt + 1}/{retries}: {last}')
        time.sleep(1.5 * (attempt + 1))
    return json.dumps({'reply': f'抱歉，我开小差了（{last or "空响应"}），再说一次？', 'need_card': {}, 'action': 'ask'}, ensure_ascii=False)


def _parse_llm(content: str) -> dict:
    try:
        return json.loads(content)
    except Exception:
        # 容错：提取 JSON 对象
        s = content.strip()
        if s.startswith('```'):
            s = s.split('\n', 1)[1].rsplit('```', 1)[0]
        try:
            return json.loads(s)
        except Exception:
            return {'reply': content[:200], 'need_card': {}, 'action': 'ask'}


# ========== 推荐（四级流水线简化版 + 防幻觉）==========

def search_recommend(need_card: dict) -> list:
    """按需求卡搜索推荐：关键词扩展 + 相关性过滤 + 排除词 + 价格区间 + 性价比排序 + 防幻觉"""
    keyword = need_card.get('keyword') or ''
    budget = need_card.get('budget') or ''
    exclude = need_card.get('exclude') or []
    purpose = need_card.get('purpose') or ''
    if not keyword:
        return []

    # 0. 关键词扩展（电脑→[电脑,笔记本,游戏本,台式机]；避免泛词匹配垃圾）
    kw_set = [keyword]
    EXPAND = {
        '电脑': ['笔记本', '游戏本', '台式机', '电脑'],
        '笔记本': ['笔记本', '游戏本'],
        '手机': ['手机'], '耳机': ['耳机', '蓝牙耳机'], '电视': ['电视'],
        '羽绒服': ['羽绒服'], '外套': ['外套', '夹克'], '鞋': ['鞋', '运动鞋'],
        '牛奶': ['牛奶', '纯牛奶'], '零食': ['零食', '大礼包'],
        '面霜': ['面霜'], '精华': ['精华'], '口红': ['口红'],
    }
    kw_set = EXPAND.get(keyword, [keyword])

    # 1. 搜索（快通道 + 商品库兜底）
    items = []
    try:
        from api_client import search_goods, search_pdd
        items = search_goods(keyword) + search_pdd(keyword)
    except Exception:
        pass
    if len(items) < 5:
        try:
            from db import get_conn
            conn = get_conn()
            rows = conn.execute('''SELECT * FROM product_items
                WHERE price > 0 ORDER BY sales DESC LIMIT 60''').fetchall()
            conn.close()
            for r in rows:
                items.append({'platform': r['platform'], 'title': r['title'], 'actualPrice': r['price'],
                              'shopName': r['shop_name'], 'url': r['url'], 'goodsId': r['item_id'],
                              'monthSales': r['sales'], 'brand': r['brand']})
        except Exception:
            pass

    # 2. 相关性过滤：标题/品牌必须含扩展词之一（防泛词匹配垃圾）
    items = [it for it in items
             if any(k in str(it.get('title', '')) or k in str(it.get('brand', '')) for k in kw_set)]

    # 3. 排除词过滤（ShopAgent-X 反选排除）
    if exclude:
        for ex in exclude:
            items = [it for it in items if ex not in str(it.get('title', ''))]

    # 4. 价格区间：上限=预算；下限=预算 8%（防 5 元螺丝刀混入 8000 预算场景）
    if budget and budget != '99999':
        max_price = float(budget)
        items = [it for it in items
                 if 0 < (it.get('actualPrice') or 0) <= max_price
                 and (it.get('actualPrice') or 0) >= max_price * 0.08]
    else:
        items = [it for it in items if (it.get('actualPrice') or 0) > 0]

    # 5. 防幻觉：只保留有真实数据的商品（校验 title/price 存在）
    items = [it for it in items if it.get('title') and it.get('actualPrice')]

    # 6. 性价比排序（含店铺信誉动态权重）
    try:
        from api_client import value_score
        for it in items:
            it['_vs'] = value_score(it)
        items.sort(key=lambda x: x.get('_vs', 0), reverse=True)
    except Exception:
        items.sort(key=lambda x: x.get('actualPrice', 999))

    # 7. 去重（同平台同 ID）
    seen, uniq = set(), []
    for it in items:
        k = f"{it.get('platform')}|{it.get('goodsId') or it.get('item_id') or it.get('title')}"
        if k not in seen:
            seen.add(k)
            uniq.append(it)
    return uniq[:6]


# ========== 主入口 ==========

def chat(session_id: str, user_text: str, user_name: str = '') -> dict:
    """一轮聊天：返回 {reply, need_card, action, items, profile_updated}"""
    sess = get_session(session_id)
    history = sess['history']
    need_card = sess['need_card']
    if user_name and not sess['user_name']:
        sess['user_name'] = user_name

    history.append({'role': 'user', 'content': user_text})
    # 只保留最近 12 轮（上下文控制）
    history = history[-24:]

    # 组 LLM 消息：系统 + 画像 + 需求卡 + 历史
    profile = get_profile(user_name or sess['user_name'])
    sys_msg = GUIDE_SYSTEM + f"\n用户画像：预算档={profile['budget_tier']} 品牌倾向={profile['brands']} 关注品类={profile['categories']}"
    if need_card:
        sys_msg += f"\n当前需求卡：{json.dumps(need_card, ensure_ascii=False)}"
    messages = [{'role': 'system', 'content': sys_msg}] + history

    try:
        raw = _call_llm(messages)
        out = _parse_llm(raw)
    except Exception as e:
        out = {'reply': f'抱歉，我开小差了（{str(e)[:40]}），再说一次？', 'need_card': need_card, 'action': 'ask'}

    new_card = out.get('need_card') or need_card
    reply = out.get('reply') or ''
    action = out.get('action') or 'ask'

    history.append({'role': 'assistant', 'content': reply})
    save_session(session_id, history, new_card, user_name or sess['user_name'])
    merge_profile(user_name or sess['user_name'], new_card)

    # 需求齐 → 推荐
    items = []
    if action == 'recommend':
        items = search_recommend(new_card)
        if not items and not new_card.get('keyword'):
            # 没有关键词：把 reply 当作搜索意图，尝试提取
            new_card['keyword'] = _extract_keyword(reply + user_text)
            items = search_recommend(new_card)

    return {'reply': reply, 'need_card': new_card, 'action': action, 'items': items,
            'profile_updated': bool(user_name or sess['user_name'])}


def _extract_keyword(text: str) -> str:
    """从文本提取商品关键词（简单规则：取常见品类词）"""
    for w in ['电脑', '笔记本', '手机', '耳机', '平板', '电视', '冰箱', '洗衣机', '空调',
              '羽绒服', '外套', '卫衣', '运动鞋', '牛奶', '零食', '咖啡', '面霜', '精华',
              '口红', '洗衣液', '纸', '杯', '灯', '锅']:
        if w in text:
            return w
    return text.strip()[:12]


if __name__ == '__main__':
    import sys
    sid = 'test'
    while True:
        text = input('你: ')
        if text == 'q':
            break
        r = chat(sid, text, '嘉铭')
        print(f"AI: {r['reply']}")
        if r['items']:
            print(f"推荐 {len(r['items'])} 个:")
            for it in r['items']:
                print(f"  ¥{it['actualPrice']} | {it['title'][:30]} | {it.get('shopName','')}")
