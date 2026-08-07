# -*- coding: utf-8 -*-
"""
京东联盟 API 测试脚本
接口：jd.union.open.goods.query（商品搜索/查询）
验证京东联盟 API 能正常返回商品数据
"""

import hashlib
import os
import sys
import time
import json
import requests

# 强制 UTF-8 输出（Windows PowerShell 兼容）
sys.stdout.reconfigure(encoding="utf-8")

# 从环境变量读取凭证
APP_KEY = os.environ.get("JD_APP_KEY", "")
APP_SECRET = os.environ.get("JD_APP_SECRET", "")
ACCESS_TOKEN = os.environ.get("JD_ACCESS_TOKEN", "")

# API 网关
API_URL = "https://api.jd.com/routerjson"


def generate_sign(params, app_secret):
    """
    京东联盟签名算法：
    1. 参数按 ASCII 升序排序
    2. 拼接成 key1value1key2value2...（无分隔符）
    3. 前后加 AppSecret
    4. MD5 转大写
    """
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    sign_str = app_secret
    for key, value in sorted_params:
        sign_str += f"{key}{value}"
    sign_str += app_secret
    sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
    return sign


def search_goods(keyword, page_index=1, page_size=10):
    """搜索京东商品"""
    # 业务参数（JSON 序列化后放入 360buy_param_json）
    biz_params = {
        "keyword": keyword,
        "pageIndex": page_index,
        "pageSize": page_size,
    }
    param_json = json.dumps(biz_params, ensure_ascii=False)

    # 公共参数（access_token 按需传入，部分接口不需要）
    params = {
        "method": "jd.union.open.goods.query",
        "app_key": APP_KEY,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "format": "json",
        "v": "1.0",
        "sign_method": "md5",
        "360buy_param_json": param_json,
    }

    # 如果有 access_token 则加上
    if ACCESS_TOKEN:
        params["access_token"] = ACCESS_TOKEN

    # 生成签名
    params["sign"] = generate_sign(params, APP_SECRET)

    # 发送请求
    print(f"正在搜索京东商品: {keyword}")
    print(f"接口: jd.union.open.goods.query")
    print(f"网关: {API_URL}")
    print("-" * 60)

    try:
        resp = requests.post(API_URL, data=params, timeout=15)
        result = resp.json()
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}")
        return

    # 解析结果
    # 京东返回格式: {"jd_union_open_goods_query_responce": {"code": "0", ...}}
    response_key = "jd_union_open_goods_query_responce"

    if response_key not in result:
        print(f"[ERROR] 未找到响应字段 {response_key}")
        print(f"完整返回: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return

    resp_data = result[response_key]

    if resp_data.get("code") != "0":
        print(f"[ERROR] API 返回错误码: {resp_data.get('code')}")
        print(f"错误信息: {resp_data.get('message', resp_data.get('zh_desc', '未知'))}")
        print(f"完整返回: {json.dumps(resp_data, ensure_ascii=False, indent=2)}")
        return

    # 解析商品列表
    query_result_str = resp_data.get("queryResult", "{}")
    query_result = json.loads(query_result_str) if isinstance(query_result_str, str) else query_result_str

    goods_list = query_result.get("data", [])

    if not goods_list:
        print("API 调用成功，但未返回商品数据")
        print(f"完整返回: {json.dumps(query_result, ensure_ascii=False, indent=2)}")
        return

    print(f"搜索成功！返回 {len(goods_list)} 条商品\n")

    for i, goods in enumerate(goods_list[:10], 1):
        sku_info = goods.get("skuInfo", [])
        # 获取价格信息
        price_info = goods.get("priceInfo", {})
        lowest_price = price_info.get("lowestPrice", "N/A")
        original_price = price_info.get("originPrice", "N/A")

        # 获取佣金信息
        commission_info = goods.get("commissionInfo", {})
        commission_share = commission_info.get("commissionShare", "N/A")

        # 商品名称
        sku_name = goods.get("skuName", "未知商品")

        print(f"  {i}. {sku_name}")
        print(f"     最低价: {lowest_price}  原价: {original_price}  佣金比例: {commission_share}%")
        print()


def main():
    if not APP_KEY or not APP_SECRET:
        print("[ERROR] 请先设置环境变量 JD_APP_KEY 和 JD_APP_SECRET")
        print("PowerShell 示例:")
        print('  $env:JD_APP_KEY = "你的AppKey"')
        print('  $env:JD_APP_SECRET = "你的SecretKey"')
        return

    if not ACCESS_TOKEN:
        print("[WARN] 未设置 JD_ACCESS_TOKEN，将尝试不带授权调用")
        print("(部分接口不需要 access_token)")

    print("=" * 60)
    print("京东联盟 API 测试")
    print("=" * 60)
    print()

    # 测试1：搜索手机
    search_goods("手机")

    print("=" * 60)
    print("测试完成！")


if __name__ == "__main__":
    main()
