"""ClaudeExec host adapter for schema-bound isolated generation."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .base import (
    HostCapture,
    event_context_id,
    event_uses_tool,
    schema_instruction,
    strip_json_fence,
    text,
)

from .telemetry import HostObservation


HOST_ID = "claude"
PROVENANCE_MODE = "host-signed"
DISALLOWED_TOOLS = ",".join(
    (
        "Task",
        "Agent",
        "Bash",
        "BashOutput",
        "KillShell",
        "Glob",
        "Grep",
        "Read",
        "Edit",
        "MultiEdit",
        "Write",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "TodoWrite",
        "EnterPlanMode",
        "ExitPlanMode",
        "Skill",
        "SlashCommand",
        "ListMcpResources",
        "ReadMcpResource",
    )
)


def run_claude_exec_isolated(
    *,
    prompt: str,
    output_schema: Mapping[str, Any],
    model_revision: str,
    timeout_seconds: int = 180,
) -> HostCapture:
    """Run Claude Code headlessly with settings, MCP, and tools disabled."""

    if len(text(model_revision)) < 3:
        raise ValueError("ClaudeExec topic adapter requires an explicit model revision")
    with HostObservation(HOST_ID, model_revision, prompt) as observation:
        with tempfile.TemporaryDirectory(prefix="avereth-topic-isolated-") as temporary:
            isolated_root = Path(temporary)
            schema_text = json.dumps(output_schema, ensure_ascii=False, indent=2)
            executable = shutil.which("claude") or "claude"
            command = [
                executable,
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--model",
                text(model_revision),
                "--strict-mcp-config",
                "--mcp-config",
                '{"mcpServers":{}}',
                "--setting-sources",
                "",
                "--disallowedTools",
                DISALLOWED_TOOLS,
                "--append-system-prompt",
                schema_instruction(schema_text),
            ]
            try:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    cwd=isolated_root,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError(
                    "ClaudeExec isolated generation BLOCKED: "
                    f"timed out after {timeout_seconds} seconds; "
                    "no receipt or seed seal was issued"
                ) from exc
            except OSError as exc:
                raise ValueError(
                    "ClaudeExec isolated generation BLOCKED: the claude CLI could not be "
                    "launched; no receipt or seed seal was issued"
                ) from exc
            observation.process_result(completed)
            if completed.returncode != 0:
                raise ValueError(
                    "ClaudeExec isolated generation failed: "
                    + text(completed.stderr or completed.stdout)
                )
            events: list[Any] = []
            for line in completed.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError("ClaudeExec emitted non-JSON provenance output") from exc
            if not events:
                raise ValueError("ClaudeExec emitted no provenance events")
            if any(event_uses_tool(event) for event in events):
                raise ValueError(
                    "ClaudeExec isolation failed because the generation context used a tool"
                )
            context_ids = {
                context_id
                for context_id in (event_context_id(event) for event in events)
                if context_id
            }
            if len(context_ids) != 1:
                raise ValueError("ClaudeExec provenance must expose exactly one context id")
            results = [
                event
                for event in events
                if isinstance(event, Mapping) and event.get("type") == "result"
            ]
            if not results or results[-1].get("is_error"):
                raise ValueError("ClaudeExec did not produce its schema-constrained last message")
            raw_text = strip_json_fence(text(results[-1].get("result")))
            try:
                json.loads(raw_text)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "ClaudeExec did not produce its schema-constrained last message"
                ) from exc
            return HostCapture(
                raw_output=raw_text.encode("utf-8"),
                run_id=observation.run_id,
                model_revision=text(model_revision),
                context_id=next(iter(context_ids)),
                telemetry=observation.finish(context_id=next(iter(context_ids))),
            )
