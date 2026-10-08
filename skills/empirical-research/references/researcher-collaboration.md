# 风险路由的隔离研究者协作

本合同把原本常由多人完成的程序性研究工作纳入 `design → execution`，不新增阶段、状态机、
结果注册表或完成权威。`research_design.json` 仍是唯一设计事实源，
`method_execution.json` 仍是唯一执行事实源，`cnki-paper` 仍是唯一完成控制面。

## 一、路由对象

机器只从唯一 `method-adapter-registry.json.researcher_dispatch_policy` 读取操作—任务映射。
一个 `STEP-*` 可映射到以下一种或多种程序任务：

| Task kind | 研究工件 |
|---|---|
| `pilot_codebook_calibration` | 试编码、修订前后编码手册及变更日志 |
| `independent_coding` | 按同一冻结单位规则与编码手册形成相互隔离的逐项标签 |
| `agreement_calculation` | 从首轮输出重算一致率、Krippendorff α 及适用的 κ／π |
| `disagreement_adjudication` | 精确分歧集及其逐项裁决 |
| `reference_set_construction` | 经隔离构建、分歧处置并冻结的参照标签集 |
| `holdout_validation` | 对标签不可见的留出单元预测及参照比对 |
| `boundary_case_review` | 冻结边界清单的逐项纳入、排除或不确定处置 |
| `inference_audit` | 结果、证据、Claim 与正文允许／禁止主张之间的逐项审计 |

`independent_coding`、`reference_set_construction` 与 `holdout_validation` 的任务身份本身要求
`isolated_multi`，设计中的 `not_applicable` 不能取消这条客观要求。试编码校准、边界案例和推断审计
由风险触发；纯确定性复算或低风险直接读取可保持 `single`。系统不计算统一质量分，也不使用固定
样本量、固定一致性阈值或固定代理配额代替方法判断。

## 二、设计期风险剖面

每个 `execution_blueprint.steps[]` 可登记 `researcher_risk`：

- `epistemic_fit`：独立复现、竞争解读、确定性复算、单一判断或不适用；
- `interpretive_ambiguity` 与 `consequence_of_error`：`low|moderate|high`；
- `codebook_maturity`：`stable|provisional|new|not_applicable`；
- `reference_basis`：外部基准、规则核验、模型构建、混合证据、缺失或不适用；
- `holdout_status`：计划、已冻结、不可得或不适用；
- `boundary_case_load`：边界案例负荷；
- `inference_distance`：结果到主张的直接、一步或多步距离；
- `rationale`：为何该组合适合当前问题、材料与主张。

未显式填写时，编译器只从已登记的方法族、operation 与 Claim type 生成可复算默认值；显式值只能
覆盖这些有类型字段。`protocol compile` 将决定投影为
`avereth-researcher-dispatch-decision/v1`，包含任务、模式、最低独立研究者数、条件仲裁、冻结输入范围、
风险根据和 decision SHA-256。`task_kinds` 只列首轮研究任务，`post_run_task_kinds` 列首轮封存后
由控制面确定性执行的工作，`conditional_task_kinds` 只在实际分歧出现后触发。三者不得混写进
Researcher A/B 的首轮输出。该决定是设计事实的只读编译结果，不形成第三份权威。

## 三、隔离执行顺序

1. 冻结同一单位／边界清单、材料版本、编码手册或推断规则，登记 Artifact ID 与 SHA-256。
2. 为 `Researcher A`、`Researcher B`（必要时可增加 C、D……）建立不同 run/context；各运行使用
   同一冻结协议和同一研究输入范围，但不能读取同伴提示、输出、父线程判断、隐藏参照标签或审计材料。
3. 每个研究者只返回严格 `avereth-research-artifact/v1` JSON；首轮输出立即作为不同 Artifact ID、
   不同内容 SHA 封存，不得在看到同伴结果后覆盖。
4. 控制面从逐项标签重算一致性和精确分歧集。报告语义必须是 `run_consistency`、
   `reference_agreement` 或 `stability`；只有真实外部基准才可使用 `external_accuracy`。
5. 存在分歧且当前任务要求仲裁时，另启不同 run/context 的 `Adjudicator`。它只能接收冻结协议、
   精确分歧日志和全部封存首轮输出，并且必须在首轮输出全部完成后开始；其输出只覆盖分歧项。
6. 参照标签集、留出集、边界清单和推断审计分别完成任务专属闭环；未解决项不能随 accepted action
   进入下游。

中性角色名只承担功能区分。研究者和仲裁者不输出身份自述、免责声明、寒暄、Markdown 围栏或
工作流 PASS 声明；身份透明由 run/context、模型修订、reasoning effort、提示词摘要、输入范围摘要、
时间和工件摘要承担，而不是在每个研究判断中反复自我说明。

## 四、严格输出合同

`avereth-research-artifact/v1` 顶层只能有：

```json
{
  "schema_version": "avereth-research-artifact/v1",
  "operation_id": "STEP-001",
  "role": "Researcher A",
  "task_kinds": ["independent_coding"],
  "items": [
    {
      "item_id": "UNIT-001",
      "label": "registered-label",
      "evidence_locator": "materials/units.json#UNIT-001",
      "rationale": "Application of the frozen rule to the located evidence.",
      "confidence": 0.9
    }
  ]
}
```

顶层或 item 多余字段、空 item、重复 ID、缺少证据定位／理由、越界 confidence、角色或 operation
漂移均失败关闭。此严格结构同时保证“只返回研究工件”，无需扫描自然语言身份声明。

## 五、执行事实与硬门

每个风险路由 action 把 `avereth-researcher-collaboration/v1` 嵌入自身
`researcher_collaboration`。它至少绑定：

- dispatch decision SHA、operation、mode、task kinds 与冻结 input Artifact；
- 每次研究运行的 neutral role、run/context、模型及修订、reasoning effort、prompt/protocol/input
  SHA、开始/结束时间、盲态、封存状态与输出 Artifact；
- 每个任务的输入、输出、run 和专属详情；
- 复算的一致性工件、精确分歧工件以及适用的仲裁运行；
- 参照集、留出集、边界清单和主张审计工件。

以下任一事实阻塞 accepted action：

- 风险决定漂移、应多研究者而缺少协作记录、独立 run/context 或输出身份重复；
- 输入范围或冻结协议不一致、同伴输出可见、首轮结果未封存、输出不是严格 JSON 工件；
- 指标不能从逐项标签复算、分歧日志不等于实际分歧、仲裁早于首轮封存或未覆盖精确分歧集；
- 试编码缺少手册前版／后版／变更日志，编码或边界复核未覆盖冻结 manifest；
- 参照标签集无有效标签，留出研究者看到参照标签，或留出 manifest／标签身份未冻结；
- 推断审计没有覆盖当前 STEP 的全部 Claim、审计工件不属于 action 输出或仍有未解决项。

一致性值是诊断事实，不是统一自动 PASS 分数。解释取向、扎根、话语或规范路线只有在独立复现或
竞争解读与其认识论相容时才分发；成员反馈、参与者同意、伦理审批和真实外部专家判断不能由代理
角色替代。

## 六、下游边界

`action_result_trace.md` 从 canonical v3 自动投影研究者模式、角色／context、任务、一致性与仲裁；
它不是第二事实源。build、ProsePacket、复现包和正文只消费通过完整 execution validator 的
accepted-action/result/Artifact/Claim-disposition 链。推断审计可以要求 `retain|narrow|withdraw`，
不能扩张原设计的 inference ceiling，也不能自行宣布阶段完成。
