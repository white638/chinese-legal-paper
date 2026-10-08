# {{HOST_DISPLAY_NAME}} 方法适配契约 v5.0

本文件只规定 `empirical-research` 与父工作流、专用方法引擎之间的接口。方法知识见
`method-adapters.md`，机器字段见 `method-adapter-registry.json`，面向研究者的答复质量见
`design-answer-protocol.md`；不要在这里复制第三套方法清单。

## 1. 控制边界

- `cnki-paper` 持有中文论文状态与完成语义；
- `cnki-paper` 提供写作、结果验证和审计引擎；
- `empirical-research` 持有方法路线与执行契约；
- `quant-causal-inference`、`qual-process-tracing`、`qual-qca`、
  `qual-content-analysis`、`aers-thematic-analysis`、`text-as-data-cn` 和
  `aers-prisma-slr` 只执行各自方法动作。

下游引擎完成动作后必须返回父控制面，不得改题、另建状态机、跳过设计门或宣布论文完成。

## 2. 两种任务形态

### 独立方法答复

用户只要求审查、解释或改进一项方法时，按 `design-answer-protocol.md` 直接回答。只使用题面和
用户提供的事实，不虚构工作区、内部 ID、schema、版本、权限、执行结果或完成状态；不因技能内部
存在契约就强迫用户先创建一套文件。

### 工作区设计与执行

进入 CNKI-Paper 工作区后：

- `research_design.json` 是唯一设计事实源，兼容读取 v1–v4、新写入使用 `cnki-research-design/v4`；
- `method_execution.json` 是唯一执行与结果事实源，兼容读取 v1–v3、新写入使用 `cnki-method-execution/v3`；
- 设计 v1–v3、执行 v1/v2 只允许兼容读取或显式迁移；迁移工件保持 `needs-review`，不把旧自由文本动作提升为 accepted action；
- `execution_record.md`、原六份设计 Markdown 与新增的 `operationalization_matrix.md`、`execution_protocol.md`、`next_action.md`、`method_pilot_report.md`、`action_result_trace.md`、`claim_disposition_report.md` 均为自动生成视图，不得并行手改；
- 专用引擎产生的代码本、时间线、真值表、模型日志、流程图、表图或检索记录只是 Artifact，
  必须由 Execution ID 登记路径、角色、版本和 SHA-256，不能成为第二份状态真相。

旧工作区中的 `design_protocol.md`、`result_register.md` 等文件可以作为迁移输入或辅助工件保留，
但不再是每条路线必须新建的统一骨架，也不能覆盖两个 JSON 契约。

## 3. 设计进入执行的条件

任何估计、编码、校准、主题建模、筛选或综合开始前，父设计至少已经确认：

1. 问题、答案任务和 Design ID；
2. 概念、材料总体/案例/语料/档案边界；
3. 路线功能、主辅关系和多路线整合；
4. 关键假设、比较或竞争解释；
5. 权限、伦理、隐私和复现条件；
6. Claim/Evidence 映射与推断上限。
7. 若适用，Case Universe/Case/Scope/Comparison/Within-case 身份、选案知情状态、材料角色和整合顺序。
8. 每个活动 Claim 的 `OPR-*` 操作化，以及无环 `STEP-*` 蓝图中的 `mvmr|full`、读写集、accepted 前置、方法操作、预期 Artifact、验收诊断和失败路由。

字段存在不等于设计优良；方法适配、代表性、诊断力、阈值和外推仍需独立解释性研究运行论证并绑定证据。

## 4. 执行回写

每个实际动作和结果回写 `method_execution.json`：

- 每次动作以稳定 action/operation/attempt 登记，保存启动时设计 SHA、参数／提示词／代码本快照、输入输出、环境、诊断、失败代码、处置路线、偏离和结果；不覆盖失败尝试；
- 全量动作前先以真实材料、分析单位、一次提取／编码、方法动作、哈希工件、passing diagnostic、result 与 claim disposition 完成 MVMR；所需 MVMR 未 accepted 时不得接受 full action；
- 数据集、语料、访谈、档案、搜索记录、排除决定、代码/模型输出、表图和环境均登记 Artifact ID；
- 每个落稿数字或定性发现登记 Result ID，并映射 accepted action、Design/Claim/Evidence/Artifact 及适用的 Case/Scope/Comparison/Within-case ID；action/result/Artifact 必须双向闭合；
- 实际增删案例、范围修订、机制痕迹、理论预测—观察、矛盾/负面案例和路线交接均登记；
- 计划与实际偏离、零结果、反向结果、未支持结果和伦理事件不得省略；
- 受限材料登记合法访问与受控复核路径，不虚假声明公开；
- 设计路线摘要、适配器版本或工件内容变化时，旧执行状态和下游凭证失效。

不得把手工抄写的系数、百分比、QCA 指标、编码统计、主题比例、PRISMA 数量或案例证据写入正文。

父工作流与复现包只消费 canonical v3 下游资格投影：accepted action、passing diagnostics、
result/Artifact 双向绑定和适用 Claim disposition 缺一不可。active v3 失败或无合格结果时资格为空，
不得回退到字符串 Result ID。该投影复用执行 validator，不是第二结果注册表。

方法支持状态仍在唯一 method adapter registry 中声明。`experimental_method_support` 表示已有
可检查骨架，不等于 production；至少具有方法专属 MVMR、正例、反例和 worked example 的真实
L4 才可 `production_ready`，L5 另需端到端评测。通用 scaffold 与空壳资产不能抬高成熟度。

## 5. 专用引擎

按注册表路由已有引擎；缺少顶层引擎的方法由 `empirical-research` 内部适配器执行。专用引擎的
阈值、诊断和输出只在适用任务中使用：

- 定量因果：目标量、识别假设、比较、诊断、不确定性；
- 过程追踪：时间线、机制/竞争机制、证据账本和诊断力；
- 一致性分析：竞争理论、可区分预测、预测—观察矩阵和理论相对评价；
- QCA：校准、真值表、矛盾、余项、解与案例回查；
- 内容/主题/文本即数据：语料版本、单位、代码/表示、适用验证与语境；
- 系统综述：协议、检索、筛选、流程守恒、评价与综合。

不得把任何引擎的固定样本量、显著性、信度、QCA 或饱和阈值升级为通用 PASS/FAIL。

## 6. 父工作流交接

交回 build 前：

1. v4 设计仍 confirmed，OPR/STEP 蓝图、路线与案例设计摘要同执行记录匹配；
2. 每个活动 Claim 和计划结果已有执行处置；
3. 结果、负面发现、偏离、环境和工件哈希完整；
4. 结果验证明确允许与禁止解释；
5. 贡献完成 retain、narrow、revise 或 withdraw 校准；
6. 统一 execution gate 通过。

未满足时返回 design/execution 修复，不用正文润色掩盖方法缺口。
