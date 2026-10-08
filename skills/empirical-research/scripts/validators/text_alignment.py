"""Validate semantic alignment, reuse, and source-direction artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    issue,
    read_rows_artifact,
    require_columns,
    require_fields,
    require_mapping,
    substantive,
    text,
    validate_independent_review_bundle,
)


def _time(value: Any) -> datetime | None:
    token = text(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(token)
    except ValueError:
        return None


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        (
            "alignment_unit",
            "direction_rule",
            "boilerplate_policy",
            "third_source_policy",
            "translation_policy",
        ),
        prefix,
        "ME.ALIGNMENT.DESIGN_INCOMPLETE",
    )
    threshold = require_mapping(
        findings,
        contract.get("threshold_plan"),
        f"{prefix}.threshold_plan",
        "ME.ALIGNMENT.DESIGN_INCOMPLETE",
    )
    require_fields(
        findings,
        threshold,
        ("selection_basis", "sensitivity_range"),
        f"{prefix}.threshold_plan",
        "ME.ALIGNMENT.DESIGN_INCOMPLETE",
    )
    for field in ("source_manifest_artifact_id", "target_manifest_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    rows = read_rows_artifact(
        ctx,
        contract.get("matches_artifact_id"),
        f"{prefix}.matches_artifact_id",
        findings,
    )
    required = {
        "source_id",
        "target_id",
        "source_time",
        "target_time",
        "similarity",
        "boilerplate_status",
        "shared_source_status",
    }
    require_columns(
        findings,
        rows,
        required,
        f"{prefix}.matches_artifact_id",
        "ME.ALIGNMENT.MATCH_SCHEMA",
    )
    pair_ids = [
        f"{text(row.get('source_id'))}::{text(row.get('target_id'))}"
        for row in rows
        if substantive(row.get("source_id")) and substantive(row.get("target_id"))
    ]
    if len(pair_ids) != len(set(pair_ids)):
        findings.append(
            issue(
                "ME.ALIGNMENT.MATCH_DUPLICATE",
                "Alignment output contains duplicate source-target pairs",
                f"{prefix}.matches_artifact_id",
            )
        )
    for index, row in enumerate(rows):
        missing = sorted(field for field in required if not substantive(row.get(field)))
        if missing:
            findings.append(
                issue(
                    "ME.ALIGNMENT.MATCH_SCHEMA",
                    f"Alignment row {index + 1} lacks: {', '.join(missing)}",
                    f"{prefix}.matches_artifact_id",
                )
            )
            break
        source_time = _time(row.get("source_time"))
        target_time = _time(row.get("target_time"))
        if source_time is None or target_time is None:
            findings.append(
                issue(
                    "ME.ALIGNMENT.TIME_INVALID",
                    f"Alignment row {index + 1} has an invalid ISO date/time",
                    f"{prefix}.matches_artifact_id",
                )
            )
            break
        if text(contract.get("direction_rule")) == "source-precedes-target" and source_time > target_time:
            findings.append(
                issue(
                    "ME.ALIGNMENT.DIRECTION_VIOLATION",
                    f"Alignment row {index + 1} reverses the registered temporal direction",
                    f"{prefix}.matches_artifact_id",
                )
            )
            break
    artifact_path(
        ctx,
        contract.get("threshold_sensitivity_artifact_id"),
        f"{prefix}.threshold_sensitivity_artifact_id",
        findings,
    )
    findings.extend(
        validate_independent_review_bundle(
            ctx,
            primary_artifact_id=contract.get("matches_artifact_id"),
            review_artifact_id=contract.get("independent_validation_artifact_id"),
            run_manifest_artifact_id=contract.get("researcher_run_manifest_artifact_id"),
            disagreement_artifact_id=contract.get("disagreement_log_artifact_id"),
            expected_item_ids=set(pair_ids),
            prefix=prefix,
            code_prefix="ME.ALIGNMENT",
        )
    )
    return findings
