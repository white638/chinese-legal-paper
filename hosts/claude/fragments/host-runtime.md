# Claude Code 宿主运行契约

- 安装根：`${CLAUDE_CONFIG_DIR:-~/.claude}`；技能位于 `skills/`，代理位于 `agents/*.md`，入口位于 `commands/avereth.md`。
- Python：优先 `CLAUDE_PYTHON`，再尝试系统 Python 3.10+；不探测 Codex 捆绑运行时。
- 浏览器：使用 `chrome-devtools` MCP（`mcp__chrome-devtools__*` 工具族），并服从当前 MCP 能力与登录边界。
- 受控生成：默认 `claude-exec` 宿主签名隔离；`agent-declared` 仅按两阶段 prompt/response/context 清单运行并明确披露声明式来源。
- 权限映射：主代理继承宿主工具，隔离写作、评审与研究代理仅声明 `tools: Read`。
