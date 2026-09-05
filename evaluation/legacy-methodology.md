> Archived methodology for historical experiments. Commands and formats below describe the retired runtime preserved in Git history.

# 实验与人工评测口径

## 当前研究问题

在单性质、单注入机制和固定预算下，提供目标性质能否提高 LLM 的 top-1 机制命中率、场景可用性或单位成本收益。当前不评价自动测试执行和全仓库完备性。

## 两个实验条件

- `property-directed`：共同材料加一个相关 Q。
- `matched-no-property`：共同材料完全相同，但不提供或特权化具体 Q；模型可以在源码阅读中形成、修正或放弃临时性质假设，再表述其最终机制所威胁的性质与实现义务。

两侧必须使用相同模型配置、源码工具、轮次、工具调用上限和最多一个 Candidate 的输出契约。单次比较是 top-1 优先级比较；重复运行通过显式 `--episodes N` 或重复 guided 运行完成，不能把多 episode baseline 与一次 guided 运行直接计算胜率。

`shared-evidence` 暂不进入主实验，只保留为后续成本消融。

## 自动校验与人工评分边界

程序输出纯机器事实 `runs.csv`，其中包括 Candidate 的 strict/recoverable/schema/provenance 状态和成本。隐藏 evaluator 在独立的 `annotations.csv` 中使用 `evaluation/oracles` 的语义机制卡人工评分：

| Field | Score | Meaning |
|---|---:|---|
| mechanism | 0–2 | 是否命中决定性 ordering、guard、threshold 或 state relation |
| evidence | 0–1 | 引用是否真实、已读且支持该源码主张 |
| property linkage | 0–1 | 是否正确连接到给定或自派生性质 |
| P | 0–1 | 前置状态和拓扑是否足以指导构造 |
| A | 0–1 | 是否包含触发机制所需的关键事件和故障窗口 |
| V | 0–1 | 是否给出直接否定性质的最小谓词 |
| O | 0–1 | 是否能从明确观测判断 V |
| uncertainty discipline | 0–1 | 是否区分源码事实与待验证条件 |

Mechanism=0 表示错误根因或只有泛化怀疑；Mechanism=1 表示找到相关区域或结果现象但没有决定性关系；Mechanism=2 表示与隐藏 oracle 的决定性关系语义等价。

第一版将满足以下条件的输出标记为 `test-worthy`：

```text
Mechanism == 2
and Evidence == 1
and PropertyLinkage == 1
and P == 1 and A == 1 and V == 1 and O == 1
```

这是 evaluator 的判定，不是模型自己的 `candidate_found` 声明。

## clean 对照和同根去重

clean target 只表示未故意注入 mutation，不表示实现已被证明没有其他问题。clean 上的 Candidate 必须人工判断；不能自动全部标为假阳性。

同一实现机制从多个性质或多个 episode 被发现时使用同一个 `duplicate_group`，target-level 独立发现只计一次；重复次数作为稳定性单独报告。例如 vote 持久化机制同时关联 Q-VOTE-1 与 Q-ELECT-1，仍是一个机制发现。

## 失败分型

| Failure | Diagnostic |
|---|---|
| 未读取 ground-truth anchor | 代码定位失败 |
| 已读取 anchor 但 Mechanism<2 | 机制推理失败 |
| Mechanism=2 但 P/A/V/O 不完整 | 场景展开失败 |
| Mechanism=2 但源码读取和 token 很高 | 搜索成本问题 |
| clean 上重复声称注入机制 | 性质诱导或错误归因 |
| 评分者对语义等价描述不一致 | oracle 定义或评分指南不足 |

## 成本与重复性

每次运行报告实际 turns、tool calls、prompt cache hit/miss、completion tokens、total tokens、duration、files read 和去重后的 source lines read。多个 episode 只能称为 isolated contexts 或 independent runs；没有受支持的 sampling seed 时，不称为独立随机样本。
