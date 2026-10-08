# Scientific Validity Model

## 核心命题

“字段已填写”不等于“方法已成立”。Avereth 将科学有效性拆成四类不同问题，每类由不同
证据回答：

| 层次 | 问题 | 主要证据 |
|---|---|---|
| 合同完整性 | 是否明确声明问题、构念、单位、材料、比较基础与推断目标 | 类型化 design contract |
| 执行真实性 | 是否真的按确认设计执行，是否登记偏离、负面结果与环境 | `method_execution.json` 与日志 |
| 测量有效性 | 观测或模型输出是否测到声称的构念 | 冻结参照、证据定位、预测、类别指标、误判和敏感性工件 |
| 推断有效性 | 比较、反事实、机制痕迹或组态结果是否支持目标 Claim | 识别/机制诊断与哈希结果工件 |

四层不能折算成一个总分。合同完整但测量失败，不能因复现做得好而补偿；模型指标漂亮但
比较基础不成立，也不能获得因果语言。

## Declared 与 observed inference ceiling

核心方法注册表给出 method family 在满足条件时最多可以支持的 Claim 类型，这是
`declared ceiling`。实际项目还必须经过方法专用 validator。验证结果形成
`observed inference ceiling`：

```text
observed ceiling
  = core family capability
  ∩ confirmed design route
  ∩ actually executed diagnostics
  ∩ passed measurement and identification evidence
```

这里的交集是权限收窄，不是数值打分。validator 只能保持或降低上限，不能因为期刊偏好、
写作措辞、显著性或单个高指标扩大核心能力。

典型收窄包括：

- 训练/验证泄漏：独立验证主张降级，必要时只保留探索性描述；
- 文本处理发生在文件层但按句子计算独立样本：推断单位不成立，阻止相应效应语言；
- 过程追踪缺少竞争机制或来源独立性：不能通过 `causal_mechanism`；
- QCA 结果被改写为变量平均净效应：阻止该 Claim，而不是在局限段补救；
- 识别诊断失败：保留结果工件，但把正文主张收窄到诊断允许的层级。

## Claim–Evidence–Artifact 图

每个承重主张至少有以下可追踪关系：

```text
Claim ID
  → Evidence ID(s)
  → Artifact path + SHA-256
  → producing route / command / environment
  → validator result
  → observed inference ceiling
```

正文数字不得只保存在稿件。表图、模型输出和测量指标均从工件生成；手工转录的数字在进入
正文前必须能回指可复算来源。来源身份、文献判断、研究设计和实际执行仍分别由现有唯一真相
文件管理，Claim 图只引用这些事实，不复制它们。

## Validator 的权限

validator 可以：

- 在 design 阶段检查类型化合同的嵌套 required/type/enum/const，在 execution 阶段检查文件
  存在、SHA-256、完整 schema、行列和身份集合；
- 检查训练/验证/估计集合是否重叠；
- 从标签与预测重算 confusion matrix、precision、recall、F1 等；
- 核对样本数、风险集、事件顺序、删失、聚类和处理层级；
- 检查来源传播链、同源证据、时间方向与 Claim—工件链接；
- 在条件不成立时发出稳定错误码并收窄推断权限。

validator 不可以：

- 设定所有项目通用的 F1、样本量、p 值、饱和或一致性阈值；
- 判断理论问题是否重要、构念是否值得测量或案例是否有理论价值；
- 用“通过概率”覆盖缺失工件或逻辑矛盾；
- 允许同一运行自我验证，或把模型参照一致率冒充外部准确率；
- 让期刊 pack 扩大核心 Claim 能力。

## 验证与检查点语义

- `PASS`：结构和可复核事实满足当前合同；不代表理论价值已经得到证明。
- `FAIL`：存在可复核的合同、工件、内部一致性或推断越界问题。
- `BLOCKED`：缺少权限、材料、凭证、运行环境或必要的解释性处置。
- `NOT_APPLICABLE`：该 profile 不适用于当前确认路线，且不产生写入。

`needs-independent-review` 是合同字段，不是第五个公开状态。确定性检查完整但解释性证据不足
时，不能签发 `PASS`；应由隔离上下文的研究运行补齐来源、理由和分歧处置，再重新验证。

任何结果都保留负面发现与偏离。失败的诊断是研究结果的一部分，不应通过删除文件或改写
limitation 被隐藏。
