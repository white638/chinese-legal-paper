---
name: cnki-journal-index
description: Query journal indexing/inclusion status on CNKI - check which databases include a journal (北大核心, CSSCI, CSCD, SCI, EI, etc.), get impact factors and evaluation data. Use when user asks about a journal's level, indexing, or ranking.
---

# CNKI Journal Indexing Query (收录查询)

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 获取适配器使用时，先读取父技能的 `references/{{SUBSKILL_ADAPTER_FILE}}` 与 `references/acquisition-registry.md`。把收录、ISSN/CN、主办方、周期、指标、稳定 URL 和核验日期返回给父线程写入 `purpose=venue` 的 registry 记录；不要直接运行下游 gate。

> **{{HOST_DISPLAY_NAME}} 浏览器适配**：先使用 `{{BROWSER_TOOL_NAME}}` 并服从其运行时说明。正文中的浏览器动作按父技能 adapter 映射成当前宿主支持的标签页、定位器与页面求值操作。


Check which databases index a journal and extract evaluation metrics from its CNKI detail page.

## Arguments

`$ARGUMENTS` is either:
- A journal name (will search first, then navigate to detail)
- A CNKI journal detail URL (containing `navi.cnki.net/knavi/detail`)

## Steps

### 1. Navigate to the journal detail page

**If URL provided:** Navigate directly.
- Navigate the selected Chrome tab to the URL.
- Wait for visible text `["该刊被以下数据库收录"]` with timeout 15000.

**If journal name provided:** Search first.
- Navigate to `https://navi.cnki.net/knavi`
- Search for the journal (same as cnki-journal-search steps 2-4)
- Click the first matching journal title link
- List Chrome tabs and select the newly opened detail tab.
- Wait for the detail page to load

### 2. Check for captcha

Take snapshot. If "拖动下方拼图完成验证" found, notify user.

### 3. Extract journal info via JavaScript

Evaluate this function in the selected Chrome tab:

```javascript
() => {
  const body = document.body.innerText;

  // Journal title
  const titleEl = document.querySelector('h3.titbox, h3.titbox1');
  const titleText = titleEl?.innerText?.trim() || '';
  const titleParts = titleText.split('\n').map(s => s.trim()).filter(Boolean);
  const nameCN = titleParts[0] || '';
  const nameEN = titleParts[1] || '';

  // Indexing tags - extract from text between title and "基本信息"
  const tagText = body.match(/Chinese.*?\n\n([\s\S]*?)\n\n基本信息/)?.[1]
    || body.match(new RegExp(nameCN + '[\\s\\S]*?\\n\\n([\\s\\S]*?)\\n\\n基本信息'))?.[1]
    || '';
  const knownTags = ['北大核心','CSSCI','CSCD','SCI','EI','CAS','JST','WJCI','AMI','Scopus','卓越期刊','网络首发'];
  const indexedIn = knownTags.filter(tag => tagText.includes(tag) || body.includes(tag));

  // Basic info
  const sponsor = body.match(/主办单位[：:]\s*(.+?)(?=\n)/)?.[1] || '';
  const frequency = body.match(/出版周期[：:]\s*(\S+)/)?.[1] || '';
  const issn = body.match(/ISSN[：:]\s*(\S+)/)?.[1] || '';
  const cn = body.match(/CN[：:]\s*(\S+)/)?.[1] || '';

  // Publication info
  const collection = body.match(/专辑名称[：:]\s*(.+?)(?=\n)/)?.[1] || '';
  const paperCount = body.match(/出版文献量[：:]\s*(.+?)(?=\n)/)?.[1] || '';

  // Evaluation info
  const impactComposite = body.match(/复合影响因子[：:]\s*([\d.]+)/)?.[1] || '';
  const impactComprehensive = body.match(/综合影响因子[：:]\s*([\d.]+)/)?.[1] || '';

  // "该刊被以下数据库收录" section - click "更多介绍" first if needed
  const moreBtn = Array.from(document.querySelectorAll('a')).find(a => a.innerText?.includes('更多介绍'));
  const hasMoreIntro = !!moreBtn;

  return {
    nameCN,
    nameEN,
    indexedIn,
    sponsor,
    frequency,
    issn,
    cn,
    collection,
    paperCount,
    impactComposite,
    impactComprehensive,
    hasMoreIntro,
    rawTagText: tagText.substring(0, 200)
  };
}
```

### 4. Get detailed indexing info (optional)

If the extraction shows `hasMoreIntro: true`, click the "更多介绍" link to expand detailed indexing information, then take a new snapshot to capture the expanded content.

The expanded section typically lists specific database inclusions with years, such as:
- 北大核心期刊（2023年版）
- CSCD中国科学引文数据库来源期刊（2023-2024年度）
- EI 工程索引（美）

### 5. Check "统计与评价" tab (for detailed metrics)

If the user wants detailed evaluation data:
- Find and click the "统计与评价" link/tab in the snapshot
- Wait for the statistics section to load
- Extract additional metrics (H-index, citation distribution, etc.)

### 6. Present results

```
## {nameCN} ({nameEN})

**收录数据库：** {indexedIn joined by " | "}

**基本信息：**
- ISSN: {issn}
- CN: {cn}
- 主办单位: {sponsor}
- 出版周期: {frequency}
- 专辑: {collection}
- 出版文献量: {paperCount}

**评价指标：**
- 复合影响因子 (2025版): {impactComposite}
- 综合影响因子 (2025版): {impactComprehensive}

**收录情况：**
{For each tag in indexedIn: "- ✓ {tag}"}
```

## Verified Page Structure

The journal detail page (`navi.cnki.net/knavi/detail`) has:

| Data                  | Location                                    |
|-----------------------|---------------------------------------------|
| Title                 | `h3.titbox.titbox1` — first line CN, second line EN |
| Indexing tags         | Text nodes after title: "北大核心", "EI", "CSCD", etc. |
| "被以下数据库收录"    | `h4` heading, below tags                   |
| Basic info            | Text patterns: "主办单位：", "ISSN：", "CN：", "出版周期：" |
| Publication info      | Text patterns: "专辑名称：", "出版文献量：" |
| Evaluation info       | Text patterns: "复合影响因子：", "综合影响因子：" |
| Detailed indexing     | Expandable via "更多介绍" link              |
| Stats tab             | "统计与评价" tab link                       |
| Detail page opens in  | **New tab** — use list_pages + select_page  |

## Common Indexing Databases

| Tag       | Full Name                                    |
|-----------|----------------------------------------------|
| 北大核心   | 北京大学中文核心期刊                          |
| CSSCI     | 中文社会科学引文索引                          |
| CSCD      | 中国科学引文数据库                            |
| SCI       | Science Citation Index                       |
| EI        | Engineering Index                            |
| CAS       | Chemical Abstracts Service                   |
| JST       | Japan Science and Technology Agency          |
| WJCI      | World Journal Clout Index                    |
| AMI       | 中国人文社会科学期刊 AMI 综合评价             |
| Scopus    | Elsevier Scopus                              |

## 收录标签不等于文献分量

本技能返回的 `indexedIn`、影响因子与"统计与评价"数据只描述**刊物**的当前收录状态，不描述某篇文章的分量：

- 核心目录逐版更替，标签按知网当前挂载版本显示；判断一篇早年文献的刊物身份要核刊发当年的目录版本；
- 集刊／辑刊没有这些标签，但在史学、古典学、法学中常比核心刊更专业；港台刊走 THCI／TSSCI，与 CSSCI 互不重叠；
- 影响因子是刊级均值，与单篇被引无关；"网络首发"标签只说明该刊参与首发，不是质量信号；
- 知网收录本身不证明刊物正规：疑似套刊、一号多刊或非法出版物按 `cnki-paper/references/source-channels-cn.md` 第 4.3 节核 CN 号与主管主办单位。

单篇文献的分量（机构与作者、被引按年龄归一、下载≠质量、基金边界、转载信号、争鸣文、学位论文与会议论文）按 `source-channels-cn.md` 第 4.1–4.2 节判断；本技能的返回只填 `purpose=venue` 记录。
