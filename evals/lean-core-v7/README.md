# Lean Core v7：版本化回归与能力库

`manifest.json` 保存案例身份、任务、tags、failure_mode、risk、hard_checks、target_metrics 和 lifecycle。
已有 30 项是任务库的历史初始集合；运行数量由本次改动、相关案例和预算决定。旧基线字段与历史运行继续可读，不能把它们当成当前模型收益。

`novelty`、`knowledge-change`、`refutation` tags 关联选题与反证能力。
对应的 [novelty-regression](../novelty-regression/README.md) 提供来源绑定自动参考、模型双顺序捕获和组件对照；
其局部指标与中央任务完成、成本及硬性合同检查一起解释，人工标注不属于执行依赖。

## 选择与冻结

| scope | 用途 | 选中数量 |
|---|---|---|
| smoke | 小范围执行入口检查 | 1–3 |
| targeted | 日常相关回归 | 3–8，默认最多 6 |
| broader | 模型升级、较大结构变更或扩大诊断 | 按相关范围及 max_cases |

`max_cases` 是预算上限。相关案例不足时报告 NOT RUN，不用无关案例补齐。
支持 `--tags`、`--exclude-tags` 与实际 diff 路径；显式 tags 选择所需能力，diff 用于识别受影响的 tags。
选择按相关性、风险与稳定 ID 排序。source bank 快照、选中任务全文、筛选条件和 selection SHA 一起冻结；
双方必须使用同一选择，失败或未完成案例留在选中分母内。

```bash
python evals/lean-core-v7/selection.py evals/lean-core-v7/manifest.json --scope targeted --tags reference-loading,citation --max-cases 4 --output experiment/selected-manifest.json
```

真实失败先形成最小复现，添加案例时保存 origin_evidence，不能把合成材料标成真实故障。
`selection.py --add-case case.json --output new-bank.json` 生成递增版本；
`--archive-id ID --coverage coverage.json` 需要覆盖该例全部 hard_checks 的实际确定性验证记录与原因。
归档只降低未来运行范围，已有任务与实验快照保留。infrequent 案例只进入 broader。

## 按登记目标判断

`experiment.json` 在执行前绑定两侧完整配置、允许改变的 JSON Pointer、评测模式、选中 manifest 与目标。
同一模型、推理设置、实际材料与所选任务配对；实际配置差异必须与 `allowed_config_changes` 一致。

```json
{
  "target": {
    "category": "efficiency",
    "metric": "input_tokens",
    "direction": "decrease",
    "min_relative_improvement": 0.1
  },
  "execution": {"repeat_on_uncertain": 0}
}
```

- **Hard integrity**：逐任务核验来源、引用、证据边界、负面结果、数字、方法/结果、权限和科学状态中该任务声明的检查；新增已核实硬错误或任务完成退步即 REJECT。
- **Workflow regression**：任务完成率、实际读取、工具/代理调用、重试、耗时和持续工件。必须有真实测量，未知为 null。
- **Soft quality**：清晰度、自然文风和论证流畅度只作诊断。普通工程实验不能只凭偏好获胜而 KEEP。

KEEP 需要无新增硬退步、无关键未知且登记目标达到正的最小改善阈值。明显达到同量级恶化阈值为 REJECT；
微小差、测量缺失、条件不匹配或关键冲突为 UNCERTAIN。相同既有错误不是新增回归，也不能作为 prose 推广的合格事实基础。

支持目标：
`integrity/hard_failure_count/decrease`、`reliability/task_completion_rate/increase`、
`efficiency/实际成本字段/decrease`、`prose/pairwise_preference/increase`。
前三者至少登记正的 `min_absolute_improvement` 或 `min_relative_improvement`，两项存在时同时满足。
prose 需登记 `min_win_margin >= 0.2` 与样本要求；Commonplace 默认 5–10 项，且先通过 hard、protected、citation、semantic 检查。

报告包括 `decision_basis`、`target_metric`、`hard_regressions`、`cost_delta` 与 `soft_diagnostics`；
`quality_improvement_proven=false` 表示 KEEP 是本次工程目标的判断，不证明论文整体优秀。
同一实验只登记一个主目标，便于解释改进依据。

## 匿名评审与有界重复

prose 主 judge 接收随机 A/B 文本与同一任务材料，返回 A/B/TIE/UNCERTAIN、置信度、理由和定位。
默认抽取 20% 交换位置复核。低置信度时才调用不同模型系列的第二 judge；
观测到位置翻转、评审失败或冲突，均不能自动保留。保存实际 prompt、输出、上下文、模型和匿名映射，映射不进入 judge。

效率、可靠性与完整性目标可以依据完整可核验记录判断，无需为每个样本调用文风 judge。
人类检查可选。完整 Commonplace 2×2 用于手动研究。

`repeat_on_uncertain` 为 0、1 或 2，表示最多增加的轮数。每轮重跑双方完整选中集合；
保留首轮与全部实际尝试、文件 SHA 和判决，不择优、不隐藏失败。重复结果不一致继续 UNCERTAIN，
因此重复主要补充诊断，不能把一次不确定抹成通过。

## 初始化真实输入

```bash
python evals/lean-core-v7/execute_run.py --init-spec experiment-setup --code-root /path/to/clean/paper1 --codex /path/to/codex --scope targeted --tags prose,claim-evidence --max-cases 3
python evals/lean-core-v7/execute_run.py experiment-setup/execution-spec.json --manifest experiment-setup/selected-manifest.json --experiment experiment-setup/experiment.json --preflight-output preflight.json
```

初始化与预检不调用模型，不代填许可、确认或分数。只要求选中案例的真实材料。填写：

- 完整配置：实际模型、推理设置、Codex/Python 版本、`prompt_version=codex-workflow-adapter/v1`、材料模式和预算。目前只支持实际生效的 `task_timeout_seconds`，不能宣称未实施 token/费用限额。
- 材料：每个 snapshot 的 files 包含 path、sha256、destination、source_id、role、content_verified、permission 与 verification_notes。合法内容与权限不能靠哈希代替。
- 授权：实际 authority_evidence 与 permitted_endpoint（profile_complete 或 stage_complete）。缺少研究问题/标题确认时保留真实 checkpoint。
- 执行器与独立 assessor：精确 argv 审查依据与 SHA，支持 request/workspace/spec_root/python 路径替换；保留宿主 sandbox。
- 实验：真实登记时间、两侧有效配置 SHA、allowed_config_changes、target 和重复预算。代码版本须匹配干净 checkout。

## 执行组件实验

```bash
python evals/lean-core-v7/paired_run.py baseline/execution-spec.json candidate/execution-spec.json --experiment experiment.json --scope targeted --tags reference-loading --max-cases 4 --judge-config judge-config.json --output-root paired-run --execute
```

不带 `--execute` 仅预检。可以传入 `--baseline-code`、`--candidate-code` 和精确 `--baseline-ref`，
使不同 checkout 与所选任务保持可核对的绑定。配置文件和实际工作流初始值一致，不能只改变标签。

`instruction_variant=current|lean|minimal` 是可选实验变量；同代码消融登记 `/instruction_variant`。
current 使用该代码版本完整指令；lean 投影其路由、控制器、硬边界与完成合同并保留 JIT 入口；
minimal 提供短控制合同。投影只写本次临时 runtime 的主 Skill，保留实际前后 SHA；
controller、权限 profile、证据检查和收据代码一致。旧源码不能明确分离完整硬合同的 lean 投影会拒绝，
可用旧 current 与新 lean 的不同 checkout 比较。

执行器保留原始 stdout/stderr、事件、实际输出、controller 端点检查和独立 assessment。
每次尝试封存，恢复检查 SHA；明确重试用新 attempt。Ctrl-C 终止当前进程树并保留未运行项。
`close_loop.py` 可单独核验已有 capture，绑定实际正文、材料、assessment 与 trace 后判断；
其他二进制材料需可核对的文本版本。没有材料或目标时不宣称执行成功。

`compare_runs.py` 的 `review_required` 是历史严格检查兼容状态，不要求人类评审，也不代替新目标判断。
`diagnose_runs.py` 退出码 0 只表示报告生成。任何 eval 都不签科学收据、不自动修改源码或发布。

## CI 与证据状态

确定性 CI 每次提交运行。live workflow 默认 targeted，支持 host-smoke 与 broader，以及 tags、
baseline_ref、max_cases、repeat_on_uncertain。host-smoke 只检验宿主执行，不评价研究质量。
相关差分按标签选择案例；没有凭证/材料时明确 `Live evidence: NOT RUN`，模型调用为 0。

需要 GitHub secrets `OPENAI_API_KEY`、`AVERETH_LEAN_INPUT_TOKEN`，以及 vars
`AVERETH_LEAN_INPUT_REPOSITORY`、`AVERETH_LEAN_INPUT_REF`、`AVERETH_LEAN_BASELINE_REF`。
材料 ref 和 baseline ref 固定完整 SHA；材料仓库提供两侧规格、实验、judge 配置与实际输入。
原始材料、正文和 trace 不自动上传。托管 runner 的本地文件随作业结束清理；长期实验用获准的存储。

确定性检查 PASS、宿主 smoke PASS、真实工程目标 KEEP 与论文整体质量是不同结论。
当前案例库历史评测状态不由合成测试或安装成功改写。
