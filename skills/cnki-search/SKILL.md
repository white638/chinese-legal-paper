---
name: cnki-search
description: Search CNKI (中国知网) for papers by keyword. Use when the user wants to find academic papers on a topic.
---

# CNKI Basic Search

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 获取适配器使用时，先读取父技能的 `references/{{SUBSKILL_ADAPTER_FILE}}` 与 `references/acquisition-registry.md`。返回结构化查询和结果数据，由父线程写入 `literature_registry.json` 并生成 `source_index.md`；不要直接手改 source index、晋级 `final-source` 或运行下游 gate。若正文冲突，以父技能契约为准。

> **{{HOST_DISPLAY_NAME}} 浏览器适配**：先使用 `{{BROWSER_TOOL_NAME}}` 并服从其运行时说明。正文中的浏览器动作按父技能 adapter 映射成当前宿主支持的标签页、定位器与页面求值操作。


## 检索前先读 `references/search-strategy.md`

本技能只负责把检索式送进知网并把结果页读回来。用哪个字段、开不开核心刊过滤、按什么排序、何时滚雪球、何时可以说"搜完了"，全部以 `references/search-strategy.md` 为准。三条最关键的提醒：

1. **一个检索式不是一次检索**：每个核心概念至少走同义近义、学科变体、古今用语、译名拼音四路扩展，各建 Query ID；只跑一个主题词就估规模或宣布"研究稀少"不成立。
2. **核心刊过滤开与关各跑一次**：CSSCI／北大核心过滤只作用于期刊库，史学专刊、集刊、学位论文、会议、港台文献会被系统性漏掉；只跑开过滤的组不能用于声称覆盖或饱和。
3. **相关度首页不是分量**：至少看相关度、被引、时间三个视图各一屏，被引按年龄归一后再判分量；检索式、字段、过滤、排序、页码、结果数、日期、稳定 URL 全部写入 registry query，零结果要记排查结论。

Search CNKI for papers using keyword(s). Returns result count and structured result list (titles, URLs, authors, journal, date) in a single call.

## Arguments

$ARGUMENTS contains the search keyword(s) in Chinese or English.

## Steps

### 1. Navigate

Use Chrome browser navigation → `https://kns.cnki.net/kns8s/search`

### 2. Search + extract results (single evaluate_script, NO wait_for)

Replace `YOUR_KEYWORDS` with actual search terms:

```javascript
async () => {
  const query = "YOUR_KEYWORDS";

  // Wait for search input (replaces wait_for)
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.querySelector('input.search-input')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Check captcha (only if visible on screen, not hidden SDK at top:-1000000)
  const outer = document.querySelector('#tcaptcha_transform_dy');
  if (outer && outer.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  // Fill and submit (verified selectors: input.search-input, input.search-btn)
  const input = document.querySelector('input.search-input');
  input.value = query;
  input.dispatchEvent(new Event('input', { bubbles: true }));
  document.querySelector('input.search-btn')?.click();

  // Wait for results
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.body.innerText.includes('条结果')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Check captcha again
  const outer2 = document.querySelector('#tcaptcha_transform_dy');
  if (outer2 && outer2.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  // Extract current page results (merged parse-results)
  const rows = document.querySelectorAll('.result-table-list tbody tr');
  const checkboxes = document.querySelectorAll('.result-table-list tbody input.cbItem');
  const results = Array.from(rows).map((row, i) => {
    const titleLink = row.querySelector('td.name a.fz14');
    const authors = Array.from(row.querySelectorAll('td.author a.KnowledgeNetLink') || []).map(a => a.innerText?.trim());
    const journal = row.querySelector('td.source a')?.innerText?.trim() || '';
    const date = row.querySelector('td.date')?.innerText?.trim() || '';
    const citations = row.querySelector('td.quote')?.innerText?.trim() || '';
    const downloads = row.querySelector('td.download')?.innerText?.trim() || '';
    return {
      n: i + 1,
      title: titleLink?.innerText?.trim() || '',
      href: titleLink?.href || '',
      exportId: checkboxes[i]?.value || '',
      authors: authors.join('; '),
      journal,
      date,
      citations,
      downloads
    };
  });

  return {
    query,
    total: document.querySelector('.pagerTitleCell')?.innerText?.match(/([\d,]+)/)?.[1] || '0',
    page: document.querySelector('.countPageMark')?.innerText || '1/1',
    results
  };
}
```

### 3. Report

Present results as a numbered list:

```
Searched CNKI for "$ARGUMENTS": found {total} results (page {page}).

1. {title}
   Authors: {authors} | Journal: {journal} | Date: {date}
   Citations: {citations} | Downloads: {downloads}

2. ...
```

### 4. Follow-up: navigate to a paper

When the user wants to open or download a specific paper, use `navigate_page` with the result's `href` URL directly — do NOT click the link (clicking opens a new tab and wastes 3 extra tool calls for tab management).

## Captcha detection

Check `#tcaptcha_transform_dy` element's `getBoundingClientRect().top >= 0`.
Tencent captcha SDK preloads DOM at `top: -1000000px` (off-screen, not active).
Only return `error: 'captcha'` when `top >= 0` (actually visible to user).

## Verified selectors

| Element | Selector | Notes |
|---------|----------|-------|
| Search input | `input.search-input` | id=`txt_search`, placeholder "中文文献、外文文献" |
| Search button | `input.search-btn` | type="button" |
| Result count | `.pagerTitleCell` | text "共找到 X 条结果" |
| Page indicator | `.countPageMark` | text "1/300" |
| Result rows | `.result-table-list tbody tr` | Each row = one paper |
| Title link | `td.name a.fz14` | Paper title with href |
| Authors | `td.author a.KnowledgeNetLink` | Author name links |
| Journal | `td.source a` | Journal/source link |
| Date | `td.date` | Publication date text |
| Citations | `td.quote` | Citation count |
| Downloads | `td.download` | Download count |

## Batch export to Zotero

When user wants to save results to Zotero, use batch export directly from the results page — **do NOT navigate to each detail page**. The `exportId` in results equals the detail page's `#export-id`. Call `cnki-export` skill with batch mode (Step 1B). See cnki-export SKILL.md for details.

## Tool calls: 2 (navigate + evaluate_script)
