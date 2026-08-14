# 架构（architecture）

> 每个文件/模块的作用。改结构前先读这里，改完更新这里。

## Go购 项目结构（C:/Users/luoji/shopping-agent/）

```
shopping-agent/
├── src/
│   ├── app.py               # FastAPI 入口（95 行，路由已拆分）
│   ├── routes/
│   │   ├── api.py           # API 路由（搜索历史/盯价/采集控制，with closing 已全覆盖）
│   │   ├── search.py        # 搜索 SSE（is_disconnected 已加，遗留入口 DEPRECATED）
│   │   └── pages.py         # 页面路由
│   ├── db.py                # SQLite helper（连接管理）
│   ├── api_client.py        # 大淘客/京东联盟 API 封装
│   ├── llm_parse.py         # DeepSeek 调用（导购 Pro + 意图解析 + cost_limit 护栏）
│   ├── crawl.py             # 四平台采集引擎（20h 上限，单实例锁装饰器）
│   ├── browser_pool.py      # DrissionPage 浏览器池（headless 平台隔离）
│   ├── pdd_search.py / jd_search.py / tb_search.py  # 各平台搜索
│   ├── sentiment.py         # 评论情感分析（舆情模块，观复可复用）
│   └── app_state.py         # 全局状态
├── templates/               # HTML 页面（guide.html 陪你出发 + index.html v2.0）
├── static/img/avatar.png    # 导购头像
├── tools/
│   └── etf_screener.py      # ETF 多维对比（年化/回撤/夏普/相关性，纯标准库）
├── memory-bank/             # ← 本目录（Pi 启动先读这里）
├── docs/
│   ├── SYNC.md              # 小布↔Pi 同步日志（10000+ 行，历史归档）
│   ├── 雕龙方案_v1.md       # 雕龙方案 v1.4
│   ├── PI_RULES.md          # Pi 前置行为指令（规则一~十二）
│   ├── PI_SDD.md            # SDD 四阶段门禁
│   └── 消费行业指数基金选型报告.md
└── CONSTITUTION.md          # Go购 行为准则（Always/Ask First/Never）
```

## 关键设计决策

| 决策 | 位置 | 原因 |
|------|------|------|
| 双通道搜索 | routes/search.py | API 快 + 浏览器全量，非佣金商品也能搜到 |
| headless 平台隔离 | browser_pool.py | 淘宝 headless、唯品会有头隐藏、京东 API 榜单 |
| 文件即真相 | memory-bank/ | 学 oh-story：状态存 md 不存库，git 可追踪崩溃不丢 |
| 不可变前缀 | llm_parse.py | 学 Reasonix：system prompt 一字不动保缓存 |

## 数据层 → MCP 架构参考（2026-08-13，NewsNow 21k⭐ 精读）

**场景**：将来把 Go购/观复的数据能力暴露给 AI 消费时，用这套模式。

**NewsNow 架构**（Node/Nitro，我们参考思路不参考栈）：
```
source 插件体系（每平台一个源：微博/知乎/HN/ProductHunt）
    ↓ 各自抓取解析
统一聚合层（定时刷新 30min + 手动强刷）
    ↓
数据存储（本地 DB）
    ↓
MCP Server（Streamable HTTP）→ AI 直接查热点，免复制粘贴
```

**三个设计点**：
1. **source 插件化**：每平台一个插件文件，加源 = 加文件，不影响核心
2. **MCP 暴露**：数据做成标准接口（工具名 + schema），AI 用 `get_hot_topics(source)` 查——印证 mcp-builder 方法论
3. **聚合先行**：先收拢多源 → 再决定怎么消费（人看 or AI 查），数据层与消费层解耦

**对我们的应用**：
- Go购 的价格数据/盯价 → 将来可包 MCP 给 Pi/观复调
- 观复的行情/财报数据 → 按此模式暴露
- agents-radar 已解决"AI 盯热点"，NewsNow 的 source 插件化思路可借鉴到 radar 扩展新源
