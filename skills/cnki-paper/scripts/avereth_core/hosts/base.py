"""Host-generation contracts shared by the Avereth runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .telemetry import HostTelemetry


@dataclass(frozen=True)
class HostCapture:
    """Raw host output plus the provenance needed by controller receipts."""

    raw_output: bytes
    run_id: str
    model_revision: str
    context_id: str
    telemetry: HostTelemetry | None = None


class GenerationAdapter(Protocol):
    """Minimal interface implemented by every host capture adapter."""

    host_id: str
    provenance_mode: str

    def capture(
        self,
        *,
        prompt: str,
        output_schema: Mapping[str, Any],
        model_revision: str,
        timeout_seconds: int,
    ) -> HostCapture:
        ...


def text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def event_uses_tool(value: Any) -> bool:
    forbidden = (
        "tool_call",
        "tool_use",
        "command_execution",
        "shell",
        "mcp_call",
        "web_search",
        "image_generation",
        "computer_use",
    )
    if isinstance(value, Mapping):
        for key, item in value.items():
            if key in {"type", "name", "kind"} and isinstance(item, str):
                token = item.casefold()
                if any(marker in token for marker in forbidden):
                    return True
            if event_uses_tool(item):
                return True
    elif isinstance(value, list):
        return any(event_uses_tool(item) for item in value)
    return False


def event_context_id(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in (
            "session_id",
            "sessionId",
            "thread_id",
            "threadId",
            "context_id",
            "contextId",
        ):
            if text(value.get(key)):
                return text(value.get(key))
        for item in value.values():
            found = event_context_id(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = event_context_id(item)
            if found:
                return found
    return ""


def strip_json_fence(value: str) -> str:
    rendered = value.strip()
    if rendered.startswith("```"):
        first_break = rendered.find("\n")
        if first_break != -1 and rendered.rstrip().endswith("```"):
            rendered = rendered[first_break + 1 :].rstrip()
            rendered = rendered[: rendered.rfind("```")].strip()
    return rendered


def schema_instruction(schema_text: str) -> str:
    return (
        "Respond with ONLY a JSON value that validates against this JSON Schema. "
        "Do not add a Markdown fence, commentary, or any text outside the JSON value.\n"
        + schema_text
    )
