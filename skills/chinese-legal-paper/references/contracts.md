# 法学附加合同

唯一控制器是 `cnki-paper`。本扩展不维护阶段文件或签发完成收据。`legal_profile: chinese-law-v1` 是可选配置；不启用时保持原工作流。法律工件存在而标志被删除会退回 intake，防止静默跳过检查。详细机器合同在 `schemas/`；不要用自由文本替代字段。

## 工件与责任

| 工件 | 写入阶段 | 内容与权威边界 |
|---|---|---|
| `reference_materials/legal_sources.json` | acquisition | Source ID 的法域、法源类型、版本、访问范围、身份复核；来源题名作者等仍在唯一 literature registry |
| `legal_analysis.json` | design | 绑定既有 research_design 和每个 Claim ID 的适用时间、法域、方法及理由；设计/执行仍使用 paper1 正本 |
| `legal_citations.json` | build | 本轮规范稿、具体片段、定位符、引注与主张支持关系 |
| `legal_review.json` | audit | 当前稿件的法学复核依据和未决问题；是附加审查记录，不是独立评审或完成凭证 |

阶段检查与原有最早未完成阶段共同决定回退。只做选题的任务不要求尚未适用的正文工件；`manuscript_audit` 可以没有 design，此时引用的 `claim_id=null`，必须绑定原稿的具体文字。其他任务的引用必须指向既有 Claim ID。

所有附加工件和其显式引用的本地依据文件都进入原有 audit/output 文件指纹。字段或原文变动会让当前收据失效；支持关系另有绑定摘要。当前实现使用整文件 SHA-256，宁可重新复核，也不猜测一段变更一定不影响其他引注。

## 建立记录

```text
python -X utf8 scripts/legal_paper.py template source
python -X utf8 scripts/legal_paper.py template analysis --method doctrinal
python -X utf8 scripts/legal_paper.py template claim
python -X utf8 scripts/legal_paper.py template citations
python -X utf8 scripts/legal_paper.py template citation
python -X utf8 scripts/legal_paper.py template review
python -X utf8 scripts/legal_paper.py hash WORKSPACE/ACTUAL_FILE
python -X utf8 scripts/legal_paper.py bindings WORKSPACE
```

模板有意保留空白和 `pending`，不能通过检查。工具只打印模板/摘要，不自动替人确认来源或观点。填写真实内容，再按当前阶段写入合同。`enable --apply` 只备份配置、启用标志并创建空来源扩展；它不会迁移旧稿或伪造已完成状态。已有合法的旧版工作区须先走控制器的显式迁移。

### 来源

- `source_id` 必须在 `reference_materials/literature_registry.json.sources` 存在；`source_digest` 绑定该完整规范记录的有序 JSON SHA-256，可用 `bindings` 查看。
- `version_id` 是资料版本身份，不是“最新”标签。不同版本应有不同 Source ID 和实际来源文件；同名法律不得按题名自动合并。
- `kind` 分法规、司法解释、政策、原始裁判、案例摘要、学术文献和历史资料；`representation` 标明官方正文、裁判文书、出版正文、编者摘要或二手引述。
- 规范资料需要发布机关、效力层级、文号，以及公布/生效/失效时间、核对时间和依据。层级是描述字段，程序不把它压成一个能自动解决冲突的排序分数。
- 案例需要法院、案号、程序、裁判日期、文书类型、生效状态及关联程序的 Source ID。摘要不得伪装成裁判全文；同案不同审级不能自动去重成一份判决。
- `access.level` 分 metadata/abstract/partial/fulltext；`permission` 分 public/licensed/user_provided/unknown。partial/fulltext 需要依据及本地 UTF-8 文本绑定，且只能指向该规范来源的 `local_file` 或 `verification.ocr_text_file`。登记完整全文是实际阅读判断，程序检查不能证明下载者未误标。
- `scope=literature_only` 只适用于确实没有法律原始资料的任务，必须说明理由。不能用该值掩盖需要但未取得的法条或裁判。

### 日期与适用

日期使用 `YYYY-MM-DD`。生效区间为 `[effective_from, effective_to)`，结束日不再有效；平台提供“最后有效日”时需据原始废止规则明确转换，不能猜日期。`effective_to=null` 表示尚无已知结束日，不等于永久有效。

`use=current_law` 必须落在有效区间内，版本核对日期覆盖论述截止日；`historical_law` 另有 `fact_date`。解释、规范建议、经验判断、比较法分别标注，不能将修改建议写成现行义务。跨法域使用需具体说明可比理由。适用复核必须考虑溯及力、过渡条款、特别法、主体、地域、程序与救济；这些仍是实质判断，不由日期比较替代。

### 原文与引注

绑定对象是 `{path, sha256}`；`path` 为工作区内使用 `/` 的相对路径，不能越界或经符号链接指向外部。片段再增加 `start,end,quote`，按 UTF-8 解码后 Unicode 字符的零基、左闭右开区间定位；不是字节或 UTF-16 下标。直接引文必须与原文区间完全一致。删节、译文或改写不得假装字面相同的原文，按改写/转引记录并保留具体解释。

每条引注有 `CIT-...` ID，规范 Markdown 稿使用 `[^CIT-001]` 之类的脚注标记。标记集合必须与登记集合一致；程序不自动认出所有其他语法的引注。引入此覆盖检查前，需将实际要核查的引用逐项登记；`citation_rules` 复核还要检查没有漏登记的普通脚注和无注实质主张。

印刷页、PDF 页面、法条款项、段号与节号明确分开。定位符复核需要真实依据文件，不能把 PDF 第 10 页直接写成期刊第 10 页。`support_review.binding_digest` 绑定当前来源正本、Claim、稿件片段、原文、定位符及引用用途。`bindings` 可打印应有摘要，但该命令不更新 review；只有重新看过依赖后才能改为 verified。

转引时 `source_id` 始终是实际阅读的中介文献，原文锚点和页码也属于它；另外用 `original_source_id` 标明原始文献在唯一来源库的记录。未直接读到原始文献时，它可以停留在题录层，不能标为已读全文。工作稿脚注会明确“未直接核阅，转引自”，不编造原文页码。

复核对象含实际 reviewer、reviewed_at、reason 和 basis 文件绑定。记录 verified 只是可追溯的责任声明；程序不能证明复核者的法律判断正确。审计问题为 blocking 时必须解决并记录依据，不能靠删除问题或更改状态掩盖它。

## 故障处理

缺少原文、字段、版本依据或未决审查返回 FAIL 及阶段/错误码。源文件或稿件变化返回 STALE，需要在真实复核后重建绑定。新检查依赖丢失时控制器失败关闭，不将法学任务降成普通论文。无依赖的独立解释或局部语言工作仍可继续。检查均只读，不自动改法规、补页码、执行数据库内容中的命令或签发通过收据。
