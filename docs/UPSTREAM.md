# 来源、宿主与升级政策

## 一个公共源码上游

Avereth 只维护一个公共源码历史。`codex` 与 `claudecode` 不再作为彼此人工同步的长期演化中心；
迁移稳定后，公共主分支应使用中立名称 `main`。旧宿主分支保留一个发布周期作为只读回退线，
不得继续接收公共功能提交。

同一提交必须可重建两套发行物：

```text
avereth-<version>-codex
avereth-<version>-claude-code
```

公共事实源包括 `skills/`、`agent-specs/`、`entrypoints/` 与控制器代码。宿主差异只进入
`hosts/<host>/`、`avereth_core/hosts/`、构建器和明确的兼容 allowlist。`.dist/`、安装树和 CI artifact
都是派生产物，禁止反向覆盖规范源。

## 宿主能力矩阵

| 能力 | Codex | Claude Code |
|---|---:|---:|
| host-signed 隔离生成 | `codex-exec` | `claude-exec` |
| agent-declared 两阶段来源 | 不支持 | 支持 |
| Agent 格式 | TOML | Markdown + YAML frontmatter |
| 只读权限映射 | `sandbox_mode = "read-only"` | `tools: Read` |
| 入口 | `prompts/avereth.md` | `commands/avereth.md` |
| OpenAI Skill metadata | 保留 | 排除 |

`host-signed` 与 `agent-declared` 是不同来源语义。公共控制器可共享 schema、协议、签名与 receipt
验证，但不得把声明式来源伪装成宿主签名隔离。构建期 profile 决定可用 runner；不运行时猜宿主。

## 第三方来源

部分引用、结构化评审、LaTeX 和 Word 检查算法源自 PaperSpine 4.0.0（WUBING2023），按 MIT
License 修改和再分发。完整来源、移植文件清单和许可分别记录在 `THIRD_PARTY_NOTICES.md` 与
`licenses/PaperSpine-MIT.txt`。

保留来源声明不代表存在运行依赖。上游产品身份、进度模型、UI、更新器和控制面没有进入当前架构。

## 接收算法或宿主更新

1. 在短生命周期分支审查具体算法、宿主接口与许可证，不整目录覆盖本地包；
2. 先判断变化属于公共协议还是宿主适配，公共规则只修改一次；
3. 说明真实失灵、受保护底线、最小移植边界和回滚办法；
4. 把算法改写为本地 `GateResult`/报告合同，不引入第二阶段、配置或完成权威；
5. 更新来源声明、能力 profile、agent/entrypoint 模板或 adapter；
6. 生成 Codex 与 Claude 两套包，分别执行 smoke、host leak、isolated install、doctor 与 parity；
7. 只有公共内核一致、宿主能力未混淆且旧收据正确 fail closed 时才合并。

最低本地验收：

```powershell
& $Python -B -X utf8 tools\build_host.py --host codex --out .dist\codex --json
& $Python -B -X utf8 tools\build_host.py --host claude --out .dist\claude --json
& $Python -B -X utf8 tools\smoke_check.py .dist\codex --host codex
& $Python -B -X utf8 tools\smoke_check.py .dist\claude --host claude
& $Python -B -X utf8 -m unittest discover -s skills\cnki-paper\scripts -p 'test_*.py'
& $Python -B -X utf8 -m unittest discover -s tools -p 'test_*.py'
```

CNKI 获取、国际发现、方法适配器、期刊包和页面证据仍是懒加载适配器。更新任一适配器不得取得阶段
所有权、另建事实表、把元数据升级为正文证据、改变 publication track 门禁，或让动作/schema 漂移继续
接受旧 receipt。
