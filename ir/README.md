# 审计任务结果与后续边界

当前产物是每个操作任务的 `result.json`，包含 task_id、多个 candidates、逐要求的 requirement_results 和 unresolved。完整英文输出约定见 [TASK_RESULT.md](../audit-specs/common/TASK_RESULT.md)。

Candidate 使用任务内唯一的 id 和 requirement_ids 关联要求，保留源码证据、实现义务、机制、最小因果链、P/A/V/O 与不确定性。不同任务可以使用相同的局部候选 ID；跨任务引用需要同时标明 task_id。一个机制影响多条要求时，由当前任务将关联合并；程序不执行语义去重。

任务未处理或漏报的要求保留为 not_checked，未知依赖保留为 insufficient_evidence。no_candidate 不是正确性证明，Candidate 也不是执行确认。`summary.json` 中的阶段执行状态与这些要求级状态分开。

所有源码引用必须由本任务真实的 read_file 记录支撑。没有原始读取证据的初始映射不能直接充当 Candidate 证据。

当前没有自动执行 DSL、场景执行器、形式证明或旧报告迁移器。历史结果保持原格式存档，当前运行器不读取或适配它们。
