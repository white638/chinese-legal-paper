---
name: socs-mechanism-social-process
description: 用于把 empirical-research 已验证的机制证据呈现为《社会学研究》读者可理解的社会过程。本 venue overlay 不选择中介模型、案例、过程追踪测试、编码规则、阈值或修复。
---

# 社会过程呈现（socs-mechanism-social-process）

## 权威边界

机制 claim、行动者/条件/序列、竞争机制、可观察痕迹、证据诊断力、来源独立性、测量和推断上限
由 empirical-research 核心 family/typed contract 决定。本技能只能解释这些记录的社会学意义。

## 应报告的核心事实

- 核心合同 ID/修订、mechanism claim ID、最强竞争机制和 observed inference ceiling。
- 定量机制路线的 target、时间/反事实假设、诊断与敏感性 Artifact IDs 和 dispositions。
- 质性/过程路线的 `process-tracing/v1` 预测痕迹、诊断证据矩阵、负面/缺失证据、来源独立性工件。
- claim–evidence–artifact 图中每个社会过程节点的证据定位，以及失败后的 narrowed/withdrawn 处置。

## 《社会学研究》呈现层

用“行动者—关系/制度条件—行动或互动—中间状态—结果—范围条件”的语言解释核心机制记录，
但不把一项统计中介、一个引文或一段时间线升级为机制证明。正文呈现决定性证据和竞争解释；完整
矩阵、来源链、失败和偏离放入附录。

## 反模式

- 由 venue 包指定中介/调节或过程追踪检验
- 只有系数或生动材料，没有核心 competing-mechanism 与诊断证据矩阵
- 省略负面、缺失或同源证据仍宣称 causal mechanism
- 用 limitation 段落补救核心诊断失败

## 输出格式

```text
【核心机制合同】id + revision + claim ID
【社会过程】actor → condition → action/interaction → intermediate state → outcome
【竞争机制】core record
【诊断证据】Artifact IDs + dispositions
【来源独立/负面证据】core records
【推断上限】retained / narrowed / withdrawn
【正文/附录位置】社会学解释 + 完整工件定位
```
