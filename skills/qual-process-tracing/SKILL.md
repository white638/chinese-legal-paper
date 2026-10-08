---
name: qual-process-tracing
description: 过程追踪 process tracing 操作技能（可执行）：单/少案例的因果机制分析。把 Collier 四类诊断检验（风向草/箍圈/冒烟枪/双重决定性）与 Beach & Pedersen 变体选择落成"时间线→机制拆解→假设与对弈→证据检验→评估"协议，并用 scripts/ptrace.py（仅标准库）按非对称推断规则自动判定假设状态、做形式化贝叶斯更新。Use when the user does 过程追踪、因果机制分析、单案例/少案例因果推断、机制检验、案例内推断、within-case。Trigger on 过程追踪、process tracing、因果机制、机制检验、冒烟枪、箍圈检验、smoking gun、hoop test、案例内推断、贝叶斯过程追踪、关键案例机制。属于 empirical-research 编排层的定性分支之一。
---

# Qual-Process-Tracing：过程追踪

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `empirical-research` 或 `cnki-paper` 实证分支子技能使用时，先读取 `empirical-research/references/{{METHOD_ADAPTER_FILE}}`；若工作流由 `cnki-paper` 发起，也读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 并服从 `cnki-paper` 控制器的 `avereth.py gate --stage <stage>`。本技能产出的时间线、机制图、焦点/对弈假设、证据账本、检验类型判定和推断摘要必须落到 `paper_rewriting_output\empirical\` 或父工作流指定目录；未登记来源、检验类型和非对称推断规则的案例证据不得回写正文。

`empirical-research` 定性分支。面向**单/少案例的因果机制**："X 如何（通过什么环节）导致 Y"。
做强**案例内（within-case）**推断，区别于跨案例相关。证据出处见
`empirical-research/references/qual-methods-evidence.md`。

## 协议

1. **时间线/叙事先行**。先把事件序列做扎实描述——"诊断性证据的判定核心依赖先验知识"，
   描述是因果推断之基。
2. **拆解因果机制**为可检验的环节（实体+活动的链条）：X →〔环节1〕→〔环节2〕→ Y。
   每个环节要能落到"若机制为真，应观察到什么/不应观察到什么"。
3. **列焦点假设 + 对弈假设**。过程追踪的力量在于用证据**消除对弈解释**。
4. **对每条预期证据指定检验类型**（据"通过对肯定推断是否必要/充分"）：

   | 检验 | 必要? | 充分? | 通过 | 不通过 |
   |---|---|---|---|---|
   | 风向草 straw | 否 | 否 | 略支持 | 略弱（皆不决定） |
   | 箍圈 hoop | 是 | 否 | 存活，**不能确证** | **剔除焦点假设（证伪）** |
   | 冒烟枪 smoking-gun | 否 | 是 | **确证**、实质削弱对弈 | 不能拒绝 |
   | 双重决定性 doubly-decisive | 是 | 是 | 确证并消除对弈 | 剔除 |

   **通过与不通过必须按检验类型区别对待**（非对称）：箍圈靠"不通过"杀假设，冒烟枪靠"通过"立假设。
5. **收集证据、判定、评估**：每个假设是被剔除 / 确证 / 仅存活？对弈假设削弱到何种程度？
6. **（可选）形式化贝叶斯**：对关键证据给出似然比 LR=P(E|H)/P(E|¬H)，顺序更新对"机制存在"的置信度。
   ⚠ 四检验是**原型贝叶斯**；正式贝叶斯化（Fairfield & Charman 对数似然比 / Bennett / Humphreys &
   Jacobs）是 2011 后的发展——**分层报告**，勿混为一谈。

## 变体选择（Beach & Pedersen）

动手前定变体（由分析目标驱动）：**理论检验**（已有理论，检验机制是否在案例中运作）、
**理论建构**（从案例归纳机制）、**解释结果**（穷尽解释某一重要结果，常组合多机制）、
**理论修订**（2nd 版新增）。变体决定朝向理论还是案例、做何种推断、能否嵌入混合方法。

## 可执行工具 `scripts/ptrace.py`（仅标准库）

```bash
python ptrace.py tests                                 # 四检验参考表
python ptrace.py classify --test hoop --passed false   # 单条证据推断含义（→ 剔除）
python ptrace.py assess ledger.csv                     # 证据账本→逐假设状态（剔除/确证/存活/矛盾）
python ptrace.py bayes --prior 0.3 --lr 4,0.5,8        # 形式化贝叶斯顺序更新
```

证据账本 CSV 列：`id,hypothesis,test,passed,note`（test∈straw/hoop/smoking_gun/doubly_decisive，
中文别名亦可；passed∈通过/不通过/true/false）。工具按非对称规则判定，并标记"矛盾"（同一假设既被
箍圈剔除又被冒烟枪确证→须复查）。**20 项单测**核验四检验推断规则，见 `test_ptrace.py`。

## 好的过程追踪 = 

证据按检验类型分级、认真对待对弈假设、机制环节明确可检验、诊断性判断说明其先验依据、
对"通过/不通过"作非对称解读、保留可追溯的证据-环节映射。

## 衔接

- 机制拆解、假设表、证据-检验映射全程 `repro_pack.py` 留痕（`decision` 记检验类型指定的理由，
  代表性证据可追溯到史料/访谈定位）。
- 混合方法：过程追踪常与定量（quant-causal-inference 的 DID/IV）三角验证——定量定"有无效应"，
  过程追踪定"经由何种机制"。整合报告交 `cnki-paper` build 阶段。
- 中文语境：过程追踪在中国政治/政策过程研究中应用渐广；史料/档案/访谈的证据分级与透明呈现
  （DA-RT/主动引用，见 evidence 文档"框架指针"）须结合目标期刊惯例。
