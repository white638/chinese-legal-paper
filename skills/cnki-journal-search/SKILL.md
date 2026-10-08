---
name: cnki-journal-search
description: Search for journals/publications on CNKI by name, ISSN, CN, or sponsor. Use when the user wants to find a specific journal or browse publications.
---

# CNKI Journal Search (期刊检索)

## {{HOST_DISPLAY_NAME}} 集成

当本技能作为 `cnki-paper` 获取适配器使用时，先读取父技能的 `references/{{SUBSKILL_ADAPTER_FILE}}` 与 `references/acquisition-registry.md`。把期刊检索写成 `purpose=venue` 的 registry query，并返回稳定期刊页数据；不要直接手改 source index 或运行下游 gate。若正文冲突，以父技能契约为准。

> **{{HOST_DISPLAY_NAME}} 浏览器适配**：先使用 `{{BROWSER_TOOL_NAME}}` 并服从其运行时说明。正文中的浏览器动作按父技能 adapter 映射成当前宿主支持的标签页、定位器与页面求值操作。


## Arguments

`$ARGUMENTS` is a journal name, ISSN, CN number, or sponsor name.

## Steps

### 1. Navigate

Use Chrome browser navigation → `https://navi.cnki.net/knavi`

### 2. Search + extract results (single evaluate_script, NO wait_for)

Evaluate the following script in the selected Chrome tab. Replace `QUERY_HERE` with the actual search term:

```javascript
async () => {
  const query = "QUERY_HERE";

  // Wait for page load
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.querySelector('input.researchbtn')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Check captcha (visible on screen, not hidden SDK at top:-1000000)
  const outer = document.querySelector('#tcaptcha_transform_dy');
  if (outer && outer.getBoundingClientRect().top >= 0) return { error: 'captcha' };

  // Auto-detect search type and fill
  const select = document.querySelector('select');
  if (select) {
    if (/^\d{4}-\d{3}[\dXx]$/.test(query)) select.value = 'ISSN';
    else if (/^\d{2}-\d{4}/.test(query)) select.value = 'CN';
    select.dispatchEvent(new Event('change', { bubbles: true }));
  }

  const input = document.querySelector('input[placeholder*="检索词"]');
  if (input) input.value = query;

  // Click search button (verified selector: input.researchbtn)
  document.querySelector('input.researchbtn')?.click();

  // Wait for results
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.body.innerText.includes('条结果')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });

  // Click 期刊 tab to filter journals only
  const tabs = document.querySelectorAll('li a');
  for (const a of tabs) { if (a.innerText.trim() === '期刊') { a.click(); break; } }
  await new Promise(r => setTimeout(r, 1500));

  // Extract journal results
  const body = document.body.innerText;
  const countMatch = body.match(/共\s*(\d+)\s*条结果/) || body.match(/找到\s*(\d+)\s*条结果/);
  const count = countMatch ? parseInt(countMatch[1]) : 0;

  const results = [];
  const titleLinks = document.querySelectorAll('a[href*="knavi/detail"]');
  titleLinks.forEach(link => {
    const text = link.innerText?.trim();
    if (!text || text.length < 2) return;
    const parent = link.closest('li, .list-item') || link.parentElement?.parentElement;
    const pt = parent?.innerText || '';
    results.push({
      name: text.split('\n')[0]?.trim(),
      url: link.href,
      issn: pt.match(/ISSN[：:]\s*(\S+)/)?.[1] || '',
      cn: pt.match(/CN[：:]\s*(\S+)/)?.[1] || '',
      cif: pt.match(/复合影响因子[：:]\s*([\d.]+)/)?.[1] || '',
      aif: pt.match(/综合影响因子[：:]\s*([\d.]+)/)?.[1] || '',
      citations: pt.match(/被引次数[：:]\s*([\d,]+)/)?.[1] || '',
      downloads: pt.match(/下载次数[：:]\s*([\d,]+)/)?.[1] || '',
      sponsor: pt.match(/主办单位[：:]\s*(.+?)(?=\n|ISSN)/)?.[1]?.trim() || ''
    });
  });

  return { query, count, results };
}
```

### 3. Present results

```
期刊检索 "$ARGUMENTS"（共 {count} 条）：

1. {name}
   ISSN: {issn} | CN: {cn}
   复合影响因子: {cif} | 综合影响因子: {aif}
   被引: {citations} | 下载: {downloads}
```

## Notes

- Journal detail pages open in **new tab** — use `list_pages` + `select_page`
- If only 1 journal result, can auto-navigate to detail page for `cnki-journal-index`
- Search button selector: `input.researchbtn` (not generic `button`)

## Captcha detection

Check `#tcaptcha_transform_dy` element's `getBoundingClientRect().top >= 0`.
Tencent captcha SDK preloads DOM at `top: -1000000px` (off-screen, not active).
Only return `error: 'captcha'` when `top >= 0` (actually visible to user).

## Tool calls: 2 (navigate + evaluate_script)
