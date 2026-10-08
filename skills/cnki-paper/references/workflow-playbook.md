# 工作流实战手册（CNKI-Paper v7 本地研究引擎）

本手册把问题定向、按发表轨道实采、研究设计、方法执行、证据推断、写作和审计接成一条可恢复控制脊柱。`cnki-paper` 是唯一控制面；私有 `avereth_core` 提供本地动作，检索、数据、方法、评审和渲染只按当前任务调用。权威边界见 `integration-architecture.md`，问题牵引判准见 `problem-led-research.md`。

机器状态保持兼容，认识活动允许回退：

`intake〔问题定向〕 → acquisition〔侦察获取〕 ⇄ research〔问题化与定向补检〕 →〔问题／工作标题承诺〕 → design ⇄ execution →〔问题／贡献／标题再判断〕 → build ⇄ audit〔表达／标题一致性〕 → output`

对用户以五个语义阶段呈现：`Scope=intake`、`Evidence=acquisition+research`、
`Analysis=design+execution`、`Manuscript=build`、`Verify=audit+output`。这是同一控制器的只读投影，
不改变八个机器阶段、profile 终点、回退与收据。

阶段与三问的对应（判准见 `three-questions-standard.md`）：`intake/acquisition/research` 先问“何种现实张力值得理解、已经知道什么”，问题承诺锁定“还要认识什么及什么才算非平凡回答”，`design` 回答“如何认识”，`execution` 形成“实际认识到了什么”并允许推翻问题，`build/audit/output` 负责诚实表达、批判复核与交付。问题、设计、证据和推断没有可审计答案时，不进入正文工序。问题承诺、设计路由、执行后再判断和审计同时用辩证、历史、系统、战略、底线、创新六种思维复核，但只记录改变决定的维度，不增加六张必填表或关键词质量门。

## 阶段 0：intake — 运行时体检、恢复与配置

每次新建、恢复或更新后先通过统一控制器体检和恢复：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
{{RUNTIME_HOME_ASSIGNMENT}}
{{WORKFLOW_PYTHON_CANDIDATES}}
    (Get-Command python -ErrorAction SilentlyContinue).Source
)
$Python = $null
foreach ($Candidate in $PythonCandidates | Select-Object -Unique) {
    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { continue }
    & $Candidate -B -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
    if ($LASTEXITCODE -eq 0) { $Python = $Candidate; break }
}
if (-not $Python) { throw 'Avereth v7 requires Python 3.10 or newer.' }
$Controller = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth.py'
& $Python -X utf8 $Controller doctor
& $Python -X utf8 $Controller status paper_rewriting_output
& $Python -X utf8 $Controller plan paper_rewriting_output --granularity stage --json
```

doctor 非零退出时停止并修复它报告的运行时或配置问题；v7 doctor 始终只读。`plan` 输出只读 `avereth-plan/v2`；stage 粒度用于恢复路由，当前最早阶段为 execution 时可改用 `--granularity operation` 查看操作级协议。恢复任务只执行 status 给出的最早未完成阶段，不通过修补或重写已通过工件来“修复状态”。

config 缺失时通过 Avereth 对话或本地 `intake_wizard.py` 生成并校验 `workflow_config.json`。配置存在后回到控制器，从 status 给出的第一个未完成阶段续跑，不重复覆盖已通过工件。

用户给出的期限、篇幅、课程／会议／期刊交付物和现有材料必须进入战略裁剪：它们可以改变候选范围、证据优先级和合法 task profile，但不能降低权限、来源、推断和用户确认底线。不得把期限当作跳过侦察 acquisition、research 定向补检或提前请求最终选题确认的理由；前置证据未完成时只能给暂定问题／工作题、风险与缺口清单。若期限只允许描述、测量、综述或范围受限的案例回答，就明确收窄问题与标题，不承诺无法执行的因果或系统级结论。

配置至少锁定：

- scene、tier、`output_language: zh`、目标期刊/会议；
- `publication_track`：`cnki-cn`、`international-ssci` 或 `mixed`；同一值写入 acquisition v2/v3 注册表，冲突即阻塞；
- `task_profile`：`full_paper`、`topic_selection`、`research_design`、`manuscript_audit` 或 `manuscript_revision`；
- 用户已提供材料及其真实访问状态；需要结构化数据时另登记定量数据检查触发条件；
- Word、LaTeX/PDF、翻译包和投稿包需求；
- 目标刊要求的引文体系与参考文献样式；
- 可选的 `citation_requirement`（只接受 user/venue 的真实外部最低数及依据）与 humanize 强度；旧 `citation_target_count` 必须迁移并分类。

引用样式必须来自 config、用户选择或目标刊投稿须知/范文。不得把上游英文模板的纯数字外观当成中文期刊通用规则。

配置后、系统检索前建立 `problem_orientation.md`。至少登记稳定 `PO-*`、实践触发、相关行动者、张力／未知、为何重要、可能失效的常识或移植框架、改变当前判断的材料、来源与认识状态、研究者位置和接近性、`feasibility-only/not-selected` 的方法数据角色，以及可追溯确认来源。它只冻结“为何值得寻找问题”，不提前锁定最终问题、方法或结论。若历史形成、跨层反馈、政策时序、重大风险或长期目标会改变定向，在同一叙述中写清相应阶段、系统边界、战略后果和最坏误判；不相关时不为凑齐六维造字段。运行 intake gate；未通过就不进入 acquisition。

## 阶段 1：acquisition — 侦察获取与统一登记（主线程）

获取分两遍。下表是整个发现环的能力菜单；acquisition 首遍只执行与初始 `PO-*`、真实权限和可复现查询有关的最小侦察，research 再围绕已出现的张力、竞争解释、反证和候选问题调用其余能力。不得在问题成形前为了通过工具门机械堆满全部范文、SOTA 或文献数量。

| 步骤 | 能力 | 产出 |
|---|---|---|
| 选刊（按需） | `journal-fit` 技能 | 目标刊未定或考虑改投时先走选刊：刊种 pack 路由＋anatomy 刊性＋目标刊官方来源实采核验，产匹配度表并请用户确认目标刊；本步结果直接复用进期刊情报 |
| 期刊情报 | 活动发表轨道的期刊目录／出版社官网 | 中文轨核验 CSSCI、北大核心、AMI、ISSN/CN、主办方与投稿体例；国际轨核验目标刊出版社页面、ISSN、scope、article types 与作者指南 |
| 本刊范文 | CNKI 期刊目录或目标刊出版社／合法机构仓储 | 每轨至少一条真实角色记录；另取至少五篇同刊同类型可比论文计算动态文献基线，范文角色数不代替文献量 |
| 领域 SOTA | CNKI 高级检索／`cnki-snowball` 或 OpenAlex／Scholar 发现＋DOI／出版社／合法 OA 原文 | 按轨道形成前沿、撞车对象、理论谱系和反证候选；发现页只作候选，承重前回内容原文核验 |
| 术语谱系 | CNKI 精确词/近义词/构词变体检索＋权威原典 | 核心术语的中文学界通行形式、规范译名、学科谱系、近邻概念和自创词撞车记录；查询式、日期、结果规模与代表来源登记进 source index |
| 内容核验 | 详情页/摘要/导出 | 注册表 verification + `extracted_notes/<ID>.md` |
| 本刊范文全文（承重者必需） | 筛选后逐篇下载 | 数量由实际刊性与功能比较责任决定；`cnki-cn` 存 `materials/cnki_pdfs/<ID>.pdf`，国际轨使用目标刊出版社或合法仓储全文，可存 `materials/source_pdfs/<ID>.pdf`；全部登记为 `target-example` 并做 SHA-256 封存 |
| 其他必要全文 | 筛选后最小下载 | 存入工作区受管 PDF 路径；只下载承重或需要页码核证的文献 |
| 网络经验 | 官方/原始网页检索 | 政策、统计、事件和机构实践的 URL、页面标题、机构与采集日期；用于经验线索，不替代学术理论 |
| 法规·案例（按需） | 北大法宝（pkulaw.com） | 议题涉法律法规、规范性文件、政策文件或司法案例时的经验材料系统检索：法规记标题、发文字号、发布/实施日期、时效性状态，案例记案号、审理法院、裁判日期 |
| 案例素材（按需） | 全球案例发现系统（htcases.com） | 公共管理/工商管理/图书情报三案例库（各含中国库、素材库、全球在线版；机构订阅或 CARSI 登录）。教学案例是教学化加工的二手材料：作论文经验素材时优先素材库并回溯一手来源（政府文件、公告、报道），登记案例名、库别、来源与采集日期 |
| 经典原典（按需） | 理论库（data.lilun.cn） | 党建、统战、思想理论议题引马列经典、领导人著作、党的文献时，用人民出版社"中国共产党思想理论资源数据库"按语句/章节检索定位规范卷页；引注引原典版本（如《文集》卷+页），页码核证接 `page-evidence` 渠道① |
| 国际学术来源 | `intl-search`（OpenAlex＋Google Scholar 并列发现、OpenAlex 引文滚雪球、S2 独有字段）＋`intl-export` DOI 通道 | 在 `international-ssci|mixed` 中是正常证据生态，在 `cnki-cn` 中是补充；覆盖由问题与承重责任决定，不设外文数量配额。Scholar 只作候选发现／撞车／DOI 线索，选定对象回 DOI／出版社／合法 OA 原文并跑 backward+forward 滚雪球补 SOTA 图谱 |

先完整读取 `acquisition-registry.md` 与 `research-material-feasibility.md`。把发表轨道、查询、权限探针、来源、核验、下载和用途统一写入 acquisition v2/v3 `reference_materials/literature_registry.json`；再由脚本生成 `reference_materials/source_index.md` 与 `citation_support_bank.md`。另以 `reference_materials/research_material_registry.json` 登记材料事实、真实小样本探针和访问／许可／覆盖／格式边界；学术材料只引用已有 Source ID，不复制 provider、URL、DOI 或题名形成第二来源表。仅有题名的记录仍是 screening evidence；两个 Markdown 都是派生视图，不是可手改的第二事实表。普通开放网络 `final-source` 必须登记作者／发布者、资助或利益关系、支持／质疑 Source ID、核验日期、状态和说明；无法证明时保持 `needs-review`。CNKI、官方原始记录和经 DOI／学术出版社／合法 OA 原文核验的学术文献不承担普通网页统一横向核验门，但仍服从各自内容、身份、日期与撤稿核验。

定量、计算、混合方法、用户明确找数据，或主张必须依赖结构化数据时，才读取
`quantitative-data-check.md`。本地、公开下载、API、注册、申请、机构订阅和商业路线平等比较；
acquisition 只记录候选获取路线，不扫描本机目录、不建立跨项目目录或资产快照。访问状态、许可与
变量信息在用于候选时回官方元数据或用户文件核实；token、cookie、密码和 API key 禁止进入工件。

经验材料涉法条与案例时优先北大法宝而非零散网页转载：其法规库带时效性状态与效力级别、案例库带案号，可追溯性优于转载页。登录与机构权限按实际平台由 `{{BROWSER_TOOL_NAME}}` 复用用户 Chrome。

**权限通则（适用北大法宝、知网、国际出版社及一切本工作流要求读取全文的订阅库）**：遇权限墙／登录墙时，只暂停依赖该访问条件的来源获取和后续动作，记录具体来源、访问状态与所需操作，并在当前阶段继续 controller 允许、已获授权且不依赖该条件的工作。登录、机构接入、验证码与下载确认由主线程向用户交接；子代理返回 `PRIMARY_THREAD_ACTION_REQUIRED` 并说明具体操作，主线程请用户在原 Chrome 登录、切换机构网络或提供合法机构权限。

必要访问条件仍不可用时，相应依赖与阶段资格保持阻塞；不得用条目元数据、摘要或未经授权副本替代本阶段要求的全文，也不得把降级材料标成该门已完成。只对活动发表轨道实际要求的来源执行权限门；国际轨道不因 CNKI 权限不可用而阻塞。正文引注法规／案例时引原典（发文字号／案号），北大法宝页面 URL 只作为核验通道登记进 source index；证据身份仍属 `web-experience` 经验层，不替代学术理论。

范文选择优先“研究任务同构”而非“主题相同”：重点比较贡献形态、论证主线、材料—理论接口与识别/解释任务。侦察首遍可只保留筛选线索；到 research 问题承诺前，无论是否请求深度仿写，都须完成活动轨道的范文全文合同，并让注册表的每条 `target-example` 记录同时保留规范来源 URL、本地 `.pdf` 路径、下载状态和 SHA-256。PDF 须可解析并包含摘要之外的多页文章正文结构与参考文献；扫描件另附带哈希 OCR 文本。所有轨道只要求至少一条真实、角色有效的范文记录并逐条核验；覆盖充分性由目标刊、文章类型、论证任务和研究审查决定，`mixed` 也不重复两套数量门。

完成真实获取后运行：

```powershell
$Acq = Join-Path $AverethHome 'skills\cnki-paper\scripts\cnki_acquisition.py'
& $Python -X utf8 $Acq seal paper_rewriting_output
& $Python -X utf8 $Acq sync paper_rewriting_output
& $Python -X utf8 $Acq validate paper_rewriting_output --scope reconnaissance --write
& $Python -X utf8 $Controller gate paper_rewriting_output --stage acquisition
```

侦察 acquisition gate 只证明：问题定向已存在、活动发表轨道的权限与查询记录真实、至少一条适用学术来源进入 v2/v3 注册表、派生视图一致。`cnki-cn` 要求 CNKI，`international-ssci` 要求国际学术来源，`mixed` 要求两种生态；它不证明覆盖充分，也不允许请求最终问题确认。

acquisition 通过后、research 深入前，主动向用户提供一次**可跳过、非绑定的方向否决点**：用户可以提前排除明确不想研究的方向，并在 `workflow_config.json.direction_veto` 记录 `status=recorded|declined`、排除项和确认依据。未回应、选择跳过或记录格式待核都不得阻塞 research；该决定只删除方向，不能替用户选定问题，也绝不替代 research 完成后的正式问题与工作标题确认。

## 阶段 2：research — 问题化、定向补检与研究合成

research 的规范序列为 `direction_contract → literature_reconnaissance〔真实检索〕 → grounded seed portfolio → portfolio audit → taste_pairwise_judgement〔材料初步成立且确需取舍或用户请求时，可选〕 → 有依据的 finalists → F0 需求拆解 → F1 低成本筛查 → candidate_focus〔软确认〕 → F2 最小可行证据 → adversarial_collision_search〔C1/C2〕 → novelty_clearance〔硬确认，C3〕 → question_commitment`；`problem-led-research.md` 与本节各检查点说明都服从这一条序列。F2 必须用真实最小样本证明访问、许可／伦理、覆盖、必需字段或角色、机器可读性、链接／可比性、变异／识别、成本和来源稳定性；只有 `PASS` 或经校验的窄义 `NOT_APPLICABLE` 才放行高成本获取与综合。`CONDITIONAL` 必须收窄并复验；`BLOCKED/FAIL/STALE/NEEDS_REVIEW` 均阻塞。访谈等人类参与材料不得在伦理与许可前以 pilot 绕过。详细合同见 `research-material-feasibility.md`。

定量分支的 F1 只形成轻量数据准备卡：候选来源、访问路线、单位、时空、必需变量、链接、
变异／识别、许可、风险和下一项最低成本核验。它不计算总分，也不取得 F2 或设计权威。
选定路线仍须取得真实文件／查询结果、绑定 SHA-256 并运行现有 F2 探针；数据库介绍、元数据页面、
字段名相似或“本地已有”不能授权高成本获取、因果方法或正文。

按 `engine/research.md` 的实质协议组织 Scene Analyst、Exemplar Learner、SOTA Mapper 三个研究角色。角色从通过侦察 gate 的注册表派生 source index、笔记与材料出发，由主线程根据它们暴露的缺口继续在活动发表轨道中真实定向补检并回写同一注册表；角色自身不直接操作来源平台。能使用不同上下文时才称“隔离”。不可用时主线程可按相同输入边界依次产同名工件，但必须标为 single-agent synthesis，不能冒充相互独立。

定向补检形成 `final-source` 后，完整读取 `critical-reading-and-synthesis.md`。运行 `literature_analysis.py migrate paper_rewriting_output --dry-run` 检查需读来源，审阅后才可 `--apply`；迁移骨架全部保持 `needs-review`。随后对每个 final-source 完成 `CR-*`：先还原问题、范围与空白，再在作者讨论之前独立读取数据／材料，按来源类型评价方法或论证，最后比较作者结论、替代解释、局限、利益关系和允许／禁止用途。摘要／详情页只能形成 `limited` 的作者位置记录；承重方法、结果、因果、机制、稳健性和冲突裁决须补合法全文。

逐篇裁决后建立 `SYN-*`，按问题连接支持、限定、矛盾、不确定与不可比关系，说明可比性、评价权重、异质性原因、分析者判断和剩余未知。`motivation_options_after_research.md`、Dialogue Option Cards、`sota_gap_map.md` 和真实空白判断消费这些综合单元，不能从书目列表或摘要支持句直接跳到“学界认为”。

Exemplar Learner 先按 `top-journal-anatomy.md` 的承重四维拆解：问题意识、贡献形态、论证主线、材料—理论接口；国际目标刊还须对齐出版社声明的 scope 与 article type，中文目标刊则保留刊方与 CNKI 刊性核验。完整八维与量规评级由主线程在合成时完成，写入 `style_profile.md` 和后续理据矩阵。每篇范文再做一张功能性 Narrative Wrap：背景/已知、张力、核心回答、解释/边界和认识结局各落在何处，章节如何交接，理论/构念/情境/行动者分别承担什么角色；只学认知推进，不把五阶段名称写进正文，也不改动目标刊的章节契约。`style_profile.md` 另加 Author Voice 与 Genre Weighting：登记可复用的概念对、判断尺度、立场强度、节奏偏好、第一人称/语态惯例和修辞禁区；理论稿强化概念与判断，定性稿强化机制叙事与行动者，定量稿只在标题、引言、讨论和结论提高风格权重，方法与结果保持透明。范文包含图表时再登记其**论证功能**（时间线、机制、比较、分布等）、表题/图题位置、表注与来源写法、列宽/信息密度及黑白样式；只学功能同构的图表，不按主题相似照搬版式。范文中的独创命名只能作为概念化动作样本，不得直接移植、近义改名或据此宣称学界已有通说。

主线程随后读取 `topic-induction-deduction.md` 与 `research-question-design.md`，建立六渠道输入账本：本轮用户材料或有位置说明的实践观察 `practice-experience`、可追溯官方／原始网络材料 `web-experience`、模型记忆中的经验线索 `memory-experience`、模型记忆中的理论候选 `memory-theory`、经摘要/详情/全文核验的知网理论 `cnki-theory`、经 DOI／出版社／合法 OA 摘要或原文核验的 `international-theory`。每个候选必须连接一个 `PO-*`、至少一个可追溯 practice/web 经验锚点，并按 `publication_track` 连接理论锚点：中文轨用 CNKI、国际轨用国际原文、混合轨同时使用二者；理论 Trace 与 Collision Trace 中的 Source/Query ID、DOI 或 URL 必须解析到当前 literature registry，未登记编号不算身份链。两种模型记忆渠道均可缺席，只能生成假设，不能标成已核验事实、引文或必填配额。用户既往论文与手稿（含本机其他论文工作区、会话记忆中的项目）不进入任何渠道，不得用来锚定或预设新选题；仅当用户本轮明确要求延续某稿时按未发表手稿处理（见该文件“既往稿件隔离”）。

先用 `avereth-topic-packet/v1` 在材料隔离条件下生成并封存问题种子，对 seed/screened 执行轻量方向契合、材料消融、语义签名与组合审计；仅对用户入围的 2–3 个 finalist 至少完成一轮：经验线索 → 归纳模式/异常与负例 → 公开先验理论视角 → 核验理论前提 → 演绎命题、支持观察与反证观察 → 定向补检 → 修正理论、边界或选题。两个通道的定向检索按该文件"视角×追问循环"执行（视角引导提问＋检索接地追问＋反收敛检查；未答问题记入 `sota_gap_map.md` 作证据缺口）。每个 finalist 另写 `Provisional Research Question`，标一个 `Primary Question Type`，并用 `O=…；T=…；I=…；P=…；R=强关系/弱关系：…` 展开五要素。分类看答案任务，不按疑问词机械判断。候选矩阵再填 `Gap Reality Check`，排查发表时滞、术语错配、相邻覆盖和贡献不足；填 `Outcome Unit & Comparison Design`。解释性、预测性和“有些……有些……”式问题锁定共同结果、可比单位及核心/对照案例分工；描述性、操作性、规范性弱关系问题则写清还原对象、行动主体—目标或行为—规范联系及相应设计，不虚构因果变量。候选比较还要检查：主要矛盾是否抓准、历史阶段是否会改变命题、系统边界和层次是否完整、用户与目标刊的全局价值是否成立、最坏误判及不可越过边界是什么、所谓创新是否带来可核验认识增量；只把影响保留／合并／淘汰决定的内容写入现有矩阵和选项说明，不新增固定六列。把 finalist 深核写入 `topic_induction_deduction_matrix.md`，运行 `topic_reasoning_check.py paper_rewriting_output --markdown --write`；未通过就不能请求 soft focus。

`Gap Reality Check` 依 `research-gap-diagnosis.md` 在原列内写一个主落点、阻断原因、具体未知、当前 `SYN-*`、反替代、研究责任和撤回条件。知识空白只作总状态；不新增七列，不要求候选覆盖七类，也不让“概念／理论／方法”等关键词替代证据判断。

research gate 前至少有：

- `research_dossier.md`
- `exemplar_learning_dossier.md`
- `style_profile.md`
- `sota_gap_map.md`
- `topic_induction_deduction_matrix.md`
- `motivation_options_after_research.md`
- 若触发定量分支：按 `quantitative-data-check.md` 形成数据准备卡；它不能替代下列 F2 工件
- 可审计的 `literature_registry.json` 与其生成的 `source_index.md`
- acquisition 所有的 `research_material_registry.json`：材料身份不复制 Source 事实，所选材料有真实探针文件与 SHA-256
- research 所有的 `research_feasibility.json`：所选候选为当前 F2 PASS 或窄义 N/A，basis 未过期
- `literature_analysis.json` 与其生成的 `critical_reading_report.md`、`literature_synthesis_matrix.md`、`literature_analysis_check.md`
- 活动发表轨道的 `target-example`：至少一条同刊、来源真实且实际可读的 PDF；目标刊动态基线的五篇可比论文另在 literature analysis 中留存可核验身份、类型、年份、篇幅和学术参考文献数
- 活动发表轨道的 `field-sota`：至少一条回 CNKI／DOI／出版社／合法 OA 原文完成内容核验的前沿来源；完整覆盖由研究问题、板块图和饱和检索裁决

### Research 内部轨道：来源覆盖与引用准备

`citation_support_bank.md` 是 `literature_registry.json` 的生成视图，不是独立阶段。它在问题确认前用于检查真实文献覆盖、证据缺口、时效和撞车风险；主张层的 Evidence ID—Claim ID 映射在 design 建立。

1. 从候选题推理矩阵的归纳模式、理论命题、反证条件和竞争解释派生中文方法词、问题词、应用词、邻域词与不限年奠基组；需要国际对话时加 1–2 组官方英译短语。外文承重方向另对 1–2 篇奠基/高被引对话对象跑引文滚雪球（`intl-search` 的 `openalex_snowball.py`，back+forward 各一轮）补齐候选；中文承重文献同理用 `cnki-snowball`（六方向，首页免验证、翻页验证码在环）。S2 他引上下文只作支撑句定位线索，滚雪球条目一律先 `candidate-only`，入库前回原文核验。滚雪球得到的"谁引谁"在条目取得 Source ID 后登记为注册表 `edges`（`acquisition-registry.md` 5.3）；奠基链覆盖门据 `cites` 边核验连通，真实反方据 `stance=critical` 边核验，立场只能来自读到的施引段落。
   外文关键词发现可并列运行 OpenAlex 与 Google Scholar；用户显式要求 Scholar 时直接查 Scholar。Scholar 只读第一页、间隔 ≥5 秒、单会话 ≤5 次；题名、片段、被引数和 Scholar BibTeX 统一登记为 `candidate-only`。DOI、URL 或题名—首位作者—年份命中既有来源时复用 Source ID；承重前须回 DOI／出版社／合法 OA 原文完成内容与撤稿核验。
2. `cnki-cn|mixed` 的中文组用核心来源筛选，结果页导出 GB/T/EndNote 元数据；`international-ssci|mixed` 的国际组保留发现查询并回 DOI／出版社／合法 OA 原文；两者都须从详情页、摘要或全文补 claim-support 内容。
3. 根据任务范围形成足以比较候选问题的覆盖；数量、时效与内容核验状态作为可见诊断，不把固定文献数或固定近年比例冒充普适质量门。配置要求的最低 `final-source` 仍须真实满足，奠基文献单独标识。
4. 生成视图沿用 12 列：

```text
Candidate ID | Reference/BibTeX | Year | Recency | Supports Section |
Support Claim Sentence | Why This Paper Fits | Source | Source Channel |
Verified | Citation Scope | Verification Note
```

5. 所有字段先写入注册表，由同步脚本生成视图。CNKI 行必须：

   - `Candidate ID` 复用 `literature_registry.json` 的稳定 `source_id`，不得另造编号；
   - `Source Channel=CNKI`；
   - `Source` 与注册表中的稳定 URL 一致；
   - `Verification Note` 同时含稳定 URL/标识符、采集/核验方式和 ISO 日期；
   - `Citation Scope=final-source` 的行必须有从摘要、详情页或全文核验出的具体 Support Claim Sentence；结果页筛选项标 `candidate-only`、`Verified=no`，不得用于写作或支撑主张。

6. 中文非 DOI 文献以 CNKI 详情页、导出元数据、期刊目录或本地原文构成可审计链；无 DOI 不等于未核验，也不要强塞 Crossref。外文 DOI 条目可另跑 DOI/Crossref 核验。中文专著以读秀书目页核验著录（书名/作者/出版社/年份/ISBN），马列经典与党的文献以理论库原文核验规范卷页（见 `cnki-operations.md` §12）。
7. **撤稿检查**：`final-source` 条目逐条过——外文看 OpenAlex `is_retracted`（true 是警示须回出版社核对真实状态，见 `cnki-operations.md` §9），中文查 CNKI 详情页与期刊官网撤稿/更正声明；确系撤稿不得作支撑文献引用，检查结果记 Verification Note。

运行 `cnki_acquisition.py sync` 后执行 `cnki_acquisition.py validate paper_rewriting_output --scope focused --write`，按 `publication_track` 检查范文、field-SOTA、final-source 与两个生成视图的一致性；所有轨道都验证角色身份，不执行数量或 CNKI 比例门。随后以 `literature_analysis.py validate` 裁决动态基线／兜底、来源计数、核心深读、板块覆盖和饱和检索。完整合同未通过时不得请用户作最终选择，但可继续补检和修订候选。

### research 内部检查点：candidate portfolio 到 question commitment

顺序以阶段 2 开头的规范序列为准，本节只展开各检查点。

**选题来源、侦察与候选组合**：执行 `topic-selection-protocol.md` 第 1–5 节，统一来源授权、真实侦察、packet 新写／历史兼容、隔离封存与候选准入。当前检查点再按以下研究工件和 C0–C3 规则深化入围方向。

只有 finalist 说明完整 `PO-*`、问题根据、研究问题原句、问题主类型、O-T-I-P-R、经验/理论 Input IDs、归纳模式或异常、先验视角、理论前提、演绎预期、支持与反证观察、经验—理论张力、迭代修订、按轨道撞车、真实空白核验、结果/决策单位与设计、材料可行性、推断边界和超 claim 风险。`topic_induction_deduction_matrix.md` 对 finalist 给出 `Provisional Title` 与 `Title Function / Claim Boundary`；`motivation_options_after_research.md` 的十六列和 Dialogue Option Cards 也只深核这 2–3 个 finalist，并与 finalist 集合一一对应。旧 `CNKI Collision` 表头仍兼容，但内容必须服从 `publication_track`。

**taste_pairwise_judgement（有分支品味卡时）**：`direction_contract.field` 解析到一张分支品味卡后，`taste_judge.py` 把 screened 候选与侦察集中去身份的已发表条目在隔离上下文中成对比较，产出 `taste_judgement.json`／`.md`（`authority=signal-not-gate`）；排序、四味判定与平庸路径进入 C0 的 retain/merge/drop/defer 理由，不作放行门、不折总分；热词剥离与平实改写两个探针翻转率超过三分之一即 `shortcut_suspected`，该轮只作未校准意见。无卡则本步不适用。命令、探针与校准语义见 `taste-judgement.md`。

**快失败与就地修复（成本纪律）**：探索阶段的返工代价必须压在最早的环节。种子数窗口（broad 12–18）已由生成 schema（按 lane 数分摊 min/max）与 `host-seal` 封存前预检强制，不会再拖到 bind 才暴露；`--compiled-at/--dispatched-at/--issued-at/--sealed-at` 一律省略让脚本自打 UTC 时钟，禁止手写时间戳制造时序颠倒。bind/validate 因**装配性账目**失败时——如 `RDEC.CANDIDATE.DISTINCTNESS` 的 declared difference_dimensions 未被复核支持（把候选声明改成复核结果的子集即可）、presented/finalist 列表错位、时间戳次序、字段归位——只修 `research_decision.json` 本身再重跑 validate；**只有** receipt 自身校验失败（签名/摘要/schema 不符）或其绑定输入真的变化（packet、seed seal、portfolio 摘要更新）才允许重发隔离子代理，重发前先说明是哪个 receipt 因何失效。哈希/receipt 记账操作按协议步骤合批执行（一步一次脚本调用），不逐字段起进程。语义复核中判为 load-bearing-distinct 的 pair 不再要求成句 rationale（difference_dimensions 即证据），只有 equivalent/uncertain 需要实质理由。

`research_decision.json` 是候选/C0–C3/问题挑战的 canonical contract。顶层 `disposition=pending|cleared|reopen|withdrawn` 只作粗粒度事实，控制器纯派生 `provisional/focused/challenged/reopened/cleared/withdrawn` 六种 research 内投影，不新增状态机。`focused` 时还纯派生 `preclearance_readiness`：C0–C3、候选/问题与 Query–Source–SYN 科学依据仍有错误就继续 `research_evidence`，全部内部一致才请求独立 `hard_clearance_confirmation`。C0 登记 `retain/merge/drop/defer` 及合并图；C1 必须引用完成且显式绑定当前候选的 collision/SOTA Query、非空且 content-verified 并通过轨道角色检查的 Source、最强碰撞 Source ID 与候选绑定且真实连接 Source 的 `SYN-*`，zero-hit 不得被写成新颖性证据；C2 对 `object / question_or_estimand / theory_or_mechanism / unit_case_time_scope / materials_and_identification_logic / existing_answer / claimed_contribution` 七维逐项登记 `same/partial/different/unknown`（范围可 `overlapping`），并区分 collision severity。实质碰撞若想 reframe，必须同时证明：剩余未知有独立理论或实践后果、新问题有不同可观察经验预期、可得材料能识别差异、回答会改变对原问题的判断；只换地区、年份、方法、数据或重述理论不得放行。C3 单独记录人类有界新颖性判断、非新内容、允许/禁止主张和确认身份，不用统一总分。soft focus 与 hard clearance 不得复用同一个确认事件。

主候选表仍是十六列，不增加 gap 分类列。每个 `Gap Reality Check` 只有在 `Status=corroborated` 且 Evidence Basis 可解析到当前 `literature_analysis.json` 的 `SYN-*` 时才可进入用户确认；机器核验结构和身份，不给 gap 的学术分量打分。

同一文件先建立 `Dialogue Option Cards`，再从卡片生成用户可见选项；每个选项登记 Response Target Type、Controlling Dispute/Unknown、Position/Source IDs、Candidate Response、Strongest Countervoice、Who Cares、So What 与 Missing Voice，并准确说明真正改变读者判断的后果及边界；若当前证据只支持一个明确 reader update，不制造第二通道。合法对象仅为 `explicit-dispute`、`common-assumption`、`literature-omission`；显性争论至少有两个来源支持的不同立场，不能为了“他们说／我说”制造阵营。公允性与最强反方质量交给隔离评审，Source ID、字段和占位状态由 research gate 裁决。

硬放行后写或确认 `confirmed_motivation.md`，记录确认来源、Problem Orientation IDs、问题为何仍值得追问、Non-trivial Answer Test、精确研究问题、问题主类型、最终动机表述、所选候选的 `Gap Diagnosis`、被否选项及理由、范围限制和禁止主张，并锁定主控对话／未知、回应对象类型、文献立场与 Source ID、初始作者回应、最强反方、Who Cares、So What 和遗漏声音处置。同一张 Field/Content 表还须登记 `Working Title`、`Title Authority=user-fixed|user-approved-working`、`Title Function=question-led|claim-neutral`、`Title Claim Boundary` 与 `Title Revision Rule=locked|reconfirm-if-substantive`；用户指定原题只能先锁定、提示风险和请求授权，不能静默改题。该文件仍是用户承诺/标题的 canonical authority；`research_decision.json` 只绑定其语义摘要，不生成或覆盖它。selected-candidate subgraph 绑定所选 candidate 语义、Option 矩阵投影、PO canonical 语义、相关 Query/Source/SYN、C2/C3、当前问题和承诺；其中无循环 `clearance_basis_digest` 不含 hard confirmation 本身，hard confirmation 的 `basis_sha256` 必须精确匹配，最终 subgraph 再纳入该确认。未关联背景与非所选候选变化不 stale，相关 collision/SOTA 新证据必须 stale；`bind` 只可初始化空摘要或修复同一 live graph 的派生报告，不能重算摘要而保留旧 hard confirmation。问题可在标题仍 locked 时被 challenge；这只会令 research FAIL，不会静默改题。统一使用 `$Python -X utf8 $Controller research-decision challenge ...`、`reopen ...`、`resolve-retained ...`、`migrate ...`、`rollback ...` 受控命令；先输出 plan，显式 `--apply` 才在 controller transition lock 下写入并保存 manifest/backup，rollback 同时核验 decision/report 当前 applied digest、备份摘要和路径边界后原子恢复。reopen 的用户提供问题先登记为 `draft`，不会自动 cleared；必须重跑 C0–C3 并取得晚于挑战/证据变化的新 hard confirmation。全部撤回还需独立用户确认“全部撤回且不替换”，随后终止于 research，novelty report 为 `NOT_APPLICABLE`，design 以后 N/A，且不生成替代问题、稿件或 audit/output receipt。v6.0→v6.1 显式迁移保留旧 `confirmed_motivation.md`，但缺少 canonical research decision 时必定重开 research。

不得从模型直觉、现成数据、可用模型或公共网页直接替用户确定选题；侦察 acquisition 和 research 定向补检前置检查未过时不请求最终确认。

## 阶段 3：design — 研究设计与推断契约

读取 `research-design-spine.md`、`research-foundations.md`、`method-routing.md`、
`measurement-inference.md`、`literature-review-routing.md`（仅综述路线）与
`terminology-governance.md`，建立 `research_design.json` 和 `terminology_register.md`。
`research_design.json` 是唯一机器可判设计真相：兼容读取 v1–v4，新建与修改只写
`cnki-research-design/v4`。`knowledge_design_matrix.md`、`concept_register.md`、
`claim_evidence_scope_matrix.md`、`method_route_matrix.md` 和
`research_integrity_check.md`、`case_design_matrix.md` 以及 v4 新增的
`operationalization_matrix.md`、`execution_protocol.md` 全部由它生成，不得手工维护。

每个 STEP 依据 operation、关联 Claim type 与类型化 `researcher_risk` 编译研究者分发决定。
独立编码、参照标签集构建和留出验证必须至少两个隔离 run/context；试编码校准、边界案例与
推断审计在相应质量风险触发时进入多研究者模式。该投影不改变八阶段，也不另存设计权威。

`knowledge_state.gap_authenticity` 重复 `confirmed_motivation.md` 的两轴诊断核心：主落点、阻断原因、具体 Gap Claim 与当前 `SYN-*`。设计只把它转换为条件式研究责任，不由 gap 标签自动选方法；任一核心身份改变都先回 research 更新综合并重新获得用户确认。

契约先锁定 Question/Concept/Claim/Design/Evidence 稳定 ID，再按问题与推断目标填写条件分支：

- 每条路线：稳定 Design ID、family/function/role、依赖、问题/主张/证据映射、材料边界、
  选择、权限伦理、复现、报告计划与推断上限；
- 多路线：sequential、convergent、nested、complementary 或 adjudicative 的路线顺序、
  交接、材料独立性、冲突处理和综合推断上限；
- 案例导向剖面：所有设计显式声明适用性；适用时登记 Case Universe/Case/Scope/
  Comparison/Within-case ID、理论目的、因果逻辑、结果知情选案、材料角色与整合顺序；
- 条件适配：实验、调查、案例/过程/一致性、QCA、内容/话语/文本即数据、网络、比较/类型学、
  历史、扎根、描述/关联/预测/因果定量、计算、四类综述、概念/诠释/规范；
- 可执行协议：每个活动 Claim 由稳定 `OPR-*` 落到可观察项、识别／测量规则、材料、质量检查、
  判定规则与失败后果；每个 OPR 进入稳定 `STEP-*`，步骤声明 `mvmr|full`、读写集、accepted
  前置、`method-operation/v1` 操作、预期 Artifact、验收诊断与失败路由；
- 认识论与治理：本体论、认识论、范式、研究逻辑、研究者位置、兼容理由，以及数据真实性、
  选择性报告、引用、署名、既往发表、一稿多投、利益冲突、AI 与隐私。

设计复核把六种思维落实为条件式设计责任：历史性主张须有可辩护的分期、连续性／断裂与因果时序；系统性主张须明确层次、边界、反馈、外溢和跨层推断；战略性问题须把设计能力集中到决定性未知；底线须给权限、伦理、推断、停止与回退条件；创新路线须说明它比成熟做法多识别什么以及如何被证伪。辩证关系贯穿竞争解释和材料判别。没有相关主张时不机械添加历史或系统模块。

经验研究同时把 `empirical-research` 的设计、数据/语料、样本、分析、结果、伦理与复现工件登记进契约。固定样本量、统一 p 值/信效度/QCA 阈值、“必须有假设”或“RCT 天然最高级”只作参考提醒，不作通用硬门。

方法 operation profile 与支持声明只登记在既有 `method-adapter-registry.json`。成熟度检查累积
L0–L5；`production_ready` 至少须有 L4 的方法专属 MVMR、正例、反例和 worked example，L5
另需 design→execution→result→writing 端到端评测。其余准确标为
`experimental_method_support`；通用 scaffold、共享空壳 fixture 或文件存在不能抬高成熟度。

运行：

```powershell
$Design = Join-Path $AverethHome 'skills\cnki-paper\scripts\research_design.py'
& $Python -X utf8 $Design schema --version v4
& $Python -X utf8 $Design template --family <family>
& $Python -X utf8 $Design render paper_rewriting_output
& $Python -X utf8 $Design validate paper_rewriting_output --write --stage design
& $Python -X utf8 $Controller gate paper_rewriting_output --stage design
& $Python -X utf8 $Controller protocol validate paper_rewriting_output --json
& $Python -X utf8 $Controller protocol compile paper_rewriting_output --json
& $Python -X utf8 $Controller plan paper_rewriting_output --granularity operation --json
& $Python -X utf8 $Controller next paper_rewriting_output --json --explain
```

`protocol compile|validate`、`next` 与 operation-level plan 都是只读投影；需要刷新生成视图时才
显式运行 `protocol render paper_rewriting_output`，它不会写 canonical protocol 或推进阶段。

旧工作区先 `migrate --dry-run --to v4`，确认后再 `migrate --apply --to v4`；无法从旧契约或
自由文本证明的案例角色、范围条件、机制痕迹、一致性结果、OPR 或 STEP 保持 `needs-review`。
v1–v3 可只读 status/render，但任何新执行、审计或凭证都要求 confirmed v4；迁移不得把 prose
或字符串动作提升为可执行事实。设计门只自动裁决来源身份、
必填边界、ID 关系、跨工件一致性、伪随机化、路线能力越界、同源伪独立、材料泄漏、伦理与治理
等客观问题；价值、概念贴切性、范式/方法适配、选案价值、代表性、范围质量、比较可比性、阈值
与外推进入 REVIEW，不伪装成机械分数。

标题、摘要、各级标题、中心命题和贡献陈述中的核心概念全部登记为 `established-cn`、
`official-cn`、`translated-established` 或 `author-proposed`，并用注册表 Source ID
说明中文学科谱系、近邻区分和内涵外延。自创术语默认最多一个；多个须记录不可合并性、
层级和用户批准。

## 阶段 4：execution — 构建证据、分析与推断

design 通过后才执行方法。先读 `empirical-research/references/method-adapters.md`、
`method-execution-contract.md`、`research-integrity.md` 和 `researcher-collaboration.md`；案例导向路线再读
`case-oriented-comparative-design.md`。执行唯一机器事实源为
`method_execution.json`（兼容读取 v1–v3、新写 v3）。v1/v2 只可兼容读取或显式迁移；
`execution_record.md`、`method_pilot_report.md`、`action_result_trace.md` 与
`claim_disposition_report.md` 只由工具生成：

```powershell
$Execution = Join-Path $AverethHome 'skills\empirical-research\scripts\method_execution.py'
& $Python -X utf8 $Execution schema --version v3
& $Python -X utf8 $Execution scaffold paper_rewriting_output
& $Python -X utf8 $Execution validate paper_rewriting_output --write --stage execution
& $Python -X utf8 $Execution render paper_rewriting_output
```

新工作区不运行 migrate；旧 v1/v2 执行先 dry-run，再由操作者明确 apply。迁移保留已有 ID 与
SHA，但清空类型化 actions、降为 `needs-review` 并要求重新绑定，不生成 accepted action、MVMR、
诊断或 PASS。

```powershell
& $Python -X utf8 $Execution migrate paper_rewriting_output --to v3 --dry-run
& $Python -X utf8 $Execution migrate paper_rewriting_output --to v3 --apply
```

每个 run 登记 Execution ID、Design ID、adapter version、设计路线摘要、问题/主张/证据以及
Case/Scope/Comparison/Within-case ID 映射、
不可覆盖的 action attempts、方法族执行字段、哈希工件、正式结果、偏离、失败代码与路由、负面
发现、伦理事件、软件环境和执行后推断上限。每个 action 绑定蓝图 operation、attempt、
`mvmr|full`、启动时设计 SHA、输入输出工件、诊断、结果与主张处置；只有全部诊断通过的
accepted action 可以产生正式 result，双方引用和 Artifact 输出必须闭合。合法不适用/撤回必须
有理由，不用空字段伪装完成。

当编译决定为 `isolated_multi`，控制面以 `Researcher A/B` 等中性功能角色分发相同冻结协议和
相同研究输入范围，使用不同 run/context 并封存首轮严格 JSON 工件；随后从逐项标签重算一致性和
精确分歧，分歧存在时才启用不同 `Adjudicator`。参照标签、留出标签、同伴输出和父线程判断按任务
保持不可见。全部 provenance、任务记录、指标、分歧和仲裁嵌入当前 action 的
`researcher_collaboration`；研究者不输出身份自述或工作流结论。

全量执行前先完成 MVMR：用真实 material、真实 analysis unit、一次提取／编码、设计内方法动作、
哈希工件、passing diagnostic、result 和 claim disposition 闭合最小方法链。蓝图所需 MVMR
operations 未全部 accepted 时，full action 不得 accepted。MVMR 是 execution 内检查点，不是第九阶段。

所有路线必须把真实材料、测量/识别、样本/选案/语料/论证步骤、权限伦理和复现工件接入稳定
Execution/Design/Evidence/Claim/Artifact ID。不得用计划文本冒充执行，不得用同一材料在未披露
切分或独立性的情况下循环建构并验证主张。伪随机化、训练泄漏、同源伪独立、未登记数字/结果、
内容哈希变化和未解决伦理事件均阻塞。案例导向执行还必须登记实际纳入、选案偏离、理论预测—
观察、机制痕迹、负面案例、范围修订和路线交接；一般案例研究、过程追踪、一致性分析与 QCA
分别服从其主张能力，不得互相冒充。

结果承重场景先通过 `method_execution.py::downstream_eligibility`，再按 `engine/results-validation.md` 的 Derived View（八列，含 Result/Claim/Action/Artifact ID 与 Interpretation Boundary）从规范投影生成说明性 `results_validation.md`。

每个活动 Claim ID 必须落到执行记录、证据位置和允许解释范围；负结果、边界条件和不支持项同样登记。运行 `results_validation_check.py`；该检查器不读取 Markdown 行来授予资格，手填 Claim ID 或数字不能通过。综述或非结果场景按其路线声明不适用理由，不伪造结果。

build、ProsePacket 与复现包只消费 `method_execution.py` canonical 下游资格投影中的 result：
accepted action、result 与 Artifact 必须双向绑定，Claim disposition 必须允许当前用途。
仅 `supported|qualified` 结果与 `retained` 处置的组合才能支撑原命题；`null|negative|not-supported`
结果与 `narrowed|withdrawn` 处置的组合只进入显式负面／null 报告。active v3 校验失败或
没有合格 result 时资格为空，不回退到字符串 Result ID、旧动作文本或手填数字。

### 检查点：problem_and_contribution_reappraisal

执行后先允许结果反过来检验问题，再按 `engine/contribution.md` 写 `confirmed_contribution.md`。在 `Calibration Receipt` 增加：

- `Problem Disposition After Execution`：`retain`、`refine`、`reopen` 或 `withdraw`；
- `Gap Disposition After Execution`：`retain`、`refine`、`reclassified` 或 `withdrawn`；主落点、阻断原因、具体命题或 `SYN-*` 核心变化时回 research；
- `Reader Prior` / `Reader Posterior` / `Displaced Source`：先验与后验分别投影自 `research_design.json.knowledge_baseline` 和 `method_execution.json.knowledge_update`。按贡献类型、来源身份及 accepted result→claim 链校准；词面相等或包含只提示复核，不据此拒绝复现、边界收窄或负结果。字段与迁移见 `taste-judgement.md`。
- 改变处置的 Execution/Claim/Evidence IDs、负面结果和偏离。
- `Title Disposition After Execution`：`retain`、`narrow`、`revise`、`reopen` 或 `withdraw`；
- `Evidence-Calibrated Title`、带 EXE/Claim/Evidence ID 的 `Title Revision Basis` 和 `Title User Decision`。实质改题必须来自执行结果或范围边界并由用户确认；`user-fixed` / `locked` 题目还须显式解锁。

`reopen`、`withdraw`、gap `reclassified` 或 `withdrawn` 是合法认识结果，但会阻止 build 并返回 research 重新确认问题或终止项目，标题处置也必须同步重开或撤回。方法新颖、模型复杂、显著结果、图表整洁、期刊标题公式或已经投入大量工作都不能覆盖问题或 gap 失效，也不能成为实质改题依据。问题仍成立时，再至少完成贡献文件的四个必填区块，并明确：

再判断时重做适用的六维复核：证据是否改变矛盾主次、历史分期或系统边界，原问题是否仍服务全局目标，最坏风险是否触底，创新假设是否获得了真实增量。任一变化必须传播到问题、设计、贡献、标题和下游工件；不得用沉没成本或局部成功维持原路线。

- 单一核心贡献陈述；
- 哪个问题/缺口使贡献必要；
- 哪些已有材料或结果可以验证；
- 允许的强主张、禁止的越界主张与证据缺口；
- 评审为什么应把它识别为可发表增量。

贡献必须来自已核验 SOTA 缺口与真实执行结果/材料，不能先写结论再反向挑引用。`Calibration Receipt` 还登记用户确认来源、Execution ID、当前 Claim ID、Evidence ID，以及设计期预期贡献的 `retain`、`narrow`、`revise` 或 `withdraw` 处置；问题处置与贡献处置不得混写。每个承重主张复用稳定 Claim ID，其证据需求和允许/禁止外推不得超过设计契约的推断上限；政策口号、单篇文章偶然命名和模型记忆不能自动升级为学界通行概念。先运行 `research_design.py validate paper_rewriting_output --write --stage execution` 和 `method_execution.py validate paper_rewriting_output --write --stage execution`，再运行 `problem_orientation_check.py paper_rewriting_output --stage execution --write` 与 `contribution_check.py`，最后执行统一 execution gate。

对话层不得挤掉设计 v4／执行 v3 的研究事实层。涉及主张、反方或实质修订的答复，按相关性恢复
Position—Source—Claim—Evidence—Design—Execution—Case／Scope—Artifact，给出
竞争解释的不同经验预期、负面或跨案例不一致的传播、允许／禁止推断及不能 PASS 的
未解决状态；字段名和模板标签本身不算判别证据。

没有工作区的直接来源处置、文献评述、作者回应、反方处理、意义说明，或不改变含义的
表层局部改字，先读取 `dialogic-argument.md`，但不创建完整论文工件。贡献句替换、新证据
入稿、标题／范围变化或最终交付一律进入 `manuscript_revision`。生成前只做
一次承重事实卡：记下用户要的成品，并冻结每个声音的 speaker、result object、
predicate strength、scope 与 epistemic status，以及题面给出的单位、案例／材料、
关键数字或定位、已知关系和未知项。最小充分不是最短，而是决定性交付与必要边界
全部闭合后停止；不得把相邻结果偷换成贡献，不得由“多地材料”补出共同处理，也不得
把候选机制写成已观察事实。

具名节点、Claim、段落或登记项的替换任务另锁定命名交付身份：标题或首个承重句先
处置原 result object；证据、反例或反方若谈另一结果，只能保留为独立身份和未决连接，
不得晋升为被替换对象的新结果。末次核对同时确认下一步材料覆盖原结果、证据结果及
桥接变量，不能因相邻结果更易测量而静默删除用户点名的结果。直接交付以三项并列
收口：命名结果的处置与下一证据、证据结果的独立口径／出处与连续记录、结果桥状态
与待核变量。可用真实名称替代 A／B 标签，但不得合并或省略；B 已有数值也须保存其
样本／单位、指标、时段、数值、来源及后续同口径观测状态。泛称“补数据”或“关系
未决”不算闭合。

草稿后只做一次承重闭合：从末句、意义句和当前结论反向核对事实卡，修复结果重命名、
静默变强／变弱、声音混同、前后矛盾及受新证据影响的残留旧含义。直接答复按题目
条件触发附加动作：活反方能生成同一结果并改变结论时才判别；题目询问意义、受众或
行动时才写读者后果；发生统计比较或推断时才核对实际比较、不确定性和检验归属；
直接引语、归属／语境争议或可直接引注文本才显示已有稳定定位。直接任务不强制两个
读者通道或反方四项，不补造缺失统计量和页码。先交付用户要的可替换文本，不向正文
播报内部工件名；正文优先按“对象／行动—材料或证据—实质判断—必要边界”推进，暂时删去作者动作句后仍须能够复述对象、证据和判断。完整论文仍维护下述对话图，但反方处置只须从论证链恢复，不要求逐格写成答辩段；没有满足同一结果、同一阶段、来源支持、改变 Claim 且有判别证据的反方时，正文反方为 0 合法。

完整论文的贡献校准仍须按 `dialogic-argument.md` 建立 provisional `dialogic_argument_map.md`，先用 Dialogue Contract 的最终立场、回应模式、主控对话、贡献 Claim IDs、材料性反方处置、准确 reader update、遗漏声音和禁止解读约束贡献；一致后才确认贡献，并在 build 前转为最终图。Position–Response Map 把每个文献立场连接 Source—Claim—Evidence—Execution 身份链；Section Voice Map 至少覆盖摘要、引言、核心分析／结果和结论；Substantive Revision Delta 登记新发现引起的来源复核、主张修订、全部受影响位置与派生工件的传播和意外含义修复。`dialogic_argument_check.py` 只裁决身份、字段、跨工件一致性与未解决状态，不裁决文气或说服力。

Substantive Revision Delta 的可读日志另须保存修改编号、层级、旧值、新值、依据、受影响
身份与稿内／生成物位置、重跑检查、未解决项、失效范围和状态。错误材料可以有理由地
排除，但原 Evidence／Artifact 身份、出处、排除理由和完整结果清单必须保留。

**新建完整论文或实际重开 execution 的修订，没有通过执行记录、结果验证、贡献校准和对话图，不得产蓝图、理据矩阵、改写或正文。** `manuscript_revision` 若合同判定只从 build 重开，则复用封存的上游身份：surface 以基线—工作稿哈希差异为最低完成证据，argument 另须留下现有证据重组轨迹；这不会减免 audit/output 的完整适用审计或文献积累基线。

## 阶段 5：build — 规划、写作与文笔重建

### 5.1 成稿前工件

`full_paper`／`manuscript_revision` 先按 `engine/manuscript-compiler.md` 显式执行
`manuscript init` 并审核 `avereth-manuscript-contract/v1`，首次以
`manuscript render --baseline` 启用。baseline 会先把既有非生成规划视图及 SHA-256
归档；不得静默覆盖。之后 `section_blueprints.md`、`writing_rationale_matrix.md`、
promise/lifecycle/reader-state/cross-section 报告和 trace manifest 都由 MIR 生成，禁止手填。
authority／contract 变化必须重建完整 stale Move closure，并用 `manuscript prove-rebuild`
逐 Move 绑定当前 packet／draft／section output；只改变规范稿 SHA 不能视为重建。

两类工作流共同先建立：

- `dialogic_argument_map.md`
- `evidence_bank.md`（含 `## Page Evidence`）
- `section_blueprints.md`
- `writing_rationale_matrix.md`
- `promise_delivery_matrix.md`、`claim_lifecycle_matrix.md`、`reader_state_report.md`、
  `cross_section_sync_report.md`、`manuscript_trace_manifest.json`

再按 workflow 补齐：

- `build_from_materials`：`source_inventory.md`、`figure_asset_map.md`、`claim_register.md`；`figure_asset_map.md` 同时登记所有表格与图片的论证功能、目标刊功能同构范文、来源/口径、是否新增或删除、最终格式和真实渲染检查结果；
- `rewrite_existing`：`original_logic_map.md`、`rewrite_matrix.md`、`logic_transfer_audit.md`；
- 动机/贡献线程模型与 surface map 只在深度修订路径明确要求时生成，不是通用 build 硬门。

理据矩阵由全局合同与 MIR 逐行投影 `confirmed_contribution.md`、`research_design.json` 的 Claim/Design 身份、登记文献与 authority anchor；每个 Move 注明它回答哪项未知、执行何种功能、使用什么权威以及受何推断上限约束。需要改变内容时编辑合同或上游权威并重新 render，不直接改派生矩阵。

### 5.2 写作

按蓝图、矩阵与 `dialogic_argument_map.md` 逐段成稿；所有事实、数字、引语和页码都有 evidence/citation 追踪。每个正文单元先经 Materiality Compiler 形成瞬时 `avereth-prose-packet/v2`，只带研究对象、`reader_question`、`plain_core`、注册 Claim 的规范命题与受保护语义原子（主体／对象、关系、方向／极性、推断强度、范围、数字、引文、citation/locator）、有序 `explanation_path`、逐项绑定 ID 和 `evidence_function` 的最小证据内容、warrant、已激活边界／反方与具体 reader update；完整 evidence bank、状态、失败项、评审意见和回复信语言都不得越过防火墙。规范命题默认只要求语义保真，句法、语序、用词和修辞可重写；只有直接引语、法条、正式假设、量表条目、登记定义或用户锁定文本要求逐字。

正文内部链统一为 `ProsePacket → Writer → deterministic protected-atom gate → Clarity Editor → Explanation/Leakage Gate → Semantic Fidelity Gate → Clean-read Audit`；它们都是 build/audit 内动作，不新增阶段、stage receipt、质量分或完成权威。新 build request 的普通 Claim 显式使用 `realization_mode=semantic`，省略只进入 `legacy_exact` 兼容锁定。Writer 默认按“对象／现象—直接判断—机制／过程—证据锚定及其论证作用—认识增量—必要边界”回答读者问题。边界只用 `calibrated_verb`、`positive_scope`、`single_full_statement`、`footnote_or_cross_reference` 或 `omit`，同一 Boundary ID 只在一个承重位置完整出现。来源声音、必要短引文和作者推断必须可区分。最强反方及让步边界必须真实改变主张、证据解释或适用范围，但无需在正文中逐项陈列；后台审计不得转录成作者答辩。语义复核先由 `semantic-dispatch` 固化 packet／draft、canonical prompt 与 writer／clarity context，再由第三个隔离 context 输出 `avereth-semantic-fidelity-review/v1` 原始 JSON；`semantic-assure` 绑定 manifest、prompt、raw output、限定输入域和独立 context，`semantic-fidelity` 同时验证 provenance、canonical→draft、draft→canonical 及主体／关系、方向／极性、推断强度、范围、证据作用和边界，之后才能进入 Clean-read Audit。所有记录都不取得阶段完成权。

Clarity Editor（兼容名 `avereth_compressor`）的五个动作、`avereth-clarity-edit-ledger/v1` 字段合同与前后稿直接比较规则以 `academic-prose.md` §1.2 和 `avereth_compressor` agent 合同为正本。节级 5%、段级 15% 的再读软诊断可在 packet request 或 `revision_contract.expression_budget.clarity_growth_soft_limits` 中配置 `section_ratio`／`paragraph_ratio`；无合法 `BRIDGE|DEFINE` 锚点的增长硬失败。整篇改稿若使用 `DEFINE`，`revision_contract.expression_budget.registered_terms` 必须是精确术语数组，`clarity_actions[].source_anchor` 必须命中；审稿或回复语言不能自造术语锚。审稿 Finding 若建议新增表达，只允许 `TEXT_EDIT + ADD + Owner Stage: build` 并在 Recommended Action 明示 `BRIDGE`／`DEFINE`；编译器将其路由为 argument 变更，但它仍须在实施后通过实际 expression budget、ledger 和前后稿直接比较，不能用审稿建议自证新增合法。初稿出现贡献先道歉、段首让步、预防误解、限定堆积或隐性“质疑—让步—回复—限定”时，读取 `anti-defensive-writing.md`，先分类真实负结果、概念对比、范围、作者防守与流程泄漏，再整段重建；不按否定词词频删除真实结果或必要边界。可按 `dialogic-argument.md` 少量化用中文短句框架，但不设句式配额、关键词门或英语表面形式检查，模板不能替代证据。核心术语只使用 `terminology_register.md` 决定采用的形式，通行译名不随意另译，官方／政策词明确其是经验对象还是分析概念，未登记的新词不得在写作中临时出现。中文引文外观遵循配置和目标刊，底层保持对真实条目的可追踪链接，不手打不可核对的编号。

### 5.3 结构先行的中文学术文笔重建

完整正文形成后、格式与 AIGC 风险调整前，先在 `academic_prose_audit.md` 建立三行 Title Revision Chain：`question_commitment` 必须等于 `confirmed_motivation.md` 的工作标题，`post_execution` 必须等于 `confirmed_contribution.md` 的证据校准标题，`final` 必须等于真实稿件标题；每行登记 Problem/Claim/Evidence IDs、范围、变更类型、依据、读者复原和状态。然后完整读取 `academic-prose.md` 与 `anti-defensive-writing.md`，执行“前置审查 + 五遍”的外至内改稿序列。期刊规定的引言、理论/文献、方法、结果、讨论和图表仍完整保留；Narrative Wrap 只在信息层之上建立读者理解路径：

0. 标题回环、外架构与论证盲点：先核对标题是否让独立读者恢复问题、证据允许的回答与范围。build/audit 只可登记 `none` 或不改变问题、主张、范围的 `surface` 调整；若需要新增机制、结果、概念、案例或时间范围，停止润色并回到 research/design/execution。再只浏览标题、摘要、引言末、各章首尾和结论，锁定中心主张、引言结束、结论开始、章节作用与关键术语；提出最强相关抗辩。替代解释只有在解释同一结果、同一阶段并产生可区分预期时才作为竞争解释；解释不同阶段、结果或层次时改标互补、阶段性、条件或边界关系，无独特预期、证据或功能者整合或删除。每项实质边界只在一个承重位置完整说明，其他位置短限定或回指，避免用“无法确认、不能确定、仅能说明”反复播报研究过程。该步未通过，不进入词句和格式润色；
1. 叙事包装、主线与反向提纲：先填背景—张力—核心回答—解释/边界—认识结局五阶段图，写清每阶段的读者问题和交接；再用贡献压缩句核对全文主线，标明理论、构念、情境和行动者的功能，移动、合并、拆分或删除无功能论证单元；
2. 承重段落与逻辑链：逐项核对对象／行动、主张、证据、担保/分析和边界/含义，补出被省略的中间前提；让具体材料先“展示”，再明确“解释”，并在行动主体影响解释时写清谁在何种约束下做了什么、影响了谁。逐段暂时删除只说明“本文／本研究做什么或不做什么”的句子；对剩余防御单元执行信息贡献测试与假想批评者测试，分类为可删除免责声明、必要范围、真实方法限制、证据性限定、有用对比或必要责任，分别做直接主张、正面范围、精确限定、集中安置或 `KEEP-WITH-MATERIAL-ANCHOR`。最后一种必须绑定稳定 `B-*`、注册材料锚点、Claim ID、实质 Claim Delta 与唯一完整位置。若删除后无法复述对象发生了什么、证据显示什么和当前判断，说明应迁移承重信息并重建段落，而不是增加作者解释；
3. 句子信息流、术语、凝练度与异常措辞：先对照 `terminology_register.md` 抽查摘要、引言、主体承重段和结论的旧信息、主谓动作、句末新重点、通行译名、中文学科谱系与术语一致性；用删减测试压缩不承担论证功能的词、句、段，但保留事实、数字、反证和边界；行动者重要时优先主动语态，研究选择需要负责且目标刊允许时可用“我/我们”，均不设比例。再对标题、摘要、正文、小标题、图表文字、资料来源/注释和作者自写脚注做全文扫描，清理空间层级隐喻、分析脚手架、审计/工程语域和未经登记的压缩标签，引用原文与文献题名只标记不擅改。普通正文不因修订过程新增粗体，除非目标刊模板、标题层级、学科规范或用户明确要求；
4. 主张力度校准：把强主张逐项映射到 evidence/design 与推断上限，区分因果、相关、机制、描述和初步证据；
5. （仅 `prose_mode=distinguished`）增强遍：建立不可损失清单，依次做洞见提炼、思想压缩、文气与声音调整；不能由证据支持的洞见返回上游，不得靠修辞补造。

终遍由未参与成稿的隔离读者只看最终正文，先对每个承重单元回答四问：发生了什么，为什么发生，证据如何支持解释，改变什么认识。然后仅凭标题复述问题、回答和范围，再按“研究对象与具体问题—实质答案—最强证据—推断边界”的次序复述，随后才复原作者相对前人的定位、五阶段认知路径、读者所得和首次回读／受阻位置。读者还须逐个承重单元指出最早出现的实质判断，并定位首次出现“知道作者拒绝什么，却仍不知道对象发生了什么或证据说明什么”的位置；贡献、主题句或结论若先以 caveat、自我削弱或作者谈判延迟判断，须给出稿内位置。Clean-read 还要判断最终稿是否泄露评论顺序、隐性“质疑—让步—回复—限定”链、重复 Boundary ID 或后插补丁接缝；读者应理解论证，但无法反推意见到来的顺序。不能用作者预期答案帮助其复述。再对叙事连续性、语言凝练度、读者可读性、行动主体可见性、展示—解释平衡给出带稿内位置的定性反馈。全部结果写入唯一工件 `academic_prose_audit.md`：所有模式必含 Title Revision Chain、外架构与章节角色、强抗辩与解释角色、边界安置、Narrative Wrap、对话与声音审计、实质性修改差异和定性表达评价表；distinguished 再附增强登记表、忠实性清单、五维判决三张表。然后运行：

```powershell
& $Python -X utf8 <cnki-paper-skill-dir>/scripts/dialogic_argument_check.py paper_rewriting_output --markdown --write
& $Python -X utf8 <cnki-paper-skill-dir>/scripts/academic_prose_check.py paper_rewriting_output --markdown
```

build gate 不接受空模板、全篇同一套段落公式、未解决状态、缺失五阶段或作者自测冒充独立读者；定性五维任一仍为 WEAK/NEEDS REVISION 必须改稿。distinguished 还要求增强登记表至少 3 行实质动作、忠实性六类损失为 0、五维判决无退步且至少 4 维达标或提升。句长、主动语态、第一人称、连接词和套话只产生上下文复核项，不作为机械质量分数。

稿件含图表时，build 还必须按 `top-journal-anatomy.md` §3.5 逐张完成“分析问题—范文功能对照—信息结构—来源/边界—渲染结果”复核。表格须让未读正文的同行仅凭表题、列名、行值与表注说清比较对象、材料／指标和关系，不得保留“裁决、判定、相合程度、核验状态、来源获取失败”等内部工作语；连续否定值优先改为正面范围或材料状态，科学上承重的缺失值则保留并定义基准。任何“未出现／为零”若被用于推出“不能／必须／足以”，必须另有比较、担保与相邻解释处置。新增图形必须使机制、时序、分支或层级关系比文字/表格明显更易读，不为装饰而加图。

## 阶段 6：audit — 审计、三方评审与 Finding 生命周期

1. 先在 `terminology_register.md` 补齐 Manuscript Use Audit：每个采用术语登记首次使用位置、登记形式、定义/边界、未登记变体和最终状态；逐项核对标题、摘要、标题层级、图表、变量/编码名称与结论。正文仍有未解决变体、自创术语未获确认、随意另译或无法定位中文学科谱系时，返回 design/execution/build。
2. 先运行 acquisition validator，核对 acquisition schema、条件式开放网络可信度、生成的 source/citation 视图、Evidence ID、Claim ID、页码与稿内引用身份链；再运行 `dialogic_argument_check.py ... --write` 和 `academic_prose_check.py paper_rewriting_output --require-manuscript --markdown --write`。若工作区同时有可编辑主稿和生成后的 TeX，显式传 `--manuscript <可编辑主稿>`，不得让陈旧生成物遮蔽最终正文。引用完整性门禁默认审实际交付的主 Word 文件，并同时读取导出的 `references.bib`；只有 TeX／Markdown 确为引用身份的权威源时，才在配置中显式写 `citation_audit_manuscript`，路径无效时不得静默回退。对话 checker 只硬检身份、字段、状态、跨工件一致性和修订传播；prose checker 硬检 Title Revision Chain、稿题一致、Narrative Wrap、对话／声音、实质修改、扩展读者复述和五项定性反馈，不给标题或文笔打机械分。final 发生实质改题时必须回到拥有变化事实的 research/design/execution；只有明确不改变问题、主张与范围的 surface 调整可留在 build/audit。distinguished 缺少增强登记表、忠实性清单或五维判决（无退步、至少 4 维达标/提升）时直接失败。随后复跑 `topic_reasoning_check.py` 与 `research_design.py validate paper_rewriting_output --write --stage audit`，再运行本地 artifact、citation quality、citation integrity、integrity、section economy、LaTeX/Word 等适用检查。`citation_integrity_audit.py` 必须读取实际定稿而非候选池：双向核对稿内引用与文后条目，阻断 `candidate-only`／`not-for-citation` 的实际使用以及 DOI 指向另一作品、题名／作者明显不符；投稿或公开发布的可疑条目须用不同索引或不同查询路径完成第二遍核验。网络不可达、Crossref/OpenAlex 未收录或中文来源无 DOI 只记 `NOT CHECKED`／待作者核验，并回 CNKI、出版社、机构、ISBN、档案或本地全文链处理，不能直接判虚构。文笔审计未覆盖真实正文、独立读者复述失真、标题与问题／贡献／稿件漂移、对话图与动机／贡献／身份链漂移、选题推理链失真或设计契约与执行、贡献、结果、正文漂移时，回到 research/design/execution/build 的所属阶段修复。
3. 用 `avereth_core/tools/structured_review.py --dispatch` 冻结规范稿 path/SHA、`review_run_id` 和三份 prompt；再把三份 prompt 分别交给 Methods、Contribution、Clarity，原样保存三份 `*_review_output.md`。validate 的对象是输出文件，不是 prompt。每份输出必须使用严格 v2：精确五列表 `Dimension ID | Applicability | Score | Reason | Manuscript Location`，`Applicability=APPLICABLE|NOT_APPLICABLE|BLOCKED`，一行 `Review Verdict: PASS|FINDINGS`；每条 Finding 使用稳定 role-local ID，并给 Severity、Confidence、Category、稿件位置与引文片段、问题、读者后果、真实 Repair Kind、Owner Stage、Text Action、建议和净字数变化。PASS 可以零 Finding；不得为数量制造异议。Overall Score 只作诊断，不能抵消 Critical/Major。
4. 三位 reviewer 都只报告可观察的稿件位置和问题，不得看见、猜测或生成内部 Claim/Evidence/Design/Execution ID；mapper 在编译时读取内部支持工件补齐 `exact|inferred|unresolved|not_applicable` 映射。Contribution 只额外看到经过清洗的确认语义，继续检查 Gap Diagnosis—当前 `SYN-*`—研究问题—执行结果—实际贡献是否同一；Clarity 对最终稿作 clean read，不读 `academic_prose_audit.md`、`dialogic_argument_map.md`、确认合同或审稿／回复工件。它在承重单元恢复发生什么、为什么、证据如何支持和改变什么认识，并检查 substantive explanation、positive formulation 与 revision cleanliness；真实负结果、有用概念对比和法律伦理限制不因否定形式被删除，评论顺序、隐性答辩链和补丁接缝则须定位。中文顶刊任务可由 `splice_anatomy_rubric.py` 注入 §4 的 0/1/2 补充诊断；它不替代严格五列表，不另建平均分 gate，也不得手工改 prompt 冒充脚本产物。
5. 写 `review_assurance.json` 时，新 run 只接受 `cnki-review-assurance/v2`：绑定同一 review run 与稿件 path/SHA，并逐角色登记真实 context ID、prompt/output path 与 SHA、input scope、隔离声明。只有三个 context、三条输出路径和三个输出 SHA 都各不相同时可写 `mode=independent` 且逐项 `isolation_declared=true`；否则写 `single_agent` 且逐项 `isolation_declared=false`。文本相似只报告 `textual_diversity_score`，不作为独立性证明。旧 `cnki-review-assurance/v1` 只读显示 `legacy_read_only_needs_review`，不能推断 Severity、VERIFIED、稿件身份或独立性，也不能签新 audit receipt。
6. 按 `engine/reviewer-audit.md` 运行 `review_lifecycle.py ... compile --write`：三份原始输出保持不可修改，编译器写 `review_findings.json`（`avereth-review-findings/v3`）和缺失时的 OPEN `review_resolution.json` scaffold（`avereth-review-resolution/v2`）。三份来源 verdict 全为 PASS 时，零意见合法并生成 `NO_MATERIAL_OBJECTIONS`；任一来源不是 PASS 时不得用空表通过。`structured_review.md`、`reviewer_audit.md` 和 `revision_plan.md` 全部从两个 JSON 生成，`reviewer_audit.md` 的第三部分统一命名为 **Editorial Fit Assessment**；三份 Markdown 禁止手填。
7. 只在 `review_resolution.json` 中裁决和核销 Finding。实际改稿先进入 `revision_contract` v2 隔离 batch；每个 change 明确绑定全合同唯一 RFK，batch 的 `target_finding_keys` 必须与所选 change 覆盖精确一致，再以 `revision_impact.json` 的真实 content-unit diff preflight 后单次原子 promotion。随后按影响最小派发 reviewer 并追加 `review_cycles[]`：DELTA 只给 changed units，FULL 三审给完整规范稿、changed units、角色职责与 rubric。每轮绑定 before/after SHA、changed units、role input digest、输出 SHA 和 PASS/FINDINGS/BLOCKED，失败轮不得覆盖。role digest 不含整篇 after SHA 身份字段，只含 Reviewer 实际看到的 role impact、文本／依赖／确认语义投影与 reviewer 实现摘要；未进入 prompt 的 authority 行不触发误重跑，投影语义变化必须失效。稳定 `finding_key` 使相同问题重开而非换措辞新建；`OPTIONAL_POLISH` 进入非阻塞 backlog；第二次重开先完成结构化根因诊断。Severity 变化须有裁决身份、context 和理由；Critical 不得普通 WAIVED。VERIFIED 继续要求真实修改、科学工件、传播检查和独立 verifier。旧 findings v2/resolution v1 只读，显式迁移不得把 legacy `post_revision_review` 猜成新 cycle。
8. `revision_plan.md` 只是只读路由：复用既有 `revision_contract.route_for_change_classes` 并与 Owner Stage 合成 `effective_earliest_reopen_stage`，绝不自动改上游。`full_paper` 报告应重开的既有阶段；`manuscript_audit` 只请求扩展修订权限；`manuscript_revision` 必须由显式授权且逐 Finding 覆盖的 `revision_contract.json` amendment 才可执行。取得授权后仍由 controller 回到最早事实所有阶段，不在 audit 内补写来源、重做设计或重跑分析。执行正文修订前，把审稿原文、Comment ID、处置理由和意见顺序限定在 Response View；Writer-safe View 只保留已授权的 Claim/Evidence/Structure Delta。先归并这三类 Delta，必要时更新所有权威，再重画受影响 section blueprint 并整节重写；不把意见顺序或逐条回复当作正文提纲。两种 View 只是临时编译投影，不新增权威。
9. 运行 `page-evidence` 严格审计；A/B 级可核销。C 级仅进入阻塞性核验报告，不进入终稿或稿末清单；补成 A/B 级，或删除、改写对应页码式主张后才能通过。
10. 执行统一控制器 `gate ... --stage audit`。唯一 action graph 固定为 deterministic preflight → 原始评审严格校验 → Finding 编译／resolution scaffold → 生命周期校验并重建 JSON 派生视图 → reviewer audit 检查；随后才签内容摘要和规范稿 SHA 绑定的 audit receipt。缺少 resolution 时可以生成 OPEN scaffold 和视图，但 audit 必须 fail closed。任一 raw output、assurance、registry、resolution、规范稿或派生视图漂移都失败。

评审纪律是“价值优先、证据约束”：否定意见必须给可执行抬档路径；严谨不等于把已有真实发现改写成自我证伪，也不允许为了保住贡献隐瞒不支持结果。编辑综合另用六种思维检查主要矛盾、历史条件、系统整体、战略目标、最坏风险和有据创新，尤其防止局部文字、指标或方法表现掩盖整体失配；未改变评审决定的维度无需逐项凑数。同时执行**两分法止战**（`three-questions-standard.md` §8）：不得以方法标签（定量/定性、个案/大样本、归纳/演绎、描述/因果）压分或毙稿，质疑设计只问三点——研究问题是否由真实未知推出、设计是否制造了回答该主张所需的变异/反事实/过程证据、推断是否越过设计上限；“解释一切”式声称（R² 近 100%、无失效条件的主张）按越限处理，对已知结论的单纯复证按零增量处理。

## 阶段 7：output — 候选渲染、真实视觉复核与事务发布

output 只消费当前 PASS audit receipt 绑定的精确规范稿路径与 SHA，不重猜稿件、不重跑 audit、不在渲染时修改学术内容。配置明确决定 Word/PDF、语言与可选翻译／投稿／正式回复包；缺渲染器、缺包源、缺合同或缺真实 QA 时返回 BLOCKED，不能把已有文件或手工转换冒充完成。所有交付先写到 `.avereth-output-candidate/`，守卫和视觉复核通过后才整批发布；中途失败须恢复旧交付与旧凭证。

### 第一次 gate：只生成候选并停在 QA 门

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$Out = (Resolve-Path 'paper_rewriting_output').Path

$FirstOutput = & $Python -X utf8 $Controller gate $Out --stage output 2>&1
$FirstExit = $LASTEXITCODE
$FirstOutput | Out-Host
if ($FirstExit -ne 2 -or -not (($FirstOutput -join "`n") -match 'OUTPUT\.QA_REQUIRED')) {
    throw "Expected exit 2 with OUTPUT.QA_REQUIRED; got exit $FirstExit."
}

$CandidateRoot = Join-Path $Out '.avereth-output-candidate'
$CandidatePath = Join-Path $CandidateRoot 'candidate_manifest.json'
if (-not (Test-Path -LiteralPath $CandidatePath -PathType Leaf)) {
    throw 'candidate_manifest.json is missing.'
}
$Candidate = Get-Content -LiteralPath $CandidatePath -Raw | ConvertFrom-Json
$Records = @($Candidate.deliveries) + @($Candidate.qa_artifacts)
$TargetRecords = @($Records | Where-Object { [string]$_.path -match '(?i)\.pdf$' })
$Targets = @($TargetRecords | ForEach-Object {
    Join-Path $CandidateRoot (([string]$_.path).Replace('/', '\'))
})
if ($Targets.Count -eq 0) { throw 'No rendered PDF review targets were declared.' }
$Targets | ForEach-Object {
    if (-not (Test-Path -LiteralPath $_ -PathType Leaf)) { throw "Missing review target: $_" }
    Start-Process -FilePath $_
}
```

**停在这里。逐个打开上面列出的每个 PDF，逐页检查正文、分页、表图、脚注／引文、字体、截断、空白页与黑白可读性。命令只负责打开文件，不代表已经看过。没有真实逐页复核，不得执行下一段。**

### 记录真实 QA，再复跑同一 gate

```powershell
$ReviewedList = ($TargetRecords | ForEach-Object { [string]$_.path }) -join ', '
& $Python -X utf8 $Controller record-render-qa $Out `
    --reviewer-mode single_agent `
    --reviewed-by '<actual thread/context ID>' `
    --notes "Reviewed every page of: $ReviewedList" `
    --confirm-visual-review
if ($LASTEXITCODE -ne 0) { throw 'record-render-qa failed.' }

& $Python -X utf8 $Controller gate $Out --stage output
if ($LASTEXITCODE -ne 0) { throw 'Output publication did not pass.' }

$Receipt = Get-Content -LiteralPath (Join-Path $Out 'output_receipt.json') -Raw | ConvertFrom-Json
$Manifest = Get-Content -LiteralPath (Join-Path $Out 'final_artifact_manifest.json') -Raw | ConvertFrom-Json
if ($Receipt.status -ne 'PASS' -or $Manifest.status -ne 'PASS') {
    throw 'Durable output receipt/manifest is not PASS.'
}
& $Python -X utf8 $Controller status $Out --json
```

本人亲自查看用 `human`；同一主线程代理实际查看用 `single_agent`，并在 `--reviewed-by` 写真实 thread/context ID；只有真实隔离上下文才用 `independent`。任何规范稿、配置、audit receipt、候选内容或 target 变化都会使 QA stale，必须重新生成并逐页查看。不得编辑候选、手工复制到 final、直接运行守卫写 durable root，或把文件存在当作视觉复核。

翻译、投稿与正式回复不新增状态：它们是同一 output 事务的可选子动作。翻译要求独立中文源与 `avereth-translation-coverage/v1`；投稿要求目标刊确认的 `avereth-submission-contract/v1` 与 exact 文件清单；正式回复仅用于 `manuscript_revision`，要求 reviewer source、稳定 Comment ID 和 `review_comment_confirmation.json`，并只能从已通过 audit 的最终稿与绑定修订前稿之间的真实 diff 生成回复矩阵、信与变更记录；回复信、评论原文和逐条回复不得反向生成或修补正文。三类包的源稿放在配置登记的 source 路径，最终包、守卫报告、预览与哈希一起进入 `final_artifact_manifest.json` 和 `output_receipt.json`。具体合同见 `engine/translate.md`、`engine/submission.md` 与 `engine/respond.md`。

Word/PDF 批注必须回写唯一可编辑源稿，重建全部交付格式，复核批注页及受重排影响的下游页，再刷新 audit/output receipt；禁止直接修补旧 PDF。复杂引用样式服从目标刊模板、CSL 或 BibTeX，不用手写方括号替代真实 citation link。`page_evidence_audit.md` 的 VERIFY 清单必须为空，最终正文不得残留内部核验标记；否则只交付阻塞性审阅包，不进入 output。

## 页码证据速查

- 期刊引文：用 `page-evidence` 的本地 PDF 定位脚本核对，形成 B 级证据。
- 原典专著：优先页面影像和规范定位符，形成 A 级证据。
- 仅有知网三角旁证：C 级，只能留在工作稿和阻塞性核验报告；终稿前补成 A/B 级，或删除、改写页码式主张。
- 书目页码范围不等于具体引文页码证据。

# Rhetorical architecture routing note

Use [`rhetorical-architecture.md`](rhetorical-architecture.md) only within the existing research and build stages: Problem Arc is an optional `literature_analysis.json` projection; Thought Moves, hooks, scenes/returns, and title fulfillment are AMC/MIR build projections; Context Anchors remain in the evidence bank and selected ProsePacket. No item advances a stage without the ordinary controller gate, and legacy artifacts without the optional fields remain compatible.

## 可选的发现活动

现象驱动入口、材料暴露顺序和 `research_notes.md` 的范围见
`problem-led-research.md` 的“可选的现象驱动发现与研究笔记”。一项候选足以继续时，
可在既有 `exploration.narrow_direction_exemption` 中填写 `actual_alternatives` 与
`stopping_reason`，说明实际考虑过什么和为何停止；旧完整格式仍可读取。已尝试家族和来源
仍由现有探索记录拥有。设计封存前，将有来源的知识基线记入 `knowledge_baseline`；
执行后再记录 `knowledge_update`，具体字段和历史处理见 `taste-judgement.md`。
