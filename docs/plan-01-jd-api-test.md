# 方案：京东联盟 API 测试（plan-01）

> 目标：验证京东联盟 API 能正常返回商品数据，与大淘客保持统一进度。

## 一、测试接口

- **接口**：`jd.union.open.goods.search`（商品搜索）
- **网关**：`https://api.jd.com/routerjson`
- **方法**：POST

## 二、公共参数

| 参数 | 值 | 说明 |
|------|-----|------|
| method | jd.union.open.goods.search | 接口名称 |
| app_key | 环境变量 JD_APP_KEY | 应用密钥 |
| access_token | 环境变量 JD_ACCESS_TOKEN | 授权令牌 |
| timestamp | yyyy-MM-dd HH:mm:ss | 当前时间 |
| format | json | 返回格式 |
| v | 1.0 | API版本 |
| sign_method | md5 | 签名算法 |
| sign | 自动计算 | 签名 |

## 三、业务参数（360buy_param_json）

```json
{"keyword": "手机", "pageIndex": 1, "pageSize": 10}
```

## 四、签名算法

1. 收集所有参数（除 sign 外），按参数名 ASCII 升序排序
2. 拼接成 `key1value1key2value2...`（无分隔符）
3. 前后加 AppSecret：`AppSecret + 拼接串 + AppSecret`
4. MD5 加密，转大写

## 五、安全

- AppKey / AppSecret / AccessToken 从环境变量读取，不写进代码
- 环境变量名：`JD_APP_KEY` / `JD_APP_SECRET` / `JD_ACCESS_TOKEN`
- `.env.example` 中补充京东相关变量（不含真实值）
- `.gitignore` 排除 `.env`

## 六、预期结果

- 返回 code=0（成功）
- 打印 10 条商品（标题 + 价格 + 佣金比例）
- 确认京东 API 可用，三个平台数据源统一到"已验证"状态

## 七、与大淘客的区别

| | 大淘客 | 京东联盟 |
|---|---|---|
| 网关 | openapi.dataoke.com | api.jd.com/routerjson |
| 签名 | 参数排序 + &key=secret → MD5 | 参数排序 + keyvalue → 前后夹secret → MD5 |
| 业务参数 | 直接传 | 放在 360buy_param_json 里 JSON 序列化 |
| 覆盖平台 | 淘宝+拼多多 | 仅京东 |
