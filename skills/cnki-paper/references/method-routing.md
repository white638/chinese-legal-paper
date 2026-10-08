# 方法路由 v3.1：问题先于方法

## 决策顺序

1. 锁定主问题、子问题和答案任务；
2. 确定概念、材料单位、时间和所需证据；
3. 明确每个主张的推断上限；
4. 选择能产生该证据的一条主路线；
5. 只有主路线不能回答某个子任务时才加辅助/验证路线；
6. 多路线声明交接、独立性、冲突和综合上限；
7. 进入 execution 前冻结 Design ID 和路线内容摘要。

不从“我会某软件”“定量更科学”“案例更深入”或期刊时尚倒推问题。

## 问题到功能

| 问题 | 常见 route.function | 典型路线 | 不自动要求 |
|---|---|---|---|
| 描述 | collection / analysis / synthesis | 描述定量、历史重构、内容分析、综述 | 假设、因果识别 |
| 解释 | identification / analysis | 定量因果、实验、比较、过程追踪、QCA | 大样本或显著性 |
| 预测 | analysis | 预测定量、文本即数据、计算模型 | 因果效应 |
| 操作 | analysis / argument | 评估、比较、模拟、规范—经验组合 | 唯一最优解 |
| 规范 | argument | 规范、概念、诠释、制度比较 | 量化和假设 |

方法族及条件字段见 `empirical-research/references/method-adapters.md`。机器枚举只读取 `method-adapter-registry.json`。

## 单路线

单路线仍需说明材料、选择、权限、伦理、复现、报告计划和推断上限。`integration.strategy=single` 不表示没有替代解释或反证条件。

## 多路线

- sequential：前一路线的结果如何决定后一路线；
- convergent：不同材料如何独立回答同一问题，不一致如何处理；
- nested：案例/子样本如何嵌入更大材料；
- complementary：路线回答不同层次，不伪称相互验证；
- adjudicative：路线如何区分竞争解释。

每条路线必须有独立 Design ID、主辅角色、依赖和问题/主张映射。若材料共享，明确共享到何种程度。综合推断不能超过各路线真正共同补足的范围。

## 综述路由

嵌入式、叙述式、范围和系统综述分别运行。只有系统综述强制 PRISMA 2020；范围综述采用适用扩展；其他综述披露选择边界但不冒充系统流程。详见 `literature-review-routing.md`。

## 定量任务

定量必须填写 task_type：

- descriptive：表征与不确定性；
- associational：条件关联，不写因果；
- predictive：预定义目标、基准、训练/验证/测试和漂移；
- causal：estimand、时序、反事实/比较、识别假设和诊断。

普通回归不会自动把 associational 变成 causal。

## 文本任务

- content_analysis：系统编码和内容模式，信度按实际编码设计适用；
- discourse_analysis：语境、权力、位置、竞争解读和反身性；
- text_as_data：计算表示、数据隔离、模型验证和解释边界。

关键词频率不能自动代表态度、行为或因果；话语分析不被强迫套用编码一致性阈值。

## 合法非实证路线

conceptual 使用定义、论证图、相邻概念、边界案例和反例；interpretive 使用语境、解释规则、竞争解读和反身性；normative 分开价值与事实前提、受影响主体、最强反对、反例和制度约束。它们可以没有数据集、假设和因果识别，但不能没有材料/论证身份和推断边界。

这些路线以及以史料叙事承重的历史／制度史研究，进入 build 时使用 `humanities-argument` 稿件 profile
（文献与诠释框架 → 史料与分析进路 → 分析），而不是数据—方法—结果骨架；选择规则见
`engine/manuscript-compiler.md`，史料层级、版本、著录与引文忠实度规则见 `primary-source-citation.md`。
`method_routes[].family` 为 interpretive／normative／theory_generation／review 或 `empirical=false`
时自动选中；历史研究若登记为 case_process，须在 `workflow_config.manuscript_profile` 显式指定。

## 变更

路线可以发展，但必须记录变更、理由、确认性/探索性身份、受影响 Claim ID 和推断上限。问题、核心材料或主路线变化时返回 design/用户确认；结果不利时不得通过删除或改写路线制造成功。
