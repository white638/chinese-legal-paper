# 运行轨迹与配对评测

运行轨迹用于定位成本与失败来源。科学事实、阶段状态和完成收据继续由原有控制器裁决。
旁路观测不进入论文工作区 registry、Writer packet 或 receipt roots。

## 可选运行时采集

Codex 与 Claude 的隔离生成返回 `HostCapture.telemetry`，包含原始 JSONL stdout、stderr、解析后的
events、run/context 身份、请求的模型版本、提示词 SHA、实际耗时和宿主报告的 token 用量。
启动失败、超时、非 JSON 输出和隔离校验失败也可保留现场。`agent-declared` 没有宿主轨迹时保持
`telemetry=None`，不得补造 `host-signed` 观测。

Codex 隔离执行需要宿主支持 `skip_host_skill_discovery`，以便关闭本机 Skill 自动发现。
请求使用独立目录与受限工具设置；服务端错误优先从结构化事件报告，完整 stderr 保留在轨迹中。

默认只在内存保留宿主返回的轨迹。需要本地持久记录时，显式设置独立于论文工作区的目录：

```powershell
$env:AVERETH_TELEMETRY_DIR = 'D:\avereth-evaluation\observations'
$env:AVERETH_TELEMETRY_RUN_ID = 'experiment-baseline-01'
$env:AVERETH_TELEMETRY_PARENT_OPERATION = 'task-01'
```

每次观测使用独占新建的 JSON 文件，原始事件顺序保持不变。控制器另存实际命令、stdout/stderr、
退出码与耗时；`plan` 保存已选择的 reference requests；阶段 gate 和 audit action 保存调用结果与
耗时，缓存命中保留原来的 execution 标记。关闭采集只需移除 `AVERETH_TELEMETRY_DIR`。
写入诊断目录失败会在 stderr 提示，但不能改写科学结果、阻塞原本有效的 gate 或授予完成资格。

原始轨迹可能包含材料正文、工具参数、路径和输出，仅保存在用户选定的目录。公开版本证据应使用
已检查的聚合报告；不会默认上传原始轨迹或将其添加到 Git。

## 测量口径

- 宿主 usage 按 terminal 记录统计，避免把流式增量与总数重复相加。请求的模型别名与宿主原始
  model 字段都应保留；别名不能证明服务端权重固定。Claude 的 input_tokens 使用宿主同名字段，
  缓存计费字段仍在原始 usage 中，不按另一宿主的计费语义换算。
- 只有可识别的完整宿主事件流才给出工具调用次数；启动／完成生命周期按调用身份去重。
  未完成流、缺失 usage 或宿主不支持的测量为 `null`。
- 计划读取与实际读取分开。reference requests 证明计划选择，不能证明 Agent 真正读过这些文字。
  实际读取量只来自捕获的读取结果或可核验的文件读取事件；不能用文件大小、shell 命令文本或
  模型自述估算。需要读取的参照集与实际使用标签缺失时，recall 和 unused reads 保持未知。
- gate 返回零可能表示已有有效结果或不适用，不能直接算一次缺陷捕获。独立捕获、误报和修复
  成功需逐缺陷、带定位的独立评审；相同错误码不足以判定两个 gate 抓到了同一个缺陷。

## 自动评测到修改

知识改变与最近邻比较使用 [创新性回归组件](../evals/novelty-regression/README.md)。来源、片段与自动参考先冻结，
独立模型响应再导入；调用预算、缺失顺序、位置翻转和低置信度保留在报告中。
第二模型只在可复核的不确定样本上花费剩余预算。自动参考是行为回归依据，人类检查可选。

使用 [Lean Core 组件实验入口](../evals/lean-core-v7/README.md) 按改动、tags 与预算选择版本化案例，再冻结任务、材料快照、实际代码和
完整生效配置建立同条件实验。真实运行、独立 assessment、capture、compare、diagnose 的原始
证据分别保留。缺材料、真实用户检查点或运行中断保留在分母中；传输 smoke 只验证宿主接通。

日常工程迭代比较生产版本与单变量候选，分别考察一项 reviewer/gate、一组派生输出或读取范围。
每组实际配置差异必须与预登记的 `allowed_config_changes` 完全一致。候选不能凭配置名跳过既有
科学门禁。中央自动评测区分 hard integrity、workflow regression 与 soft quality；只有预登记目标
达到改善阈值且没有新增硬退步、任务完成退步或关键未知时，才生成 KEEP。

主 judge 接收随机 A/B 顺序，可选择任一方、平局或不确定。默认对 20% 的样本交换位置复核，
可在冻结配置中调整抽样率；低置信度时升级到不同模型系列的第二 judge。
第二 judge 使用双向顺序核对，位置翻转或冲突保持不确定。保存每次真实提示、输出、上下文、模型和标签映射；
judge 不接收代码版本、来源模型或标签映射。缺少第二系列配置时，困难样本保持不确定。

新增已核实硬错误、权限／科学状态或完成退步为 REJECT；相同既有错误单列。工程目标可以是错误减少、
完成率提高或已测成本降低。普通论文偏好只作 soft_diagnostic；效率目标不需要额外文风评审。
报告 decision_basis、target_metric、hard_regressions、cost_delta 与 quality_improvement_proven=false。
小于登记阈值的差异、缺少目标测量和关键冲突为 UNCERTAIN。重复必须预登记上限、保留每轮与全部案例，
不挑选有利轮次。执行 Git 合并或运行时推广仍须符合项目已有授权。

Commonplace 的默认评测使用 5–10 个真实任务的 C/D 配对，完整 2×2 用于手动研究交互效应。
它允许用达到登记差距的 prose preference 决定保留，但先通过 hard、protected、citation 与 semantic 检查。
人类检查属于可选校准。Constraint Census 记录规则归属；current/lean/minimal 仅改变实验指令投影。
Reviewer、gate 与 reference 的删减分别做单变量实验；工件及 Skill catalog 的合并依据实际消费与触发记录。
