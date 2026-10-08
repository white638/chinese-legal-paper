---
name: intl-export
description: 外文文献著录导出：DOI 一键换 BibTeX（doi.org content negotiation）并生成 GB/T 7714 外文著录串；在 cnki-paper 中只推进统一注册表的元数据状态，不自行宣布内容已核验。Use whenever the user has DOIs or foreign papers and needs reference entries — 外文参考文献、BibTeX、GB/T 7714 外文格式、著录、参考文献格式化 — typically right after intl-search finds papers, or when adding foreign items to a citation bank.
---

# 外文文献著录导出（DOI → BibTeX + GB/T 7714）

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 工作流子技能使用时，先读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}`，按其中与本技能同名或同类的规则记录产物，并遵守 `cnki-paper` 控制器 `avereth.py gate --stage <stage>` 的阶段门槛。若本技能正文与该适配契约冲突，以适配契约和父技能 gate 为准。

```bash
python scripts/doi_export.py 10.1080/20954816.2024.2386503 [更多DOI ...]
python scripts/doi_export.py --file dois.txt --out refs.md
```

每个 DOI 输出两种格式：

- **GB/T 7714 外文著录**（中文期刊要求外文文献也按此格式）：
  `XIE F, JIANG N, KUANG X. Towards an accurate understanding of 'new quality
  productive forces'[J]. Economic and Political Studies, 2025, 13(1): 1-15.
  DOI: 10.1080/20954816.2024.2386503.`
  规则：≤3 作者全列（姓全大写+名缩写，不加缩写点），>3 列前三加 `et al`；机构作者
  （Crossref `name` 字段）原样保留；`title` 与 `subtitle` 以 `: ` 拼接；`edition-number`≥2
  时写 `2nd ed`（初版不写）；缺出版地/出版社/年份/页码时整段省略，不留悬空标点。
  文献类型标识按 Crossref `type` 自动映射，并按 GB/T 7714-2015 分类型套模板：

  | Crossref type | 输出模板 |
  |---|---|
  | `journal-article` | `作者. 题名[J]. 刊名, 年, 卷(期): 页码. DOI: x.`（无卷时 `年(期)`） |
  | `book` / `monograph` / `edited-book` / `reference-book` | `作者. 题名[M]. 译者, trans. 2nd ed. 出版地: 出版社, 年. DOI: x.`（纯编著无作者时用编者 + `, ed`/`, eds`） |
  | `book-chapter` / `book-section` / `book-part` | `作者. 章题[M]//编者, eds. 书名. 出版地: 出版社, 年: 页码. DOI: x.` |
  | `proceedings-article` | `作者. 题名[C]//会议录名(container-title，缺则 event.name). 出版地: 出版社, 年: 页码. DOI: x.` |
  | `dissertation` | `作者. 题名[D]. 地点: 授予单位(institution，缺则 publisher), 年. DOI: x.` |
  | `report` | `作者或机构. 题名[R]. 出版地: 出版者, 年. DOI: x.` |
  | `posted-content`（预印本/工作论文） | `作者. 题名[EB/OL]. (发布日期 YYYY-MM-DD)[引用日期]. https://doi.org/x.` |
  | `dataset` | `作者. 题名[DS/OL]. 出版地: 出版者, 年[引用日期]. https://doi.org/x.` |

  译者位置采用 GB/T 7714-2015 的"题名[M]. 其他责任者, 责任方式."写法（外文用 `trans`），
  不放在作者后。引用日期 `[YYYY-MM-DD]` 取脚本运行当天；正式投稿前若重新访问过链接应更新。
  未列出的 Crossref 类型：有 `container-title` 的按期刊模板、否则按图书模板，标识用 `[Z]`，
  需人工改。中文特有类型（古籍、档案、报纸、译著、汇编析出、政府公文等）与"常见错误 12 条"
  见 `references/gbt7714-cn-types.md`；脚本只处理外文 DOI 文献，中文条目按该文件手工著录。
- **BibTeX**（LaTeX 投稿用）：经 `doi.org` 内容协商获取出版社权威记录。

实现说明：BibTeX 来自 `https://doi.org/<DOI>` 带 `Accept: application/x-bibtex`
的请求（出版社/Crossref 官方数据，非第三方转换）；GB/T 7714 由
`api.crossref.org/works/<DOI>` 的 JSON 构造。脚本自带重试与 1s 节流。

## 入库约定

作为 `cnki-paper` 子技能时，DOI 导出结果先返回父控制面，由父控制面写
`reference_materials/literature_registry.json`；不得直接维护
`source_index.md` 或 `citation_support_bank.md`。

- DOI、BibTeX 与 Crossref 元数据只把来源推进到 `metadata-exported`，默认仍是
  `citation_scope=candidate-only`；有真实 DOI 不等于读过摘要或全文。
- Reference/BibTeX、年份和 `https://doi.org/<DOI>` 作为注册表元数据保存；再由
  `cnki_acquisition.py sync` 生成两个视图。
- 只有回出版社或合法 OA 原文读取摘要／详情／全文，写出具体 support claim，完成撤稿检查与适用的可信度／页码审计后，才可改为 `content-verified/final-source`。
- Crossref 的 print/online 出版年可能差一年（如在线 2024、纸面 2025）；正文引用以拟引版本为准，并在出版社页核对。
- 若 DOI、规范 URL 或题名—首位作者—年份已存在，复用原 Source ID，只补充 DOI/export Query ID 和元数据，不新建重复来源。
