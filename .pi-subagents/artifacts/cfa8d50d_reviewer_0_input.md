# Task for reviewer

[Read from: C:\Users\luoji\shopping-agent\plan.md, C:\Users\luoji\shopping-agent\progress.md]

你是架构师+Agent 工程大师。审查 C:/Users/luoji/shopping-agent 的'观复'（投资研究 Agent：定时任务链 GFBrief/GFWeekly/GFXQTrack/GFWBTrack + 虚拟盘 + 大V 跟踪 + 微信推送）架构成熟度与二期规划。
读：docs/架构师复盘报告.md、docs/观复待办综合方案.md（二期14项/三期4项）、docs/观复技术方案.md、docs/观复验收清单.md。方法论参照《深入理解AI Agent》（状态栏/在线-离线双循环/特性开关/消融/熔断/可观测性/评估/安全边界——你的知识即可）。
审查：
① 架构成熟度：SIGNALS 注册表 status（候选/enabled）作为特性开关——接入完整吗（core_loop/holdings_review 是否遍历）？晨报=状态栏（代码键值对）信息密度？diag/breaker 可观测性？定时任务失败恢复（vbs+cron+日志）？
② 双循环：虚拟盘（在线）+Q11 校准/回测（离线）闭环完整度
③ 数据层：tushare 主源+baostock/新浪/巨潮 fallback——SLA 风险/缓存/节流/限流
④ 安全：token/cookie 管理、xq_cookies 敏感处理、大V 内容未来进 LLM 的提示注入风险
⑤ 二期 14 项审查：优先级排序合理吗？砍/合并/提前哪些？（云服务器/大盘择时六亿温度/月九转/搬砖降本/S3右侧买回/大V发言LLM解读/知识修剪/鹿鼎公图视觉读取）
⑥ 单点故障：哪些模块坏=瘫痪（backup 13文件覆盖检查/依赖链）
输出：## 架构+Agent工程审查报告
### 1. 维度打分（0-10）：架构成熟度/可观测性/数据层/安全/规划合理性/演进路径
### 2. 发现（🔴/🟡/💭）症状→来源→后果→药方
### 3. 二期规划裁决：每项 保留/砍/合并/提前+理由
### 4. 总评+最该先修 3 件事
凭证据。

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