# 交错 DID 完整协议（Staggered Difference-in-Differences）

适用场景：处理在**不同单位于不同时点**开始生效——政策分批试点、逐省推开、逐年扩围（低碳城市试点、
智慧城市试点、自贸区分批设立、高铁分年开通、省直管县分批改革……）。中文公共管理/政治学/经济社会学
的政策评估稿件绝大多数属于此类。总入口文献：**Roth, Sant'Anna, Bilinski & Poe (2023, *Journal of
Econometrics* 235(2))** 的综述；本文按其框架落成可操作协议，并对接 `causal-panel-v1.schema.json` 的字段。

> 本协议的地位：`SKILL.md`"识别优先"表中 DID/事件研究两行的展开。凡处理时点 ≥2 个队列，先读本文再填
> `treatment_cohorts / control_group / parallel_trends / alternative_timing_plan / placebo_plan`。

## 0. 一页结论

1. 处理交错 + 效应可能随队列或时间变化 → **静态与动态 TWFE 都不作主结果**，只作对比列。
2. 主结果用**异质稳健估计量**之一：Callaway-Sant'Anna（CS）、Sun-Abraham（SA）、Borusyak-Jaravel-Spiess
   填补法（BJS）、Gardner 两步法（did2s）、Wooldridge 扩展 TWFE（ETWFE）、de Chaisemartin-D'Haultfœuille（dCDH）。
   至少报两种，且说明对照组是 never-treated 还是 not-yet-treated。
3. 平行趋势**不能被"检验通过"证明**：报预趋势图 + 预检验功效（Roth 2022）+ HonestDiD 敏感性（Rambachan & Roth 2023）。
4. 基期 = **处理前最后一期**（ℓ = −1）；有预期效应则把基期再往前推并在正文写明。
5. 聚类层级 = **处理分配层级**；簇数 < 约 40 用 wild cluster bootstrap；处理簇极少（≤5）另做置换/随机化推断。
6. 政策"发文年"与"实施年"不同时，主结果取**首个完整实施年**，另一口径进稳健性表，两者都要登记进
   `alternative_timing_plan`。

## 1. 为什么 TWFE 在交错处理下不能作主结果

### 1.1 静态 TWFE：负权重与"禁止比较"

标准双向固定效应回归 `Y_it = α_i + λ_t + β·D_it + ε_it` 在处理交错时，`β̂` 是全部可构造的 2×2 DID 的
**加权平均**（Goodman-Bacon 2021, *Journal of Econometrics* 225(2)）。这些 2×2 里有三类：
(a) 处理组 vs never-treated；(b) 早处理组 vs 晚处理组（晚处理组尚未处理时作对照）；
(c) **晚处理组 vs 早处理组（早处理组已处理后作对照）**。第 (c) 类是"禁止比较"（forbidden comparison）：
若早处理组的效应随时间变化（动态效应），它作为对照时会把自身效应的变化从晚处理组的估计里**减掉**，
结果可以偏小、偏大甚至变号。Bacon 分解的权重取决于各队列样本份额与处理时点在面板中的位置——
处理时点靠中间的队列权重最大，与效应大小无关。

de Chaisemartin & D'Haultfœuille (2020, *American Economic Review* 110(9)) 从另一角度证明：`β̂` 是各
(组, 期) 处理效应的加权和，权重加总为 1 但**可为负**；`twowayfeweights` 可直接算出负权重份额与
"效应异质到何种程度会让 β̂ 变号"的稳健性度量。Baker, Larcker & Wang (2022, *Journal of Financial
Economics* 144(2)) 用模拟说明在效应随处理时长增长时 TWFE 的偏误有多大。

### 1.2 动态 TWFE（事件研究）：各期系数互相污染

把处理拆成相对时间哑变量 `Σ_ℓ β_ℓ·1[t − G_i = ℓ]` 并不解决问题。Sun & Abraham (2021, *Journal of
Econometrics* 225(2)) 证明：在效应随队列异质时，`β̂_ℓ` 是本期效应与**其他相对期、其他队列**效应的
非凸线性组合；后果之一是**平行趋势成立时预处理期系数仍可能显著非零**——审稿人看到"预趋势显著"时
先问这一条。若两端 bin 被截断（把 ℓ ≤ −K 或 ℓ ≥ K 合并），污染更重。

### 1.3 什么情况下 TWFE 仍可作主结果

- 处理**同时**发生（单一时点）且有干净对照组——经典 2×2，TWFE 即 DID。
- 处理交错但研究者能论证效应同质（几乎不可能被证实；可用 Jakiela 2021 的简单诊断：
  按处理状态分块画残差化 `Y` 对残差化 `D` 的散点，看权重与效应是否与处理时长相关）。
- 其余情形：TWFE 只作对比列，正文写明"作为与既有文献可比的参照"。

### 1.4 异质稳健估计量一览

| 估计量 | 核心思路 | 默认对照 | 协变量 | 处理可退出 | 对预趋势的依赖 | 软件（R / Stata / Python） |
|---|---|---|---|---|---|---|
| CS：Callaway & Sant'Anna (2021) | 逐 (队列 g, 期 t) 估 `ATT(g,t)`，只用"干净"2×2，再按需聚合 | never- 或 not-yet-treated（可选） | 双重稳健 DR（Sant'Anna & Zhao 2020），协变量取基期值 | 否（要求吸收态处理） | 只需基期与 t 之间平行 | `did` / `csdid` / statspai `sp.callaway_santanna`、`csdid`、`differences` |
| SA：Sun & Abraham (2021) | 队列 × 相对期饱和交互，加权得各期 ATT | never-treated，缺则最晚处理队列 | 线性加入（非 DR） | 否 | 同上 | `fixest::sunab` / `eventstudyinteract` / pyfixest（待核是否内置） |
| BJS：Borusyak, Jaravel & Spiess (2024) | 用**未处理观测**拟合单位与时间固定效应，填补处理观测的 `Y(0)` | 全部未处理观测（含 not-yet） | 可加 | 否 | 要求**所有**前期平行且无预期，效率最高但对预趋势最敏感 | `didimputation` / `did_imputation` / 待核 |
| Gardner (2022) did2s | 两步：先用未处理观测估固定效应，再对残差回归处理哑变量 | 同 BJS | 可加 | 否 | 同 BJS | `did2s` / `did2s` / `pyfixest.did2s` |
| Wooldridge (2021) ETWFE | 队列 × 后期哑变量（× 协变量）饱和的 TWFE；可扩展到 Poisson/Logit（Wooldridge 2023, *Econometrics Journal* 26(3)） | never-treated 或 not-yet | 可加、可与队列交互 | 否 | 同 CS | `etwfe` / `jwdid` / — |
| dCDH (2020, 2024) | 比较"切换者"与"未切换者"；2024 版允许非二元、非吸收处理 | not-yet-switched | 可加 | **是** | 局部平行 | `DIDmultiplegtDYN` / `did_multiplegt_dyn` / — |
| 堆叠回归 Stacked DID（Cengiz, Dube, Lindner & Zipperer 2019, *QJE* 134(3)） | 每个队列配"干净"对照建子数据集，堆叠后加 队列×单位、队列×时间 FE | 各子集内 never/not-yet | 可加 | 否 | 同 CS | 手工 / `stackedev` / 手工 |
| LP-DID（Dube, Girardi, Jordà & Taylor 2023, NBER WP 31184，待核） | 局部投影逐期估计 | 干净对照 | 可加 | 是 | 局部平行 | `lpdid` / `lpdid` / `pyfixest.lpdid` |

选择判据：
- 有足够 never-treated 且处理吸收 → CS 为主，SA 或 BJS 为副。
- 没有 never-treated（全体最终都处理）→ CS 用 not-yet-treated；SA 以最晚队列为对照（其最后几期不可估）；
  BJS 亦可，但此时"最晚队列的后期"无对照，事件窗口自然截断，别硬画出来。
- 处理会退出或强度变化 → dCDH 2024 或 LP-DID；或者把处理重定义为"曾处理"（ITT 口径）并写明。
- 面板短、队列多、想要效率 → BJS，但必须同时报 CS，因为 BJS 在预趋势存在时偏误更大。
- 结果变量是计数/比例/有大量零 → ETWFE 的 Poisson 版或分别报广延与集约边际（见
  `empirical-research/references/data-preparation.md` 对 log(1+x) 的讨论）。

## 2. 决策流程

```
处理是否交错？ ──否──► 经典 2×2 DID（TWFE 可用）；仍要平行趋势图 + 安慰剂 + 聚类推断
   │是
是否存在 never-treated？
   ├─是 ► 主：CS(never)；副：CS(not-yet)、SA、BJS。两种对照结果差异大 → 先查 never-treated 是否"特殊"
   └─否 ► 主：CS(not-yet)；副：SA(最晚队列为对照)、BJS；正文写明最晚队列的后期无对照
处理是否吸收（一旦处理不退出）？
   ├─是 ► 上述估计量
   └─否 ► dCDH 2024 / LP-DID，或重定义为"曾处理"并说明 estimand 变化
聚合方式（从 ATT(g,t) 出发）：
   simple  = 全部后期 ATT(g,t) 按队列规模加权 → 主表单一系数
   dynamic = 按相对期 ℓ 聚合 → 事件研究图（主图）
   group   = 按队列聚合 → 检查结果是否由某一批试点驱动
   calendar= 按日历年聚合 → 检查是否由某一年（如疫情年）驱动
推断：聚类层级 = 处理分配层级；簇数少 → wild cluster bootstrap；处理簇 ≤5 → 置换推断
```

### 2.1 never-treated 与 not-yet-treated 的含义与风险

- **never-treated 作对照**：识别假设是"从未试点的单位与试点单位在无政策时趋势相同"。风险：从未入选的
  单位往往系统性不同（更穷、更远、能力更弱），条件平行趋势需要协变量（用 DR-DID）；样本末年仍未处理
  但之后会处理的单位被当成 never-treated，是"样本截断造成的假 never"，要在正文写明并做删除该组的稳健性。
- **not-yet-treated 作对照**：识别假设是"晚试点者在试点前的趋势与早试点者相同"，这通常更可信（同为试点
  候选），但要求**无预期效应**——晚试点者若提前调整（申报、准备），对照被污染。另需注意最晚队列的
  后期没有对照，事件窗口右端自动缩短。
- 两种对照都报；差异大不是"选一个好看的"的理由，而是识别假设可能不成立的信号。

### 2.2 事件研究图要件

横轴相对期（基期 ℓ = −1 标注为 0 且无置信区间）；纵轴 ATT；逐点 95% 置信区间之外**再加同时置信带**
（`did` 包 `cband = TRUE`）；水平零线；注明估计量、对照组、聚类层级与簇数；每个 ℓ 下方或脚注给出
贡献该期的队列数与观测数（远端 ℓ 往往只剩一两个队列）；两端是否 binned 要写明；若同时画 TWFE 与 CS，
用同一纵轴刻度。以处理前最后一期为基期（见 `SKILL.md`"实战教训"）。

## 3. 平行趋势：检验、敏感性、条件版本

### 3.1 预趋势检验的功效问题

Roth (2022, *AER: Insights* 4(3)) 指出两点：(i) 常见的预趋势检验对"足以改变结论的违背"功效很低，
"预处理期系数不显著"不等于平行趋势成立；(ii) 只在预检验通过后才报告的估计存在**预检验偏误**——通过筛选
的样本恰好是预趋势偶然有利的样本。操作：用 `pretrends`（R/Stata）计算"若存在能把主效应解释掉的线性
预趋势，现有检验以多大概率拒绝它"，功效 < 50% 就不能拿"预趋势不显著"当证据，只能作为与 HonestDiD
并列的描述。

### 3.2 HonestDiD 敏感性分析怎么做与怎么报

Rambachan & Roth (2023, *Review of Economic Studies* 90(5)) 的思路：不假设平行趋势精确成立，而是限定
**后处理期的违背相对于前处理期违背有多大**，在该限制下给出部分识别的置信区间。两类限制：
- **相对幅度 RM**：后期违背 ≤ M̄ × 前期最大违背。M̄ = 1 表示"后期趋势偏离不超过前期观察到的最大偏离"，
  是最常用的基准。
- **平滑 SD**：趋势的二阶差分（斜率变化）≤ M。适合前趋势近似线性的场合。

报告方式：(a) 一张图，横轴 M̄（或 M），纵轴 ATT 的稳健置信区间；(b) 报**崩溃值**（breakdown value）——
使区间开始包含 0 的最小 M̄；(c) 正文一句话："即便允许后处理期的平行趋势违背达到前处理期最大违背的
X 倍，效应仍显著为正"。实现：R `HonestDiD`（`honest_did()` 助手可直接吃 `did::aggte` 的动态输出）、
Stata `honestdid`（吃 `csdid` 或 `eventstudyinteract` 的系数与协方差）。需要至少 1 个（RM）或 2 个（SD）
前处理期系数。statspai 文档列有 `honest_did`，可用性以安装版本为准。

### 3.3 条件平行趋势与协变量

若平行趋势只在控制 X 后成立，用 Sant'Anna & Zhao (2020, *Journal of Econometrics* 219(1)) 的
**双重稳健 DR-DID**（结果回归 + 逆概率加权，任一模型正确即一致），CS 的 `xformla` 即此。规则：
- 协变量必须是**处理前**取值（基期值或时不变量）。把时变协变量直接塞进 TWFE 回归，若协变量本身受
  政策影响，就是"坏控制"，会吞掉部分效应（Caetano, Callaway, Payne & Rodrigues 2022 工作论文，待核）。
- 协变量的作用是让"条件于 X 的趋势"可比，不是"控制一切"。别放结果变量的滞后项（Nickell 偏误 + 坏控制）。
- 对照组与处理组在 X 上无重叠 → DR 权重爆炸，报重叠图并修剪，estimand 相应改为重叠总体上的 ATT。

### 3.4 预期效应与 Ashenfelter dip

- **预期效应**：政策公布到实施之间单位提前反应 → 基期（ℓ = −1）已含效应，估计偏小。处理：把基期前移
  （`did::att_gt(anticipation = k)`），或将"处理时点"定义为公布年而非实施年，两种口径都报。
- **Ashenfelter dip**（Ashenfelter 1978, *Review of Economics and Statistics* 60(1)）：单位在处理前一期
  结果暂时下滑（如被选中试点的恰是刚经历困难的城市），以该期为基期会**高估**效应。诊断：预处理期
  系数在 ℓ = −2, −3 显著为正而 ℓ = −1 为 0 就是信号。处理：基期改为 ℓ = −2 或 −3 并报敏感性；
  或用多期平均作基期。
- 基期的选择要在 `parallel_trends.window` 字段写明，并作为稳健性表的固定一行。

## 4. 其他设计问题

### 4.1 连续处理 / 剂量 DID

Callaway, Goodman-Bacon & Sant'Anna (2024, NBER WP 32117，待核) 证明：即使每个剂量水平的平行趋势都成立，
比较不同剂量以得到"剂量-反应斜率"仍需**强平行趋势**——所有单位在任一剂量下的潜在结果路径相同，即
不存在"按收益选剂量"。连续处理的 TWFE 同样有负权重问题。操作：优先报各剂量水平的 `ATT(d|d)`（水平效应）
并把剂量分箱；斜率解释要单独论证强平行趋势；把连续处理二值化（有/无）作为稳健性而非主结果。

### 4.2 处理退出与开关

CS/SA/BJS 假设处理是吸收态。试点被撤销、政策到期、企业退出园区等属于"开关"处理：用 dCDH 2024
（`did_multiplegt_dyn`）或 LP-DID；或将处理定义为"曾处理"（ITT）、或截断样本到首次退出前，三种
方案 estimand 不同，正文必须说明选择的是哪一个、为什么。

### 4.3 少聚类与推断

- 聚类层级取**处理分配层级**（Abadie, Athey, Imbens & Wooldridge 2023, *QJE* 138(1)）：省级政策 + 市级
  数据 → 按省聚类，簇数 ≤ 31。序列相关下不聚类会严重高估显著性（Bertrand, Duflo & Mullainathan 2004, *QJE* 119(1)）。
- 簇数少于约 40：wild cluster bootstrap（Cameron, Gelbach & Miller 2008, *Review of Economics and Statistics*
  90(3)；`boottest` / `fwildclusterboot` / `wildboottest`），报 bootstrap p 值与置信区间。
- **处理簇极少**（1–5 个省试点）：wild cluster bootstrap 也失效（MacKinnon & Webb 2018, *Econometrics Journal*
  21(2)），改用 Conley & Taber (2011, *Review of Economics and Statistics* 93(1)) 的置换推断或 Ferman & Pinto
  (2019, *Review of Economics and Statistics* 101(3)) 的异方差修正。
- CS 的默认推断是乘子 bootstrap，给同时置信带；簇数少时同样要换 wild bootstrap 或报置换分布。

### 4.4 SUTVA 与溢出

试点城市的政策会外溢到邻近非试点城市（示范、竞争、要素流动），对照组被污染时估计偏向零或偏离。
`spillover_plan` 至少写一条：(i) 删除与试点相邻（共享边界或 X 公里内）的对照单位重跑；(ii) 直接估计
"邻近处理"效应（对照组按与最近试点的距离分层）；(iii) 结果变量若是"份额/排名"类零和量，溢出是机制
的一部分，要在解释里承认。空间溢出 DID 的正式处理见 Butts (2023) 工作论文（待核）。

### 4.5 安慰剂

- **随机化处理时点**：只用处理前样本，把处理时点前移 1–3 期，效应应为 0。
- **随机化处理单位**：从全部单位随机抽同样数量作"伪处理组"（保留原时点分布），重复 500–1000 次，
  画伪系数分布并标注真实估计所在分位（Chetty, Looney & Kroft 2009, *AER* 99(4) 的做法）。真实估计落在
  分布 95% 以外才算通过；落在分布中间说明结果可能由面板结构而非政策驱动。
- **安慰剂结果**：理论上不应受政策影响的结果变量（如上一年已确定的存量）不应出现效应。
- 以上三项登记进 `placebo_plan`；安慰剂"未通过"要写进论文而非删掉。

### 4.6 中国情境常见坑

1. **试点分批**：几乎所有"国家级 XX 试点"都有 2–4 批，天然交错；第一批往往是能力最强的城市，
   队列间效应异质是常态，不是例外。
2. **试点选择内生**：申报制下入选与地方能力、领导重视度相关。至少做：把试点年份（或是否试点）对基期
   特征回归，报告哪些变量预测入选；用这些变量做 DR-DID；讨论选择与趋势的关系而不只是与水平的关系。
3. **聚类层级**：省级政策用市级数据，按省聚类而非按市；市级政策用企业数据，按市聚类。簇数由此决定
   推断方法（§4.3）。
4. **发文年 vs 实施年**：文件常在年末下发、次年生效；年中发文则当年只有半年暴露。主结果取首个完整
   实施年；发文年口径进稳健性；两者写进 `alternative_timing_plan`。
5. **政策叠加**：同一城市常同时是多个试点。至少列出与研究政策同期的其他重大试点，控制其哑变量或
   做三重差分；正文承认无法完全分离。
6. **样本末端队列**：最后一批试点只有 1–2 个后期，dynamic 聚合的远端不可靠；group 聚合能看出末端
   队列是否拉动结果。
7. **行政区划变更**导致的假"进入/退出"（撤县设区、撤地设市）：先按 `data-preparation.md` §5 对齐再定义处理。
8. **数据年份**：《中国城市统计年鉴》t 年卷载 t−1 年数据；政策年与数据年错位一年是最常见的手误。

## 5. 报告要件

### 5.1 主表

一列 TWFE（对比），至少两列异质稳健估计量（如 CS-never、CS-not-yet 或 SA），每列注明：estimand
（simple ATT 或指定窗口的平均动态 ATT）、对照组、协变量（基期值）、固定效应、标准误类型、聚类层级与
簇数、单位数与观测数、处理队列数、事件窗口。表下注写"TWFE 列仅供与既有文献比较，主结果为第 (2)–(3) 列"。

### 5.2 事件研究图

见 §2.2 八项要件。若正文只放一张图，放 CS(never) 的 dynamic 聚合，把 TWFE 与其他估计量的版本放附录，
但纵轴刻度一致。

### 5.3 稳健性表顺序

1. 换估计量（CS / SA / BJS / did2s / ETWFE）；2. 换对照组（never / not-yet / 删除样本末年才处理者）；
3. 换处理时点定义（发文年 / 实施年 / 前移一年）；4. 换基期（−1 / −2 / 多期平均）；5. HonestDiD 崩溃值；
6. 安慰剂三项；7. 删溢出邻居、删每一队列、删每一年（leave-one-out）；8. 推断替换（wild bootstrap /
置换）；9. 规格曲线（statspai `sp.spec_curve`）汇总以上全部。

### 5.4 审稿人最常见的 8 个问题及预案

| 质疑 | 预案 |
|---|---|
| "你用 TWFE，异质效应下有偏" | 主结果已是 CS/SA；报 Bacon 分解中禁止比较的权重份额与 `twowayfeweights` 负权重份额 |
| "预趋势不显著不等于平行趋势成立" | 报 `pretrends` 功效 + HonestDiD 崩溃值；正文措辞改为"在允许 X 倍违背时仍稳健" |
| "试点非随机" | 入选预测回归 + DR-DID + not-yet 对照 + 讨论"选择依赖水平而非趋势"的理由 |
| "对照组被溢出污染" | 删相邻对照重跑；报距离分层的溢出估计 |
| "簇太少" | wild cluster bootstrap p 值；处理簇 ≤5 用置换推断；照实报告边缘显著 |
| "政策时点定义任意" | `alternative_timing_plan` 里的两种口径都在稳健性表 |
| "结果由某一批试点或某一年驱动" | group 与 calendar 聚合 + leave-one-cohort/year-out |
| "同期其他政策混淆" | 列出同期试点；控制或三重差分；安慰剂结果变量 |

## 6. 实现对照表

| 任务 | Python | R | Stata |
|---|---|---|---|
| Bacon 分解 | 待核 | `bacondecomp` | `bacondecomp` |
| 负权重诊断 | — | `TwoWayFEWeights` | `twowayfeweights` |
| CS 估计与聚合 | statspai `sp.callaway_santanna`；`csdid`（PyPI）；`differences` | `did::att_gt` + `aggte` | `csdid` |
| SA 交互加权 | 待核 | `fixest::sunab` | `eventstudyinteract` |
| BJS 填补法 | 待核 | `didimputation` | `did_imputation` |
| Gardner 两步法 | `pyfixest.did2s` | `did2s` | `did2s` |
| ETWFE | — | `etwfe` | `jwdid` |
| dCDH 开关处理 | — | `DIDmultiplegtDYN` | `did_multiplegt_dyn` |
| DR-DID（2×2） | — | `DRDID` | `drdid` |
| 预趋势功效 | — | `pretrends` | `pretrends` |
| HonestDiD | statspai `honest_did`（版本待核） | `HonestDiD` | `honestdid` |
| wild cluster bootstrap | `wildboottest` | `fwildclusterboot` | `boottest` |
| 事件研究图 | statspai `sp.event_study` + `sp.enhanced_event_study_plot` | `did::ggdid`、`fixest::iplot` | `event_plot`、`csdid_plot` |
| 规格曲线 | statspai `sp.spec_curve` | `specr` | `speccurve`（待核） |

## 7. 与 `causal-panel-v1` 契约的字段对接

| 字段 | 本文对应 | 最低要求 |
|---|---|---|
| `treatment_cohorts` | §2、§4.6 | 列每一队列的处理年、单位数、是否在样本末年才处理 |
| `control_group` | §2.1 | never / not-yet / 二者皆报；说明为何 |
| `pre_treatment_window` | §2.2、§3.5 | 基期与前期长度；binned 端点 |
| `parallel_trends.status / window / diagnostic_artifact_id` | §3 | 事件研究图 + `pretrends` 功效 + HonestDiD 崩溃值三件套的工件 ID |
| `spillover_plan` | §4.4 | 至少一条可执行方案 |
| `clustering_level` | §4.3 | 层级、簇数、少簇修正 |
| `alternative_timing_plan` | §4.6 第 4 条 | 发文年 / 实施年 / 前移 |
| `placebo_plan` | §4.5 | 时点、单位、结果三类 |

## 参考文献（作者 + 年份 + 出处；标"待核"者投稿前核对卷期）

- Abadie, A., Athey, S., Imbens, G. W., & Wooldridge, J. M. (2023). When should you adjust standard errors for clustering? *Quarterly Journal of Economics*, 138(1).
- Ashenfelter, O. (1978). Estimating the effect of training programs on earnings. *Review of Economics and Statistics*, 60(1).
- Baker, A. C., Larcker, D. F., & Wang, C. C. Y. (2022). How much should we trust staggered difference-in-differences estimates? *Journal of Financial Economics*, 144(2).
- Bertrand, M., Duflo, E., & Mullainathan, S. (2004). How much should we trust differences-in-differences estimates? *Quarterly Journal of Economics*, 119(1).
- Borusyak, K., Jaravel, X., & Spiess, J. (2024). Revisiting event-study designs: Robust and efficient estimation. *Review of Economic Studies*, 91(6).
- Butts, K. (2023). Difference-in-differences with spatial spillovers. 工作论文（待核）。
- Callaway, B., & Sant'Anna, P. H. C. (2021). Difference-in-differences with multiple time periods. *Journal of Econometrics*, 225(2).
- Callaway, B., Goodman-Bacon, A., & Sant'Anna, P. H. C. (2024). Difference-in-differences with a continuous treatment. NBER Working Paper 32117（待核）。
- Cameron, A. C., Gelbach, J. B., & Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. *Review of Economics and Statistics*, 90(3).
- Cengiz, D., Dube, A., Lindner, A., & Zipperer, B. (2019). The effect of minimum wages on low-wage jobs. *Quarterly Journal of Economics*, 134(3).
- Chetty, R., Looney, A., & Kroft, K. (2009). Salience and taxation: Theory and evidence. *American Economic Review*, 99(4).
- Conley, T. G., & Taber, C. R. (2011). Inference with "difference in differences" with a small number of policy changes. *Review of Economics and Statistics*, 93(1).
- de Chaisemartin, C., & D'Haultfœuille, X. (2020). Two-way fixed effects estimators with heterogeneous treatment effects. *American Economic Review*, 110(9).
- de Chaisemartin, C., & D'Haultfœuille, X. (2024). Difference-in-differences estimators of intertemporal treatment effects. *Review of Economics and Statistics*（卷期待核）。
- Dube, A., Girardi, D., Jordà, Ò., & Taylor, A. M. (2023). A local projections approach to difference-in-differences event studies. NBER Working Paper 31184（待核）。
- Ferman, B., & Pinto, C. (2019). Inference in differences-in-differences with few treated groups and heteroskedasticity. *Review of Economics and Statistics*, 101(3).
- Gardner, J. (2022). Two-stage differences in differences. 工作论文（arXiv 2207.05943）。
- Goodman-Bacon, A. (2021). Difference-in-differences with variation in treatment timing. *Journal of Econometrics*, 225(2).
- Jakiela, P. (2021). Simple diagnostics for two-way fixed effects. 工作论文（arXiv 2103.13229，待核编号）。
- MacKinnon, J. G., & Webb, M. D. (2018). The wild bootstrap for few (treated) clusters. *Econometrics Journal*, 21(2).
- Rambachan, A., & Roth, J. (2023). A more credible approach to parallel trends. *Review of Economic Studies*, 90(5).
- Roth, J. (2022). Pretest with caution: Event-study estimates after testing for parallel trends. *American Economic Review: Insights*, 4(3).
- Roth, J., Sant'Anna, P. H. C., Bilinski, A., & Poe, J. (2023). What's trending in difference-in-differences? A synthesis of the recent econometrics literature. *Journal of Econometrics*, 235(2).
- Sant'Anna, P. H. C., & Zhao, J. (2020). Doubly robust difference-in-differences estimators. *Journal of Econometrics*, 219(1).
- Sun, L., & Abraham, S. (2021). Estimating dynamic treatment effects in event studies with heterogeneous treatment effects. *Journal of Econometrics*, 225(2).
- Wooldridge, J. M. (2021). Two-way fixed effects, the two-way Mundlak regression, and difference-in-differences estimators. 工作论文（SSRN）。
- Wooldridge, J. M. (2023). Simple approaches to nonlinear difference-in-differences with panel data. *Econometrics Journal*, 26(3).
- 刘冲、沙学康、张妍 (2022). 交错双重差分：处理效应异质性与估计方法选择. 《数量经济技术经济研究》第 9 期（待核）。
- 江艇 (2022). 因果推断经验研究中的中介效应与调节效应. 《中国工业经济》第 5 期。
