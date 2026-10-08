---
name: cpa-heterogeneity
description: 用于在《中国行政管理》稿件中呈现 empirical-research 已登记的异质性、条件性或组态结果。本 venue overlay 不选择分组、交互、差异检验、QCA 阈值、显著性标准或修复路径。
---

# 异质性与条件性呈现（cpa-heterogeneity）

## 权威边界

子组/条件、理论依据、比较对象、估计目标、multiplicity family、分析程序、诊断、偏离和推断上限
均由 empirical-research 核心合同决定。本期刊包只能解释和呈现登记结果；不能在看到结果后新增切分，
也不能规定统一的差异检验或数值阈值。

## 应报告的核心事实

- 核心合同 ID/修订、主 claim 与条件性 claim 的关系、登记时间和理论映射。
- 子组/条件、比较对象与 target/estimand 身份，以及 measurement/dependence Artifact IDs。
- `CORE.INFERENCE.MULTIPLICITY_PLAN`、`CORE.INFERENCE.SENSITIVITY_BINDING` 和任何偏离记录。
- 每项结果的 Artifact ID、disposition 与 observed inference ceiling；探索性结果保留 core 标签。
- QCA 或比较案例路线只报告核心登记的条件、校准/比较身份、矛盾/稳健性和 case-return 工件；
  不把组态改写为净效应。

## 《中国行政管理》呈现层

正文按行政层级、治理情境或制度条件解释核心登记结果的公共管理含义，但不重新定义分析。完整条件
清单、比较、multiplicity、失败、偏离和敏感性工件进入附录。审稿人要求新切分时，应先回到核心
合同登记并重新验证，再在回复信中报告其探索性/确认性身份和推断处置。

## 反模式

- 看到结果后按地区、层级或人群反复切分并挑选显著项
- 用期刊偏好指定差异检验、交互形式、QCA 校准或阈值
- 只报告组内显著/不显著，不报告核心比较目标和 multiplicity disposition
- 把探索性异质性写成预设机制证据

## 输出格式

```text
【核心合同】id + revision + claim IDs
【登记条件/子组】core records + theoretical mapping
【比较目标】target/estimand identity
【Multiplicity/diagnostics】requirement + Artifact IDs + disposition
【偏离】registered / exploratory + timestamp
【推断上限】retained / narrowed / withdrawn
【正文/附录位置】公共管理解释 + 完整工件定位
```
