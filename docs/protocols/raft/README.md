# Raft 材料

Raft 原文、许可、版本和协议疑点维护在 [协议来源清单](../../../audit-specs/protocols/raft/sources.yaml)，转换脚本位于 [scripts/protocols/raft/prepare_materials.py](../../../scripts/protocols/raft/prepare_materials.py)。实现范围另放在 `audit-specs/protocols/raft/targets/<implementation>/`，不会由 Raft 导入器默认选择。

导入需要 Poppler `pdftotext`。默认只读本地缓存，添加 `--download` 可获取公开原件。原件和转换文本默认保存在 `.cache/materials/raft/`；材料包通过必填的 `--output` 指定位置，避免不同实现互相覆盖。

导入器保留 Raft 扩展论文原文、阅读顺序文本和 layout 文本。Figure 2 按 State、AppendEntries、RequestVote、Rules for Servers 和图注分别提取，保留 PDF 页码及裁剪坐标，避免双栏条件交错。其他正文按原有标题和连续行区间分块。

博士论文使用 `online.pdf`，默认版本见来源清单，导入印刷页 27–29、40–42、48–64、72–75、136–137，涉及持久化、领导权转移、PreVote、快照与只读操作，并保留作者勘误。该版本的前言偏移为 17 页；导入其他版本时必须核对页码与章节，不能把所有协议变体视为通用要求。

本地文件可以显式导入：

```bash
python3 scripts/protocols/raft/prepare_materials.py \
  --raft-pdf "$RAFT_PDF" \
  --dissertation-pdf "$DISSERTATION_PDF" \
  --dissertation-readme "$DISSERTATION_README" \
  --dissertation-version "$DISSERTATION_VERSION" \
  --target-spec "$TARGET_SPEC" \
  --output "$MATERIALS"
```

`TARGET_SPEC` 是所选 Raft 实现的来源配置文件，`MATERIALS` 是输出材料包路径。它们与审计时的实际源码路径 `TARGET_ROOT` 分开。没有实现配置时只导入协议材料，并明确记录尚未选择实现范围和故障模型。资料缺失、转换问题和扩展适用性继续留在 `unresolved`，不以自己的协议总结替代原文。

`PROTOCOL_CONTEXT.md` 与 `EVENT_SEMANTICS.md` 是项目定义，仍留在 Raft 目录中供参考，不冒充论文要求或自动进入模型输入。当前实现示例见 [etcd/raft](targets/etcd-raft.md)。
