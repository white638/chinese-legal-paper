# 定性方法证据基础（qual-process-tracing / qual-qca / qual-content-analysis 共用）

本文件是 Phase 2 三个定性技能的**可追溯证据底座**。内容来自一次 deep-research
（5 路检索 → 26 源 → 107 断言 → 25 条三票对抗式核验 → 24 条确认 / 1 条否决，2026-06-14）。
**与套件"绝不伪造"理念一致：技能里的每个阈值/规则都在此有出处，且明确区分"公认共识"与
"方法论争议"，并标注未核实项。**

> ⚠ **总警示（贯穿三技能）**：下列所有**数值阈值**（QCA 一致性 0.75/0.80/0.90、覆盖度 0.60、
> PRI 0.50/0.75、频次保留 70–80%；信度 .70/.80/.90）在原始文献中均被框定为**惯例/经验法则/
> 示例**，而非硬性普适要求。技能中一律以"约定俗成的惯例（需在论文中为所选阈值辩护）"表述，
> **不得**用"必须 = 此值"的刚性口径。

## 一、过程追踪 process tracing

- **定义与推断逻辑**（Collier 2011；Beach & Pedersen）：过程追踪是"依据研究问题与假设来选取并
  分析**诊断性证据**的系统性检验"，既服务描述也服务因果评估；红利在于**案例内（within-case）**
  推断。"判定证据是否具诊断性**核心依赖先验知识**"——确立"观察的推断权重是其背景之函数"的
  (原型)贝叶斯方向。操作起点：**先做事件时间线/叙事**，扎实描述是因果推断之基。
- **四类诊断检验**（Van Evera 1997 原创，Collier 2011 Table 1 系统化）——按"通过该检验对肯定推断
  是否**必要**/是否**充分**"两维分类：

  | 检验 | 必要? | 充分? | 通过的含义 | 不通过的含义 |
  |---|---|---|---|---|
  | 风向草 straw-in-the-wind | 否 | 否 | 略微支持 | 略微削弱（不剔除） |
  | 箍圈 hoop | 是 | 否 | **不能**确证 | **剔除**焦点假设（证伪） |
  | 冒烟枪 smoking-gun | 否 | 是 | **强力支持**、实质削弱对弈假设 | **不能**拒绝假设 |
  | 双重决定性 doubly-decisive | 是 | 是 | 确证并消除对弈假设 | 剔除焦点假设 |

- **非对称推断 + 对弈假设削弱梯度**（Collier 2011 逐字）：通过——风向草"略微"、箍圈"有所"、
  冒烟枪"实质"、双重决定性"消除"削弱对弈假设。**通过与不通过必须按检验类型区别对待**。
- **变体选择**（Beach & Pedersen）：1st 版(2013) 三变体=理论检验/理论建构/解释结果；2nd 版(2019)
  增第四=理论修订。沿四维区分（朝向理论/案例、推断类型、机制理解、能否嵌入混合方法）；
  **由分析目标驱动选择**。
- **⚠ 归属精确化**：四检验为**原型贝叶斯**；**正式贝叶斯化**是 2011 后由 Bennett、
  Fairfield & Charman（对数似然比形式化）、Humphreys & Jacobs 发展——技能须分层呈现，勿把
  形式化贝叶斯归于 Collier 2011 本人。
- 源：Collier 2011 *PS* 44(4)；Beach & Pedersen *Process-Tracing Methods*（U-Mich，2013/2019）。

## 二、QCA / fsQCA

- **协议骨架**：Schneider & Wagemann (2010, *Comparative Sociology* 9(3):397-418) 的 **26 条 A–Z
  良好实践标准**，按"分析时刻**之前 / 之中 / 之后**"三阶段组织——直接用作 QCA 检查清单骨架。
- **充分性阈值**（Ragin 2006/2024；Mattke et al.）：原始一致性 raw consistency **≥0.75 为下限**，
  更高（0.80/0.85/0.90）更可靠；Ragin 2024 以 **0.80** 为将真值表行编码为"真(1)"的常用示例；
  <0.70 实质不一致；≈1.0 清晰子集。**行编码须在应用频次阈值之后**。
- **PRI**（模糊集必查）：PRI 一致性 **>0.50**（否则路径无定论，可能同时充分于高/低结果），
  经验法则约 **≥0.75**。
- **必要性**：条件一致性 **≥0.90 且覆盖度 ≥0.60**，并报告 **RoN（必要性相关度）>0.60** 以排除
  因条件近乎常量造成的**平凡必要**。
- **必要性高频误用警示**（Ragin 2024）：① 一致的**超集关系仅是必要性第一步，非证明**；
  ② 条件"出现在所有解路径中"≠必要（解覆盖度通常远<100%）；③ 两个各自"通常必要"的条件
  **相组合，其联合必要性可能跌破 0.90**。
- **频次（案例）阈值**（Greckhamer et al. 2018）：选得使应用后**约保留 70–80% 观测**；小 N 典型
  取 1–2，大 N（>100）需更高。
- **⚠ 校准 calibration 未核实**：fsQCA 直接校准三锚点（完全隶属/交叉点/完全不隶属对应模糊分）
  及具体经验示例数值，在本次核验中**被否决（1-2 票）**。技能讲校准只做**概念层**（直接法 vs
  间接法；三个质性锚点的含义），**不引用具体数字作为权威**，并指引用户查 **Ragin 2008
  《Redesigning Social Inquiry》/ Schneider & Wagemann 2012 专著**原文定锚。
- **⚠ 方法论争议（应纳入技能）**：Cooper & Glaesser (2016, *Field Methods* 28(3)) 论证
  Schneider & Wagemann 为修补有限多样性问题而提出的 **ESA（增强标准分析）** 在识别"经验必要
  条件"时所依赖的余项假设**在同一分析内相互不一致**，故其标注的"经验必要条件"实非经验必要。
  此为**归属性批评**（非既定共识；S&W 有回应，另有 Baumgartner 的 CNA 巧合分析路线）。
- 源：Schneider & Wagemann 2010；Ragin 2024 (COMPASSS Research Note)；Mattke et al. (CAIS,
  forthcoming)；Cooper & Glaesser 2016。

## 三、内容分析 / 主题分析的组间信度

- **指数选择（硬规则）**：**拒绝单独使用百分比一致（percent agreement）**——它受偶合膨胀，
  方法学界共识视为"误导性且不当偏宽松"。须用**校正偶合**的指数：**Cohen's κ、Scott's π、
  Krippendorff's α**。
- **分层可接受阈值**（Lombard, Snyder-Duch & Bracken 2002, *HCR* 28(4)）：系数 **≥.90 几乎总
  可接受；≥.80 多数情形可接受；.70 仅限某些探索性研究/某些保守指标**。对偏宽松指标用更高门槛，
  对保守的校正偶合指标可用更低门槛。
- **⚠ 争议**：O'Connor & Joffe (2020)、Zhao et al. 批评这些门槛武断、应情境化——技能须标注
  "门槛须经论证、非绝对"。
- **质性内容分析流程**：Mayring——归纳式类目发展 + 演绎式类目应用；编码手册/单位化/抽样。
  反身性主题分析见已 vendored 的 `aers-thematic-analysis`（Braun & Clarke 六阶段）。
- 源：Lombard et al. 2002（matthewlombard.com/reliability 逐字）；Mayring 2014；
  Krippendorff *Content Analysis*。

## 四、研究设计与透明度（框架指针，本次未达确认断言，按"指针"使用）

> 此角度检索到来源但**无断言通过三票核验**（合成阶段被预算/去重过滤）。故以下仅作**已确立框架
> 的指针**，技能中引用须标"框架指针，未经本次对抗核验"，不杜撰细节。

- 案例选择：Seawright & Gerring (2008) "Case Selection Techniques"（典型/多样/极端/偏离/影响/
  最相似/最不同 七型）。
- 定性透明度运动：DA-RT（Data Access & Research Transparency）、ATI（Annotation for Transparent
  Inquiry / 主动引用）。
- 混合方法整合：Fetters, Curry & Creswell (2013) 的整合层次（设计/方法/解释与报告）。

## 五、未核实 / 待补（技能不得假装已解决）

1. **fsQCA 校准锚点的权威数值**（被否决）→ 用户须查 Ragin 2008 / S&W 2012 原文。
2. **中文社科本土适配**：本批断言全部来自英文原典，未核证《政治学研究》《公共管理学报》
   《社会》等对阈值的本土采纳与争议（检索中出现 thepaper.cn、sysu/sufe PDF 等中文源，但未进入
   确认断言）→ 用户结合目标期刊审稿惯例自行补证。
3. **QCA 稳健性检验、软件链**（fs/QCA、R 的 QCA/SetMethods、NVivo/MAXQDA、α 计算实现）的
   逐步操作细节未系统核证。

## 完整来源清单（高质量项）

Collier 2011（Berkeley PDF / Cambridge）；Beach & Pedersen（U-Mich Press）；Beach & Pedersen
SSRN 1902082（三变体）；Schneider & Wagemann 2010（Brill）；Ragin 2024（COMPASSS）；
Mattke et al.（Bamberg 预印本）；Cooper & Glaesser 2016（SAGE）；Lombard et al.（ResearchGate /
matthewlombard.com）；Mayring 2014（qualitative-content-analysis.org）；Seawright & Gerring 2008、
ATI（NSF）、Fetters et al. 2013（Yale PDF）。完整 26 源见会话 deep-research 输出。
