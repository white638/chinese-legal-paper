"""Validate institutional-grammar parsing and clause-alignment artifacts."""

from __future__ import annotations

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    issue,
    read_rows_artifact,
    require_fields,
    require_list,
    substantive,
    text,
)


CORE_FIELDS = {
    "actor",
    "deontic",
    "action",
    "object",
    "condition",
    "exception",
    "enforcement_body",
    "consequence",
}
MATCH_CATEGORIES = {
    "full_alignment",
    "partial_alignment",
    "functional_equivalence",
    "parallel_compatible",
    "procedural_gap",
    "substantive_conflict",
    "indeterminate",
}


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        ("clause_unit", "ambiguity_policy"),
        prefix,
        "ME.INSTITUTIONAL_GRAMMAR.CONTRACT_INCOMPLETE",
    )
    grammar_fields = require_list(
        findings,
        contract.get("grammar_fields"),
        f"{prefix}.grammar_fields",
        "ME.INSTITUTIONAL_GRAMMAR.CONTRACT_INCOMPLETE",
    )
    missing_fields = sorted(CORE_FIELDS - {text(item) for item in grammar_fields})
    if missing_fields:
        findings.append(
            issue(
                "ME.INSTITUTIONAL_GRAMMAR.CONTRACT_INCOMPLETE",
                "Institutional grammar omits: " + ", ".join(missing_fields),
                f"{prefix}.grammar_fields",
            )
        )
    categories = require_list(
        findings,
        contract.get("match_categories"),
        f"{prefix}.match_categories",
        "ME.INSTITUTIONAL_GRAMMAR.CONTRACT_INCOMPLETE",
    )
    invalid = sorted({text(item) for item in categories} - MATCH_CATEGORIES)
    if invalid:
        findings.append(
            issue(
                "ME.INSTITUTIONAL_GRAMMAR.CATEGORY_INVALID",
                "Unknown clause-match categories: " + ", ".join(invalid),
                f"{prefix}.match_categories",
            )
        )
    parsed = read_rows_artifact(
        ctx,
        contract.get("parsed_clauses_artifact_id"),
        f"{prefix}.parsed_clauses_artifact_id",
        findings,
    )
    if parsed:
        row_keys = set(parsed[0])
        absent = sorted(CORE_FIELDS - row_keys)
        if absent:
            findings.append(
                issue(
                    "ME.INSTITUTIONAL_GRAMMAR.PARSE_SCHEMA",
                    "Parsed clauses omit columns: " + ", ".join(absent),
                    f"{prefix}.parsed_clauses_artifact_id",
                )
            )
    matches = read_rows_artifact(
        ctx,
        contract.get("clause_matches_artifact_id"),
        f"{prefix}.clause_matches_artifact_id",
        findings,
    )
    for index, row in enumerate(matches):
        if not all(substantive(row.get(key)) for key in ("source_clause_id", "target_clause_id", "category")):
            findings.append(
                issue(
                    "ME.INSTITUTIONAL_GRAMMAR.MATCH_SCHEMA",
                    f"Clause match row {index + 1} lacks source, target, or category",
                    f"{prefix}.clause_matches_artifact_id",
                )
            )
            break
        if text(row.get("category")) not in MATCH_CATEGORIES:
            findings.append(
                issue(
                    "ME.INSTITUTIONAL_GRAMMAR.CATEGORY_INVALID",
                    f"Clause match row {index + 1} uses an unregistered category",
                    f"{prefix}.clause_matches_artifact_id",
                )
            )
            break
    for field in ("ambiguity_review_artifact_id", "sensitivity_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    return findings
