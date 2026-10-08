"""Two-phase staged rendering, visual QA, publication, and output manifest."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..artifacts import report_passed, sha256_file
from ..build.manuscript import ManuscriptSelectionError, select_manuscript
from ..config import read_config
from ..models import Finding, GateResult
from ..receipts import AUDIT_SCHEMA, OUTPUT_MD_REL, OUTPUT_REL, read_receipt
from ..version import VERSION
from .guards import required_report_relatives, run_guards
from .policy import delivery_relatives, preview_relatives
from .render import RenderOutcome, render_candidate
from .response import build_response_package, input_bindings as response_input_bindings
from .submission import build_submission_package, input_bindings as submission_input_bindings
from .translation import build_translation_package, input_bindings as translation_input_bindings


CANDIDATE_DIR = Path(".avereth-output-candidate")
CANDIDATE_MANIFEST_REL = CANDIDATE_DIR / "candidate_manifest.json"
CANDIDATE_QA_REL = CANDIDATE_DIR / "render_qa.json"
QA_REL = Path("render_qa.json")
OUTPUT_RUN_REL = Path("output_run.json")
FINAL_MANIFEST_JSON_REL = Path("final_artifact_manifest.json")
FINAL_MANIFEST_MD_REL = Path("final_artifact_manifest.md")
CANDIDATE_SCHEMA = "avereth-output-candidate/v1"
QA_SCHEMA = "avereth-render-qa/v1"
OUTPUT_RUN_SCHEMA = "avereth-output-run/v1"
FINAL_MANIFEST_SCHEMA = "avereth-final-artifact-manifest/v1"
TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
MANAGED_PACKAGE_ROOTS = (
    Path("translation_zh"),
    Path("submission_package"),
    Path("review_response"),
    Path("rebuttal"),
    Path("render_qa"),
)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _digest_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _candidate_root(outdir: Path) -> Path:
    return outdir / CANDIDATE_DIR


def _reset_candidate(outdir: Path) -> Path:
    root = _candidate_root(outdir)
    resolved = root.resolve()
    if resolved.parent != outdir.resolve() or resolved.name != CANDIDATE_DIR.name:
        raise RuntimeError("refusing to reset an unexpected output candidate path")
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    return root


def _implementation_binding() -> dict[str, str]:
    bindings = {
        name: sha256_file(Path(__file__).with_name(name))
        for name in (
            "policy.py", "render.py", "guards.py", "run.py",
            "translation.py", "submission.py", "response.py",
        )
    }
    for name in ("latex_guard.py", "section_economy_check.py", "word_guard.py"):
        path = TOOLS_DIR / name
        bindings[f"tools/{name}"] = sha256_file(path) if path.is_file() else ""
    return bindings


def _output_policy(outdir: Path, config: dict[str, Any], canonical: Path) -> dict[str, Any]:
    values = {
        key: config.get(key)
        for key in (
            "output_language",
            "word_output",
            "pdf_output",
            "word_font_policy",
            "citation_mode",
            "max_sections",
            "translation_package",
            "submission_package",
            "target_name",
            "submission_source_dir",
            "submission_contract",
            "submission_required_files",
            "response_package",
            "response_source_dir",
            "response_review_source",
            "response_required_files",
            "translation_source",
            "translation_coverage_source",
        )
    }
    return {
        "deliveries": sorted(delivery_relatives(config, canonical)),
        "previews": sorted(preview_relatives(config)),
        "package_inputs": sorted(
            [
                *translation_input_bindings(outdir, config),
                *submission_input_bindings(outdir, config),
                *response_input_bindings(outdir, config),
            ],
            key=lambda item: (str(item.get("role") or ""), str(item.get("path") or "")),
        ),
        "config": values,
        "implementation": _implementation_binding(),
    }


def _candidate_current(
    outdir: Path,
    canonical: dict[str, str],
    policy: dict[str, Any],
    audit_receipt_sha256: str,
) -> dict[str, Any]:
    payload = _json(outdir / CANDIDATE_MANIFEST_REL)
    if payload.get("schema_version") != CANDIDATE_SCHEMA or payload.get("framework_version") != VERSION:
        return {}
    if payload.get("canonical_manuscript") != canonical:
        return {}
    if payload.get("output_policy") != policy:
        return {}
    if payload.get("audit_receipt_sha256") != audit_receipt_sha256:
        return {}
    root = _candidate_root(outdir)
    records = payload.get("deliveries") or []
    qa_records = payload.get("qa_artifacts") or []
    if not isinstance(records, list) or not records or not isinstance(qa_records, list):
        return {}
    actual_delivery_paths = sorted(
        str(record.get("path") or "") for record in records if isinstance(record, dict)
    )
    if actual_delivery_paths != policy.get("deliveries"):
        return {}
    for record in [*records, *qa_records]:
        if not isinstance(record, dict):
            return {}
        relative = str(record.get("path") or "")
        path = root / relative
        try:
            path.resolve().relative_to(root.resolve())
        except ValueError:
            return {}
        if not path.is_file() or sha256_file(path) != record.get("sha256"):
            return {}
    qa_paths = sorted(
        str(record.get("path") or "")
        for record in qa_records
        if isinstance(record, dict)
    )
    if qa_paths != policy.get("previews"):
        return {}
    for preview in qa_records:
        if not isinstance(preview, dict) or not isinstance(preview.get("pages"), int) or preview.get("pages", 0) <= 0:
            return {}
    if not _review_targets(payload):
        return {}
    return payload


def _review_targets(candidate: dict[str, Any]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for record in [*(candidate.get("deliveries") or []), *(candidate.get("qa_artifacts") or [])]:
        if isinstance(record, dict) and str(record.get("path") or "").lower().endswith(".pdf"):
            targets.append({key: record.get(key) for key in ("path", "sha256", "size", "pages") if record.get(key) is not None})
    return targets


def record_visual_qa(
    outdir: Path,
    *,
    reviewer_mode: str,
    reviewed_by: str = "",
    notes: str = "",
) -> tuple[dict[str, Any], int]:
    """Record an explicit declaration only after the candidate was visually read."""

    active = read_config(outdir).payload
    audit_path = outdir / "audit_receipt.json"
    try:
        selection = select_manuscript(outdir, active)
    except ManuscriptSelectionError as exc:
        return {"status": "BLOCKED", "issues": [str(exc)]}, 2
    if not audit_path.is_file():
        return {"status": "BLOCKED", "issues": ["a current audit receipt is required"]}, 2
    canonical = selection.as_dict()
    policy = _output_policy(outdir, active, selection.path)
    candidate = _candidate_current(outdir, canonical, policy, sha256_file(audit_path))
    targets = _review_targets(candidate)
    if not candidate or not targets:
        return {"status": "BLOCKED", "issues": ["render a current candidate before recording QA"]}, 2
    if reviewer_mode not in {"human", "single_agent", "independent"}:
        return {"status": "BLOCKED", "issues": ["reviewer_mode must be human, single_agent, or independent"]}, 2
    if not reviewed_by.strip():
        return {"status": "BLOCKED", "issues": ["visual QA requires the actual reviewer or thread identity"]}, 2
    payload: dict[str, Any] = {
        "schema_version": QA_SCHEMA,
        "framework_version": VERSION,
        "status": "PASS",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_mode": reviewer_mode,
        "reviewed_by": reviewed_by,
        "candidate_manifest_digest": _digest_json(candidate),
        "reviewed_targets": targets,
        "pages_reviewed": "all",
        "notes": notes,
    }
    _atomic_json(outdir / CANDIDATE_QA_REL, payload)
    return payload, 0


def _qa_payload_findings(
    payload: dict[str, Any],
    *,
    candidate_digest: str,
    review_targets: list[dict[str, Any]],
    relative_path: str,
) -> list[Finding]:
    findings: list[Finding] = []
    if (
        payload.get("schema_version") != QA_SCHEMA
        or payload.get("framework_version") != VERSION
        or payload.get("status") != "PASS"
    ):
        findings.append(Finding(
            "OUTPUT.QA_REQUIRED",
            "render QA must be a current v6 PASS record",
            relative_path,
        ))
        return findings
    if payload.get("reviewer_mode") not in {"human", "single_agent", "independent"}:
        findings.append(Finding("OUTPUT.QA_IDENTITY", "render QA requires a declared reviewer mode", relative_path))
    if not str(payload.get("reviewed_by") or "").strip():
        findings.append(Finding("OUTPUT.QA_IDENTITY", "render QA requires the actual reviewer or thread identity", relative_path))
    try:
        reviewed_at = datetime.fromisoformat(str(payload.get("reviewed_at") or "").replace("Z", "+00:00"))
        valid_time = reviewed_at.tzinfo is not None
    except ValueError:
        valid_time = False
    if not valid_time:
        findings.append(Finding("OUTPUT.QA_TIME", "render QA requires a parseable timezone-aware reviewed_at timestamp", relative_path))
    if payload.get("candidate_manifest_digest") != candidate_digest:
        findings.append(Finding("OUTPUT.QA_STALE", "render QA does not bind the current candidate", relative_path))
    if not review_targets:
        findings.append(Finding("OUTPUT.QA_TARGETS", "the output route has no rendered PDF target for full-page visual review"))
    elif payload.get("reviewed_targets") != review_targets or payload.get("pages_reviewed") != "all":
        findings.append(Finding("OUTPUT.QA_INCOMPLETE", "render QA must cover every page of every rendered review target", relative_path))
    return findings


def _qa_status(outdir: Path, candidate: dict[str, Any]) -> GateResult:
    payload = _json(outdir / CANDIDATE_QA_REL)
    findings = _qa_payload_findings(
        payload,
        candidate_digest=_digest_json(candidate),
        review_targets=_review_targets(candidate),
        relative_path=CANDIDATE_QA_REL.as_posix(),
    )
    return GateResult.blocked("output", findings) if findings else GateResult.pass_("output")


def _write_run(outdir: Path, status: str, *, findings: list[Finding] | None = None, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "schema_version": OUTPUT_RUN_SCHEMA,
        "framework_version": VERSION,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "findings": [item.as_dict() for item in findings or []],
        **extra,
    }
    _atomic_json(outdir / OUTPUT_RUN_REL, payload)


def _publish_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    shutil.copy2(source, temporary)
    temporary.replace(destination)


def _safe_managed_relative(outdir: Path, raw: object) -> str | None:
    relative = str(raw or "").strip().replace("\\", "/")
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts:
        return None
    allowed = {
        "final_paper/paper.docx",
        "final_paper/paper.zh.docx",
        "final_paper/paper.pdf",
        "word_report.md",
        "word_report.zh.md",
        "latex_guard.md",
        "section_economy_check.md",
        "translation_guard.md",
        "translation_word_report.md",
        "submission_check.md",
        "respond_check.md",
        "render_qa.json",
    }
    if relative not in allowed and not any(path.parts and path.parts[0] == root.name for root in MANAGED_PACKAGE_ROOTS):
        return None
    try:
        (outdir / path).resolve().relative_to(outdir.resolve())
    except ValueError:
        return None
    return path.as_posix()


def _previous_managed_paths(outdir: Path) -> set[str]:
    previous = _json(outdir / FINAL_MANIFEST_JSON_REL)
    records = previous.get("artifacts") if isinstance(previous.get("artifacts"), list) else []
    paths: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        relative = _safe_managed_relative(outdir, record.get("path"))
        if relative:
            paths.add(relative)
    return paths


def _managed_root_files(outdir: Path) -> set[str]:
    paths: set[str] = set()
    for relative_root in MANAGED_PACKAGE_ROOTS:
        root = outdir / relative_root
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if path.is_file():
                paths.add(path.relative_to(outdir).as_posix())
    return paths


def _manifest_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Final Artifact Manifest",
        "",
        "Status: PASS",
        "",
        f"Canonical manuscript: `{payload['canonical_manuscript']['path']}`",
        "",
        "## Published Artifacts",
        "",
        "| Path | SHA256 | Bytes |",
        "|---|---|---:|",
    ]
    for item in payload.get("artifacts") or []:
        lines.append(f"| `{item['path']}` | `{item['sha256']}` | {item['size']} |")
    lines.append("")
    return "\n".join(lines)


def _publish(
    outdir: Path,
    candidate: dict[str, Any],
    canonical: dict[str, str],
    audit_receipt: dict[str, Any],
    *,
    config: dict[str, Any],
    required_guard_reports: tuple[str, ...],
    receipt_signer: Callable[[], bool],
) -> dict[str, Any]:
    root = _candidate_root(outdir)
    sources: dict[str, Path] = {}
    for record in [*(candidate.get("deliveries") or []), *(candidate.get("qa_artifacts") or [])]:
        relative = str(record["path"])
        sources[relative] = root / relative
    reports = root / "reports"
    for relative in required_guard_reports:
        source = reports / relative
        if not source.is_file():
            raise RuntimeError(f"required staged guard report is missing: {relative}")
        if not report_passed(source):
            raise RuntimeError(f"required staged guard report is not PASS: {relative}")
        sources[relative] = source
    candidate_qa = outdir / CANDIDATE_QA_REL
    qa_findings = _qa_payload_findings(
        _json(candidate_qa),
        candidate_digest=_digest_json(candidate),
        review_targets=_review_targets(candidate),
        relative_path=CANDIDATE_QA_REL.as_posix(),
    )
    if qa_findings:
        raise RuntimeError("staged render QA is invalid before publication: " + "; ".join(item.message for item in qa_findings))
    sources[QA_REL.as_posix()] = candidate_qa
    published = [
        {"path": relative, "sha256": sha256_file(source), "size": source.stat().st_size}
        for relative, source in sorted(sources.items())
    ]
    candidate_digest = _digest_json(candidate)
    candidate_binding = {
        "deliveries": candidate.get("deliveries") or [],
        "qa_artifacts": candidate.get("qa_artifacts") or [],
        "review_targets": _review_targets(candidate),
    }
    payload: dict[str, Any] = {
        "schema_version": FINAL_MANIFEST_SCHEMA,
        "framework_version": VERSION,
        "status": "PASS",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "canonical_manuscript": canonical,
        "audit_receipt_sha256": sha256_file(outdir / "audit_receipt.json"),
        "renderers": candidate.get("renderers") or [],
        "artifacts": sorted(published, key=lambda item: item["path"]),
        "output_policy": candidate.get("output_policy"),
        "action_implementation": _implementation_binding(),
        "candidate_manifest_digest": candidate_digest,
        "candidate_binding": candidate_binding,
        "required_guard_reports": list(required_guard_reports),
    }
    metadata_paths = (
        FINAL_MANIFEST_JSON_REL,
        FINAL_MANIFEST_MD_REL,
        Path("output_artifact_check.md"),
        OUTPUT_RUN_REL,
        OUTPUT_REL,
        OUTPUT_MD_REL,
    )
    managed_paths = {
        "final_paper/paper.docx",
        "final_paper/paper.zh.docx",
        "final_paper/paper.pdf",
        "render_qa/word_preview.pdf",
        "word_report.md",
        "word_report.zh.md",
        "latex_guard.md",
        "section_economy_check.md",
        "translation_guard.md",
        "translation_word_report.md",
        "submission_check.md",
        "respond_check.md",
        "render_qa.json",
    }
    managed_paths.update(_previous_managed_paths(outdir))
    previous_paths = {relative for relative in managed_paths if (outdir / relative).is_file()}
    desired_paths = set(sources)
    unknown = sorted(_managed_root_files(outdir) - previous_paths - desired_paths)
    if unknown:
        raise RuntimeError(
            "unmanaged files exist in reserved output roots; move or register them before publishing: "
            + ", ".join(unknown)
        )
    touched = sorted(desired_paths | previous_paths | {item.as_posix() for item in metadata_paths})
    with tempfile.TemporaryDirectory(prefix="avereth-output-backup-") as raw_backup:
        backup = Path(raw_backup)
        existed: set[str] = set()
        for relative in touched:
            destination = outdir / relative
            if destination.is_file():
                existed.add(relative)
                saved = backup / relative
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
        try:
            for relative, source in sorted(sources.items()):
                _publish_file(source, outdir / relative)
            for relative in sorted(previous_paths - desired_paths):
                stale = outdir / relative
                if stale.is_file():
                    stale.unlink()
            _atomic_json(outdir / FINAL_MANIFEST_JSON_REL, payload)
            _atomic_text(outdir / FINAL_MANIFEST_MD_REL, _manifest_markdown(payload))
            _atomic_text(
                outdir / "output_artifact_check.md",
                "# Output Artifact Check\n\nStatus: PASS\n\n"
                f"Published artifacts: {len(published)}\n",
            )
            _write_run(
                outdir,
                "PASS",
                candidate_manifest_digest=candidate_digest,
                final_manifest_sha256=sha256_file(outdir / FINAL_MANIFEST_JSON_REL),
            )
            completion = validate_completion(outdir, config=config)
            if not completion.ok:
                detail = "; ".join(
                    f"{finding.code}: {finding.message}" for finding in completion.findings
                )
                raise RuntimeError(f"published output failed durable completion validation: {detail}")
            if not receipt_signer():
                raise RuntimeError("output receipt signer rejected the published output")
        except Exception as exc:
            for relative in reversed(touched):
                destination = outdir / relative
                saved = backup / relative
                if relative in existed:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(saved, destination)
                elif destination.is_file():
                    destination.unlink()
            raise RuntimeError(f"transactional output publication failed and was rolled back: {exc}") from exc
    return payload


def run_output(
    outdir: Path,
    *,
    config: dict[str, Any] | None = None,
    prepublish_validator: Callable[[], tuple[bool, str]] | None = None,
    receipt_signer: Callable[[], bool] | None = None,
) -> GateResult:
    active = dict(config if config is not None else read_config(outdir).payload)
    if prepublish_validator is None or receipt_signer is None:
        return GateResult.blocked(
            "output",
            [
                Finding(
                    "OUTPUT.CONTROLLER_REQUIRED",
                    "run the output stage through avereth.py so the controller can revalidate the audit and sign inside one publication transaction",
                )
            ],
        )
    audit = read_receipt(outdir, "audit")
    if audit.legacy or audit.payload.get("schema_version") != AUDIT_SCHEMA or audit.payload.get("status") != "PASS":
        return GateResult.blocked("output", [Finding("OUTPUT.AUDIT_REQUIRED", "a current v6 PASS audit receipt is required")])
    try:
        selection = select_manuscript(outdir, active)
    except ManuscriptSelectionError as exc:
        return GateResult.fail("output", [Finding("OUTPUT.CANONICAL", str(exc))])
    canonical = selection.as_dict()
    if audit.payload.get("canonical_manuscript") != canonical:
        return GateResult.fail("output", [Finding("OUTPUT.AUDIT_SOURCE_CHANGED", "canonical manuscript no longer matches the audit receipt")])
    audit_path = outdir / "audit_receipt.json"
    audit_sha256 = sha256_file(audit_path)
    policy = _output_policy(outdir, active, selection.path)

    candidate = _candidate_current(outdir, canonical, policy, audit_sha256)
    if not candidate:
        root = _reset_candidate(outdir)
        outcome: RenderOutcome = render_candidate(outdir, root, selection, active)
        if not outcome.result.ok:
            _write_run(outdir, outcome.result.status.value.upper(), findings=list(outcome.result.findings))
            return outcome.result
        for builder in (
            build_translation_package,
            build_submission_package,
            build_response_package,
        ):
            package_outcome = builder(outdir, root, selection, active)
            if not package_outcome.result.ok:
                _write_run(
                    outdir,
                    package_outcome.result.status.value.upper(),
                    findings=list(package_outcome.result.findings),
                )
                return package_outcome.result
            outcome.deliveries.extend(package_outcome.deliveries)
            outcome.qa_artifacts.extend(package_outcome.qa_artifacts)
            outcome.renderers.extend(package_outcome.renderers)
        candidate = {
            "schema_version": CANDIDATE_SCHEMA,
            "framework_version": VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "canonical_manuscript": canonical,
            "audit_receipt_sha256": audit_sha256,
            "output_policy": policy,
            "deliveries": outcome.deliveries,
            "qa_artifacts": outcome.qa_artifacts,
            "renderers": outcome.renderers,
        }
        _atomic_json(outdir / CANDIDATE_MANIFEST_REL, candidate)
        finding = Finding(
            "OUTPUT.QA_REQUIRED",
            "rendered candidates are ready; visually inspect every page, then record render QA and rerun output",
            CANDIDATE_DIR.as_posix(),
        )
        _write_run(outdir, "BLOCKED", findings=[finding], candidate_manifest_digest=_digest_json(candidate))
        return GateResult.blocked("output", [finding])

    qa = _qa_status(outdir, candidate)
    if not qa.ok:
        _write_run(outdir, "BLOCKED", findings=list(qa.findings), candidate_manifest_digest=_digest_json(candidate))
        return qa
    guards = run_guards(
        outdir,
        config=active,
        canonical=selection,
        delivery_root=_candidate_root(outdir),
        report_root=_candidate_root(outdir) / "reports",
    )
    if not guards.ok:
        _write_run(outdir, guards.status.value.upper(), findings=list(guards.findings), candidate_manifest_digest=_digest_json(candidate))
        return guards
    audit_current, audit_issue = prepublish_validator()
    if not audit_current:
        finding = Finding(
            "OUTPUT.AUDIT_CHANGED",
            f"audit became invalid before publication: {audit_issue}",
        )
        _write_run(outdir, "FAIL", findings=[finding])
        return GateResult.fail("output", [finding])
    candidate = _candidate_current(outdir, canonical, policy, audit_sha256)
    if not candidate or not audit_path.is_file() or sha256_file(audit_path) != audit_sha256:
        finding = Finding(
            "OUTPUT.INPUT_CHANGED",
            "audit receipt, output policy, or staged delivery changed before publication",
        )
        _write_run(outdir, "FAIL", findings=[finding])
        return GateResult.fail("output", [finding])
    required_reports = required_report_relatives(active, selection.path)
    manifest = _publish(
        outdir,
        candidate,
        canonical,
        audit.payload,
        config=active,
        required_guard_reports=required_reports,
        receipt_signer=receipt_signer,
    )
    return GateResult.pass_(
        "output",
        generated=(OUTPUT_RUN_REL.as_posix(), FINAL_MANIFEST_JSON_REL.as_posix(), FINAL_MANIFEST_MD_REL.as_posix()),
        semantic_digest=_digest_json(manifest),
    )


def validate_completion(
    outdir: Path,
    *,
    config: dict[str, Any] | None = None,
) -> GateResult:
    """Validate only durable published state; scratch candidates may be deleted."""

    active = dict(config if config is not None else read_config(outdir).payload)
    findings: list[Finding] = []
    audit_path = outdir / "audit_receipt.json"
    audit = read_receipt(outdir, "audit")
    if (
        not audit_path.is_file()
        or audit.legacy
        or audit.payload.get("schema_version") != AUDIT_SCHEMA
        or audit.payload.get("status") != "PASS"
    ):
        return GateResult.fail(
            "output",
            [Finding("OUTPUT.AUDIT_REQUIRED", "a current v6 PASS audit_receipt.json is required")],
        )
    try:
        selection = select_manuscript(outdir, active)
    except ManuscriptSelectionError as exc:
        return GateResult.fail("output", [Finding("OUTPUT.CANONICAL", str(exc))])
    canonical = selection.as_dict()
    audit_sha256 = sha256_file(audit_path)
    policy = _output_policy(outdir, active, selection.path)
    required_reports = list(required_report_relatives(active, selection.path))

    run_payload = _json(outdir / OUTPUT_RUN_REL)
    manifest = _json(outdir / FINAL_MANIFEST_JSON_REL)
    qa_payload = _json(outdir / QA_REL)
    if run_payload.get("schema_version") != OUTPUT_RUN_SCHEMA or run_payload.get("status") != "PASS":
        findings.append(Finding("OUTPUT.RUN_INVALID", "output_run.json must be a v6 PASS run", OUTPUT_RUN_REL.as_posix()))
    if manifest.get("schema_version") != FINAL_MANIFEST_SCHEMA or manifest.get("status") != "PASS":
        findings.append(
            Finding("OUTPUT.MANIFEST_INVALID", "final_artifact_manifest.json must be a v6 PASS manifest", FINAL_MANIFEST_JSON_REL.as_posix())
        )
    if run_payload.get("framework_version") != VERSION or manifest.get("framework_version") != VERSION:
        findings.append(Finding("OUTPUT.VERSION_CHANGED", "output run and manifest must use the current engine version"))
    if manifest.get("canonical_manuscript") != canonical:
        findings.append(Finding("OUTPUT.MANIFEST_SOURCE_CHANGED", "final manifest does not bind the current canonical manuscript"))
    if manifest.get("audit_receipt_sha256") != audit_sha256:
        findings.append(Finding("OUTPUT.MANIFEST_AUDIT_CHANGED", "final manifest does not bind the current audit receipt"))
    if manifest.get("output_policy") != policy:
        findings.append(Finding("OUTPUT.MANIFEST_POLICY_CHANGED", "final manifest does not bind the current output policy"))
    if manifest.get("action_implementation") != _implementation_binding():
        findings.append(Finding("OUTPUT.IMPLEMENTATION_CHANGED", "output implementation changed after publication"))
    if manifest.get("required_guard_reports") != required_reports:
        findings.append(Finding("OUTPUT.GUARD_REPORT_SET", "final manifest does not bind the exact current guard-report set"))

    candidate_digest = manifest.get("candidate_manifest_digest")
    if not isinstance(candidate_digest, str) or len(candidate_digest) != 64:
        findings.append(Finding("OUTPUT.CANDIDATE_BINDING", "final manifest lacks a valid candidate-manifest digest"))
        candidate_digest = ""
    if run_payload.get("candidate_manifest_digest") != candidate_digest:
        findings.append(Finding("OUTPUT.RUN_CANDIDATE_CHANGED", "output run does not bind the published candidate digest"))
    binding = manifest.get("candidate_binding")
    if not isinstance(binding, dict):
        binding = {}
        findings.append(Finding("OUTPUT.CANDIDATE_BINDING", "final manifest lacks durable candidate records"))
    deliveries = binding.get("deliveries") if isinstance(binding.get("deliveries"), list) else []
    qa_artifacts = binding.get("qa_artifacts") if isinstance(binding.get("qa_artifacts"), list) else []
    review_targets = binding.get("review_targets") if isinstance(binding.get("review_targets"), list) else []
    binding_records = [record for record in [*deliveries, *qa_artifacts] if isinstance(record, dict)]
    if len(binding_records) != len(deliveries) + len(qa_artifacts):
        findings.append(Finding("OUTPUT.CANDIDATE_RECORD", "durable candidate binding contains an invalid record"))
    delivery_paths = sorted(str(record.get("path") or "") for record in deliveries if isinstance(record, dict))
    if delivery_paths != policy.get("deliveries", []):
        findings.append(Finding("OUTPUT.DELIVERY_SET", "published delivery set does not exactly match output policy"))
    expected_targets = _review_targets({"deliveries": deliveries, "qa_artifacts": qa_artifacts})
    if not expected_targets:
        findings.append(Finding("OUTPUT.QA_TARGETS", "published output has no rendered PDF target for full-page visual review"))
    qa_paths = sorted(str(record.get("path") or "") for record in qa_artifacts if isinstance(record, dict))
    if qa_paths != policy.get("previews"):
        findings.append(Finding("OUTPUT.PREVIEW_SET", "durable preview set does not exactly match the output plan"))
    for preview in qa_artifacts:
        if not isinstance(preview, dict) or not isinstance(preview.get("pages"), int) or preview.get("pages", 0) <= 0:
            findings.append(Finding("OUTPUT.PREVIEW_PAGES", "every durable preview must record a positive page count"))
    if review_targets != expected_targets:
        findings.append(Finding("OUTPUT.REVIEW_TARGETS", "final manifest has inconsistent rendered review targets"))
    findings.extend(_qa_payload_findings(
        qa_payload,
        candidate_digest=str(candidate_digest),
        review_targets=review_targets,
        relative_path=QA_REL.as_posix(),
    ))

    manifest_path = outdir / FINAL_MANIFEST_JSON_REL
    if run_payload.get("final_manifest_sha256") != (sha256_file(manifest_path) if manifest_path.is_file() else ""):
        findings.append(Finding("OUTPUT.RUN_MANIFEST_CHANGED", "output run does not bind the final manifest"))

    records = manifest.get("artifacts")
    seen: set[str] = set()
    manifest_records: dict[str, dict[str, Any]] = {}
    if not isinstance(records, list) or not records:
        findings.append(Finding("OUTPUT.MANIFEST_EMPTY", "final manifest contains no published artifacts"))
    else:
        for record in records:
            if not isinstance(record, dict):
                findings.append(Finding("OUTPUT.MANIFEST_RECORD", "final manifest contains an invalid artifact record"))
                continue
            relative = str(record.get("path") or "")
            path = (outdir / relative).resolve()
            try:
                path.relative_to(outdir.resolve())
            except ValueError:
                findings.append(Finding("OUTPUT.MANIFEST_PATH", f"artifact escapes workspace: {relative}"))
                continue
            if not relative or relative in seen:
                findings.append(Finding("OUTPUT.MANIFEST_PATH", f"artifact path is empty or duplicated: {relative!r}"))
                continue
            seen.add(relative)
            manifest_records[relative] = record
            if not path.is_file():
                findings.append(Finding("OUTPUT.ARTIFACT_MISSING", f"published artifact is missing: {relative}", relative))
                continue
            if record.get("sha256") != sha256_file(path) or record.get("size") != path.stat().st_size:
                findings.append(Finding("OUTPUT.ARTIFACT_CHANGED", f"published artifact changed: {relative}", relative))
    for record in binding_records:
        relative = str(record.get("path") or "")
        published = manifest_records.get(relative, {})
        if (
            not relative
            or published.get("sha256") != record.get("sha256")
            or published.get("size") != record.get("size")
        ):
            findings.append(Finding("OUTPUT.CANDIDATE_RECORD", f"published artifact does not match durable candidate record: {relative!r}"))
    expected_artifacts = {
        QA_REL.as_posix(),
        *required_reports,
        *(str(record.get("path") or "") for record in binding_records),
    }
    if seen != expected_artifacts:
        findings.append(Finding("OUTPUT.MANIFEST_SET", "final manifest artifact set does not exactly match durable delivery, QA, and guard records"))
    for relative in required_reports:
        if not report_passed(outdir / relative):
            findings.append(Finding("OUTPUT.GUARD_REPORT_INVALID", f"published guard report is missing or not PASS: {relative}", relative))
    fixed_deliveries = {
        "final_paper/paper.docx",
        "final_paper/paper.zh.docx",
        "final_paper/paper.pdf",
    }
    stale = sorted(
        relative
        for relative in fixed_deliveries - set(policy.get("deliveries", []))
        if (outdir / relative).is_file()
    )
    if stale:
        findings.append(Finding("OUTPUT.STALE_DELIVERY", "unrequested managed deliveries remain: " + ", ".join(stale)))
    planned_managed = {
        *policy.get("deliveries", []),
        *policy.get("previews", []),
    }
    package_stale = sorted(_managed_root_files(outdir) - planned_managed)
    if package_stale:
        findings.append(Finding(
            "OUTPUT.STALE_PACKAGE_FILE",
            "unrequested or unmanaged package files remain: " + ", ".join(package_stale),
        ))
    if not report_passed(outdir / FINAL_MANIFEST_MD_REL):
        findings.append(Finding("OUTPUT.MANIFEST_VIEW", "final_artifact_manifest.md is missing or not PASS"))
    if not report_passed(outdir / "output_artifact_check.md"):
        findings.append(Finding("OUTPUT.ARTIFACT_REPORT", "output_artifact_check.md is missing or not PASS"))
    return GateResult.fail("output", findings) if findings else GateResult.pass_("output")
