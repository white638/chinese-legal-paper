When the `claude` CLI is unavailable or the user explicitly accepts declared
provenance, use the sanctioned `--runner agent-declared` two-phase route
instead: `--emit-prompts DIR`, then spawn one fresh subagent per emitted prompt
through the Agent tool (give it only that prompt file's content), save each raw
JSON reply to its `*.response.json` and the real agent context id to
`*.context.txt`, and finish with `--responses DIR`. The controller still binds
responses by prompt SHA and applies every schema, accounting, and seal gate;
receipts carry `AGENT-DECLARED-` run ids, and you must disclose that mode as
declared provenance, not host-signed isolation. The same two-phase route exists
for `host-screen`, `material-discovery`, and `semantic-review`; use a distinct
fresh subagent for every step.
