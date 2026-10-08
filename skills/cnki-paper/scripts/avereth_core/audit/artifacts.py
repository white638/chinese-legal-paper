"""Eight-state artifact consistency audit.

This replaces the old all-deliverables artifact checker during the academic
audit phase.  Rendered PDF/DOCX and submission packages belong to output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..build.manuscript import ManuscriptSelectionError, select_manuscript
from ..models import Finding, GateResult
from ..stages import STAGES, inspect_stage


def _token(value: object) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _canonical_source(outdir: Path, config: dict[str, Any]) -> Path | None:
    try:
        return select_manuscript(outdir, config).path
    except ManuscriptSelectionError:
        return None


def _applicable_prerequisites(config: dict[str, Any]) -> tuple[str, ...]:
    profile = _token(config.get("task_profile") or "full_paper")
    if profile == "manuscript_audit":
        return ("intake", "acquisition")
    if profile == "manuscript_revision":
        reopen = _token(config.get("earliest_reopen_stage"))
        # The authoritative value normally lives in revision_contract.json;
        # the status gate validates that contract before run_all.  This local
        # audit stays conservative if the route is not repeated in config.
        if reopen not in {"research", "design", "execution", "build"}:
            return ("intake", "build")
        start = STAGES.index(reopen)
        stages = list(STAGES[start : STAGES.index("audit")])
        if reopen == "research":
            stages.insert(0, "acquisition")
        return ("intake", *stages)
    return tuple(STAGES[: STAGES.index("audit")])


def audit_artifacts(outdir: Path, config: dict[str, Any] | None = None) -> GateResult:
    active = dict(config or {})
    findings: list[Finding] = []
    for stage in _applicable_prerequisites(active):
        result = inspect_stage(outdir, stage, active)
        if not result.ok:
            findings.extend(result.findings)

    if _canonical_source(outdir, active) is None:
        findings.append(
            Finding(
                "ARTIFACT.CANONICAL_MANUSCRIPT",
                "declare exactly one non-empty canonical manuscript source inside the workspace",
                "final_paper",
            )
        )

    nested = outdir / "paper_rewriting_output"
    if nested.is_dir():
        findings.append(
            Finding(
                "ARTIFACT.NESTED_OUTPUT",
                "a nested paper_rewriting_output directory would create two artifact roots",
                "paper_rewriting_output",
            )
        )

    if findings:
        return GateResult.fail("audit", findings)
    return GateResult.pass_("audit")


def render_markdown(result: GateResult) -> str:
    lines = [
        "# Avereth Artifact Check",
        "",
        f"Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "Scope: canonical research, design, execution, build, and manuscript-source artifacts.",
        "Rendered delivery files are checked by the output gate.",
    ]
    if result.findings:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(
            f"- [{finding.code}] {finding.message}"
            + (f" (`{finding.artifact}`)" if finding.artifact else "")
            for finding in result.findings
        )
    lines.append("")
    return "\n".join(lines)


def run(outdir: Path, config: dict[str, Any] | None = None, *, write: bool = True) -> GateResult:
    result = audit_artifacts(outdir, config)
    if write:
        (outdir / "artifact_check.md").write_text(render_markdown(result), encoding="utf-8")
    return result
