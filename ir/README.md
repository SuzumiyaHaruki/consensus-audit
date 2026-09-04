# Candidate-v0 与后续边界

当前唯一实现的中间产物是每次运行的 `parsed-candidate.json`：

```text
response.md
+ evidence-manifest.json
→ Candidate-v0格式校验
→ 源码引用provenance校验
→ 隐藏mechanism oracle人工评分
```

Candidate-v0 保存一个主机制、源码证据、最小因果链、自然语言 P/A/V/O 和不确定性。它是可评价的发现产物，不是已确认缺陷，也不是供自动执行器直接消费的最终 DSL。

自动场景执行、TLA+ 可达性检查、多 Candidate 合并和 Case IR 当前均未实现。只有出现真实下游消费者后，才根据其具体输入需求增加相应 schema，避免现在同时为论文表述、人工评分和未来执行器设计一套无法验证的 IR。
