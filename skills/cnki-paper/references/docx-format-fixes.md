# DOCX 投稿格式修复清单（OOXML 级）

中文期刊投稿稿在 Word/WPS 里反复踩的格式坑，逐条落到精确的 WordprocessingML 规则，
并标注**自动**（`scripts/docx_fixup/docx_normalize.py` 哪个开关）还是**手动/需判断**。

> 工具定位：与 `tex2docx`（从 LaTeX 从零生成）正交——本工具修复**任意已有 docx**
> （Word/WPS 另存、协作回稿、tex2docx 产物）。直接改解包后的 XML，不用 python-docx
> （它会抹掉我们关心的元素顺序与脚注细节）。

## 用法

```powershell
$DocxFix = Join-Path $AverethHome 'skills\cnki-paper\scripts\docx_fixup\docx_normalize.py'
# 默认安全集（fonts+quote-fonts+footnotes+indent+wps），输出旁加 .fixed.docx
& $Python -X utf8 $DocxFix 稿件.docx

# 全部修复（含破坏性项）
& $Python -X utf8 $DocxFix 稿件.docx 成稿.docx --all

# 只修引号字体槽；不改正文字符
& $Python -X utf8 $DocxFix 稿件.docx --quote-fonts

# 确需把直引号改为弯引号时显式开启
& $Python -X utf8 $DocxFix 稿件.docx --smart-quotes --quote-fonts

# 只校验不变量，不写文件
& $Python -X utf8 $DocxFix 稿件.docx --check

# 只合法化文件名（不碰文档）
& $Python -X utf8 $DocxFix --sanitize '题目": 草稿/v2*.docx'
```

风险分层：

| 集合 | 含 | 说明 |
|---|---|---|
| 默认集 | `fonts quote-fonts footnotes indent wps` | 不改引号字符；按语境修正 run 级字体槽 |
| 需显式开启 | `smart-quotes headings citations tables grayscale` | 字符改写或启发式操作，跑前先备份、抽查 |

`--quotes` 暂作 `--smart-quotes --quote-fonts` 的弃用兼容别名；新调用应写明两个职责。

**末尾兜底**：无论跑哪些 op，结束都会按 ECMA-376 规范顺序重排 pPr/rPr/边框/blip
（`reorder_all`），使"每步过 schema 校验"成为**构造性保证**而非事后祈祷。

---

## ⚠ 三个致命坑（已上单测，见 `test_docx_normalize.py`）

1. **同形弯引号必须按语境路由**。`“ ” ‘ ’` 位于 General Punctuation：中文引号需要
   `w:hint="eastAsia"`，英文引号和撇号需要 `w:hint="default"`。`hint` 是 run 级属性，
   所以引号必须拆成独立 run；不能再把所有弯引号统一指定为东亚字体槽。
   → `normalize_quote_fonts`，单测 `TestQuoteFontRouting`。
2. **含 `w:drawing` 的段不能 `clear_runs`**。任何"清空段落 run 再重建"的操作，遇到含
   图形/嵌入对象（`w:drawing`/`w:object`/`w:pict`）的段必须跳过，否则**直接丢图**。
   → `clear_runs` 含图时返回 `False` 拒绝执行，单测 `TestClearRunsGuard`。
3. **脚注 id 顺序必须 == 引用顺序**。`footnotes.xml` 里 `w:footnote/@w:id` 的顺序，必须
   与 `document.xml` 里 `w:footnoteReference/@w:id` 的出现顺序一致，否则**正文标 1 实际
   显示成另一条脚注内容**。→ `reorder_footnotes`，单测 `TestFootnoteOrder`。

---

## 内容类

### 1. 字体：补 `w:eastAsia`（`--fonts`，自动）
只设了西文字体（`w:ascii`/`w:hAnsi`）而没设 `w:eastAsia` 时，中文会回退到默认字体。
规则：凡 `w:rFonts` 有 latin 字体却无 `eastAsia`，补 `w:eastAsia="SimSun"`（宋体）；
docDefaults 的 rFonts 同样补。**只补不覆盖**——已显式设 KaiTi/SimHei 的不动。

### 2. 引号字符与字体槽分开处理

- `--quote-fonts` 是默认低风险动作：先按段落配对引号，显式 `w:lang` 优先；否则以被引内容中
  CJK/Latin 强字符 70% 为阈值，不能判定时再看宿主段落。中文引号设 `eastAsia`，英文引号和
  `don't`、`O’Connor`、`researchers’` 中的撇号设 `default`。无法可靠配对时保留原值并报告。
- 安全拆分只处理子元素为 `w:rPr`/`w:t` 的纯文本 run，深拷贝原样式并保留 `xml:space`。
  含 drawing/object/pict、域、instrText、tab、br、脚注引用等结构的 run 原样跳过并计数。
- 覆盖 `document.xml`、脚注、尾注、批注、全部页眉和页脚；超链接与修订容器内的安全文本 run
  在原容器中拆分，不丢链接或修订关系。
- `--smart-quotes` 只负责字符转换，默认关闭。它先识别英文撇号，对无法确认的 prime、英尺／英寸
  和未配对直引号保持原字符；转换后是否路由字体仍由 `--quote-fonts` 决定。
- tex2docx 可用 `\zhquote{...}`、`\enquote{...}` 明确指定引号语言；标题、副标题、作者、正文和
  脚注统一经过 quote-aware `runsOf()`，标题中文引号继承 SimHei，正文中文引号继承 SimSun。

### 3. 标题：去重号 + 字号层级（`--headings`，半自动）
- `（一）（一）` 重复编号 → 折叠为 `（一）`（正则 `^（(序号)）（\1）`，安全）。注意 tex2docx
  会自动给 `\subsection` 加 `（一）`，若源里标题文字**又**手写了 `（一）`，就会重号——这是
  历史成因。
- 字号层级：默认**不动**（期刊各异）。要统一传 `--heading-sizes "1=32,2=28,3=24"`
  （half-point：32=三号16pt? 实际 32 半磅=16pt；常用 二号44/小三30/四号28/小四24，按目标
  期刊《投稿须知》填）。

### 4. 引注：上标 + 合并 + 移位（`--citations`，破坏性）
- **上标**：把 `[n]`/`[n-m,k]` 拆成独立 run 并设 `w:vertAlign w:val="superscript"`，前后
  文本保留（拆 run）。含图段跳过（致命坑 2）。
- **合并连续**：`[8][9]→[8-9]`，`[8][9][10][12]→[8-10,12]`（连续段用 `-`，跳号用 `,`，
  GB/T 7714 规范）。
- **上标与标点的先后（按目标刊二选一，不是通行规则）**：GB/T 7714-2015 只规定顺序编码制
  用方括号阿拉伯数字上标，**不规定上标在标点之前还是之后**。实际存在两种惯例：
  - ① **标点前**（顺序编码制刊最常见）：上标紧跟被引内容之后，`……如既有研究所示[5]。`；
    引一个词或短语时尤其如此，`"制度韧性"[5]一词……`；
  - ② **句末标点后**（部分刊，多见于页下注刊的注码，也有少数顺序编码制刊）：`……如既有研究所示。[5]`。
  本工具 `--citations` 的移位动作实现的是 ②（`结论[5]。 → 结论。[5]`）。**跑之前先打开目标刊
  最近一期范文看引注落点**：范文是 ① 就**不要**跑移位（只做上标+合并）；范文是 ② 才执行；
  同一篇稿内只能用一种。体例判据与两种惯例的完整说明见 `cn-journal-conventions.md` 第 9 节。
- ⚠ 局限：只处理**单个 `w:t` 内**的引注；跨 run 拆分的引注需手动。跑前务必抽查。

### 5. 注释/脚注重排（`--footnotes`，自动）
序号与出现顺序不符 → 按引用顺序重编号；脚注按致命坑 3 的规则同步处理。CNKI/WPS 反复
另存后脚注 id 错乱是高发问题。

---

## 结构/排版类

### 7. 三线表（`--tables`，破坏性）
把表格规整为三线表，逐项删除：
- `w:tblStyle`（表样式引用）、`w:tblPr` 下的 `w:shd`（表底纹）；
- 行级 `w:tblPrEx`（覆盖表属性、常带边框/底纹残留）；
- 单元格 `w:tcPr` 下的 `w:shd`、`w:tcBorders`（内框）。

保留：表级 `w:tblBorders` 只留 **top + bottom**（粗 1.5pt，`sz=12`）；**表头行**（第一行）
单元格加 **bottom** 细线（`sz=8`）。

**边框子元素顺序必须 `top/left/bottom/right`**（CT_Borders schema 约束）——由 `reorder_children(_, BORDER_ORDER)` 保证，单测 `TestOrdering.test_border_order`。

> ⚠ 该 op 把**所有**表格都三线表化。若稿中有需保留网格的表（如问卷矩阵），先排除或跑后手改。

### 8. 图（`--grayscale`，部分自动）
- **彩图改黑白**：给每个 `a:blip` 插 `<a:grayscl/>`（渲染期转灰度，**不动图像字节、可逆**）。
  比 Pillow 重新编码更安全。
- **`lineRule="exact"` 把内联图裁成一条线**：含 `w:drawing` 的段若 `w:spacing/@w:lineRule="exact"`，
  改为 `auto`（`fix_drawing_line_spacing`，随 `--grayscale` 一起）。
- **图内文字压图**：检测靠版面判断，**手动**——通常是文本框 anchored 浮于图上，应改为嵌入式
  或调 z-order。
- **替换图要更新 extent**：换图后必须同步 `wp:extent`(@cx,@cy) 与 `pic:spPr/a:ext`，否则按旧尺寸
  拉伸变形。涉及新图实际像素，属**手动/逐图**操作（公式：EMU = px / dpi × 914400）。

### 8.1 表图真实渲染验收（手动/必做）

OOXML 可解析、`word_guard` 通过和媒体文件真实嵌入，都不能说明版面已经可投稿。含图表的终稿须用
Word、WPS 或目标交付格式真实渲染后逐张检查：

- 表题是否与表格同页，跨页表是否重复表头，单行是否被拆开，资料来源/表注是否孤悬到下一页；
- 列宽是否按信息量分配，是否因等宽列导致长文本逐字换行；表中长解释能否移到正文或短注；
- 图题与来源位置是否符合目标刊，图中文字在100%缩放和黑白打印下是否仍可读；
- 图是否被固定行距裁切，箭头、框线和灰度是否仍能表达原关系；
- 图表是否重复正文或彼此重复；不能增加分析清晰度的图表应删除。

检查结果写入 `figure_asset_map.md`。`docx_normalize --check` 只证明结构不变量，不能替代本轮视觉验收。

### 8.2 批注驱动的回写与重建（手动/必做）

PDF 或 Word 批注指向的是读者在某一版面位置遇到的问题，不授权直接修改生成物。每条批注须先定位到可编辑源稿中的段落、表格单元格、图注或元数据，再按以下闭环处理：

1. 登记批注页、选中文本、真实问题和修改类别；逻辑、证据或概念问题先改论证，不能只换词或调版式。
2. 回写唯一可编辑源稿，并同步修改摘要、目录、交叉引用、重复出现的表述和其他交付格式的同一信息。
3. 重新生成 Word 与 PDF，不在旧 PDF 上覆盖文字或打补丁。
4. 真实渲染检查批注页；若改动引起分页、表格跨页、脚注或图注移动，继续检查所有受影响的下游页，直至版面重新稳定。
5. 复跑适用的内容审计、`word_guard.py`、OOXML 不变量检查和 output gate，刷新 audit/output receipt 与最终文件哈希。源稿改变而凭证仍沿用旧指纹，视为未完成。

批注若指出“表格中否定词过密”，先按学术文笔协议判断每个否定是否承重；版面验收只检查改写后单元格是否可读，不用删除“不”字数量冒充内容修复。批注若指出逻辑跳跃，必须在源稿中补比较、担保和推断边界，不能靠脚注或表注遮盖。

### 9. 段落首行缩进（`--indent`，自动）
- 用 `w:ind/@w:firstLineChars="200"`（按字数，2 字）而非 `@w:firstLine`（twips）——换设备/
  字号不走样。工具把现有 `firstLine` 换成 `firstLineChars`；`--indent-missing` 给无缩进正文段
  补 2 字（不动标题/列表/含图段）。
- **`w:ind` 必须排在 `w:jc` 之前**（CT_PPr schema 顺序）——由 `reorder_children(_, PPR_ORDER)`
  保证，单测 `TestOrdering.test_ind_before_jc`。

---

## 工程类

### 10. 脚注无 API，直改 XML（同 #5）
docx 无脚注高层 API，必须直接编辑 `word/footnotes.xml` + `word/document.xml` 里的
`w:footnoteReference`。**id 顺序 == 引用顺序**（致命坑 3）。separator/continuationSeparator
（id 通常 -1、0）**绝不重编号**；内容脚注从 `max(special)+1` 起编。

### 11. 打包：WPS 另存扰动 styles.xml（`--wps` + 按需解析，部分自动）
- WPS 重新保存会改写 `styles.xml`（丢 docDefaults 的 eastAsia 等）。工具的对策：**只回写真正
  改动过的部件**——footnotes-only 跑完 `styles.xml` 字节不变（已验证）；`--fonts` 会补回
  docDefaults 的 eastAsia。
- 深度 WPS 修复（命名空间污染、样式表重排）超出本工具范围，需手动比对原始 `styles.xml`。
- **每步过 schema 校验**：`--check` 跑不变量校验（pPr/rPr/边框顺序、脚注 id 顺序、XML 可解析）。
  注意这是**不变量校验**，非完整 ECMA-376 XSD 校验（未内置 .xsd）；内容级校验另见
统一入口 `scripts/avereth_core/tools/word_guard.py`。

### 12. 文件名（`--sanitize`，自动）
- Windows 非法字符 `" / : * ? < > | \` → 对应**全角** `＂／：＊？＜＞｜＼`。
- **CJK NFC 规范化**：`unicodedata.normalize("NFC", name)`——避免 macOS 传来的 NFD（分解式）
  文件名在 Windows 显示/匹配异常。
- 去首尾空白与**尾部点号**（Windows 不允许）。输出路径的文件名部分自动过此处理。

### 12.1 投稿副本与作者元数据（手动/必做）

论坛或期刊要求另交摘要、全文、Word/PDF 双格式时，先从官方征稿原文提取并冻结作者姓名、单位、分论坛、文类、命名分隔符、字数和格式要求，再从用户指定的简历或权威个人材料填写身份；不得由正文署名、旧稿或记忆猜测。最终检查：

- 摘要文件和全文文件内的题名、作者、单位与邮件正文一致；摘要正文满足目标刊／论坛体例，关键词数量与格式符合要求；
- 同一文类的 Word/PDF 使用完全相同的文件名主干，文件名按官方顺序排列字段，不擅自替换破折号、空格或单位简称；
- PDF 由最终 Word/源稿重建，二者题名、作者、单位、摘要、正文和参考文献一致；投稿副本不残留内部日志、批注、修订痕迹、隐藏文字或旧属性；
- 交付清单记录最终路径、页数／字数、SHA-256 和生成时间，邮件只引用该清单中的最终文件。

---

## 与校验链的关系
- 本工具 `--check`：OOXML **结构不变量**（顺序/脚注/可解析）。
- Pandoc 正式 Word 输出：生成 DOCX 后、包校验和预览前自动执行 `quote-fonts`；原始 DOCX 的
  lossless-copy 路径不自动改写用户模板。
- `scripts/avereth_core/tools/word_guard.py`：除字数、结构和引用外，逐 run 检查中文／英文引号、
  撇号、未拆 run 和歧义配对；错误码为 `WORD.QUOTE_FONT_MISMATCH`、
  `WORD.APOSTROPHE_FONT_MISMATCH`、`WORD.QUOTE_RUN_NOT_SPLIT`，歧义作为
  `WORD.QUOTE_LOCALE_AMBIGUOUS` 警告。目标刊模板模式仍可传 `--font-policy template`。
- 链路：生成 DOCX → `quote-fonts` → OOXML 不变量检查 → Word/WPS 预览 → `word_guard.py` → 逐页验收。
