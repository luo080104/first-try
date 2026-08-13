# 当前进度（progress）

> 最后更新：2026-08-13 中午。Pi 每次工作后更新此文件 + SYNC.md。

## Go购（v2.0 收尾）

### 已完成
- [x] v2.0 交互打磨：纯卡片导航 / 陪你出发 / 商品库输入即搜 / 实时搜索计时 / 搜索历史
- [x] 8/13 全量审查修复：连接泄漏 22 处（with closing）、SSE 断线检测、遗留入口 DEPRECATED、crawl 装饰器确认、price_trend 10 分钟缓存
- [x] family_pin **前后端全链路**（后端 be21479 + 前端 8f0eb49：密码菜单 + 8 页面 15 处带 pin）
- [x] 导购模型切 Pro、对话上下文链路（session_id）
- [x] ruff 295→0、semgrep 清理、缓存 94%
- [x] Headroom 0.34.0 接入（proxy 8787 + env 开关 + dashboard 汉化 113 处）

### 待办
- [ ] git push 10+ 提交（热点 TLS 卡死，回家 WiFi 推）
- [x] Langfuse 接入已完成（8/12：key + @observe + shared/llm.py + 真实调用验证）——非待办（小布清单核对修正）
- [ ] Headroom kompress 模型 2.5GB 下载完 → 去 --no-optimize → 分批验证压缩
- [ ] 采集重跑（PDD 三板斧，等 WiFi/冷却）
- [ ] 手机端验证（等用户测试）

## 雕龙（暂停中）

- [ ] 方案 v1.4 就绪（9 模块+8 Hook+16 决策）——⑥ 质检已扩到 14 项（+人性化评分）
- [ ] lightnovel-crawler v4.14.0 已装（17 中文源）
- [ ] 待：找极道天魔真实 URL → 爬前三章 → 小布拆节拍写风格规范
- [x] diao-long 仓库已改名（luo080104/diao-long）——非待办（小布清单核对修正）
- [ ] tools/humanizer_scorer.py 已就位（质检第 14 项备用）

## 观复（缓办）

- [ ] 等投研平台积累 + 用户明确思路
- [ ] 蓝本：daily_stock_analysis（61k⭐）+ DeepFund + token-optimizer-mcp
- [ ] 4433 基金法则 + ETF 折溢价已记
- [ ] **9 个数据工具待迁移**（a-stock-data/westock-data/futuapi/stock-* ×3/macro-monitor/earnings-tracker）→ 启动时迁 data_provider/，清单在观复规划.md

## 工具/技能

- [x] easy-vibe/vibe-coding-cn（~/ref/）——⚠️ 修正：Paseo/tldr 实际未装（progress 记录错误，2026-08-13 核对）
- [x] 39 skill 分类检查完成（9 工具待迁观复，29 角色正确，humanizer 保留）
- [x] 技能路由表 + 安装前分拣原则已入 MEMORY.md
- [x] humanizer_scorer.py 已入 tools/（雕龙质检第 14 项）
- [ ] Paseo 未装（progress 曾误记已装）——如需要：装 + 配置
- [ ] codebase-memory-mcp 补精读（克隆失败，待网络好）
- [ ] BGE-M3 2GB 下载（回家）
- [ ] tech-stack 待记：SQLite FTS5 优先于向量库（轻量场景）

## 个人事务（重要，勿忘）

- [ ] **实验室申请简历**（MetaEvo，8/17 截止）——用户之前说 15 号左右交，还差简历撰写！
- [ ] 暑假作业：4/5 完成，第四项 AI 绘画不做，01 需要补照片
