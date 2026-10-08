"""Assemble a venue-configured submission package inside output staging."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from ..artifacts import sha256_file
from ..build.manuscript import ManuscriptSelection
from ..models import Finding, GateResult
from ..tools.word_guard import check_docx
from .policy import package_enabled, primary_delivery_relatives, submission_preview_relative
from .render import RenderOutcome, _file_record, _pdf_pages, _render_word_preview


PLACEHOLDER_RE = re.compile(
    r"(?:\bTODO\b|\bTBD\b|\bPLACEHOLDER\b|\bVERIFY\b|\bXXX\b|待填|待定|占位|待作者|待补)",
    re.IGNORECASE,
)


def _safe_required_names(config: dict[str, Any]) -> tuple[list[str], list[Finding]]:
    raw = config.get("submission_required_files")
    if not isinstance(raw, list) or not raw:
        return [], [Finding(
            "OUTPUT.SUBMISSION_REQUIREMENTS",
            "submission_package=journal requires an explicit non-empty submission_required_files list from the target venue",
        )]
    names: list[str] = []
    findings: list[Finding] = []
    for item in raw:
        token = str(item or "").strip().replace("\\", "/")
        path = Path(token)
        if not token or path.is_absolute() or ".." in path.parts:
            findings.append(Finding(
                "OUTPUT.SUBMISSION_PATH",
                f"unsafe submission required-file path: {token!r}",
            ))
        else:
            names.append(path.as_posix())
    return sorted(set(names)), findings


def _source_root(outdir: Path, config: dict[str, Any]) -> tuple[Path | None, Finding | None]:
    raw = str(config.get("submission_source_dir") or "").strip()
    if not raw:
        return None, Finding(
            "OUTPUT.SUBMISSION_SOURCE_REQUIRED",
            "submission_package=journal requires submission_source_dir",
        )
    root = (outdir / raw).resolve()
    try:
        root.relative_to(outdir.resolve())
    except ValueError:
        return None, Finding("OUTPUT.SUBMISSION_SOURCE_PATH", "submission_source_dir must stay inside the workspace", raw)
    if not root.is_dir():
        return None, Finding("OUTPUT.SUBMISSION_SOURCE_MISSING", "submission_source_dir is missing", raw)
    return root, None


def input_bindings(outdir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    if not package_enabled(config, "submission_package"):
        return []
    names, _ = _safe_required_names(config)
    root, _ = _source_root(outdir, config)
    records: list[dict[str, Any]] = []
    for name in names:
        path = root / name if root is not None else None
        records.append({
            "role": "submission_material",
            "path": f"{str(config.get('submission_source_dir') or '').strip().rstrip('/')}/{name}",
            "sha256": sha256_file(path) if path is not None and path.is_file() else "",
        })
    raw_contract = str(config.get("submission_contract") or "").strip()
    contract = (outdir / raw_contract).resolve() if raw_contract else None
    valid_contract = False
    if contract is not None:
        try:
            contract.relative_to(outdir.resolve())
            valid_contract = contract.is_file()
        except ValueError:
            valid_contract = False
    records.append({
        "role": "submission_contract",
        "path": raw_contract,
        "sha256": sha256_file(contract) if valid_contract and contract is not None else "",
    })
    return records


def _contract(outdir: Path, config: dict[str, Any], required_names: list[str]) -> tuple[dict[str, Any], list[Finding]]:
    raw = str(config.get("submission_contract") or "").strip()
    path = (outdir / raw).resolve() if raw else outdir / "__missing_submission_contract__"
    try:
        path.relative_to(outdir.resolve())
    except ValueError:
        return {}, [Finding("OUTPUT.SUBMISSION_CONTRACT_PATH", "submission_contract must stay inside the workspace", raw)]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}, [Finding("OUTPUT.SUBMISSION_CONTRACT_REQUIRED", "submission_contract must be a readable JSON contract", raw)]
    if not isinstance(payload, dict):
        return {}, [Finding("OUTPUT.SUBMISSION_CONTRACT_REQUIRED", "submission_contract must contain one JSON object", raw)]
    findings: list[Finding] = []
    if payload.get("schema_version") != "avereth-submission-contract/v1" or payload.get("status") != "confirmed":
        findings.append(Finding(
            "OUTPUT.SUBMISSION_CONTRACT_STATUS",
            "submission contract must use avereth-submission-contract/v1 with status=confirmed",
            raw,
        ))
    if sorted(str(item).replace("\\", "/") for item in payload.get("required_files") or []) != required_names:
        findings.append(Finding(
            "OUTPUT.SUBMISSION_CONTRACT_FILES",
            "submission contract required_files must exactly match submission_required_files",
            raw,
        ))
    target = str(config.get("target_name") or "").strip()
    if target and str(payload.get("target_name") or "").strip() != target:
        findings.append(Finding("OUTPUT.SUBMISSION_CONTRACT_TARGET", "submission contract target_name does not match workflow_config.json", raw))
    if not str(payload.get("confirmed_by") or "").strip():
        findings.append(Finding("OUTPUT.SUBMISSION_CONTRACT_CONFIRMATION", "submission contract requires a real confirmed_by identity", raw))
    language = str(payload.get("language") or "").strip().lower()
    if language not in {"en", "zh", "mixed"}:
        findings.append(Finding("OUTPUT.SUBMISSION_CONTRACT_LANGUAGE", "submission contract language must be en, zh, or mixed", raw))
    return payload, findings


def build_submission_package(
    outdir: Path,
    candidate_root: Path,
    canonical: ManuscriptSelection,
    config: dict[str, Any],
) -> RenderOutcome:
    if not package_enabled(config, "submission_package"):
        return RenderOutcome(GateResult.pass_("output"))
    if str(config.get("submission_package") or "").strip().lower() != "journal":
        return RenderOutcome(GateResult.fail("output", [Finding(
            "OUTPUT.SUBMISSION_MODE",
            "submission_package must be none or journal",
        )]))
    names, findings = _safe_required_names(config)
    source_root, root_issue = _source_root(outdir, config)
    if root_issue:
        findings.append(root_issue)
    if findings or source_root is None:
        return RenderOutcome(GateResult.blocked("output", findings))
    contract, contract_findings = _contract(outdir, config, names)
    if contract_findings:
        return RenderOutcome(GateResult.fail("output", contract_findings))

    materials: list[tuple[str, Path]] = []
    word_checks: list[str] = []
    contract_language = str(contract.get("language") or "auto").lower()
    word_language = contract_language if contract_language in {"en", "zh"} else "auto"
    for name in names:
        path = (source_root / name).resolve()
        try:
            path.relative_to(source_root)
        except ValueError:
            findings.append(Finding("OUTPUT.SUBMISSION_PATH", f"submission material escapes source directory: {name}"))
            continue
        if not path.is_file() or path.stat().st_size <= 0:
            findings.append(Finding("OUTPUT.SUBMISSION_FILE_MISSING", f"required submission material is missing or empty: {name}"))
            continue
        if path.suffix.lower() in {".md", ".txt", ".tex"}:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            if PLACEHOLDER_RE.search(text):
                findings.append(Finding("OUTPUT.SUBMISSION_PLACEHOLDER", f"submission material contains an unresolved placeholder: {name}"))
        elif path.suffix.lower() == ".docx":
            result = check_docx(
                path,
                1,
                language=word_language,
                citation_mode=str(config.get("citation_mode") or "numeric"),
                font_policy="skip",
                require_title=False,
            )
            if not result.ok:
                findings.append(Finding(
                    "OUTPUT.SUBMISSION_WORD_INVALID",
                    f"submission DOCX failed structural/placeholder Word checks: {name}: "
                    + "; ".join(result.findings[:4]),
                    name,
                ))
            else:
                word_checks.append(f"{name}: {result.text_length} text characters, {result.paragraph_count} paragraphs")
        else:
            findings.append(Finding(
                "OUTPUT.SUBMISSION_FORMAT",
                f"submission material must be .md, .txt, .tex, or a valid .docx file: {name}",
                name,
            ))
        materials.append((name, path))
    primary = primary_delivery_relatives(config, canonical.path)
    primary_paths = [(Path(relative).name, candidate_root / relative) for relative in primary]
    missing_primary = [name for name, path in primary_paths if not path.is_file()]
    if missing_primary:
        findings.append(Finding(
            "OUTPUT.SUBMISSION_MANUSCRIPT",
            "staged manuscript deliveries are missing: " + ", ".join(missing_primary),
        ))
    if findings:
        return RenderOutcome(GateResult.fail("output", findings))

    package = candidate_root / "submission_package"
    package.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    qa_records: list[dict[str, Any]] = []
    renderers: list[dict[str, Any]] = []
    for name, source in [*primary_paths, *materials]:
        destination = package / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        records.append(_file_record(candidate_root, destination))
        if name.lower().endswith(".docx") and source in {path for _, path in materials}:
            preview = candidate_root / submission_preview_relative(name)
            issue = _render_word_preview(destination, preview, renderers)
            if issue:
                status = GateResult.blocked if issue.code == "OUTPUT.RENDERER_MISSING" else GateResult.fail
                return RenderOutcome(status("output", [issue]), renderers=renderers)
            record = _file_record(candidate_root, preview)
            record["pages"] = _pdf_pages(preview)
            qa_records.append(record)
    manifest_path = package / "submission_manifest.json"
    manifest = {
        "schema_version": "avereth-submission-package/v1",
        "status": "PASS",
        "canonical_manuscript": canonical.as_dict(),
        "target_name": str(config.get("target_name") or ""),
        "required_files": names,
        "contract": {
            "path": str(config.get("submission_contract") or ""),
            "sha256": sha256_file(outdir / str(config.get("submission_contract") or "")),
            "language": contract.get("language"),
        },
        "artifacts": records,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    records.append(_file_record(candidate_root, manifest_path))
    report = candidate_root / "reports" / "submission_check.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Submission Package Check\n\nStatus: PASS\n\n"
        "Venue-declared files are present, non-empty, placeholder-free, and bound to the staged manuscript.\n\n"
        + ("## Submission Word Checks\n\n" + "\n".join(f"- {item}" for item in word_checks) + "\n" if word_checks else ""),
        encoding="utf-8",
    )
    return RenderOutcome(GateResult.pass_("output"), records, qa_records, renderers)
