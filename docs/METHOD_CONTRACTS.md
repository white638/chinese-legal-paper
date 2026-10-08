# Method Contracts

## 权威层级

方法合同采用单向叠加，不允许下层反向重写上层：

```text
core method registry + research_design/method_execution contracts
  → family-specific typed contract and validator
  → internal method profile (for example public-text-politics)
  → journal reporting/transparency overlay
```

核心权威包括：

- `skills/empirical-research/references/method-adapter-registry.json`：method family 与 Claim
  capability 的唯一机器注册表；
- `research_design.json`：项目确认设计、estimand/target、比较或反事实基础与设计路线；
- `method_execution.json`：实际执行、偏离、负面结果、环境和哈希工件；
- `skills/empirical-research/references/schemas/methods/`：类型化 family/profile 合同（存在
  对应 schema 时）；
- 核心 method validator 的实际输出：observed inference ceiling 的唯一来源。

Markdown 说明可以解释合同，但不是第二注册表。

## 类型化合同最小外壳

新路线在既有设计/执行结构内登记：

```json
{
  "method_contract_schema": "text-as-data/measurement-v2",
  "method_contract_revision": "1",
  "method_profile": "text-as-data/measurement-v2",
  "method_contract": {},
  "artifact_refs": ["ART-PREDICTIONS", "ART-METRICS"]
}
```

`method_contract_schema` 必须解析到受管 schema；未来版本 fail closed。`method_contract`
保存类型化字段，`artifact_refs` 只保存稳定 Artifact ID；实际路径、SHA-256 与角色仍由该 run
唯一的 `artifacts` 数组持有。诸如“模型表现可靠”的文字只能进入说明字段，不能替代预测、
标签、诊断或敏感性工件。

设计阶段使用同一个核心 loader 执行 schema 的嵌套 `required`、`type`、`enum`、`const`、
数组和闭合对象规则；不能把畸形合同拖到 execution 才发现。执行阶段再执行完整 schema、
Artifact ID 解析、路径/SHA 链与核心 method validator。

核心合同至少区分：

- 设计时声明与执行后观察；
- source/corpus identity 与研究者判断；
- 开发、验证和最终推断数据；
- 文本分析单位、处理单位、有效样本单位与聚类单位；
- requested Claim 与 observed inference ceiling；
- 主结果、负面结果、偏离和敏感性结果。

## 内部 profile

内部 profile 可以增加该方法场景所需的字段、工件角色和机器检查，但必须：

- 引用核心 method family 和 Claim capability，不复制列表；
- 不拥有工作流阶段、收据或论文完成语义；
- 不把方法建议变成所有项目通用的分数或阈值；
- 把确定性检查与研究者解释性判断明确分开，并为后者保留证据和理由；
- 为合法、典型错误、边界和推断越界提供对抗 fixtures。

补充层的最小外壳是：

```json
{
  "method_contract_schema": "text-as-data/measurement-v2",
  "method_contract_revision": "1",
  "method_contract": {},
  "supplemental_profile_id": "claim_measurement",
  "supplemental_contract": {
    "schema_version": "avereth-public-text-politics/claim-measurement/v2",
    "profile_id": "claim_measurement"
  },
  "artifact_refs": ["ART-CORPUS", "ART-REFERENCE", "ART-REFERENCE-RUNS"]
}
```

profile 的唯一绑定位于核心注册表相应合同的 `supplemental_profiles`；pack manifest 不参与
运行时选择。补充合同不得直接出现 `estimand`、`counterfactual`、
`identification_assumptions`、`claim_type(s)`、`capabilities`、`method_contract_schema` 或
任何 validator 字段；合法场景使用 `*_ref` 指向核心合同。补充 schema ID 也不得写入顶层
`method_contract_schema`。

`skills/empirical-research/packs/public-text-politics/` 遵循这一模式。

## 期刊 overlay 合同

期刊包只允许增加以下内容：

- `reporting`：哪些核心字段和诊断需要在正文或附录呈现；
- `transparency`：数据、代码、材料、匿名与披露要求；
- `presentation`：表图、篇幅、体例和读者沟通；
- `submission`：投稿文件、声明和平台检查；
- `sources`：期刊官方要求的来源、核验日期和时效提醒。

期刊包不得定义或覆盖：

- `claim_capabilities`
- `estimand` 的项目值或 schema
- `inference_ceiling`
- `method_contract_schema`
- `validators` / `method_validator`
- `next_stage` / `completed_stage` / `status` / `gate` / `receipt`
- `method_override` / `execution_engine`
- 任何工作流阶段、收据或完成语义

期刊可以要求“在正文报告核心 estimand”或“附上平行趋势诊断”，但只能通过引用核心字段
表达，不能在 pack 内重新定义 estimand 或自建一个更宽松/更严格的科学验证器。若某项要求
确实属于普遍科学有效性，应先进入核心 method contract 和对抗测试，再由期刊 overlay 要求
呈现；若只属于该刊报告偏好，则保留为 overlay。

未来如增加结构化 `journal-overlay.json`，最小形态为：

```json
{
  "schema_version": "avereth-journal-method-overlay/v1",
  "journal": "example-journal",
  "core_method_contract_ref": {
    "id": "causal-design/v1",
    "revision": "1"
  },
  "reporting": {"require_core_fields": ["estimand_or_target"]},
  "transparency": {},
  "presentation": {},
  "submission": {},
  "sources": []
}
```

`core_method_contract_ref` 只能使用唯一方法注册表已经登记的合同 ID 和当前 revision；即使某个
schema 文件位于 empirical-research 目录，只要未登记，仍是孤儿资产，不能被期刊 overlay
引用。`tools/check_journal_overlays.py` 检查 journal pack 中是否出现自建 schema、Python validator、
非受管核心引用或保留字段。它不会把期刊关于方法写作的普通 Markdown 建议误判为新的方法
控制面。`skills/journal-fit/references/venue-overlay-registry.json` 必须与仓库发现到的全部
`*-workflow` 入口精确同集，使它们共同继承 `cnki-paper` 工作区控制面；该 registry 只登记 venue
router 边界，不含 method capability、validator、status 或 receipt。

## 失败与迁移

- schema、路径、哈希或 validator 引用无法解析：`FAIL`；
- 缺少权限、材料或必须的解释性证据：`BLOCKED`，并可保留 `needs-independent-review` 合同标记；
- 旧自由文本合同：保持只读或经显式迁移进入新 schema，不自动声称通过；
- validator 失败：保留工件与结果，修改设计或收窄 Claim 后重新验证；
- 期刊要求与核心方法合同冲突：核心合同优先，期刊 overlay 报告冲突而不能覆盖。
