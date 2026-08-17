I have enough evidence. Compiling the review.

## 架构+Agent工程审查报告

> 证据范围：docs 四件套（架构师复盘报告/待办综合方案/技术方案/验收清单）+ 实际代码 22 个模块逐行核对 + 测试实跑（185 collected / 1 fail）+ git 状态。所有结论带 `文件:行号`。

### 1. 维度打分（0-10）

| 维度 | 分 | 一句话理由 |
|---|---|---|
| 架构成熟度 | **7.5** | 五层信任链/事件日志/验证纪律是真架构；但 SIGNALS 注册表是"文档型"非"特性开关"，S2 enabled 却零运行时接线 |
| 可观测性 | **6.5** | diag.jsonl/breaker/数据源状态段齐全且真实；但 xq 熔断是死代码、core_loop 仍 5 处静默 except、定时任务无 LastRun 自动核验 |
| 数据层 | **7.5** | tushare 主源(2000分已购)+baostock+百度+巨潮链条真实、东财 1s+抖动节流、SQLite 增量缓存、双源 >20% 标 conflict——无源健康度持久化 |
| 安全 | **7.0** | token 走 .env 不入库、xq_cookies 明确不备份且被 .gitignore 覆盖、gf_web 仅 127.0.0.1、大V 内容当前零 LLM 处理（注入面未开）；.env.example 缺 2 个 key 文档 |
| 规划合理性 | **7.5** | 红线门槛（判定后启用）正确；14 项中 2 项可砍（家人共享/桌面应用）、3 项可合并、1 项已半落地（大V 可信度）、1 项已闭环（tushare 付费） |
| 演进路径 | **7.5** | MVP→二期→三期全带验证闸门、dsh 底座候选、本地模型边界诚实；但二期 14 项一次铺开缺排期权重 |

---

### 2. 发现（🔴/🟡/💭）

**🔴 F1：雪球熔断器是死代码——每日主抓取路径的失败从不计数**
- 症状：`tools/strategy_engine/xq_track.py` 的 `_api_get()`（L85-98）调用 `_xq_fail()` 计熔断，但**全库 grep 无任何调用方**；真正的每日路径 `track()`（L205-260）/`fetch_posts()`（L400+）/`resolve_cubes()` 的失败全是 `except: pass`，不 record_fail。
- 来源：breaker 接入时只改了入口 main()（L450 `is_tripped("xq")`），漏了失败计数点。
- 后果：文档宣称"当日失败≥5 熔断防刷接口"（待办方案 L108 书精读新五项②）对雪球实际不生效——cookie 过期/接口 400 会静默零更新。**对照 wb_track.py `_run_cli`（L62-80）正确 record_fail("wb")——同一承诺两种实现。**
- 药方：`track()`/`fetch_posts()` 的 except 分支统一 `_xq_fail()`，30 分钟。

**🔴 F2：backup 覆盖缺口——两个新模块的关键数据不进备份**
- 症状：`tools/strategy_engine/backup.py` BACKUP_FILES（L15-37，16 项）缺 `xq_posts.jsonl`（观点型大V 发言，08-17 新增模块，重抓需登录态+id 去重集合）和 `failed_track.jsonl`（失败票黑名单，`failed_pool.py` L19——书 L2540 行为约束）。
- 来源：备份清单 08-16 定稿，08-17 新增 failed_pool/xq_posts 后未同步清单。
- 后果：丢了黑名单=买回纪律重置（真金白银层面）；丢 xq_posts=发言历史全丢。`data/backup/20260817/` 实测 13 文件，正是缺这两个。
- 药方：BACKUP_FILES 加 3 行（含 review_history.json——Q14 观察连季记录），5 分钟。

**🔴 F3：测试套件不再"全过"——真实失败 + 状态耦合**
- 症状：`tests/test_v12_modules.py::test_dashboard_alert_on_cash`（L56-60）断言"现金偏高→告警"，假设"当前 78%"——但 f0e9ecb（投完现金决策落账）后 `data/portfolio.json` 现金=8,981/80,000（11%），`risk_dashboard.py` L74-76 阈值 >15% 不再触发 → **assert False 实测复现**。验收清单"163 测全过"已过期（实为 185 collected）。
- 来源：测试读真实 portfolio.json（无 mock），业务状态变了测试就碎。
- 后果：CI/commit 前自检（技术方案 L178 红线）不可信；下次改 dashboard 无法分辨"我的改动坏了"还是"状态又变了"。
- 药方：测试注入固定 portfolio（monkeypatch Portfolio），断言逻辑而非实时数据。已存在同类好先例（test_weekly_equity_png_generated 的 monkeypatch 法）。

**🟡 F4：SIGNALS 注册表=目录而非特性开关——注册制意图未闭环**
- 症状：signals.py L205-253 定义了 5 条含 status，注释宣称"回测/核心循环/文档按注册表遍历"（L200）——实际：`core_loop.py` `_b3_from_kline`（L95-120）硬编码 `sg.b3_triple_confirm`，从不读 `SIGNALS["B3"]["status"]`；**S2（status=enabled）全库无任何运行时调用方**（grep 仅 backtest.py/sell_rules.yaml/signals.py）；`holdings_review.py` 不遍历注册表；`list_signals` 仅被 backtest.py L352-361 用于注册校验。
- 来源：08-15 注册制重构只做了"登记+回测校验"层，运行时接线仍是散装 if/else。
- 后果：①"候选/否决"状态无执行约束——新信号忘接/误接无注册表兜底；②文档与事实漂移（S2 标 enabled 但从未在晨报/周报/盯价中跑）。
- 药方：core_loop/holdings_review 改遍历 `list_signals(status=="enabled")`；S2 要么接线进 weekly/price_watch，要么注册表标"候选——待接线"（诚实优先）。

**🟡 F5：定时任务失败恢复停在"文档教训"，无代码核验**
- 症状：一次性触发器 bug 的教训只写在 docs/观复待办综合方案.md L169-172（"注册后必须查 LastRunTime"）；全库 grep `ScheduledTask|LastRun` 零代码命中。且晨报新鲜度告警（morning_brief.py L137-160）**寄生在被监控对象内部**——GFBrief 任务死了，没人发"晨报没来"的告警（自指环）。大V 净值快照段（L152-157）只打 `ℹ️` 无过期阈值。
- 来源：运维纪律靠人记，未制度化。
- 后果：xq/wb 两个 16:00 任务静默死亡的最大观测窗口=用户注意到为止；cookie 过期（xq_a_token 约 30 天）同样无主动探测。
- 药方：晨报加"昨日 brief.log mtime"自检段（10 行），或独立 watchdog vbs；xq_nav 最后快照 >3 天转 `⚠️`。

**🟡 F6：core_loop 仍有多处静默 except——"except:pass 不再静默"只做了门面**
- 症状：书精读新五项①宣称落地（114fed5），但 `core_loop.py` 内 L108（B3 计算失败）、L162（入队失败）、L175（推送失败）、L193（质量检查失败）仍是裸 `except: pass`——无 log_diag。diag 接线只覆盖了 morning_brief/weekly_report 的段级 try。
- 后果：每日循环里静默掉的不只是"边缘错误"——入队失败=信号丢失用户不知道（违反复盘报告自己写的 M3 教训）。
- 药方：4 个 except 各补一行 `diag.log_diag("core_loop", ...)`。

**💭 F7：gate_check Alpha 门槛是软闸**
- `gate_check.py` L250-260：归因数据不足（alpha_positive=None）时 4 周跑赢**仍通过**，只标注"Alpha 待确认"。与"Alpha>0 才通过判定"（验收清单 N-1）字面不符——按设计可接受（先到为准兜底），但 9/12 判定时若归因数据不足，验收口径需提前对齐。

**💭 F8：测试套件非封闭——全量 pytest 跑 10 分钟挂起**
- `test_fund_flow.py` 实打 live akshare 接口（43.7s）；全量跑卡在约 38% 超时。docs 口径"全过"不可复现为快速绿灯。建议网络测试统一 `@pytest.mark.network` + 默认跳过或 mock。

**💭 F9：小项**
- `.env.example` 缺 TUSHARE_TOKEN/WEIBO_CLI_TOKEN（data_tushare.py L20、wb_track.py L25 都读但无文档）——新机配置要考古。
- `notify_gf.py` push_with_pic（L139-157）手写 .env 解析器——与 data_tushare/wb_track 重复三份，未来加 key 要改三处。
- `run_xq_track.vbs`/`run_wb_track.vbs` 用裸 `python`（PATH 依赖），brief/weekly 用全路径——两种风格并存，PATH 变了 xq/wb 静默失败。
- `.pi-subagents/` 未 gitignore（本会话产物入工作区）。

---

### 3. 二期规划裁决（14 项）

| 二期项 | 裁决 | 理由 |
|---|---|---|
| Bull/Bear 双视角 | **保留** | 二期锚点；DeepSeek flash 成本可控（技术方案 L584-590 三阶段演进定案） |
| 大盘择时层（六亿指数温度+月九转） | **保留+提前** | 是 market_status 的增强而非新系统；六亿已在 POST_TRACK（xq_track.py L34）；月九转与 TD Sequential 同源（indicators 已有）——**虚拟盘 4 周等待期即可开工**，不必等判定 |
| 大V 可信度评分（Q17） | **保留（已半落地）** | trust_level（xq_track.py L333）+ score_bigv（bigv.py）已存在且周报已显示贴近度——二期只做"两套合并为统一证据账本"，工作量减 70% |
| 基金筛选+讲解（4433） | **保留** | WealthAgent 8 层分类蓝本就位（技术方案 L743） |
| 基金 T+1 订单 | **合并** | 并入基金模块，不独立立项 |
| 大V 发言 LLM 解读（防注入） | **保留（排期靠后）** | 前置：①F2 补 xq_posts 备份 ②xq_posts 积累 ≥1 个月样本；external_content 证据指令隔离（待办 L118）设计正确，落地时 LLM 只能"总结引用"不能"执行指令" |
| 搬砖降本（Q13/Q18） | **保留（先回测）** | 有 idea_backtest 通道（A 标准裁决 L215-229）——小七规则已走通流程，搬砖/网格同法裁决后再进候选池；与"网格降本"合并 |
| 云服务器评估 | **保留** | 判定通过日启动的触发点正确；**建议评估内容含"定时任务监控/告警"**（回应 F5）——单机 Windows 调度的脆弱是当前最大运维痛点 |
| S3 右侧买回研究 | **保留（研究项）** | 现状仅招行有效（signals.py L154-156 十年回测）——样本需扩，归入 Q11 校准清单 |
| 可转债增强仓日历提醒 | **保留** | cb_strategy 已逐字节移植 + kzz.ics 源现成，成本低 |
| 黄金盯价 | **合并** | 就是 price_watch 加 2-3 个黄金 ETF 代码（518880/159934）——半小时，不配独立项 |
| 创业板/科创板 ±20% 涨跌停 | **砍**（并入 backtest 参数化） | 一次参数调整（backtest.py `_limit_blocked` 现为固定 10%）——非独立工作项 |
| 家人共享评估 | **砍** | 范围蔓延；真钱稳定前无讨论基础 |
| 知识文档周期修剪 | **保留（季度级，最后做）** | 纯运维低价值；backup 只备份不整理已是现状，设固定季度提醒即可 |

**三期修正**：① tushare 付费 **已闭环**（data_tushare.py L11 "2000 积分已购 08-15" + data.py L168 "主源切换 08-17"）——从三期清单移除；② 鹿鼎公实盘图视觉读取 **降级为"文字/手动录入优先"**——8/23 体验包评估先行，VL 读图 ROI 低（抄作业=调仓数字，图只是展示载体，TA-Lib 数值路径已覆盖形态）；③ 桌面应用评估 **砍**——gf_web 127.0.0.1:8201 + 手机推送已满足使用场景。

---

### 4. 总评 + 最该先修 3 件事

**总评**：架构师复盘报告 8.3 分大体公允——信任链分层、验证纪律、事件日志、防前视是真实资产（我逐一核对过代码，不是文档吹嘘）。**但报告没看见的 3 个真相**：①注册制是"登记册"不是"开关"，S2/S3/B3 的运行时接线是散装的，feature-flag 承诺兑现了一半；②可观测性外衣下有两处硬伤——xq 熔断死代码、定时任务无自动核验（"静默失败比失败更危险"是它自己写的 M3 教训，而最可能静默失败的正是调度层）；③"163 测全过"已失真（185 collected 1 fail，全量还跑不完）。二期 14 项整体合理，但**砍 2 项、合并 3 项、提前 1 项（大盘择时）、1 项已闭环（tushare 付费）**后，真实工作量约 8 项，且全部可以并行于虚拟盘等待期（9/12 前），不必等判定。

**最该先修 3 件事**：
1. **修复 xq 熔断死代码 + 补 xq 失败计数**（xq_track.py track/fetch_posts/resolve_cubes 的 except 分支 `_xq_fail()`）——30 分钟，恢复"防刷接口/防静默失效"承诺；顺带把大V 净值快照过期改 `⚠️` 阈值。
2. **backup.py 补 3 个文件**（xq_posts.jsonl / failed_track.jsonl / review_history.json）——5 分钟，堵住"黑名单纪律丢失"和"大V 发言历史丢失"。
3. **修 test_dashboard_alert_on_cash 状态耦合 + 让 SIGNALS status 真正约束 core_loop**（遍历 enabled 替换硬编码 B3）——半天，同时恢复"全过"可复现性和特性开关真实性。

---

## Review
- Correct：五层信任链/事件日志/双源交叉/防前视/熔断+diag 骨架/备份排除敏感文件/127.0.0.1 绑定——全部代码级核实为真；gate_check 已含红利风格对照（复盘报告 P1 已落地）。
- Fixed：无（review-only，未改任何文件）。
- Blocker：F1（xq 熔断死代码）、F2（备份缺口）、F3（测试失败）——均不影响 9/12 判定，但应在二期开工前清掉。
- Note：F4-F6 是成熟度差距而非错误；F7-F9 为小项。`.pi-subagents/` 未 gitignore 建议补。