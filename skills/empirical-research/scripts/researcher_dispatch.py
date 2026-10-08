#!/usr/bin/env python3
"""Risk-routed isolated researcher collaboration for method operations.

The module is deliberately subordinate to the existing design and execution
contracts.  It compiles a non-persisted dispatch decision from one v4 STEP and
validates the collaboration record embedded in the corresponding v3 action.
It does not own workflow state, method results, or stage completion.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence


POLICY_SCHEMA = "avereth-researcher-dispatch-policy/v1"
DECISION_SCHEMA = "avereth-researcher-dispatch-decision/v1"
COLLABORATION_SCHEMA = "avereth-researcher-collaboration/v1"
ARTIFACT_SCHEMA = "avereth-research-artifact/v1"
AGREEMENT_SCHEMA = "avereth-researcher-agreement/v1"
DISAGREEMENT_SCHEMA = "avereth-researcher-disagreements/v1"
REFERENCE_SET_SCHEMA = "avereth-reference-label-set/v1"

TASK_KINDS = {
    "independent_coding",
    "pilot_codebook_calibration",
    "agreement_calculation",
    "disagreement_adjudication",
    "reference_set_construction",
    "holdout_validation",
    "boundary_case_review",
    "inference_audit",
}
ORCHESTRATION_TASKS = {"agreement_calculation", "disagreement_adjudication"}
RISK_LEVELS = {"low", "moderate", "high"}
EPISTEMIC_FITS = {
    "independent_replication",
    "competing_readings",
    "deterministic_recompute",
    "single_judgment",
    "not_applicable",
}
CODEBOOK_MATURITY = {"not_applicable", "stable", "provisional", "new"}
REFERENCE_BASES = {
    "not_applicable",
    "external_benchmark",
    "rule_verified",
    "model_constructed",
    "mixed_evidence",
    "absent",
}
HOLDOUT_STATUSES = {"not_applicable", "planned", "frozen", "unavailable"}
INFERENCE_DISTANCES = {"direct", "one_step", "multi_step"}
METRIC_SEMANTICS = {
    "run_consistency",
    "reference_agreement",
    "stability",
    "external_accuracy",
}
REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max", "ultra"}
NEUTRAL_RESEARCHER_ROLE = re.compile(r"^Researcher [A-Z]$")
SHA256 = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class ResearcherIssue:
    code: str
    message: str
    path: str = ""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _route_for_step(step: Mapping[str, Any], design: Mapping[str, Any]) -> Mapping[str, Any]:
    design_id = _text(step.get("design_id")).upper()
    return next(
        (
            route
            for route in design.get("method_routes") or []
            if isinstance(route, Mapping) and _text(route.get("id")).upper() == design_id
        ),
        {},
    )


def _claim_types(step: Mapping[str, Any], design: Mapping[str, Any]) -> set[str]:
    wanted = {_text(value).upper() for value in step.get("claim_ids") or [] if _text(value)}
    return {
        _text(claim.get("type"))
        for claim in design.get("claims") or []
        if isinstance(claim, Mapping) and _text(claim.get("id")).upper() in wanted
    }


def _task_kinds(step: Mapping[str, Any], policy: Mapping[str, Any]) -> list[str]:
    operation = _text(_mapping(step.get("procedure")).get("operation"))
    task_map = _mapping(policy.get("task_operation_map"))
    return sorted(
        task
        for task, operations in task_map.items()
        if task in TASK_KINDS and operation in {_text(value) for value in _list(operations)}
    )


def validate_risk_profile(value: Any, *, path: str = "researcher_risk") -> list[ResearcherIssue]:
    if value is None:
        return []
    if not isinstance(value, Mapping):
        return [ResearcherIssue("RD.RESEARCHER_RISK.INVALID", "researcher_risk must be an object", path)]
    issues: list[ResearcherIssue] = []
    enums = {
        "epistemic_fit": EPISTEMIC_FITS,
        "interpretive_ambiguity": RISK_LEVELS,
        "consequence_of_error": RISK_LEVELS,
        "codebook_maturity": CODEBOOK_MATURITY,
        "reference_basis": REFERENCE_BASES,
        "holdout_status": HOLDOUT_STATUSES,
        "boundary_case_load": RISK_LEVELS,
        "inference_distance": INFERENCE_DISTANCES,
    }
    missing = [field for field in enums if not _text(value.get(field))]
    if missing:
        issues.append(
            ResearcherIssue(
                "RD.RESEARCHER_RISK.INVALID",
                "researcher_risk lacks: " + ", ".join(missing),
                path,
            )
        )
    unknown = sorted(set(value) - set(enums) - {"rationale"})
    if unknown:
        issues.append(
            ResearcherIssue(
                "RD.RESEARCHER_RISK.INVALID",
                "Unsupported researcher-risk fields: " + ", ".join(unknown),
                path,
            )
        )
    for field, allowed in enums.items():
        token = _text(value.get(field))
        if token and token not in allowed:
            issues.append(
                ResearcherIssue(
                    "RD.RESEARCHER_RISK.INVALID",
                    f"Unsupported {field}: {token!r}",
                    f"{path}.{field}",
                )
            )
    if value and not _text(value.get("rationale")):
        issues.append(
            ResearcherIssue(
                "RD.RESEARCHER_RISK.RATIONALE_MISSING",
                "An explicit researcher-risk profile needs a substantive rationale",
                f"{path}.rationale",
            )
        )
    return issues


def derive_risk_profile(
    step: Mapping[str, Any],
    design: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    tasks = _task_kinds(step, policy)
    route = _route_for_step(step, design)
    family = _text(route.get("family"))
    claims = _claim_types(step, design)
    high_claims = {_text(value) for value in _list(policy.get("high_consequence_claim_types"))}
    qualitative_independence = {
        "content_analysis",
        "text_as_data",
        "review",
        "comparative",
        "historical",
        "conceptual",
    }
    competing_readings = {
        "grounded_theory",
        "interpretive",
        "discourse_analysis",
        "normative",
    }
    default_fit = (
        "independent_replication"
        if family in qualitative_independence
        else "competing_readings"
        if family in competing_readings
        else "deterministic_recompute"
    )
    default_ambiguity = (
        "high"
        if {"reference_set_construction", "boundary_case_review"} & set(tasks)
        else "moderate"
        if tasks
        else "low"
    )
    default_consequence = "high" if claims & high_claims else "moderate" if tasks else "low"
    default_codebook = (
        "provisional"
        if "pilot_codebook_calibration" in tasks
        else "stable"
        if "independent_coding" in tasks
        else "not_applicable"
    )
    default_reference = "model_constructed" if "reference_set_construction" in tasks else "not_applicable"
    default_holdout = "planned" if "holdout_validation" in tasks else "not_applicable"
    default_boundary = "high" if "boundary_case_review" in tasks else "moderate" if "independent_coding" in tasks else "low"
    default_distance = (
        "multi_step"
        if "inference_audit" in tasks and default_consequence == "high"
        else "one_step"
        if "inference_audit" in tasks
        else "direct"
    )
    profile: dict[str, Any] = {
        "source": "derived_from_design",
        "epistemic_fit": default_fit,
        "interpretive_ambiguity": default_ambiguity,
        "consequence_of_error": default_consequence,
        "codebook_maturity": default_codebook,
        "reference_basis": default_reference,
        "holdout_status": default_holdout,
        "boundary_case_load": default_boundary,
        "inference_distance": default_distance,
        "rationale": "Derived from the registered method family, operation kind, and linked claim types.",
    }
    explicit = step.get("researcher_risk")
    if isinstance(explicit, Mapping):
        profile.update(
            {
                key: value
                for key, value in explicit.items()
                if key in profile and key != "source" and _text(value)
            }
        )
        profile["source"] = "explicit_design_profile"
    if claims & high_claims:
        # The registered claim type establishes a minimum error consequence;
        # a local profile may add risk, but may not downgrade this policy floor.
        profile["consequence_of_error"] = "high"
    return profile


def compile_dispatch_decision(
    step: Mapping[str, Any],
    design: Mapping[str, Any],
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    policy = _mapping(registry.get("researcher_dispatch_policy"))
    if _text(policy.get("schema_version")) != POLICY_SCHEMA:
        raise ValueError(f"Method registry lacks {POLICY_SCHEMA}")
    tasks = _task_kinds(step, policy)
    risk = derive_risk_profile(step, design, policy)
    always = {_text(value) for value in _list(policy.get("always_isolated_tasks"))}
    conditional = {_text(value) for value in _list(policy.get("conditional_isolated_tasks"))}
    triggers: list[str] = []
    if set(tasks) & always:
        triggers.append("TASK.REQUIRES_INDEPENDENT_RUNS")
    if "pilot_codebook_calibration" in tasks and risk["codebook_maturity"] in {"new", "provisional"}:
        triggers.append("RISK.CODEBOOK_NOT_STABLE")
    if "boundary_case_review" in tasks and (
        risk["boundary_case_load"] == "high" or risk["interpretive_ambiguity"] == "high"
    ):
        triggers.append("RISK.BOUNDARY_OR_AMBIGUITY_HIGH")
    if "inference_audit" in tasks and (
        risk["consequence_of_error"] == "high" or risk["inference_distance"] == "multi_step"
    ):
        triggers.append("RISK.INFERENCE_HIGH_CONSEQUENCE")
    if set(tasks) & conditional and risk["interpretive_ambiguity"] == "high":
        triggers.append("RISK.INTERPRETIVE_AMBIGUITY_HIGH")
    if tasks and risk["epistemic_fit"] == "not_applicable":
        triggers.append("RISK.EPISTEMIC_FIT_CONFLICT")
    multi = bool(tasks and triggers)
    agreement_tasks = {_text(value) for value in _list(policy.get("agreement_tasks"))}
    adjudication_tasks = {
        _text(value) for value in _list(policy.get("adjudication_on_disagreement_tasks"))
    }
    roles = ["Researcher A", "Researcher B"] if multi else ["Researcher A"]
    adjudicator_on_disagreement = bool(multi and set(tasks) & adjudication_tasks)
    requires_agreement = bool(multi and set(tasks) & agreement_tasks)
    if adjudicator_on_disagreement:
        roles.append("Adjudicator")
    return {
        "schema_version": DECISION_SCHEMA,
        "policy_version": _text(policy.get("policy_version")),
        "operation_id": _text(step.get("id")).upper(),
        "task_kinds": tasks,
        "mode": "isolated_multi" if multi else "single",
        "independent_researcher_count": 2 if multi else 1,
        "adjudicator_on_disagreement": adjudicator_on_disagreement,
        "requires_agreement_recomputation": requires_agreement,
        "post_run_task_kinds": (
            ["agreement_calculation"]
            if requires_agreement and "agreement_calculation" not in tasks
            else []
        ),
        "conditional_task_kinds": (
            ["disagreement_adjudication"]
            if adjudicator_on_disagreement and "disagreement_adjudication" not in tasks
            else []
        ),
        "roles": roles,
        "risk_profile": risk,
        "trigger_codes": sorted(set(triggers)),
        "input_scope": sorted({_text(value).replace("\\", "/") for value in step.get("read_set") or [] if _text(value)}),
        "output_contract": ARTIFACT_SCHEMA,
        "identity_instruction": "Use the assigned neutral functional role and return only the research artifact.",
    }


def _time(value: Any) -> datetime | None:
    token = _text(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _artifact_path(base: Path, artifact: Mapping[str, Any]) -> Path | None:
    raw = _text(artifact.get("path"))
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved = (base / candidate).resolve()
    try:
        resolved.relative_to(base.resolve())
    except ValueError:
        return None
    return resolved if resolved.is_file() else None


def _read_json_artifact(base: Path, artifact: Mapping[str, Any]) -> Any:
    path = _artifact_path(base, artifact)
    if path is None:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None


def _scope_digest(artifact_ids: Sequence[str], artifacts: Mapping[str, Mapping[str, Any]]) -> str:
    rows = [
        {"id": identifier, "sha256": _text(artifacts.get(identifier, {}).get("sha256")).casefold()}
        for identifier in sorted(set(artifact_ids))
    ]
    return canonical_digest({"artifacts": rows})


def _item_rows(payload: Any) -> list[Mapping[str, Any]]:
    rows = payload.get("items") if isinstance(payload, Mapping) else payload
    return [row for row in rows or [] if isinstance(row, Mapping)] if isinstance(rows, list) else []


def _item_id(row: Mapping[str, Any]) -> str:
    return _text(row.get("item_id") or row.get("id") or row.get("claim_id")).upper()


def _labels(payload: Any) -> dict[str, str]:
    return {
        _item_id(row): _text(row.get("label") or row.get("reference_label") or row.get("disposition"))
        for row in _item_rows(payload)
        if _item_id(row)
    }


def _nominal_metrics(label_maps: Sequence[Mapping[str, str]]) -> dict[str, float | int]:
    ids = sorted(set.intersection(*(set(mapping) for mapping in label_maps))) if label_maps else []
    matrix = [[mapping.get(identifier) for mapping in label_maps] for identifier in ids]
    pairwise = [
        (row[left], row[right])
        for row in matrix
        for left in range(len(row))
        for right in range(left + 1, len(row))
        if row[left] is not None and row[right] is not None
    ]
    percent = (
        sum(1 for left, right in pairwise if left == right) / len(pairwise)
        if pairwise
        else float("nan")
    )
    alpha_observed: defaultdict[tuple[str, str], float] = defaultdict(float)
    for row in matrix:
        values = [value for value in row if value is not None]
        if len(values) < 2:
            continue
        weight = 1.0 / (len(values) - 1)
        for left, value in enumerate(values):
            for right, other in enumerate(values):
                if left != right:
                    alpha_observed[(value, other)] += weight
    alpha = float("nan")
    if alpha_observed:
        categories = {value for pair in alpha_observed for value in pair}
        n = sum(alpha_observed.values())
        marginals = {
            category: sum(alpha_observed.get((category, other), 0.0) for other in categories)
            for category in categories
        }
        observed = sum(value for (left, right), value in alpha_observed.items() if left != right) / n
        expected = (
            sum(
                marginals[left] * marginals[right]
                for left in categories
                for right in categories
                if left != right
            )
            / (n * (n - 1))
            if n > 1
            else 0.0
        )
        if expected:
            alpha = 1.0 - observed / expected
    result: dict[str, float | int] = {
        "n": len(ids),
        "percent_agreement": percent,
        "krippendorff_alpha_nominal": alpha,
    }
    if len(label_maps) == 2 and ids:
        left = [label_maps[0][identifier] for identifier in ids]
        right = [label_maps[1][identifier] for identifier in ids]
        observed = sum(1 for a, b in zip(left, right) if a == b) / len(ids)
        left_counts = Counter(left)
        right_counts = Counter(right)
        expected = sum(
            (left_counts[label] / len(ids)) * (right_counts[label] / len(ids))
            for label in set(left_counts) | set(right_counts)
        )
        result["cohen_kappa"] = (observed - expected) / (1 - expected) if expected != 1 else float("nan")
        pooled = Counter([*left, *right])
        pooled_expected = sum((count / (2 * len(ids))) ** 2 for count in pooled.values())
        result["scott_pi"] = (
            (observed - pooled_expected) / (1 - pooled_expected)
            if pooled_expected != 1
            else float("nan")
        )
    return result


def _same_number(left: Any, right: Any) -> bool:
    try:
        a, b = float(left), float(right)
    except (TypeError, ValueError):
        return False
    if math.isnan(a) and math.isnan(b):
        return True
    return abs(a - b) <= 1e-9


def _require_artifact(
    issues: list[ResearcherIssue],
    identifier: Any,
    artifacts: Mapping[str, Mapping[str, Any]],
    path: str,
) -> str:
    token = _text(identifier).upper()
    if not token or token not in artifacts:
        issues.append(ResearcherIssue("ME.RESEARCHER.ARTIFACT_UNRESOLVED", f"Unknown artifact {token!r}", path))
        return ""
    return token


def _validate_research_artifact(
    payload: Any,
    *,
    operation_id: str,
    role: str,
    task_kinds: Sequence[str],
    path: str,
) -> tuple[list[ResearcherIssue], dict[str, str]]:
    issues: list[ResearcherIssue] = []
    if not isinstance(payload, Mapping) or _text(payload.get("schema_version")) != ARTIFACT_SCHEMA:
        return [ResearcherIssue("ME.RESEARCHER.OUTPUT_SCHEMA", f"Output must use {ARTIFACT_SCHEMA}", path)], {}
    allowed = {"schema_version", "operation_id", "role", "task_kinds", "items"}
    if set(payload) != allowed:
        issues.append(
            ResearcherIssue(
                "ME.RESEARCHER.OUTPUT_NOT_ARTIFACT_ONLY",
                "Researcher output must contain only the strict research-artifact fields",
                path,
            )
        )
    if _text(payload.get("operation_id")).upper() != operation_id:
        issues.append(ResearcherIssue("ME.RESEARCHER.OUTPUT_BINDING", "Output operation_id differs from the action", f"{path}.operation_id"))
    if _text(payload.get("role")) != role:
        issues.append(ResearcherIssue("ME.RESEARCHER.OUTPUT_BINDING", "Output role differs from the registered run role", f"{path}.role"))
    if sorted(_text(value) for value in payload.get("task_kinds") or []) != sorted(task_kinds):
        issues.append(ResearcherIssue("ME.RESEARCHER.TASK_DRIFT", "Output task_kinds differ from the dispatch decision", f"{path}.task_kinds"))
    rows = _item_rows(payload)
    if not rows:
        issues.append(ResearcherIssue("ME.RESEARCHER.OUTPUT_EMPTY", "Researcher output needs item-level research records", f"{path}.items"))
    labels: dict[str, str] = {}
    for index, row in enumerate(rows):
        item_path = f"{path}.items[{index}]"
        required = {"item_id", "label", "evidence_locator", "rationale", "confidence"}
        if set(row) != required:
            issues.append(ResearcherIssue("ME.RESEARCHER.ITEM_SCHEMA", "Each item must contain exactly item_id, label, evidence_locator, rationale, and confidence", item_path))
        identifier = _item_id(row)
        label = _text(row.get("label"))
        if not identifier or not label or not _text(row.get("evidence_locator")) or not _text(row.get("rationale")):
            issues.append(ResearcherIssue("ME.RESEARCHER.ITEM_INCOMPLETE", "Research item lacks an identity, label, evidence locator, or rationale", item_path))
        try:
            confidence = float(row.get("confidence"))
        except (TypeError, ValueError):
            confidence = -1.0
        if not 0 <= confidence <= 1:
            issues.append(ResearcherIssue("ME.RESEARCHER.CONFIDENCE_INVALID", "confidence must be between 0 and 1", f"{item_path}.confidence"))
        if identifier in labels:
            issues.append(ResearcherIssue("ME.RESEARCHER.ITEM_DUPLICATE", f"Duplicate item {identifier}", item_path))
        labels[identifier] = label
    return issues, labels


def validate_collaboration(
    base: Path,
    *,
    action: Mapping[str, Any],
    step: Mapping[str, Any],
    design: Mapping[str, Any],
    registry: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
    path: str,
) -> list[ResearcherIssue]:
    """Validate one action's embedded collaboration against a recomputed decision."""

    issues: list[ResearcherIssue] = []
    decision = compile_dispatch_decision(step, design, registry)
    record = action.get("researcher_collaboration")
    accepted = _text(action.get("status")) == "accepted"
    if decision["mode"] == "isolated_multi" and accepted and not isinstance(record, Mapping):
        return [
            ResearcherIssue(
                "ME.RESEARCHER.COLLABORATION_REQUIRED",
                "The risk-routed operation requires isolated researcher collaboration before acceptance",
                f"{path}.researcher_collaboration",
            )
        ]
    if not isinstance(record, Mapping):
        return issues
    required_record_fields = {
        "schema_version",
        "decision_sha256",
        "operation_id",
        "mode",
        "task_kinds",
        "frozen_input_artifact_ids",
        "researcher_runs",
        "task_records",
        "agreement",
        "adjudication",
    }
    missing_record_fields = sorted(required_record_fields - set(record))
    if missing_record_fields:
        issues.append(
            ResearcherIssue(
                "ME.RESEARCHER.COLLABORATION_INCOMPLETE",
                "Collaboration lacks: " + ", ".join(missing_record_fields),
                f"{path}.researcher_collaboration",
            )
        )
    if _text(record.get("schema_version")) != COLLABORATION_SCHEMA:
        issues.append(ResearcherIssue("ME.RESEARCHER.SCHEMA", f"Collaboration must use {COLLABORATION_SCHEMA}", f"{path}.researcher_collaboration.schema_version"))
    if _text(record.get("operation_id")).upper() != decision["operation_id"]:
        issues.append(ResearcherIssue("ME.RESEARCHER.OPERATION_DRIFT", "Collaboration operation_id differs from the action", f"{path}.researcher_collaboration.operation_id"))
    if _text(record.get("decision_sha256")).casefold() != canonical_digest(decision):
        issues.append(ResearcherIssue("ME.RESEARCHER.DECISION_DRIFT", "Collaboration is not bound to the current risk-routed dispatch decision", f"{path}.researcher_collaboration.decision_sha256"))
    if _text(record.get("mode")) != decision["mode"]:
        issues.append(ResearcherIssue("ME.RESEARCHER.MODE_DRIFT", "Recorded collaboration mode differs from the recomputed decision", f"{path}.researcher_collaboration.mode"))
    tasks = sorted({_text(value) for value in record.get("task_kinds") or [] if _text(value)})
    if tasks != decision["task_kinds"]:
        issues.append(ResearcherIssue("ME.RESEARCHER.TASK_DRIFT", "Recorded task kinds differ from the recomputed decision", f"{path}.researcher_collaboration.task_kinds"))

    action_inputs = {_text(value).upper() for value in action.get("input_artifact_ids") or [] if _text(value)}
    action_outputs = {_text(value).upper() for value in action.get("output_artifact_ids") or [] if _text(value)}
    frozen_inputs = {_text(value).upper() for value in record.get("frozen_input_artifact_ids") or [] if _text(value)}
    if frozen_inputs != action_inputs:
        issues.append(ResearcherIssue("ME.RESEARCHER.INPUT_SCOPE_DRIFT", "Frozen collaboration inputs must exactly match action inputs", f"{path}.researcher_collaboration.frozen_input_artifact_ids"))
    for identifier in frozen_inputs:
        _require_artifact(issues, identifier, artifacts, f"{path}.researcher_collaboration.frozen_input_artifact_ids")

    raw_runs = record.get("researcher_runs")
    if not isinstance(raw_runs, list):
        issues.append(ResearcherIssue("ME.RESEARCHER.RUNS_INVALID", "researcher_runs must be an array", f"{path}.researcher_collaboration.researcher_runs"))
        raw_runs = []
    if accepted and len(raw_runs) < int(decision["independent_researcher_count"]):
        issues.append(ResearcherIssue("ME.RESEARCHER.RUN_COUNT", "Too few independently recorded researcher runs", f"{path}.researcher_collaboration.researcher_runs"))
    run_ids: set[str] = set()
    context_ids: set[str] = set()
    output_ids: set[str] = set()
    output_hashes: set[str] = set()
    protocol_hashes: set[str] = set()
    output_labels: dict[str, dict[str, str]] = {}
    primary_tasks = [task for task in tasks if task not in ORCHESTRATION_TASKS]
    completed_times: list[datetime] = []
    primary_input_scopes: set[str] = set()
    for index, run in enumerate(raw_runs):
        run_path = f"{path}.researcher_collaboration.researcher_runs[{index}]"
        if not isinstance(run, Mapping):
            issues.append(ResearcherIssue("ME.RESEARCHER.RUNS_INVALID", "Researcher run must be an object", run_path))
            continue
        required = (
            "role", "run_id", "context_id", "model_name", "model_revision", "reasoning_effort",
            "prompt_sha256", "protocol_sha256", "input_artifact_ids", "input_scope_sha256",
            "output_artifact_id", "started_at", "completed_at", "blind_to_peer_outputs",
            "blind_to_reference_labels", "sealed_first_output",
        )
        missing = [field for field in required if field not in run or (field not in {"blind_to_peer_outputs", "blind_to_reference_labels", "sealed_first_output"} and not _text(run.get(field)))]
        if missing:
            issues.append(ResearcherIssue("ME.RESEARCHER.RUN_INCOMPLETE", "Researcher run lacks: " + ", ".join(missing), run_path))
        role = _text(run.get("role"))
        if not NEUTRAL_RESEARCHER_ROLE.fullmatch(role):
            issues.append(ResearcherIssue("ME.RESEARCHER.ROLE_INVALID", "Use a neutral role such as Researcher A", f"{run_path}.role"))
        run_id = _text(run.get("run_id"))
        context_id = _text(run.get("context_id"))
        if run_id in run_ids or context_id in context_ids:
            issues.append(ResearcherIssue("ME.RESEARCHER.NOT_ISOLATED", "Researcher runs require distinct run and context identities", run_path))
        run_ids.add(run_id)
        context_ids.add(context_id)
        if _text(run.get("reasoning_effort")) not in REASONING_EFFORTS:
            issues.append(ResearcherIssue("ME.RESEARCHER.REASONING_EFFORT_INVALID", "reasoning_effort is not a supported recorded value", f"{run_path}.reasoning_effort"))
        for digest_field in ("prompt_sha256", "protocol_sha256", "input_scope_sha256"):
            if not SHA256.fullmatch(_text(run.get(digest_field))):
                issues.append(ResearcherIssue("ME.RESEARCHER.DIGEST_INVALID", f"{digest_field} must be SHA-256", f"{run_path}.{digest_field}"))
        protocol_hashes.add(_text(run.get("protocol_sha256")).casefold())
        run_inputs = {_text(value).upper() for value in run.get("input_artifact_ids") or [] if _text(value)}
        if not run_inputs <= action_inputs:
            issues.append(ResearcherIssue("ME.RESEARCHER.INPUT_SCOPE_DRIFT", "A researcher run sees artifacts outside the frozen action inputs", f"{run_path}.input_artifact_ids"))
        observed_scope = _scope_digest(sorted(run_inputs), artifacts)
        primary_input_scopes.add(observed_scope)
        if _text(run.get("input_scope_sha256")).casefold() != observed_scope:
            issues.append(ResearcherIssue("ME.RESEARCHER.INPUT_SCOPE_DRIFT", "input_scope_sha256 does not match the registered artifacts", f"{run_path}.input_scope_sha256"))
        if run.get("blind_to_peer_outputs") is not True or run.get("sealed_first_output") is not True:
            issues.append(ResearcherIssue("ME.RESEARCHER.NOT_ISOLATED", "Primary runs must be blind to peer outputs and preserve sealed first outputs", run_path))
        started = _time(run.get("started_at"))
        completed = _time(run.get("completed_at"))
        if started is None or completed is None or completed <= started:
            issues.append(ResearcherIssue("ME.RESEARCHER.TIME_INVALID", "Run timestamps must be timezone-aware and ordered", run_path))
        elif completed is not None:
            completed_times.append(completed)
        output_id = _require_artifact(issues, run.get("output_artifact_id"), artifacts, f"{run_path}.output_artifact_id")
        if output_id:
            if output_id not in action_outputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.OUTPUT_NOT_ACTION_BOUND", "Researcher output must be an action output", f"{run_path}.output_artifact_id"))
            digest = _text(artifacts[output_id].get("sha256")).casefold()
            if output_id in output_ids or digest in output_hashes:
                issues.append(ResearcherIssue("ME.RESEARCHER.NOT_ISOLATED", "Independent outputs require distinct artifact identities and content hashes", f"{run_path}.output_artifact_id"))
            output_ids.add(output_id)
            output_hashes.add(digest)
            payload = _read_json_artifact(base, artifacts[output_id])
            found, labels = _validate_research_artifact(
                payload,
                operation_id=decision["operation_id"],
                role=role,
                task_kinds=primary_tasks,
                path=f"artifact:{output_id}",
            )
            issues.extend(found)
            output_labels[run_id] = labels
    if decision["mode"] == "isolated_multi" and len(primary_input_scopes) != 1:
        issues.append(ResearcherIssue("ME.RESEARCHER.INPUT_SCOPE_DRIFT", "Independent researchers must receive the same frozen input scope", f"{path}.researcher_collaboration.researcher_runs"))
    if decision["mode"] == "isolated_multi" and len(protocol_hashes) != 1:
        issues.append(ResearcherIssue("ME.RESEARCHER.PROTOCOL_DRIFT", "Independent researchers must follow the same frozen protocol", f"{path}.researcher_collaboration.researcher_runs"))
    if decision["mode"] == "isolated_multi" and output_labels:
        item_sets = {tuple(sorted(labels)) for labels in output_labels.values()}
        if len(item_sets) != 1:
            issues.append(ResearcherIssue("ME.RESEARCHER.ITEM_COVERAGE_DRIFT", "Independent outputs must cover the same item identities", f"{path}.researcher_collaboration.researcher_runs"))

    task_records = record.get("task_records")
    if not isinstance(task_records, list):
        issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RECORD_INVALID", "task_records must be an array", f"{path}.researcher_collaboration.task_records"))
        task_records = []
    records_by_task: dict[str, Mapping[str, Any]] = {}
    for index, task in enumerate(task_records):
        task_path = f"{path}.researcher_collaboration.task_records[{index}]"
        if not isinstance(task, Mapping):
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RECORD_INVALID", "Task record must be an object", task_path))
            continue
        kind = _text(task.get("task_kind"))
        if kind not in TASK_KINDS or kind in records_by_task:
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RECORD_INVALID", f"Invalid or duplicate task kind {kind!r}", f"{task_path}.task_kind"))
        records_by_task[kind] = task
        if _text(task.get("status")) != "complete":
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_INCOMPLETE", "Accepted collaboration tasks must be complete", f"{task_path}.status"))
        for field in ("input_artifact_ids", "output_artifact_ids", "run_ids"):
            if not isinstance(task.get(field), list):
                issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RECORD_INVALID", f"{field} must be an array", f"{task_path}.{field}"))
        if not isinstance(task.get("details"), Mapping):
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RECORD_INVALID", "details must be an object", f"{task_path}.details"))
        unknown_runs = {_text(value) for value in task.get("run_ids") or []} - run_ids
        if unknown_runs and kind not in {"disagreement_adjudication", "agreement_calculation"}:
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_RUN_UNRESOLVED", "Task record names an unknown researcher run", f"{task_path}.run_ids"))
        task_inputs = {_text(value).upper() for value in task.get("input_artifact_ids") or []}
        task_outputs = {_text(value).upper() for value in task.get("output_artifact_ids") or []}
        if not task_inputs <= action_inputs | action_outputs or not task_outputs <= action_outputs:
            issues.append(ResearcherIssue("ME.RESEARCHER.TASK_ARTIFACT_DRIFT", "Task artifacts must be bound to the enclosing action", task_path))
    disagreements: set[str] = set()
    label_maps = [output_labels[run_id] for run_id in sorted(output_labels) if output_labels[run_id]]
    if len(label_maps) >= 2:
        common = set.intersection(*(set(mapping) for mapping in label_maps))
        disagreements = {
            identifier
            for identifier in common
            if len({mapping[identifier] for mapping in label_maps}) > 1
        }
    expected_task_records = set(tasks) | set(decision.get("post_run_task_kinds") or [])
    if disagreements and decision["adjudicator_on_disagreement"]:
        expected_task_records.update(decision.get("conditional_task_kinds") or [])
    if set(records_by_task) != expected_task_records:
        issues.append(
            ResearcherIssue(
                "ME.RESEARCHER.TASK_COVERAGE",
                "Task records must cover first-run, post-run, and triggered conditional tasks exactly",
                f"{path}.researcher_collaboration.task_records",
            )
        )
    agreement = record.get("agreement")
    disagreement_id = ""
    if decision["requires_agreement_recomputation"]:
        if not isinstance(agreement, Mapping) or _text(agreement.get("status")) != "complete":
            issues.append(ResearcherIssue("ME.RESEARCHER.AGREEMENT_REQUIRED", "Multi-researcher work requires a recomputed agreement record", f"{path}.researcher_collaboration.agreement"))
        else:
            semantics = _text(agreement.get("metric_semantics"))
            if semantics not in METRIC_SEMANTICS or semantics == "external_accuracy":
                issues.append(ResearcherIssue("ME.RESEARCHER.METRIC_SEMANTICS", "Independent model runs must use run_consistency, reference_agreement, or stability semantics", f"{path}.researcher_collaboration.agreement.metric_semantics"))
            metrics_id = _require_artifact(issues, agreement.get("metrics_artifact_id"), artifacts, f"{path}.researcher_collaboration.agreement.metrics_artifact_id")
            disagreement_id = _require_artifact(issues, agreement.get("disagreement_artifact_id"), artifacts, f"{path}.researcher_collaboration.agreement.disagreement_artifact_id")
            if metrics_id not in action_outputs or disagreement_id not in action_outputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.AGREEMENT_NOT_ACTION_BOUND", "Agreement metrics and disagreement log must be action outputs", f"{path}.researcher_collaboration.agreement"))
            actual = _nominal_metrics(label_maps)
            declared = _read_json_artifact(base, artifacts.get(metrics_id, {})) if metrics_id else None
            if not isinstance(declared, Mapping) or _text(declared.get("schema_version")) != AGREEMENT_SCHEMA:
                issues.append(ResearcherIssue("ME.RESEARCHER.AGREEMENT_SCHEMA", f"Metrics must use {AGREEMENT_SCHEMA}", f"artifact:{metrics_id}"))
            else:
                if _text(declared.get("metric_semantics")) != semantics:
                    issues.append(ResearcherIssue("ME.RESEARCHER.METRIC_SEMANTICS", "Metrics artifact semantics differ from the action record", f"artifact:{metrics_id}.metric_semantics"))
                for field, expected in actual.items():
                    if field == "n":
                        if declared.get(field) != expected:
                            issues.append(ResearcherIssue("ME.RESEARCHER.METRIC_MISMATCH", f"Declared {field} is not reproducible", f"artifact:{metrics_id}.{field}"))
                    elif not _same_number(declared.get(field), expected):
                        issues.append(ResearcherIssue("ME.RESEARCHER.METRIC_MISMATCH", f"Declared {field} is not reproducible", f"artifact:{metrics_id}.{field}"))
            disagreement_payload = _read_json_artifact(base, artifacts.get(disagreement_id, {})) if disagreement_id else None
            declared_disagreements = {
                _item_id(row) for row in _item_rows(disagreement_payload) if _item_id(row)
            }
            if not isinstance(disagreement_payload, Mapping) or _text(disagreement_payload.get("schema_version")) != DISAGREEMENT_SCHEMA:
                issues.append(ResearcherIssue("ME.RESEARCHER.DISAGREEMENT_SCHEMA", f"Disagreement log must use {DISAGREEMENT_SCHEMA}", f"artifact:{disagreement_id}"))
            elif declared_disagreements != disagreements:
                issues.append(ResearcherIssue("ME.RESEARCHER.DISAGREEMENT_MISMATCH", "Disagreement log does not equal the independently recomputed set", f"artifact:{disagreement_id}"))
    elif not isinstance(agreement, Mapping) or _text(agreement.get("status")) not in {
        "not_applicable",
        "complete",
    }:
        issues.append(
            ResearcherIssue(
                "ME.RESEARCHER.AGREEMENT_INVALID",
                "A collaboration without agreement recomputation must record not_applicable",
                f"{path}.researcher_collaboration.agreement",
            )
        )

    adjudication = record.get("adjudication")
    if disagreements and decision["adjudicator_on_disagreement"]:
        if not isinstance(adjudication, Mapping) or _text(adjudication.get("status")) != "complete":
            issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATION_REQUIRED", "Observed disagreements require a separate adjudication run", f"{path}.researcher_collaboration.adjudication"))
        else:
            adjudicator = adjudication.get("run")
            if not isinstance(adjudicator, Mapping):
                issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATION_INVALID", "Adjudication run must be an object", f"{path}.researcher_collaboration.adjudication.run"))
            else:
                adj_path = f"{path}.researcher_collaboration.adjudication.run"
                required = (
                    "role", "run_id", "context_id", "model_name", "model_revision",
                    "reasoning_effort", "prompt_sha256", "protocol_sha256",
                    "input_artifact_ids", "input_scope_sha256", "output_artifact_id",
                    "started_at", "completed_at", "blind_to_reference_labels",
                )
                missing = [
                    field
                    for field in required
                    if field not in adjudicator
                    or (
                        field != "blind_to_reference_labels"
                        and not _text(adjudicator.get(field))
                    )
                ]
                if missing:
                    issues.append(
                        ResearcherIssue(
                            "ME.RESEARCHER.ADJUDICATION_INVALID",
                            "Adjudication run lacks: " + ", ".join(missing),
                            adj_path,
                        )
                    )
                if _text(adjudicator.get("role")) != "Adjudicator":
                    issues.append(ResearcherIssue("ME.RESEARCHER.ROLE_INVALID", "The disagreement resolver role must be Adjudicator", f"{adj_path}.role"))
                if (
                    not _text(adjudicator.get("context_id"))
                    or not _text(adjudicator.get("run_id"))
                    or _text(adjudicator.get("context_id")) in context_ids
                    or _text(adjudicator.get("run_id")) in run_ids
                ):
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_NOT_ISOLATED", "Adjudicator needs a distinct run and context", adj_path))
                adj_inputs = {_text(value).upper() for value in adjudicator.get("input_artifact_ids") or []}
                required_adj_inputs = set(output_ids)
                if disagreement_id:
                    required_adj_inputs.add(disagreement_id)
                if not required_adj_inputs <= adj_inputs:
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_INPUT_INCOMPLETE", "Adjudicator must receive every sealed first output and the exact disagreement log", f"{adj_path}.input_artifact_ids"))
                if not adj_inputs <= action_inputs | action_outputs:
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_INPUT_SCOPE", "Adjudicator inputs must be bound to the enclosing action", f"{adj_path}.input_artifact_ids"))
                observed_scope = _scope_digest(sorted(adj_inputs), artifacts)
                if _text(adjudicator.get("input_scope_sha256")).casefold() != observed_scope:
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_INPUT_SCOPE", "Adjudicator input_scope_sha256 does not match its registered artifacts", f"{adj_path}.input_scope_sha256"))
                for digest_field in ("prompt_sha256", "protocol_sha256", "input_scope_sha256"):
                    if not SHA256.fullmatch(_text(adjudicator.get(digest_field))):
                        issues.append(ResearcherIssue("ME.RESEARCHER.DIGEST_INVALID", f"{digest_field} must be SHA-256", f"{adj_path}.{digest_field}"))
                if protocol_hashes and _text(adjudicator.get("protocol_sha256")).casefold() not in protocol_hashes:
                    issues.append(ResearcherIssue("ME.RESEARCHER.PROTOCOL_DRIFT", "Adjudicator must apply the same frozen protocol as the first runs", f"{adj_path}.protocol_sha256"))
                if _text(adjudicator.get("reasoning_effort")) not in REASONING_EFFORTS:
                    issues.append(ResearcherIssue("ME.RESEARCHER.REASONING_EFFORT_INVALID", "reasoning_effort is not a supported recorded value", f"{adj_path}.reasoning_effort"))
                if adjudicator.get("blind_to_reference_labels") is not True:
                    issues.append(ResearcherIssue("ME.RESEARCHER.HOLDOUT_LEAKAGE", "Adjudicator must remain blind to withheld reference labels", f"{adj_path}.blind_to_reference_labels"))
                started = _time(adjudicator.get("started_at"))
                completed = _time(adjudicator.get("completed_at"))
                if started is None or completed is None or completed <= started or (completed_times and started < max(completed_times)):
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_TIME_INVALID", "Adjudication must start after all first outputs are sealed", adj_path))
                output_id = _require_artifact(issues, adjudicator.get("output_artifact_id"), artifacts, f"{adj_path}.output_artifact_id")
                if output_id not in action_outputs:
                    issues.append(ResearcherIssue("ME.RESEARCHER.OUTPUT_NOT_ACTION_BOUND", "Adjudication output must be an action output", f"{adj_path}.output_artifact_id"))
                if output_id in output_ids or (
                    output_id
                    and _text(artifacts.get(output_id, {}).get("sha256")).casefold() in output_hashes
                ):
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATOR_NOT_ISOLATED", "Adjudication output must be distinct from every first output", f"{adj_path}.output_artifact_id"))
                payload = _read_json_artifact(base, artifacts.get(output_id, {})) if output_id else None
                found, final_labels = _validate_research_artifact(
                    payload,
                    operation_id=decision["operation_id"],
                    role="Adjudicator",
                    task_kinds=["disagreement_adjudication"],
                    path=f"artifact:{output_id}",
                )
                issues.extend(found)
                if set(final_labels) != disagreements:
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATION_COVERAGE", "Adjudicator output must resolve exactly the disagreement set", f"artifact:{output_id}"))
                if adjudication.get("unresolved_count") != 0:
                    issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATION_UNRESOLVED", "Accepted collaboration cannot retain unresolved disagreements", f"{path}.researcher_collaboration.adjudication.unresolved_count"))
    elif isinstance(adjudication, Mapping) and _text(adjudication.get("status")) not in {"not_triggered", "not_applicable", "complete"}:
        issues.append(ResearcherIssue("ME.RESEARCHER.ADJUDICATION_INVALID", "Adjudication status is invalid", f"{path}.researcher_collaboration.adjudication.status"))

    for task_kind, task in records_by_task.items():
        details = _mapping(task.get("details"))
        if task_kind == "pilot_codebook_calibration":
            before = _text(details.get("codebook_before_artifact_id")).upper()
            after = _text(details.get("codebook_after_artifact_id")).upper()
            changes = _text(details.get("change_log_artifact_id")).upper()
            if before not in action_inputs or after not in action_outputs or changes not in action_outputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.CALIBRATION_INCOMPLETE", "Calibration must bind the before codebook, revised codebook, and change log", f"{path}.researcher_collaboration.task_records[{task_kind}]"))
        if task_kind in {"independent_coding", "boundary_case_review"}:
            manifest_id = _text(details.get("unit_manifest_artifact_id") or details.get("boundary_manifest_artifact_id")).upper()
            if manifest_id not in action_inputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.MANIFEST_MISSING", "Coding or boundary review requires a frozen input manifest", f"{path}.researcher_collaboration.task_records[{task_kind}].details"))
            else:
                expected_ids = {_item_id(row) for row in _item_rows(_read_json_artifact(base, artifacts.get(manifest_id, {}))) if _item_id(row)}
                for run_id, labels in output_labels.items():
                    if expected_ids and set(labels) != expected_ids:
                        issues.append(ResearcherIssue("ME.RESEARCHER.ITEM_COVERAGE_DRIFT", f"Run {run_id} does not cover the frozen manifest", f"artifact:{manifest_id}"))
        if task_kind == "reference_set_construction":
            reference_id = _text(details.get("reference_set_artifact_id")).upper()
            if reference_id not in action_outputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.REFERENCE_SET_MISSING", "Reference-set construction requires an action-bound label set", f"{path}.researcher_collaboration.task_records[{task_kind}].details.reference_set_artifact_id"))
            else:
                payload = _read_json_artifact(base, artifacts.get(reference_id, {}))
                if not isinstance(payload, Mapping) or _text(payload.get("schema_version")) != REFERENCE_SET_SCHEMA or not _labels(payload):
                    issues.append(ResearcherIssue("ME.RESEARCHER.REFERENCE_SET_INVALID", f"Reference set must use {REFERENCE_SET_SCHEMA} and contain labels", f"artifact:{reference_id}"))
        if task_kind == "holdout_validation":
            holdout_id = _text(details.get("holdout_manifest_artifact_id")).upper()
            labels_id = _text(details.get("reference_labels_artifact_id")).upper()
            if holdout_id not in action_inputs or labels_id not in action_inputs:
                issues.append(ResearcherIssue("ME.RESEARCHER.HOLDOUT_INCOMPLETE", "Holdout validation requires frozen manifests and withheld reference labels", f"{path}.researcher_collaboration.task_records[{task_kind}].details"))
            for index, run in enumerate(raw_runs):
                run_inputs = {_text(value).upper() for value in _mapping(run).get("input_artifact_ids") or []}
                if labels_id in run_inputs or _mapping(run).get("blind_to_reference_labels") is not True:
                    issues.append(ResearcherIssue("ME.RESEARCHER.HOLDOUT_LEAKAGE", "Researcher runs must be blind to holdout reference labels", f"{path}.researcher_collaboration.researcher_runs[{index}]"))
        if task_kind == "inference_audit":
            audited = {_text(value).upper() for value in details.get("claim_ids") or [] if _text(value)}
            expected = {_text(value).upper() for value in step.get("claim_ids") or [] if _text(value)}
            audit_id = _text(details.get("audit_artifact_id")).upper()
            if audited != expected or audit_id not in action_outputs or details.get("unresolved_count") != 0:
                issues.append(ResearcherIssue("ME.RESEARCHER.INFERENCE_AUDIT_INCOMPLETE", "Inference audit must cover every step Claim ID, bind its artifact, and resolve all items", f"{path}.researcher_collaboration.task_records[{task_kind}].details"))
    return issues
