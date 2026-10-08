#!/usr/bin/env python3
"""Controlled manuscript-revision contract and semantic route planner."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

from avereth_core.config import read_config, validate_workflow_config, write_config
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA


LEGACY_SCHEMA_VERSION = "cnki-manuscript-revision/v1"
SCHEMA_VERSION = "cnki-manuscript-revision/v2"
CONTRACT_REL = Path("revision_contract.json")
IMPACT_REL = Path("revision_impact.json")
CHANGE_CLASS_STAGE = {
    "surface": "build",
    "argument": "build",
    "evidence": "research",
    "design": "design",
    "execution": "execution",
}
STAGE_RANK = {"research": 0, "design": 1, "execution": 2, "build": 3}
ASSURANCE_LEVELS = {"full", "reconstructed", "legacy_limited"}
BASELINE_KINDS = {"workspace", "standalone"}
BASELINE_DIR = Path("revision_baseline")
REVISION_WORKTREE_DIR = Path("revision_worktree")
BATCH_ID_RE = re.compile(r"^RB-[0-9]{3}$")
FINDING_KEY_RE = re.compile(r"^RFK-[A-F0-9]{24}$")
REVIEWER_ORDER = ("methods", "contribution", "clarity")
AUTHORITY_PATHS = (
    "research_design.json",
    "method_execution.json",
    "confirmed_motivation.md",
    "confirmed_contribution.md",
    "claim_register.md",
    "evidence_bank.md",
    "section_blueprints.md",
)
AUTHORITY_ALLOWED_CHANGE_CLASSES = {
    "research_design.json": frozenset({"design"}),
    "method_execution.json": frozenset({"execution"}),
    "confirmed_motivation.md": frozenset({"evidence"}),
    "confirmed_contribution.md": frozenset({"argument", "evidence", "execution"}),
    "claim_register.md": frozenset({"argument", "evidence", "design", "execution"}),
    "evidence_bank.md": frozenset({"evidence", "design", "execution"}),
    "section_blueprints.md": frozenset(CHANGE_CLASS_STAGE),
}


def canonical(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def route_for_change_classes(change_classes: Iterable[str]) -> str:
    classes = [canonical(item) for item in change_classes]
    if not classes:
        raise ValueError("at least one revision change class is required")
    unknown = sorted(set(classes) - set(CHANGE_CLASS_STAGE))
    if unknown:
        raise ValueError("unsupported revision change class: " + ", ".join(unknown))
    stages = [CHANGE_CLASS_STAGE[item] for item in classes]
    return min(stages, key=lambda item: STAGE_RANK[item])


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _derived_finding_key(change: dict[str, Any]) -> str:
    """Create a stable contract-local key when no review registry key exists."""
    payload = {
        "change_id": str(change.get("change_id") or ""),
        "change_class": canonical(change.get("change_class")),
        "summary": _normalize_unit_text(str(change.get("summary") or "")),
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return "RFK-" + digest[:24].upper()


def _workspace_path(base: Path, relative: str) -> Path:
    candidate = (base / relative).resolve()
    candidate.relative_to(base.resolve())
    return candidate


def _manuscript_text(path: Path) -> str:
    """Return deterministic review text for Markdown/TeX/Word manuscripts."""
    if path.suffix.lower() != ".docx":
        return path.read_text(encoding="utf-8-sig")
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if not paragraph.tag.endswith("}p"):
            continue
        text = "".join(
            node.text or "" for node in paragraph.iter() if node.tag.endswith("}t")
        ).strip()
        if text:
            paragraphs.append(text)
    return "\n\n".join(paragraphs)


def _normalize_unit_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def manuscript_units(path: Path) -> list[dict[str, Any]]:
    """Split a manuscript into stable content units.

    The unit identity is content-derived, so moving an unchanged paragraph does
    not create a new identity. Duplicate paragraphs receive a deterministic
    occurrence suffix and remain independently addressable.
    """
    text = _manuscript_text(path)
    blocks = [item for item in re.split(r"\n\s*\n+", text) if _normalize_unit_text(item)]
    seen: dict[str, int] = {}
    units: list[dict[str, Any]] = []
    current_section = "document"
    for index, raw in enumerate(blocks, start=1):
        normalized = _normalize_unit_text(raw)
        heading = re.match(r"^(?:#{1,6}\s+|\\(?:sub)*section\*?\{)(.+?)(?:\}|$)", normalized)
        if heading:
            current_section = _normalize_unit_text(heading.group(1)).lower()
        base_key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
        seen[base_key] = seen.get(base_key, 0) + 1
        suffix = f"-{seen[base_key]:02d}" if seen[base_key] > 1 else ""
        units.append(
            {
                "unit_id": f"MSU-{base_key}{suffix}",
                "ordinal": index,
                "section": current_section,
                "text_sha256": hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
                "preview": normalized[:240],
                "text": normalized,
            }
        )
    return units


def _authority_digest(base: Path, relative: str) -> str:
    path = base / relative
    return file_sha256(path) if path.is_file() else ""


def _required_reviewers(change_classes: Iterable[str]) -> tuple[list[str], bool]:
    classes = {canonical(item) for item in change_classes}
    if classes & {"design", "execution"}:
        return list(REVIEWER_ORDER), True
    reviewers: set[str] = set()
    if "evidence" in classes:
        reviewers.update(REVIEWER_ORDER)
    if "argument" in classes:
        reviewers.update(("contribution", "clarity"))
    if "surface" in classes or not reviewers:
        reviewers.add("clarity")
    return [role for role in REVIEWER_ORDER if role in reviewers], False


IDENTITY_RE = re.compile(r"\b(?:SRC|EVD|CLM|DES|DGN|OPR|STEP|EXE|RES)-[A-Za-z0-9._-]+\b")


def _affected_identity_closure(
    base: Path,
    changed_context: list[dict[str, Any]],
    declared: dict[str, Any],
) -> dict[str, list[str]]:
    """Resolve a bounded identity closure from registered graph-bearing files."""
    groups = {
        "source_ids": {str(item) for item in declared.get("source_ids") or []},
        "claim_ids": {str(item) for item in declared.get("claim_ids") or []},
        "design_ids": {str(item) for item in declared.get("design_ids") or []},
        "execution_ids": {str(item) for item in declared.get("execution_ids") or []},
    }
    seeds = set().union(*groups.values())
    fragments = {
        _normalize_unit_text(str(unit.get("text") or unit.get("preview") or ""))[:80]
        for context in changed_context
        if isinstance(context, dict)
        for side in ("before", "after")
        for unit in [context.get(side)]
        if isinstance(unit, dict) and len(_normalize_unit_text(str(unit.get("text") or unit.get("preview") or ""))) >= 24
    }
    graph_lines: list[str] = []
    for relative in ("claim_register.md", "evidence_bank.md", "research_design.json", "method_execution.json", "section_blueprints.md"):
        path = base / relative
        if path.is_file():
            try:
                graph_lines.extend(path.read_text(encoding="utf-8-sig").splitlines())
            except (OSError, UnicodeError):
                continue
    changed = True
    while changed:
        changed = False
        for line in graph_lines:
            normalized = _normalize_unit_text(line)
            ids = set(IDENTITY_RE.findall(line))
            if not ids:
                continue
            if not (ids & seeds) and not any(fragment and fragment in normalized for fragment in fragments):
                continue
            new_ids = ids - seeds
            if new_ids:
                seeds.update(new_ids)
                changed = True
    for identity in seeds:
        if identity.startswith(("SRC-", "EVD-")):
            groups["source_ids"].add(identity)
        elif identity.startswith("CLM-"):
            groups["claim_ids"].add(identity)
        elif identity.startswith(("DES-", "DGN-", "OPR-", "STEP-")):
            groups["design_ids"].add(identity)
        elif identity.startswith(("EXE-", "RES-")):
            groups["execution_ids"].add(identity)
    return {key: sorted(values) for key, values in groups.items()}


def compute_revision_impact(
    base: Path,
    contract: dict[str, Any],
    batch: dict[str, Any],
) -> dict[str, Any]:
    """Compile the current candidate delta from files and canonical identities."""
    baseline = contract.get("baseline") if isinstance(contract.get("baseline"), dict) else {}
    canonical_path = _workspace_path(base, str(baseline.get("path") or ""))
    candidate_path = _workspace_path(base, str(batch.get("candidate_path") or ""))
    before_units = manuscript_units(canonical_path)
    after_units = manuscript_units(candidate_path)
    before_ids = [item["unit_id"] for item in before_units]
    after_ids = [item["unit_id"] for item in after_units]
    matcher = difflib.SequenceMatcher(a=before_ids, b=after_ids, autojunk=False)
    changed_before: list[str] = []
    changed_after: list[str] = []
    operations: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        before = before_ids[i1:i2]
        after = after_ids[j1:j2]
        changed_before.extend(before)
        changed_after.extend(after)
        operations.append({"operation": tag.upper(), "before_unit_ids": before, "after_unit_ids": after})
    changed_ids = sorted(set(changed_before + changed_after))
    changes = contract.get("requested_changes") if isinstance(contract.get("requested_changes"), list) else []
    target_ids = {str(item) for item in batch.get("target_change_ids") or []}
    active_changes = [
        item for item in changes
        if isinstance(item, dict) and (not target_ids or str(item.get("change_id") or "") in target_ids)
    ]
    classes = [str(item.get("change_class") or "") for item in active_changes]
    target_finding_keys = sorted({str(item) for item in batch.get("target_finding_keys") or []})
    active_finding_keys = sorted(
        {
            str(key)
            for item in active_changes
            for key in item.get("target_finding_keys") or []
        }
    )
    uncovered_target_finding_keys = sorted(set(target_finding_keys) - set(active_finding_keys))
    untracked_active_finding_keys = sorted(set(active_finding_keys) - set(target_finding_keys))
    reviewers, full_review = _required_reviewers(classes)
    sealed = batch.get("authority_digests") if isinstance(batch.get("authority_digests"), dict) else {}
    current_authorities = {relative: _authority_digest(base, relative) for relative in AUTHORITY_PATHS}
    changed_authorities = sorted(
        key for key, value in current_authorities.items() if str(sealed.get(key) or "") != value
    )
    canonical_classes = {canonical(item) for item in classes if canonical(item)}
    unexpected_changed_authorities = sorted(
        relative
        for relative in changed_authorities
        if not canonical_classes & AUTHORITY_ALLOWED_CHANGE_CLASSES.get(relative, frozenset())
    )
    if set(changed_authorities) & {
        "research_design.json", "method_execution.json",
        "confirmed_motivation.md", "confirmed_contribution.md",
    }:
        reviewers = list(REVIEWER_ORDER)
        full_review = True
    elif "evidence_bank.md" in changed_authorities:
        reviewers = list(REVIEWER_ORDER)
    elif "claim_register.md" in changed_authorities:
        reviewers = ["contribution", "clarity"]
    elif "section_blueprints.md" in changed_authorities:
        reviewers = ["clarity"]
    affected = contract.get("affected_identities") if isinstance(contract.get("affected_identities"), dict) else {}
    declared = sorted({str(item) for item in batch.get("declared_changed_unit_ids") or []})
    undeclared = sorted(set(changed_ids) - set(declared))
    stale_declared = sorted(set(declared) - set(changed_ids))
    radius = (
        "GLOBAL"
        if full_review
        else "CROSS_SECTION"
        if len({item["section"] for item in before_units + after_units if item["unit_id"] in changed_ids}) > 1
        else "LOCAL"
    )
    before_by_id = {item["unit_id"]: item for item in before_units}
    after_by_id = {item["unit_id"]: item for item in after_units}
    changed_context = [
        {
            "unit_id": unit_id,
            "before": before_by_id.get(unit_id),
            "after": after_by_id.get(unit_id),
        }
        for unit_id in changed_ids
    ]
    if "surface" not in canonical_classes and any(
        str((context.get("before") or context.get("after") or {}).get("section") or "").lower() == "title"
        for context in changed_context
    ):
        full_review = True
    resolved_affected = _affected_identity_closure(base, changed_context, affected)
    undeclared_affected = {
        key: sorted(set(resolved_affected[key]) - {str(item) for item in affected.get(key) or []})
        for key in ("source_ids", "claim_ids", "design_ids", "execution_ids")
    }
    if any(undeclared_affected.values()):
        full_review = full_review or bool(
            undeclared_affected["design_ids"] or undeclared_affected["execution_ids"]
        )
    if full_review:
        reviewers = list(REVIEWER_ORDER)
        radius = "GLOBAL"
    return {
        "schema_version": "avereth-revision-impact/v1",
        "batch_id": batch.get("batch_id"),
        "before_path": str(baseline.get("path") or ""),
        "candidate_path": str(batch.get("candidate_path") or ""),
        "before_sha256": file_sha256(canonical_path),
        "after_sha256": file_sha256(candidate_path),
        "changed_unit_ids": changed_ids,
        "changed_units": operations,
        "changed_unit_context": changed_context,
        "declared_changed_unit_ids": declared,
        "undeclared_changed_unit_ids": undeclared,
        "stale_declared_unit_ids": stale_declared,
        "affected_claim_ids": resolved_affected["claim_ids"],
        "affected_evidence_ids": resolved_affected["source_ids"],
        "affected_design_ids": resolved_affected["design_ids"],
        "affected_execution_ids": resolved_affected["execution_ids"],
        "undeclared_affected_identities": undeclared_affected,
        "changed_authorities": changed_authorities,
        "unexpected_changed_authorities": unexpected_changed_authorities,
        "target_finding_keys": target_finding_keys,
        "uncovered_target_finding_keys": uncovered_target_finding_keys,
        "untracked_active_finding_keys": untracked_active_finding_keys,
        "change_classes": sorted(canonical_classes),
        "impact_radius": radius,
        "required_reviewers": reviewers,
        "full_review_required": full_review,
        "preflight_status": (
            "PASS"
            if changed_ids
            and not undeclared
            and not stale_declared
            and not any(undeclared_affected.values())
            and not unexpected_changed_authorities
            and target_finding_keys
            and not uncovered_target_finding_keys
            and not untracked_active_finding_keys
            else "FAIL"
        ),
    }


def baseline_from_path(path: Path, *, workspace_root: Path | None = None) -> dict[str, str]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    suffix = resolved.suffix.lower()
    if suffix not in {".docx", ".md", ".markdown", ".tex", ".latex"}:
        raise ValueError("standalone revision accepts Word, Markdown, or LaTeX manuscripts")
    kind = "standalone"
    stored_path = str(resolved)
    if workspace_root is not None:
        root = workspace_root.resolve()
        try:
            stored_path = resolved.relative_to(root).as_posix()
            kind = "workspace"
        except ValueError:
            pass
    return {"kind": kind, "path": stored_path, "sha256": file_sha256(resolved)}


def scaffold_contract(
    *,
    baseline: dict[str, Any],
    requested_changes: list[dict[str, Any]],
    assurance_level: str,
    authorization: dict[str, Any],
    affected_identities: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    change_classes = [str(item.get("change_class") or "") for item in requested_changes]
    default_manuscript_unit = str(baseline.get("path") or "").strip()
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline": dict(baseline),
        "requested_changes": requested_changes,
        "affected_identities": affected_identities
        or {
            "source_ids": [],
            "claim_ids": [],
            "design_ids": [],
            "execution_ids": [],
            "manuscript_units": [default_manuscript_unit] if default_manuscript_unit else [],
        },
        "earliest_reopen_stage": route_for_change_classes(change_classes),
        "assurance_level": canonical(assurance_level),
        "authorization": dict(authorization),
        "active_batch_id": None,
        "revision_batches": [],
    }


def _issue(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


def validate_revision_contract(contract: Any, *, stage: str = "research") -> list[dict[str, str]]:
    if not isinstance(contract, dict):
        return [_issue("REV.ROOT", "revision_contract.json must contain an object")]
    issues: list[dict[str, str]] = []
    schema_version = str(contract.get("schema_version") or "")
    if schema_version == LEGACY_SCHEMA_VERSION:
        if canonical(stage) in {"audit", "output"}:
            issues.append(
                _issue(
                    "REV.SCHEMA.LEGACY_READ_ONLY",
                    f"{LEGACY_SCHEMA_VERSION} is read-only; migrate explicitly to {SCHEMA_VERSION}",
                )
            )
    elif schema_version != SCHEMA_VERSION:
        issues.append(_issue("REV.SCHEMA", f"schema_version must be {SCHEMA_VERSION}"))

    baseline = contract.get("baseline")
    if not isinstance(baseline, dict):
        issues.append(_issue("REV.BASELINE", "baseline contract is missing"))
    else:
        if canonical(baseline.get("kind")) not in BASELINE_KINDS:
            issues.append(_issue("REV.BASELINE.KIND", "baseline.kind must be workspace or standalone"))
        if not str(baseline.get("path") or "").strip():
            issues.append(_issue("REV.BASELINE.PATH", "baseline.path is required"))
        if not str(baseline.get("snapshot_path") or "").strip():
            issues.append(_issue("REV.BASELINE.SNAPSHOT", "baseline.snapshot_path is required"))
        digest = str(baseline.get("sha256") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            issues.append(_issue("REV.BASELINE.HASH", "baseline.sha256 must be a 64-character SHA-256"))

    changes = contract.get("requested_changes")
    change_classes: list[str] = []
    changes_by_id: dict[str, dict[str, Any]] = {}
    registered_finding_keys: set[str] = set()
    if not isinstance(changes, list) or not changes:
        issues.append(_issue("REV.CHANGES", "at least one requested change is required"))
    else:
        seen: set[str] = set()
        for index, change in enumerate(changes, start=1):
            if not isinstance(change, dict):
                issues.append(_issue("REV.CHANGE.RECORD", f"requested change {index} is invalid"))
                continue
            change_id = str(change.get("change_id") or "").strip()
            if not change_id or change_id in seen:
                issues.append(_issue("REV.CHANGE.ID", f"requested change {index} needs a unique change_id"))
            seen.add(change_id)
            if change_id:
                changes_by_id[change_id] = change
            if not str(change.get("summary") or "").strip():
                issues.append(_issue("REV.CHANGE.SUMMARY", f"requested change {change_id or index} lacks a summary"))
            change_class = canonical(change.get("change_class"))
            change_classes.append(change_class)
            if change_class not in CHANGE_CLASS_STAGE:
                issues.append(
                    _issue(
                        "REV.CHANGE.CLASS",
                        f"requested change {change_id or index} has unsupported class {change_class or '<missing>'}",
                    )
                )
            if schema_version == SCHEMA_VERSION:
                finding_keys = change.get("target_finding_keys")
                if not isinstance(finding_keys, list) or not finding_keys:
                    issues.append(
                        _issue(
                            "REV.CHANGE.FINDING_KEYS",
                            f"requested change {change_id or index} requires non-empty target_finding_keys",
                        )
                    )
                else:
                    normalized_keys = [str(item) for item in finding_keys]
                    if len(normalized_keys) != len(set(normalized_keys)) or any(
                        not FINDING_KEY_RE.fullmatch(item) for item in normalized_keys
                    ):
                        issues.append(
                            _issue(
                                "REV.CHANGE.FINDING_KEYS",
                                f"requested change {change_id or index} target_finding_keys must be unique RFK keys",
                            )
                        )
                    duplicated = registered_finding_keys & set(normalized_keys)
                    if duplicated:
                        issues.append(
                            _issue(
                                "REV.CHANGE.FINDING_KEY_DUPLICATE",
                                "finding keys may belong to only one requested change: " + ", ".join(sorted(duplicated)),
                            )
                        )
                    registered_finding_keys.update(normalized_keys)

    if change_classes and all(item in CHANGE_CLASS_STAGE for item in change_classes):
        expected_stage = route_for_change_classes(change_classes)
        if canonical(contract.get("earliest_reopen_stage")) != expected_stage:
            issues.append(
                _issue(
                    "REV.ROUTE",
                    f"earliest_reopen_stage must be {expected_stage} for the declared changes",
                )
            )

    affected = contract.get("affected_identities")
    expected_identity_groups = {
        "source_ids",
        "claim_ids",
        "design_ids",
        "execution_ids",
        "manuscript_units",
    }
    if not isinstance(affected, dict):
        issues.append(_issue("REV.AFFECTED", "affected_identities map is required"))
    else:
        has_affected_identity = False
        for key in expected_identity_groups:
            values = affected.get(key)
            if not isinstance(values, list) or any(not str(item).strip() for item in values):
                issues.append(_issue("REV.AFFECTED.GROUP", f"affected_identities.{key} must be a list"))
            elif values:
                has_affected_identity = True
        if not has_affected_identity:
            issues.append(
                _issue(
                    "REV.AFFECTED.EMPTY",
                    "affected_identities must name at least one source, claim, design, execution, or manuscript identity",
                )
            )

    assurance = canonical(contract.get("assurance_level"))
    if assurance not in ASSURANCE_LEVELS:
        issues.append(
            _issue(
                "REV.ASSURANCE",
                "assurance_level must be full, reconstructed, or legacy_limited",
            )
        )
    if assurance == "legacy_limited" and canonical(stage) == "output":
        issues.append(
            _issue(
                "REV.ASSURANCE.OUTPUT",
                "legacy_limited may support audit or surface work but cannot receive full output PASS",
            )
        )

    authorization = contract.get("authorization")
    if not isinstance(authorization, dict):
        issues.append(_issue("REV.AUTH", "authorization record is required"))
    else:
        status = canonical(authorization.get("status"))
        if status not in {"confirmed", "not_required", "pending"}:
            issues.append(_issue("REV.AUTH.STATUS", "authorization.status is unsupported"))
        evidence = str(authorization.get("evidence") or authorization.get("source") or "").strip()
        if status == "confirmed" and not evidence:
            issues.append(_issue("REV.AUTH.EVIDENCE", "confirmed authorization must retain its evidence"))
        substantive = any(item in {"evidence", "design", "execution"} for item in change_classes)
        if (substantive or canonical(stage) in {"audit", "output"}) and status != "confirmed":
            issues.append(
                _issue(
                    "REV.AUTH.REQUIRED",
                    "substantive revision and final delivery require explicit user authorization",
                )
            )
    if schema_version == SCHEMA_VERSION:
        batches = contract.get("revision_batches")
        if not isinstance(batches, list):
            issues.append(_issue("REV.BATCHES", "revision_batches must be an array"))
            batches = []
        seen_batches: set[str] = set()
        active_batch_id = contract.get("active_batch_id")
        for index, batch in enumerate(batches, start=1):
            if not isinstance(batch, dict):
                issues.append(_issue("REV.BATCH.RECORD", f"revision batch {index} must be an object"))
                continue
            batch_id = str(batch.get("batch_id") or "")
            if not BATCH_ID_RE.fullmatch(batch_id) or batch_id in seen_batches:
                issues.append(_issue("REV.BATCH.ID", f"revision batch {index} requires a unique RB-NNN batch_id"))
            seen_batches.add(batch_id)
            if str(batch.get("status") or "") not in {"STAGED", "PREFLIGHT_PASS", "PROMOTED", "VERIFIED", "BLOCKED"}:
                issues.append(_issue("REV.BATCH.STATUS", f"{batch_id or index} has an invalid status"))
            candidate_rel = str(batch.get("candidate_path") or "")
            if not candidate_rel:
                issues.append(_issue("REV.BATCH.CANDIDATE", f"{batch_id or index} lacks candidate_path"))
            if int(batch.get("promotion_count") or 0) not in {0, 1}:
                issues.append(_issue("REV.BATCH.PROMOTION_COUNT", f"{batch_id or index} must promote at most once"))
            if str(batch.get("status") or "") in {"PROMOTED", "VERIFIED"} and int(batch.get("promotion_count") or 0) != 1:
                issues.append(_issue("REV.BATCH.PROMOTION", f"{batch_id or index} promoted status requires exactly one promotion"))
            target_change_ids = [str(item) for item in batch.get("target_change_ids") or []]
            target_finding_keys = [str(item) for item in batch.get("target_finding_keys") or []]
            if not target_change_ids or len(target_change_ids) != len(set(target_change_ids)):
                issues.append(_issue("REV.BATCH.CHANGES", f"{batch_id or index} requires unique target_change_ids"))
            unknown_change_ids = sorted(set(target_change_ids) - set(changes_by_id))
            if unknown_change_ids:
                issues.append(
                    _issue("REV.BATCH.CHANGES", f"{batch_id or index} names unknown changes: {', '.join(unknown_change_ids)}")
                )
            if (
                not target_finding_keys
                or len(target_finding_keys) != len(set(target_finding_keys))
                or any(not FINDING_KEY_RE.fullmatch(item) for item in target_finding_keys)
            ):
                issues.append(_issue("REV.BATCH.FINDING_KEYS", f"{batch_id or index} requires unique RFK target_finding_keys"))
            active_finding_keys = {
                str(key)
                for change_id in target_change_ids
                for key in changes_by_id.get(change_id, {}).get("target_finding_keys") or []
            }
            if set(target_finding_keys) != active_finding_keys:
                missing = sorted(set(target_finding_keys) - active_finding_keys)
                untracked = sorted(active_finding_keys - set(target_finding_keys))
                detail = []
                if missing:
                    detail.append("uncovered " + ", ".join(missing))
                if untracked:
                    detail.append("untracked " + ", ".join(untracked))
                issues.append(
                    _issue(
                        "REV.BATCH.FINDING_COVERAGE",
                        f"{batch_id or index} target Finding coverage is inconsistent: " + "; ".join(detail),
                    )
                )
        if active_batch_id is not None and str(active_batch_id) not in seen_batches:
            issues.append(_issue("REV.BATCH.ACTIVE", "active_batch_id must name a registered revision batch"))
    return issues


def load_and_validate(base: Path, *, stage: str) -> tuple[dict[str, Any], list[dict[str, str]]]:
    path = base / CONTRACT_REL
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {}, [_issue("REV.MISSING", f"missing {CONTRACT_REL.as_posix()}")]
    except (OSError, json.JSONDecodeError) as exc:
        return {}, [_issue("REV.INVALID", f"cannot read revision contract: {exc}")]
    contract = payload if isinstance(payload, dict) else {}
    issues = validate_revision_contract(contract, stage=stage)
    baseline = contract.get("baseline") if isinstance(contract.get("baseline"), dict) else {}
    snapshot_rel = str(baseline.get("snapshot_path") or "").strip()
    if snapshot_rel:
        snapshot = (base / snapshot_rel).resolve()
        try:
            snapshot.relative_to(base.resolve())
        except ValueError:
            issues.append(_issue("REV.BASELINE.SNAPSHOT", "baseline snapshot must stay inside the revision workspace"))
        else:
            if not snapshot.is_file():
                issues.append(_issue("REV.BASELINE.SNAPSHOT", "baseline snapshot is missing"))
            elif file_sha256(snapshot) != str(baseline.get("sha256") or "").lower():
                issues.append(_issue("REV.BASELINE.SNAPSHOT", "baseline snapshot hash no longer matches the contract"))
    if contract.get("schema_version") == SCHEMA_VERSION:
        for batch in contract.get("revision_batches") or []:
            if not isinstance(batch, dict):
                continue
            batch_id = str(batch.get("batch_id") or "<unknown>")
            candidate_rel = str(batch.get("candidate_path") or "")
            if not candidate_rel:
                continue
            try:
                candidate = _workspace_path(base, candidate_rel)
            except (OSError, ValueError):
                issues.append(_issue("REV.BATCH.CANDIDATE", f"{batch_id} candidate must stay inside the workspace"))
                continue
            status = str(batch.get("status") or "")
            if status in {"STAGED", "PREFLIGHT_PASS", "BLOCKED"} and not candidate.is_file():
                issues.append(_issue("REV.BATCH.CANDIDATE", f"{batch_id} candidate is missing"))
            if status in {"PROMOTED", "VERIFIED"}:
                promoted_sha = str(batch.get("promoted_sha256") or "")
                baseline_path = str((contract.get("baseline") or {}).get("path") or "")
                try:
                    canonical_path = _workspace_path(base, baseline_path)
                except (OSError, ValueError):
                    canonical_path = Path()
                if not promoted_sha or not canonical_path.is_file() or file_sha256(canonical_path) != promoted_sha:
                    issues.append(_issue("REV.BATCH.PROMOTED_SHA", f"{batch_id} no longer binds the canonical manuscript"))
    return contract, issues


def route_plan(contract: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(contract, dict):
        return {
            "earliest_reopen_stage": None,
            "assurance_level": "unknown",
            "change_classes": [],
        }
    changes = contract.get("requested_changes") if isinstance(contract.get("requested_changes"), list) else []
    return {
        "earliest_reopen_stage": contract.get("earliest_reopen_stage"),
        "assurance_level": contract.get("assurance_level"),
        "change_classes": [
            canonical(item.get("change_class")) for item in changes if isinstance(item, dict)
        ],
        "affected_identities": contract.get("affected_identities") or {},
        "authorization_status": (contract.get("authorization") or {}).get("status")
        if isinstance(contract.get("authorization"), dict)
        else "missing",
    }


def _parse_changes(
    values: list[str],
    finding_keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    supplied_keys = [str(item).strip().upper() for item in finding_keys or []]
    if supplied_keys and len(supplied_keys) != len(values):
        raise ValueError("--finding-key count must equal --change count")
    if any(not FINDING_KEY_RE.fullmatch(item) for item in supplied_keys):
        raise ValueError("each --finding-key must use RFK- followed by 24 hexadecimal characters")
    if len(supplied_keys) != len(set(supplied_keys)):
        raise ValueError("--finding-key values must be unique")
    changes: list[dict[str, Any]] = []
    for index, value in enumerate(values, start=1):
        change_class, separator, summary = value.partition(":")
        if not separator or canonical(change_class) not in CHANGE_CLASS_STAGE or not summary.strip():
            raise ValueError(
                "each --change must use CLASS:SUMMARY where CLASS is surface, argument, evidence, design, or execution"
            )
        change: dict[str, Any] = {
            "change_id": f"CH-{index:03d}",
            "change_class": canonical(change_class),
            "summary": summary.strip(),
        }
        change["target_finding_keys"] = [
            supplied_keys[index - 1] if supplied_keys else _derived_finding_key(change)
        ]
        changes.append(change)
    return changes


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def command_init(args: argparse.Namespace) -> int:
    base = Path(args.outdir).resolve()
    destination = base / CONTRACT_REL
    if destination.exists() and not args.force:
        print(f"refusing to overwrite existing revision contract: {destination}")
        return 2
    config_read = read_config(base)
    if config_read.path is not None and (config_read.issues or validate_workflow_config(config_read.payload)):
        print("existing workflow config is not a valid v6 contract; run avereth.py migrate first")
        return 2
    initial_config = dict(config_read.payload)
    publication_track = str(initial_config.get("publication_track") or args.publication_track or "").strip()
    if not publication_track:
        print("--publication-track is required when initializing a new revision workspace")
        return 2
    try:
        changes = _parse_changes(args.change, getattr(args, "finding_key", None))
        baseline = baseline_from_path(
            Path(args.manuscript),
            workspace_root=base if Path(args.manuscript).resolve().is_relative_to(base) else None,
        )
        manuscript_path = Path(args.manuscript).resolve()
        snapshot_rel = BASELINE_DIR / f"baseline-{baseline['sha256'][:12]}{manuscript_path.suffix.lower()}"
        baseline["snapshot_path"] = snapshot_rel.as_posix()
        contract = scaffold_contract(
            baseline=baseline,
            requested_changes=changes,
            assurance_level=args.assurance_level,
            authorization={"status": "confirmed", "evidence": args.authorization_evidence},
        )
    except (OSError, ValueError) as exc:
        print(str(exc))
        return 2
    issues = validate_revision_contract(contract, stage="research")
    if issues:
        print(json.dumps({"status": "FAIL", "issues": issues}, ensure_ascii=False, indent=2))
        return 2
    base.mkdir(parents=True, exist_ok=True)
    snapshot_path = base / snapshot_rel
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    if snapshot_path.exists() and file_sha256(snapshot_path) != baseline["sha256"]:
        print(f"refusing to overwrite a mismatched baseline snapshot: {snapshot_path}")
        return 2
    if not snapshot_path.exists():
        shutil.copy2(manuscript_path, snapshot_path)

    working_path = manuscript_path
    if baseline["kind"] == "standalone":
        working_path = base / f"working_manuscript{manuscript_path.suffix.lower()}"
        if working_path.exists() and file_sha256(working_path) != baseline["sha256"]:
            print(f"refusing to overwrite an existing working manuscript: {working_path}")
            return 2
        if not working_path.exists():
            shutil.copy2(manuscript_path, working_path)
    canonical_relative = working_path.resolve().relative_to(base).as_posix()
    original_path = str(contract["baseline"].get("path") or "")
    contract["baseline"]["source_path"] = original_path
    contract["baseline"]["path"] = canonical_relative
    _write_json(destination, contract)
    config = dict(initial_config)
    config.update(
        {
            "framework_version": VERSION,
            "schema_version": WORKFLOW_CONFIG_SCHEMA,
            "task_profile": "manuscript_revision",
            "workflow": "rewrite_existing",
            "publication_track": publication_track,
            "scene": config.get("scene") or args.scene,
            "tier": config.get("tier") or "flash",
            "output_language": config.get("output_language") or args.output_language,
            "word_output": config.get("word_output") or args.word_output,
            "pdf_output": config.get("pdf_output") or args.pdf_output,
            "citation_mode": config.get("citation_mode") or args.citation_mode,
            "word_font_policy": config.get("word_font_policy") or args.word_font_policy,
            "prose_mode": config.get("prose_mode") or args.prose_mode,
            "canonical_manuscript": canonical_relative,
        }
    )
    config.pop("draft_path", None)
    config.pop("citation_audit_manuscript", None)
    config_issues = validate_workflow_config(config)
    if config_issues:
        print(json.dumps({"status": "FAIL", "issues": config_issues}, ensure_ascii=False, indent=2))
        return 2
    write_config(base, config)
    print(
        json.dumps(
            {
                "status": "PASS",
                "contract": str(destination),
                "baseline_kind": baseline["kind"],
                "earliest_reopen_stage": contract["earliest_reopen_stage"],
                "assurance_level": contract["assurance_level"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_validate(args: argparse.Namespace) -> int:
    contract, issues = load_and_validate(Path(args.outdir).resolve(), stage=args.stage)
    print(
        json.dumps(
            {
                "status": "PASS" if not issues else "FAIL",
                "schema_version": contract.get("schema_version", "missing"),
                "route_plan": route_plan(contract),
                "issues": issues,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not issues else 1


def _load_active_v2(base: Path, *, stage: str = "build") -> tuple[dict[str, Any], list[dict[str, str]]]:
    contract, issues = load_and_validate(base, stage=stage)
    if contract.get("schema_version") == LEGACY_SCHEMA_VERSION:
        issues.append(
            _issue(
                "REV.SCHEMA.LEGACY_READ_ONLY",
                f"migrate {LEGACY_SCHEMA_VERSION} explicitly before using revision batches",
            )
        )
    return contract, issues


def _batch_by_id(contract: dict[str, Any], batch_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in contract.get("revision_batches") or []
            if isinstance(item, dict) and item.get("batch_id") == batch_id
        ),
        None,
    )


def command_migrate(args: argparse.Namespace) -> int:
    base = Path(args.outdir).resolve()
    try:
        payload = json.loads((base / CONTRACT_REL).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    if not isinstance(payload, dict) or payload.get("schema_version") != LEGACY_SCHEMA_VERSION:
        print(json.dumps({"status": "FAIL", "issues": [f"source must use {LEGACY_SCHEMA_VERSION}"]}, ensure_ascii=False, indent=2))
        return 1
    migrated = dict(payload)
    migrated["schema_version"] = SCHEMA_VERSION
    review_registry: dict[str, Any] = {}
    try:
        loaded_registry = json.loads((base / "review_findings.json").read_text(encoding="utf-8-sig"))
        if isinstance(loaded_registry, dict):
            review_registry = loaded_registry
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    finding_key_by_id = {
        str(item.get("finding_id") or ""): str(item.get("finding_key") or "")
        for item in review_registry.get("findings") or []
        if isinstance(item, dict) and FINDING_KEY_RE.fullmatch(str(item.get("finding_key") or ""))
    }
    migrated_changes: list[dict[str, Any]] = []
    used_change_ids: set[str] = set()
    for index, source_change in enumerate(payload.get("requested_changes") or [], start=1):
        if not isinstance(source_change, dict):
            migrated_changes.append(source_change)
            continue
        change = dict(source_change)
        legacy_change_id = str(change.get("change_id") or "").strip()
        explicit_finding_id = str(change.pop("finding_id", "") or "").strip()
        legacy_finding_id = explicit_finding_id or (
            legacy_change_id if re.fullmatch(r"REV-(?:MET|CON|CLR)-[0-9]{3}", legacy_change_id) else ""
        )
        if legacy_finding_id:
            candidate_change_id = f"CH-{index:03d}"
        else:
            candidate_change_id = legacy_change_id or f"CH-{index:03d}"
        while candidate_change_id in used_change_ids:
            index += 1
            candidate_change_id = f"CH-{index:03d}"
        change["change_id"] = candidate_change_id
        used_change_ids.add(candidate_change_id)
        registered_key = finding_key_by_id.get(legacy_finding_id)
        change["target_finding_keys"] = [registered_key or _derived_finding_key(change)]
        migrated_changes.append(change)
    migrated["requested_changes"] = migrated_changes
    migrated["active_batch_id"] = None
    migrated["revision_batches"] = []
    migration_issues = validate_revision_contract(migrated, stage="build")
    if migration_issues:
        print(json.dumps({"status": "FAIL", "issues": migration_issues}, ensure_ascii=False, indent=2))
        return 1
    if args.apply:
        backup = base / "migration" / "revision_contract_v2" / "revision_contract.v1.json"
        if backup.exists():
            print(json.dumps({"status": "FAIL", "issues": ["migration backup already exists"]}, ensure_ascii=False, indent=2))
            return 1
        backup.parent.mkdir(parents=True, exist_ok=True)
        _write_json(backup, payload)
        _write_json(base / CONTRACT_REL, migrated)
    print(
        json.dumps(
            {
                "status": "PASS",
                "mode": "apply" if args.apply else "dry-run",
                "from": LEGACY_SCHEMA_VERSION,
                "to": SCHEMA_VERSION,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_batch_start(args: argparse.Namespace) -> int:
    base = Path(args.outdir).resolve()
    contract, issues = _load_active_v2(base)
    if issues:
        print(json.dumps({"status": "FAIL", "issues": issues}, ensure_ascii=False, indent=2))
        return 1
    batch_id = str(args.batch_id)
    if not BATCH_ID_RE.fullmatch(batch_id):
        print(json.dumps({"status": "FAIL", "issues": ["batch_id must use RB-NNN"]}, ensure_ascii=False, indent=2))
        return 1
    if contract.get("active_batch_id"):
        print(json.dumps({"status": "FAIL", "issues": ["another revision batch is active"]}, ensure_ascii=False, indent=2))
        return 1
    if _batch_by_id(contract, batch_id) is not None:
        print(json.dumps({"status": "FAIL", "issues": ["batch_id already exists"]}, ensure_ascii=False, indent=2))
        return 1
    known_changes = {
        str(item.get("change_id") or "")
        for item in contract.get("requested_changes") or []
        if isinstance(item, dict)
    }
    change_values = getattr(args, "change_id", None)
    if change_values is None:
        change_values = getattr(args, "finding_id", None)
    target_ids = list(dict.fromkeys(str(item) for item in change_values or []))
    target_finding_keys = list(
        dict.fromkeys(str(item).upper() for item in (getattr(args, "finding_key", None) or []))
    )
    if not target_ids:
        print(json.dumps({"status": "FAIL", "issues": ["at least one --change-id is required"]}, ensure_ascii=False, indent=2))
        return 1
    if not target_finding_keys or any(not FINDING_KEY_RE.fullmatch(item) for item in target_finding_keys):
        print(json.dumps({"status": "FAIL", "issues": ["--finding-key requires one or more RFK- followed by 24 hexadecimal characters"]}, ensure_ascii=False, indent=2))
        return 1
    unknown = sorted(set(target_ids) - known_changes)
    if unknown:
        print(json.dumps({"status": "FAIL", "issues": ["unknown target change IDs: " + ", ".join(unknown)]}, ensure_ascii=False, indent=2))
        return 1
    changes_by_id = {
        str(item.get("change_id") or ""): item
        for item in contract.get("requested_changes") or []
        if isinstance(item, dict)
    }
    covered_finding_keys = {
        str(key)
        for change_id in target_ids
        for key in changes_by_id.get(change_id, {}).get("target_finding_keys") or []
    }
    if set(target_finding_keys) != covered_finding_keys:
        uncovered = sorted(set(target_finding_keys) - covered_finding_keys)
        omitted = sorted(covered_finding_keys - set(target_finding_keys))
        detail: list[str] = []
        if uncovered:
            detail.append("not covered by active changes: " + ", ".join(uncovered))
        if omitted:
            detail.append("omitted from the batch: " + ", ".join(omitted))
        print(json.dumps({"status": "FAIL", "issues": ["target Finding coverage mismatch; " + "; ".join(detail)]}, ensure_ascii=False, indent=2))
        return 1
    baseline = contract.get("baseline") if isinstance(contract.get("baseline"), dict) else {}
    try:
        canonical_path = _workspace_path(base, str(baseline.get("path") or ""))
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    if not canonical_path.is_file():
        print(json.dumps({"status": "FAIL", "issues": ["canonical manuscript is missing"]}, ensure_ascii=False, indent=2))
        return 1
    candidate_rel = REVISION_WORKTREE_DIR / batch_id / f"revision_candidate{canonical_path.suffix.lower()}"
    candidate_path = base / candidate_rel
    candidate_path.parent.mkdir(parents=True, exist_ok=False)
    shutil.copy2(canonical_path, candidate_path)
    batch = {
        "batch_id": batch_id,
        "status": "STAGED",
        "target_change_ids": target_ids,
        "target_finding_keys": target_finding_keys,
        "candidate_path": candidate_rel.as_posix(),
        "before_sha256": file_sha256(canonical_path),
        "authority_digests": {
            relative: _authority_digest(base, relative) for relative in AUTHORITY_PATHS
        },
        "declared_changed_unit_ids": [],
        "impact_path": None,
        "impact_sha256": None,
        "promotion_count": 0,
        "promoted_sha256": None,
        "created_at": _now_utc(),
    }
    contract.setdefault("revision_batches", []).append(batch)
    contract["active_batch_id"] = batch_id
    _write_json(base / CONTRACT_REL, contract)
    print(json.dumps({"status": "PASS", "batch": batch}, ensure_ascii=False, indent=2))
    return 0


def command_impact(args: argparse.Namespace) -> int:
    base = Path(args.outdir).resolve()
    contract, issues = _load_active_v2(base)
    if issues:
        print(json.dumps({"status": "FAIL", "issues": issues}, ensure_ascii=False, indent=2))
        return 1
    batch = _batch_by_id(contract, str(args.batch_id))
    if batch is None:
        print(json.dumps({"status": "FAIL", "issues": ["unknown revision batch"]}, ensure_ascii=False, indent=2))
        return 1
    if str(batch.get("status") or "") not in {"STAGED", "PREFLIGHT_PASS", "BLOCKED"}:
        print(json.dumps({"status": "FAIL", "issues": ["only an unpromoted batch can be analyzed"]}, ensure_ascii=False, indent=2))
        return 1
    impact = compute_revision_impact(base, contract, batch)
    if args.accept_actual_diff and impact["changed_unit_ids"]:
        batch["declared_changed_unit_ids"] = impact["changed_unit_ids"]
        affected = contract.get("affected_identities") if isinstance(contract.get("affected_identities"), dict) else {}
        resolved_groups = {
            "source_ids": impact.get("affected_evidence_ids") or [],
            "claim_ids": impact.get("affected_claim_ids") or [],
            "design_ids": impact.get("affected_design_ids") or [],
            "execution_ids": impact.get("affected_execution_ids") or [],
        }
        for key, values in resolved_groups.items():
            affected[key] = sorted({str(item) for item in affected.get(key) or []} | {str(item) for item in values})
        affected["manuscript_units"] = sorted(
            {str(item) for item in affected.get("manuscript_units") or []}
            | {str(item) for item in impact["changed_unit_ids"]}
        )
        contract["affected_identities"] = affected
        impact = compute_revision_impact(base, contract, batch)
    impact_rel = REVISION_WORKTREE_DIR / str(args.batch_id) / "revision_impact.json"
    impact_path = base / impact_rel
    _write_json(impact_path, impact)
    # The root path is a rebuildable latest-impact view; review cycles bind the
    # immutable batch-local path so a later batch cannot rewrite their proof.
    _write_json(base / IMPACT_REL, impact)
    batch["impact_path"] = impact_rel.as_posix()
    batch["impact_sha256"] = file_sha256(impact_path)
    batch["status"] = "PREFLIGHT_PASS" if impact["preflight_status"] == "PASS" else "BLOCKED"
    _write_json(base / CONTRACT_REL, contract)
    print(json.dumps(impact, ensure_ascii=False, indent=2))
    return 0 if impact["preflight_status"] == "PASS" else 1


def command_promote(args: argparse.Namespace) -> int:
    base = Path(args.outdir).resolve()
    contract, issues = _load_active_v2(base)
    if issues:
        print(json.dumps({"status": "FAIL", "issues": issues}, ensure_ascii=False, indent=2))
        return 1
    batch = _batch_by_id(contract, str(args.batch_id))
    if batch is None:
        print(json.dumps({"status": "FAIL", "issues": ["unknown revision batch"]}, ensure_ascii=False, indent=2))
        return 1
    if str(batch.get("status") or "") != "PREFLIGHT_PASS" or int(batch.get("promotion_count") or 0) != 0:
        print(json.dumps({"status": "FAIL", "issues": ["batch must pass preflight and may be promoted exactly once"]}, ensure_ascii=False, indent=2))
        return 1
    impact_path = base / str(batch.get("impact_path") or "")
    try:
        impact = json.loads(impact_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        impact = {}
    if file_sha256(impact_path) != str(batch.get("impact_sha256") or ""):
        print(json.dumps({"status": "FAIL", "issues": ["revision impact changed after preflight"]}, ensure_ascii=False, indent=2))
        return 1
    fresh = compute_revision_impact(base, contract, batch)
    if fresh != impact or impact.get("preflight_status") != "PASS":
        print(json.dumps({"status": "FAIL", "issues": ["candidate or authority inputs changed after preflight"]}, ensure_ascii=False, indent=2))
        return 1
    baseline = contract.get("baseline") if isinstance(contract.get("baseline"), dict) else {}
    canonical_path = _workspace_path(base, str(baseline.get("path") or ""))
    candidate_path = _workspace_path(base, str(batch.get("candidate_path") or ""))
    if file_sha256(canonical_path) != str(batch.get("before_sha256") or ""):
        print(json.dumps({"status": "FAIL", "issues": ["canonical manuscript changed outside the active batch"]}, ensure_ascii=False, indent=2))
        return 1
    promoted_sha = file_sha256(candidate_path)
    next_contract = json.loads(json.dumps(contract))
    next_batch = _batch_by_id(next_contract, str(args.batch_id))
    assert next_batch is not None
    next_batch.update(
        {
            "status": "PROMOTED",
            "promotion_count": 1,
            "promoted_sha256": promoted_sha,
            "promoted_at": _now_utc(),
        }
    )
    next_contract["active_batch_id"] = None
    temp_manuscript = canonical_path.with_name(canonical_path.name + f".{args.batch_id}.tmp")
    temp_contract = (base / CONTRACT_REL).with_suffix(".json.tmp")
    shutil.copy2(candidate_path, temp_manuscript)
    temp_contract.write_text(json.dumps(next_contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    original = canonical_path.read_bytes()
    try:
        os.replace(temp_manuscript, canonical_path)
        os.replace(temp_contract, base / CONTRACT_REL)
    except OSError:
        canonical_path.write_bytes(original)
        temp_manuscript.unlink(missing_ok=True)
        temp_contract.unlink(missing_ok=True)
        raise
    print(json.dumps({"status": "PASS", "batch_id": args.batch_id, "canonical_sha256": promoted_sha, "promotion_count": 1}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="create a controlled revision workspace entry")
    init.add_argument("outdir")
    init.add_argument("manuscript")
    init.add_argument("--change", action="append", required=True)
    init.add_argument(
        "--finding-key", action="append",
        help="real RFK key bound one-to-one to each --change; repeat in the same order",
    )
    init.add_argument("--assurance-level", choices=sorted(ASSURANCE_LEVELS), default="legacy_limited")
    init.add_argument("--authorization-evidence", required=True)
    init.add_argument("--scene", choices=("journal", "conference", "report_review"), default="journal")
    init.add_argument("--publication-track", choices=("cnki-cn", "international-ssci", "mixed"))
    init.add_argument("--output-language", choices=("zh", "en"), default="zh")
    init.add_argument("--word-output", choices=("none", "docx"), default="docx")
    init.add_argument("--pdf-output", choices=("none", "pdf"), default="none")
    init.add_argument("--citation-mode", choices=("numeric", "author_year", "footnote"), default="author_year")
    init.add_argument("--word-font-policy", choices=("default", "template", "skip"), default="default")
    init.add_argument("--prose-mode", choices=("clear", "distinguished"), default="clear")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=command_init)

    validate = subparsers.add_parser("validate")
    validate.add_argument("outdir")
    validate.add_argument("--stage", choices=("research", "design", "execution", "build", "audit", "output"), default="research")
    validate.set_defaults(func=command_validate)

    migrate = subparsers.add_parser("migrate", help="explicitly migrate a legacy v1 revision contract")
    migrate.add_argument("outdir")
    migrate.add_argument("--apply", action="store_true")
    migrate.set_defaults(func=command_migrate)

    batch_start = subparsers.add_parser("batch-start", help="create an isolated revision candidate")
    batch_start.add_argument("outdir")
    batch_start.add_argument("--batch-id", required=True)
    batch_start.add_argument("--change-id", action="append", required=True, help="requested_changes[].change_id to execute in this batch")
    batch_start.add_argument("--finding-key", action="append", required=True, help="RFK key covered by the selected changes; repeat for every target Finding")
    batch_start.set_defaults(func=command_batch_start)

    impact = subparsers.add_parser("impact", help="compile deterministic revision impact")
    impact.add_argument("outdir")
    impact.add_argument("--batch-id", required=True)
    impact.add_argument("--accept-actual-diff", action="store_true")
    impact.set_defaults(func=command_impact)

    promote = subparsers.add_parser("promote", help="atomically promote one preflighted revision candidate")
    promote.add_argument("outdir")
    promote.add_argument("--batch-id", required=True)
    promote.set_defaults(func=command_promote)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
