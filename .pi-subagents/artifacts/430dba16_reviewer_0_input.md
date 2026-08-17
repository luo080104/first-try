# Task for reviewer

[Read from: C:\Users\luoji\shopping-agent\plan.md, C:\Users\luoji\shopping-agent\progress.md]

你是 Spec 轴审查员。核对 C:/Users/luoji/shopping-agent 的观复系统'规划 vs 落地一致性'。
读规划：docs/观复待办综合方案.md、docs/观复技术方案.md、docs/观复落地实施方案.md、docs/架构师复盘报告.md、docs/观复验收清单.md
对照实际代码（tools/strategy_engine/）与数据（data/）验证：
① 规划声称'已完成'的功能是否真有代码证据（晨报17:00日报/持仓今日真实盈亏/S4公告监测/B2大V观察段/B5估值温度/S3 v2启用/行业面/失败票黑名单/诊断日志diag/熔断breaker/大V跟踪xq_track/wb_track/周报HTML/备份backup）——每项：函数/路由/数据文件证据或标记'无法验证'
② 验收清单 M1/M2/M3 达成证据（M2-2 连续2周无人工干预——声称8/30复核）
③ 红线机制（未验证不落地/Q6/不自动卖/合规底线）在代码里是否有机制保证——不是只写文档（查：signals 注册表 status 字段、eval_buy 强制入口、S3 建议级不自动卖、confirm.py）
④ 二期/三期规划与现有架构的衔接预留（SIGNALS 注册制/信号状态机）
输出：## 规划落地一致性报告
### 1. 一致性矩阵：规划项|声称状态|代码证据(文件:函数)|实际状态(✅/⚠️/❌/未验证)
### 2. 红线机制核查表
### 3. 发现（🔴/🟡/💭）症状→来源→后果→药方
### 4. 一致性打分（0-10）+结论
每项至少一个文件/函数名证据。

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