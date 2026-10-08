# 知网操作实测笔记（Avereth v7）

`cnki-*` 各技能自带操作说明；本文只记录实测差异、CNKI 非 DOI 证据链和一体化获取约束。来源字段与状态以 `acquisition-registry.md` 为准。

## 0. 工作流预检

每次新建、恢复或更新后先通过统一控制器检查运行时与状态：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
{{RUNTIME_HOME_ASSIGNMENT}}
$Controller = Join-Path $AverethHome 'skills\cnki-paper\scripts\avereth.py'
& $Python -X utf8 $Controller doctor
& $Python -X utf8 $Controller status paper_rewriting_output
```

中文/CNKI 任务的唯一控制面是 `cnki-paper`；`avereth_core` 只是它的私有实现包，不提供第二套状态或完成权威。`doctor` 只诊断，不自动修改工作区。

## 1. 验证码协议

- 两种常见形态：滑块拼图（blockPuzzle）、点选文字（clickWord）。检测 URL 是否含 `verify/home`，或可见验证组件是否进入视口；SDK 预加载在远离视口的位置不算触发。
- 处理：暂停当前验证所阻断的动作，保留原 Chrome 标签页，由主线程请用户手动完成；子代理返回 `PRIMARY_THREAD_ACTION_REQUIRED` 并说明具体操作。在当前阶段继续 controller 允许且不依赖这次验证的已授权工作；用户确认后重新读取页面状态并重试当前动作一次。
- 下载会抬高风控：触发后文章页导航和同源 fetch 都可能逐次要求验证。批量下载前先说明预计次数；在 `publication_track=cnki-cn` 时，目标刊范文按 tier 数量筛选后必须逐篇下载，其他全文才执行“只下载承重文献”的最小化原则。国际轨道不启动这项 CNKI 下载合同。

## 2. 检索与解析

- 检索策略（字段取舍、四路主题词扩展、核心刊过滤开关与系统性漏检、排序视图偏差、滚雪球起止、饱和判据、PRISMA-S 式日志字段、中英检索不对等）以 `cnki-search/references/search-strategy.md` 为准；操作技能只负责执行。
- 普通/高级检索和结果解析按已安装 CNKI 技能执行；先使用 `{{BROWSER_TOOL_NAME}}`，再用当前宿主支持的标签页、定位器与页面求值操作。
- 高级检索旧版界面 `https://kns.cnki.net/kns/AdvSearch?classid=7NS01R8M` 才提供来源类别筛选；北大核心常用 `#hx`，CSSCI 常用 `#CSSCI`。页面变更时重新读取 DOM，不盲信历史选择器。
- 被引排序后轮询首行被引数字发生变化再提取；URL 已切换而导航等待超时，不应直接判失败，应读取新页面状态。
- `literature_registry.json` 的 query 记录必须保存检索式、字段/筛选、排序、页码、结果数、采集日期和稳定 URL；来源记录保存 verification status。随后由脚本生成 `source_index.md`。

## 2a. 中文术语谱系与自创词撞车检索

对标题、摘要、各级标题、中心命题和贡献陈述中的核心术语，按 `terminology-governance.md` 建检索组：

1. 精确词：完整术语加引号或主题/篇名精确检索；
2. 近义词：中文学界已有近邻概念、常见同义表达与缩略形式；
3. 构词变体：拆检前后缀和核心词根，尤其“化、性、感、力、逻辑、机制、范式、赋能、耦合”等命名；
4. 描述检索：不用拟议名称，直接检索其声称指向的现象、关系或机制；
5. 译名检索：外文原词、已有中文译名及“原词 + 中文学科”组合。

每组在 `literature_registry.json` 登记独立 Query ID、查询式、字段、核心来源/学科筛选、采集日期、结果规模和稳定结果页；代表性文献或权威原典各用唯一 Source ID。结果数量只证明“检索到了什么”，属于 screening evidence，不能单靠命中数宣布某术语已经是中文学界通说。脚本生成 source index，采用的术语在 `terminology_register.md` 引用这些 Source ID。

自创术语精确检索为零也不自动证明原创：必须继续跑近义、构词变体和描述检索，比较既有概念是否已经承担相同解释任务。若已有通行术语足够，回用通行形式；若仍采用新术语，默认最多一个，并记录用户确认。政策/法律/标准中的正式用语另登记官方原文来源，但官方出现不等于学术概念已经成立。

## 2b. 引文滚雪球（详情页六方向）

- 中文侧引文追踪用 `cnki-snowball` 技能：详情页引文网络区提供参考文献（后向）/引证文献（前向）/共引/同被引/二级参考/二级引证六方向，标签 `a#<方向>`＋`changerefdata()` 激活，容器 `#quoted-<方向>` 懒加载。
- **每方向第 1 页（每来源组约 10 条）免验证**；翻页对机构 IP（utype≠jf）必弹验证码——这是刻意风控门（`getrefdata` 带 `captchId` 参数），**不得直调内部函数绕过**，按铁律 1 交用户完成后续跑。深前向改走检索页被引排序。
- 数据端点 `restapi/citation-api/v1/literature/{references|citations}` 的 `v` 令牌一次性，直连/重放必 `400001 引文参数无效`，只能驱动页面自身 JS。
- 引证文献默认时间倒序（最新对话视图）；滚雪球产出是书目级 screening evidence，入注册表 query 记 `purpose=snowball` 与 `snowball:<方向>@<种子>`，条目共用稳定 Source ID，拟引用仍须详情页内容核验。
- **中国引文库（ref.cnki.net）是引文追踪的补充入口**（页面标题实核 2026-07；知网权限体系，风控纪律同主站）：被引文献检索、学者/机构/期刊引证统计与引证报告。详情页六方向仍是逐篇滚雪球主通道；引文库用于按被引筛选承重文献、核对被引数与查全交叉验证。首次使用先实测页面结构再固化选择器，产出同记 screening evidence。

## 3. knavi 期刊导航空白页

现象：显示“找到 N 条结果”但列表为空。历史有效修复是点击期刊 doctype 标签 `ul.doctype li#ZNZEND0A a`，再轮询实际 `dl.result`。不要点击顶部导航中同名“期刊”链接；若选择器失效，按可见语义重新定位并更新记录。

## 4. 批量导出与引用库

### 4.1 已验证导出参数

`POST https://kns.cnki.net/dm8/API/GetExport`

```text
filename=<结果页复选框 input.cbItem 的 value>
displaymode=GBTREFER,elearning,EndNote
uniplatform=NZKPT
```

`displaymode` 必须逐字为 `GBTREFER,elearning,EndNote`；响应 mode 常见为 `GBTREFER` / `ELEARNING` / `ENDNOTE`。年份优先取 EndNote `%D` 或 ELEARNING 年份字段。每页通常 20 条，循环留出节流间隔。

### 4.2 CNKI 非 DOI 证据链

citation bank 使用 12 列单表（含 `Citation Scope`），但来源身份由注册表统一。每一行 CNKI 文献都写：

- `Candidate ID` 精确复用注册表 `source_id`；
- `Source Channel=CNKI`；
- `Source` 与注册表中的可重访 CNKI 详情页、期刊目录页或 DOI 落地页一致；
- `Verified=yes` 与 `Citation Scope=final-source` 只在题名/作者/来源及拟用支撑内容已经由摘要、详情页或全文核对后使用；仅结果页筛选或书目导出的条目标为 `Verified=no`、`Citation Scope=candidate-only`；
- `Verification Note` 必须同时包含稳定 URL/标识符、内容核验方式和 ISO 采集日期，例如：
  `https://kns.cnki.net/kcms2/article/abstract?...；CNKI 详情页核对题名/作者并读取摘要内容；采集 2026-07-10`；
- `Support Claim Sentence` 是能支撑正文的一句具体判断，不能是题名改写。

中文 DOI 常不被 Crossref 收录。CNKI 详情页、导出元数据、期刊目录或本地 PDF 可以构成可靠的非 DOI 核验链；不要把无 DOI 自动判为 unverified，也不要用 `Verified=yes` 自我声明替代稳定 URL 和采集方法。

### 4.3 目标刊引文体例

引用显示由 `workflow_config.json`、用户明确选择和目标刊投稿须知/范文共同决定。脚注制、顺序编码、著者—出版年制均可能正确；不能把纯数字 `[1]` 硬编码成所有中文期刊的默认。无论显示形式如何，引用必须与真实 bibliography/footnote 条目可追踪关联。

核对具体刊的著录细节（标点、字段序、双语"等/et al."处理）时，可查 zotero-chinese/styles（github.com/zotero-chinese/styles，社区维护的数百个中文期刊/学位论文 CSL 样式）作机读参考——该刊已有实现的 csl 文件就是其著录规则的结构化表达。仅作参考不 vendor（CC BY-SA 3.0 与本仓库 MIT 不兼容），最终以刊方投稿须知与近期刊文实例为准。

## 5. 同源 fetch 批量抓摘要

在合法登录的 `kns.cnki.net` 页面上下文内，可使用带 credentials 的同源 fetch 获取少量详情页并用 DOMParser 解析。实测宜小批次、请求间留间隔。

风控升高后 fetch 也可能 302 到验证页。判断最终 `resp.url`、可见验证元素和返回内容，不能只查 HTML 是否含某个固定字符串。采集方式和日期仍要写入 source index/citation bank。

## 6. PDF 下载与机构权限

- 详情页显示机构图书馆等身份时，通常可点 PDF 下载；权限状态仍须实际核验。
- `publication_track=cnki-cn` 的 research 至少保留一条身份、权限、正文和本地文件均通过的目标刊范文 PDF；摘要、详情页笔记、公开副本和其他数据库文件不能替代，主协议明确列出的窄例外除外。文献基线所需至少五篇可比论文可通过 DOI／URL／本地哈希核验，不等同于五份目标范文 PDF。
- CNKI 轨道的下载探针遇登录墙、机构权限或下载限制时，只暂停受影响的来源获取和依赖动作，保留原 Chrome 标签页，由主线程请用户登录、切换机构网络或提供合法机构权限；在当前阶段继续 controller 允许且不依赖该权限的已授权工作。必要权限仍不可用时，相应来源获取和依赖其资格的阶段保持阻塞，不得降级完成 research。国际轨道只对实际需要的国际来源权限保持同等真实性要求，不因 CNKI 权限不可用而阻塞。
- 下载后确认浏览器已完成落盘，归档到 `materials/cnki_pdfs/<ID>.pdf`（稳定 ASCII ID），在注册表记录原题名、作者、来源页、下载时间和文件映射；运行 `cnki_acquisition.py seal` 写入 SHA-256。
- 中文文件名与中文路径优先用 Python `pathlib` 或安全的 PowerShell literal path 处理。
- 下载后把 reference mode 调整为 local-first（若 config 支持），运行注册表 `sync` 生成 source index，再重新生成 `source_inventory.md`。
- 范文按“同构优先”筛选；除此以外，只下载已筛选、需要全文或页码核证的文献，不要为凑引用池数量盲目下载。

## 7. 本地审计与输出校验（Windows / 中文语境）

| 项目 | 风险 | 处理 |
|---|---|---|
| 所有 Python 脚本 | Windows GBK 控制台打印特殊字符可能崩溃 | 设置 `PYTHONUTF8=1` 和 `PYTHONIOENCODING=utf-8` |
| `citation_bank_check.py` | 多表表头、空 Source Channel、`final-source` 只有书目无支撑句会形成弱行 | 使用本地 12 列单表；CNKI 行按第 4.2 节填写 |
| `citation_quality_audit.py` | 中文 DOI/无 DOI 条目可能无法走 Crossref | 使用稳定 CNKI URL + 采集方式/日期的非 DOI 验证链 |
| 来源清单 / integrity | 清单与注册表漂移 | 以 `literature_registry.json` 为唯一真相，`source_inventory.md` 只作派生视图 |
| `structured_review.py` | dispatch 需要可评审稿；Reviewer 输出可能缺少严格 v2 字段或夹带内部 ID | 先有规范稿；只向三个隔离 Reviewer 分发各自生成 prompt，并校验三份不可变 `*_review_output.md` 的严格 v2 合同；Reviewer 不接触 Claim/Evidence/Design/Execution ID |
| `contribution_check.py` | 动机被误当贡献、模板占位 | 填满 `confirmed_contribution.md` 四个区块；在蓝图/正文前 PASS |
| `results_validation_check.py` | 缺少执行真相、规范执行校验阻断，或没有带 `allowed_uses` 的结果 | 只消费 `method_execution.py::downstream_eligibility`；`results_validation.md` 仅作可重建说明视图，不能授权结果使用 |
| `review_lifecycle.py` | assurance、Finding、resolution、cycle 或派生视图漂移 | 按不可变 raw outputs → `cnki-review-assurance/v2` → `avereth-review-findings/v3` → `avereth-review-resolution/v2` 编译；返修追加 hash-bound cycle，Markdown 只由两个 canonical JSON 生成 |
| `reviewer_audit_check.py` | 评审意见未结构化、零 Finding 被误用或重大问题未闭合 | 验证规范 JSON 生命周期与其派生视图；标题统一为 `Editorial Fit Assessment`；仅三份源 verdict 均为 PASS 时允许零 Finding |
| `avereth.py gate --stage audit` | 旧报告、手填 Markdown 或未关闭的重大评审意见 | 由本地 action graph 依次完成 raw validation、lifecycle compile/validate/render 与 audit checks，再签 audit receipt；禁止手工伪造 PASS |

更新后若发现 reviewer 输出、动态年份、清单命名或路由回退，先运行 `doctor` 与只读 `status` 定位最早责任阶段；需要迁移旧工作区时显式运行 `migrate --dry-run`，不要在单次项目里绕过 gate。

## 8. 正式输出与渲染 QA

正式交付只有一条路径：完整执行 `workflow-playbook.md` 阶段 7 的“两次 output gate—中间真实逐页复核”协议。转换器、Word 规范化和各守卫只是控制器内部或 build 前的准备动作，不得直接写最终目录、替代候选 QA 或单独宣告交付完成。翻译、投稿与正式回复的输入合同分别见 `engine/translate.md`、`engine/submission.md`、`engine/respond.md`。

## 8b. docx 投稿格式修复（OOXML）

```powershell
$DocxFix = Join-Path $AverethHome 'skills\cnki-paper\scripts\docx_fixup\docx_normalize.py'
& $Python -X utf8 $DocxFix 稿件.docx 成稿.docx --all
& $Python -X utf8 $DocxFix 成稿.docx --check
```

默认安全集处理字体、引号、脚注、缩进和 WPS 扰动；标题、引文、表格、灰度等破坏性项需显式开启并抽查。含 drawing 的段落不可粗暴清空 runs；纯引号 run 的 eastAsia hint、脚注 id 顺序和 ECMA-376 元素顺序均须保持。

## 9. 外文文献通道

- 外文发现由 OpenAlex 与 Google Scholar 并列承担；用户显式要求 Scholar 时可直接查 Scholar。两条通道都先生成候选，不因来源名或被引数自动提高证据等级。Semantic Scholar 只补 TLDR、citation context、recommend 等独有字段。
- OpenAlex 短语检索优先加引号；中文概念先确认正式英译并测试变体。
- **深度靠引文滚雪球**：确定要对话的奠基/高被引外文后，跑 `intl-search` 的 `openalex_snowball.py`（backward 挖理论谱系、forward 挖最新对话与撞车），发现路径（种子 DOI 与方向）写入 Verification Note 以便审计重放。关键词检索只保证"搜到了"，不保证"覆盖了引用骨架"。
- Semantic Scholar（`s2_search.py`）只取独有字段：tldr 快筛、他引上下文（citation contexts）、recommend 推荐。**他引上下文是别人转述，仅作主张定位线索与影响力证据，进引用库前必须回原文核验**；共享池 429 常态，稳定使用设 `S2_API_KEY`。
- 外文承重文献需全文核验支撑句时，优先用 OpenAlex `--json` 的 `oa_pdf` 开放获取直链，下载遵循"下载最小化"。
- 长 PDF/双栏 PDF 找支撑句时，可用 `pymupdf4llm`（`pip install pymupdf4llm`，PyMuPDF 官方扩展，无模型依赖）`to_markdown()` 一步转 markdown：多栏阅读顺序重建、表格识别、纯图像页自动 OCR，比裸 `page.get_text()` 更适合双栏社科刊；提取文本只作定位与核验辅助，引用页码仍按 `page-evidence` 分级。
- **订阅全文平台 Taylor & Francis Online（tandfonline.com）**：Routledge 系社科期刊（政治学/IR/公管强刊）全文所在地。OpenAlex/DOI 定位后，经用户 Chrome 的机构权限（IP/CARSI）取全文核验支撑句；按权限通则，遇付费墙先请用户登录或确认权限，不得静默降级为只用摘要。其他出版社平台（SAGE/Wiley/Springer/CUP/OUP）同规。
- 外文动作先写 acquisition v2/v3 `literature_registry.json`；`source_index.md` 与 `citation_support_bank.md` 只由 `cnki_acquisition.py sync` 生成，禁止手改。外文条目在生成视图中标记 `K-foreign`；Source 使用 DOI/出版社稳定页，Verification Note 写标识符、核验渠道和日期。
- 有 DOI 的外文条目可以进入 DOI/Crossref 审计；Crossref 年份与纸面出版年不一致时，以拟引版本为准并记录。
- **撤稿检查（citation 质量硬项）**：外文条目看 `openalex_search.py --json` 的 `is_retracted`——**true 是警示不是判决**（OpenAlex 把 Crossref/Retraction Watch 的更正、关注表达也并入该布尔值，2025 年研究已证实误报），须回出版社页面/Crossref 核对真实状态：确系撤稿则不得引用（或仅作为撤稿事件本身的研究对象并明示）；更正/关注表达则引用时核对更正后内容。中文条目在 CNKI 详情页与期刊官网查撤稿/更正声明。检查结果记入 Verification Note。
- Scholar 页面只使用当前 `{{BROWSER_TOOL_NAME}}`：只读第一页、两次检索至少间隔 5 秒、单会话最多 5 次，不自动翻页。可选 `intl-search/scripts/scholar_search.py` 使用 `scholarly` 做同样的低频首屏提取，不配置代理，也不调用追加 fill/cited-by/BibTeX 请求。
- Scholar query 固定 `channel="Google Scholar"`，保存原检索式、filters、可复核 `scholar.google.com/scholar?q=` URL、页面 About/约数或透明标记的首屏提取数、日期和用途。浏览器返回题名、作者／刊物／年份行、外链、片段、被引数和 query URL，由父控制面写入注册表。
- Scholar 结果首次登记为 `discovered/candidate-only`；Scholar BibTeX 至多 `metadata-exported/candidate-only`。DOI、规范 URL 或题名＋首位作者＋年份精确命中时复用原 Source ID，只追加 Scholar Query ID；模糊命中独立证据复核。
- 拟晋升时回 DOI／出版社／合法 OA 原文，补 `verification.content_url`、摘要／全文 support claim、撤稿状态与日期，并完成适用的 credibility/page-evidence。Scholar 查询页、片段、被引数或 BibTeX 不能成为 content verification/final-source。在 `cnki-cn` 中，它们也不能满足 CNKI 的期刊、目标刊范文、SOTA 或撞车核验；在 `international-ssci|mixed` 中，回到原文并完成身份核验后的同一 Source ID 可直接承担国际范文、前沿、理论或引用角色，不需要先制造 CNKI 零结果例外。
- 检测 URL 含 `google.com/sorry`、reCAPTCHA 或空结果风控页时暂停当前 Scholar 动作，由主线程请用户在原 Chrome 处理；只重试当前动作一次。仍失败就停止 Scholar，继续 OpenAlex 并如实报告未完成，不切换浏览器或绕过验证。

## 10. Zotero 推送（可选）

CNKI 导出 JSON 可交给已安装的 Zotero 推送脚本；需 Zotero 桌面端监听本地端口。推送只是文献管理动作，不能替代 citation bank 的 claim-support 和 verification 字段。反向读取（把用户 Zotero 库当材料源）可装社区 zotero-mcp 后由用户提供条目；库内条目按 `candidate-only` 处理，仍须回 CNKI/原文核验后才可入引用库。

## 11. 页码证据与 CNKI 中文表达

- 页码引注进入 `evidence_bank.md` 的 `## Page Evidence`；A/B 级可核销，C 级知网三角旁证仍保留 `VERIFY` 并阻断终稿，只进入阻塞性核验报告。
- 书目页码范围不是引文定位；期刊 PDF 用本地版式定位形成 B 级，原典尽量取得页面影像或规范定位符形成 A 级。
- 中文表达优化读取本技能的 `academic-prose.md`、`anti-defensive-writing.md` 与 `top-journal-anatomy.md`，减少模板句、机械对称和空泛元话语，贴合目标刊刊性。它不改变证据边界，也不承诺规避 AIGC 检测或达到特定分数。

## 12. CNKI 之外的国内补充源

在 `cnki-cn` 中，CNKI 是核心中文源，这一定位不变。国内补充源用于收录差异的交叉核验、扩充非范文材料和在取得必需 CNKI 范文 PDF 后减少额外下载；除主协议明确的窄例外外，它们不能在 CNKI 风控受限或无权限时替代 research 硬门要求的 `target_example` PDF。无权限时由主线程请求用户提供合法权限；必要权限仍不可用时，只阻断相应来源和依赖其资格的阶段，在当前阶段继续 controller 允许且不依赖该条件的已授权工作。`international-ssci` 不继承这项 CNKI 前置条件；`mixed` 按实际承重责任保留中文与国际两种证据链。

- **NCPSSD 国家哲学社会科学文献中心**（https://www.ncpssd.cn ，域名已自 .org 迁移，旧 nssd.cn 站点已停服）：社科院主办的公益平台，免费注册即可下载大量中文社科期刊全文（CSSCI 刊覆盖良好），另有外文期刊库与古籍库。无稳定公开 API 时用 `{{BROWSER_TOOL_NAME}}` 复用用户浏览器；登记注册表时 channel 写 `NCPSSD`，稳定 URL、采集方式与 ISO 日期同规。
- **万方 / 维普**：无可靠开源 API，GitHub 上的爬虫项目普遍年久失修且有 ToS 风险，不引入脚本化抓取。仅当特定文献 CNKI 未收录（如部分学位论文、地方刊）时经浏览器检索并独立核验，逐条登记。
- **读秀（duxiu.com）——中文专著的书目与试读通道**：引用中文学术专著时，以读秀书目页核验著录信息（书名/作者/出版社/年份/ISBN），目录与正文试读页可确认章节归属；页码核证与文献传递走 `page-evidence` 的读秀/超星节。机构订购权限走用户 Chrome。
- **理论库（data.lilun.cn，人民出版社"中国共产党思想理论资源数据库"）——马列经典与党的文献的原典通道**：党建、统战、思想理论类议题引用《马克思恩格斯文集》、领导人著作、党的重要文献时，用其图书库/知识库按语句/章节检索定位原文与规范卷页（页面模块实核 2026-07，内容需登录）；引注引原典版本卷页，页码核证接 `page-evidence`（渠道树①即本库）。机构权限走用户 Chrome，无权限先找用户。
- 补充源发现的文献凡拟引用，元数据（题名/作者/刊/年/期/页码；专著含出版社/ISBN）仍须回 CNKI 详情页、原刊页面或读秀/理论库书目页核验后再入 citation bank，避免多源元数据漂移；证据链规则与第 4.2 节一致。
- 本节只列与 CNKI 直接互补的期刊与专著通道。明清档案、实录与古籍电子库、地方志、近代报刊、当代政府文献、统计、当代报纸、人大复印等转载信号、港台与海外中文、学位论文的渠道树，以及文献分量与低质刊识别、网络首发回改、撤稿处理，见 `source-channels-cn.md`。
