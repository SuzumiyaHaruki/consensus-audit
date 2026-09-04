# 共识实现性质审计框架

本项目用于研究“AI 根据协议性质审计具体共识实现，并提出可验证违例场景”。目前以 Raft 和 `etcd/raft` 进行首轮实验，但框架不绑定单一协议、实现或模型服务。

## 当前结构

```text
consensus-audit/
├── README.md                         # 人类使用说明（不提供给 AI）
├── docs/
│   └── architecture.md               # 总体分层和扩展约定
├── ir/
│   ├── README.md                     # Candidate/Case职责和下游消费边界
│   └── templates/                    # 最小、可修改的YAML草案
├── orchestrator/
│   ├── src/consensus_audit/           # 材料装配、LLM工具循环和产物记录
│   └── tests/                         # 不访问外部API的离线测试
├── pyproject.toml
└── audit-specs/                      # 可组合的审计定义
    ├── catalog.yaml                  # 材料组合清单，由实验运行器读取
    ├── baseline/                     # 无性质对照任务和报告格式
    │   ├── AUDIT_TASK.md
    │   └── REPORT_TEMPLATE.md
    ├── common/
    │   ├── AUDIT_TASK.md             # 跨协议通用审计任务
    │   └── REPORT_TEMPLATE.md        # 统一Markdown报告格式
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

一次实验不应把整个 `audit-specs` 目录都交给 AI。运行器根据 `catalog.yaml` 组合共享材料与当前审计分支的专属材料。

```text
性质审计 = shared fault model + shared target boundary + guided task + protocol context + event semantics + one Q + guided report template
baseline = shared fault model + shared target boundary + baseline task + baseline report template
```

当前材料集为 `raft-etcd-v1`。推荐每次只指定一个性质，例如 `Q-VOTE-1`，并为每个代码版本创建全新上下文。

批量运行时，orchestrator会按指定顺序为每个 Q 创建完全独立的消息上下文，只装入当前性质文件；上一项的 reasoning、工具结果和最终报告不会传给下一项。

当需要减少重复源码探索时，可指定 `--context-mode shared-evidence`。该模式仍为每个 Q 创建全新的模型消息上下文，但在批次目录中一次性建立机械的文件/Go 声明索引，并在各 Q 之间复用完全相同的原始 `list_files`、`search_code`、`read_file` 工具结果。索引和共享证据不包含代码语义总结、漏洞猜测、Candidate 或 verdict；每个 Q 仍须自行阅读源码并形成独立判断。

`baseline` 子命令读取 material set 的共享材料和 baseline 专属材料，但不会装入 protocol context、event semantics 或任何 Q。未显式指定 `--episodes` 时，episode 数等于该 material set 的性质数，以匹配 `--all-properties` 的独立审计预算。

## 盲测边界

人工根因、mutation 说明、正确代码切片、触发测试和历史实验结果不得放入 `audit-specs`。将来需要的隐藏评价材料应由独立存储和权限边界管理，运行 AI 时不要挂载或暴露。

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

模型一旦形成临时结论，最多再进行两次可能推翻该结论的源码工具调用。默认 24 轮预算中的最后一轮为强制报告轮：该轮不再提供任何工具，模型必须基于已有证据返回 `credible_risk`、`no_credible_risk` 或 `insufficient_evidence`。程序只限制调查期限，不替模型判断证据是否充分。未指定 `--allow-tests` 时，提示会明确告知模型执行工具不可用。

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

运行同一 target 的无性质 baseline：

```bash
consensus-audit baseline \
  --material-set raft-etcd-v1 \
  --target-root /home/nitro/Desktop/etcd-raft \
  --api-key-file /home/nitro/Desktop/key.txt \
  --model deepseek-v4-pro
```

baseline 默认根据 material set 的性质数量创建 episode；`raft-etcd-v1` 当前因此运行 7 次。每个 episode 都使用全新的消息上下文，也可用 `--episodes` 显式覆盖。

## 实验口径与人工评分

“给定正确 Q 后能否发现对应机制”是条件审计实验，只评价 property-conditioned audit，不能直接与多 episode baseline 比较。端到端发现实验必须在同一个 target 上让性质侧运行 `--all-properties`，让 baseline 运行默认的同数量 episode，然后分别按全部报告的 finding 并集判断是否命中目标机制。

运行器只保存原始报告与 evidence manifest，不机械判断报告质量。隐藏人工评价按 detection、property linkage、scenario adequacy 和 evidence fidelity 四层记录；同一机制在多个 baseline episode 中重复出现时，target-level detection 只计一次。具体表格和口径见 [评测说明](docs/evaluation.md)。

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
response.md      模型最终返回的Markdown审计报告
summary.json     耗时、token、轮次和最终结论
error.json       失败时的错误与已消耗预算
```

`runs/` 默认不纳入版本控制。

多性质运行会创建 `runs/<timestamp>-batch/`，包含：

```text
batch-request.json     批次配置和性质顺序
batch-summary.json     每项完成/失败状态与累计token
<timestamp>-Q-.../     每个性质的独立运行目录
```

单个性质失败不会阻止批次继续执行后续性质；批次结束后通过汇总文件报告失败项。

baseline 会创建 `runs/<timestamp>-baseline-batch/`，其中包含 `baseline-request.json`、`baseline-summary.json` 和该 material set 对应数量的独立 episode 目录。

模型只要停止调用工具并返回非空最终内容，运行就视为完成。程序将内容原样保存为 `response.md`，不解析 Markdown，也不机械判断证据是否充分、结论是否正确；这些工作由人工审查完成。

`evidence-manifest.json` 不使用模型的自我描述，而是从 `events.jsonl` 重建：哪些文件真正读取了哪些区间、哪些文件只是搜索命中、运行了哪些测试、哪些工具调用失败。旧运行可以回填：

```bash
consensus-audit build-evidence \
  --run-directory /path/to/property-run
```

`--context-mode shared-evidence` 时，批次目录还包含：

```text
shared-context/repository-index.json       机械文件/Go 声明位置索引
shared-context/shared-evidence.jsonl       首次取得的原始源码工具结果
shared-context/shared-evidence-summary.json 新取证与复用取证计数
```

这些文件不含模型的 reasoning、报告、Candidate 或跨性质 verdict。每个性质目录中的 `evidence-manifest.json` 会单独标出其使用的新取证和复用取证。

分析报告中的可信风险后续先表示为 [Candidate IR](ir/README.md)，相关 Q的同根风险经整合和语义复核后形成 Case IR，再交给 TLA+和执行器。

## 本地验证

```bash
PYTHONPATH=orchestrator/src \
  python3 -m unittest discover -s orchestrator/tests -v
```
