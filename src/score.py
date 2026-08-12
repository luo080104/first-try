# score.py - 内容可信度评分（按 WorkBuddy 审核修正实现）
# 维度：互动35% + 口碑30% + 价格20% + 时效15%，博主乘法系数，跨平台一致性加分
import datetime
import json
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'shopping.db')
BLOGGERS_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'bloggers.json')

# 博主白名单/黑名单（人工维护，data/bloggers.json）
def load_bloggers():
    try:
        with open(BLOGGERS_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {'whitelist': [], 'blacklist': []}

def blogger_factor(author: str) -> float:
    """博主信誉乘法系数：白名单1.15 / 黑名单0.70 / 未知0.95"""
    b = load_bloggers()
    if author in b.get('whitelist', []):
        return 1.15
    if author in b.get('blacklist', []):
        return 0.70
    return 0.95

# ---------- 互动健康度（平台内归一化） ----------

def interact_score(platform: str, d: dict) -> float:
    """各平台互动指标归一化到 0-1，再取均值（WorkBuddy 修正：避免 B站碾压）"""
    try:
        if platform == 'bili':
            play = int(d.get('play', 0) or 0)
            like = int(d.get('like', 0) or 0)
            comment = int(d.get('comment', 0) or 0)
            if play == 0:
                return 0.3
            like_rate = min(like / play / 0.08, 1.0)     # 赞播比 8% 满分
            comment_rate = min(comment / play / 0.02, 1.0)  # 评论率 2% 满分
            return (like_rate + comment_rate) / 2
        elif platform == 'xhs':
            like = int(d.get('like', 0) or 0)
            comment = int(d.get('comment', 0) or 0)
            # 小红书点赞参考：100 赞以上算活跃
            like_s = min(like / 1000, 1.0)
            comment_s = min(comment / 200, 1.0)
            return (like_s * 0.6 + comment_s * 0.4)
        elif platform == 'tieba':
            comment = int(d.get('comment', 0) or 0)
            return min(comment / 100, 1.0)
    except Exception:
        pass
    return 0.3

# ---------- 口碑倾向（从情感缓存表） ----------

def sentiment_score(platform: str, content_id: str) -> dict:
    """返回 {score: 0-1, pos, neg, total, ad, data_limited}"""
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            'SELECT positive, negative, neutral, ad_suspect, total FROM comment_sentiment WHERE platform=? AND content_id=?',
            (platform, content_id)).fetchone()
        conn.close()
        if not row:
            return {'score': 0.5, 'pos': 0, 'neg': 0, 'total': 0, 'ad': 0, 'data_limited': True}
        pos, neg, _neu, ad, total = row
        if total < 5:
            return {'score': 0.5, 'pos': pos, 'neg': neg, 'total': total, 'ad': ad, 'data_limited': True}
        # 口碑分：正面占比 - 负面占比*1.5（负面信息量大），软广嫌疑每条 -0.05
        s = (pos - neg * 1.5) / total - ad * 0.05
        return {'score': max(0.05, min(0.98, s)), 'pos': pos, 'neg': neg,
                'total': total, 'ad': ad, 'data_limited': False}
    except Exception:
        return {'score': 0.5, 'pos': 0, 'neg': 0, 'total': 0, 'ad': 0, 'data_limited': True}

# ---------- 价格合理性（当前价 vs 历史最低价） ----------

def price_score(keyword: str) -> dict:
    """价格合理性：有≥3条历史价正常算，不足取0.5+数据积累中（WorkBuddy 修正）"""
    try:
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute('''
            SELECT price, original_price FROM price_history
            WHERE title LIKE ? ORDER BY queried_at DESC LIMIT 30
        ''', (f'%{keyword}%',)).fetchall()
        conn.close()
        prices = [r[0] for r in rows if r[0] and r[0] > 1]  # 过滤占位价
        if len(prices) < 3:
            return {'score': 0.5, 'data_limited': True, 'lowest': None}
        lowest = min(prices)
        current = prices[0]
        # 当前价越接近最低价分越高
        s = max(0.1, min(1.0, lowest / current))
        return {'score': s, 'data_limited': False, 'lowest': lowest}
    except Exception:
        return {'score': 0.5, 'data_limited': True, 'lowest': None}

# ---------- 时效性 ----------

def freshness_score(pub_ts) -> float:
    """30天内1.0 / 半年0.8 / 一年0.5 / 更久0.2"""
    if not pub_ts:
        return 0.6
    try:
        ts = int(pub_ts)
        if ts > 10**12:  # 毫秒转秒
            ts = ts // 1000
        age_days = (datetime.datetime.now() - datetime.datetime.fromtimestamp(ts)).days
        if age_days <= 30:
            return 1.0
        if age_days <= 182:
            return 0.8
        if age_days <= 365:
            return 0.5
        return 0.2
    except Exception:
        return 0.6

# ---------- 综合评分 ----------

def score_content(item: dict, keyword: str) -> dict:
    """内容综合可信度评分（0-100）"""
    platform = item.get('type', '')
    content_id = item.get('content_id', '')

    inter = interact_score(platform, item)
    senti = sentiment_score(platform, content_id)
    price = price_score(keyword)
    fresh = freshness_score(item.get('pub_ts'))
    factor = blogger_factor(item.get('author', ''))

    total = (inter * 0.35 + senti['score'] * 0.30 + price['score'] * 0.20 + fresh * 0.15) * factor * 100

    # 软广/广告降权
    if item.get('is_ad') or senti['ad'] >= 2:
        total *= 0.7
    if senti['ad'] >= 1:
        total *= 0.9

    # 数据充分度标签
    flags = []
    if senti['data_limited']:
        flags.append('评论数据有限')
    if price['data_limited']:
        flags.append('价格数据积累中')

    return {
        'score': round(max(5, min(98, total)), 1),
        'inter': round(inter, 2),
        'sentiment': {'pos': senti['pos'], 'neg': senti['neg'], 'ad': senti['ad']},
        'fresh': fresh,
        'flags': flags,
    }

if __name__ == '__main__':
    # 自测
    test = {'type': 'bili', 'content_id': '117002123353', 'play': 561549, 'like': 6663,
            'comment': 800, 'author': '王***外', 'pub_ts': 1758280581}
    print(score_content(test, '石头岛'))
