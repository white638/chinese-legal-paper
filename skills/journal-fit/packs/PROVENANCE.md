# Journal Packs 来源与取舍

- **上游**：https://github.com/brycewang-stanford/Awesome-Journal-Skills
- **vendored commit**：`91580d7821f3ba47b621435707a3668fb4687060`（2026-07-16）
- **许可**：MIT（见本目录 `LICENSE`，Copyright (c) 2026 Bryce Wang；上游全库及各包统一 MIT）
- **性质**：本目录是 `journal-fit` 技能的**按需读取资料库**，不是已注册技能——`packs/**/skills/*/SKILL.md` 嵌套在技能子目录下，不会被 Claude Code 技能发现机制加载，其 frontmatter 仅供人读与索引提取。

## 收录范围（29 包，仅人文社科相关）

| 本地目录 | 上游目录 | 内容 |
|---|---|---|
| `cn-broad/` | Chinese-SocialScience-Journal-Skills | 102 个中文社科（经管为主）期刊选刊 profile + `cn-journal-workflow` 路由 |
| `en-broad/` | English-SocialScience-Journal-Skills | 100 个英文经管期刊选刊 profile + `en-journal-workflow` 路由 |
| `apsr/` `ajps/` `jop/` `world-politics/` `international-organization/` | 对应 *-Skills | 政治学/IR 英文顶刊深度包（约 12 技能/包） |
| `asr/` `ajs-sociology/` `social-forces/` `spq/` `jmf/` `criminology/` `demography/` | 对应 *-Skills | 社会学/犯罪学/人口学深度包 |
| `jpsp/` `psychological-bulletin/` `psychological-science/` | 对应 *-Skills | 心理学深度包 |
| `journal-of-communication/` `poq/` `aerj/` | 对应 *-Skills | 传播学/舆论调查/教育学深度包 |
| `ahr/` `art-bulletin/` `mind/` `pmla/` `critical-inquiry/` `jaar/` | 对应 *-Skills | 历史/艺术史/哲学/文学/批评理论/宗教深度包 |
| `sociological-studies/` `social-sciences-in-china/` `chinese-public-administration/` | 对应 *-Skills | 中文深度包：《社会学研究》《中国社会科学》《中国行政管理》 |

## 裁剪规则（md-only）

- 只保留 `*.md`（SKILL.md、resources 文档、worked-examples、README）。
- 排除：`resources/code/`（Stata/Python 模板——本套件由 `quant-causal-inference` 统一提供）、`assets/`（封面图）、`.claude-plugin/`（插件清单）、LICENSE 副本（根目录一份统领）。
- 未收录的上游内容：计算机/自然科学各包、中文经管拼音深度目录约 100 个、根目录广度期刊文件夹约 200 个、其余中文经管深度包（《经济研究》《管理世界》等 12 个——`cn-broad` 已含其轻量 profile，深度包按需再取）。

## 更新方式

浅克隆上游后按上表映射重跑 md-only 拷贝（robocopy `*.md /S /XD code`），更新本文件的 commit 与日期；重扫 `tools/smoke_check.py` 全仓库检查。

## 使用纪律（与 cnki-paper 铁律一致）

各 profile 中的易变事实（字数、费用、审稿周期、查重线、系统入口、收录状态）带上游核验日期，一律视为**候选情报**：给出投稿建议前必须按该包"官方核验清单"重新核验官网/采编系统；与最新官方要求冲突时以官方为准。
