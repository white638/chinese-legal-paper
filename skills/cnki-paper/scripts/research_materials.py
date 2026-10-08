#!/usr/bin/env python3
"""Validate and probe acquisition-owned research-material facts.

The registry records material identity, access, permission, bounded probe
evidence, and stable failure-cache entries.  It never stores credentials and
does not decide whether a candidate question is answerable; that judgment
belongs to :mod:`research_feasibility` in the research stage.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from avereth_core.infrastructure.locks import exclusive_lock


SCHEMA_VERSION = "avereth-research-material-registry/v1"
REGISTRY_REL = Path("reference_materials/research_material_registry.json")
SCHEMA_ASSET = (
    Path(__file__).resolve().parents[1]
    / "references"
    / "schemas"
    / "avereth-research-material-registry-v1.schema.json"
)
MIGRATION_REL = Path("migration/research_materials")
PROBE_IMPLEMENTATION_VERSION = "research-material-probe/v1"

MATERIAL_TYPES = {
    "structured_dataset",
    "api",
    "public_text",
    "policy_legal_text",
    "archive_case",
    "interview",
    "survey",
    "restricted_data",
    "systematic_review_corpus",
    "manual_evidence",
}
ACCESS_STATUSES = {"VERIFIED", "BLOCKED", "FAILED", "UNKNOWN", "NOT_APPLICABLE"}
PERMISSION_STATUSES = {"PERMITTED", "PENDING", "DENIED", "NOT_REQUIRED", "UNKNOWN"}
PROBE_STATUSES = {"PASS", "BLOCKED", "FAIL", "NOT_APPLICABLE"}
FAILURE_CODES = {
    "NO_ACTUAL_ACCESS",
    "AUTHORIZATION_PENDING",
    "REQUIRED_PERIOD_ABSENT",
    "REQUIRED_UNIT_ABSENT",
    "REQUIRED_FIELD_ABSENT",
    "PARSER_FAILED",
    "NO_LINKAGE_KEY",
    "NO_REQUIRED_VARIATION",
    "LEGAL_RESTRICTION",
    "ETHICS_NOT_CLEARED",
    "COST_EXCEEDS_POLICY",
    "SOURCE_UNSTABLE",
}
SECRET_KEYS = {
    "password",
    "cookie",
    "cookies",
    "api_key",
    "api_token",
    "access_token",
    "refresh_token",
    "secret",
    "secret_key",
    "credential_value",
    "authorization_header",
    "bearer_token",
}
SHA256 = re.compile(r"^[a-f0-9]{64}$")


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


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_identity(path: Path, metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
    )


def _sha256(path: Path) -> str:
    """Stream one stable file identity and fail if it changes while hashing."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = _file_identity(path, os.fstat(handle.fileno()))
        while block := handle.read(1024 * 1024):
            digest.update(block)
        after = _file_identity(path, os.fstat(handle.fileno()))
    if after != before or _file_identity(path, path.stat()) != before:
        raise OSError("file changed during hashing")
    return digest.hexdigest()


def _timestamp(value: Any) -> bool:
    try:
        parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _resolve(path: Path) -> tuple[Path, Path]:
    target = path.resolve()
    return (target.parent, target) if target.suffix.casefold() == ".json" else (target, target / REGISTRY_REL)


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


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_registry(path: Path) -> tuple[Path, Path, dict[str, Any]]:
    base, target = _resolve(path)
    payload = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("research_material_registry.json must contain one JSON object")
    return base, target, payload


def _secret_paths(value: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if str(key).strip().casefold() in SECRET_KEYS and item not in (None, "", False, [], {}):
                found.append(path)
            found.extend(_secret_paths(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_secret_paths(item, f"{prefix}[{index}]"))
    return found


def material_identity(material: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "material_id": _text(material.get("material_id")).upper(),
        "material_type": _text(material.get("material_type")),
        "source_ids": sorted(
            _text(item).upper() for item in material.get("source_ids") or [] if _text(item)
        ),
        "material_locator": deepcopy(material.get("material_locator")),
        "access": deepcopy(material.get("access")),
    }


def material_identity_digest(material: Mapping[str, Any]) -> str:
    return canonical_digest(material_identity(material))


def failure_cache_key(
    candidate_semantic_digest: str,
    question_version_digest: str,
    material_digest: str,
    implementation_version: str,
) -> str:
    return canonical_digest(
        {
            "candidate_semantic_digest": candidate_semantic_digest,
            "question_version_digest": question_version_digest,
            "material_identity_digest": material_digest,
            "probe_implementation_version": implementation_version,
        }
    )


def _records(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(item.get("material_id")).upper(): item
        for item in payload.get("materials") or []
        if isinstance(item, Mapping) and _text(item.get("material_id"))
    }


def material_projection(
    payload: Mapping[str, Any],
    material_id: str,
    probe_ids: Sequence[str],
) -> tuple[dict[str, Any], list[str]]:
    material = _records(payload).get(_text(material_id).upper())
    if material is None:
        return {}, [f"unknown material identity: {material_id}"]
    probes = {
        _text(item.get("probe_id")).upper(): item
        for item in material.get("probes") or []
        if isinstance(item, Mapping) and _text(item.get("probe_id"))
    }
    wanted = [_text(item).upper() for item in probe_ids if _text(item)]
    missing = [item for item in wanted if item not in probes]
    if missing:
        return {}, [f"material {material_id} lacks probes: {', '.join(missing)}"]
    projection = {
        "material_identity": material_identity(material),
        "material_identity_digest": material_identity_digest(material),
        "probes": {identity: deepcopy(probes[identity]) for identity in sorted(set(wanted))},
    }
    projection["projection_digest"] = canonical_digest(projection)
    return projection, []


def live_material_basis(
    payload: Mapping[str, Any], refs: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    projections: dict[str, Any] = {}
    issues: list[str] = []
    for reference in refs:
        material_id = _text(reference.get("material_id")).upper()
        probe_ids = [
            _text(item).upper() for item in reference.get("probe_ids") or [] if _text(item)
        ]
        projection, projection_issues = material_projection(payload, material_id, probe_ids)
        issues.extend(projection_issues)
        if projection:
            projections[material_id] = projection
    basis = {
        "registry_id": _text(payload.get("registry_id")),
        "probe_implementation_version": _text(payload.get("probe_implementation_version")),
        "materials": projections,
    }
    return basis, issues


def _validate_evidence_file(
    base: Path, evidence: Mapping[str, Any], result: ValidationResult, path: str
) -> None:
    resolved = _safe_path(base, evidence.get("path"))
    declared = _text(evidence.get("sha256")).casefold()
    if resolved is None:
        result.add("RM.EVIDENCE.PATH", "probe evidence path must stay inside the workspace", f"{path}.path")
    else:
        try:
            evidence_is_file = resolved.is_file()
        except OSError:
            result.add(
                "RM.EVIDENCE.RESOURCE",
                "probe evidence cannot be inspected safely",
                f"{path}.path",
            )
        else:
            if not evidence_is_file:
                result.add("RM.EVIDENCE.MISSING", "probe evidence file is missing", f"{path}.path")
            else:
                try:
                    actual = _sha256(resolved)
                except (OSError, MemoryError):
                    result.add(
                        "RM.EVIDENCE.RESOURCE",
                        "probe evidence cannot be verified safely",
                        f"{path}.path",
                    )
                else:
                    if not SHA256.fullmatch(declared) or actual != declared:
                        result.add("RM.EVIDENCE.HASH", "probe evidence SHA-256 does not match the current file", f"{path}.sha256")
    if len(_text(evidence.get("role"))) < 2:
        result.add("RM.EVIDENCE.ROLE", "probe evidence needs a substantive role", f"{path}.role")


def _validate_pass_probe(
    material: Mapping[str, Any], probe: Mapping[str, Any], result: ValidationResult, path: str
) -> None:
    material_type = _text(material.get("material_type"))
    if _text(probe.get("parse_status")) != "PASS":
        result.add("RM.PROBE.PARSE", "a PASS probe must record parse_status=PASS", f"{path}.parse_status")
    if not probe.get("evidence_files"):
        result.add("RM.PROBE.NO_ACTUAL_EVIDENCE", "a PASS probe needs at least one hash-bound evidence file", f"{path}.evidence_files")
    if material_type == "structured_dataset":
        if not isinstance(probe.get("observed_rows"), int) or probe.get("observed_rows", 0) <= 0:
            result.add("RM.PROBE.ROWS", "structured data probe must observe at least one row", f"{path}.observed_rows")
        if not probe.get("observed_fields"):
            result.add("RM.PROBE.FIELDS", "structured data probe must record observed fields", f"{path}.observed_fields")
        if len(_text(probe.get("key_assessment"))) < 4:
            result.add("RM.PROBE.KEY", "structured data probe must assess the unique/linkage key", f"{path}.key_assessment")
    elif material_type == "api":
        for field_name in ("query_summary", "pagination_status", "rate_limit_status"):
            if len(_text(probe.get(field_name))) < 4:
                result.add("RM.PROBE.API", f"API probe lacks {field_name}", f"{path}.{field_name}")
        if not probe.get("observed_fields"):
            result.add("RM.PROBE.FIELDS", "API probe must record response fields", f"{path}.observed_fields")
    elif material_type in {"public_text", "policy_legal_text", "archive_case"}:
        if not isinstance(probe.get("observed_documents"), int) or probe.get("observed_documents", 0) <= 0:
            result.add("RM.PROBE.DOCUMENTS", "text/archive probe must obtain at least one real document", f"{path}.observed_documents")
    elif material_type in {"interview", "survey"}:
        access = material.get("access") if isinstance(material.get("access"), Mapping) else {}
        if _text(access.get("ethics_status")) not in {"CLEARED", "NOT_REQUIRED"}:
            result.add("RM.PROBE.ETHICS", "human-subject material cannot PASS without cleared/not-required ethics", f"{path}.access.ethics_status")
    elif material_type == "restricted_data":
        access = material.get("access") if isinstance(material.get("access"), Mapping) else {}
        if _text(access.get("permission_status")) != "PERMITTED":
            result.add("RM.PROBE.AUTHORIZATION", "restricted data require actual authorization before PASS", f"{path}.access.permission_status")
    elif material_type == "systematic_review_corpus":
        if "pass" not in _text(probe.get("deduplication_status")).casefold():
            result.add("RM.PROBE.DEDUP", "systematic-review corpus must verify export and deduplication", f"{path}.deduplication_status")


def validate_registry(
    base: Path, payload: Mapping[str, Any], *, scope: str = "acquisition"
) -> ValidationResult:
    result = ValidationResult()
    if _text(payload.get("schema_version")) != SCHEMA_VERSION:
        result.add("RM.SCHEMA", f"schema_version must be {SCHEMA_VERSION}", "schema_version")
        return result
    if not re.fullmatch(r"MATREG-\d{3,}", _text(payload.get("registry_id"))):
        result.add("RM.ID", "registry_id must match MATREG-###", "registry_id")
    implementation = _text(payload.get("probe_implementation_version"))
    if not implementation:
        result.add("RM.PROBE.VERSION", "probe_implementation_version is required", "probe_implementation_version")
    for secret_path in _secret_paths(payload):
        result.add("RM.SECRET.FORBIDDEN", "credential values, cookies, tokens, and secrets must not be stored", secret_path)
    applicability = payload.get("applicability")
    if not isinstance(applicability, Mapping):
        result.add("RM.APPLICABILITY", "applicability must be an object", "applicability")
        applicability = {}
    app_status = _text(applicability.get("status"))
    if app_status not in {"APPLICABLE", "NOT_APPLICABLE", "NEEDS_REVIEW"}:
        result.add("RM.APPLICABILITY", "unsupported applicability status", "applicability.status")
    if len(_text(applicability.get("rationale"))) < 8:
        result.add("RM.APPLICABILITY.RATIONALE", "applicability needs a substantive rationale", "applicability.rationale")

    raw_materials = payload.get("materials")
    if not isinstance(raw_materials, list):
        result.add("RM.MATERIALS", "materials must be an array", "materials")
        raw_materials = []
    if app_status == "APPLICABLE" and not raw_materials:
        result.add("RM.MATERIALS.EMPTY", "applicable research must register at least one real material source", "materials")
    if app_status == "NOT_APPLICABLE" and raw_materials:
        result.add("RM.APPLICABILITY.CONFLICT", "NOT_APPLICABLE cannot silently retain empirical material claims", "materials")
    if app_status == "NEEDS_REVIEW" and scope == "research":
        result.add("RM.APPLICABILITY.REVIEW", "material applicability is still needs-review", "applicability.status")

    literature_registry = _read_json(base / "reference_materials" / "literature_registry.json")
    known_source_ids = {
        _text(item.get("source_id")).upper()
        for item in literature_registry.get("sources") or []
        if isinstance(item, Mapping) and _text(item.get("source_id"))
    }
    seen_materials: set[str] = set()
    seen_probes: set[str] = set()
    material_digests: dict[str, str] = {}
    for index, material in enumerate(raw_materials):
        path = f"materials[{index}]"
        if not isinstance(material, Mapping):
            result.add("RM.MATERIAL.INVALID", "every material must be an object", path)
            continue
        material_id = _text(material.get("material_id")).upper()
        if not re.fullmatch(r"MAT-\d{3,}", material_id) or material_id in seen_materials:
            result.add("RM.MATERIAL.ID", "material_id must be unique and match MAT-###", f"{path}.material_id")
        seen_materials.add(material_id)
        material_digests[material_id] = material_identity_digest(material)
        if _text(material.get("material_type")) not in MATERIAL_TYPES:
            result.add("RM.MATERIAL.TYPE", "unsupported material_type", f"{path}.material_type")
        source_ids = {
            _text(item).upper() for item in material.get("source_ids") or [] if _text(item)
        }
        if not source_ids:
            result.add("RM.MATERIAL.SOURCE_REFS", "material must reference at least one canonical literature-registry Source ID", f"{path}.source_ids")
        elif not source_ids.issubset(known_source_ids):
            result.add(
                "RM.MATERIAL.SOURCE_UNKNOWN",
                "material references unknown canonical Source IDs: " + ", ".join(sorted(source_ids - known_source_ids)),
                f"{path}.source_ids",
            )
        if not isinstance(material.get("material_locator"), Mapping) or not material.get("material_locator"):
            result.add("RM.MATERIAL.LOCATOR", "material needs a technical dataset/catalog/version locator", f"{path}.material_locator")
        access = material.get("access")
        if not isinstance(access, Mapping):
            result.add("RM.ACCESS", "material access must be an object", f"{path}.access")
            access = {}
        access_status = _text(access.get("status"))
        permission = _text(access.get("permission_status"))
        if access_status not in ACCESS_STATUSES:
            result.add("RM.ACCESS.STATUS", "unsupported access status", f"{path}.access.status")
        if permission not in PERMISSION_STATUSES:
            result.add("RM.ACCESS.PERMISSION", "unsupported permission status", f"{path}.access.permission_status")
        if not isinstance(access.get("credential_required"), bool):
            result.add("RM.ACCESS.CREDENTIAL_FLAG", "credential_required must be boolean", f"{path}.access.credential_required")
        if access_status == "VERIFIED" and permission not in {"PERMITTED", "NOT_REQUIRED"}:
            result.add("RM.ACCESS.CONFLICT", "VERIFIED access requires permitted or not-required permission", f"{path}.access")

        raw_probes = material.get("probes")
        if not isinstance(raw_probes, list):
            result.add("RM.PROBES", "probes must be an array", f"{path}.probes")
            raw_probes = []
        for probe_index, probe in enumerate(raw_probes):
            probe_path = f"{path}.probes[{probe_index}]"
            if not isinstance(probe, Mapping):
                result.add("RM.PROBE.INVALID", "every probe must be an object", probe_path)
                continue
            probe_id = _text(probe.get("probe_id")).upper()
            if not re.fullmatch(r"PROBE-\d{3,}", probe_id) or probe_id in seen_probes:
                result.add("RM.PROBE.ID", "probe_id must be globally unique and match PROBE-###", f"{probe_path}.probe_id")
            seen_probes.add(probe_id)
            if not _timestamp(probe.get("performed_at")):
                result.add("RM.PROBE.TIME", "probe needs an ISO timestamp with timezone", f"{probe_path}.performed_at")
            status = _text(probe.get("status"))
            if status not in PROBE_STATUSES:
                result.add("RM.PROBE.STATUS", "unsupported probe status", f"{probe_path}.status")
            if _text(probe.get("parse_status")) not in PROBE_STATUSES:
                result.add("RM.PROBE.PARSE_STATUS", "unsupported parse_status", f"{probe_path}.parse_status")
            evidence_files = probe.get("evidence_files")
            if not isinstance(evidence_files, list):
                result.add("RM.EVIDENCE.INVALID", "evidence_files must be an array", f"{probe_path}.evidence_files")
                evidence_files = []
            for evidence_index, evidence in enumerate(evidence_files):
                if not isinstance(evidence, Mapping):
                    result.add("RM.EVIDENCE.INVALID", "evidence file record must be an object", f"{probe_path}.evidence_files[{evidence_index}]")
                    continue
                _validate_evidence_file(base, evidence, result, f"{probe_path}.evidence_files[{evidence_index}]")
            errors = probe.get("errors")
            if not isinstance(errors, list):
                result.add("RM.PROBE.ERRORS", "probe errors must be an array", f"{probe_path}.errors")
                errors = []
            if status in {"FAIL", "BLOCKED"} and not errors:
                result.add("RM.PROBE.FAILURE_REASON", "failed/blocked probe must record a stable error", f"{probe_path}.errors")
            if status == "PASS":
                _validate_pass_probe(material, probe, result, probe_path)

    raw_failures = payload.get("failures")
    if not isinstance(raw_failures, list):
        result.add("RM.FAILURES", "failures must be an array", "failures")
        raw_failures = []
    seen_cache_keys: set[str] = set()
    for index, failure in enumerate(raw_failures):
        path = f"failures[{index}]"
        if not isinstance(failure, Mapping):
            result.add("RM.FAILURE.INVALID", "failure cache entry must be an object", path)
            continue
        code = _text(failure.get("failure_code"))
        cache_key = _text(failure.get("cache_key")).casefold()
        if code not in FAILURE_CODES:
            result.add("RM.FAILURE.CODE", "unsupported stable failure code", f"{path}.failure_code")
        if cache_key in seen_cache_keys or not SHA256.fullmatch(cache_key):
            result.add("RM.FAILURE.CACHE_KEY", "failure cache key must be unique SHA-256", f"{path}.cache_key")
        seen_cache_keys.add(cache_key)
        material_digest = _text(failure.get("material_identity_digest")).casefold()
        expected = failure_cache_key(
            _text(failure.get("candidate_semantic_digest")).casefold(),
            _text(failure.get("question_version_digest")).casefold(),
            material_digest,
            _text(failure.get("probe_implementation_version")),
        )
        if cache_key != expected:
            result.add("RM.FAILURE.CACHE_STALE", "failure cache key does not match its semantic inputs", f"{path}.cache_key")
        if material_digest not in set(material_digests.values()):
            result.add("RM.FAILURE.MATERIAL_STALE", "failure refers to a changed or unknown material identity", f"{path}.material_identity_digest")
        if _text(failure.get("status")) not in {"ACTIVE", "RESOLVED"}:
            result.add("RM.FAILURE.STATUS", "failure status must be ACTIVE or RESOLVED", f"{path}.status")
        if not _timestamp(failure.get("observed_at")):
            result.add("RM.FAILURE.TIME", "failure needs an ISO timestamp with timezone", f"{path}.observed_at")
    return result


def validate_contract(path: Path, *, scope: str = "acquisition") -> tuple[Path, dict[str, Any] | None, ValidationResult]:
    base, target = _resolve(path)
    result = ValidationResult()
    if not target.is_file():
        result.add("RM.FILE.MISSING", f"research material registry is missing: {REGISTRY_REL.as_posix()}", REGISTRY_REL.as_posix())
        return base, None, result
    try:
        payload = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        result.add("RM.JSON.INVALID", f"research material registry cannot be read: {exc}", REGISTRY_REL.as_posix())
        return base, None, result
    if not isinstance(payload, dict):
        result.add("RM.JSON.INVALID", "research material registry must contain one object", REGISTRY_REL.as_posix())
        return base, None, result
    return base, payload, validate_registry(base, payload, scope=scope)


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _transaction(
    base: Path,
    before: Mapping[str, Any] | None,
    after: Mapping[str, Any],
    *,
    operation: str,
) -> dict[str, Any]:
    target = base / REGISTRY_REL
    before_bytes = target.read_bytes() if target.is_file() else b""
    before_sha = hashlib.sha256(before_bytes).hexdigest() if before_bytes else None
    after_sha = canonical_digest(after)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = base / MIGRATION_REL / f"{stamp}-{after_sha[:12]}"
    root.mkdir(parents=True, exist_ok=False)
    backup_rel: str | None = None
    if before_bytes:
        backup = root / REGISTRY_REL.name
        backup.write_bytes(before_bytes)
        backup_rel = backup.relative_to(base).as_posix()
    _atomic_json(target, after)
    current_sha = _sha256(target)
    manifest = {
        "schema_version": "avereth-research-material-mutation/v1",
        "operation": operation,
        "path": REGISTRY_REL.as_posix(),
        "before_sha256": before_sha,
        "after_sha256": current_sha,
        "backup": backup_rel,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_json(root / "mutation_manifest.json", manifest)
    manifest["manifest"] = (root / "mutation_manifest.json").relative_to(base).as_posix()
    return manifest


def _plan(before: Mapping[str, Any] | None, after: Mapping[str, Any], operation: str) -> dict[str, Any]:
    return {
        "schema_version": "avereth-research-material-mutation/v1",
        "mode": "plan",
        "operation": operation,
        "path": REGISTRY_REL.as_posix(),
        "before_digest": canonical_digest(before) if before else None,
        "after_digest": canonical_digest(after),
    }


def init_payload(*, not_applicable: bool, rationale: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "registry_id": "MATREG-001",
        "probe_implementation_version": PROBE_IMPLEMENTATION_VERSION,
        "applicability": {
            "status": "NOT_APPLICABLE" if not_applicable else "NEEDS_REVIEW",
            "rationale": rationale,
        },
        "materials": [],
        "failures": [],
    }


def init_command(path: Path, *, not_applicable: bool, rationale: str, apply: bool) -> int:
    base, target = _resolve(path)
    if target.exists():
        print(f"Refusing to overwrite existing registry: {target}", file=sys.stderr)
        return 2
    payload = init_payload(not_applicable=not_applicable, rationale=rationale)
    result = validate_registry(base, payload, scope="acquisition")
    if result.errors:
        print(json.dumps({"status": "FAIL", "issues": [item.as_dict() for item in result.errors]}, ensure_ascii=False, indent=2))
        return 2
    if not apply:
        print(json.dumps(_plan(None, payload, "init"), ensure_ascii=False, indent=2))
        return 0
    base.mkdir(parents=True, exist_ok=True)
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-material-init"):
            report = _transaction(base, None, payload, operation="init")
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def _json_arg(value: str, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be a JSON object: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def _next_probe_id(payload: Mapping[str, Any]) -> str:
    values = [
        int(match.group(1))
        for material in payload.get("materials") or []
        if isinstance(material, Mapping)
        for probe in material.get("probes") or []
        if isinstance(probe, Mapping)
        if (match := re.fullmatch(r"PROBE-(\d+)", _text(probe.get("probe_id"))))
    ]
    return f"PROBE-{max(values, default=0) + 1:03d}"


def _probe_sample(sample: Path, adapter: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "format": sample.suffix.casefold().lstrip(".") or "binary",
        "observed_rows": 0,
        "observed_documents": 0,
        "observed_fields": [],
    }
    if adapter == "tabular":
        suffix = sample.suffix.casefold()
        if suffix == ".csv":
            with sample.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            result["observed_rows"] = len(rows)
            result["observed_fields"] = list(rows[0]) if rows else []
        elif suffix == ".json":
            value = json.loads(sample.read_text(encoding="utf-8-sig"))
            rows = value if isinstance(value, list) else [value]
            result["observed_rows"] = len(rows)
            result["observed_fields"] = sorted({str(key) for row in rows if isinstance(row, Mapping) for key in row})
        else:
            raise ValueError("tabular adapter currently parses CSV or JSON; use manual-evidence for a verified external parser receipt")
    elif adapter in {"public-text", "api", "archive"}:
        text = sample.read_text(encoding="utf-8-sig", errors="strict")
        if not text.strip():
            raise ValueError("sample is empty")
        result["observed_documents"] = 1
        if adapter == "api" and sample.suffix.casefold() == ".json":
            value = json.loads(text)
            rows = value if isinstance(value, list) else [value]
            result["observed_rows"] = len(rows)
            result["observed_fields"] = sorted({str(key) for row in rows if isinstance(row, Mapping) for key in row})
    else:
        if sample.stat().st_size <= 0:
            raise ValueError("sample is empty")
        result["observed_documents"] = 1
    return result


def probe_command(
    path: Path,
    *,
    material_id: str,
    adapter: str,
    sample: Path,
    performed_at: str,
    candidate_digest: str,
    question_digest: str,
    failure_code: str | None,
    details: str,
    fields: list[str],
    key_assessment: str,
    query_summary: str,
    pagination_status: str,
    rate_limit_status: str,
    deduplication_status: str,
    time_coverage: str,
    spatial_coverage: str,
    unit_coverage: str,
    apply: bool,
    header_confirmed: bool = False,
) -> int:
    # ``header_confirmed`` is the operator's explicit acknowledgement for tabular
    # samples whose first row is a header; it is accepted here so the controller
    # CLI and the module signature stay aligned.  It does not alter probe truth.
    try:
        base, _target, before = load_registry(path)
        after = deepcopy(before)
        material = next(
            (
                item for item in after.get("materials") or []
                if isinstance(item, dict) and _text(item.get("material_id")).upper() == material_id.upper()
            ),
            None,
        )
        if material is None:
            raise ValueError(f"unknown material: {material_id}")
        safe_sample = _safe_path(base, sample)
        if safe_sample is None:
            raise ValueError("sample path must stay inside the workspace")
        config = _read_json(base / "workflow_config.json")
        policy = config.get("resource_policy") if isinstance(config.get("resource_policy"), Mapping) else {}
        max_sample_bytes = int(policy.get("max_f2_sample_bytes") or 10_485_760)
        max_probe_seconds = int(policy.get("max_f2_probe_seconds") or 120)
        if safe_sample.is_file() and safe_sample.stat().st_size > max_sample_bytes:
            failure_code = "COST_EXCEEDS_POLICY"
            details = details or (
                f"sample size {safe_sample.stat().st_size} exceeds configured F2 limit {max_sample_bytes}"
            )
        implementation = _text(after.get("probe_implementation_version"))
        identity_digest = material_identity_digest(material)
        cache_key = failure_cache_key(candidate_digest, question_digest, identity_digest, implementation)
        cached = next(
            (
                item for item in after.get("failures") or []
                if isinstance(item, Mapping)
                and _text(item.get("cache_key")) == cache_key
                and _text(item.get("status")) == "ACTIVE"
            ),
            None,
        )
        if cached is not None:
            print(json.dumps({"status": "CACHED_FAILURE", "cache_key": cache_key, "failure": cached}, ensure_ascii=False, indent=2))
            return 1
        observed: dict[str, Any]
        probe_status = "PASS"
        errors: list[dict[str, str]] = []
        probe_started = time.monotonic()
        try:
            if failure_code:
                raise RuntimeError(details or failure_code)
            if not safe_sample.is_file():
                raise FileNotFoundError(f"sample does not exist: {sample}")
            observed = _probe_sample(safe_sample, adapter)
            if time.monotonic() - probe_started > max_probe_seconds:
                failure_code = "COST_EXCEEDS_POLICY"
                raise RuntimeError(
                    f"probe exceeded configured F2 time limit {max_probe_seconds} seconds"
                )
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            observed = {"format": sample.suffix.casefold().lstrip(".") or "unknown", "observed_rows": 0, "observed_documents": 0, "observed_fields": []}
            failure_code = failure_code or ("PARSER_FAILED" if safe_sample.is_file() else "NO_ACTUAL_ACCESS")
            probe_status = "BLOCKED" if failure_code in {"AUTHORIZATION_PENDING", "ETHICS_NOT_CLEARED"} else "FAIL"
            errors = [{"code": failure_code, "message": details or str(exc)}]
        evidence_files = []
        if safe_sample.is_file():
            evidence_files.append({
                "path": safe_sample.relative_to(base).as_posix(),
                "sha256": _sha256(safe_sample),
                "role": "probe-sample",
            })
        probe = {
            "probe_id": _next_probe_id(after),
            "performed_at": performed_at,
            "adapter": adapter,
            "status": probe_status,
            "format": observed.get("format") or "unknown",
            "parse_status": "PASS" if probe_status == "PASS" else probe_status,
            "observed_rows": observed.get("observed_rows", 0),
            "observed_documents": observed.get("observed_documents", 0),
            "observed_fields": sorted(set(fields or observed.get("observed_fields") or [])),
            "key_assessment": key_assessment,
            "query_summary": query_summary,
            "pagination_status": pagination_status,
            "rate_limit_status": rate_limit_status,
            "deduplication_status": deduplication_status,
            "time_coverage": _json_arg(time_coverage, "time-coverage"),
            "spatial_coverage": _json_arg(spatial_coverage, "spatial-coverage"),
            "unit_coverage": _json_arg(unit_coverage, "unit-coverage"),
            "evidence_files": evidence_files,
            "errors": errors,
        }
        material.setdefault("probes", []).append(probe)
        access = material.setdefault("access", {})
        access["status"] = "VERIFIED" if probe_status == "PASS" else "BLOCKED" if probe_status == "BLOCKED" else "FAILED"
        if probe_status != "PASS":
            # Cache the post-probe identity.  Access status is part of material
            # identity so a permission/source change invalidates the failure,
            # while an unchanged failed material produces a stable cache hit.
            identity_digest = material_identity_digest(material)
            cache_key = failure_cache_key(candidate_digest, question_digest, identity_digest, implementation)
            failure = {
                "failure_code": failure_code,
                "cache_key": cache_key,
                "candidate_semantic_digest": candidate_digest,
                "question_version_digest": question_digest,
                "material_identity_digest": identity_digest,
                "probe_implementation_version": implementation,
                "observed_at": performed_at,
                "status": "ACTIVE",
                "details": details or errors[0]["message"],
            }
            after.setdefault("failures", []).append(failure)
        validation = validate_registry(base, after, scope="acquisition")
        if validation.errors:
            raise ValueError("; ".join(f"[{item.code}] {item.message}" for item in validation.errors))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not apply:
        report = _plan(before, after, "probe")
        report.update({"status": probe_status, "probe_id": probe["probe_id"], "cache_key": cache_key})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1 if probe_status != "PASS" else 0
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-material-probe"):
            report = _transaction(base, before, after, operation="probe")
    except (OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report.update({"status": probe_status, "probe_id": probe["probe_id"], "cache_key": cache_key})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if probe_status != "PASS" else 0


def rollback_command(path: Path, manifest_path: Path, *, apply: bool) -> int:
    base, target = _resolve(path)
    try:
        resolved_manifest = _safe_path(base, manifest_path)
        if resolved_manifest is None or not resolved_manifest.is_file():
            raise ValueError("rollback manifest must be an existing file inside the workspace")
        manifest = _read_json(resolved_manifest)
        if manifest.get("schema_version") != "avereth-research-material-mutation/v1":
            raise ValueError("unsupported research-material rollback manifest")
        if _text(manifest.get("path")) != REGISTRY_REL.as_posix():
            raise ValueError("rollback manifest targets a different artifact")
        current_sha = _text(manifest.get("after_sha256"))
        if not target.is_file() or _sha256(target) != current_sha:
            raise ValueError("research material registry changed after the mutation; refusing rollback")
        backup_raw = manifest.get("backup")
        backup = _safe_path(base, backup_raw) if backup_raw else None
        before_sha = _text(manifest.get("before_sha256"))
        if backup is not None and (not backup.is_file() or _sha256(backup) != before_sha):
            raise ValueError("rollback backup is missing or changed")
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report = {"schema_version": "avereth-research-material-rollback/v1", "status": "READY", "path": REGISTRY_REL.as_posix()}
    if not apply:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    try:
        with exclusive_lock(base, ".avereth-transition.lock", "another workspace transition is in progress", operation="research-material-rollback"):
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


def validate_command(path: Path, *, scope: str, json_stdout: bool) -> int:
    _base, payload, result = validate_contract(path, scope=scope)
    report = {
        "schema_version": _text((payload or {}).get("schema_version")),
        "status": result.status,
        "scope": scope,
        "issues": [item.as_dict() for item in result.issues],
    }
    if json_stdout:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("# Research Material Registry Check\n")
        print(f"Status: {result.status}\n")
        for issue in result.issues:
            print(f"- [{issue.code}] {issue.message}")
    return 1 if result.errors else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    init_parser = commands.add_parser("init")
    init_parser.add_argument("path", type=Path)
    init_parser.add_argument("--not-applicable", action="store_true")
    init_parser.add_argument("--rationale", default="Material applicability requires explicit review before research.")
    init_parser.add_argument("--apply", action="store_true")
    validate_parser = commands.add_parser("validate")
    validate_parser.add_argument("path", type=Path)
    validate_parser.add_argument("--scope", choices=("acquisition", "research"), default="acquisition")
    validate_parser.add_argument("--json", action="store_true")
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("path", type=Path)
    probe_parser.add_argument("--material", required=True)
    probe_parser.add_argument("--adapter", choices=("local-file", "tabular", "api", "public-text", "archive", "human-subject", "restricted-data", "manual-evidence"), required=True)
    probe_parser.add_argument("--sample", type=Path, required=True)
    probe_parser.add_argument("--performed-at", default=datetime.now(timezone.utc).isoformat())
    probe_parser.add_argument("--candidate-semantic-digest", required=True)
    probe_parser.add_argument("--question-version-digest", required=True)
    probe_parser.add_argument("--failure-code", choices=sorted(FAILURE_CODES))
    probe_parser.add_argument("--details", default="")
    probe_parser.add_argument("--field", action="append", default=[])
    probe_parser.add_argument("--key-assessment", default="")
    probe_parser.add_argument("--query-summary", default="")
    probe_parser.add_argument("--pagination-status", default="")
    probe_parser.add_argument("--rate-limit-status", default="")
    probe_parser.add_argument("--deduplication-status", default="")
    probe_parser.add_argument("--time-coverage", default="{}")
    probe_parser.add_argument("--spatial-coverage", default="{}")
    probe_parser.add_argument("--unit-coverage", default="{}")
    probe_parser.add_argument("--apply", action="store_true")
    rollback_parser = commands.add_parser("rollback")
    rollback_parser.add_argument("path", type=Path)
    rollback_parser.add_argument("--manifest", type=Path, required=True)
    rollback_parser.add_argument("--apply", action="store_true")
    commands.add_parser("schema")
    args = parser.parse_args(argv)
    if args.command == "init":
        return init_command(args.path, not_applicable=args.not_applicable, rationale=args.rationale, apply=args.apply)
    if args.command == "validate":
        return validate_command(args.path, scope=args.scope, json_stdout=args.json)
    if args.command == "probe":
        return probe_command(
            args.path,
            material_id=args.material,
            adapter=args.adapter,
            sample=args.sample,
            performed_at=args.performed_at,
            candidate_digest=args.candidate_semantic_digest,
            question_digest=args.question_version_digest,
            failure_code=args.failure_code,
            details=args.details,
            fields=args.field,
            key_assessment=args.key_assessment,
            query_summary=args.query_summary,
            pagination_status=args.pagination_status,
            rate_limit_status=args.rate_limit_status,
            deduplication_status=args.deduplication_status,
            time_coverage=args.time_coverage,
            spatial_coverage=args.spatial_coverage,
            unit_coverage=args.unit_coverage,
            apply=args.apply,
        )
    if args.command == "rollback":
        return rollback_command(args.path, args.manifest, apply=args.apply)
    if args.command == "schema":
        print(SCHEMA_ASSET.read_text(encoding="utf-8"), end="")
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
