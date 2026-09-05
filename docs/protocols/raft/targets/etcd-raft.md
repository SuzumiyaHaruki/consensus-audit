# etcd/raft 审计配置

实现配置位于 [sources.yaml](../../../../audit-specs/protocols/raft/targets/etcd-raft/sources.yaml)，复用已有 [目标范围](../../../../audit-specs/protocols/raft/targets/etcd-raft/TARGET_BOUNDARY.md) 和 [crash-recovery-cft 故障模型](../../../../audit-specs/fault-models/crash-recovery-cft.md)。范围仍包含固定成员、同步与异步存储、两种 PreVote 设置、快照、只读模式及领导权转移。

在仓库根目录准备材料并检查提取输入：

```bash
export PYTHONPATH="$PWD/orchestrator/src"
MATERIALS=.cache/materials/raft/etcd-raft/source-bundle.json
python3 scripts/protocols/raft/prepare_materials.py \
  --target-spec audit-specs/protocols/raft/targets/etcd-raft/sources.yaml \
  --output "$MATERIALS"
python3 -m consensus_audit extract-requirements --materials "$MATERIALS" --dry-run
```

默认离线读取 `.cache/materials/raft/`；需要获取原文时在导入命令中加 `--download`，或按 [Raft 材料说明](../README.md) 显式提供本地 PDF。不会扫描其他目录寻找目标或材料。

下面是真实模型调用的最短流程，仅在操作者明确授权并设置 `API_KEY_FILE` 后执行。`TARGET_ROOT` 必须显式指向实际被测 etcd/raft 版本：

```bash
EXTRACT_RUN=$(python3 -m consensus_audit extract-requirements \
  --materials "$MATERIALS" --api-key-file "$API_KEY_FILE")

# Human step: edit requirements.json, review sources and operations,
# and set only confirmed requirements to review_status=accepted.
python3 -m consensus_audit validate-requirements \
  --materials "$EXTRACT_RUN/materials.json" --requirements "$EXTRACT_RUN/requirements.json"

MAP_RUN=$(python3 -m consensus_audit locate-code \
  --materials "$EXTRACT_RUN/materials.json" --requirements "$EXTRACT_RUN/requirements.json" \
  --target-root "$TARGET_ROOT" --api-key-file "$API_KEY_FILE")

python3 -m consensus_audit audit \
  --materials "$EXTRACT_RUN/materials.json" --requirements "$EXTRACT_RUN/requirements.json" \
  --code-map "$MAP_RUN/code-map.json" --target-root "$TARGET_ROOT" --api-key-file "$API_KEY_FILE"
```

各模型阶段均可改用 `--dry-run`，但不会生成供下一阶段使用的成功结果。目标 README、`doc.go`、公开类型、接口及配置注释在定位或审计需要时读取，不能以最新上游文档替代目标版本。

人工待确认项包括具体目标路径和版本、PreVote/领导权转移变体、Figure 2 的 `lastApplied` 与作者勘误、异步存储完成和发布语义，以及租约读所需的时钟假设。这些问题分别保存在 Raft 来源清单和本实现配置中，不会被默认带入其他 Raft 实现。
