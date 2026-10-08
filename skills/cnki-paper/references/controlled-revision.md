# 受控稿件修订

## 适用范围与资格

`manuscript_revision` 接受两种入口：已有 CNKI-Paper 工作区，或一篇 Word、Markdown、LaTeX 旧稿。二者都先建立 `revision_contract.json`，不从文件名或用户一句“润色”猜测修改影响。

只有可证明不改变含义、标题、主张、证据集、范围且不形成最终稿交付的局部改字可留在 Direct route；新增文献、稿内贡献句替换、标题、范围或最终文件交付即使只涉及一处，也从这里进入正式修订。

## 修改分类与最早重开阶段

| 修改类 | 典型变化 | 最早阶段 |
|---|---|---|
| `surface` | 标点、格式、无含义变化的措辞 | build |
| `argument` | 使用现有证据重组论证 | build |
| `evidence` | 新文献、新主张、标题实质变化、范围变化 | research |
| `design` | 识别策略、测量、方法或选案变化 | design |
| `execution` | 分析、结果、偏离或负面发现变化 | execution |

多个修改同时存在时取最上游阶段。`cnki-manuscript-revision/v2` 合同保存基线文件 SHA-256、逐项修改要求、受影响 Source／Claim／Design／Execution／Manuscript 身份、最早阶段、授权证据和保证等级；每个 `requested_changes[]` 还必须以非空且全合同唯一的 `target_finding_keys[]` 绑定 RFK。来自审阅的修改复用 `review_findings.json` 中的规范 key；无审阅来源的用户修改由初始化器按 change ID、类别和摘要生成稳定的合同内 RFK。至少登记一个受影响身份，初始化暂时无法细分时以基线稿路径作为整稿身份，实施前再收窄到真实单元。初始化会把原稿封存到 `revision_baseline/`；单篇外部稿另复制为工作稿，后续修改工作稿而不是覆盖唯一原件。每次验证都复核封存副本哈希，不能用已经改过的稿件冒充基线。

每轮修改必须新建 `revision_worktree/RB-NNN/` 隔离候选稿。`batch-start` 同时声明本批执行的 change ID 与全部 RFK；batch 的 `target_finding_keys[]` 必须与活动 change 绑定的 key 并集精确相等，任何未覆盖或遗漏都阻塞。候选稿可反复编辑，但规范稿在 preflight 前保持不变。`revision_impact.json` 由规范稿与候选稿的真实内容单元 diff、Finding 覆盖、声明身份和 research/design/execution 权威摘要确定性生成；漏报或多报的单元、Finding 未覆盖、未授权权威漂移、空差异都阻塞。通过后 `promote` 以临时文件替换方式一次性更新规范稿和 batch 记录；同一 batch 的 `promotion_count` 永远不得超过 1。

门禁按该边界复用已经封存的上游工作，而不是让轻量修订重新要求整套研究工件。`surface` 的 build 至少证明工作稿位于修订工作区且内容哈希已经相对基线变化；`argument` 还须以 `rewrite_matrix.md` 或 `dialogic_argument_map.md` 说明现有证据如何被重组。只有回到 research/design/execution 的修订才重新要求其后全部承重合同。audit/output 始终执行完整适用审计，轻量 build 不等于完整论文通过。

## 保证等级

- `full`：当前工作区从 acquisition 到 output 的承重合同完整且可验证。
- `reconstructed`：旧稿的来源、问题、设计、执行和正文身份已重建并通过相应门禁。
- `legacy_limited`：只能审计问题或进行不改变含义的局部表层修改；不得声称“完整学术论文已通过”，不得取得 output PASS。

无论修改表面多小，若用户要求最终完整交付，文献积累仍须达到动态基线或合法兜底。新增文献、新主张、范围和标题实质变化必须回 research 并重新经过用户问题确认；方法和执行变化分别回 design 与 execution。

默认保证等级为 `legacy_limited`，因为单篇文件本身不能证明来源、设计和执行链已经重建。只有实际补齐并验证后才能上调。

旧 `cnki-manuscript-revision/v1` 只能读取和审计；运行 `revision_contract.py migrate OUTDIR --apply` 才会备份旧合同并升级。迁移不会推断不存在的 batch、impact 或复核事实。

## 命令入口

```powershell
$Revision = Join-Path $AverethHome 'skills\cnki-paper\scripts\revision_contract.py'
& $Python -X utf8 $Revision init OUTDIR MANUSCRIPT --publication-track cnki-cn `
  --change "surface:修正标点与格式" --finding-key RFK-0123456789ABCDEF01234567 `
  --authorization-evidence "用户本轮要求"
& $Python -X utf8 $Revision validate OUTDIR --stage build
& $Python -X utf8 $Revision batch-start OUTDIR --batch-id RB-001 `
  --change-id CH-001 --finding-key RFK-0123456789ABCDEF01234567
# 只编辑 OUTDIR/revision_worktree/RB-001/revision_candidate.*
& $Python -X utf8 $Revision impact OUTDIR --batch-id RB-001 --accept-actual-diff
& $Python -X utf8 $Revision promote OUTDIR --batch-id RB-001
```

示例中的 `cnki-cn` 必须替换为本任务真实的 `cnki-cn`、`international-ssci` 或
`mixed` 轨道；不得由控制器猜测。

审阅驱动修订应在 `init` 时把每个真实 RFK 按顺序用 `--finding-key` 绑定到对应
`--change`；两者数量不等、RFK 格式错误或重复时命令 fail-closed。没有上游 Finding
的独立修订可省略该参数，此时控制器生成仅限本合同使用的稳定 RFK。
