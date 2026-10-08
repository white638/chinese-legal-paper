---
name: qual-content-analysis
description: 内容分析操作技能（可执行）：政策文本/媒体语料/开放问答的系统编码——编码手册设计、归纳(Mayring)vs演绎编码、抽样与单位化、运行一致性或组间信度。用 scripts/reliability.py（仅标准库）算百分比一致、Cohen's κ、Scott's π、Krippendorff's α，并区分模型运行稳定性与实际人际编码信度。Use when the user does 内容分析、文本编码、编码手册、编码框架、一致性、Krippendorff α、Cohen kappa、政策文本分析、媒体内容分析、开放题编码。区别于 aers-thematic-analysis（反身性主题分析，解释取向）：本技能偏系统化/可量化编码。Trigger on 内容分析、content analysis、编码手册、codebook、编码框架、运行一致性、intercoder reliability、Krippendorff、kappa、Scott pi、信度系数、政策文本编码。属于 empirical-research 编排层的定性分支之一。
---

# Qual-Content-Analysis：内容分析（系统编码 + 信度）

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `empirical-research` 或 `cnki-paper` 实证分支子技能使用时，先读取 `empirical-research/references/{{METHOD_ADAPTER_FILE}}`；若工作流由 `cnki-paper` 发起，也读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 并服从 `cnki-paper` 控制器的 `avereth.py gate --stage <stage>`。本技能产出的抽样框、单位化规则、编码手册版本、试编码记录、信度报告、正式编码表和频次/交叉表必须落到 `paper_rewriting_output\empirical\` 或父工作流指定目录；未登记校正偶合信度或复现来源的编码结果不得回写正文。

`empirical-research` 定性分支。面向**政策文本、媒体语料、议案、开放问答**的系统化编码。
与 `aers-thematic-analysis`（Braun & Clarke 反身性主题分析，解释/归纳取向）互补：本技能偏
**系统化、可量化、强调可复核一致性**的内容分析（Krippendorff / Mayring）。证据出处见
`empirical-research/references/qual-methods-evidence.md`。

## 协议

**1. 抽样与单位化**
- 界定语料总体与抽样框（如某政策领域 2000–2024 全部中央文件）；记录纳入/排除标准。
- 定**编码单位**（记录单位 vs 语境单位）：是句、段、还是整篇？单位化规则要明确到可复制。

**2. 编码手册（codebook）设计**
- 每个类目：名称、定义、纳入标准、排除标准、典型例、边界例。**演绎**（理论先定类目，Mayring
  演绎式类目应用）或**归纳**（Mayring 归纳式类目发展：从语料中提炼，定抽象层级与修订规则）或
  混合。先在小样本试编码 → 修订手册 → 再正式编码。

**3. 一致性与参照验证（关键质量关）**
- **硬规则：不得单独用百分比一致**（受偶合膨胀、偏宽松，方法学界共识视为误导）。必须报告
  **校正偶合**的指数：Cohen's κ（2 列）、Scott's π（2 列）、**Krippendorff's α**（≥2 列、
  容缺失、可跨测量层级）。
- 模型研究运行之间的系数报告为 `run-consistency` / `stability`，同时登记 run/context、模型修订、
  提示词哈希和输出工件；它不等于准确率，也不替代冻结参照、证据定位和分歧处置。
- 若项目实际研究的是人际编码信度，可显式选 `intercoder-reliability`；Lombard 分层阈值只是该文献
  传统中的惯例，须论证而非自动 PASS。
- 父工作流按 `researcher-collaboration.md` 风险路由：正式独立编码至少由两个隔离 context 使用
  同一冻结单位规则与编码手册完成，首轮输出先封存再重算分歧；只有实际出现分歧时才交不同
  `Adjudicator`。参照集和留出标签必须隔离，任何同源输出或标签泄漏均不能作为一致性证据。
- 报告须给：**指数名 + 值 + 列数 + 单位数 + 指标语义**；一致性不足时修订手册、运行协议或参照设计。

**4. 正式编码与分析**
- 验证证据满足当前用途后全量编码；类目频次/共现/交叉表；必要时与定量变量关联。

## 可执行工具 `scripts/reliability.py`（仅标准库）

CSV：首行=编码者名，每行=一个编码单位，单元格=类目，空=缺失。

```bash
python scripts/reliability.py data.csv                       # α + (两编码者时) %/κ/π
python scripts/reliability.py data.csv --coders 张,李        # 指定两列算 κ/π
python scripts/reliability.py data.csv --semantics intercoder-reliability  # 仅实际人际编码研究
```

实现并**单测**（手算值，见 `test_reliability.py`，11 项全过）：百分比一致、Cohen's κ、
Scott's π、Krippendorff's α（名义，重合矩阵法，≥2 编码者容缺失）。α 公式 1−Do/De 与
Krippendorff 一致；工具会标注 Lombard 分层提示并**显式警告不可单用百分比一致**。
序数/区间 α 与大规模计算可用 R 的 `irr`/`icr` 包或 Python `krippendorff` 库；本工具覆盖中文
内容分析常用的名义类目一致性报告。

## 常见错误

- 只报百分比一致而无校正偶合系数。
- 把模型运行一致性写成准确率或人际编码信度。
- 编码手册定义模糊、无边界例 → 信度低却归咎编码者。
- 把 .80 当硬门槛而不结合指数保守性与研究阶段论证。
- 单位化规则不可复制（别人无法切出同样的编码单位）。

## 衔接

- 编码手册版本、试编码信度、正式信度全程 `repro_pack.py` 留痕（`decision` 记手册修订理由，
  落稿 α/κ 值写入 `method_execution.json` 的哈希工件定位，`check` 审计）。代表性引用须可追溯到原文位置（语料编号+定位）。
- 解释取向的主题归纳走 `aers-thematic-analysis`；大规模文本统计走 [Phase 3] `text-as-data-cn`。
- 结果叙事交 `cnki-paper` build 阶段；类目频次/交叉表过 `docx_fixup --tables`。
- 中文语境：政策文本内容分析在中文公共管理/传播学常见；目标期刊对信度报告的期待（是否必报 α、
  可接受阈值）须自行核证（见 evidence 文档"未核实"项）。
