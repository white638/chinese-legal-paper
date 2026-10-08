#!/usr/bin/env python3
"""Check downstream result eligibility from canonical method execution.

``method_execution.json`` and its full v3 validator own result truth.  The
human-readable ``results_validation.md`` file is only a rebuildable explanatory
view; its rows, claim labels, and numbers can never create downstream
eligibility.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping


_METHOD_EXECUTION_MODULE: Any | None = None


@dataclass
class ResultsValidationResult:
    path: str
    ok: bool
    row_count: int
    mapped_rows: int
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    authority_path: str = ""
    projection_status: str = "BLOCKED"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check canonical method-execution results permitted for downstream use."
    )
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Rebuild results_validation.md from canonical downstream eligibility "
            "and write results_validation_check.md beside it."
        ),
    )
    return parser.parse_args()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _method_execution_module() -> Any:
    """Load the one execution authority without copying its validation logic."""
    global _METHOD_EXECUTION_MODULE
    if _METHOD_EXECUTION_MODULE is not None:
        return _METHOD_EXECUTION_MODULE
    path = (
        Path(__file__).resolve().parents[4]
        / "empirical-research"
        / "scripts"
        / "method_execution.py"
    )
    module_name = "avereth_method_execution_authority"
    if module_name in sys.modules:
        _METHOD_EXECUTION_MODULE = sys.modules[module_name]
        return _METHOD_EXECUTION_MODULE
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load execution authority from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _METHOD_EXECUTION_MODULE = module
    return module


def _projection_issue_lines(projection: Mapping[str, Any]) -> list[str]:
    lines: list[str] = []
    issues = projection.get("issues")
    if not isinstance(issues, list):
        return lines
    for item in issues:
        if not isinstance(item, Mapping):
            continue
        code = _text(item.get("code")) or "ME.ELIGIBILITY.BLOCKED"
        message = _text(item.get("message")) or "canonical validation rejected the execution contract"
        path = _text(item.get("path"))
        location = f" [{path}]" if path else ""
        lines.append(f"{code}{location}: {message}")
    return lines


def canonical_projection(workspace: Path) -> Mapping[str, Any]:
    """Return one fail-closed snapshot from the canonical execution authority."""
    try:
        projection = _method_execution_module().downstream_eligibility(Path(workspace))
    except Exception as exc:
        return {
            "schema_version": "cnki-downstream-eligibility/error",
            "execution_schema_version": "",
            "status": "BLOCKED",
            "issues": [
                {
                    "code": "ME.ELIGIBILITY.VALIDATOR_FAILURE",
                    "severity": "ERROR",
                    "message": (
                        "Canonical downstream eligibility could not be computed: "
                        f"{exc}"
                    ),
                    "path": "method_execution.json",
                }
            ],
            "results": {},
        }
    if isinstance(projection, Mapping):
        return projection
    return {
        "schema_version": "cnki-downstream-eligibility/error",
        "execution_schema_version": "",
        "status": "BLOCKED",
        "issues": [
            {
                "code": "ME.ELIGIBILITY.PROJECTION_MALFORMED",
                "severity": "ERROR",
                "message": "Canonical downstream eligibility returned a non-object projection.",
                "path": "method_execution.json",
            }
        ],
        "results": {},
    }


def _projection_record_findings(result_id: str, record: Mapping[str, Any]) -> list[str]:
    """Check identity completeness, not execution truth, in a projected record."""
    findings: list[str] = []
    prefix = f"Canonical result {result_id}"
    if _text(record.get("result_id")).upper() != result_id:
        findings.append(f"{prefix} has a mismatched result_id field.")

    allowed_uses = record.get("allowed_uses")
    if not isinstance(allowed_uses, list):
        findings.append(f"{prefix} has a malformed allowed_uses list.")
        return findings
    normalized_uses = {_text(value).lower() for value in allowed_uses if _text(value)}
    if not normalized_uses:
        return findings

    identity_lists: dict[str, list[str]] = {}
    for field_name in ("claim_ids", "action_ids", "artifact_ids"):
        values = record.get(field_name)
        normalized = (
            [_text(value).upper() for value in values if _text(value)]
            if isinstance(values, list)
            else []
        )
        identity_lists[field_name] = normalized
        if not normalized:
            findings.append(
                f"{prefix} is downstream-eligible but has no canonical {field_name}."
            )

    claim_allowed = record.get("claim_allowed_uses")
    if not isinstance(claim_allowed, Mapping):
        findings.append(f"{prefix} has no claim-specific allowed-use mapping.")
    else:
        projected_union = {
            _text(use).lower()
            for claim_id in identity_lists["claim_ids"]
            for use in (
                claim_allowed.get(claim_id)
                if isinstance(claim_allowed.get(claim_id), list)
                else []
            )
            if _text(use)
        }
        if projected_union != normalized_uses:
            findings.append(
                f"{prefix} allowed_uses do not match its claim-specific licenses."
            )

    artifact_hashes = record.get("artifact_sha256")
    if not isinstance(artifact_hashes, Mapping):
        findings.append(f"{prefix} has no artifact SHA-256 mapping.")
    else:
        for artifact_id in identity_lists["artifact_ids"]:
            digest = _text(artifact_hashes.get(artifact_id))
            if not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
                findings.append(
                    f"{prefix} has no valid SHA-256 identity for artifact {artifact_id}."
                )

    attempts = record.get("action_attempts")
    if not isinstance(attempts, list):
        findings.append(f"{prefix} has no canonical action-attempt records.")
    else:
        attempt_ids = {
            _text(item.get("id")).upper()
            for item in attempts
            if isinstance(item, Mapping) and _text(item.get("id"))
        }
        if attempt_ids != set(identity_lists["action_ids"]):
            findings.append(
                f"{prefix} action_ids do not match its current accepted action attempts."
            )
        for attempt in attempts:
            if not isinstance(attempt, Mapping):
                findings.append(f"{prefix} contains a malformed action-attempt record.")
                continue
            action_id = _text(attempt.get("id")).upper() or "<missing-action-id>"
            if (
                not _text(attempt.get("operation_id"))
                or not isinstance(attempt.get("attempt"), int)
                or _text(attempt.get("status")) != "accepted"
                or not re.fullmatch(
                    r"[0-9a-fA-F]{64}",
                    _text(attempt.get("parameter_snapshot_sha256")),
                )
            ):
                findings.append(
                    f"{prefix} action {action_id} lacks a complete accepted-attempt identity."
                )

    if not re.fullmatch(r"[0-9a-fA-F]{64}", _text(record.get("authority_digest"))):
        findings.append(f"{prefix} has no valid authority digest.")
    return findings


def _projection_integrity(
    projection: Mapping[str, Any],
) -> tuple[str, Mapping[str, Any], list[str], list[str]]:
    """Return status, records, eligible IDs, and fail-closed view findings."""
    projection_status = _text(projection.get("status")).upper() or "BLOCKED"
    if projection_status != "PASS":
        findings = [
            "Canonical method-execution validation is BLOCKED; a Markdown results view "
            "cannot override this decision."
        ]
        findings.extend(_projection_issue_lines(projection))
        return projection_status, {}, [], findings

    projected_results = projection.get("results")
    if not isinstance(projected_results, Mapping):
        return projection_status, {}, [], [
            "PASS projection has no results mapping; fail closed."
        ]

    findings: list[str] = []
    for field_name in (
        "design_sha256",
        "adapter_registry_sha256",
        "execution_sha256",
        "projection_digest",
    ):
        if not re.fullmatch(r"[0-9a-fA-F]{64}", _text(projection.get(field_name))):
            findings.append(
                f"PASS projection has no valid {field_name} authority identity."
            )

    eligible_result_ids: list[str] = []
    malformed_result_ids: list[str] = []
    for result_id, record in projected_results.items():
        normalized_id = _text(result_id).upper()
        if not normalized_id or not isinstance(record, Mapping):
            malformed_result_ids.append(normalized_id or "<missing-result-id>")
            continue
        findings.extend(_projection_record_findings(normalized_id, record))
        allowed_uses = {
            _text(value).lower()
            for value in (
                record.get("allowed_uses")
                if isinstance(record.get("allowed_uses"), list)
                else []
            )
            if _text(value)
        }
        if allowed_uses:
            eligible_result_ids.append(normalized_id)

    if malformed_result_ids:
        findings.append(
            "Canonical projection contains malformed result records: "
            + ", ".join(sorted(malformed_result_ids))
        )
    if not eligible_result_ids:
        findings.append(
            "Canonical projection contains no result with non-empty allowed_uses; "
            "there is nothing licensed for downstream reporting or claim support."
        )
    return projection_status, projected_results, eligible_result_ids, findings


def validate(
    results_path: Path,
    *,
    projection: Mapping[str, Any] | None = None,
) -> ResultsValidationResult:
    """Validate the workspace through the canonical downstream projection.

    ``results_path`` is retained as the public API because callers historically
    passed ``results_validation.md``.  Its parent is the workspace; the Markdown
    content is intentionally never parsed or treated as evidence.
    """
    results_path = Path(results_path)
    workspace = results_path.parent
    execution_path = workspace / "method_execution.json"
    findings: list[str] = []
    warnings: list[str] = []

    if results_path.is_file():
        warnings.append(
            "results_validation.md was treated only as a derived explanatory view; "
            "its rows, claim IDs, and numbers did not affect this decision."
        )
    else:
        warnings.append(
            "results_validation.md is absent; rebuild the optional explanatory view from "
            "the canonical eligibility projection."
        )

    if projection is None:
        projection = canonical_projection(workspace)

    (
        projection_status,
        projected_results,
        eligible_result_ids,
        integrity_findings,
    ) = _projection_integrity(projection)
    findings.extend(integrity_findings)

    return ResultsValidationResult(
        str(results_path),
        not findings,
        len(projected_results),
        len(eligible_result_ids),
        findings,
        warnings,
        str(execution_path),
        projection_status,
    )


def _md_cell(value: Any) -> str:
    text = _text(value)
    if not text:
        return "—"
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", "<br>")


def _identity_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({_text(value).upper() for value in values if _text(value)})


def _artifact_identities(record: Mapping[str, Any]) -> str:
    artifact_hashes = record.get("artifact_sha256")
    hashes = artifact_hashes if isinstance(artifact_hashes, Mapping) else {}
    identities = [
        f"{artifact_id}@{_text(hashes.get(artifact_id)) or '<missing-sha256>'}"
        for artifact_id in _identity_list(record.get("artifact_ids"))
    ]
    return "<br>".join(identities) or "—"


def render_results_validation(projection: Mapping[str, Any]) -> str:
    """Render the sole rebuildable results view from one canonical projection."""
    (
        projection_status,
        projected_results,
        eligible_result_ids,
        findings,
    ) = _projection_integrity(projection)
    view_status = "PASS" if projection_status == "PASS" and not findings else "BLOCKED"
    lines = [
        "# Results Validation",
        "",
        "> Rebuildable explanatory view. Canonical authority remains "
        "`method_execution.downstream_eligibility`; editing this Markdown cannot "
        "create or change downstream eligibility.",
        "",
        f"- Derived view status: **{view_status}**",
        f"- Canonical projection status: **{projection_status}**",
        f"- Projection schema: `{_text(projection.get('schema_version')) or '<missing>'}`",
        f"- Execution schema: `{_text(projection.get('execution_schema_version')) or '<missing>'}`",
        f"- Design SHA-256: `{_text(projection.get('design_sha256')) or '<missing>'}`",
        f"- Adapter registry SHA-256: `{_text(projection.get('adapter_registry_sha256')) or '<missing>'}`",
        f"- Execution SHA-256: `{_text(projection.get('execution_sha256')) or '<missing>'}`",
        f"- Projection SHA-256: `{_text(projection.get('projection_digest')) or '<missing>'}`",
        "- Execution Claim IDs: "
        + _md_cell(
            ", ".join(_identity_list(projection.get("execution_claim_ids")))
        ),
        f"- Projected results: {len(projected_results)}",
        f"- Downstream-eligible results: {len(eligible_result_ids)}",
        "",
    ]
    if view_status != "PASS":
        lines.extend(["## Blocking Findings", ""])
        if findings:
            lines.extend(f"- {_md_cell(finding)}" for finding in findings)
        else:
            lines.append("- Canonical projection did not license a results view.")
        lines.append("")
        return "\n".join(lines)

    lines.extend(
        [
            "## Result–Claim–Use Licenses",
            "",
            "<!-- avereth:view-role=identity-projection -->",
            "",
            "| Result ID | Result Status / Type | Claim ID | Claim Disposition | Allowed Uses | Action IDs | Artifact ID @ SHA-256 | Result Authority SHA-256 |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for result_id in sorted(projected_results, key=lambda value: _text(value).upper()):
        record = projected_results[result_id]
        if not isinstance(record, Mapping):
            continue
        normalized_result_id = _text(result_id).upper()
        claim_ids = _identity_list(record.get("claim_ids")) or [""]
        dispositions = (
            record.get("claim_dispositions")
            if isinstance(record.get("claim_dispositions"), Mapping)
            else {}
        )
        claim_uses = (
            record.get("claim_allowed_uses")
            if isinstance(record.get("claim_allowed_uses"), Mapping)
            else {}
        )
        for claim_id in claim_ids:
            uses = (
                claim_uses.get(claim_id)
                if isinstance(claim_uses.get(claim_id), list)
                else []
            )
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(normalized_result_id),
                        _md_cell(
                            f"{_text(record.get('status'))} / {_text(record.get('type'))}"
                        ),
                        _md_cell(claim_id),
                        _md_cell(dispositions.get(claim_id)),
                        _md_cell(", ".join(sorted({_text(use) for use in uses if _text(use)}))),
                        _md_cell(", ".join(_identity_list(record.get("action_ids")))),
                        _md_cell(_artifact_identities(record)),
                        _md_cell(record.get("authority_digest")),
                    ]
                )
                + " |"
            )

    lines.extend(
        [
            "",
            "## Domain Result Statements",
            "",
            "<!-- avereth:view-role=domain-narrative; identity-columns=1; narrative-identity-authority=none -->",
            "",
            "> Human-readable result prose. Tokens in Result Statement, including questionnaire "
            "variable names, are domain content rather than workflow identities. Canonical "
            "eligibility and identity remain defined by `method_execution.downstream_eligibility`.",
            "",
            "| Result ID | Result Statement |",
            "|---|---|",
        ]
    )
    for result_id in sorted(projected_results, key=lambda value: _text(value).upper()):
        record = projected_results[result_id]
        if not isinstance(record, Mapping):
            continue
        lines.append(
            "| "
            + " | ".join(
                [
                    _md_cell(_text(result_id).upper()),
                    _md_cell(record.get("text")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Accepted Action Attempts",
            "",
            "| Result ID | Action ID | Operation ID | Attempt | Status | Parameter Snapshot SHA-256 | Output Artifact IDs | Checks |",
            "|---|---|---|---:|---|---|---|---|",
        ]
    )
    for result_id in sorted(projected_results, key=lambda value: _text(value).upper()):
        record = projected_results[result_id]
        if not isinstance(record, Mapping):
            continue
        attempts = record.get("action_attempts")
        if not isinstance(attempts, list):
            continue
        for attempt in sorted(
            (item for item in attempts if isinstance(item, Mapping)),
            key=lambda item: _text(item.get("id")).upper(),
        ):
            checks = []
            check_records = attempt.get("check_results")
            if isinstance(check_records, list):
                for check in sorted(
                    (item for item in check_records if isinstance(item, Mapping)),
                    key=lambda item: _text(item.get("id")).upper(),
                ):
                    artifacts = ",".join(_identity_list(check.get("artifact_ids")))
                    suffix = f"[{artifacts}]" if artifacts else ""
                    checks.append(
                        f"{_text(check.get('id')).upper()}:{_text(check.get('status'))}{suffix}"
                    )
            lines.append(
                "| "
                + " | ".join(
                    [
                        _md_cell(_text(result_id).upper()),
                        _md_cell(_text(attempt.get("id")).upper()),
                        _md_cell(_text(attempt.get("operation_id")).upper()),
                        _md_cell(attempt.get("attempt")),
                        _md_cell(attempt.get("status")),
                        _md_cell(attempt.get("parameter_snapshot_sha256")),
                        _md_cell(", ".join(_identity_list(attempt.get("output_artifact_ids")))),
                        _md_cell("; ".join(checks)),
                    ]
                )
                + " |"
            )
    lines.append("")
    return "\n".join(lines)


def to_markdown(result: ResultsValidationResult) -> str:
    lines = [
        "# Results Validation Check",
        "",
        f"- Canonical authority: `{result.authority_path}`",
        f"- Derived view: `{result.path}`",
        f"- Canonical projection: **{result.projection_status}**",
        f"- Status: **{'PASS' if result.ok else 'FAIL'}**",
        f"- Projected results: {result.row_count}",
        f"- Results with downstream allowed uses: {result.mapped_rows}",
        "- Authority rule: `results_validation.md` is explanatory only and cannot create eligibility.",
        "",
        "## Findings",
        "",
    ]
    if result.findings:
        lines.extend(f"- {finding}" for finding in result.findings)
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    results_path = output_dir / "results_validation.md"
    projection = canonical_projection(output_dir)
    if args.write:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(
            render_results_validation(projection),
            encoding="utf-8",
        )
    result = validate(results_path, projection=projection)
    markdown = to_markdown(result)

    if args.write:
        report_path = output_dir / "results_validation_check.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(markdown, encoding="utf-8")

    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
