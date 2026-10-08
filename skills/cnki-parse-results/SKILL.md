---
name: cnki-parse-results
description: Parse current CNKI search results page into structured paper data (title, authors, journal, date, citations). Use after a search has been performed and you need to extract the results.
---

# CNKI Parse Search Results

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 获取适配器使用时，先读取父技能的 `references/{{SUBSKILL_ADAPTER_FILE}}` 与 `references/acquisition-registry.md`。结果页条目只返回为 `discovered/candidate-only`，由父线程写入 `literature_registry.json`；不要直接手改 source index、晋级 `final-source` 或运行下游 gate。若正文冲突，以父技能契约为准。

> **{{HOST_DISPLAY_NAME}} 浏览器适配**：先使用 `{{BROWSER_TOOL_NAME}}` 并服从其运行时说明。正文中的浏览器动作按父技能 adapter 映射成当前宿主支持的标签页、定位器与页面求值操作。


Extract structured paper data from the current CNKI search results page.

## Prerequisites

The current Chrome page must be a CNKI search results page (URL contains `kns.cnki.net` and page shows "条结果").

## Steps

### 1. Verify we are on a results page

Take a fresh page/accessibility snapshot. Verify the page contains "条结果". If not, inform the user that no search results page is currently open.

Check for captcha ("拖动下方拼图完成验证") - if found, notify user to solve it manually.

### 2. Extract results via JavaScript

Evaluate this function in the selected Chrome tab:

```javascript
() => {
  const rows = document.querySelectorAll('.result-table-list tbody tr');
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const results = Array.from(rows).map((row, index) => {
    const nameCell = row.querySelector('td.name');
    const titleLink = nameCell?.querySelector('a.fz14');
    const authorCell = row.querySelector('td.author');
    const sourceCell = row.querySelector('td.source');
    const dateCell = row.querySelector('td.date');
    const dataCell = row.querySelector('td.data');
    const quoteCell = row.querySelector('td.quote');
    const downloadCell = row.querySelector('td.download');
    const isOnlineFirst = !!nameCell?.querySelector('.marktip');

    return {
      number: index + 1,
      title: titleLink?.innerText?.trim() || '',
      url: titleLink?.href || '',
      exportId: checkboxes[index]?.value || '',
      authors: Array.from(authorCell?.querySelectorAll('a.KnowledgeNetLink') || []).map(a => a.innerText?.trim()),
      journal: sourceCell?.querySelector('a')?.innerText?.trim() || '',
      date: dateCell?.innerText?.trim() || '',
      database: dataCell?.innerText?.trim() || '',
      citations: quoteCell?.innerText?.trim() || '',
      downloads: downloadCell?.innerText?.trim() || '',
      isOnlineFirst: isOnlineFirst
    };
  });

  const totalText = document.querySelector('.pagerTitleCell')?.innerText || '';
  const totalMatch = totalText.match(/([\d,]+)/);
  const pageInfo = document.querySelector('.countPageMark')?.innerText || '';

  return {
    papers: results,
    totalCount: totalMatch ? totalMatch[1] : 'unknown',
    pageInfo: pageInfo
  };
}
```

### 3. Present results

Format as a numbered list:

```
CNKI search results ({totalCount} total, page {pageInfo}):

1. {title} {isOnlineFirst ? "[网络首发]" : ""}
   Authors: {authors joined by "; "}
   Journal: {journal} | Date: {date} | Type: {database}
   Citations: {citations} | Downloads: {downloads}
   URL: {url}

2. ...
```

`isOnlineFirst=true`（网络首发）的条目没有终稿卷、期、页码，`date` 是首发日期而非刊出日期。登记 registry 时在 `metadata` 记 `online_first=true` 与首发日期／DOI，引用按电子期刊格式；正式刊出后必须回详情页回改卷期页，并复核正文中的页码引注与引文文字（首发版与正式版页码不同）。规则见 `cnki-paper/references/source-channels-cn.md` 第 4.4 节。

### 4. Fallback: snapshot-based parsing

If JavaScript returns empty (DOM structure changed), take a fresh page/accessibility snapshot and parse the accessibility tree manually:

Look for the repeating pattern:
- `checkbox` → `StaticText` (number) → `link` with URL containing `kcms2/article/abstract` (title) → `link`s with URL containing `kcms2/author/detail` (authors) → `link` with URL containing `navi.cnki.net/knavi/detail` (journal) → `StaticText` (date) → `StaticText` (database type)

## Verified DOM Selectors (CNKI uses jQuery, stable semantic class names)

| Data       | Selector                         | Notes                      |
|------------|----------------------------------|----------------------------|
| Table      | `.result-table-list tbody tr`    | Each row = one paper       |
| Checkbox   | `input.cbItem`                   | value = export encrypted ID |
| Number     | `td.seq`                         | Row sequence number        |
| Title      | `td.name a.fz14`                 | Paper title link           |
| Authors    | `td.author a.KnowledgeNetLink`   | Author name links          |
| Journal    | `td.source a`                    | Journal/source link        |
| Date       | `td.date`                        | Publication date text      |
| DB Type    | `td.data`                        | Database type (期刊/学位论文) |
| Citations  | `td.quote`                       | Citation count             |
| Downloads  | `td.download`                    | Download count             |
| Online 1st | `td.name .marktip`               | "网络首发" label            |
| Total      | `.pagerTitleCell`                 | "共找到 X 条结果"           |
| Page       | `.countPageMark`                  | "1/300" format             |
