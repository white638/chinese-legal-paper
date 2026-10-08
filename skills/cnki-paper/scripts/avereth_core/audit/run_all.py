"""Run each academic-audit action exactly once; never sign a receipt."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import meaningful_file, sha256_file
from ..build.manuscript import ManuscriptSelectionError, select_manuscript
from ..config import read_config
from ..models import Finding, GateResult
from ..stages import inspect_stage
from ..hosts.runtime_observation import record_runtime_event
from .artifacts import run as run_artifact_audit
from .integrity import run as run_integrity_audit
from .reviewers import validate as validate_review_outputs


TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
RUN_LOG_REL = Path("audit_run.json")

# Declared responsibility inputs and produced reports are part of the cache
# contract.  A cache hit is legal only when the implementation, this exact
# input projection, and every output hash remain unchanged.
ACTION_INPUTS: dict[str, tuple[str, ...]] = {
    "dialogic_argument": ("dialogic_argument_map.md", "writing_rationale_matrix.md", "evidence_bank.md", "@manuscript"),
    "academic_prose": ("academic_prose_audit.md", "writing_rationale_matrix.md", "@manuscript"),
    "citation_integrity": ("@manuscript", "final_paper/references.bib", "citation_support_bank.md", "reference_materials/literature_registry.json"),
    "citation_traceability": ("citation_support_bank.md", "reference_materials/literature_registry.json"),
    "citation_quality_facts": ("citation_support_bank.md", "reference_materials/literature_registry.json", "@manuscript"),
    "contribution": ("confirmed_motivation.md", "confirmed_contribution.md", "research_design.json", "method_execution.json", "@manuscript"),
    "results": ("results_validation.md", "research_design.json", "method_execution.json", "@manuscript"),
    "page_evidence": ("evidence_bank.md", "reference_materials/literature_registry.json", "@manuscript"),
    "reviewer_assurance": ("review_assurance.json", "review_findings.json", "review_resolution.json", "@manuscript"),
}
ACTION_OUTPUTS: dict[str, tuple[str, ...]] = {
    "dialogic_argument": ("dialogic_argument_check.md",),
    "academic_prose": ("academic_prose_check.md",),
    "citation_integrity": ("citation_integrity_audit.md",),
    "citation_traceability": ("citation_bank_check.md",),
    "citation_quality_facts": ("citation_quality_audit.md",),
    "contribution": ("contribution_check.md",),
    "results": ("results_validation_check.md",),
    "page_evidence": ("page_evidence_audit.md",),
    "reviewer_assurance": ("reviewer_audit_check.md",),
}
ACTION_IMPACT_CLASSES: dict[str, frozenset[str]] = {
    "dialogic_argument": frozenset({"argument", "evidence", "design", "execution"}),
    "academic_prose": frozenset({"surface", "argument", "evidence", "design", "execution"}),
    "citation_integrity": frozenset({"surface", "evidence"}),
    "citation_traceability": frozenset({"evidence"}),
    "citation_quality_facts": frozenset({"evidence"}),
    "contribution": frozenset({"argument", "evidence", "design", "execution"}),
    "results": frozenset({"evidence", "design", "execution"}),
    "page_evidence": frozenset({"evidence"}),
    "reviewer_assurance": frozenset({"surface", "argument", "evidence", "design", "execution"}),
}


@dataclass(frozen=True)
class Action:
    name: str
    script: Path
    arguments: tuple[str, ...]
    blocking: bool = True


def _runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def _run(action: Action) -> tuple[int, str]:
    try:
        result = subprocess.run(
            [sys.executable, str(action.script), *action.arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_runtime_env(),
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 2, str(exc)
    detail = " ".join((result.stdout + "\n" + result.stderr).split())[-1200:]
    return result.returncode, detail


def _digest_payload(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _action_input_digest(action: Action, outdir: Path, manuscript: Path) -> str:
    files: list[dict[str, str]] = []
    for declared in ACTION_INPUTS.get(action.name, ("@manuscript",)):
        target = manuscript if declared == "@manuscript" else outdir / declared
        files.append(
            {
                "path": "@manuscript" if declared == "@manuscript" else declared,
                "sha256": sha256_file(target) if target.is_file() else "",
            }
        )
    if action.name == "page_evidence":
        shared = action.script.with_name("evidence_contract.py")
        for module in (shared, action.script.with_name("pdf_locate.py")):
            files.append({"path": "@implementation/" + module.name,
                          "sha256": sha256_file(module) if module.is_file() else ""})
        if shared.is_file():
            spec = importlib.util.spec_from_file_location("_page_evidence_contract", shared)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            files.extend(module.artifact_inputs(outdir))
    implementation = sha256_file(action.script) if action.script.is_file() else ""
    return _digest_payload(
        {
            "contract": "avereth-audit-action-input/v1",
            "name": action.name,
            "arguments": [
                value.replace(str(outdir), "@outdir").replace(str(manuscript), "@manuscript")
                for value in action.arguments
            ],
            "inputs": files,
            "implementation_sha256": implementation,
        }
    )


def _output_artifacts(action: Action, outdir: Path) -> list[dict[str, str]]:
    return [
        {"path": relative, "sha256": sha256_file(outdir / relative)}
        for relative in ACTION_OUTPUTS.get(action.name, ())
        if (outdir / relative).is_file()
    ]


def _revision_impact(outdir: Path) -> tuple[dict[str, Any], str]:
    path = outdir / "revision_impact.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}, ""
    return (payload if isinstance(payload, dict) else {}), sha256_file(path)


def _impact_touches_action(action: Action, impact: dict[str, Any]) -> bool:
    classes = {str(item) for item in impact.get("change_classes") or []}
    if classes & ACTION_IMPACT_CLASSES.get(action.name, frozenset()):
        return True
    if action.name in {"contribution", "results"} and any(
        impact.get(field)
        for field in ("affected_claim_ids", "affected_design_ids", "affected_execution_ids")
    ):
        return True
    if action.name in {"citation_integrity", "citation_traceability", "citation_quality_facts", "page_evidence"} and impact.get("affected_evidence_ids"):
        return True
    return False


def _cached_action_record(
    previous: dict[str, Any], action: Action, outdir: Path, manuscript: Path
) -> dict[str, Any] | None:
    if previous.get("status") != "PASS":
        return None
    expected_input = _action_input_digest(action, outdir, manuscript)
    expected_impl = sha256_file(action.script) if action.script.is_file() else ""
    impact, impact_sha = _revision_impact(outdir)
    records = previous.get("actions") if isinstance(previous.get("actions"), list) else []
    old = next(
        (
            item for item in records
            if isinstance(item, dict) and item.get("name") == action.name
        ),
        None,
    )
    if (
        not isinstance(old, dict)
        or old.get("returncode") != 0
        or old.get("input_digest") != expected_input
        or old.get("implementation_sha256") != expected_impl
    ):
        return None
    if old.get("revision_impact_sha256") != impact_sha and _impact_touches_action(action, impact):
        return None
    outputs = old.get("output_artifacts")
    if not isinstance(outputs, list) or not outputs:
        return None
    for artifact in outputs:
        if not isinstance(artifact, dict):
            return None
        relative = str(artifact.get("path") or "").replace("\\", "/")
        try:
            target = (outdir / relative).resolve()
            target.relative_to(outdir.resolve())
        except ValueError:
            return None
        if not target.is_file() or artifact.get("sha256") != sha256_file(target):
            return None
    return {
        "name": action.name,
        "returncode": 0,
        "detail": "reused exact PASS action result",
        "execution": "REUSED",
        "input_digest": expected_input,
        "implementation_sha256": expected_impl,
        "revision_impact_sha256": impact_sha,
        "output_artifacts": outputs,
    }


def _select_canonical_manuscript(outdir: Path, config: dict[str, Any]) -> Path | None:
    try:
        return select_manuscript(outdir, config).path
    except ManuscriptSelectionError:
        return None


def _citation_integrity_arguments(outdir: Path, manuscript: Path, config: dict[str, Any]) -> tuple[str, ...]:
    arguments = [str(manuscript), "--output", str(outdir / "citation_integrity_audit.md")]
    bib = outdir / "final_paper" / "references.bib"
    if bib.is_file():
        arguments.extend(["--bib", str(bib)])
    bank = outdir / "citation_support_bank.md"
    if bank.is_file():
        arguments.extend(["--bank", str(bank)])
    scene = str(config.get("scene") or "").strip().lower()
    if scene in {"journal", "conference"}:
        arguments.extend(["--publication-mode", "--verify-online"])
    arguments.append("--write")
    return tuple(arguments)




def _actions(
    outdir: Path,
    skills_dir: Path,
    config: dict[str, Any],
    manuscript: Path,
) -> list[Action]:
    actions = [
        Action(
            "dialogic_argument",
            skills_dir / "cnki-paper" / "scripts" / "dialogic_argument_check.py",
            (str(outdir), "--markdown", "--write"),
        ),
        Action(
            "academic_prose",
            skills_dir / "cnki-paper" / "scripts" / "academic_prose_check.py",
            (
                str(outdir),
                "--manuscript",
                str(manuscript),
                "--markdown",
                "--write",
                "--require-manuscript",
            ),
        ),
        Action(
            "citation_integrity",
            TOOLS_DIR / "citation_integrity_audit.py",
            _citation_integrity_arguments(outdir, manuscript, config),
        ),
        Action(
            "citation_traceability",
            TOOLS_DIR / "citation_bank_check.py",
            (
                str(outdir / "citation_support_bank.md"),
                "--target-count",
                "0",
                "--multiplier",
                "1",
                "--recent-ratio",
                "0",
                "--markdown",
                "--write",
            ),
        ),
        Action(
            "citation_quality_facts",
            TOOLS_DIR / "citation_quality_audit.py",
            (
                str(outdir),
                "--min-score",
                "0",
                "--max-error-ratio",
                "1",
                "--max-pending-ratio",
                "1",
                "--write",
            ),
        ),
        Action("contribution", TOOLS_DIR / "contribution_check.py", (str(outdir), "--markdown", "--write")),
    ]
    if str(config.get("scene") or "").strip().lower() in {"journal", "conference", "competition"}:
        actions.append(
            Action("results", TOOLS_DIR / "results_validation_check.py", (str(outdir), "--markdown", "--write"))
        )
    actions.append(
        Action(
            "page_evidence",
            skills_dir / "page-evidence" / "scripts" / "page_evidence_audit.py",
            (str(outdir), "--manuscript", str(manuscript), "--strict", "--write"),
        )
    )
    actions.extend(
        [
            Action(
                "structured_review",
                TOOLS_DIR / "structured_review.py",
                (
                    str(outdir),
                    "--manuscript",
                    str(manuscript),
                    "--validate",
                    str(outdir / "review_prompts"),
                    "--json",
                ),
            ),
            Action(
                "review_finding_compile",
                TOOLS_DIR / "review_lifecycle.py",
                (
                    str(outdir),
                    "compile",
                    "--review-dir",
                    "review_prompts",
                    "--manuscript",
                    str(manuscript),
                    "--write",
                    "--json",
                ),
            ),
            Action(
                "review_lifecycle",
                TOOLS_DIR / "review_lifecycle.py",
                (
                    str(outdir),
                    "validate",
                    "--manuscript",
                    str(manuscript),
                    "--write",
                    "--json",
                ),
            ),
            Action(
                "reviewer_assurance",
                TOOLS_DIR / "reviewer_audit_check.py",
                (
                    str(outdir),
                    "--manuscript",
                    str(manuscript),
                    "--markdown",
                    "--write",
                ),
            ),
        ]
    )
    return actions


def run_all(
    outdir: Path,
    skills_dir: Path,
    *,
    config: dict[str, Any] | None = None,
    write_log: bool = True,
) -> GateResult:
    """Run the audit action graph once.  The caller owns receipt lifecycle."""

    config_read = read_config(outdir)
    config = dict(config if config is not None else config_read.payload)
    findings: list[Finding] = []
    generated: list[str] = []
    invocations: dict[str, int] = {}
    records: list[dict[str, Any]] = []
    try:
        previous_run = json.loads((outdir / RUN_LOG_REL).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        previous_run = {}
    _, current_impact_sha = _revision_impact(outdir)

    artifact_result = run_artifact_audit(outdir, config, write=True)
    invocations["artifact_consistency"] = 1
    generated.append("artifact_check.md")
    records.append(
        {
            "name": "artifact_consistency",
            "returncode": 0 if artifact_result.ok else 1,
            "execution": "EXECUTED",
            "input_digest": _digest_payload({"config": config, "action": "artifact_consistency"}),
            "implementation_sha256": sha256_file(Path(__file__).with_name("artifacts.py")),
            "revision_impact_sha256": current_impact_sha,
            "output_artifacts": (
                [{"path": "artifact_check.md", "sha256": sha256_file(outdir / "artifact_check.md")}]
                if (outdir / "artifact_check.md").is_file() else []
            ),
        }
    )
    findings.extend(artifact_result.findings)

    manuscript = _select_canonical_manuscript(outdir, config)
    if manuscript is None:
        findings.append(
            Finding(
                "AUDIT.CANONICAL_MANUSCRIPT",
                "declare one canonical manuscript source; multiple or missing source files cannot be selected silently",
                "final_paper",
            )
        )
        actions: list[Action] = []
    else:
        actions = _actions(outdir, skills_dir, config, manuscript)
        integrity_result = run_integrity_audit(outdir, manuscript, write=True)
        invocations["integrity"] = 1
        records.append(
            {
                "name": "integrity",
                "returncode": 0 if integrity_result.ok else 1,
                "execution": "EXECUTED",
                "input_digest": _digest_payload(
                    {"canonical_sha256": sha256_file(manuscript), "config": config, "action": "integrity"}
                ),
                "implementation_sha256": sha256_file(Path(__file__).with_name("integrity.py")),
                "revision_impact_sha256": current_impact_sha,
                "output_artifacts": (
                    [{"path": "integrity_audit.md", "sha256": sha256_file(outdir / "integrity_audit.md")}]
                    if (outdir / "integrity_audit.md").is_file() else []
                ),
            }
        )
        findings.extend(integrity_result.findings)
        generated.append("integrity_audit.md")

    for action in actions:
        if action.name in invocations:
            findings.append(Finding("AUDIT.DUPLICATE_ACTION", f"audit action scheduled twice: {action.name}"))
            continue
        invocations[action.name] = 1
        observed_start = time.monotonic()
        cached = _cached_action_record(previous_run, action, outdir, manuscript)
        if cached is not None:
            code, detail = 0, str(cached["detail"])
            records.append(cached)
        else:
            page_input_before = _action_input_digest(action, outdir, manuscript) if action.name == "page_evidence" else None
            if not action.script.is_file():
                code, detail = 127, f"missing audit implementation: {action.script}"
            else:
                code, detail = _run(action)
            if page_input_before is not None and page_input_before != _action_input_digest(action, outdir, manuscript):
                code, detail = 2, "page-evidence inputs changed during execution"
            records.append(
                {
                    "name": action.name,
                    "returncode": code,
                    "detail": detail,
                    "execution": "EXECUTED",
                    "input_digest": _action_input_digest(action, outdir, manuscript),
                    "implementation_sha256": sha256_file(action.script) if action.script.is_file() else "",
                    "revision_impact_sha256": current_impact_sha,
                    "output_artifacts": _output_artifacts(action, outdir),
                }
            )
        record_runtime_event("audit.action", gate=action.name, stage="audit", exit_code=code,
                             execution=records[-1]["execution"],
                             wall_time_seconds=time.monotonic() - observed_start,
                             output_artifacts=records[-1].get("output_artifacts", []),
                             unique_catch=None, false_positive=None, repair_succeeded=None)
        if code != 0 and action.blocking:
            findings.append(
                Finding("AUDIT.ACTION_FAILED", f"{action.name} failed: {detail or f'exit {code}'}")
            )

    for relative in (
        "dialogic_argument_check.md",
        "academic_prose_check.md",
        "citation_integrity_audit.md",
        "citation_bank_check.md",
        "integrity_audit.md",
        "citation_quality_audit.md",
        "contribution_check.md",
        "review_findings.json",
        "review_resolution.json",
        "structured_review.md",
        "reviewer_audit.md",
        "revision_plan.md",
        "reviewer_audit_check.md",
        "results_validation_check.md",
        "page_evidence_audit.md",
    ):
        if meaningful_file(outdir / relative):
            generated.append(relative)

    review_postcondition = validate_review_outputs(outdir, manuscript)
    invocations["review_postcondition"] = 1
    records.append(
        {
            "name": "review_postcondition",
            "returncode": 0 if review_postcondition.ok else 1,
            "execution": "EXECUTED",
            "input_digest": _digest_payload(
                {"canonical_sha256": sha256_file(manuscript) if manuscript else "", "action": "review_postcondition"}
            ),
            "implementation_sha256": sha256_file(Path(__file__).with_name("reviewers.py")),
            "revision_impact_sha256": current_impact_sha,
            "output_artifacts": [],
        }
    )
    findings.extend(review_postcondition.findings)

    postcondition = inspect_stage(outdir, "audit", config)
    invocations["audit_postcondition"] = 1
    records.append(
        {
            "name": "audit_postcondition",
            "returncode": 0 if postcondition.ok else 1,
            "execution": "EXECUTED",
            "input_digest": _digest_payload({"config": config, "action": "audit_postcondition"}),
            "implementation_sha256": sha256_file(Path(__file__).resolve().parents[1] / "stages.py"),
            "revision_impact_sha256": current_impact_sha,
            "output_artifacts": [],
        }
    )
    findings.extend(postcondition.findings)

    payload = {
        "schema_version": "avereth-audit-run/v1",
        "status": "PENDING" if not findings else "FAIL",
        "canonical_manuscript": (
            {
                "path": str(manuscript.relative_to(outdir)).replace("\\", "/"),
                "sha256": sha256_file(manuscript),
            }
            if manuscript
            else None
        ),
        "invocations": invocations,
        "actions": records,
        "findings": [finding.as_dict() for finding in findings],
    }
    if write_log:
        temporary = (outdir / RUN_LOG_REL).with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(outdir / RUN_LOG_REL)
        generated.append(RUN_LOG_REL.as_posix())
    if findings:
        return GateResult.fail("audit", findings)
    return GateResult.pass_("audit", generated=generated)


def finalize_run_log(
    outdir: Path,
    result: GateResult,
    *,
    assurance_issues: list[str],
    upstream_issues: list[str],
) -> GateResult:
    """Append the controller-owned final postconditions exactly once."""

    try:
        payload = json.loads((outdir / RUN_LOG_REL).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    findings = list(result.findings)
    findings.extend(Finding("AUDIT.REVIEW_ASSURANCE", issue) for issue in assurance_issues)
    findings.extend(Finding("AUDIT.UPSTREAM_CHANGED", issue) for issue in upstream_issues)
    invocations = payload.get("invocations") if isinstance(payload.get("invocations"), dict) else {}
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    _, current_impact_sha = _revision_impact(outdir)
    if "review_assurance_postcondition" in invocations:
        findings.append(Finding("AUDIT.DUPLICATE_ACTION", "review assurance postcondition ran more than once"))
    else:
        invocations["review_assurance_postcondition"] = 1
        actions.append(
            {
                "name": "review_assurance_postcondition",
                "returncode": 0 if not assurance_issues else 1,
                "execution": "EXECUTED",
                "input_digest": _digest_payload(
                    {"action": "review_assurance_postcondition", "issues": assurance_issues}
                ),
                "implementation_sha256": sha256_file(Path(__file__).resolve().parents[1] / "cli.py"),
                "revision_impact_sha256": current_impact_sha,
                "output_artifacts": [],
            }
        )
    if "upstream_postcondition" in invocations:
        findings.append(Finding("AUDIT.DUPLICATE_ACTION", "upstream postcondition ran more than once"))
    else:
        invocations["upstream_postcondition"] = 1
        actions.append(
            {
                "name": "upstream_postcondition",
                "returncode": 0 if not upstream_issues else 1,
                "execution": "EXECUTED",
                "input_digest": _digest_payload(
                    {"action": "upstream_postcondition", "issues": upstream_issues}
                ),
                "implementation_sha256": sha256_file(Path(__file__).resolve().parents[1] / "cli.py"),
                "revision_impact_sha256": current_impact_sha,
                "output_artifacts": [],
            }
        )
    payload.update(
        {
            "status": "FAIL" if findings else "PASS",
            "invocations": invocations,
            "actions": actions,
            "findings": [finding.as_dict() for finding in findings],
        }
    )
    temporary = (outdir / RUN_LOG_REL).with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(outdir / RUN_LOG_REL)
    return GateResult.fail("audit", findings) if findings else GateResult.pass_("audit", generated=result.generated)


def validate_completion(
    outdir: Path,
    *,
    config: dict[str, Any] | None = None,
) -> GateResult:
    """Fail closed unless the once-only audit graph and its reports are current."""

    active = dict(config if config is not None else read_config(outdir).payload)
    findings: list[Finding] = []
    try:
        payload = json.loads((outdir / RUN_LOG_REL).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    if payload.get("schema_version") != "avereth-audit-run/v1" or payload.get("status") != "PASS":
        findings.append(
            Finding("AUDIT.RUN_INVALID", "audit_run.json must be a finalized v6 PASS run", RUN_LOG_REL.as_posix())
        )
    try:
        selection = select_manuscript(outdir, active)
        canonical = selection.as_dict()
    except ManuscriptSelectionError as exc:
        canonical = {}
        findings.append(Finding("AUDIT.CANONICAL_MANUSCRIPT", str(exc)))
    if payload.get("canonical_manuscript") != canonical:
        findings.append(
            Finding("AUDIT.RUN_SOURCE_CHANGED", "audit_run.json does not bind the current canonical manuscript")
        )
    invocations = payload.get("invocations")
    actions = payload.get("actions")
    if not isinstance(invocations, dict) or not invocations or any(value != 1 for value in invocations.values()):
        findings.append(Finding("AUDIT.INVOCATION_COUNT", "every audit action and postcondition must run exactly once"))
    action_names: list[str] = []
    skills_dir = Path(__file__).resolve().parents[4]
    expected: dict[str, str] = {
        "artifact_consistency": sha256_file(Path(__file__).with_name("artifacts.py")),
        "integrity": sha256_file(Path(__file__).with_name("integrity.py")),
        "review_postcondition": sha256_file(Path(__file__).with_name("reviewers.py")),
        "audit_postcondition": sha256_file(Path(__file__).resolve().parents[1] / "stages.py"),
        "review_assurance_postcondition": sha256_file(Path(__file__).resolve().parents[1] / "cli.py"),
        "upstream_postcondition": sha256_file(Path(__file__).resolve().parents[1] / "cli.py"),
    }
    canonical_sha = str(canonical.get("sha256") or "") if canonical else ""
    expected_inputs: dict[str, str] = {
        "artifact_consistency": _digest_payload({"config": active, "action": "artifact_consistency"}),
        "integrity": _digest_payload({"canonical_sha256": canonical_sha, "config": active, "action": "integrity"}),
        "review_postcondition": _digest_payload({"canonical_sha256": canonical_sha, "action": "review_postcondition"}),
        "audit_postcondition": _digest_payload({"config": active, "action": "audit_postcondition"}),
        "review_assurance_postcondition": _digest_payload({"action": "review_assurance_postcondition", "issues": []}),
        "upstream_postcondition": _digest_payload({"action": "upstream_postcondition", "issues": []}),
    }
    _, current_impact_sha = _revision_impact(outdir)
    expected_action_names: list[str] = ["artifact_consistency", "integrity"]
    if canonical:
        for action in _actions(outdir, skills_dir, active, outdir / canonical["path"]):
            expected[action.name] = sha256_file(action.script) if action.script.is_file() else ""
            expected_inputs[action.name] = _action_input_digest(
                action, outdir, outdir / canonical["path"]
            )
            expected_action_names.append(action.name)
    expected_action_names.extend(
        [
            "review_postcondition",
            "audit_postcondition",
            "review_assurance_postcondition",
            "upstream_postcondition",
        ]
    )
    if not isinstance(actions, list):
        findings.append(Finding("AUDIT.ACTION_LOG", "audit action log is missing"))
    else:
        for record in actions:
            if not isinstance(record, dict):
                findings.append(Finding("AUDIT.ACTION_LOG", "audit action log contains an invalid record"))
                continue
            action_names.append(str(record.get("name") or ""))
            if record.get("returncode") != 0:
                findings.append(
                    Finding("AUDIT.ACTION_FAILED", f"audit action did not pass: {record.get('name') or '<unknown>'}")
                )
            execution = str(record.get("execution") or "")
            if execution not in {"EXECUTED", "REUSED", "SKIPPED_NOT_APPLICABLE"}:
                findings.append(
                    Finding(
                        "AUDIT.EXECUTION_MODE",
                        f"audit action lacks a valid execution mode: {record.get('name') or '<unknown>'}",
                    )
                )
            if not re.fullmatch(r"[a-f0-9]{64}", str(record.get("input_digest") or "")):
                findings.append(
                    Finding(
                        "AUDIT.INPUT_DIGEST",
                        f"audit action lacks an exact input digest: {record.get('name') or '<unknown>'}",
                    )
                )
            elif record.get("input_digest") != expected_inputs.get(str(record.get("name") or "")):
                findings.append(
                    Finding(
                        "AUDIT.INPUT_CHANGED",
                        f"audit action inputs changed after execution: {record.get('name') or '<unknown>'}",
                    )
                )
            expected_digest = expected.get(str(record.get("name") or ""))
            if expected_digest is None or record.get("implementation_sha256") != expected_digest:
                findings.append(
                    Finding(
                        "AUDIT.IMPLEMENTATION_CHANGED",
                        f"audit action implementation is missing or changed: {record.get('name') or '<unknown>'}",
                    )
                )
            if str(record.get("revision_impact_sha256") or "") != current_impact_sha:
                findings.append(
                    Finding(
                        "AUDIT.IMPACT_CHANGED",
                        f"audit action does not bind the current revision impact: {record.get('name') or '<unknown>'}",
                    )
                )
            outputs = record.get("output_artifacts")
            if record.get("name") == "page_evidence" and (
                not isinstance(outputs, list) or
                {item.get("path") for item in outputs if isinstance(item, dict)} != {"page_evidence_audit.md"}
            ):
                findings.append(Finding("AUDIT.OUTPUT_BINDING", "page-evidence audit must bind its declared report artifact"))
            if not isinstance(outputs, list):
                findings.append(
                    Finding(
                        "AUDIT.OUTPUT_BINDING",
                        f"audit action output bindings are missing: {record.get('name') or '<unknown>'}",
                    )
                )
            else:
                for artifact in outputs:
                    if not isinstance(artifact, dict):
                        findings.append(Finding("AUDIT.OUTPUT_BINDING", "audit action has an invalid output binding"))
                        continue
                    relative = str(artifact.get("path") or "").replace("\\", "/")
                    try:
                        target = (outdir / relative).resolve()
                        target.relative_to(outdir.resolve())
                    except ValueError:
                        target = Path()
                    if not relative or not target.is_file() or artifact.get("sha256") != sha256_file(target):
                        findings.append(
                            Finding(
                                "AUDIT.OUTPUT_CHANGED",
                                f"cached audit output is missing or changed: {relative or '<missing>'}",
                            )
                        )
    if isinstance(invocations, dict) and sorted(action_names) != sorted(str(key) for key in invocations):
        findings.append(Finding("AUDIT.ACTION_LOG", "audit action log and invocation counts disagree"))
    if set(action_names) != set(expected):
        missing = sorted(set(expected) - set(action_names))
        extra = sorted(set(action_names) - set(expected))
        findings.append(
            Finding(
                "AUDIT.ACTION_SET",
                "audit action set differs from the current graph"
                + (f"; missing={','.join(missing)}" if missing else "")
                + (f"; extra={','.join(extra)}" if extra else ""),
            )
        )
    if action_names != expected_action_names:
        findings.append(
            Finding(
                "AUDIT.ACTION_ORDER",
                "audit action order differs from the canonical graph; "
                f"expected={json.dumps(expected_action_names, ensure_ascii=False)}; "
                f"actual={json.dumps(action_names, ensure_ascii=False)}",
            )
        )
    if payload.get("findings") not in ([], None):
        findings.append(Finding("AUDIT.RUN_FINDINGS", "audit_run.json still contains blocking findings"))
    artifact_result = inspect_stage(outdir, "audit", active)
    findings.extend(artifact_result.findings)
    review_result = validate_review_outputs(
        outdir,
        (outdir / canonical["path"]) if canonical else None,
    )
    findings.extend(review_result.findings)
    return GateResult.fail("audit", findings) if findings else GateResult.pass_("audit")


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--skills-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = {
        "stage": "audit",
        "status": "blocked",
        "findings": [
            {
                "code": "AUDIT.CONTROLLER_REQUIRED",
                "message": "run `avereth.py gate OUTDIR --stage audit`; the controller owns locking and receipt lifecycle",
                "severity": "error",
            }
        ],
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("# Avereth Audit\n\nStatus: BLOCKED")
        print("- run `avereth.py gate OUTDIR --stage audit`; the controller owns locking and receipt lifecycle")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
