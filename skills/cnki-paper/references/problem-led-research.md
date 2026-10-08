# 问题牵引的研究螺旋

本协议防止 CNKI-Paper 把“资料齐全、模型漂亮、工件完整”误当成“问题值得研究”。技术只负责提高获取、分析、复核与交付的可靠性；问题的分量、理论判断和实践意义仍由研究者与用户承担。来源合同由 `publication_track` 决定，不能把 CNKI 数量误作国际稿件的问题价值证明。

## 一条控制脊柱，三个认识回环

为兼容既有工作区，控制器仍公开八个机器状态：

`intake → acquisition → research → design → execution → build → audit → output`

但研究活动不再被理解为一次性流水线，而是三组可回退的认识回环：

1. **发现环**：`intake〔问题定向〕 → acquisition〔侦察获取〕 ⇄ research〔问题化与定向补检〕 →〔问题／工作标题承诺〕`；
2. **求证环**：`design〔回答策略〕 ⇄ execution〔真实探究与解释〕 →〔问题／贡献／标题再判断〕`；
3. **表达环**：`build〔论证表达〕 ⇄ audit〔批判复核与标题一致性〕 → output〔发布〕`。

回退不是失败。新材料推翻问题前提时回到 research；设计不能制造所需证据时回到 design；执行只得到常识性结论、问题失去分量或必须换题时，不得靠包装贡献进入 build；审计发现表达掩盖证据边界时回到 build 或更早的事实所有阶段。

## 六种思维怎样推动回环

三问决定先后，六种思维决定在关键处看什么：辩证思维识别联系、主要矛盾和竞争解释；历史思维复原形成过程、阶段与条件变化；系统思维检查边界、层次、结构—功能、反馈和外溢；战略思维用用户目的、合法终点和决定性未知统揽优先级；底线思维守住权限、伦理、事实、推断、确认和交付红线并准备回退；创新思维针对真实瓶颈提出可证伪、可回退的改进。完整判准见 `three-questions-standard.md` §0。

六种思维不平均用力。问题承诺、设计路由、执行后再判断和审计只记录足以改变决定的观察；其余保持未适用或待核，不新建六个状态、六张表或自动评分。若新证据改变主要矛盾、历史条件、系统边界、战略价值或底线风险，任务回到拥有该变化事实的最早阶段，而不是在当前阶段追加解释补丁。

聚焦时先确定哪一项未知最能改变对研究对象的判断，再区分回答它必需的解释、材料和范围条件。
真实张力可以来自相冲突的预期，也可以来自概念、规范标准、过程或可靠描述的缺失。重要性取决于
解答后果，不能靠强造对立或预写反常结论获得。选题沿既有 seed 字段说明前提、后果及修正条件，
具体操作见 `topic-selection-protocol.md` §4–§5。

把兴趣发展成论文问题时，先辨认真正值得研究的谜题：什么可追溯现象与常识、既有理论或预期不一致，或哪个重要未知尚未得到可靠回答；再选能解释该现象的核心概念，区分看似相近却不能替代的对象、层次和判断；随后提出有根据的可能解释，并通过定向文献检索检查其已有答案、反例、竞争预期和理论边界。只有针对共同待解释对象且具有可区分预期的解释才称为竞争；不存在真实竞争时保留未知，不凑阵营。这是发现环中的迭代，不要求脱离来源一次完成，也不新增字段、表格或阶段。

入围后的问题聚焦应给出一个明确的知识变化：既有认识在哪个条件下成立，当前材料可能要求
修改其中哪部分，什么结果会让原判断保持不变。变化可以是范围、解释、分类或证据可信度，
不要求每项研究推翻理论。最近邻、假定挑战与可重建展示沿用 `research_decision.json` 的记录，
详见 `topic-selection-protocol.md` §6“知识改变与最近邻比较”。

每个最终选题都须说清相对于既有知识拟增加、修正、否定或重新组织什么，以及什么材料能够支持或改变这一预期；执行后用实际结果重新判断，不能把预期增量写成已实现贡献。问题的理论张力、可研究性和可论证性共同决定取舍，题名醒目、方法复杂或材料现成不能代替这三项。

## 为什么不是增加第九阶段或简单换序

- 不另设一个名为 `problem` 的机器阶段：把问题价值封装成可自动 PASS 的独立工序，容易制造新的表格主义，也会破坏旧工作区、CLI、任务终点和凭证兼容。问题定向因此是 intake 内的认识检查点，并继续接受 research 与 execution 的反向修订。
- 不把 research 整体移到 acquisition 前：完全脱离文献和可追溯经验的“内心问题”也可能只是成见。先有问题定向，再做最小侦察；研究合成暴露缺口后再定向补检，既防工具反向造题，也防主观直觉拒绝证据。
- 不取消方法、来源和审计硬门：反技术主义针对的是工具目的化，不是反对严谨、数据或可复核方法。越强调问题与思想，越要诚实显示证据上限和可能推翻自己的材料。

## 标题不是包装：三次校准而非第九阶段

标题是“问题—可兑现回答—证据—范围”的压缩契约，不是检索关键词的华丽排列，也不是执行前预写的结论。它横穿三个既有回环，因此不新增 `title` 机器状态，不另建一份与问题、贡献并列的标题真相表：

1. **问题承诺时建立工作标题**：候选阶段只允许 `question-led` 或 `claim-neutral`，并登记不承诺何种尚未验证的结果、机制、因果或新概念。`confirmed_motivation.md` 同时记录 `Title Authority` 和 `Title Revision Rule`；用户指定题目默认为 `user-fixed / locked`，不得静默改写。
2. **执行后按证据再判断**：`confirmed_contribution.md` 记录 `retain / narrow / revise / reopen / withdraw`、证据校准标题、EXE/Claim/Evidence 身份链接、修订依据和用户决定。方法新、模型复杂、期刊偏好或“更吸引人”都不是实质改题依据；问题重开或撤回时，标题契约一并重开或撤回。
3. **成稿时核对交付一致性**：`academic_prose_audit.md` 用三行 Title Revision Chain 连接 `question_commitment → post_execution → final`。final 只能是 `none` 或不改变问题、主张、范围的 `surface` 调整；若标题出现新机制、新结果、新概念或范围变化，必须回到拥有该变化事实的 research/design/execution，而不能在润色中藏过去。

硬门只检查权限、字段、身份链接、节点间一致性、用户再确认和稿题一致；标题是否有洞见、是否准确有力、是否符合目标刊文气仍由结合证据的研究判断与读者评审承担。目标刊标题公式只能帮助诊断表达，不能反向制造问题或承诺。

## research 内部的五步裁决，不新增状态

发现环在 research 内依次运行 `direction_contract → literature_reconnaissance〔真实检索〕 → material-quarantined seed portfolio → screened portfolio audit → taste_pairwise_judgement〔材料初步成立且确需取舍或用户请求时，可选〕 → 有依据的 finalists → F0 需求拆解 → F1 低成本筛查 → candidate_focus〔软确认〕 → F2 最小可行证据 → adversarial_collision_search → novelty_clearance〔硬确认〕 → question_commitment`。这些检查点不产生第九阶段，也不以候选数、命中数、材料备份数或自动分数替代判断。F2 用真实小样本验证访问、许可／伦理、覆盖、字段／角色、可读性、链接、变异、成本与稳定性；只有 PASS 或窄义 N/A 才能进入昂贵定向获取和 C1–C3。C0 对真实候选作 retain/merge/drop/defer；只有一个候选时，简述实际考虑过的替代方向与停止理由，不制造陪跑候选。C1 必须把最强撞题结论落实到已登记、内容核验完成且具备 collision/SOTA 轨道角色的 Query/Source/SYN 身份；零命中只是检索观察，不证明新颖。C2 用七个实质维度比较对象、问题/估计对象、理论/机制、单位/案例/时空范围、材料与识别逻辑、既有答案和声称贡献；实质碰撞后的转向只有在独立后果、不同可观察预期、可识别材料和改变原判断四项同时成立且不是装饰性差异时才可保留为新问题。C3 由人类作有边界的最终放行，明确哪些并不新、能说什么、不能说什么。材料合同详见 `research-material-feasibility.md`。

### 隔离式发散与组合审计

普通选题请求默认 `direction_first`。在读取工作区前，先把本轮目标、学科／子领域、核心未知、偏好贡献、
对象范围、必须保留／避免项、允许邻近范围、发表轨道、方法角色和用户授权冻结为 `direction_contract`（`field` 写分支名而非"政治学"这类总称，
以便按别名解析到 `references/taste/branch-taste-cards.json` 的一张分支品味卡；歧义时在 `topic_selection.taste_card` 显式指定），
再编译 `avereth-topic-packet/v1`。该 packet 的封闭字段表只允许本轮要求、方向契约、发表轨道、明确限制和
邻近范围；工作区数据、代码本、旧选题／旧稿、既有文献、方法和材料便利性属于显式排除项。种子封存的
SHA 与时间必须早于任何工作区材料准入时间。相同方向契约在两套无关工作区中应产生相同 packet 投影；
只改变方向契约则 packet 摘要必须改变。

先生成问题种子而非标题。宽发散默认尝试核心问题、竞争机制、边界比较、历史过程、概念测量、反常负例、
跨层级和高风险理论等适用通道，以 12–18 个原始种子形成 6–9 个 screened 候选并覆盖至少四个家族。
这些数字是默认探索宽度，不是质量分或无条件硬配额；有效豁免必须保存完整家族尝试与淘汰账本。候选按
`seed / screened / finalist / selected` 渐进成熟，只有 2–3 个 finalist 进入完整归纳—演绎矩阵、材料路线、
撞车与新颖性核验。

screened 候选登记生成通道、问题家族、方向契合、工作区关系、材料消融、七维语义签名和最近似候选差异。
七维为研究对象、待解释现象、机制／理论张力、分析单位、时间逻辑、贡献类型和证据逻辑；至少现象、机制／
张力、分析单位或贡献类型之一发生真实变化，才是承重差异。只换标题、数据、方法、地区、年份、结果措辞或
理论标签的组合判为伪多样。`direction_first` 中消融 `survives` 才进入主清单；`depends` 单列为材料机会旁支，
`fails` 或 `lure` 淘汰。材料只能在种子封存后以 `support/challenge/partial/incidental/lure` 身份进入。

数据只在定量、计算、混合方法、用户明确找数据，或主张必须依赖结构化数据时进入 F1/F2。
本地文件、公开下载、API、注册、申请、机构订阅和商业来源按问题适配、变量、覆盖、许可、
成本与可复现性平等比较；本机已经拥有不构成选题优先权。数据触发候选的价值、理论位置与
新颖性保持 `UNVERIFIED`，必须重新连接 `PO-*`、实践／网络经验和当前发表轨道的理论／撞车链。
选题发散只提示路线，设计确认前核验元数据／问卷／代码本，正式分析前核验真实样本或查询结果，
结果写作绑定实际数据、方法、结果和 SHA。完整边界见 `quantitative-data-check.md`。

`research_decision.json` 只拥有候选、C0–C3 与问题挑战；`confirmed_motivation.md` 继续拥有用户承诺和标题事实，二者以可验证语义绑定连接而不双写。顶层粗粒度 disposition 由控制器投影为 provisional/focused/challenged/reopened/cleared/withdrawn；focused 只有在 `preclearance_readiness` 确认 C0–C3 与候选—问题—Query/Source/SYN 科学依据内部一致后，才请求独立 hard confirmation。封印范围仅是 selected-candidate subgraph：所选 candidate/Option/PO 语义、科学依据与承诺先形成不含 hard confirmation 的 `clearance_basis_digest`，用户确认以 `basis_sha256` 精确绑定后再进入最终 subgraph。普通背景与非所选项变化不触发过期，关联 collision/SOTA 证据变化必须重开，`bind` 不得以重算摘要保留旧确认。问题版本可以在工作标题仍 locked 时被挑战：锁定标题只表示不能静默改标题，不表示研究问题不可证伪。挑战与重开必须从 `avereth.py research-decision ...` 受控入口经过 plan/apply/rollback、控制器锁和备份；新问题先是 draft，重新完成 C0–C3 和新的人类确认后才允许 clear。所有候选撤回是合法认识结果，但必须由独立用户确认全部撤回且不替换，才终止于 research、令后续阶段 N/A；系统不得自动制造替代问题或交付物。旧 v6.0 承诺文件迁移时保留为 canonical 历史事实，不据此自动构造 v6.1 research decision。

## 问题定向契约

workspace 路线在任何系统检索、模型选择或数据盘点前建立 `problem_orientation.md`。它只锁定“为什么值得寻找一个问题”，不提前锁定最终研究问题、方法或结论。

```markdown
# Problem Orientation

| Field | Content |
|---|---|
| Orientation ID | PO-01 |
| Practical encounter | 用户题面、田野／工作经验、可追溯社会现象或明确的文献异常。 |
| Affected actors | 谁处在该矛盾、制度或后果之中。 |
| Tension or unknown | 目前不能用常识或既有解释直接消解的矛盾、异常或未知。 |
| Why it matters | 若不回答，会妨碍何种理解、判断或行动。 |
| Common-sense or imported frame at risk | 哪个看似当然的结论、移植框架或默认前提可能需要修正。 |
| What could change our mind | 什么材料会使当前定向被保留、收窄、改写或撤回。 |
| Origin | user-provided / practice-observation / source-backed / hypothesis-only。 |
| Epistemic status | provisional / hypothesis-only / source-backed；不得把记忆写成事实。 |
| Researcher position and access | 研究者与对象的关系、可接近材料及明显盲区。 |
| Method/data role | feasibility-only 或 not-selected；方法、模型和现成数据不得成为选题理由。 |
| Confirmation source | 用户本轮题面、明确确认或可定位的会议／任务记录。 |
```

硬门只检查字段、身份、认识状态与方法从属关系，不给“问题价值”打机械分。问题是否重大、是否值得长期追问、是否真正来自社会生活，由用户确认与后续隔离评审根据实际内容判断；关键词、表格长度、模型复杂度和文献数量都不能代替这项判断。

## 两遍获取，而非先堆资料

### 侦察获取

acquisition 首遍只证明：问题定向已存在、活动发表轨道的来源权限真实、查询可复现、至少有一条适用学术来源进入唯一注册表，且 source index 与注册表一致。`cnki-cn` 使用 CNKI 探针与最小 CNKI 来源；`international-ssci` 使用国际来源 HTTP(S) 探针与最小国际学术来源；`mixed` 保留两种生态。此时不要求提前凑齐完整范文／SOTA 合同。

### 定向补检

research 围绕实际出现的张力、竞争解释、反证和问题候选反复补检。到问题承诺前，仍须满足活动发表轨道的完整合同（角色、目标刊文献基线与兜底数字见 `literature-sufficiency.md`）。最终来源还须覆盖主要立场、真实反方、奠基链、近期变化和方法责任，并连续两轮定向补检不再发现新板块。数量只证明学术积累最低线，不能证明问题价值或代替覆盖判断。

## 输入不是固定配方

选题输入允许六种渠道，理论锚点按发表轨道启用：

- `practice-experience`：用户本轮材料、田野／工作经验或有位置说明的实践观察；
- `web-experience`：可追溯的官方或原始网络材料；
- `memory-experience`：仅作 `hypothesis-only` 的经验线索；
- `memory-theory`：仅作 `theory-candidate` 的理论候选；
- `cnki-theory`：经摘要、详情或全文核验的中文理论与争论。
- `international-theory`：经 DOI、出版社或合法 OA 摘要／原文核验的国际理论与争论。

每个候选必须连接一个 `PO-*` 问题定向、至少一个可追溯经验锚点（practice 或 web），以及活动发表轨道要求的经核验理论／争论锚点：`cnki-cn` 用 `cnki-theory`，`international-ssci` 用 `international-theory`，`mixed` 同时使用二者。模型记忆可以缺席；它永远不是为了凑齐输入层而必须制造的原料。用户材料也不因来自实践就自动成为已证事实，必须保留其来源与认识状态。

## 两次承诺、标题三校准与一次重开

1. **问题承诺**：research 末端由用户确认精确问题、问题定向 ID、为何仍值得追问、非平凡答案判准、范围与禁止主张。确认前不进入 design 或正文。
2. **问题／贡献再判断**：execution 后不仅校准贡献，还要登记问题处置 `retain`、`refine`、`reopen` 或 `withdraw`，并说明实际认识比常识多了什么。`reopen` 或 `withdraw` 是合法结果，但必须停止 build，回到 research 重新确认或终止项目。
3. **贡献承诺**：只有问题仍成立、执行证据确实改变了认识且主张未越过设计上限时，才确认贡献并进入 build。

正文聚焦承接这些既有事实：以当前 `RQ-*`、主 Claim、设计责任和实际结果确定具体主线，选择足以
回答问题的最小论证责任链。多条主张或跨节推理需要显式分工时，使用 AMC 的可选 `proof_obligation`
及 Section 职责；其合同见 `engine/manuscript-compiler.md`。反驳、负面或不确定结果可以完成一项
研究责任，并改变最终答案。删节判断须保留理解、方法透明度和推断成立必需的内容。

## 反技术主义不等于反方法

- 不以方法标签、模型新旧、回归表整洁或工件数量评价问题价值。
- 不因强调问题意识而降低来源身份、权限、复现、负面结果、推断边界和最终渲染要求。
- 不把“直面实践”理解成轶事即证据；实践负责提出张力，证据与方法负责检验和限定回答。
- 不把“本土原创”理解成拒绝外来理论；允许对话、比较和借鉴，但必须由中国经验中的真实问题决定采用、修正或拒绝何种框架。

## 可选的现象驱动发现与研究笔记

用户明确从指定现象或材料探索时，可声明 `topic_selection.origin_mode=phenomenon_first`、
`workspace_policy=declared_source_from_start` 和 `direction_contract.workspace_role=declared-phenomenon-source`。
这一路径与 `direction_first` 使用同一控制器、种子封存和问题价值检查。仅将显式声明的工作区相对路径
交给材料投影，按现有 path/SHA、生成 prompt、capture 与种子封存记录材料暴露及候选形成顺序。
不得把已暴露样本声称为独立验证集。材料依赖可以是经验发现的来源，不自动降低候选价值；说明实际观察
挑战了什么前提、还存在什么替代解释即可，不因为材料现成而免除来源与可行性检查。默认入口仍保持隔离。

主研究者可在 intake 至 execution 维护一份可选 `research_notes.md`，记录暂定解释、反例、问题改写、
最薄弱环节与下一步检查。它没有长度、完整性或提交频率要求，不是证据、阶段条件或 receipt 依赖。
笔记中的想法须经原有来源、设计、真实执行与 Claim/Evidence 链才能进入正式论证；整份笔记不能送给 Writer。
正式 Writer 继续只读取 ProsePacket。删除笔记不改变规范事实、阶段判断或已登记证据。
