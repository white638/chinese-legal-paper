---
name: intl-search
description: 检索国外/英文学术文献，以 OpenAlex 与 Google Scholar 并列做发现检索，OpenAlex 引文滚雪球补深度、Semantic Scholar 只补独有字段；Scholar 可走受控 Chrome 或可选 scholarly 适配器。Use whenever the user needs foreign-language or international literature — 外文文献、英文文献、国外研究、SSCI、谷歌学术、Google Scholar、Web of Science 替代、文献综述需要覆盖国外、citation bank 加外文、滚雪球、引文追踪、citation chasing — including topic search, citation ranking, year filters, abstracts, collision checking, DOI recovery, and backward/forward citation chasing.
---

# 外文文献检索（OpenAlex + Scholar 并列发现，滚雪球补深度，S2 补字段）

广度由 OpenAlex 与 Google Scholar 两条发现通道互相补漏，深度靠对承重文献的引文滚雪球；两者不是证据等级。OpenAlex 返回的摘要与 Scholar 返回的题名、片段、被引数、BibTeX 都先是候选，拟承重时仍须回 DOI、出版社或合法 OA 原文核验。

OpenAlex、滚雪球和 S2 脚本仅用标准库。Scholar 可用当前 Chrome，也可用可选的 `scholarly` 适配器；后者不配置代理、不绕验证码，并在阻断时停止。

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 工作流子技能使用时，先读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}`，按其中与本技能同名或同类的规则记录产物，并遵守 `cnki-paper` 控制器 `avereth.py gate --stage <stage>` 的阶段门槛。若本技能正文与该适配契约冲突，以适配契约和父技能 gate 为准。

## 并列发现 A：OpenAlex API（稳定、零验证码、带摘要与被引数）

```bash
python scripts/openalex_search.py "QUERY" [--per-page 15] [--pages 1] [--from-year 2020] \
    [--sort cited|relevance|date] [--type article|review] [--language en] [--oa] [--json] \
    [--mailto you@example.com]
```

- **短语必须加引号**：`"\"new quality productive forces\""`。不加引号是全文散词匹配，
  高被引噪音会淹没真命中（实测：散词 3.3 万条全是无关文献，短语 2705 条全部相关）。
- `--sort cited` 找领域奠基文献，`--sort date` 找最新对话对象；建议双视图各跑一次
  （与知网套路一致）。
- `--pages N` 走游标翻页（每页 `--per-page` 条）；引用库建库需要每组 30–50 条候选时用它，
  不要手动改 per-page 超过 50。
- `--oa` 只看开放获取；`--json` 行内 `oa_pdf` 是 OA 全文直链——外文承重文献需要全文核验；`is_retracted` 为 true 时是撤稿警示（含更正/关注表达误报，须回出版社页面核对真实状态再定去留）
  支撑句时优先走它（下载前仍按"下载最小化"纪律告知用户）。
- `--json` 输出带重建摘要（OpenAlex 的 abstract_inverted_index 已还原为正文），
  用于候选筛选和定位拟核验主张；作为承重摘要证据前仍须在注册表记录真实内容核验渠道与具体 support claim。
- **摘要缺失是常态，不是零结果**：Elsevier 等大出版社不向 OpenAlex 开放摘要，`--json` 的 `abstract` 大面积为空。空摘要的候选须回出版社页或 DOI 落地页读摘要再筛选，不得因无摘要而剔除，也不得用题名替代摘要写 support claim。
- `--mailto you@example.com` 进入 OpenAlex 的 polite pool，限额与稳定性显著高于匿名池；`--pages` 多页或批量滚雪球前先加上（用真实可达邮箱，邮箱不写进注册表）。
- **`--language zh` 不能替代知网**：OpenAlex 对无 DOI 的中文期刊几乎不覆盖，而中文社科刊多数无 Crossref DOI；`--language zh` 返回的多是少数出版社刊或带英文摘要的条目。中文文献的规模与覆盖仍以 CNKI 查询为准，OpenAlex 的中文零结果不能登记为中文空白。
- 结果含 DOI —— 交给 `intl-export` 技能换 BibTeX 与 GB/T 7714。

中文主题找对应英文文献的窍门：先想该概念的官方英译（如 新质生产力 →
"new quality productive forces"），主题词常有学界变体（再试 "new productive forces"、
拼音直写等），各跑一次短语检索合并。

中英检索不对等：本土概念先中后英（英文只找海外对话，不估规模）；舶来概念先英后中（中文看本土化与本土争鸣）；混合概念两边平行建组。合并前做概念对等检验——通行译名与竞争译名、英文词是否指同一现象、回译是否落回同一中文词、学科是否对等；不通过者两边各记 query，不在覆盖门上互相抵充。细则见 `cnki-search/references/search-strategy.md` 第 10 节。

## 深度：引文滚雪球（承重外文文献必做）

```bash
python scripts/openalex_snowball.py <DOI 或 W-ID> [--direction all|back|forward|related] \
    [--limit 30] [--from-year 2020] [--sort cited|date] [--json]
python scripts/openalex_snowball.py --title "Weaponized Interdependence" --direction forward
```

- **定位**：关键词检索回答"搜到了什么"，滚雪球回答"这个领域相互引用的骨架长什么样"。
  对确定要对话的 1–3 篇外文奠基/高被引文献，backward+forward 各跑一轮，补齐 SOTA
  图谱并检查撞车（citationchaser/openalexR 同款方法，纯标准库实现）。
- `backward`＝它引了谁（挖理论谱系与奠基文献）；`forward`＝谁引了它（`--sort date` 看
  前沿动向，`--sort cited` 看主流承接）；`related` 是算法弱信号，仅供发散，质量参差。
- `--from-year` 对三个方向统一生效；想看全量 backward 谱系就别加年份过滤。
- `--title` 取检索 top hit 当种子，输出首行回显解析结果——**务必确认是目标文献再用下文**。
- `--cd-index [--cd-window 5] [--cd-sample 200]`：对种子算 SciNet 式颠覆指数 (n_i−n_j)/(n_i+n_j)，
  n_i 是只引种子不引其参考文献的施引者，n_j 是同时引用种子与其前人的施引者（省略 n_k）。综述类靠 −1，
  取代前人的奠基作靠 +1。只用于在多篇高被引候选里挑滚雪球种子，不是证据，不写进注册表 support claim。
- 关系入库：backward 条目登记 Source ID 后写 `edges`（from=种子、to=条目、`relation=cites`、`evidence=openalex`），
  forward 反向；格式见 `cnki-paper/references/acquisition-registry.md` 5.3。
- 入库规则：结果与关键词检索同规走 `intl-export`；发现路径（种子 DOI + back/forward）写进
  Verification Note，便于审计时重放。

## 补充：Semantic Scholar 通道（只为独有字段来）

```bash
python scripts/s2_search.py search "query" [--limit 10] [--year 2019-] [--fos "Political Science"]
python scripts/s2_search.py cites 10.1162/isec_a_00351 [--limit 20] [--influential]
python scripts/s2_search.py refs  10.1162/isec_a_00351
python scripts/s2_search.py recommend 10.1162/isec_a_00351
```

- 三样独有资产：`tldr` 一句话摘要（快筛用）；`cites`/`refs` 的 **citation contexts
  他引上下文**——别人引用该文时写的句子，用来定位主张与判断影响力（`--influential`
  只留强影响引用），**它不是原文，进引用库前必须回原文核验**；`recommend` 推荐
  （质量普遍高于 OpenAlex related）。
- 共享池 429 是常态：脚本自带 15/30/45s 三段退避，仍失败以退出码 2 结束 → 回 OpenAlex。
  需要稳定访问就申请免费 key 并设环境变量 `S2_API_KEY`。
- OpenAlex 能做的事不要来 S2 做。
- `cites`/`refs` 的 contexts 是引文立场的线索：登记为 `edges` 时 `evidence=semantic-scholar`、`stance=unknown`，
  把上下文放进 `context_quote`；只有回原文读到施引段落后才能改 `evidence=full-text-read` 并判 `stance`。

## 并列发现 B：Google Scholar

Google Scholar 与 OpenAlex 并列承担外文发现、命题撞车和 DOI 线索；用户显式要求 Scholar 时可直接走本通道。它不能直接形成内容核验或全文证据。

两种受控入口共用 `references/scholar-browser.md` 的同一纪律与结构化返回：

- 当前用户 Chrome：只读第一页，用现行 `{{BROWSER_TOOL_NAME}}` 接口；
- 可选 `scholarly`：运行 `scripts/scholar_search.py`，依赖见 `requirements-optional.txt`。该脚本最多取首屏 10 条，不调用 `fill`、`citedby` 或 BibTeX 追加请求，不配置代理。

```bash
python scripts/scholar_search.py "\"weaponized interdependence\"" \
  --query-id Q-GS-001 --purpose collision --from-year 2019 --pretty
```

检索间隔 ≥5 秒、单会话 ≤5 次、绝不自动翻页。遇 `google.com/sorry`、reCAPTCHA、空结果风控页或 `scholarly` 阻断异常，停止 Scholar；由用户在原 Chrome 处理后只重试当前动作一次，仍失败则继续 OpenAlex 并如实标记 Scholar 未完成。禁止代理池、Cookie/账号导出和验证码绕过。

## 可选扩展：多源 MCP

需要 arXiv/PubMed/SSRN/CORE 等专库直连全文时，可另装开源
[paper-search-mcp](https://github.com/openags/paper-search-mcp)（MCP/CLI 两用，
免费源优先）；本技能不依赖它——社科议题的元数据 OpenAlex 已覆盖其绝大多数来源。

## 输出去向

作为 `cnki-paper` 子技能时，结构化结果先交父控制面去重并写入唯一事实表
`reference_materials/literature_registry.json`。OpenAlex、Scholar、S2 与
`intl-export` 都不得直接写 `source_index.md` 或 `citation_support_bank.md`；二者只能由
`cnki_acquisition.py sync` 从注册表生成。

Scholar 浏览器或 `scholarly` 结果统一使用 `channel="Google Scholar"`、
`state=discovered`（Scholar BibTeX 至多 `metadata-exported`）和
`citation_scope=candidate-only`。DOI/URL/题名—首位作者—年份命中既有记录时复用
原 Source ID，只追加 Query ID；模糊命中交独立证据复核。只有回 DOI／出版社／合法 OA 原文完成内容、承重主张、撤稿与适用的可信度／页码核验后，才在原记录上晋升。
