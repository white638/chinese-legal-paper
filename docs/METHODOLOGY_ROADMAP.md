# Artifact-Verified Methodology Roadmap

## 目标

Avereth 的方法升级不再以“又增加了多少方法名称”为目标，而是把设计声明绑定到真实
数据、诊断结果和可复算工件：系统既要知道研究者声明打算做什么，也要核对实际执行是否
与声明一致、结果是否足以承载目标推断。

主链保持不变：

```text
intake → acquisition → research → design → execution → build → audit → output
```

不增加第九阶段，不创建竞争状态机，不把 profile、validator 或期刊 pack 变成新的完成
权威。`cnki-paper` 继续拥有阶段与完成语义，`empirical-research` 拥有方法合同，专用 pack
只提供合同投影和检查项。

## 目标链

```text
Research Question
  → Claim / Estimand / Mechanism
  → Core Method Family
  → Typed Method Contract
  → Frozen Data and Diagnostic Artifacts
  → Method-Specific Validator
  → Observed Inference Ceiling
  → Claim–Evidence–Artifact Graph
  → Manuscript
```

设计合同是计划；`method_execution.json` 是实际执行记录；哈希工件是可复核事实。三者
不能互相冒充。

## 实施切片

| 切片 | 交付 | 发布门 |
|---|---|---|
| 方法评测接入 CI | empirical contract、research-design、research-methods 与 registry coverage | 任一硬失败阻塞发布 |
| 类型化方法合同 | method family schema、artifact refs、validator dispatch、兼容迁移 | 自由文本不能替代承重工件 |
| 公开文本政治学 pack | 七个内部 profile、机器检查清单、合同 schema、对抗 fixtures | 不新增 Skill/阶段/Claim 注册表 |
| 测量有效性 | 冻结语料、金标准、类别指标、误判与敏感性工件、LLM 运行身份 | 指标可从预测与标签复算 |
| 推断与稳健性 | estimand、反事实、处理/分析/聚类单位、识别诊断、误差传播 | 诊断失败必须收窄推断 |
| 可逆研究决策 | 候选组合、软聚焦、对抗撞题、七维裁决、用户放行与版本挑战 | 只有 cleared 问题版本可进入 design |
| 期刊 overlay 收敛 | 报告、透明度、呈现与投稿要求引用核心合同 | 期刊 pack 不得拥有 schema/validator/推断权威 |

这些切片可以增量合入，但后一个切片不得复制前一个切片的权威数据。例如公开文本
profile 只能引用核心 Claim 能力；期刊 overlay 只能引用核心 method contract。

## 明确排除

本路线不实施三个“黄金项目”，也不创建对应 `examples/` 目录或空占位：

- `white-paper-traceability`
- `trump-congress-agenda`
- `hainan-rcep-compatibility`

真实项目材料、版权/权限、长期数据维护和研究者判断不能用占位工件冒充。方法层是否发布
由合同、对抗 fixture、复算检查和回归证据决定，不以这三个项目为门槛。

## 方法层 Definition of Done

1. 承重诊断由结构化、哈希绑定工件提供，解释性文字不能替代它。
2. 正文主要数字能够从登记的数据或模型输出重新生成。
3. 每个 method family/profile 至少有合法、边界和推断越界测试，并有至少两个实际执行、
   命中该方法族语义 validator 错误码的非通用典型错误；缺字段、关键词重复等通用模板不计
   入这个最低数。
4. 测量开发数据与最终推断数据可核对地区分；重叠只能明确降级为探索性。
5. 机器检查结构、内部一致性、复算性和推断越界，不产生跨项目统一方法质量分数。
6. 因果效应和因果机制分别绑定专属核心合同；limitation 段落不能修复失败的识别合同。
7. 期刊包只能增加报告、透明度、呈现和投稿要求，不能重写科学有效性的核心定义。

## 迁移原则

旧 `research_design/v3` 与 `method_execution/v2` 继续可读。核心合同采用显式
`method_contract_schema` 与 `method_contract`；内部 profile 另用
`supplemental_profile_id` 与 `supplemental_contract`，两者都通过核心注册表的同一 loader
解析。`artifact_refs` 只登记稳定 Artifact ID；旧自由文本只作为解释或
迁移输入，不自动升级为验证通过。未来 schema 一律 fail closed；迁移必须保留旧文件、
记录版本和哈希，并允许回滚。
