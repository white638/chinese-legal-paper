# 可验证的同行评审与返修闭环

本协议规定 audit 内部的审稿生命周期。它不新增机器阶段：`cnki-paper` 仍以
`intake → acquisition → research → design → execution → build → audit → output`
八状态为唯一控制脊柱。Methods、Contribution、Clarity 三位评审只产生只读意见；
评审结果、编辑裁决、返修和复核都不能自行推进阶段或签发完成凭证。

## 权威顺序

审稿事实按以下顺序单向流动：

```text
canonical manuscript snapshot
  → immutable reviewer outputs
  → review_assurance.json (cnki-review-assurance/v2)
  → review_findings.json (avereth-review-findings/v3)
  → review_resolution.json (avereth-review-resolution/v2)
  → structured_review.md / reviewer_audit.md / revision_plan.md
```

- 三份 `review_prompts/*_review_output.md` 是不可改写的来源证据；每份由输出文件
  SHA-256 和逐 Finding 来源块 SHA-256 封印。
- `review_findings.json` 是原始意见的唯一机器投影。编辑不得手工删项、改写问题、
  降低严重性或把两条意见合并成一条而不留下裁决。
- `review_resolution.json` 是裁决、返修、核销和再开的唯一权威。
- `structured_review.md`、`reviewer_audit.md`、`revision_plan.md` 只由上述 JSON
  确定性生成。不得手填、补行、改状态或把 Markdown 当作第二事实源。

## 1. 冻结稿件并派发严格 v2 评审

先确定可评审的规范稿，再运行 dispatch。`review_manifest.json` 会封印
`review_run_id`、规范稿路径与 SHA-256、三份 prompt 摘要。一个 review run 只审这一份
稿件快照；稿件或 prompt 改变后必须产生新的 run，不能覆盖旧的 Finding registry。

```powershell
$StructuredReview = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\structured_review.py'
& $Python -X utf8 $StructuredReview paper_rewriting_output `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --dispatch
```

把三份 prompt 分别交给 `avereth_methods`、`avereth_contribution`、
`avereth_clarity`。每位评审只能看到自己的生成 prompt，不能读取另一位的 prompt、输出、
编辑综合、assurance 或控制器状态。Contribution prompt 可以包含 `Sanitized Confirmed Semantic Context`；三位
评审都不得看到、猜测或生成内部 Claim/Evidence/Design/Execution ID。内部身份由后续
mapper 根据可观察的稿件位置和引文片段补齐。

每份原始输出必须使用严格 v2 合同：

- 一张精确五列表：`Dimension ID | Applicability | Score | Reason | Manuscript Location`；
- `Applicability` 只允许 `APPLICABLE`、`NOT_APPLICABLE`、`BLOCKED`；只有
  `APPLICABLE` 使用 1–5 分，其余为 `N/A`；
- 一行 `Review Verdict: PASS|FINDINGS`；PASS 可以没有 Finding，禁止为数量造问题；
- 每条真实 Finding 包含 `Finding ID`、`Severity`、`Confidence`、`Category`、
  `Location`、`Quoted Span`、`Issue`、`Reader Consequence`、`Repair Kind`、
  `Owner Stage`、`Text Action`、`Recommended Action`、`Net Word Delta`；
- `Repair Kind` 必须区分 `TEXT_EDIT`、`ADD_EVIDENCE`、`RERUN_ANALYSIS`、
  `REDESIGN`、`REOPEN_RESEARCH`、`NARROW_CLAIM`、`REMOVE_CLAIM`、
  `NO_ACTION`；科学问题不能伪装成措辞问题；
- Overall Score 只是可选诊断，不能抵消 Critical 或 Major。

Venue Fit 只有在已验证目标刊合同存在时才可 `APPLICABLE`；缺少必要合同使用
`BLOCKED`，稿件未触发时使用 `NOT_APPLICABLE`。目标刊名称或一般印象不能自行把它
升级为可评分状态。中文顶刊的 anatomy 0/1/2 量规只是补充语义诊断，不能替代这张精确
五列表，也不另建平均分硬门。

## 2. 如实登记 assurance v2

三份输出落盘后，主线程写 `review_assurance.json`：

- `schema_version=cnki-review-assurance/v2`；
- 同一 `review_run_id` 和被审稿件 path/SHA-256；
- 每位 reviewer 的真实 role、`context_id`、prompt path/SHA-256、output path/SHA-256、
  `input_scope` 与如实的隔离声明；`independent` 必须为 `isolation_declared=true`，
  `single_agent` 必须为 `isolation_declared=false`；
- Methods 与 Clarity 的 `input_scope=manuscript_only`；Contribution 使用
  `manuscript_and_sanitized_confirmed_semantics`；
- 只有三个 context ID、三条输出路径和三个非空输出 SHA-256 都彼此不同，才可声明
  `mode=independent`；否则如实写 `single_agent`。

文本相似度只形成 `textual_diversity_score`，用于发现复制或模板污染；它不是独立性
分数。独立性只由上下文、输入边界和文件身份链证明。

`cnki-review-assurance/v1` 仅作为旧工作区的只读历史证据显示
`legacy_read_only_needs_review`。它不能推断 Severity、VERIFIED、稿件身份或独立性，
也不能授权新的 audit receipt；必须重新派发 v2 review run。

## 3. 编译 Finding registry

先验证三份原始输出，再编译 registry 和 resolution scaffold：

```powershell
$ReviewLifecycle = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\review_lifecycle.py'
& $Python -X utf8 $StructuredReview paper_rewriting_output `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --validate paper_rewriting_output/review_prompts
& $Python -X utf8 $ReviewLifecycle paper_rewriting_output compile `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --write
```

编译器逐项建立稳定 `REV-MET-*`、`REV-CON-*`、`REV-CLR-*` Finding，保留来源
role/context/output SHA、来源块 SHA、原始 Severity/Confidence、稿件 locator、问题、
读者后果和返修责任。内部 mapper 再读取工作区的 Claim/Evidence/Design/Execution 事实，
把映射明确标为 `exact`、`inferred`、`unresolved` 或 `not_applicable`。Critical/Major
必须完成 `exact|inferred` 映射；`unresolved` 时不得进入返修或核销。

零 Finding 只有在三份不可变来源 verdict 都精确为 PASS 时合法。此时 registry 为
`NO_MATERIAL_OBJECTIONS`，resolution 同名且没有行；不创建虚假 Objection。任一来源为
FINDINGS、来源集合不完整或稿件 SHA 变化，都不能走零意见 PASS。

## 4. 裁决、路由与显式授权

`review_resolution.json` 初始化时每条 Finding 都是 OPEN。状态只沿合法历史迁移：

```text
OPEN → PLANNED → APPLIED → VERIFIED
OPEN/PLANNED → MERGED | REJECTED | WAIVED
APPLIED/VERIFIED/WAIVED → REOPENED → PLANNED/APPLIED
```

- coverage 必须精确等于原始 Finding ID 集；遗漏或新增 ID 直接失败；
- Severity 改变必须登记 original/final、裁决理由、裁决者身份和 context；
- Critical 不得普通 WAIVED；须真正修复并 VERIFIED，或删除其使之致命的核心主张；
- REJECTED、WAIVED、MERGED 都须满足各自裁决、授权或目标 Finding 闭合合同；
- gate 看 Finding 生命周期，不用 Reviewer 平均分或 editor `/100` 总分抵消问题。

`revision_plan.md` 只是 JSON 派生的路由计划。路由复用现有
`revision_contract.route_for_change_classes`，再与 reviewer 的 `owner_stage` 合并为
`effective_earliest_reopen_stage`；它不得直接修改 research/design/execution/build：

- `full_paper`：报告应重开的既有最早阶段；
- `manuscript_audit`：保持只读，只请求扩展为可修订 profile；
- `manuscript_revision`：要求显式授权且逐 Finding 覆盖的 `revision_contract.json`
  amendment；合同未覆盖 Finding ID 或声明阶段过晚时继续阻塞。

得到用户授权后，仍由 `cnki-paper` controller 按最早责任阶段执行返修。不得在 audit
里静默改上游工件，也不得为审稿生命周期增加第九阶段。

## 5. APPLIED 与 VERIFIED 的最低证据

APPLIED 不是“已写好修复计划”。它至少绑定：被审稿件 before SHA、实际 after SHA、当前
稿件路径、非空真实 diff、`changed_locations`、`change_summary`、执行者身份/context、
受影响 Claim/Evidence/Design/Execution ID，以及科学返修所需的真实 rerun artifact
identity、kind、路径与 SHA-256。所有科学返修都拒绝配置、prompt／原始 reviewer output、
JSON 派生视图、canonical controller 文件和规范稿充当工件；`RERUN_ANALYSIS` 还必须逐项
精确匹配 `method_execution.json.runs[].artifacts` 的 ID／路径／SHA，并在声明受影响
Execution ID 时匹配所属 run。其他 kind 必须匹配其 acquisition/design 权威登记，不能用
任意工作区文件代替。`method_execution.json` 是 dispatch 时封印的 mapper 输入；合法更新
该权威后须归档旧 run 并重新 dispatch，不能为核销绕过 input digest。

任何实际稿件变化都必须先经 `revision_contract` v2 batch 的 preflight 与单次 promotion，
再追加 `review_cycles[]`。每个 cycle 绑定 batch、父 cycle、before/after SHA、不可变
`revision_impact.json`、实际 changed unit 集、required/dispatched/reused reviewer 分区、
逐角色 input digest 和不可变输出。只影响表述时通常只派 Clarity；argument 变化派
Contribution+Clarity；evidence 变化或 design/execution 权威漂移进入 FULL 三审。
DELTA prompt 只提供真实 changed units、该角色依赖投影与获准确认语义；FULL prompt
向三名角色分别提供完整规范稿，同时标出 changed units、依赖闭包、角色职责与 rubric。
`FULL` 不是只改 manifest.mode 的扩大派发，Reviewer 必须实际审阅完整稿。
FINDINGS/BLOCKED cycle 都保留，不覆盖为 PASS；当前规范稿只有在 cycle tip 精确绑定
其 SHA 且最新 cycle 为 PASS 时才可 CLOSED。逐 Finding 的 VERIFIED 证据仍不可省略。

`finding_key` 由角色、稳定类别、真实 repair kind、映射身份和内容型稿件单元确定，不取决于
Issue 句式或段落序号。增量意见必须分类为 `UNRESOLVED_EXISTING`、
`REVISION_REGRESSION`、`NEW_MATERIAL` 或 `OPTIONAL_POLISH`；后者进入 optional backlog，
不阻塞交付。跨 key 合并只能由编辑以 identity-graph 依据显式裁决。相同 key 第二次
REOPENED 后，resolution 必须登记 instruction failure、owner-stage check、rewrite scope、
claim/evidence change、reviewer conflict 与 next strategy 六项根因分析，之后才可继续。

增量派发和周期编译使用 batch 内不可变 impact，不使用会被下一批覆盖的顶层便捷视图：

```powershell
$StructuredReview = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\structured_review.py'
$ReviewLifecycle = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\review_lifecycle.py'
$Impact = 'paper_rewriting_output/revision_worktree/RB-001/revision_impact.json'
& $Python -X utf8 $StructuredReview paper_rewriting_output `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --dispatch-delta --impact-manifest $Impact --cycle-id RC-001 --json
# reviewer 原始输出与 cycle_assurance.json 写入 review_prompts/cycles/RC-001/ 后：
& $Python -X utf8 $ReviewLifecycle paper_rewriting_output cycle `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --cycle-id RC-001 --write --json
```

dispatch manifest 中 `required_reviewers` 必须精确等于 impact 路由，且
`dispatched_reviewers` 与 `reused_reviewers` 形成不重叠、无遗漏的分区；复用项还须由
`reused_from_cycles` 指向较早的同角色 PASS cycle，并保持 role input digest 相同。该摘要
只计算该角色真正消费的 role impact、changed-unit 文本、FULL 时的完整稿、依赖闭包、
获准确认语义及 reviewer/dispatch 实现摘要；整篇 `after_sha256` 身份字段只绑定 cycle，
不得作为 DELTA 复用键。authority 只有投影进 dependency context 或确认语义才进入摘要：
未投影的无关行变化不会强制重跑，被投影的 design/execution/confirmed 语义或 reviewer
实现变化会使相关摘要失效。

Critical/Major 的 VERIFIED 还必须：

- 复核当前规范稿，`verified_against_sha256` 精确等于 after/current manuscript SHA；
- 保存 verification method、result、remaining boundary、验证输出 SHA；
- 验证输出固定写入 `review_prompts/verifications/<FindingID>.md`，工件本身必须回显
  review run ID、Finding ID、before/current SHA、method、remaining boundary、PASS、
  verifier identity/context；原始 reviewer output、prompt 或 dispatch 文件不得复用；
- verifier 的 identity 和 context 都与 applier 不同；
- 对 abstract、introduction、analysis/results、conclusion、figures/tables、
  response materials 逐项登记 `CHECKED` 及证据，或有理由的 `NOT_APPLICABLE`；
- 若复核发现问题仍在，转为 REOPENED，不能修改状态文字冒充关闭。

只有全部原始 Finding 成为合法终态，顶层 resolution 才可为 CLOSED。缺少 resolution
时工具可以生成 OPEN scaffold 和派生视图，但 audit 必须 fail closed。

## 6. 只从 JSON 生成视图并验收

更新 canonical JSON 后运行：

```powershell
& $Python -X utf8 $ReviewLifecycle paper_rewriting_output validate `
  --manuscript paper_rewriting_output/final_paper/main.tex `
  --write
& $Python -X utf8 $Controller status paper_rewriting_output --json
& $Python -X utf8 $Controller gate paper_rewriting_output --stage audit
```

生成视图固定为：

- `structured_review.md`：来源 verdict、全部 Finding、身份映射、编辑裁决与建议；
- `reviewer_audit.md`：Reviewer Value Map、Objection Register、
  **Editorial Fit Assessment**；
- `revision_plan.md`：只读阶段路由、授权缺口和活动 Finding。

三份 JSON 派生视图的动态表格单元统一转义管道符、反斜杠和换行；同一安全投影也用于
动态详情文本，不能借 JSON 内容注入伪列、伪状态或新 Markdown 行。

统一 audit action graph 的次序为 deterministic preflight → 原始评审严格校验 → Finding
编译／scaffold → 生命周期校验并重建视图 → reviewer audit 检查。任一来源、assurance、
registry、resolution、规范稿或派生视图漂移都失败；只有 controller 的当前 status 与 audit
receipt 才能宣告 audit 完成。

每项 audit action 记录 `input_digest`、`implementation_sha256`、`execution` 和输出哈希。
只有上一次完整 audit 为 PASS、责任输入与实现摘要相同且所有输出仍按哈希存在时，才可
标记 `REUSED`；否则必须 `EXECUTED`。不适用项只能显式为 `SKIPPED_NOT_APPLICABLE`，不能
伪装成 PASS。实现更新会无条件使旧缓存失效。

旧 `avereth-review-findings/v2` + `avereth-review-resolution/v1` 是只读历史对。仅当旧
`post_revision_review` 为空时，才可通过 `review_lifecycle.py OUTDIR migrate --apply` 备份后
显式升级；非空 legacy 全局复核不得被猜测为新 cycle，必须保留历史并重新派发。
