# Constraint Census

本清单为 Current / Lean / Minimal 文本消融提供候选及证据。第一优先级是合并入口层的重复展开；第二优先级是把条件性操作细节留给已经存在的 JIT references。科学状态、来源与执行事实、用户确认、权限、ProsePacket firewall 和交付收据的要求保持不变。

清单不是 runtime registry，不改变 controller、schema、gate、adapter 或论文工作区。它没有运行真实模型，也不证明删改后任务完成率、效率或论文质量提升。

## 1. 冻结基线与范围

基线为 `a4b32e1bb39f7c6f9fd655450f59636215e0f9c7`。下表及后文 `S`、`E`、`A` 的行号均指该 Git revision 的原始文件；并行修改后的工作树行号不作为原位置。可用 `git show a4b32e1:<path>` 重建原文。

| 缩写 | 原文件 | 行数 | UTF-8 bytes | Unicode characters | Git blob 内容 SHA-256 |
|---|---|---:|---:|---:|---|
| S | [skills/cnki-paper/SKILL.source.md](../skills/cnki-paper/SKILL.source.md) | 210 | 15,249 | 8,260 | `914346242d9561a59a08193a54218ae663479c10640ae1fc0ada00784a9d1260` |
| E | [entrypoints/avereth.source.md](../entrypoints/avereth.source.md) | 37 | 2,109 | 2,109 | `bb0f8a064ae3506150f43c1643651c8a338f72a23cd5ca9cdb1ff84bfbea6a3f` |
| A | [agent-specs/avereth.agent.toml](../agent-specs/avereth.agent.toml) | 61 | 4,241 | 4,241 | `261451122b45f3c2fcd42a29fc1e48b3f58b1fa12e15c7a13fdac393ac24bc71` |
| 合计 | 三个源文件 | 308 | 21,599 | 14,610 | 不作拼接哈希 |

上述计数包含 frontmatter、TOML metadata、空行与尚未展开的 host placeholder。它们是静态源文件体积，**不是实际加载上下文、输入 token、读取次数或耗时**。不同入口不一定同时加载，host build 还会展开 bootstrap；不能把三文件总和当成每次任务成本。

只检查三份公开指令及其指向的既有 JIT / controller 实现。外部提案中的研究结论不作为本清单已验证的事实。未做逐条 Git 历史归因；除下文明确记录的当前重复或兼容事实外，规则的历史起因统一为 `history_origin=unknown`。

分类含义：

- **hard invariant**：事实、权限、科学状态或完成真实性边界。可以精简重复文字，不能在本次消融中撤销责任。
- **domain knowledge**：本项目特有的文献、方法、体裁或操作知识，优先在相关任务中 JIT 加载。
- **heuristic**：规划、表达或检查顺序的默认策略。修改仍需满足当前机器合同；有代码强制的策略不能只删提示词。
- **historical scaffold**：有证据表明用于弥补过去能力限制的约束。不能仅凭篇幅、措辞或兼容字段判定。
- **duplicate**：同一责任在多个可见层重复展开。删除对象是重复展开，不是该责任本身。

“既有 enforcement”只说明所指实现能检查什么；读取过源代码不等于运行过测试，更不等于证明模型遵守了全部自然语言边界。

## 2. 唯一责任层

| 层 | 建议保留的责任 | 应由其他层承担的内容 |
|---|---|---|
| Entrypoint | 启动、足够的 Direct / Workspace 判别、定位并加载主 Skill、解释用户传入参数 | 阶段操作、选题协议展开、正文与审稿操作、完整完成流程 |
| Agent spec | Avereth 身份、用户交付身份与权限边界、事实输入隔离、最小控制合同、主线程访问交接 | 每阶段算法、文件字段清单、具体 schema 版本、完整 reviewer / output SOP |
| 主 Skill | 工作流语义、路由定义、不可越过的边界、controller bootstrap、JIT 使用与完成合同 | 方法族、体裁、Commonplace、评审、视觉 QA 的详细操作说明 |
| 已有 JIT reference | 对应 action、发表轨道、方法或交付条件的操作知识 | 独立阶段、独立完成声明或与 controller 冲突的状态判断 |
| Controller / canonical validators | 当前状态、合法操作、身份与 hash 绑定、具体事实合同、收据和事务交付 | 推测真实用户授权、把总分当研究成立、证明宿主实际视觉/隔离行为 |

多个入口各自可用时仍需要最小路由信息。不能把完整路由定义从 E、A、S 同时删除，再假定尚未加载的 Skill 会纠正路由。entrypoint 和 agent 可保留短判别及指针；唯一详细语义归 S。

## 3. Hard invariants：保留的最小合同

| ID | 精确原位置与责任 | 建议唯一责任层 | 既有 enforcement 与实际边界 | 处置与理由 |
|---|---|---|---|---|
| HI-01 | S:8、48–53、61–67、201–202；E:6、17、34；A:7、18–20：状态、最早未完成阶段与完成权威 | Controller；S 保留如何读取和声明结果的短合同 | `scripts/avereth_core/cli.py:1621–1668` 的 `gate_stage` 拒绝越过最早失败阶段；`workflow_registry.py:293–307` 声明阶段投影。不能阻止代理在对话中虚称完成 | 保留责任；删除入口重复展开。不得把派生 MIR、plan 或评测变成完成权威 |
| HI-02 | A:7–8、59–60；E:35、37；S:84–85、203–205：用户标题/对象/理论/交付身份与外部操作授权 | Agent spec；工作流确认由 controller 检查 | Agent `permission_profile=workspace_write` 仅声明宿主权限范围；未发现统一 validator 能证实所有 push、消息、付款的真实用户授权。`research_decision.py:5368–5375` 检查当前问题和承诺绑定 | 保留 agent 的显式权限与身份合同；不得以已有文件或可调用工具推定授权 |
| HI-03 | S:78–81；A:28：candidate metadata 不自动取得来源身份或内容资格 | Acquisition canonical registry / validator；S 保留底线 | `cnki_acquisition.py:993`、`:1365`、`:1549`、`:1744` 检查核验记录、全文结构、身份/轨道与文件；不能自动证明填写核验记录的人真实阅读过论文 | 保留来源真实性要求，元数据操作细节 JIT |
| HI-04 | S:82–83、115–117；A:28–29：真实 accepted result、负面结果与推断边界 | Design / execution canonical validators；ProsePacket 下游资格 | `prose_packet.py:688–757` 只投影当前合法结果用途；`skills/empirical-research/scripts/method_execution.py` 验证 accepted action / result / artifact 链；实际科学解释仍需证据判断 | 保留；不能用更自然的语言、负面结果缺省或总评分补偿越界 |
| HI-05 | S:52、84–85、109；E:34；A:30–31：问题、动机、范围、工作标题及标题权限须明确确认 | S 定义确认语义；`confirmed_motivation.md` / controller 承载记录 | `plan_service.py:149–184` 投影用户检查点；`research_decision.py:3819`、`:5368–5375` 验证承诺结构/绑定。真实对话授权仍需代理如实记录 | 保留；`can_run_gate=false` 不能由代理解释为可跳过确认 |
| HI-06 | S:144–147、159、163–165；A:32–38：正文事实输入仅限 ProsePacket，语言范例不授权事实/引文 | Agent 最小隔离合同 + 既有 `academic-prose.md` §1；packet validators 执行字段/内容合同 | `prose_packet.py:1932`、`:2114`、`:2513`、`:2921`；`commonplace_retrieve.py:validate_packet`、`commonplace_writing.py:check_run`。字段/摘要可核验，但实际上下文隔离必须真实执行 | 保留事实防火墙；可把字段枚举及操作序列从常驻层移往 JIT，不能对 Writer 开放完整库 |
| HI-07 | S:138–139；A:39–41：MIR 派生性、stale closure 与实际进入规范稿的当前输出 | Manuscript compiler | `scripts/avereth_core/build/manuscript_compiler.py:_rebuild_proof_issues`、`validate_workspace` 绑定当前合同、packet、两稿和语义保证链 | 保留代码和简短主 Skill 指针；删除 agent 中完整 rebuild 说明不等于解除 rebuild 要求 |
| HI-08 | S:119–125、169–172；A:42–46：如实说明研究者/评审隔离，保留首轮输出 | Operation risk router / review validators；agent 保留不得冒称隔离 | `skills/empirical-research/scripts/researcher_dispatch.py:614–689`、`:799–826` 检查不同 context、协议与输出；`structured_review.py:1372` 起封存派发。仅有不同字符串 ID 不能证明实际独立宿主上下文 | 保留 provenance 与真实模式；详细派发规则延迟加载 |
| HI-09 | S:177–179、201–206；E:29–35；A:49–55：当前 PASS audit、真实视觉 QA、事务交付和不得虚报完成 | Output controller；agent 保留真实检查与停止边界 | `scripts/avereth_core/output/run.py:200–282` 验证 QA 声明和当前候选；`:526–648` 两步交付；`:648` 起验证完成。程序不能证明操作者真的逐页看过图 | 保留；只把步骤/命令搬到 output JIT。不可将首次 QA_REQUIRED 当最终交付 |
| HI-10 | S:73–74：不手动删除锁，只恢复当前主机、已死亡 PID、未漂移锁 | Lock implementation；故障时加载操作说明 | `scripts/avereth_core/infrastructure/locks.py:158–229`、`:241–268` 检查状态和确认 | 保留恢复前提；具体操作可按 doctor 故障 JIT，不能将“减少步骤”用作强制删锁依据 |
| HI-11 | A:56–58：登录、机构访问、captcha、下载确认留在主线程 | Agent spec | `acquisition-registry.md:28` 规定相同边界；未发现覆盖所有宿主的自动交接执行器 | 保留为 agent 权限/访问约束，不能因其未被代码完全强制而删除 |

本节中的源码路径若未带 `skills/`，均相对 `skills/cnki-paper/`。函数名是稳定定位，原行号辅助查找；源码定位证据不宣称实现消除了全部事实或权限风险。

## 4. Duplicate：优先删重复展开

| ID | 精确原位置 | 建议唯一责任层与保留点 | 当前 enforcement / 风险 | Lean 候选动作 |
|---|---|---|---|---|
| DU-01 | S:13–18；E:7–17；A:10–20：完整 Direct / Workspace 列举与 setup | S 维护完整定义；E/A 各保留足够的分流短句和 S 指针 | 路由发生在 controller 前，不能用 `gate_stage` 证明模型会正确路由 | 压缩 E/A 重复分类，不删除独立入口的最小分类能力。优先配对测“表层改字”和“实质改题” |
| DU-02 | S:57–65；E:15–22；A:17–22：doctor/status/plan、最早阶段、JIT | S §3 为唯一操作语义；E 只负责定位安装的 S | `plan_service.py:23–75`、`:99–184` 确定实际读取/写入范围；`cli.py:1621–1668` 强制 gate 顺序 | E 删除 doctor 后续展开，A 简化为服从主 Skill/current plan；保留可发现 bootstrap |
| DU-03 | S:105–111；E:24–27；A:23–25：选题前置协议及内部阶段目录 | S 保留“检查材料前读唯一协议”；细则归 `topic-selection-protocol.md` | `workflow_registry.py:329` 及 `plan_service.py:144–145` 在 research/topic-portfolio 返回协议，intake 不一定返回 | 删除 E/A 中 origins/reconnaissance/isolation/sealing/screening 的目录式复述；不能删掉 S 的前置指针 |
| DU-04 | S:201–208；E:29–35；A:49–55：继续可逆工作、修复、检查点、真实失败 | Agent 维护权限/停止边界；S 维护 profile/receipt 完成语义 | Controller 可验证工件状态；持续推进、是否需要访问/费用和如实汇报依赖代理行为 | E 移除完整 follow-through 段落；A/S 只保留各自责任，避免两份完整终点说明 |
| DU-05 | S:78–87；A:28–31：来源资格、负面结果、精确确认 | S 的证据底线及 canonical validators；A 留“不得超出证据或伪造确认”的最小合同 | HI-03 至 HI-05 | A 不展开具体确认字段或来源处理程序；这些字段仍由主 Skill/JIT/validator 保留 |
| DU-06 | S:129–142；A:39–41：MIR、contract、stale closure | 既有 compiler JIT；S 保留 build 入口和事实边界 | HI-07；`workflow_registry.py:341–344` 在 build/manuscript 已返回全文协议 | 删除 A 的 rebuild 操作段，S 只保留条件指针及派生性 |
| DU-07 | S:158–165；A:35–38；`academic-prose.md:30–42`：Commonplace 与 Clarity 细则 | `commonplace-writing.md` 和 `academic-prose.md` §1 | `plan_service.py:44–45` 仅启用 Commonplace 时加载其 reference；完整链另有 `check_run` | A 不常驻双稿借用步骤；S 保留 enable 条件与事实/语言权限区别 |
| DU-08 | S:119–125、169–172；A:42–46：operation dispatch 与正式三方评审 | Operation plan + execution/reference；正式评审 reference | `plan_service.py:194–215`；HI-08 | A 保留独立性真实性短句，移走实际角色、首轮输出及仲裁程序 |
| DU-09 | S:181–197 与前文多处路径列表；`workflow_registry.py:293–360` | `reference_requests` 返回局部路径与 section；Direct 保留必要自定位路径 | registry/plan 是声明源；主 Skill 索引本身不新增证据 | 缩短 Workspace 的重复大索引；保留 Direct 所需、维护专用和不能由当前 JIT 发现的指针 |

`tools/test_build_host.py:77–87` 在基线中要求三个生成入口都包含 `topic-selection-protocol.md` 和 `reference_requests`。这是可定位的**基线重复字符串要求**，不是重复文字仍有模型收益的证据。当前测试检查入口链接主 Skill，选题与 reference_requests 的详细协议由主 Skill 承担。原字符串要求的历史起因为 `unknown`。

## 5. Domain knowledge：移至已有 JIT

以下动作只减少常驻正文。没有相关 JIT 的任务仍须保留可发现的最小指针，不能把“移走”实现成不可达。

| ID | 精确原位置与内容 | 建议唯一 JIT / 触发 | 既有读取路径或 enforcement | 处置与理由 |
|---|---|---|---|---|
| DK-01 | S:26–34：三个发表轨道、当次官方核验、两个位置一致 | `acquisition-registry.md` §3/§6；`workflow-playbook.md` intake 配置 | `workflow_registry.py:317–322` acquisition actions；`cnki_acquisition.py:1744` 起验证 registry | 主 Skill 保留 Workspace 才需轨道及不得以 metadata 替代核验；三轨解释延迟加载。intake 的默认 scope action 不返回 acquisition reference，须保留配置指针 |
| DK-02 | S:20–24：单篇深读、对话/防御写作、摘要证据上限 | `critical-reading-and-synthesis.md`、`anti-defensive-writing.md`、`dialogic-argument.md` | research 的 `critical-reading` action 已存在；Direct 不经过 plan | 保留 Direct 条件指针和证据上限短句，避免 Lean 破坏无 Workspace 的文献答复 |
| DK-03 | S:89–101：定量触发、访问路线、数据探针、设计/执行绑定 | `quantitative-data-check.md` §触发条件/强度与门禁 | `workflow_registry.py:657–670`；`plan_service.py:52–53`、`:94–95` 已条件加载 | 主 Skill 留“问题需要结构化数据时按当前 plan 加载”；操作字段与路线清单延迟加载 |
| DK-04 | S:105–111：选题四种来源模式、侦察、候选准入 | `topic-selection-protocol.md` §1–§6 | `workflow_registry.py:329`；协议自身 `:3–5` 要求入口只保留摘要 | 保留“检查材料前读”指针；主 Skill 不复述六步内部流程。不能用 research JIT 取代此前的隔离要求 |
| DK-05 | S:115–125：design v4/execution v3、MVMR、单/多研究者 | `research-design-spine.md`；`empirical-research/references/method-execution-contract.md` | `workflow_registry.py:333–340` method-design / analysis；operation plan 输出 dispatch | 版本、方法准备与派发细则 JIT；当前已确认设计要求的 MVMR 与隔离不能因删文字而跳过 |
| DK-06 | S:129–142：体裁 profile 判别、史料/估计区别、proof obligations | `engine/manuscript-compiler.md` §MVP contract/Argument focus/Commands | `workflow_registry.py:341–344` 返回全文；compiler 有 profile 选择与验证 | 主 Skill 留 full_paper/revision 的 compiler 入口；体裁例子、自动判别次序及中文骨架进入现有全文协议 |
| DK-07 | S:136–137、195：中文刊物体例、史料原典 | `cn-journal-conventions.md`、`primary-source-citation.md` | `plan_service.py:54–74` 已按语言、方法和阶段选择 section；`test_plan_service.py:159–164` 检查史料章节 | 移走常驻说明，保留未结构化声明历史任务时的发现能力；不能把“历史方法”误读为估计型论文 |
| DK-08 | S:144–165：packet 字段、rhetorical contracts、具体 Clarity 动作 | `academic-prose.md` §1；`rhetorical-architecture.md`；`commonplace-writing.md` | build/manuscript 加载 prose §1；compiler reference `:264–266` 指向 rhetorical；Commonplace 有单独条件读取 | 常驻保留事实输入/firewall和不可增强推断；字段清单、引用节奏与操作顺序 JIT。移动引用时验证间接指针仍可达 |
| DK-09 | S:169–172；A:44–46：正式评审角色、immutable raw output、assurance/findings | `engine/reviewer-audit.md` §1–§6 | `workflow_registry.py:354` 的 structured-review action；`structured_review.py:1372` 起派发/封存 | 正式审计触发才读完整细则；普通改字不得因索引存在就自动调用三评审 |
| DK-10 | S:174–175：revision 分类、最早重开阶段 | `controlled-revision.md` §修改分类与最早重开阶段 | `plan_service.py:46–48` 按 manuscript_revision profile 加载；registry `:309–310` | 主 Skill 保留实质变更必须回事实拥有阶段；具体分类表延迟加载 |
| DK-11 | S:177–179：两次 output gate、全部 PDF、QA mode/context | `workflow-playbook.md` 阶段7；`docx-format-fixes.md` | `workflow_registry.py:355–356` 已按 output/docx-format 请求；HI-09 | 主 Skill 保留真实 QA 和当前 audit 前提；命令、字段与逐页步骤延迟加载 |
| DK-12 | S:191、210：品味、研究笔记、knowledge_baseline/update、历史项目 | `taste-judgement.md` §贡献事实与派生视图/历史项目与回退 | `workflow_registry.py:175` 已把 research_notes 标为 scratch；本次未找到 taste reference 的自动 action 条件 | 笔记不作证据/Writer 输入的边界保留；品味工具清单先变条件指针，不能宣称已有自动 JIT 覆盖 |
| DK-13 | S:73–74：锁恢复命令 | 既有 `workflow-playbook.md` intake / `recover-lock --help`，仅锁故障时 | `infrastructure/locks.py:241–268` 保留硬前提；`integration-architecture.md:43` 当前把动作正本指向 S §3 与 playbook | 搬移前先让 playbook/CLI help 明确承接当前唯一操作说明；本项不能简单删除 S 后留下循环指针 |

JIT 自身仍有可测负担：`plan_service.py:46–48` 对 revision 几乎所有非 output 阶段加入整份 controlled-revision；`:49–51` 在中文/混合轨若干 action 加入整份 cnki-operations；`:44–45` 在 Commonplace 的 research/build/audit 加入整份协议。是否产生重复读取取决于宿主实际行为，当前证据不足以把这些自动加载判成冗余。应测实际 reference reads 后，再改变已有 action scopes。

## 6. Heuristic 与 historical scaffold 的实验边界

| ID | 分类与精确原位置 | 建议唯一责任层 | 既有 enforcement / 未知 | 处置与可证伪理由 |
|---|---|---|---|---|
| HE-01 | heuristic；S:8–9、91、110–111：问题优先、不用数据反向造题、说明决定性取舍 | 主 Skill 一条研究规划默认；选题细节 JIT | `topic-selection-protocol.md` 及 direction contract 可检查授权与来源；问题是否有价值不能由字符串完全判断 | 可压缩常识式展开，保留方向授权。测模型是否反向用可得数据预设问题、是否遗漏真实取舍 |
| HE-02 | heuristic；S:57、E:22、A:17–18：已读未变规则不重读；首次或 runtime 变化 doctor | 主 Skill bootstrap | Controller doctor 可诊断环境；未发现自动证明“当前上下文已读且未变”的检查器 | 保留合理默认，可测宿主读取缓存和重复 doctor；不删环境变化后必要验证 |
| HE-03 | heuristic；S:140–142：最小充分主线/责任链、按复杂度启用 proof obligation | Compiler JIT 的设计帮助 | AMC/profile 对已激活字段有约束；是否需要更复杂论证链部分是研究判断 | 文本可条件加载；启用后的事实/兑现检查保留。测过度工件化与论证责任遗漏 |
| HE-04 | heuristic（执行策略），伴随 HI-06/HI-07；S:154–156、163–165：固定 Writer→Clarity→Semantic→Clean Read 序列 | 既有 prose 协议与当前 validator；风险触发仅作为单独实验 | `prose_packet.py`、compiler rebuild 和 Commonplace 当前验证完整链，不能只删 Skill 步骤而让 runtime 仍要求它 | 本次只移动操作说明。删 reviewer / 条件触发须另设单变量实验，量化 unique catches 与新增 hard failures；不纳入文本 Lean 的默认变更 |
| HE-05 | heuristic；S:169–172：评审按需，普通 clean read 不制造 Finding 配额 | Review JIT / review action | 正式 review 已有 immutable/version 合同；是否值得派发属于任务策略 | 保留按需触发，测不必要 agent calls；不能以“按需”宣称未执行的 isolated review 完成 |
| HE-06 | heuristic；S:203–208、E:29–35、A:49–55：持续推进、无新信息不重试、新能力先证据再默认 | Agent 停止/推进边界；组件实验流程另行维护 | 不存在覆盖全部工具与真实恢复机会的确定性判别器 | 去跨层重复；“继续”与“停止”两方向均须测。不能只优化较少调用而接受提前结束 |
| HS-01 | historical scaffold：**未证实**；S:48、138、152 的八阶段兼容、baseline 恢复和旧字段兼容 | 既有 controller/legacy/compiler | 当前存在合法旧工件消费者和恢复合同；只证明兼容用途，不证明曾为弱模型添加或已无价值 | `history_origin=unknown`；保留兼容责任。候选只能删常驻解释，不能删恢复能力或把旧工件自动升级 |
| HS-02 | historical scaffold：**未证实**；S:191、210 的品味工具名、历史项目处理、临时笔记说明 | 既有 taste reference / scratch 规则 | `research_notes.md` 仍在 registry 登记；本次未提供实际任务消费频率或历史缺陷记录 | `history_origin=unknown`；移入条件文档可实验，不能直接判为“旧模型补丁”或删除实际字段 |

本范围内没有足够证据把任何约束正式认定为“已过时的 historical scaffold”。兼容协议、清晰度编辑步骤和冗长说明都不自动具有这一分类。

## 7. 可直接采用的消融变量

以下是实验选择表，不是新运行协议、任务数量门槛或 stage。每次只改变一组可归因变量；controller、事实文件、权限与必要 JIT 内容保持同一版本。

| 实验 ID | Current → Lean 单变量 | Minimal 对照边界 | 相关 tags / 需要观察的失败 | 首要测量 |
|---|---|---|---|---|
| CC-ENTRY | DU-02/03/04：去 E 的阶段/JIT/选题/完成展开，保留 bootstrap 与最小路由 | 保留 agent 最小权限和主 Skill 可发现性；不能同时移走 S 前置指针 | routing、checkpoint、permissions、reference-loading；Direct 误建工作区、选题提前看材料、缺确认 | 实际加载 bytes、重复读取、错误路由、任务完成 |
| CC-AGENT | DU-06/07/08：A 只保留 identity/permissions/firewall/最小控制合同 | 同一 JIT 和 validator 可用；不减事实上下文隔离 | prose、method、artifact、claim-evidence；错误跨稿复用、漏独立性、stale closure | agent 常驻 tokens、tool/agent calls、hard failures |
| CC-DOMAIN | DK-03/05/06/07/09/10/11：S 条件细节变为已存在 JIT 指针 | 主 Skill 仍可判断何时请求资料；没有自动覆盖的 DK-01/12/13 单独处理 | reference-loading、quantitative、method、citation、prose；需要时找不到域知识/字段、无关时多读 | unique/duplicate reference reads、加载 bytes、completion、evidence completeness |
| CC-INDEX | DU-09：主 Skill 不常驻重复的大路径索引 | Direct 与维护任务保留明确可发现路径 | routing、context、reference-loading；选错 leaf skill 或误读全部阶段 | 实际检索/读取次数、错触发、多触发、缺读 |
| CC-HEURISTIC | HE-01/03/06 中一个规划默认，独立于入口/JIT 改动 | 保持事实与授权前提及机器合同 | task-completion、context、retries；提前停止、无意义循环、过度步骤 | completion、retries、tool/agent calls、latency |
| CC-REVIEW | HE-04 中一个 reviewer 的调用条件，另行预登记 | 不得关闭 protected facts、否定结果、权限、receipt 或 ProsePacket 边界 | prose、negative-result、claim-evidence；独有缺陷是否丢失 | unique catches、repair outcome、hard regressions、tokens、latency |

Current 是冻结源；Lean 是一个预先列出 CC/DU/DK 项的 candidate；Minimal 是同一宿主与 controller 下只保留最小路由、权限、事实/状态合同及域知识获取入口的实验条件。**本清单没有生成或运行这三套模型条件。** 同时删除多个职责的 Minimal 只能用于能力基线，不能据它独立归因某一条规则的收益。

可从现有回归库选择代表任务：独立翻译/表层改字、同一句请求中发生实质改题、无材料的 topic selection、历史原典研究、定量执行、已存在稿件的受控修订、Commonplace 写作、已到 QA_REQUIRED 的交付。数量由变更与不确定性决定，不强制凑固定数量。

静态检查已有定位：`tools/test_build_host.py:77–87`（入口字符串合同）；`test_plan_service.py:17–31`（最早阶段）、`:33–53`（定量条件）、`:55–65`（确认/完成停点）、`:131–141`（action 不改状态/写权限）、`:166–180`（output section 与 topic 单一协议）。事实与完整链回归可复用既有 `test_prose_packet.py`、`test_commonplace_writing.py`、`test_manuscript_compiler.py`、`test_output_transaction.py` 和 `test_researcher_dispatch.py`。这些是本次检视的测试位置，**没有在本清单任务中重新运行**。

## 8. 判定与记录

一次候选的静态结果可以是“常驻源文本减少”“去掉多处相同展开”“JIT 路径仍可达”。只有真实配对执行才可报告 completion、input tokens、调用次数、耗时或费用差异。静态 byte 差不能换算成未测 token；reference_requests 也不能代替 actual reads。

配对记录应沿用现有 telemetry / eval outputs，至少识别：同一任务和材料、baseline/candidate revision、所改 census ID、模型/宿主/预算、实际读取及其重复、tool/agent/gate calls、重试、持续工件、真实 tokens/latency，以及逐项 hard integrity 和任务完成结果。缺失测量保留 unknown，不为 census 另建科学状态或每条规则的永久工件。

新增来源伪造、无授权操作、科学状态/确认漂移、主张越界、负面结果丢失或虚报完成，均不能由 prose preference 或较少 tokens 抵消。满足 hard constraints 后，KEEP 只说明预登记工程目标有证据改善；它不自动意味着论文整体质量提升。条件不匹配、测量缺失、结果接近或归因混杂时保留 UNCERTAIN。

删除候选的采用依据应写成具体范围，例如 `CC-ENTRY / efficiency_gain / quality_improvement_proven=false`，并绑定实际证据。删除一份重复说明只需要证明唯一责任仍可到达且相关行为未退化；删除一个 gate、reviewer 或有消费者的 artifact 需要独立实验，不能借文本去重一并实施。

## 9. 当前 Lean 文本的责任归属

当前 S 的“事实、权限与写作边界”“领域知识按需读取”“停止与完成”规定工作流责任；A 规定身份、授权、事实隔离与主线程访问边界；E 负责分流及主 Skill bootstrap。前文 a4b32e1 的精确原位置保持不变，当前文本处置不作为实测 KEEP。

主 Skill 保留检查材料前读取选题协议、锁恢复前提、精确问题/动机/范围/标题确认、负面结果、ProsePacket firewall 与真实逐页 QA。历史/案例过程研究显式选择 humanities profile 的例外由默认 compiler JIT 的 “Profile selection” 段规定；正式评审的 `single_agent` 诚实声明归 reviewer-audit §2。

普通新 Claim 的 `realization_mode=semantic` 要求归 `academic-prose.md` §1，由默认 build/manuscript JIT 直接加载，对应基线 S:163。该节明确：省略字段仅用于旧包的 `legacy_exact` 兼容，不能关闭新稿语义保真检查。`prose_packet.py:1121–1122` 的程序缺省及 `:1529` 的 semantic gate 条件保持原合同。

`agent-specs/manifest.json` 的主 agent phrase 合同聚焦 identity、bootstrap、authority、permission 与 firewall。相对 a4b32e1，主 agent 的15项短语约束变为9项，原集合中13项细节短语由其所属主 Skill/JIT/validator 负责；manifest 不再要求它们同时出现在主 agent 中。正式 Writer、Clarity Editor、Methods/Contribution/Clarity reviewer、Researcher 与 Adjudicator 的 manifest 合同与基线一致。此项核对的是字符串合同和责任归属，不证明模型行为或效率改善。
