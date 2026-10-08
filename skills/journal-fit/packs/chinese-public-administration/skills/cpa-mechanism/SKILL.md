---
name: cpa-mechanism
description: 用于在《中国行政管理》稿件中呈现 empirical-research 已验证的机制合同与证据。本 venue overlay 只负责公共管理语境解释和版面位置，不选择中介模型、过程追踪检验、阈值或修复路径。
---

# 机制证据呈现（cpa-mechanism）

## 权威边界

机制主张、竞争机制、可观察痕迹、时间顺序、证据诊断力、来源独立性、统计目标、验证器和推断上限
均由 empirical-research 核心 family/typed contract 决定。缺少记录时退回核心，不得用“本刊偏好”
补选中介、调节、检验或案例材料。

## 应报告的核心事实

- 核心合同 ID/修订、机制 claim ID、最强竞争机制、observed inference ceiling。
- 定量机制路线：登记的 estimand/target、时间顺序/反事实、假设和诊断 Artifact ID、处置与
  `CORE.INFERENCE.SENSITIVITY_BINDING` 结果。
- 过程机制路线：`process-tracing/v1` 的 predicted traces、诊断证据矩阵、来源独立性、负面/缺失
  痕迹 Artifact ID 和处置。
- 任何核心诊断失败后的 narrowed/withdrawn 处置；不能靠 limitation 补救。

## 《中国行政管理》呈现层

正文用公共管理语言说明“谁在何种制度条件下通过什么过程产生何种结果”，并把每一机制节点定位到
核心 Artifact。完整矩阵、来源链、模型身份、失败和偏离放入附录或透明度材料。审稿人要求新检验时，
先形成核心合同修订并重新验证，回复信只报告该结果。

## 反模式

- 把中介显著、调节显著或一段访谈直接写成机制成立
- 在 venue 层指定统计中介方法或过程追踪检验
- 没有竞争机制、来源独立性和负面证据仍宣称 `causal_mechanism`

## 输出格式

```text
【核心机制合同】id + revision + claim ID
【竞争机制】core record
【诊断证据】Artifact ID + disposition
【来源/时间顺序】core records
【推断上限】retained / narrowed / withdrawn
【正文/附录位置】机制解释 + 完整工件定位
【下一步】cpa-heterogeneity（仅做 venue 呈现）
```
