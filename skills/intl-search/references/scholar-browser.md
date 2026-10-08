# Google Scholar 受控发现协议

## 1. 权限与定位

OpenAlex 与 Google Scholar 并列承担外文发现、命题撞车和 DOI 恢复；Semantic Scholar 只补独有字段。Scholar 的题名、作者／刊物／年份行、外链、片段、被引数和 BibTeX 都是筛选线索，不是内容核验、全文或权威著录。

Scholar 有两个入口：

1. 当前用户 Chrome：只用 `{{BROWSER_TOOL_NAME}}` 的现行浏览器绑定与页面接口（`tab.playwright` 或宿主同等的导航／页面求值工具）；
2. 可选 `scholarly`：运行 `scripts/scholar_search.py`，只取首屏候选，不调用追加填充、他引或 BibTeX 请求，不配置代理。

不得使用独立 Playwright、内置浏览器、后台爬虫、代理池、Cookie／账号导出、API key 服务或验证码绕过。用户显式要求 Scholar 时可直接走本通道；普通外文研究可与 OpenAlex 分别检索后在同一注册表去重。

## 2. 查询契约

查询 URL 固定为可复核的：

```text
https://scholar.google.com/scholar?q=<URL 编码检索式>&hl=en
```

可加 `as_ylo`、`as_yhi` 和按时间排序的 `scisbd=1`。检索式原文保留引号，不只保存编码后的 URL。

父控制面写入 acquisition v2：

```json
{
  "query_id": "Q-GS-001",
  "channel": "Google Scholar",
  "purpose": "collision",
  "query": "\"weaponized interdependence\"",
  "filters": {
    "years": "2019-2026",
    "sort": "relevance",
    "first_page_only": true
  },
  "result_count": 1250,
  "result_count_is_approximate": true,
  "result_count_basis": "page-displayed-about-total",
  "result_count_note": "页面显示 About/约 1,250 条，属于约数。",
  "url": "https://scholar.google.com/scholar?q=%22weaponized+interdependence%22&hl=en",
  "collected_at": "2026-08-04",
  "status": "complete"
}
```

Chrome 读取页面的 About/约数总量时使用 `result_count_basis=page-displayed-about-total` 并保留原显示文本。`scholarly` 不暴露总量时，只能登记首屏实际提取数，使用 `first-page-extracted` 并明确“不是数据库总量”。两种都必须标为约数，不能据此证明覆盖充分。

## 3. Chrome 单页操作

1. 先完整读取 `{{BROWSER_TOOL_NAME}}`，连接用户当前 Chrome；Chrome 不可用时停止，不切换其他浏览器。
2. 复用现有绑定或新建普通标签，导航到编码后的 Scholar URL。不得读取 cookie、localStorage、密码、profile 或浏览器存储。
3. 每次导航后重新读取页面状态，再从当前 DOM 提取。以当前宿主浏览器工具的实际接口为准：有的宿主通过 `tab.playwright` 从 DOM 提取，有的宿主的 devtools 工具即以 `navigate_page`／`evaluate_script` 命名，两者都不是错误；不要因接口名称差异改换浏览器或另起独立浏览器实例。
4. 只读第一页，不点击“下一页”，不自动展开 cited-by、版本列表或引用弹层。
5. 两次检索启动间隔不少于 5 秒，单会话最多 5 次检索。

首屏选择器是页面实测起点，不是永久契约：

| 数据 | 选择器／规则 |
|---|---|
| 结果块 | `div.gs_r.gs_or` |
| 标题与外链 | `h3.gs_rt a`；无外链标题保留待独立证据复核 |
| 作者／刊物／年份行 | `div.gs_a` |
| 片段 | `div.gs_rs` |
| 被引数 | `div.gs_fl a` 文本匹配 `/Cited by|被引用/` |
| 页面结果数 | `#gs_ab_md .gs_ab_mdw`，保留原文本并解析整数 |

返回父控制面的结构：

```json
{
  "query": {"channel": "Google Scholar", "url": "..."},
  "results": [
    {
      "title": "...",
      "authors_venue_year": "...",
      "external_url": "...",
      "snippet": "...",
      "cited_by": 0,
      "query_url": "...",
      "rank": 1
    }
  ]
}
```

浏览器动作只返回结构化对象；父控制面负责去重、Source ID 和注册表写入，不另存第二份书目真相。

## 4. 注册、去重与晋升

- 首次登记统一为 `channel="Google Scholar"`、`state=discovered`、`citation_scope=candidate-only`；片段和被引数放 `metadata`，不得写成 `verification.support_claim`。
- Scholar BibTeX 至多推进到 `metadata-exported/candidate-only`，不能把 `Verified` 改为 yes。
- DOI、规范 URL 或“题名＋首位作者＋年份”精确命中既有记录时复用原 Source ID，只追加 Scholar Query ID。模糊命中保持独立证据复核，不自动合并。
- 承重晋升须把 canonical channel/URL 改为 DOI、出版社或合法 OA 原文，记录 `verification.content_url`、摘要／详情／全文／PDF 核验方法、具体 support claim、撤稿状态与日期，并完成 acquisition v2 适用的可信度和正文页码审计。
- Scholar 查询页、结果片段、被引数、他人转述或 BibTeX 均不得作为 content verification；Scholar 也不能满足 CNKI-only 的 `venue`、`target-exemplar`、`sota` 合同。

## 5. 风控与停止

阻断信号包括 URL 含 `google.com/sorry`、可见 `form#gs_captcha_f`／`#recaptcha`，或页面只有空结果／异常流量提示。立即暂停，请用户在原 Chrome 完成；用户确认后只重试当前动作一次。仍失败就停止 Scholar，本轮继续 OpenAlex，并明确报告 Scholar 未完成。不得自动轮换代理、UA、账号或浏览器。
