# 研究设计主干 v4

## 唯一事实源与兼容策略

工作区唯一机器可判设计事实源是 `research_design.json`。

- 兼容读取：`cnki-research-design/v1`、v2、v3 与 v4；
- 新建、修改、执行、审计和签发新凭证：统一使用 v4；
- v1–v3 仅可 status/render 或作为显式迁移输入；必须迁移、解决全部 `needs-review`，并由用户显式确认研究问题与设计后才能进入新 execution；
- 旧六份设计视图以及 v4 新增的 `operationalization_matrix.md`、`execution_protocol.md` 均由 `research_design.json` 自动生成，禁止手工维护第二份真相。

正式 JSON Schema 位于 `schemas/cnki-research-design-v1.schema.json` 至 `schemas/cnki-research-design-v4.schema.json`。

```powershell
$Design = Join-Path $AverethHome 'skills\cnki-paper\scripts\research_design.py'
& $Python -X utf8 $Design schema --version v4
& $Python -X utf8 $Design template --family process_tracing
& $Python -X utf8 $Design validate paper_rewriting_output --write --stage design
& $Python -X utf8 $Design render paper_rewriting_output
& $Python -X utf8 $Design migrate paper_rewriting_output --dry-run --to v4
& $Python -X utf8 $Design migrate paper_rewriting_output --apply --to v4
```

template 和 migration 只产生 `needs-review` 草稿，不得自动补成 confirmed；迁移器不会把旧 prose、计划句或字符串动作提升为可执行事实。

## v4 对象

| 对象 | 身份 | 责任 |
|---|---|---|
| `research_questions[]` | `RQ-*` | 一个 primary，可有子问题；类型、答案任务、O-T-I-P-R、确认记录 |
| `concepts[]` | `CON-*` | 定义、边界、来源、识别/操作规则、测量或诠释有效性 |
| `claims[]` | `CLM-*` | 类型、问题/设计/证据映射、允许/禁止范围、状态 |
| `evidence[]` | `EVD-*` | 材料位置、Source ID、时间、用途、支持主张和独立性 |
| `method_routes[]` | `DSN-*` | 方法族、功能、主辅角色、依赖、材料、伦理、复现和推断上限 |
| `operationalizations[]` | `OPR-*` | 将活动 Claim/Concept 落到维度、可观察项、识别／测量规则、材料、抽取／转换、质量检查、判定规则、失败后果和预期结果类型 |
| `execution_blueprint.steps[]` | `STEP-*` | `mvmr|full` 步骤、OPR/Claim/Material/Evidence 映射、读写集、前置条件、操作、研究者风险、预期工件、验收检查和失败路由 |
| `case_design.case_universes[]` | `CUN-*` | 案例总体的纳排、时间、空间、层级和分析单位 |
| `case_design.cases[]` | `CAS-*` | 案例边界、选案、结果知情状态、理论角色与材料角色 |
| `case_design.scope_conditions[]` | `SCP-*` | 范围条件及其 Claim/Design/Evidence 映射和推断影响 |
| `case_design.comparisons[]` | `CMP-*` | 至少两个案例的比较逻辑、时间/层级对齐、威胁与上限 |
| `case_design.within_case_analyses[]` | `WCA-*` | 过程追踪、一致性分析或其他个案内分析的证据责任 |
| hypotheses/propositions/frameworks | 稳定 ID | 仅按问题和路线需要使用 |
| alternatives/falsification_conditions | 稳定 ID | 竞争解释/反对、区分性证据和处置 |

ID 不随标题润色更换；删除或替代对象保留状态和变更记录，不能复用旧 ID 指向新含义。

`knowledge_state` 不是一段自由摘要。它必须登记 `review_type`（embedded、narrative、
scoping 或 systematic）、`search_scope`、`screening_rules`、`reading_records`、
`quality_appraisal`、`synthesis_logic` 和 `contradictory_evidence`，再据此填写 known、
unknown、gap_authenticity、maturity 与 expected_contribution。声明 systematic 时必须有
对应的 review 方法路线和 PRISMA 报告连接；其他类型不得被自动套用系统综述硬门。

`gap_authenticity` 使用 `research-gap-diagnosis.md` 的现有字段内合同，保持问题承诺时已确认的主落点、阻断原因、具体命题与 `SYN-*` 核心身份。它只生成条件式设计责任，不自动决定方法：概念／测量落点要求分类或识别规则，理论／解释落点要求可区分预期，证据落点要求精度／复现／三角验证责任，识别／方法落点要求说明修复何种盲点，范围／群体落点要求迁移或异质性检验，行动／实践落点要求主体—目标—约束—证据桥—评价标准。若设计过程改变 gap 核心，先回 research 重新综合与确认，不能在 design 内静默替换。

每个概念必须至少有一项 `operationalization_or_recognition`：变量路线写指标、编码和数据来源，
概念/诠释/规范路线写可识别规则、边界案例或论证中的使用规则。`measurement` 使用结构化状态与
说明，记录测量误差、编码/识别可信性或明确的不适用理由；空数组和空对象不能通过。

## 操作化与执行蓝图

v4 把“说明将如何研究”提升为可校验的操作协议，但不新增事实源。每个活动 Claim 必须至少被
一个 `OPR-*` 覆盖；每个 `OPR-*` 必须进入一个计划 `STEP-*`。步骤只引用设计内已有的
Question/Claim/Concept/Material/Evidence/Design ID，并通过现有
`method-adapter-registry.json` 的 `operation_profile_asset` 解析 `method-operation/v1`
操作、artifact role、诊断与失败 taxonomy；不复制方法族清单或另建 operation registry。

蓝图是有向无环图。每个步骤声明 `read_set`、`write_set`、accepted 前置步骤、procedure、
expected artifacts、acceptance checks 与 `on_failure`。`mvmr` 步骤必须独立于 full；full
步骤只有在所需 MVMR 步骤 accepted 后才可执行。MVMR 不是新的 workflow stage，而是
execution 内先用真实材料、真实分析单位、一次提取／编码、方法动作、哈希工件、通过诊断、
结果和主张处置闭合最小方法链。

控制器只读编译 `avereth-research-protocol/v1`，并通过 `protocol compile|validate`、`next`
或 `plan --granularity operation` 投影当前可执行动作。`protocol render` 只显式刷新派生视图；
不保存 canonical protocol JSON，也不赋予步骤或 Markdown 执行权威。

每个步骤的可选 `researcher_risk` 记录认识论适配、解释歧义、误判后果、编码手册成熟度、参照
基础、留出状态、边界案例负荷、推断距离和理由。编译器将其与 operation／Claim type 合并，投影
是否至少分发两个隔离研究者及何时启用仲裁；独立编码、参照集构建和留出验证不能由
`not_applicable` 绕过。完整合同见
`empirical-research/references/researcher-collaboration.md`。

## 研究问题

只按答案任务选择 primary type：

- descriptive：可靠表征对象、分布、类型、序列或变化；
- explanatory：区分原因、机制或条件；
- predictive：对未观察结果作预先可验证预测；
- operational：在目标、约束和备选下形成行动判断；
- normative：公开价值/事实前提并辩护标准或制度。

O-T-I-P-R 记录对象、时间、发生领域、视角和关系。不同类型激活自己的 `task_fields`；不要求所有问题写成变量关系或具有假设。所有活跃问题必须保留用户确认来源和时间。

## 多方法路线

每条 `method_routes[]` 必须说明：

1. family、function、role、依赖路线；
2. 对应问题、主张和证据；
3. 方法及其与问题匹配的理由；
4. 单位、材料宇宙、纳排、实际范围、时间、版本和选择逻辑；
5. 权限、伦理、复现和证据材料独立性；
6. 确认/探索/事后、负面结果、偏离和结果清单计划；
7. 推断上限、禁止推断与限制；
8. 方法族条件字段与设计期工件。

多路线时，`integration.strategy` 必须为 sequential、convergent、nested、complementary 或 adjudicative，并记录路线顺序、交接、材料独立性、冲突处理和综合推断上限。单路线使用 `single`。同源材料的不同格式不能宣称独立验证。

方法字段以 `empirical-research/references/method-adapter-registry.json` 为机器注册表，以 `empirical-research/references/method-adapters.md` 为解释。

同一注册表还索引 operation profile 并保存 `declared_support_status`。成熟度由
`tools/check_method_maturity.py` 累积计算：L0 名称，L1 结构化 design fields，L2 方法族原生
typed contract/validator，L3 合格 `method-operation/v1` profile，L4 方法专属 MVMR 加正例、
反例和 worked example，L5 再有 design→execution→result→writing 端到端评测。
`production_ready` 至少要求 L4；其余保持 `experimental_method_support`。通用 scaffold、共享
空壳 fixture、占位路径或单个示例文件只能证明资产存在，不能冒充方法族已达到 L4/L5。

## 案例导向剖面

v4 继续要求 `case_design`。案例、过程追踪、QCA、比较和一致性分析路线使用
`applicability=active`；明确不涉及案例导向的路线使用 `not-applicable`；历史路线不得仅凭
方法标签推断是否适用。案例导向不是新增方法族，而是连接案例总体、选案、范围、跨案例和
个案内分析的共同设计层。

主张能力分为 `causal_effect`、`causal_mechanism`、`causal_configuration` 和
`theory_evaluation`。一般案例研究不自动支持机制；过程追踪主要支持机制推断；QCA 主要支持
必要、充分、合取和多路径组态；一致性分析主要支持竞争理论的相对评价。跨案例与个案内分析
并用时，另在 `case_design.integration.sequence` 登记 `cross-case-first`、
`within-case-first` 或 `iterative`。完整规则见
`empirical-research/references/case-oriented-comparative-design.md`。

## 认识论与治理

`epistemic_position` 记录本体论、认识论、范式、研究逻辑、研究者位置和兼容理由。标签不评分，兼容性进入独立解释性评审。详见 `research-foundations.md`。

`governance` 记录选择性报告、数据真实性、引用、署名、既往发表、一稿多投、利益冲突、AI 和隐私。状态缺失、未知、不利或仅有占位语不能通过。详见 `empirical-research/references/research-integrity.md`。

## 硬门与软检查

硬门只覆盖可定位事实：

- Source ID/内部 ID 不存在或身份冲突；
- 问题、概念、材料、案例、时间、层级或版本边界缺失；
- 活动 Claim 未被 `OPR-*` 覆盖、OPR 未进入步骤、步骤图有环／未知依赖／读写或前置冲突；
- 方法族 required operation/artifact role 未进入蓝图，MVMR 缺必要步骤，或 full 依赖尚未 accepted 的 MVMR；
- researcher risk 枚举／理由无效，或任务身份要求的隔离多研究者被错误降为单研究者；
- 未确认设计进入 execution；
- 主张没有相应适配器能力，或效应、机制、组态、理论评价互相冒充；
- 随机化无法审计、同源材料伪装独立、训练/验证材料泄漏；
- 权限、伦理、治理、结果清单或偏离状态缺失；
- 设计—执行—案例/范围/比较/个案内分析—结果—贡献—正文漂移；
- 工件或凭证内容哈希变化。

以下只作 WARNING/REVIEW：选题价值、概念质量、方法适配、选案价值、典型性、代表性、范围条件质量、比较可比性、机制诊断力、替代解释、理论饱和、QCA/显著性/信效度阈值、模型优劣、次国家外推和规范论证力度。

## 累积检查与下游资格

design 确认结构与完整 OPR→STEP 路径；execution 重新校验设计并验证 `method_execution.json`；build 只消费 canonical v3 下游资格投影中由 accepted action 双向绑定且处置允许的结果；复现视图同样只消费该链上的数字；audit 检查完整身份链、负面结果与独立评审；output 检查最终文件和当前设计/执行/注册表摘要。active v3 校验失败或无合格结果时不得回退到字符串 ID。任何上游内容变化都会使旧凭证失效。

## 迁移

v1–v3→v4 保留稳定问题/概念/主张/证据/设计 ID、Source ID、用户确认线索、工件路径和哈希。旧案例、过程、QCA、比较或历史路线不能从自由文本推导案例角色、范围条件、机制痕迹或一致性结果；相关 `case_design` 统一标记 `needs-review`。非案例路线可机械生成 `not-applicable`。迁移只建立待复核 OPR/STEP 壳，不从旧 prose 或动作句推断可执行步骤、accepted action、MVMR、诊断或 PASS。dry-run 零写入；apply 先按内容摘要备份，再生成 v4 草稿；重复 apply 幂等；未来 schema 安全阻塞。
