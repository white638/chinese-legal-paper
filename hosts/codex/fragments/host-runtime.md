# Codex 宿主运行契约

- 安装根：`${CODEX_HOME:-~/.codex}`；技能位于 `skills/`，代理位于 `agents/*.toml`，入口位于 `prompts/avereth.md`。
- Python：优先 `CODEX_PYTHON`，Windows 可回退到 Codex 捆绑 Python，再尝试系统 Python 3.10+。
- 浏览器：先调用 `chrome:control-chrome` 并服从其运行时说明；不要改用 Claude DevTools MCP。
- 受控生成：仅支持 `codex-exec` 的宿主签名隔离；不接受 `agent-declared` 收据。
- 权限映射：主代理为 `workspace-write`，隔离写作、评审与研究代理为 `read-only`。
