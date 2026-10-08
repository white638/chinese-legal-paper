# 研究材料可得性与 F2 最小可行证据

材料可得性不是第九阶段。它是 `acquisition` 持有材料事实、`research` 持有候选判断，
并由后续设计与执行继续兑现的跨阶段硬合同：

`F0 需求拆解 → F1 低成本筛查 → 候选软聚焦 → F2 最小可行证据 → C1/C2/C3 → 问题承诺`

只有 F2 `PASS` 或经校验的窄义 `NOT_APPLICABLE` 才能启动定向批量获取、完整语料构建、
嵌入、全量综合等高成本动作。`CONDITIONAL` 必须先收窄问题、材料范围或识别要求并重新
验证；`BLOCKED`、`FAIL`、`STALE` 与迁移生成的 `NEEDS_REVIEW` 均不得放行。

## 两份机器真相

### `reference_materials/research_material_registry.json`

- schema：`avereth-research-material-registry/v1`；canonical owner 是 `acquisition`，
  `research` 可通过受控探针补写。
- 只登记材料事实：来源身份、访问与许可、时间／空间／单位覆盖、格式、所需字段、
  小样本探针和失败观察。
- 学术来源只能引用 `literature_registry.json` 中已有的 Source ID。不得在材料注册表
  复制 provider、URL、DOI 或题名形成第二个来源身份表。
- 探针证据必须是工作区内真实文件并绑定 SHA-256；凭描述、计划、API 名称或元数据
  声称“可获得”不能 PASS。
- 失败缓存以候选语义、问题版本、材料身份和探针实现版本为键。它是可重建的节流信息，
  不是 canonical 判断，也不进入 audit/output 收据的选择性证据根。

### `research_feasibility.json`

- schema：`avereth-research-feasibility/v1`；owner 是 `research`。
- 每个候选逐项裁决九维：实际访问、法律与伦理、覆盖、必需字段／角色、机器可读性、
  链接与可比性、变异或识别、成本与时间、来源稳定性。
- `PASS` 必须引用当前材料及成功探针，并绑定所选候选、问题版本、候选语义、材料基础
  与最终 feasibility basis digest。任一承重引用变化即 `STALE`。
- `NOT_APPLICABLE` 只适用于研究任务确实不需要外部经验材料的窄例外；“非定量”、
  “理论研究”或“材料以后再找”本身都不是 N/A 理由。
- 访谈、实验或其他人类参与材料在伦理与许可未满足前不得以“先做 pilot”绕过。

## F0、F1 与 F2

F0 从候选问题反推所需材料类型、字段／角色、覆盖、链接、变异／识别、许可和成本约束。
F1 只允许元数据查询、权限／伦理检查和极小样本探测；它可以淘汰明显不可行材料，不能
证明研究可执行。软聚焦后才运行 F2：实际取得最小样本，验证文件可读、字段或角色存在、
覆盖和链接成立、关键变异可观察，并将证据哈希写入注册表。

F2 是科学可证伪门，不是资料数量门。不得设置统一样本量、备选数据源配额、候选数量或
自动可行性分数。资源上限来自 `workflow_config.json.resource_policy`，其作用是熔断成本，
不是替代实质判断。

## 定量任务的轻量 F1

只有定量、计算、混合方法、用户明确找数据，或主张必须依赖结构化数据时，才读取
`quantitative-data-check.md` 并生成数据准备卡。它在 F1 平等比较 `local_file`、公开下载、API、
注册、申请、机构订阅和商业路线，只记录问题所需的分析单位、时空覆盖、变量、链接、识别、
许可、风险和下一项最低成本核验。

数据准备卡不是来源注册表、材料事实、stage、receipt 或 F2。候选状态、网页介绍、目录说明、
变量名相似和“本机已有”都不能授权定向批量获取、研究设计、因果方法或正文。正式 F2 仍须把
具体真实文件／查询结果、字段、范围、关键变异和 SHA-256 写入本合同已有的材料注册表与探针链。

## 动态绑定和传播

收据只绑定当前 selected-candidate subgraph 中实际引用的材料和探针文件。非所选候选或
无关背景材料变化不应使放行过期；所选材料、探针、问题版本或候选语义变化必须重开 F2。

`research_decision.json.research_feasibility_ref` 必须精确绑定 F2 basis；
`research_design.json.material_plan` 必须继承所选材料、探针、字段／角色、覆盖、链接、
变异与 realization rule；`method_execution.json.material_realizations` 必须绑定真实执行文件
及其 SHA-256，并逐项说明覆盖、链接、变异的实现与偏离。设计不能扩大 F2 已证明的范围，
执行不能以自由文本代替材料兑现。

## 受控命令

所有变更先输出 plan，只有显式 `--apply` 才在 transition lock 下备份并原子写入：

```powershell
& $Python -X utf8 $Controller research-materials validate paper_rewriting_output --scope acquisition --json
& $Python -X utf8 $Controller research-materials probe paper_rewriting_output `
  --material MAT-001 --adapter tabular --sample reference_materials\samples\MAT-001.csv `
  --candidate-semantic-digest <sha256> --question-version-digest <sha256> --field required_id
& $Python -X utf8 $Controller research-feasibility bind paper_rewriting_output `
  --assessment candidate-f2.json --select
& $Python -X utf8 $Controller research-feasibility resource-state paper_rewriting_output
& $Python -X utf8 $Controller research-feasibility authorize paper_rewriting_output --action directed_retrieval
```

第二次运行相同命令并加 `--apply` 才写入。`reopen` 和 `rollback` 同样遵守 plan/apply。
OpenAlex 多页获取与滚雪球等已接入 `resource_guard.py` 的高成本适配器必须提供工作区，
并在动作前取得授权；其他新增高成本适配器必须复用同一授权函数，不能自行解释 PASS。

## 迁移

旧工作区迁移只创建 `NEEDS_REVIEW` 骨架并把最早重开点设为 `acquisition` 或 `research`；
不得从已有 PDF、来源数量、设计文本、旧 PASS 收据或“曾经跑过分析”推断 F2 PASS。
迁移的创建文件、输入摘要和回滚删除都进入验证 manifest。
