# tb_search.py - 淘宝浏览器搜索（DrissionPage，page.listen 拦截 MTOP JSON）
# 约束：真浏览器+真账号 / 低频（调用间隔>=30s）/ 遇验证码即停 / 只读提取
# 第一次使用：运行后浏览器弹出，手动登录淘宝一次，之后免登录
# 用法: from tb_search import search_taobao; items = search_taobao('石头岛')
#
# 核心思路（来自 CSDN 2025-09 文章实测）：
#   浏览器渲染淘宝搜索页时，会自动调用 mtop.relationrecommend.wirelessrecommend.recommend API
#   DrissionPage 的 page.listen 可以拦截这个请求的响应，直接拿到结构化 JSON
#   无需处理签名/token/风控——浏览器全部搞定了
#   这和 tb_spider_ref 项目调的同一个 API，但 tb_spider_ref 用 requests 直调 → RGV587
#   DrissionPage 让浏览器调 → 成功
#
# 备用方案：page.listen 失败时，回退到 HTML 卡片文本解析（和 jd_search.py 同模式）

import sys
import os
import time
import re
import json

EDGE_PATHS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_PATHS = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
PROFILE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'tb_profile')
_last_call_time = 0  # 低频约束

# MTOP API 特征字符串（浏览器渲染搜索页时自动调用的接口）
# 来源：CSDN 2025-09 文章 + tb_spider_ref/config.py 交叉验证
MTOP_API_PATTERN = 'mtop.relationrecommend.wirelessrecommend.recommend'

def _find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

def search_taobao(keyword: str, max_items: int = 20, login_wait: int = 150) -> list:
    """淘宝关键词搜索（浏览器自动化 + API 拦截）。
    返回: [{platform, title, price, original_price, sales, shop, location, is_ad, url}]
    遇验证码返回 [] 并打印提示。"""
    global _last_call_time
    # 低频约束：两次调用间隔至少 30 秒
    wait = 30 - (time.time() - _last_call_time)
    if wait > 0:
        print(f'⏳ 淘宝搜索频率控制，等待 {int(wait)} 秒...')
        time.sleep(wait)
    _last_call_time = time.time()

    browser_path = _find_browser()
    if not browser_path:
        print('❌ 未找到 Chrome/Edge')
        return []

    from DrissionPage import Chromium, ChromiumOptions
    co = ChromiumOptions()
    co.set_browser_path(browser_path)
    co.set_user_data_path(PROFILE_DIR)
    co.set_argument('--start-maximized')
    browser = Chromium(co)
    tab = browser.latest_tab

    try:
        # 方案 A：page.listen 拦截 MTOP API JSON（首选）
        items = _search_via_listen(tab, keyword, max_items, login_wait)
        if items:
            return items[:max_items]

        # 方案 B：回退到 HTML 卡片文本解析
        print('⚠️ API 拦截未成功，回退到 HTML 解析...')
        items = _search_via_html(tab, keyword, max_items)
        return items[:max_items]

    finally:
        browser.quit()


def _search_via_listen(tab, keyword: str, max_items: int, login_wait: int) -> list:
    """方案 A：拦截浏览器发出的 MTOP API 请求，直接拿 JSON 响应。"""

    # 开始监听 MTOP API
    tab.listen.start(MTOP_API_PATTERN)

    # 访问淘宝搜索页
    url = f'https://s.taobao.com/search?q={keyword}&ie=utf8'
    tab.get(url)

    # 登录检测（淘宝搜索需要登录）
    if _needs_login(tab):
        print('🔐 请在浏览器窗口手动登录淘宝（仅首次需要）...')
        deadline = time.time() + login_wait
        logged = False
        while time.time() < deadline:
            if not _needs_login(tab):
                logged = True
                break
            time.sleep(3)
        if not logged:
            print('⏰ 登录超时')
            return []
        # 登录后重新访问搜索页
        tab.get(url)
        tab.listen.start(MTOP_API_PATTERN)  # 重新监听

    # 验证码检测
    if _has_captcha(tab):
        print('⚠️ 遇到淘宝验证码，本次跳过（按约束不尝试绕过）')
        return []

    # 等待 MTOP API 响应（超时 15 秒）
    try:
        packet = tab.listen.wait(timeout=15)
    except Exception:
        return []

    if packet is None:
        return []

    try:
        body = packet.response.body
        if isinstance(body, str):
            data = json.loads(body)
        elif isinstance(body, dict):
            data = body
        else:
            return []
    except Exception:
        return []

    # 解析 MTOP 响应（结构与 tb_spider_ref 的解析逻辑一致）
    return _parse_mtop_response(data, max_items)


def _parse_mtop_response(data: dict, max_items: int) -> list:
    """从 MTOP API JSON 响应中提取商品列表。"""
    items = []

    # 检查返回状态
    ret_list = data.get('ret', [])
    ret_str = '|'.join(ret_list) if isinstance(ret_list, list) else str(ret_list)
    if 'SUCCESS' not in ret_str:
        print(f'⚠️ MTOP 返回非成功: {ret_str[:200]}')
        return []

    raw_data = data.get('data', {})
    raw_items = raw_data.get('itemsArray', [])

    # 企业购 fallback
    if not raw_items or (isinstance(raw_items, list) and all(isinstance(x, str) for x in raw_items)):
        raw_items = raw_data.get('itemsArrayRec', [])

    for raw_item in raw_items:
        if isinstance(raw_item, str):
            try:
                raw_item = json.loads(raw_item)
            except (json.JSONDecodeError, TypeError):
                continue
        if not isinstance(raw_item, dict):
            continue

        try:
            title = raw_item.get('title', '') or raw_item.get('item_name', '')
            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title).strip()[:80]

            price_str = str(raw_item.get('priceShow', raw_item.get('price', '')))
            price = _extract_price(price_str)

            original_str = str(raw_item.get('originalPrice', raw_item.get('oriPrice', '')))
            original = _extract_price(original_str)

            sales = raw_item.get('sales', raw_item.get('realSales', ''))
            shop = raw_item.get('nick', raw_item.get('shopName', raw_item.get('sellerNick', '')))
            item_id = str(raw_item.get('nid', raw_item.get('itemId', '')))
            is_ad = raw_item.get('isAd', '') or raw_item.get('spm', '')

            # 拼商品链接
            url = ''
            if item_id and item_id.isdigit():
                url = f'https://item.taobao.com/item.htm?id={item_id}'

            if title and price:
                items.append({
                    'platform': 'taobao',
                    'title': title,
                    'price': price,
                    'original_price': original if original and original > price else None,
                    'sales': str(sales)[:20] if sales else '',
                    'shop': str(shop)[:30] if shop else '',
                    'location': '',
                    'is_ad': bool(is_ad),
                    'url': url,
                })
        except Exception:
            continue

        if len(items) >= max_items:
            break

    return items


def _search_via_html(tab, keyword: str, max_items: int) -> list:
    """方案 B：解析 HTML 商品卡片文本（备用，当 API 拦截失败时）。"""

    # 确保在搜索结果页
    url = f'https://s.taobao.com/search?q={keyword}&ie=utf8'
    if 's.taobao.com/search' not in tab.url:
        tab.get(url)
        tab.wait.doc_loaded()

    # 触发懒加载
    tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
    time.sleep(2)
    tab.run_js('window.scrollTo(0, 0)')
    time.sleep(1)

    # 验证码检测
    if _has_captcha(tab):
        print('⚠️ 遇到淘宝验证码，本次跳过')
        return []

    # 淘宝商品卡片选择器（2025 版，带 hash 后缀，用 contains 匹配）
    # 来源：kuazhi.com 2025 文章实测
    # a.doubleCardWrapperAdapt--mEcC7olq（新）/ Card--doubleCardWrapper--L2XFE73（旧）
    cards = tab.eles('xpath://a[contains(@class,"doubleCardWrapper")]', timeout=5)
    if not cards:
        cards = tab.eles('xpath://*[contains(@class,"Card--doubleCard")]', timeout=3)
    if not cards:
        cards = tab.eles('xpath://*[contains(@class,"goodsCardWrapper")]', timeout=3)

    items = []
    for c in cards[:max_items + 5]:
        try:
            txt = c.text.replace('\n', '|').strip()
        except Exception:
            continue

        # 广告标记
        is_ad = '广告' in txt

        # 价格
        prices = re.findall(r'[¥￥](\d+(?:\.\d+)?)', txt)
        price = float(prices[0]) if prices else None
        original = float(prices[1]) if len(prices) > 1 else None

        if not price:
            continue

        # 标题：取文本的第一段（去掉广告/价格等）
        parts = txt.split('|')
        title = ''
        for p in parts:
            p = p.strip()
            if p and '¥' not in p and '￥' not in p and '广告' not in p \
               and '人付款' not in p and '人收货' not in p and '月销' not in p \
               and '包邮' not in p and not re.match(r'^[\d,.]+$', p):
                title = p[:80]
                break

        # 销量
        sales = ''
        m = re.search(r'([\d.]+万人?付款|[\d.]+万人?收货|月销[\d.]+万?)', txt)
        if m:
            sales = m.group(1)

        # 店铺
        shop = ''
        for p in parts:
            if '旗舰店' in p or '专营店' in p or '专卖店' in p or '官方' in p:
                shop = p.strip()[:30]
                break

        # 链接
        link = ''
        try:
            link = c.link or c.attr('href') or ''
        except Exception:
            pass

        items.append({
            'platform': 'taobao',
            'title': title,
            'price': price,
            'original_price': original if original and original > price else None,
            'sales': sales,
            'shop': shop,
            'location': '',
            'is_ad': is_ad,
            'url': link,
        })

    return items[:max_items]


def _needs_login(tab) -> bool:
    """检测是否在登录页。"""
    try:
        html_head = tab.html[:3000]
        return '请登录' in html_head or 'login' in tab.url.lower() or '亲，请登录' in html_head
    except Exception:
        return False


def _has_captcha(tab) -> bool:
    """检测是否有验证码。"""
    try:
        html_head = tab.html[:5000]
        return '安全验证' in html_head or '滑动验证' in html_head or '拖动' in html_head
    except Exception:
        return False


def _extract_price(s: str) -> float:
    """从字符串中提取价格数字。"""
    if not s:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', str(s))
    return float(m.group(1)) if m else None


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '石头岛'
    items = search_taobao(kw)
    print(f'\n淘宝「{kw}」: {len(items)} 条')
    for it in items:
        ad = ' [广告]' if it['is_ad'] else ''
        print(f"  ¥{it['price']} | {it['title'][:40]} | {it['shop']} | {it['sales']}{ad}")
