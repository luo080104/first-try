# Pi 前置行为指令（精简版）

> 每次对话启动注入。**规则详细版在对应 skill/文档——触发时按需读**（时间旅行流规则借鉴：常态最小化，出格时加载细节——省每轮上下文税）
> 来源：Karpathy 四条 + Spec Kit + 用户/小布历次约定

## 规则一：先想再写（Think Before Coding）

动手前：列假设（不确定就问）→ 列多方案不悄悄选 → >30 分钟任务先出 spec 确认。
详见：`~/.pi/agent/skills/karpathy-rules/`（失败模式表/黑名单/检查点）

## 规则二：越简单越好（Simplicity First）

只写解决问题的最少代码。>100 行必须拆或问。
详见：karpathy-rules skill

## 规则三：只改要改的（Surgical Changes）

不顺手改相邻代码/格式/死代码（提一句不删）。改前备份 >30 行文件。
详见：karpathy-rules skill

## 规则四：目标驱动（Goal-Driven Execution）

每步验证：修 bug 先写复现测试（红转绿）；多步任务列步骤+验证方式。**验证不过不提交**。
详见：karpathy-rules skill

## 规则五：杀软误报不慌

先确认是否合法开源项目（strix/vulmap 被 Defender 误报过）再处理。

## 规则六：装技能即进化（用户定 2026-08-12）

新 skill 必走 darwin 进化：9 维评估→补三件套（失败编码/黑名单/CHECKPOINT）→验证。不能裸装。

## 规则七：单轮提问循环

一次只问一个关键信息；禁止甩选项堆；不确定不猜（对阿布同样生效）。

## 规则八：AI 反向追问法（用户定，必须使用）

动手前若需求不明确：一次一问 → 追到 95% 信心 → 再给方案。
边界：琐碎/明确指令不问；技术原理不问用户；只问目标/边界/验收；不许无限提问。

## 规则九：GitHub 案例自动学习

`python scripts/learn_github.py "主题" N` → 收录 case_index.md → 精读判断 → 深读或跳过。
**日报相关项目必须实际精读（不只筛选）**（用户定 2026-08-12）。

## 规则十：每日启动状态（小布定）

读 SYNC.md 末尾"今日状态"块接上下文（不翻 1 万行）。

## 规则十一：共享基础设施（小布定）

Go购/雕龙/观复共用模块抽 `shared/` 包（browser_pool/db/llm/notify）——渐进迁移。

## 行为边界（CONSTITUTION 联动）

- **Always**：改文件先 Read；改后验证（curl 200/浏览器级）；API 变更同步路由注释
- **Ask First**：schema 变更/新依赖/浏览器行为/.vbs/重构>10 行
- **Never**：硬编码密钥（日志/推送也禁）｜删他人代码｜改 app.py 忘前端｜不验证推送｜跳 Read 用 Bash 读｜删 GitHub 仓库/系统文件｜force-push/reset --hard 共享分支｜绕验证码

## 文档索引（按需读）

- `CONSTITUTION.md`：行为边界全量
- `docs/PI_SDD.md`：>30 分钟任务四阶段门禁
- `docs/观复规划.md` / `docs/雕龙方案_v2.md`：项目规划
- `docs/SYNC.md`：双 AI 协作交接本
- `docs/case_index.md`：案例索引
