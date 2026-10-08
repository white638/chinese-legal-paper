"""The sole eight-state artifact spine for the local research engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import meaningful_file, report_passed, semantic_digest
from .models import ArtifactSpec, Finding, GateResult, WorkflowStatus
from .workflow_registry import (
    ARTIFACT_DEFINITIONS,
    LEGACY_STAGE_ALIASES,
    STAGE_ORDER as STAGES,
    TASK_PROFILE_TERMINALS,
    build_variant_specs,
    stage_artifact_specs,
)


def canonical_stage(stage: str) -> str:
    return LEGACY_STAGE_ALIASES.get(stage, stage)


def _base_stage_specs(stage: str, config: dict[str, Any] | None = None) -> tuple[ArtifactSpec, ...]:
    stage = canonical_stage(stage)
    active = dict(config or {})
    specs = stage_artifact_specs(stage)
    if stage == "audit" and str((config or {}).get("scene") or "").strip().lower() not in {
        "journal",
        "conference",
        "competition",
    }:
        specs = tuple(
            spec
            for spec in specs
            if spec.path not in {"results_validation.md", "results_validation_check.md"}
        )
    if stage != "build":
        return specs
    explicit = str(
        active.get("canonical_manuscript")
        or active.get("citation_audit_manuscript")
        or ""
    ).strip()
    if explicit:
        specs = tuple(
            ArtifactSpec(explicit, description="canonical manuscript source")
            if spec.description == "canonical manuscript source"
            else spec
            for spec in specs
        )
    profile = str(active.get("task_profile") or "full_paper").strip().lower().replace("-", "_")
    reopen = str(active.get("earliest_reopen_stage") or "").strip().lower().replace("-", "_")
    if profile == "manuscript_audit" or (profile == "manuscript_revision" and reopen == "build"):
        return tuple(
            spec for spec in specs if spec.description == "canonical manuscript source"
        )
    workflow = str(active.get("workflow") or "rewrite_existing").strip().lower()
    return specs + build_variant_specs(workflow)


def stage_specs(stage: str, config: dict[str, Any] | None = None) -> tuple[ArtifactSpec, ...]:
    specs = _base_stage_specs(stage, config)
    if (config or {}).get("legal_profile") == "chinese-law-v1":
        if not (stage == "design" and (config or {}).get("task_profile") == "manuscript_audit"):
            specs += tuple(row.as_spec() for row in ARTIFACT_DEFINITIONS
                           if row.domain_profile == "chinese-law-v1" and row.owner_stage == canonical_stage(stage))
    return specs


def _present(outdir: Path, spec: ArtifactSpec) -> str | None:
    for relative in spec.candidates:
        path = outdir / relative
        if meaningful_file(path) if spec.meaningful else path.exists():
            return relative
    return None


def inspect_stage(outdir: Path, stage: str, config: dict[str, Any] | None = None) -> GateResult:
    stage = canonical_stage(stage)
    if stage not in STAGES:
        return GateResult.fail(stage, [Finding("STAGE.UNKNOWN", f"unknown stage: {stage}")])
    findings: list[Finding] = []
    present: list[str] = []
    for spec in stage_specs(stage, config):
        relative = _present(outdir, spec)
        if relative is None:
            label = " or ".join(spec.candidates)
            findings.append(
                Finding(
                    "ARTIFACT.MISSING",
                    f"required {spec.description or 'artifact'} is missing: {label}",
                    spec.path,
                )
            )
            continue
        present.append(relative)
        if spec.report_must_pass and not report_passed(outdir / relative):
            findings.append(
                Finding(
                    "REPORT.NOT_PASS",
                    f"{relative} must contain one unambiguous terminal Status: PASS",
                    relative,
                )
            )
    if findings:
        return GateResult.fail(stage, findings)
    return GateResult.pass_(stage, semantic_digest=semantic_digest(outdir, present))


def _inspect_artifact_workflow(
    outdir: Path,
    config: dict[str, Any] | None = None,
    *,
    terminal_stage: str = "output",
) -> WorkflowStatus:
    """Private artifact diagnostic; public progress lives in cli.status_payload."""
    status = WorkflowStatus()
    terminal_index = STAGES.index(terminal_stage) if terminal_stage in STAGES else len(STAGES) - 1
    for stage in STAGES[: terminal_index + 1]:
        result = inspect_stage(outdir, stage, config)
        status.stages[stage] = result
        if not result.ok:
            status.next_stage = stage
            status.findings.extend(result.findings)
            return status
    status.next_stage = "complete"
    status.is_complete = True
    return status
