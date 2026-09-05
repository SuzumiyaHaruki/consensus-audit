# 共识实现测试候选发现框架

本项目研究：给定共识实现、协议材料、故障模型和可选的目标性质，LLM 能否以较低成本提出少量、源码支撑充分、值得进入后续测试的协议违例候选场景。Candidate 是面向测试的假设，不是已确认缺陷或可达性证明。

## 当前结构

```text
consensus-audit/
├── README.md                         # 人类使用说明（不提供给 AI）
├── docs/
│   └── architecture.md               # 总体分层和扩展约定
├── evaluation/
│   ├── oracles/                       # 不提供给模型的人工机制标注
│   └── score-template.csv             # Candidate人工评分表
├── ir/
│   └── README.md                      # Candidate-v0边界和后续阶段
├── orchestrator/
│   ├── src/consensus_audit/           # 材料装配、工具循环、解析和证据校验
│   └── tests/                         # 不访问外部API的离线测试
├── pyproject.toml
└── audit-specs/                      # 可组合的审计定义
    ├── catalog.yaml                  # 材料组合清单，由实验运行器读取
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

## 材料组合

一次实验不把整个 `audit-specs` 目录交给 AI。运行器根据 `catalog.yaml` 装配共同材料，性质侧再额外加入一个 Q：

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

人工根因、mutation 说明、触发轨迹和历史结果不得放入 `audit-specs` 或目标源码树。当前人工机制卡位于 `evaluation/oracles`，材料装配器不会读取该目录；模型文件工具也只能访问 `TARGET_ROOT`。正式实验仍应保证运行环境不会把评价目录作为目标暴露给模型。

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

模型通过受限工具自主检查 `TARGET_ROOT`：

- `list_files`：枚举源码文件；
- `search_code`：通过 ripgrep 搜索；
- `read_file`：按行读取 UTF-8 文本；
- `run_go_test`：默认不开放，只有显式指定 `--allow-tests` 才可使用。

所有文件工具都限制在目标根目录内，并禁止读取 `.git`。

模型一旦形成临时结论，最多再进行两次可能推翻该结论的源码工具调用。默认 24 轮预算中的最后一轮不再提供工具，模型必须返回一个状态为 `candidate_found`、`no_candidate` 或 `insufficient_evidence` 的 Candidate-v0 JSON 对象。程序验证格式和代码引用来源，但不判断机制语义是否正确。未指定 `--allow-tests` 时，提示会明确告知模型执行工具不可用。

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

每次运行在 `runs/<timestamp>-<property>/` 中保存：

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
