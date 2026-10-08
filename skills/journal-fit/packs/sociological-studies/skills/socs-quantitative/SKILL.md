---
name: socs-quantitative
description: 用于在《社会学研究》稿件中呈现 empirical-research 已验证的定量合同和工件。本 venue overlay 只负责社会学解释与版面位置，不选择回归、多层、事件史、序列模型、诊断、阈值或修复。
---

# 定量结果呈现（socs-quantitative）

## 权威边界

target/estimand、单位、变量/测量、比较/反事实、模型身份、缺失、依赖、诊断、敏感性和推断上限
均由 empirical-research 核心合同决定。本技能不能按本刊偏好选择方法或在看到结果后补造稳健性。

## 应报告的核心事实

- 核心 family/profile、contract revision、claim ID、target/estimand 和 observed inference ceiling。
- 测量、样本、missingness、时间/事件、comparison/counterfactual、dependence 和 uncertainty 记录。
- `CORE.CAUSAL.ESTIMAND_BINDING`、`CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`、
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`、`CORE.INFERENCE.MULTIPLICITY_PLAN` 与
  `CORE.INFERENCE.SENSITIVITY_BINDING` 中适用的 Artifact ID 和处置。
- 核心执行工件生成的主要数量、区间、失败诊断、偏离和探索性标签。

## 《社会学研究》呈现层

把核心数量翻译为社会分层、制度、组织、家庭或行动者过程的实质含义，并说明它能支持何种社会学
主张。正文保留决定性诊断和推断上限；完整合同、工件、失败、偏离和复算命令放附录/透明度材料。

## 反模式

- 由期刊包给研究问题匹配具体模型或估计器
- 只报告显著性，不定位 core target、Artifact 和 ceiling
- 把相关路线结果写成因果或机制结论
- 在回复信中临时换模型而不修订并重验核心合同

## 输出格式

```text
【核心合同】family/profile + revision + claim ID
【目标与单位】core target/estimand + analysis/independence units
【主要结果】Artifact ID + magnitude/uncertainty
【核心诊断】requirement IDs + dispositions
【推断上限】retained / narrowed / withdrawn
【社会学解释】正文句 + 附录工件定位
【下一步】socs-mechanism-social-process（仅做 venue 呈现）
```
