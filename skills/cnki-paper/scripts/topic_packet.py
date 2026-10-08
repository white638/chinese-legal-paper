#!/usr/bin/env python3
"""Compile and validate the material-quarantined topic-divergence packet.

The packet is a transient research-stage projection.  It narrows the first
generation context to the current request and direction contract; it is not a
workflow stage, scientific authority, or completion receipt.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from avereth_core.config import (
    DIRECTION_CONTRACT_FIELDS,
    DIRECTION_CONTRACT_FIELD_SET,
    read_config,
    validate_workflow_config,
)
from avereth_core.hosts import (
    ALL_RUNNERS,
    HostCapture,
    default_host_runner,
    ensure_runner_allowed,
    read_agent_capture,
    run_claude_exec_isolated,
    run_codex_exec_isolated,
    write_agent_capture_request,
)


SCHEMA_VERSION = "avereth-topic-packet/v1"
SEED_SEAL_SCHEMA_VERSION = "avereth-topic-seed-seal/v1"
GENERATION_DISPATCH_SCHEMA_VERSION = "avereth-topic-generation-dispatch/v1"
GENERATION_RECEIPT_SCHEMA_VERSION = "avereth-topic-generation-receipt/v1"
GENERATION_PROTOCOL_SCHEMA_VERSION = "avereth-topic-generation-protocol/v2"
LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION = "avereth-topic-generation-protocol/v1"
ISOLATED_DISPATCHER_ISSUER = "avereth-topic-isolated-dispatcher/v1"
SCHEDULER_RECEIPT_TTL_SECONDS = 900
DECLARED_MATERIAL_MAX_FILE_BYTES = 1_000_000
DECLARED_MATERIAL_MAX_TOTAL_BYTES = 2_000_000
GENERATION_LANE_INSTRUCTIONS = {
    "core_problem": "Identify the direction's most consequential unresolved core problem.",
    "competing_mechanism": "Generate competing explanations that imply distinguishable observations.",
    "boundary_comparison": "Identify boundaries or comparisons where an explanation should hold or fail.",
    "historical_process": "Trace formation, transition, layering, or temporal reversal as the research problem.",
    "concept_measurement": "Question whether current concepts or measures obscure the load-bearing phenomenon.",
    "anomaly_negative_case": "Use anomalies and negative cases to challenge the dominant expectation.",
    "cross_level": "Connect actors or processes across individual, organizational, institutional, or international levels.",
    "high_risk_theory": "Reconstruct the problem or theory rather than adding a cosmetic variable.",
    "core_mechanism_boundary": "Cover core problems, competing mechanisms, and boundary comparisons without title variants.",
    "anomaly_concept_high_risk": "Cover anomalies, concept or measurement reconstruction, and high-risk theory directions.",
}
ORIGIN_MODES = {"direction_first", "workspace_extension", "material_opportunity", "phenomenon_first"}
WORKSPACE_ROLE_BY_ORIGIN = {
    "direction_first": "optional-after-divergence",
    "workspace_extension": "declared-extension-source",
    "material_opportunity": "declared-material-source",
    "phenomenon_first": "declared-phenomenon-source",
}
BRAINSTORM_DEPTHS = {"broad", "focused"}
# Mirror of the bind-stage RDEC.PORTFOLIO.SEED_BREADTH window (research_decision.py);
# enforced early here so an out-of-window portfolio fails at generation/seal instead
# of after screening and semantic review have already been paid for.
BROAD_SEED_WINDOW = (12, 18)
WORKSPACE_POLICIES = {"quarantine_until_divergence", "declared_source_from_start"}
DIRECTION_ALLOWED_INPUTS = (
    "current_user_request",
    "direction_contract",
    "publication_track",
    "explicit_constraints",
    "acceptable_adjacency",
)
ALLOWED_INPUTS = DIRECTION_ALLOWED_INPUTS
DECLARED_MATERIAL_ALLOWED_INPUTS = (
    *DIRECTION_ALLOWED_INPUTS,
    "declared_material_projection",
)
QUARANTINED_INPUTS = (
    "workspace_data",
    "codebooks",
    "prior_topic_lists",
    "prior_manuscripts",
    "workspace_literature",
    "existing_methods",
    "material_convenience",
)
# Fresh, direction-scoped retrieval evidence (CNKI/exa/OpenAlex...) compiled just
# before the packet. Unlike QUARANTINED_INPUTS it is not workspace anchoring: it
# grounds divergence in the real literature landscape so seeds do not rest on the
# model's parametric memory alone. Legacy v1 packets remain readable; new
# direction-first compilation and generation require this bounded input.
RECON_INPUT_KEY = "literature_reconnaissance"
RECON_SOURCES = {
    "cnki",
    "exa",
    "openalex",
    "google_scholar",
    "semantic_scholar",
    "web_of_science",
    "other",
}
RECON_ENTRY_REQUIRED_KEYS = {"query", "source", "title", "year", "claim"}
RECON_ENTRY_OPTIONAL_KEYS = {"authors", "venue", "identifier", "retrieved_at", "relations"}
RECON_MAX_ENTRIES = 60
RECON_MAX_FIELD_CHARS = 500
# Optional verified relations between recon entries. ``target`` names another
# entry's identifier; absence of a relation means "unverified", never "unrelated".
RECON_RELATIONS = {"cites", "cited-by", "co-cited-with"}
RECON_RELATION_EVIDENCE = {"openalex", "semantic_scholar", "cnki", "crossref", "other"}
RECON_RELATION_KEYS = {"target", "relation", "evidence"}
RECON_MAX_RELATIONS = 20
PACKET_KEYS = {
    "schema_version",
    "compiled_at",
    "origin_mode",
    "brainstorm_depth",
    "workspace_policy",
    "current_user_request",
    "direction_contract",
    "direction_contract_digest",
    "publication_track",
    "explicit_constraints",
    "acceptable_adjacency",
    "allowed_inputs",
    "excluded_inputs",
    "material_visibility",
    "declared_workspace_scope",
    "packet_sha256",
}
SEED_KEYS = {
    "seed_id",
    "candidate_family",
    "problem",
    "anomaly_or_unknown",
    "why_it_matters",
    "potential_disconfirmation",
}
LEGACY_GENERATION_PROTOCOL = {
    "schema_version": LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION,
    "input_scope": list(ALLOWED_INPUTS),
    "forbidden_inputs": list(QUARANTINED_INPUTS),
    "output_fields": sorted(SEED_KEYS),
    "rules": [
        "derive problem seeds only from the bound topic packet",
        "do not inspect or infer workspace materials outside the packet",
        "return one JSON array whose seed objects use the exact output fields",
    ],
}
LEGACY_DECLARED_MATERIAL_GENERATION_PROTOCOL = {
    "schema_version": LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION,
    "input_scope": list(DECLARED_MATERIAL_ALLOWED_INPUTS),
    "forbidden_inputs": list(QUARANTINED_INPUTS),
    "output_fields": sorted(SEED_KEYS),
    "rules": [
        "derive problem seeds from the bound topic packet and only the declared material projection",
        "do not inspect or infer undeclared workspace materials",
        "generate multiple substantively distinct candidate families rather than variants of one material convenience",
        "return one JSON array whose seed objects use the exact output fields",
    ],
}
GENERATION_FOCUS_RULES = [
    "use anomaly_or_unknown for a supported explanation or premise under real pressure, or a consequential unresolved unknown",
    "use why_it_matters to identify the judgment an answer would change",
    "use potential_disconfirmation for feasible evidence or reasoning that distinguishes support, revision, and withdrawal",
    "preserve descriptive, historical, normative, and synthesis questions without inventing contradictions or a preferred answer",
]
GENERATION_PROTOCOL = {
    **LEGACY_GENERATION_PROTOCOL,
    "schema_version": GENERATION_PROTOCOL_SCHEMA_VERSION,
    "rules": [*LEGACY_GENERATION_PROTOCOL["rules"], *GENERATION_FOCUS_RULES],
}
DECLARED_MATERIAL_GENERATION_PROTOCOL = {
    **LEGACY_DECLARED_MATERIAL_GENERATION_PROTOCOL,
    "schema_version": GENERATION_PROTOCOL_SCHEMA_VERSION,
    "rules": [
        *LEGACY_DECLARED_MATERIAL_GENERATION_PROTOCOL["rules"],
        *GENERATION_FOCUS_RULES,
    ],
}
GENERATION_DISPATCH_KEYS = {
    "schema_version",
    "issuer",
    "packet_sha256",
    "material_projection_sha256",
    "material_refs",
    "input_scope",
    "input_sha256",
    "prompt",
    "prompt_sha256",
    "protocol",
    "protocol_sha256",
    "lane_id",
    "run_id",
    "model_revision",
    "context_id",
    "dispatched_at",
    "dispatch_sha256",
}
GENERATION_RECEIPT_KEYS = {
    "schema_version",
    "issuer",
    "issued_at",
    "expires_at",
    "receipt_id",
    "scheduler_session_id",
    "scheduler_key_id",
    "dispatched_at",
    "dispatch_sha256",
    "packet_sha256",
    "material_projection_sha256",
    "material_refs",
    "input_scope",
    "input_sha256",
    "prompt_sha256",
    "protocol_sha256",
    "lane_id",
    "run_id",
    "model_revision",
    "context_id",
    "raw_output_sha256",
    "seeds",
    "seed_output_digest",
    "signature",
    "receipt_sha256",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normal(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _text(value).lower())


def _valid_timestamp(value: Any) -> bool:
    try:
        datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return bool(_text(value))


def _timestamp(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def direction_contract_projection(value: Mapping[str, Any]) -> dict[str, Any]:
    """Project only the direction fields authorized by the workflow schema."""

    return {key: value.get(key) for key in DIRECTION_CONTRACT_FIELDS}


def topic_policy(config: Mapping[str, Any]) -> dict[str, str]:
    declared = config.get("topic_selection")
    declared = declared if isinstance(declared, Mapping) else {}
    origin_mode = _text(declared.get("origin_mode")) or "direction_first"
    brainstorm_depth = _text(declared.get("brainstorm_depth")) or "broad"
    default_workspace_policy = (
        "quarantine_until_divergence"
        if origin_mode == "direction_first"
        else "declared_source_from_start"
    )
    return {
        "origin_mode": origin_mode,
        "brainstorm_depth": brainstorm_depth,
        "workspace_policy": _text(declared.get("workspace_policy"))
        or default_workspace_policy,
    }


def _recon_relation_issues(
    value: Any, path: str, identifiers: set[str], own_identifier: str
) -> list[str]:
    issues: list[str] = []
    if not isinstance(value, list):
        return [f"{path}.relations must be an array"]
    if len(value) > RECON_MAX_RELATIONS:
        issues.append(f"{path}.relations cannot exceed {RECON_MAX_RELATIONS} entries")
    seen: set[tuple[str, str]] = set()
    for number, relation in enumerate(value):
        rel_path = f"{path}.relations[{number}]"
        if not isinstance(relation, Mapping):
            issues.append(f"{rel_path} must be an object")
            continue
        keys = {str(key) for key in relation}
        missing = sorted(RECON_RELATION_KEYS - keys)
        extra = sorted(keys - RECON_RELATION_KEYS)
        if missing:
            issues.append(f"{rel_path} lacks fields: " + ", ".join(missing))
        if extra:
            issues.append(f"{rel_path} contains unauthorized fields: " + ", ".join(extra))
        target = _text(relation.get("target"))
        if not target:
            issues.append(f"{rel_path}.target is required")
        elif target not in identifiers:
            issues.append(f"{rel_path}.target must equal another entry's identifier")
        elif own_identifier and target == own_identifier:
            issues.append(f"{rel_path}.target cannot be the entry itself")
        kind = _text(relation.get("relation"))
        if kind not in RECON_RELATIONS:
            issues.append(f"{rel_path}.relation must be one of: " + ", ".join(sorted(RECON_RELATIONS)))
        if _text(relation.get("evidence")) not in RECON_RELATION_EVIDENCE:
            issues.append(
                f"{rel_path}.evidence must be one of: " + ", ".join(sorted(RECON_RELATION_EVIDENCE))
            )
        pair = (kind, target)
        if pair in seen:
            issues.append(f"{rel_path} repeats {kind} toward {target}")
        seen.add(pair)
    return issues


def _recon_issues(value: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(value, list) or not value:
        return ["literature_reconnaissance must be a non-empty array of retrieval entries"]
    if len(value) > RECON_MAX_ENTRIES:
        issues.append(
            f"literature_reconnaissance cannot exceed {RECON_MAX_ENTRIES} entries"
        )
    identifiers = {
        _text(entry.get("identifier"))
        for entry in value
        if isinstance(entry, Mapping) and _text(entry.get("identifier"))
    }
    for index, entry in enumerate(value):
        path = f"literature_reconnaissance[{index}]"
        if not isinstance(entry, Mapping):
            issues.append(f"{path} must be an object")
            continue
        keys = {str(key) for key in entry}
        if "relations" in keys:
            issues.extend(
                _recon_relation_issues(entry.get("relations"), path, identifiers, _text(entry.get("identifier")))
            )
        missing = sorted(RECON_ENTRY_REQUIRED_KEYS - keys)
        extra = sorted(keys - RECON_ENTRY_REQUIRED_KEYS - RECON_ENTRY_OPTIONAL_KEYS)
        if missing:
            issues.append(f"{path} lacks fields: " + ", ".join(missing))
        if extra:
            issues.append(f"{path} contains unauthorized fields: " + ", ".join(extra))
        if _text(entry.get("source")) not in RECON_SOURCES:
            issues.append(
                f"{path}.source must be one of: " + ", ".join(sorted(RECON_SOURCES))
            )
        for field in ("query", "title", "claim"):
            if not _text(entry.get(field)):
                issues.append(f"{path}.{field} is required")
        year = entry.get("year")
        if not isinstance(year, int) or isinstance(year, bool) or not (
            1500 <= year <= 2100
        ):
            issues.append(f"{path}.year must be an integer publication year")
        for field in keys - {"year", "relations"}:
            if len(_text(entry.get(field))) > RECON_MAX_FIELD_CHARS:
                issues.append(
                    f"{path}.{field} exceeds {RECON_MAX_FIELD_CHARS} characters"
                )
        if "retrieved_at" in keys and not _valid_timestamp(entry.get("retrieved_at")):
            issues.append(f"{path}.retrieved_at must be an ISO-8601 timestamp")
    return issues


def generation_input_scope(packet: Mapping[str, Any]) -> tuple[str, ...]:
    base = (
        DIRECTION_ALLOWED_INPUTS
        if _text(packet.get("origin_mode")) == "direction_first"
        else DECLARED_MATERIAL_ALLOWED_INPUTS
    )
    if packet.get(RECON_INPUT_KEY):
        return (*base, RECON_INPUT_KEY)
    return base


def generation_protocol(
    packet: Mapping[str, Any],
    *,
    protocol_version: str = GENERATION_PROTOCOL_SCHEMA_VERSION,
) -> dict[str, Any]:
    if protocol_version == GENERATION_PROTOCOL_SCHEMA_VERSION:
        direction_protocol = GENERATION_PROTOCOL
        material_protocol = DECLARED_MATERIAL_GENERATION_PROTOCOL
    elif protocol_version == LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION:
        direction_protocol = LEGACY_GENERATION_PROTOCOL
        material_protocol = LEGACY_DECLARED_MATERIAL_GENERATION_PROTOCOL
    else:
        raise ValueError("unsupported topic generation protocol version")
    protocol = dict(
        direction_protocol
        if _text(packet.get("origin_mode")) == "direction_first"
        else material_protocol
    )
    if packet.get(RECON_INPUT_KEY):
        protocol["input_scope"] = [*protocol["input_scope"], RECON_INPUT_KEY]
        protocol["rules"] = [
            *protocol["rules"],
            "ground every seed in the bound literature_reconnaissance landscape: "
            "target the gaps, contradictions, and untested assumptions it actually reveals",
            "name the recon entries a seed responds to inside anomaly_or_unknown",
            "do not restate a question a recon entry already answers, and do not "
            "reverse-engineer topics from whatever data or method is merely convenient",
        ]
    return protocol


def _generation_protocol_version(
    packet: Mapping[str, Any], protocol_sha256: Any
) -> str | None:
    # Receipts bind the original prompt through this signed protocol digest.
    for version in (
        GENERATION_PROTOCOL_SCHEMA_VERSION,
        LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION,
    ):
        if _text(protocol_sha256) == canonical_digest(
            generation_protocol(packet, protocol_version=version)
        ):
            return version
    return None


def packet_projection(packet: Mapping[str, Any]) -> dict[str, Any]:
    projection = {
        key: packet.get(key)
        for key in sorted(PACKET_KEYS - {"packet_sha256"})
    }
    if RECON_INPUT_KEY in packet:
        projection[RECON_INPUT_KEY] = packet.get(RECON_INPUT_KEY)
    return projection


def build_packet(
    config: Mapping[str, Any],
    *,
    current_user_request: str,
    compiled_at: str,
    declared_workspace_scope: Sequence[str] = (),
    literature_reconnaissance: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    issues = validate_workflow_config(dict(config))
    if issues:
        raise ValueError("invalid workflow config: " + "; ".join(issues))
    if _text(config.get("task_profile")) != "topic_selection":
        raise ValueError("topic packet is available only for task_profile=topic_selection")
    direction_contract = config.get("direction_contract")
    if not isinstance(direction_contract, Mapping):
        raise ValueError("topic selection requires one explicit direction_contract")
    if not _text(current_user_request):
        raise ValueError("current_user_request is required")
    if not _valid_timestamp(compiled_at):
        raise ValueError("compiled_at must be an ISO-8601 timestamp")
    policy = topic_policy(config)
    scope = [_text(item) for item in declared_workspace_scope if _text(item)]
    bounded_direction = direction_contract_projection(direction_contract)
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "compiled_at": compiled_at,
        **policy,
        "current_user_request": _text(current_user_request),
        "direction_contract": bounded_direction,
        "direction_contract_digest": canonical_digest(bounded_direction),
        "publication_track": _text(config.get("publication_track")),
        "explicit_constraints": [
            _text(item)
            for item in config.get("special_requirements") or []
            if _text(item)
        ],
        "acceptable_adjacency": _text(direction_contract.get("acceptable_adjacency")),
        "allowed_inputs": list(
            DIRECTION_ALLOWED_INPUTS
            if policy["origin_mode"] == "direction_first"
            else DECLARED_MATERIAL_ALLOWED_INPUTS
        ),
        "excluded_inputs": list(QUARANTINED_INPUTS),
        "material_visibility": (
            "quarantined"
            if policy["origin_mode"] == "direction_first"
            else "declared-source"
        ),
        "declared_workspace_scope": scope,
    }
    if literature_reconnaissance is not None:
        recon_entries = list(literature_reconnaissance)
        recon_problems = _recon_issues(recon_entries)
        if recon_problems:
            raise ValueError(
                "invalid literature reconnaissance: " + "; ".join(recon_problems)
            )
        packet[RECON_INPUT_KEY] = [dict(item) for item in recon_entries]
        packet["allowed_inputs"] = [*packet["allowed_inputs"], RECON_INPUT_KEY]
    packet["packet_sha256"] = canonical_digest(packet_projection(packet))
    validation = validate_packet(packet, config, for_generation=True)
    if validation:
        raise ValueError("invalid topic packet: " + "; ".join(validation))
    return packet


def validate_packet(
    packet: Mapping[str, Any],
    config: Mapping[str, Any] | None = None,
    *,
    for_generation: bool = False,
) -> list[str]:
    """Read v1 history without authorizing an ungrounded new generation run."""

    issues: list[str] = []
    missing = sorted(PACKET_KEYS - set(packet))
    extra = sorted(set(packet) - PACKET_KEYS - {RECON_INPUT_KEY})
    if missing:
        issues.append("topic packet lacks fields: " + ", ".join(missing))
    if extra:
        issues.append("topic packet contains unauthorized fields: " + ", ".join(extra))
    if RECON_INPUT_KEY in packet:
        issues.extend(_recon_issues(packet.get(RECON_INPUT_KEY)))
    if _text(packet.get("schema_version")) != SCHEMA_VERSION:
        issues.append(f"schema_version must be {SCHEMA_VERSION}")
    if not _valid_timestamp(packet.get("compiled_at")):
        issues.append("compiled_at must be an ISO-8601 timestamp")
    origin = _text(packet.get("origin_mode"))
    if origin not in ORIGIN_MODES:
        issues.append("origin_mode is unsupported")
    if for_generation:
        if origin == "direction_first" and RECON_INPUT_KEY not in packet:
            issues.append(
                "new direction_first generation requires literature_reconnaissance; "
                "legacy packets are read-only: perform retrieval and recompile with --recon"
            )
        recon = packet.get(RECON_INPUT_KEY)
        compiled = _timestamp(packet.get("compiled_at"))
        for index, entry in enumerate(recon if isinstance(recon, list) else []):
            if not isinstance(entry, Mapping):
                continue
            path = f"literature_reconnaissance[{index}]"
            if not _text(entry.get("identifier")):
                issues.append(f"{path}.identifier is required for new generation")
            retrieved = _timestamp(entry.get("retrieved_at"))
            if retrieved is None:
                issues.append(f"{path}.retrieved_at is required for new generation")
            elif compiled is not None and retrieved > compiled:
                issues.append(f"{path}.retrieved_at cannot follow packet compilation")
    if _text(packet.get("brainstorm_depth")) not in BRAINSTORM_DEPTHS:
        issues.append("brainstorm_depth is unsupported")
    workspace_policy = _text(packet.get("workspace_policy"))
    if workspace_policy not in WORKSPACE_POLICIES:
        issues.append("workspace_policy is unsupported")
    if not _text(packet.get("current_user_request")):
        issues.append("current_user_request is required")
    direction_contract = packet.get("direction_contract")
    if not isinstance(direction_contract, Mapping):
        issues.append("direction_contract must be one object")
        direction_contract = {}
    else:
        missing_direction = sorted(DIRECTION_CONTRACT_FIELD_SET - set(direction_contract))
        extra_direction = sorted(
            str(key)
            for key in direction_contract
            if key not in DIRECTION_CONTRACT_FIELD_SET
        )
        if missing_direction:
            issues.append(
                "direction_contract lacks authorized fields: "
                + ", ".join(missing_direction)
            )
        if extra_direction:
            issues.append(
                "direction_contract contains unauthorized fields: "
                + ", ".join(extra_direction)
            )
        expected_workspace_role = WORKSPACE_ROLE_BY_ORIGIN.get(origin)
        if (
            expected_workspace_role is not None
            and _text(direction_contract.get("workspace_role"))
            != expected_workspace_role
        ):
            issues.append(
                "direction_contract.workspace_role does not match origin_mode"
            )
    if _text(packet.get("direction_contract_digest")) != canonical_digest(direction_contract):
        issues.append("direction_contract_digest does not match the packet contract")
    expected_inputs = list(generation_input_scope(packet))
    if list(packet.get("allowed_inputs") or []) != expected_inputs:
        issues.append("allowed_inputs must be the exact origin-specific input scope")
    if list(packet.get("excluded_inputs") or []) != list(QUARANTINED_INPUTS):
        issues.append("excluded_inputs must explicitly quarantine every workspace anchoring source")
    scope = packet.get("declared_workspace_scope")
    if not isinstance(scope, list) or any(not _text(item) for item in scope):
        issues.append("declared_workspace_scope must be an array of non-empty strings")
        scope = []
    elif len({_text(item) for item in scope}) != len(scope):
        issues.append("declared_workspace_scope paths must be unique")
    if origin == "direction_first":
        if _text(packet.get("material_visibility")) != "quarantined":
            issues.append("direction_first requires material_visibility=quarantined")
        if workspace_policy != "quarantine_until_divergence":
            issues.append("direction_first requires workspace_policy=quarantine_until_divergence")
        if scope:
            issues.append("direction_first packet cannot contain a declared workspace scope")
    else:
        if _text(packet.get("material_visibility")) != "declared-source":
            issues.append("workspace/material-origin packets require material_visibility=declared-source")
        if not scope:
            issues.append("workspace/material-origin packets require an explicit declared workspace scope")
    if _text(packet.get("packet_sha256")) != canonical_digest(packet_projection(packet)):
        issues.append("packet_sha256 does not match the material-bounded packet projection")

    if config is not None:
        for message in validate_workflow_config(dict(config)):
            issues.append("workflow config: " + message)
        policy = topic_policy(config)
        for field in ("origin_mode", "brainstorm_depth", "workspace_policy"):
            if _text(packet.get(field)) != policy[field]:
                issues.append(f"topic packet {field} differs from workflow_config.json")
        if _text(packet.get("publication_track")) != _text(config.get("publication_track")):
            issues.append("topic packet publication_track differs from workflow_config.json")
        live_contract = config.get("direction_contract")
        if (
            not isinstance(live_contract, Mapping)
            or dict(direction_contract) != direction_contract_projection(live_contract)
        ):
            issues.append("topic packet direction_contract differs from workflow_config.json")
    return list(dict.fromkeys(issues))


def declared_material_projection(
    packet: Mapping[str, Any],
    workspace_root: Path | None,
) -> list[dict[str, str]]:
    """Read only explicitly declared UTF-8 files into a bounded host projection."""

    origin = _text(packet.get("origin_mode"))
    if origin == "direction_first":
        return []
    if workspace_root is None:
        raise ValueError(
            "workspace/material-origin generation requires an explicit workspace root"
        )
    root = workspace_root.resolve()
    if not root.is_dir():
        raise ValueError("declared material workspace root is not a directory")
    declared = packet.get("declared_workspace_scope")
    if not isinstance(declared, list) or not declared:
        raise ValueError("workspace/material-origin generation has no declared material files")
    projection: list[dict[str, str]] = []
    total_bytes = 0
    for index, value in enumerate(declared):
        raw_path = _text(value).replace("\\", "/")
        if not raw_path or raw_path.startswith("/") or re.match(r"^[A-Za-z]:", raw_path):
            raise ValueError(f"declared material path {index} must be workspace-relative")
        resolved = (root / raw_path).resolve()
        try:
            relative = resolved.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError(f"declared material path {index} escapes the workspace root") from exc
        if not resolved.is_file():
            raise ValueError(f"declared material path {relative} is not one readable file")
        raw = resolved.read_bytes()
        if len(raw) > DECLARED_MATERIAL_MAX_FILE_BYTES:
            raise ValueError(
                f"declared material path {relative} exceeds the one-megabyte file limit"
            )
        total_bytes += len(raw)
        if total_bytes > DECLARED_MATERIAL_MAX_TOTAL_BYTES:
            raise ValueError("declared material projection exceeds the two-megabyte total limit")
        try:
            material_text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"declared material path {relative} must be UTF-8 text"
            ) from exc
        projection.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "text": material_text,
            }
        )
    projection.sort(key=lambda item: item["path"])
    if len({item["path"] for item in projection}) != len(projection):
        raise ValueError("declared material paths resolve to duplicate workspace files")
    return projection


def declared_material_refs(
    material_projection: Sequence[Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"path": _text(item.get("path")), "sha256": _text(item.get("sha256"))}
        for item in material_projection
    ]


def generation_lane_instruction(lane_id: Any) -> str:
    normalized = _text(lane_id)
    instruction = GENERATION_LANE_INSTRUCTIONS.get(normalized)
    if instruction is None:
        raise ValueError(
            "generation lane_id must be one controller-owned lane: "
            + ", ".join(sorted(GENERATION_LANE_INSTRUCTIONS))
        )
    return instruction


def canonical_generation_prompt(
    packet: Mapping[str, Any],
    lane_id: str,
    material_projection: Sequence[Mapping[str, Any]] = (),
    *,
    protocol_version: str = GENERATION_PROTOCOL_SCHEMA_VERSION,
) -> str:
    """Return the controller-owned prompt for the packet's explicit origin mode."""

    generation_protocol(packet, protocol_version=protocol_version)
    bounded_packet = json.dumps(
        packet_projection(packet),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    lane_instruction = generation_lane_instruction(lane_id)
    if (
        protocol_version == LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION
        and packet.get("origin_mode") == "phenomenon_first"
    ):
        lane_instruction += ("\nUse only the declared material projection to identify an observation that challenges an existing explanation. Distinguish an empirical anomaly from mere convenient access. State the observation, which premise it challenges, and what would change the question. Material dependence is not a negative value signal. Keep unknown provenance or recording conditions unknown. Do not call exposed material an independent holdout. Retain a single worthwhile direction when that is all the evidence supports; record actual alternatives and a substantive stopping reason without manufacturing companions.")
    elif packet.get("origin_mode") == "phenomenon_first":
        lane_instruction += (
            "\nUse only the declared material projection to identify a consequential "
            "observation or unknown. State the observation, any supported premise it "
            "puts under pressure, and what would change the question. Material "
            "dependence is not a negative value signal. Keep unknown provenance or "
            "recording conditions unknown. Do not call exposed material an independent "
            "holdout. Retain a single worthwhile direction when that is all the "
            "evidence supports; record actual alternatives and a substantive stopping "
            "reason without manufacturing companions."
        )
    focus_note = ""
    if protocol_version == GENERATION_PROTOCOL_SCHEMA_VERSION:
        focus_note = (
            "Use the existing fields to specify one bounded, answerable problem. "
            "In problem, ask the question without prescribing a preferred answer. "
            "In anomaly_or_unknown, name a packet-supported existing explanation or "
            "premise and the observation, condition, or reasoning that puts it under "
            "real pressure; alternatively identify an important unknown and why the "
            "bound evidence leaves it unresolved. Distinguish retrieved facts from "
            "tentative interpretations: a thin search or different scopes do not "
            "establish a dominant assumption or a contradiction. In why_it_matters, "
            "state which substantive judgment an answer would change and why that "
            "change matters. In potential_disconfirmation, specify feasible evidence "
            "or reasoning that would support, revise, or withdraw the framing or "
            "proposed explanation. Compare explanations through implications that "
            "actually differ; compatible explanations may coexist and must not be "
            "presented as mutually exclusive. Descriptive, historical, normative, "
            "and synthesis questions are legitimate without opposing causal "
            "mechanisms or a dramatic contradiction. Treat the lane as a search "
            "lens; state unsupported premises and evidence availability as unknown "
            "instead of inventing support or a final punchline.\n"
        )
    materials = [dict(item) for item in material_projection]
    recon_note = ""
    if packet.get(RECON_INPUT_KEY):
        recon_note = (
            "The TopicPacket carries a literature_reconnaissance array of real, "
            "recently retrieved CNKI/international search results bound to this "
            "direction. Treat it as the current landscape: ground every seed in the "
            "gaps, contradictions, and untested assumptions it actually reveals, and "
            "name the entries a seed responds to inside anomaly_or_unknown. Entries "
            "may carry verified relations (cites, cited-by, co-cited-with, each with "
            "its evidence source): treat a missing relation as unverified rather than "
            "absent, and never assert that two entries conflict, extend, or ignore "
            "each other unless the recorded relations or their claims support it. Do not "
            "restate a question a recon entry already answers, and do not "
            "reverse-engineer topics from whatever data or method is merely "
            "convenient.\n"
        )
    if _text(packet.get("origin_mode")) == "direction_first":
        if materials:
            raise ValueError("direction_first generation cannot receive material inputs")
        return (
            "Generate direction-only problem seeds for the declared lane.\n"
            f"Lane ID: {_text(lane_id)}\n"
            f"Controller instruction: {lane_instruction}\n"
            "Use only the bound TopicPacket below. Do not inspect, infer, or request "
            "workspace data, codebooks, prior topics, manuscripts, workspace literature, "
            "existing methods, or material convenience. Return one JSON array; every "
            "object must use exactly the protocol output fields.\n"
            + recon_note
            + focus_note
            + f"TopicPacket: {bounded_packet}"
        )
    if not materials:
        raise ValueError(
            "workspace/material-origin generation requires a controlled declared-material projection"
        )
    bounded_materials = json.dumps(
        materials,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return (
        "Generate problem seeds from the declared research direction and only the "
        "controller-projected workspace materials below. Produce multiple substantively "
        "distinct candidate families; do not turn filenames, datasets, methods, places, "
        "or years into cosmetic variants. Do not inspect or infer any undeclared workspace "
        "content. Return one JSON array; every object must use exactly the protocol output "
        "fields.\n"
        f"Origin mode: {_text(packet.get('origin_mode'))}\n"
        f"Lane ID: {_text(lane_id)}\n"
        f"Controller instruction: {lane_instruction}\n"
        + recon_note
        + focus_note
        + f"TopicPacket: {bounded_packet}\n"
        f"DeclaredMaterialProjection: {bounded_materials}"
    )


def generation_input_digest(
    packet: Mapping[str, Any],
    material_projection: Sequence[Mapping[str, Any]] = (),
    lane_id: str = "",
) -> str:
    generation_lane_instruction(lane_id)
    return canonical_digest(
        {
            "packet": packet_projection(packet),
            "input_scope": list(generation_input_scope(packet)),
            "declared_material_projection": [
                dict(item) for item in material_projection
            ],
            "lane_id": _text(lane_id),
        }
    )


def generation_dispatch_projection(dispatch: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: dispatch.get(key)
        for key in sorted(GENERATION_DISPATCH_KEYS - {"dispatch_sha256"})
    }


def build_generation_dispatch(
    packet: Mapping[str, Any],
    *,
    lane_id: str,
    run_id: str,
    model_revision: str,
    context_id: str,
    dispatched_at: str,
    material_projection: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    packet_issues = validate_packet(packet, for_generation=True)
    if packet_issues:
        raise ValueError("invalid topic packet: " + "; ".join(packet_issues))
    materials = [dict(item) for item in material_projection]
    prompt = canonical_generation_prompt(packet, lane_id, materials)
    protocol = generation_protocol(packet)
    dispatch: dict[str, Any] = {
        "schema_version": GENERATION_DISPATCH_SCHEMA_VERSION,
        "issuer": ISOLATED_DISPATCHER_ISSUER,
        "packet_sha256": _text(packet.get("packet_sha256")),
        "material_projection_sha256": canonical_digest(materials),
        "material_refs": declared_material_refs(materials),
        "input_scope": list(generation_input_scope(packet)),
        "input_sha256": generation_input_digest(packet, materials, lane_id),
        "prompt": prompt,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "protocol": protocol,
        "protocol_sha256": canonical_digest(protocol),
        "lane_id": _text(lane_id),
        "run_id": _text(run_id),
        "model_revision": _text(model_revision),
        "context_id": _text(context_id),
        "dispatched_at": dispatched_at,
    }
    dispatch["dispatch_sha256"] = canonical_digest(
        generation_dispatch_projection(dispatch)
    )
    issues = validate_generation_dispatch(
        packet,
        dispatch,
        material_projection=materials,
    )
    if issues:
        raise ValueError("invalid generation dispatch: " + "; ".join(issues))
    return dispatch


def validate_generation_dispatch(
    packet: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    material_projection: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    issues: list[str] = []
    if set(dispatch) != GENERATION_DISPATCH_KEYS:
        missing = sorted(GENERATION_DISPATCH_KEYS - set(dispatch))
        extra = sorted(set(dispatch) - GENERATION_DISPATCH_KEYS)
        if missing:
            issues.append("generation dispatch lacks fields: " + ", ".join(missing))
        if extra:
            issues.append(
                "generation dispatch contains unauthorized fields: " + ", ".join(extra)
            )
    if _text(dispatch.get("schema_version")) != GENERATION_DISPATCH_SCHEMA_VERSION:
        issues.append(
            f"generation dispatch schema_version must be {GENERATION_DISPATCH_SCHEMA_VERSION}"
        )
    if _text(dispatch.get("issuer")) != ISOLATED_DISPATCHER_ISSUER:
        issues.append("generation dispatch must be issued by the isolated topic dispatcher")
    if _text(dispatch.get("packet_sha256")) != _text(packet.get("packet_sha256")):
        issues.append("generation dispatch does not bind the current topic packet")
    if list(dispatch.get("input_scope") or []) != list(generation_input_scope(packet)):
        issues.append("generation dispatch input_scope is not the exact origin-specific allowlist")
    origin = _text(packet.get("origin_mode"))
    materials = (
        [dict(item) for item in material_projection]
        if material_projection is not None
        else ([] if origin == "direction_first" else None)
    )
    refs = dispatch.get("material_refs")
    if not isinstance(refs, list) or any(
        not isinstance(item, Mapping)
        or set(item) != {"path", "sha256"}
        or not _text(item.get("path"))
        or not re.fullmatch(r"[a-f0-9]{64}", _text(item.get("sha256")))
        for item in (refs if isinstance(refs, list) else [])
    ):
        issues.append("generation dispatch material_refs must be exact path/SHA-256 bindings")
        refs = []
    if origin == "direction_first" and refs:
        issues.append("direction_first generation dispatch cannot bind material refs")
    if origin != "direction_first" and not refs:
        issues.append("workspace/material-origin dispatch requires declared material refs")
    if materials is not None:
        if refs != declared_material_refs(materials):
            issues.append("generation dispatch material_refs do not match the bounded projection")
        if _text(dispatch.get("material_projection_sha256")) != canonical_digest(materials):
            issues.append("generation dispatch material projection digest is stale")
        try:
            expected_input_sha = generation_input_digest(
                packet,
                materials,
                _text(dispatch.get("lane_id")),
            )
        except ValueError:
            expected_input_sha = ""
        if expected_input_sha and _text(dispatch.get("input_sha256")) != expected_input_sha:
            issues.append("generation dispatch input_sha256 does not bind the bounded origin input")
    elif not re.fullmatch(
        r"[a-f0-9]{64}", _text(dispatch.get("material_projection_sha256"))
    ):
        issues.append("generation dispatch material projection digest is invalid")
    lane_id = _text(dispatch.get("lane_id"))
    try:
        generation_lane_instruction(lane_id)
    except ValueError as exc:
        issues.append(str(exc))
    protocol_version = _generation_protocol_version(
        packet, dispatch.get("protocol_sha256")
    )
    if protocol_version is None:
        issues.append("generation dispatch protocol digest is unsupported")
        protocol_version = GENERATION_PROTOCOL_SCHEMA_VERSION
    if materials is not None:
        try:
            prompt = canonical_generation_prompt(
                packet, lane_id, materials, protocol_version=protocol_version
            )
        except ValueError:
            prompt = ""
        if prompt:
            if dispatch.get("prompt") != prompt:
                issues.append("generation dispatch prompt is not the canonical origin-specific prompt")
            if _text(dispatch.get("prompt_sha256")) != hashlib.sha256(
                prompt.encode("utf-8")
            ).hexdigest():
                issues.append("generation dispatch prompt_sha256 does not match the canonical prompt")
    elif not re.fullmatch(r"[a-f0-9]{64}", _text(dispatch.get("prompt_sha256"))):
        issues.append("generation dispatch prompt_sha256 is invalid")
    protocol = generation_protocol(packet, protocol_version=protocol_version)
    if dispatch.get("protocol") != protocol:
        issues.append("generation dispatch protocol is not the canonical origin-specific protocol")
    if _text(dispatch.get("protocol_sha256")) != canonical_digest(protocol):
        issues.append("generation dispatch protocol_sha256 does not match the canonical protocol")
    for field in ("run_id", "model_revision", "context_id"):
        if len(_text(dispatch.get(field))) < 3:
            issues.append(f"generation dispatch requires a substantive {field}")
    dispatched = _timestamp(dispatch.get("dispatched_at"))
    compiled = _timestamp(packet.get("compiled_at"))
    if dispatched is None:
        issues.append("generation dispatch dispatched_at must be an ISO-8601 timestamp")
    elif compiled is not None and dispatched < compiled:
        issues.append("generation dispatch cannot precede TopicPacket compilation")
    if _text(dispatch.get("dispatch_sha256")) != canonical_digest(
        generation_dispatch_projection(dispatch)
    ):
        issues.append("dispatch_sha256 does not match the dispatcher projection")
    return list(dict.fromkeys(issues))


def _seed_issues(seeds: Any, *, prefix: str = "seeds") -> list[str]:
    issues: list[str] = []
    if not isinstance(seeds, list) or not seeds:
        return [f"{prefix} requires at least one direction-derived problem seed"]
    ids: list[str] = []
    problems: list[str] = []
    for index, seed in enumerate(seeds):
        if not isinstance(seed, Mapping):
            issues.append(f"{prefix}[{index}] must be an object")
            continue
        if set(seed) != SEED_KEYS:
            issues.append(
                f"{prefix}[{index}] contains fields outside the direction-only seed contract"
            )
        seed_id = _text(seed.get("seed_id"))
        if not re.fullmatch(r"SEED-\d{2,}", seed_id):
            issues.append(f"{prefix}[{index}].seed_id must match SEED-##")
        ids.append(seed_id)
        for field in SEED_KEYS - {"seed_id"}:
            if len(_text(seed.get(field))) < 8:
                issues.append(f"{prefix}[{index}].{field} is not substantive")
        problems.append(_normal(seed.get("problem")))
    if len(set(ids)) != len(ids):
        issues.append(f"{prefix} identities must be unique")
    if len(set(problems)) != len(problems):
        issues.append(f"{prefix} contains duplicate problem statements")
    return issues


def _raw_seed_array(raw_output: bytes | str) -> tuple[bytes, list[dict[str, Any]]]:
    raw_bytes = raw_output.encode("utf-8") if isinstance(raw_output, str) else raw_output
    value = json.loads(raw_bytes.decode("utf-8-sig"))
    if not isinstance(value, list):
        raise ValueError("generation raw output must contain one JSON seed array")
    if any(not isinstance(item, dict) for item in value):
        raise ValueError("every generated seed must be one JSON object")
    seeds = [dict(item) for item in value]
    issues = _seed_issues(seeds, prefix="generation raw output")
    if issues:
        raise ValueError("; ".join(issues))
    return raw_bytes, seeds


def generation_receipt_projection(receipt: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: receipt.get(key)
        for key in sorted(
            GENERATION_RECEIPT_KEYS - {"receipt_sha256", "signature"}
        )
    }


def _issue_generation_receipt(
    packet: Mapping[str, Any],
    dispatch: Mapping[str, Any],
    *,
    raw_output: bytes | str,
    issued_at: str,
    receipt_id: str,
    scheduler_session_id: str,
    scheduler_key_id: str,
    signing_key: bytes,
    material_projection: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    materials = [dict(item) for item in material_projection]
    dispatch_issues = validate_generation_dispatch(
        packet,
        dispatch,
        material_projection=materials,
    )
    if dispatch_issues:
        raise ValueError("invalid generation dispatch: " + "; ".join(dispatch_issues))
    raw_bytes, seeds = _raw_seed_array(raw_output)
    issued = _timestamp(issued_at)
    if issued is None:
        raise ValueError("issued_at must be an ISO-8601 timestamp")
    expires_at = (
        issued + timedelta(seconds=SCHEDULER_RECEIPT_TTL_SECONDS)
    ).isoformat().replace("+00:00", "Z")
    receipt: dict[str, Any] = {
        "schema_version": GENERATION_RECEIPT_SCHEMA_VERSION,
        "issuer": ISOLATED_DISPATCHER_ISSUER,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "receipt_id": receipt_id,
        "scheduler_session_id": scheduler_session_id,
        "scheduler_key_id": scheduler_key_id,
        "dispatched_at": dispatch.get("dispatched_at"),
        "dispatch_sha256": dispatch.get("dispatch_sha256"),
        "packet_sha256": dispatch.get("packet_sha256"),
        "material_projection_sha256": dispatch.get("material_projection_sha256"),
        "material_refs": dispatch.get("material_refs"),
        "input_scope": list(dispatch.get("input_scope") or []),
        "input_sha256": dispatch.get("input_sha256"),
        "prompt_sha256": dispatch.get("prompt_sha256"),
        "protocol_sha256": dispatch.get("protocol_sha256"),
        "lane_id": dispatch.get("lane_id"),
        "run_id": dispatch.get("run_id"),
        "model_revision": dispatch.get("model_revision"),
        "context_id": dispatch.get("context_id"),
        "raw_output_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "seeds": seeds,
        "seed_output_digest": canonical_digest(seeds),
    }
    receipt["receipt_sha256"] = canonical_digest(
        generation_receipt_projection(receipt)
    )
    receipt["signature"] = hmac.new(
        signing_key,
        receipt["receipt_sha256"].encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    issues = validate_generation_receipt(
        packet,
        receipt,
        verification_key=signing_key,
        material_projection=materials,
    )
    if issues:
        raise ValueError("invalid generation receipt: " + "; ".join(issues))
    return receipt


def _receipt_dispatch(
    receipt: Mapping[str, Any],
    packet: Mapping[str, Any],
    material_projection: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    lane_id = _text(receipt.get("lane_id"))
    materials = [dict(item) for item in material_projection]
    protocol_version = _generation_protocol_version(
        packet, receipt.get("protocol_sha256")
    )
    if protocol_version is None:
        raise ValueError("generation receipt protocol digest is unsupported")
    prompt = canonical_generation_prompt(
        packet, lane_id, materials, protocol_version=protocol_version
    )
    return {
        "schema_version": GENERATION_DISPATCH_SCHEMA_VERSION,
        "issuer": receipt.get("issuer"),
        "packet_sha256": receipt.get("packet_sha256"),
        "material_projection_sha256": receipt.get("material_projection_sha256"),
        "material_refs": receipt.get("material_refs"),
        "input_scope": receipt.get("input_scope"),
        "input_sha256": receipt.get("input_sha256"),
        "prompt": prompt,
        "prompt_sha256": receipt.get("prompt_sha256"),
        "protocol": generation_protocol(packet, protocol_version=protocol_version),
        "protocol_sha256": receipt.get("protocol_sha256"),
        "lane_id": lane_id,
        "run_id": receipt.get("run_id"),
        "model_revision": receipt.get("model_revision"),
        "context_id": receipt.get("context_id"),
        "dispatched_at": receipt.get("dispatched_at"),
        "dispatch_sha256": receipt.get("dispatch_sha256"),
    }


def validate_generation_receipt(
    packet: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    verification_key: bytes | None = None,
    material_projection: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    issues: list[str] = []
    if set(receipt) != GENERATION_RECEIPT_KEYS:
        missing = sorted(GENERATION_RECEIPT_KEYS - set(receipt))
        extra = sorted(set(receipt) - GENERATION_RECEIPT_KEYS)
        if missing:
            issues.append("generation receipt lacks fields: " + ", ".join(missing))
        if extra:
            issues.append(
                "generation receipt contains unauthorized fields: " + ", ".join(extra)
            )
    if _text(receipt.get("schema_version")) != GENERATION_RECEIPT_SCHEMA_VERSION:
        issues.append(
            f"generation receipt schema_version must be {GENERATION_RECEIPT_SCHEMA_VERSION}"
        )
    if _text(receipt.get("issuer")) != ISOLATED_DISPATCHER_ISSUER:
        issues.append("generation receipt must be issued by the isolated topic dispatcher")
    if not re.fullmatch(r"TOPIC-RUN-[a-f0-9]{32}", _text(receipt.get("receipt_id"))):
        issues.append("generation receipt receipt_id is invalid")
    if not re.fullmatch(
        r"TOPIC-SCHED-[a-f0-9]{32}",
        _text(receipt.get("scheduler_session_id")),
    ):
        issues.append("generation receipt scheduler_session_id is invalid")
    if not re.fullmatch(r"TOPIC-KEY-[a-f0-9]{32}", _text(receipt.get("scheduler_key_id"))):
        issues.append("generation receipt scheduler_key_id is invalid")
    origin = _text(packet.get("origin_mode"))
    materials = (
        [dict(item) for item in material_projection]
        if material_projection is not None
        else ([] if origin == "direction_first" else None)
    )
    if materials is not None:
        try:
            dispatch_issues = validate_generation_dispatch(
                packet,
                _receipt_dispatch(receipt, packet, materials),
                material_projection=materials,
            )
        except ValueError as exc:
            dispatch_issues = [str(exc)]
        issues.extend(
            "generation receipt dispatch binding: " + item
            for item in dispatch_issues
        )
    else:
        if _text(receipt.get("packet_sha256")) != _text(packet.get("packet_sha256")):
            issues.append("generation receipt is bound to a different topic packet")
        if list(receipt.get("input_scope") or []) != list(generation_input_scope(packet)):
            issues.append("generation receipt input scope is stale")
        if _generation_protocol_version(packet, receipt.get("protocol_sha256")) is None:
            issues.append("generation receipt protocol digest is stale")
        refs = receipt.get("material_refs")
        if not isinstance(refs, list) or not refs:
            issues.append("workspace/material-origin receipt requires declared material refs")
        for field in (
            "dispatch_sha256",
            "material_projection_sha256",
            "input_sha256",
            "prompt_sha256",
        ):
            if not re.fullmatch(r"[a-f0-9]{64}", _text(receipt.get(field))):
                issues.append(f"generation receipt {field} is invalid")
    issued = _timestamp(receipt.get("issued_at"))
    dispatched = _timestamp(receipt.get("dispatched_at"))
    expires = _timestamp(receipt.get("expires_at"))
    if issued is None:
        issues.append("generation receipt issued_at must be an ISO-8601 timestamp")
    elif dispatched is None or issued < dispatched:
        issues.append("generation receipt cannot be issued before its dispatch")
    if expires is None:
        issues.append("generation receipt expires_at must be an ISO-8601 timestamp")
    elif issued is None or expires <= issued:
        issues.append("generation receipt expires_at must follow issued_at")
    if not re.fullmatch(r"[a-f0-9]{64}", _text(receipt.get("raw_output_sha256"))):
        issues.append("generation receipt raw_output_sha256 must be one SHA-256 digest")
    seeds = receipt.get("seeds")
    issues.extend(_seed_issues(seeds, prefix="generation receipt seeds"))
    if _text(receipt.get("seed_output_digest")) != canonical_digest(
        seeds if isinstance(seeds, list) else []
    ):
        issues.append("generation receipt seed_output_digest does not bind its parsed seeds")
    if _text(receipt.get("receipt_sha256")) != canonical_digest(
        generation_receipt_projection(receipt)
    ):
        issues.append("receipt_sha256 does not match the generation receipt projection")
    signature = _text(receipt.get("signature"))
    if not re.fullmatch(r"[a-f0-9]{64}", signature):
        issues.append("generation receipt requires one scheduler HMAC signature")
    elif verification_key is None:
        issues.append("generation receipt signature lacks a scheduler verification key")
    else:
        expected_signature = hmac.new(
            verification_key,
            _text(receipt.get("receipt_sha256")).encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            issues.append("generation receipt scheduler signature does not match")
    return list(dict.fromkeys(issues))


def _utc_now_stamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def seed_output_schema(*, depth: str = "", lane_count: int = 0) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "array",
        "minItems": 1,
        "items": {
            "type": "object",
            "required": sorted(SEED_KEYS),
            "properties": {
                "seed_id": {"type": "string", "pattern": r"^SEED-[0-9]{2,}$"},
                "candidate_family": {"type": "string", "minLength": 4},
                "problem": {"type": "string", "minLength": 8},
                "anomaly_or_unknown": {"type": "string", "minLength": 8},
                "why_it_matters": {"type": "string", "minLength": 8},
                "potential_disconfirmation": {"type": "string", "minLength": 8},
            },
            "additionalProperties": False,
        },
    }
    if _text(depth) == "broad" and lane_count >= 1:
        low, high = BROAD_SEED_WINDOW
        per_lane_min = max(1, -(-low // lane_count))
        per_lane_max = max(per_lane_min, high // lane_count)
        schema["minItems"] = per_lane_min
        schema["maxItems"] = per_lane_max
        schema["description"] = (
            f"Return {per_lane_min}-{per_lane_max} seeds for this lane; "
            f"{lane_count} isolated lane(s) must together seal "
            f"{low}-{high} seeds for broad divergence."
        )
    return schema

GenerationRunner = Callable[[Mapping[str, Any]], bytes | str]
KEY_STORE_SCHEMA_VERSION = "avereth-topic-scheduler-key-store/v1"
_SCHEDULER_CONSTRUCTION_TOKEN = object()
_CAPABILITY_TOKEN = object()
_ACTIVE_KEY_STORES: dict[str, "TopicSchedulerKeyStore"] = {}


def default_scheduler_key_store_path() -> Path:
    override = _text(os.environ.get("AVERETH_TOPIC_SCHEDULER_KEY_STORE"))
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        state_root = Path(
            os.environ.get("LOCALAPPDATA")
            or (Path.home() / "AppData" / "Local")
        )
    else:
        state_root = Path(
            os.environ.get("XDG_STATE_HOME")
            or (Path.home() / ".local" / "state")
        )
    return state_root / "Avereth" / "topic_scheduler_keys.json"


class TopicSchedulerKeyStore:
    """Controlled scheduler ledger; secrets never enter research artifacts."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path.resolve() if path is not None else None
        self._memory: dict[str, Any] = {
            "schema_version": KEY_STORE_SCHEMA_VERSION,
            "sessions": {},
        }

    def _load(self) -> dict[str, Any]:
        if self.path is None or not self.path.is_file():
            return json.loads(json.dumps(self._memory))
        value = json.loads(self.path.read_text(encoding="utf-8-sig"))
        if (
            not isinstance(value, dict)
            or value.get("schema_version") != KEY_STORE_SCHEMA_VERSION
            or not isinstance(value.get("sessions"), dict)
        ):
            raise ValueError("topic scheduler key store is invalid")
        return value

    def _save(self, payload: Mapping[str, Any]) -> None:
        rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if self.path is None:
            self._memory = json.loads(rendered)
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.path)

    def create_session(
        self,
        *,
        key_id: str,
        session_id: str,
        key: bytes,
    ) -> None:
        payload = self._load()
        sessions = payload["sessions"]
        if key_id in sessions:
            raise ValueError("topic scheduler key id already exists")
        sessions[key_id] = {
            "session_id": session_id,
            "key_b64": base64.b64encode(key).decode("ascii"),
            "receipts": {},
        }
        self._save(payload)
        _ACTIVE_KEY_STORES[key_id] = self

    def record_receipt(self, *, key_id: str, receipt_id: str, digest: str) -> None:
        payload = self._load()
        session = payload["sessions"].get(key_id)
        if not isinstance(session, dict):
            raise ValueError("topic scheduler key id is unknown")
        receipts = session.setdefault("receipts", {})
        if receipt_id in receipts:
            raise ValueError("topic scheduler receipt id already exists")
        receipts[receipt_id] = {"digest": digest, "consumed": False}
        self._save(payload)

    def receipt_state(self, *, key_id: str, receipt_id: str) -> tuple[str, bool] | None:
        payload = self._load()
        session = payload["sessions"].get(key_id)
        if not isinstance(session, dict):
            return None
        record = (session.get("receipts") or {}).get(receipt_id)
        if not isinstance(record, dict):
            return None
        return (_text(record.get("digest")), record.get("consumed") is True)

    def consume_receipts(self, *, key_id: str, receipt_ids: Sequence[str]) -> None:
        payload = self._load()
        session = payload["sessions"].get(key_id)
        if not isinstance(session, dict):
            raise ValueError("topic scheduler key id is unknown")
        receipts = session.get("receipts") or {}
        for receipt_id in receipt_ids:
            record = receipts.get(receipt_id)
            if not isinstance(record, dict) or record.get("consumed") is True:
                raise ValueError("topic scheduler receipt cannot be consumed")
        for receipt_id in receipt_ids:
            receipts[receipt_id]["consumed"] = True
        self._save(payload)

    def verification_key(self, *, key_id: str, session_id: str) -> bytes | None:
        payload = self._load()
        session = payload["sessions"].get(key_id)
        if not isinstance(session, dict) or _text(session.get("session_id")) != session_id:
            return None
        try:
            value = base64.b64decode(_text(session.get("key_b64")), validate=True)
        except (ValueError, TypeError):
            return None
        return value if len(value) == 32 else None


def resolve_scheduler_key_store(
    key_id: str,
    supplied: TopicSchedulerKeyStore | None = None,
) -> TopicSchedulerKeyStore | None:
    if supplied is not None:
        return supplied
    if key_id in _ACTIVE_KEY_STORES:
        return _ACTIVE_KEY_STORES[key_id]
    return TopicSchedulerKeyStore(default_scheduler_key_store_path())


class _ControlledGenerationCapability:
    """Host-owned capture adapter; ordinary scheduler calls cannot replace it."""

    def __init__(self, capture: GenerationRunner, *, _token: object) -> None:
        if _token is not _CAPABILITY_TOKEN:
            raise ValueError("generation capability must be issued by the orchestrator")
        self._capture = capture

    def capture(self, bounded_input: Mapping[str, Any]) -> HostCapture:
        return self._capture(bounded_input)


class _CodexExecGenerationCapability(_ControlledGenerationCapability):
    def __init__(
        self,
        *,
        model_revision: str,
        timeout_seconds: int,
        output_schema: Mapping[str, Any] | None = None,
    ) -> None:
        self.model_revision = _text(model_revision)
        self.timeout_seconds = timeout_seconds
        self._output_schema = dict(output_schema) if output_schema else None
        super().__init__(self._capture_codex, _token=_CAPABILITY_TOKEN)

    def _capture_codex(self, bounded_input: Mapping[str, Any]) -> HostCapture:
        if set(bounded_input) != {
            "packet",
            "declared_material_projection",
            "prompt",
            "protocol",
        }:
            raise ValueError("CodexExec generation received an unauthorized input scope")
        return run_codex_exec_isolated(
            prompt=_text(bounded_input.get("prompt")),
            output_schema=self._output_schema or seed_output_schema(),
            model_revision=self.model_revision,
            timeout_seconds=self.timeout_seconds,
        )


class _ClaudeExecGenerationCapability(_ControlledGenerationCapability):
    def __init__(
        self,
        *,
        model_revision: str,
        timeout_seconds: int,
        output_schema: Mapping[str, Any] | None = None,
    ) -> None:
        self.model_revision = _text(model_revision)
        self.timeout_seconds = timeout_seconds
        self._output_schema = dict(output_schema) if output_schema else None
        super().__init__(self._capture_claude, _token=_CAPABILITY_TOKEN)

    def _capture_claude(self, bounded_input: Mapping[str, Any]) -> HostCapture:
        if set(bounded_input) != {
            "packet",
            "declared_material_projection",
            "prompt",
            "protocol",
        }:
            raise ValueError("ClaudeExec generation received an unauthorized input scope")
        return run_claude_exec_isolated(
            prompt=_text(bounded_input.get("prompt")),
            output_schema=self._output_schema or seed_output_schema(),
            model_revision=self.model_revision,
            timeout_seconds=self.timeout_seconds,
        )


class _AgentDeclaredGenerationCapability(_ControlledGenerationCapability):
    def __init__(self, *, model_revision: str, responses_dir: Path) -> None:
        self.model_revision = _text(model_revision)
        self.responses_dir = Path(responses_dir)
        super().__init__(self._capture_agent, _token=_CAPABILITY_TOKEN)

    def _capture_agent(self, bounded_input: Mapping[str, Any]) -> HostCapture:
        if set(bounded_input) != {
            "packet",
            "declared_material_projection",
            "prompt",
            "protocol",
        }:
            raise ValueError("agent-declared generation received an unauthorized input scope")
        return read_agent_capture(
            self.responses_dir,
            prompt=_text(bounded_input.get("prompt")),
            model_revision=self.model_revision,
        )


class TopicGenerationScheduler:
    """Dispatch through a host-owned capability and seal its captured output.

    Production callers cannot submit a runner, prompt, or raw output to
    :meth:`run`.  HMAC secrets and the one-time receipt ledger stay in the
    controlled key store named by ``scheduler_key_id``; no secret is written to
    the research decision or seed seal.  This is local controller provenance,
    not a defense against the machine owner.
    """

    def __init__(
        self,
        packet: Mapping[str, Any],
        *,
        capability: _ControlledGenerationCapability,
        key_store: TopicSchedulerKeyStore,
        material_projection: Sequence[Mapping[str, Any]],
        _token: object,
    ) -> None:
        if _token is not _SCHEDULER_CONSTRUCTION_TOKEN:
            raise ValueError("topic scheduler must be constructed by the orchestrator")
        issues = validate_packet(packet, for_generation=True)
        if issues:
            raise ValueError("invalid topic packet: " + "; ".join(issues))
        self.packet = dict(packet)
        self.material_projection = [dict(item) for item in material_projection]
        origin = _text(self.packet.get("origin_mode"))
        if origin == "direction_first" and self.material_projection:
            raise ValueError("direction_first scheduler cannot receive declared materials")
        if origin != "direction_first" and not self.material_projection:
            raise ValueError(
                "workspace/material-origin scheduler requires declared material inputs"
            )
        self.session_id = "TOPIC-SCHED-" + uuid.uuid4().hex
        self.key_id = "TOPIC-KEY-" + uuid.uuid4().hex
        self._signing_key = secrets.token_bytes(32)
        self._capability = capability
        self._key_store = key_store
        self._contexts: set[str] = set()
        self._key_store.create_session(
            key_id=self.key_id,
            session_id=self.session_id,
            key=self._signing_key,
        )

    @classmethod
    def _from_orchestrator(
        cls,
        packet: Mapping[str, Any],
        *,
        capability: _ControlledGenerationCapability,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
    ) -> "TopicGenerationScheduler":
        """Internal host wiring for the real isolated-generation capability."""

        if not isinstance(capability, _ControlledGenerationCapability):
            raise ValueError("orchestrator generation capability is invalid")
        return cls(
            packet,
            capability=capability,
            key_store=key_store
            or TopicSchedulerKeyStore(default_scheduler_key_store_path()),
            material_projection=declared_material_projection(packet, workspace_root),
            _token=_SCHEDULER_CONSTRUCTION_TOKEN,
        )

    @classmethod
    def from_codex_exec(
        cls,
        packet: Mapping[str, Any],
        *,
        model_revision: str,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
        timeout_seconds: int = 180,
        lane_count: int = 0,
    ) -> "TopicGenerationScheduler":
        """Reachable production factory backed by a fresh projectless CodexExec run."""

        return cls._from_orchestrator(
            packet,
            capability=_CodexExecGenerationCapability(
                model_revision=model_revision,
                timeout_seconds=timeout_seconds,
                output_schema=seed_output_schema(
                    depth=_text(packet.get("brainstorm_depth")),
                    lane_count=lane_count,
                ),
            ),
            key_store=key_store,
            workspace_root=workspace_root,
        )

    @classmethod
    def from_claude_exec(
        cls,
        packet: Mapping[str, Any],
        *,
        model_revision: str,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
        timeout_seconds: int = 180,
        lane_count: int = 0,
    ) -> "TopicGenerationScheduler":
        """Production factory backed by a fresh projectless ClaudeExec run."""

        return cls._from_orchestrator(
            packet,
            capability=_ClaudeExecGenerationCapability(
                model_revision=model_revision,
                timeout_seconds=timeout_seconds,
                output_schema=seed_output_schema(
                    depth=_text(packet.get("brainstorm_depth")),
                    lane_count=lane_count,
                ),
            ),
            key_store=key_store,
            workspace_root=workspace_root,
        )

    @classmethod
    def from_agent_declared(
        cls,
        packet: Mapping[str, Any],
        *,
        model_revision: str,
        responses_dir: Path,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
    ) -> "TopicGenerationScheduler":
        """Production factory for prompt-bound, caller-relayed subagent captures."""

        return cls._from_orchestrator(
            packet,
            capability=_AgentDeclaredGenerationCapability(
                model_revision=model_revision,
                responses_dir=responses_dir,
            ),
            key_store=key_store,
            workspace_root=workspace_root,
        )

    @classmethod
    def from_runner(
        cls,
        packet: Mapping[str, Any],
        *,
        runner: str,
        model_revision: str,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
        timeout_seconds: int = 180,
        responses_dir: Path | None = None,
        lane_count: int = 0,
    ) -> "TopicGenerationScheduler":
        normalized = ensure_runner_allowed(runner)
        if normalized == "codex-exec":
            return cls.from_codex_exec(
                packet,
                model_revision=model_revision,
                key_store=key_store,
                workspace_root=workspace_root,
                timeout_seconds=timeout_seconds,
                lane_count=lane_count,
            )
        if normalized == "claude-exec":
            return cls.from_claude_exec(
                packet,
                model_revision=model_revision,
                key_store=key_store,
                workspace_root=workspace_root,
                timeout_seconds=timeout_seconds,
                lane_count=lane_count,
            )
        if responses_dir is None:
            raise ValueError("agent-declared generation requires --responses")
        return cls.from_agent_declared(
            packet,
            model_revision=model_revision,
            responses_dir=responses_dir,
            key_store=key_store,
            workspace_root=workspace_root,
        )

    @classmethod
    def _for_test(
        cls,
        packet: Mapping[str, Any],
        *,
        test_capture: GenerationRunner,
        key_store: TopicSchedulerKeyStore | None = None,
        workspace_root: Path | None = None,
        test_run_id: str = "test-topic-run",
        test_model_revision: str = "test-topic-model",
        test_context_id: str = "test-topic-context",
    ) -> "TopicGenerationScheduler":
        """Explicit test-only injection point; never used by production routing."""

        def capture(bounded_input: Mapping[str, Any]) -> HostCapture:
            raw_output = test_capture(bounded_input)
            if not isinstance(raw_output, (bytes, str)):
                raise ValueError("test capture must return raw bytes or text")
            return HostCapture(
                raw_output=(
                    raw_output.encode("utf-8")
                    if isinstance(raw_output, str)
                    else raw_output
                ),
                run_id=test_run_id,
                model_revision=test_model_revision,
                context_id=test_context_id,
            )

        capability = _ControlledGenerationCapability(
            capture,
            _token=_CAPABILITY_TOKEN,
        )
        return cls(
            packet,
            capability=capability,
            key_store=key_store or TopicSchedulerKeyStore(),
            material_projection=declared_material_projection(packet, workspace_root),
            _token=_SCHEDULER_CONSTRUCTION_TOKEN,
        )

    def run(
        self,
        *,
        lane_id: str,
        dispatched_at: str,
        issued_at: str,
    ) -> dict[str, Any]:
        """Dispatch the exact bounded input and capture the runner's raw output."""

        issues = validate_packet(self.packet, for_generation=True)
        if issues:
            raise ValueError("invalid topic packet: " + "; ".join(issues))
        prompt = canonical_generation_prompt(
            self.packet,
            lane_id,
            self.material_projection,
        )
        runner_input = {
            "packet": json.loads(
                json.dumps(packet_projection(self.packet), ensure_ascii=False)
            ),
            "declared_material_projection": json.loads(
                json.dumps(self.material_projection, ensure_ascii=False)
            ),
            "prompt": prompt,
            "protocol": json.loads(
                json.dumps(generation_protocol(self.packet), ensure_ascii=False)
            ),
        }
        capture = self._capability.capture(runner_input)
        if not isinstance(capture, HostCapture):
            raise ValueError("generation capability returned no controlled HostCapture")
        normalized_context = _text(capture.context_id)
        if normalized_context in self._contexts:
            raise ValueError("generation contexts cannot be reused within one scheduler session")
        dispatch = build_generation_dispatch(
            self.packet,
            lane_id=lane_id,
            run_id=capture.run_id,
            model_revision=capture.model_revision,
            context_id=normalized_context,
            dispatched_at=dispatched_at,
            material_projection=self.material_projection,
        )
        receipt_id = "TOPIC-RUN-" + uuid.uuid4().hex
        receipt = _issue_generation_receipt(
            self.packet,
            dispatch,
            raw_output=capture.raw_output,
            issued_at=issued_at,
            receipt_id=receipt_id,
            scheduler_session_id=self.session_id,
            scheduler_key_id=self.key_id,
            signing_key=self._signing_key,
            material_projection=self.material_projection,
        )
        self._key_store.record_receipt(
            key_id=self.key_id,
            receipt_id=receipt_id,
            digest=_text(receipt.get("receipt_sha256")),
        )
        self._contexts.add(normalized_context)
        return receipt

    def seal(
        self,
        *,
        generation_receipts: Sequence[Mapping[str, Any]],
        sealed_at: str,
    ) -> dict[str, Any]:
        """Consume fresh receipts once and assemble their deterministic seeds."""

        receipts = [dict(item) for item in generation_receipts]
        if not receipts:
            raise ValueError("seed seal requires at least one scheduler generation receipt")
        seen: set[str] = set()
        sealed = _timestamp(sealed_at)
        if sealed is None:
            raise ValueError("sealed_at must be an ISO-8601 timestamp")
        for receipt in receipts:
            receipt_id = _text(receipt.get("receipt_id"))
            if receipt_id in seen:
                raise ValueError("a generation receipt cannot be supplied twice")
            seen.add(receipt_id)
            state = self._key_store.receipt_state(
                key_id=self.key_id,
                receipt_id=receipt_id,
            )
            if state is None:
                raise ValueError("generation receipt is unknown to this scheduler ledger")
            ledger_digest, consumed = state
            if consumed:
                raise ValueError("generation receipt has already been consumed")
            if ledger_digest != _text(receipt.get("receipt_sha256")):
                raise ValueError("generation receipt differs from the scheduler ledger")
            if _text(receipt.get("scheduler_key_id")) != self.key_id:
                raise ValueError("generation receipt belongs to a different scheduler key")
            issues = validate_generation_receipt(
                self.packet,
                receipt,
                verification_key=self._signing_key,
                material_projection=self.material_projection,
            )
            if issues:
                raise ValueError("invalid generation receipt: " + "; ".join(issues))
            expires = _timestamp(receipt.get("expires_at"))
            if expires is None or sealed > expires:
                raise ValueError("generation receipt expired before seed sealing")
        seal = _assemble_seed_seal(
            self.packet,
            generation_receipts=receipts,
            sealed_at=sealed_at,
            scheduler_session_id=self.session_id,
            scheduler_key_id=self.key_id,
            key_store=self._key_store,
            material_projection=self.material_projection,
        )
        self._key_store.consume_receipts(
            key_id=self.key_id,
            receipt_ids=sorted(seen),
        )
        validation = validate_seed_seal(
            self.packet,
            seal,
            key_store=self._key_store,
            material_projection=self.material_projection,
        )
        if validation:
            raise ValueError("invalid finalized seed seal: " + "; ".join(validation))
        return seal


def seed_seal_projection(seal: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: seal.get(key)
        for key in (
            "schema_version",
            "packet_sha256",
            "sealed_at",
            "scheduler_session_id",
            "scheduler_key_id",
            "generation_receipts",
            "seed_count",
            "seeds",
        )
    }


def sealed_seed_portfolio(
    receipt_bound_seeds: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Derive the seal's combined seed array from receipt-bound seeds.

    Isolated generation lanes cannot coordinate their seed numbering, so the
    seal renumbers the receipt-ordered union sequentially; every other seed
    field stays identical to its generation receipt.
    """

    portfolio: list[dict[str, Any]] = []
    for index, seed in enumerate(receipt_bound_seeds, start=1):
        item = dict(seed)
        item["seed_id"] = f"SEED-{index:02d}"
        portfolio.append(item)
    return portfolio


def _assemble_seed_seal(
    packet: Mapping[str, Any],
    *,
    generation_receipts: Sequence[Mapping[str, Any]],
    sealed_at: str,
    scheduler_session_id: str,
    scheduler_key_id: str,
    key_store: TopicSchedulerKeyStore,
    material_projection: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    issues = validate_packet(packet, for_generation=True)
    if issues:
        raise ValueError("invalid topic packet: " + "; ".join(issues))
    receipts = [dict(item) for item in generation_receipts]
    if not receipts:
        raise ValueError("seed seal requires at least one dispatcher-issued generation receipt")
    seeds = sealed_seed_portfolio(
        [
            seed
            for receipt in receipts
            for seed in receipt.get("seeds") or []
            if isinstance(seed, Mapping)
        ]
    )
    seal: dict[str, Any] = {
        "schema_version": SEED_SEAL_SCHEMA_VERSION,
        "packet_sha256": _text(packet.get("packet_sha256")),
        "sealed_at": sealed_at,
        "scheduler_session_id": scheduler_session_id,
        "scheduler_key_id": scheduler_key_id,
        "generation_receipts": receipts,
        "seed_count": len(seeds),
        "seeds": seeds,
    }
    seal["seed_portfolio_sha256"] = canonical_digest(seed_seal_projection(seal))
    validation = validate_seed_seal(
        packet,
        seal,
        key_store=key_store,
        require_consumed=False,
        material_projection=material_projection,
    )
    if validation:
        raise ValueError("invalid seed seal: " + "; ".join(validation))
    return seal


def validate_seed_seal(
    packet: Mapping[str, Any],
    seal: Mapping[str, Any],
    *,
    key_store: TopicSchedulerKeyStore | None = None,
    require_consumed: bool = True,
    material_projection: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    issues: list[str] = []
    expected_keys = {
        "schema_version",
        "packet_sha256",
        "sealed_at",
        "scheduler_session_id",
        "scheduler_key_id",
        "generation_receipts",
        "seed_count",
        "seeds",
        "seed_portfolio_sha256",
    }
    if set(seal) != expected_keys:
        missing = sorted(expected_keys - set(seal))
        extra = sorted(set(seal) - expected_keys)
        if missing:
            issues.append("seed seal lacks fields: " + ", ".join(missing))
        if extra:
            issues.append("seed seal contains unauthorized fields: " + ", ".join(extra))
    if _text(seal.get("schema_version")) != SEED_SEAL_SCHEMA_VERSION:
        issues.append(f"seed seal schema_version must be {SEED_SEAL_SCHEMA_VERSION}")
    if _text(seal.get("packet_sha256")) != _text(packet.get("packet_sha256")):
        issues.append("seed seal does not bind the current topic packet")
    sealed = _timestamp(seal.get("sealed_at"))
    compiled = _timestamp(packet.get("compiled_at"))
    if sealed is None:
        issues.append("seed seal sealed_at must be an ISO-8601 timestamp")
    elif compiled is not None and sealed < compiled:
        issues.append("seed portfolio cannot be sealed before the topic packet was compiled")

    scheduler_session_id = _text(seal.get("scheduler_session_id"))
    if not re.fullmatch(r"TOPIC-SCHED-[a-f0-9]{32}", scheduler_session_id):
        issues.append("seed seal scheduler_session_id is invalid")
    scheduler_key_id = _text(seal.get("scheduler_key_id"))
    if not re.fullmatch(r"TOPIC-KEY-[a-f0-9]{32}", scheduler_key_id):
        issues.append("seed seal scheduler_key_id is invalid")
    resolved_store = resolve_scheduler_key_store(scheduler_key_id, key_store)
    verification_key = (
        resolved_store.verification_key(
            key_id=scheduler_key_id,
            session_id=scheduler_session_id,
        )
        if resolved_store is not None
        else None
    )
    if verification_key is None:
        issues.append(
            "seed seal scheduler key is unavailable from the controlled key store"
        )

    receipts = seal.get("generation_receipts")
    if not isinstance(receipts, list) or not receipts:
        issues.append("seed seal requires dispatcher-issued generation receipts")
        receipts = []
    context_ids: list[str] = []
    raw_digests: list[str] = []
    receipt_bound_seeds: list[dict[str, Any]] = []
    origin = _text(packet.get("origin_mode"))
    materials = (
        [dict(item) for item in material_projection]
        if material_projection is not None
        else ([] if origin == "direction_first" else None)
    )
    if origin != "direction_first" and materials is None:
        issues.append(
            "seed seal validation requires the current declared material projection"
        )
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            issues.append(f"generation_receipts[{index}] must be an object")
            continue
        for message in validate_generation_receipt(
            packet,
            receipt,
            verification_key=verification_key,
            material_projection=materials,
        ):
            issues.append(f"generation_receipts[{index}]: {message}")
        if _text(receipt.get("scheduler_session_id")) != scheduler_session_id:
            issues.append(
                f"generation_receipts[{index}] belongs to a different scheduler session"
            )
        if _text(receipt.get("scheduler_key_id")) != scheduler_key_id:
            issues.append(
                f"generation_receipts[{index}] belongs to a different scheduler key"
            )
        ledger_state = (
            resolved_store.receipt_state(
                key_id=scheduler_key_id,
                receipt_id=_text(receipt.get("receipt_id")),
            )
            if resolved_store is not None
            else None
        )
        if ledger_state is None:
            issues.append(f"generation_receipts[{index}] is unknown to the key-store ledger")
        else:
            ledger_digest, consumed = ledger_state
            if ledger_digest != _text(receipt.get("receipt_sha256")):
                issues.append(
                    f"generation_receipts[{index}] differs from the key-store ledger"
                )
            if require_consumed and not consumed:
                issues.append(
                    f"generation_receipts[{index}] has not been consumed by seed sealing"
                )
        context_ids.append(_text(receipt.get("context_id")))
        raw_digests.append(_text(receipt.get("raw_output_sha256")))
        receipt_bound_seeds.extend(
            dict(seed)
            for seed in receipt.get("seeds") or []
            if isinstance(seed, Mapping)
        )
        issued = _timestamp(receipt.get("issued_at"))
        if sealed is not None and (issued is None or sealed < issued):
            issues.append(
                f"generation_receipts[{index}] cannot be sealed before receipt issuance"
            )
        expires = _timestamp(receipt.get("expires_at"))
        if sealed is not None and (expires is None or sealed > expires):
            issues.append(f"generation_receipts[{index}] expired before seed sealing")
    if len(set(context_ids)) != len(context_ids):
        issues.append("generation receipts must use distinct context identities")
    if len(set(raw_digests)) != len(raw_digests):
        issues.append("generation receipts must bind distinct raw outputs")

    seeds = seal.get("seeds")
    if not isinstance(seeds, list):
        issues.append("seed seal seeds must be one array")
        seeds = []
    issues.extend(_seed_issues(seeds, prefix="seed seal seeds"))
    if seeds != sealed_seed_portfolio(receipt_bound_seeds):
        issues.append("seed seal seeds must be derived exactly from its generation receipts")
    if seal.get("seed_count") != len(seeds):
        issues.append("seed_count does not match the sealed seed array")
    if _text(seal.get("seed_portfolio_sha256")) != canonical_digest(
        seed_seal_projection(seal)
    ):
        issues.append("seed_portfolio_sha256 does not match the sealed direction-only seeds")
    return list(dict.fromkeys(issues))


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _write_json(path: Path | None, payload: Mapping[str, Any]) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path is None:
        print(rendered, end="")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)
    print(f"Wrote {path}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("workspace", type=Path)
    compile_parser.add_argument("--current-user-request", required=True)
    compile_parser.add_argument(
        "--compiled-at",
        help="ISO-8601; defaults to the script's own UTC clock",
    )
    compile_parser.add_argument("--declared-workspace-scope", action="append", default=[])
    compile_parser.add_argument(
        "--recon",
        type=Path,
        help=(
            "JSON array of fresh CNKI/exa/OpenAlex retrieval entries "
            "(query/source/title/year/claim/identifier/retrieved_at [+authors/venue]) "
            "binding the real literature landscape into seed generation; "
            "required for direction_first"
        ),
    )
    compile_parser.add_argument("--output", type=Path)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("packet", type=Path)
    validate_parser.add_argument("--workspace", type=Path)
    validate_parser.add_argument(
        "--for-generation",
        action="store_true",
        help="check new-run reconnaissance requirements instead of legacy read compatibility",
    )

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("packet", type=Path)
    dispatch_parser.add_argument(
        "--lane-id",
        required=True,
        choices=sorted(GENERATION_LANE_INSTRUCTIONS),
    )
    dispatch_parser.add_argument("--run-id", required=True)
    dispatch_parser.add_argument("--model-revision", required=True)
    dispatch_parser.add_argument("--context-id", required=True)
    dispatch_parser.add_argument(
        "--dispatched-at",
        help="ISO-8601; defaults to the script's own UTC clock",
    )
    dispatch_parser.add_argument("--workspace-root", type=Path)
    dispatch_parser.add_argument("--output", type=Path)

    host_seal_parser = subparsers.add_parser(
        "host-seal",
        help="run the build-selected host adapter and seal its controller receipts",
    )
    host_seal_parser.add_argument("packet", type=Path)
    host_seal_parser.add_argument("--model-revision", required=True)
    host_seal_parser.add_argument(
        "--runner",
        choices=ALL_RUNNERS,
        default=default_host_runner(),
        help=(
            "host-signed CodexExec/ClaudeExec, or Claude agent-declared two-phase "
            "capture with --emit-prompts followed by --responses"
        ),
    )
    host_seal_parser.add_argument(
        "--emit-prompts",
        type=Path,
        help="agent-declared phase 1: write per-lane prompts plus a manifest",
    )
    host_seal_parser.add_argument(
        "--responses",
        type=Path,
        help="agent-declared phase 2: read saved subagent responses and context ids",
    )
    host_seal_parser.add_argument(
        "--lane-id",
        action="append",
        required=True,
        choices=sorted(GENERATION_LANE_INSTRUCTIONS),
        help="repeat controller-owned lane ids for mutually isolated generation runs",
    )
    host_seal_parser.add_argument(
        "--dispatched-at",
        help="ISO-8601; defaults to the script's own UTC clock",
    )
    host_seal_parser.add_argument(
        "--issued-at",
        help="ISO-8601; defaults to the script's own UTC clock",
    )
    host_seal_parser.add_argument(
        "--sealed-at",
        help="ISO-8601; defaults to the script's own UTC clock at seal time",
    )
    host_seal_parser.add_argument(
        "--allow-seed-breadth-exemption",
        action="store_true",
        help=(
            "seal a broad-divergence portfolio outside the 12-18 window; only "
            "valid when a narrow-direction exemption will be recorded at bind"
        ),
    )
    host_seal_parser.add_argument("--timeout-seconds", type=int, default=180)
    host_seal_parser.add_argument(
        "--workspace-root",
        type=Path,
        help="required for workspace_extension/material_opportunity/phenomenon_first declared inputs",
    )
    host_seal_parser.add_argument("--output", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            config_read = read_config(args.workspace)
            if config_read.path is None:
                raise ValueError("workflow configuration is missing")
            recon_entries: list[dict[str, Any]] | None = None
            if args.recon is not None:
                recon_raw = json.loads(args.recon.read_text(encoding="utf-8-sig"))
                if not isinstance(recon_raw, list):
                    raise ValueError("--recon file must contain one JSON array")
                recon_entries = recon_raw
            packet = build_packet(
                config_read.payload,
                current_user_request=args.current_user_request,
                compiled_at=args.compiled_at or _utc_now_stamp(),
                declared_workspace_scope=args.declared_workspace_scope,
                literature_reconnaissance=recon_entries,
            )
            _write_json(args.output, packet)
            return 0
        if args.command == "validate":
            config = None
            if args.workspace is not None:
                config_read = read_config(args.workspace)
                config = config_read.payload
            packet = _read_object(args.packet)
            issues = validate_packet(packet, config, for_generation=args.for_generation)
            if issues:
                print("FAIL")
                print("\n".join(f"- {item}" for item in issues))
                return 1
            print("PASS")
            if not args.for_generation and validate_packet(packet, config, for_generation=True):
                print("READ_ONLY: legacy packet is readable; fresh retrieval and --recon are required for new generation")
            return 0
        if args.command == "host-seal":
            packet = _read_object(args.packet)
            runner = ensure_runner_allowed(args.runner)
            if runner == "agent-declared":
                if bool(args.emit_prompts) == bool(args.responses):
                    raise ValueError(
                        "agent-declared host-seal requires exactly one of "
                        "--emit-prompts or --responses"
                    )
                if args.emit_prompts:
                    packet_issues = validate_packet(packet, for_generation=True)
                    if packet_issues:
                        raise ValueError("invalid topic packet: " + "; ".join(packet_issues))
                    projection = declared_material_projection(packet, args.workspace_root)
                    lane_schema = seed_output_schema(
                        depth=_text(packet.get("brainstorm_depth")),
                        lane_count=len(args.lane_id),
                    )
                    for lane_id in args.lane_id:
                        prompt_path = write_agent_capture_request(
                            args.emit_prompts,
                            step=lane_id,
                            prompt=canonical_generation_prompt(packet, lane_id, projection),
                            output_schema=lane_schema,
                            model_revision=args.model_revision,
                        )
                        print(f"prompt emitted: {prompt_path}")
                    print(
                        "agent-declared generation pending: spawn one fresh subagent "
                        "per prompt, save its raw JSON reply and real context id, then "
                        "rerun host-seal with --responses"
                    )
                    return 0
            elif args.emit_prompts or args.responses:
                raise ValueError(
                    "--emit-prompts/--responses require --runner agent-declared"
                )
            scheduler = TopicGenerationScheduler.from_runner(
                packet,
                runner=runner,
                model_revision=args.model_revision,
                workspace_root=args.workspace_root,
                timeout_seconds=args.timeout_seconds,
                responses_dir=args.responses,
                lane_count=len(args.lane_id),
            )
            dispatched_at = args.dispatched_at or _utc_now_stamp()
            issued_at = args.issued_at or dispatched_at
            receipts = [
                scheduler.run(
                    lane_id=lane_id,
                    dispatched_at=dispatched_at,
                    issued_at=issued_at,
                )
                for lane_id in args.lane_id
            ]
            depth = _text(packet.get("brainstorm_depth"))
            total_seeds = sum(
                len(receipt.get("seeds") or []) for receipt in receipts
            )
            low, high = BROAD_SEED_WINDOW
            if (
                depth == "broad"
                and not (low <= total_seeds <= high)
                and not args.allow_seed_breadth_exemption
            ):
                raise ValueError(
                    f"broad divergence captured {total_seeds} seeds across "
                    f"{len(receipts)} lane(s), outside the {low}-{high} window "
                    "that bind enforces later; rerun or add a lane now, or pass "
                    "--allow-seed-breadth-exemption when a narrow-direction "
                    "exemption will be recorded"
                )
            seal = scheduler.seal(
                generation_receipts=receipts,
                sealed_at=args.sealed_at or _utc_now_stamp(),
            )
            _write_json(args.output, seal)
            return 0
        dispatch_packet = _read_object(args.packet)
        dispatch_materials = declared_material_projection(
            dispatch_packet,
            args.workspace_root,
        )
        dispatch = build_generation_dispatch(
            dispatch_packet,
            lane_id=args.lane_id,
            run_id=args.run_id,
            model_revision=args.model_revision,
            context_id=args.context_id,
            dispatched_at=args.dispatched_at or _utc_now_stamp(),
            material_projection=dispatch_materials,
        )
        _write_json(args.output, dispatch)
        return 0
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        print(f"topic packet error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
