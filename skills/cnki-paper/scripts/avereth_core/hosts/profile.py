"""Resolve the build-selected host profile and its runner capabilities."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


PROFILE_SCHEMA_VERSION = "avereth-host-profile/v1"
CAPABILITIES = {
    "codex": {
        "default_runner": "codex-exec",
        "allowed_runners": ("codex-exec",),
    },
    "claude": {
        "default_runner": "claude-exec",
        "allowed_runners": ("claude-exec", "agent-declared"),
    },
}
ALL_RUNNERS = tuple(
    sorted({runner for value in CAPABILITIES.values() for runner in value["allowed_runners"]})
)


def profile_path() -> Path:
    return Path(__file__).resolve().parents[3] / "host_profile.json"


def active_host_profile() -> dict[str, Any]:
    path = profile_path()
    if path.is_file():
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or payload.get("schema_version") != PROFILE_SCHEMA_VERSION:
            raise ValueError(f"invalid Avereth host profile: {path}")
        host_id = payload.get("host_id")
    else:
        host_id = os.environ.get("AVERETH_HOST", "codex").strip().lower()
        payload = {"schema_version": PROFILE_SCHEMA_VERSION, "host_id": host_id}
    if host_id not in CAPABILITIES:
        raise ValueError(f"unsupported Avereth host profile: {host_id!r}")
    expected = CAPABILITIES[host_id]
    declared_default = payload.get("default_runner", expected["default_runner"])
    declared_allowed = tuple(payload.get("allowed_runners", expected["allowed_runners"]))
    if declared_default != expected["default_runner"] or declared_allowed != expected["allowed_runners"]:
        raise ValueError("Avereth host profile runner capabilities do not match the runtime contract")
    return {
        **payload,
        "default_runner": declared_default,
        "allowed_runners": declared_allowed,
    }


def active_host_id() -> str:
    return str(active_host_profile()["host_id"])


def default_host_runner() -> str:
    return str(active_host_profile()["default_runner"])


def ensure_runner_allowed(runner: str) -> str:
    normalized = runner.strip().lower()
    profile = active_host_profile()
    if normalized not in profile["allowed_runners"]:
        raise ValueError(
            f"runner {normalized!r} is unavailable for host {profile['host_id']!r}; "
            f"allowed: {', '.join(profile['allowed_runners'])}"
        )
    return normalized
