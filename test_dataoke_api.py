"""
大淘客 API 调用验证脚本
测试接口：各大榜单 (get-ranking-list)
运行方式：python test_dataoke_api.py
"""

import hashlib
import os
import sys
import time
import requests

# 修复 Windows 终端编码问题
sys.stdout.reconfigure(encoding="utf-8")

# ===== 配置 =====
API_URL = "https://openapi.dataoke.com/api/goods/get-ranking-list"
APP_KEY = os.environ.get("DTK_APP_KEY", "")
APP_SECRET = os.environ.get("DTK_APP_SECRET", "")
VERSION = "v1.3.1"


def make_sign(params: dict) -> str:
    """
    大淘客签名算法：
    1. 所有参数按 key 升序排序
    2. 拼接成 key1=value1&key2=value2 格式
    3. 末尾追加 &key={appSecret}
    4. MD5 加密后转大写
    """
    sorted_keys = sorted(params.keys())
    sign_str = "&".join(f"{k}={params[k]}" for k in sorted_keys)
    sign_str += f"&key={APP_SECRET}"
    md5 = hashlib.md5(sign_str.encode("utf-8")).hexdigest().upper()
    return md5


def get_ranking_list(rank_type=1, page_id=1, page_size=10):
    """调用各大榜单接口"""
    # 所有请求参数（公共参数 + 业务参数）
    params = {
        "appKey": APP_KEY,
        "version": VERSION,
        "rankType": rank_type,
        "pageId": page_id,
        "pageSize": page_size,
    }
    # 生成签名
    params["sign"] = make_sign(params)

    print(f"请求地址: {API_URL}")
    print(f"请求参数: {params}")
    print("-" * 60)

    # 发送请求
    resp = requests.get(API_URL, params=params, timeout=10)
    print(f"HTTP 状态码: {resp.status_code}")

    data = resp.json()
    print(f"返回码: {data.get('code')}")
    print(f"返回信息: {data.get('msg')}")
    print("-" * 60)

    # 解析结果
    if data.get("code") == 0:
        raw_data = data.get("data", [])
        # data 可能是列表（商品数组）或字典（含 list 字段）
        if isinstance(raw_data, list):
            goods_list = raw_data
        elif isinstance(raw_data, dict):
            goods_list = raw_data.get("list", [])
        else:
            goods_list = []
        print(f"成功！共返回 {len(goods_list)} 条商品\n")
        for i, item in enumerate(goods_list, 1):
            title = item.get("dtitle") or item.get("title", "无标题")
            price = item.get("actualPrice", "?")
            coupon = item.get("couponPrice", 0)
            sales = item.get("monthSales", "?")
            print(f"  {i:2d}. {title}")
            print(f"      券后价: {price}元  优惠券: {coupon / 100:.1f}元  月销: {sales}")
        return True
    else:
        print(f"失败！错误信息: {data.get('msg')}")
        return False


if __name__ == "__main__":
    if not APP_KEY or not APP_SECRET:
        print("错误：环境变量未设置！")
        print("请先设置 DTK_APP_KEY 和 DTK_APP_SECRET")
        print("PowerShell 示例:")
        print('  $env:DTK_APP_KEY = "你的AppKey"')
        print('  $env:DTK_APP_SECRET = "你的AppSecret"')
        exit(1)

    print("=" * 60)
    print("大淘客 API 调用验证")
    print(f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"AppKey: {APP_KEY[:6]}...")
    print("=" * 60 + "\n")

    get_ranking_list(rank_type=1, page_id=1, page_size=10)
