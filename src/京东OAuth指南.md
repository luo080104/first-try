# 京东联盟 OAuth 授权指南（补全京东关键词搜索）

> 目标：拿到 access_token，让 goods.query 关键词搜索可用。
> 现状：material.query 免 token 但只能返回频道推荐（keyword 实测无效）。
> 操作时间：约 30 分钟，审核 1-5 天。不阻塞双平台比价开发。

## 前置条件
- 已注册京东联盟账号（union.jd.com）✅ 你已有
- 已有应用（appKey/appSecret）✅ 你已有

## 流程（五步）

### 第 1 步：进入开放平台
打开 https://open.union.jd.com → 登录 → 「应用管理」

### 第 2 步：确认/配置应用
- 找到你的应用，确认状态为「已上线」（未上线先点上线/发布）
- 配置「回调地址 redirect_uri」：随便填一个，如 `https://localhost/callback`
  （保存后后面要用）

### 第 3 步：获取授权链接并打开
授权链接格式：
```
https://open.union.jd.com/oauth2/authorize?app_key=你的appKey&response_type=code&redirect_uri=https://localhost/callback&state=1
```
- 浏览器打开此链接 → 登录京东 → 点击同意授权
- 浏览器地址栏会跳转到回调地址并带 `code=xxxxx`（一次性，5 分钟内有效）

### 第 4 步：用 code 换 token
用浏览器或工具请求：
```
https://open.union.jd.com/oauth2/accessToken?app_key=你的appKey&app_secret=你的appSecret&grant_type=authorization_code&code=上一步的code&redirect_uri=https://localhost/callback
```
返回 JSON 里的 `access_token` 就是我们要的（token 有效期约 90 天，过期后重走 3-4 步）。

### 第 5 步：把 token 给我
把 access_token 发我（存 .env 的 JD_ACCESS_TOKEN），我来验证 goods.query 搜索并接入比价流程。

## 注意事项
- code 一次性且 5 分钟有效，换 token 要快
- 如果页面提示「应用未上线/无权限」，先完成应用上线（可能需要审核）
- 京东联盟文档可能更新，操作时以页面实际为准；遇到问题截图给 WorkBuddy 查
