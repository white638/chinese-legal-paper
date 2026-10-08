# 识别设计手册：IV · RDD · 匹配与加权 · 合成控制与中介/调节

本文是 `SKILL.md`"识别优先"表中 IV、RDD、PSM、SCM、中介五行的展开，与 `did-staggered.md` 并列。
每节结构相同：识别假设 → 估计与诊断 → 中国情境 → 报告要件 → 审稿人常见质疑与预案。所有设计都要先填
`causal-design-v1.schema.json` 的 `estimand / unit_of_treatment / independence_unit / counterfactual /
identification_assumptions[]`，每条假设配一个 `diagnostic_artifact_id`——**没有诊断工件的假设只能标 `untested`，
不能标 `supported`**。

## 一、工具变量 IV

### 1.1 四个假设（Angrist, Imbens & Rubin 1996, *JASA* 91(434)）

| 假设 | 含义 | 可否检验 | 诊断 |
|---|---|---|---|
| 相关性 | Z 影响 D | 可 | 首阶段系数、有效 F（§1.3） |
| 排他性 | Z 只经由 D 影响 Y | **不可**，只能论证 | 排他性论证段 + 零首阶段子样本的简化式（§1.2） |
| 独立性（外生） | Z 与潜在结果、潜在处理独立（条件于 X） | 不可 | Z 对基期特征的平衡表；Z 的产生机制描述 |
| 单调性 | 无"反抗者"（Z 变动不会让任何人反向改变 D） | 部分可 | 按子群看首阶段符号是否一致（Imbens & Angrist 1994, *Econometrica* 62(2)） |

另加 SUTVA。四条中最常被审稿人攻击的是排他性，其次是弱工具。

### 1.2 排他性只能论证不能检验：常见工具及其争议

| 工具类型 | 例 | 排他性争议 | 对策 |
|---|---|---|---|
| 地理/自然 | 到海岸线/港口距离、地形起伏度（Nunn & Puga 2012, *REStat* 94(1)）、河流密度 | 地理通过贸易、迁移、疾病、文化等多渠道影响结果；面板中时不变工具必须与时变冲击交互，交互项继承同样问题 | 逐一列出并控制可观测渠道；报"零首阶段"子样本的简化式应为 0（Bound & Jaeger 2000 思路；Altonji, Elder & Taber 2005, *JPE* 113(1)） |
| 历史变量 | 通商口岸、科举配额、传教士分布、明清驿站 | 历史持续性本身就是多渠道；空间自相关会让显著性虚高（Kelly 2019 工作论文，待核） | Conley 空间标准误；Conley, Hansen & Rossi (2012, *REStat* 94(1)) 的"近似外生"敏感性 |
| 气象 | 降雨、气温、日照 | Mellon (2024, *AJPS*，卷期待核) 列出 194 种通过天气违反排他性的路径 | 只在结果变量与天气的其他渠道可论证隔离时使用 |
| Bartik / shift-share | 基期行业份额 × 全国行业增长 | 两种识别框架：GPSS (2020, *AER* 110(8)) 视份额为外生（等价于以份额为暴露度的 DID，须论证份额与其他冲击无关，报 Rotemberg 权重看哪些行业驱动）；BHJ (2022, *REStud* 89(1)) 视冲击为准随机（须冲击数量多、与暴露无关）。二选一并按其条件论证 | 报 Rotemberg 权重；推断用 Adão, Kolesár & Morales (2019, *QJE* 134(4)) 的份额相关标准误 |
| 同群均值 | 同省其他城市均值、同行业均值 | 共同冲击直接违反排他性（Angrist 2014, *Labour Economics* 30） | 通常不可用；至少要论证不存在省级共同冲击且已控省×年 FE |
| 滞后项 | 用 D 的滞后一期作 D 的工具 | 误差序列相关时排他性必然失效（Bellemare, Masaki & Pepinsky 2017, *Journal of Politics* 79(3)；Reed 2015, *Oxford Bulletin* 77(6)） | 不作为主要识别；滞后只在理论明确指出时序时用作解释变量 |

写排他性论证段的方法：把"Z → Y 的所有可能路径"列成表，逐条说明它要么被控制、要么与结果不相关、
要么方向与主效应相反（保守）。Lal, Lockhart, Xu & Zu (2024, *Political Analysis* 32(4)) 复制 67 篇政治学
IV 研究，多数首阶段偏弱且 IV 估计远大于 OLS——"IV > OLS 好几倍"本身就是排他性或弱工具的红旗（Jiang 2017,
*Review of Corporate Finance Studies* 6(2)）。

### 1.3 弱工具：为什么"F ≥ 10"已过时

- 来源：Staiger & Stock (1997, *Econometrica* 65(3)) 的经验法则与 Stock & Yogo (2005) 临界值，仅适用于
  **同方差、单一内生变量**，且目标是"2SLS 相对 OLS 的偏误 ≤ 10%"，不是控制检验的规模。用异方差/聚类
  稳健标准误时，常规 F 与 Kleibergen-Paap F 都没有对应的临界值表。
- **有效 F**（Montiel Olea & Pflueger 2013, *JBES* 31(3)）：对异方差、自相关、聚类稳健；临界值随"允许的最坏
  情形偏误"变化，单工具、5% 显著性下，允许 10% 偏误约需 23.1，5% 偏误约需 37.4（待核精确值）。
  Stata `weakivtest`，R `ivmodel` 或手工。
- **tF 校正**（Lee, McCrary, Moreira & Porter 2022, *AER* 112(10)）：单内生变量单工具时，用 1.96 做 t 检验
  要保证名义 5% 水平，首阶段 F 须 > 104.7；否则按其表放大临界值（F = 10 时临界值约 3.4，待核）。
  报"tF 校正后的置信区间"即可，不必换估计量。
- **Anderson-Rubin 置信区间**（Anderson & Rubin 1949）：对任意强度的工具都有效，允许无界区间；弱工具时
  它是唯一可信的区间，出现无界或不连通就照实报（Andrews, Stock & Sun 2019, *Annual Review of Economics*
  11 的综述）。Stata `weakiv`，R `ivmodel`，Python `ivmodels`（待核）。
- 报告规则：**有效 F + AR 区间必报**，tF 校正在单工具时加报；F 在 10–100 之间时正文明写"常规 t 检验
  可能过度拒绝，以 AR 区间为准"。Keane & Neal (2023, *Journal of Econometrics* 235(2)) 对此的实践指南可作依据。

### 1.4 LATE 解释与 compliers 刻画

2SLS 识别的是**遵从者**（因 Z 变动而改变 D 的单位）的平均效应（Imbens & Angrist 1994），不是总体 ATE。
必做：(1) 用 Abadie (2003, *Journal of Econometrics* 113(2)) 的 κ 加权或 Marbach & Hangartner (2020,
*Political Analysis* 28(3)) 的方法刻画遵从者在协变量上的分布，与总体比较，说明外推边界；
(2) 多个工具时 2SLS 是各工具 LATE 的加权平均（Mogstad, Torgovitsky & Walters 2021, *AER* 111(11)），
权重可能不合意；(3) 带协变量的 2SLS 只有在协变量"饱和"（或线性设定正确）时才是 LATE 的凸加权
（Blandhol, Bonney, Mogstad & Torgovitsky 2022, NBER WP 29709，待核），协变量多时用交互或非参数方式。

### 1.5 过度识别检验的局限

Hansen J / Sargan 检验的前提是**至少一个工具有效且效应同质**。恰好识别无法检验；效应异质时不同工具
识别不同 LATE，J 拒绝可能只是异质性；全部工具同样无效时 J 也可能不拒绝。结论：J 通过不是排他性证据，
J 拒绝要认真对待。

### 1.6 控制变量与"坏控制"

- 需要的控制：让"Z 独立于潜在结果"成立的变量（如 Bartik 的基期结构、地理工具的省份 FE）。
- 坏控制（Angrist & Pischke 2009；Cinelli, Forney & Pearl 2024, *Sociological Methods & Research* 53(3)）：
  受 D 或 Z 影响的变量（政策后变量、中介、对撞）。IV 中额外的坏控制是控制了 Z 的下游变量（例如工具是
  地形、控制了人均 GDP），会把工具的部分变异当成"已解释"而制造偏误。
- 同一组控制放进首阶段与第二阶段；手工两步会算错标准误，用一体化命令。

### 1.7 报告要件

首阶段表（系数、有效 F、KP F 作对比）；简化式（Z → Y）；2SLS 与 OLS 并列；AR 区间与 tF 区间；
遵从者刻画表；排他性论证段与零首阶段子样本检验；J 检验（若过度识别）并注明其局限；工具的产生机制描述
（谁、何时、为何这样分配）。统一登记：`identification_assumptions` 四条各配诊断工件。

### 1.8 审稿人常见质疑与预案

| 质疑 | 预案 |
|---|---|
| 排他性不成立 | 路径表逐条回应；零首阶段子样本；Conley-Hansen-Rossi 近似外生区间 |
| 工具弱 | 有效 F、AR 区间、tF 区间；若 AR 无界，措辞降为"方向一致但幅度不确定" |
| IV 远大于 OLS | 讨论测量误差衰减、LATE 与 ATE 差异、弱工具偏误、排他性，四者哪一个最可能 |
| LATE 不能外推 | 遵从者刻画 + 说明政策相关人群是否即遵从者 |
| 时不变工具在面板中如何识别 | 说明交互的时变冲击及其外生性；报交互项本身的排他性论证 |
| 多工具 J 检验 | 说明异质性下 J 的局限；报每个工具单独的估计 |

## 二、断点回归 RDD

### 2.1 连续性假设与估计对象

驱动变量 X、断点 c、处理 D = 1[X ≥ c]（清晰）或 P(D=1|X) 在 c 处跳跃（模糊）。识别假设：E[Y(0)|X] 与
E[Y(1)|X] 在 c 处**连续**（Hahn, Todd & van der Klaauw 2001, *Econometrica* 69(1)）。估计对象是 **c 处的
局部效应**（清晰）或 c 处遵从者的 LATE（模糊）——外部效度天然受限，正文要承认。综合入门：Imbens & Lemieux
(2008, *Journal of Econometrics* 142(2))、Lee & Lemieux (2010, *JEL* 48(2))、Cattaneo, Idrobo & Titiunik (2020,
2024, Cambridge Elements)。

### 2.2 估计：CCT 带宽、稳健偏差校正 CI、多项式阶数

- **默认设定**：局部线性（p = 1）、三角核、MSE 最优带宽（Calonico, Cattaneo & Titiunik 2014, *Econometrica*
  82(6)）；`rdrobust` 同时输出常规、偏差校正、**稳健**三行——报常规点估计配稳健置信区间（Cattaneo 等的
  推荐实践），或三行全报。CER 最优带宽（Calonico, Cattaneo & Farrell 2020, *Econometrics Journal* 23(2)）
  更小，更适合推断，可作副结果。
- **多项式阶数**：不用全局高阶多项式（Gelman & Imbens 2019, *JBES* 37(3)）——权重怪异、对阶数敏感、
  覆盖率错误。p = 1 主，p = 2 副；p ≥ 3 只在附录作为"与旧文献可比"。
- **带宽敏感性图**：横轴带宽（0.5h 到 2h），纵轴估计与稳健 CI；左右不对称带宽（`msetwo`）作副。
- **驱动变量离散**（年龄整数、分数整数）：不要按驱动变量聚类（Kolesár & Rothe 2018, *AER* 108(8)），
  用其诚实 CI 或局部随机化框架；`rdrobust` 开 `masspoints`。
- **协变量**：只能作效率提升，不能作识别（Calonico, Cattaneo, Farrell & Titiunik 2019, *REStat* 101(3)）；
  加入后点估计变化大是信号，不是修正。

### 2.3 有效性检验

1. **密度检验**：McCrary (2008, *Journal of Econometrics* 142(2)) 或 Cattaneo, Jansson & Ma (2020, *JASA* 115(531))
   的局部多项式密度（`rddensity`，无需预分箱）；报 p 值与密度图。拒绝 = 驱动变量被操纵，RDD 无效
   （若操纵是"堆积"，改用 bunching 方法而不是硬做 RDD）。
2. **协变量连续性**：把每个处理前协变量当结果跑同一 RDD，都不应跳跃；做成一张表。
3. **伪断点**：在断点两侧各取若干伪 c（每侧只用该侧数据，避免真实处理污染），效应应为 0。
4. **甜甜圈 RDD**：删除 |X − c| < ε 的观测重跑（Barreca, Guldi, Lindo & Waddell 2011, *QJE* 126(4)），ε 取
   多个值；用于应对断点附近堆积或轻度操纵。方法适配器已规定：剔除断点附近信息后的分析只能作压力测试或
   新的估计对象，不能替代原效应。
5. **rdplot**：IMSE 最优分箱（`rdplot`，默认 `esmv`）的分箱散点 + 全局多项式仅供可视化；不要用可视化的
   多项式做估计。

### 2.4 模糊 RDD、多断点、地理 RDD、局部随机化

- **模糊**：报首阶段跳跃（D 在 c 处的概率变化）；首阶段弱时问题与 IV 相同（§1.3）；`rdrobust(fuzzy=)`。
- **多断点**（不同省/年份分数线不同）：归一化合并 vs 逐断点估计（Cattaneo, Keele, Titiunik & Vazquez-Bare
  2016, *Journal of Politics* 78(4)；`rdmulti`），合并后的估计是各断点效应的加权平均，权重要报。
- **地理 RDD**（Dell 2010, *Econometrica* 78(6)；Keele & Titiunik 2015, *Political Analysis* 23(1)）：边界两侧
  须只有一种处理变化——省界同时改变财政、司法、教育等一切制度时，效应是"复合处理"，只能解释为边界效应。
- **局部随机化**（Cattaneo, Frandsen & Titiunik 2015, *Journal of Causal Inference* 3(1)；`rdlocrand`）：在很小
  窗口内把处理视为随机，用随机化推断；适合离散驱动变量与小样本。
- **时间断点 RDiT**（政策按日期生效）：与 DID 或事件研究混同，且时间序列自相关严重（Hausman & Rapson
  2018, *Annual Review of Resource Economics* 10），慎用。

### 2.5 中国情境

| 门槛 | 例 | 主要风险 |
|---|---|---|
| 人口规模线 | 城市规模划分标准（国发〔2014〕51 号：100/300/500/1000 万城区常住人口）触发落户、用地、地铁审批等政策 | 复合处理：同一门槛捆绑多项政策；人口数本身可"被统计" |
| 分数线 | 高考录取线、重点高中录取线、公务员笔试线 | 分数线逐年逐省不同 → 多断点；加分政策造成堆积 |
| 年龄/任期线 | 干部任职年龄杠杠、退休年龄、届满换届 | 年龄离散、"年龄操纵"有记录；换届是时间断点 |
| 政策门槛 | 贫困县认定指标、小微企业应纳税所得额门槛、规模以上企业 2000 万营收线、小规模纳税人 500 万线 | 税收类门槛几乎必然堆积（bunching），RDD 无效，改 bunching 估计 |
| 地理线 | 淮河供暖线（Chen, Ebenstein, Greenstone & Li 2013, *PNAS* 110(32)） | 边界两侧其他政策与气候的连续性需逐一论证 |

### 2.6 报告要件

rdplot；主表（常规 + 稳健行、左右带宽 h 与 b、带宽内 N、核、阶数）；密度检验 p 与图；协变量连续性表；
带宽敏感性图；伪断点表；甜甜圈表；模糊设计的首阶段；多断点的权重；局部效应的外推边界一句话。

### 2.7 审稿人常见质疑与预案

| 质疑 | 预案 |
|---|---|
| 驱动变量被操纵 | 密度检验 + 甜甜圈 + 操纵动机与能力的制度论证 |
| 带宽/阶数任意 | CCT 最优带宽为主，敏感性图覆盖 0.5h–2h，p = 1/2 并报 |
| 只是局部效应 | 承认；报断点附近样本的特征与总体比较 |
| 门槛捆绑多项政策 | 列出全部以同一门槛为条件的政策，说明哪些同时跳跃、效应如何解释 |
| 驱动变量离散 | Kolesár-Rothe 诚实 CI 或局部随机化 |
| 模糊首阶段弱 | 报首阶段有效 F 与 AR 区间 |

## 三、匹配与加权

### 3.1 框架与 King & Nielsen 对 PSM 的批评

匹配/加权的识别假设是**可观测变量上的选择**（条件独立/可忽略性）+ **重叠**（Rosenbaum & Rubin 1983,
*Biometrika* 70(1)）。它不解决不可观测混杂——正文要写明这一点，别用"匹配后处理组与对照组可比"暗示因果。

King & Nielsen (2019, *Political Analysis* 27(4)) 的核心批评：倾向得分匹配模仿的是**完全随机试验**而非
区组随机试验，按倾向得分修剪样本反而可能**增加**协变量不平衡（"PSM 悖论"），修剪越多越差；1:1 最近邻
匹配还丢弃大量数据。替代：
- **粗化精确匹配 CEM**（Iacus, King & Porro 2012, *Political Analysis* 20(1)）：先分箱再精确匹配，平衡有上界；
  estimand 变为匹配到的子总体。
- **熵平衡**（Hainmueller 2012, *Political Analysis* 20(1)）：对对照组重加权使一阶、二阶矩精确匹配，
  不丢样本；R `ebal`，Stata `ebalance`。
- **IPW / 稳定化权重**、**CBPS**（Imai & Ratkovic 2014, *JRSS-B* 76(1)）、**AIPW/双重稳健**（Robins, Rotnitzky
  & Zhao 1994, *JASA* 89(427)；Bang & Robins 2005, *Biometrics* 61(4)）：结果模型与倾向模型任一正确即一致。
- **双重机器学习 DML**（Chernozhukov et al. 2018, *Econometrics Journal* 21(1)）：高维协变量时的 DR 版本，
  仍是可观测选择假设。
- 匹配作为**预处理**（Ho, Imai, King & Stuart 2007, *Political Analysis* 15(3)）：匹配后再做回归调整，比单纯
  匹配或单纯回归都稳。

### 3.2 共同支撑与修剪

画处理组与对照组的倾向得分分布；重叠差则修剪。Crump, Hotz, Imbens & Mitnik (2009, *Biometrika* 96(1)) 的
[0.1, 0.9] 规则是常用起点。修剪后 estimand 变为**重叠总体上的效应**，正文必须说明，且报修剪掉的单位数与特征。

### 3.3 平衡诊断

- 标准化均值差 |SMD| < 0.1（0.25 是宽松线）、方差比在 0.5–2 之间、eCDF 统计量；love plot（R `cobalt`）。
- 平衡要查协变量的平方项与交互项，不只一阶矩。
- **不要用 t 检验 p 值报平衡**：p 值随样本量变化，匹配后 N 减小会"自动通过"（Imai, King & Stuart 2008,
  *JRSS-A* 171(2)）。
- 匹配算法（卡尺、是否放回、比例）必须预先登记（`repro_pack.py decision`），不能试到平衡好看为止。

### 3.4 不可观测混杂的敏感性

| 方法 | 回答的问题 | 适用 | 实现 |
|---|---|---|---|
| Rosenbaum 界 Γ（Rosenbaum 2002） | 不可观测变量要把处理概率比扭曲到多大，结论才翻转 | 匹配后配对样本 | R `rbounds`，Stata `rbounds`/`mhbounds` |
| Oster (2019, *JBES* 37(2)) δ | 不可观测选择要达到可观测选择的几倍才能使 β = 0（假设 R_max，常取 1.3×R̃） | 线性回归 | Stata `psacalc`，R `robomit` |
| E-value（VanderWeele & Ding 2017, *Annals of Internal Medicine* 167(4)） | 混杂因子与处理、结果的关联至少多强才能解释掉效应（风险比尺度） | 二元结果/风险比 | R `EValue` |
| 稳健值 RV（Cinelli & Hazlett 2020, *JRSS-B* 82(1)） | 混杂因子需解释处理与结果残差方差的多大比例；可用已观测协变量作基准 | 线性回归 | R/Stata `sensemakr`，Python `PySensemakr` |

规则：至少报一种，且**无论结果是否有利都报**；Oster δ 不要只在 δ > 1 时才出现在论文里；Oster 方法在控制
变量本身内生时不可靠（Diegert, Masten & Poirier 2022 工作论文，待核），线性设定优先 sensemakr 的 RV 并以
最强的已观测协变量作基准。

### 3.5 匹配后推断

- 最近邻匹配估计量在多个连续协变量下有渐近偏误，需偏误校正（Abadie & Imbens 2006, *Econometrica* 74(1)）；
  **有放回最近邻匹配不能用 bootstrap 算标准误**（Abadie & Imbens 2008, *Econometrica* 76(6)）。
- 在估计的倾向得分上匹配时标准误须调整（Abadie & Imbens 2016, *Econometrica* 84(2)）；Stata `teffects psmatch`
  默认给出该调整；`psmatch2` 的标准误不正确，仅用于探索。
- 加权类方法（IPW/熵平衡/CBPS）可用 bootstrap 或 M 估计标准误；聚类结构仍按处理分配层级处理。
- **PSM-DID**：匹配处理前协变量与处理前结果时警惕均值回归（Daw & Hatfield 2018, *Health Services Research*
  53(6)）；Chabé-Ferret (2015, *Journal of Econometrics* 185(1)) 建议匹配处理前对称多期结果。匹配后的 DID 仍要
  过 `did-staggered.md` 的全部要求。

### 3.6 报告要件

协变量清单及其"处理前"性质；倾向模型设定；算法（卡尺、比例、放回）；匹配/未匹配/修剪的单位数；
匹配前后平衡表（SMD、方差比）与 love plot；重叠图；estimand（ATT 或重叠总体 ATT）；标准误方法；
至少一种敏感性分析；PSM / CEM / 熵平衡 / IPW / AIPW 的对照表作稳健性。

### 3.7 审稿人常见质疑与预案

| 质疑 | 预案 |
|---|---|
| 不可观测混杂 | RV/E-value/Γ 并报；用最强已观测协变量作基准说明需要多强的混杂 |
| PSM 悖论 | CEM 或熵平衡对照；报修剪路径上的平衡变化 |
| 卡尺/算法任意 | 预登记；多算法对照表 |
| 用 p 值报平衡 | 改 SMD |
| 修剪改变了总体 | 明写重叠总体 estimand，报被修剪单位特征 |
| 标准误错误 | AI(2016) 调整或加权法 bootstrap |
| 为何不用 DID/IV | 说明无外生时变冲击或工具；把匹配定位为"可观测选择下的最优努力" |

## 四、合成控制与中介、调节

### 4.1 合成控制 SCM 要件

Abadie & Gardeazabal (2003, *AER* 93(1))、Abadie, Diamond & Hainmueller (2010, *JASA* 105(490); 2015, *AJPS*
59(2))、综述 Abadie (2021, *JEL* 59(2))。
- **前期拟合**：处理前期越长越好（经验上 ≥ 10 期），拟合差（pre-RMSPE 相对结果变量尺度大）就不能用
  （Ferman & Pinto 2021, *Quantitative Economics* 12(4) 证明不完美拟合下的偏误）。处理单位落在 donor 凸包
  之外时权重非负约束使拟合必然差——换 augmented SCM 或放弃。
- **donor pool**：与处理单位结构相似、同期未受类似冲击、无溢出的单位；剔除理由逐一写明。
- **预测变量选择**：不能"挑到好看为止"（Ferman, Pinto & Possebom 2020, *JPAM* 39(2)）——报所有常见设定
  的结果；把全部处理前结果值都放进预测变量会使其他协变量失去作用（Kaul, Klößner, Pfeifer & Schieler 2022,
  *JBES* 40(3)）。
- **推断**：空间安慰剂置换——对每个 donor 假装处理，得到差距分布；报**后/前 RMSPE 比**的排名 p 值
  = 处理单位排名 /(J + 1)；时间安慰剂（把处理时点前移）；leave-one-donor-out。正式方法：Chernozhukov,
  Wüthrich & Zhu (2021, *JASA* 116(536)) 的保形推断、Cattaneo, Feng & Titiunik (2021, *JASA* 116(536)) 的
  预测区间（`scpi`）。
- 报告：权重表、预测变量平衡表、处理与合成的路径图、差距图、置换分布图、RMSPE 比排名。

### 4.2 SDID、augmented SCM、gsynth

- **合成 DID**（Arkhangelsky, Athey, Hirshberg, Imbens & Wager 2021, *AER* 111(12)）：同时用单位权重（如 SCM）
  与时间权重（如 DID），含单位固定效应故不要求水平精确匹配；多处理单位、交错处理均可（Stata `sdid`，
  Clarke, Pailañir, Athey & Imbens 2023 工作论文，待核）；标准误用 placebo/bootstrap/jackknife。
- **augmented SCM**（Ben-Michael, Feller & Rothstein 2021, *JASA* 116(536)）：用岭回归修正前期不平衡，允许
  负权重，报"外推程度"。
- **广义合成控制**（Xu 2017, *Political Analysis* 25(1)）：交互固定效应，多处理单位；需足够前期与处理单位数。

### 4.3 中介分析

- **Baron & Kenny (1986, *JPSP* 51(6)) 三步法在因果推断下失效**：把中介 M 放进 Y 对 D 的回归，需要**序贯
  可忽略性**（Imai, Keele & Yamamoto 2010, *Statistical Science* 25(1)）——(i) D 相对潜在结果与潜在中介可忽略；
  (ii) **M 相对潜在结果可忽略（条件于 D 与 X）**。即便 D 随机，(ii) 也不自动成立；M 内生时直接效应与间接
  效应都有偏，且总效应估计也被"政策后变量"污染（Acharya, Blackwell & Sen 2016, *APSR* 110(3)；Montgomery,
  Nyhan & Torres 2018, *AJPS* 62(3)）。方法适配器已明文规定：政策后中介不能作为总效应的普通控制变量。
- **可做的**：(a) 把机制变量当**结果**估 D → M（与主设计同样的识别策略），这是最诚实的机制证据；
  (b) 用处理前调节变量做异质性（理论预期机制强的子群效应更大）；(c) Imai, Keele & Tingley (2010,
  *Psychological Methods* 15(4)) 的 ACME/ADE 配敏感性参数 ρ（中介与结果误差的相关），报 ρ 达到多大 ACME 归零
  （R `mediation`，Stata `medeff`，Python `statsmodels` `Mediation`）；(d) Acharya-Blackwell-Sen 的**受控直接效应
  CDE**（序贯 g 估计，R `DirectEffects`）：回答"把中介固定在某值时 D 的效应还剩多少"，只需中介的可忽略性
  在条件于中间混杂后成立，比 ACME 假设弱。
- 中文经济学界的判断：江艇 (2022, 《中国工业经济》第 5 期) 指出政策评估文献中大量"三步法中介"不可信，
  建议只做 D → M 与理论驱动的异质性；Bullock, Green & Ha (2010, *JPSP* 98(4)) 与 Heckman & Pinto (2015,
  *Econometric Reviews* 34(1–2)) 是同一结论的英文来源。
- 报告：机制假设的 DAG；D → M 表；若报 ACME，配 ρ 敏感性图与"序贯可忽略性为何可信"的论证段；若报 CDE，
  写明中介固定值与中间混杂集合。

### 4.4 调节效应（交互项）

Hainmueller, Mummolo & Xu (2019, *Political Analysis* 27(2)) 指出乘法交互模型依赖两个常被忽略的假设：
**线性交互效应**（D 的边际效应随 M 线性变化）与 **M 的共同支撑**（M 的各取值上处理组与对照组都有观测）。
诊断：(1) 分箱估计（M 的低/中/高三分位各估一个边际效应）；(2) 核估计的边际效应曲线；(3) 边际效应图下方
叠加 M 的直方图（分处理状态）。两者与线性交互估计差异大就报分箱结果为主。基本规则（Brambor, Clark &
Golder 2006, *Political Analysis* 14(1)）：全部构成项都进模型；报边际效应图而非只报交互系数；调节变量须为
处理前变量。R/Stata `interflex`。

### 4.5 报告要件与审稿人质疑

| 设计 | 必报 | 常见质疑 → 预案 |
|---|---|---|
| SCM | 权重、预测变量平衡、路径图、置换分布、RMSPE 比排名、多设定对照 | "donor 挑选任意" → 剔除理由表 + leave-one-out；"前期拟合差" → augmented/SDID 或放弃 |
| SDID | 单位/时间权重、与 SCM/DID 三者并列 | "为何不用 DID" → 报三者并列并解释差异来源 |
| 中介 | DAG、D → M、ρ 敏感性或 CDE 设定 | "三步法不可信" → 改 D → M + 异质性；"中介内生" → CDE 或删除该分析 |
| 调节 | 分箱 + 核 + 直方图三合一图 | "交互项线性假设" → 分箱结果；"共同支撑缺失" → 删除无重叠区间并说明 |

## 五、实现对照表

| 任务 | Python | R | Stata |
|---|---|---|---|
| 2SLS / 高维 FE IV | statspai `sp.ivreg`；`linearmodels.iv` | `fixest::feols(y ~ x \| fe \| d ~ z)`；`ivreg` | `ivreg2`、`ivreghdfe` |
| 有效 F / 弱工具稳健推断 | `ivmodels`（待核） | `ivmodel`（AR、CLR） | `weakivtest`（MOP 有效 F）、`weakiv`（AR/CLR/K） |
| 遵从者刻画 | 手工 κ 加权 | `ivdesc` | 手工 |
| RDD 估计 / 密度 / 局部随机化 / 多断点 | `rdrobust`、`rddensity`（PyPI） | `rdrobust`、`rddensity`、`rdlocrand`、`rdmulti` | `rdrobust`、`rddensity`、`rdlocrand`、`rdmulti` |
| 匹配 / 加权 / 平衡 | statspai（版本待核）；`dowhy`、`econml` | `MatchIt`、`WeightIt`、`cobalt`、`cem`、`ebal`、`CBPS` | `teffects psmatch/ipw/aipw`、`cem`、`ebalance`、`kmatch` |
| 敏感性 | `PySensemakr` | `sensemakr`、`EValue`、`rbounds`、`robomit` | `sensemakr`、`psacalc`、`rbounds`、`mhbounds` |
| 合成控制及变体 | `pysyncon`（Synth / augmented / robust） | `Synth`、`tidysynth`、`augsynth`、`synthdid`、`gsynth`、`scpi` | `synth`、`synth_runner`、`sdid`、`scpi` |
| 中介 / CDE | statspai `sp.mediation`；`statsmodels.stats.mediation` | `mediation`、`DirectEffects` | `medeff`、`paramed`；CDE 待核 |
| 调节诊断 | 待核 | `interflex` | `interflex` |

## 参考文献（作者 + 年份 + 出处；标"待核"者投稿前核对）

- Abadie, A. (2003). Semiparametric instrumental variable estimation of treatment response models. *Journal of Econometrics*, 113(2).
- Abadie, A. (2021). Using synthetic controls: Feasibility, data requirements, and methodological aspects. *Journal of Economic Literature*, 59(2).
- Abadie, A., & Imbens, G. W. (2006/2008/2016). *Econometrica*, 74(1); 76(6); 84(2).
- Abadie, A., Diamond, A., & Hainmueller, J. (2010). *JASA*, 105(490); (2015). *AJPS*, 59(2).
- Acharya, A., Blackwell, M., & Sen, M. (2016). Explaining causal findings without bias: Detecting and assessing direct effects. *American Political Science Review*, 110(3).
- Adão, R., Kolesár, M., & Morales, E. (2019). Shift-share designs: Theory and inference. *Quarterly Journal of Economics*, 134(4).
- Andrews, I., Stock, J. H., & Sun, L. (2019). Weak instruments in instrumental variables regression: Theory and practice. *Annual Review of Economics*, 11.
- Angrist, J. D., Imbens, G. W., & Rubin, D. B. (1996). Identification of causal effects using instrumental variables. *JASA*, 91(434).
- Arkhangelsky, D., Athey, S., Hirshberg, D. A., Imbens, G. W., & Wager, S. (2021). Synthetic difference-in-differences. *American Economic Review*, 111(12).
- Ben-Michael, E., Feller, A., & Rothstein, J. (2021). The augmented synthetic control method. *JASA*, 116(536).
- Borusyak, K., Hull, P., & Jaravel, X. (2022). Quasi-experimental shift-share research designs. *Review of Economic Studies*, 89(1).
- Calonico, S., Cattaneo, M. D., & Titiunik, R. (2014). Robust nonparametric confidence intervals for regression-discontinuity designs. *Econometrica*, 82(6).
- Cattaneo, M. D., Jansson, M., & Ma, X. (2020). Simple local polynomial density estimators. *JASA*, 115(531).
- Chernozhukov, V., et al. (2018). Double/debiased machine learning for treatment and structural parameters. *Econometrics Journal*, 21(1).
- Cinelli, C., & Hazlett, C. (2020). Making sense of sensitivity: Extending omitted variable bias. *JRSS-B*, 82(1).
- Cinelli, C., Forney, A., & Pearl, J. (2024). A crash course in good and bad controls. *Sociological Methods & Research*, 53(3).
- Crump, R. K., Hotz, V. J., Imbens, G. W., & Mitnik, O. A. (2009). Dealing with limited overlap in estimation of average treatment effects. *Biometrika*, 96(1).
- Gelman, A., & Imbens, G. (2019). Why high-order polynomials should not be used in regression discontinuity designs. *JBES*, 37(3).
- Goldsmith-Pinkham, P., Sorkin, I., & Swift, H. (2020). Bartik instruments: What, when, why, and how. *American Economic Review*, 110(8).
- Hainmueller, J. (2012). Entropy balancing for causal effects. *Political Analysis*, 20(1).
- Hainmueller, J., Mummolo, J., & Xu, Y. (2019). How much should we trust estimates from multiplicative interaction models? *Political Analysis*, 27(2).
- Iacus, S. M., King, G., & Porro, G. (2012). Causal inference without balance checking: Coarsened exact matching. *Political Analysis*, 20(1).
- Imai, K., Keele, L., & Tingley, D. (2010). A general approach to causal mediation analysis. *Psychological Methods*, 15(4).
- Imai, K., Keele, L., & Yamamoto, T. (2010). Identification, inference and sensitivity analysis for causal mediation effects. *Statistical Science*, 25(1).
- King, G., & Nielsen, R. (2019). Why propensity scores should not be used for matching. *Political Analysis*, 27(4).
- Kolesár, M., & Rothe, C. (2018). Inference in regression discontinuity designs with a discrete running variable. *American Economic Review*, 108(8).
- Lal, A., Lockhart, M., Xu, Y., & Zu, Z. (2024). How much should we trust instrumental variable estimates in political science? *Political Analysis*, 32(4)（卷期待核）。
- Lee, D. S., McCrary, J., Moreira, M. J., & Porter, J. (2022). Valid t-ratio inference for IV. *American Economic Review*, 112(10).
- McCrary, J. (2008). Manipulation of the running variable in the regression discontinuity design: A density test. *Journal of Econometrics*, 142(2).
- Montiel Olea, J. L., & Pflueger, C. (2013). A robust test for weak instruments. *JBES*, 31(3).
- Oster, E. (2019). Unobservable selection and coefficient stability: Theory and evidence. *JBES*, 37(2).
- Sant'Anna, P. H. C., & Zhao, J. (2020). Doubly robust difference-in-differences estimators. *Journal of Econometrics*, 219(1).
- VanderWeele, T. J., & Ding, P. (2017). Sensitivity analysis in observational research: Introducing the E-value. *Annals of Internal Medicine*, 167(4).
- Xu, Y. (2017). Generalized synthetic control method. *Political Analysis*, 25(1).
- 陈云松 (2012). 逻辑、想象和诠释：工具变量在社会科学因果推断中的应用. 《社会学研究》第 6 期（待核）。
- 胡安宁 (2012). 倾向值匹配与因果推论：方法论述评. 《社会学研究》第 1 期（待核）。
- 江艇 (2022). 因果推断经验研究中的中介效应与调节效应. 《中国工业经济》第 5 期。
