"""Two-phase declared-provenance capture for fresh Claude Code subagents."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any, Mapping

from .base import HostCapture, schema_instruction, strip_json_fence, text


SCHEMA_VERSION = "avereth-agent-declared-capture/v1"
MANIFEST_NAME = "manifest.json"


class AgentResponsesPending(Exception):
    """Raised after prompt emission while fresh-subagent responses are pending."""

    def __init__(self, request_dir: Path) -> None:
        super().__init__(
            "agent-declared capture request emitted; spawn one fresh subagent per "
            f"prompt under {request_dir}, save each raw JSON reply and real context "
            "id, then rerun the same command with --responses"
        )
        self.request_dir = request_dir


def _load_manifest(directory: Path) -> dict[str, Any]:
    path = directory / MANIFEST_NAME
    if not path.is_file():
        return {"schema_version": SCHEMA_VERSION, "model_revision": "", "steps": {}}
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != SCHEMA_VERSION
        or not isinstance(payload.get("steps"), dict)
    ):
        raise ValueError("agent-declared capture manifest is invalid")
    return payload


def _bound_manifest_path(
    directory: Path,
    *,
    step: str,
    entry: Mapping[str, Any],
    field: str,
    suffix: str,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", step):
        raise ValueError("agent-declared capture manifest has an invalid step name")
    expected = f"{step}{suffix}"
    if text(entry.get(field)) != expected:
        raise ValueError(
            f"agent-declared capture manifest path binding is invalid: {field}"
        )
    path = (directory / expected).resolve()
    if path.parent != directory or path.name != expected:
        raise ValueError(
            f"agent-declared capture manifest path escapes its directory: {field}"
        )
    return path


def write_agent_capture_request(
    directory: Path,
    *,
    step: str,
    prompt: str,
    output_schema: Mapping[str, Any],
    model_revision: str,
) -> Path:
    """Write one canonical prompt and bind it into the capture manifest."""

    step_slug = re.sub(r"[^A-Za-z0-9_-]", "-", text(step))
    if not step_slug:
        raise ValueError("agent-declared capture step name is required")
    if len(text(model_revision)) < 3:
        raise ValueError("agent-declared capture requires an explicit model revision")
    if not isinstance(output_schema, Mapping):
        raise ValueError("agent-declared capture requires a controlled output schema")
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    manifest = _load_manifest(directory)
    if manifest["steps"] and text(manifest.get("model_revision")) != text(model_revision):
        raise ValueError(
            "agent-declared capture directory already targets another model revision"
        )
    manifest["model_revision"] = text(model_revision)
    schema_text = json.dumps(output_schema, ensure_ascii=False, indent=2)
    prompt_path = directory / f"{step_slug}.prompt.md"
    prompt_path.write_text(
        prompt + "\n\n" + schema_instruction(schema_text) + "\n",
        encoding="utf-8",
    )
    manifest["steps"][step_slug] = {
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_path": prompt_path.name,
        "response_path": f"{step_slug}.response.json",
        "context_path": f"{step_slug}.context.txt",
    }
    (directory / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return prompt_path


def read_agent_capture(
    directory: Path,
    *,
    prompt: str,
    model_revision: str,
) -> HostCapture:
    """Load a response only when it matches the exact canonical prompt and model."""

    directory = Path(directory).resolve()
    manifest = _load_manifest(directory)
    if not manifest["steps"]:
        raise ValueError("agent-declared capture manifest has no emitted prompts")
    if text(manifest.get("model_revision")) != text(model_revision):
        raise ValueError(
            "agent-declared responses were emitted for a different model revision"
        )
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    matched_step = ""
    matched: Mapping[str, Any] | None = None
    for step, entry in manifest["steps"].items():
        if isinstance(entry, Mapping) and text(entry.get("prompt_sha256")) == digest:
            matched_step = step
            matched = entry
            break
    if matched is None:
        raise ValueError(
            "agent-declared responses do not cover the current canonical prompt; "
            "re-emit prompts because the packet, portfolio, or materials changed"
        )
    prompt_path = _bound_manifest_path(
        directory,
        step=matched_step,
        entry=matched,
        field="prompt_path",
        suffix=".prompt.md",
    )
    response_path = _bound_manifest_path(
        directory,
        step=matched_step,
        entry=matched,
        field="response_path",
        suffix=".response.json",
    )
    context_path = _bound_manifest_path(
        directory,
        step=matched_step,
        entry=matched,
        field="context_path",
        suffix=".context.txt",
    )
    if not prompt_path.is_file():
        raise ValueError(f"agent-declared prompt is missing: {prompt_path.name}")
    emitted_prompt = prompt_path.read_text(encoding="utf-8-sig")
    if not emitted_prompt.startswith(prompt + "\n\n"):
        raise ValueError(
            f"agent-declared prompt no longer matches its manifest: {prompt_path.name}"
        )
    if not response_path.is_file():
        raise ValueError(f"agent-declared response is missing: {response_path.name}")
    if not context_path.is_file():
        raise ValueError(f"agent-declared context id is missing: {context_path.name}")
    raw_text = strip_json_fence(response_path.read_text(encoding="utf-8-sig"))
    try:
        json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"agent-declared response is not valid JSON: {response_path.name}"
        ) from exc
    context_id = text(context_path.read_text(encoding="utf-8-sig").strip())
    if len(context_id) < 3:
        raise ValueError(f"agent-declared context id is missing: {context_path.name}")
    return HostCapture(
        raw_output=raw_text.encode("utf-8"),
        run_id=f"AGENT-DECLARED-{matched_step}-" + uuid.uuid4().hex,
        model_revision=text(model_revision),
        context_id=context_id,
    )
