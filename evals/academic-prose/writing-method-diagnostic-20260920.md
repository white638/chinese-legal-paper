# 写作诊断：真实证据上的首轮成对审读

2026-09-20。结论：这次小样本诊断未证明候选规则带来稳定文笔提升。两位评审均未发现可确认的硬性事实或语义错误，但在证据忠实度上都小幅偏好基线，指出候选的两处范围歧义；这些风险不能用流畅度抵消。

## 条件与边界

使用同一份冻结证据：Lurquin 等（2016）的自我损耗研究与 Sanchez 等（2017）的图片启动重复研究。完整出版商正文和 PDF 已核对；仅核验出版物报告，未重算原始数据，未审计预注册时间戳或全面核验被引研究。两篇分别为 [PLOS ONE 0147770](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0147770) 和 [PLOS ONE 0172636](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0172636)，均标示 CC BY 4.0。

任务 A 为中文两段，区分未检出与不存在；任务 B 为英文两段，比较研究如何改变理论判断。基线和候选各由新的隔离上下文一次生成，未筛选重试，原始文本保留如下。两位评审各在新的独立上下文中只读证据与匿名成稿；第二位看到反向排列。各上下文继承本任务模型，未执行不同模型系列或人工校准；未测随机种子、成本或延迟，不宣称统计稳定性。

**版本边界：** 采样比较的是基线 Writer 与首轮候选 Writer 中选出的写作规则，并非生产流水线双包运行。随后工程检查又移除了新 ProsePacket 的统一句数上限和限定前后次序，并同步相关指令；因此以下结果是保留的首轮诊断，最终安装版的端到端文笔效果仍未验证。未为改变偏好而重写或重抽样。

## 分项结果

| 任务 | 推理可恢复性 | 作者判断 | 阅读连贯性 | 证据忠实度 |
|---|---|---|---|---|
| A 中文 | 两位均平局 | 两位均平局 | 两位均平局 | 两位均小幅偏好基线 |
| B 英文 | 一位偏好候选，一位平局 | 两位均平局 | 两位均平局 | 两位均小幅偏好基线 |

不加总维度，不把两位同系列模型当作两次独立统计试验，也不把一致判断称作人工验证。B 的推理偏好不同，保留分歧，未裁定候选优胜。

候选 A 的“对图片操作效果的否定”可能扩大了前文仅针对较大预期下降的范围；区间仍容纳零及非零效应。候选 B 的“delimit the remaining predicted effect more closely”可能被读成两研究实际精度已经排序；证据包没有 S1 的对应区间，设计检验力不能直接代替结果区间。两处都存在较弱、可成立的语境读法，故评审将其列为表达风险，未判为硬错误。使用这类段落时，需把判断对象写回“较大预期图片效应”及“当前报告提供的区间约束”，不能凭修辞加强结论。

## 冻结材料

- 证据 SHA-256：`21b1a4d7f21885fb8ce9fdf0ff187dad705ac77aff38736a6ec4cee280df21f5`
- 基线输出 SHA-256：`6d9eac2aee468cbf1a7eb34081ea15e4fea91b8341d07c646d38dd0e78bbd748`
- 候选输出 SHA-256：`baa75c0b4215ee17579b5b2d5cd226a6e8d5ef07887f8f21e81ebbf98fb8f285`
- 盲评映射：R1 的 L=基线、M=候选；R2 的 L=候选、M=基线。映射仅在报告汇总时公开。

## 基线原始成稿

### A

在特定任务中未检出预期差异，会削弱效应在这些条件下稳定出现的判断，却不能仅凭统计不显著认定效应不存在。Lurquin等（2016）让参与者先完成视频注意控制任务，再以操作广度任务测量工作记忆表现；损耗组未显著表现更差，点估计反而略好。这一结果未能支持“先前自我控制降低后续表现”在该任务组合中的预测。作者另行开展的未预注册贝叶斯分析偏向零假设，贝叶斯因子为2.40，提供了有限的补充依据。不过，研究对d=0.40的效应具有80%检验力，这一设计敏感度不能转化为对更小效应的排除。操作广度测量的是工作记忆表现，从这一指标进一步推论自我控制，还需要论证两者的联系；研究并未直接测量一种可耗尽资源的存在及其变化。

Sanchez等（2017）则通过区间估计限制了图片操作可能产生的效应大小。四站点综合估计为d=.07，95%置信区间为[−.12,.25]；负值才符合《思想者》图片降低上帝信念的预测。该区间包含零，并在预期方向上只延伸至很小的效应，因此比一句“不显著”提供了更多判断依据。但这一约束首先落在短时图片暴露与自报信念之间。图片记忆检查检验参与者是否注意图片，独立的正向控制显示另一任务的效应，两者都未确证图片改变了分析性思维。因此，这项重复研究削弱了以该图片实验支持“分析性思维降低宗教信念”的因果论证，而理论关系本身仍需通过有效改变分析性思维的操作来检验。前一研究质疑特定任务序列中的表现损耗，后一研究限制特定图片操作的效应；它们对理论的约束，都取决于测量精度以及实验实际检验了哪一个理论环节。

### B

Lurquin et al. (2016) weaken the expectation that prior self-control reliably impairs subsequent performance in the tested attention-control–OSPAN sequence. The depletion group performed slightly better, although the difference was not statistically significant. This direction provides no support for the predicted impairment, while the nonsignificant test alone cannot establish a zero effect. An additional, non-preregistered Bayesian analysis favored the null by a factor of 2.40, offering limited support beyond that test. Yet the reported 80% power applied to an effect of d = 0.40, leaving smaller effects less readily detectable. The theoretical update therefore concerns the reproducibility of this particular sequential-task prediction. Extending it to the existence of a depletable resource requires establishing how working-memory performance represents self-control; the study did not directly measure such a resource.

Sanchez et al. (2017) constrain the estimated magnitude of a different experimental effect: brief exposure to The Thinker lowering self-reported belief in God relative to exposure to Discobolus. Their four-site estimate, d = .07 with a 95% confidence interval of [−.12, .25], includes zero and extends only a small distance in the predicted negative direction. This weakens the use of that image experiment as causal evidence that analytic thinking reduces religious belief. Connecting the result to the broader theory, however, requires knowing whether the images changed analytic thinking. Image-memory checks assessed attention, and the independent positive control detected an effect in another task; neither established the proposed cognitive change. The studies consequently challenge different theoretical links: the predicted performance cost within a particular task sequence, and an image-based causal demonstration with an uncertain connection to analytic thinking. Neither resolves its broader theory across other tasks or interventions, but each identifies a specific experimental basis on which confidence should decrease.

## 首轮候选原始成稿

### A

Lurquin 等（2016）的结果削弱了“先前的自我控制使后续表现下降”在视频注意控制—OSPAN任务组合中的预测，却不足以认定效应不存在。在200人的分析样本中，损耗组的表现略好于控制组，方向与预测相反，但差异未达统计显著（p=.146，d=.22）。这里的“不显著”表示检验未能拒绝零假设，不能直接转化为零假设成立的证据。作者另行计算的贝叶斯因子为2.40，提供了偏向零假设的有限支持；这项分析未预注册，应与原定检验区分。研究对d=.40的效应具有80%的检验力，较小效应仍可能难以检出。因此，数据使这一任务组合中的损耗预测更难获得支持，而其他任务中的效应仍须通过相应研究判断。

Sanchez 等（2017）则表明，未检出效应也可以对理论预期形成实质约束。其四站综合效应为d=.07，95%置信区间为[−.12,.25]；负值才表示《思想者》图片使上帝信念降低。该区间包含零，也容纳小幅下降，但与作者转录的原研究效应d=−.59明显不符。由此得到的判断比“差异不显著”更具体：这次重复研究削弱了该图片操作产生较大信念下降的证据基础。不过，图片记忆检查针对注意情况，另一个赌徒谬误任务的正向控制也未检验图片是否增强分析性思维。对图片操作效果的否定因而不能直接延伸为对分析性思维与宗教信念之间因果关系的否定。未检出效应与不存在效应的距离，既取决于估计精度，也取决于实验操作与理论构念之间的联系。

### B

Lurquin et al. (2016) weaken the prediction that exerting self-control impairs subsequent performance in the video-attention–OSPAN sequence. The depletion group performed slightly better, contrary to the predicted direction, although the difference was not statistically significant (p = .146, d = .22). This result challenges the expected performance decrement without establishing that its true magnitude is zero. The additional Bayes factor of 2.40 favored the null, but supplied limited support and was not preregistered. With 80% power for d = .40, the study leaves smaller effects less securely assessed. Its theoretical force also depends on treating OSPAN performance as an indicator of self-control: the outcome measures working memory, while the hypothesized depletable resource was not directly measured. Confidence therefore declines in this experimental demonstration, with the broader resource account requiring tests across justified operationalizations.

Sanchez et al. (2017) place a more explicit quantitative constraint on their target demonstration. Across four sites, the pooled effect of viewing *The Thinker* rather than *Discobolus* was d = .07, with a 95% confidence interval of [−.12, .25]. Because negative values indicate reduced belief, the interval accommodates only a small decrease and excludes the original d = −.59 reported in their comparison. This sharply weakens the empirical basis for a substantial belief-reducing effect of that image manipulation. Whereas Lurquin et al. leave detection of smaller effects unresolved, Sanchez et al. delimit the remaining predicted effect more closely. Yet the causal step from image exposure to analytic thinking remains uncertain: neither picture-memory checks nor a positive control involving a separate gambler’s-fallacy task establishes that the images induced analytic thought. The replication thus constrains an operational claim more firmly than it resolves whether analytic thinking itself can reduce religious belief.
