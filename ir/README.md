# Candidate / Case IR

这里保存 AI分析与后续 TLA+/真实执行之间的最小中间表示，不属于 AI输入。

```text
response.md + evidence-manifest.json
→ Candidate（未经审查的单个风险假设）
→ Case（可合并多个Q、经语义修正的场景）
→ TLA+检查P_protocol
→ 执行器实现P并执行A
→ Oracle检查O并据此判断V
```

## Candidate

每个 Candidate对应 AI报告中的一个风险，保留来源、性质、代码证据、风险机制，以及场景草案 `P/A/V/O`。它只是待复核假设，不能解释为确认缺陷。

## Case

Case可以整合多个相关 Candidate，例如同一投票持久化风险同时影响 Vote Safety和Election Safety。人工或后续整理器在 Case中修正：

- 性质与事件完成语义；
- 实际成立的代码证据；
- `P_protocol / P_implementation / P_environment`；
- 拓扑和动作 `A`；
- 性质违例 `V`与可观测 Oracle `O`；
- TLA+和执行器所需参数。

## 使用边界

- 原始 `response.md` 和 `evidence-manifest.json` 不修改；
- TLA+只消费 Case中的协议 P、拓扑和模型参数；
- 执行器消费实现/环境 P和动作A，Oracle用O判断V；
- 当前模板是可修改草案，等真实消费者出现后再收紧字段和校验。

模板：

- `templates/candidate.yaml`
- `templates/case.yaml`
