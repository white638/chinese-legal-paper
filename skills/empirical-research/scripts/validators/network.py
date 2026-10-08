"""Validate political discourse-network data without conflating co-word networks."""

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


EDGE_FIELDS = ("actor", "claim", "position", "time", "source")


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"
    require_fields(
        findings,
        contract,
        ("network_boundary", "dependence_plan", "source_identity_policy"),
        prefix,
        "ME.DISCOURSE_NETWORK.CONTRACT_INCOMPLETE",
    )
    if text(contract.get("network_kind")) in {"co-word", "cooccurrence", "word_cooccurrence"}:
        findings.append(
            issue(
                "ME.DISCOURSE_NETWORK.COWORD_CONFLATION",
                "A co-word network cannot be registered as an Actor-Claim-Position discourse network",
                f"{prefix}.network_kind",
            )
        )
    edge_schema = require_list(
        findings,
        contract.get("edge_schema"),
        f"{prefix}.edge_schema",
        "ME.DISCOURSE_NETWORK.CONTRACT_INCOMPLETE",
    )
    if tuple(text(item).casefold() for item in edge_schema) != EDGE_FIELDS:
        findings.append(
            issue(
                "ME.DISCOURSE_NETWORK.EDGE_SCHEMA",
                "Discourse network edges must be Actor-Claim-Position-Time-Source",
                f"{prefix}.edge_schema",
            )
        )
    rows = read_rows_artifact(
        ctx,
        contract.get("edges_artifact_id"),
        f"{prefix}.edges_artifact_id",
        findings,
    )
    for index, row in enumerate(rows):
        missing = [field for field in EDGE_FIELDS if not substantive(row.get(field))]
        if missing:
            findings.append(
                issue(
                    "ME.DISCOURSE_NETWORK.EDGE_SCHEMA",
                    f"Edge row {index + 1} lacks: {', '.join(missing)}",
                    f"{prefix}.edges_artifact_id",
                )
            )
            break
    for field in ("dependence_diagnostics_artifact_id", "source_provenance_artifact_id"):
        artifact_path(ctx, contract.get(field), f"{prefix}.{field}", findings)
    return findings
