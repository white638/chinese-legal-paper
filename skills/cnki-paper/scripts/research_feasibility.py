#!/usr/bin/env python3
"""Validate F2 minimum-viable-evidence judgments and enforce resource fuses.

This research-owned contract answers one narrow question: can the selected
question be supported by *verified* materials within the stated inference
boundary?  It consumes acquisition-owned material facts, binds only the
selected material/probe subgraph, and refuses to unlock expensive actions for
CONDITIONAL, BLOCKED, FAIL, NEEDS_REVIEW, or stale judgments.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from avereth_core.infrastructure.locks import exclusive_lock
from research_materials import (
    REGISTRY_REL,
    canonical_digest,
    live_material_basis,
    validate_contract as validate_material_contract,
)


SCHEMA_VERSION = "avereth-research-feasibility/v1"
FEASIBILITY_REL = Path("research_feasibility.json")
SCHEMA_ASSET = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "schemas"
    / "avereth-research-feasibility-v1.schema.json"
)
MIGRATION_REL = Path("migration/research_feasibility")
SHA256 = re.compile(r"^[a-f0-9]{64}$")

DIMENSIONS = {
    "actual_access",
    "legal_and_ethics",
    "coverage",
    "required_fields_or_roles",
    "machine_readability",
    "linkage_and_comparability",
    "variation_or_identification",
    "cost_and_time",
    "source_stability",
}
DIMENSION_VERDICTS = {"PASS", "CONDITIONAL", "BLOCKED", "FAIL", "NOT_APPLICABLE"}
VERDICTS = {"PASS", "CONDITIONAL", "BLOCKED", "FAIL", "NOT_APPLICABLE", "STALE", "NEEDS_REVIEW"}
UNLOCKING_VERDICTS = {"PASS", "NOT_APPLICABLE"}

LOW_COST_ACTIONS = {
    "requirement_decomposition",
    "metadata_query",
    "permission_check",
    "ethics_check",
    "small_sample_acquisition",
    "format_probe",
    "field_probe",
    "limited_collision_precheck",
}
POST_FEASIBILITY_ACTIONS = {
    "directed_retrieval",
    "bulk_download",
    "full_corpus_build",
    "embeddings",
    "full_synthesis",
    "multi_round_review",
}
POST_COMMITMENT_ACTIONS = {
    "model_training",
    "full_research_design",
    "manuscript_drafting",
}
ALL_ACTIONS = LOW_COST_ACTIONS | POST_FEASIBILITY_ACTIONS | POST_COMMITMENT_ACTIONS


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str = ""
    severity: str = "ERROR"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    def add(self, code: str, message: str, path: str = "", severity: str = "ERROR") -> None:
        self.issues.append(Issue(code, message, path, severity))

    @property
    def errors(self) -> list[Issue]:
        return [item for item in self.issues if item.severity == "ERROR"]

    @property
    def status(self) -> str:
        return "FAIL" if self.errors else "PASS"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _timestamp(value: Any) -> bool:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(path: Path) -> tuple[Path, Path]:
    target = path.resolve()
    return (target.parent, target) if target.suffix.casefold() == ".json" else (target, target / FEASIBILITY_REL)


def _safe_path(base: Path, raw: Any) -> Path | None:
    token = _text(raw)
    if not token:
        return None
    candidate = Path(token)
    try:
        resolved = candidate.resolve() if candidate.is_absolute() else (base / candidate).resolve()
        resolved.relative_to(base.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _assessment_projection(assessment: Mapping[str, Any]) -> dict[str, Any]:
    """Project only feasibility semantics; operational notes cannot mask drift."""

    return {
        "candidate_id": _text(assessment.get("candidate_id")).upper(),
        "topic_option_id": _text(assessment.get("topic_option_id")),
        "question_version_id": _text(assessment.get("question_version_id")),
        "question_text": _text(assessment.get("question_text")),
        "candidate_semantic_digest": _text(assessment.get("candidate_semantic_digest")).casefold(),
        "required_observations": deepcopy(assessment.get("required_observations") or []),
        "material_refs": deepcopy(assessment.get("material_refs") or []),
        "dimensions": deepcopy(assessment.get("dimensions") or {}),
        "critical_dimensions": deepcopy(assessment.get("critical_dimensions") or []),
        "verdict": _text(assessment.get("verdict")),
        "allowed_question_boundary": deepcopy(assessment.get("allowed_question_boundary") or {}),
        "fallbacks": deepcopy(assessment.get("fallbacks") or []),
        "rationale": _text(assessment.get("rationale")),
    }


def _assessments(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(item.get("candidate_id")).upper(): item
        for item in payload.get("candidate_assessments") or []
        if isinstance(item, Mapping) and _text(item.get("candidate_id"))
    }


def selected_live_basis(
    base: Path, payload: Mapping[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    selected_id = _text(payload.get("selected_candidate_id")).upper()
    selected = _assessments(payload).get(selected_id)
    if selected is None:
        return {}, ["selected candidate assessment is missing"]
    _material_base, registry, registry_result = validate_material_contract(base, scope="research")
    if registry is None or registry_result.errors:
        issues.extend(f"[{item.code}] {item.message}" for item in registry_result.errors)
        return {}, issues
    material_basis, material_issues = live_material_basis(registry, selected.get("material_refs") or [])
    issues.extend(material_issues)
    assessment_projection = _assessment_projection(selected)
    assessment_digest = canonical_digest(assessment_projection)
    material_digest = canonical_digest(material_basis)
    basis = {
        "selected_assessment": assessment_projection,
        "selected_assessment_digest": assessment_digest,
        "material_basis": material_basis,
        "material_basis_digest": material_digest,
    }
    basis["basis_digest"] = canonical_digest(
        {
            "selected_assessment_digest": assessment_digest,
            "material_basis_digest": material_digest,
        }
    )
    return basis, issues


def _probe_records(registry: Mapping[str, Any]) -> dict[tuple[str, str], Mapping[str, Any]]:
    records: dict[tuple[str, str], Mapping[str, Any]] = {}
    for material in registry.get("materials") or []:
        if not isinstance(material, Mapping):
            continue
        material_id = _text(material.get("material_id")).upper()
        for probe in material.get("probes") or []:
            if isinstance(probe, Mapping):
                records[(material_id, _text(probe.get("probe_id")).upper())] = probe
    return records


def _material_records(registry: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(item.get("material_id")).upper(): item
        for item in registry.get("materials") or []
        if isinstance(item, Mapping) and _text(item.get("material_id"))
    }


def _validate_assessment_shape(
    assessment: Mapping[str, Any], result: ValidationResult, path: str
) -> None:
    candidate_id = _text(assessment.get("candidate_id")).upper()
    if not re.fullmatch(r"CAND-\d{2,}", candidate_id):
        result.add("RF.ASSESSMENT.CANDIDATE_ID", "candidate_id must match CAND-##", f"{path}.candidate_id")
    if len(_text(assessment.get("topic_option_id"))) < 1:
        result.add("RF.ASSESSMENT.TOPIC", "topic_option_id is required", f"{path}.topic_option_id")
    if len(_text(assessment.get("question_version_id"))) < 1:
        result.add("RF.ASSESSMENT.QUESTION_VERSION", "question_version_id is required", f"{path}.question_version_id")
    if len(_text(assessment.get("question_text"))) < 8:
        result.add("RF.ASSESSMENT.QUESTION", "question_text must be substantive", f"{path}.question_text")
    if not SHA256.fullmatch(_text(assessment.get("candidate_semantic_digest")).casefold()):
        result.add("RF.ASSESSMENT.CANDIDATE_DIGEST", "candidate_semantic_digest must be SHA-256", f"{path}.candidate_semantic_digest")
    observations = assessment.get("required_observations")
    if not isinstance(observations, list) or not observations or any(len(_text(item)) < 4 for item in observations):
        result.add("RF.ASSESSMENT.OBSERVATIONS", "F0 must state substantive required observations", f"{path}.required_observations")
    refs = assessment.get("material_refs")
    if not isinstance(refs, list):
        result.add("RF.ASSESSMENT.MATERIAL_REFS", "material_refs must be an array", f"{path}.material_refs")
        refs = []
    seen_materials: set[str] = set()
    for ref_index, reference in enumerate(refs):
        ref_path = f"{path}.material_refs[{ref_index}]"
        if not isinstance(reference, Mapping):
            result.add("RF.MATERIAL_REF.INVALID", "material reference must be an object", ref_path)
            continue
        material_id = _text(reference.get("material_id")).upper()
        if not re.fullmatch(r"MAT-\d{3,}", material_id) or material_id in seen_materials:
            result.add("RF.MATERIAL_REF.ID", "material_id must be unique and match MAT-###", f"{ref_path}.material_id")
        seen_materials.add(material_id)
        probe_ids = [_text(item).upper() for item in reference.get("probe_ids") or [] if _text(item)]
        if not probe_ids or len(probe_ids) != len(set(probe_ids)) or any(not re.fullmatch(r"PROBE-\d{3,}", item) for item in probe_ids):
            result.add("RF.MATERIAL_REF.PROBES", "probe_ids must contain unique PROBE-### identities", f"{ref_path}.probe_ids")
    dimensions = assessment.get("dimensions")
    if not isinstance(dimensions, Mapping):
        result.add("RF.DIMENSIONS", "dimensions must be an object", f"{path}.dimensions")
        dimensions = {}
    missing_dimensions = DIMENSIONS - set(dimensions)
    extra_dimensions = set(dimensions) - DIMENSIONS
    if missing_dimensions:
        result.add("RF.DIMENSIONS.MISSING", "missing dimensions: " + ", ".join(sorted(missing_dimensions)), f"{path}.dimensions")
    if extra_dimensions:
        result.add("RF.DIMENSIONS.UNKNOWN", "unknown dimensions: " + ", ".join(sorted(extra_dimensions)), f"{path}.dimensions")
    for name, verdict in dimensions.items():
        if verdict not in DIMENSION_VERDICTS:
            result.add("RF.DIMENSION.VERDICT", f"unsupported dimension verdict for {name}", f"{path}.dimensions.{name}")
    critical = assessment.get("critical_dimensions")
    if not isinstance(critical, list) or not critical:
        result.add("RF.CRITICAL.EMPTY", "at least one critical dimension is required", f"{path}.critical_dimensions")
        critical = []
    unknown_critical = {_text(item) for item in critical} - DIMENSIONS
    if unknown_critical:
        result.add("RF.CRITICAL.UNKNOWN", "unknown critical dimensions: " + ", ".join(sorted(unknown_critical)), f"{path}.critical_dimensions")
    verdict = _text(assessment.get("verdict"))
    if verdict not in VERDICTS:
        result.add("RF.VERDICT", "unsupported feasibility verdict", f"{path}.verdict")
    critical_results = {_text(dimensions.get(_text(name))) for name in critical}
    if verdict == "PASS" and not critical_results.issubset({"PASS", "NOT_APPLICABLE"}):
        result.add("RF.CRITICAL.VETO", "PASS is forbidden while a critical dimension is conditional, blocked, or failed", f"{path}.verdict")
    if verdict == "CONDITIONAL" and critical_results & {"BLOCKED", "FAIL"}:
        result.add("RF.CRITICAL.VETO", "CONDITIONAL cannot override a blocked or failed critical dimension", f"{path}.verdict")
    boundary = assessment.get("allowed_question_boundary")
    if not isinstance(boundary, Mapping):
        result.add("RF.BOUNDARY", "allowed_question_boundary must be an object", f"{path}.allowed_question_boundary")
        boundary = {}
    for field_name in ("statement", "time_scope", "spatial_scope", "unit_scope"):
        if len(_text(boundary.get(field_name))) < (8 if field_name == "statement" else 1):
            result.add("RF.BOUNDARY.FIELD", f"boundary lacks {field_name}", f"{path}.allowed_question_boundary.{field_name}")
    if not boundary.get("allowed_claim_types"):
        result.add("RF.BOUNDARY.CLAIMS", "boundary must state allowed claim types", f"{path}.allowed_question_boundary.allowed_claim_types")
    boundary_materials = {_text(item).upper() for item in boundary.get("material_ids") or [] if _text(item)}
    if boundary_materials != seen_materials:
        result.add("RF.BOUNDARY.MATERIALS", "boundary material_ids must exactly match material_refs", f"{path}.allowed_question_boundary.material_ids")
    if len(_text(assessment.get("rationale"))) < 8:
        result.add("RF.RATIONALE", "assessment needs a substantive rationale", f"{path}.rationale")
    if not _timestamp(assessment.get("assessed_at")):
        result.add("RF.TIME", "assessed_at must include an ISO timezone", f"{path}.assessed_at")


def validate_feasibility(base: Path, payload: Mapping[str, Any]) -> ValidationResult:
    result = ValidationResult()
    if _text(payload.get("schema_version")) != SCHEMA_VERSION:
        result.add("RF.SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version")
        return result
    if not re.fullmatch(r"FEAS-\d{3,}", _text(payload.get("feasibility_id"))):
        result.add("RF.ID", "feasibility_id must match FEAS-###", "feasibility_id")
    status = _text(payload.get("status"))
    if status not in VERDICTS:
        result.add("RF.STATUS", "unsupported feasibility status", "status")
    assessments = payload.get("candidate_assessments")
    if not isinstance(assessments, list):
        result.add("RF.ASSESSMENTS", "candidate_assessments must be an array", "candidate_assessments")
        assessments = []
    if not assessments and status == "NEEDS_REVIEW":
        result.add(
            "RF.REVIEW.REQUIRED",
            "migration skeleton cannot infer F2 PASS; complete an explicit candidate assessment",
            "candidate_assessments",
        )
        return result
    if not assessments:
        result.add("RF.ASSESSMENTS", "candidate_assessments must contain at least one assessment", "candidate_assessments")
    seen: set[str] = set()
    for index, assessment in enumerate(assessments):
        path = f"candidate_assessments[{index}]"
        if not isinstance(assessment, Mapping):
            result.add("RF.ASSESSMENT.INVALID", "every assessment must be an object", path)
            continue
        candidate_id = _text(assessment.get("candidate_id")).upper()
        if candidate_id in seen:
            result.add("RF.ASSESSMENT.DUPLICATE", "candidate_id must be unique", f"{path}.candidate_id")
        seen.add(candidate_id)
        _validate_assessment_shape(assessment, result, path)

    selected_id = _text(payload.get("selected_candidate_id")).upper()
    question_version_id = _text(payload.get("question_version_id"))
    selected = _assessments(payload).get(selected_id)
    if selected is None:
        result.add("RF.SELECTED.MISSING", "selected_candidate_id does not resolve to an assessment", "selected_candidate_id")
        return result
    if question_version_id != _text(selected.get("question_version_id")):
        result.add("RF.SELECTED.QUESTION", "question_version_id does not match the selected assessment", "question_version_id")
    if status != _text(selected.get("verdict")):
        result.add("RF.SELECTED.STATUS", "top-level status must equal the selected assessment verdict", "status")

    material_base, registry, registry_result = validate_material_contract(base, scope="research")
    for issue in registry_result.errors:
        result.add("RF.MATERIAL.CONTRACT", f"[{issue.code}] {issue.message}", REGISTRY_REL.as_posix())
    if registry is None:
        return result
    refs = selected.get("material_refs") or []
    if status == "NOT_APPLICABLE":
        applicability = registry.get("applicability") if isinstance(registry.get("applicability"), Mapping) else {}
        if _text(applicability.get("status")) != "NOT_APPLICABLE":
            result.add("RF.NA.REGISTRY", "NOT_APPLICABLE requires an explicit acquisition-owned N/A finding", "status")
        if refs:
            result.add("RF.NA.MATERIALS", "NOT_APPLICABLE cannot bind material probes", "candidate_assessments")
    elif status in UNLOCKING_VERDICTS and not refs:
        result.add("RF.PASS.NO_MATERIAL", "PASS requires at least one verified material/probe reference", "candidate_assessments")

    materials = _material_records(registry)
    probes = _probe_records(registry)
    for ref_index, reference in enumerate(refs):
        if not isinstance(reference, Mapping):
            continue
        material_id = _text(reference.get("material_id")).upper()
        material = materials.get(material_id)
        if material is None:
            result.add("RF.MATERIAL.UNKNOWN", f"unknown material: {material_id}", f"material_refs[{ref_index}]")
            continue
        access = material.get("access") if isinstance(material.get("access"), Mapping) else {}
        if status == "PASS" and _text(access.get("status")) != "VERIFIED":
            result.add("RF.MATERIAL.ACCESS", f"PASS requires VERIFIED access for {material_id}", f"material_refs[{ref_index}]")
        if status == "PASS" and _text(access.get("permission_status")) not in {"PERMITTED", "NOT_REQUIRED"}:
            result.add("RF.MATERIAL.PERMISSION", f"PASS requires permission for {material_id}", f"material_refs[{ref_index}]")
        for probe_id in reference.get("probe_ids") or []:
            probe = probes.get((material_id, _text(probe_id).upper()))
            if probe is None:
                result.add("RF.PROBE.UNKNOWN", f"unknown probe {_text(probe_id)} for {material_id}", f"material_refs[{ref_index}]")
            elif status == "PASS" and _text(probe.get("status")) != "PASS":
                result.add("RF.PROBE.NOT_PASS", f"PASS requires a successful probe: {_text(probe_id)}", f"material_refs[{ref_index}]")

    live, live_issues = selected_live_basis(base, payload)
    for issue in live_issues:
        result.add("RF.BASIS.MISSING", issue, "material_basis_digest")
    if live:
        declared_assessment = _text(payload.get("selected_assessment_digest")).casefold()
        declared_material = _text(payload.get("material_basis_digest")).casefold()
        declared_basis = _text(payload.get("basis_digest")).casefold()
        if declared_assessment != live["selected_assessment_digest"]:
            result.add("RF.BASIS.ASSESSMENT_STALE", "selected assessment digest is stale", "selected_assessment_digest")
        if declared_material != live["material_basis_digest"]:
            result.add("RF.BASIS.MATERIAL_STALE", "selected material/probe basis is stale", "material_basis_digest")
        if declared_basis != live["basis_digest"]:
            result.add("RF.BASIS.STALE", "feasibility basis digest is stale", "basis_digest")
    return result


def validate_contract(path: Path) -> tuple[Path, dict[str, Any] | None, ValidationResult]:
    base, target = _resolve(path)
    result = ValidationResult()
    if not target.is_file():
        result.add("RF.FILE.MISSING", f"research feasibility contract is missing: {FEASIBILITY_REL.as_posix()}", FEASIBILITY_REL.as_posix())
        return base, None, result
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        result.add("RF.JSON.INVALID", f"research feasibility contract cannot be read: {exc}", FEASIBILITY_REL.as_posix())
        return base, None, result
    if not isinstance(payload, dict):
        result.add("RF.JSON.INVALID", "research feasibility contract must contain one object", FEASIBILITY_REL.as_posix())
        return base, None, result
    return base, payload, validate_feasibility(base, payload)


def feasibility_reference(base: Path) -> tuple[dict[str, Any] | None, list[str]]:
    _base, payload, result = validate_contract(base)
    issues = [f"[{item.code}] {item.message}" for item in result.errors]
    if payload is None or result.errors:
        return None, issues
    if _text(payload.get("status")) not in UNLOCKING_VERDICTS:
        return None, [f"feasibility verdict {_text(payload.get('status'))} does not unlock downstream work"]
    selected = _assessments(payload).get(_text(payload.get("selected_candidate_id")).upper())
    boundary = selected.get("allowed_question_boundary") if isinstance(selected, Mapping) else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "feasibility_id": _text(payload.get("feasibility_id")),
        "candidate_id": _text(payload.get("selected_candidate_id")).upper(),
        "question_version_id": _text(payload.get("question_version_id")),
        "candidate_semantic_digest": _text((selected or {}).get("candidate_semantic_digest")),
        "verdict": _text(payload.get("status")),
        "selected_assessment_digest": _text(payload.get("selected_assessment_digest")),
        "material_basis_digest": _text(payload.get("material_basis_digest")),
        "basis_digest": _text(payload.get("basis_digest")),
        "allowed_question_boundary_digest": canonical_digest(boundary or {}),
    }, []


def resource_unlock_state(base: Path, *, question_committed: bool = False) -> dict[str, Any]:
    reference, issues = feasibility_reference(base)
    if reference is None:
        phase = "pre_feasibility"
        allowed = LOW_COST_ACTIONS
        blocker = issues[0] if issues else "F2 minimum viable evidence has not passed"
    elif question_committed:
        phase = "post_commitment"
        allowed = ALL_ACTIONS
        blocker = None
    else:
        phase = "post_feasibility"
        allowed = LOW_COST_ACTIONS | POST_FEASIBILITY_ACTIONS
        blocker = "question commitment is required for design, training, or drafting"
    return {
        "schema_version": "avereth-resource-unlock/v1",
        "phase": phase,
        "feasibility_ref": reference,
        "allowed_actions": sorted(allowed),
        "blocked_actions": sorted(ALL_ACTIONS - allowed),
        "resource_blocker": blocker,
    }


def authorize_action(base: Path, action: str, *, question_committed: bool = False) -> dict[str, Any]:
    if action not in ALL_ACTIONS:
        return {
            "schema_version": "avereth-resource-authorization/v1",
            "status": "FAIL",
            "action": action,
            "reason": "unknown resource action",
        }
    state = resource_unlock_state(base, question_committed=question_committed)
    permitted = action in set(state["allowed_actions"])
    return {
        "schema_version": "avereth-resource-authorization/v1",
        "status": "PASS" if permitted else "BLOCKED",
        "action": action,
        "phase": state["phase"],
        "reason": None if permitted else state["resource_blocker"],
        "feasibility_ref": state["feasibility_ref"],
    }


def _transaction(
    base: Path,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
    *,
    operation: str,
) -> dict[str, Any]:
    target = base / FEASIBILITY_REL
    before_bytes = target.read_bytes() if target.is_file() else b""
    before_sha = hashlib.sha256(before_bytes).hexdigest() if before_bytes else None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = base / MIGRATION_REL / f"{stamp}-{canonical_digest(after)[:12]}"
    root.mkdir(parents=True, exist_ok=False)
    backup_rel: str | None = None
    if before_bytes:
        backup = root / FEASIBILITY_REL.name
        backup.write_bytes(before_bytes)
        backup_rel = backup.relative_to(base).as_posix()
    _atomic_json(target, after)
    manifest = {
        "schema_version": "avereth-research-feasibility-mutation/v1",
        "operation": operation,
        "path": FEASIBILITY_REL.as_posix(),
        "before_sha256": before_sha,
        "after_sha256": _sha256(target),
        "backup": backup_rel,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(root / "mutation_manifest.json", manifest)
    manifest["manifest"] = (root / "mutation_manifest.json").relative_to(base).as_posix()
    return manifest


def _plan(before: Mapping[str, Any] | None, after: Mapping[str, Any], operation: str) -> dict[str, Any]:
    return {
        "schema_version": "avereth-research-feasibility-mutation/v1",
        "mode": "plan",
        "operation": operation,
        "path": FEASIBILITY_REL.as_posix(),
        "before_digest": canonical_digest(before) if before else None,
        "after_digest": canonical_digest(after),
    }


def bind_payload(
    before: Mapping[str, Any] | None,
    assessment: Mapping[str, Any],
    *,
    select: bool,
) -> dict[str, Any]:
    after = deepcopy(before) if before else {
        "schema_version": SCHEMA_VERSION,
        "feasibility_id": "FEAS-001",
        "status": "NEEDS_REVIEW",
        "selected_candidate_id": None,
        "question_version_id": None,
        "candidate_assessments": [],
        "selected_assessment_digest": None,
        "material_basis_digest": None,
        "basis_digest": None,
        "invalidation_archive": [],
    }
    candidate_id = _text(assessment.get("candidate_id")).upper()
    records = [
        deepcopy(item)
        for item in after.get("candidate_assessments") or []
        if isinstance(item, Mapping) and _text(item.get("candidate_id")).upper() != candidate_id
    ]
    records.append(deepcopy(dict(assessment)))
    after["candidate_assessments"] = records
    if select or not _text(after.get("selected_candidate_id")):
        after["selected_candidate_id"] = candidate_id
        after["question_version_id"] = _text(assessment.get("question_version_id"))
        after["status"] = _text(assessment.get("verdict"))
    return after


def bind_command(path: Path, assessment_path: Path, *, select: bool, apply: bool) -> int:
    base, target = _resolve(path)
    before: dict[str, Any] | None = None
    if target.is_file():
        try:
            before = json.loads(target.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"cannot read existing feasibility contract: {exc}", file=sys.stderr)
            return 2
    resolved = _safe_path(base, assessment_path)
    if resolved is None or not resolved.is_file():
        print("assessment JSON must be an existing file inside the workspace", file=sys.stderr)
        return 2
    try:
        assessment = json.loads(resolved.read_text(encoding="utf-8-sig"))
        if not isinstance(assessment, dict):
            raise ValueError("assessment must contain one JSON object")
        after = bind_payload(before, assessment, select=select)
        live, live_issues = selected_live_basis(base, after)
        if live_issues:
            raise ValueError("; ".join(live_issues))
        after["selected_assessment_digest"] = live["selected_assessment_digest"]
        after["material_basis_digest"] = live["material_basis_digest"]
        after["basis_digest"] = live["basis_digest"]
        validation = validate_feasibility(base, after)
        if validation.errors:
            raise ValueError("; ".join(f"[{item.code}] {item.message}" for item in validation.errors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not apply:
        print(json.dumps(_plan(before, after, "bind"), ensure_ascii=False, indent=2))
        return 0
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-feasibility-bind"):
            report = _transaction(base, before, after, operation="bind")
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report["status"] = after["status"]
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def reopen_command(path: Path, *, reason: str, apply: bool) -> int:
    try:
        base, target = _resolve(path)
        before = json.loads(target.read_text(encoding="utf-8-sig"))
        if not isinstance(before, dict):
            raise ValueError("research_feasibility.json must contain one object")
        after = deepcopy(before)
        archive = {
            "invalidated_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "selected_candidate_id": after.get("selected_candidate_id"),
            "question_version_id": after.get("question_version_id"),
            "basis_digest": after.get("basis_digest"),
        }
        after.setdefault("invalidation_archive", []).append(archive)
        after["status"] = "STALE"
        selected = _assessments(after).get(_text(after.get("selected_candidate_id")).upper())
        if isinstance(selected, dict):
            selected["verdict"] = "STALE"
        live, live_issues = selected_live_basis(base, after)
        if live_issues:
            raise ValueError("; ".join(live_issues))
        after["selected_assessment_digest"] = live["selected_assessment_digest"]
        after["material_basis_digest"] = live["material_basis_digest"]
        after["basis_digest"] = live["basis_digest"]
        validation = validate_feasibility(base, after)
        if validation.errors:
            raise ValueError("; ".join(f"[{item.code}] {item.message}" for item in validation.errors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not apply:
        print(json.dumps(_plan(before, after, "reopen"), ensure_ascii=False, indent=2))
        return 0
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-feasibility-reopen"):
            report = _transaction(base, before, after, operation="reopen")
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report["status"] = "STALE"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def rollback_command(path: Path, manifest_path: Path, *, apply: bool) -> int:
    base, target = _resolve(path)
    try:
        resolved_manifest = _safe_path(base, manifest_path)
        if resolved_manifest is None or not resolved_manifest.is_file():
            raise ValueError("rollback manifest must be an existing file inside the workspace")
        manifest = json.loads(resolved_manifest.read_text(encoding="utf-8-sig"))
        if manifest.get("schema_version") != "avereth-research-feasibility-mutation/v1":
            raise ValueError("unsupported research-feasibility rollback manifest")
        if _text(manifest.get("path")) != FEASIBILITY_REL.as_posix():
            raise ValueError("rollback manifest targets a different artifact")
        if not target.is_file() or _sha256(target) != _text(manifest.get("after_sha256")):
            raise ValueError("research feasibility changed after the mutation; refusing rollback")
        backup_raw = manifest.get("backup")
        backup = _safe_path(base, backup_raw) if backup_raw else None
        if backup is not None and (not backup.is_file() or _sha256(backup) != _text(manifest.get("before_sha256"))):
            raise ValueError("rollback backup is missing or changed")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report = {"schema_version": "avereth-research-feasibility-rollback/v1", "status": "READY", "path": FEASIBILITY_REL.as_posix()}
    if not apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-feasibility-rollback"):
            if backup is None:
                target.unlink()
            else:
                temporary = target.with_suffix(target.suffix + ".rollback.tmp")
                shutil.copy2(backup, temporary)
                temporary.replace(target)
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report["status"] = "ROLLED_BACK"
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def validate_command(path: Path, *, json_stdout: bool) -> int:
    _base, payload, result = validate_contract(path)
    report = {
        "schema_version": _text((payload or {}).get("schema_version")),
        "status": result.status,
        "feasibility_verdict": _text((payload or {}).get("status")),
        "issues": [item.as_dict() for item in result.issues],
    }
    if json_stdout:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("# Research Feasibility Check\n")
        print(f"Status: {result.status}\n")
        for issue in result.issues:
            print(f"- [{issue.code}] {issue.message}")
    return 1 if result.errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    bind_parser = commands.add_parser("bind")
    bind_parser.add_argument("path", type=Path)
    bind_parser.add_argument("--assessment", type=Path, required=True)
    bind_parser.add_argument("--select", action="store_true")
    bind_parser.add_argument("--apply", action="store_true")
    reopen_parser = commands.add_parser("reopen")
    reopen_parser.add_argument("path", type=Path)
    reopen_parser.add_argument("--reason", required=True)
    reopen_parser.add_argument("--apply", action="store_true")
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("path", type=Path)
    rollback_parser.add_argument("--manifest", type=Path, required=True)
    rollback_parser.add_argument("--apply", action="store_true")
    authorize_parser = commands.add_parser("authorize")
    authorize_parser.add_argument("path", type=Path)
    authorize_parser.add_argument("--action", choices=sorted(ALL_ACTIONS), required=True)
    authorize_parser.add_argument("--question-committed", action="store_true")
    state_parser = commands.add_parser("resource-state")
    state_parser.add_argument("path", type=Path)
    state_parser.add_argument("--question-committed", action="store_true")
    commands.add_parser("schema")
    args = parser.parse_args(argv)
    if args.command == "validate":
        return validate_command(args.path, json_stdout=args.json)
    if args.command == "bind":
        return bind_command(args.path, args.assessment, select=args.select, apply=args.apply)
    if args.command == "reopen":
        return reopen_command(args.path, reason=args.reason, apply=args.apply)
    if args.command == "rollback":
        return rollback_command(args.path, args.manifest, apply=args.apply)
    if args.command == "authorize":
        report = authorize_action(args.path.resolve(), args.action, question_committed=args.question_committed)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if args.command == "resource-state":
        print(json.dumps(resource_unlock_state(args.path.resolve(), question_committed=args.question_committed), ensure_ascii=False, indent=2))
        return 0
    if args.command == "schema":
        print(SCHEMA_ASSET.read_text(encoding="utf-8"), end="")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
