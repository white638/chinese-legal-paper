"""Validate mechanism claims against a structured diagnostic-evidence matrix."""

from __future__ import annotations

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    is_narrowed,
    issue,
    read_rows_artifact,
    require_fields,
    require_list,
    require_mapping,
    substantive,
    text,
)


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        ("mechanism", "strongest_competing_mechanism", "inference_boundary"),
        prefix,
        "ME.PROCESS_TRACING.CONTRACT_INCOMPLETE",
    )
    rows = read_rows_artifact(
        ctx,
        contract.get("diagnostic_matrix_artifact_id"),
        f"{prefix}.diagnostic_matrix_artifact_id",
        findings,
    )
    required = {
        "mechanism_node",
        "theoretical_prediction",
        "observation",
        "diagnosticity",
        "competing_mechanism",
        "source_id",
    }
    for index, row in enumerate(rows):
        missing = sorted(field for field in required if not substantive(row.get(field)))
        if missing:
            findings.append(
                issue(
                    "ME.PROCESS_TRACING.MATRIX_INCOMPLETE",
                    f"Diagnostic matrix row {index + 1} lacks: {', '.join(missing)}",
                    f"{prefix}.diagnostic_matrix_artifact_id",
                )
            )
            break
    if rows and not any(
        text(row.get("competing_mechanism")) == text(contract.get("strongest_competing_mechanism"))
        for row in rows
    ):
        findings.append(
            issue(
                "ME.PROCESS_TRACING.RIVAL_UNTESTED",
                "The diagnostic matrix never tests the registered strongest competing mechanism",
                f"{prefix}.diagnostic_matrix_artifact_id",
            )
        )
    artifact_path(
        ctx,
        contract.get("source_independence_artifact_id"),
        f"{prefix}.source_independence_artifact_id",
        findings,
    )
    negative = require_list(
        findings,
        contract.get("negative_evidence"),
        f"{prefix}.negative_evidence",
        "ME.PROCESS_TRACING.NEGATIVE_EVIDENCE_MISSING",
        nonempty=False,
    )
    unresolved = any(
        isinstance(item, dict) and text(item.get("status")) in {"missing", "unresolved"}
        for item in negative
    )
    if unresolved and not is_narrowed(ctx.run.get("inference_disposition")):
        findings.append(
            issue(
                "ME.PROCESS_TRACING.MISSING_TRACE_NOT_NARROWED",
                "Missing or unresolved predicted traces require a narrowed mechanism conclusion",
                f"{ctx.path}.inference_ceiling_observed",
            )
        )
    return findings
