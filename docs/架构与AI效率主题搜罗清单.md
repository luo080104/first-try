# 架构隐患 + AI 效率主题搜罗（2026-08-11 晚，第一轮）

> 8 主题：code-quality/static-analysis/technical-debt/refactoring/code-review/ai-coding/llm-tools/prompt-engineering

## 🔴 精读候选（8 个）

### 架构隐患排查类

| 候选 | ★ | 价值 | 来源主题 |
| --- | --- | --- | --- |
| **tirth8205/code-review-graph** | 29848 | 本地代码智能图（MCP/CLI）——依赖图/隐患可视化，**架构排查直接工具** | static-analysis/code-review |
| **semgrep/semgrep** | 16189 | 多语言轻量静态分析（找 bug 变体/漏洞）——比 ai-review-cli 更强 | static-analysis |
| **The-PR-Agent/pr-agent** | 12492 | 开源 PR 审查器（agent 自动审 PR）——三 agent 代码审查升级 | code-review |
| **repowise-dev/repowise** | 5136 | 代码库智能：健康评分/架构指标——**技术债可视化** | technical-debt |

### 高效 AI 工具类

| 候选 | ★ | 价值 | 来源主题 |
| --- | --- | --- | --- |
| **usestrix/strix** | 51303 | AI 渗透测试工具（找并修漏洞）——安全防线升级 | code-quality |
| **oraios/serena** | 27890 | MCP 语义检索编码工具包——让 agent 精准找代码 | ai-coding |
| **headroomlabs-ai/headroom** | 65996 | 压缩工具输出/日志/RAG 块——**省 token**（比 RTK 更广） | prompt-engineering |
| **zilliztech/claude-context** | 12386 | 代码搜索 MCP（整个代码库做上下文）——大项目 context 管理 | ai-coding |

## 🟡 备选（按需再深读）

- pre-commit（15502，提交前检查框架——CONSTITUTION 工具化）
- github/scientist（7748，安全重构验证）
- reviewdog（9518，自动审查集成）
- adamtornhill/code-maat（2623，git 数据挖掘技术债）
- asottile/git-code-debt（621，代码债仪表盘）
- super-linter（10543，多 linter 组合）
- latitude-llm（4578，LLM 监控平台）
- modem-dev/hunk（8245，审查优先 diff 查看器）
- backnotprop/plannotator（7669，agent 计划审查可视化）
- 已装确认：rtk（75798）/ ponytail（101029）/ caveman（97583）已在我们的工具箱 ✅

## 与现有工具的互补

| 我们已有 | 本次发现升级 |
| --- | --- |
| ai-review-cli（DeepSeek 审查） | semgrep（确定性静态分析）+ pr-agent（PR 审查） |
| pi-lens（LSP 反馈） | code-review-graph（依赖图/架构隐患） |
| RTK（bash 压缩） | headroom（工具输出/日志/RAG 压缩——更广） |
| hermes-memory | serena/claude-context（代码库语义检索） |

---

## 九、8 个精读完成（2026-08-11 晚）

| 候选 | ★ | 精读结论 | 落地 |
|---|---|---|---|
| **semgrep** | 16189 | **实战跑通**：扫 Go购 db.py 发现 7 个 SQL 拼接警告（白名单模式多误报但值得复核）——确定性静态分析，免费快速 | ✅ **装**（pip 已装 1.172.0，替代/补充 ai-review-cli） |
| code-review-graph | 29848 | Tree-sitter 结构图+增量追踪+MCP——审查省 token 71 倍（flask 全库 143K→2.2K） | 📌 大项目适用（我们项目小，价值中等） |
| headroom | 65996 | 语义压缩层（工具输出/日志/RAG）+ **可逆 CCR**（原文缓存可取回）——压缩率 92% | 📌 参考（context-mode 已覆盖；可逆思路借鉴） |
| serena | 27890 | MCP 语义检索/编辑/重构——符号级抽象（不靠行号）——"IDE for coding agent" | 📌 参考（MCP 需手动配；我们项目小） |
| pr-agent | 12492 | 开源 PR 审查器（Qodo 社区版）——GitHub/GitLab 集成 | 📌 参考（我们本地 git 流程，code-reviewer skill 已覆盖） |
| repowise | 5136 | 代码健康评分+5层索引+**Change risk**（合并前风险）——AGPL | 📌 change risk 思路借鉴 |
| strix | 51303 | AI 渗透测试（自主黑客找漏洞修复） | 📌 安全栈已有（semgrep+审查）；渗透测试过重 |
| claude-context | 12386 | 向量库语义搜索 MCP——大代码库成本优化 | 📌 与 serena 同类（参考） |

## 落地清单
1. ✅ **semgrep 已装**（pip 1.172.0）——加入日常：`semgrep --config auto src/` 快速静态扫描
2. 📌 复核 db.py 的 7 个 SQL 拼接警告（确认白名单安全）
3. 📌 headroom 可逆压缩思路 → context-mode 增强参考
4. 📌 change risk（合并前风险）→ 已在我的 security-auditor 底线清单（同思路 ✅）
