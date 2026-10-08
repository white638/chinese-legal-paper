# 数据准备与变量构造指南

面向中文公共管理 / 政治学 / 经济社会学定量研究者。定位：`quant-causal-inference` 流水线 §数据 步骤的操作
手册，与 `reproducibility.md`（`repro_pack.py`）配套；与 `method-adapters.md`"定量"一节的要求一致。

## 0. 原则：每个清洗决策都是研究决策

- **分叉路径**：缩尾比例、缺失处理、样本期、删哪些城市……每一处都是一次未登记的自由度（Gelman & Loken
  2014, *American Scientist* 102(6)）。同一份数据换几种"合理"清洗就能让系数换号，这不是清洗问题，是研究
  设计问题。对策不是不做选择，而是**先写下、再执行、全部报告**（规格曲线：Simonsohn, Simmons & Nelson
  2020, *Nature Human Behaviour* 4；多重宇宙：Steegen et al. 2016, *Perspectives on Psychological Science* 11(5)）。
- **与 `reproducibility.md` 对接**：
  - 每个数据文件 → `repro_pack.py add-source --file ... --source-url ... --access-date ...`（sha256 锁定）。
  - 每一步样本排除 → `exclude --step "删缺失因变量" --n-before N0 --n-after N1`，构成 `sample_log.json`
    的样本构造链，正文脚注直接引用。
  - 每条清洗规则（缩尾水平、插补方法、平减指数、区划对齐口径）→ `decision --date --what --why`，
    **在动手之前**登记；事后改动再记一条，说明为何偏离。
  - 清洗脚本放 `scripts/`，`data/raw/` 只读，`data/clean/` 只能由脚本生成；不允许手改 Excel。
- **先写数据契约再动手**。最小契约字段：

```
来源与版本      年鉴名/数据库名、卷/版本、发布日期、获取日期、URL 或 DOI、表号
单位与时间      观测单位（城市/县/企业/个人）、时间频率、起止年、是否平衡面板
主键            id 字段、年份字段；(id, year) 唯一性承诺
核心变量定义    结果 / 处理 / 协变量各自的原始字段、口径、单位（万元/亿元/%）
预期样本量      按来源应有的 N；差异必须在 sample_log 里解释
缺失策略        每个变量的缺失机制判断与处理（§1）
异常值策略      缩尾/截尾水平、按年还是合并（§2）
平减            指数名、基期、来源（§3）
合并键          跨表合并用的代码、年份对齐规则（§5）
预注册的替代口径 哪些变量有第二种测量、都要报（§7）
```

## 1. 缺失

### 1.1 先判断机制，再选方法

| 机制 | 含义 | 判断思路 | 备注 |
|---|---|---|---|
| MCAR 完全随机 | 缺失与一切无关 | Little (1988, *JASA* 83(404)) 检验只能拒绝 MCAR，不能证明 | 现实中少见 |
| MAR 随机 | 缺失只依赖已观测变量 | 把"是否缺失"对已观测变量回归，看谁预测缺失 | 多重插补 / FIML 的前提 |
| MNAR 非随机 | 缺失依赖未观测值本身 | 靠实质判断：不报某指标的县往往就是该指标差的县 | 需选择模型、模式混合模型或界 |

机制不可被数据"证明"，只能论证；论证写进正文或附录，不写就是默认 MCAR，审稿人会问。

### 1.2 方法的适用与禁忌

| 方法 | 无偏条件 | 禁忌 |
|---|---|---|
| 列删（完整案例） | MCAR；或缺失只在协变量、且给定协变量后与 Y 无关（White & Carlin 2010, *Statistics in Medicine* 29(28)） | 缺失比例大且与 Y 相关时有偏、功效损失 |
| 对删（pairwise） | 无 | 各统计量样本不一致，回归中禁用 |
| 均值/单一插补 | 无 | 低估方差、扭曲相关，只能用于纯预测特征 |
| 多重插补 MI（Rubin 1987） | MAR + 插补模型包含分析模型所有变量（含结果、交互项） | 插补模型漏掉分析变量（不相容） |
| FIML | MAR，SEM/极大似然框架 | 非似然估计量（如 2SLS、匹配）不适用 |
| 选择模型 / 模式混合 | MNAR，需排除约束或敏感性参数 | 把 Heckman 当万能修正 |
| 界（Manski / Lee 2009, *REStud* 76(3)） | 最弱假设 | 区间可能太宽而无结论——但诚实 |

MI 操作要点：m 取多少——旧规则 3–5 个已不够；按 White, Royston & Wood (2011, *Statistics in Medicine*
30(4))，m ≥ 不完整案例百分比（缺 30% 则 m ≥ 30）；Graham, Olchowski & Gilreath (2007, *Prevention Science*
8(3)) 从功效角度给出类似量级。合并用 Rubin 规则（点估计取均值，方差 = 组内 + (1 + 1/m) × 组间）。面板
数据用 Amelia 类方法加时间多项式与前后期（Honaker & King 2010, *AJPS* 54(2)）；插补后的结果变量可用
"先插补后删除"（von Hippel 2007, *Sociological Methodology* 37(1)）。软件：R `mice`（van Buuren 2018）、
`Amelia`；Stata `mi`；Python `statsmodels.imputation.mice`。

### 1.3 缺失指示变量法的问题

对协变量缺失加一个"缺失=1"哑变量并把缺失值填 0/均值，即使 MCAR 也有偏（Jones 1996, *JASA* 91(433)；
Allison 2001）。仅在随机试验中（处理已随机）对协变量可接受。观察研究的因果回归里不要用。

### 1.4 面板中的"缺失即退出"

- 个体/企业/城市在某年后消失，是**样本流失**，不是随机缺失。诊断：把"下一期是否流失"对基期特征与
  滞后结果回归（Fitzgerald, Gottschalk & Moffitt 1998, *Journal of Human Resources* 33(2)），显著即流失与
  结果相关。
- 处理：逆概率流失权重（Wooldridge 2002, *Portuguese Economic Journal* 1）；Lee (2009) 界；报"仅留存样本"
  与"含流失前观测"两版。
- 企业数据中的退出（注销、并购、降到规模线以下）是**结果**的一部分——不能当缺失删掉，要单独作为结果报。

### 1.5 缺失比例阈值只是经验法则

"缺失 > 5%/10%/40% 就……"没有理论依据；Madley-Dowd et al. (2019, *Journal of Clinical Epidemiology* 110)
明确指出缺失比例不应决定是否 MI，关键是机制与缺失信息比例 FMI。正文写明：变量缺失比例、机制判断、
方法、m、以及列删版本的结果对照。

## 2. 异常值与极端值

### 2.1 录入错误 vs 真实极端

先查错再谈处理：单位错（万元/亿元）、小数点移位、非负变量为负、同一单位同年重复行、同比变化 > 10 倍、
市辖区 > 全市、分省加总 ≠ 全国。能回原始年鉴核实的**改正并登记**（`decision`），不能核实的删除并登记
（`exclude`）。真实极端（北上广深的 GDP、个别县的矿业收入）不是错误，处理方式属于 §2.2。

### 2.2 缩尾与截尾：何时合理、何时是操纵

- 缩尾（winsorize，1%/99% 替换为分位值）保留样本、压缩杠杆；截尾（trim）删除，改变总体。二者都要在
  数据契约里预先写明水平与"按年/合并"方式。
- **只对连续的结果与协变量做**，不对处理哑变量、比例上下界明确的变量（0–1 份额）做。
- **必报未缩尾结果**；再报 0 / 1% / 2.5% / 5% 一列对照。Leone, Minutti-Meza & Wasley (2019, *The Accounting
  Review* 94(6)) 比较发现稳健回归（Huber/MM）通常优于缩尾；Cook 距离与 DFBETA 诊断可指出哪些观测在驱动结果。
- 操纵信号：事后调整缩尾水平直至显著；只在某一变量上缩尾；单侧缩尾无理由；缩尾残差而非变量。
  这些都能被规格曲线暴露。

### 2.3 对数变换、log(1+x) 与 IHS

- 结果变量含大量零时，log(1+x) 与反双曲正弦 IHS 的"百分比效应"解释不成立：Chen & Roth (2024, *QJE*
  139(2)) 证明其 ATE 随测量单位任意变化（把元换成万元，估计就变），不是尺度不变的估计对象。IHS 的弹性
  同样依赖尺度（Bellemare & Wichman 2020, *Oxford Bulletin* 82(1)）。
- 替代：(a) 分别报广延边际 1[Y > 0] 与集约边际 log(Y | Y > 0)；(b) 水平值上跑 Poisson/PPML（Silva &
  Tenreyro 2006, *REStat* 88(4)；非计数的非负变量同样适用），系数近似为比例效应；(c) 直接报水平效应；
  (d) 明确定义"零与正值之间的权衡"作为估计对象。已发表文献用 log(1+x) 不构成沿用理由。
- **比率变量分母为零**：不要静默设为 0 或删除。改用份额（分子/总量）、把分母作控制、或按 Kronmal (1993,
  *JRSS-A* 156(3)) 的建议避免比率作因变量；登记处理的观测数。

## 3. 平减与可比

- **指数与变量匹配**：GDP/增加值 → GDP 平减指数；居民收入、工资、消费 → CPI；固定资产投资 → 固定资产
  投资价格指数；工业产值 → 工业生产者出厂价格指数（分行业更好，Brandt, Van Biesebroeck & Zhang 2012,
  *Journal of Development Economics* 97(2) 给出工企库的分行业投入/产出平减做法）。
- **年鉴给的是"上年 = 100"环比**，要链式累乘到基期：`P_t = P_{t−1} × 指数_t / 100`，基期设 100；基期年份
  写进契约，换基期只改水平不改增长率。
- **年份固定效应吸收全国共同价格变化**，但不吸收省际差异；有省级 CPI 就用省级；跨省水平比较还需空间
  价格平减（Brandt & Holz 2006, *Economic Development and Cultural Change* 55(1)，2000 年基期，更新版本待核）。
- **汇率**：流量（FDI、进出口）用年均汇率，存量用年末；数据来源（国家统计局/人民银行）与 1994 年汇率
  并轨前后的口径写明；美元额先换算再平减，或直接用美元平减指数，二选一并写明。
- 对数结果 + 年份 FE 时名义值与实际值的系数相同（共同平减被吸收），但描述统计表仍要报实际值并注明基期。

## 4. 指数与合成变量

| 方法 | 适用 | 陷阱 |
|---|---|---|
| 等权 | 指标数少、理论上等重要 | 量纲与方向必须先统一 |
| 主成分 PCA | 指标高度相关、只要一个"综合水平" | 第一主成分未必对应概念；载荷符号不定；载荷随样本变；解释方差比例要报 |
| 熵值法 | 中文文献常用 | 权重由样本**离散度**决定而非理论重要性——离散大的指标自动得高权重；权重随样本（加一年、加一市）变化，逐年分别计算会使面板不可比，须在**全样本合并**上计算（"全局熵值法"）并说明；极差标准化后极端值主导；负向指标的方向一致化与"+0.0001 平移处理零值"都影响结果 |
| 层次分析 AHP（Saaty 1980） | 有专家判断 | 主观；报判断矩阵与一致性比率 CR < 0.1；专家构成写明 |
| TOPSIS 等距离法 | 排序目的 | 与权重法叠加时误差累积 |

通用要求（OECD/JRC 2008 *Handbook on Constructing Composite Indicators*；Greco, Ishizaka, Tasiou & Torrisi
2019, *Social Indicators Research* 141）：指标清单（来源、方向、标准化方式）、权重表、加总方式（加法可补偿，
几何不可补偿）、稳健性（换权重方法重跑主回归；权重随机扰动后的排名相关）。正文披露：主指数用什么方法，
附录给等权/PCA/熵值三版权重与主回归对照；指数作解释变量时说明测量误差导致的衰减方向。

## 5. 中国面板特有问题

### 5.1 行政区划代码跨年变更

- **代码表来源**：民政部《中华人民共和国行政区划代码》历年表与区划变更公告；国家统计局《统计用区划代码
  和城乡划分代码》（逐年）。两套代码在县级以上一致，乡镇级不同。
- **变更类型与处理**：
  - 撤县设区：县从县级面板消失，市辖区口径突然扩大。方案 A（固定边界）——按参考年（如 2020）边界把前期
    县合并进市辖区；方案 B——保留原单位并把变更年作为事件；方案 C——删除变更单位。三者 estimand 不同，
    写明选择与受影响单位数（唐为、王媛 2015, 《经济研究》第 9 期，待核）。
  - 撤地设市：地区/盟/自治州升地级市（如铜仁、毕节 2011，海东 2013，日喀则、昌都 2014，林芝 2015，哈密、
    山南 2016，那曲 2017），升格前多无市级统计——是"进入"而非缺失。
  - 撤销与合并：巢湖 2011 拆入合肥/芜湖/马鞍山；莱芜 2019 并入济南；三沙 2012 新设；儋州 2015 升格。
  - 省直管县（财政）：多数省份代码不变但财政关系变，可能就是研究的处理变量；口径写明是"财政直管"还是
    "行政直管"（海南等）。
- **操作**：建一张 (代码, 年份) → 稳定 ID 的交叉表放 `data/clean/crosswalk_*.csv`，登记来源；合并前先按
  年份对齐代码，再合并；变更单位打 `boundary_change` 标记，主结果删除该标记单位作稳健性。

### 5.2 "市辖区"与"全市"口径

《中国城市统计年鉴》双口径并列。市辖区边界随撤县设区变动，全市边界相对稳定。规则：概念指向城市核心
（城区人口、建成区）用市辖区并处理 §5.1 的跳变；其余用全市；**同一回归不混用两种口径**；描述统计表注明口径。

### 5.3 统计年鉴修订与普查年跳变

- 经济普查（2004、2008、2013、2018、2023）后 GDP 等指标回溯修订；人口普查（2010 六普、2020 七普）与 1%
  抽样（2005、2015）年份常住人口重新基准化，部分省份回溯修订，部分不修——同一变量在普查年出现跳变。
- 年鉴后续版本会修订前一年数据。规则二选一并写明：每年取自次年年鉴（初值）或统一取自最新版（修订值）；
  不能混用。
- 常住人口与户籍人口不是同一变量；人均指标的分母写明用哪一个，两者差异在流入地极大。
- 地方 GDP "挤水分"（辽宁 2017、内蒙古与天津 2018 等）造成结构断裂；涉及省份加断裂哑变量或做删除稳健性。
- 2007 年政府收支分类改革使财政收支科目断裂；2011 年规模以上工业企业门槛由 500 万元升至 2000 万元；
  这些口径变化写进契约的"口径变更"栏。

### 5.4 删除直辖市 / 自治州的惯例与理由

地级市面板常删北京、天津、上海、重庆（行政级别为省级，财政与人事体制不可比）与自治州/盟/地区（非地级市、
统计口径与覆盖不同），有时删西藏（数据缺失）。**理由是可比性与数据可得性，不是"它们是离群值"**——
后者是按结果删样本。主结果删除，稳健性保留全样本；两种 N 都在 sample_log 登记。

### 5.5 缺年插补的诚实披露

地方志、早年年鉴常缺整年。可插补的只有**变化缓慢的存量**（人口、道路里程、耕地面积），线性插补一年并打
`imputed` 标记，稳健性删除插补观测。**结果变量与处理变量不插补，端点不外推**。正文或附录给出插补观测数
与比例。

### 5.6 企业数据库（工企库）的断裂与匹配

- 覆盖 1998–2013（2014 起停更）；2010 年缺工业增加值等关键变量；2008–2009 年部分财务指标缺失；2011 年
  门槛变更导致样本构成断裂；2007 年以后行业分类口径调整。
- 匹配：法人代码跨年重复使用，须按 Brandt et al. (2012) 的顺序——代码 → 名称 → 法定代表人 + 电话 + 地址
  → 成立年份 + 行业 + 区县——逐级匹配并记录每级匹配的比例。
- 清洗惯例（Cai & Liu 2009, *Economic Journal* 119(537)；聂辉华、江艇、杨汝岱 2012, 《世界经济》第 5 期）：
  删除从业人员 < 8、总资产/固定资产/销售额缺失或为负、流动资产 > 总资产、累计折旧 < 当期折旧、成立年份
  无效等；每条规则 `exclude` 登记。
- 分行业平减（§3）；全要素生产率的计算方法（OP/LP/ACF）属于变量构造决策，登记。

### 5.7 追踪调查（CFPS / CGSS / CHIP 等）的权重与追踪

- 抽样权重与面板权重的变量名随波次变化，以官方用户手册为准（待核具体字段）。描述性总体估计**必须**加权；
  因果回归是否加权按 Solon, Haider & Wooldridge (2015, *Journal of Human Resources* 50(2))：效应异质且要总体
  平均、或抽样依赖结果时加权，否则不加权并控制分层变量；两版都报。
- 个体 ID 跨波次稳定，家庭 ID 会随分家变化；变量措辞与选项跨波次改变（收入定义、量表刻度）要逐波对齐
  并记录；流失按 §1.4 处理。
- CGSS 为重复截面（部分年份有追踪模块），不能当个体面板用。

### 5.8 其他常见数据源的断裂

夜间灯光 DMSP（1992–2013）与 VIIRS（2012 起）不可直接拼接，用校准数据集（Li, Zhou, Zhao & Zhao 2020,
*Scientific Data* 7）；县级年鉴覆盖逐年不同；2000 年前地级市数据零散。

## 6. 面板平衡与样本期

- 固定效应估计在非平衡面板上仍一致，条件是缺失机制可忽略（Wooldridge 2010）；**强制平衡**（删除任何
  有缺失年的单位）等于只留"幸存者"，引入选择。默认用非平衡面板，报平衡面板作稳健性，并解释两者差异。
- 进入/退出：新设单位（升格城市、新企业）与退出单位的处理写明；DID 中样本开始前已处理的单位（always-
  treated）无法贡献识别，Callaway-Sant'Anna 会自动剔除，TWFE 不会——手动剔除并登记。
- 样本期截断：起止年由数据可得性或政策变更决定，不能由结果决定；换起止年是稳健性表的固定一行。
- 面板检查清单：(id, year) 唯一；时间无缺口或缺口已标记；时不变变量确实时不变；处理变量若用吸收态估计量
  则单调不减；每年单位数表放附录。

## 7. 变量构造与测量

- **核心解释变量多种测量并报**：如"数字经济水平"有指数、专利数、企业数三种口径，预注册主口径，三种全报；
  只报显著的那种是选择性报告。结果变量同理。
- **哑变量基准组**：解释只相对基准组；基准组取最大或理论上有意义的类别并在表注写明。
- **交互项中心化**：中心化只改变主效应的解释（"M 取均值时 D 的效应"而非"M = 0 时"），不改变交互系数，
  也不真正解决共线性（Aiken & West 1991）；交互项的诊断走 `identification-designs.md` §4.4。
- **高维固定效应吸收后的解释**：城市 + 年份 FE 下系数来自城市内跨年变异，时不变变量（地理、历史）被吸收
  而非"被控制"，不能再解释其系数；省 × 年 FE 下识别来自同省内城市间差异；城市 × 年 FE 下城市级变量无
  变异可用。表注写明"被吸收的变量"。
- **滞后一期不解决内生性**（Bellemare, Masaki & Pepinsky 2017, *Journal of Politics* 79(3)）；只在理论指出
  时序时使用滞后解释变量，并说明。
- **标准化与单位**：百分比变量写明 0–1 还是 0–100；标准化系数只在需要比较不同量纲的效应大小时报。
- **测量误差**：代理变量的经典测量误差使系数向零衰减；处理变量的误差在 DID 中意味着错分——写明代理与
  概念的距离。

## 8. 数据真实性与口径核验

- 每个来源记：官方名称、卷/版本、出版/更新日期、获取日期、URL/DOI、表号或字段名。二手汇编（EPS、CNRDS、
  CSMAR、Wind、中经网等）**回原始年鉴抽查**：随机抽 ≥ 5% 或 ≥ 30 个 (单位, 年份, 变量) 单元核对，登记
  不一致数与处理方式。
- 口径变更（§5.3）逐条列在附录"数据说明"。
- 一致性检查：分省加总与全国、市辖区 ≤ 全市、份额加总 = 1、增长率与水平互相印证、单位统一。
- PDF/OCR 年鉴的数字要抽查小数点与千分位。
- 以上全部落到 `provenance.json` 与 `decisions.jsonl`，`repro_pack.py check` 不过不投稿。

## 9. 数据准备自检清单

1. 每个数据文件已 `add-source`，sha256 与行列数登记。
2. 数据契约在清洗前写完并冻结（`decision` 登记）。
3. (id, year) 唯一性已验证；重复行已处理并登记。
4. 每个变量的缺失比例与机制判断已写；方法与 m 已登记。
5. 面板流失已诊断（流失对基期特征回归）。
6. 录入错误已核对原始来源；改正与删除分别登记。
7. 缩尾/截尾水平与方式预先登记；未缩尾结果保留。
8. 结果变量含零时未用 log(1+x)/IHS 作主结果，或已论证估计对象。
9. 比率变量分母为零的处理已登记。
10. 平减指数、基期、来源写明；环比已链式换算。
11. 合成指数的指标、方向、标准化、权重、替代权重结果齐备。
12. 行政区划交叉表建立并登记来源；变更单位已标记。
13. 市辖区/全市口径统一。
14. 普查年与修订版本规则写明；断裂哑变量或稳健性已做。
15. 删除直辖市/自治州的理由写明，全样本稳健性已跑。
16. 插补观测已标记并报数量。
17. 企业库匹配逐级比例已记录。
18. 调查权重使用规则写明，加权/不加权两版都有。
19. 平衡/非平衡面板选择写明；每年单位数表已备。
20. 核心变量的替代测量已预注册并全部报告。
21. 高维 FE 吸收的变量在表注列出。
22. 二手数据抽查已做，不一致已登记。
23. `repro_pack.py check` 通过。

## 10. 必须在正文或附录披露的最小清单

- 数据来源与版本、获取日期、口径变更说明。
- 样本构造链（每步 n_before → n_after）与最终 N。
- 变量定义表：原始字段、单位、口径、平减、缩尾、变换。
- 缺失处理：比例、机制判断、方法。
- 行政区划对齐规则与受影响单位数。
- 删除的单位类别（直辖市/自治州/西藏等）及理由。
- 插补观测数量与标记。
- 合成指数的构造方法与权重。
- 面板平衡性与样本期选择理由。
- 核心变量的替代测量及其结果。

## 参考文献（作者 + 年份 + 出处；标"待核"者投稿前核对）

- Aiken, L. S., & West, S. G. (1991). *Multiple Regression: Testing and Interpreting Interactions*. Sage.
- Allison, P. D. (2001). *Missing Data*. Sage.
- Bellemare, M. F., & Wichman, C. J. (2020). Elasticities and the inverse hyperbolic sine transformation. *Oxford Bulletin of Economics and Statistics*, 82(1).
- Bellemare, M. F., Masaki, T., & Pepinsky, T. B. (2017). Lagged explanatory variables and the estimation of causal effect. *Journal of Politics*, 79(3).
- Brandt, L., & Holz, C. A. (2006). Spatial price differences in China: Estimates and implications. *Economic Development and Cultural Change*, 55(1).
- Brandt, L., Van Biesebroeck, J., & Zhang, Y. (2012). Creative accounting or creative destruction? Firm-level productivity growth in Chinese manufacturing. *Journal of Development Economics*, 97(2).
- Cai, H., & Liu, Q. (2009). Competition and corporate tax avoidance: Evidence from Chinese industrial firms. *Economic Journal*, 119(537).
- Chen, J., & Roth, J. (2024). Logs with zeros? Some problems and solutions. *Quarterly Journal of Economics*, 139(2).
- Fitzgerald, J., Gottschalk, P., & Moffitt, R. (1998). An analysis of sample attrition in panel data. *Journal of Human Resources*, 33(2).
- Gelman, A., & Loken, E. (2014). The statistical crisis in science. *American Scientist*, 102(6).
- Graham, J. W., Olchowski, A. E., & Gilreath, T. D. (2007). How many imputations are really needed? *Prevention Science*, 8(3).
- Greco, S., Ishizaka, A., Tasiou, M., & Torrisi, G. (2019). On the methodological framework of composite indices. *Social Indicators Research*, 141.
- Honaker, J., & King, G. (2010). What to do about missing values in time-series cross-section data. *American Journal of Political Science*, 54(2).
- Jones, M. P. (1996). Indicator and stratification methods for missing explanatory variables in multiple linear regression. *JASA*, 91(433).
- Kronmal, R. A. (1993). Spurious correlation and the fallacy of the ratio standard revisited. *JRSS-A*, 156(3).
- Lee, D. S. (2009). Training, wages, and sample selection: Estimating sharp bounds on treatment effects. *Review of Economic Studies*, 76(3).
- Leone, A. J., Minutti-Meza, M., & Wasley, C. E. (2019). Influential observations and inference in accounting research. *The Accounting Review*, 94(6).
- Li, X., Zhou, Y., Zhao, M., & Zhao, X. (2020). A harmonized global nighttime light dataset 1992–2018. *Scientific Data*, 7.
- Little, R. J. A. (1988). A test of missing completely at random for multivariate data with missing values. *JASA*, 83(404).
- Madley-Dowd, P., Hughes, R., Tilling, K., & Heron, J. (2019). The proportion of missing data should not be used to guide decisions on multiple imputation. *Journal of Clinical Epidemiology*, 110.
- OECD & JRC (2008). *Handbook on Constructing Composite Indicators: Methodology and User Guide*. OECD.
- Rubin, D. B. (1987). *Multiple Imputation for Nonresponse in Surveys*. Wiley.
- Saaty, T. L. (1980). *The Analytic Hierarchy Process*. McGraw-Hill.
- Silva, J. M. C. S., & Tenreyro, S. (2006). The log of gravity. *Review of Economics and Statistics*, 88(4).
- Simonsohn, U., Simmons, J. P., & Nelson, L. D. (2020). Specification curve analysis. *Nature Human Behaviour*, 4.
- Solon, G., Haider, S. J., & Wooldridge, J. M. (2015). What are we weighting for? *Journal of Human Resources*, 50(2).
- Steegen, S., Tuerlinckx, F., Gelman, A., & Vanpaemel, W. (2016). Increasing transparency through a multiverse analysis. *Perspectives on Psychological Science*, 11(5).
- van Buuren, S. (2018). *Flexible Imputation of Missing Data* (2nd ed.). CRC Press.
- von Hippel, P. T. (2007). Regression with missing Ys: An improved strategy for analyzing multiply imputed data. *Sociological Methodology*, 37(1).
- White, I. R., & Carlin, J. B. (2010). Bias and efficiency of multiple imputation compared with complete-case analysis for missing covariate values. *Statistics in Medicine*, 29(28).
- White, I. R., Royston, P., & Wood, A. M. (2011). Multiple imputation using chained equations: Issues and guidance for practice. *Statistics in Medicine*, 30(4).
- Wooldridge, J. M. (2002). Inverse probability weighted M-estimators for sample selection, attrition, and stratification. *Portuguese Economic Journal*, 1.
- Wooldridge, J. M. (2010). *Econometric Analysis of Cross Section and Panel Data* (2nd ed.). MIT Press.
- 聂辉华、江艇、杨汝岱 (2012). 中国工业企业数据库的使用现状和潜在问题. 《世界经济》第 5 期。
- 唐为、王媛 (2015). 行政区划调整与人口城市化：来自撤县设区的经验证据. 《经济研究》第 9 期（待核）。
