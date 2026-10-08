"""Validate estimand-first causal, panel/event-study, and text-matching contracts."""

from __future__ import annotations

from typing import Any, Mapping

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    is_narrowed,
    issue,
    read_rows_artifact,
    require_columns,
    require_fields,
    require_list,
    require_mapping,
    substantive,
    text,
    validate_independent_review_bundle,
)


def _core(ctx: ValidationContext, findings: list[Finding]) -> None:
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
        ("unit_of_treatment", "unit_of_analysis", "independence_unit"),
        prefix,
        "ME.INFERENCE.UNIT_MISSING",
    )
    counterfactual = require_mapping(
        findings,
        contract.get("counterfactual"),
        f"{prefix}.counterfactual",
        "ME.INFERENCE.COUNTERFACTUAL_MISSING",
    )
    require_fields(
        findings,
        counterfactual,
        ("comparison_state", "comparison_population", "time_basis"),
        f"{prefix}.counterfactual",
        "ME.INFERENCE.COUNTERFACTUAL_MISSING",
    )
    assumptions = require_list(
        findings,
        contract.get("identification_assumptions"),
        f"{prefix}.identification_assumptions",
        "ME.INFERENCE.ASSUMPTIONS_MISSING",
    )
    failed = False
    for index, assumption in enumerate(assumptions):
        path = f"{prefix}.identification_assumptions[{index}]"
        if not isinstance(assumption, Mapping):
            findings.append(issue("ME.INFERENCE.ASSUMPTIONS_MISSING", "Assumption must be an object", path))
            continue
        require_fields(
            findings,
            assumption,
            ("id", "statement", "status"),
            path,
            "ME.INFERENCE.ASSUMPTIONS_MISSING",
        )
        artifact_path(ctx, assumption.get("diagnostic_artifact_id"), f"{path}.diagnostic_artifact_id", findings)
        if text(assumption.get("status")) not in {"supported", "not-rejected", "satisfied"}:
            failed = True
    for field in ("estimate_artifact_id", "sensitivity_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    if failed and not is_narrowed(ctx.run.get("inference_disposition")):
        findings.append(
            issue(
                "ME.INFERENCE.DIAGNOSTIC_FAILED_NOT_NARROWED",
                "Failed or unresolved identification diagnostics require an explicit narrowed inference ceiling",
                f"{ctx.path}.inference_ceiling_observed",
            )
        )
    effective = contract.get("effective_sample_size")
    if isinstance(effective, Mapping):
        reported_unit = text(effective.get("unit"))
        independence_unit = text(contract.get("independence_unit"))
        if reported_unit and independence_unit and reported_unit != independence_unit:
            findings.append(
                issue(
                    "ME.INFERENCE.PSEUDO_REPLICATION",
                    "Effective N must use the registered independence unit",
                    f"{prefix}.effective_sample_size.unit",
                )
            )


def _panel(ctx: ValidationContext, findings: list[Finding]) -> None:
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        (
            "treatment_cohorts",
            "control_group",
            "pre_treatment_window",
            "spillover_plan",
            "clustering_level",
            "alternative_timing_plan",
            "placebo_plan",
        ),
        prefix,
        "ME.INFERENCE.PANEL_CONTRACT_INCOMPLETE",
    )
    parallel = require_mapping(
        findings,
        contract.get("parallel_trends"),
        f"{prefix}.parallel_trends",
        "ME.INFERENCE.PANEL_CONTRACT_INCOMPLETE",
    )
    require_fields(
        findings,
        parallel,
        ("status", "window"),
        f"{prefix}.parallel_trends",
        "ME.INFERENCE.PANEL_CONTRACT_INCOMPLETE",
    )
    artifact_path(
        ctx,
        parallel.get("diagnostic_artifact_id"),
        f"{prefix}.parallel_trends.diagnostic_artifact_id",
        findings,
    )
    if text(parallel.get("status")) in {"failed", "violated", "unresolved"} and not is_narrowed(
        ctx.run.get("inference_disposition")
    ):
        findings.append(
            issue(
                "ME.INFERENCE.PARALLEL_TRENDS_FAILED",
                "A failed parallel-trends diagnostic requires a narrowed result, not a limitation-only note",
                f"{ctx.path}.inference_ceiling_observed",
            )
        )


def _text_matching(ctx: ValidationContext, findings: list[Finding]) -> None:
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        (
            "matching_unit",
            "text_representation",
            "distance_function",
            "matching_threshold",
            "template_handling",
            "matches_artifact_id",
        ),
        prefix,
        "ME.INFERENCE.TEXT_MATCHING_INCOMPLETE",
    )
    for field in ("balance_before_artifact_id", "balance_after_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    match_rows = read_rows_artifact(
        ctx,
        contract.get("matches_artifact_id"),
        f"{prefix}.matches_artifact_id",
        findings,
    )
    require_columns(
        findings,
        match_rows,
        ("match_id", "treated_id", "control_id", "distance", "evidence_locator"),
        f"{prefix}.matches_artifact_id",
        "ME.INFERENCE.TEXT_MATCH_SCHEMA",
    )
    match_ids = [
        text(row.get("match_id"))
        for row in match_rows
        if substantive(row.get("match_id"))
    ]
    if len(match_ids) != len(set(match_ids)):
        findings.append(
            issue(
                "ME.INFERENCE.TEXT_MATCH_DUPLICATE",
                "Text-matching output contains duplicate match IDs",
                f"{prefix}.matches_artifact_id",
            )
        )
    findings.extend(
        validate_independent_review_bundle(
            ctx,
            primary_artifact_id=contract.get("matches_artifact_id"),
            review_artifact_id=contract.get("independent_match_validation_artifact_id"),
            run_manifest_artifact_id=contract.get("researcher_run_manifest_artifact_id"),
            disagreement_artifact_id=contract.get("match_disagreement_artifact_id"),
            expected_item_ids=set(match_ids),
            prefix=prefix,
            code_prefix="ME.INFERENCE.TEXT_MATCH",
        )
    )
    separation = require_mapping(
        findings,
        contract.get("data_role_separation"),
        f"{prefix}.data_role_separation",
        "ME.INFERENCE.DATA_ROLE_MISSING",
    )
    status = text(separation.get("status"))
    if status not in {"separated", "overlap-disclosed-exploratory"}:
        findings.append(
            issue(
                "ME.INFERENCE.DATA_ROLE_MISSING",
                "Measurement-development and effect-estimation data roles must be separated or explicitly downgraded",
                f"{prefix}.data_role_separation.status",
            )
        )
    if status == "overlap-disclosed-exploratory" and not is_narrowed(
        ctx.run.get("inference_disposition")
    ):
        findings.append(
            issue(
                "ME.INFERENCE.OVERLAP_NOT_DOWNGRADED",
                "Overlapping development and inference data require an exploratory/narrowed ceiling",
                f"{ctx.path}.inference_ceiling_observed",
            )
        )


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    _core(ctx, findings)
    if ctx.schema_id == "causal-panel/v1":
        _panel(ctx, findings)
    if ctx.schema_id == "text-matching/v2":
        _text_matching(ctx, findings)
    return findings
