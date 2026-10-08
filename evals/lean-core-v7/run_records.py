"""Shared local evidence and numeric validation for run reports."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected an object: {path}")
    return payload


def evidence_valid(evidence: object, root: Path) -> bool:
    if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str):
        return False
    try:
        path = (root / evidence["path"]).resolve()
        return (path.is_relative_to(root.resolve()) and path.is_file() and bool(path.stat().st_size)
                and hashlib.sha256(path.read_bytes()).hexdigest() == evidence.get("sha256"))
    except OSError:
        return False


def bind_file(root: Path, raw: str) -> dict:
    path = (root / raw).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file() or not path.stat().st_size:
        raise ValueError(f"evidence must be a nonempty file inside the run root: {raw}")
    return {"path": path.relative_to(root.resolve()).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def number(value: object, *, quality: bool = False) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 <= value and (not quality or value <= 4))


def selection_bindings(manifest: dict) -> dict:
    from selection import validate_selection
    selected = validate_selection(manifest)
    return {key: selected[key] for key in ("selection_sha256", "bank_sha256")} if selected else {}


def selection_issues(manifest: dict, run: dict) -> list[str]:
    expected = selection_bindings(manifest)
    return [f"run does not bind selected {key}" for key in ("selection_sha256", "bank_sha256")
            if run.get(key) != expected.get(key)]


def required_hard_checks(task: dict, defaults=()) -> tuple[str, ...]:
    declared = task.get("hard_checks", [])
    if not isinstance(declared, list) or any(not isinstance(item, str) or not item for item in declared):
        raise ValueError("case hard_checks must be a list of nonempty identifiers")
    return tuple(dict.fromkeys([*defaults, *declared]))
