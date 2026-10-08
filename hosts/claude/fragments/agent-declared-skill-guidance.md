`claude` CLI 不可用或用户明确接受声明式来源时，可改用 `--runner agent-declared` 两阶段路线：
先以 `--emit-prompts DIR` 生成逐通道 canonical prompt 与 manifest，再让 Agent 工具为每个 prompt 启动一个
只接收该 prompt 的全新子代理，将完整 JSON 回复与真实 context id 写入清单指定路径，最后以 `--responses DIR`
收取封存。该路线仍受 prompt SHA、schema、记账和 seal gate 约束，但收据以 `AGENT-DECLARED-` 标注，必须向用户
如实说明它是声明式来源而非宿主签名隔离；两条来源路线不得混用。
