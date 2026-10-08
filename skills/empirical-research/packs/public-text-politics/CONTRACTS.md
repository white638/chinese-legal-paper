# Public Text Politics Contracts

所有承重工件只引用执行合同中已登记的稳定 `Artifact ID`；真实路径与 SHA-256 仍由
`method_execution.json` 的 `runs[].artifacts` 单一登记，profile 不复制第二份身份表。自由文本可以解释
为什么这样设计，但不能替代 schema 要求的冻结输入、预测、诊断或敏感性工件。以下
合同是核心 method contract 的 profile 投影，不另建 Claim 能力表或推断上限表。
唯一 profile 绑定必须从核心注册表各合同的 `supplemental_profiles` 解析；`manifest.json`
只是资产清单。本目录的 supplemental schema 只收紧公开文本场景字段，不能直接声明
estimand、counterfactual、identification assumptions、Claim 类型、核心 schema 或 validator，
只能用 `*_ref` 引用核心合同，也不能扩大 Claim 能力。

## claim_measurement

分析单位固定登记为 claim，并明确构念定义、编码手册版本、冻结语料、来源扎根的参照、开发与
独立验证清单、类别级指标、误判分析和敏感性结果。每个研究运行登记独立的 run/context、模型
修订、提示词哈希和输出工件。系统复核集合重叠并从预测文件重算类别指标；模型研究者提交构念
意义、参照可信度和误差处置的逐项理由。内部模型参照只支持 `reference_agreement`，不支持
`external_accuracy`。

## semantic_alignment_and_reuse

分别冻结来源语料与候选语料，登记时间方向、对齐单位、表示方法、阈值网格、模板条款、
法律套话、共同第三方来源和翻译链。候选对与独立复核对必须落到工件。确定性检查核对来源早于
目标、阈值敏感性和共同来源标记；隔离上下文的模型研究者判断功能等价、借用与独立生成之间
哪种解释最合理，并登记证据与分歧处置。

## legislative_process

以 bill family 而非单个版本或句子作为基本风险集身份，登记家族去重规则、程序时间、
首次实质推进、竞争风险、届期删失、法律形式、时间变化协变量与聚类层级。机器检查家族
映射、事件排序和删失一致性；研究者判断何种程序动作在研究问题中构成“实质推进”并给出理由。

## institutional_grammar

每条制度语句至少拆为主体、规范词、行为、对象、条件、例外、执行机关和后果，并保存
编码规则、标注、分歧和验证工件。匹配类别必须保留完全一致、部分一致、功能等价、可并行、
程序缺口、实质冲突和无法判断。文本、法律、执行机制与治理能力兼容性分别报告；综合权重
只能作为敏感性分析，不能成为主结果。

## public_source_process_tracing

为每个机制节点登记理论预测、预期痕迹和证据诊断力，并至少登记一个最强竞争机制。证据
账本必须保存来源产生背景、传播链、独立性审计、缺失痕迹和公开记录沉默。机器检查链条和
重复来源；研究者判断某条痕迹在具体背景下是 straw-in-the-wind、hoop、smoking-gun 还是
doubly-decisive，以及公开记录沉默具有多大含义。

## discourse_network

观测记录固定为 `Actor–Claim–Position–Time–Source`，并分别保存行动者解析、主张测量、
立场测量、时窗与边构造工件。共词只可作为文本结构，不得直接替代政治行动者—主张—立场
网络。机器检查五元组、实体解析与网络依赖诊断；研究者判断行动者边界与联盟解释并绑定来源。

## text_in_causal_design

先登记文本在因果设计中的角色，再引用核心 estimand、反事实与识别诊断，不在本 profile
重写它们。合同显式区分处理层级、文本分析单位、有效样本单位、聚类层级、测量开发清单与
效应估计清单，并要求测量误差敏感性和哈希结果工件。若开发集与估计集重叠，只能登记为
`exploratory_only`；识别或测量诊断失败时必须收窄 observed inference ceiling。
