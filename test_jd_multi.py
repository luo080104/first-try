# -*- coding: utf-8 -*-
"""京东联盟 API 多接口测试"""
import requests
import json
import hashlib
import time
import sys

sys.stdout.reconfigure(encoding="utf-8")

APP_KEY = "ed65706b4132ee846a05f2ed8a3e3350"
APP_SECRET = "361449e7aa6946b5a0733d2cd24259c6"
API_URL = "https://api.jd.com/routerjson"


def generate_sign(params, app_secret):
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = app_secret
    for key, value in sorted_params:
        sign_str += f"{key}{value}"
    sign_str += app_secret
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()


def call_api(method, biz_params, with_token=False, token=""):
    params = {
        "method": method,
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "360buy_param_json": json.dumps(biz_params, ensure_ascii=False),
    }
    if with_token and token:
        params["access_token"] = token
    params["sign"] = generate_sign(params, APP_SECRET)

    resp = requests.post(API_URL, data=params, timeout=15)
    return resp.text


# 测试1: goods.query 不带 token
print("=== 测试1: goods.query 不带 token ===")
biz1 = {"goodsReqDTO": {"keyword": "手机", "pageIndex": "1"}}
result1 = call_api("jd.union.open.goods.query", biz1)
print(f"返回: {result1[:500]}")
print()

# 测试2: goods.material.query (非权限接口)
print("=== 测试2: goods.material.query (非权限接口) ===")
biz2 = {"goodsReq": {"eliteId": "1", "pageIndex": "1", "pageSize": "10"}}
result2 = call_api("jd.union.open.goods.material.query", biz2)
print(f"返回: {result2[:500]}")
print()

# 测试3: goods.jingfen.query (非权限接口)
print("=== 测试3: goods.jingfen.query (非权限接口) ===")
biz3 = {"goodsReq": {"eliteId": "1", "pageIndex": "1", "pageSize": "10"}}
result3 = call_api("jd.union.open.goods.jingfen.query", biz3)
print(f"返回: {result3[:500]}")
print()

# 测试4: category.goods.get (非权限接口)
print("=== 测试4: category.goods.get (非权限接口) ===")
biz4 = {"reqQuery": {"parentId": "0"}}
result4 = call_api("jd.union.open.category.goods.get", biz4)
print(f"返回: {result4[:500]}")
