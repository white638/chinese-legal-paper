"""Local build action: promote, validate, and bind the canonical manuscript."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..artifacts import semantic_digest, sha256_file
from ..config import read_config
from ..models import Finding, GateResult
from ..stages import stage_specs, inspect_stage
from ..version import VERSION
from .manuscript import (
    ManuscriptSelection,
    ManuscriptSelectionError,
    PreparedManuscript,
    prepare_manuscript,
    select_manuscript,
)
from .manuscript_compiler import compiler_applies, implementation_paths, validate_workspace


BUILD_RUN_REL = Path("build_run.json")
BUILD_RUN_SCHEMA = "avereth-build-run/v1"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _artifact_paths(outdir: Path, config: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for spec in stage_specs("build", config):
        for candidate in spec.candidates:
            path = outdir / candidate
            if path.is_file() and path.stat().st_size > 0:
                paths.append(candidate)
                break
    return paths


def _implementation_binding(content_validator: Path | None = None) -> dict[str, str]:
    binding = {
        "build/run.py": sha256_file(Path(__file__)),
        "build/manuscript.py": sha256_file(Path(__file__).with_name("manuscript.py")),
    }
    for path in implementation_paths():
        try:
            relative = path.relative_to(Path(__file__).resolve().parents[3]).as_posix()
        except ValueError:
            relative = path.name
        binding[f"manuscript-compiler/{relative}"] = sha256_file(path) if path.is_file() else ""
    if content_validator is not None:
        binding["codex_cnki_gate.py"] = (
            sha256_file(content_validator) if content_validator.is_file() else ""
        )
    return binding


def _manuscript_compiler_status(outdir: Path, config: dict[str, Any]) -> GateResult:
    if not compiler_applies(config):
        return GateResult.pass_("build")
    issues = validate_workspace(outdir, config)
    if not issues:
        return GateResult.pass_("build")
    return GateResult.fail(
        "build",
        [
            Finding(
                "BUILD.MANUSCRIPT." + issue.code.removeprefix("MS-").replace("-", "."),
                issue.message,
                issue.path or None,
            )
            for issue in issues
        ],
    )


def build_run_status(
    outdir: Path,
    config: dict[str, Any] | None = None,
    *,
    content_validator: Path | None = None,
) -> GateResult:
    active = dict(config if config is not None else read_config(outdir).payload)
    manuscript_result = _manuscript_compiler_status(outdir, active)
    if not manuscript_result.ok:
        return manuscript_result
    path = outdir / BUILD_RUN_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return GateResult.fail(
            "build",
            [Finding("BUILD.RUN_MISSING", "run the local build gate to bind the canonical manuscript", BUILD_RUN_REL.as_posix())],
        )
    try:
        selection = select_manuscript(outdir, active)
    except ManuscriptSelectionError as exc:
        return GateResult.fail("build", [Finding("BUILD.CANONICAL", str(exc))])
    current_paths = _artifact_paths(outdir, active)
    current_digest = semantic_digest(outdir, current_paths)
    findings: list[Finding] = []
    if payload.get("schema_version") != BUILD_RUN_SCHEMA or payload.get("status") != "PASS":
        findings.append(Finding("BUILD.RUN_INVALID", "build_run.json is not a v6 PASS run", BUILD_RUN_REL.as_posix()))
    if payload.get("framework_version") != VERSION:
        findings.append(Finding("BUILD.VERSION_CHANGED", "build run belongs to another engine version", BUILD_RUN_REL.as_posix()))
    if payload.get("action_implementation") != _implementation_binding(content_validator):
        findings.append(Finding("BUILD.IMPLEMENTATION_CHANGED", "build implementation changed after the run", BUILD_RUN_REL.as_posix()))
    if payload.get("canonical_manuscript") != selection.as_dict():
        findings.append(Finding("BUILD.CANONICAL_CHANGED", "canonical manuscript changed after the local build run", selection.relative_path))
    if payload.get("artifact_digest") != current_digest:
        findings.append(Finding("BUILD.ARTIFACTS_CHANGED", "build-bearing artifacts changed after the local build run", BUILD_RUN_REL.as_posix()))
    draft_raw = str(active.get("draft_path") or "").strip()
    current_draft: dict[str, str] = {}
    if draft_raw:
        draft = Path(draft_raw)
        draft = draft if draft.is_absolute() else outdir / draft
        try:
            resolved = draft.resolve()
            relative = resolved.relative_to(outdir.resolve()).as_posix()
        except (OSError, ValueError):
            relative = ""
        if relative and resolved.is_file():
            current_draft = {"path": relative, "sha256": sha256_file(resolved)}
    if payload.get("source_draft", {}) != current_draft:
        findings.append(Finding("BUILD.DRAFT_CHANGED", "registered draft authority changed after the local build run", draft_raw or None))
    return GateResult.fail("build", findings) if findings else GateResult.pass_("build", semantic_digest=current_digest)


def prepare_build(
    outdir: Path,
    *,
    config: dict[str, Any] | None = None,
) -> tuple[GateResult, PreparedManuscript | None]:
    active = dict(config if config is not None else read_config(outdir).payload)
    try:
        prepared = prepare_manuscript(outdir, active)
    except ManuscriptSelectionError as exc:
        return GateResult.fail("build", [Finding("BUILD.CANONICAL", str(exc))]), None
    manuscript_result = _manuscript_compiler_status(outdir, active)
    if not manuscript_result.ok:
        return manuscript_result, prepared
    artifact_result = inspect_stage(outdir, "build", active)
    if not artifact_result.ok:
        return artifact_result, prepared
    return GateResult.pass_("build"), prepared


def record_build(
    outdir: Path,
    selection: ManuscriptSelection,
    *,
    config: dict[str, Any] | None = None,
    content_validator: Path | None = None,
) -> GateResult:
    active = dict(config if config is not None else read_config(outdir).payload)
    manuscript_result = _manuscript_compiler_status(outdir, active)
    if not manuscript_result.ok:
        return manuscript_result
    artifact_result = inspect_stage(outdir, "build", active)
    if not artifact_result.ok:
        return artifact_result
    paths = _artifact_paths(outdir, active)
    digest = semantic_digest(outdir, paths)
    payload: dict[str, Any] = {
        "schema_version": BUILD_RUN_SCHEMA,
        "framework_version": VERSION,
        "status": "PASS",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "canonical_manuscript": selection.as_dict(),
        "source_draft": {},
        "artifact_digest": digest,
        "action_implementation": _implementation_binding(content_validator),
        "artifacts": [
            {"path": relative, "sha256": sha256_file(outdir / relative)}
            for relative in sorted(paths)
        ],
    }
    draft_raw = str(active.get("draft_path") or "").strip()
    if draft_raw:
        draft = Path(draft_raw)
        draft = draft if draft.is_absolute() else outdir / draft
        try:
            resolved = draft.resolve()
            relative = resolved.relative_to(outdir.resolve()).as_posix()
        except (OSError, ValueError):
            relative = ""
        if relative and resolved.is_file():
            payload["source_draft"] = {"path": relative, "sha256": sha256_file(resolved)}
    _atomic_json(outdir / BUILD_RUN_REL, payload)
    return GateResult.pass_("build", generated=(BUILD_RUN_REL.as_posix(),), semantic_digest=digest)


def run_build(outdir: Path, *, config: dict[str, Any] | None = None) -> GateResult:
    """Prepare and record a build for direct callers.

    The controller uses ``prepare_build`` and ``record_build`` around its
    shared content validator so a failed gate never leaves a PASS run.
    """

    result, prepared = prepare_build(outdir, config=config)
    if not result.ok or prepared is None:
        return result
    recorded = record_build(outdir, prepared.selection, config=config)
    if not recorded.ok:
        from .manuscript import rollback_preparation

        rollback_preparation(prepared)
    return recorded
