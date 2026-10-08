# 研究判断的校准

品味意见是可选辅助，不拥有阶段放行、候选淘汰或自动排序权限。最低材料基础成立、候选接近而确需取舍，或用户明确要求时才调用。来源、设计、真实执行、推断上限和用户授权仍由原有控制器负责。

## 范本采样与判断

`taste_exemplars.py` 保留同刊同年分层、跨刊轮转、引用窗口与冷题保护。shortlist 的 positive/negative 是历史采样键，分别表示高引和低引层；middle 是中间层，均不决定读者的正负判断。百分位只描述实际取得的队列，被上限截断的采集不能声称完整覆盖。

`anonymous-mixed-pool/v2` 混合三个层，只向读者展示临时编号、标题和摘要。原身份、来源、引用层及映射留在审计侧。`--pick-positive`、`--pick-negative` 是上限，不是配额；两类都允许为空。读者逐项给 positive、negative、uncertain 或 rejected，允许跨采样层选择。材料不足或看不懂不能作为负例依据。

```text
taste_exemplars.py shortlist <slug> --harvest <harvest.json> --out <shortlist.json>
taste_exemplars.py emit-select <slug> --shortlist <shortlist.json> --out <capture> --model-revision <revision>
taste_exemplars.py collect-select <slug> --shortlist <shortlist.json> --responses <capture> --model-revision <revision> --write
```

每个 prompt 使用独立上下文，原样保存 JSON 回复和真实 context id。收集器校验完整处置、身份、理由及 prompt 绑定后，写回同一品味卡登记表。`exemplar_selection` 保存协议、短名单哈希、匿名映射及处置，条目保留 capture 元数据。标题和摘要不能证明全文论证厚度；匿名化也不能保证模型不识别熟悉内容。

旧范本保留历史身份；新范本标为 `calibration_status=unvalidated`。`exemplars-registered` 只表示已登记。locked 保留用户选择，不冻结来源有效性。刷新沿用 harvest/ingest/shortlist/select，365 天年龄提示不成为研究阶段门。

## 研究动作教学材料

已发表研究用于学习问题构造、概念区分和证据组织；同期原始方案用于同成熟度比较。两者用途分开。教学范例不加入 reference set，不参加方案胜负比较，也不进入 topic generator、ProsePacket、Writer 或 Clarity。登记时的 `why`、引用层和正负标签不能自动成为已核对的论证证据。

语言范例另按 `commonplace-writing.md` 从已核验全文重新选取与拆解，生成白名单 CommonplacePacket；
它不继承教学条目的评分、胜负意见或审查上下文。该可选投影可进入 Writer，但不进入 ProsePacket 或 Clarity。

原范例条目可附 `research_move`，身份继续使用该条目的 identifier，不另建权威文献库。`--teaching-exemplars on` 才启用，默认 off；`--teaching-limit 0..3` 默认 2，表示每次投影上限，零表示不投影。没有合格拆解时允许零例，不要求补足，不影响既有研究阶段。此功能仍为未经行为评测确认的可选能力。

`research_move` 使用 `avereth-research-move/v1`：

| 字段 | 内容与边界 |
|---|---|
| schema_version、version | 协议及本条拆解版本；内容变化须更新版本并重新 emit/collect |
| source.identifier | 与原范例 identifier 一致 |
| source.level、origin | level 为 abstract、inspected_excerpt、full_text 或 synthetic；真实文献 origin 为 published_result，合成例为 synthetic |
| source.content、content_sha256、locator | 已核对短摘及其 UTF-8 SHA-256、可定位的页面或段落；短摘最多 1200 字符，预算不授予转载权限 |
| source.verification | status=content-verified，basis 说明实际核对了什么；元数据命中不构成内容核验 |
| source.permission | status=permitted，basis 说明该短摘获准使用的依据；未知权限不投影 |
| prior_understanding、move | 原有认识与具体改变问题、概念、解释或判断的动作；均为有来源边界的阅读拆解 |
| support | basis=author_claim 或 inspected_argument，加 text；abstract 只接受 author_claim，不能推定全文厚度 |
| without_move | kind=synthetic_ablation，加 text；删去关键动作的教学对照，不能冒充真实结果 |
| limits | 推理上限和不宜迁移的场景，不能留空 |

拆解的主要文本字段各最多 400 字符。整例为合成材料时使用 `SYN-` 身份、source.level=synthetic、source.origin=synthetic、support.basis=synthetic，prompt 明示其合成身份。历史文献的事后拆解不表示作者真实发现过程。inspected_excerpt 或 full_text 也只能支持已核对的部分，不能用来源等级标签替代实质阅读。

`taste_cards.teaching_projection()` 仅选择通过以上结构、身份、权限声明和原文哈希校验的条目；不合格条目及原因写入 plan 的 excluded。校验无法独立证明解释忠实、核验声明真实或教学质量，仍须研究者按 locator 审查。已有条目的历史赞语不会被静默改写成 research_move。

实际发送的 prompt 显示教学身份、版本、来源等级、短摘、拆解、合成对照与限制。`avereth-teaching-projection/v1` 是可重建视图；它的实际内容及 SHA-256 保存在 plan 和 judgement 中，整体输入摘要进入 prompt 及 capture 绑定。

## 同等信息条件下的比较

`taste_judge.py` 输出 `avereth-taste-judgement/v2`。两边均使用 maturity、question、baseline、mechanism、prediction、evidence、update、text 字段，缺失保持未知。裁判先填写 one_analysis 和 two_analysis，再给 preference；这是同次响应中的分别分析，不是两次独立评审。

目前选题入口评估 proposal。`--references` 的原始方案须带 `comparison_view`，声明 `maturity=proposal`、`origin=contemporaneous`，并提供 question、update 与 provenance。provenance 包含 source_id、locator、recorded_at、verification_basis、permission_basis、information_basis，分别记录来源身份、原始方案位置与记录时间、内容核对、使用权限及信息条件可比性的依据。程序检查声明是否齐备，不能仅凭来源标签证明同期性、相同信息条件或独立金标准身份；这些依据仍须实质核对。

`plan` 在调用模型之前报告 pool_count、eligible_count、selected_count 以及每个被排除参照的原因。选取参照时先排除已知不可比条目，再按共享规则选择，单个合格参照也可使用。回溯重建方案、只有 contemporaneous 标签而无依据的方案、侦察论文的 result 均不派发比较 prompt。没有可比配对时，`comparison_status=no_comparable_pairs`、dispatch_count=0；emit 只保存计划，collect 可保存零判断报告，ranking 仍为空。这里的计划状态不是研究阶段状态，也不是单侧评价或模型弃判。

显式传入空 references 数组或空 reconnaissance 数组时，参照池保持空；只有两个输入都未指定，才读取工作区 literature_registry。该默认来源仍按 result 处理，其实际消费文件也进入输入绑定。

计划已接收的方案如果仍不足以支持裁判判断，使用 uncertain；实际条件不匹配则使用 not_comparable，可比较且相当才用 tie。弃判不计作输，不据此淘汰候选。

```text
taste_judge.py plan <workspace> --references <plans.json> --teaching-exemplars on --model-revision <revision> --out <plan.json>
taste_judge.py emit <workspace> --references <plans.json> --teaching-exemplars on --model-revision <revision> --out <capture>
taste_judge.py emit <workspace> --references <plans.json> --teaching-exemplars on --variant order-swap --model-revision <revision> --out <swapped>
taste_judge.py collect <workspace> --references <plans.json> --teaching-exemplars on --responses <capture> --probe order-swap <swapped> --model-revision <revision> --write
```

换序保持材料不变，由不同上下文作答，报告同一配对的翻转和位置不一致。hot-strip 与 plain-rewrite 的语义保持未核实时，`semantic_status=unverified`，翻转不能自动标为风格偏见。行为校准还应测试真正削弱内容的对照，不能只奖励意见不变。

意见保持 `calibration_status=unvalidated`、`decision_policy=opinions-only`，ranking 为空。胜场是比较计数，不是候选排序规则。每对的双边分析均保留；第一对的汇总展示不表示跨对一致。

emit/collect 必须使用相同的教学开关、预算、卡、来源、候选和改写输入。输入文件的路径与 SHA-256、`input_sha256` 以及 `teaching_projection_sha256` 绑定实际计划。来源等级、权限说明、教学内容或版本变化均使旧 capture 失效。collect 校验当前重建计划与发出计划完全一致；validate 检查已记录输入文件仍匹配。重新生成使用新的 capture 目录，保留旧计划和原始响应，避免旧意见被新 prompt 静默复用。关闭教学只停止范例投影，同期方案要求、独立上下文、换序探针和 opinions-only 权限继续有效。

## 贡献事实与派生视图

贡献校准区分做了什么、结果支持什么、增加了什么认识。允许 explanation-revision、boundary-refinement、independent-replication、negative-result、description-measurement、conceptual-normative；方法失败和越界主张不能由贡献措辞抵消。

`research_design.json.knowledge_baseline` 拥有 origin（contemporaneous、retrospective 或 unknown）、judgement 和 source_refs（实际 Source、SYN、DOI 或 URL）。声称 contemporaneous 还须有 recorded_at，早于各动作 started_at；没有可核对记录时标 retrospective 或 unknown，不能补造预注册。

`method_execution.json.knowledge_update` 拥有 kind、baseline_origin、work_performed、result_interpretation、supported_update、limitations、result_ids、claim_ids，以及 semantic_assessment（status 与 rationale）。status 为 supported、restatement 或 uncertain；只有 supported 且既有 accepted action→artifact→result→claim 链成立才接受校准。语义评价是一项有依据的判断，不是程序已经证明知识新颖性。

negative-result 还须声明 null_interpretation 为 inconclusive、bounded-effect 或 explanation-excluded；后两者附 null_basis 说明精度或排除依据。不显著不自动等于无效应。independent-replication 需 replication.independent_material 与 independence_basis，其依据须指向已登记材料，供研究者实质审查；程序检查声明与理由，不能仅凭布尔值证明材料独立。相同材料重复运行不属于独立复现。

`confirmed_contribution.md` 保留用户处置和标题权限。Reader Prior、Reader Posterior 分别投影自 judgement、supported_update，须与 JSON 一致。Displaced Source 指被取代的来源；未取代来源的复现可写 none，基线 source_refs 仍须解析到 content-verified final-source、工作区保存文件及 SHA。SYN 还须有有效的来源绑定和实际链接。

字符串相等或包含只提示复核，不证明缺少增量；同义改写也不证明存在增量。边界收窄、可信度增加、合法负结果和概念推进均按相应证据判断。

## 历史项目与回退

旧 prompt 和 v1 judgement 保留为历史，不重标成 v2；重新 emit/collect 才得到新协议意见。prompt、材料或卡变化后，旧 capture 绑定不再适用。

缺少 knowledge_baseline 或 knowledge_update 时明确报告缺失，不自动补成通过。先 dry-run 既有迁移，保留原件和哈希；需要改变封存设计时，按现有修订授权及依赖失效处理，不能仅重算摘要就沿用旧动作确认。已发布交付物不被静默替换。

安装回退使用官方备份。现象驱动保持显式启用；研究笔记始终可删除，因为它不拥有事实或 receipt 权威。正式 Writer、Clarity 和终遍双读者继续遵循现有写作防火墙与审计合同。
