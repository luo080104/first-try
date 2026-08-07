# -*- coding: utf-8 -*-
"""
京东联盟 API 测试脚本
测试三个商品查询接口：
1. jd.union.open.goods.material.query（猜你喜欢，非权限）
2. jd.union.open.goods.jingfen.query（京粉精选，非权限）
3. jd.union.open.goods.query（关键词搜索，需权限+token）
"""

import hashlib
import os
import sys
import time
import json
import requests

sys.stdout.reconfigure(encoding="utf-8")

# 从环境变量读取凭证
APP_KEY = os.environ.get("JD_APP_KEY", "")
APP_SECRET = os.environ.get("JD_APP_SECRET", "")
ACCESS_TOKEN = os.environ.get("JD_ACCESS_TOKEN", "")

API_URL = "https://api.jd.com/routerjson"


def generate_sign(params, app_secret):
    """
    京东联盟签名算法（官方文档标准）：
    1. 所有参数按 ASCII 升序排序
    2. 拼接成 key1value1key2value2...（无分隔符）
    3. 前后加 AppSecret
    4. MD5 转大写
    """
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = app_secret
    for key, value in sorted_params:
        sign_str += f"{key}{value}"
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def call_api(method, biz_params, use_token=False):
    """调用京东联盟 API"""
    params = {
        "method": method,
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "360buy_param_json": json.dumps(biz_params, ensure_ascii=False),
    }
    if use_token and ACCESS_TOKEN:
        params["access_token"] = ACCESS_TOKEN
    params["sign"] = generate_sign(params, APP_SECRET)

    resp = requests.post(API_URL, data=params, timeout=15)
    return resp.json()


def print_goods(goods_list, max_show=10):
    """打印商品列表"""
    for i, goods in enumerate(goods_list[:max_show], 1):
        sku_name = goods.get("skuName", "未知商品")
        price_info = goods.get("priceInfo", {})
        lowest_price = price_info.get("lowestPrice", "N/A")
        original_price = price_info.get("originPrice", "N/A")
        commission_info = goods.get("commissionInfo", {})
        commission_share = commission_info.get("commissionShare", "N/A")
        brand_name = goods.get("brandName", "无品牌")

        print(f"  {i}. {sku_name}")
        print(f"     品牌: {brand_name}  最低价: {lowest_price}  原价: {original_price}  佣金: {commission_share}%")
        print()


def test_material_query():
    """测试猜你喜欢商品推荐"""
    print("-" * 60)
    print("接口1: jd.union.open.goods.material.query（猜你喜欢，非权限）")
    print("-" * 60)

    biz_params = {"goodsReq": {"eliteId": "1", "pageIndex": "1", "pageSize": "10"}}
    result = call_api("jd.union.open.goods.material.query", biz_params)

    resp_key = "jd_union_open_goods_material_query_responce"
    if resp_key not in result:
        print(f"[ERROR] {json.dumps(result, ensure_ascii=False, indent=2)}")
        return False

    resp_data = result[resp_key]
    if resp_data.get("code") != "0":
        print(f"[ERROR] code={resp_data.get('code')}")
        return False

    query_str = resp_data.get("queryResult", "{}")
    query_result = json.loads(query_str) if isinstance(query_str, str) else query_str

    if query_result.get("code") != 200:
        print(f"[ERROR] 业务码={query_result.get('code')}, msg={query_result.get('message')}")
        return False

    goods_list = query_result.get("data", [])
    print(f"✅ 成功！返回 {len(goods_list)} 条商品\n")
    print_goods(goods_list)
    return True


def test_jingfen_query():
    """测试京粉精选商品查询"""
    print("-" * 60)
    print("接口2: jd.union.open.goods.jingfen.query（京粉精选，非权限）")
    print("-" * 60)

    biz_params = {"goodsReq": {"eliteId": "1", "pageIndex": "1", "pageSize": "10"}}
    result = call_api("jd.union.open.goods.jingfen.query", biz_params)

    resp_key = "jd_union_open_goods_jingfen_query_responce"
    if resp_key not in result:
        print(f"[ERROR] {json.dumps(result, ensure_ascii=False, indent=2)}")
        return False

    resp_data = result[resp_key]
    if resp_data.get("code") != "0":
        print(f"[ERROR] code={resp_data.get('code')}")
        return False

    query_str = resp_data.get("queryResult", "{}")
    query_result = json.loads(query_str) if isinstance(query_str, str) else query_str

    if query_result.get("code") != 200:
        print(f"[ERROR] 业务码={query_result.get('code')}, msg={query_result.get('message')}")
        return False

    goods_list = query_result.get("data", [])
    print(f"✅ 成功！返回 {len(goods_list)} 条商品\n")
    print_goods(goods_list)
    return True


def test_keyword_search(keyword="手机"):
    """测试关键词商品查询（需要权限 + access_token）"""
    print("-" * 60)
    print(f"接口3: jd.union.open.goods.query（关键词搜索，需权限+token）")
    print(f"搜索关键词: {keyword}")
    print("-" * 60)

    biz_params = {"goodsReqDTO": {"keyword": keyword, "pageIndex": "1", "pageSize": "10"}}
    result = call_api("jd.union.open.goods.query", biz_params, use_token=True)

    resp_key = "jd_union_open_goods_query_responce"
    if resp_key not in result:
        # 可能是 error_response
        err = result.get("error_response", {})
        print(f"[SKIP] token无效或无权限: {err.get('zh_desc', '未知')}")
        print("  → 需要通过 OAuth 获取有效 access_token 后使用")
        return False

    resp_data = result[resp_key]
    if resp_data.get("code") != "0":
        print(f"[ERROR] code={resp_data.get('code')}")
        return False

    query_str = resp_data.get("queryResult", "{}")
    query_result = json.loads(query_str) if isinstance(query_str, str) else query_str

    if query_result.get("code") != 200:
        print(f"[SKIP] 业务码={query_result.get('code')}, msg={query_result.get('message')}")
        print("  → 需要申请 goods.query 接口权限或获取有效 token")
        return False

    goods_list = query_result.get("data", [])
    print(f"✅ 成功！返回 {len(goods_list)} 条商品\n")
    print_goods(goods_list)
    return True


def main():
    if not APP_KEY or not APP_SECRET:
        print("[ERROR] 请先设置环境变量 JD_APP_KEY 和 JD_APP_SECRET")
        return

    print("=" * 60)
    print("京东联盟 API 测试")
    print(f"AppKey: {APP_KEY[:8]}...")
    print(f"AccessToken: {'已设置' if ACCESS_TOKEN else '未设置'}")
    print("=" * 60)
    print()

    results = {}
    results["material.query"] = test_material_query()
    print()
    results["jingfen.query"] = test_jingfen_query()
    print()
    results["goods.query"] = test_keyword_search()

    print("=" * 60)
    print("测试总结:")
    for api, ok in results.items():
        status = "✅ 通过" if ok else "❌ 未通过"
        print(f"  {api}: {status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
