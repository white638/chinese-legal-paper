"""Shared, standard-library-only helpers for method artifact validation."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    path: str


@dataclass(frozen=True)
class ValidationContext:
    base: Path
    schema_id: str
    contract: Mapping[str, Any]
    route: Mapping[str, Any]
    run: Mapping[str, Any]
    artifacts: Mapping[str, Mapping[str, Any]]
    path: str


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, Mapping):
        return "; ".join(
            f"{key}={text(item)}" for key, item in value.items() if text(item)
        )
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return "; ".join(text(item) for item in value if text(item))
    return str(value).strip()


def substantive(value: Any) -> bool:
    token = text(value)
    return bool(
        token
        and token.casefold() not in {"-", "--", "n/a", "na", "none", "null"}
        and "needs-review" not in token.casefold()
        and "待复核" not in token
        and "待确认" not in token
    )


def issue(code: str, message: str, path: str, severity: str = "ERROR") -> Finding:
    return Finding(code=code, severity=severity, message=message, path=path)


def require_mapping(
    findings: list[Finding], value: Any, path: str, code: str
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        findings.append(issue(code, f"{path} must be an object", path))
        return {}
    return value


def require_list(
    findings: list[Finding],
    value: Any,
    path: str,
    code: str,
    *,
    nonempty: bool = True,
) -> list[Any]:
    if not isinstance(value, list):
        findings.append(issue(code, f"{path} must be an array", path))
        return []
    if nonempty and not value:
        findings.append(issue(code, f"{path} must not be empty", path))
    return value


def require_fields(
    findings: list[Finding],
    value: Mapping[str, Any],
    fields: Iterable[str],
    path: str,
    code: str,
) -> None:
    for field in fields:
        if not substantive(value.get(field)):
            findings.append(
                issue(code, f"A substantive value is required for {path}.{field}", f"{path}.{field}")
            )


def artifact_ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {text(item).upper() for item in value if substantive(item)}


def artifact_path(
    ctx: ValidationContext,
    artifact_id: Any,
    path: str,
    findings: list[Finding],
    *,
    code: str = "ME.CONTRACT.ARTIFACT_UNRESOLVED",
) -> Path | None:
    identifier = text(artifact_id).upper()
    if not identifier:
        findings.append(issue(code, f"Artifact ID is required at {path}", path))
        return None
    declared_refs = artifact_ids(ctx.run.get("artifact_refs"))
    if identifier not in declared_refs:
        findings.append(
            issue(
                "ME.CONTRACT.ARTIFACT_REF_MISSING",
                f"{identifier} is used by the typed contract but absent from artifact_refs",
                path,
            )
        )
    artifact = ctx.artifacts.get(identifier)
    if not isinstance(artifact, Mapping):
        findings.append(issue(code, f"Unknown typed-contract artifact {identifier}", path))
        return None
    raw = text(artifact.get("path"))
    candidate = (ctx.base / raw).resolve()
    try:
        candidate.relative_to(ctx.base.resolve())
    except ValueError:
        findings.append(issue(code, f"Artifact path escapes the workspace: {raw}", path))
        return None
    if not candidate.is_file():
        findings.append(issue(code, f"Artifact file is missing: {raw}", path))
        return None
    declared_sha = text(artifact.get("sha256")).casefold()
    if re.fullmatch(r"[0-9a-f]{64}", declared_sha) is None:
        findings.append(
            issue(
                "ME.ARTIFACT.HASH_MISSING",
                f"Artifact {identifier} requires a valid SHA-256 binding",
                path,
            )
        )
        return None
    try:
        actual_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError as exc:
        findings.append(
            issue(
                "ME.CONTRACT.ARTIFACT_UNREADABLE",
                f"Artifact cannot be read for hash verification: {raw}: {exc}",
                path,
            )
        )
        return None
    if actual_sha != declared_sha:
        findings.append(
            issue(
                "ME.ARTIFACT.HASH_CHANGED",
                f"Artifact {identifier} content differs from its registered SHA-256",
                path,
            )
        )
        return None
    return candidate


def read_json_artifact(
    ctx: ValidationContext,
    artifact_id: Any,
    path: str,
    findings: list[Finding],
) -> Any:
    candidate = artifact_path(ctx, artifact_id, path, findings)
    if candidate is None:
        return None
    try:
        return json.loads(candidate.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(
            issue(
                "ME.CONTRACT.ARTIFACT_INVALID",
                f"Artifact is not valid JSON: {candidate.name}: {exc}",
                path,
            )
        )
        return None


def read_rows_artifact(
    ctx: ValidationContext,
    artifact_id: Any,
    path: str,
    findings: list[Finding],
) -> list[dict[str, Any]]:
    candidate = artifact_path(ctx, artifact_id, path, findings)
    if candidate is None:
        return []
    suffix = candidate.suffix.casefold()
    try:
        if suffix == ".csv":
            with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        if suffix == ".jsonl":
            rows: list[dict[str, Any]] = []
            for line_number, line in enumerate(
                candidate.read_text(encoding="utf-8-sig").splitlines(), start=1
            ):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise ValueError(f"line {line_number} is not an object")
                rows.append(dict(value))
            return rows
        if suffix == ".json":
            value = json.loads(candidate.read_text(encoding="utf-8-sig"))
            if isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
                return [dict(item) for item in value]
            if isinstance(value, Mapping) and isinstance(value.get("rows"), list):
                return [dict(item) for item in value["rows"] if isinstance(item, Mapping)]
            raise ValueError("JSON artifact must be an array of objects or contain a rows array")
        rows = []
        for token in candidate.read_text(encoding="utf-8-sig").splitlines():
            token = token.strip()
            if token:
                rows.append({"item_id": token})
        return rows
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        findings.append(
            issue(
                "ME.CONTRACT.ARTIFACT_INVALID",
                f"Cannot parse structured artifact {candidate.name}: {exc}",
                path,
            )
        )
        return []


def require_columns(
    findings: list[Finding],
    rows: Sequence[Mapping[str, Any]],
    columns: Iterable[str],
    path: str,
    code: str,
) -> None:
    required = set(columns)
    if not rows:
        findings.append(issue(code, f"Structured artifact contains no rows: {path}", path))
        return
    for index, row in enumerate(rows):
        missing = sorted(column for column in required if not substantive(row.get(column)))
        if missing:
            findings.append(
                issue(
                    code,
                    f"Row {index + 1} lacks required columns/values: {', '.join(missing)}",
                    path,
                )
            )
            return


def is_narrowed(value: Any) -> bool:
    if isinstance(value, Mapping):
        return text(value.get("status")) == "narrowed"
    token = text(value).casefold()
    return token.startswith(("narrowed:", "收窄:", "收窄：", "exploratory:", "探索性:"))


def finite_number(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def validate_independent_review_bundle(
    ctx: ValidationContext,
    *,
    primary_artifact_id: Any,
    review_artifact_id: Any,
    run_manifest_artifact_id: Any,
    disagreement_artifact_id: Any,
    expected_item_ids: set[str],
    prefix: str,
    code_prefix: str,
) -> list[Finding]:
    """Validate provenance separation and complete disposition for model research review."""

    findings: list[Finding] = []
    primary_id = text(primary_artifact_id).upper()
    review_id = text(review_artifact_id).upper()
    primary_path = artifact_path(
        ctx,
        primary_id,
        f"{prefix}.primary_artifact_id",
        findings,
    )
    review_path = artifact_path(
        ctx,
        review_id,
        f"{prefix}.independent_review_artifact_id",
        findings,
    )
    manifest = read_json_artifact(
        ctx,
        run_manifest_artifact_id,
        f"{prefix}.researcher_run_manifest_artifact_id",
        findings,
    )
    runs = manifest.get("runs") if isinstance(manifest, Mapping) else None
    if not isinstance(runs, list) or not runs:
        findings.append(
            issue(
                f"{code_prefix}.RUN_MANIFEST_INVALID",
                "Researcher-run manifest must contain a non-empty runs array",
                f"{prefix}.researcher_run_manifest_artifact_id",
            )
        )
        runs = []

    by_role: dict[str, Mapping[str, Any]] = {}
    run_ids: set[str] = set()
    context_ids: set[str] = set()
    output_ids: set[str] = set()
    for index, row in enumerate(runs):
        row_path = f"{prefix}.researcher_run_manifest_artifact_id.runs[{index}]"
        if not isinstance(row, Mapping):
            findings.append(
                issue(
                    f"{code_prefix}.RUN_MANIFEST_INVALID",
                    "Each researcher run must be an object",
                    row_path,
                )
            )
            continue
        require_fields(
            findings,
            row,
            (
                "role",
                "run_id",
                "context_id",
                "model_name",
                "model_revision",
                "completed_at",
                "system_prompt_sha256",
                "user_prompt_sha256",
                "output_artifact_id",
            ),
            row_path,
            f"{code_prefix}.RUN_MANIFEST_INVALID",
        )
        role = text(row.get("role"))
        run_id = text(row.get("run_id"))
        context_id = text(row.get("context_id"))
        output_id = text(row.get("output_artifact_id")).upper()
        if role in by_role:
            findings.append(
                issue(
                    f"{code_prefix}.RUN_MANIFEST_INVALID",
                    f"Researcher-run role {role!r} is duplicated",
                    row_path,
                )
            )
        elif role:
            by_role[role] = row
        if run_id in run_ids or context_id in context_ids or output_id in output_ids:
            findings.append(
                issue(
                    f"{code_prefix}.REVIEW_NOT_INDEPENDENT",
                    "Primary and review runs require distinct run, context, and output identities",
                    row_path,
                )
            )
        run_ids.add(run_id)
        context_ids.add(context_id)
        output_ids.add(output_id)
        artifact_path(ctx, output_id, f"{row_path}.output_artifact_id", findings)
        for digest_field in ("system_prompt_sha256", "user_prompt_sha256"):
            digest = text(row.get(digest_field))
            if len(digest) != 64 or any(
                character not in "0123456789abcdefABCDEF" for character in digest
            ):
                findings.append(
                    issue(
                        f"{code_prefix}.RUN_MANIFEST_INVALID",
                        f"{digest_field} must be a SHA-256 digest",
                        f"{row_path}.{digest_field}",
                    )
                )

    primary_run = by_role.get("primary")
    review_run = by_role.get("independent_review")
    if primary_run is None or review_run is None:
        findings.append(
            issue(
                f"{code_prefix}.RUN_MANIFEST_INVALID",
                "Researcher-run manifest requires exactly one primary and one independent_review run",
                f"{prefix}.researcher_run_manifest_artifact_id",
            )
        )
    else:
        if text(primary_run.get("output_artifact_id")).upper() != primary_id:
            findings.append(
                issue(
                    f"{code_prefix}.RUN_BINDING_MISMATCH",
                    "Primary run output must bind the primary analysis artifact",
                    f"{prefix}.researcher_run_manifest_artifact_id",
                )
            )
        if text(review_run.get("output_artifact_id")).upper() != review_id:
            findings.append(
                issue(
                    f"{code_prefix}.RUN_BINDING_MISMATCH",
                    "Independent review run output must bind the review artifact",
                    f"{prefix}.researcher_run_manifest_artifact_id",
                )
            )

    if primary_id == review_id:
        findings.append(
            issue(
                f"{code_prefix}.REVIEW_NOT_INDEPENDENT",
                "Independent review cannot reuse the primary output artifact",
                f"{prefix}.independent_review_artifact_id",
            )
        )
    if primary_path is not None and review_path is not None:
        primary_digest = text((ctx.artifacts.get(primary_id) or {}).get("sha256")).casefold()
        review_digest = text((ctx.artifacts.get(review_id) or {}).get("sha256")).casefold()
        if primary_digest and primary_digest == review_digest:
            findings.append(
                issue(
                    f"{code_prefix}.REVIEW_NOT_INDEPENDENT",
                    "Independent review and primary output cannot share the same content hash",
                    f"{prefix}.independent_review_artifact_id",
                )
            )

    review_payload = read_json_artifact(
        ctx,
        review_id,
        f"{prefix}.independent_review_artifact_id",
        findings,
    )
    if not isinstance(review_payload, Mapping):
        findings.append(
            issue(
                f"{code_prefix}.REVIEW_INVALID",
                "Independent review artifact must be a structured JSON object",
                f"{prefix}.independent_review_artifact_id",
            )
        )
        review_payload = {}
    require_fields(
        findings,
        review_payload,
        (
            "review_run_id",
            "primary_output_artifact_id",
            "reviewed_item_ids",
            "resolution_rule",
            "unresolved_count",
        ),
        f"{prefix}.independent_review_artifact_id",
        f"{code_prefix}.REVIEW_INVALID",
    )
    if review_run is not None and text(review_payload.get("review_run_id")) != text(
        review_run.get("run_id")
    ):
        findings.append(
            issue(
                f"{code_prefix}.RUN_BINDING_MISMATCH",
                "Review artifact must name the registered independent review run",
                f"{prefix}.independent_review_artifact_id",
            )
        )
    if text(review_payload.get("primary_output_artifact_id")).upper() != primary_id:
        findings.append(
            issue(
                f"{code_prefix}.RUN_BINDING_MISMATCH",
                "Review artifact must bind the registered primary output",
                f"{prefix}.independent_review_artifact_id",
            )
        )
    reviewed = review_payload.get("reviewed_item_ids")
    reviewed_ids = (
        {text(item) for item in reviewed if substantive(item)}
        if isinstance(reviewed, list)
        else set()
    )
    if reviewed_ids != expected_item_ids:
        findings.append(
            issue(
                f"{code_prefix}.REVIEW_COVERAGE",
                "Independent review IDs must exactly cover the primary analysis output",
                f"{prefix}.independent_review_artifact_id",
            )
        )
    if finite_number(review_payload.get("unresolved_count")) != 0:
        findings.append(
            issue(
                f"{code_prefix}.REVIEW_UNRESOLVED",
                "Every disagreement must be resolved or explicitly excluded",
                f"{prefix}.independent_review_artifact_id",
            )
        )

    disagreement_rows = read_rows_artifact(
        ctx,
        disagreement_artifact_id,
        f"{prefix}.disagreement_log_artifact_id",
        findings,
    )
    require_columns(
        findings,
        disagreement_rows,
        ("item_id", "status", "resolution", "evidence_locator"),
        f"{prefix}.disagreement_log_artifact_id",
        f"{code_prefix}.DISAGREEMENT_LOG_INVALID",
    )
    unresolved = [
        row
        for row in disagreement_rows
        if text(row.get("status")) not in {"resolved", "excluded", "no-disagreement"}
    ]
    if unresolved:
        findings.append(
            issue(
                f"{code_prefix}.REVIEW_UNRESOLVED",
                "Disagreement log contains unresolved items",
                f"{prefix}.disagreement_log_artifact_id",
            )
        )
    return findings
