---
name: cpa-identification
description: 用于把 empirical-research 已验证的研究设计呈现在《中国行政管理》稿件中。本 venue overlay 只规定中文呈现、透明度与审稿回应位置，不选择方法、估计器、阈值、诊断或修复路径。
---

# 研究设计呈现（cpa-identification）

## 权威边界

研究问题、claim capability、estimand、反事实、识别假设、方法合同、诊断、执行器和推断上限
均由 `empirical-research` 核心注册表与工件链决定。本期刊包不能据稿件类型另选方法，也不能在
回复信中补造验证。缺少核心记录时，退回 empirical-research，而不是在本技能内给出替代方案。

## 触发时机

- 把已验证的定量、定性、规范或混合研究设计写入《中国行政管理》稿件
- 决定哪些核心合同事实放正文、附录或透明度材料
- 回应审稿人对识别、测量、案例选择、机制或推断边界的疑问

## 各方法模式只报告核心记录

### 定量与因果路线

- 报告 `CORE.CAUSAL.ESTIMAND_BINDING` 中登记的估计对象、单位、反事实和主张边界，以及
  `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS` 的 Artifact ID、结果与推断处置。
- 面板或事件时序设计报告 `CORE.PANEL.STAGGERED_DESIGN` 的批次、比较组、时间窗口、诊断工件
  与 observed inference ceiling；本期刊包不指定估计器或修复方法。
- 报告 `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`、`CORE.INFERENCE.MULTIPLICITY_PLAN` 和
  `CORE.INFERENCE.SENSITIVITY_BINDING` 的登记事实与失败结果。

### 调查、测量与计算路线

- 报告核心抽样、分析单位、测量构念、验证工件、误差/稳定性、缺失与敏感性处置。
- 计算或随机步骤报告 `CORE.REPRO.STOCHASTIC_IDENTITY`；不得在 venue 层另设统一信效度阈值。

### 案例、过程追踪、规范与混合路线

- 报告核心登记的案例/材料选择理由、范围、竞争解释、诊断证据矩阵、claim-evidence-artifact
  链和 observed inference ceiling；不得在此定义期刊专属检验。
- 规范路线报告核心概念、价值前提、论证链及允许/禁止解释；混合路线报告核心登记的各分支身份、
  整合点、跨分支证据图与合并后的推断边界。

## 《中国行政管理》呈现层

正文优先让一般公共管理读者看到：研究问题、核心合同 ID/修订、目标量或主张、最关键诊断结果、
实质含义与推断上限。完整合同、哈希工件、失败诊断和偏离登记放入附录或透明度材料，并在正文给出
准确定位。审稿人要求改变方法时，应记录为核心合同修订并重新验证，回复信只报告该处置。

## 审稿回应

| 审稿疑问 | venue 层应呈现的核心事实 |
|---|---|
| “因果主张是否成立” | estimand/反事实、假设诊断 Artifact ID、结果与 observed inference ceiling |
| “时序或比较组是否可靠” | `CORE.PANEL.STAGGERED_DESIGN` 登记与诊断处置 |
| “标准误/样本独立性是否一致” | `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` 的单位和不确定性记录 |
| “测量是否可信” | 核心测量验证、误差分析、敏感性 Artifact ID 与处置 |
| “案例或机制是否有选择性” | 核心选择理由、竞争机制、诊断证据矩阵与负面证据 |

## 反模式

- 用期刊偏好替代 empirical-research 的方法合同或推断上限
- 在回复信中临时选择新的估计器、诊断、阈值或案例逻辑
- 只写“已做稳健性检验”，不链接核心 Artifact ID、结果和失败处置
- 用 limitation 段落掩盖核心诊断失败

## 输出格式

```text
【核心方法合同】id + revision
【登记目标】estimand / target / mechanism / normative claim
【核心诊断】requirement ID + Artifact ID + PASS/FAIL/NEEDS-REVIEW
【推断处置】retained / narrowed / withdrawn + observed inference ceiling
【正文呈现】最关键事实与实质解释
【附录/透明度】完整合同、工件、失败与偏离定位
【下一步】cpa-mechanism（仅做 venue 呈现，不改变核心方法）
```
