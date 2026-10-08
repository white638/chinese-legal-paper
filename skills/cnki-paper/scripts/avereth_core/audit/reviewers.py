"""Semantic postcondition for the JSON-authoritative review lifecycle."""

from __future__ import annotations

from pathlib import Path

from ..models import Finding, GateResult
from ..tools.review_lifecycle import default_manuscript, validate_lifecycle


def validate(outdir: Path, manuscript: Path | None = None) -> GateResult:
    manuscript = (manuscript or default_manuscript(outdir)).resolve()
    result = validate_lifecycle(outdir.resolve(), manuscript, require_views=True)
    findings = [
        Finding(
            "REVIEW.LIFECYCLE",
            issue,
            "review_findings.json/review_resolution.json",
        )
        for issue in result.findings
    ]
    return GateResult.fail("audit", findings) if findings else GateResult.pass_("audit")
