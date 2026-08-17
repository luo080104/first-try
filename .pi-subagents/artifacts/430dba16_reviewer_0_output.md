All verification complete. Compiling the report.

## 规划落地一致性报告

**审查范围**：docs/观复待办综合方案.md、观复技术方案.md、观复落地实施方案.md、架构师复盘报告.md、观复验收清单.md ↔ tools/strategy_engine/ + data/
**注意**：`plan.md` 不存在（ENOENT）——progress.md 引用的实为 `task_plan.md`。审查以 progress.md + 五份 docs 为准。

---

### 1. 一致性矩阵：规划项 | 声称状态 | 代码证据 | 实际状态

| 规划项 | 声称 | 代码证据（文件:函数） | 实际 |
| --- | --- | --- | --- |
| 晨报 17:00 日报 | ✅ M3-1 | notify_gf.py:81 `push_brief`（工作日 17:00 收盘总结）；morning_brief.py:128 `build_brief`；GFBrief 定时任务 Ready（StartBoundary 08-17T17:00，DaysOfWeek=62 工作日）| ⚠️ 机制全在，但今晨 09:32 一次运行崩溃未推送（见发现 1） |
| 持仓今日真实盈亏 | ✅ | morning_brief.py:156-181 【持仓今日】→ portfolio.py:164 `positions`（pnl/pnl_pct 逐持仓） | ✅ |
| S4 公告监测 | ✅ N-8 段 | s4_monitor.py（巨潮关键词 STRONG_KEYWORDS：减持/质押/立案…）+ morning_brief.py:202-208 挂载；data/s4_alerts.jsonl（1 条） | ✅ 模块+接线在；触发记录少（1 条——待积累） |
| B2 大V观察段 | ✅ | weekly_report.py:239 「📡 大V 观察」+ :292 观点型发言分组；xq_track.py/wb_track.py 数据源 | ✅ |
| B5 估值温度 | ✅ | filters.py:64 `check_valuation`（PE<15/PB<2+百分位<10%）+ market_status.py `_rate_fair_pe`/PE 百分位 | ✅ |
| S3 v2 启用 | ✅ | signals.py:148 `s3_valuation_exit`（v2：百分位>80 且破 6 月均线→减仓 1/3）；SIGNALS["S3"] status=enabled | ✅ |
| 行业面 | ✅ 一期 | industry.py:score_industry（格局8/位置6/周期4/政策2=20 分）+ strategy_score.py:139 `_score_industry`（0-120 总分）+ holdings_review.py:163 接线 | ✅ |
| 失败票黑名单 | ✅ | failed_pool.py（record_sell/check_rebuy）+ data/failed_track.jsonl（2 条）+ git 2f77a0a | ✅ |
| 诊断日志 diag | ✅ 新五项① | diag.py `log_diag`→data/diag.jsonl + test_diag.py | ⚠️ 模块+测试在，但只接晨报路径；**data/diag.jsonl 不存在**（从未写入——崩溃路径在防护之外，见发现 3） |
| 熔断 breaker | ✅ 新五项② | breaker.py（record_fail/is_tripped→data/breaker.json）+ xq_track.py:110-119/577-581 + wb_track.py:54/77-81 + test_breaker.py | ✅ 接线完整（data/breaker.json 无——未触发过，合理） |
| 大V跟踪 xq_track/wb_track | ✅ N-4/N-5 | xq_track.py（雪球 4 接口 API）+ wb_track.py（微博官方 OAuth）+ data：xq_cubes.json(54)/xq_posts(47)/wb_statuses(407)/bigv_trades(239)+GFXQTrack/GFWBTrack Ready | ✅ |
| 周报 HTML | ✅ N-7 | weekly_report_html.py `build_html`→data/weekly_report.html + gf_web.py:225 `/weekly` 路由 | ✅ |
| 备份 backup | ✅ N-6 | backup.py:46 `daily_backup`（30 天清理）+ notify_gf.py:90 挂载 + data/backup/20260816/20260817（13 文件快照）+ test_weekly_report.py:46 | ✅ |
| M1-1 回测 10 年 3 策略 | ✅ | backtest.py（自写引擎）+ test_backtest_pairing.py（97% 丢失修复）+ signals.py B3 定案 docstring | ✅ 模块证据在；78.9%/80.3% 胜率数字存于文档未重跑复验 |
| M1-2 防未来函数 | ✅ | backtest.py:51 `tm_year` 动态起点 + :172 `_limit_blocked` + 事件配对重构 | ✅ |
| M1-3 数据降级链 | ✅ | data.py 多源链 + morning_brief.py:56 `_data_source_status`（状态段显式） | ✅ |
| M2-1 8 万虚拟盘 | ✅ | data/portfolio.json init_cash=80000，8/15 太保/平安/中信；**8/17 增华电 6500 股/招行 500 股（现 5 持仓）** | ✅ 但"3 持仓 22.3%"描述已过时 |
| M2-2 连续 2 周无人工干预 | 🔄 8/30 复核（文档自认"从未正式核验"） | 无专门核验脚本/日志——brief.log 为唯一运行痕迹 | ⚠️ 计划诚实（未声称已完成）；但今晨崩溃已在观察窗口内，8/30 复核必须计入 |
| M2-3 4 周跑赢+Alpha>0 | ⏳ 9/12 | gate_check.py（CONSECUTIVE_WEEKS=4 + 归因 Alpha>0 判定）+ portfolio.record_equity 净值积累 | ✅ 机制在，判定未到期 |
| M2-4 信号确认闭环 | ✅ | core_loop.py:217-222 达标信号→confirm.append_pending + confirm.py 状态机 + signal_ledger.py | ✅ |
| M3-2 周报 15:30 | ✅ | GFWeekly Ready（Friday 15:30）+ weekly_report.py | ✅ |
| M3-3 行为画像段 | ✅ | weekly_report.py:120/146/226（Q10 纪律检查段） | ✅ |
| M3-4 风险提醒 | ✅ | risk_dashboard.py + gate_check Alpha 归因 | ✅ |

### 2. 红线机制核查表

| 红线 | 规划出处 | 代码机制 | 结论 |
| --- | --- | --- | --- |
| 未验证不落地 | 落地实施 §四 + Q6 | SIGNALS 注册表 status 字段（enabled/候选/否决——signals.py:205-252）+ verify_book_rules.py 回测前置 + B3_VARIANTS 否决项登记 | ⚠️ 半强制：注册表是登记制，core_loop.py:111 **直接硬编码调 `b3_triple_confirm`**，不走 `get_signal/list_signals(status="enabled")` 过滤——新信号接入时不注册也不报错 |
| Q6 失效条件 | Q6 定案 | signals.py:159-161 S3 数据缺失→"不触发（宁可不卖不可乱卖）"；B3 数据不足→False | ✅ |
| 不自动卖 | 技术方案 §九 + 确认层 | core_loop.py:218-222 信号只进 confirm 待确认队列；portfolio.sell 仅人工调用；S3 desc 明示"建议级不自动卖"；s4_monitor docstring"只提醒不自动卖" | ✅ 机制成立 |
| eval_buy 强制入口 | 8/17 甲方要求 | holdings_review.py:135 `eval_buy`（全体系：打分+技术+估值+8 标准+否决+行业面） | ⚠️ 约定性入口非强制 gate：core_loop.py:189 走独立的 `score_stock` 路径，两条买入评估路径并存，无代码校验"买入必须过 eval_buy" |
| 确认状态机 | dsh 审批策略 | confirm.py：pending/confirmed/ignored 三态 + 幂等去重（:47）+ signal_ledger verified/pending 验证态 | ✅ |
| 合规底线 | 大V 定案 | xq_track.py 头注释"只抓公开可见数据不碰付费"、wb_track.py"官方开放平台 API OAuth" | ✅ 文档级承诺（无代码强校验——外部合规以公开数据/官方 API 为前提，可接受） |

### 3. 发现

**🔴 F1 — 日报首段无防护，崩溃即整报丢失（8/17 实锤）**
- 症状：今日 09:32 运行 `push_brief` 在 build_brief 第 1 段崩溃——brief.log 尾部完整 traceback：`morning_brief.py:136 ms.market_status()` → `data.py:216 tencent_quote` → `urllib.error.URLError [WinError 10053] 连接被中止`。备份已写（backup/20260817 09:32）但日报未推送。
- 来源：morning_brief.py:136 大盘段未包 try/except（其余 9 个段都有），market_status.py:110 内部也无 tencent_quote 防护；无重试/降级。
- 后果：M3-1"晨报全自动"与 M2-2"无人工干预"观察窗口内已出现失败；失败仅留在 brief.log，无推送告警、无 diag 记录——接近静默失败（Go购 红线③同类）。
- 药方：build_brief 首段包 try/except + diag 记录；market_status 的 tencent_quote 加 1 次重试或降级源。

**🔴 F2 — "全量测试通过"红线当前不成立**
- 症状：`pytest --collect-only` → **196 collected + 1 ERROR**：`test_jd_detail.py - KeyError: 'jd_union_open_goods_material_query_respo...'`。
- 来源：验收清单声称"当前 163——全量通过"；根目录 JD 项目测试文件污染收集（非观复模块）。
- 后果：质量红线①（全量测试通过）无法满足；"163 测全过"为过时数字。
- 药方：修 test_jd_detail.py 的 fixture/密钥依赖，或 pyproject 排除 JD 测试。

**🟡 F3 — diag 只接晨报，周报/回测路径未接线**
- 症状：`grep -rln log_diag` 仅命中 diag.py 与 morning_brief.py；规划（新五项①）称"晨报/周报/回测关键路径"。data/diag.jsonl 不存在。
- 来源：书精读新五项①落地为部分接线。
- 后果：周报/回测失败仍静默；F1 恰暴露该缺口。
- 药方：weekly_report.py/backtest.py 失败分支补 log_diag。

**🟡 F4 — SIGNALS 注册表非强制 gate**
- 症状：core_loop.py:111 硬编码 `sg.b3_triple_confirm`，未过滤 status；注册表更多是"文档化登记 + 回测工具遍历"（B3_VARIANTS 供 make_buy 工厂）。
- 后果："未验证不落地"依赖纪律而非代码——二期新增信号时可能绕过登记。
- 药方：core_loop 改走 `get_signal("B3")` + status 检查；或接受为轻量登记制并标注。

**🟡 F5 — bigv_trades 含历史回填，与"每日自动"口径混**
- 症状：data/bigv_trades.jsonl 239 条中 ts 年份分布 2016×3/2019×3/2021×1/2022×16/2025×12（共 35 条 <2026），首条 ts=2016-08-30 sys_rebalancing。
- 来源：雪球组合调仓历史回填（首次抓取拉全量）。
- 后果：周报大V 段统计"本周调仓"若不过滤旧 ts 会失真。
- 药方：统计侧按 ts≥本周过滤（检查 weekly_report.py:239 段是否已过滤——未确认）。

**💭 F6 — M2-1 描述过时**：portfolio.json 现 5 持仓（8/17 落账华电/招行，git f0e9ecb），验收清单仍写"3 持仓 22.3%"。

**💭 F7 — 二/三期衔接预留**：SIGNALS 注册制（dict+list_signals+get_signal+status+**min_cash 字段**——架构师 B1 已落地）、B3_VARIANTS 工厂、signal_ledger verified/pending 轻量状态机、confirm 三态——二期信号扩展/三期满仓都留有扩展点；"信号状态机"是轻量版而非完整状态机，够用。

### 4. 一致性打分：**7.5/10**

- 加分：13/14 功能项有真实代码+数据+定时任务三重证据（xq/wb/backup/breaker/diag/行业面全部可指认函数与数据文件）；红线"不自动卖"机制真实成立；M2-2 未核验的事实被文档诚实标注（8/30 复核是计划不是谎报）。
- 扣分：两处 🔴（日报崩溃路径、测试红线失效）都是"声称全自动/全通过"与实际运行证据的直接冲突；红线中两条（未验证不落地、eval_buy 强制）是登记/约定级而非代码强制级。
- 结论：**规划与落地主体一致，可信度高；但"全自动无干预"叙事被今日实崩戳破，M2-2 复核必须把 8/17 崩溃计入失败，且修复 F1/F3 后 diag 才真正闭环。**

---