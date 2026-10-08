#!/usr/bin/env python3
"""Validate the canonical peer-review lifecycle, never hand-written Markdown."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import review_lifecycle


@dataclass
class ReviewerAuditResult:
    path: str
    manuscript: str
    ok: bool
    review_run_id: str = ""
    registry_status: str = "missing"
    recommendation: str = "BLOCK"
    finding_count: int = 0
    effective_earliest_reopen_stage: str | None = None
    route_action: str = "none"
    findings: list[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate review_findings.json and review_resolution.json."
    )
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--manuscript")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def validate(output_dir: Path, manuscript: Path | None = None) -> ReviewerAuditResult:
    manuscript = (manuscript or review_lifecycle.default_manuscript(output_dir)).resolve()
    lifecycle = review_lifecycle.validate_lifecycle(
        output_dir.resolve(), manuscript, require_views=True
    )
    metrics: dict[str, Any] = lifecycle.metrics
    route = metrics.get("review_route") if isinstance(metrics.get("review_route"), dict) else {}
    return ReviewerAuditResult(
        path=str((output_dir / "review_resolution.json").resolve()),
        manuscript=str(manuscript),
        ok=lifecycle.ok,
        review_run_id=str(metrics.get("review_run_id") or ""),
        registry_status=str(metrics.get("registry_status") or "missing"),
        recommendation=str(metrics.get("recommendation") or "BLOCK"),
        finding_count=int(metrics.get("finding_count", 0) or 0),
        effective_earliest_reopen_stage=(
            str(route.get("effective_earliest_reopen_stage"))
            if route.get("effective_earliest_reopen_stage")
            else None
        ),
        route_action=str(route.get("action") or "none"),
        findings=list(lifecycle.findings),
    )


def to_markdown(result: ReviewerAuditResult) -> str:
    lines = [
        "# Reviewer Audit Check",
        "",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Review run: `{result.review_run_id or 'missing'}`",
        f"- Registry status: `{result.registry_status}`",
        f"- Lifecycle recommendation: `{result.recommendation}`",
        f"- Finding count: `{result.finding_count}`",
        f"- Effective earliest reopen stage: `{result.effective_earliest_reopen_stage or 'none'}`",
        f"- Route action: `{result.route_action}`",
        f"- Canonical resolution: `{result.path}`",
        f"- Current manuscript: `{result.manuscript}`",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in result.findings)
    if not result.findings:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    manuscript = Path(args.manuscript).resolve() if args.manuscript else None
    result = validate(output_dir, manuscript)
    markdown = to_markdown(result)
    if args.write:
        report_path = output_dir / "reviewer_audit_check.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = report_path.with_suffix(report_path.suffix + ".tmp")
        temporary.write_text(markdown, encoding="utf-8", newline="\n")
        temporary.replace(report_path)
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
