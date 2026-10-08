# Avereth 维护规范

本文规定仓库级维护流程，不改变 `cnki-paper` 的八阶段控制器、方法合同或完成权威。

## 1. 分支与合并

- 一个中立公共主分支是唯一源码基线；迁移完成后使用 `main`。`codex` 与 `claudecode` 只保留
  一个发布周期作为只读回退线，不再接收公共功能。
- PR 默认保持为 Draft，直到确定性 CI、安装校验和回滚说明齐备。
- 禁止向公共主分支强制推送，禁止在未验证的情况下直接覆盖运行时快照。
- 建议保护 `main`：要求 PR、要求全部公共测试和 Codex/Claude 宿主矩阵通过、禁止强制推送和删除分支。

## 2. 两类验证必须分开

### 确定性门禁

常规 `Avereth CI` 只运行离线、可重复、无凭证的检查：

- Python 编译、registry 漂移和生成运行时 doctor；
- 控制器、经验研究、工具和语义 eval；
- 离线 academic-prose corpus；
- Codex/Claude 双构建、host leak、隔离安装、构建—运行时 parity、生成文件清洁度。

日常 PR 与默认分支推送运行代表性兼容矩阵：Ubuntu 覆盖 Python 3.10–3.13，Windows 与
macOS 覆盖 Python 3.12；确定性公共套件和 Codex/Claude 宿主构建仍在每次运行中执行。
每周一 03:17 UTC 的定时运行执行完整 3×4 兼容矩阵，也可从 Actions 手动运行并启用
`full_matrix`。分支推送只在默认分支触发，功能分支由 PR 事件验证，避免同一提交同时触发
push 与 pull_request 两套重复作业。

这些检查可以阻止合并，因为相同提交应得到相同结果。

### 模型评测证据

`Avereth live evaluation` 提供 host-smoke、targeted 与 broader。host-smoke 需要
`OPENAI_API_KEY` 与 `AVERETH_EVAL_MODEL`；配对执行另需固定版本的材料仓库、访问凭证与 baseline，
具体配置见 `evals/lean-core-v7/README.md`。
模型输出、网络状态和服务端变化会造成波动，中央 `lean-core-v7` 按相同条件对照生产版本与候选，
按改动与 tags 选择版本化案例，以硬性完整性、任务完成和预登记目标给出 `KEEP / REJECT / UNCERTAIN`。
普通文风评分是诊断信号；prose 实验在事实、引用和语义检查通过后比较偏好。
报告明确 decision_basis 与 quality_improvement_proven=false；缺目标、测量或关键一致性时不自动保留。
人类检查属于可选校准。自动结论不替代确定性合同，也不自动推进任何研究阶段。

创新性组件使用 [novelty-regression](../evals/novelty-regression/README.md) 的来源绑定控制、双顺序模型输出与条件复核。
自动参考同时检查误报创新和误杀合理增量；人工标注不属于运行依赖。构造控制的通过率只证明对应行为，
研究新颖性、自然任务泛化和版本收益分别需要相应的实际证据。

当 prose packet、writer/fidelity/compression 逻辑或盲评 corpus 发生实质变化时，
应在合并前或发布前运行对应的真实实验；缺少条件时将 live evidence 标为 NOT RUN。
报告只保存在获准位置，原始材料、正文和 trace 不自动上传。

## 3. 维护顺序

架构简化优先使用 [运行轨迹与配对评测](TRAJECTORY_EVALUATION.md) 的实测证据。
`lean-core-v7` 的冻结任务、逐项材料、独立 assessment、capture 与 compare/diagnose 构成版本证据链；
运行数量服从所选能力与预算；传输 smoke 不代表研究任务完成。材料、配置或评审条件缺失时明确 NOT RUN/blocked。
新增默认复杂度与删减科学门禁均须先取得相应真实对照，不能用派生工件数量或诊断脚本退出码替代。

1. 先复现问题，记录失败命令、输入和受影响合同。
2. 优先修复唯一事实源；不要在 overlay、迁移层或文档中复制第二套规则。
3. 运行最小相关测试，再运行完整确定性 CI。
4. 涉及公共源码、Agent、入口或安装树时，同时生成两个宿主包，执行 host leak、隔离安装、
   installed doctor 和 build/runtime parity。
5. 检查 `git diff`，确认没有意外生成文件、收据或工作区材料。
6. 在 PR 中写明风险、迁移影响和回滚方式。

## 4. 发布检查

发布前至少确认：

- README、版本号与 CHANGELOG 描述一致；
- Codex 与 Claude 发行物来自同一提交，共享控制内核文件哈希一致；
- Agent 权限、入口、OpenAI metadata 与 runner 能力严格按宿主 profile 输出；
- `host-signed` 与 `agent-declared` receipt 保持不同来源语义；
- workflow registry 和方法 registry 无漂移，全部 schema/validator 引用可解析；
- 旧工作区迁移仍可 dry-run、apply 和 rollback；
- 安装脚本在 Windows 与 Unix 路径上均由 CI 覆盖；
- `THIRD_PARTY_NOTICES.md` 与 `licenses/` 保留真实来源和许可证义务；
- GitHub Actions 均固定到完整 commit SHA，并由 Dependabot 提交更新 PR；
- 两个 runtime artifact 均可由对应提交重新构造，而非作为新的源码事实源。

## 5. 维护优先级

依次处理：安全或数据损坏风险、状态/收据一致性、迁移与回滚、跨平台兼容、
确定性与可复现性、性能和体验。没有对应测试或合同证据的功能扩展不应插队。

## 6. 复杂性预算

新增阶段、代理、默认 reference、CLI 命令、持久工件、schema 或 gate 前，PR 必须给出：

1. 一个可复现的真实失败或重复返工；
2. 现有单代理／现有事实源／现有脚本为何不能稳定解决；
3. 对照评测中质量、错误率、返工、上下文或工具调用的实际改善；
4. 默认路径是否可以保持不变并将能力延迟加载；
5. 删除或回滚路径。

新增规则还须解释确定性代码或既有 JIT reference 为何不能解决，以及增加的上下文、调用和步骤。
删除重复说明优先验证唯一规范可达及相关行为；删除 gate、reviewer 或有消费者的工件按单变量消融。
已有组件没有可识别独立价值且消融未发现回归时倾向删除，不以模型整体写作总分给组件续期。
重大模型升级再比较 current/lean/minimal，普通提交使用相关 targeted 回归。依据和责任盘点见 `CONSTRAINT_CENSUS.md`。

不能证明增益的能力只可作为可选 adapter，不进入默认上下文。重构按“先删功能和概念，再拆文件”
执行；把同样的状态和工件移动到新模块，不算减法。禁止建立 simplification registry、lean receipt、
兼容 state 或新的上层 orchestrator。阶段数、代理数、工件数和代码行数只作维护诊断，不成为运行时质量门。
