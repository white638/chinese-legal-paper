---
name: management-world
description: Use when targeting 《管理世界》(Management World) or deciding whether a Chinese social-science/econ/management manuscript fits this journal. Applies the journal's fit, framing, core-contract reporting, house-style, official-submission-check, and desk-reject heuristics.
---

# 《管理世界》投稿（management-world）

## 期刊定位

中国管理与应用经济旗舰期刊，完整生命周期支持已在 `Journal-of-Management-World-Skills` 中实现。这里提供目标 pack 内的快速触发和改投判断。

这个 skill 是**定位 / 选刊 / 改写框架**工具，不替代该刊最新官方投稿须知。正式投稿前必须重新核对官网、采编系统或编辑部发布的最新模板。

## 触发时机

- 用户明确说目标期刊是《管理世界》或 Management World
- 稿件主题接近本刊，但不确定问题意识、方法强度和读者对象是否匹配
- 需要把一篇通用中文经管稿改写成《管理世界》更容易接受的叙事
- 投稿前需要列出本刊高频拒稿风险和改投方向

## 关键事实（核验日期 2026-09-02；以官网最新投稿须知为准）

- **主管/主办**：国务院发展研究中心主管主办（来源：https://glsj.chinajournal.net.cn/WKB2/WebPublication/wkTextContent.aspx?mid=glsj&navigationContentID=011127bd-74c1-48b3-bed7-30349045a7d4 知网承载期刊页）
- **刊期与创刊年**：1985 年创刊（来源同上）；刊期官方页未明示——待核（2026-09-02 未能从官方页面核实）（官网 www.mwm.net.cn 本次连接失败）
- **费用政策**：自 2007 年起不再支付稿费（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v 知网采编系统投稿须知）；不收审稿费/版面费声明载于官网，本次未能抓取——待核（2026-09-02 未能从官方页面核实）
- **字数**：无硬性字数，“文章篇幅应与其贡献相匹配”（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v）
- **摘要/关键词**：首页提供中英文标题、**300 字以内**中文摘要、**3～5 个**关键词及作者姓名、单位、联系方式、致谢；首页以外不得出现可能泄露作者身份的信息（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v）
- **引注体例**：所有注释与参考文献列于**文章末尾**，注释连续编号，参考文献按作者汉语拼音或英文名顺序排列，只列正文（含脚注）引用过的文献（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v）
- **审稿周期与匿名方式**：推行**匿名审稿制度**；初审时间 **2 个月**（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v）
- **查重**：待核（2026-09-02 未能从官方页面核实）
- **投稿系统/官网**：网络在线投稿（实名注册），知网采编系统 glsj.cbpt.cnki.net；官网 www.mwm.net.cn（2026-09-02 抓取超时，未能核实）；本刊未委托任何单位/个人组稿；审稿中编辑部可索取研究数据（来源：https://glsj.cbpt.cnki.net/EditorB2N/PromptPageInfo.aspx?c=1&t=v）

## 选题偏好

- 中国管理实践与制度情境
- 企业、产业、公共政策和宏观管理问题
- 可产生操作性政策建议的规范实证或案例研究

## 方法与证据的报告边界

- 明示 `empirical-research` 核心合同 ID 与版本，按适用项原样报告已登记的估计对象或理论目标、假设、诊断处置、哈希绑定 Artifact ID 和 observed inference ceiling。
- 说明这些既有记录为何与本刊读者相关；期刊层不选择估计器、聚类层级、阈值、诊断或修复方案。
- 核心记录缺失或诊断失败时，返回 `empirical-research`，并如实报告收窄或撤回后的推断；不得在期刊层补救。
- 本刊层只补充版面位置、数据/代码、披露和透明度等呈现要求。

## 结构与写作

- 引言要先把中国实践中的管理问题讲清，再进入方法和发现
- 政策建议应具体到主体、环节和可执行动作
- 理论贡献不能脱离中国制度场景

## 路由防误投

- 本刊快速定位属于“管理科学与工商管理”通道；只有当稿件的核心贡献满足“组织、战略、创新管理、管理科学模型、系统工程或企业管理机制必须是核心贡献”时，才把 《管理世界》 作为首选。
- 相近 profile 先比较：`nankai-business-review`（《南开管理评论》） / `business-management-journal`（《经济管理》） / `chinese-journal-of-management`（《管理学报》） / `management-review`（《管理评论》）。若这些刊物的读者对象更贴近，不要因为名称、地区或变量相似而强行投本刊。
- 常见误投：若只是国内政策评估，优先回到综合经济或产业经济刊。 正式建议前仍需进入官方核验清单。

## 官方核验清单

- 正式给出投稿格式/流程建议前，先读取 `../../resources/source-basis.md` 和 `../../resources/official-source-map.md`，从其中的官方来源锚点或同一主办/出版体系入口开始核验，并在回答中说明核验日期。
- 深度包未随本套件收录；全流程走 `cnki-paper` 主工作流，本 profile 只做选刊与定位
- 核对最新投稿须知、匿名要求、摘要关键词、图表与参考文献
- 检索“《管理世界》 投稿须知 / 征稿简则 / 作者指南”，以最新页面为准；不要沿用二手代投网站格式
- 核对是否要求匿名正文、作者信息页、基金信息单列、数据/程序/补充材料、版权协议或不收费声明
- 若本 skill 与最新官方要求冲突，以官方要求为准

## 投稿前自检

- [ ] 一句话说明为什么这篇稿件属于《管理世界》的核心读者范围
- [ ] 引言前 3 段已经出现本刊关心的问题层级、理论/机制和主要证据
- [ ] 文献综述至少对话 2-3 篇本刊或同层级中文期刊近年同主题文章
- [ ] 方法、数据、图表和参考文献格式已按最新官方稿约复核
- [ ] 政策/管理启示从本文证据推出，而不是泛泛口号

## 高频拒稿雷区

- 把《管理世界》写成纯计量经济学刊，缺制度背景和实践意义
- 政策建议停留在加强、完善、推进
- 案例资料厚但没有理论抽象

## 改投判断

深度包未随本套件收录；需要全流程处理时走 `cnki-paper` 主工作流，本 profile 只做选刊与定位；偏数理模型转 journal-of-management-sciences-china。

## 输出格式

```text
【匹配度】高 / 中 / 低（一句话理由）
【目标期刊】《管理世界》
【选题标签】<最贴近的 2-3 个主题>
【核心方法合同】<ID/版本；诊断处置；Artifact ID；observed inference ceiling>
【最大风险】<最可能导致退稿的一点>
【需核验官方要求】<投稿系统/匿名/摘要/图表/数据等>
【改投建议】<若不匹配，给出更合适期刊>
```
