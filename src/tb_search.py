# tb_search.py - 淘宝浏览器搜索（DrissionPage，page.listen 拦截 MTOP JSON）
# 约束：真浏览器+真账号 / 低频（调用间隔>=30s）/ 遇验证码即停 / 只读提取
# 第一次使用：运行后浏览器弹出，手动登录淘宝一次，之后免登录
# 用法: from tb_search import search_taobao; items = search_taobao('石头岛')
#
# === 2026-08-07 v2 更新（借鉴 5 个 GitHub 项目源码） ===
# 1. 多包拦截：淘宝会发两次相同请求，第一个是假数据，第二个才是真的（CSDN 154302696 实测）
# 2. 多 API 监听：同时监听多个 MTOP 接口，增加命中率（xiuyegege/DrissionPage_taobao_monitor_shop）
# 3. 丰富字段：借鉴 iokNokarl/taobao_spider 的 models.py，提取品牌/服务标签/商品属性/地区/天猫标识
# 4. 搜索页 URL：用 uland.taobao.com/sem/tbsearch（ShilongLee/Crawler 用的搜索入口）
# 5. 翻页加载：滚动触发更多 API 请求（xiuyegege 的 get_shop_info 模式）
import json
import os
import re
import sys
import time
import urllib.parse

from browser_pool import get_browser, rehide_loop

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
# 端口 9300：淘宝专属（京东用 9301，CDP 用 9222），互不冲突

# 多 API 监听模式（来源：xiuyegege multi-API + CSDN 文章 + ShilongLee search.py 交叉验证）
# 淘宝搜索页可能触发以下任意一个 API，全部监听增加命中率
MTOP_API_PATTERNS = [
    '/h5/mtop.relationrecommend.wirelessrecommend.recommend/2.0/',  # 主搜索 API（CSDN 精确匹配）
    'mtop.taobao.search.',                                 # 搜索通用前缀
    'mtop.taobao.shop.simple.fetch',                       # 店铺商品列表
    'mtop.taobao.shop.item.list',                          # 店铺商品列表2
]

# iokNokarl models.py 的服务标签映射表
SERVICE_TAG_MAP = {
    'p4p': '广告', 'guanggao': '广告',
    'tmallPC': '天猫', 'tmall': '天猫',
    'richangrexiaobaokuan2': '热销爆款',
    'thbxf1': '退货宝', 'shipping48H': '48小时发货',
    'baoyounew': '包邮', 'cainixihuan': '猜你喜欢',
    'jinpaimaijia': '金牌卖家', 'huabei': '花呗',
    'sfk': '分期', 'global': '海外', 'chaoshi': '超市',
    'ershou': '二手', 'xinpin': '新品', 'cuxiao': '促销',
    'pinpai': '品牌', 'tianmaoguoji': '天猫国际',
    'taobaoteshe': '淘宝特卖', 'pinzhixinxuan': '品质新选',
    'yushou': '预售', 'dingjin': '定金',
    'tianmaochaoshi': '天猫超市', 'tianmaohexiao': '天猫合销',
    'duigongzhifupc': '对公支付', 'xiancaihoufupc': '先采后付',
}

def _find_browser():
    for p in EDGE_PATHS + CHROME_PATHS:
        if os.path.exists(p):
            return p
    return None

from browser_pool import serialize


@serialize('tb')
def search_taobao(keyword: str, max_items: int = 20, login_wait: int = 150, page: int = 1) -> list:
    """淘宝关键词搜索（浏览器自动化 + API 拦截）。
    返回: [{platform, title, price, original_price, sales, shop, location, is_ad, is_tmall,
           brand, service_tags, url}]
    遇验证码返回 [] 并打印提示。"""
    global _last_call_time
    # 低频约束：两次调用间隔至少 30 秒
    wait = 30 - (time.time() - _last_call_time)
    if wait > 0:
        print(f'[tb] 频率控制，等待 {int(wait)} 秒...')
        time.sleep(wait)
    _last_call_time = time.time()

    browser_path = _find_browser()
    if not browser_path:
        print('[tb] 未找到 Chrome/Edge')
        return []

    browser = get_browser('tb')
    tab = browser.latest_tab

    try:
        # 方案 A：page.listen 拦截 MTOP API JSON（首选）
        items = _search_via_listen(tab, keyword, max_items, login_wait, page)
        if items:
            return items[:max_items]

        # 方案 B：回退到 HTML 卡片文本解析
        print('[tb] API 拦截未成功，回退到 HTML 解析...')
        items = _search_via_html(tab, keyword, max_items)
        return items[:max_items]

    finally:
        # 小布方案：搜索完强制隐藏兜底（防导航/重建后窗口可见）
        try:
            rehide_loop('tb')
        except Exception:
            pass

def _search_via_listen(tab, keyword: str, max_items: int, login_wait: int, page_num: int) -> list:
    """方案 A：拦截浏览器发出的 MTOP API 请求，直接拿 JSON 响应。

    关键改进（来自 CSDN 154302696 实测）：
    淘宝会伪造两个相同的请求，第一个是假数据，第二个才是真数据。
    所以需要等待多个包，跳过第一个。"""

    # 单监听主搜索接口（多 pattern 会导致 wait 拿不到包）
    tab.listen.start(MTOP_API_PATTERNS[0])

    # 搜索页 URL：uland SEM 入口（CSDN 2025-09 实测成功，风控宽松）
    keyword_encoded = urllib.parse.quote(keyword, encoding='utf-8')
    url = (f'https://uland.taobao.com/sem/tbsearch?bc_fl_src=tbsite_T9W2LtnM'
           f'&channelSrp=bingSomama&clk1=343ce7d3ea06de2cf1a203e8562d1eed'
           f'&commend=all&ie=utf8&initiative_id=tbindexz_20170306'
           f'&keyword={keyword_encoded}&page={page_num}'
           f'&preLoadOrigin=https%3A%2F%2Fwww.taobao.com&q={keyword_encoded}'
           f'&refpid=mm_2898300158_3078300397_115665800437'
           f'&search_type=item&sourceId=tb.index&tab=all')
    tab.get(url)

    # 登录检测（淘宝搜索需要登录）
    if _needs_login(tab):
        print('[tb] 请在浏览器窗口手动登录淘宝（仅首次需要）...')
        deadline = time.time() + login_wait
        logged = False
        while time.time() < deadline:
            if not _needs_login(tab):
                logged = True
                break
            time.sleep(3)
        if not logged:
            print('[tb] 登录超时')
            return []
        # 登录后重新访问搜索页（先停旧监听再重启，避免重复 start）
        tab.get(url)
        tab.listen.stop()
        tab.listen.start(MTOP_API_PATTERNS[0])

    # 验证码检测（按约束不绕过；抛异常让采集层识别并暂停该词）
    if _has_captcha(tab):
        from errors import CaptchaError
        raise CaptchaError('淘宝验证码拦截')

    # 等待 MTOP API 响应 —— 多包模式
    # CSDN 实测：淘宝发两次相同请求，第一次假数据，第二次真数据
    items = []
    packets_received = 0
    max_packets = 3  # 最多等 3 个包

    while packets_received < max_packets and len(items) < max_items:
        try:
            packet = tab.listen.wait(timeout=15)
        except Exception:
            break

        if packet is None or isinstance(packet, bool):
            break

        packets_received += 1
        print(f'[tb] 收到第 {packets_received} 个数据包...')

        try:
            body = packet.response.body
            if isinstance(body, bytes):
                body = body.decode('utf-8', errors='replace')
            if isinstance(body, str):
                # 剥离 JSONP 包装: mtopjsonpN({...})
                m = re.match(r'mtopjsonp\d+\((.*)\)\s*$', body.strip(), re.DOTALL)
                body = m.group(1) if m else body
                data = json.loads(body)
            elif isinstance(body, dict):
                data = body
            else:
                continue
        except Exception as e:
            print(f'[tb] 包解析失败: {str(e)[:80]} | body前60字: {str(body)[:60]}')
            continue

        # 检查是否是搜索结果 API 的响应
        ret_list = data.get('ret', [])
        ret_str = '|'.join(ret_list) if isinstance(ret_list, list) else str(ret_list)

        # 如果返回 RGV587（风控），跳过这个包
        if 'RGV587' in ret_str:
            print(f'[tb] 第 {packets_received} 个包触发风控 RGV587，跳过')
            continue

        # 如果不是 SUCCESS，可能是假数据或错误包，跳过
        if 'SUCCESS' not in ret_str:
            print(f'[tb] 第 {packets_received} 个包状态: {ret_str[:100]}')
            continue

        # 解析商品数据
        parsed = _parse_mtop_response(data, max_items - len(items))
        if parsed:
            items.extend(parsed)
            print(f'[tb] 第 {packets_received} 个包解析出 {len(parsed)} 条商品')
            if len(items) >= max_items:
                break
        else:
            print(f'[tb] 第 {packets_received} 个包无有效商品数据（可能是假数据包）')

    # 如果第一批数据不够，滚动加载更多（xiuyegege 模式）
    if len(items) < max_items and packets_received > 0:
        print(f'[tb] 当前 {len(items)} 条，滚动加载更多...')
        for _ in range(3):
            tab.run_js('window.scrollTo(0, document.body.scrollHeight)')
            time.sleep(2)
            try:
                packet = tab.listen.wait(timeout=10)
                if packet and not isinstance(packet, bool):
                    body = packet.response.body
                    if isinstance(body, bytes):
                        body = body.decode('utf-8', errors='replace')
                    if isinstance(body, str):
                        m = re.match(r'mtopjsonp\d+\((.*)\)\s*$', body.strip(), re.DOTALL)
                        body = m.group(1) if m else body
                        data = json.loads(body)
                    elif isinstance(body, dict):
                        data = body
                    else:
                        continue
                    parsed = _parse_mtop_response(data, max_items - len(items))
                    if parsed:
                        items.extend(parsed)
                        print(f'[tb] 滚动加载 +{len(parsed)} 条')
                        if len(items) >= max_items:
                            break
            except Exception:
                continue

    tab.listen.stop()
    return items


def _parse_mtop_response(data: dict, max_items: int) -> list:
    """从 MTOP API JSON 响应中提取商品列表。

    字段映射来源：iokNokarl/taobao_spider models.py + ShilongLee search.py
    提取字段：
      item_id, title, price, price_desc, real_sales, procity(省/市),
      pic_url, item_url, shop(name/url), is_p4p(广告), is_tmall(天猫),
      service_tags(服务标签), brand(品牌), product_attrs(商品属性),
      same_count(同款数), seller_id(卖家ID)
    """
    items = []

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
            item_id = str(raw_item.get('nid', raw_item.get('itemId', raw_item.get('item_id', ''))))
            if not item_id:
                continue

            # 标题（清理 HTML 标签，iokNokarl 模式）
            title_html = raw_item.get('title', '') or raw_item.get('item_name', '')
            title = re.sub(r'<[^>]+>', '', title_html).strip()[:100]

            # 价格（iokNokarl 模式）
            price_show = raw_item.get('priceShow', {})
            if isinstance(price_show, dict):
                price_str = str(price_show.get('price', raw_item.get('price', '')))
            else:
                price_str = str(price_show or raw_item.get('price', ''))
            price = _extract_price(price_str)

            # 原价
            original_str = str(raw_item.get('originalPrice', raw_item.get('oriPrice', '')))
            original = _extract_price(original_str)

            # 销量
            sales = raw_item.get('realSales', raw_item.get('sales', ''))

            # 店铺信息（iokNokarl 模式）
            shop_info = raw_item.get('shopInfo', {})
            if isinstance(shop_info, dict):
                shop = shop_info.get('title', shop_info.get('shopName', ''))
            else:
                shop = str(shop_info or raw_item.get('nick', raw_item.get('sellerNick', '')))

            # 地区（iokNokarl 模式：procity 拆分省/市）
            procity = raw_item.get('procity', '')
            province, city = _split_procity(procity)
            location = procity.strip() if procity else ''

            # 广告标记
            is_p4p = raw_item.get('isP4p', 'false') == 'true'
            is_ad = is_p4p or bool(raw_item.get('isAd', ''))

            # 天猫标识（iokNokarl 模式：检查 icons 数组）
            icons = raw_item.get('icons', [])
            is_tmall = False
            service_tags = []
            if isinstance(icons, list):
                for icon in icons:
                    if not isinstance(icon, dict):
                        continue
                    alias = icon.get('alias', '')
                    text = icon.get('text', '')
                    if alias in ('tmallPC', 'tmall'):
                        is_tmall = True
                    if text:
                        service_tags.append(text)
                    elif alias and alias not in ('p4p', 'guanggao'):
                        service_tags.append(SERVICE_TAG_MAP.get(alias, alias))

            # 品牌提取（iokNokarl 模式：从 structuredUSPInfo 提取）
            brand = ''
            usp_list = raw_item.get('structuredUSPInfo', [])
            if isinstance(usp_list, list):
                for usp in usp_list:
                    if isinstance(usp, dict) and usp.get('propertyName', '') == '品牌':
                        brand = usp.get('propertyValueName', '')
                        break

            # 同款数量、卖家ID
            same_count = raw_item.get('sameCount', '')
            seller_id = str(raw_item.get('userId', raw_item.get('sellerId', '')))

            # 浏览热度
            summary_tips = raw_item.get('summaryTips', [])
            summary = ' | '.join(summary_tips) if isinstance(summary_tips, list) and summary_tips else ''

            # 商品链接
            item_url = raw_item.get('auctionURL', raw_item.get('itemUrl', ''))
            if item_url and not item_url.startswith('http'):
                item_url = f'https:{item_url}'
            elif not item_url and item_id and item_id.isdigit():
                item_url = f'https://item.taobao.com/item.htm?id={item_id}'

            # 图片链接
            pic_url = raw_item.get('pic_path', raw_item.get('picPath', raw_item.get('pic', '')))
            if pic_url and not pic_url.startswith('http'):
                pic_url = f'https:{pic_url}'

            if title and price:
                items.append({
                    'platform': 'tb',
                    'title': title,
                    'price': price,
                    'original_price': original if original and original > price else None,
                    'sales': str(sales)[:20] if sales else '',
                    'shop': str(shop)[:50] if shop else '',
                    'location': location,
                    'province': province,
                    'city': city,
                    'is_ad': is_ad,
                    'is_tmall': is_tmall,
                    'brand': brand,
                    'service_tags': service_tags,
                    'seller_id': seller_id,
                    'same_count': str(same_count) if same_count else '',
                    'summary': summary,
                    'url': item_url,
                    'pic_url': pic_url,
                    'item_id': item_id,
                })
        except Exception:
            continue

        if len(items) >= max_items:
            break

    return items


def _search_via_html(tab, keyword: str, max_items: int) -> list:
    """方案 B：解析 HTML 商品卡片文本（备用，当 API 拦截失败时）。"""

    keyword_encoded = urllib.parse.quote(keyword, encoding='utf-8')
    url = f'https://s.taobao.com/search?q={keyword_encoded}&ie=utf8'
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
        from errors import CaptchaError
        raise CaptchaError('淘宝验证码拦截')

    # 淘宝商品卡片选择器（2025 版，带 hash 后缀，用 contains 匹配）
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

        is_ad = '广告' in txt

        prices = re.findall(r'[\u00a5\uFFE5](\d+(?:\.\d+)?)', txt)
        price = float(prices[0]) if prices else None
        original = float(prices[1]) if len(prices) > 1 else None

        if not price:
            continue

        parts = txt.split('|')
        title = ''
        for p in parts:
            p = p.strip()
            if p and '\u00a5' not in p and '\uFFE5' not in p and '广告' not in p \
               and '人付款' not in p and '人收货' not in p and '月销' not in p \
               and '包邮' not in p and not re.match(r'^[\d,.]+$', p):
                title = p[:100]
                break

        sales = ''
        m = re.search(r'([\d.]+万人?付款|[\d.]+万人?收货|月销[\d.]+万?)', txt)
        if m:
            sales = m.group(1)

        shop = ''
        for p in parts:
            if '旗舰店' in p or '专营店' in p or '专卖店' in p or '官方' in p:
                shop = p.strip()[:50]
                break

        link = ''
        try:
            link = c.link or c.attr('href') or ''
        except Exception:
            pass

        items.append({
            'platform': 'tb',
            'title': title,
            'price': price,
            'original_price': original if original and original > price else None,
            'sales': sales,
            'shop': shop,
            'location': '',
            'is_ad': is_ad,
            'is_tmall': '天猫' in txt,
            'brand': '',
            'service_tags': [],
            'seller_id': '',
            'same_count': '',
            'summary': '',
            'url': link,
            'pic_url': '',
            'item_id': '',
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


def _split_procity(procity: str):
    """将 '浙江 宁波' 拆分为 ('浙江', '宁波')。来源：iokNokarl models.py"""
    if not procity:
        return '', ''
    parts = procity.strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0] if parts else '', ''


def _extract_price(s: str) -> float:
    """从字符串中提取价格数字。"""
    if not s:
        return None
    m = re.search(r'(\d+(?:\.\d+)?)', str(s))
    return float(m.group(1)) if m else None


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else '石头岛'
    items = search_taobao(kw)
    print(f'\n[tb] 淘宝「{kw}」: {len(items)} 条')
    for it in items:
        tags_str = ' '.join(it.get('service_tags', []))
        tmall = ' [天猫]' if it['is_tmall'] else ''
        ad = ' [广告]' if it['is_ad'] else ''
        brand = f' [{it["brand"]}]' if it['brand'] else ''
        loc = f' {it["location"]}' if it['location'] else ''
        print(f'  ¥{it["price"]} | {it["title"][:40]} | {it["shop"][:20]} | {it["sales"]}{loc}{brand}{tmall}{ad}')
        if tags_str:
            print(f'         标签: {tags_str}')
