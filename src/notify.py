# notify.py - 盯价推送（v6 最后一环，WorkBuddy 计划②）
# 渠道：企业微信群机器人 webhook（免费无需认证）
# 流程：定时检查 watched_items → 按标题搜索最新价 → 命中目标价 → 推送到企业微信群
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

# 企业微信群机器人 webhook（.env 配置 WECHAT_WEBHOOK；未配置则只记录不推送）
def _get_webhook() -> str:
    env = {}
    path = os.path.join(os.path.dirname(__file__), '..', '.env')
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return os.environ.get('WECHAT_WEBHOOK', '') or env.get('WECHAT_WEBHOOK', '')


def push_wechat(text: str) -> bool:
    """企业微信群机器人推送（markdown）。未配置 webhook 返回 False。"""
    hook = _get_webhook()
    if not hook:
        print('[notify] 未配置 WECHAT_WEBHOOK，跳过推送（只记录）')
        return False
    try:
        import json
        import urllib.request
        body = json.dumps({
            'msgtype': 'markdown',
            'markdown': {'content': text},
        }).encode('utf-8')
        req = urllib.request.Request(hook, data=body, headers={'Content-Type': 'application/json'})
        resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
        if resp.get('errcode') == 0:
            print('[notify] ✅ 企业微信推送成功')
            return True
        print(f'[notify] 推送失败: {resp}')
        return False
    except Exception as e:
        print(f'[notify] 推送异常: {str(e)[:80]}')
        return False


def check_and_notify() -> dict:
    """检查所有活跃盯价：按标题搜索最新价 → 命中目标价 → 推送。
    返回统计 {checked, hit, pushed, errors}"""
    from db import get_conn, get_excluded_platforms

    conn = get_conn()
    watches = conn.execute("""
        SELECT id, title, platform, item_id, current_price, target_price, last_notified_at
        FROM watched_items WHERE is_active=1
    """).fetchall()
    conn.close()
    if not watches:
        return {'checked': 0, 'hit': 0, 'pushed': 0, 'errors': []}

    from api_client import search_goods, search_pdd
    stat = {'checked': 0, 'hit': 0, 'pushed': 0, 'errors': []}
    excluded = get_excluded_platforms()

    for w in watches:
        stat['checked'] += 1
        title = w['title']
        platform = w['platform'] or 'tb'
        item_id = str(w['item_id'] or '')
        target = w['target_price']
        try:
            # 按标题关键词搜最新价（快通道，缓存优先）
            items = []
            if platform == 'pdd' and platform not in excluded:
                items = search_pdd(title[:20])
            elif platform == 'tb' and platform not in excluded:
                items = search_goods(title[:20])
            elif platform == 'jd' and platform not in excluded:
                try:
                    from jd_api import search_jd_by_api
                    items = search_jd_by_api(title[:20])
                except Exception:
                    items = []
            # 匹配 item_id（无 item_id 则取最低价）
            cur = None
            if item_id:
                cur = next((it for it in items if str(it.get('goodsId') or '') == item_id), None)
            if cur is None and items:
                cur = min(items, key=lambda x: x.get('actualPrice') or 999999)
            if not cur or not cur.get('actualPrice'):
                continue
            new_price = float(cur['actualPrice'])
            # 更新当前价
            conn = get_conn()
            conn.execute('UPDATE watched_items SET current_price=? WHERE id=?', (new_price, w['id']))
            conn.commit()
            conn.close()
            # 命中目标价 → 推送（防重复：同一盯价只推一次，除非价格再创新低）
            if target and new_price <= float(target):
                last = w['last_notified_at']
                if not last or new_price < float(w['current_price'] or 0):
                    stat['hit'] += 1
                    msg = (f"<font color=\"warning\">🎯 盯价提醒！</font>\n"
                           f"> **{title[:40]}**\n"
                           f"> 现价 **¥{new_price}**（目标 ¥{target}）✅\n"
                           f"> 平台：{platform}")
                    if cur.get('url'):
                        msg += f"\n> [点此查看]({cur['url']})"
                    if push_wechat(msg):
                        stat['pushed'] += 1
                        conn = get_conn()
                        conn.execute('UPDATE watched_items SET last_notified_at=datetime(\'now\',\'localtime\') WHERE id=?', (w['id'],))
                        conn.execute('INSERT INTO push_log (watch_id, title, price, target, platform) VALUES (?,?,?,?,?)',
                                     (w['id'], title[:80], new_price, target, platform))
                        conn.commit()
                        conn.close()
        except Exception as e:
            stat['errors'].append(f'{title[:20]}: {str(e)[:40]}')

    return stat


if __name__ == '__main__':
    print(check_and_notify())
