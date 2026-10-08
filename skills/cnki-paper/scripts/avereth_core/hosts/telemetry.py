"""Optional local execution observations, outside scientific state and receipts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _decoded(value: Any) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else (value or "")


def parse_events(stdout: str) -> tuple[list[Any], int]:
    events, invalid = [], 0
    for line in stdout.splitlines():
        if line.strip():
            try:
                events.append(json.loads(line))
            except ValueError:
                invalid += 1
    return events, invalid


def _count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def host_measurements(host: str, events: list[Any], *, complete: bool) -> dict[str, Any]:
    """Use terminal host usage records; never count both deltas and totals."""
    measurements: dict[str, Any] = {
        "input_tokens": None, "output_tokens": None, "tool_calls": None,
        "context_files_loaded": None, "context_bytes_loaded": None,
        "agent_calls": None, "persistent_artifacts_created": None,
        "unnecessary_user_interruptions": None,
    }
    objects = [event for event in events if isinstance(event, dict)]
    if host == "codex":
        usage = [e.get("usage") for e in objects if e.get("type") == "turn.completed"]
    elif host == "claude":
        results = [e for e in objects if e.get("type") == "result"]
        usage = [results[-1].get("usage")] if results else []
    else:
        usage = []
    for metric in ("input_tokens", "output_tokens"):
        if complete and usage and all(isinstance(u, dict) and _count(u.get(metric)) for u in usage):
            measurements[metric] = sum(u[metric] for u in usage)
    # Interrupted streams may contain starts without completions. Their count is unknown.
    if complete and usage and host == "codex":
        items = [e.get("item") for e in objects if e.get("type") == "item.completed"]
        tool_types = {"command_execution", "mcp_tool_call", "web_search", "file_change", "collab_tool_call"}
        measurements["tool_calls"] = len({
            item.get("id", str(index)) for index, item in enumerate(items)
            if isinstance(item, dict) and item.get("type") in tool_types
        })
    elif complete and usage and host == "claude":
        messages = [e["message"] for e in objects if e.get("type") == "assistant" and isinstance(e.get("message"), dict)]
        blocks = [block for message in messages if isinstance(message.get("content"), list)
                  for block in message["content"] if isinstance(block, dict)]
        measurements["tool_calls"] = len({b.get("id", str(i)) for i, b in enumerate(blocks) if b.get("type") == "tool_use"})
    return measurements


def save_observation(payload: dict[str, Any]) -> Path | None:
    """Opt-in sidecars use exclusive creation; their presence grants no authority."""
    directory = os.environ.get("AVERETH_TELEMETRY_DIR")
    if not directory:
        return None
    root = Path(directory).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    path = root / ("observation-" + uuid.uuid4().hex + ".json")
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def emit_observation(payload: dict[str, Any]) -> None:
    try:
        save_observation(payload)
    except (OSError, ValueError) as exc:
        # A diagnostic sink cannot change a scientific result or receipt decision.
        print(f"Avereth telemetry was not saved: {exc}", file=sys.stderr)


@dataclass(frozen=True)
class HostTelemetry:
    run_id: str
    host: str
    model_revision: str
    started_at: str
    wall_time_seconds: float
    events: list[Any]
    raw_stdout: str
    raw_stderr: str
    status: str
    failure_type: str | None
    context_id: str | None
    measurements: dict[str, Any]
    prompt_sha256: str
    invalid_event_lines: int
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "avereth-host-telemetry/v1", "authority": "diagnostic_only",
                "operation": "isolated_generation",
                "parent_operation": os.environ.get("AVERETH_TELEMETRY_PARENT_OPERATION"),
                "experiment_run_id": os.environ.get("AVERETH_TELEMETRY_RUN_ID"), **asdict(self)}


class HostObservation:
    def __init__(self, host: str, model_revision: str, prompt: str):
        self.host, self.model_revision = host, model_revision
        self.run_id = host.upper() + "-RUN-" + uuid.uuid4().hex
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.started = time.monotonic()
        self.prompt_sha256 = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.stdout = self.stderr = ""
        self.result: HostTelemetry | None = None

    def __enter__(self):
        return self

    def process_result(self, completed: subprocess.CompletedProcess) -> None:
        self.stdout, self.stderr = _decoded(completed.stdout), _decoded(completed.stderr)

    def finish(self, *, context_id: str | None = None, status: str = "completed",
               failure_type: str | None = None, failure_reason: str | None = None) -> HostTelemetry:
        events, invalid = parse_events(self.stdout)
        elapsed = time.monotonic() - self.started
        measurements = host_measurements(self.host, events, complete=status == "completed" and not invalid)
        measurements["wall_time_seconds"] = elapsed
        self.result = HostTelemetry(
            self.run_id, self.host, self.model_revision, self.started_at, elapsed,
            events, self.stdout, self.stderr, status, failure_type, context_id,
            measurements, self.prompt_sha256, invalid, failure_reason,
        )
        return self.result

    def __exit__(self, exc_type, exc, traceback):
        if exc is not None:
            cause = exc.__cause__ or exc
            if isinstance(cause, subprocess.TimeoutExpired):
                self.stdout, self.stderr = _decoded(cause.stdout), _decoded(cause.stderr)
                self.finish(status="interrupted", failure_type="timeout", failure_reason=str(exc))
            elif isinstance(cause, KeyboardInterrupt):
                self.finish(status="interrupted", failure_type="cancelled", failure_reason="Host invocation interrupted")
            else:
                self.finish(status="failed", failure_type=type(cause).__name__, failure_reason=str(exc))
        elif self.result is None:
            self.finish(status="failed", failure_type="missing_result")
        emit_observation(self.result.to_dict())
        return False
