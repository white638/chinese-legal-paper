---
name: quant-causal-inference
description: 中文人文社科定量因果推断引擎（可执行）：把"识别策略 → 描述统计/平衡表 → 识别图 → 主回归（渐进控制）→ 异质性/机制 → 稳健性炮阵 → 复现"跑成一条产 Word/Excel/LaTeX 表的流水线。默认驱动 MIT 的 statspai 包（`pip install statspai`，一行产带中文的 AER 式回归表），并给出 R（fixest/did）与 Stata（reghdfe/csdid）等价路径。Use when the user runs 定量/因果推断分析 in social science — 回归、DID、双重差分、RDD/断点回归、IV/工具变量、PSM/倾向得分匹配、合成控制、事件研究、平行趋势检验、稳健性检验、异质性分析、中介机制、回归表导出。Trigger on 因果推断、双重差分、断点回归、工具变量、倾向得分匹配、合成控制、固定效应、聚类标准误、回归表、稳健性、平行趋势、event study、DID/RDD/IV/PSM/DML。属于 empirical-research 编排层的定量分支；纯定性走 aers-thematic-analysis / qual-*。
---

# Quant-Causal-Inference：中文人文社科定量因果推断引擎

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `empirical-research` 或 `cnki-paper` 实证分支子技能使用时，先读取 `empirical-research/references/{{METHOD_ADAPTER_FILE}}`；若工作流由 `cnki-paper` 发起，也读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 并服从 `cnki-paper` 控制器的 `avereth.py gate --stage <stage>`。本技能产出的识别设计、数据契约、模型日志、表图、稳健性结果和 manuscript-ready 数字必须落到 `paper_rewriting_output\empirical\` 或父工作流指定目录；未经复现登记的系数、样本量、统计量不得回写正文。

`empirical-research` 的**定量可执行分支**。默认驱动 **statspai**（MIT 包，`pip install statspai`，
≥1.6）——一次 `import statspai as sp` 即可跑完整因果推断并产**带中文的 Word/Excel/LaTeX 回归表**；
习惯 R/Stata 的同法（见下"等价路径"）。本技能是**原创**指导层，statspai 是被驱动的开源包。

> 服从 `empirical-research` 三条铁律：**识别先于估计、数字皆可复现、来源全程留痕**。
> 估计量与识别假设未写下，不跑 `estimate`。

## 前置

```bash
pip install statspai          # 默认引擎；产 Word/Excel/LaTeX 表（Word 导出开箱即用，已实测）
pip install pyfixest          # 高维固定效应 sp.feols(...|fe1+fe2) 需要它（否则报 ImportError）
# 或：pip install pandas statsmodels linearmodels   # 不用 statspai 时的经典栈兜底
```

> 实测（statspai 1.17）：`sp.regress`（聚类SE）、`sp.mean_comparison`、`sp.causal_question().identify()`、
> `sp.regtable(...).to_word()` 开箱即跑，中文标签正常，产出的 docx 可直接过 `docx_fixup --tables` 规整三线表。
> 仅 `sp.feols` 高维固定效应这一支需补装 `pyfixest`。

## 识别优先（先写下，再开跑）

定量社科被审稿打回最常见的原因是**识别不清**。动手前先填这张表（冻结到 git，即预注册）：

| 设计 | 估计方程 | 识别假设（必须在正文为其辩护） |
|---|---|---|
| 双重差分 DID | `Y_it = α_i + λ_t + β·D_it + X'γ + ε_it` | 平行趋势（条件于 X）；无预期效应。**交错处理下 TWFE 不作主结果**（负权重/禁止比较），主结果用 Callaway-Sant'Anna / Sun-Abraham / BJS 填补法，见 `references/did-staggered.md` |
| 事件研究（交错 DID） | 动态 `β_e`（组×时 ATT 聚合） | 组×时平行趋势；基期取处理前最后一期；预趋势检验功效低，配 HonestDiD 敏感性（Rambachan & Roth 2023）；见 `references/did-staggered.md` §3 |
| 工具变量 IV/2SLS | `Y=α+β·D+X'γ+ε; D=π·Z+X'δ+u` | 外生 + 相关 + 单调 + 排他（排他只能论证不能检验）；弱工具改报有效 F（Montiel Olea-Pflueger）/ tF 校正 / Anderson-Rubin 区间，不再用"首阶段 F≥10"，见 `references/identification-designs.md` §一 |
| 断点回归 RDD | 局部线性 + CCT 最优带宽 + 稳健偏差校正 CI（rdrobust） | 断点处 E[Y(0)\|X] 连续；无操纵（McCrary / rddensity 密度检验）+ 协变量在断点处连续 + 带宽敏感性 + 伪断点；不用高阶多项式；见 `references/identification-designs.md` §二 |
| 倾向得分匹配 PSM / 加权 | 条件独立 | 可忽略性 + 共同支撑（love plot，\|SMD\|<0.1，方差比）；King & Nielsen (2019) 警示 PSM 悖论，优先 CEM / 熵平衡 / IPW-AIPW；不可观测混杂须报敏感性（Oster δ / Rosenbaum Γ / E-value / sensemakr RV）；见 `references/identification-designs.md` §三 |
| 合成控制 SCM | `Ŷ_1t=Σ w_j Y_jt` | 处理前拟合好 + 无溢出 + donor pool 无同期冲击；置换检验与 RMSPE 比；见 `references/identification-designs.md` §四 |
| 中介分析 | ACME/ADE（Imai-Keele-Tingley）或受控直接效应 CDE | 序贯可忽略性（中介相对处理与结果均可忽略）——三步法不满足即失效；政策后变量不能当控制；报 ρ 敏感性；见 `references/identification-designs.md` §四 |

statspai 的 `sp.causal_question(...).identify()` 会**强制**你先声明（总体/处理/结果/估计量/设计）
再给出估计器与假设清单——把它当预注册产物，先 `freeze` 再 `estimate`。

## 流水线（每步映射论文章节 + 产出物）

```
论文章节            statspai 动作                                         产出
─────────────────  ───────────────────────────────────────────────────  ──────────────
§数据               sample log + 数据契约（缺失/重复/面板平衡 go-no-go）   repro_pack add-source/exclude
§描述统计 表1        sp.sumstats · sp.mean_comparison（全/处理/控制+Δ）      tables/table1.{docx,xlsx}
§识别(图)            sp.event_study/enhanced_event_study_plot · rdplot ·    figures/fig2_*.png(300dpi)
                    rddensity(McCrary) · binscatter(首阶段) · 平行趋势图
§主结果 表2         渐进控制 M1→M5：sp.regress / sp.feols(高维FE) /         tables/table2.{docx,xlsx}
                    sp.ivreg / sp.callaway_santanna → sp.regtable
§异质性/机制 表3    分组回归 · sp.mediation · CATE                          tables/table3.{docx,xlsx}
§稳健性 表A1        安慰剂 · Oster界 · honest_did · 替换设定 · 双向聚类 ·    tables/tableA1.{docx,xlsx}
                    规格曲线 sp.spec_curve
§复现               method_execution 登记哈希工件定位 → repro check 审计    REPRODUCIBILITY.md
```

最小可跑骨架（替换列名/问题即用）：

```python
import statspai as sp                              # MIT 包
# 1) 识别优先：先声明、冻结
q = sp.causal_question(treatment="政策试点", outcome="财政透明度", data=df,
                       estimand="ATT", design="did", time="year", id="city")
plan = q.identify(); print(plan.summary())          # 估计器 + 识别假设；冻结到 artifacts/
# 2) 表1 平衡表 → Word（中文标签直接用）
sp.mean_comparison(df, ["人口","财政自给率","城镇化率"], group="政策试点",
                   test="ttest", title="表1 处理组与控制组均衡性").to_word("tables/table1.docx")
# 3) 识别图：事件研究查平行趋势
es = sp.event_study(df, y="财政透明度", treat_time="试点年份", time="year",
                    unit="city", window=(-4,4), ref_period=-1)
sp.enhanced_event_study_plot(es).savefig("figures/fig2_event.png", dpi=300)
# 4) 主回归渐进控制 → 一张多列 Word 表
M1 = sp.regress("财政透明度 ~ 政策试点", df, cluster="province")
M2 = sp.feols("财政透明度 ~ 政策试点 + 人口 + 城镇化率 | province + year", df, vcov={"CRV1":"province"})
sp.regtable(M1, M2, coef_labels={"政策试点":"试点处理效应"},
            stats=["N","R2","Cluster","FE"], title="表2 政策试点对财政透明度的影响").to_word("tables/table2.docx")
```

> **中文字体**：matplotlib 默认无中文字形，图标题会变 ▢▢▢。绘图前设
> `mpl.rcParams["font.sans-serif"]=["Microsoft YaHei","SimHei",...]; mpl.rcParams["axes.unicode_minus"]=False`，
> 并 `savefig.dpi=300`。statspai 的表导出不受此影响。

## 按需深读

| 场景 | 读 | 何时读 |
|---|---|---|
| 处理分批推开（多队列/多时点）的 DID 与事件研究 | `references/did-staggered.md` | 填识别表、选估计量与对照组、画事件研究图、写 HonestDiD 之前；回应"TWFE 有偏"时 |
| IV / RDD / 匹配加权 / 合成控制 / 中介与调节 | `references/identification-designs.md` | 选定设计后、跑主回归前；写稳健性表与回应审稿人时 |
| 缺失、异常值、平减、指数构造、行政区划对齐、面板平衡 | `empirical-research/references/data-preparation.md` | §数据 动手清洗前——每个清洗决策先 `decision`/`exclude` 登记再执行 |
| 表图与数字的报告规范 | `empirical-research/references/reporting-standards.md` | 出表出图、把数字回写正文时 |

## 等价路径（习惯 R / Stata 者）

| 任务 | R | Stata |
|---|---|---|
| 高维固定效应 | `fixest::feols(y~x|fe1+fe2, cluster=~id)` | `reghdfe y x, absorb(fe1 fe2) vce(cluster id)` |
| 交错 DID | `did::att_gt` / `fixest::sunab` | `csdid` / `did_imputation` / `eventstudyinteract` |
| 断点 RDD | `rdrobust::rdrobust` | `rdrobust` / `rddensity` |
| 工具变量 | `fixest::feols(y~1|fe|d~z)` / `AER::ivreg` | `ivreg2` / `ivreghdfe` |
| 合成控制 | `Synth` / `synthdid` | `synth` / `sdid` |
| 回归表导出 | `modelsummary` / `etable` | `outreg2` / `esttab` |

方法无关——选你和合作者最顺手的；但**识别假设的辩护、稳健性炮阵、复现登记三件事一个都不能少**。

## 人文社科特别提醒

- **样本常较小**：聚类数少时聚类标准误失效，考虑 wild bootstrap（`boottest` / `fwildclusterboot`）。
- **准实验做政策评估**：政策"试点"很少随机，平行趋势/安慰剂检验是底线，别只报一个显著的 DID。
- **调查数据**：注意抽样权重与分层；Likert 量表别当连续变量硬跑 OLS（考虑有序 Logit）。
- **别把相关说成因果**：无可信识别策略时，老老实实写"关联"，这与套件"绝不伪造"一脉相承。

## 实战教训（2026-06 面板稿全流程回写）

以下五条来自一篇 6 年省级面板稿的三方评审与修订实录，均为评审真实提出、修订真实生效：

- **同义反复自检**：核心自变量若由分类映射构造（如"职业→技能组"），结论可能是定义的
  重述——用**独立外部轴双验**（教育年限轴 + 工资轴各自重分组再跑），三轴同向才立得住；
  发现映射反例（如采矿业高工资但低教育）要在正文明写而不是藏起来。
- **离散分类配连续度量**：分组结果（占比升降）用连续度量（如加权平均受教育年限）复核
  单调性，逐年单调比"期初期末两点比较"抗质疑得多。
- **少聚类诚实报告**：wild bootstrap 后主结果 p 值变边缘（如 .095）就照实报告并讨论，
  别换设定把它"做显著"——审稿人对少聚类的敏感度远高于对边缘显著的容忍度。
- **事件研究基期**：以**处理前最后一期**为基期（而非样本首年），否则前趋势与处理效应混同。
- **核心命题形式化**：把主张写成可证伪命题（"若 X，则观测到 Y；观测到非 Y 即证伪"），
  评审的"不可证伪/注水"指控当场失效——这也直接对上 anatomy 量规 §3.3 的顶刊档。

## 衔接

- 跑前/跑后用 `empirical-research/scripts/repro_pack.py`：`add-source` 登记数据、`exclude` 记样本构造、
  在 `method_execution.json` 登记每个落稿系数的 Evidence、Artifact 与 locator，`check` 审计、`freeze` 锁环境。
- 表格回写：导出的 docx 表过 `cnki-paper/scripts/docx_fixup/docx_normalize.py --tables` 规整为三线表；
  彩图过 `--grayscale`。
- 结果叙事交 `cnki-paper` build 阶段；引文页码交 `page-evidence`。
- 若 statspai 未安装且不便安装：退回 `statsmodels`/`linearmodels`（经典栈），流程与产出规范不变。
