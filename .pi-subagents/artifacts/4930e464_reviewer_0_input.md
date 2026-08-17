# Task for reviewer

[Read from: C:\Users\luoji\shopping-agent\plan.md, C:\Users\luoji\shopping-agent\progress.md]

你是金融大师（资深投资体系审查员）。审查 C:/Users/luoji/shopping-agent 的'观复'——吴老师书体系执行器（高股息价值投资——虚拟盘验证中——8万资金 89% 仓位：太保/平安/中信/华电/招行）。
先读：docs/三本书精读审视报告.md、docs/大V策略双视角报告.md、docs/爸妈投资理念.md（精读关键章节——低潮买入/估值/卖出）；然后审 tools/strategy_engine/ 投资逻辑：
① 打分体系（strategy_score.py）：价值40+估值30+技术20+票源10+行业20=120制门槛80——权重合理吗？'行业面20分加入但门槛80不变'的语义变化（老100制80%=80分 vs 新120制80分=67%）？分红率40-75%健康区/ROE阈值15的依据强度？
② 回测质量（idea_backtest.py、.wbs_tmp/s3_backtest.py 的 S3 v2 定案：2015-2026 十一半年 5 只样本——招行收益99%+回撤减半）——幸存者偏差？样本量够吗？前视偏差？单次回测能定案启用吗？
③ 虚拟盘判定标准（9/12：连续4周跑赢沪深300 且 Alpha>0 或满90天）——统计力度（样本22交易日）够吗？
④ 行业面（industry.py）：蛋卷 pe_percentile 当'位置'、格局/政策静态档案（人工评级）——静态档案过拟合风险？银行81%高位扣分 vs 招行个股仍被推加仓的矛盾？
⑤ 书忠实度：B3低潮买入/S2周布林上轨/S3估值减仓v2/失败票黑名单/抄底分批/搬砖——对照主书偏差处
⑥ 持仓结构（89%仓位/5只——金融3只+公用1只+证券1只）集中度风险
输出：## 金融大师审查报告
### 1. 维度打分（0-10）：打分设计/回测质量/判定标准/行业面/书忠实度/仓位结构
### 2. 发现（🔴/🟡/💭）症状→来源→后果→药方
### 3. 风险清单（幸存者偏差/过拟合/数据陷阱/方法论缺陷）
### 4. 总评+最该先修 3 件事
引用具体代码/数字。

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