# Public Text Politics

`public-text-politics` 是 `empirical-research` 内部的方法 profile pack，不是顶层
Skill，也不拥有工作流阶段、收据或论文完成语义。它把公开文本政治学中反复出现的
七类设计转成类型化合同、工件角色和可执行检查清单；方法 family、Claim 能力和最终
推断上限仍由核心方法注册表与实际验证结果决定。

## 七个 profile

| Profile | 研究对象 | 首要失败风险 |
|---|---|---|
| `claim_measurement` | 主张、框架、立场、责任归因等监督式测量 | 开发集与验证集泄漏；同一模型运行自我验证 |
| `semantic_alignment_and_reuse` | 条款对齐、文本复用、政策扩散、来源借用 | 时间倒置、模板套话、共同第三方来源和翻译链 |
| `legislative_process` | 法案家族、委员会推进、法律化与竞争风险 | 版本重复计数、届期删失错误、句子数冒充风险集单位 |
| `institutional_grammar` | 主体—规范词—行为—条件—例外—执行—后果 | 用单一加权分数掩盖不同类型的不兼容 |
| `public_source_process_tracing` | 公开来源中的机制痕迹、竞争机制和记录沉默 | 同源转述被当作独立证据；找不到被写成不存在 |
| `discourse_network` | `Actor–Claim–Position–Time–Source` 关系 | 共词网络被改写为行动者联盟网络 |
| `text_in_causal_design` | 文本作为结果、处理、匹配、控制或机制证据 | 文本单位冒充独立样本；测量开发数据污染效应估计 |

## 使用顺序

1. 先由核心注册表确定 method family 和 Claim 类型。
2. 在 `research_design.json` 的路线中用 `supplemental_profile_id` 选择核心注册表已绑定的
   profile，并把补充合同写入 `supplemental_contract`；补充 schema 不能填入
   `method_contract_schema` 冒充核心合同。
3. 补充合同只写稳定 Artifact ID；实际路径与 SHA-256 只写入
   `method_execution.json` 的 `runs[].artifacts`。
4. 共享 contract loader 在设计阶段检查核心与补充 schema，在执行阶段解析同一注册表、
   核对 Artifact ID 并继续调用核心 method validator。`machine_checks[].check_kind` 只是
   可审计的检查需求目录，不是第二份 validator 调度表。
5. 检查未通过时降低 observed inference ceiling 或退回设计/执行，不能在 limitation
   段落中补一句话放行；执行记录仍保留实际偏离、负面结果和工件。

`manifest.json` 只是非权威的 pack 资产清单；唯一机器绑定位于
`references/method-adapter-registry.json` 各核心合同的 `supplemental_profiles`。
`profile.schema.json` 约束 profile；`contracts/*.schema.json` 只增加公开文本场景的补充约束，
不能声明 estimand、counterfactual、识别假设、Claim 类型、推断上限或 validator，只能通过
`*_ref` 引用核心事实；`fixtures/*.json` 为每个 profile 固定
一个合法正例、两个典型错误、一个边界例和一个推断越界例。这里没有示范研究项目，
也不会创建 `examples/` 占位目录。

## 判断边界

机器可以核对文件、哈希、集合重叠、行列结构、指标复算、计数一致性、时间方向、
Claim–Evidence–Artifact 链和推断越界。确定性检查不能用统一 F1、样本量、显著性或“方法
质量总分”代替模型研究者对构念意义、证据诊断力、阈值充分性和理论价值的有据判断。
