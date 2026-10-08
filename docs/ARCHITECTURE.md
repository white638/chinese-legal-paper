# Lean Research Spine 架构

## 单源双构建

```text
skills/ + agent-specs/ + entrypoints/       唯一规范源
                  |
          tools/build_host.py
          /                     \
hosts/codex/profile.json   hosts/claude/profile.json
          |                     |
Codex TOML/prompt/runtime  Claude Markdown/command/runtime
```

Agent 的 `name/description/permission_profile/instructions` 只在 `agent-specs/` 维护；renderer 将高层
权限分别映射为 Codex `sandbox_mode` 与 Claude `tools`。入口和主 Skill 的公共正文由模板生成。
宿主 profile 同时冻结 home、Python 环境变量、入口、metadata 策略与 runner 能力矩阵。

`avereth_core/hosts/base.py` 定义最小 capture 合同；CodexExec、ClaudeExec 和 Claude
agent-declared adapter 保留各自真实隔离与来源语义。两套发行物可以不同，公共阶段、schema、receipt
验证与研究规则不能分叉。

## 单一控制面

```text
Avereth
  -> cnki-paper             唯一阶段、gate、回退与完成权威
       -> avereth_core      私有实现，无 Skill/状态/receipt
       -> lazy adapters     检索、定量数据、方法、期刊、页证据、渲染
       -> isolated agents   仅在设计风险或正式审计触发
```

任何 adapter、reviewer、MIR、ProsePacket 或派生报告都不能推进工作区或宣称完成。

## 五个语义阶段，八个机器阶段

`workflow_registry.py` 在同一 `StageDefinition` 中登记语义阶段与机器阶段映射：

```text
scope       = intake
evidence    = acquisition + research
analysis    = design + execution
manuscript  = build
verify      = audit + output
```

五阶段只用于 `status/plan` 的用户可见投影，没有独立 state、artifact、gate、receipt 或 migration。
控制器继续以八阶段判断最早失败、合法终点和回退：

```text
intake -> acquisition -> research -> design -> execution -> build -> audit -> output
```

## 渐进披露

`plan` 只列最早机器阶段当前需要的 references/adapters/allowed writes。intake 不再默认加载完整架构、
全阶段手册和所有可选能力。CNKI 规则只在 `cnki-cn|mixed` 或实际 CNKI 页面操作时加载；
`quantitative-data-check` 只在定量／计算／混合研究或用户明确要求数据时加载；方法、评审和渲染同理。

operation 级 plan 只在 execution 从 design v4/execution v3 投影工作项、依赖、失败路线和
`researcher_dispatch`。所有 plan/compile/next 操作只读。

## 唯一事实源

- `workflow_config.json`：任务、轨道和交付配置；
- `literature_registry.json`：来源身份；
- `literature_analysis.json`：批判阅读、综合与充分性；
- `research_material_registry.json` / `research_feasibility.json`：材料事实与 F2；
- `research_design.json`：设计；
- `method_execution.json`：真实执行与结果；
- `revision_contract.json`：受控修订授权和最早回退；
- canonical manuscript：规范稿；
- `audit_receipt.json` / `output_receipt.json`：内容与交付完成凭证。

Markdown 报告、计划、数据准备卡、MIR 和 review views 都是派生或 supporting outputs，不是第二真相。

## 数据按需

系统不维护全局数据资产 SQLite、跨工作区快照、自动变量匹配或长期公共数据库 starter。
`quantitative-data-check` 接受用户已经提供或当前问题选中的数据路线，只核验访问类型、分析单位、覆盖、
变量、链接、识别、许可、真实样本和哈希。它不能取得 Source、F2、design、result 或 completion 权威。

## 全文写作防火墙

full paper/revision 在 build 内由 manuscript compiler 从 build 前 canonical authority 生成 contract/MIR。
MIR 管理 Section/Move 依赖和 stale closure，但不进入 Writer，也不是科学权威。

Writer 只接收 `avereth-prose-packet/v2` 的当前 Claim、最小证据内容与作用、warrant、必要边界、
reader question/update 和保护原子。控制器状态、完整 evidence bank、评审意见、回复材料、数据获取日志、
未选来源和迁移历史禁止进入。正文链完成 deterministic、clarity、semantic fidelity 与 clean read 后，
才能证明进入规范稿。

## 多代理边界

普通研究使用主代理。执行中只有 risk router 判定 `isolated_multi` 才使用多个 Researcher run/context，
封存首轮输出后重算一致性并仅对真实分歧仲裁。

正式 audit review 的三个角色只读各自 prompt；原始输出不可手改。不同 context/output 才能声明
independent，否则记录 single_agent。review lifecycle 是 audit 内部动作，不是第九阶段。

## 验证与发布

`status` 与 `gate` 共用校验语义。gate 只能运行最早机器阶段；晚于失败阶段的请求零写失败。
build/audit/output 与 transition lock 记录 PID、主机、时间和 operation。

audit receipt 绑定规范稿和学术责任输入。output 从该 path+SHA 生成候选，以 QA_REQUIRED 停止；
真实逐页视觉检查后，第二次 gate 才执行守卫、事务发布和 output receipt。中途失败恢复旧交付集。

## 兼容与迁移

旧工作区通过单一 legacy 路径 dry-run/apply/rollback。未知未来 schema、冲突配置、多份规范稿和
凭证型输入 fail closed。不得为 Lean Core 新增第二迁移权威、兼容状态或上层 orchestrator。
