# Contribution-First（贡献优先）

本文件是本地执行与审计契约的基石。一篇论文被接受或退回，取决于它的**贡献**——它给领域添加的那一件可辩护的东西——而不是文字有多流畅。动机说明*读者为何该在意*；设计写下若证据支持则可能成立的预期贡献；确认贡献写下*执行实际交付了什么、愿意接受何种评判*。三者不可互换。

本文件同时是全套件**贡献判准的唯一主轴**：`top-journal-anatomy.md` §3.3 的五阶贡献阶梯。`dialogic-argument.md` 的回应对象与回应模式、`research-gap-diagnosis.md` 的缺口落点、`three-questions-standard.md` 的增量判准，都作为该阶梯的投影在 §"统一映射表" 中对齐；不再另设一套与之并列的贡献分类。

## The Contribution-First Hard Rule（贡献优先硬规则）

Reader Prior 应对应最近邻支持的具体认识，Reader Posterior 对应实际执行后允许的更新。
选题期 `assumption_challenge` 中的旧／替代预期、不变条件与修订条件只是待检验责任；
校准时回到真实结果决定 retain、narrow、revise 或 withdraw。`novelty_delta_view.md` 只帮助核对
两者的关系，不向 `confirmed_contribution.md` 或 Writer 授予新事实。

> **没有已执行的证据、没有经校准的 `confirmed_contribution.md`，就没有实质写作。**

具体地：

- `paper_rewriting_output/confirmed_contribution.md` 必须在相关证据／分析已执行之后撰写，包含 Calibration Receipt，并在分节起草、蓝图或改写开始**之前**通过 `contribution_check.py`。
- `confirmed_motivation.md` 回答"这个问题为什么重要"；`confirmed_contribution.md` 回答"*本文*确立了什么此前不存在的东西，以及我们能主张到多强"。只有动机没有贡献是文献综述；只有贡献没有动机是没人问过的结果。两者都要，且贡献统领。
- 之后的每个工件（分节蓝图、写作理由矩阵、稿件本身）都必须回溯到这里唯一的 Core 贡献陈述。一个段落若不推进、支持或限定该陈述，就不属于本文。
- 陈述回应增量时，保留已确认的结果对象、单位、案例／材料事实和已知关系。不得用相邻构念替换既定结果、假定跨案例共享同一处理、或把候选机制叙述成观察事实来制造新颖性。
- 若只需一句不创建或修改工作流的本地贡献句，走 `cnki-paper` 直接答复协议：生成前建一张短的承重事实卡，冻结每个声音的说话者、结果对象、谓词强度、范围和认识状态；生成后对最终句、意义句和边界句做一次闭合。"最小充分"指每项决定性义务都已关闭，不是最短措辞。只有题面确实触发时才激活反方、读者收益、统计与定位检查；默认不要求两条收益通道或四项反方处置。
- 完整工作流经 `cnki-paper` 路由时，在校准本贡献的同时创建 provisional `dialogic_argument_map.md`。用最终立场、已激活承重反方的接受／拒绝／未决部分与当前可用的有界结论、结果实际支持的具体读者更新和禁止解读，反过来修订贡献，直到通过。当没有任何已登记替代解释能在同一分析阶段生成同一结果并改变主张时，正文反方数为零是合法的。不制造第二条收益通道：一次精确地改变读者的默认、决策或研究动作，强于两条泛化的意义。随后再冻结 Position—Source—Claim—Evidence—Execution 身份、稿件声音和每个受影响修订位置，进入 build。对话图是约束贡献校准的论证契约，不是第二份来源、设计或执行真相表。

WHY 这是硬门：生成稿最常见的失败，是流畅地改善每一句，却始终不承诺一个审稿人能接受或拒绝的主张。设计期的预期可以引导执行，但只有观察到的证据能校准最终承诺。在写正文之前锁定这个证据约束下的贡献，论文才对唯一可检验的主张负责。

---

## 统一映射表：五阶贡献阶梯是唯一主轴

### 为什么只留一条主轴

此前套件里四套分类并存且互不映射：本文件旧版的 CS 口径七类（new method / dataset / system / benchmark……）、anatomy §3.3 的五阶贡献阶梯、`dialogic-argument.md` 的三类回应对象与六种回应模式、`research-gap-diagnosis.md` 的六个缺口落点。四套并存的后果是：动机文件说的 gap、贡献文件填的类型、对话图登记的回应模式各说各话，审计只能逐表对字段，却查不出"这三处说的是不是同一件事"。

自本版起：

1. **五阶贡献阶梯是唯一主轴**（旧理论新场景 → 新条件／范围 → 新机制 → 新概念／类型学 → 反转既有结论）。`Contribution type` 只填阶梯序号与名称（非实证研究填对应形态，见下表末列）。
2. 回应对象、回应模式、缺口落点与阻断原因是阶梯的**投影**，不是并列分类。它们在各自工件里继续登记，但审计时按下表核对是否与所选阶一致。
3. 每一阶预设了**必须交付的证据类型**与**推断强度上限**。阶选高了而证据只够低阶，处置只有一种：收窄到证据支持的那一阶（这是 `three-questions-standard.md` §9 意义上的升档，不是降级）。
4. CS 口径的 new method / dataset / system / benchmark 分类**不再作为贡献类型**；仅当 `task_genre` 为技术报告时按文末附注使用。

### 映射表

| 阶 | 贡献形态（anatomy §3.3） | 回应对象（dialogic §3） | 回应模式（dialogic §5） | 缺口主落点 · 典型阻断（gap-diagnosis §2–3） | 必须交付的证据 | 推断强度上限（措辞层级见 dialogic §4） | 非实证研究对应形态 |
|---|---|---|---|---|---|---|---|
| 1 | **旧理论新场景**：成熟框架搬到未验证语境 | `common-assumption`（默认框架可平移）或 `literature-omission`（该场景未被覆盖） | `agree` / `extend` | `scope-population` · `misaligned-or-condition-changed` 或 `biased-coverage` | ①场景特殊性论证——该场景的哪一项条件可能改变原结论；②与原场景可比的观察（同一结果对象、可比测量）；③对"一致／不一致"的明确判定 | "在该场景中与 X 一致／不一致"；不得推"X 普遍成立""X 已获本土验证" | **新诠释**：把既有解释框架用于新文本、事件或制度，须论证该对象为何要求这一读法 |
| 2 | **新条件／范围**：既有机制在何种条件下成立或失效 | `explicit-dispute`（结果冲突可由条件解释）或 `common-assumption`（默认无条件成立） | `agree-and-qualify` | `theory-explanation`（范围条件）或 `scope-population` · `inconsistent-or-incomparable` | ①条件已测量；②条件两侧都有观察（含反面观察）；③跨条件比较显示结果差异；④选样、测量差异等替代解释已排除 | "在 C 条件下成立、非 C 条件下减弱或消失"；缺条件两侧观察时只能写"随……而异" | **论证重建**：说明某论证或规范结论只在特定前提下成立，并把前提写出来 |
| 3 | **新机制**：同一因果关系中未被识别的中间环节 | `common-assumption`（默认黑箱）或 `literature-omission`（遗漏环节） | `extend` / `reframe` / `synthesize` | `theory-explanation` · `insufficient-or-imprecise` | ①过程证据——时序、中间环节可见、可作箍圈／冒烟枪检验的观察；②竞争机制的不同预期与判别材料；③单案例须交代案例内变异与推断上限（`three-questions-standard.md` §6、§6A） | "支持机制可能存在""在已观察场景中更符合"；单案例不得推频率、平均影响或普遍范围 | **概念史重构**：重建概念或命题经由何种传播、接受、转译环节演变 |
| 4 | **新概念／类型学**：命名无名现象或建立有区分度的分类 | `literature-omission`（无名现象）或 `common-assumption`（旧概念已足够） | `reframe` / `synthesize` | `concept-measurement` · `inconsistent-or-incomparable`（旧概念使案例不可比） | ①撞车检索（`terminology-governance.md`）；②内涵、外延、近邻区分；③分析收益——旧概念做不到的解释、区分或测量任务；④类型学维度互斥、穷尽；⑤归类规则可操作 | 概念主张只主张"有区分度且有分析收益"，不自动附带因果主张；命名不等于机制 | **新诠释 / 概念史重构**：提出新读法或重画概念谱系 |
| 5 | **反转既有结论**：推翻被广泛接受的判断 | `explicit-dispute` | `disagree` | `evidence` 或 `theory-explanation` · `biased-coverage` 或 `misaligned-or-condition-changed` | ①压倒性且相互独立的证据；②能解释旧结论为何出现（选样、测量、时期、保存偏倚）；③三角验证；④全部负面结果与反例登记 | 要求最高；只有同时解释旧结论成因才可写"修正"，否则只能写"提出相反证据" | **史实纠正 / 论证重建**：指出既有叙事所据史料或论证前提有误 |

### 怎么用这张表

- **选阶只选一阶**。全文所有部件为它服务；标题、摘要、结论回扣同一阶。列三条不同阶的"小贡献"就是 anatomy §6 反模式 4 的贡献注水。
- **阶决定证据责任，不由方法标签决定**。同一阶在定量、定性、诠释、规范路线下的证据形态不同，但要回答的问题相同：读者凭什么相信这一阶成立？
- **一致性核对**（audit 阶段由 Contribution Reviewer 执行，机器不判）：`confirmed_motivation.md` 的 `Response Target Type` 与 `Gap Diagnosis` 的 `Primary Locus`、`dialogic_argument_map.md` 的 `Response Mode`、本文件的 `Contribution type` 是否落在表中同一行或相邻可解释的组合上。落点是 `action-practice` 的研究不占独立一阶——它的理论贡献仍要归到 1–5 之一，实践贡献另写。
- **增量方向感**（`three-questions-standard.md` §7）：复现的增量取决于材料独立性、精度和适用范围，而非结论是否反转；沿用相同材料重复运行不自动增加证据。翻案同样须满足来源、执行与推断要求。
- **哪一阶最受奖励随刊而变**（anatomy §3.3 注）：这只描述已发表样本，不构成"每篇都要造词"或"必须找机制"的指令。

### 技术报告体裁附注

仅当 `task_genre` 明确为技术报告、系统说明或工具论文时，才可在 `Contribution type` 中额外标注 new method / dataset / system / benchmark / application 之一作为**体裁标签**，且仍须同时填写它对应的阶：新数据集通常是阶 1 或阶 2 的证据基础而非贡献本身；新方法若不改变可见证据或识别能力，只是 `identification-method` 落点的手段。社科稿件不使用该标签。

---

## 伪贡献清单（12 条）

下表针对中文社科（尤其定量）稿件里最常见的"看起来像贡献"的写法。每条给识别信号与"要变成真贡献需补什么"。命中任一条不等于退稿，等于**当前陈述不能作为 Core 贡献**，须按"补什么"列补齐或收窄到证据支持的那一阶。

| # | 伪贡献 | 识别信号（中文稿常见句式） | 要变成真贡献需补什么 | 补齐后落到哪一阶 |
|---|---|---|---|---|
| 1 | 仅换地区／年份／数据 | "以 X 省为例""基于 2019—2023 年面板数据""已有研究多集中于东部，本文以中西部为样本" | 论证该地区／时期的哪一项条件可能改变原结论，并把差异转成可检验的预期；若结果与原结论一致，只能作为阶 1 的一致性证据表述 | 1（论证场景特殊则可到 2） |
| 2 | 仅换案例而不论证场景为何特殊 | "本文选取 X 市作为案例，弥补了既有案例的不足""该案例具有典型性" | 案例选择的方法论理由（典型／极端／关键／偏差案例）；说明该案例相对既有案例改变了哪项理论负载的条件；交代换一个案例结论会不会变 | 1 或 2；机制可见时可到 3 |
| 3 | 仅加一个变量、调节项或中介 | "引入 X 作为调节变量，丰富了……的机制研究""构建有调节的中介模型""检验了 X 在 Y 与 Z 之间的中介作用" | 该变量对应的理论张力：为何既有理论预期它不起作用或方向相反；调节项须有条件两侧的反面观察；中介若要称"机制"，须有时序或过程证据而非仅统计中介检验；否则按 `associational` 报告，措辞停在"与该解释一致" | 2（调节）或 3（中介有过程证据） |
| 4 | 仅换测量或方法复证已知结论 | "本文运用 X 方法重新检验……结论依然稳健""采用更前沿的 Y 模型" | 说明旧测量／方法留下了什么具体偏误或盲点、新方法为何改变可见证据或识别能力（`identification-method` 落点）；若结果不变，贡献只能写成对既有结论的稳健性证据并降级措辞 | 2 或作为证据责任修复，不独立成阶 |
| 5 | "丰富了……研究／为……提供了新视角" | "拓展了……的研究视野""为理解……提供了新的分析视角""具有重要的理论与现实意义" | 写出被改变的具体命题、读者的哪一项默认判断或决策会因此变化（`Who Cares` / `So What`）；写不出即删 | 无落点，须重写 |
| 6 | 命名式建构无机制 | "本文提出'X 型治理'／'Y 式动员'概念""构建了……分析框架" | 撞车检索、内涵外延、近邻概念区分、分析收益（旧概念做不到什么）；命名之后拆出机制或类型学维度；已有概念足以解释时沿用旧名 | 4（无机制、无区分度则退回 1） |
| 7 | 把文献综述当贡献 | "系统梳理了……的研究脉络""对……进行了述评" | 只有登记为 `review` 路线（narrative／scoping／systematic）并产出有界综合判断（`SYN-*`、冲突解释、剩余未知）时，综述本身才是交付物；否则综述是手段，贡献要写综述之后做了什么 | 依综述结论落 2 或 5；嵌入式综述不独立成贡献 |
| 8 | 把描述当解释 | "呈现了……的现状与特征，揭示了……的内在逻辑""描绘了……的演进历程" | 描述可以是合法贡献，但要按 `three-questions-standard.md` §5 定位（知识薄弱领域的探索性描述）并给出清晰概念、分类与比较基准；一旦写"揭示逻辑／解释原因"，就须满足 Gerring 四要件（§4） | 描述性贡献归 1 或 4（新分类）；宣称解释则按 3 审 |
| 9 | 把政策建议当理论贡献 | "为……提供政策参考""对完善……具有借鉴意义" | 实践贡献走 `action-practice` 落点：明确行动主体、目标、约束、知识—行动冲突与证据桥；理论贡献另写并归到 1–5 之一；不得用对策条数替代理论增量 | 不占独立一阶 |
| 10 | 把"首次"当贡献 | "首次将……应用于……""目前尚无研究关注……" | "首次"只是检索观察：先排除术语错配、相邻覆盖、发表时滞与"无人做因为不值得做"（`research-gap-diagnosis.md` §3）；再论证为何值得做、做了之后改变什么 | 排除替代解释后按实际贡献归阶 |
| 11 | 把数据规模当贡献 | "基于 X 万条微观数据""覆盖全国 N 个城市""构建了大规模数据库" | 规模只有在修复具体证据责任（精度、覆盖偏倚、异质性、既有证据区间容纳何种不同答案）时才有意义；写出旧证据为何不足、新证据把区间收窄到什么程度 | `evidence` 落点的证据责任，不独立成阶 |
| 12 | 用限定词堆叠制造"新颖" | "数字化转型背景下基层治理共同体的韧性生成机制""双重压力型体制下……" | 逐个删限定词做删减测试：删掉后命题是否仍新？每个保留的限定词须对应一项已测量的条件或已界定的范围；限定词不是条件就删 | 限定词若是真实条件归 2；否则退回原阶 |

WHY 要点名这些：审稿人对这 12 类的判断几乎是条件反射，而作者最容易在这些地方自我说服。其中第 3 条（仅加变量／调节项／中介）是中文定量稿最高频的伪贡献——统计上的中介或调节效应本身不构成新条件或新机制，只有对应的理论张力、条件两侧的反面观察和过程证据才构成。

---

## The Artifact: `confirmed_contribution.md`

保存于 `paper_rewriting_output/confirmed_contribution.md`。它有**四个贡献区块加一张校准凭证**。每一行都为了逼出一个具体决定；"WHY" 说明这一格含糊或空缺时会出什么问题。不得把单元格留成 `TODO`、`TBD`、`...` 或模板占位——未填的格子意味着这个决定从未真正作出。下面模板中的英文标题与字段名被 `contribution_check.py`、`codex_cnki_gate.py`、`problem_orientation_check.py`、`dialogic_argument_check.py` 与 `academic_prose_check.py` 按文字解析，**原样保留**，内容格可用中文。

```markdown
# Confirmed Contribution

## Core Contribution

| Field | Content |
|---|---|
| Main contribution statement | 全文要捍卫的唯一一句话。一个主张，具体，可证伪。 |
| Contribution type | 五阶之一：1 旧理论新场景 / 2 新条件与范围 / 3 新机制 / 4 新概念与类型学 / 5 反转既有结论；非实证研究写对应形态（新诠释 / 概念史重构 / 论证重建 / 史实纠正）。只选一项。 |
| One-sentence reviewer payoff | 审稿人只记住一件事，就是这句。写成对领域的价值，不写成做了什么活动。 |

## Why This Contribution Is Needed

| Field | Content |
|---|---|
| Field problem | 领域关心的大问题。这个研究领域为何存在。 |
| Specific gap | 本文填补的精确缺口。不是"X 研究不足"，而是点名那个洞；与 `confirmed_motivation.md` 的 Gap Diagnosis 主落点一致。 |
| Concrete challenge | 缺口为何难以关闭（解释它至今仍开着的经验、材料或识别障碍）。 |
| Why prior work leaves it unresolved | 点名最接近的既有研究，逐个说明它为何没有已经解决该缺口。 |

## How This Paper Responds

| Field | Content |
|---|---|
| Design response | 回应缺口的核心思路或机制。"怎么做"，直接对着上面的挑战。 |
| Evidence required | 一位持怀疑态度的审稿人要相信 Core 贡献所需的证据；按所选阶在映射表中的"必须交付的证据"列出，先列再核对手头有什么。 |
| Evidence available | 实际拥有并满足"required"的证据（执行记录、案例过程材料、比较、稳健性、档案互证等）。 |
| Evidence missing | required 与 available 之间的差。非空时 Core 贡献必须收窄或补做；诚实填写这一格是防止越界的关键。 |

## Claim Boundary

| Field | Content |
|---|---|
| Strong claims allowed | 被 Evidence available 完全支撑的主张，按全强度陈述。 |
| Claims to soften or avoid | 证据承载不了的主张。降级（"提示""在本场景中"）或删除。 |
| Novelty risk | 最可能的"这早有人做过"异议（含伪贡献清单命中项），以及你的诚实回答。 |
| Significance risk | 最可能的"所以呢／太窄"异议，以及你的诚实回答。 |

## Calibration Receipt

| Field | Content |
|---|---|
| User confirmation source | 接受校准后贡献的消息、会议记录或确认记录。 |
| Execution IDs | 产生相关结果的 `execution_record.md` 稳定 `EXE-*` 行。 |
| Active Claim IDs | 执行后保留的稳定 `CLM-*` 主张。 |
| Evidence IDs | 支持这些主张的稳定 `EVD-*` 证据单元。 |
| Expected contribution disposition | 对每项设计期预期：`retain`、`narrow`、`revise` 或 `withdraw`，并说明理由。 |
| Gap disposition after execution | `retain`、`refine`、`reclassified` 或 `withdrawn`；主落点、阻断原因、具体命题或 `SYN-*` 基础变化时，回 research 再进 build。 |
| Problem Disposition After Execution | `retain`、`refine`、`reopen` 或 `withdraw`；`reopen`／`withdraw` 阻止 build 并回 research 重新确认问题。 |
| Reader Prior | 从 `research_design.json.knowledge_baseline.judgement` 派生的有来源基线；不确定性本身可作为基线，但须说明哪些判断及证据仍未确定。 |
| Reader Posterior | 从 `method_execution.json.knowledge_update.supported_update` 派生的认识变化。复现、边界收窄、负结果与概念推进均按证据判断；词面变化不证明增量，词面相同也不直接否定增量。 |
| Displaced Source | 被修正或限定的已登记 Source／DOI／URL／SYN 身份；复现等未取代来源的情形可写 none，知识基线的 source_refs 仍须实际解析到来源及材料。 |
| Title Disposition After Execution | `retain`、`narrow`、`revise`、`reopen` 或 `withdraw`。 |
| Evidence-Calibrated Title | 执行后按证据校准的标题；只有已登记证据支持的回答、机制或概念才可入题（`title-design.md` §2）。 |
| Title Revision Basis | 改题依据，须带 EXE / CLM / EVD 身份；方法新颖、期刊偏好或"更吸引人"不是依据。 |
| Title User Decision | 用户对校准标题的确认；`user-fixed` / `locked` 题目须显式解锁。 |
```

WHY 四个区块按这个顺序：贡献只有在**被需要**（区块 2）、**有证据回应**（区块 3）、**被限定而不越界**（区块 4）时才是真的。区块 1 是承诺；2–4 让承诺活过评审。`Evidence missing` 与 `Claim boundary` 是作者最常跳过、审稿人最常惩罚的部分，所以本地契约把它们设为必填。Calibration Receipt 后八行由 `problem_and_contribution_reappraisal` 检查点要求（见 `workflow-playbook.md`），在执行后填写；其中 `Reader Prior / Reader Posterior / Displaced Source` 三行把"超越常识的增量"从自报改成先验—后验对照，机器核对规范 JSON 投影、来源及材料哈希、贡献类型和 accepted result→claim 链；语义评价须说明依据，不把字符串比较当作知识增量证明。缺失历史基线不自动补成事前记录，参见 `taste-judgement.md`。

---

## Per-Section Writing Checklists（分节写作清单）

这些清单把贡献优先逻辑折进稿件各节。它们是清单，不是独立工件：每一项都应能追溯到 `confirmed_contribution.md` 的某个字段。中文社科稿常无独立的"结果"节，此时"核心分析节"（案例分析、史料分析、规范论证）承担"结果作为验证"的职责。

### CHECKLIST — 引言论证阶梯

引言是贡献的论证，分级递进。每一级都向主张收窄；跳级是引言"读起来没问题却什么也没说"的最常见原因。

- [ ] **问题**——确立领域问题（`Why This Contribution Is Needed → Field problem`）。这个领域为何重要。例：不是"基层治理很重要"，而是"县级政府同时承受'谋发展'与'保稳定'的双重约束，二者如何被平衡此前只有规范讨论"。
- [ ] **进展**——既有研究已经做到什么。公允陈述；这是缺口可信的前提，也是不立稻草人的前提（`dialogic-argument.md` §4）。
- [ ] **缺口**——留下的具体缺口（`→ Specific gap`）加上让它开着的具体挑战。这是整个引言的支点。缺口类型与 anatomy §3.2 四型（空白／矛盾／未及／误判）对应，矛盾型与误判型比空白型更受顶刊青睐。
- [ ] **研究问题**——把缺口转成本文要回答的精确问题或目标。
- [ ] **贡献承诺**——把 Core 贡献（`Core Contribution → Main contribution statement`）作为对研究问题的回答说出来，并让读者能辨认它属于哪一阶。
- [ ] **证据预告**——点名将支撑承诺的证据（`How This Paper Responds → Evidence available`），承诺不裸奔。例："基于 A 县 2016—2023 年三轮政策调整的过程材料"。
- [ ] **读者收益**——以审稿人收益收束（`Core Contribution → One-sentence reviewer payoff`）：接受这个贡献后读者得到什么。

WHY 要阶梯：每一级都必须是下一级的必要前提。缺口不从进展推出、问题不从缺口推出，贡献就会显得没有动机，文字再好也没用。

### CHECKLIST — 方法可信度

方法节不只是描述，它让 Design response *可信*。每个设计选择都要回答"为什么是它而不是显而易见的替代方案"。

- [ ] 每个主要设计选择都对应它克服的 `Concrete challenge`（不是"本文采用双重差分"，而是"采用双重差分是因为试点县的选取并非随机，需要以未试点县的同期变化作反事实"）。
- [ ] 材料／数据来源、案例或样本选择、测量与识别策略各自有理由，而不只是被陈述。案例选择要说清是典型、极端、关键还是偏差案例（anatomy §3.5）。
- [ ] 比较基准（对照组、反事实、竞争解释、反面案例）的设计正是为了产出 `Evidence required`，而不是顺手可得的东西。
- [ ] 可复核的承重细节在场（数据来源与口径、访谈或档案清单、编码手册、模型设定、史料版本），审稿人无法以"不可核验"驳回。
- [ ] 方法节没有暗中假定任何列在 `Claims to soften or avoid` 中的主张（例如把待检验的中介环节写成"作用路径"）。

### CHECKLIST — 结果作为验证

结果（或核心分析）不是指标堆放，它是贡献受审的法庭。每个小节验证一个承诺。

- [ ] 每个结果小节对应 `Evidence required` 中的一项，并检验引言中的一个承诺。
- [ ] 每个小节都写明：问题 → 证据（表、图、过程材料、档案）→ 比较 → 解释 → 它证明了什么、没证明什么。
- [ ] 主结果以 `Strong claims allowed` 允许的强度直接支撑 `Main contribution statement`。
- [ ] `Evidence missing` 中的内容在这里明显地*没有*被主张。不存在从"提示"到"证明"的静默升级；中介或调节的统计显著不被写成"机制成立"。

起草每个结果小节之前先写一句定位句：

```text
本小节检验"[承诺]"这一贡献承诺，通过展示[证据]支持[允许强度下的主张]，但不主张超出[边界]。
```

### CHECKLIST — 讨论：洞见与机制

讨论把结果转成*理解*。弱的讨论复述数字；强的讨论解释机制并安放贡献。

- [ ] 重述答案（贡献），不重述过程。
- [ ] 解释**机制**：Design response 为什么产生了这个结果——是洞见，不只是结果。例：不是"绩效考核显著提高了整改率"，而是"考核把上级注意力转化为可预期的检查节点，基层据此把有限资源集中在可被看见的整改项目上"。
- [ ] 归因：每个关键设计选择贡献了什么（回扣方法可信度）。
- [ ] 与 `Why prior work leaves it unresolved` 中点名的既有研究对位，显示缺口现在被关上了——并按 `dialogic-argument.md` §5 交代对最强反方的接受、拒绝与未决。
- [ ] 从 `Evidence missing` / `Claim boundary` 说明局限，但不让中心主张溶解。
- [ ] 以回答 `Significance risk` 收束：领域层面的含义，不是泛泛的"具有借鉴意义"。

### CHECKLIST — 摘要贡献契约（5 步）

摘要是一份契约：它按顺序承诺论文恰好交付的贡献。五句话，五个任务。

1. **问题与利害**——领域问题及其为何重要（`Field problem`）。
2. **缺口**——具体未解决的缺口（`Specific gap` + 既有研究为何不足）。
3. **贡献**——作为回应的 Core 贡献（`Main contribution statement` + `Design response`）。
4. **证据**——最强的支撑结果（`Evidence available`），按允许强度陈述。
5. **收益**——审稿人收益／领域含义（`One-sentence reviewer payoff`），限定到不越界。

WHY 是契约：摘要若承诺超过 `Strong claims allowed`，论文在第一行就已越界。摘要必须能逐字段对照 `confirmed_contribution.md` 核验。中文刊摘要常见的"丰富了……研究""提供了新视角"收尾，只有锚在可定义、可区分且有证据的贡献上才不算注水（anatomy §3.3）。

---

## How To Use It

1. 完成设计与执行；校验 canonical `method_execution.json` 及其下游资格投影。`execution_record.md` 与 `results_validation.md` 只作为派生视图。
2. 起草 `confirmed_contribution.md`：先在映射表中选定一阶，按该阶的"必须交付的证据"填 `Evidence required`，过一遍伪贡献清单，再填满四个贡献区块与 Calibration Receipt；在锁定 Core 陈述之前诚实解决 `Evidence missing`。
3. 运行 `& $Python -X utf8 (Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth_core\tools\contribution_check.py') paper_rewriting_output`，直到通过（exit 0）。
4. 只有此时才进入分节蓝图与写作——每一节都回溯到 Core 贡献。
5. 主张或证据一旦变化，重跑执行与贡献检查；贡献移动会使下游各节失效。
