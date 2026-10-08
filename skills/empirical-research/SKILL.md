---
name: empirical-research
description: 社会科学方法设计与执行层：为 cnki-research-design/v4 提供实验、调查、案例/过程/一致性、QCA、文本、网络、比较、历史、扎根、定量、计算、综述、概念、诠释和规范适配器，并以 cnki-method-execution/v3 登记可追溯操作、最小可行方法运行、结果、偏离、负面发现、环境和哈希工件。Use whenever the user is doing social-science research, including 研究设计、实验、调查、访谈、案例研究、过程追踪、一致性分析、QCA、内容/话语/文本即数据、社会网络、比较/类型学、历史、扎根理论、描述/关联/预测/因果定量、计算社会科学、综述执行、概念/诠释/规范分析、数据清洗、稳健性、复现 or mixed methods. When invoked from cnki-paper, it is an internal design/execution adapter and never owns paper-completion semantics.
---

# Empirical-Research v5.1

本技能负责“如何设计并实际执行方法”，不负责 CNKI 获取或宣布论文完成。由 `cnki-paper` 调用时，先完整读取：

1. `references/{{METHOD_ADAPTER_FILE}}`
2. `references/method-adapters.md`
3. `references/design-answer-protocol.md`
4. `references/method-execution-contract.md`
5. `references/research-integrity.md`
6. `references/researcher-collaboration.md`
7. 案例、过程追踪、QCA、比较或一致性分析时读 `references/case-oriented-comparative-design.md`
8. 父工作流的 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}`

机器方法枚举只读 `references/method-adapter-registry.json`；不要在 SKILL 或 Markdown 中另建竞争注册表。

## 进入条件

- 研究问题已经用户确认；
- `research_design.json` 为 confirmed `cnki-research-design/v4`；
- 每条路线已有 Design ID、问题/主张/证据映射、材料边界、权限/伦理、复现和推断上限；
- 每个活动 Claim 已有稳定 `OPR-*` 操作化，并进入声明 `mvmr|full`、读写集、accepted 前置、方法操作、预期工件、验收诊断和失败路由的 `STEP-*`；
- `case_design` 已 confirmed：案例导向路线使用稳定 Case/Scope/Comparison/Within-case ID，其他路线显式 `not-applicable`；
- 来源或材料可合法访问；
- 需要的专用引擎和运行环境可用。

v1–v3 设计只能兼容读取；新执行前先用 cnki-paper 的 `research_design.py migrate --to v4`，通过独立、证据扎根的研究运行解决 needs-review，并保留用户对研究问题与设计的显式确认。迁移不会把旧 prose 或字符串动作提升为执行协议。

## 执行契约

```powershell
{{RUNTIME_HOME_ASSIGNMENT}}
$Execution = Join-Path $AverethHome 'skills\empirical-research\scripts\method_execution.py'
python $Execution schema --version v3
python $Execution scaffold paper_rewriting_output
python $Execution validate paper_rewriting_output --write --stage execution
python $Execution render paper_rewriting_output
python $Execution migrate paper_rewriting_output --to v3 --dry-run
python $Execution migrate paper_rewriting_output --to v3 --apply
$Exhibits = Join-Path $AverethHome 'skills\empirical-research\scripts\exhibits\exhibit.py'
python $Exhibits validate paper_rewriting_output --json
python $Exhibits table --spec SPEC.json --data DATA.csv --out table.md --format md
```

`method_execution.json` 兼容读取 v1–v3、单写 v3，是唯一执行事实源；`execution_record.md`、`method_pilot_report.md`、`action_result_trace.md` 与 `claim_disposition_report.md` 是生成视图。scaffold 与 migration 永远是 needs-review。承重路线还要登记 `method_contract_schema`、revision、profile、类型化合同和稳定 Artifact ID 引用；validator 从预测、标签、诊断及模型输出复算，不允许自由文本替代。每个 run 绑定完整设计摘要、适配器注册表摘要、问题/主张/证据、Case/Scope/Comparison/Within-case ID、不可覆盖的 action attempts、MVMR、工件、正式结果、失败／偏离、负面发现、伦理事件、环境和结构化主张处置。只有通过全部诊断的 accepted action 可以产生正式 result，action/result/Artifact 必须双向闭合；MVMR 未覆盖蓝图要求的真实材料、分析单位、提取／编码、方法动作、工件、诊断、结果与主张处置时，full action 不得 accepted。

定量、计算、混合路线或用户明确要求重建表图时，可在 design v4 的 execution blueprint 中增加
独立 `exhibit_rendering` STEP。其 Action 在 `parameter_snapshot.content.exhibit_spec` 以
`avereth-exhibit-spec/v1` 冻结参数，读取已接受结果的
哈希工件，输出 `avereth-exhibit-data/v1` companion data、矢量图、PNG 预览和 render log。
来源 numeric value 同时登记 quantity/unit/estimand/不确定性语义；render log 与 Action 所指
`software_environments[].exhibit_renderer` 精确绑定。该组件只在检测到 ExhibitSpec 时激活；
不要求纯人文论文加图，也不把图片提升为数值事实源。
样式 profile 声明字体回退链，render log 记录实际解析字体并计入环境身份；回归／平衡表可用 `table` 子命令
不经 R 投影为 Markdown／LaTeX 三线表，供中文稿件走可编辑表格。

每个 STEP 的 researcher dispatch 只由唯一 registry 的 policy、已登记 operation／Claim type 与
`researcher_risk` 编译。要求 `isolated_multi` 时，至少两个不同 run/context 以同一冻结协议独立形成
首轮工件，再由 canonical validator 重算一致性与精确分歧，必要时交不同 `Adjudicator`；完整记录
嵌入 action 的 `researcher_collaboration`，不另建协作事实源。角色使用 `Researcher A/B` 等中性名，
研究者只返回严格 JSON 工件，不输出身份自述。完整合同见 `references/researcher-collaboration.md`。

operation profile asset、失败 taxonomy 与成熟度证据路径继续只由 `method-adapter-registry.json` 索引，支持状态也只在该注册表声明；实际 profile／证据文件不构成竞争注册表。未完成方法专属 MVMR、正例、反例和 worked example 的方法准确声明为 `experimental_method_support`；只有至少真实 L4 才可 `production_ready`，L5 另需 design→execution→result→writing 端到端评测。通用 scaffold、共享空壳 fixture 或文件存在不能抬高成熟度。

## 路由

按主问题和主张功能选择：

- experiment
- survey（observation/interview/focus_group/questionnaire）
- case_study、process_tracing、congruence_analysis
- qca
- content_analysis、discourse_analysis、text_as_data
- social_network
- comparative
- historical
- grounded_theory
- quantitative（descriptive/associational/predictive/causal）
- computational
- review（embedded/narrative/scoping/systematic）
- conceptual、interpretive、normative

缺少顶层专用技能的方法由本技能内部适配器执行；不要为每个方法新增相互竞争的顶层状态机。已有引擎继续复用：

- `quant-causal-inference`
- `qual-process-tracing`
- `qual-qca`
- `qual-content-analysis`
- `aers-thematic-analysis`
- `text-as-data-cn`
- `aers-prisma-slr`

## 多路线

多路线必须服从 research_design.integration：

- sequential：按登记交接；
- convergent：独立材料并行并处理冲突；
- nested：子样本/案例嵌入总体；
- complementary：回答不同层次，不伪称相互验证；
- adjudicative：区分竞争解释。

共享上游材料必须披露；不同文件格式不等于独立证据。综合推断不超过各路线实际共同支持的范围。

## 执行纪律

1. 设计先于分析：不得先跑结果再编造路线或识别假设。
2. 所有材料/数据变换、选择、排除和版本留痕。
3. 每个落稿数字映射 Evidence ID、哈希 Artifact ID、JSON/CSV/text locator 与重现命令；validator 从定位值核对，不手敲统计量，也不在 gate 中执行任意命令。
4. 所有计划结果、零/负面结果和偏离登记；确认性、探索性和事后身份不互换。
5. 环境、软件、包、参数、种子和复现命令登记；受限材料提供合法受控复核路径。
6. 结果措辞服从路线能力和 inference ceiling；预测不等于因果，网络结构不等于机制，文本频率不等于态度。
7. 方法判断不依赖固定 p 值、样本量、信效度、QCA 或饱和阈值。
8. 面向研究者答复时只使用题面或工作区已经给出的产品、schema、权限和结果事实；一般方法问题不得自行注入 CNKI-Paper 的内部版本、文件名或 issue code。
9. 先写决定路线成立与否的少数瓶颈，再写“核验结果 → 处置 → 推断上限”分支；不要让共同字段和工件清单压过方法特定判断，也不要在仍可审计的风险核验前过早撤销设计标签。决策优先只调整顺序和篇幅，不能遗漏题面异常或路线专属最低闭环。
10. 案例导向路线把因果效应、因果机制、因果组态和理论评价分开；普通案例研究不自动支持机制，一致性分析不单独证明效应或机制，QCA 组态不改写成平均效应。
11. 实际增删案例、范围修订、机制痕迹、理论预测—观察、矛盾/负面案例和跨路线交接必须登记；同一材料不得伪装为理论形成后的独立验证。
12. build、ProsePacket 与复现包只消费 canonical v3 下游资格投影中由 accepted action 双向绑定、诊断通过且 Claim disposition 允许的 result；active v3 失败或无合格结果时不回退到字符串 ID 或旧数字清单。

## 方法专用门禁

客观事实可阻塞：伪随机化、抽样/语料/档案/案例边界或版本缺失、案例时间或层级缺失、跨案例不足两个案例、路线能力越界、同源材料伪独立、训练/验证泄漏、无权使用、伦理/隐私事件、设计—执行案例漂移、未登记增删案例或结果/数字、遗漏矛盾/负面结果、工件哈希变化和选择性报告。

只作风险/独立解释性评审：选案价值、典型性、代表性、范围条件质量、效度强弱、比较可比性、模型优劣、机制诊断力、QCA 阈值、理论饱和、范式适配、次国家外推和规范论证力度。评审运行必须绑定来源、理由、替代解释和独立 context，不要求特定研究者身份。

## 复现与回写

可继续用 `scripts/repro_pack.py` 登记来源、排除、决策和环境；数字只写入 `method_execution.json`，`repro/numbers.jsonl` 只是自动派生兼容视图，并只投影 accepted-action-bound result。方法引擎输出统一作为 `method_execution.json` 的 Artifact ID。只有 execution validate 通过、结果与负面发现完整、贡献完成 retain/narrow/withdraw 校准后，才回写 `cnki-paper` build。表/图进入 Word 后仍需实际渲染，引用页码仍由 page-evidence 审计。

## 索引

- 方法适配：`references/method-adapters.md`
- 设计答复质量：`references/design-answer-protocol.md`
- 执行契约：`references/method-execution-contract.md`
- 诚信治理：`references/research-integrity.md`
- 风险路由研究者协作：`references/researcher-collaboration.md`
- 机器注册表：`references/method-adapter-registry.json`
- 既有引擎：`references/methods-playbook.md`
- 复现：`references/reproducibility.md`
- 定性依据：`references/qual-methods-evidence.md`
- 案例导向比较研究：`references/case-oriented-comparative-design.md`
- 数据准备与变量构造：`references/data-preparation.md`
- 结果报告规范：`references/reporting-standards.md`
- 实证表图合同：`references/exhibits/exhibit-contract.md`
