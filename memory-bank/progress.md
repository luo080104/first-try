# 当前进度（progress）

> 最后更新：2026-08-15。Pi 每次工作后更新此文件 + SYNC.md。
>
> **维护纪律（2026-08-15 用户指出）：更新本文件前必须核对 docs/SYNC.md 尾部 + `git log --oneline`，禁止从旧版直接继承待办**——progress.md 是易过时缓存，SYNC.md/git log 才是事实源。

## Go购（v2.0 收尾）

### 已完成

- [x] v2.0 交互打磨：纯卡片导航 / 陪你出发 / 商品库输入即搜 / 实时搜索计时 / 搜索历史
- [x] 8/13 全量审查修复：连接泄漏 22 处（with closing）、SSE 断线检测、遗留入口 DEPRECATED、crawl 装饰器确认、price_trend 10 分钟缓存
- [x] family_pin **前后端全链路**（后端 be21479 + 前端 8f0eb49：密码菜单 + 8 页面 15 处带 pin）
- [x] 导购模型切 Pro、对话上下文链路（session_id）
- [x] ruff 295→0、semgrep 清理、缓存 94%
- [x] Headroom 0.34.0 接入（proxy 8787 + env 开关 + dashboard 汉化 113 处）
- [x] **Headroom 压缩验证完成**（8/14：kompress 模型 1.4G 已下——长请求实测省 32%（817→556）——start_server.vbs 已配 LLM_API_URL 走 proxy——下次启动自动压缩）

### 待办

- [ ] git push 10+ 提交（热点 TLS 卡死，回家 WiFi 推）
- [x] Langfuse 接入已完成（8/12：key + @observe + shared/llm.py + 真实调用验证）——非待办（小布清单核对修正）
- [ ] 采集重跑（PDD 三板斧，等 WiFi/冷却）
- [ ] 手机端验证（等用户测试）

## 雕龙（暂停中）

- [ ] 方案 v1.4 就绪（9 模块+8 Hook+16 决策）——⑥ 质检已扩到 14 项（+人性化评分）
- [ ] lightnovel-crawler v4.14.0 已装（17 中文源）
- [ ] 待：找极道天魔真实 URL → 爬前三章 → 小布拆节拍写风格规范
- [x] diao-long 仓库已改名（luo080104/diao-long）——非待办（小布清单核对修正）
- [ ] tools/humanizer_scorer.py 已就位（质检第 14 项备用）

## 观复（进行中——8/14 用户拍板『妈妈不参与——直接搭建』）

### 8/14-15 已落地（git 提交可溯）

- [x] 20 问研讨收官（Q1-Q20 全定案，docs/观复研讨20问.md + 桌面 docx 已交付）
- [x] Q14-Q20 定案逐一落地（季度体检/增强仓/双轨止损/X证据链/低潮右侧化/人机分工/产品哲学反着来）
- [x] 观复架构 v2.0（Q20 收官版，docs/观复落地实施方案.md）
- [x] 策略库 v2 父母样例（47 知识点 + B/S/P/R/N 全套，docs/观复策略库_父母样例.md）
- [x] 5-10 万操作方案 v1.1（Q4 v2 修正——集中优质，桌面已交付）
- [x] M1.5 策略引擎（task_plan.md）：data/indicators/filters/market_status/morning_brief 全过 + 18 单测
- [x] strategy_score 动态打分（Q12：价值40/估值30/技术20/票源10 + 硬否决）
- [x] core_loop 每日循环骨架（数据→打分→信号真实运行）
- [x] 基本面数据管线（新浪三表+东财分红——价值面 40 分真实：平安 78.5/中信 77.7）
- [x] 本地模型栈定稿（Ollama+qwen3:8b+qwen2.5vl:7b+whisper+BGE-M3 ~14GB，回家装）
- [x] 蓝本：daily_stock_analysis（61k⭐）+ DeepFund + token-optimizer-mcp；4433 已记

### 待办

- [ ] **战术层回测**（前置：回测框架精读 backtrader/VectorBT——walk-forward 验证 B3 三重确认/S2 周布林降本——达标才启用，红线）
- [ ] 集思录 cookie（用户会给）→ cb_strategy 7 扩展策略全可用
- [ ] 爸妈书 → 策略库 YAML 提炼（47 知识点已列，翻译待做）
- [ ] 9 个数据工具迁移（a-stock-data 等 → data_provider/，清单在观复规划.md）
- [ ] 虚拟盘 10 万搭建 + 最便宜云服务器（2核2G 30-50 元/月）
- [ ] 晨报 9:00 定时推送（复用 Go购 企业微信通道）
- [ ] 大V vpush 自动方案（60+ 名单 + 分级保障 + ProxyCat 备胎链）
- [ ] 本地模型回家一次装齐（14GB）

### 8/14 已就位（小布落地 + Pi 抽查验证）

- [x] cb_strategy 可转债 13 策略（东财免费源 1049 只实测）
- [x] behavioral_diagnosis 行为诊断 6 维度（处置效应等——虚拟盘纪律达标用）
- [x] risk_engine 风控 13 指标 + 3 风险检查器（signal.py 缺失已补齐）
- [x] 大V 爬取精读（xueqiu-scraper 半自动/weiboSpider 备选——源链确认）
- [x] textsnap 整图直读打通（PaddleOCR-VL-1.5——134 张原照批量 OCR）

## 工具/技能

- [x] easy-vibe/vibe-coding-cn（~/ref/）
- [x] 39 skill 分类检查完成（9 工具待迁观复，29 角色正确，humanizer 保留）
- [x] 技能路由表 + 安装前分拣原则已入 MEMORY.md
- [x] humanizer_scorer.py 已入 tools/（雕龙质检第 14 项）
- [x] tech-stack 补记：SQLite FTS5 优先于向量库（2026-08-15）
- [x] codebase-memory-mcp **已装已测**（8/13 晚：~/codebase-memory/ v0.10.3——Go购 6 秒索引/search 1.1 秒——备用引擎，Pi MCP 接入待需要时研究）
- [x] ~~Paseo~~ 已删除（8/13 晚小布确认未装建议删项；单 AI 流程不需要）
- [ ] BGE-M3 2GB 下载（回家）

## 个人事务（重要，勿忘）

- [x] **实验室申请简历**（MetaEvo）——8/13 晚已投递（防露馅版 v6+：AI 协作开发口径）
- [x] 班干部面试——8/15 已完成
- [x] 暑假作业——4/5，01 照片已补（8/15 完成）
