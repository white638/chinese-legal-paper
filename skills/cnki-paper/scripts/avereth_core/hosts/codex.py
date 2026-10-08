"""CodexExec host adapter for schema-bound isolated generation."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping

from .base import HostCapture, event_context_id, event_uses_tool, text

from .telemetry import HostObservation


HOST_ID = "codex"
PROVENANCE_MODE = "host-signed"


def run_codex_exec_isolated(
    *,
    prompt: str,
    output_schema: Mapping[str, Any],
    model_revision: str,
    timeout_seconds: int = 180,
) -> HostCapture:
    """Run Codex in a fresh projectless read-only context and capture output."""

    if len(text(model_revision)) < 3:
        raise ValueError("CodexExec topic adapter requires an explicit model revision")
    with HostObservation(HOST_ID, model_revision, prompt) as observation:
        with tempfile.TemporaryDirectory(prefix="avereth-topic-isolated-") as temporary:
            isolated_root = Path(temporary)
            schema_path = isolated_root / "output.schema.json"
            output_path = isolated_root / "last-message.json"
            schema_path.write_text(
                json.dumps(output_schema, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            command = [
                "codex",
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--enable",
                "skip_host_skill_discovery",
                "--skip-git-repo-check",
                "-s",
                "read-only",
                "--disable",
                "shell_tool",
                "--disable",
                "apps",
                "--disable",
                "browser_use",
                "--disable",
                "in_app_browser",
                "--disable",
                "computer_use",
                "--disable",
                "image_generation",
                "--disable",
                "multi_agent",
                "--disable",
                "plugins",
                "--disable",
                "standalone_web_search",
                "--model",
                text(model_revision),
                "--cd",
                str(isolated_root),
                "--output-schema",
                str(schema_path),
                "--output-last-message",
                str(output_path),
                "--json",
                "--color",
                "never",
                "-",
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
                    "CodexExec isolated generation BLOCKED: "
                    f"timed out after {timeout_seconds} seconds; "
                    "no receipt or seed seal was issued"
                ) from exc
            except OSError as exc:
                raise ValueError(
                    "CodexExec isolated generation BLOCKED: the codex CLI could not be "
                    "launched; no receipt or seed seal was issued"
                ) from exc
            observation.process_result(completed)
            if completed.returncode != 0:
                errors = []
                for line in completed.stdout.splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict) and event.get("type") == "error" and text(event.get("message")):
                        errors.append(text(event["message"]))
                raise ValueError(
                    "CodexExec isolated generation failed: "
                    + ("\n".join(errors) or text(completed.stderr or completed.stdout))
                )
            events: list[Any] = []
            for line in completed.stdout.splitlines():
                if not line.strip():
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError("CodexExec emitted non-JSON provenance output") from exc
            if not events:
                raise ValueError("CodexExec emitted no provenance events")
            if any(event_uses_tool(event) for event in events):
                raise ValueError(
                    "CodexExec isolation failed because the generation context used a tool"
                )
            context_ids = {
                context_id
                for context_id in (event_context_id(event) for event in events)
                if context_id
            }
            if len(context_ids) != 1:
                raise ValueError("CodexExec provenance must expose exactly one context id")
            if not output_path.is_file():
                raise ValueError("CodexExec did not produce its schema-constrained last message")
            return HostCapture(
                raw_output=output_path.read_bytes(),
                run_id=observation.run_id,
                model_revision=text(model_revision),
                context_id=next(iter(context_ids)),
                telemetry=observation.finish(context_id=next(iter(context_ids))),
            )
