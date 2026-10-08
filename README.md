# 中文法学论文 Skill

面向 Codex 和 Claude Code 的中文法学论文研究与写作工具，支持选题、文献检索、法律资料整理、论文起草、修改和引注核查。

项目基于 paper1 / Avereth，补充了中国法学研究所需的法源版本、裁判分析、研究方法和引注核验流程。可以从一个研究方向开始，也可以接着已有的提纲或稿件继续工作。

## 功能

- **选题与文献研究**：梳理具体争议、已有研究和材料条件，形成研究问题与提纲。
- **法律资料核查**：核对法条版本、效力时间、案例身份和程序信息，区分原始文本、编辑要旨与二手引用。
- **法学论证**：支持规范解释、裁判分析、规范理论、比较法、实证法学、立法研究和法律史等方法。
- **写作与修改**：依据已核实的材料组织论证、起草正文、回应反对意见，并检查修改是否改变原意。
- **引注与稿件整理**：核查引用出处、原文位置及其与论点的关系，生成基础脚注并检查 Word 原生脚注结构。

## 安装

需要 Git 和 Python 3.10 及以上版本。

```bash
git clone https://github.com/white638/chinese-legal-paper.git
cd chinese-legal-paper
```

安装到 Codex：

```bash
python -X utf8 tools/install_runtime.py --host codex
```

安装到 Claude Code：

```bash
python -X utf8 tools/install_runtime.py --host claude
```

选择自己使用的客户端执行即可。如果本机使用 `python3` 命令，将上面的 `python` 替换为 `python3`。

仓库已包含配套研究模块，请使用安装器完成安装。安装器会备份被替换的文件，并检查安装结果。安装完成后，新开会话使用。

## 使用示例

在 Codex 中，可以用 `$chinese-legal-paper` 指定技能，并说明研究方向、已有材料和希望完成的工作。

**从研究方向开始：**

```text
使用 $chinese-legal-paper，帮我梳理行政处罚中比例原则的研究选题。
先检索已有研究，找出值得讨论的具体争议，再评估材料是否足够。
```

**修改已有稿件：**

```text
使用 $chinese-legal-paper，检查这篇论文的论证结构和概念使用。
结合我提供的材料修改，说明哪些判断需要补充证据。
```

**核查引注：**

```text
使用 $chinese-legal-paper，审核这篇论文的法条版本、案例和文献引注。
标出出处有误、原文定位不清、引用不足以支持结论的地方，并列出待核材料。
```

在 Claude Code 中，也可以直接说明“使用 chinese-legal-paper 技能”及具体任务。

## 文献与数据库

| 渠道 | 用途 | 使用条件 |
|---|---|---|
| Exa 等公开检索工具 | 发现文献、法规、案例和公开资料 | 当前客户端已连接相应搜索工具 |
| 中国知网 | 检索中文学术文献、查看详情及取得授权内容 | 通过浏览器使用，全文与下载取决于账号权限 |
| 北大法宝 MCP | 查询法律法规、案例及相关法律资料 | 配置 Token，并具备相应服务权限与额度 |
| Crossref、OpenAlex、Semantic Scholar、Unpaywall | 查询外文文献题录、DOI 和开放获取线索 | 部分服务需要 API Key 或联系邮箱 |

配置方法见[检索与数据库说明](skills/chinese-legal-paper/references/providers.md)。北大法宝和知网的账号联调需在实际使用环境中完成。

检索结果和摘要不能代替原文核实。当前内置脚注样式用于工作稿，投稿时仍需按目标期刊的具体规则复核。

## 文档

- [完整使用说明](docs/CHINESE_LEGAL_PAPER.md)
- [法学研究方法](skills/chinese-legal-paper/references/methods.md)
- [引注与稿件整理](skills/chinese-legal-paper/references/citations.md)
- [架构说明](docs/ARCHITECTURE.md)

## 许可

第三方组件的许可与来源见[第三方声明](THIRD_PARTY_NOTICES.md)。项目尚未设置统一的开源许可证。
