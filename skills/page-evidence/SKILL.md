---
name: page-evidence
description: 引文页码溯源与核证：把稿件中每一处"第X页"式引注落实为分级证据（A 页面影像核证 / B 本地原版式 PDF 定位 / C 知网三角旁证），覆盖理论库、读秀、全国图书馆参考咨询联盟、籍合网、Google Books、Internet Archive、HathiTrust 等渠道，并用脚本审计成稿。Use when 用户要求页码精确、页码溯源、核对引用页码、原典专著页码核证、引文出处定位，或要处理稿末【VERIFY】清单。
---

# Page-Evidence：引文页码溯源与核证

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 工作流子技能使用时，先读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}`，按其中与本技能同名或同类的规则记录产物，并遵守 `cnki-paper` 控制器 `avereth.py gate --stage <stage>` 的阶段门槛。若本技能正文与该适配契约冲突，以适配契约和父技能 gate 为准。

页码精确的前提是**版本锁定**：先把引用条目钉死到唯一版本（出版社 + 出版年 +
版次，能记 ISBN 就记），证据必须来自同一版本，否则宁可降级为章节级引用。
本技能给每一处页码引注配一条可机检的证据记录，并在成稿时审计闭环。

## 证据分级模型

| Tier | 含义 | 取得方式 | 效力 |
|---|---|---|---|
| A | 页面影像核证 | 在与纸书逐页一致的数据库里检索到该页影像并截图存证（渠道见 references/page-sources.md） | 解除【VERIFY】 |
| B | 本地原版式 PDF 核证 | 完整引文与原始文字一致，来源、版本、工件哈希及定位符均通过检查 | 解除【VERIFY】 |
| C | 知网三角旁证 | ≥2 篇互相独立的论文以同一版本同一页码引用同段文字 | 仅提升置信度，**不解除【VERIFY】** |
| （空） | 未核证 | — | 必须带【VERIFY】并列入稿末清单 |

证据登记在 `paper_rewriting_output/evidence_bank.md` 的 `## Page Evidence`
小节（独立小节，不动上游 Evidence Bank 原表），表结构是本技能的权威规范：

| Evidence ID | Work (Edition-locked) | Locator | Quote Snippet | Tier | Evidence Source | Evidence File | Status | Source ID | Source Record SHA256 | Artifact SHA256 | Locator Kind | PDF Pages | Page Basis | Raw Span |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

- **Evidence ID**：`PE-01` 起编。
- **Work**：著作 + 版本锁定串（如 `马克思恩格斯文集(第5卷). 人民出版社, 2009`）。
- **Locator**：`第610页` / `pp. 12-15` / 规范定位符（`AA 5:23`、`《论语·学而》`）。
- **Quote Snippet**：完整待引用文字，与稿件中的直接引文一致；缩短的检索片段不能替代完整引文核验。
- **Evidence Source**：A 级写渠道 URL；B 级写 `文件名#p<PDF页>(版面<出版页>)`；
  C 级写两篇旁证论文的知网 URL。
- **Evidence File**：A 级截图的相对路径（存 `paper_rewriting_output/evidence/`，
  命名 `PE-01_<渠道>_p<页码>.png`）；B 级为注册来源 PDF 的工作区相对路径；C 级可空。
- **Status**：`verified` 或 `VERIFY`。
- **Source ID**：复用 `reference_materials/literature_registry.json` 的来源标识。引用键可通过现有 `citation_key` / `zotero_link.citation_key` 唯一解析；不新增身份登记表。
- **Source Record SHA256**：对该来源记录使用 UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")` 序列化后计算 SHA-256。`evidence_contract.source_digest()` 提供同一计算。版本、权限或来源登记发生变化后需要重新核证。
- **Artifact SHA256**：Evidence File 的实际字节 SHA-256。A 级绑定截图，B 级绑定注册 PDF。
- **Locator Kind**：`publication` 或 `pdf`。PDF 页序明确写 `PDF 第N页`；不能代替出版页码。
- **PDF Pages**：B 级的实际 PDF 页序（从 1 开始，如 `2-3`）。
- **Page Basis**：出版页码映射的观察依据。B 级写 `labels: <原页核对依据>` 或 `start-page=23: <元数据及原页依据>`；PDF 页序写 `pdf-index`。A 级记录人工看到的版本和页码依据。
- **Raw Span**：B 级完整引文在该次原始文本提取中的字符区间 `start:end`，从 0 开始、右端不含。用于消歧，提取结果变化后重新定位。

来源登记必须保留题名、出版年和可用的出版社、版次、ISBN；Work 与这些字段一致。稿件可通过既有 Source ID、引用键或 Evidence ID 绑定；旧式著录须唯一对应登记中的题名及版本，页码和相似文本不能独立授权匹配。

旧八列表仍可读取。缺少当前身份、工件或定位绑定的历史 `verified` 保持待核证；保留历史材料和凭证，只在新核验通过后使用当前结果。

### 特殊定位符

Locator 列遇到下列载体时按此书写，规范与著录示例见
`cnki-paper/references/primary-source-citation.md` 第 5 节：

- **影印本双页码**：写影印新页码并标上／下栏（`第7册第123页下`），需要跨版本
  定位时括注原书叶码（`原书卷三叶十二上`）；A 级截图须含册次与新页码角标。
- **古籍卷叶面**：无排印页码的刻本、稿抄本写 `卷X叶Y上/下`（或 `Ya/Yb`），跨叶
  写起止叶面；证据为叶面影像。
- **档案件号**：一史馆写全宗名＋档号（`宫中朱批奏折 04-01-××-××××-×××`），台北
  故宫写文献编号，二史馆写全宗号＋案卷号，件内多页再加页；档号即定位符，URL
  不能替代。
- **电子古籍库文本**：籍合网整理本页码与纸书一致可直接产 A 级；其他库的文字层只
  作检索线索，Locator 写纸本页码或卷／篇／条目并回纸本或影像核对，未核对保持
  【VERIFY】。
- **无固定页码电子书**：流式版一律不作页码来源；写章节或规范定位符并降级为
  章节级引用，或改用同版本纸书页码。

## 路径一：期刊论文 / 本地 PDF（产 B 级）

知网期刊 PDF 是原版式，页脚印刷页码即出版页码，且检索元数据自带起止页。

```bash
# 单条引文：--start-page 填该文的起始出版页码（来自知网元数据）
PYTHONIOENCODING=utf-8 python scripts/pdf_locate.py paper_rewriting_output/materials/X.pdf \
  --quote "完整待引用文字" --start-page 23 --page-basis "出版社元数据及首页页脚" \
  --registry paper_rewriting_output/reference_materials/literature_registry.json \
  --source-id SRC-001 --work "题名、出版社、出版年及版次" --markdown

# 批量：一行一条引文（或 JSON 数组）
PYTHONIOENCODING=utf-8 python scripts/pdf_locate.py materials/cnki_pdfs/ \
  --quotes-file quotes.txt --markdown
```

- 宽松检索返回所有候选及原始文字、上下文、PDF 页序、页标签、字符区间和忠实度诊断。严格比较仅接受已定义的全半角和空白差异，保留符号、大小写、数字、单位、上下标及否定。跨页时跳过页眉页脚得到的候选仍需核对完整引文。
- 多处命中保持歧义；查看 JSON 候选后可用单条引文的 `--select-hit N` 明确选择。空、纯标点和少于八个归一化字符的输入安全返回，不产生通过信号。
- 页标签是 PDF 元数据。只有记录了原页核对依据后才能作为出版页码映射；否则使用明确的 PDF 页序。非数字规范定位符继续由原典来源核验负责，本脚本的数值页码审计不声称覆盖全部规范定位符。
- 表行的 Status 始终是 `VERIFY`。完整引文、来源版本、原文语境及页码依据核对后才登记 `verified`；审计再次核对实际工件和完整文字。定位成功或退出码 0 本身不授予核证。
- 双栏乱序、图像中的公式和仅靠字形位置表达的上下标，需要回原页核对。提取的字符文本一致不能代替图像核证，也不能证明转述或推断受到支持。
- 依赖 PyMuPDF：`pip install pymupdf`。

## 路径二：原典专著（产 A 级）

按 references/page-sources.md 的渠道决策树走（概要：理论库 → 读秀/超星 →
全国图书馆参考咨询联盟 → 籍合网 → Google Books / Internet Archive /
HathiTrust → 馆藏出版社电子书平台）。在 {{HOST_DISPLAY_NAME}} 中先调用 `{{BROWSER_TOOL_NAME}}`
并按其运行时文档自动化：站内检索引文 → 命中页影像 → 截图保存到
`paper_rewriting_output/evidence/` → 登记 A 级行。

**规范定位符优先**：柏拉图用 Stephanus 页码、亚里士多德用 Bekker 码、康德用
科学院版 AA 卷:页、先秦典籍用篇章号、二十四史用"卷 + 中华书局点校本页码"、
马恩中文引用用《马克思恩格斯文集》(2009) 卷+页。规范定位符版本无关、任何
版本均可核对——Locator 写定位符，所选版本页码作附注，对照表见
references/page-sources.md。

## 路径三：知网三角旁证（产 C 级）

原典暂时拿不到 A 级证据时：在知网高级检索切**全文**字段检索引文片段
（操作见 `cnki-advanced-search`），找 ≥2 篇互相独立（不同作者、不同机构）
的论文以同一版本同一页码引用同段文字，把两篇的知网 URL 写入 Evidence
Source，Tier 记 `C`，Status 保持 `VERIFY`。

## 成稿审计（质量闭环步骤）

```bash
PYTHONIOENCODING=utf-8 python scripts/page_evidence_audit.py paper_rewriting_output --markdown --write
```

控制器显式传入选定的规范稿并保存报告；独立使用时通过 `--manuscript` 指定 Markdown、TeX 或 DOCX。DOCX 包含脚注和尾注。识别三类数值页码引注（`第X页`、GB/T 7714 冒号页码如
`2009: 610`、`p./pp.`），逐条对照 `## Page Evidence` 表：

- 唯一来源及版本对应、覆盖引注范围、状态严格等于 `verified`，且 A/B 工件与各项绑定核验通过 → PASS；
- 命中 C 级 → TRIANGULATED（仍留【VERIFY】）；
- 无证据行 → NO-EVIDENCE（【VERIFY】）。

`--write` 落盘 `page_evidence_audit.md`，其【VERIFY】小节就是交给用户的稿末
待办清单。默认仅结构性错误返回非零；`--strict` 时任何非 A/B 引注都判失败。
没有适用的数值页码引注时明确返回 `NOT_APPLICABLE`。存在适用引注但缺少证据表时失败。A 级仍依赖真实的人工影像核对，脚本验证其来源和保存工件，不从哈希推断影像内容。

## 铁律

1. **版本锁定先于页码**：没锁版本的页码无意义，审计一律 VERIFY。
2. **流式电子书禁止作页码来源**：微信读书、得到、Kindle 流式版等无可靠纸书
   页码映射。
3. **C 级只是旁证**：二手引用再多也不等于核对过原书。
4. **截图必须落盘**：A 级证据口说无凭，无 Evidence File 的 A 级行按未核证处理。
5. Windows GBK 控制台跑脚本前置 `PYTHONIOENCODING=utf-8`（同套件其他校验脚本）。
