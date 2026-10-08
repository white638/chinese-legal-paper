# 多发表轨道文献获取与来源注册表契约

## 目录

1. 何时读取
2. 获取闭环
3. 注册表结构
4. 查询记录
5. 来源记录
6. 状态与证据等级
7. PDF 落盘闭环
8. 与本地研究工件的连接
9. 命令
10. 旧任务迁移

## 1. 何时读取

执行 `acquisition` 阶段、恢复旧任务、批量导出、下载全文、做 CNKI／国际引文滚雪球或修复引用追踪时读取本文件。CNKI 页面选择器与站点差异仍读取 `cnki-operations.md` 和对应 `cnki-*` 技能；国际发现与原文回查读取 `intl-search`／`intl-export` 的当前说明。

## 2. 获取闭环

一次来源获取必须形成以下链条：

`可复现查询 → 结果发现 → 元数据导出 → 内容核验 → 按需全文落盘 → SHA-256 封存 → Source ID 贯穿 Evidence ID/Claim ID/正文`

只完成点击、题名抄录、导出或浏览器显示“正在下载”，都不算获取闭环。PDF 必须在项目目录内真实存在、可被 PDF 解析器读取、呈现多页文章正文与可核验的学术引证装置（文末参考文献或规范页下注）、通过 SHA-256 复算，并由注册表记录来源 URL；只带 `%PDF-`／`%%EOF` 的壳文件、空白页或把题名—作者—刊名—年份—摘要填进 PDF 的元数据包装均不算全文。扫描型 PDF 须另存可核验 OCR 文本旁证。

获取在主线程运行，因为登录、机构权限、下载和 captcha 可能需要用户现有 Chrome。隔离研究角色只读落盘注册表及其派生 source index，不直接操作来源平台。

## 3. 注册表结构

唯一事实表为：

`paper_rewriting_output/reference_materials/literature_registry.json`

最小结构：

```json
{
  "schema_version": "cnki-acquisition/v3",
  "target_name": "目标期刊或会议",
  "tier": "flash",
  "publication_track": "cnki-cn",
  "access": {
    "status": "verified",
    "method": "institutional-ip",
    "checked_at": "2026-07-28",
    "download_probe": {
      "status": "passed",
      "url": "https://kns.cnki.net/kcms2/article/abstract?..."
    }
  },
  "queries": [],
  "sources": []
}
```

`target_name`、`tier`、`publication_track` 必须与 `workflow_config.json` 一致。`publication_track` 只能是 `cnki-cn`、`international-ssci` 或 `mixed`；`init` 从 config 写入。新工作区不得依赖缺省轨道。权限记录只说明本次活动来源生态的真实探针，不保存 cookie、账号、密码或浏览器存储。

## 4. 查询记录

每次检索、目录读取或滚雪球都登记一个 query：

```json
{
  "query_id": "Q-SOTA-001",
  "channel": "CNKI",
  "purpose": "sota",
  "query": "主题=... AND 关键词=...",
  "field": "SU",
  "filters": {
    "source_types": ["CSSCI", "北大核心"],
    "years": "2024-2026",
    "sort": "被引"
  },
  "result_count": 84,
  "url": "https://kns.cnki.net/...",
  "collected_at": "2026-07-28",
  "status": "complete"
}
```

`channel` 缺省按 `CNKI` 解释，仅用于旧记录兼容。CNKI 查询必须保留 `cnki.net` 的稳定结果页或详情页 URL；国际数据库、出版社、Web 和本地材料必须写明实际通道，并在 `url` 中保留可复核链接或项目内来源路径。`venue`、`target-exemplar`、`sota` 是查询目的，不是 CNKI 身份：`cnki-cn` 由真实完成的 CNKI 查询满足，`international-ssci` 由 OpenAlex／Google Scholar／Crossref／Semantic Scholar 等国际学术发现查询满足，`mixed` 可由两种生态的查询合并覆盖。发现查询只能证明检索路径；来源是否获得范文／前沿角色仍由第 6 节的原文身份合同决定。

### 4.1 Google Scholar 查询

OpenAlex 与 Google Scholar 并列承担外文发现；Scholar 可由受控 Chrome 或可选
`intl-search/scripts/scholar_search.py`（`scholarly`）执行。两者都只返回结构化对象，父控制面负责写注册表。

Scholar query 必须：

- 固定 `channel="Google Scholar"`，保留原检索式、`filters` 对象、用途、ISO 日期与 `status=complete`；
- `url` 使用 `https://scholar.google.com/scholar?...&q=...`，不能登记普通 Google 搜索、`google.com/sorry`、引用弹层或缓存链接；
- `result_count` 保存页面 About/约数总量；并写
  `result_count_is_approximate=true`、
  `result_count_basis=page-displayed-about-total` 与原显示语义说明；
- `scholarly` 不暴露总量时，只能保存首屏提取数，使用
  `result_count_basis=first-page-extracted` 并明确该数不是数据库总量；
- 在 `cnki-cn` 中，Scholar 无论 purpose 如何都不能核销 CNKI 的 `venue`、`target-exemplar`、`sota` 合同；在 `international-ssci|mixed` 中，合格 Scholar query 可核销相应的**发现查询**，但结果页、片段、被引数或 BibTeX 本身仍不能取得来源角色，必须回 DOI／出版社／合法 OA 原文核验。

Scholar 只读第一页，检索间隔不少于 5 秒、单会话最多 5 次、不自动翻页。验证码或风控页按 `intl-search/references/scholar-browser.md` 停止协议处理。

允许的 `purpose`：

- `venue`：期刊身份、收录、刊期与选题信息；
- `target-exemplar`：目标刊同构范文；
- `sota`：领域前沿与撞车对象；
- `collision`：精确/近义命题撞车；
- `terminology`：术语谱系与译名；
- `snowball`：引文网络；
- `citation`：引用覆盖池；
- `other`：确有必要的补充查询。

focused acquisition gate 至少要求在活动发表轨道可用的学术生态中完成 `venue`、`target-exemplar`、`sota` 三类查询。零结果也必须记录真实 `result_count=0`，但要说明检索式；不得用“没有搜到”替代查询证据，也不得把另一轨道不适用的零结果当作国际来源晋级的前置例外。

## 5. 来源记录

一个真实来源只建一个记录，多种用途放入同一 `roles` 数组：

```json
{
  "source_id": "CNKI-T001",
  "channel": "CNKI",
  "roles": ["target-example", "field-sota"],
  "title": "论文题名",
  "authors": ["作者甲", "作者乙"],
  "venue": "期刊名",
  "publication_year": 2026,
  "url": "https://kns.cnki.net/kcms2/article/abstract?...",
  "query_ids": ["Q-EX-001", "Q-SOTA-001"],
  "state": "pdf-downloaded",
  "verification": {
    "method": "pdf",
    "verified_at": "2026-07-28",
    "title_match": "yes",
    "support_claim": "从正文核验出的、可明确支撑稿件的一句判断。"
  },
  "local_file": "materials/cnki_pdfs/CNKI-T001.pdf",
  "sha256": "64位十六进制摘要",
  "citation_scope": "final-source",
  "reason": "与本研究任务和目标刊贡献形态同构",
  "used_for": ["style", "sota", "citation"],
  "collected_at": "2026-07-28"
}
```

允许的 `roles`：`target-example`、`field-sota`、`citation-candidate`、`theory`、`terminology`、`snowball`、`web-experience`、`local-material`、`other`。

允许的 `citation_scope`：

- `candidate-only`：筛选或元数据覆盖池，不得写入正文；
- `final-source`：已完成内容核验，可以进入论文；
- `not-for-citation`：只学习体例、检索碰撞或提供背景，不作为论文引文。

同一真实文献不得因来自 CNKI、Scholar、OpenAlex、DOI 或出版社多个入口而建立多个 Source ID。若同一文献既是范文又是 SOTA，在 `roles` 中并列；角色名表示它在论文工作流中的证据责任，不表示数据库归属。
新记录使用 `publication_year`；迁移器仍识别旧 `year` 字段，但下一次注册表核验时应归一化。可引来源必须有可判定的发表年份。

引文忠实度与转引（史料、原典与一切直接引文适用，规范见 `primary-source-citation.md`）：

- `verification.support_claim` 须写明核验所据的版本与页码（整理者／出版社／出版年，或档号＋件内页），例如“已据中华书局 1977 年点校本《清史稿》卷一一四第 ×××× 页逐字核对”；只写“已核”不构成核验依据。
- 逐字核对过的直接引文在 `support_claim` 中标“逐字核对”并给页码；只读过摘要、录文或电子库文字层的，写明实际读到的载体，不得写成已核纸本或原件。
- 转引时原始文献若单独建 Source ID，其 `state` 不得写 `content-verified`，`verification.method` 只能对应实际读到的载体；在 `support_claim` 或 `reason` 中写“转引自 <二手文献 Source ID> 第 × 页，原书未见”，二手文献照常核验。
- 正文页码仍须进入 `page-evidence` 的 A/B/C 分级；转引与未核纸本的引文保持【VERIFY】，不因注册表已有记录而解除。

### 5.1 Scholar 候选与唯一身份

Scholar 首屏结果统一登记为：

```json
{
  "source_id": "GS-CAND-001",
  "channel": "Google Scholar",
  "roles": ["citation-candidate"],
  "title": "Paper title",
  "authors": ["First Author", "Second Author"],
  "publication_year": 2025,
  "url": "https://publisher.example/article",
  "query_ids": ["Q-GS-001"],
  "state": "discovered",
  "verification": {},
  "citation_scope": "candidate-only",
  "metadata": {
    "scholar_bibliographic_line": "authors - venue, year - publisher",
    "scholar_snippet": "result-page excerpt",
    "scholar_cited_by": 12
  },
  "reason": "撞车、筛选或 DOI 恢复候选",
  "used_for": ["screening", "collision", "doi-recovery"],
  "collected_at": "2026-08-04"
}
```

片段、被引数和 Scholar BibTeX 只能放 metadata/著录层；BibTeX 至多推进到
`metadata-exported/candidate-only`，不能写入 `verification.support_claim`，
也不能把 Citation Scope 改为 final-source。

去重按确定性从强到弱执行：DOI、规范 URL、题名＋首位作者＋年份。精确命中时复用原
Source ID，只向 `query_ids` 追加 Scholar Query ID；不得新建重复记录。拼写、译名、
作者缩写或年份不一致等模糊命中只标独立证据复核，不自动合并。

Scholar 候选晋升承重来源时，在同一 Source ID 上把 canonical channel/URL 改为 DOI、出版社或
合法 OA 原文，至少记录：

- `verification.method=abstract|detail|full-text|pdf`、ISO 日期与具体 support claim；
- 非 Scholar 的 `verification.content_url`；
- `verification.retraction_status` 与 `retraction_checked_at`；
- 若晋升为国际 `field-sota`，还须保留工作区本地全文 PDF、`sha256`；扫描件另记 `verification.ocr_text_file` 与 `ocr_text_sha256`；
- acquisition v2/v3 适用的 credibility；正文使用具体页码时另接 page-evidence。

Scholar 查询页、结果片段、被引数、他人转述或 BibTeX 不能作为 content verification。确系撤稿
不得作支撑来源；更正版本须核对更正后内容并使用
`retraction_status=corrected-version-verified`。

### 5.2 开放网络最终来源的条件式可信度

只有同时满足以下三项的普通开放网络来源才强制填写 `credibility`：

1. `citation_scope=final-source`；
2. URL 是公开 HTTP(S) 网络材料；
3. 通道既不是 CNKI，也不是明确的官方原始记录通道。

CNKI 文献、经 DOI／学术出版社／合法 OA 原文核验的学术文献，以及 `official`、`official-web`、`government`、`government-web`、
`institutional-primary`、`official-record` 通道的官方原始记录，不受普通网页统一横向核验
门槛约束；这不免除其各自的内容、日期、撤稿和身份核验。普通 `web` 记录不能仅靠把
`source_class` 自称为 `official-primary` 来绕过门禁。

```json
{
  "credibility": {
    "source_class": "scholarly-publisher",
    "authorship_publisher": "作者身份及发布机构的核验结果",
    "sponsorship_interest": "资助、广告、利益关系或未发现情况",
    "corroborating_source_ids": ["WEB-C002"],
    "contradicting_source_ids": ["WEB-C003"],
    "checked_at": "2026-07-30",
    "status": "passed",
    "note": "说明横向核验支持了什么、仍有什么限制。"
  }
}
```

`source_class` 可为 `official-primary`、`scholarly-publisher`、`news-media`、
`ngo`、`commercial`、`personal`、`open-web` 或 `other-public-web`。状态可为
`passed`、`needs-review`、`not-applicable` 或 `rejected`。横向来源必须是注册表中
其他 Source ID，不能用来源自己为自己背书。作为开放网络 `final-source` 时，只有
`passed` 且至少有一个支持或质疑 Source ID 才能通过；信息不足一律保持
`needs-review`，不得从关键词、域名或旧笔记自动推断 PASS。把网页另存为工作区文件
不会改变其来源类别，也不能借删除 URL 绕过可信度核验。

v2/v3 中，`credibility.status=passed` 必须至少有一条真正独立的
`corroborating_source_ids`：该 Source ID 已登记、已完成内容核验，具有证据用途角色，
且不与当前来源处于同一互证循环。自引、两节点或多节点纯循环均不构成横向核验。
`contradicting_source_ids` 应保留用于呈现反对证据，但不能替代支持性横向来源。

### 5.3 引文边（edges）

来源之间的关系不是备注，是数据。注册表顶层可选 `edges` 数组记录两个已登记 Source ID 之间经核验的关系，
供"奠基链"和"真实反方"覆盖门做机器核验，也供 `SYN-*` 的 `source_links[].edge_ids` 引用：

```json
{
  "edge_id": "EDGE-001",
  "from_source_id": "CNKI-S003",
  "to_source_id": "CNKI-S001",
  "relation": "cites",
  "evidence": "full-text-read",
  "stance": "critical",
  "context_quote": "该文将奏折数量当作信息流量，忽略了内容层的失真问题。",
  "context_locator": "第 45 页第 2 段",
  "query_id": "Q-SNOW-001",
  "verified_at": "2026-09-04"
}
```

- `relation`：`cites`（from 引用 to，有方向）、`co-cited-with`（同被引，无方向）、`co-mentioned-with`（同段共提及，无方向）。
- `evidence`：`openalex`、`semantic-scholar`、`crossref`、`other-index` 是索引层证据，`cnki-detail` 是知网详情页引文区，
  `grobid-paragraph`、`full-text-read` 表示实际读到了施引段落。
- `stance` 只对 `cites` 边有意义，取 `supportive|critical|neutral|unknown`，缺省 `unknown`。**`unknown` 以外的立场必须来自
  施引文本**（`evidence` 为 `grobid-paragraph` 或 `full-text-read`）并附至少 10 字的 `context_quote`；S2 的他引上下文、
  题名含"商榷"之类的词法线索只能先登记 `stance=unknown` 并把线索放进 `context_quote`，读到原文后再改立场。
- `co-mentioned-with` 同样要求段落级证据与共提及的 `context_quote`；`co-cited-with` 可由索引或详情页证明，可用 `via_source_id`
  记录那篇同时引用两者的文献。
- 端点必须是本注册表的 Source ID，不得自引；`edge_id` 唯一；同一对端点同一关系只登记一次（无方向关系按无序对去重）；
  `verified_at` 为 ISO 日期；`query_id` 若填写须解析到已登记 query。候选来源之间也可登记边，边不改变来源的 `citation_scope`。
- 来路映射：`intl-search` 的 `openalex_snowball.py` backward 结果给出"种子引用了谁"（from=种子，to=条目，`evidence=openalex`），
  forward 结果给出"谁引用了种子"（from=条目，to=种子）；`s2_search.py cites/refs` 同理，`contexts` 先进 `context_quote`、立场留 `unknown`；
  `cnki-snowball` 的 references/citations 对应 `evidence=cnki-detail`，coreferences/cocitations 对应 `co-cited-with`。
  条目只有登记为 Source ID 后才能成为边的端点。
- 验证：`validate` 对 edges 做结构校验并计入 `stats.citation_edges`；`sync` 生成的 `source_index.md` 末尾附 Citation Edges 表。
  覆盖门如何使用边见 `literature-sufficiency.md` 第五节。

## 6. 状态与证据等级

状态只能向前推进：

1. `discovered`：结果页或目录发现；
2. `metadata-exported`：题名、作者、刊名、年份等已从注册来源导出或详情页核对；
3. `content-verified`：摘要、详情页实质内容或原文已读，并有具体 support claim；
4. `pdf-downloaded`：全文真实落盘并封存。

`final-source` 至少达到 `content-verified`，且 `verification.method` 只能是 `abstract`、`detail`、`full-text` 或 `pdf`。题名、导出元数据、滚雪球列表不能写 `final-source`。

`target-example` 必须达到 `pdf-downloaded`，以 `pdf`/`full-text` 核验，记录 `title_match=yes`、核验日期和具体结构/论证用途。文件须可解析、含多页文章正文和可核验的文末参考文献或规范页下注、SHA-256 一致；不同范文的 URL、项目内路径和文件摘要都必须互异。`field-sota` 至少达到 `content-verified`；国际轨的 `field-sota` 同样保留本地全文 PDF 与 SHA-256，不能让发现页或摘要元数据冒充原文。数量与来源生态按轨道解释：

- `cnki-cn`：`target-example` 与 `field-sota` 每种角色至少一条合格记录；外部范文只可走 SKILL 主协议中用户明确授权、CNKI 查询确证零结果后的窄例外。
- `international-ssci`：机器门至少要求 1 条合格 `target-example` 和 1 条合格 `field-sota`，并逐条审查所有已声明角色记录；这只是“角色真实存在”的下限，不是外文数量配额。范文须来自目标刊出版社或合法机构仓储全文，并与 config 的目标刊一致；前沿须回 DOI／出版社／合法 OA 原文完成内容与撤稿核验，且两类角色 PDF 都通过正文型文件检查。国际 source-index 与 citation minimum 只计注册表中相应国际学术通道的合格记录，普通网页不能在已有一条学术来源后填满剩余下限。覆盖是否充分由问题、竞争解释、反证、主张责任和隔离评审判断。
- `mixed`：至少各有一条 CNKI 与国际学术来源；范文／前沿角色可由适合该责任的生态承担，不设置双份数量门。理论锚点、撞车与最终引文仍须保留两种生态的真实证据链。

页面核验与页码证据不是同一件事。正文出现具体页码时，仍须进入 `page-evidence` 的 A/B/C 证据等级。

## 7. PDF 落盘闭环

1. 筛选后先告知用户预计下载篇数和可能验证码次数。
2. 在详情页做真实下载探针；无权限即请求合法登录/机构网络并保持阻塞。
3. 触发下载后，确认浏览器下载已经完成，而非只看到点击反馈。
4. 将文件保存或移动到工作区受管路径；CNKI 通常使用 `paper_rewriting_output/materials/cnki_pdfs/<ASCII-ID>.pdf`，国际全文可使用 `paper_rewriting_output/materials/source_pdfs/<ASCII-ID>.pdf`。
5. 打开本地文件检查解析性、页数、正文、文章结构、引证装置（文末参考文献或规范页下注）与题名，并在 `verification.title_match` 记录 `yes`；扫描件将 OCR 全文保存为工作区 `.txt`/`.md`，在 `verification.ocr_text_file` 记录路径。
6. 在注册表填写 `local_file` 和 `state=pdf-downloaded`；扫描件同时填写 `verification.ocr_text_sha256`。
7. 运行 `seal` 计算并写入 SHA-256。
8. 运行 `sync` 生成 source index 与 citation support bank，再运行 acquisition gate。

`cnki-cn` 的目标刊范文不得用公开副本替代 CNKI 下载，除非严格满足主协议的窄例外。`international-ssci` 的范文可来自目标刊出版社或合法机构仓储全文，不要求先证明 CNKI 零结果；发现页、聚合元数据和未经授权副本不能替代。任何轨道的承重文献在无合法全文权限时都不能虚报已核验；按该文献在当前工作流的实际必要性决定请求权限、改换主张或删除来源。

## 8. 与本地研究工件的连接

- `source_index.md`：只由注册表生成，禁止手改。
- `citation_support_bank.md`：同样只由注册表生成；每一行的 `Candidate ID` 等于 `source_id`，Source Channel、URL、年份、核验和 Citation Scope 均来自注册表。它用于检查覆盖，不是第二份书目真相。
- `research_design.json` / `evidence_bank.md`：每条学术证据把 Evidence ID 映射到 Source ID 与 Claim ID；页码另接 page-evidence 记录。
- `style_profile.md`：只引用 `target-example` Source ID，不复制独创措辞。
- `sota_gap_map.md`：区分 `field-sota`、`candidate-only` 与 `final-source`。
- `references.bib`/脚注：只从 `final-source` 生成；citation key 与 Source ID 的映射应保留在登记或构建记录中。

## 9. 命令

```powershell
$env:PYTHONUTF8='1'
{{RUNTIME_HOME_ASSIGNMENT}}
$Acq = Join-Path $AverethHome 'skills\cnki-paper\scripts\cnki_acquisition.py'

& $Python -X utf8 $Acq init paper_rewriting_output
& $Python -X utf8 $Acq migrate paper_rewriting_output --dry-run --to v3
& $Python -X utf8 $Acq migrate paper_rewriting_output --apply --to v3
# 如需回滚，使用 apply 输出中的 manifest 路径
& $Python -X utf8 $Acq migrate paper_rewriting_output --rollback migration/acquisition_v3/migration.<digest>.json
& $Python -X utf8 $Acq seal paper_rewriting_output
& $Python -X utf8 $Acq sync paper_rewriting_output
& $Python -X utf8 $Acq validate paper_rewriting_output --scope reconnaissance --write
& $Python -X utf8 $Acq validate paper_rewriting_output --scope focused --write
```

- `init` 只生成必然阻塞的空骨架，不会伪造已完成状态。
- `migrate --dry-run --to v3` 零写入展示迁移计划；`--apply` 按源文件摘要备份
  v1/v2 注册表后写 v3，不代造 Exa、Zotero、citation key 或核验 PASS；`--rollback`
  只在注册表仍与迁移后摘要一致时字节级恢复，迁移后发生改动则拒绝破坏性回滚。
- `seal` 只为真实存在的本地 PDF 计算摘要。
- `sync` 从注册表同时生成 source index 与 citation support bank；发现未受管的旧手工视图时拒绝覆盖。
- `sync --force` 首次覆盖旧手工 citation bank 前，会将其保存到 `migration/research_design_v3/citation_support_bank.legacy.md`；重复执行保持幂等。
- `validate --scope reconnaissance` 用于 acquisition 首遍，只验活动发表轨道的真实权限／查询、最小适用来源登记与两个生成视图的一致性；`--scope focused` 用于 research 问题承诺前，按 `publication_track` 验收范文、field-SOTA 与 final-source 角色合同。三轨都不从 flash/pro 推导数量；完整文献基线由 `literature_analysis.json` v2 单独裁决。`manuscript_audit` 可跳过为现成稿件新下载范文，但不能跳过已登记来源、文件摘要和身份链真实性。

## 10. 旧任务迁移

脚本读取 acquisition v1/v2/v3，新建注册表使用 v3。未启用 Exa/Zotero 集成的 v2
工作区继续可读可验；一旦出现 integration manifest/snapshot 就必须显式迁到 v3。
v1 只允许检查与迁移，统一 acquisition 及后续 gate 在迁移完成前保持阻塞。
旧任务已有 v1 或需要启用 integration 的 v2 注册表时：

```powershell
& $Python -X utf8 $Acq migrate paper_rewriting_output --dry-run --to v3
& $Python -X utf8 $Acq migrate paper_rewriting_output --apply --to v3
```

先检查 dry-run 的 `needs_review_source_ids`。应用迁移后，逐条核验开放网络最终来源；
纯 CNKI、官方网页和非最终候选不会被制造统一可信度负担。迁移重复执行应报告
`already-current` 且零写入。

旧任务只有 `source_index.md` 时：

```powershell
& $Python -X utf8 $Acq migrate-index paper_rewriting_output
```

迁移只保留可识别的旧行，不自动创造查询溯源、权限状态或内容核验。随后必须：

1. 补录真实 queries 与 access 探针；
2. 对每条来源重新确定 state 与 citation scope；
3. 对真实 PDF 运行 `seal`；
4. 审核注册表后运行 `sync --force`；
5. 重新通过 acquisition 与 research gate。

这条路径用于恢复，不允许把旧笔记批量标成 `content-verified`。
