# 方案：大淘客 API 调用验证（阶段 0 第一步）

## 目标
验证大淘客 API 凭证可用，能成功搜索到商品数据。

## 背景
- 大淘客账号已注册，应用已创建
- 已获取 AppKey 和 AppSecret
- 多多进宝 PID 已获取

## 技术方案

### 1. 环境准备
- 在 first-try 项目目录下创建 Python 虚拟环境
- 安装依赖：requests
- 将 AppKey、AppSecret 设为环境变量（不硬编码在代码中）

### 2. API 信息
- 基础地址：`https://openapi.dataoke.com/api/`
- 签名算法：
  1. 所有参数按 key 升序排序
  2. 拼接成 `key1=value1&key2=value2` 格式
  3. 末尾追加 `&key={appSecret}`
  4. MD5 加密后转大写
- 测试接口：各大榜单 `/goods/get-ranking-list`
  - 参数：rankType=1（实时榜）、pageId=1、pageSize=10
  - 版本：v1.3.1

### 3. 测试脚本：test_dataoke_api.py
功能：
- 从环境变量读取 AppKey 和 AppSecret
- 生成签名
- 调用榜单接口
- 打印返回的商品名称和价格
- 如果返回商品列表则验证通过

### 4. 文件结构
```
first-try/
├── docs/
│   └── plan-00-api-test.md    ← 本文件
├── test_dataoke_api.py         ← 测试脚本
├── .env.example                ← 环境变量模板（不含真实值）
└── .gitignore                  ← 排除 .env、__pycache__、venv
```

### 5. 安全措施
- AppKey/AppSecret 只存在环境变量中，不写入代码
- .gitignore 排除 .env 文件
- .env.example 只写占位符

## 预期结果
脚本运行后打印出 10 条商品信息（标题 + 券后价），确认 API 通了。

## 风险
- 签名算法如果不对，API 返回签名错误 → 按 SDK 源码确认算法后修正
- 应用审核可能未完成 → 如果返回权限错误，需要等审核通过
