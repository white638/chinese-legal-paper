# 方法执行契约

`method_execution.json` 是方法执行和结果的唯一机器事实源。读取器兼容 `cnki-method-execution/v1`、v2、v3；新 scaffold 只写 v3，并绑定 confirmed `cnki-research-design/v4`。v1/v2 继续按原合同验证和渲染；进入新执行前必须显式迁移、重绑动作并重新确认，旧字符串动作不会自动获得执行权威。

## 命令

```powershell
$Execution = Join-Path $AverethHome 'skills\empirical-research\scripts\method_execution.py'
python $Execution schema --version v3
python $Execution scaffold paper_rewriting_output
python $Execution validate paper_rewriting_output --write --stage execution
python $Execution render paper_rewriting_output
python $Execution migrate paper_rewriting_output --to v3 --dry-run
python $Execution migrate paper_rewriting_output --to v3 --apply
python scripts/validate_method_artifacts.py paper_rewriting_output --json
python scripts/validate_measurement.py paper_rewriting_output
python scripts/migrate_method_contracts.py paper_rewriting_output --dry-run
python scripts/exhibits/exhibit.py validate paper_rewriting_output --json
python scripts/exhibits/exhibit.py render --spec SPEC.json --data DATA.csv --out NEW_DIR --environment-id ENV-EXHIBIT-001
python ../cnki-paper/scripts/avereth_core/build/exhibit_map.py paper_rewriting_output --write
```

`scaffold` 只建立 `needs-review` 草稿，绝不证明已执行。v2→v3 迁移保留 run/result/artifact/environment ID 与已有 SHA，但把顶层状态降为 `needs-review`，清空类型化 actions，把旧字符串动作放入迁移清单，并令既有结果等待重新绑定 accepted action；不会伪造 MVMR、诊断或 PASS。v3 的 `render` 重建 `execution_record.md`、`method_pilot_report.md`、`action_result_trace.md` 与 `claim_disposition_report.md`；四者均为派生视图。apply 前按内容摘要备份，dry-run 零写入，未知未来 schema 安全阻塞。

## 最小结构

- 根：schema、设计 schema、完整设计摘要、适配器注册表摘要、完整状态、runs、reporting、software_environments；
- run：Execution ID、Design ID、family、adapter version、设计路线哈希、问题/主张/证据与 Case/Scope/Comparison/Within-case ID 映射、不可覆盖的类型化 action attempts、显式 `minimum_viable_run`、类型化核心方法合同/修订/设计摘要、稳定工件与结果、结构化偏离/失败路线、负面发现、伦理事件、环境 ID 和主张处置；
- action：稳定 ID、蓝图 `operation_id`、同 operation 唯一递增 attempt、`mvmr|full`、状态、启动时设计 SHA、参数/提示词/模型/编码手册快照 SHA、输入/输出工件、环境、诊断、失败代码、处置路线、偏离和结果 ID；风险路由的程序任务另在同一 action 内嵌 `researcher_collaboration`，绑定隔离 run/context、封存输出、一致性、分歧、仲裁与任务工件；只有 `accepted` action 可以产正式 result；
- artifact：稳定 ID、安全的工作区内路径、SHA-256 和角色；
- result：稳定 ID、accepted `action_ids`、文本、类型、Claim/Evidence/Artifact 及适用的案例设计 ID、状态、允许/禁止解释和可复算数字；result 与 action 必须双向绑定，工件必须来自该 action 输出；复现包只消费通过这条 accepted-action 链的数字；
- minimum viable method run：在全量执行前，以真实 material、真实 analysis unit、一次提取/编码、设计内方法动作、哈希工件、passing diagnostic、result 和 claim disposition 构成闭环；蓝图要求的 MVMR operations 未全部 accepted 时，full action 不得 accepted；
- case execution：实际纳入案例、登记增删、预测—观察矩阵、机制痕迹、负面案例、范围修订、交接结果及独立复核状态；
- reporting：结果清单、负面发现、偏离和选择性报告声明。

每个活跃 Design ID 和 Claim ID 必须有执行处置。合法终止使用 `not-applicable` 或 `withdrawn` 并记录理由，不用空字段伪装完成。

## 可选实证表图动作

社科实证表图使用 `avereth-exhibit-spec/v1`，直接放在一个已登记 STEP 对应 Action 的
`parameter_snapshot.content.exhibit_spec` 中；同一 `content` 保留 operation/procedure 快照，不新增
顶层事实表或执行 schema 版本。渲染 Action 可以
`result_ids=[]`，因为它展示既有科研 Result，不产生新的科学结果。其 `source_result_ids` 必须回到
通过 accepted estimation Action 与哈希 Artifact 闭合的已有 Result，渲染 Action 自身不得成为来源
Result 的生产 Action。

图片只承担展示；CSV/JSON companion data 使用 `avereth-exhibit-data/v1` 并作为 `plot_data` 或
`table_data` Artifact 登记。每个非参考点通过 `source_numeric_locator` 与来源 Result 已登记的
`numeric_values[].locator` 核对，数量、单位、estimand 和不确定性语义来自同一 numeric value 的
`exhibit_semantics`。PDF/SVG/PNG、render log 和 companion data 都写入当前 run 的
`artifacts`，由同一个 accepted 渲染 Action 输出。详细字段、角色、失败码和激活边界见
`references/exhibits/exhibit-contract.md`。

`figure_asset_map.md` 仍由 build 阶段拥有。build 内部的 `exhibit_map.py --write` 只在 canonical
execution 通过后更新该文件的机器预填标记区，绑定 execution SHA 并保留作者确认内容；它不推进阶段
或签收据。

`supplemental_profile_id` 不是独立方法合同。只要设计或执行出现任一 supplemental 字段（包括仅有 `supplemental_contract` 或其设计摘要），就必须同时声明非空且已注册的 `supplemental_profile_id`、核心 `method_contract_schema` 与 `method_contract_revision`；空对象和假值不能绕过该存在性检查。loader 必须从唯一 registry 全局解析该 profile，并核对其登记的 core ID 与 active revision。缺少 profile 或核心合同、错绑其他核心、修订漂移或同名多重注册均在 not-applicable、withdrawn 及空 core 等任何早退前失败关闭。

## Canonical 下游资格

`method_execution.py` 的 canonical validator 同时投影下游资格，不另建结果注册表。正式 result
只有在其 `action_ids` 全部解析到 accepted action、action/result 双向引用一致、result 工件来自
这些 action 输出、诊断通过且 Claim disposition 允许当前用途时，才能进入 build、ProsePacket
或复现包。`retained` 可用于原 Claim 支撑；`narrowed|withdrawn` 只可用于显式负面／null 报告，
不能继续支持原命题。active v3 缺少合格结果、解析失败或语义校验失败时，下游资格为空，禁止
回退到正则匹配 Result ID、旧字符串动作或手填数字。

## 方法支持成熟度

operation profile 与 `declared_support_status` 继续登记在唯一
`method-adapter-registry.json`。`check_method_maturity.py` 累积计算 L0–L5；
`production_ready` 至少要求 L4，即方法专属 MVMR、positive case、negative case 与 worked
example 都有真实可运行证据，L5 另需 design→execution→result→writing 端到端评测。当前未达
该证据闭环的方法保持 `experimental_method_support`。通用 scaffold、共享空壳 fixture、路径存在
或一份示例文本不是 L4/L5 证据，也不使执行结果自动取得下游资格。

## 累积验证

execution、build、audit、output 都重新检查：

- v4 设计是否仍 confirmed，完整设计 SHA 与 action 启动 SHA 是否一致；
- operation/attempt 是否唯一且追加保存，accepted action 是否通过全部诊断并产出真实哈希工件；
- MVMR 是否覆盖真实材料、分析单位、提取/编码、方法动作、工件、诊断、结果与主张处置，full 是否满足 accepted 前置动作；
- route hash、adapter version 与 family 是否漂移；
- 同一核心 registry/loader 下的类型化 schema、revision、profile、设计合同摘要、可选 supplemental 合同与 Artifact ID 引用是否一致；validator 始终由核心合同调度，supplemental profile 不得自建 validator；
- 实际 Case/Scope/Comparison/Within-case ID 是否与设计一致，增删案例和范围修订是否登记；
- 过程追踪是否有机制痕迹，一致性分析是否有预测—观察矩阵，QCA 是否被误写为平均效应；
- 结果和数字是否映射到登记身份及哈希工件，登记数字是否等于 locator 实际取值；
- 因果或外推措辞是否超过路线能力；
- null/negative/not-supported 结果是否保留并逐项 narrow/withdraw 主张，偏离、失败代码、处置路线和 failed action 是否双向一致；
- 环境、版本与复现命令是否存在；
- 生成视图与当前 JSON 是否一致。
- 风险决定是否可复算；要求多研究者时，首轮运行是否真正隔离并封存，一致性与分歧是否从逐项
  工件复算，适用仲裁是否晚于全部首轮输出且精确覆盖分歧，参照／留出／边界／推断任务是否闭合。

文本测量还会从逐条预测重算 confusion matrix、reference agreement、macro/micro F1 与每类
precision/recall/F1/support，核对 item 与 document/group 两层拆分，并要求误判、敏感性及分维度
`measurement_validity.json`。研究运行登记模型修订、独立 context、提示词哈希和输出工件；模型参照
只报告 `reference_agreement`，同模型重复只报告 `stability`，只有外部基准可报告
`external_accuracy`。空参照、空预测、ID 覆盖不全、同源输出或未解决分歧均失败关闭。

完整的研究者协作结构、任务路由和身份表述规则见 `researcher-collaboration.md`。

旧自由文本路线可由 `migrate_method_contracts.py` dry-run 后显式 apply。迁移仅建立
`needs-review` 类型化占位和内容寻址备份，不推断不存在的工件或 PASS；rollback 必须指定
快照，未知未来版本失败关闭。

后续任何设计、执行、案例级结果、最终文件或注册表摘要变化都会使对应 audit/output 凭证失效。设计迁移导致执行绑定摘要变化时不得静默重签；案例相关执行先降为独立复核。
