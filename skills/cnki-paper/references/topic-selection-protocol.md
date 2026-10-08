# 选题来源、侦察与候选组合协议

本文件是 `task_profile=topic_selection` 的操作规范。入口、Avereth Agent 与主 Skill 只保留路由摘要，
在当前操作涉及选题组合时读取本文件。`cnki-paper` 控制器仍是阶段与完成权威；下述 packet、
生成凭证、种子封存、筛选、语义复核和组合审计均属于 research 内部证明，不新增阶段、来源表或完成权威。

## 1. 以本轮用户要求确定来源模式

在发现前冻结 `direction_contract`：当前目标、领域、核心问题、期望贡献、对象范围、必须保留／避免、
允许邻近范围、发表轨道、方法角色、工作区角色及 `authority=current-user-request`。
`origin_mode` 只能来自本轮明确要求，不能由 `materials_dir`、文件数、清洗程度或既有工作推定。

| 来源模式 | 用户授权依据 | 工作区角色与可见性 |
|---|---|---|
| `direction_first`（默认） | 围绕某研究方向提出选题 | `optional-after-divergence`；`quarantine_until_divergence` |
| `workspace_extension` | 明确延续指定既有项目 | `declared-extension-source`；仅声明材料从起点可见 |
| `material_opportunity` | 明确从指定材料寻找研究机会 | `declared-material-source`；仅声明材料从起点可见 |
| `phenomenon_first` | 明确从指定现象或材料中的观察探索问题 | `declared-phenomenon-source`；仅声明材料从起点可见 |

后三种模式使用 `workspace_policy=declared_source_from_start`，必须登记 `declared_workspace_scope`。
它们沿用相同的方向契合、种子封存、可行性、新颖性和用户确认要求；来源模式本身不构成材料授权证明。
`phenomenon_first` 应说明真实观察挑战了什么既有解释或前提、还存在哪些替代解释、什么证据会改变问题。
材料依赖可以构成经验发现的来源，不自动降低问题价值。未知的出处或记录条件仍保持未知，
已暴露材料不得称为独立 holdout。

用户锁定的标题、对象、理论和范围继续保留。方向合同有实质变化时回到拥有该事实的最早阶段，
使原组合及选中候选依据失效，再生成当前合同下的组合。

## 2. 新的方向发散必须先做真实文献侦察

`direction_first` 的顺序为：方向合同 → 真实检索侦察 → 编译 packet → 封存种子 → 受控筛选 →
候选材料检查 → 组合语义复核。不能用模型参数记忆、旧 packet 或测试数据代替本轮侦察。

围绕 `field/core_problem/object_scope` 通常拟 3–6 组检索式，每组查看前 8–15 条相关结果，去重后
保留至多 60 条。中文证据使用知网检索适配器，外文使用 Exa/OpenAlex 等国际检索适配器；
`mixed` 两边都覆盖。数量用于控制检索成本，不是贡献分数。某渠道不可用时如实说明，继续可用渠道，
不得虚构命中；完全没有可用侦察时不能启动新的方向发散。已有声明材料可以支撑材料／现象模式的
初始发现，但不能免除随后按发表轨道进行的文献定位、碰撞和新颖性核验。

把实际读到的检索结果保存为 JSON 数组，经 `topic_packet.py compile --recon <file>` 绑定：

| 字段 | 内容 |
|---|---|
| `query` | 产生该条目的实际检索式 |
| `source` | `cnki/exa/openalex/google_scholar/semantic_scholar/web_of_science/other` |
| `title`、`year` | 真实题名与整数出版年份 |
| `claim` | 实际读到的摘要或内容支持的一句话结论；不得推断未读的方法或结果 |
| `identifier` | 可回查的 DOI 或稳定 URL |
| `retrieved_at` | 实际检索时间，早于或等于 packet 编译时间 |
| `authors`、`venue` | 可选的真实著录信息 |
| `relations` | 可选的已核验互引关系，见下文 |

每项文本字段不超过 500 字符。`relations` 每条至多 20 项，使用
`target/relation/evidence`：`target` 对应另一侦察条目的 identifier；`relation` 取
`cites/cited-by/co-cited-with`；`evidence` 取 `openalex/semantic_scholar/cnki/crossref/other`。
对承重对话对象核查实际互引；缺少关系仅表示未核验。不得把“甲建立在乙之上”编成“甲乙冲突”。

侦察条目及其修改参与 packet/input/prompt/protocol 的摘要绑定，生成和筛选上下文可以读取。
每个种子的 `anomaly_or_unknown` 应点名回应的侦察条目，提出其中实际未回答的空白、矛盾或未检验假设。
这些条目仍是检索线索；校验字段、哈希或生成凭证不证明条目真实，也不把它们升级成正文证据。
`literature_registry.json` 继续是唯一来源身份表，承重前须回合法内容来源完成现有核验与登记。

### v1 兼容边界

`avereth-topic-packet/v1` 保留历史结构及摘要：`validate` 可只读检查旧 packet，包括缺少侦察或
早期侦察缺少追溯字段的 packet。它会明确报告 `READ_ONLY`。该结果仅表示可读取，不授权重新生成。
`validate --for-generation` 检查当前运行要求；新编译、`dispatch`、`host-seal` 的 prompt 发出／执行、
新 seal，以及新的筛选／材料发现／组合语义复核操作都受该要求约束。新的 `direction_first` 必须有非空、格式有效的侦察条目及
`identifier/retrieved_at`；不得删除字段、修改时间或重用旧 packet 来绕过。
其他模式若提交侦察，也须满足新写入的追溯要求。旧 packet、旧 seal 和原签名不会被原地改写；
需要新生成时完成真实检索并重新编译，输入变化后重新绑定相应下游证明。

## 3. 受控隔离生成与材料投影

首次发散使用 `topic_packet.py host-seal`。生产 `{{HOST_EXEC_NAME}}` 适配器从 packet 构造固定
prompt/protocol，各通道运行于全新 projectless、read-only 上下文，自行捕获原始输出，
由控制器外部 key store 保存密钥并签发凭证。调用者 runner、调用者提供的原始输出、
无签名自报或手写 receipt 均不能替代宿主签名隔离。

{{AGENT_DECLARED_SKILL_GUIDANCE}}

`direction_first` 在种子封存和 `host-screen` 完成前隔离工作区数据、代码本、旧选题、旧稿、
工作区文献、现成方法与材料便利性。侦察只允许新取得的方向文献进入，不能夹带工作区历史。

显式授权的另外三种模式必须传入 `host-seal --workspace-root`。控制器只读取
`declared_workspace_scope` 中的有界 UTF-8 文件，执行工作区相对路径与真实路径边界检查；
单文件最多 1 MB，总计最多 2 MB。生成凭证绑定当前 path/SHA、完整受限材料投影、input、
prompt、protocol、run、model 和 context。模式标签、调用者摘要或文件名不能替代此投影。
文件变化、越界或缺少投影均使相应输入绑定失效。

由运行时填写真实 UTC 时间；通常省略 `--compiled-at/--dispatched-at/--issued-at/--sealed-at`。
每个通道保留实际 run/context/model 与原始输出，不能复用上下文或冒称签名隔离。超时和捕获失败
不产生成功凭证；原始输出不能手改后冒充同一次捕获。

## 4. 问题种子、准入与材料检查

先生成问题，再生成标题。按适用性覆盖核心问题、竞争机制、边界／比较、历史过程、概念／测量、
反常／负例、跨层级和高风险理论等通道。每个种子保留 `seed_id/candidate_family/problem/
anomaly_or_unknown/why_it_matters/potential_disconfirmation`。

用这些既有字段说明问题为什么不能被现有答案直接消解：`anomaly_or_unknown` 写出有出处的
预期与观察之间的张力，或尚未解决的重要未知；`why_it_matters` 说明不同答案会改变哪项具体
认识、判断或行动；`potential_disconfirmation` 给出能区分可能答案，或使问题被修正、收窄、
撤回的材料与判断条件。理论、规范、概念和探索性描述可以从有后果的未知出发；只有共享
待解释对象且预期可区分时才登记竞争解释。不得制造文献冲突，也不得把希望得到的结论写成
预定答案。侦察阶段未核验的前提继续作为待核线索。

宽发散默认 12–18 个 raw seeds、6–9 个 screened 候选、至少四个适用家族，仅 2–3 个 finalist
进入完整矩阵和深核。宽度是带豁免的探索目标，不应制造陪跑项。确实狭窄时登记实际考虑的替代、
已尝试家族、淘汰／不适用理由及停止原因；`--allow-seed-breadth-exemption` 只允许先封存，
bind 仍须验证结构化豁免。不得用空的理由放宽，亦不得无理由截断真实选项。

种子封存后运行 `research_decision.py host-screen`，在 `direction_first` 材料准入前完成受控筛选：
逐个记录 sealed seed 的 `retain/merge/drop` 去向，绑定每个呈现候选的 exact core 与家族，
依据当前方向合同分别判断 `topic/problem/contribution/trajectory` 四层 fit，记录 verdict、basis 与 rationale。
任一层 `weak/uncertain` 都不能进入 screened 主清单；字段自报不替代受控筛选凭证。

之后逐候选检查工作区材料，记录 `support/challenge/partial/incidental/lure`、材料 path/SHA、
消融结果和锚定风险。`direction_first` 主清单仅保留移除材料后问题仍成立的候选：
`depends` 单列为材料机会旁支，`fails/lure` 排除。材料丰富只能改善可行性，不能提高方向契合排序。
声明材料／现象模式按其授权来源判断依赖，仍需说明问题价值和可推翻条件。

`direction_first` 材料准入后发现此前种子未覆盖的异常，只能通过
`research_decision.py material-discovery` 追加。受控凭证必须绑定材料 path/SHA、相对既有 seed/core
的 `previously_unseen` 比较、独立新上下文，以及四层 `strong` fit。调用者自报 discovery lane 不构成证明。

## 5. 语义差异、用户可见空间图与取舍

在 soft focus 前运行 `research_decision.py semantic-review`，由生产 `{{HOST_EXEC_NAME}}`
适配器复核当前组合并将输出凭证绑定进 portfolio audit。
{{AGENT_DECLARED_SKILL_FOLLOWUP}}

每个 screened 候选绑定 seed lineage、方向合同字段、描述性七维 semantic signature、材料消融，
以及与最近似候选之间经独立复核的承重差异。七维为研究对象、待解释现象、机制／理论张力、分析单位、
时间逻辑、贡献类型和证据逻辑，字段以当前 `research_decision.json` schema 为准。
标题、编号、同义措辞、数据、地区、年份、方法、因变量措辞或理论标签的改变均不能单独构成不同问题。
候选自报的差异只是复核输入。`equivalent/uncertain` 须给实质理由，明确不同的 pair 按现有协议绑定
支持的差异维度；不用增加理由篇幅或假想评审意见替代语义判断。

向用户展示核心契合、邻近扩展、高风险高回报及单列材料机会四组；只展示实际成立的组，
不得为分组制造候选。每项（含材料旁支）显示问题家族、方向理由、实质差异、材料角色、
潜在贡献、最大不确定性／失败风险及为何值得深核。保留最稳健、最平衡、最高原创潜力三种
决策角色的真实取舍；不能只列题名后让用户自行补齐研究判断。

对满足方向与材料条件的候选，优先解释解答后果、可能答案的可区分性和当前可行性之间的
决定性取舍。新颖性说明相对于既有答案改变了什么；不能用自动平均分、反转幅度或一句话的
醒目程度替代判断。简洁表述应保留对象、核心未知与成立条件。

有适用分支品味卡且需要取舍时，可按 `taste-judgement.md` 使用成对比较信号。
它是 `signal-not-gate`，不替代方向契合、语义差异、来源核验或用户决定；未完成真实对照校准
不能成为放松现有审查的依据。

## 6. 入围后的证据与明确确认

候选按 `seed → screened → finalist → selected` 递进加深。仅 finalist 完整填写
问题定向、归纳／演绎矩阵、暂定标题及主张边界、Dialogue Option Cards 和动机选项；
不得把全套最终候选工件强加给每个初始种子。

在同一 research 控制链内完成 F0 材料需求、F1 低成本筛查、soft focus、F2 最小可行证据，
再做对抗性撞题检索及 C1/C2、C3 有界放行和 question commitment。
材料检查规则见 `research-material-feasibility.md`；C0–C3、来源／综合身份和承诺绑定的
详细执行见 `workflow-playbook.md` 的 research 检查点。F2 的真实访问、许可／伦理、覆盖、
字段或角色、可读性、链接、变异、成本和稳定性未通过时不进入昂贵获取或新颖性放行。
零命中不证明新颖；实质碰撞后的重构必须有独立后果、不同可观察预期、可识别材料，且会改变原判断。

完成当前阶段要求的 acquisition 与 research 后，才请求用户确认精确问题、动机、范围、
工作标题和标题权限。soft focus 与 hard clearance 使用不同确认事件；明确确认之前不得进入
design 或正文。用户固定标题按 `user-fixed/locked` 保留，实质变动重新确认。

只有控制器当前 status 与对应 gate/receipt 通过才可声明阶段完成。方向合同改变使整个组合失效；
工作区文件变化只阻断 selected、finalist 或当前决策角色依赖的关系，其他 screened 关系标为局部 stale，
不抹去仍有效的选中子图。装配字段或派生报告不一致应就地修复；仅在凭证无效或绑定输入实际变化时
重跑相应隔离动作，保留旧凭证和研究事实。

### 知识改变与最近邻比较

对值得深核的 finalist，先指出最近邻研究已经回答了什么，再说明当前候选可能改变的假定、
范围、机制或证据可信度。最近邻按消解候选贡献的能力选择；主题相近只作为召回线索。
广泛侦察后优先检查同一问题、答案和证据逻辑，保留实际找到的最多 3–5 项，不为凑数填充文献。

使用现有 `research_decision.json` 中的记录：

- `c1_collision_evidence.nearest_neighbors` 保存 Source、SYN、collision relevance、八维比较和逐项反驳。
- `c2_overlap_adjudication.knowledge_delta` 保存当前候选的同维描述与一个有边界的 `delta_statement`。
- `assumption_challenge` 保存被质疑假定、来源、旧解释与替代解释的不同预期、判别材料、
  不改变原认识的条件、需要修正判断的条件及受影响读者。

八维比较为问题、现象／估计对象、单位／群体、既有解释、机制／条件、证据逻辑、主要答案和
尚未完成的研究责任。未知项显式保留。差异句须说明已有研究在何种条件下确立了什么、
本研究拟改变哪项认识、凭什么材料区分解释；“首次”“文献少”本身不承担这个责任。

每个最近邻的反驳状态为 `can_refute / cannot_refute / unclear`。强判断必须连接已完成内容核验的
Source、登记原文或 OCR 文件中的精确片段与定位、具体既有主张、候选主张和比较理由。
文件 SHA 和字符区间证明所比较片段保持一致；它们不证明解释本身正确。
信息不足时保留 unclear。cannot_refute 只说明该项证据不能消解该主张，不能推出绝对新颖性。

`knowledge_change_contract={schema_version:cnki-knowledge-change/v1, claim_level:high}` 显式启用
高主张 finalist／selected 的 assumption challenge 责任。增量研究可选择 boundary-test，
不适用理论挑战时给出具体理由；复制、负结果和独立证据以可信度或范围更新承担贡献，
不用构造理论颠覆。该声明不会授予贡献等级、内容核验或用户确认。

`research_decision.py novelty-delta WORKSPACE` 读取正本生成比较视图；加 `--write` 仅重建
`novelty_delta_view.md`。该文件是可删除、可重建的展示，不进入事实权威或完成判断。
自动评测负责来源和行为一致性诊断，最终问题承诺继续使用当前用户授权与证据绑定合同。
