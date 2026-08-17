# 代码审查报告

审查范围：`C:/Users/luoji/shopping-agent`，重点 tools/strategy_engine/ 核心模块 + tests/（37 文件 / 185 用例）。全程凭源码与实测证据（含一次实盘数据验证、全量测试运行），未验证项已标注。

---

### 1. 五维打分（0-10）+一句话理由

| 维度 | 分 | 一句话理由 |
|---|---|---|
| 正确性 | **6** | 核心纯函数与 S3 v2 双条件语义正确，但晨报 S3 与失败票黑名单两处把"最旧"周线当"现价"用（实测确认），且 0% 估值百分位被 `or 50` 误判、打分门槛被中性 10 分实际稀释到 70/100。 |
| 可读性 | **8** | docstring 先行、中文注释讲清"为什么"（书 L 编号/拍板日期），命名一致；仅个别诊断标签（"check as _gate_c"）与动作元组（"加仓"重复）有笔误。 |
| 架构 | **7** | 模块职责清晰、信号注册表/源链 fallback/纯函数传参设计得当；但行业面在 3 个打分入口只接 1 个、N 不买清单/B4/B5 过滤层在生产线无任何生产者。 |
| 安全 | **8** | token 走 .env（gitignore 覆盖）、雪球 cookie 落 `data/xq_*`（已忽略）、无硬编码密钥、账本原子写；残留仅本机明文 cookie 的可接受风险。 |
| 性能 | **6** | SQLite 缓存/节流/去重/合并拉取齐全；但 tushare 主源仍触发 baostock 全量交叉验证、基本面缓存仅进程内（每次 CLI 重拉全量）、去重全文件扫描 O(n²)。 |

---

### 2. 发现列表

**🔴1. 日报 S3 信号用"2 年前"的价格计算（现价/6月均线全是旧数据）**
- 症状→来源：`morning_brief.py:257-263` —— `_wk = data.bs_kline_weekly(_pos["code"], years=2)[:24]` 取的是**最早**24 根周线，`_last = _wk[0]["close"]` 取的是**最早**一根的收盘价。实测确认 `bs_kline_weekly` 返回升序（2026-08-14 实跑：first=2025-01-03 / last=2026-08-14），故 `[:24]`+`[0]` = 约 1.5–2 年前的行情。
- 后果：日报【S3 估值减仓提示】用 2 年前价格比对"现价<6月均线"——该信号随机失真（PE 百分位是当前值、价格是旧值），可能漏报或误报减仓提醒；此为每日生产路径，静默出错。
- 药方：`[:24]` → `[-24:]`，`_wk[0]` → `_wk[-1]`。

**🔴2. 失败票买回纪律同样比对 2 年前价格（同根因切片 bug）**
- 症状→来源：`failed_pool.py:93-103` —— `wk = data.bs_kline_weekly(...)[:24]`，`cur = wk[0]["close"]`（注释写"现价"）。布林下轨 mid/std 用 `reversed(wk)`（此处方向对），但 `cur` 取的是最旧收盘价。
- 后果：书 L2540"不到周线下轨不买回"的拦截判定比对的是 ~2 年前价格——纪律形同虚设且晨报会输出错误结论。
- 药方：`cur = wk[-1]["close"]`（或 `closes[0]`，与 reversed 逻辑统一）。

**🔴3. 120 制门槛 80 被"中性 10 分"实际稀释为四维 70/100，且两条生产打分路径根本不接入行业面**
- 症状→来源：`strategy_score.py:194-201`（`_score_industry` 缺失即返中性 10）；`core_loop.py:189` 与 `holdings_review.py:60` 调 `score_stock` 均**不传 industry**，唯 `holdings_review.py:163`（eval_buy）传。
- 后果：每日循环与季度体检中，每只票无条件白得 10 分（行业面 20 的 50%）；总满分 120、门槛 80 时，价值/估值/技术/票源四维实际过线只需 **70/100**（v1 为 80/100）——门槛被静默降低 10 分，"中性 fallback 不惩罚"的设计在两条主路径上退化为"人人加分"。任务点①的核心语义问题实锤。
- 药方：二选一——(a) core_loop/holdings_review 补传 `industry=score_industry(code)`；(b) 数据缺失时行业分记 0 并把行业维度从"加分制"改为"准入加分"，避免缺失即白得半满。

**🟡4. 买入评估/持仓重打分硬编码 `is_leader=True`（票源面白送 5 分）**
- 症状→来源：`holdings_review.py:59` 与 `holdings_review.py:155` —— `s = {"is_leader": True, "bigv_holding": False}`，与个股是否真在龙头池无关。
- 后果：eval_buy 是甲方强制的买入评估唯一入口，任何股票都被当龙头 +5 分，叠加 🔴3 的 +10，共 +15 虚分。
- 药方：用 `core_loop.load_leader_pool()` 实查代码是否在池内，`is_leader = code in pool`。

**🟡5. 硬否决层（N 不买清单 + 红线 + B4/B5 过滤器）在生产路径全部空转**
- 症状→来源：`filters.py:99-135` 的 N 规则依赖 `ps/price_from_low/holder_reduce/listing_years/recent_surge/sw_code` 等字段，全仓 grep 确认 **tools/ 无任何生产者**提供这些字段（tencent_quote 只给 pe/pb/price）；`check_redlines` 在生产调用处 `redlines={}`（`strategy_score.py:161`、eval_buy/holdings_review 均不传）；`filter_stock/check_valuation/check_value_8` 除测试外零调用。
- 后果：晨报宣称"基本面检查（不买清单）——观复会继续过滤"，实际否决分支永远不会触发——"烂票永远 0 分"目前只有测试里成立。
- 药方：要么为 N 清单补数据生产者（距低点涨幅/上市年数可算，减持/巨量需外部数据流），要么把"未接入"如实标注到讲解文本与文档，去掉"已过滤"暗示。

**🟡6. `or 50`/`or 100` 把合法的 0% 百分位当缺失值**
- 症状→来源：`strategy_score.py:150` `pct = v.get("pe_percentile") or 50`；`filters.py:127` `(v.get("pe_percentile") or 100) > 10.0`。
- 后果：个股 PE 处于历史最低（百分位真实 = 0.0）时，估值分从 10 变 5；B5 相对估值检查把"历史最低位"判成">10% 未到低潮"而否决——方向性错误。
- 药方：用 `is None` 判缺失（`v.get("pe_percentile"); if pct is None: pct = 50`）。

**🟡7. tushare 主源路径仍做 baostock 全量交叉验证；`ts_pe_pb_history` 单页截断未验证**
- 症状→来源：`data.py:265-277` —— tushare 成功后仍调 `bs_pe_pb_history(code)`（冷缓存 = 10 年日频全量拉取），这正是 2026-08-17 主源切换想规避的"baostock 挂起"风险，只是降级为"每次冷缓存补一枪"。`data_tushare.py:262` `daily_basic(..., limit=10000)` 单次调用在 tushare 分页/点数限制下是否只回一页（约 1000 行 ≈ 4 年）**未验证**——若截断，十年百分位窗口被静默缩短。
- 后果：S3/估值百分位的十年窗口可能不是十年；交叉验证成本抵消部分主源切换收益。
- 药方：验证 `daily_basic` 分页行为（必要时循环翻页）；交叉验证改为"每周一次且复用 SQLite 缓存"。

**🟡8. 测试有效性三处问题（1 个真实失败 + 真网络 + 弱断言）**
- 症状→来源：
  - `tests/test_v12_modules.py:57` `test_dashboard_alert_on_cash` 断言真实 `data/portfolio.json` 的现金告警——**本次全量运行实际失败**（185 收集，1 failed），依赖真实账本状态，属环境敏感测试而非逻辑测试；
  - `tests/test_market_status.py` 未 mock `_rate_fair_pe()`（`market_status.py:59`），每测真实调 akshare 债券接口——全量套件因此跑 9 分钟；
  - `test_market_status.py:test_high_market` 断言 `s["status"] in ["高潮", "正常"]`——两种结果都过，测不出判定逻辑。
- 后果：套件"绿"不代表逻辑对；失败测试长期存在会掩盖真回归。
- 药方：dashboard 测试改为 temp 账本 + monkeypatch；market_status 测试 mock `_rate_fair_pe`；弱断言收严为单值。

**💭9. `evaluate_tactical` 的 6 月均线在周线输入下是 ~27 个月均线**
- 症状→来源：`signals.py:186` `ma6 = sum(closes[-120:])/len(...)`——若 closes 为周线（B3 同源），120 根 ≈ 27 个月而非 6 个月。当前无调用方（grep 确认），属休眠入口，先标注。
- 药方：按输入频率显式换算（周线用 26 根）。

**💭10. 股息率口径偏松：最近 2 次分红可跨 2 年**
- 症状→来源：`fundamentals.py:157-160` `divs[:2]`（除息日倒序）求和 ÷ 现价，若两笔分红间隔近两年则股息率虚高；分红率同源。
- 药方：按除息日取最近 12 个月窗口。

**💭11. 雪球熔断漏计：`track()` 内失败只 `pass` 不 `record_fail`**
- 症状→来源：`xq_track.py:171-218` 的 try/except 仅 `pass`，未走 `_xq_fail()`——熔断器只对 `_api_get`/resolve 生效，track 主循环的连续失败不会触发"当日跳过"。
- 药方：except 分支补 `_xq_fail()`。

**💭12. 行为画像动作元组笔误**
- 症状→来源：`weekly_report.py:120-121` `("buy", "加仓", "加仓")` / `("sell", "减仓", "减仓")`——"加仓"重复且实际事件 action 只有 buy/sell，"加仓"分支永远不匹配。
- 药方：收紧为 `("buy",)` / `("sell",)`，或与 portfolio 事件命名统一。

**💭13. diag 标签截断无意义**
- 症状→来源：`morning_brief.py:236/274/281` `log_diag("晨报", "check as _gate_c", ...)`、`"build_alert_sect"`——故障定位时看不出是哪个段。
- 药方：换成真实函数名（`gate_check.check`、`s4_monitor.build_alert_section`）。

---

### 3. Health Score

**25 / 100**（100 起扣）

| 等级 | 数量 | 扣分 |
|---|---|---|
| 🔴 | 3（#1 #2 #3） | −45 |
| 🟡 | 5（#4 #5 #6 #7 #8） | −25 |
| 💭 | 5（#9–#13） | −5 |
| **合计** | | **25** |

扣分集中在"生产路径静默出错"（旧数据信号、门槛稀释）与"声明了但没接线"（N 清单、行业面、过滤层）两类。

---

### 4. 值得肯定项

- **核心逻辑单测是真断言且隔离良好**：strategy_score/signals/portfolio/holdings_review/breaker/diag/failed_pool/data_tushare/xq_track 等 45 个核心用例 8.3s 全过，mock 到位、临时文件不污染真实账本（`test_portfolio.py` 事件流跟随临时路径的修复尤其规范）。
- **数据源链设计成熟**：tushare→baostock→百度三级 fallback + SQLite 日增量缓存 + `_em_throttle` 节流 + 双源 `conflict` 标记不静默（`data.py:302-318`），数据边界都收在今天（防前视）。
- **容错成体系而非裸 `except:pass`**：绝大多数 except 带 `log_diag` 结构化落盘（diag.jsonl）+ 注释红线依据；breaker 熔断（当日失败 ≥5 跳过、次日重置）+ 晨报显式数据缺口标注（UZI data_gap）。
- **记账工程质量高**：`os.replace` 原子写账本、事件流 append-only 全可追溯、净值记录幂等、Q13 网格加仓批号、`check_constraints` 的 P1/Q4/Q5 检查（尽管 CLI 层"不阻止只提示"是半自动红线设计）。
- **纪律化的演进过程留痕**：S3 v1 因回测 -50~-90% 被数据裁决弃用并注明、九转从 B3 三重版剔除、MA 变体注册表标"否决"——"回测裁决后再启用"的流程本身是可靠的。

---

### 5. 结论 + 最该先修 3 件事

**结论**：这是一个文档纪律、测试质量、容错设计都明显高于平均的"书体系执行器"项目，架构骨架（纯函数打分 + 注册表 + 源链 fallback）正确。但**生产路径与"声明"之间存在系统性落差**：S3/买回纪律读到旧数据、行业面与 N 清单未接线却已生效计分、门槛被中性分静默稀释——核心打分与信号输出目前**不可完全采信**，需先修再跑。

**最该先修 3 件事**：
1. **修两处周线切片 bug**（🔴1/🔴2，一行各改）：`[:24]`→`[-24:]`、`[0]`→`[-1]`——日报 S3 与买回纪律从"比 2 年前价格"恢复为"比现价"。
2. **定行业面接入口径**（🔴3）：core_loop/holdings_review 补传 `score_industry`，或数据缺失记 0 分；同时去掉 eval_buy/holdings_review 硬编码 `is_leader=True`（🟡4）——否则打分系统给出的是 70/100 门槛 + 15 分虚分。
3. **修 0% 百分位 falsy bug**（🟡6）+ 给 N 清单补齐输入生产者或明示"未接入"（🟡5）——让否决与 B5 检查真正生效而不是只在测试里成立。

---