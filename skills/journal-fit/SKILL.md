---
name: journal-fit
description: 选刊与按刊适配：判断一篇论文稿件适合投哪个期刊（中文/英文、人文社科），或把稿件按目标期刊的定位、体例、审稿偏好做适配改写。Use when the user asks 这篇论文投哪个期刊、适合投什么刊、选刊、期刊匹配、改投哪里、按某期刊要求写/改论文、期刊投稿要求、journal fit / where to submit / venue selection / tailor manuscript to a journal. 覆盖 253 个期刊 pack（116 中文社科含政治学／公管／国际关系／史学核心刊 + 110 英文经管与公管／政治学刊 + 27 个人文社科单刊深度包，含 APSR/AJPS/IO/World Politics、PAR/JPART/Governance、《中国社会科学》《社会学研究》《中国行政管理》《政治学研究》《历史研究》）。中文论文全流程写作仍走 cnki-paper；本技能负责"投哪"与"按刊改"。
---

# Journal-Fit：选刊与按刊适配

本技能回答两个问题：**这篇稿子投哪**（场景 A）与**按目标刊怎么改**（场景 B）。它是 `cnki-paper` 的期刊适配层，不是独立写作流程：全流程写作、引用库、审计仍由主工作流负责。

## {{HOST_DISPLAY_NAME}} 集成

中文刊实采通过 `cnki-journal-index`、`cnki-journal-toc` 与 `{{BROWSER_TOOL_NAME}}` 完成；进入 CNKI 页面前先读取 Chrome 控制技能的运行时说明。若由 `cnki-paper` 触发，还要读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}`，把选刊证据写入父工作流的期刊情报、source index 与 style profile，不得绕过用户确认目标刊的硬门。

## 资产

- `references/pack-index.md` — 全部 253 刊索引（刊名 → pack 路径 → 定位一句话）。路由前先读它，不要盲目 ls。
- `references/cn-journal-channels.json` — 中文刊学科通道与细分方向表（十一类通道）；`scripts/build_cn_siblings.py` 据此生成每个 cn-broad profile 的通道标签与"相近 profile"列表。新增中文 profile 时先在此登记再跑脚本，不要手写姊妹刊。
- `packs/` — vendored 期刊 pack 资料库（来源与纪律见 `packs/PROVENANCE.md`）：
  - 深度包 27 个（单刊全流程约 12 技能：定位/选题/文献/设计/写作风格/图表/投稿/返修/审稿文化，另有 `resources/official-source-map.md` 官方信息源图与 `resources/exemplars/`）；
  - 广度合集 2 个（每刊一个"选刊 profile"：定位、关键事实带核验日期、选题偏好、拒稿雷区、改投判断、官方核验清单；内置路由 skill `cn-journal-workflow` / `en-journal-workflow`）。
- 本套件既有资产**优先于 pack**：目标刊在 `cnki-paper/references/top-journal-anatomy.md` §2 有实采刊性时（政治学/公管中文顶刊），以 anatomy 为主、pack 为补充；二者冲突以实采为准。

## 场景 A：选刊（目标刊未定或考虑改投）

1. **稿件画像四问**（借两个 router 的判准）：学科与读者对象；问题层级（理论命题/制度/行业政策/个案）；方法形态（理论、因果识别、测度、问卷/案例、诠释、规范研究）；投稿目标（冲顶刊还是题刊匹配与效率）。稿件已有 `confirmed_contribution.md` 或摘要时从中提取，不重问用户。
2. **候选生成**：读 `pack-index.md` 圈 3–6 个候选；相关 pack 的 profile 逐个读（深度包读其定位/submission 子技能即可，不必全读）。中文政治学／IR／公管／史学核心刊已有 cn-broad profile（《政治学研究》《公共行政评论》《世界经济与政治》《国际政治研究》《开放时代》《学术月刊》《探索与争鸣》《社会》《历史研究》《清史研究》《近代史研究》《中国史研究》《史学月刊》等），但仍有对口刊不在 pack 内——用 anatomy §2 刊性表与 CNKI 期刊导航补候选，不得因 pack 没收录就漏掉。这批 profile 的关键事实只含 2026-09-02 当次从官方页面核到的条目，标"待核"的项必须在本轮实采。
3. **实采核验（中文刊）**：对进入短名单的刊用 `cnki-journal-index`（收录/影响因子）、`cnki-journal-toc`（近期目录与栏目——判断选题风向）核验；投稿体例与字数以官网/编辑部最新须知为准。英文刊按该 pack `resources/official-source-map.md` 的官方锚点用 WebFetch/浏览器核验。
4. **输出匹配度表**并请用户确认（投稿目标是用户决策，同 motivation 硬门逻辑）：

```text
【首选】<刊名>（匹配度+一句理由）
【备选 1..2】<刊名>（差异点）
【不建议投】<刊名>（错位一句话）
【当前最大短板】选题/理论/识别/机制/字数/体例
【投稿前必核验】<官方须知项，注明本表事实的核验日期>
```

5. 用户确认目标刊后：新稿返回 `cnki-paper` 当前八阶段控制面（期刊情报步骤直接复用本场景实采结果）；已成稿转场景 B。

## 场景 B：按刊适配（目标刊已定）

1. 读目标刊 pack：深度包按需读对应阶段子技能（写作风格、结构、图表、投稿清单、返修）；广度 profile 全读。中文顶刊叠加 anatomy 对应刊节与量规。
2. 产出**按刊修改清单**，逐项落到稿件真实位置：叙事框架与开篇 tell、结构与栏目匹配、方法呈现深度、字数与摘要/关键词/体例、投稿件清单（匿名要求、基金单列、数据政策、cover letter）。中文刊参考文献著录细节可查 zotero-chinese/styles 已实现的该刊 CSL 样式作机读参考（仅参考不 vendor，CC BY-SA；最终以刊方须知为准）。
3. 在 `cnki-paper` 当前八阶段工作区内时：修改清单作为 overlay 证据返回父工作流，由 build/audit 的现有合同决定写入位置；独立改稿时清单本身即交付物，逐项改完后给出"已改/待用户决策"对照。
4. 返修（revise & resubmit）与审稿意见回应：深度包的 rebuttal/review-process 子技能给该刊审稿文化与回应模板；逐条回应仍须以稿件真实修改为据，不写空头承诺。

## 硬纪律

1. **pack 事实=候选情报**。字数、费用、审稿周期、查重线、系统入口、收录状态均带上游核验日期，随时会过时；给出投稿建议前必须按该刊"官方核验清单"重新核验官网/采编系统，并在结论中注明核验日期。核验不了要明说，不得让旧数值冒充现状。
2. **无权限先找用户**。期刊官网、采编系统、数据库遇权限墙/登录墙时，先请用户在 Chrome 登录或提供机构权限，用户确认无法提供后才降级用公开元数据并标注证据等级；不得静默降级。
3. **选刊建议不是学术判断的替代**。匹配度低的首要出路是回 `cnki-paper` 抬档（重做论证/补证据/收窄主张），降档改投是用户决策；不承诺录用率或审稿结果。
4. **中文刊以 CNKI 实采与官方渠道为准**，pack 与模型记忆只生成候选；引用刊性结论时区分"pack 情报（某日期）""anatomy 实采""本轮实采"。
5. **姊妹刊与通道标签只信 channels.json**。cn-broad profile 的"路由防误投"由 `scripts/build_cn_siblings.py` 按学科通道与细分方向生成；若某 profile 的相近刊看起来跨学科（如经济刊配社科综合刊），先查 `cn-journal-channels.json` 的分类是否需要修正并重跑脚本，不要在单个 profile 里手改。
6. **venue overlay 不拥有工作区状态**。任何 pack 内的 `*-workflow` 都只是期刊 lens router：不得创建/推进 stage，不得签 receipt、调用 gate、覆盖 `status` 或 `method_contract`，也不得直接执行统计/NLP 引擎。它只选择要读取的期刊资料并把建议、报告与透明度要求返回 `cnki-paper`；方法有效性回到 `empirical-research` 核心合同和 validator。

## 前置条件

| 依赖 | 用途 | 缺失时 |
|---|---|---|
| `packs/` 与 `references/pack-index.md` | 选刊路由与按刊情报 | 重装本套件（install.ps1）；上游更新见 PROVENANCE |
| `cnki-journal-index` / `cnki-journal-toc` / `{{BROWSER_TOOL_NAME}}` | 中文刊实采核验 | 报告阻塞，改用官网公开页并降级标注 |
| `cnki-paper`（anatomy §2、当前八阶段控制面） | 中文顶刊刊性与全流程写作 | 本技能可独立跑选刊，但工作区写入、阶段和交付须回主工作流 |
