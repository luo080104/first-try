# detail_crawler.py - 四平台商品详情浏览器爬取（小布决策：API只覆盖佣金商品，浏览器抓全量）
# 复用各平台登录态+端口：tb9300/jd9301/vip9302/pdd9303；低频 15-20s；新商品入库时触发，不重跑全量
import os
import random
import re
import sys
import time

from browser_pool import get_browser, rehide_loop
from diag import diag

sys.path.insert(0, os.path.dirname(__file__))

EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
if not os.path.exists(EDGE):
    EDGE = r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'

PROFILES = {
    'tb': ('data/tb_profile', 9300),
    'jd': ('data/jd_profile', 9301),
    'vip': ('data/vip_profile', 9302),
    'pdd': ('data/pdd_profile', 9303),
}
_last_call = 0


def _rate_limit():
    """15-20s 随机低频（小布方案）"""
    global _last_call
    wait = random.uniform(15, 20) - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _browser(platform):
    return get_browser(platform)


def crawl_tb_detail(item_id: str) -> dict:
    """淘宝商品详情页：标题/价格/店铺/好评率"""
    _rate_limit()
    browser = _browser('tb')
    tab = browser.latest_tab
    try:
        # 先访问首页建立会话（否则详情页会跳登录——实测关键步骤）
        tab.get('https://www.taobao.com/')
        tab.wait.doc_loaded()
        time.sleep(4)
        tab.get(f'https://item.taobao.com/item.htm?id={item_id}')
        tab.wait.doc_loaded()
        time.sleep(6)
        html = tab.html
        if 'noitem' in tab.url:
            return {}
        r = {}
        # 多选择器兜底解析（案例启发：pachong_ref 每个字段一串备选 CSS）
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            def first(selectors):
                for sel in selectors:
                    e = soup.select_one(sel)
                    if e and e.get_text(strip=True):
                        return e.get_text(strip=True)
                return ''
            title = first(['h1', '.tb-main-title', '.ItemHeader--mainTitle', '.item-title',
                           '.goods-title', '.product-title', '.tm-title', '.main-title',
                           '.detail-title', '.item-name', '.tb-detail-hd h1'])
            if title:
                r['title'] = re.sub(r'\s+', ' ', title)[:80]
            else:  # <title> 兜底
                m = re.search(r'<title>([^<]{5,80})</title>', html)
                if m:
                    r['title'] = re.sub(r'[-_].*$', '', m.group(1)).strip()[:80]
            price = first(['.tm-price', '.Price--priceText', '.price', '.item-price',
                           '.goods-price', '.product-price', '.real-price', '.sale-price',
                           '.price-now', '.tb-rmb-num'])
            if price:
                pm = re.search(r'[\d.]+', price)
                if pm:
                    r['price'] = pm.group(0)
            sales = first(['.tb-sell-count', '.ItemHeader--salesCount', '.sale-num',
                           '.month-sales', '.sold-num', '.deal-cnt'])
            if sales:
                sm = re.search(r'[\d.]+[万+]?', sales)
                if sm:
                    r['sales'] = sm.group(0)
            rate = first(['.tb-rate-count', '.ItemHeader--commentCount', '.rate-num'])
            if rate:
                rm = re.search(r'[\d.]+[万+]?', rate)
                if rm:
                    r['comment'] = rm.group(0)
            shop = first(['.tb-shop-name', '.shop-name', '.ShopHeader--title', '.store-name',
                          '.tm-shop-name', '.shop-info-name'])
            if shop:
                r['shop'] = shop[:40]
        except Exception as e:
            diag("detail_crawler", "first", e, "店铺信息解析失败——该条目缺店铺字段")
        # 店铺链接（shop{userId}.taobao.com → 店铺页/成立时间线索）
        m2 = re.search(r'(?:https?:)?//shop(\d+)\.taobao\.com', html)
        if m2:
            r['shop_user_id'] = m2.group(1)
        if not r.get('shop'):
            m3 = re.search(r'class="[^"]*(?:shop|Shop)[^"]*"[^>]*>([^<]{2,40})', html)
            if m3:
                r['shop'] = m3.group(1).strip()[:40]
        return r
    except Exception as e:
        print(f'[detail-tb] {str(e)[:60]}')
        return {}
    finally:
        try:
            rehide_loop('tb')
        except Exception as e:
            diag("detail_crawler", "crawl_tb_detail", e, "tb 隐藏失败——窗口可能可见")

def crawl_jd_detail(item_id: str) -> dict:
    """京东商品详情页（验证码拦截则返回空，由联盟API字段兜底）"""
    _rate_limit()
    browser = _browser('jd')
    tab = browser.latest_tab
    try:
        tab.get(f'https://item.jd.com/{item_id}.html')
        tab.wait.doc_loaded()
        time.sleep(4)
        html = tab.html
        if '安全验证' in html[:5000] or '拖动' in html[:5000]:
            print('[detail-jd] 验证码拦截，跳过（联盟API兜底）')
            return {}
        r = {}
        m = re.search(r'<title>([^<]{5,80})</title>', html)
        if m:
            r['title'] = re.sub(r'[-_].*$', '', m.group(1)).strip()[:80]
        m2 = re.search(r'好评[率度][：:]?\s*([\d.]+%?)', html)
        if m2:
            r['good_rate'] = m2.group(1)
        m3 = re.search(r'class="[^"]*shop-name[^"]*"[^>]*>([^<]{2,40})', html)
        if m3:
            r['shop'] = m3.group(1).strip()[:40]
        return r
    except Exception as e:
        print(f'[detail-jd] {str(e)[:60]}')
        return {}
    finally:
        try:
            rehide_loop('jd')
        except Exception as e:
            diag("detail_crawler", "crawl_jd_detail", e, "jd 隐藏失败——窗口可能可见")

def crawl_detail(platform: str, item_id: str) -> dict:
    """统一入口：按平台爬详情（低频 15-20s）"""
    if platform == 'tb':
        return crawl_tb_detail(item_id)
    if platform == 'jd':
        return crawl_jd_detail(item_id)
    # pdd/vip：详情页结构复杂，先返回空（等二期），由 API/商品库兜底
    print(f'[detail-{platform}] 浏览器详情待二期（API/商品库兜底中）')
    return {}


if __name__ == '__main__':
    plat = sys.argv[1] if len(sys.argv) > 1 else 'tb'
    iid = sys.argv[2] if len(sys.argv) > 2 else ''
    if not iid:
        import sqlite3
        conn = sqlite3.connect('data/shopping.db')
        row = conn.execute("SELECT item_id FROM product_items WHERE platform=? AND item_id != '' LIMIT 1", (plat,)).fetchone()
        conn.close()
        iid = row[0] if row else ''
    r = crawl_detail(plat, iid)
    print(f'详情({plat}):', r)
