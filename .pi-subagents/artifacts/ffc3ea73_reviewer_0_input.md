# Task for reviewer

[Read from: C:\Users\luoji\shopping-agent\plan.md, C:\Users\luoji\shopping-agent\progress.md]

你是资深代码审查员（五维：正确性/可读性/架构/安全/性能）。审查项目 C:/Users/luoji/shopping-agent 的观复投资系统核心代码（Python——tools/strategy_engine/ 下 46 模块）。
重点文件：strategy_score.py（打分 v2：分红率/行业面/120制门槛80）、signals.py（B3/S2/S3）、portfolio.py（虚拟盘记账）、data.py（估值 tushare 主源切换+fallback）、industry.py（行业面——蛋卷百分位）、idea_backtest.py（回测）、morning_brief.py（日报——except 诊断接入）、weekly_report.py、holdings_review.py（eval_buy）、diag.py、breaker.py、failed_pool.py、data_tushare.py、xq_track.py、wb_track.py
审查要点：①打分逻辑正确性（120 制门槛 80 语义、行业面预计算传入的纯函数设计、中性 10 分 fallback 是否被滥用）②S3 v2 双条件逻辑③虚拟盘记账（buy/sell/事件流/净值）④tushare 主源+baostock/新浪/巨潮 fallback 链⑤错误处理（except:pass 是否过度——容错 vs 掩盖）⑥安全（token/cookie）⑦性能（网络缓存/节流/重复拉取）⑧tests/ 37 个文件测试有效性（测对东西吗——真断言还是摆设）
输出（Markdown）：## 代码审查报告
### 1. 五维打分（0-10）+一句话理由
### 2. 发现列表——每条 [🔴阻塞/🟡建议/💭小改进] 症状→来源(文件:行)→后果→药方
### 3. Health Score（100起扣——🔴15/🟡5/💭1）
### 4. 值得肯定项
### 5. 结论+最该先修 3 件事
凭证据（文件:行号）——拿不准标'未验证'——不要只夸。

## Acceptance Contract
Acceptance level: attested
Completion is not accepted from prose alone. End with a structured acceptance report.

Criteria:
- criterion-1: Return concrete findings with file paths and severity when applicable

Required evidence: review-findings, residual-risks

Finish with a fenced JSON block tagged `acceptance-report` in this shape:
Use empty arrays when no items apply; array fields contain strings unless object entries are shown.
`criteriaSatisfied[].status` must be exactly one of: satisfied, not-satisfied, not-applicable.
`commandsRun[].result` must be exactly one of: passed, failed, not-run.
`manualNotes` and `notes` are optional strings; an empty string means no note and does not satisfy `manual-notes` evidence.
```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "specific proof"
    }
  ],
  "changedFiles": [
    "src/file.ts"
  ],
  "testsAddedOrUpdated": [
    "test/file.test.ts"
  ],
  "commandsRun": [
    {
      "command": "command",
      "result": "passed",
      "summary": "short result"
    }
  ],
  "validationOutput": [
    "validation output or concise summary"
  ],
  "residualRisks": [
    "none"
  ],
  "noStagedFiles": true,
  "diffSummary": "short description of the diff",
  "reviewFindings": [
    "blocker: file.ts:12 - issue found, or no blockers"
  ],
  "manualNotes": "anything else the parent should know"
}
```