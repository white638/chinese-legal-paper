---
name: text-as-data-cn
description: 中文文本即数据/计算社会科学操作技能（可执行）：把政策文本、媒体语料、舆情、议案等大规模中文文本落成"语料构建→预处理/分词→表示→分析→验证→回写"流水线。核心 scripts/textstat.py（仅标准库）做词频/TF-IDF/关键词/共现网络，分词用 jieba（可选前端）；主题模型(LDA/STM)、词向量等重型分析指引到 gensim/sklearn/R。强调 Grimmer & Stewart "自动化文本方法必须验证"。Use when the user does 文本分析、文本即数据、计算社会科学、政策文本分析、舆情分析、词频、TF-IDF、关键词提取、共现网络、语义网络、主题模型、LDA、情感分析、词典法、文本标度。Trigger on 文本即数据、text as data、计算社会科学、政策文本、舆情、词频、TF-IDF、关键词、共现网络、语义网络、主题模型、LDA、STM、情感分析、词向量、文本挖掘。属于 empirical-research 编排层的计算/文本分支。
---

# Text-as-Data-CN：中文文本即数据

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `empirical-research` 或 `cnki-paper` 实证分支子技能使用时，先读取 `empirical-research/references/{{METHOD_ADAPTER_FILE}}`；若工作流由 `cnki-paper` 发起，也读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 并服从 `cnki-paper` 控制器的 `avereth.py gate --stage <stage>`。本技能产出的语料清单、预处理决策、分词/词典说明、模型日志、验证证据、敏感性检查、图表和 manuscript-ready 数字必须落到 `paper_rewriting_output\empirical\` 或父工作流指定目录；未做任务型验证的自动化文本结果不得回写正文。

`empirical-research` 的计算/文本分支。面向**政策文本、媒体语料、舆情、议案、领导讲话**等
大规模中文文本的量化分析。

> ⚠ **铁律（Grimmer & Stewart 2013，已核证）：自动化文本方法是"错误的语言模型"，在新语料上的
> 表现不可假定 → 验证强制、且须针对具体问题；方法增强而非替代精读。** 按任务分型验证：
> **有监督分类** → 对冻结的任务型参照重算混淆矩阵与逐类 F1；模型参照只报告
> `reference_agreement`，只有外部基准可报告 `external_accuracy`。**无监督**（主题模型等）→
> 综合实验、实质、统计三类证据与来源扎根的独立解释性复核。没有验证的文本结果不可投稿。
> 已核证的方法论主干见 `references/text-as-data-evidence.md`；⚠ **中文分词工具对比、情感词典、
> Wordfish、词向量/语义网络本次 deep-research 未能核证**（该文档 D 节）——下文只列常见工具名，
> 须**自行选型并验证**，勿当默认正确。

## 前置

```bash
# 核心（词频/TF-IDF/共现）仅标准库，无需安装；分词与重型分析按需装：
pip install jieba                 # 中文分词（textstat.py --segment 需要；也可用预分词输入）
pip install gensim scikit-learn   # 主题模型 LDA / 文档-词矩阵 / 词向量
# 结构主题模型 STM（带协变量，政治学常用）：R 的 stm 包
# 文本标度 Wordfish/Wordscores：R 的 quanteda(.textmodels)
```

## 工作流

1. **语料构建**：界定总体与**抽样框**（如某政策领域全部中央文件 2000–2024）；记录纳入/排除、
   去重、元数据（时间/发文机构/层级）。来源用 `repro_pack.py add-source` 登记（哈希、条数）。
2. **预处理**：分词（中文必做，工具取舍见 evidence 文档）、停用词、繁简统一、领域**自定义词典**
   （政策术语、机构名、专有名词易被切错）、未登录词处理。**预处理决策影响一切下游结果**——
   全部 `repro_pack.py decision` 留痕。
3. **表示**：词频、TF-IDF（区分高频与高区分度词）、文档-词矩阵、共现/语义网络、词向量。
4. **分析（按问题选）**：描述统计与关键词；**词典法/情感**（中文情感词典）；**主题模型** LDA/STM；
   **文本标度** Wordfish(无监督)/Wordscores(有监督)；语义网络中心性。
5. **验证（不可省）**：由隔离上下文抽样复核主题/类别，冻结逐项证据与分歧处置；按参照来源
   报告 agreement、stability 或 external accuracy，并结合主题连贯度、排他性、intrusion 和下游稳健性说明语义有效性。
6. **回写**：图表交 `docx_fixup`，结果叙事交 `cnki-paper` build 阶段；每个落稿数字写入 `method_execution.json` 的哈希 Artifact + locator，`repro_pack.py` 只生成派生视图。

## 可执行工具 `scripts/textstat.py`（核心仅标准库，13 项单测）

```bash
# 输入：--input 每行一文档（空格分词；或 --segment 用 jieba 分原文）；或 --dir 目录每 .txt 一文档
python textstat.py freq     --input docs.txt --top 30 [--segment --stopwords sw.txt --min-len 2]
python textstat.py tfidf    --input docs.txt --top 30          # 跨语料汇总 TF-IDF 排名
python textstat.py keywords --dir corpus/  --top 10           # 每文档 top 关键词
python textstat.py cooc     --input docs.txt --window 2 --min-count 3 --out edges.csv  # 共现边表→Gephi
python textstat.py segment  --input raw.txt --out tokens.txt  # 需 jieba
```

实现并**单测**（手算值，`test_textstat.py`）：词频、文档频率、TF-IDF（tf×ln(N/df)）、共现网络
（窗口内无向计数）。设计上**核心不依赖第三方**（可测、可复现），分词是唯一可选第三方前端。
共现 `edges.csv`（source,target,weight）可直接导入 Gephi/igraph/networkx 画网络。

## 方法菜单（库指引 + 验证要点）

| 方法 | 工具 | 验证要点（✓=本次已核证；⚠=本次未核证，须自行选型并验证） |
|---|---|---|
| 词频/TF-IDF/关键词 | `textstat.py`（自带，已测） | 停用词/分词是否合理；高频≠重要（看 TF-IDF 区分度） |
| 共现/语义网络 | `textstat.py` → Gephi/networkx | ⚠ 窗口/阈值/中心性解读须自定 + 做敏感性；勿当因果 |
| 主题模型 LDA / STM | gensim·sklearn；R `stm`（带协变量，政治学常用） | ✓ **别用 perplexity/held-out likelihood 选 K**；K 取**一组候选跨 K 比较**；**连贯度+排他性**（STM FREX，ω=0.7）+**词侵入 intrusion**；连贯度单用不够（自动指标约 1/5 假显著） |
| 词典法/情感 | ⚠ 中文情感词典（DUTIR/HowNet/NTUSD…，本次未核证） | 词典覆盖与领域适配；对冻结参照重算混淆矩阵/F1，并准确标注 agreement 或 external accuracy |
| 文本标度 | R `quanteda`：Wordscores（✓）；Wordfish（⚠ 未核证） | ✓ Wordscores 经大规模检验**会失败**（LBG"收缩"）→ 先验证再信 |
| 词向量 | ⚠ gensim / 中文预训练（本次未核证） | 语义有效性；勿过度解读相似度 |

> ✓ **已核证主干**（见 evidence A/B/C 节，三票核验）：验证按任务分型、别用 perplexity 选 K、
> 连贯度+排他性+词侵入、自动连贯度单用约 1/5 假显著、Wordscores 会失败。
> ⚠ **本次未核证**（D 节，仅列工具名）：中文分词工具对比、情感词典、Wordfish、语义网络/词向量
> ——本 SKILL **不对未核证项凭记忆下断言**，须自行查中文 NLP benchmark 并按 B 节原则验证。

## 中文特别提醒

- **分词决定下游**：政策/机构/专名极易切错，务必加领域自定义词典。⚠ jieba/pkuseg/THULAC/HanLP/LTP
  的准确度取舍**本次 deep-research 未能核证**——按你的语料查中文 NLP benchmark 选型，并用来源扎根的抽样复核与下游敏感性验证；
  `textstat.py` 默认用 jieba 只是常见前端，**非"最佳"背书**。
- 繁简混用要统一；停用词表按语料调；未登录词（新词、缩略语）要查漏。
- 文本即数据在中文传播/政治/公管渐热，但**误用也多**（只报词频不验证、把主题模型当客观真理、
  把相似度当因果）——验证与稳健性是底线。

## 衔接

- 预处理与分析的每个决策（分词工具、停用词、K、阈值）`repro_pack.py decision` 留痕；落稿数字
  数字写入 `method_execution.json` 的哈希工件定位，`check` 审计；语料 `add-source` 锁哈希。
- 与定性互补：文本即数据给宏观模式，`qual-content-analysis`/`aers-thematic-analysis` 给深度编码，
  `qual-process-tracing` 给机制——大语料定模式、小样本独立深描复核，是常见稳健组合。
- 文献源与成稿控制面均为 `cnki-paper`；图表交 `docx_fixup`。目标期刊对文本方法的报告与验证
  期待须自行核证（见 evidence 文档"未核实/待补"）。
