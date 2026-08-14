# 技术栈

> memory-bank 模式：技术决策固化在此，改动前先读。

## 统一技术栈（Go购 / 雕龙 / 观复）

| 层 | 选择 | 备注 |
|----|------|------|
| 后端 | Python FastAPI | Go购 已验证 |
| 数据库 | SQLite（零配置单文件） | 雕龙以后可加向量库 |
| 向量检索 | BGE-M3（中文嵌入标杆）+ Qdrant | 雕龙用，代码就绪待模型下载 |
| 浏览器自动化 | DrissionPage + browser_pool | Go购 爬虫（淘宝 headless 已切） |
| 模型 | DeepSeek-V4-Pro（主推理，性能第一） | 缓存命中 94%，cost_limit ¥3/日护栏 |
| 推送 | Server酱（MVP）→ 企业微信应用消息（家人用） | ntfy 备选 |
| 前端 | PWA 网页（手机浏览器） | Go购 v2.0 卡片化 |
| 小说爬取 | lightnovel-crawler v4.14.0（17 中文源内置） | 雕龙数据管道 |
| 监控 | Langfuse（已装待接入 Go购） | 三 Agent 共用 token 追踪 |

## 共享基础设施（规则十一，待抽取 shared/ 包）

```
shared/
├── browser_pool.py   ← 从 Go购 src/ 抽取
├── db.py             ← SQLite helper
├── llm.py            ← DeepSeek 调用封装（含 cost_limit 护栏）
└── notify.py         ← 推送通道
```

## 编码约束（PI_RULES.md 全文见 docs/）

- Karpathy 四原则 + Ponytail YAGNI 七步决策梯（规则十二）
- SDD 四阶段门禁（spec → plan → tasks → implement）
- 单轮提问循环（规则七/八）
- 装技能即 Darwin 三件套（规则六）
