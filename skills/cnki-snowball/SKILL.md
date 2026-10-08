---
name: cnki-snowball
description: CNKI 引文滚雪球（citation chasing）——从知网文献详情页提取参考文献（后向）、引证文献（前向）及共引/同被引/二级共六个方向的引文列表，可链式追踪。Use when the user wants to chase citations of a Chinese paper on CNKI — 滚雪球、引文追踪、引文网络、参考文献列表、引证文献列表、谁引用了这篇、这篇引了谁、后向/前向检索. Requires the paper's detail page URL (from cnki-search results).
---

# CNKI 引文滚雪球

## {{HOST_DISPLAY_NAME}} 集成

先完整读取 `{{BROWSER_TOOL_NAME}}` 的运行时说明，再用当前支持的标签页、点击与页面求值操作。作为 `cnki-paper` 获取适配器运行时，同时读取 `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` 与 `acquisition-registry.md`；父线程把种子、方向、日期和 URL 写为 `purpose=snowball` 的 registry query，发现条目复用稳定 Source ID 并先登记为 `candidate-only`，不得跨越父级 citation gate。

从详情页的引文网络区提取六个方向：`references` 参考文献（后向，挖理论谱系）、`citations` 引证文献（前向，挖最新对话；默认时间倒序）、`coreferences` 共引文献（引了相同参考文献的近亲，耦合）、`cocitations` 同被引文献（被同批后续文献共同引用）、`secondreferences`/`secondcitations` 二级参考/二级引证。

**权限边界（2026-07 实测）**：每方向第 1 页（每来源组约 10 条）随标签激活免验证加载；**翻页对机构 IP 用户（utype≠jf）必弹验证码**——页面 `getrefdata` 自带 `captchId` 参数，这是刻意的风控门，**不得调用内部函数绕过**，翻页走"用户在环"（第 3 步）。数据端点 `restapi/citation-api/v1/literature/{references|citations}` 的 `v` 令牌一次性，直连重放必 400001，只能驱动页面自身 JS。

## Steps

### 1. Navigate

使用当前 Chrome 控制运行时导航到文献详情页 URL。
URL 来自 cnki-search 结果的 `href`，**必须整条使用**（内含长令牌，截断即 404）。只有题名时先跑 cnki-search 拿 href。

### 2. Trigger + extract（单次 evaluate_script）

按需改第一行 `dirs`（默认后向+前向）：

```javascript
async () => {
  const dirs = ["references", "citations"];
  await new Promise((r, j) => {
    let n = 0;
    const c = () => { if (document.querySelector('#refpartdiv, a#references')) r(); else if (++n > 30) j('timeout'); else setTimeout(c, 500); };
    c();
  });
  const cap = document.querySelector('#tcaptcha_transform_dy');
  if (cap && cap.getBoundingClientRect().top >= 0) return { error: 'captcha' };
  const out = { title: document.title.replace(' - 中国知网', '') };
  for (const dir of dirs) {
    const a = document.querySelector('a#' + dir);
    if (!a) { out[dir] = { error: 'tab missing' }; continue; }
    a.scrollIntoView({ block: 'center' });
    try { changerefdata(a); } catch (e) { a.click(); }
    await new Promise((r) => {
      let n = 0;
      const c = () => {
        const d = document.querySelector('#quoted-' + dir);
        if (d && d.innerText.trim().length > 50) r();
        else if (++n > 40) r();
        else setTimeout(c, 500);
      };
      c();
    });
    const d = document.querySelector('#quoted-' + dir);
    if (!d) { out[dir] = { error: 'no data block' }; continue; }
    // 滚一遍触发其他来源组（博硕/图书等）的懒加载
    d.querySelectorAll('[id^="nxgp-kcms-data-ref-"]').forEach(g => g.scrollIntoView({ block: 'center' }));
    await new Promise(r => setTimeout(r, 1500));
    const groups = Array.from(d.querySelectorAll('.dbTitle')).map(g => g.innerText.replace(/\s+/g, ' ').trim());
    const items = Array.from(d.querySelectorAll('li')).map(li => ({
      txt: (li.innerText || '').trim(),
      href: li.querySelector('a.document-title')?.href || li.querySelector('a')?.href || ''
    })).filter(x => x.txt);
    const pager = Array.from(d.querySelectorAll('.pageBar')).map(p => p.innerText.replace(/\s+/g, ' ').trim());
    out[dir] = { groups, count: items.length, items, pager };
  }
  return out;
}
```

### 3. 翻页（可选，验证码在环）

需要第 2 页以后的数据时：通过当前 Chrome 运行时真实点击分页链接（`#nxgp-kcms-data-ref-<dir>-journal-page a[data-page="2"]`；合成 DOM click 可能不触发），随后检查 `.citation-turnpage` / `.citation-mask-shade` 弹层——**弹出即停，请用户在原标签页完成验证**，用户确认后重跑第 2 步的提取段（不再 changerefdata）。逐页如此。深前向（数百条引证）不要在 CNKI 硬翻，改走检索页被引排序或收窄需求。

### 4. Report / 登记

- 条目格式 `[N] 题名[刊别]. 作者;作者.刊名,年(期)` ＋ 详情页 href（可作为新种子链式再滚）。
- 入 `literature_registry.json`：query 写 `purpose=snowball`、`snowball:<方向>@<种子题名或URL>`、页面类型、稳定 URL 与采集日期；条目未经详情页/摘要核验前一律 `candidate-only`。随后由父线程生成 source index。
- 条目取得 Source ID 后，父线程把引用关系登记为注册表 `edges`：references 方向 from=种子、to=条目，citations 方向反向，
  `relation=cites`、`evidence=cnki-detail`、`stance=unknown`；coreferences／cocitations 登记为 `co-cited-with`。
  格式与规则见 `cnki-paper/references/acquisition-registry.md` 5.3。

## Verified selectors & mechanics（2026-07 实测）

| 元素 | 选择器 | 说明 |
|---|---|---|
| 方向标签 | `a#references` `a#citations` `a#coreferences` `a#cocitations` `a#secondreferences` `a#secondcitations` | onclick=`changerefdata(this)` |
| 数据容器 | `#quoted-<方向id>` | 懒加载，激活标签后填充 |
| 来源组块 | `div[id^=nxgp-kcms-data-ref-<方向>-<组>]` | 组=journal/博硕等；`.dbTitle` 含"期刊 共N条" |
| 条目 | 组内 `ul.ebBd li` | `span.number` + `a.document-title`(href 可链式) + 著录文本 |
| 分页器 | `#nxgp-kcms-data-ref-<方向>-<组>-page.pageBar` | `span.active` 当前页、`a[data-page=N]`、共N页 |
| 验证弹层 | `.citation-turnpage` `.citation-mask-shade` | 机构用户翻页触发，交用户处理 |

- 实测样本：新质生产力网络首发文（参考文献 15 条全提取）；任保平《经济研究》2024（被引 831，引证文献期刊组 724 条/73 页，首页 10 条免验证）。
- 引证文献默认**时间倒序**（最新对话视图）；要"高被引引用者"视图，用检索页被引排序（中文）或 OpenAlex snowball forward `--sort cited`（外文）。
- 主题相近但无引文关系的发散，用详情页"相似文献"或 OpenAlex related，不在本技能范围。

## 纪律

- **只对承重/奠基文献滚**（种子通常 ≤3 篇）；每个种子＝1 次导航＋1 次提取脚本，风控暴露与一次详情页核验相当。
- 验证码协议与 cnki-paper 铁律 1 一致：弹出即暂停，用户完成后重试一次。
- 提取结果是**书目级证据**（screening evidence）：题名/作者/刊/年可信，但拟引用前仍须进详情页做内容核验，遵守引用库 12 列契约。

## Tool calls: 2（navigate + evaluate_script）；每翻一页 +1 次脚本＋一次用户验证
