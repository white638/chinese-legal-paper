"""Offline contracts for Exa discovery runs and Zotero identity snapshots.

These validators are deliberately read-only and use only the Python standard
library.  They validate adapter handoffs; they do not mutate the canonical
literature registry or advance an Avereth stage.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


EXA_RUN_SCHEMA = "avereth-exa-run/v1"
EXA_MANIFEST_SCHEMA = "avereth-exa-manifest/v1"
ZOTERO_SNAPSHOT_SCHEMA = "avereth-zotero-snapshot/v1"
PURPOSES = {"venue", "sota", "collision", "terminology", "citation", "other"}
FETCH_STATES = {"not-fetched", "fetched", "failed"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
SOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
ZOTERO_KEY_RE = re.compile(r"^[A-Z0-9]{8}$")
SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")
EXA_RUN_PATH_RE = re.compile(
    r"^reference_materials/integrations/exa_runs/[A-Za-z0-9._-]+\.json$"
)
EXA_RUN_FIELDS = {
    "schema_version", "query_id", "purpose", "workstream", "query",
    "executed_at", "tool", "results_reviewed", "results",
}
EXA_RESULT_FIELDS = {
    "rank", "title", "url", "author", "published_at", "highlights",
    "content_fetch", "citation_scope",
}
EXA_MANIFEST_FIELDS = {"schema_version", "runs"}
EXA_MANIFEST_RUN_FIELDS = {
    "query_id", "path", "sha256", "executed_at", "result_count",
}
ZOTERO_SNAPSHOT_FIELDS = {
    "schema_version", "server_id", "library_id", "library_version",
    "captured_at", "items",
}
ZOTERO_ITEM_FIELDS = {
    "source_id", "item_key", "item_version", "citation_key", "doi",
    "identity_digest", "attachment_keys",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _nonnegative_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _date_time(value: Any) -> bool:
    text = _text(value)
    if not text or "T" not in text:
        return False
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _http_url(value: Any) -> bool:
    parsed = urlsplit(_text(value))
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _unknown_field_issues(
    payload: dict[str, Any],
    allowed: set[str],
    label: str,
) -> list[str]:
    return [
        f"{label} contains unsupported field {field!r}"
        for field in sorted(set(payload) - allowed)
    ]


def _json_object(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, [f"invalid JSON object at {path}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"integration artifact must contain one JSON object: {path}"]
    return payload, []


def zotero_identity_digest(snapshot: dict[str, Any], item: dict[str, Any]) -> str:
    """Return the stable digest of the identity fields frozen by the snapshot."""

    raw_attachments = item.get("attachment_keys")
    attachments = raw_attachments if isinstance(raw_attachments, list) else []
    identity = {
        "attachment_keys": sorted(_text(value) for value in attachments),
        "citation_key": _text(item.get("citation_key")),
        "doi": _text(item.get("doi")).lower(),
        "item_key": _text(item.get("item_key")),
        "item_version": item.get("item_version"),
        "library_id": snapshot.get("library_id"),
        "server_id": _text(snapshot.get("server_id")),
        "source_id": _text(item.get("source_id")),
    }
    canonical = json.dumps(
        identity,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_exa_run(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["Exa run must be an object"]
    issues.extend(_unknown_field_issues(payload, EXA_RUN_FIELDS, "Exa run"))
    if payload.get("schema_version") != EXA_RUN_SCHEMA:
        issues.append(f"schema_version must be {EXA_RUN_SCHEMA}")
    query_id = _text(payload.get("query_id"))
    if not isinstance(payload.get("query_id"), str) or not IDENTIFIER_RE.fullmatch(query_id):
        issues.append("query_id is invalid")
    if _text(payload.get("purpose")) not in PURPOSES:
        issues.append("purpose is unsupported")
    for field in ("workstream", "query", "tool"):
        if not isinstance(payload.get(field), str) or not _text(payload.get(field)):
            issues.append(f"{field} is required")
    if not _date_time(payload.get("executed_at")):
        issues.append("executed_at must be an ISO date-time")
    results_reviewed = payload.get("results_reviewed")
    if not _nonnegative_integer(results_reviewed):
        issues.append("results_reviewed must be a non-negative integer")
    results = payload.get("results")
    if not isinstance(results, list):
        issues.append("results must be a list")
        return issues
    if _nonnegative_integer(results_reviewed) and results_reviewed != len(results):
        issues.append("results_reviewed must equal the number of retained run results")
    ranks: set[int] = set()
    for number, result in enumerate(results, start=1):
        prefix = f"result {number}"
        if not isinstance(result, dict):
            issues.append(f"{prefix} must be an object")
            continue
        issues.extend(_unknown_field_issues(result, EXA_RESULT_FIELDS, prefix))
        rank = result.get("rank")
        if not _positive_integer(rank):
            issues.append(f"{prefix} rank must be a positive integer")
        elif rank in ranks:
            issues.append(f"{prefix} rank is duplicated")
        else:
            ranks.add(rank)
        if not isinstance(result.get("title"), str) or not _text(result.get("title")):
            issues.append(f"{prefix} title is required")
        if not isinstance(result.get("url"), str) or not _http_url(result.get("url")):
            issues.append(f"{prefix} url must be HTTP(S)")
        for optional_text in ("author", "published_at"):
            if optional_text in result and not isinstance(result.get(optional_text), str):
                issues.append(f"{prefix} {optional_text} must be a string")
        highlights = result.get("highlights")
        if not isinstance(highlights, list) or any(not isinstance(item, str) for item in highlights):
            issues.append(f"{prefix} highlights must be a string list")
        if _text(result.get("content_fetch")) not in FETCH_STATES:
            issues.append(f"{prefix} content_fetch is unsupported")
        if result.get("citation_scope") != "candidate-only":
            issues.append(f"{prefix} must remain citation_scope=candidate-only")
    return issues


def validate_exa_manifest(payload: Any, *, workspace: Path | None = None) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["Exa manifest must be an object"]
    issues.extend(
        _unknown_field_issues(payload, EXA_MANIFEST_FIELDS, "Exa manifest")
    )
    if payload.get("schema_version") != EXA_MANIFEST_SCHEMA:
        issues.append(f"schema_version must be {EXA_MANIFEST_SCHEMA}")
    runs = payload.get("runs")
    if not isinstance(runs, list):
        issues.append("runs must be a list")
        return issues
    query_ids: set[str] = set()
    paths: set[str] = set()
    for number, run in enumerate(runs, start=1):
        prefix = f"manifest run {number}"
        if not isinstance(run, dict):
            issues.append(f"{prefix} must be an object")
            continue
        issues.extend(_unknown_field_issues(run, EXA_MANIFEST_RUN_FIELDS, prefix))
        query_id = _text(run.get("query_id"))
        if not isinstance(run.get("query_id"), str) or not IDENTIFIER_RE.fullmatch(query_id):
            issues.append(f"{prefix} query_id is invalid")
        elif query_id in query_ids:
            issues.append(f"{prefix} query_id is duplicated")
        else:
            query_ids.add(query_id)
        relative = _text(run.get("path")).replace("\\", "/")
        if not isinstance(run.get("path"), str) or not EXA_RUN_PATH_RE.fullmatch(relative):
            issues.append(f"{prefix} path is outside the controlled Exa run directory")
        elif relative in paths:
            issues.append(f"{prefix} path is duplicated")
        else:
            paths.add(relative)
        digest = _text(run.get("sha256"))
        if not isinstance(run.get("sha256"), str) or not SHA256_RE.fullmatch(digest):
            issues.append(f"{prefix} sha256 is invalid")
        if not _date_time(run.get("executed_at")):
            issues.append(f"{prefix} executed_at must be an ISO date-time")
        if not _nonnegative_integer(run.get("result_count")):
            issues.append(f"{prefix} result_count must be a non-negative integer")
        if workspace is None or not EXA_RUN_PATH_RE.fullmatch(relative):
            continue
        artifact = workspace / Path(relative)
        payload_run, load_issues = _json_object(artifact)
        issues.extend(f"{prefix}: {issue}" for issue in load_issues)
        if payload_run is None:
            continue
        actual_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        if digest.lower() != actual_digest:
            issues.append(f"{prefix} sha256 does not match the run artifact")
        issues.extend(f"{prefix}: {issue}" for issue in validate_exa_run(payload_run))
        if payload_run.get("query_id") != query_id:
            issues.append(f"{prefix} query_id does not match the run artifact")
        if payload_run.get("executed_at") != run.get("executed_at"):
            issues.append(f"{prefix} executed_at does not match the run artifact")
        results = payload_run.get("results")
        if isinstance(results, list) and run.get("result_count") != len(results):
            issues.append(f"{prefix} result_count does not match the run artifact")
    return issues


def validate_zotero_snapshot(payload: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(payload, dict):
        return ["Zotero snapshot must be an object"]
    issues.extend(
        _unknown_field_issues(payload, ZOTERO_SNAPSHOT_FIELDS, "Zotero snapshot")
    )
    if payload.get("schema_version") != ZOTERO_SNAPSHOT_SCHEMA:
        issues.append(f"schema_version must be {ZOTERO_SNAPSHOT_SCHEMA}")
    if not isinstance(payload.get("server_id"), str) or not _text(payload.get("server_id")):
        issues.append("server_id is required")
    for field in ("library_id", "library_version"):
        if not _nonnegative_integer(payload.get(field)):
            issues.append(f"{field} must be a non-negative integer")
    if not _date_time(payload.get("captured_at")):
        issues.append("captured_at must be an ISO date-time")
    items = payload.get("items")
    if not isinstance(items, list):
        issues.append("items must be a list")
        return issues
    source_ids: set[str] = set()
    item_keys: set[str] = set()
    citation_keys: set[str] = set()
    for number, item in enumerate(items, start=1):
        prefix = f"Zotero item {number}"
        if not isinstance(item, dict):
            issues.append(f"{prefix} must be an object")
            continue
        issues.extend(_unknown_field_issues(item, ZOTERO_ITEM_FIELDS, prefix))
        source_id = _text(item.get("source_id"))
        item_key = _text(item.get("item_key"))
        citation_key = _text(item.get("citation_key"))
        if not isinstance(item.get("source_id"), str) or not SOURCE_ID_RE.fullmatch(source_id):
            issues.append(f"{prefix} source_id is invalid")
        elif source_id in source_ids:
            issues.append(f"{prefix} source_id is duplicated")
        else:
            source_ids.add(source_id)
        if not isinstance(item.get("item_key"), str) or not ZOTERO_KEY_RE.fullmatch(item_key):
            issues.append(f"{prefix} item_key is invalid")
        elif item_key in item_keys:
            issues.append(f"{prefix} item_key is duplicated")
        else:
            item_keys.add(item_key)
        if not _nonnegative_integer(item.get("item_version")):
            issues.append(f"{prefix} item_version must be a non-negative integer")
        if not isinstance(item.get("citation_key"), str) or not citation_key:
            issues.append(f"{prefix} citation_key is required")
        elif citation_key in citation_keys:
            issues.append(f"{prefix} citation_key is duplicated")
        else:
            citation_keys.add(citation_key)
        identity_digest = _text(item.get("identity_digest"))
        if not isinstance(item.get("identity_digest"), str) or not SHA256_RE.fullmatch(identity_digest):
            issues.append(f"{prefix} identity_digest is invalid")
        if "doi" in item and not isinstance(item.get("doi"), str):
            issues.append(f"{prefix} doi must be a string")
        attachments = item.get("attachment_keys")
        if not isinstance(attachments, list):
            issues.append(f"{prefix} attachment_keys must be a list")
        elif len(attachments) != len(set(map(str, attachments))):
            issues.append(f"{prefix} attachment_keys must be unique")
        elif any(
            not isinstance(value, str) or not ZOTERO_KEY_RE.fullmatch(_text(value))
            for value in attachments
        ):
            issues.append(f"{prefix} attachment key is invalid")
        if SHA256_RE.fullmatch(identity_digest) and identity_digest.lower() != zotero_identity_digest(
            payload, item
        ):
            issues.append(f"{prefix} identity_digest does not match the frozen identity fields")
    return issues


def load_json_object(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Public read-only loader used by the integration gate."""

    return _json_object(path)
