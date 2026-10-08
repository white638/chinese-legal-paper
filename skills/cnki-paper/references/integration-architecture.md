# CNKI-Paper 集成架构：Lean Research Spine

本文件规定权威边界。Avereth 是用户代理身份；`cnki-paper` 是唯一 Skill、状态机和完成权威；
`avereth_core` 是无 Skill、无状态、无独立收据的私有实现包。

## 1. 问题中心，而非基础设施中心

默认研究主轴是：

`研究问题 → 证据获取 → 分析与论证 → 论文写作 → 最终核验`

CNKI、国际检索、Exa、Zotero、定量数据、方法适配、评审和渲染都是按需能力。适配器只能返回
结构化事实、材料或检查结果，不能选择问题、取得 Source/final-source 身份、推进阶段或宣称完成。

| 层 | 责任 | 禁止事项 |
|---|---|---|
| `cnki-paper` controller | 八阶段、profile 终点、gate、回退、收据 | 委托完成语义或建立第二状态机 |
| `avereth_core` | 本地 build/audit/output/迁移动作 | 创建第二 progress、receipt 或科学事实源 |
| acquisition adapters | 发现、获取、导出、来源核验 | 把候选直接写成 final-source |
| `quantitative-data-check` | 按需核验已选数据路线、元数据、样本、变量与哈希 | 扫描全局资产、反向造题、授予设计／结果资格 |
| method adapters | 设计／执行事实检查 | 自行选择问题或伪造执行 |
| venue/page adapters | 刊性、格式、精确页证据 | 取得阶段所有权 |
| isolated reviewers | 只读角色意见 | 写工作区、互看输出或宣称完成 |

## 2. 五个语义阶段是八阶段的只读投影

五个语义阶段（`scope` / `evidence` / `analysis` / `manuscript` / `verify`）与八个机器阶段的映射只在 `workflow_registry.py` 声明一次，由 `status/plan` 投影；用户可见表、机器阶段顺序与各 profile 的合法终点见 `SKILL.md` §2。该映射没有独立状态、工件、收据、迁移器或 gate；实质变化仍回到拥有该事实的最早机器阶段。

## 3. 声明式合同与渐进披露

`avereth_core/workflow_registry.py` 是工件、运行时组件、机器阶段和语义阶段映射的唯一类型化声明源。
每个工件只登记一次 owner、阶段必需性、receipt 绑定、可重建性、迁移资格和允许 schema。

`avereth-plan/v2` 是只读投影。它只列当前最早机器阶段需要的 references、adapters 和 allowed writes；
不再在 intake 默认加载整个架构、全手册和所有阶段规则。完整架构与维护规则只在技能维护、迁移或
控制器故障诊断时加载。当前阶段用不到的 CNKI、数据、方法、评审和渲染规则不进入上下文。

operation 级计划只在 execution 从 design v4/execution v3 投影工作项、依赖、失败路线和
`researcher_dispatch`。`protocol compile|validate`、`next` 和 plan 均只读；显式 render 也只刷新派生视图。

## 4. 状态与动作一致性

`status`、`gate`、`plan`、阶段锁与 `recover-lock` 的动作语义以 `workflow-playbook.md` 阶段 0 与 `SKILL.md` §3 为正本。本文只保留架构约束：只读动作不写入，任何写入动作只能在最早失败阶段运行，锁只在显式确认且内容未漂移时恢复。

## 5. 唯一事实与身份链

来源、批判综合、设计、执行分别只以 `literature_registry.json`、`literature_analysis.json`、
`research_design.json`、`method_execution.json` 为机器事实。材料事实由
`research_material_registry.json` 保存，候选最小可行证据由 `research_feasibility.json` 保存；
二者不是新的阶段。

所有正文主张沿 Source—Claim—Evidence—Design—Execution—Artifact 回溯。执行 v3 存在时，
build、ProsePacket 与复现只消费 accepted action、通过诊断、result/Artifact 双向闭合且允许当前
Claim 用途的 canonical 下游资格投影。active v3 校验失败时资格为空，不回退到字符串 ID 或旧数字清单。

定量数据准备只在定量／计算／混合研究或用户明确要求时触发。它比较本地、公开下载、API、注册、
申请、机构和商业路线，核验元数据与真实样本，但不维护跨项目 SQLite 目录、数据资产快照、变量匹配器、
公共机会 starter 或候选数据矩阵。真实文件／查询结果、字段、范围、许可、变异和 SHA 仍必须在设计与
执行中兑现。

## 6. 全文论证与 Prose firewall

`avereth_core/build/manuscript_compiler.py` 是 build 内部的全文论证编译器。它从 build 前 canonical
事实编译 `avereth-manuscript-contract/v1` 与 Section/Move MIR；MIR 是派生投影，不是第九阶段、
科学权威、receipt 或 Writer 输入。

上游权威、合同或规范稿变化传播 stale closure。每个 stale Move 必须绑定当前 packet、Writer draft、
Clarity draft/ledger、semantic dispatch/assurance 与真实进入规范稿的唯一输出。首次 baseline 在覆盖旧视图前
生成带原／替换 SHA 的可恢复 archive。

逐单元正文的事实只经 `avereth-prose-packet/v2`：传递当前 Claim、最小证据内容与作用、warrant、必要边界和
reader update；状态、失败项、完整证据库、评审意见、回复语言、数据获取日志和未选数据源不得进入。

Commonplace 按 `commonplace-writing.md` 生成 sibling 语言包，只含当前 Move 的局部原文和修辞拆解。
新建全文与实质修订任务显式采用 `prose_conditioning=auto`，按 Move 使用合格范例；检索缺口记录后可沿单包证据路径写作，锁定文本保持逐字路径。旧配置缺省和 `none` 不变，`commonplace` 保留严格双包行为。
Bank／phraseology 是语言派生视图，不拥有科学事实。Writer 双包输入须有显式配置及当前身份绑定；检索与缺口记录保留在控制侧，不能把来源、借用或语义失败转换为范例缺口。
借用检查重算两稿，文件闭包进入现有 receipt。Clarity 与语义评审保持其既有事实输入边界。

## 7. 多代理按风险与审计触发

普通研究默认单一主代理。研究者协作只服从 design/operation risk router 的
`single|isolated_multi` 决定；只有真实多运行任务才封存独立首轮输出、重算一致性并按分歧仲裁。

正式 isolated review 是 audit 内部动作，不是普通写作前置，也不是第二完成权威；三评审的信息流、独立性判据与 assurance/findings/resolution 版本以 `engine/reviewer-audit.md` 与 `cnki-review-assurance-v2` schema 为正本。revision plan 只计算最早回退阶段，不能直接修改上游。

Scout 的可选公开发现通道见 [delegation.md](delegation.md)。只读 plan 给出派发与不派发理由；
执行研究者决策引用原 `researcher_dispatch`，不能重算或削弱所需运行数。
公开搜索由主线程受限桥接，严格隔离生成器继续拒绝所有工具调用。
候选接纳只生成派生线索，不能改写任何科学正本或阶段收据。

## 8. 收据与交付边界

audit receipt 绑定规范稿、承重来源／综合／设计／执行、学术检查、原始 reviewer outputs、assurance、
findings/resolution 与动作实现；output 从该 path+SHA 单向渲染，绑定候选、视觉 QA、守卫、交付和清单。

output 的两次 gate、`OUTPUT.QA_REQUIRED` 停点与逐页视觉 QA 纪律见 `workflow-playbook.md` 阶段 7；规范稿、audit、候选或预览变化都使 QA 失效。

旧配置、工件与收据只经 `avereth_core/legacy` 显式 dry-run/apply/rollback 迁移或作为历史证据读取。
不得为 Lean Core 再创建兼容状态、迁移权威或上层 orchestrator。
