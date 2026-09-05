# 共识实现审计

从协议原文提取可审核的要求，再结合源码与接口契约，提出能够指导后续测试的共识违例 Candidate。Candidate 是有证据支持的假设，不是已确认缺陷，也不是正确性证明。

项目只有一条运行流程：

```text
材料导入 → 要求草稿 → 人工核对 → 代码与契约定位
        → 按 operation 组织独立审计任务
        → 多个 Candidate + 每条要求的处理情况 + 未解决问题
```

模型命令为 `extract-requirements`、`locate-code`、`audit`，另有离线的 `validate-requirements`。三个模型阶段共用一套有预算限制的调用循环；提示词与模型材料全部使用英文。

## 代码结构

```text
consensus-audit/
├── orchestrator/
│   ├── src/consensus_audit/             # 通用运行代码，不包含具体协议或实现分支
│   │   ├── cli.py                      # 命令入口、参数和客户端配置
│   │   ├── source_materials.py         # 材料块、来源引用、read_material 工具
│   │   ├── preparation.py              # 要求提取、代码定位及映射输入检查
│   │   ├── preparation_validation.py   # 要求/映射检查、人工状态、operation 分组
│   │   ├── audit.py                    # 独立审计任务装配、结果与成本汇总
│   │   ├── runner.py                   # 三阶段共用的模型/工具循环和有限恢复
│   │   ├── deepseek.py                 # 模型客户端、请求与用量解析
│   │   ├── workspace.py                # 目标树内的枚举、搜索和读取工具
│   │   ├── report.py                   # JSON 解析、多候选关联和源码引用检查
│   │   ├── artifacts.py                # 运行目录、文件写入、事件及成本记录
│   │   └── evidence.py                 # 从实际工具记录整理读取证据
│   └── tests/
│       ├── fakes.py                    # 离线模型响应和测试辅助函数
│       ├── test_pipeline.py            # 完整链路、多候选、隔离与失败处理
│       ├── test_deepseek.py            # 客户端离线测试
│       ├── test_workspace.py           # 文件工具与访问边界测试
│       ├── fixtures/                   # 独立的合成材料和源码样例
│       └── protocols/raft/             # Raft 专属导入测试
├── scripts/protocols/raft/
│   └── prepare_materials.py            # Raft 原件获取、文本转换与材料包组装
├── audit-specs/
│   ├── common/                         # 公共 Candidate 标准和任务输出约定
│   ├── preparation/                    # 要求提取、代码定位的英文 Prompt
│   ├── audit/                          # 通用英文审计 Prompt
│   ├── fault-models/                   # 可复用故障模型
│   └── protocols/raft/
│       ├── sources.yaml                # Raft 原文来源、版本与许可
│       ├── PROTOCOL_CONTEXT.md         # 项目定义的 Raft 记号
│       ├── EVENT_SEMANTICS.md          # 项目定义的 Raft 事件词汇
│       └── targets/etcd-raft/
│           ├── sources.yaml            # etcd/raft 范围、故障模型和契约线索
│           └── TARGET_BOUNDARY.md      # 此实现的审计范围
├── docs/
│   ├── architecture.md                 # 模块职责、阶段边界和扩展约定
│   └── protocols/raft/                 # Raft 材料说明及各实现的使用示例
├── ir/README.md                        # 任务结果与后续测试的边界
├── runs/requirements-ds-flash/          # 当前纳入 Git 的要求提取实验
├── runs-old/                           # 本地历史运行档案，不纳入 Git
├── evaluation/                         # 历史研究评价资料，不进入模型输入
└── .cache/materials/                   # 按协议、实现组织的本地材料缓存
```

`cli.py` 将三个模型命令交给 `preparation.py` 或 `audit.py` 组织阶段工作，再统一使用 `runner.py` 调用客户端和受限工具。`report.py`、`preparation_validation.py` 负责各阶段的基本结果检查，`artifacts.py` 与 `evidence.py` 保存和整理实际记录。协议与实现专属内容分别位于各大目录的 `protocols/<protocol>/` 和 `targets/<implementation>/` 下；增加其他共识或实现时复用通用运行代码，详细约定见 [架构说明](docs/architecture.md)。

## 最短使用流程

要求 Python 3.10+ 和 PyYAML。先使用所选协议目录中的导入脚本生成材料包，将其路径设为 `MATERIALS`；当前可用的配置与命令见 [etcd/raft 使用示例](docs/protocols/raft/targets/etcd-raft.md)。以下通用命令在仓库根目录运行：

```bash
export PYTHONPATH="$PWD/orchestrator/src"
python3 -m consensus_audit extract-requirements \
  --materials "$MATERIALS" --dry-run
```

通用 Prompt、模型循环和文件工具位于共享目录；协议来源、转换规则及项目定义放在对应 `protocols/<protocol>/` 目录，实现范围及接口线索进一步放在其 `targets/<implementation>/` 目录。模型命令只接收材料包和显式目标路径，不选择或假定某一种协议。目录约定见 [架构说明](docs/architecture.md)。

以下命令会真正调用模型，须由操作者明确授权并设置 `API_KEY_FILE` 后执行；本次重构没有运行收费实验。`TARGET_ROOT` 也必须由操作者设置为实际被测版本的源码路径，程序不猜测历史目标路径。

```bash
EXTRACT_RUN=$(python3 -m consensus_audit extract-requirements \
  --materials "$MATERIALS" \
  --api-key-file "$API_KEY_FILE")
```

人工直接编辑 `$EXTRACT_RUN/requirements.json`，核对原文、触发条件、量词、时序、例外和推导，将要求的 `review_status` 改为 `accepted`、`rejected`，或继续保留 `pending`。可以统一 operation 名称、合并确实重复的要求；合并时保留来源，并更新相关 `block_results.requirement_ids`。环境假设也须审核，不能用未经确认的假设支持候选。

```bash
python3 -m consensus_audit validate-requirements \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json"

MAP_RUN=$(python3 -m consensus_audit locate-code \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --target-root "$TARGET_ROOT" --api-key-file "$API_KEY_FILE")

AUDIT_RUN=$(python3 -m consensus_audit audit \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --code-map "$MAP_RUN/code-map.json" \
  --target-root "$TARGET_ROOT" --api-key-file "$API_KEY_FILE")
```

三个模型命令都可用 `--dry-run` 替换 `--api-key-file ...`。dry-run 只保存待发送输入，不读取密钥、不调用服务，也不产生虚构的要求、映射或审计结果。定位需要人工接受的真实要求；审计需要实际定位产生的映射，不能用上一阶段的 dry-run 冒充成功结果。

## 材料和证据边界

各协议的导入器负责保留原文、来源版本与引用位置，并将转换疑点和变体差异写入材料包的 `unresolved`。实现配置负责选择范围与可复用故障模型，不以模型记忆替代原文，不把某个实现的扩展自动应用到其他实现。

提取只能通过 `read_material` 访问已经导入的材料块，不能读取目标代码、mutation、历史 Candidate 或评价结果。程序逐块处理并保留失败记录；模型不能将新要求自动标为 accepted。结构检查不保证语义正确或要求全面。

定位和审计通过受限的 `list_files`、`search_code`、`read_file` 读取指定目标，并可用 `read_material` 补读已登记原文。工具不执行测试、不修改文件、不访问 `.git` 或目标树外路径。目标 README、包级文档、接口与配置注释只在需要时读取，且必须来自该目标版本。文档表达契约或意图，不证明代码已经实现保证。

现有故障模型和目标范围继续复用。保留的协议记号与事件词汇明确标为项目定义，不是论文原文，也不自动进入模型输入。`runs-old/` 和 `evaluation/` 中的历史资料仅为研究档案，没有运行时依赖，不能作为模型材料或审计目标。

## 任务和结果

定位按完整 operation 列表组织任务：跨操作要求会在每个相关操作中定位，不因首次出现就跳过另一侧。`code-map.json` 按 operation 和 requirement_id 记录位置、职责、契约和未知依赖。`located` 仅表示获得了审查起点；`partial`、`unresolved` 都不等于范围外或安全。

审计运行的 `input.json` 保存简单任务清单。每个任务具有独立 task_id 和全新上下文，联合检查本操作的多条已接受要求。模型必须读取原始源码，可以补读其他代码与已登记材料。任务之间不共享对话、推理或 Candidate；同一要求可以关联多个操作任务。

每个任务的 `result.json` 包含：

- `candidates`：独立机制的候选列表，使用任务内唯一 id 和 `requirement_ids`，保留源码证据、机制、最小因果链、P/A/V/O 与不确定性。同一机制涉及多条要求时合并为一个候选。
- `requirement_results`：逐要求记录 `candidate_found`、`no_candidate`、`insufficient_evidence`、`not_checked` 或 `not_applicable`，并关联候选 ID。
- `unresolved`：本任务仍未解决的问题。定位阶段的未知依赖和未接受项也保留在审计输入及汇总中。

发现一个候选不能代表其他要求已检查；模型应在预算内继续处理剩余要求。漏报项由程序补为 `not_checked` 并说明原因。`not_applicable` 必须有配置或规范依据，不能因为没找到代码就使用；`no_candidate` 只表示本轮没有形成候选。

## 记录、预算与离线验证

每个模型任务明确记录 `stage` 和 `task_id`，保存 `request.json`、实际 `input.json`、`events.jsonl`、最后的原始 `response.md`、证据清单和用量汇总。所有中间原始响应也保留在事件日志中。提取输出 `requirements.json`，定位输出 `code-map.json`，审计输出任务结果及总汇总。

共同预算默认为每个块或操作任务 12 轮、40 次工具调用，可用 `--max-turns` 和 `--max-tool-calls` 调整。格式恢复最多一次，且占用原预算；空响应、非法输出、调用失败、预算耗尽与成功返回的逐要求结论分开记录。单个任务失败不阻止其余任务，已知用量和未完成要求不会消失。退出码 2 表示阶段有调用/输出失败或尚无 accepted 要求；逐要求检查情况始终需要查看汇总。

三阶段汇总已报告的 token 用量。可用 `--input-price`、`--cached-input-price`、`--output-price` 提供同一币种的每百万 token 价格；价格、用量或前序记录缺失时不猜测完整金额。API 未返回的用量无法由程序推算。

映射复用保留简单的实际输入、Git 版本和已读取源码区间比对。它不是整仓快照；未读取依赖发生变化时仍需重新定位。保留完整运行目录以便核对引用。

```bash
PYTHONPATH=orchestrator/src python3 -m unittest discover -s orchestrator/tests -v
```

离线测试使用小型 synthetic fixture 和 fake client，验证完整链路、多要求/多候选关联、上下文隔离，以及失败、遗漏和预算耗尽时的记录。不会读取真实密钥、运行模型实验或用隐藏 oracle 调整规则。正式使用前仍需确认目标路径、材料版本、扩展语义及接口完成条件；离线通过不代表真实模型发现效果得到验证。

模块职责与输出边界见 [架构说明](docs/architecture.md) 和 [任务结果说明](ir/README.md)。
