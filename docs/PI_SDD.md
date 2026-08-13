# Pi SDD 工作纪律

> 来源：Spec Kit + Agent Skills (Addy Osmani)
> 适用范围：任何预计超过 30 分钟的任务
> 工具：一句话修复、注释调整等不需要走完整流程

## 四阶段门禁

```
SPECIFY ──→ PLAN ──→ TASKS ──→ IMPLEMENT
   │          │        │          │
   ▼          ▼        ▼          ▼
  等确认     等确认    等确认     自动执行
```

**每阶段不通过人类确认，不准进入下一阶段。**

---

### Phase 1: SPECIFY（定义做什么）

写一个简短的 spec 文档，包含：
- **目标**：要解决什么问题、成功什么样
- **假设**：列出你默认成立的假设，等纠正
- **边界**：明确不做什么

```markdown
## Spec: 修弹窗问题

### 目标
浏览器任务栏图标残留——采集进程结束后图标不消失

### 假设
- 问题出在 vbs 启动方式而非浏览器本身 [对吗？]
- 只影响任务栏图标，不影响采集功能 [对吗？]

### 边界
- 不改变浏览器采集逻辑
- 不动 browser_pool 的 headless 分支
```

### Phase 2: PLAN（定义怎么做）

- 技术方案（改什么文件、用什么方法）
- 风险点（改了 A 会不会影响 B）
- 验证方式（改完后怎么确认修好了）

**计划头固定格式**（学 writing-plans，Superpowers）：

```markdown
# [功能名] 实施计划

**Goal:** [一句话：做什么]
**Architecture:** [2-3 句：怎么实现]
**Tech Stack:** [关键技术/库]
**Spec:** [对应 spec 文档路径]

## Global Constraints
[spec 里的全局约束逐字复制——版本下限/依赖限制/命名规则，每条一行]
```

**No Placeholders 铁律**（学 writing-plans）：
- 每个任务必须包含**实际内容**——真正的代码、真正的测试、真正的命令
- 禁止：`TBD` / `TODO` / "写适当的错误处理" / "类似 Task N" / "添加验证"（不写具体代码）
- 工程师可能只看到自己的任务——Interfaces 块要写清楚 Consumes/Produces 的**精确签名**

### Phase 3: TASKS（拆成任务）

每个任务：
- 一次能做完的粒度（**2-5 分钟一步**）
- 有明确的验收条件
- 有验证命令
- **每步是 TDD 循环**：写失败测试 → 跑确认失败 → 写最小实现 → 跑确认通过 → commit

```markdown
- [ ] 改 start_server.vbs：python.exe → pythonw.exe
  - 验收：重启服务后任务栏无图标
  - 验证：tasklist | findstr python 确认是 pythonw 进程
```

### Phase 4: IMPLEMENT（执行）

- 按顺序逐条执行任务
- 每完成一条验证一条
- 全做完后跑一次完整冒烟测试
