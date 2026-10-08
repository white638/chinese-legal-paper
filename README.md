# 中文法学论文 Skill

面向中国法学论文的研究、写作、修订和引注核验，支持 Codex 与 Claude Code。

本仓库提供 `chinese-legal-paper` 1.0.0 及其配套的 paper1 / Avereth 7.2.0 运行代码。
`cnki-paper` 继续统一管理证据、研究阶段和完成状态；法学扩展增加法源版本、裁判程序、
方法卡、原文定位和引注支持关系检查。

## 快速开始

在装有 Python 3.10+ 的环境中：

```text
git clone https://github.com/white638/chinese-legal-paper.git
cd chinese-legal-paper
python -X utf8 tools/install_runtime.py --host codex --json
```

Claude Code 使用 `--host claude`。安装器先构建与检查，再备份并更新对应宿主的受管文件。
不要只复制 `skills/chinese-legal-paper`，它需要同版控制器中的法律检查接入。

安装后，在新会话中输入：

```text
使用 $chinese-legal-paper 帮我研究中文法学论文。
研究方向是……，已有材料是……。先核实研究问题、最近邻文献和材料可行性。
```

## 主要能力

- 法源、时间版本、裁判身份与程序信息登记；区分原文、编辑要旨和二手引用。
- 七类方法卡：规范解释、裁判分析、规范理论、比较法、实证法学、立法与制度设计、法律史。
- 原文定位、引用支持关系和稿件变更后的重新核验；Markdown 工作稿脚注与 Word 原生脚注结构检查。
- 北大法宝 MCP 客户端；Crossref、OpenAlex、Semantic Scholar、Unpaywall 元数据或开放获取线索查询。
- 复用 Exa 公开发现、CNKI 浏览器操作、paper1 证据约束写作与正式交付检查。

完整说明见 [使用文档](docs/CHINESE_LEGAL_PAPER.md)，接入参数见
[数据库适配说明](skills/chinese-legal-paper/references/providers.md)。

## 已验证范围

初版在 Windows 环境中发现 1700 项自动化测试，1699 项通过，1 项因符号链接权限跳过。
新增法学测试 60 项通过；Codex/Claude 构建与隔离安装检查通过。公开仓库的自动检查结果以
本仓库 Actions 为准，不能用本机结果代替远端结果。

Crossref 已完成真实题录查询测试。北大法宝付费服务、CNKI 账号与全文下载、其他需凭据的
学术接口尚未在用户账号下联调。题录或摘要不是已读全文，数据库访问权由实际账号决定。
本版未实现完整《法学引注手册》和任意期刊的全部特殊格式，也未完成真实论文全流程质量评测。

## 许可与来源

保留全部既有组件的许可和来源声明，见 [第三方声明](THIRD_PARTY_NOTICES.md)。
根目录尚未为全部原创代码指定统一开源许可证；公开可见不等于为所有内容授予相同许可。

## 配套研究运行时

以下保留 paper1 / Avereth 的架构、安装与运行说明。

### Avereth / CNKI-Paper v7.2.0

Avereth 是面向中文/CNKI、国际 SSCI 与混合证据生态的学术研究与写作代理。
`cnki-paper` 是唯一阶段和完成权威；`avereth_core` 是私有实现包。系统默认围绕研究问题、
证据、分析、论证和交付工作，检索、数据、方法、评审与渲染能力按需加载。

[Commonplace Writing Loop](skills/cnki-paper/references/commonplace-writing.md) 按当前论证动作检索已核验全文的局部范例。
新建全文与实质修订任务默认显式写入 `prose_conditioning=auto`：有合格范例时使用证据包与语言包，记录真实检索缺口后可用单包继续，锁定文本保持原样。
初始化参数 `--prose-conditioning none|commonplace|auto` 可覆盖此默认；旧配置缺省及 `none` 保留原路径，`commonplace` 保留严格双包要求。
所有模式均遵循问题推进、概念辨析、语境引用和自然段落组织；`none` 只关闭范文输入。借用、事实与语义检查不因范例缺口而放宽。
默认选择表达明确的写作偏好；真实文笔收益仍由固定任务的独立配对审读判断，不能用工程测试代替。
已保存[八类验收案例](evals/academic-prose/writing-method-cases.md)与[首轮真实材料诊断](evals/academic-prose/writing-method-diagnostic-20260920.md)；后者未证明稳定提升，最终安装版的端到端文笔效果仍未验证。

[知识改变验证](skills/cnki-paper/references/topic-selection-protocol.md) 将入围问题与最可能消解其贡献的
最近邻逐维比较，记录可核验反驳、假定或范围更新及不改变原认识的条件。只读差异视图由现有正本重建。
[自动创新性回归](evals/novelty-regression/README.md) 使用来源绑定对照、独立模型输出和换序检查，
同时观察误报创新与误杀增量研究；不确定结果保留为 UNCERTAIN。

## 单一源码，双宿主构建

仓库只维护一份研究内核、Agent 语义和入口正文。`hosts/codex` 与 `hosts/claude`
只声明路径、权限、入口、元数据和受控生成能力；构建器从同一提交生成两个互斥发行包：

```text
canonical skills + agent-specs + entrypoints
                    |
          +---------+---------+
          |                   |
  .dist/codex           .dist/claude
  agents/*.toml         agents/*.md
  prompts/avereth.md     commands/avereth.md
  openai.yaml 保留      openai.yaml 排除
```

`.dist/` 是可重建产物，不接受手工维护，也不是新的事实源。公共控制器、schema、receipt、
八阶段状态机和评测只维护一份；宿主差异必须落在 profile、fragment、renderer 或 host adapter。

## Lean Research Spine

用户任务以五个语义阶段呈现：

| 语义阶段 | 八阶段兼容映射 | 核心任务 |
|---|---|---|
| Scope | `intake` | 任务、问题定向、范围、轨道、目标刊与交付 |
| Evidence | `acquisition + research` | 来源发现、核验、阅读、综合、问题确认 |
| Analysis | `design + execution` | 研究设计、真实分析、结果与问题再判断 |
| Manuscript | `build` | 论证组织、证据约束写作、规范稿 |
| Verify | `audit + output` | 引用／证据／语义／格式核验、渲染与交付 |

五阶段是 `status/plan` 的只读投影，不是第二状态机。机器控制脊柱仍为：

```text
intake -> acquisition -> research -> design -> execution -> build -> audit -> output
```

这保留旧工作区、回退、profile 终点和 receipt 兼容，同时让默认上下文只加载当前任务需要的规则。

入口、Avereth Agent 与主 Skill 都先判定 Direct／Workspace。独立解释、翻译与表层改字
完成必要核验即可返回；只有 Workspace 才配置发表轨道并启动控制器。
`plan` 用 `reference_requests` 给出当前动作的文件、章节和读取理由，`required_references`
保留为路径索引。用 `plan OUTDIR --reference-action ACTION --json` 选择当前阶段的局部动作；
可用动作随计划返回，读取焦点不改变阶段、写权限或科学门禁。

## 可选 Scout 发现试点

[派发与候选发现](skills/cnki-paper/references/delegation.md) 保留单一主代理与原控制器，
通过 `plan.delegation_requests` 给出当前阶段的只读派发合同。Scout 默认关闭，按问题分区工作；
主线程经受限公开检索桥接捕获候选，再用原获取流程核验来源。上游变化阻断旧结果，
重复接纳不写入重复候选；研究者的风险路由与严格隔离生成器不变。
Scout 保持默认关闭的试点状态；真实质量与效率收益仍待配对实测。

## 核心边界

- 先确认实践张力与问题定向，再做侦察获取；完成定向补检后由用户确认精确问题、动机、范围、
  工作标题和标题权限，确认前不进入 design 或正文。
- 选题操作遵循 `skills/cnki-paper/references/topic-selection-protocol.md`。普通请求默认
  `direction_first`，新生成须绑定真实文献侦察；材料／现象来源需要当前明确授权与受限投影。
  旧 packet 只读兼容不授权新生成；四层方向契合、受控隔离、封存与用户确认继续生效。
- `literature_registry.json`、`literature_analysis.json`、`research_design.json`、
  `method_execution.json` 分别是来源、批判综合、设计与执行唯一机器事实源。
- 搜索结果、Exa、Scholar、Zotero 元数据和发现页只能作候选；承重前回合法内容来源核验。
- 实证数字必须来自真实 accepted action，负面结果、偏离和推断边界必须传播到贡献与正文。
- build 保留 ProsePacket 上下文隔离、protected-atom、Clarity、semantic fidelity 与 Clean Read；
  控制器状态、评审意见、数据日志和完整证据库不进入 Writer。
- full paper/revision 的 manuscript contract 与 MIR 是 build 派生投影，不是第九阶段或科学权威；
  上游漂移仍须证明受影响正文真实重建。
- 正式 isolated review 只在 audit 按需运行；普通研究与写作默认单一主代理。执行中的多研究者协作
  只服从设计风险路由，不设固定代理配额。
- output 第一次只生成候选；逐页视觉复核后第二次 gate 才事务发布并签收。

## 数据按需

全局 SQLite 数据目录、跨项目快照、自动变量匹配和公共数据库 starter 不属于默认论文控制面。
只有定量、计算、混合方法、用户明确找数据，或主张必须依赖结构化数据时，才调用
`quantitative-data-check`。

本地文件、公开下载、API、注册、申请、机构订阅和商业来源按问题适配、变量、覆盖、许可、成本与
可复现性平等比较。选题发散只提示候选路线；设计前核验元数据／问卷／代码本；分析前核验真实样本
或查询结果；结果写作绑定实际数据、方法、结果和 SHA。定量准备卡不能替代 F2 材料探针或执行事实。

## 证据轨道

- `cnki-cn`：中文期刊、会议、课程论文或明确依赖 CNKI 的任务；
- `international-ssci`：国际学术证据生态，允许 0 条 CNKI 来源；
- `mixed`：中外对话都对承重主张不可替代。

轨道必须同时写入 `workflow_config.json` 与 `literature_registry.json`。SSCI 状态、scope、
article type 和作者指南须当次核验 Clarivate、期刊和出版社官方来源。

## 中文法学论文扩展

`chinese-legal-paper` 1.0.0 为 `cnki-paper` 增加法源与时间版本、裁判程序、七类法学方法、
原文定位和引注支持关系检查，以及北大法宝 MCP 和国外学术元数据客户端。工作区按需启用
`legal_profile=chinese-law-v1`；仍由原控制器判定阶段和完成。它不授予知网全文权限，
不把题录检索或合同检查的 PASS 当作法律论证正确。使用方式、实际支持范围和接入限制见
[中文法学论文使用说明](docs/CHINESE_LEGAL_PAPER.md)。必须安装同一版本的完整宿主运行时，
单独复制新 Skill 目录不足以启用控制器检查。

## 安装

Windows PowerShell：

```powershell
# Codex（默认）
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1

# Claude Code
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -AverethHost claude
```

macOS / Linux / Git Bash：

```bash
# Codex（默认）
bash ./install.sh

# Claude Code
bash ./install.sh --host claude
```

安装器要求 Python 3.10+。它先从规范源构建并验收目标宿主包，再可恢复地备份旧运行时、同步受管文件，
最后执行 agent、entrypoint、installed doctor 与 runtime parity 验收。默认分别安装到 `~/.codex` 和
`~/.claude`；可用 `-RuntimeHome` / `--runtime-home` 指定隔离目录。

## 使用（Codex 示例）

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$BundledPython = Join-Path $HOME '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$PythonCandidates = @($env:CODEX_PYTHON, $BundledPython) + @((Get-Command python -ErrorAction SilentlyContinue).Source)
$Python = $null
foreach ($Candidate in $PythonCandidates | Select-Object -Unique) {
  if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate -PathType Leaf)) { continue }
  & $Candidate -B -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)"
  if ($LASTEXITCODE -eq 0) { $Python = $Candidate; break }
}
if (-not $Python) { throw 'Avereth requires Python 3.10 or newer.' }
$Controller = Join-Path $HOME '.codex\skills\cnki-paper\scripts\avereth.py'

& $Python -X utf8 $Controller doctor paper_rewriting_output
& $Python -X utf8 $Controller status paper_rewriting_output --json
& $Python -X utf8 $Controller plan paper_rewriting_output --json
& $Python -X utf8 $Controller gate paper_rewriting_output --stage research
```

Claude Code 安装树位于 `${CLAUDE_CONFIG_DIR:-~/.claude}`，命令入口为 `/avereth`；其生成 runner
默认是 `claude-exec`，并额外允许显式披露的 `agent-declared` 两阶段路线。Codex 入口为
`/prompts:avereth`，只允许 `codex-exec`。构建期 profile 决定宿主，不由模型运行时猜测。

只执行 status 返回的最早机器阶段。`plan` 只读输出当前语义阶段、机器阶段、references、adapters 和
allowed writes；只有 execution 需要 operation 级计划：

```powershell
& $Python -X utf8 $Controller plan paper_rewriting_output --granularity operation --json
& $Python -X utf8 $Controller protocol validate paper_rewriting_output --json
& $Python -X utf8 $Controller protocol compile paper_rewriting_output --json
& $Python -X utf8 $Controller next paper_rewriting_output --explain
```

完整论文／返修进入 build 时：

```powershell
& $Python -X utf8 $Controller manuscript init paper_rewriting_output --apply
& $Python -X utf8 $Controller manuscript compile paper_rewriting_output --json
& $Python -X utf8 $Controller manuscript render paper_rewriting_output --baseline
& $Python -X utf8 $Controller manuscript validate paper_rewriting_output --json
```

材料真实性与 F2 继续使用受控探针：

```powershell
& $Python -X utf8 $Controller research-materials validate paper_rewriting_output --scope acquisition --json
& $Python -X utf8 $Controller research-feasibility validate paper_rewriting_output --json
& $Python -X utf8 $Controller research-feasibility resource-state paper_rewriting_output
```

## 迁移

旧工作区通过显式、可逆迁移进入当前运行时。未知未来 schema、冲突配置、多份不一致规范稿和凭证型
字段安全阻塞；旧 PASS receipt 只作历史证据。

```powershell
& $Python -X utf8 $Controller migrate paper_rewriting_output --dry-run
& $Python -X utf8 $Controller migrate paper_rewriting_output --apply
& $Python -X utf8 $Controller migrate paper_rewriting_output --rollback <backup_manifest.json>
```

## 开发验收

可选 [运行轨迹与配对评测](docs/TRAJECTORY_EVALUATION.md) 保留宿主原始事件、实际耗时、用量、
控制器调用及 audit action 记录，并连接 [按改动选择案例的组件实验入口](evals/lean-core-v7/README.md)。
任务库按版本保存，默认 targeted 选择相关案例。KEEP 需要完整性与任务完成不退步，且预登记目标达到改善阈值；
文风偏好通常只作诊断，结果不证明论文整体质量提升。约束责任与消融范围见 [Constraint Census](docs/CONSTRAINT_CENSUS.md)。

```powershell
& $Python -B -X utf8 tools\build_host.py --host codex --out .dist\codex --json
& $Python -B -X utf8 tools\build_host.py --host claude --out .dist\claude --json
& $Python -B -X utf8 tools\host_leak_check.py . --source
& $Python -B -X utf8 tools\host_leak_check.py .dist\codex --host codex
& $Python -B -X utf8 tools\host_leak_check.py .dist\claude --host claude
& $Python -B -X utf8 tools\smoke_check.py .dist\codex --host codex
& $Python -B -X utf8 tools\smoke_check.py .dist\claude --host claude
& $Python -B -X utf8 tools\check_workflow_registry.py --check
& $Python -B -X utf8 tools\agent_bundle_check.py .dist\codex\agents --host codex
& $Python -B -X utf8 tools\agent_bundle_check.py .dist\claude\agents --host claude
& $Python -B -X utf8 -m unittest discover -s skills\cnki-paper\scripts -p 'test_*.py'
& $Python -B -X utf8 -m unittest discover -s skills\empirical-research\scripts -p 'test_*.py'
& $Python -B -X utf8 -m unittest discover -s tools -p 'test_*.py'
& $Python -B -X utf8 tools\install_runtime.py --host codex --runtime-home .ci-install\codex --json
& $Python -B -X utf8 tools\install_runtime.py --host claude --runtime-home .ci-install\claude --json
```

发布底线是：八阶段完成权威唯一、五阶段投影无写入、status 纯读、gate 不能越级、来源／结果真实性
不退步、输出事务可回滚、安装树与源码一致。新能力只有在真实失败案例和对照评测证明现有核心无法
稳定完成时才进入默认路径，否则保持可选和延迟加载。

更多边界见 [架构说明](docs/ARCHITECTURE.md)、[维护规范](docs/MAINTENANCE.md) 与
[来源及升级政策](docs/UPSTREAM.md)。历史发布说明保存在 GitHub Releases。
