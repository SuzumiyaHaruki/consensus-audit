# 实验与人工评测口径

## 两类实验

条件审计实验给每个 mutation 提供与其对应的 Q，用于测量模型在已知正确性质时定位代码机制并生成场景的能力。该结果不能直接与多 episode baseline 计算胜率。

端到端发现实验在同一个 target 上运行完整 material set：性质侧对每个 Q 建立独立上下文，baseline 运行同等数量的独立 unguided episode。两侧均按所有报告的 finding 并集判断 target 是否被检出。建议同时加入未修改 target，用于观察无依据 finding。

## 人工评分表

隐藏评价材料不得提供给被测模型。每个 finding 使用以下字段记录：

| Field | Meaning |
|---|---|
| target | 被测代码目录的隐藏评价 ID |
| arm | `guided` 或 `baseline` |
| run | Q-ID 或 baseline episode |
| expected mechanism | 隐藏 mutation 或 clean 标记 |
| detection | 是否定位 mutation 所在机制或等价因果机制 |
| linkage | 是否正确连接到给定 Q；baseline 则评价其自行提出的正确性要求是否成立 |
| P | 前置状态是否可达且完整 |
| A | 动作或故障序列是否完整 |
| V | 是否给出最小语义违例 |
| O | oracle 是否能从可观测事件判断 V |
| evidence fidelity | 源码声明是否与 evidence manifest 一致 |
| duplicate group | 与同 target 其他 finding 的同根去重 ID |
| notes | 错误归因、遗漏前提和过度声称 |

Detection、linkage、P、A、V、O 和 evidence fidelity 分开记录，避免仅凭泛化怀疑获得完整检出分。一个 target 内同根 finding 只计一次 target-level detection，重复出现次数可作为稳定性数据单独报告。

## 资源与重复性

每次运行报告实际 turns、tool calls、prompt cache hit/miss、completion tokens、total tokens 和 duration，而不仅报告最大预算。多个 episode 只能称为 isolated contexts 或 independent runs；在没有显式且受支持的 sampling seed 时，不称为独立随机样本。
