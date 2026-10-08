"""Explicit, reversible migration from legacy workspace contracts to v6."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from ..config import LEGACY_CONFIG_REL, WORKFLOW_CONFIG_REL, validate_workflow_config
from ..build.manuscript import DEFAULT_CANDIDATES
from ..version import VERSION, WORKFLOW_CONFIG_SCHEMA
from ..receipts import (
    LEGACY_AUDIT_MD_REL,
    LEGACY_AUDIT_REL,
    LEGACY_OUTPUT_MD_REL,
    LEGACY_OUTPUT_REL,
    LEGACY_STATUS_MD_REL,
    LEGACY_STATUS_REL,
)
from ..workflow_registry import (
    STAGE_ORDER as STAGES,
    migration_contracts,
    migration_schema_allowlist,
)


MIGRATION_DIR = Path("migration/local_engine_v6")
MIGRATION_REPORT_REL = MIGRATION_DIR / "migration_report.json"
ACQUISITION_HANDOFF_REL = MIGRATION_DIR / "acquisition_handoff.json"
ROLLBACK_RECEIPT_REL = MIGRATION_DIR / "rollback_receipt.json"
BACKUP_SCHEMA = "avereth-migration-backup/v1"
ROLLBACK_SCHEMA = "avereth-migration-rollback/v1"
CONTRACTS = migration_contracts()
SCHEMA_ALLOWED = migration_schema_allowlist()
CANONICAL_CANDIDATES = DEFAULT_CANDIDATES
SECRET_TOKENS = {
    "api_key",
    "apikey",
    "token",
    "secret",
    "password",
    "cookie",
    "cookies",
    "credential",
    "credentials",
    "authorization",
    "bearer",
    "client_secret",
    "secret_key",
    "access_key_id",
    "sessionid",
    "session_cookie",
    "private_key",
}
MIGRATABLE_CONFIG_FIELDS = frozenset({
    "framework_version",
    "schema_version",
    "workflow",
    "task_profile",
    "topic_selection",
    "direction_contract",
    "publication_track",
    "scene",
    "tier",
    "output_language",
    "word_output",
    "pdf_output",
    "citation_mode",
    "word_font_policy",
    "prose_mode",
    "resource_policy",
    "target_name",
    "materials_dir",
    "user_motivation",
    "special_requirements",
    "canonical_manuscript",
    "draft_path",
    "citation_audit_manuscript",
    "citation_requirement",
    "citation_target_count",
    "legacy_citation_target",
    "reviewer_persona",
    "page_evidence_required",
    "max_sections",
    "target_exemplar_acquisition_override",
    "direction_veto",
    "translation_package",
    "translation_source",
    "translation_coverage_source",
    "submission_package",
    "submission_source_dir",
    "submission_contract",
    "submission_required_files",
    "response_package",
    "response_source_dir",
    "response_review_source",
    "response_required_files",
    "migration",
})
ACQUISITION_HANDOFF_FIELDS = frozenset({"official_urls", "reference_paths"})
KNOWN_RETIRED_CONFIG_FIELDS = frozenset({
    "detection_platform",
    "humanize_thresholds",
    "humanize_tier",
    "reference_mode",
    "ui_language",
    "v5_migration",
})
KNOWN_CONFIG_FIELDS = (
    MIGRATABLE_CONFIG_FIELDS
    | ACQUISITION_HANDOFF_FIELDS
    | KNOWN_RETIRED_CONFIG_FIELDS
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _semantic_config(payload: dict[str, Any]) -> dict[str, Any]:
    ignored = {"framework_version", "migration"}
    return {key: value for key, value in payload.items() if key not in ignored}


def _snapshot_digest(outdir: Path, relatives: list[Path]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(relatives, key=lambda value: value.as_posix()):
        path = outdir / relative
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\n")
    return digest.hexdigest()


def _future_schema_issues(outdir: Path) -> list[str]:
    issues: list[str] = []
    for relative, allowed in SCHEMA_ALLOWED.items():
        path = outdir / relative
        if not path.is_file():
            continue
        payload = _json_object(outdir / relative)
        schema = str(payload.get("schema_version") or "")
        if schema not in allowed:
            issues.append(
                f"unknown, missing, or future schema blocks migration: {relative.as_posix()}={schema or '<missing>'}"
            )
    return issues


def _canonical_source_issues(outdir: Path, config: dict[str, Any]) -> list[str]:
    present = [
        relative
        for relative in CANONICAL_CANDIDATES
        if (outdir / relative).is_file() and (outdir / relative).stat().st_size > 0
    ]
    canonical = str(config.get("canonical_manuscript") or "").strip().replace("\\", "/")
    legacy_alias = str(config.get("citation_audit_manuscript") or "").strip().replace("\\", "/")
    if canonical and legacy_alias:
        try:
            canonical_path = (Path(canonical) if Path(canonical).is_absolute() else outdir / canonical).resolve()
            alias_path = (Path(legacy_alias) if Path(legacy_alias).is_absolute() else outdir / legacy_alias).resolve()
        except OSError:
            return ["canonical manuscript aliases cannot be resolved"]
        if canonical_path != alias_path:
            return ["canonical_manuscript conflicts with legacy citation_audit_manuscript"]
    explicit = canonical or legacy_alias
    if explicit:
        selected = Path(explicit)
        candidate = selected if selected.is_absolute() else outdir / selected
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(outdir.resolve())
        except (OSError, ValueError):
            return ["canonical_manuscript must resolve inside the workspace"]
        if relative.suffix.lower() not in {".tex", ".md", ".docx"}:
            return ["canonical_manuscript must be a .tex, .md, or .docx source"]
        if not resolved.is_file() or resolved.stat().st_size <= 0:
            return [f"declared canonical_manuscript is missing or empty: {relative.as_posix()}"]
        return []
    if len(present) > 1:
        return [
            "multiple manuscript candidates exist; declare canonical_manuscript before migration: "
            + ", ".join(path.as_posix() for path in present)
        ]
    return []


def _normalized_key(value: object) -> str:
    raw = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", str(value))
    raw = re.sub(r"[^a-zA-Z0-9]+", "_", raw).strip("_").lower()
    return raw


def _secret_key(value: object) -> bool:
    normalized = _normalized_key(value)
    return any(
        normalized == token
        or normalized.startswith(token + "_")
        or normalized.endswith("_" + token)
        for token in SECRET_TOKENS
    )


def _secret_key_paths(payload: Any, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if _secret_key(key) and value not in (None, "", False, [], {}):
                found.append(path)
            found.extend(_secret_key_paths(value, path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            found.extend(_secret_key_paths(value, f"{prefix}[{index}]"))
    elif isinstance(payload, str) and "://" in payload:
        try:
            parsed = urlsplit(payload)
            query_keys = [key for key, value in parse_qsl(parsed.query, keep_blank_values=True) if value]
            if parsed.username or parsed.password:
                found.append(f"{prefix}.url_userinfo" if prefix else "url_userinfo")
        except ValueError:
            query_keys = []
        for key in query_keys:
            if _secret_key(key):
                found.append(f"{prefix}.query.{key}" if prefix else f"query.{key}")
    return found


def _project_v6_config(outdir: Path, source: dict[str, Any]) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in source.items()
        if key in MIGRATABLE_CONFIG_FIELDS and key != "migration"
    }
    legacy_alias = str(payload.pop("citation_audit_manuscript", "") or "").strip()
    if legacy_alias and not str(payload.get("canonical_manuscript") or "").strip():
        payload["canonical_manuscript"] = legacy_alias
    legacy_target = payload.pop("citation_target_count", None)
    if legacy_target is not None and "legacy_citation_target" not in payload:
        payload["legacy_citation_target"] = {
            "value": legacy_target,
            "classification": "unclassified",
        }
    payload["framework_version"] = VERSION
    payload["schema_version"] = WORKFLOW_CONFIG_SCHEMA
    payload.setdefault(
        "resource_policy",
        {
            "max_f1_metadata_queries": 12,
            "max_f2_sample_bytes": 10485760,
            "max_f2_probe_seconds": 120,
        },
    )
    if payload.get("word_output") not in {"none", "docx"}:
        payload["word_output"] = "docx"
    if payload.get("pdf_output") not in {"none", "pdf"}:
        canonical = str(payload.get("canonical_manuscript") or "").lower()
        payload["pdf_output"] = (
            "pdf"
            if canonical.endswith(".tex") or (outdir / "final_paper" / "main.tex").is_file()
            else "none"
        )
    return payload


def _canonical_digest(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _reference_path_binding(outdir: Path, raw_value: Any) -> dict[str, Any]:
    """Seal a legacy reference path without reading outside the workspace."""

    raw = str(raw_value or "").strip()
    binding: dict[str, Any] = {"path_kind": "invalid", "workspace_path": ""}
    if not raw:
        return binding
    candidate = Path(raw)
    candidate = candidate if candidate.is_absolute() else outdir / candidate
    try:
        resolved = candidate.resolve()
        relative = resolved.relative_to(outdir.resolve()).as_posix()
    except (OSError, ValueError):
        binding["path_kind"] = "outside_workspace"
        return binding
    binding["workspace_path"] = relative
    if resolved.is_file():
        binding.update({
            "path_kind": "file",
            "file_sha256": _sha256(resolved),
            "size": resolved.stat().st_size,
        })
        return binding
    if not resolved.is_dir():
        binding["path_kind"] = "missing"
        return binding

    inventory: list[dict[str, Any]] = []
    for path in sorted(resolved.rglob("*"), key=lambda value: value.as_posix().lower()):
        if not path.is_file():
            continue
        try:
            item_resolved = path.resolve()
            item_relative = item_resolved.relative_to(outdir.resolve()).as_posix()
        except (OSError, ValueError):
            continue
        inventory.append({
            "path": item_relative,
            "sha256": _sha256(item_resolved),
            "size": item_resolved.stat().st_size,
        })
    binding.update({
        "path_kind": "directory",
        "inventory": inventory,
        "inventory_sha256": _canonical_digest(inventory),
    })
    return binding


def _handoff_input_digest(payload: dict[str, Any]) -> str:
    return _canonical_digest({
        "schema_version": payload.get("schema_version"),
        "framework_version": payload.get("framework_version"),
        "source_config_sha256": payload.get("source_config_sha256"),
        "input_fields": payload.get("input_fields"),
        "items": payload.get("items"),
    })


def _acquisition_handoff(
    source: dict[str, Any],
    *,
    source_sha256: str,
    outdir: Path,
) -> dict[str, Any]:
    inputs = {
        key: source[key]
        for key in sorted(ACQUISITION_HANDOFF_FIELDS)
        if source.get(key) not in (None, "", [], {})
    }
    if not inputs:
        return {}
    items: list[dict[str, Any]] = []
    for field, raw in inputs.items():
        values = raw if isinstance(raw, list) else [raw]
        for index, value in enumerate(values, start=1):
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            item = {
                "input_id": f"{field}:{index}",
                "field": field,
                "value": value,
                "value_sha256": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
            }
            if field == "reference_paths":
                item.update(_reference_path_binding(outdir, value))
            items.append(item)
    payload = {
        "schema_version": "avereth-acquisition-migration-handoff/v1",
        "framework_version": VERSION,
        "status": "needs_review",
        "source_config_sha256": source_sha256,
        "input_fields": inputs,
        "items": items,
        "resolved_by": "",
        "dispositions": [],
        "next_action": (
            "register every lawful local path and public URL in literature_registry.json; "
            "directory inputs require an expanded disposition with one registered/discarded "
            "file disposition per sealed inventory entry; then set status=resolved and resolved_by"
        ),
    }
    payload["input_digest"] = _handoff_input_digest(payload)
    return payload


def _contains_exact_value(payload: Any, expected: Any) -> bool:
    if payload == expected:
        return True
    if isinstance(payload, dict):
        return any(_contains_exact_value(value, expected) for value in payload.values())
    if isinstance(payload, list):
        return any(_contains_exact_value(value, expected) for value in payload)
    return False


def acquisition_handoff_issues(outdir: Path) -> list[str]:
    """Fail closed until migrated evidence inputs have an explicit disposition."""

    path = outdir / ACQUISITION_HANDOFF_REL
    current = _json_object(outdir / WORKFLOW_CONFIG_REL)
    migration_metadata = (
        current.get("migration")
        if isinstance(current.get("migration"), dict)
        else {}
    )
    report = _json_object(outdir / MIGRATION_REPORT_REL)
    legacy = _json_object(outdir / LEGACY_CONFIG_REL)
    required = bool(
        migration_metadata.get("acquisition_handoff_required")
        or migration_metadata.get("acquisition_handoff_fields")
        or report.get("acquisition_handoff_keys")
        or any(legacy.get(key) not in (None, "", [], {}) for key in ACQUISITION_HANDOFF_FIELDS)
    )
    if not path.is_file():
        return ([
            "ACQUISITION.MIGRATION_HANDOFF_MISSING: workflow migration declared evidence inputs, "
            "but the sealed acquisition handoff is missing"
        ] if required else [])
    payload = _json_object(path)
    issues: list[str] = []
    if payload.get("schema_version") != "avereth-acquisition-migration-handoff/v1":
        issues.append("ACQUISITION.MIGRATION_HANDOFF_SCHEMA: unsupported acquisition handoff schema")
        return issues
    if payload.get("framework_version") != VERSION:
        issues.append("ACQUISITION.MIGRATION_HANDOFF_VERSION: acquisition handoff engine version changed")
    expected_path = str(migration_metadata.get("acquisition_handoff_path") or "")
    expected_fields = sorted(str(value) for value in migration_metadata.get("acquisition_handoff_fields") or [])
    actual_fields = sorted(str(value) for value in (payload.get("input_fields") or {}))
    expected_digest = str(migration_metadata.get("acquisition_handoff_input_digest") or "")
    actual_digest = _handoff_input_digest(payload)
    if expected_path and expected_path != ACQUISITION_HANDOFF_REL.as_posix():
        issues.append("ACQUISITION.MIGRATION_HANDOFF_PATH: workflow config declares an unsafe handoff path")
    if expected_fields and expected_fields != actual_fields:
        issues.append("ACQUISITION.MIGRATION_HANDOFF_FIELDS: handoff fields differ from workflow migration metadata")
    if payload.get("input_digest") != actual_digest or (expected_digest and expected_digest != actual_digest):
        issues.append("ACQUISITION.MIGRATION_HANDOFF_DIGEST: sealed handoff inputs or inventory changed")
    if issues:
        return issues
    if payload.get("status") != "resolved":
        issues.append(
            "ACQUISITION.MIGRATION_HANDOFF_PENDING: migrated official URLs/reference paths "
            "must be registered or explicitly discarded before acquisition can pass"
        )
        return issues
    if not str(payload.get("resolved_by") or "").strip():
        issues.append("ACQUISITION.MIGRATION_HANDOFF_IDENTITY: resolved_by is required")

    source_sha = str(payload.get("source_config_sha256") or "")
    manifest_raw = str(report.get("backup_manifest") or "")
    source_payload: dict[str, Any] = {}
    try:
        manifest_path = _contained(outdir, manifest_raw)
        manifest = _json_object(manifest_path)
        source_entries = [
            item
            for item in manifest.get("files") or []
            if isinstance(item, dict)
            and str(item.get("path") or "") in {
                WORKFLOW_CONFIG_REL.as_posix(), LEGACY_CONFIG_REL.as_posix()
            }
            and item.get("sha256") == source_sha
        ]
        if source_entries:
            backup_path = _contained(outdir, str(source_entries[0].get("backup") or ""))
            if backup_path.is_file() and _sha256(backup_path) == source_sha:
                source_payload = _json_object(backup_path)
    except (OSError, ValueError):
        source_payload = {}
    if not source_payload:
        issues.append(
            "ACQUISITION.MIGRATION_HANDOFF_SOURCE: original migration backup cannot prove the handoff inputs"
        )
        return issues
    inputs = payload.get("input_fields") if isinstance(payload.get("input_fields"), dict) else {}
    expected_inputs = {
        key: source_payload[key]
        for key in sorted(ACQUISITION_HANDOFF_FIELDS)
        if source_payload.get(key) not in (None, "", [], {})
    }
    if inputs != expected_inputs:
        issues.append("ACQUISITION.MIGRATION_HANDOFF_INPUTS: handoff inputs differ from the sealed source config")
        return issues
    expected_items = payload.get("items") if isinstance(payload.get("items"), list) else []
    expected_by_id = {
        str(item.get("input_id")): item
        for item in expected_items
        if isinstance(item, dict)
    }
    dispositions = payload.get("dispositions")
    if not isinstance(dispositions, list):
        dispositions = []
    disposition_by_id = {
        str(item.get("input_id")): item
        for item in dispositions
        if isinstance(item, dict) and item.get("input_id")
    }
    if set(disposition_by_id) != set(expected_by_id) or len(dispositions) != len(expected_by_id):
        issues.append(
            "ACQUISITION.MIGRATION_HANDOFF_DISPOSITIONS: every migrated input requires exactly one disposition"
        )
        return issues

    registry = _json_object(outdir / "reference_materials" / "literature_registry.json")
    sources = {
        str(item.get("source_id")): item
        for item in registry.get("sources") or []
        if isinstance(item, dict) and item.get("source_id")
    }
    queries = {
        str(item.get("query_id")): item
        for item in registry.get("queries") or []
        if isinstance(item, dict) and item.get("query_id")
    }
    for input_id, disposition in disposition_by_id.items():
        state = str(disposition.get("status") or "").strip().lower()
        expected_item = expected_by_id[input_id]
        path_kind = str(expected_item.get("path_kind") or "")
        if path_kind == "directory" and expected_item.get("inventory"):
            if state != "expanded":
                issues.append(
                    f"ACQUISITION.MIGRATION_HANDOFF_STATUS: {input_id} is a non-empty directory "
                    "and requires status=expanded with per-file dispositions"
                )
                continue
            inventory = {
                str(item.get("path")): item
                for item in expected_item.get("inventory") or []
                if isinstance(item, dict) and item.get("path")
            }
            file_dispositions = disposition.get("file_dispositions")
            if not isinstance(file_dispositions, list):
                file_dispositions = []
            by_path = {
                str(item.get("path")): item
                for item in file_dispositions
                if isinstance(item, dict) and item.get("path")
            }
            if set(by_path) != set(inventory) or len(file_dispositions) != len(inventory):
                issues.append(
                    f"ACQUISITION.MIGRATION_HANDOFF_DIRECTORY: {input_id} requires exactly one "
                    "disposition for every sealed inventory file"
                )
                continue
            for relative, file_disposition in by_path.items():
                file_state = str(file_disposition.get("status") or "").strip().lower()
                if file_state == "discarded":
                    if not str(file_disposition.get("reason") or "").strip():
                        issues.append(
                            f"ACQUISITION.MIGRATION_HANDOFF_REASON: {input_id}:{relative} discard requires a reason"
                        )
                    continue
                if file_state != "registered":
                    issues.append(
                        f"ACQUISITION.MIGRATION_HANDOFF_STATUS: {input_id}:{relative} must be registered or discarded"
                    )
                    continue
                source_ids = [str(value) for value in file_disposition.get("source_ids") or [] if str(value)]
                records = [sources[value] for value in source_ids if value in sources]
                expected_sha = str(inventory[relative].get("sha256") or "")
                if len(records) != len(source_ids) or not records or not any(
                    str(record.get("local_file") or "").replace("\\", "/") == relative
                    and str(record.get("sha256") or "") == expected_sha
                    for record in records
                ):
                    issues.append(
                        f"ACQUISITION.MIGRATION_HANDOFF_BINDING: {input_id}:{relative} is not bound "
                        "to a registry source with the sealed path and SHA256"
                    )
            continue
        if state == "discarded":
            if path_kind == "directory" and expected_item.get("inventory"):
                issues.append(
                    f"ACQUISITION.MIGRATION_HANDOFF_STATUS: {input_id} non-empty directory cannot be discarded as one item"
                )
                continue
            if not str(disposition.get("reason") or "").strip():
                issues.append(f"ACQUISITION.MIGRATION_HANDOFF_REASON: {input_id} discard requires a reason")
            continue
        if state != "registered":
            issues.append(f"ACQUISITION.MIGRATION_HANDOFF_STATUS: {input_id} status must be registered or discarded")
            continue
        source_ids = [str(value) for value in disposition.get("source_ids") or [] if str(value)]
        query_ids = [str(value) for value in disposition.get("query_ids") or [] if str(value)]
        records = [sources[value] for value in source_ids if value in sources]
        records.extend(queries[value] for value in query_ids if value in queries)
        if len(records) != len(source_ids) + len(query_ids) or not records:
            issues.append(f"ACQUISITION.MIGRATION_HANDOFF_REGISTRY: {input_id} references missing registry IDs")
            continue
        expected_value = expected_item.get("value")
        if path_kind == "file":
            workspace_path = str(expected_item.get("workspace_path") or "")
            file_sha = str(expected_item.get("file_sha256") or "")
            bound = any(
                str(record.get("local_file") or "").replace("\\", "/") == workspace_path
                and str(record.get("sha256") or "") == file_sha
                for record in records
            )
        else:
            bound = any(_contains_exact_value(record, expected_value) for record in records)
        if not bound:
            issues.append(
                f"ACQUISITION.MIGRATION_HANDOFF_BINDING: {input_id} value is not bound to its registry records"
            )
    return issues


def _semver(value: object) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:[-+][0-9A-Za-z.-]+)?", str(value or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def _framework_and_config_schema_issues(
    *,
    current_path: Path,
    current: dict[str, Any],
    legacy_path: Path,
    legacy: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    target = _semver(VERSION)
    for label, path, payload, allow_missing in (
        (WORKFLOW_CONFIG_REL.as_posix(), current_path, current, False),
        (LEGACY_CONFIG_REL.as_posix(), legacy_path, legacy, True),
    ):
        if not path.is_file() or not payload:
            continue
        raw_version = str(payload.get("framework_version") or "").strip()
        parsed = _semver(raw_version)
        if not raw_version and allow_missing:
            pass
        elif parsed is None:
            issues.append(f"invalid framework version blocks migration: {label}={raw_version or '<missing>'}")
        elif target is not None and parsed > target:
            issues.append(f"future framework version blocks migration: {label}={raw_version}")
        schema = str(payload.get("schema_version") or "").strip()
        if label == WORKFLOW_CONFIG_REL.as_posix():
            if schema != WORKFLOW_CONFIG_SCHEMA:
                issues.append(
                    f"unknown or missing workflow config schema blocks migration: {label}={schema or '<missing>'}"
                )
        elif schema and schema != WORKFLOW_CONFIG_SCHEMA:
            issues.append(f"unknown workflow config schema blocks migration: {label}={schema}")
    return issues


def _earliest_reopen(outdir: Path, config: dict[str, Any]) -> str:
    candidates = ["audit"]
    schemas = {relative: str(_json_object(outdir / relative).get("schema_version") or "") for relative in SCHEMA_ALLOWED}
    profile = str(config.get("task_profile") or "full_paper").strip().lower().replace("-", "_")
    acquisition_schema = schemas[Path("reference_materials/literature_registry.json")]
    integration_enabled = any(
        (outdir / relative).is_file()
        for relative in (
            Path("reference_materials/integrations/exa_runs/manifest.json"),
            Path("reference_materials/integrations/zotero_snapshot.json"),
        )
    )
    if acquisition_schema not in {"cnki-acquisition/v2", "cnki-acquisition/v3"}:
        candidates.append("acquisition")
    elif integration_enabled and acquisition_schema != "cnki-acquisition/v3":
        candidates.append("acquisition")
    if schemas.get(Path("reference_materials/research_material_registry.json")) != "avereth-research-material-registry/v1":
        candidates.append("acquisition")
    if profile != "manuscript_audit" and schemas[Path("literature_analysis.json")] != "cnki-literature-analysis/v2":
        candidates.append("research")
    if profile != "manuscript_audit" and schemas.get(Path("research_decision.json")) != "cnki-research-decision/v1":
        # v6.0 had confirmed_motivation.md but no canonical candidate/collision
        # decision.  Preserve that commitment as history and reopen research;
        # never synthesize a replacement question during the v6.1 migration.
        candidates.append("research")
    if profile != "manuscript_audit" and schemas.get(Path("research_feasibility.json")) != "avereth-research-feasibility/v1":
        candidates.append("research")
    if profile in {"full_paper", "research_design", "manuscript_revision"} and schemas[Path("research_design.json")] != "cnki-research-design/v4":
        candidates.append("design")
    if profile in {"full_paper", "manuscript_revision"} and schemas[Path("method_execution.json")] != "cnki-method-execution/v3":
        candidates.append("execution")
    if profile in {"full_paper", "manuscript_revision", "manuscript_audit"} and not any(
        (outdir / relative).is_file() and (outdir / relative).stat().st_size > 0
        for relative in CANONICAL_CANDIDATES
    ) and not str(config.get("canonical_manuscript") or "").strip():
        candidates.append("build")
    if not str(config.get("publication_track") or "").strip():
        candidates.append("intake")
    if any(config.get(key) not in (None, "", [], {}) for key in ACQUISITION_HANDOFF_FIELDS):
        candidates.append("acquisition")
    return min(candidates, key=STAGES.index)


def plan(outdir: Path) -> dict[str, Any]:
    legacy_path = outdir / LEGACY_CONFIG_REL
    current_path = outdir / WORKFLOW_CONFIG_REL
    legacy_payload = _json_object(legacy_path)
    current_payload = _json_object(current_path)
    legacy_files = [relative for relative in CONTRACTS if (outdir / relative).is_file()]
    snapshot_digest = _snapshot_digest(outdir, legacy_files) if legacy_files else hashlib.sha256(b"").hexdigest()
    issues: list[str] = []

    if not legacy_path.is_file() and not current_path.is_file():
        issues.append("no legacy or v6 workflow configuration exists to migrate")
    if legacy_path.is_file() and not legacy_payload:
        issues.append("legacy config is invalid or is not a JSON object")
    if current_path.is_file() and not current_payload:
        issues.append("workflow_config.json is invalid or is not a JSON object")
    current_migration = (
        current_payload.get("migration")
        if isinstance(current_payload.get("migration"), dict)
        else {}
    )
    retired_digest = str(current_migration.get("legacy_config_sha256") or "")
    legacy_is_retired = bool(
        retired_digest
        and legacy_path.is_file()
        and _sha256(legacy_path) == retired_digest
    )
    if (
        legacy_payload
        and current_payload
        and not legacy_is_retired
        and _semantic_config(legacy_payload) != _semantic_config(current_payload)
    ):
        issues.append("workflow_config.json conflicts with paper_spine_config.json")
    if retired_digest and legacy_path.is_file() and not legacy_is_retired:
        issues.append("retired paper_spine_config.json changed after migration")

    active_config = current_payload or legacy_payload
    unknown_config_keys = sorted(
        str(key)
        for key in active_config
        if key not in KNOWN_CONFIG_FIELDS
    )
    if unknown_config_keys:
        issues.append(
            "unsupported workflow config keys require explicit classification before migration: "
            + ", ".join(unknown_config_keys)
        )
    issues.extend(
        _framework_and_config_schema_issues(
            current_path=current_path,
            current=current_payload,
            legacy_path=legacy_path,
            legacy=legacy_payload,
        )
    )
    issues.extend(_future_schema_issues(outdir))
    issues.extend(_canonical_source_issues(outdir, active_config))
    secret_documents: list[tuple[str, dict[str, Any]]] = [
        (WORKFLOW_CONFIG_REL.as_posix(), current_payload),
        (LEGACY_CONFIG_REL.as_posix(), legacy_payload),
    ]
    for relative in CONTRACTS:
        if relative.suffix.lower() != ".json" or relative in {WORKFLOW_CONFIG_REL, LEGACY_CONFIG_REL}:
            continue
        payload = _json_object(outdir / relative)
        if payload:
            secret_documents.append((relative.as_posix(), payload))
    secret_paths = sorted(
        {
            f"{label}.{path}"
            for label, payload in secret_documents
            if payload
            for path in (
                candidate
                for candidate in _secret_key_paths(payload)
                if not (
                    label == "revision_contract.json"
                    and candidate == "authorization"
                    and isinstance(payload.get("authorization"), dict)
                )
            )
        }
    )
    if secret_paths:
        issues.append(
            "secret-like config keys must be removed and rotated before migration: "
            + ", ".join(secret_paths)
        )
    projected = _project_v6_config(outdir, active_config) if active_config else {}
    if projected:
        issues.extend(
            f"projected v6 config is incomplete: {issue}"
            for issue in validate_workflow_config(projected)
        )

    already_current = bool(
        current_payload
        and current_payload.get("framework_version") == VERSION
        and current_payload.get("schema_version") == WORKFLOW_CONFIG_SCHEMA
        and not validate_workflow_config(current_payload)
        and _json_object(outdir / "reference_materials" / "research_material_registry.json").get("schema_version")
        == "avereth-research-material-registry/v1"
        and _json_object(outdir / "research_feasibility.json").get("schema_version")
        == "avereth-research-feasibility/v1"
        and not issues
    )
    backups = [
        {"path": relative.as_posix(), "sha256": _sha256(outdir / relative)}
        for relative in legacy_files
    ]
    backup_root = MIGRATION_DIR / "backups" / snapshot_digest[:12]
    earliest = _earliest_reopen(outdir, active_config) if active_config else "intake"
    invalidated = list(STAGES[STAGES.index(earliest) :])
    config_operation = "replace" if current_path.is_file() else "create"
    retired_keys = sorted(key for key in active_config if key in KNOWN_RETIRED_CONFIG_FIELDS)
    handoff_keys = sorted(
        key
        for key in ACQUISITION_HANDOFF_FIELDS
        if active_config.get(key) not in (None, "", [], {})
    )
    writes = [WORKFLOW_CONFIG_REL.as_posix(), MIGRATION_REPORT_REL.as_posix()]
    for relative in (
        Path("reference_materials/research_material_registry.json"),
        Path("research_feasibility.json"),
    ):
        if not (outdir / relative).is_file():
            writes.append(relative.as_posix())
    if handoff_keys:
        writes.append(ACQUISITION_HANDOFF_REL.as_posix())
    return {
        "schema_version": "avereth-workspace-migration/v1",
        "source": "paperspine",
        "target_framework_version": VERSION,
        "status": "blocked" if issues else "already-current" if already_current else "planned",
        "issues": issues,
        "snapshot_digest": snapshot_digest,
        "backups": backups,
        "backup_root": backup_root.as_posix(),
        "config_operation": config_operation,
        "writes": writes,
        "retired_config_keys": retired_keys,
        "acquisition_handoff_keys": handoff_keys,
        "invalidated_stages": invalidated,
        "earliest_reopen_stage": earliest,
        "legacy_receipt_disposition": "legacy_valid_v5_history_only",
        "preserved": ["manuscripts", "PDF and DOCX files", "source files", "review outputs"],
        "rollback": (
            (
                "restore workflow_config.json and all other files listed in backup_manifest.json from "
                if config_operation == "replace"
                else "restore files listed in backup_manifest.json and remove the created workflow_config.json from "
            )
            + backup_root.as_posix()
        ),
    }


def _contained(root: Path, raw: str | Path) -> Path:
    candidate = Path(raw)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"migration path escapes workspace: {raw}") from exc
    return resolved


def _rollback_payload(
    outdir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
    *,
    expected_post_sha256: str = "",
) -> dict[str, Any]:
    backup_manifest_relative = (
        manifest_path.resolve().relative_to(outdir.resolve()).as_posix()
    )
    issues: list[str] = []
    if manifest.get("schema_version") != BACKUP_SCHEMA:
        issues.append("unsupported backup manifest schema")
    snapshot = str(manifest.get("snapshot_digest") or "")
    if not re.fullmatch(r"[0-9a-f]{64}", snapshot):
        issues.append("backup manifest snapshot digest is invalid")
    files = manifest.get("files")
    if not isinstance(files, list):
        files = []
        issues.append("backup manifest file list is invalid")
    verified: dict[str, Path] = {}
    for item in files:
        if not isinstance(item, dict):
            issues.append("backup manifest contains an invalid entry")
            continue
        relative = str(item.get("path") or "")
        backup_raw = str(item.get("backup") or "")
        try:
            destination = _contained(outdir, relative)
            backup = _contained(outdir, backup_raw)
            backup.relative_to(manifest_path.parent.resolve())
        except (OSError, ValueError):
            issues.append(f"backup entry path is unsafe: {relative or '<empty>'}")
            continue
        if not backup.is_file() or _sha256(backup) != item.get("sha256"):
            issues.append(f"backup digest verification failed: {relative}")
            continue
        verified[relative] = backup
        if destination == outdir.resolve():
            issues.append(f"backup destination is unsafe: {relative}")
    operation = str(manifest.get("config_operation") or "")
    post_sha = str(manifest.get("post_config_sha256") or expected_post_sha256 or "")
    current = outdir / WORKFLOW_CONFIG_REL
    if operation not in {"create", "replace"}:
        issues.append("backup manifest config_operation is invalid")
    if not post_sha or not current.is_file() or _sha256(current) != post_sha:
        issues.append("workflow_config.json changed after migration; refusing destructive rollback")
    if operation == "replace" and WORKFLOW_CONFIG_REL.as_posix() not in verified:
        issues.append("replacement rollback has no verified workflow_config.json backup")
    handoff_raw = str(manifest.get("acquisition_handoff_path") or "")
    handoff_sha = str(manifest.get("acquisition_handoff_sha256") or "")
    handoff_path: Path | None = None
    if handoff_raw or handoff_sha:
        try:
            handoff_path = _contained(outdir, handoff_raw)
        except ValueError:
            issues.append("acquisition handoff rollback path is unsafe")
        if (
            handoff_path is None
            or handoff_path != (outdir / ACQUISITION_HANDOFF_REL).resolve()
            or not handoff_path.is_file()
            or not handoff_sha
            or _sha256(handoff_path) != handoff_sha
        ):
            issues.append("acquisition handoff changed after migration; refusing destructive rollback")
    created_files = manifest.get("created_files")
    if not isinstance(created_files, list):
        created_files = []
    verified_created: list[Path] = []
    for item in created_files:
        if not isinstance(item, dict):
            issues.append("created-file rollback entry is invalid")
            continue
        relative = str(item.get("path") or "")
        try:
            created = _contained(outdir, relative)
        except ValueError:
            issues.append(f"created-file rollback path is unsafe: {relative or '<empty>'}")
            continue
        if not created.is_file() or _sha256(created) != str(item.get("sha256") or ""):
            issues.append(f"created migration skeleton changed after migration: {relative}")
            continue
        verified_created.append(created)
    if issues:
        return {
            "schema_version": ROLLBACK_SCHEMA,
            "status": "blocked",
            "issues": issues,
            "backup_manifest": backup_manifest_relative,
        }

    if operation == "create":
        current.unlink()
    else:
        backup = verified[WORKFLOW_CONFIG_REL.as_posix()]
        temporary = current.with_suffix(current.suffix + ".rollback.tmp")
        shutil.copy2(backup, temporary)
        temporary.replace(current)
    if handoff_path is not None:
        handoff_path.unlink()
    for created in verified_created:
        created.unlink()
    receipt = {
        "schema_version": ROLLBACK_SCHEMA,
        "framework_version": VERSION,
        "status": "rolled_back",
        "operation": operation,
        "rolled_back_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_digest": snapshot,
        "backup_manifest": backup_manifest_relative,
        "backup_manifest_sha256": _sha256(manifest_path),
    }
    _atomic_json(outdir / ROLLBACK_RECEIPT_REL, receipt)
    return receipt


def rollback(outdir: Path, manifest_path: Path) -> tuple[dict[str, Any], int]:
    try:
        resolved = _contained(outdir, manifest_path)
    except ValueError as exc:
        return {"schema_version": ROLLBACK_SCHEMA, "status": "blocked", "issues": [str(exc)]}, 2
    manifest = _json_object(resolved)
    report = _rollback_payload(outdir, resolved, manifest)
    return report, 0 if report.get("status") == "rolled_back" else 2


def apply(outdir: Path) -> tuple[dict[str, Any], int]:
    migration = plan(outdir)
    if migration["status"] == "blocked":
        return migration, 2
    if migration["status"] == "already-current":
        return migration, 0

    backup_root = outdir / Path(str(migration["backup_root"]))
    backup_root.mkdir(parents=True, exist_ok=True)
    for item in migration["backups"]:
        relative = Path(str(item["path"]))
        source = outdir / relative
        backup = backup_root / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            shutil.copy2(source, backup)
        if _sha256(backup) != item["sha256"]:
            migration["status"] = "blocked"
            migration["issues"] = [f"backup verification failed: {relative.as_posix()}"]
            return migration, 2
        item["backup"] = backup.relative_to(outdir).as_posix()
    manifest_path = backup_root / "backup_manifest.json"
    manifest: dict[str, Any] = {
        "schema_version": BACKUP_SCHEMA,
        "snapshot_digest": migration["snapshot_digest"],
        "config_operation": migration["config_operation"],
        "files": migration["backups"],
    }
    _atomic_json(manifest_path, manifest)

    legacy_payload = _json_object(outdir / LEGACY_CONFIG_REL)
    current_payload = _json_object(outdir / WORKFLOW_CONFIG_REL)
    current_path = outdir / WORKFLOW_CONFIG_REL
    source_payload = current_payload or legacy_payload
    post_sha = ""
    created_handoff = False
    created_skeletons: list[Path] = []
    try:
        if not source_payload:
            raise RuntimeError("no source workflow configuration is available")
        payload = _project_v6_config(outdir, source_payload)
        source_config_path = current_path if current_payload else outdir / LEGACY_CONFIG_REL
        source_config_sha256 = _sha256(source_config_path)
        handoff = _acquisition_handoff(
            source_payload,
            source_sha256=source_config_sha256,
            outdir=outdir,
        )
        migration_metadata = {
            "from": "legacy-workspace",
            "migrated_at": datetime.now(timezone.utc).isoformat(),
            "snapshot_digest": migration["snapshot_digest"],
            "source_config_sha256": source_config_sha256,
        }
        if handoff:
            migration_metadata.update({
                "acquisition_handoff_required": True,
                "acquisition_handoff_path": ACQUISITION_HANDOFF_REL.as_posix(),
                "acquisition_handoff_fields": sorted(handoff["input_fields"]),
                "acquisition_handoff_input_digest": handoff["input_digest"],
            })
        if (outdir / LEGACY_CONFIG_REL).is_file():
            migration_metadata["legacy_config_sha256"] = _sha256(outdir / LEGACY_CONFIG_REL)
        payload["migration"] = migration_metadata
        _atomic_json(current_path, payload)
        post_sha = _sha256(current_path)
        manifest["post_config_sha256"] = post_sha
        _atomic_json(manifest_path, manifest)

        verified = _json_object(current_path)
        verified_issues = validate_workflow_config(verified)
        if not isinstance(verified.get("migration"), dict) or verified_issues:
            raise RuntimeError(
                "migration did not produce a valid v7 workflow configuration"
                + (": " + "; ".join(verified_issues) if verified_issues else "")
            )

        if handoff:
            handoff_path = outdir / ACQUISITION_HANDOFF_REL
            if handoff_path.exists():
                raise RuntimeError(
                    "acquisition migration handoff already exists; reconcile it before applying migration"
                )
            _atomic_json(handoff_path, handoff)
            created_handoff = True
            manifest["acquisition_handoff_path"] = ACQUISITION_HANDOFF_REL.as_posix()
            manifest["acquisition_handoff_sha256"] = _sha256(handoff_path)
            _atomic_json(manifest_path, manifest)

        material_path = outdir / "reference_materials" / "research_material_registry.json"
        if not material_path.exists():
            _atomic_json(
                material_path,
                {
                    "schema_version": "avereth-research-material-registry/v1",
                    "registry_id": "MATREG-001",
                    "probe_implementation_version": "research-material-probe/v1",
                    "applicability": {
                        "status": "NEEDS_REVIEW",
                        "rationale": "Migrated workspace requires an explicit material-applicability review; no PASS was inferred.",
                    },
                    "materials": [],
                    "failures": [],
                },
            )
            created_skeletons.append(material_path)
        feasibility_path = outdir / "research_feasibility.json"
        if not feasibility_path.exists():
            _atomic_json(
                feasibility_path,
                {
                    "schema_version": "avereth-research-feasibility/v1",
                    "feasibility_id": "FEAS-001",
                    "status": "NEEDS_REVIEW",
                    "selected_candidate_id": None,
                    "question_version_id": None,
                    "candidate_assessments": [],
                    "selected_assessment_digest": None,
                    "material_basis_digest": None,
                    "basis_digest": None,
                    "invalidation_archive": [],
                },
            )
            created_skeletons.append(feasibility_path)
        manifest["created_files"] = [
            {
                "path": path.relative_to(outdir).as_posix(),
                "sha256": _sha256(path),
            }
            for path in created_skeletons
        ]
        _atomic_json(manifest_path, manifest)

        migration["status"] = "applied"
        migration["applied_at"] = datetime.now(timezone.utc).isoformat()
        migration["backup_manifest"] = manifest_path.relative_to(outdir).as_posix()
        migration["post_config_sha256"] = post_sha
        _atomic_json(outdir / MIGRATION_REPORT_REL, migration)
        return migration, 0
    except (OSError, RuntimeError, ValueError) as exc:
        rollback_report = _rollback_payload(
            outdir,
            manifest_path,
            manifest,
            expected_post_sha256=post_sha,
        ) if post_sha and current_path.is_file() else {"status": "not-required"}
        migration["status"] = "blocked"
        migration["issues"] = [str(exc)]
        migration["automatic_rollback"] = rollback_report
        if created_handoff:
            handoff_path = outdir / ACQUISITION_HANDOFF_REL
            if handoff_path.is_file():
                handoff_path.unlink()
        for skeleton in created_skeletons:
            if skeleton.is_file():
                skeleton.unlink()
        return migration, 2
