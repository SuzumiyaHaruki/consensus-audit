# 两阶段准备与 prepared 审计

这条可选流程按“材料 → 要求草稿 → 人工审核 → 代码定位 → Candidate”运行。原有 `run`、`baseline`、Q 文件及历史实验保持原有口径。新增的模型提示词和材料均为英文；本文件只供人阅读。

在仓库根目录运行以下命令，无需安装新的 Python 依赖：

```bash
export PYTHONPATH="$PWD/orchestrator/src"
python3 -m consensus_audit --help
```

## 材料导入

来源清单位于 [sources.yaml](../audit-specs/sources.yaml)。原始 PDF、转换文本及材料包保存在 `.cache/materials/`，不提交版权状态不明的论文原文。程序不会把项目 Q、EVENT_SEMANTICS 或 Agent 指令冒充论文要求，也不会读取目标仓库来决定要求。

默认离线，复用已有缓存；缺失的资料会写入材料包的 `unresolved`：

```bash
python3 scripts/prepare_materials.py
```

需要重新获取公开原文时，可以显式联网下载。该命令不调用模型：

```bash
python3 scripts/prepare_materials.py --download
```

也可以导入自己提供的原件，路径由操作者设置：

```bash
python3 scripts/prepare_materials.py \
  --raft-pdf "$RAFT_PDF" \
  --dissertation-pdf "$DISSERTATION_PDF" \
  --dissertation-readme "$DISSERTATION_README" \
  --dissertation-version "$DISSERTATION_VERSION"
```

需要系统已有 `pdftotext`（Poppler）。没有论文文件时仍可导入现有范围和故障模型，但它们不能替代协议依据。

导入器保留扩展论文全文的阅读顺序文本及 layout 文本。Figure 2 按 State、AppendEntries、RequestVote、Rules for Servers 和图注分别提取，避免双栏条件交错；每块保留 PDF 页码与裁剪坐标。其余材料按原有章节标题、页内段落连续区间枚举。引用中的行号相对于块内文本，块同时保留原始页码和起始行号。正文中的跨节引用不改写；提取模型可用 `read_material` 补读材料包中的任何块。

博士论文使用 `online.pdf`，选取印刷页 27–29、40–42、48–64、72–75、136–137，包含持久化、领导权转移、PreVote 相关上下文、快照与只读操作。前言偏移为 17 页；其他版本必须核对页码。保留与 PreVote 解释相关的成员变更上下文，不把它变为当前固定成员配置的要求。每次模型调用仅装入分配块、范围/故障模型及材料索引，需要时补读关联段落，不反复放入整本博士论文。

来源版本、转换及协议解释仍需人工核对。此次已对照原 PDF 查看 Figure 2 的布局及提取结果，但所有材料块仍标为 `pending`，这不等于人工审核通过。

## 提取与人工审核

先只生成待发送输入，不读取 API key、不请求模型，也不生成 `requirements.json`：

```bash
python3 -m consensus_audit extract-requirements \
  --materials .cache/materials/source-bundle.json \
  --dry-run
```

以下真正调用模型的命令仅供日后明确授权后执行。本次实现没有执行它们。`API_KEY_FILE` 由操作者提供，必须指向现有客户端支持的单 key 文本文件：

```bash
EXTRACT_RUN=$(python3 -m consensus_audit extract-requirements \
  --materials .cache/materials/source-bundle.json \
  --api-key-file "$API_KEY_FILE")
```

实际输入在每块的 `input.json`；响应和工具轨迹在 `events.jsonl`，最终原始文本在 `response.md`。`summary.json` 记录用量、恢复和错误。顶层保存 `materials.json` 和生成的 `requirements.json`。失败块仍有 `block_results` 和系统生成的 `unresolved`，不冒充成功提取。每次调用至多一次格式恢复，恢复用量计入同一预算。

直接编辑 `$EXTRACT_RUN/requirements.json`，逐条核对主体、触发条件、量词、时序、例外、变体及引用。`explicit` 必须有直接原文支持，`derived` 必须写出推导依据；不确定之处留在 `unresolved`。可以把 `review_status` 改为 `accepted`、`rejected`，或继续保留 `pending`。程序不会自动接受要求，也不会将自身结构校验当成人工语义审核。修订了要求或材料后需要重新定位。

```bash
python3 -m consensus_audit validate-requirements \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --materials "$EXTRACT_RUN/materials.json"
```

此命令检查结构、引用和块记录，同时显示未接受要求、环境假设和 unresolved；通过不代表协议含义正确。API 产物标为 `generation=model_api`，注入客户端产物标为 `injected_client`，离线 fixture 明确标为 synthetic。fixture 中的 accepted 仅模拟测试中的人工审核，不能用于正式协议实验。

## 定位与 prepared 审计

`TARGET_ROOT` 必须由操作者明确设置为被测源码版本的路径。程序不猜历史实验路径，不读取最新上游文档替代目标版本。定位和 prepared 只开放已有的源码读取、搜索、列目录工具，不执行测试或修改目标。

定位 dry-run 需要已审核的 requirements，但不调用模型：

```bash
python3 -m consensus_audit locate-code \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --target-root "$TARGET_ROOT" --dry-run
```

经授权后真正定位：

```bash
MAP_RUN=$(python3 -m consensus_audit locate-code \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --target-root "$TARGET_ROOT" --api-key-file "$API_KEY_FILE")
```

定位只使用 accepted 要求，同一操作共享一次定位上下文。跨操作要求定位一次，仍保留其完整 operation 列表。没有找到代码、预算耗尽或输出失败会保留 unresolved；`not_applicable` 需要配置或原文依据，找不到函数不能作为理由。

`code-map.json` 记录各要求的位置、职责、契约引用和未知依赖。引用通过同次 `read_file` 的实际返回区间核对。复用映射时比较原有输入、目标路径/Git 版本及已读取区间的原始工具结果，不新增内容 hash、冻结文件或整仓快照。这不是整仓变更检测：未读取依赖的变化仍需要操作者重新定位。应保留整个定位运行目录，避免丢失输入及引用轨迹。

prepared dry-run 必须使用实际定位所得映射，不能把定位 dry-run 当成成功结果：

```bash
python3 -m consensus_audit prepared \
  --materials "$EXTRACT_RUN/materials.json" \
  --requirements "$EXTRACT_RUN/requirements.json" \
  --code-map "$MAP_RUN/code-map.json" \
  --target-root "$TARGET_ROOT" --dry-run
```

授权后，将末尾 `--dry-run` 换成 `--api-key-file "$API_KEY_FILE"` 即执行审计。

prepared 按 operation 分组，跨操作要求保留在相关组内，重复起始代码区间去重。各任务使用全新上下文，只带本组要求、关联原文、范围/故障模型、已接受假设、映射与未知依赖、Candidate-v0 契约。模型需要重新读取原始代码，也可以补读外围依赖；定位对话和其他任务的完整对话不会传入。

Candidate 的 `property_id` 可以引用本组任一 accepted requirement；有候选时必须引用，没有候选时可以为 null。空响应、非法输出和合法 `no_candidate` 分开记录。没有定位到代码的任务仍然运行并出现在汇总里，单个任务失败不阻止其余任务。

各顶层 `summary.json` 显示任务状态和待确认项。prepared 汇总还包含 `unresolved_dependencies`、未审核/拒绝要求及三阶段已报告的 token 用量。若缺少某阶段的原运行目录，其成本标为缺失。可用 `--input-price`、`--cached-input-price`、`--output-price` 指定同一币种的每百万 token 价格；未提供价格或用量明细时，金额为 null，不猜测价格。没有返回用量的失败 API 请求无法据此推算账单金额。

退出码 0 表示运行完成或 dry-run 输入已保存；2 表示有失败/未完整处理的块、任务，或没有 accepted 要求。应查看命令打印目录中的汇总，而不是仅依据退出码判断覆盖情况。

## 离线验证与待确认项

```bash
PYTHONPATH=orchestrator/src python3 -m unittest discover -s orchestrator/tests -v
```

测试使用独立 synthetic fixture 和 fake client，覆盖提取隔离、块记录与引用、人工状态、定位遗漏、实际代码读取、过期输入、prepared 上下文隔离、补读依赖、Candidate ID、有限恢复、错误用量以及三阶段 dry-run。旧模式测试继续运行，不需要真实目标或密钥。

本次已取得公开论文及指定 Git 版本的博士论文材料，并完成材料转换和提取 dry-run。尚未确定正式目标路径、没有人工接受的真实要求，也没有真实模型提取、定位或审计结果。尤其需要核对 Figure 2 的 `lastApplied` 与作者勘误、PreVote/领导权转移变体、异步存储完成/发布契约、租约读的时钟假设。上述问题保存在材料包 `unresolved` 中，不会静默移出范围。

能力实现和离线测试通过不表示真实模型效果已经验证，也不表示所有要求得到覆盖或优于旧实验模式。
