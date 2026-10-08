"""Assemble a formal review-response or rebuttal package in output staging."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..artifacts import sha256_file
from ..build.manuscript import ManuscriptSelection
from ..models import Finding, GateResult
from .policy import primary_delivery_relatives
from .render import RenderOutcome, _file_record


PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bPLACEHOLDER\b|\bVERIFY\b|\bNEEDS[- ]?AUTHOR\b|"
    r"待填|待定|占位|待作者|待补|待核)",
    re.IGNORECASE,
)
COMMENT_ID_RE = re.compile(
    r"\b(?:CMT[-_]\d+|COMMENT[-_]\d+|R\d+[-_.]C?\d+|REV\d+[-_.]\d+)\b",
    re.IGNORECASE,
)


def mode(config: dict[str, Any]) -> str:
    value = str(config.get("response_package") or "none").strip().lower()
    return value if value in {"review_response", "rebuttal"} else "none"


def _safe_required_names(config: dict[str, Any]) -> tuple[list[str], list[Finding]]:
    raw = config.get("response_required_files")
    if not isinstance(raw, list) or not raw:
        return [], [Finding(
            "OUTPUT.RESPONSE_REQUIREMENTS",
            "a formal response package requires an explicit non-empty response_required_files list",
        )]
    names: list[str] = []
    findings: list[Finding] = []
    for item in raw:
        token = str(item or "").strip().replace("\\", "/")
        path = Path(token)
        if not token or path.is_absolute() or ".." in path.parts:
            findings.append(Finding("OUTPUT.RESPONSE_PATH", f"unsafe response required-file path: {token!r}"))
        else:
            names.append(path.as_posix())
    return sorted(set(names)), findings


def _source_root(outdir: Path, config: dict[str, Any]) -> tuple[Path | None, Finding | None]:
    raw = str(config.get("response_source_dir") or "").strip()
    if not raw:
        return None, Finding("OUTPUT.RESPONSE_SOURCE_REQUIRED", "formal response packaging requires response_source_dir")
    root = (outdir / raw).resolve()
    try:
        root.relative_to(outdir.resolve())
    except ValueError:
        return None, Finding("OUTPUT.RESPONSE_SOURCE_PATH", "response_source_dir must stay inside the workspace", raw)
    if not root.is_dir():
        return None, Finding("OUTPUT.RESPONSE_SOURCE_MISSING", "response_source_dir is missing", raw)
    return root, None


def input_bindings(outdir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    active_mode = mode(config)
    if active_mode == "none":
        return []
    names, _ = _safe_required_names(config)
    root, _ = _source_root(outdir, config)
    records: list[dict[str, Any]] = []
    for name in names:
        path = root / name if root is not None else None
        records.append({
            "role": active_mode,
            "path": f"{str(config.get('response_source_dir') or '').strip().rstrip('/')}/{name}",
            "sha256": sha256_file(path) if path is not None and path.is_file() else "",
        })
    confirmation = outdir / "review_comment_confirmation.json"
    records.append({
        "role": "review_comment_confirmation",
        "path": confirmation.name,
        "sha256": sha256_file(confirmation) if confirmation.is_file() else "",
    })
    raw_review = str(config.get("response_review_source") or "").strip()
    review = (outdir / raw_review).resolve() if raw_review else None
    valid_review = False
    if review is not None:
        try:
            review.relative_to(outdir.resolve())
            valid_review = review.is_file()
        except ValueError:
            valid_review = False
    records.append({
        "role": "review_source",
        "path": raw_review,
        "sha256": sha256_file(review) if valid_review and review is not None else "",
    })
    return records


def build_response_package(
    outdir: Path,
    candidate_root: Path,
    canonical: ManuscriptSelection,
    config: dict[str, Any],
) -> RenderOutcome:
    active_mode = mode(config)
    if str(config.get("response_package") or "none").strip().lower() not in {
        "", "none", "review_response", "rebuttal"
    }:
        return RenderOutcome(GateResult.fail("output", [Finding(
            "OUTPUT.RESPONSE_MODE",
            "response_package must be none, review_response, or rebuttal",
        )]))
    if active_mode == "none":
        return RenderOutcome(GateResult.pass_("output"))
    if str(config.get("task_profile") or "").strip().lower().replace("-", "_") != "manuscript_revision":
        return RenderOutcome(GateResult.fail("output", [Finding(
            "OUTPUT.RESPONSE_PROFILE",
            "formal response/rebuttal packaging is allowed only for task_profile=manuscript_revision",
        )]))
    names, findings = _safe_required_names(config)
    source_root, root_issue = _source_root(outdir, config)
    if root_issue:
        findings.append(root_issue)
    if findings or source_root is None:
        return RenderOutcome(GateResult.blocked("output", findings))

    materials: list[tuple[str, Path]] = []
    combined_text: list[str] = []
    for name in names:
        path = (source_root / name).resolve()
        try:
            path.relative_to(source_root)
        except ValueError:
            findings.append(Finding("OUTPUT.RESPONSE_PATH", f"response material escapes source directory: {name}"))
            continue
        if not path.is_file() or path.stat().st_size <= 0:
            findings.append(Finding("OUTPUT.RESPONSE_FILE_MISSING", f"required response material is missing or empty: {name}"))
            continue
        if path.suffix.lower() not in {".md", ".txt", ".json", ".csv"}:
            findings.append(Finding("OUTPUT.RESPONSE_FORMAT", f"response material must be a reviewable text or structured-data file: {name}"))
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if PLACEHOLDER_RE.search(text):
            findings.append(Finding("OUTPUT.RESPONSE_PLACEHOLDER", f"response material contains an unresolved author action or placeholder: {name}"))
        combined_text.append(text)
        materials.append((name, path))
    comment_ids = sorted({match.group(0).upper() for text in combined_text for match in COMMENT_ID_RE.finditer(text)})
    if not comment_ids:
        findings.append(Finding(
            "OUTPUT.RESPONSE_COMMENT_IDS",
            "formal response materials must use stable review-comment IDs",
        ))
    raw_review = str(config.get("response_review_source") or "").strip()
    review_source = (outdir / raw_review).resolve() if raw_review else outdir / "__missing_review_source__"
    try:
        review_source.relative_to(outdir.resolve())
    except ValueError:
        findings.append(Finding("OUTPUT.RESPONSE_REVIEW_PATH", "response_review_source must stay inside the workspace", raw_review))
        review_text = ""
    else:
        try:
            review_text = review_source.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            findings.append(Finding("OUTPUT.RESPONSE_REVIEW_SOURCE", "response_review_source is missing or unreadable", raw_review))
            review_text = ""
    review_comment_ids = sorted({match.group(0).upper() for match in COMMENT_ID_RE.finditer(review_text)})
    if review_comment_ids != comment_ids:
        findings.append(Finding(
            "OUTPUT.RESPONSE_REVIEW_COVERAGE",
            "formal response materials must cover the exact stable comment-ID set in response_review_source",
            raw_review,
        ))
    confirmation = outdir / "review_comment_confirmation.json"
    try:
        confirmation_payload = json.loads(confirmation.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        confirmation_payload = {}
    if (
        confirmation_payload.get("schema_version") != "avereth-review-comment-confirmation/v1"
        or confirmation_payload.get("status") != "confirmed"
        or not str(confirmation_payload.get("confirmed_by") or "").strip()
        or sorted(str(item).upper() for item in confirmation_payload.get("comment_ids") or []) != comment_ids
        or confirmation_payload.get("review_source_sha256") != (sha256_file(review_source) if review_source.is_file() else "")
    ):
        findings.append(Finding(
            "OUTPUT.RESPONSE_CONFIRMATION",
            "review_comment_confirmation.json must use avereth-review-comment-confirmation/v1, name the real confirmer, and confirm the exact stable comment-ID set",
            confirmation.name,
        ))
    primary = primary_delivery_relatives(config, canonical.path)
    primary_paths = [(Path(relative).name, candidate_root / relative) for relative in primary]
    if any(not path.is_file() for _, path in primary_paths):
        findings.append(Finding("OUTPUT.RESPONSE_MANUSCRIPT", "formal response package requires the current staged revised manuscript delivery"))
    if findings:
        return RenderOutcome(GateResult.fail("output", findings))

    package = candidate_root / active_mode
    package.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for name, source in [*primary_paths, *materials]:
        destination = package / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(_file_record(candidate_root, destination))
    manifest_path = package / "response_manifest.json"
    manifest = {
        "schema_version": "avereth-response-package/v1",
        "status": "PASS",
        "mode": active_mode,
        "canonical_manuscript": canonical.as_dict(),
        "review_comment_confirmation": {
            "path": confirmation.name,
            "sha256": sha256_file(confirmation),
        },
        "review_source": {
            "path": raw_review,
            "sha256": sha256_file(review_source),
        },
        "comment_ids": comment_ids,
        "artifacts": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records.append(_file_record(candidate_root, manifest_path))
    report = candidate_root / "reports" / "respond_check.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Formal Response Package Check\n\nStatus: PASS\n\n"
        "Stable comment IDs, author confirmation, zero placeholders, and revised-manuscript binding passed.\n",
        encoding="utf-8",
    )
    return RenderOutcome(GateResult.pass_("output"), records)
