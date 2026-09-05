# 共识实现测试候选发现框架

本项目研究：给定共识实现、协议材料、故障模型和可选的目标性质，LLM 能否以较低成本提出少量、源码支撑充分、值得进入后续测试的协议违例候选场景。Candidate 是面向测试的假设，不是已确认缺陷或可达性证明。

支持两种使用流程：已有的 `run` / `baseline` 直接装配审计材料；新增的 prepared 流程先从原文提取要求，经人工审核后定位源码，再按规范操作组织审计。提供给 LLM 的提示词和材料均使用英文。

## 当前结构

```text
consensus-audit/
├── README.md                         # 人类使用说明（不提供给 AI）
├── docs/
│   ├── architecture.md               # 总体分层和扩展约定
│   └── prepared-audit.md             # 材料导入、人工审核与 prepared 操作说明
├── scripts/
│   └── prepare_materials.py          # 公开材料获取、本地导入与 PDF 文本转换
├── evaluation/
│   ├── oracles/                       # 不提供给模型的人工机制标注
│   └── score-template.csv             # Candidate人工评分表
├── ir/
│   └── README.md                      # Candidate-v0边界和后续阶段
├── orchestrator/
│   ├── src/consensus_audit/           # 材料装配、提取、定位、审计及引用校验
│   └── tests/                         # 不访问外部API的离线测试
├── .cache/materials/                 # 本地原件、转换文本与材料包，不纳入 Git
├── pyproject.toml
└── audit-specs/                      # 可组合的审计定义
    ├── catalog.yaml                  # 材料组合清单，由实验运行器读取
    ├── sources.yaml                  # 原文来源、版本、许可及适用范围
    ├── preparation/
    │   ├── EXTRACT_REQUIREMENTS.md   # 独立的英文要求提取 Prompt
    │   └── LOCATE_CODE.md            # 独立的英文代码定位 Prompt
    ├── common/
    │   ├── AUDIT_TASK.md             # 两个实验条件共用的发现任务
    │   └── REPORT_TEMPLATE.md        # Candidate-v0 JSON契约
    ├── fault-models/
    │   └── crash-recovery-cft.md     # 可复用故障模型
    └── protocols/
        └── raft/
            ├── PROTOCOL_CONTEXT.md   # Raft共享协议记号
            ├── EVENT_SEMANTICS.md    # 抽象事件及精确完成点
            ├── properties/           # 每个Q一个独立英文文件
            │   ├── Q-VOTE-1.md
            │   ├── Q-ELECT-1.md
            │   └── ...
            └── targets/
                └── etcd-raft/
                    └── TARGET_BOUNDARY.md # 两种审计共享的目标边界
```

## 两阶段准备与 prepared 审计

```text
协议原文 + 现有范围与故障模型
  → extract-requirements → requirements.json 草稿
  → 人工编辑 review_status
  → locate-code → code-map.json
  → prepared → 各 operation 的独立 Candidate-v0 审计
```

| 入口                             | 作用                                                  | 主要结果                                          |
| -------------------------------- | ----------------------------------------------------- | ------------------------------------------------- |
| `scripts/prepare_materials.py` | 下载公开原件或导入本地材料，使用 Poppler 转换         | `source-bundle.json`，保留章节、页码及块内行号  |
| `extract-requirements`         | 逐块提取，可补读关联材料；不开放目标源码工具          | `requirements.json`，新生成项强制为 `pending` |
| `validate-requirements`        | 检查人工编辑后的结构、引用和漏块，显示审核状态        | 审核与待确认项汇总；不代表语义正确                |
| `locate-code`                  | 只定位`accepted` 要求，按需读取目标版本的源码和契约 | `code-map.json`，包含位置、职责与未知依赖       |
| `prepared`                     | 按 operation 分组，以映射为起点继续读取源码           | 独立 Candidate-v0 结果及任务汇总                  |

在仓库根目录可先完成离线材料导入和提取输入装配：

```bash
export PYTHONPATH="$PWD/orchestrator/src"
python3 scripts/prepare_materials.py
python3 -m consensus_audit extract-requirements \
  --materials .cache/materials/source-bundle.json \
  --dry-run
```

材料转换需要系统安装 `pdftotext`（Poppler）。导入默认只读取本地缓存；增加 `--download` 可获取公开原件，也可用 `--raft-pdf`、`--dissertation-pdf` 等参数导入指定文件。缺失材料会记录为 `unresolved`，不会生成替代原文。来源和许可见 [来源清单](audit-specs/sources.yaml)。

三个模型阶段均支持 `--dry-run`：只保存待发送输入，不读取 API key、不调用模型，也不生成伪造的成功结果。定位和 prepared 需要显式提供 `--target-root`；prepared 还需要实际定位生成的映射，定位 dry-run 不会产生可用于后续审计的 `code-map.json`。

人工直接编辑要求文件，将已核对项的 `review_status` 设为 `accepted` 或 `rejected`，不确定项继续保持 `pending`。定位未找到代码时保留 `unresolved`；`located` 仅表示找到了相关位置，不表示实现正确。prepared 各任务上下文独立，允许补读外围依赖；Candidate 的 `property_id` 可以引用本任务任一已接受 requirement ID。未审核要求、未解决依赖及没有定位到代码的任务都会出现在汇总中。

完整的审核步骤、三个阶段的运行命令、预算与成本选项见 [操作说明](docs/prepared-audit.md)。当前已完成材料整理、dry-run 和 fake-client 离线链路验证；真实目标路径、材料与协议解释仍需人工确认，尚未验证真实模型效果。

## 原有模式的材料组合

`run` 和 `baseline` 不把整个 `audit-specs` 目录交给 AI。运行器根据 `catalog.yaml` 装配共同材料，性质侧再额外加入一个 Q：

```text
共同材料 = fault model + target boundary + task + protocol context + event semantics + Candidate-v0 contract
property-directed = 共同材料 + one Q
matched-no-property = 共同材料
```

当前材料集为 `raft-etcd-v1`。推荐每次只指定一个性质，例如 `Q-VOTE-1`，并为每个代码版本创建全新上下文。

批量运行时，orchestrator会按指定顺序为每个 Q 创建完全独立的消息上下文，只装入当前性质文件；上一项的 reasoning、工具结果和最终报告不会传给下一项。

当需要减少重复源码探索时，可指定 `--context-mode shared-evidence`。该模式仍为每个 Q 创建全新的模型消息上下文，但在批次目录中一次性建立机械的文件/Go 声明索引，并在各 Q 之间复用完全相同的原始 `list_files`、`search_code`、`read_file` 工具结果。索引和共享证据不包含代码语义总结、漏洞猜测、Candidate 或 verdict；每个 Q 仍须自行阅读源码并形成独立判断。

`baseline` 子命令实现 `matched-no-property`：它与性质侧获得相同的协议上下文、事件完成语义、故障模型、源码工具、预算和输出契约，只不提供具体 Q。每个 episode 最多返回一个主 Candidate，因此它测量的是同等预算下的 top-1 候选优先级。默认运行一次；重复实验需显式指定 `--episodes N`。

## 盲测边界

人工根因、mutation 说明、触发轨迹和历史结果不得放入 `audit-specs` 或目标源码树。当前人工机制卡位于 `evaluation/oracles`，材料装配器不会读取该目录；定位和审计的源码工具只能访问 `TARGET_ROOT`。要求提取阶段仅开放读取已导入材料块的 `read_material`，不开放目标源码、评价资料或历史结果。正式实验仍应保证运行环境不会把评价目录作为目标暴露给模型。

协议模型、执行器、评价器和实验结果也不应混入审计定义目录；后续扩展位置见 [架构说明](docs/architecture.md)。

## LLM 调用实现

当前默认直接调用 DeepSeek 官方 OpenAI 兼容端点：

```text
base_url = https://api.deepseek.com
model = deepseek-v4-flash
thinking = enabled
reasoning_effort = high
```

默认模型为 `deepseek-v4-flash`；需要更强模型时可以显式指定 `--model deepseek-v4-pro`。

API key 从 `--api-key-file` 指定的 UTF-8 文本文件读取。文件必须只包含一个原始 key，可以带末尾换行，但不能包含变量名、引号或多个 key。key 内容不会写入 prompt、运行元数据或日志。

定位和审计模型通过受限工具自主检查 `TARGET_ROOT`：

- `list_files`：枚举源码文件；
- `search_code`：通过 ripgrep 搜索；
- `read_file`：按行读取 UTF-8 文本；
- `run_go_test`：仅原有 `run` / `baseline` 可通过显式指定 `--allow-tests` 开放；定位和 prepared 不执行测试。

所有文件工具都限制在目标根目录内，并禁止读取 `.git`。

审计模型一旦形成临时结论，最多再进行两次可能推翻该结论的源码工具调用。审计最后一轮禁止调用工具，模型必须返回一个状态为 `candidate_found`、`no_candidate` 或 `insufficient_evidence` 的 Candidate-v0 JSON 对象。程序验证格式和代码引用来源，但不判断机制语义是否正确。原有模式默认 24 轮、80 次源码工具调用；新增的提取、定位及 prepared 默认每个块或操作任务 12 轮、40 次工具调用，均可通过参数调整。提取与定位使用各自的 JSON 输出约定，不套用 Candidate 终止指令或解析器。

## 使用方法

Python 要求 3.10 或更高版本。安装项目：

```bash
cd /home/nitro/Desktop/consensus-audit
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
```

查看材料集：

```bash
consensus-audit list-materials
```

先进行不调用 API 的材料装配检查：

```bash
consensus-audit run \
  --dry-run \
  --material-set raft-etcd-v1 \
  --property Q-VOTE-1 \
  --target-root /home/nitro/Desktop/etcd-raft
```

正式调用 DeepSeek：

```bash
consensus-audit run \
  --material-set raft-etcd-v1 \
  --property Q-VOTE-1 \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt
```

顺序审计多个性质：

```bash
consensus-audit run \
  --material-set raft-etcd-v1 \
  --property Q-VOTE-1 \
  --property Q-ELECT-1 \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt
```

审计材料集中的全部性质：

```bash
consensus-audit run \
  --material-set raft-etcd-v1 \
  --all-properties \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt
```

以“共享机械索引和原始证据、隔离性质推理”模式审计全部性质：

```bash
consensus-audit run \
  --material-set raft-etcd-v1 \
  --all-properties \
  --context-mode shared-evidence \
  --target-root /home/nitro/Desktop/experiments-etcd-raft/target-v8 \
  --api-key-file /home/nitro/Desktop/key.txt
```

运行同一 target 的 matched-no-property baseline：

```bash
consensus-audit baseline \
  --material-set raft-etcd-v1 \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt \
  --model deepseek-v4-pro
```

baseline 默认运行一个独立 top-1 episode。重复运行时显式添加 `--episodes N`；每个 episode 都使用全新的消息上下文。

## 实验口径与人工评分

最小实验比较一次 `property-directed` 与一次 `matched-no-property` top-1 运行：两侧预算和 Candidate 数量相同，处理变量是是否给出目标 Q。重复运行用于观察稳定性。它不能直接代表全仓库穷举能力。

运行器机械解析 Candidate-v0，并检查引用路径和行区间是否确实由本轮 `read_file` 返回。机制是否命中隐藏 oracle、性质关联是否正确以及 P/A/V/O 是否可用仍由人工分别评分。同一机制通过多个性质被发现时只计一个独立发现。具体口径见 [评测说明](docs/evaluation.md)。

性质较多时，也可以准备一个每行一个 ID、允许空行和 `#` 注释的文本文件：

```text
Q-VOTE-1
Q-ELECT-1
Q-TERM-1
```

然后使用：

```bash
consensus-audit run \
  --material-set raft-etcd-v1 \
  --properties-file properties.txt \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt
```

默认预算为 24 次模型调用轮次、80 次源码工具调用。可以通过 `--max-turns`、`--max-tool-calls`、`--max-output-tokens` 和 `--reasoning-effort` 调整。

## 运行产物

新增流程各自创建独立运行目录：

| 阶段     | 顶层产物                                                    | 子任务记录                                                                |
| -------- | ----------------------------------------------------------- | ------------------------------------------------------------------------- |
| 提取     | `materials.json`、`requirements.json`、`summary.json` | 每块的`input.json`、`events.jsonl`、`response.md`、`summary.json` |
| 定位     | `input.json`、`code-map.json`、`summary.json`         | 每组的输入、响应、工具轨迹、证据清单及用量                                |
| prepared | `summary.json`，包含任务、待确认项及三阶段成本汇总        | 每个操作的独立审计记录和 Candidate 校验结果                               |

上述生成结果仅在实际执行对应阶段后产生。dry-run 保存输入与状态记录，不产生要求、映射或 Candidate。格式失败、空响应和合法 `no_candidate` 会分别记录；有失败的块或任务不会使其他项从汇总中消失。没有显式提供价格时仅汇总已报告的 token 用量，金额保持为 null。

原有性质审计每次在 `runs/<timestamp>-<property>/` 中保存：

```text
request.json     非敏感运行配置
prompt.md        实际发送的系统提示和材料
events.jsonl     模型响应、reasoning、工具调用及工具结果
evidence-manifest.json  根据工具轨迹生成的客观读取/搜索/测试清单
response.md      模型最终返回的原始Candidate-v0文本
parsed-candidate.json  结构合法时解析出的Candidate-v0
candidate-format-validation.json  JSON与字段契约检查
candidate-provenance-validation.json  引用路径与实际读取区间检查
summary.json     耗时、token、轮次和最终结论
error.json       失败时的错误与已消耗预算
```

`runs/` 默认不纳入版本控制；当前只保留 `runs/m6-candidate-v0/` 作为 Candidate-v0 和 matched-no-property 的首个完整案例。

多性质运行会创建 `runs/<timestamp>-batch/`，包含：

```text
batch-request.json     批次配置和性质顺序
batch-summary.json     每项完成/失败状态与累计token
<timestamp>-Q-.../     每个性质的独立运行目录
```

单个性质失败不会阻止批次继续执行后续性质；批次结束后通过汇总文件报告失败项。

baseline 会创建 `runs/<timestamp>-baseline-batch/`，其中包含 `baseline-request.json`、`baseline-summary.json` 和该 material set 对应数量的独立 episode 目录。

模型的原始输出仍保存在 `response.md`。格式不合法时运行记录为 `invalid_output`；格式合法后生成 `parsed-candidate.json`。provenance 校验只证明模型看过所引用的代码区间，不证明引用中的自然语言主张为真。

解析器优先要求纯 JSON；如果响应包含且仅包含一个有效 JSON 代码块，或在外围说明文字后包含一个有效 JSON 对象，也会提取该对象，并在格式校验中记录其非严格格式。包含多个 JSON 对象或只有工具调用标记的响应仍为 `invalid_output`。已有运行可以在不调用模型的情况下重新解析：

```bash
consensus-audit revalidate-candidate \
  --run-directory /path/to/run
```

提前结束时，可机械提取的 JSON 直接进入 schema/provenance 校验，保留原始输出和非严格格式标记；只有无法提取 JSON 对象且尚有轮次时，才进行一次禁止工具调用的模型格式恢复，其用量计入原有预算。正式重复实验前应先提交本次代码和材料修改，并在实验记录中注明该提交；旧实验不会回填当前版本号。

`evidence-manifest.json` 不使用模型的自我描述，而是从 `events.jsonl` 重建：哪些文件真正读取了哪些区间、哪些文件只是搜索命中、运行了哪些测试、哪些工具调用失败。旧运行可以回填：

```bash
consensus-audit build-evidence \
  --run-directory /path/to/property-run
```

将一个运行目录树汇总为每次运行一行的机器事实 CSV：

```bash
consensus-audit collect-results \
  --run-root /path/to/runs \
  --output evaluation-results.csv
```

该命令只收集 Candidate 状态、模型用量、输出协议状态和源码读取成本。人工评分应从 `evaluation/score-template.csv` 复制到独立的 `annotations.csv`，不会被该命令覆盖。

`--context-mode shared-evidence` 时，批次目录还包含：

```text
shared-context/repository-index.json       机械文件/Go 声明位置索引
shared-context/shared-evidence.jsonl       首次取得的原始源码工具结果
shared-context/shared-evidence-summary.json 新取证与复用取证计数
```

这些文件不含模型的 reasoning、报告、Candidate 或跨性质 verdict。每个性质目录中的 `evidence-manifest.json` 会单独标出其使用的新取证和复用取证。

Candidate-v0 的当前职责和下游边界见 [IR说明](ir/README.md)。自动场景执行与 Case IR 尚不属于当前闭环。

## 本地验证

```bash
PYTHONPATH=orchestrator/src \
  python3 -m unittest discover -s orchestrator/tests -v
```
