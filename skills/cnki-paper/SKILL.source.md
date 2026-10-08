---
name: cnki-paper
description: Avereth 的中文/CNKI、国际 SSCI 与混合轨学术研究写作控制面。用于文献研究、选题、设计、论文、审计与修订；独立答复及不改变主张、范围、证据或交付身份的表层改写使用 Direct。
---

# CNKI-Paper v7.2.0 — Lean Research Spine

Avereth 是用户代理；`cnki-paper` controller 管理研究阶段与完成资格。方法、检索、评审和渲染按当前问题调用。

## 1. 路由

- **Direct**：独立解释、翻译、文献／方法／引用问答，或不改变标题、主张、范围、证据集和交付身份的表层改写。完成必要核验后答复；不运行 doctor，不创建论文工作区，不要求发表轨道。
- **Workspace**：选题、设计、完整论文、正式审计、系统修订；新增来源或实质主张、改题／改范围、生成最终交付文件。按下文控制器状态推进。

Workspace 使用 `cnki-cn`（中文任务或要求 CNKI）、`international-ssci`（国际证据生态，可为零条 CNKI）或 `mixed`（中外证据均不可替代）。实际轨道在配置和文献注册表中一致；期刊状态与投稿要求查当次官方来源。

中文法学论文可加载相邻 `chinese-legal-paper/SKILL.md`，在既有工作区显式启用 `legal_profile=chinese-law-v1`。它补充法源版本、法律适用与引注合同；阶段、写入权限和完成收据仍由本控制器决定。

所有学术写作默认应用问题推进、概念辨析、语境引文、材料与判断交替以及按功能变化的段落与句法；按语言、学科、体裁和目标刊调整，不只用于中文或增强模式。拟题兼顾共鸣与描述，正文修辞不得超过证据。Direct 局部写作同样应用相关原则和必要核验，不因此另建 workspace 或全套审计表。

## 2. 工作流

| 语义阶段 | 机器阶段 | 工作 |
|---|---|---|
| Scope | `intake` | 问题、范围、轨道与交付 |
| Evidence | `acquisition + research` | 来源核验、阅读综合、问题与工作标题确认 |
| Analysis | `design + execution` | 设计、真实分析、结果与问题再判断 |
| Manuscript | `build` | 论证组织、证据约束写作与规范稿 |
| Verify | `audit + output` | 学术核验、渲染与交付 |

五阶段是八阶段的只读投影。实际顺序与回退由 controller 管理：

`intake → acquisition ⇄ research → design ⇄ execution → build ⇄ audit → output`

新来源或主张回 research，方法变化回 design，结果变化回 execution，表层改写及已有证据重组回 build。上游变动后重建失效的下游；晚期工件不覆盖早期失败。

## 3. 控制器与按动作读取

Workspace 首次进入或运行时变化时执行 doctor，再查看 status 与 plan：

{{SKILL_HOST_BOOTSTRAP}}

执行当前最早未完成阶段；只调用计划列出的 adapters，只写 `allowed_writes`。
`reference_requests` 给出当前动作需要的章节与理由，`required_references` 只是路径索引。
用 `plan --reference-action ACTION` 聚焦局部动作；同一上下文中已读且未变的指令可复用。
plan 不写工作区、不改变门禁、不签收据；execution 的 operation plan 决定是否需要独立研究者。

```powershell
& $Python -X utf8 $Controller gate paper_rewriting_output --stage <intake|acquisition|research|design|execution|build|audit|output>
```

锁故障先用 `recover-lock OUTDIR` 诊断，只对当前主机已死亡 PID、内容未漂移的有效锁使用 `--confirm`。
其他操作和故障处理见 `references/workflow-playbook.md` 对应阶段。

可选 Scout 仅在显式配置与当前 `delegation_requests` 下启用；按请求加载
`references/delegation.md`。主线程保留问题与综合判断、真实工具桥接和正本写入。
研究者继续服从原风险路由；资源限制只限制并发，不能减少规定的独立运行。

## 4. 事实、权限与写作边界

- `literature_registry.json`、`literature_analysis.json`、`research_design.json`、`method_execution.json` 分别拥有来源身份、批判综合、设计和执行事实。搜索、Exa、Scholar 与元数据只提供候选；承重内容需有合法来源和实际核验。
- 保留来源 ID、证据定位、实际 accepted 结果、数字、负面发现与推断边界。不得伪造来源、执行、用户授权、评审或完成；科学判断不能用模型总分或工件数量替代。
- design 或正文之前取得用户对精确问题、动机、范围、工作标题与标题权限的确认。后续实质变化按其权限处理；发布、提交、发送和付款服从已有授权。
- MIR 与生成 Markdown 是派生视图。正文事实只通过当前 `avereth-prose-packet/v2` 与 protected atoms；控制器状态、完整材料库、评审意见、回复信和未激活异议留在写作上下文之外。
- 新建 `full_paper`／`manuscript_revision` 显式使用 `prose_conditioning=auto`：主代理主动寻找并核验同论证功能的范例，按 Move 提供合法语言包；仍无合格范例时记录缺口，继续该 Move 的证据包写作，其他 Move 照常使用范例。`none`／`commonplace` 保留既有行为，`none` 只关闭范例条件化，不关闭默认写作原则；缺省旧配置和已完成工件不静默迁移。范例不能授予事实或引用资格，auto 不强制改变 locked／verbatim 模式；各路径保留逐字保护、Clarity 与规范稿兑现，语义改写继续独立语义核验，显式锁定文本以当前权威全文逐字核验。具体合同见 `commonplace-writing.md`。
- 独立研究／评审必须有真实不同的 run/context 和不可手改的首轮输出。模型一致性不称为人类验证；不能把声明式来源标成宿主签名。

## 5. 领域知识按需读取

以当前 plan 的章节为先；Direct 从下表选择与请求有关的参考，不运行阶段流程。

| 情形 | 参考与触发条件 |
|---|---|
| 选题组合 | `references/topic-selection-protocol.md`：`task_profile=topic_selection` 在检查材料或编译 packet 前读取；方向、侦察、封存与筛选归此协议 |
| 来源获取 | `references/acquisition-registry.md`；实际用 CNKI 时读 `cnki-operations.md` 和 `cnki-search/references/search-strategy.md`；中文特殊来源见 `source-channels-cn.md` |
| 深读与综合 | `references/critical-reading-and-synthesis.md`；摘要与详情页只支持窄描述，不能代替全文方法或结果核验 |
| 问题与材料 | `references/problem-led-research.md`、`research-gap-diagnosis.md`、`research-question-design.md`、`research-material-feasibility.md` |
| 定量／计算／混合研究 | `references/quantitative-data-check.md` 与同名 adapter；只在问题需要结构化数据或用户明确要求时加载 |
| 设计与执行 | `references/research-design-spine.md`、`method-routing.md`、`measurement-inference.md`；执行按 operation plan 的 `researcher_dispatch` |
| 全文与正文 | `references/engine/manuscript-compiler.md`、`academic-prose.md`：体裁 profile、论证责任、MIR、重建、Writer／Clarity／fidelity／Clean Read 合同 |
| 写作局部问题 | 默认按 `references/academic-prose.md` 的相关章节落实辨析、贯通、材料发声与节奏；防御性表达读 `anti-defensive-writing.md`；声音与公允转述读 `dialogic-argument.md`；问题推进读 `rhetorical-architecture.md`；范例检索和按段写作读 `commonplace-writing.md`。只加载当前动作所需部分 |
| 中文与史料著录 | `references/cn-journal-conventions.md`、`primary-source-citation.md` 对应章节 |
| 审计与修订 | `references/engine/reviewer-audit.md`、`controlled-revision.md`；正式 isolated review 遵守生成 prompt、原始输出和 assurance 合同 |
| 输出 | `references/workflow-playbook.md` 的 output 部分、`docx-format-fixes.md` |
| 维护与研究校准 | `references/integration-architecture.md`、`taste-judgement.md`；研究笔记可选，不拥有证据或完成资格 |

## 6. 停止与完成

Direct 完成当前答复与必要核验即可返回。Workspace 只有当前 controller status 和相应 gate/receipt 通过，才可声明阶段或交付完成。
继续当前范围内已授权的可逆动作、必要核验与修复，直到 profile 终点或真实用户检查点。缺少权限、访问、费用或范围决定时，只暂停依赖该条件的动作；继续当前阶段内 controller 允许且不依赖它的已授权工作。完成这些工作后，若仍需用户操作或没有新的恢复依据，报告具体阻塞；必要条件未满足的阶段不得宣称完成。

output 消费当前 PASS audit receipt 绑定的规范稿；`OUTPUT.QA_REQUIRED` 表示候选等待真实逐页视觉检查。
完成检查并记录真实 reviewer mode/context 后再次运行 gate，由事务输出发布文件。文件能打开、一个中间工件或一次 gate 返回均不证明交付完成。
