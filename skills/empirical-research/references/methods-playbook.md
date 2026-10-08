# 实证方法选择与引擎速查

## 一、方法选择决策树

```
研究问题
  │
  ├─ 要估计"X 对 Y 的因果效应"（有可比的处理/对照、变异来源）
  │     → 定量因果推断（quant-causal-inference）
  │        ├─ 政策/制度在某时点对部分单位生效，有前后&处理/对照 → DID / 事件研究
  │        ├─ 某连续变量过阈值才获处理（分数线/人口规模线/任期线） → 断点回归 RDD
  │        ├─ 有外生冲击/工具，但处理非随机 → 工具变量 IV
  │        ├─ 选择在可观测变量上（无好工具/断点） → PSM / 加权 + 敏感性(E值)
  │        └─ 单一处理单位 + 长前期 + 对照池 → 合成控制 SCM
  │
  ├─ 要回答"如何/为何"、机制与过程、单/少案例深描
  │     → 定性
  │        ├─ 单/少案例的因果机制、时序链条 → qual-process-tracing（过程追踪）
  │        ├─ 中等 N 案例、条件组合（哪些条件组合导致结果） → qual-qca（QCA/fsQCA）
  │        ├─ 访谈/焦点小组/开放问答，找主题模式 → aers-thematic-analysis（主题分析）
  │        └─ 政策文本/媒体语料的系统编码与信度 → qual-content-analysis（内容分析）
  │
  ├─ 大规模文本即数据（政策文本、舆情、议案）
  │     → text-as-data-cn（词频/TF-IDF/共现网络可执行；主题模型 LDA/STM 指引；验证优先）
  │
  ├─ 要系统梳理某领域全部证据
  │     → aers-prisma-slr（PRISMA 2020 系统综述）
  │
  └─ 定量 + 定性互补（解释机制 / 三角验证）
        → 混合方法：先各自按上面跑，再 [Phase 4] 做整合叙事
```

**选择原则**：方法服从问题，不为用方法而用方法；定性定量无高下，**关键看识别/推断是否可信**。
人文社科很多好问题是"如何/为何"，定性或混合往往比硬套回归更诚实。

**设计三经验法则**（判准全文见 `cnki-paper/references/three-questions-standard.md` §6）：

1. **变异性必需**——常量不能单独支撑模式或因果结论；单案例须内含子案例/跨时段观察值
   或显式反事实，复杂单位（政府/政党/改革）不豁免此要求。
2. **估效应 → 大样本**——要确定 X 是否引起 Y、估计效应的形式与强度（线性/阈值/U 型）、
   处理调节与混淆，走定量分支。
3. **追机制 → 比较个案**——要逐环节证明原因如何产生结果，走过程追踪/比较个案分支；
   机制未被阐明和证明的因果理论可以被拒绝。个案研究另守**单位同质性**：
   语义对等≠功能对等（不同时空的"同名"制度/政党未必可比），防止概念过度延伸。

## 二、引擎速查

| 分支 | 技能 | 形态 | 一句话 |
|---|---|---|---|
| 定量 | `quant-causal-inference`（原创） | 可执行 | 驱动 statspai(MIT) 跑 DID/RDD/IV/PSM/SCM，产 Word/Excel/LaTeX 表；附 R/Stata 路径 |
| 定性·主题 | `aers-thematic-analysis`（vendored MIT） | 可执行 | Braun & Clarke 六阶段编码，产 Word + 主题图 |
| 综述 | `aers-prisma-slr`（vendored MIT） | 可执行 | PRISMA 2020 27 项清单 + 流程图（引用改走 GB/T 7714） |
| 复现 | `scripts/repro_pack.py`（原创，仅标准库） | 可执行 | 数据溯源/样本留痕/数字登记/环境冻结/复现审计 |
| 定性·过程追踪 | `qual-process-tracing`（原创，含 `ptrace.py`） | 可执行 | Collier 四检验非对称推断+证据账本+形式化贝叶斯 |
| 定性·QCA | `qual-qca`（原创，含 `qca_check.py`） | 可执行 | 一致性/覆盖度/PRI/RoN 核算+惯例对照+ESA 争议 |
| 定性·内容分析 | `qual-content-analysis`（原创，含 `reliability.py`） | 可执行 | 编码手册+Cohen κ/Scott π/Krippendorff α 信度 |
| 文本即数据 | `text-as-data-cn`（原创，含 `textstat.py`） | 可执行 | 词频/TF-IDF/共现网络（标准库）；LDA/STM 指引；验证优先 |

> 实证层四分支（定量 + 定性 + 文本 + 复现）**全部落地**：各方法引擎均带仅标准库的可执行脚本 + 单测
> （合计 56 项：repro 10 + qca 12 + 信度 11 + 过程追踪 20 + 文本 13 — 另 quant 由 statspai 实测）。
> 方法论证据见各技能 references（`qual-methods-evidence.md`、`text-as-data-evidence.md`，均 deep-research
> 三票核验，未核证项明确标注）。**绝不把未核证项当事实**（套件铁律）。

## 三、回写论文的衔接（实证产出 → 成稿）

| 实证产出 | 交给 | 怎么接 |
|---|---|---|
| 回归表/描述统计表（docx） | `cnki-paper/scripts/docx_fixup/docx_normalize.py --tables` | 规整为三线表；彩图 `--grayscale` |
| 每个落稿数字（系数/N/p） | `method_execution.json` + `scripts/repro_pack.py check` | 登记 Evidence、哈希 Artifact、locator 与重现命令；安全复算不过不投稿 |
| 结果叙事/机制讨论 | `cnki-paper` build 阶段 | 把表读成段落理据，进逐段蓝图 |
| 引文/数据出处页码 | `page-evidence` | 专著/原典页码分级证据；【VERIFY】清单 |
| 定性代表性引用 | （编码审计轨迹） | 标注访谈号/原文位置，可追溯到转录 |

## 四、与 cnki-paper 主线的关系

实证选题应先过 `cnki-paper` 阶段 2（文献实采）站稳"别人做到哪"，再来本层做研究；
分析完回 `cnki-paper` 八状态写作链成稿、`docx_fixup` 出 Word。即：
**查文献(cnki-paper) → 做研究(empirical-research) → 写成稿(cnki-paper + docx_fixup)**。
