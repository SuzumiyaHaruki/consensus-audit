# 单一审计架构

```text
scripts/protocols/<protocol>/prepare_materials.py
    ↓ source-bundle.json
extract-requirements
    ↓ requirements.json（pending）
人工核对原文、推导、适用条件与 operation
    ↓ accepted requirements
locate-code
    ↓ code-map.json（操作、要求、源码/契约位置、未知依赖）
audit
    ↓ 独立操作任务的 candidates / requirement_results / unresolved
```

系统的目标是形成有源码依据、可以指导测试的 Candidate，不是自动证明协议实现正确。历史实验与人工评价材料留在研究档案中；当前运行路径不依赖它们。

## 协议和实现的目录边界

```text
audit-specs/
├── common/、preparation/、audit/      # 通用模型指令和输出要求
├── fault-models/                    # 可复用故障模型
└── protocols/
    └── raft/
        ├── sources.yaml            # Raft 原文、版本、许可和协议疑点
        ├── PROTOCOL_CONTEXT.md     # Raft 项目记号
        ├── EVENT_SEMANTICS.md      # Raft 项目事件词汇
        └── targets/
            └── etcd-raft/
                ├── sources.yaml   # 此实现选择的范围、故障模型和契约线索
                └── TARGET_BOUNDARY.md
scripts/protocols/raft/prepare_materials.py
docs/protocols/raft/README.md
docs/protocols/raft/targets/etcd-raft.md
orchestrator/src/consensus_audit/      # 与具体协议、实现无关的运行能力
```

专属内容按所在大目录继续分协议，再按需要分实现。新增另一个 Raft 实现时，在 `audit-specs/protocols/raft/targets/<implementation>/` 添加其来源配置和范围，显式传给 Raft 导入脚本；共用的 Raft 原文与转换逻辑不复制。新增其他协议时，在对应协议目录组织来源、转换脚本和说明，输出同样的材料包即可，通用运行器不增加协议分支或插件注册机制。

来源清单中的 `local` 路径相对于仓库根目录；协议清单的项目定义路径相对于该协议目录。协议原件缓存使用 `.cache/materials/<protocol>/`，每个实现的材料包由 `--output` 显式指定，推荐放在其下的 `<implementation>/`。导入脚本没有默认实现，省略实现配置会保留范围与故障模型未选择的未知项。协议疑点与实现疑点分别维护，不静默继承其他实现的范围。

通用源码搜索默认不限文件扩展名，模型可按需要指定 glob 缩小范围；`.git` 和目标树外路径仍不可访问。具体实现的语言、包文档名称和接口说明属于实现目录，通用 Prompt 只要求按需检查包文档及相关契约。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `scripts/protocols/<protocol>/prepare_materials.py` | 复用 Poppler 获取、导入、转换明确来源的原文，保留章节与位置 |
| `source_materials.py` | 材料块、来源引用、块内行号、受限 read_material |
| `preparation.py` | 枚举提取块，按完整 operation 列表定位，保留遗漏与失败 |
| `preparation_validation.py` | 要求、人工状态和映射的基本结构/引用检查，简单 operation 分组 |
| `audit.py` | 生成可查看的任务清单，装配各任务上下文，汇总任务与用量 |
| `runner.py` | 三阶段共用的模型/工具调用循环与有限恢复 |
| `deepseek.py` | 既有客户端、请求格式、网络重试和实际返回用量 |
| `workspace.py` | 目标树内的只读文件工具；定位和审计可同时补读登记材料 |
| `report.py` | 实用 JSON 提取、源码引用验证、多候选和逐要求关联 |
| `artifacts.py` / `evidence.py` | 原始输入、响应和工具事件；从真实读取轨迹生成引用清单和成本记录 |
| `cli.py` | 三个模型命令和离线要求检查，没有模式适配分支 |

## 一套调用循环

每次调用显式传入 stage、task_id、英文 Prompt、实际输入、允许的工具、输出解析/检查函数，以及轮数和工具预算。公共配置没有性质 ID。公共循环不判断协议意义，不猜任务阶段，不计划子任务，也不规定候选数量。

循环逐次记录原始响应、工具调用结果和已知用量。最后一轮禁止工具并要求阶段 JSON；格式修复最多一次，计入同一预算。成功取得合法阶段结果记为 `completed`；空响应、格式失败、调用异常和预算耗尽分别记录。`completed` 是调用结果状态，不表示任何要求被证明正确；要求级结论存在 `requirement_results` 中。

输入文件记录初始消息和工具定义，事件日志记录后续追加的消息及响应，避免每轮重复保存完整对话。dry-run 不构造客户端、不读取 key，只保存待发送输入。工具异常和调用失败保留已知用量，各阶段的聚合代码负责继续后续块或任务。

## 材料与人工核对

提取工具只能读取材料包。原文、实验范围、故障模型以及 Agent 指令有明确区分。项目自定义的记号与事件说明保留为参考，不自动作为原文要求输入。协议和扩展要求必须引用真实材料块；跨段推导标为 derived 并说明依据。材料转换与语义问题进入 unresolved。

所有模型新增项强制 pending。人工可以统一 operation、接受或拒绝要求、合并确实重复的条目；合并时保留所有依据并更新块记录。程序只检查明显结构错误、ID、引用及块记录，不设置额外审批层，也不将机械检查当成完整性或语义保证。

## 跨操作定位与审计

人工核对后的 operation 列表直接决定分组。定位以每个相关操作为一次任务，同一操作的要求共享定位；多操作要求在各组中都保留完整关联。映射用 `(operation, requirement_id)` 区分每一侧，不因一次定位完成就声称其他操作已检查。遗漏的映射补 unresolved；失败任务的全部输入要求同样保留 unresolved。

审计为各组建立独立上下文，提供本组已接受要求、相关原文/定义、既有范围和故障模型、已接受适用假设，以及与这些要求相关的各侧位置和未知依赖。没有局部来源关联的未知项作为全局问题保留，避免无依据地隐藏。重复起始位置只列一次，职责仍与具体要求和操作关联。

源码与接口契约均按需读取。初始映射只是起点；审计需读取原始代码，并可继续搜索、补读调用方和登记材料。映射不传递定位对话或结论。跨任务不共享推理、候选或语义记忆。

## 任务结果与失败

审计 Prompt、候选标准和输出结构分别位于 `audit-specs/audit/AUDIT.md`、`common/CANDIDATE_CRITERIA.md`、`common/TASK_RESULT.md`。候选标准只维护一份。

同一任务可以产生多个独立机制的 Candidate，一个 Candidate 也可以关联多条要求。程序检查任务内 ID 与双向关联，不自动判断两个自然语言机制是否相同。每条要求必须有处理记录：候选、未形成候选、证据不足、未处理或有依据的不适用。模型遗漏时补 not_checked，调用失败时全部要求记 not_checked，同时保留原始响应及失败类型。

顶层审计汇总列出任务和各要求结果、未分配/未接受项、定位状态、未知依赖及费用。即使运行全部 completed，也可能仍有 not_checked、insufficient_evidence 或未审核要求；不存在将任务完成等同于安全的转换。

引用检查仅保证路径合法、材料引用存在，以及引用源码在本任务实际读取过。保留基于既有输入、Git 版本和已读取区间的简单映射变更检查，不添加内容 hash、快照或版本管理平台。跨运行使用映射时，应保留其实际输入和工具轨迹。

当前没有自动场景执行器、可达性证明、跨任务候选去重、投票或发现率结论。后续测试可以使用 Candidate 的 P/A/V/O，但需自行确认集成条件和执行结果。
