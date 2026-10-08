"""Validate event-history and competing-risk execution contracts."""

from __future__ import annotations

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    finite_number,
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
    estimand = require_mapping(
        findings, contract.get("estimand"), f"{prefix}.estimand", "ME.INFERENCE.ESTIMAND_MISSING"
    )
    require_fields(
        findings,
        estimand,
        ("quantity", "population", "contrast", "time_horizon"),
        f"{prefix}.estimand",
        "ME.INFERENCE.ESTIMAND_MISSING",
    )
    require_fields(
        findings,
        contract,
        (
            "unit_of_treatment",
            "unit_of_analysis",
            "independence_unit",
            "time_origin",
            "censoring_rule",
            "clustering_level",
        ),
        prefix,
        "ME.EVENT_HISTORY.DESIGN_INCOMPLETE",
    )
    require_list(
        findings,
        contract.get("event_types"),
        f"{prefix}.event_types",
        "ME.EVENT_HISTORY.DESIGN_INCOMPLETE",
    )
    data = require_mapping(
        findings, contract.get("data"), f"{prefix}.data", "ME.EVENT_HISTORY.DATA_MISSING"
    )
    require_fields(
        findings,
        data,
        ("start_column", "stop_column", "event_column", "id_column"),
        f"{prefix}.data",
        "ME.EVENT_HISTORY.DATA_MISSING",
    )
    rows = read_rows_artifact(
        ctx, data.get("artifact_id"), f"{prefix}.data.artifact_id", findings
    )
    for index, row in enumerate(rows):
        for field in ("start_column", "stop_column", "event_column", "id_column"):
            column = text(data.get(field))
            if not substantive(row.get(column)):
                findings.append(
                    issue(
                        "ME.EVENT_HISTORY.DATA_SCHEMA",
                        f"Event row {index + 1} lacks registered column {column!r}",
                        f"{prefix}.data.artifact_id",
                    )
                )
                return findings
        start = finite_number(row.get(text(data.get("start_column"))))
        stop = finite_number(row.get(text(data.get("stop_column"))))
        if start is None or stop is None or stop < start:
            findings.append(
                issue(
                    "ME.EVENT_HISTORY.TIME_INVALID",
                    f"Event row {index + 1} has invalid start/stop time",
                    f"{prefix}.data.artifact_id",
                )
            )
            break
    for field in ("diagnostics_artifact_id", "estimate_artifact_id", "sensitivity_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    reported_unit = text((contract.get("effective_sample_size") or {}).get("unit"))
    treatment_unit = text(contract.get("unit_of_treatment"))
    if reported_unit in {"sentence", "claim", "token"} and treatment_unit not in {
        "sentence",
        "claim",
        "token",
    }:
        findings.append(
            issue(
                "ME.INFERENCE.PSEUDO_REPLICATION",
                "Text rows cannot replace the registered treatment/independence unit as effective N",
                f"{prefix}.effective_sample_size.unit",
            )
        )
    return findings
