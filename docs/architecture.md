# 目录与材料分层设计

## 目标

系统最终需要支持多种协议、多个实现、不同故障模型和多轮实验，同时保持以下边界：

- 协议性质不与具体代码实现耦合；
- 同一故障模型可以被多个协议复用；
- 同一协议可以审计多个目标实现；
- AI 可见材料与隐藏评价答案物理隔离；
- 静态分析、TLA+ 可达性、真实执行和结果评价可以独立演进。

## 审计定义组合

```text
Shared fault model
    + Shared target boundary
    + Guided or baseline task
    + Guided protocol/event/property package when applicable
    + Report template
    = Material set for one audit run
```

### Common

定义跨协议稳定的任务语义，例如证据要求、Risk/P/A/V/O、盲测规则和输出格式。这里不能出现 Raft、PBFT 或具体代码符号。

### Fault model

定义节点、网络、存储和活性假设。故障模型描述的是故障类型和故障后的语义，不定义协议的 quorum 算法、成员数量或具体部署能容忍多少故障。后面这些信息由协议和目标实验配置提供。

故障模型独立于某个目标实现，例如：

```text
crash-stop-cft
crash-recovery-cft
byzantine-partial-synchrony
storage-crash-consistency
```

只有实际实验需要时才增加，不提前复制相似版本。

### Protocol

保存独立于实现的性质 Q 和必要协议记号。未来可以增加：

```text
protocols/raft
protocols/pbft
protocols/hotstuff
protocols/tendermint
```

协议层不得标注某个目标实现的文件、函数或字段。

每个性质保存为独立文件，共享协议记号放在 `PROTOCOL_CONTEXT.md`，事件完成语义放在 `EVENT_SEMANTICS.md`。批量审计时，运行器只装入当前 Q，不把同批次的其他性质定义、reasoning 或结果带入该上下文。

几十个性质由外层 orchestrator 顺序调度，而不是要求单个 LLM上下文同时承载。默认隔离策略优先保证结论可归因；相关性质之间重复搜索代码的成本，后续可以通过不含语义结论的机械代码索引降低。

### Target

定义一个具体实现的系统边界、公开契约和启用配置。`TARGET_BOUNDARY.md` 由性质审计与 baseline 共享，只说明“本次审计什么”，不提供正确 quorum 公式、事件语义或性质答案。

除非研究对象就是某个固定部署，静态分析阶段不预设节点数。quorum 和成员规模应保持参数化；AI在把风险转成具体 P/A/V/O 场景时自行选择节点数量、参与者和所需 quorum，并解释为什么这个规模能够暴露风险。

同一协议的其他实现应作为并列目录加入，例如：

```text
protocols/raft/targets/hashicorp-raft
protocols/raft/targets/redisraft
```

## 实现路径发现策略

主实验的 AI 可见材料不应直接列出某个实现已知存在几条路径，也不应给出接口与配置的笛卡尔积。例如，即使人工已经知道一个目标存在两类接口和两种存储模式，也只要求 AI：

```text
发现所有与性质相关的公开入口和配置分支
→ 判断哪些阶段共享代码、哪些阶段真正分叉
→ 说明为什么没有遗漏实质不同的路径
```

已知路径矩阵作为隐藏评价知识由人工保留。若主实验遗漏某条路径，可以另做一次显式提供路径清单的诊断运行：显式清单下能够正确分析，说明主要问题在路径发现；仍然不能正确分析，说明问题在路径内的语义推理。诊断运行不能与无提示主实验混为同一种能力结论。

## 非 AI 输入组件

这些框架组件不应放入 `audit-specs`：

```text
orchestrator/       已实现：材料装配、模型调用、源码工具循环和运行预算
analyzers/          符号索引、调用关系和代码切片工具
models/             TLA+ 或其他协议模型
executors/          消息、时间、生命周期和状态控制
evaluators/         报告评分、Oracle 和统计
runs/               单次实验的配置与结果引用
```

除已实现的 `orchestrator` 外，其余目录在真正出现代码或数据前不创建空壳。

## 隐藏评价材料

人工植入缺陷的根因、修改位置、正确因果链和预期场景不能依靠目录命名约定来保密。它们应存放在 AI运行环境无法读取的位置，或由外部评价服务持有。

AI只应获得：

```text
解析后的material set
+ 当前被测工作树
+ 明确允许的分析工具
```

不应获得框架工作区的完整读取权限。

## Material set

`audit-specs/catalog.yaml` 是装配入口。每个 material set 明确列出 AI必须读取的文件，避免随着协议和目标增加而把无关材料全部送入上下文。

每个 material set 将文件分成 `shared_files`、`guided_files` 和 `baseline_files`。两种审计都读取 shared fault model 与 target boundary；性质审计另外读取 protocol context、event semantics 和当前 Q；baseline 只读取 baseline task 与报告格式。baseline 未显式指定 episode 数时，使用该 material set 的性质数量。

material set 只描述组合关系，不保存代码版本、mutation 身份、正确答案或历史结果。

## Candidate 与 Case

单 Q分析报告中的每个可信风险先形成 `Candidate IR`，保留原始报告和工具证据引用。相关 Q产生的同根风险在分析完成后可以合并为一个 `Case IR`。

Candidate 是未经审查的风险假设；Case 是供 TLA+、场景规划器和执行器消费的规范化对象。两者的定义位于顶层 `ir/`，不属于 AI输入。Case将 `P`拆为协议、实现和环境三类谓词，同时保存动作集/序列 `A`、性质违例 `V` 和 Oracle `O`。
