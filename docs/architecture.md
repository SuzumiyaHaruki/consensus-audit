# 当前架构与边界

## 目标

当前系统是共识测试的审计前端：在有限预算内，把实现源码和协议知识转化为一个有代码依据的测试候选。它不证明缺陷、场景可达性或实现整体正确性，也不生成可直接执行的测试程序。

```text
实现源码 + 协议材料 + 故障模型 + 可选目标性质
→ LLM源码搜索
→ Candidate-v0
→ 格式和引用来源校验
→ 隐藏mechanism oracle人工评分
```

## 输入材料

`audit-specs/catalog.yaml` 只列出允许进入模型上下文的材料。每个 material set 具有：

- `common_files`：故障模型、目标边界、共同任务、协议上下文、事件完成语义和 Candidate-v0 输出契约；
- `properties`：只能由 property-directed 条件逐个选择的性质文件。

两个主实验条件的共同输入完全相同：

```text
property-directed   = common_files + one Q
matched-no-property = common_files
```

因此处理变量是是否给出具体性质，而不是协议背景、完成语义、报告格式或源码工具。property-directed 从给定性质向实现义务和代码机制推进；matched-no-property 不特权化任何性质，但允许模型在源码阅读中形成、修正或放弃临时性质假设，并将最终 `property_id` 设为 `null`。

## 协议、故障模型与目标边界

协议层保存独立于实现的性质、记号和事件完成语义，不出现具体代码符号。故障模型定义节点、网络、存储和恢复假设，不预先固定协议 quorum。目标边界说明本次允许分析的接口与配置，但不包含 mutation 身份或正确答案。

新增协议或实现时增加相应的 protocol/target 材料集，不复制通用任务和输出契约。

## 运行与 Candidate-v0

每次运行使用独立消息上下文，最多输出一个主 Candidate。模型应先找到代码锚点和被破坏的实现义务，再给出决定性 ordering、guard、threshold 或 state relation，最后展开最小因果链和自然语言 P/A/V/O。

`candidate_found` 只表示模型认为存在值得交给下游测试的机制；真正的 `test-worthy` 由评价器判定。`no_candidate` 表示本轮和预算内没有候选，不是正确性证明。`insufficient_evidence` 表示决定性代码或完成语义不可得。

## 机械校验

Runner 保留原始 `response.md`，然后执行两类不涉及机制语义的检查：

1. Candidate-v0 是否为单个 JSON 对象且满足字段契约；
2. 每个源码路径是否存在，引用行区间是否完全落在本轮 `read_file` 返回的区间内。

通过后生成 `parsed-candidate.json`。provenance 通过只说明模型实际读取了相应代码，不能说明自然语言 claim 或机制结论正确。

纯 JSON 是首选格式。为了不让可恢复的展示差异覆盖机制发现结果，解析器也接受外围说明文字中唯一的有效 JSON 代码块，并记录格式警告；多个候选对象、无法解析的文本和只有工具调用语法的输出不会被猜测性修复。

## 隐藏评价材料

`evaluation/oracles` 保存人工注入机制的语义 oracle，不属于 AI 材料。Runner 不读取它，模型工具也被限制在 `TARGET_ROOT`。正式实验环境仍需确保评价目录不作为目标代码或附加材料暴露。

oracle 以决定性关系为核心，同时记录 anchor、实现义务、可接受的语义等价解释和错误但相关的解释。命中同一机制的多个性质报告只算一个独立发现。

## shared-evidence

`shared-evidence` 保留为可选消融：它在隔离推理上下文之间共享机械索引和完全相同的原始工具结果，不共享结论。当前主实验使用 `isolated`，因为已有试运行尚未显示足够的实际证据复用收益。

## 当前不实现

- 自动判断机制与 oracle 的语义等价；
- 多 Candidate 合并和跨性质结论记忆；
- TLA+ 可达性证明；
- 自动生成、部署或执行场景；
- 对整个实现的完备性质证明。

只有下游测试消费者真实建立后，才根据其输入需求设计 Case 或可执行场景 DSL。
