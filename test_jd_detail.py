# -*- coding: utf-8 -*-
"""京东联盟 API 测试 - 带 token 重试 goods.query"""
import os
import requests
import json
import hashlib
import time
import sys

sys.stdout.reconfigure(encoding="utf-8")

APP_KEY = os.environ.get("JD_APP_KEY", "")
APP_SECRET = os.environ.get("JD_APP_SECRET", "")
ACCESS_TOKEN = "0fb68ec29cc66ae746372da23cc269929790b29e53526d014d7e8190225fb0a94e3b7c29300158f4"
API_URL = "https://api.jd.com/routerjson"


def generate_sign(params, app_secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = app_secret
    for key, value in sorted_params:
        sign_str += f"{key}{value}"
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def call_api(method, biz_params, token=""):
    params = {
        "method": method,
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "360buy_param_json": json.dumps(biz_params, ensure_ascii=False),
    }
    if token:
        params["access_token"] = token
    params["sign"] = generate_sign(params, APP_SECRET)

    resp = requests.post(API_URL, data=params, timeout=15)
    return resp.text


# 测试: goods.query 带 token
print("=== goods.query 带 token ===")
biz = {"goodsReqDTO": {"keyword": "手机", "pageIndex": "1"}}
result = call_api("jd.union.open.goods.query", biz, token=ACCESS_TOKEN)
print(f"返回: {result[:800]}")
print()

# 测试: goods.material.query 详细输出（看有哪些商品）
print("=== goods.material.query 详情 ===")
biz2 = {"goodsReq": {"eliteId": "1", "pageIndex": "1", "pageSize": "5"}}
result2 = call_api("jd.union.open.goods.material.query", biz2)
data = json.loads(result2)
inner = json.loads(data["jd_union_open_goods_material_query_responce"]["queryResult"])
goods_list = inner.get("data", [])
print(f"返回 {len(goods_list)} 条商品:")
for i, g in enumerate(goods_list[:5], 1):
    name = g.get("skuName", "未知")
    price_info = g.get("priceInfo", {})
    lowest = price_info.get("lowestPrice", "N/A")
    commission = g.get("commissionInfo", {})
    share = commission.get("commissionShare", "N/A")
    brand = g.get("brandName", "未知")
    print(f"  {i}. {name}")
    print(f"     品牌: {brand}  最低价: {lowest}  佣金比例: {share}%")
    print()
