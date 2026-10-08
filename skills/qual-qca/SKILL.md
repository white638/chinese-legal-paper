---
name: qual-qca
description: 定性比较分析 QCA/fsQCA 操作技能（可执行）：把 Ragin 与 Schneider & Wagemann 的集合论方法落成"校准→真值表→充分性/必要性→稳健性"协议，并用 scripts/qca_check.py（仅标准库）算一致性、覆盖度、PRI、RoN 并对照惯例阈值。Use when the user does 定性比较分析、QCA、fsQCA、清晰集/模糊集、真值表、条件组合、必要条件/充分条件、一致性/覆盖度、校准。覆盖中文公共管理/政治学常用的条件组态分析。Trigger on QCA、fsQCA、定性比较分析、真值表、truth table、必要条件、充分条件、一致性、覆盖度、consistency、coverage、校准、calibration、条件组态、组态分析。属于 empirical-research 编排层的定性分支之一。
---

# Qual-QCA：定性比较分析（QCA/fsQCA）

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `empirical-research` 或 `cnki-paper` 实证分支子技能使用时，先读取 `empirical-research/references/{{METHOD_ADAPTER_FILE}}`；若工作流由 `cnki-paper` 发起，也读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 并服从 `cnki-paper` 控制器的 `avereth.py gate --stage <stage>`。本技能产出的案例表、校准锚点与理由、真值表、必要/充分性参数、阈值选择、解类型和稳健性检查必须落到 `paper_rewriting_output\empirical\` 或父工作流指定目录；未登记一致性、覆盖度、PRI/RoN 和阈值理由的组态结论不得回写正文。

`empirical-research` 定性分支。把集合论比较方法落成可操作协议 + 可跑的参数计算工具。
**所有阈值都是约定俗成的惯例（需在论文中为所选值辩护），不是硬性普适规则**——
证据基础与出处见 `empirical-research/references/qual-methods-evidence.md`；解表、必要条件表、真值表附录与案例回访怎么写，见 `empirical-research/references/reporting-standards.md` §4.1，本文件不重复格式。

## 协议骨架（Schneider & Wagemann 2010 的"分析时刻前/中/后"）

操作序列与 `empirical-research/references/operation-profiles/qca-v1.json` 一致：`case_set_freeze → condition_operationalization → set_calibration → necessity_analysis → truth_table_construction → contradiction_analysis → logical_remainder_adjudication → solution_minimization → robustness_analysis → case_return → configurational_disposition`。**必要性分析是必需操作，且位于真值表之前**；`multi_value_recoding` 是唯一可选操作（mvQCA 用）。每一步的阈值、锚点与理由都登记为工件（`calibration_anchors`、`truth_table`、`contradiction_register`、`remainder_decisions`、`solution_terms`、`robustness_results`、`case_return_memos`）。

### 0. 分析之前：问题、取向、条件数与案例数

- 把研究问题表述为"哪些条件（组合）对结果 Y 充分 / 必要"，明确 **csQCA** 还是 **fsQCA**，并写明研究取向（Thomann & Maggetti 2020：案例导向 vs 条件导向、实质解释 vs 理论评价）——取向决定后面阈值怎么定、案例回访回访谁。
- 每个条件与结果写清**集合含义**（"高财政自给率"指什么，而不只是变量名）；条件选择理论驱动。
- **条件数与案例数**：旧经验法则"条件数 ≤ log2(N)"过粗，改用 Marx & Dușa (2011) 的基准思路——给定条件数 k 与案例数 N，用随机数据跑同一流程，看得到"无矛盾解"的概率有多大；若你的 (k, N) 组合在随机数据下也大概率能得到解，那么得到解本身不说明任何事。他们的基准表给出各 (k, N) 下可接受的条件/案例比（具体数值以原文表为准，待核）。
- **中文公管常见区间 5–7 条件 / 20–50 案例的注意事项**：真值表有 32–128 行，观测到的行往往不到三分之一，有限多样性是常态。要求：①报告观测行数占真值表总行数的比例与余项数；②条件数尽量压到 4–5 个——合并为宏条件、用两步 QCA 把远因/近因分层、或按理论排除；③做随机数据对照：用 R `QCA` 包对同样的 (k, N) 生成随机数据跑同样阈值，报告得到解的比例；④N < 20 时每个条件都要有案例知识支撑，N > 50 时频数阈值 ≥ 2（见 §3）。

### 1. 校准（set_calibration）

- **直接法**（Ragin 2008 第 5 章）：定三个质性锚点——完全隶属（隶属度 0.95）、交叉点（0.5，最大模糊点）、完全不隶属（0.05）；把原始值到交叉点的距离按锚点换算为对数几率（完全隶属对应约 +3，完全不隶属约 −3），再经 logistic 变换得到 [0, 1] 的隶属度。fs/QCA 软件的 `calibrate()` 与 R `QCA::calibrate(type = "fuzzy", logistic = TRUE)` 实现相同。
- **间接法**（Ragin 2008）：先按理论与案例知识把案例分成 5–6 个定性等级（完全在 / 多半在 / 略在 / 略不在 / 多半不在 / 完全不在），再用分数逻辑回归把原始测量拟合到等级分数上；适用于原始测量是排序、多指标复合或研究者对案例的判断比数值更可靠的情形。
- **锚点必须有实质理由**：理论定义、案例知识、外部标准（政策线、法定门槛、国际公认标准）。用样本分位数（均值 ± SD、四分位、"95/50/5 分位"）定锚是最常见也最被批评的做法（Schneider & Wagemann 2012 第 2 章；Krogslund, Choi & Poertner 2015 显示结果对锚点高度敏感）——如果只能用分位数，必须写明为何该分位有实质意义，并在稳健性中变动它。
- **避免恰好 0.5**：隶属度 = 0.5 的案例不属于任何真值表行，会被丢掉。做法：锚点避开实际数据点；或对落在 0.5 的案例微调（±0.001）并披露；或重新审视该案例的校准。
- **偏态检查**（Schneider & Wagemann 2012 第 9 章）：逐条件与结果报告隶属度 > 0.5 的案例比例。若某集合大多数案例都 > 0.5（或都 < 0.5），后果：①它会"看起来"必要（平凡必要）；②它可能同时是 Y 与 ~Y 的子集（同时子集关系），充分一致性虚高；③解覆盖度被少数案例决定。处置：重新校准、检查概念定义是否过宽/过窄、报告 RoN 与 PRI 而不是只报一致性。
- 校准表（工件 `calibration_anchors`）登记：条件、原始测量、三锚点、依据、> 0.5 案例比例。`qual-methods-evidence.md` 标"未核实"的是**具体案例的经验锚点数值**（不存在权威值，必须自己论证），不是直接法 0.95 / 0.5 / 0.05 这三个隶属度的定义（Ragin 2008）。

### 2. 必要性分析（necessity_analysis；先于充分性、单独报告）

- 对每个条件及其否定分别检验对 Y 与 ~Y 的必要性。一致性 ≥ 0.9 是惯例门槛（Ragin 2006；Schneider & Wagemann 2012）。
- **平凡性用 RoN 判断，不用覆盖度**（Schneider & Wagemann 2012 第 9 章）：必要性覆盖度只看 X 有多大，RoN 同时惩罚"X 几乎是常量"和"Y 几乎是全集"两种平凡。RoN 无公认硬门槛；应用中多以 0.5–0.6 为界（`qual-methods-evidence.md` 记为 > 0.6），报出来并解释，不要只写"通过"。
- **析取必要条件与 SUIN**：只有当 A 与 B 是同一高阶概念的功能等价物时，A + B 才可作为必要条件报告，其中 A、B 各是 SUIN 条件（Sufficient but Unnecessary part of a factor that is Insufficient but Necessary，Mahoney, Kimball & Koivu 2009；Schneider & Wagemann 2012 第 3 章）；把所有析取一致性 ≥ 0.9 的组合都报出来是过度拟合。
- 必要条件表（条件、一致性、覆盖度、RoN）单独呈现；正文只把通过一致性与 RoN 且有案例支撑的条件称为必要；必要条件不在充分性解表里再"发现"一次。
- 扩展：Dul (2016) 的 NCA 用天花板线（CE-FDH / CR-FDH）分析"程度上的必要"（多大的 X 才够多大的 Y）并给瓶颈表；与 QCA 组合时先用 QCA 判"类型上的必要"，再用 NCA 判"程度上的必要"（Vis & Dul 2018）。
- 必要性结果约束后续的余项处理（§4 ESA）。

### 3. 充分性：真值表（truth_table_construction、contradiction_analysis）

- **频数阈值**：小样本（N 约 < 50）取 1；中大样本 ≥ 2；应用后保留约 70–80% 案例（Greckhamer, Furnari, Fiss & Aguilera 2018）；报告阈值下保留的案例数与比例。
- **raw consistency 阈值**：≥ 0.75 是下限，0.8 常用；不要机械取 0.8——把真值表按一致性排序，在阈值附近找**自然断点**（相邻行一致性的明显落差）并说明；断点两侧的行回到案例看。
- **PRI**：≥ 0.5 是下限，多数应用取 0.65–0.75；PRI 与 raw consistency 差距大（如 0.85 对 0.45）说明该行同时接近 Y 与 ~Y 的子集，应编码为 0 或剔除并说明。**行编码在应用频数阈值之后**。
- **矛盾组态**：csQCA 中同一行既有 Y = 1 又有 Y = 0 的案例；fsQCA 中一致性落在阈值附近或 PRI 低。处置顺序：①回到案例查测量 / 校准错误；②是否缺一个区分条件（加条件要回到 §0 的 k/N 约束）；③重新界定结果或案例范围；④仍无法解决则该行编码为 0，并在 `contradiction_register` 写明。不得静默删除案例。
- 同一真值表对 ~Y 也做一遍（因果非对称），~Y 的解单独报告。

### 4. 逻辑余项与解（logical_remainder_adjudication、solution_minimization）

- **三解**：保守解（conservative / complex，不用任何余项）、简约解（parsimonious，使用一切能简化的余项）、中间解（intermediate，只用与方向性期望一致的余项）；三者嵌套（简约解 ⊇ 中间解 ⊇ 保守解）。默认报告中间解，同时用简约解判核心条件。
- **方向性期望**：逐条件写"预期存在 / 缺席促成 Y / 不设期望"及理论依据，登记在 `remainder_decisions`。
- **Enhanced Standard Analysis**（Schneider & Wagemann 2012 第 8 章；Schneider & Wagemann 2013）：在标准分析之外排除三类不可接受的简化假设——①与已确认必要条件矛盾的余项（若 A 必要，含 ~A 的余项不可假设为 Y 出现）；②逻辑上不可能的余项（条件间存在逻辑蕴含）；③矛盾简化假设（同一余项在 Y 与 ~Y 的最小化中都被当作 1）。先把这些余项设为 0 再最小化。
- **模型歧义**：Quine-McCluskey 最小化可能给出多个等价解（Baumgartner & Thiem 2017）；R `QCA::minimize()` 会列出全部模型，须报告个数并说明选择依据；fs/QCA 软件默认只显示一个，不能因此假装不存在。
- **核心 / 边缘条件**：同时出现在简约解与中间解中的条件为核心，仅出现在中间解中的为边缘（Fiss 2011）。
- **报告所用余项假设**：写明用的是标准分析还是 ESA、哪些余项被假设为 1、哪些被排除及理由；只写"采用中间解"四个字不合格。

### 5. 稳健性（robustness_analysis）

- **不接受"换个阈值再跑一次"**。按 Oana & Schneider (2021, *Sociological Methods & Research*) 的稳健性协议（R `SetMethods` 实现）：
  - 定义初始解（IS）与测试集（TS）：在校准锚点、raw consistency 阈值、频数阈值各自的合理区间内取多组设定得到测试解；`rob.calibrange` / `rob.inclrange` / `rob.ncutrange` 给出解不变的参数区间（敏感范围），先报告这些区间；
  - **fit-oriented**：RF_cov（测试解相对初始解的覆盖重叠）、RF_cons（一致性差异）、RF_SC_minTS / RF_SC_maxTS（初始解与全部测试解的交集 / 并集之间的集合重合度），越接近 1 越稳健；
  - **case-oriented**：稳健核心（在初始解与所有测试解中都被覆盖的案例）与偏移案例（只在部分设定下被覆盖的案例），`rob.xyplot` 画出；偏移案例回到案例讨论。
- Skaaning (2011) 的四类变动作为补充：校准阈值、一致性阈值、频数阈值、增删案例；每类变动报告解的变化（路径增减、核心条件是否保持）。
- 稳健性节至少回答：哪些路径 / 核心条件在全部合理设定下保持；哪些只在特定设定下出现（降为探索性）；结论随之收窄。解在某一阈值处翻转时，把该阈值附近的案例逐个回访，说明它们为何敏感。

### 6. 解表、案例回访与结论（case_return、configurational_disposition）

- 解表格式（Fiss 记法、raw / unique coverage、consistency、PRI、解级参数、解类型与余项声明、模型歧义）全部按 `empirical-research/references/reporting-standards.md` §4.1。
- **案例回访**（Schneider & Rohlfing 2013 的集合论多方法）：
  - 典型案例：路径隶属度与 Y 隶属度都高的案例，每条路径至少一个，写"路径 → 案例中的实际过程"；
  - 一致性偏离案例：在路径中但 Y 缺席，写为何机制失灵（漏掉的条件？测量？范围？）；
  - 覆盖偏离案例：Y 存在但不在任何路径，写它靠什么别的路径；
  - 独特覆盖案例：只被一条路径覆盖的案例要点名，它们是该路径存在的经验理由。
- **组态表述规则**：说"A*B*~C 是 Y 的充分路径，覆盖 n 个案例"，不说"A 促进 Y"；条件只在组态中有意义，QCA 组态不得改写成平均效应或净效应（`method_execution.py` 会以 `ME.INFERENCE.CONFIGURATION_AS_EFFECT` 拒绝）。

### 7. 变体（一句话）

时序 QCA（TQCA，Caren & Panofsky 2005；Ragin & Strand 2008）把条件出现的先后编入真值表；多值 QCA（mvQCA，Cronqvist & Berg-Schlosser 2009）允许条件取多个类别值（对应 `multi_value_recoding`）；两步 QCA（Schneider & Wagemann 2006；Schneider 2019）先用远因求情境条件，再在情境内用近因求充分组态，是压缩条件数的正规办法。

## 可执行工具 `scripts/qca_check.py`（仅标准库）

对照惯例阈值算参数。**校准后**的隶属分数表（CSV，列=条件+结果，值∈[0,1]）：

```bash
python scripts/qca_check.py scan data.csv --outcome Y                 # 逐条件充分+必要总览
python scripts/qca_check.py nec  data.csv --condition A --outcome Y   # 必要性(含 RoN)
python scripts/qca_check.py suff data.csv --condition "A*~B" --outcome Y  # 充分性(含 PRI)；*=与, ~=非
```

公式（与 R 的 QCA 包一致）：充分一致 Σmin(X,Y)/ΣX、覆盖 Σmin/ΣY、PRI、必要一致 Σmin/ΣY、
RoN=Σ(1−X)/Σ(1−min(X,Y))。**12 项单测**（手算模糊/清晰集值）见 `test_qca_check.py`。
完整真值表化简（Quine-McCluskey）、校准、三解与 Oana & Schneider 稳健性协议请用 R 的 `QCA`/`SetMethods` 包（Dușa 2019；Oana, Schneider & Thomann 2021）或 fs/QCA 软件；
本工具负责**参数核算与惯例对照**这一最易错、最该自动化的环节。

## 高频误用（必须避免）

- **超集关系 ≠ 必要性证明**：一致的超集关系只是必要性的第一步。
- **"出现在所有解路径中" ≠ 必要**（解覆盖度通常远<100%）。
- 两个各自"通常必要"的条件**相组合，联合必要性可能跌破 0.90**——组合后须重算。
- 只报一致性不报覆盖度/PRI/RoN；把惯例阈值当硬规则而不辩护。
- 用样本分位数定锚却不给实质理由；有案例落在 0.5 上却不处理。
- 省略必要性分析，或把必要条件混进充分性解表里"再发现"。
- 只报中间解、不说明方向性期望与余项假设；fs/QCA 只显示一个模型就当不存在模型歧义。
- 稳健性只做"换阈值再跑"，没有 fit-oriented / case-oriented 参数与偏移案例。
- 5–7 个条件配 20–30 个案例却不报告观测行占比与随机数据对照。

## 方法论争议（应在稿中知情处理）

Cooper & Glaesser (2016) 论证 Schneider & Wagemann 的 **ESA（增强标准分析）** 在有限多样性下识别
"经验必要条件"所依赖的余项假设**在同一分析内相互不一致**，故其"经验必要条件"实非经验必要。
这是**归属性批评**（S&W 有回应；另有 Baumgartner 的 CNA 巧合分析路线）——用 ESA 时应知此辩论。
Krogslund, Choi & Poertner (2015) 对 fsQCA 参数敏感性与确认偏误的批评，是 §5 稳健性协议成为必需项的直接原因。

## 衔接

- 数据校准、案例与阈值选择全程 `empirical-research/scripts/repro_pack.py` 留痕（`decision` 记每个
  阈值/校准的理由；落稿一致性/覆盖度写入 `method_execution.json` 的哈希工件定位，`check` 审计）。
- 中文语境：QCA 在中文公共管理研究中应用渐多（方法综述见 杜运周、贾良定 2017；张明、杜运周 2019），但**误用批评也多**（把阈值当硬规则、不做稳健性、
  条件过多、锚点用分位数不辩护）；目标期刊（如《公共管理学报》）的审稿惯例须自行核证（见 evidence 文档"未核实"项）。
- 结果叙事交 `cnki-paper` build 阶段；组态表过 `docx_fixup --tables`；表格与案例回访写法以 `reporting-standards.md` §4.1 为准。
