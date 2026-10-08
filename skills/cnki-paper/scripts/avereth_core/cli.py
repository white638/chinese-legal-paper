#!/usr/bin/env python3
"""CNKI-Paper v7 local research-engine control plane."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .hosts.runtime_observation import observe_controller, observe_gate, record_runtime_event

from cnki_acquisition import validate_registry
from dialogic_argument_check import validate_dialogic_argument
from literature_analysis import (
    semantic_source_payload,
    validate_analysis,
)
from literature_sufficiency import fallback_floor
from problem_orientation_check import render_report as render_problem_orientation_report
from problem_orientation_check import validate_problem_orientation
from research_materials import validate_contract as validate_material_contract
from research_feasibility import (
    feasibility_reference,
    resource_unlock_state,
    validate_contract as validate_feasibility_contract,
)
from revision_contract import (
    CONTRACT_REL as REVISION_CONTRACT_REL,
    SCHEMA_VERSION as REVISION_CONTRACT_SCHEMA,
    load_and_validate as load_and_validate_revision,
    route_plan as revision_route_plan,
)

from .audit.run_all import (
    finalize_run_log as finalize_audit_run_log,
    run_all as run_audit_actions,
    validate_completion as validate_audit_completion,
)
from .build.manuscript import ManuscriptSelectionError, rollback_preparation, select_manuscript
from .build.manuscript_compiler import (
    IR_REL as MANUSCRIPT_IR_REL,
    LEGACY_ARCHIVE_ROOT_REL,
    TRACE_REL as MANUSCRIPT_TRACE_REL,
    ManuscriptCompilerError,
    SUPPORTED_PROFILES as MANUSCRIPT_PROFILES,
    compile_workspace as compile_manuscript,
    compiler_applies,
    init_contract as init_manuscript_contract,
    receipt_closure_paths as manuscript_receipt_closure_paths,
    record_rebuild_proofs,
    render_workspace as render_manuscript,
    restore_legacy_archive,
    validate_workspace as validate_manuscript,
    write_initialized_contract,
)
from .build.run import build_run_status, prepare_build, record_build
from .config import (
    LEGACY_CONFIG_MD_REL,
    LEGACY_CONFIG_REL,
    WORKFLOW_CONFIG_MD_REL,
    WORKFLOW_CONFIG_REL,
    config_exists,
    read_config,
    validate_workflow_config,
)
from .gates.local import gate as local_artifact_gate
from .gates.integration_gate import validate_integration_artifacts
from .infrastructure.locks import (
    LOCK_NAMES,
    exclusive_lock,
    audit_gate_lock,
    build_gate_lock,
    inspect_workspace_locks,
    output_gate_lock,
    recover_workspace_locks,
)
from .application.plan_service import REFERENCE_ACTIONS, build_plan, plan_markdown
from .application.delegation import load_discovery_context, capture_candidates, validate_candidate_result
from .application.protocol_compiler import (
    ProtocolCompilerError,
    compile_protocol,
    next_markdown,
    next_projection,
    protocol_markdown,
    render_views as render_protocol_views,
    validate_protocol,
)
from .legacy.workspace_migration import ACQUISITION_HANDOFF_REL
from .legacy.workspace_migration import apply as apply_v6_migration
from .legacy.workspace_migration import acquisition_handoff_issues
from .legacy.workspace_migration import plan as v6_migration_plan
from .legacy.workspace_migration import rollback as rollback_v6_migration
from .models import Finding, GateResult, GateStatus
from .output.run import (
    record_visual_qa,
    run_output as run_output_actions,
    validate_completion as validate_output_completion,
)
from .output.guards import required_tool_scripts as required_output_tool_scripts
from .receipts import (
    AUDIT_MD_REL,
    AUDIT_REL,
    AUDIT_SCHEMA,
    LEGACY_AUDIT_MD_REL,
    LEGACY_AUDIT_REL,
    LEGACY_OUTPUT_MD_REL,
    LEGACY_OUTPUT_REL,
    LEGACY_STATUS_MD_REL,
    LEGACY_STATUS_REL,
    OUTPUT_MD_REL,
    OUTPUT_REL,
    OUTPUT_SCHEMA,
    STATUS_MD_REL,
    STATUS_REL,
    is_legacy_gate_view,
    read_receipt,
)
from .stages import (
    LEGACY_STAGE_ALIASES,
    STAGES,
    TASK_PROFILE_TERMINALS,
    canonical_stage,
)
from .scientific_runtime import scientific_runtime_digest, scientific_runtime_issues
from .tools.review_lifecycle import (
    assurance_summary as lifecycle_assurance_summary,
    workspace_review_route,
)
from .version import VERSION
from .workflow_registry import (
    ACQUISITION_SCHEMA_V1,
    ACQUISITION_SCHEMA_V2,
    ACQUISITION_SCHEMA_V3,
    ARTIFACTS_BY_PATH,
    DESIGN_SCHEMA_V1,
    DESIGN_SCHEMA_V2,
    DESIGN_SCHEMA_V3,
    DESIGN_SCHEMA_V4,
    EXECUTION_SCHEMA_V1,
    EXECUTION_SCHEMA_V2,
    EXECUTION_SCHEMA_V3,
    GLOBAL_RUNTIME_FILES,
    INTERNATIONAL_SEARCH_SKILLS as REGISTRY_INTERNATIONAL_SEARCH_SKILLS,
    LITERATURE_ANALYSIS_SCHEMA_V1,
    LITERATURE_ANALYSIS_SCHEMA_V2,
    CNKI_SEARCH_SKILLS as REGISTRY_CNKI_SEARCH_SKILLS,
    RECEIPT_BOUND_ROOT_PATHS,
    REBUILDABLE_VIEW_PATHS,
    REQUIRED_SKILLS as REGISTRY_REQUIRED_SKILLS,
    SEMANTIC_PHASE_ORDER,
    STAGE_TO_SEMANTIC_PHASE,
    quantitative_data_check_required,
    runtime_files_for,
)


FRAMEWORK_VERSION = VERSION
AUDIT_RECEIPT_SCHEMA = AUDIT_SCHEMA
OUTPUT_RECEIPT_SCHEMA = OUTPUT_SCHEMA
LITERATURE_ANALYSIS_SCHEMA = LITERATURE_ANALYSIS_SCHEMA_V2
AUDIT_RECEIPT_REL = AUDIT_REL
AUDIT_RECEIPT_MD_REL = AUDIT_MD_REL
OUTPUT_RECEIPT_REL = OUTPUT_REL
OUTPUT_RECEIPT_MD_REL = OUTPUT_MD_REL
REVIEW_ASSURANCE_REL = Path("review_assurance.json")


class SafeArgumentParser(argparse.ArgumentParser):
    """Fail with a fixed diagnostic so argparse never reflects caller values."""

    def error(self, _message: str) -> None:
        self.exit(
            2,
            '{"status":"INVALID","code":"INVALID_COMMAND_ARGUMENTS"}\n',
        )


FINGERPRINT_EXCLUDES = {
    AUDIT_RECEIPT_REL.as_posix(),
    AUDIT_RECEIPT_MD_REL.as_posix(),
    OUTPUT_RECEIPT_REL.as_posix(),
    OUTPUT_RECEIPT_MD_REL.as_posix(),
    STATUS_REL.as_posix(),
    STATUS_MD_REL.as_posix(),
    LEGACY_STATUS_REL.as_posix(),
    LEGACY_STATUS_MD_REL.as_posix(),
    LEGACY_AUDIT_REL.as_posix(),
    LEGACY_AUDIT_MD_REL.as_posix(),
    LEGACY_OUTPUT_REL.as_posix(),
    LEGACY_OUTPUT_MD_REL.as_posix(),
}
AUDIT_FINGERPRINT_EXCLUDES = FINGERPRINT_EXCLUDES | {
    "final_artifact_manifest.md",
    "final_artifact_manifest.json",
    "output_run.json",
    "output_artifact_check.md",
    "word_report.md",
    "word_report.zh.md",
    "latex_report.md",
    "latex_guard.md",
    "section_economy_check.md",
    "translation_guard.md",
    "translation_word_report.md",
    "submission_check.md",
    "respond_check.md",
    "render_qa.json",
}
AUDIT_RENDERED_SUFFIXES = {".docx", ".pdf"}


def _rendered_delivery_path(relative: str) -> bool:
    path = Path(relative)
    return (
        len(path.parts) >= 2
        and path.parts[0] == "final_paper"
        and path.suffix.lower() in AUDIT_RENDERED_SUFFIXES
    )
RECEIPT_BOUND_ROOT_FILES = set(RECEIPT_BOUND_ROOT_PATHS)
AUDIT_BOUND_PREFIXES = (
    "review_prompts/",
    "artifacts/",
    "analysis/",
    "final_paper/",
    "reference_materials/integrations/exa_runs/",
)
OUTPUT_BOUND_PREFIXES = AUDIT_BOUND_PREFIXES + (
    "render_qa/",
    "translation_zh/",
    "submission_package/",
    "review_response/",
    "rebuttal/",
)
RECEIPT_REBUILDABLE_VIEWS = set(REBUILDABLE_VIEW_PATHS)
RECEIPT_BOUND_SOURCE_ROLES = {"target_example", "field_sota"}
RECEIPT_SEMANTIC_ONLY_FILES = {"reference_materials/literature_registry.json"}
CLI_STAGES = [*STAGES, *LEGACY_STAGE_ALIASES]
TASK_PROFILE_ALIASES = {
    "": "full_paper",
    "full": "full_paper",
    "full-paper": "full_paper",
    "full_paper": "full_paper",
    "paper": "full_paper",
    "topic": "topic_selection",
    "topic-only": "topic_selection",
    "topic_selection": "topic_selection",
    "design": "research_design",
    "design-only": "research_design",
    "research-design": "research_design",
    "research_design": "research_design",
    "audit": "manuscript_audit",
    "audit-only": "manuscript_audit",
    "manuscript-audit": "manuscript_audit",
    "manuscript_audit": "manuscript_audit",
    "revision": "manuscript_revision",
    "manuscript-revision": "manuscript_revision",
    "manuscript_revision": "manuscript_revision",
}
REQUIRED_SKILLS = REGISTRY_REQUIRED_SKILLS
REQUIRED_ENGINE_FILES = GLOBAL_RUNTIME_FILES
@dataclass
class DoctorResult:
    issues: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def default_skills_dir() -> Path:
    return Path(__file__).resolve().parents[3]


def runtime_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_python(script: Path, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=runtime_env(),
        check=False,
    )


def semver_major(value: str) -> int | None:
    match = re.match(r"^\s*(\d+)\.", value)
    return int(match.group(1)) if match else None


CNKI_SEARCH_SKILLS = set(REGISTRY_CNKI_SEARCH_SKILLS)
INTERNATIONAL_SEARCH_SKILLS = set(REGISTRY_INTERNATIONAL_SEARCH_SKILLS)


def doctor_requirements(
    config: dict[str, Any] | None,
    revision_contract: dict[str, Any] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Resolve dependencies from the active task, publication track, and output route."""
    if config is None:
        return tuple(REQUIRED_SKILLS), tuple(REQUIRED_ENGINE_FILES)
    profile = task_profile(config)
    track = canonical_workflow(config.get("publication_track") or "cnki-cn")
    word_requested = (
        canonical_workflow(config.get("word_output") or "docx") != "none"
        or str(config.get("translation_package") or "none").strip().lower() == "zh"
    )
    page_evidence_required = bool(config.get("page_evidence_required"))
    revision_from = canonical_workflow(
        (revision_contract or {}).get("earliest_reopen_stage")
    )
    revision_needs_research = profile == "manuscript_revision" and revision_from == "research"
    revision_needs_methods = profile == "manuscript_revision" and revision_from in {
        "research",
        "design",
        "execution",
    }

    skills: set[str] = {"cnki-paper"}
    if profile != "manuscript_audit" and (
        profile != "manuscript_revision" or revision_needs_research
    ):
        if track in {"cnki_cn", "cnki-cn", "mixed", ""}:
            skills.update(CNKI_SEARCH_SKILLS)
        if track in {"international_ssci", "international-ssci", "mixed"}:
            skills.update(INTERNATIONAL_SEARCH_SKILLS)
    if profile in {"full_paper", "research_design"} or revision_needs_methods:
        skills.add("empirical-research")
    if page_evidence_required and profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        skills.add("page-evidence")

    runtime_groups = {"core"}
    if config.get("legal_profile") == "chinese-law-v1":
        runtime_groups.add("legal")
        skills.add("chinese-legal-paper")
    if profile != "manuscript_audit" and (
        profile != "manuscript_revision" or revision_needs_research
    ):
        runtime_groups.add("research")
    if profile == "manuscript_revision":
        runtime_groups.add("revision")
    if profile in {"full_paper", "research_design"} or revision_needs_methods:
        runtime_groups.add("methods")
    if track in {"international_ssci", "international-ssci", "mixed"} and profile != "manuscript_audit" and (
        profile != "manuscript_revision" or revision_needs_research
    ):
        runtime_groups.add("international")
    if word_requested and profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        runtime_groups.add("word")
    if profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        runtime_groups.add("audit")
        if str(config.get("scene") or "").strip().lower() in {"journal", "conference", "competition"}:
            runtime_groups.add("results")
    if page_evidence_required:
        runtime_groups.add("page-evidence")
    if quantitative_data_check_required(config):
        runtime_groups.add("quantitative-data")
    files = set(runtime_files_for(runtime_groups))
    if profile in {"full_paper", "manuscript_revision"}:
        canonical_hint = Path(str(config.get("canonical_manuscript") or "final_paper/main.tex"))
        files.update(
            f"cnki-paper/scripts/avereth_core/tools/{name}"
            for name in required_output_tool_scripts(config, canonical_hint)
        )
    return tuple(sorted(skills)), tuple(sorted(files))


def run_doctor(
    skills_dir: Path,
    *,
    repair: bool = False,
    outdir: Path | None = None,
) -> DoctorResult:
    config_read = read_config(outdir) if outdir is not None else None
    config = config_read.payload if config_read is not None and config_read.path is not None else None
    revision_contract: dict[str, Any] | None = None
    if config is not None and task_profile(config) == "manuscript_revision" and outdir is not None:
        revision_path = outdir / REVISION_CONTRACT_REL
        if revision_path.is_file():
            try:
                raw_revision = json.loads(revision_path.read_text(encoding="utf-8-sig"))
                if isinstance(raw_revision, dict):
                    revision_contract = raw_revision
            except (OSError, json.JSONDecodeError):
                revision_contract = None
    required_skills, required_files = doctor_requirements(config, revision_contract)
    result = DoctorResult(
        details={
            "framework_version": FRAMEWORK_VERSION,
            "skills_dir": str(skills_dir),
            "profile": task_profile(config) if config is not None else "global",
            "publication_track": str((config or {}).get("publication_track") or "global"),
            "dependency_mode": "profile-aware" if config is not None else "global",
            "revision_route": str((revision_contract or {}).get("earliest_reopen_stage") or "not-applicable"),
        }
    )
    if config_read is not None:
        result.issues.extend(config_read.issues)
        if config_read.path is not None:
            for issue in validate_workflow_config(config_read.payload):
                if issue not in result.issues:
                    result.issues.append(issue)
    def skill_definition_exists(name: str) -> bool:
        rendered = skills_dir / name / "SKILL.md"
        if rendered.is_file():
            return True
        return name == "cnki-paper" and (
            skills_dir / name / "SKILL.source.md"
        ).is_file()

    def runtime_file_exists(relative: str) -> bool:
        rendered = skills_dir / relative
        if rendered.is_file():
            return True
        return relative == "cnki-paper/SKILL.md" and (
            skills_dir / "cnki-paper/SKILL.source.md"
        ).is_file()

    missing_skills = [name for name in required_skills if not skill_definition_exists(name)]
    if missing_skills:
        result.issues.append("missing required skills: " + ", ".join(missing_skills))

    missing_files = [relative for relative in required_files if not runtime_file_exists(relative)]
    if missing_files:
        result.issues.append("missing CNKI-Paper local engine files: " + ", ".join(missing_files))
    scientific_groups = scientific_runtime_groups_for_config(config or {})
    result.details["scientific_runtime_groups"] = list(scientific_groups)
    for issue in scientific_runtime_issues(skills_dir, groups=scientific_groups):
        if issue not in result.issues:
            result.issues.append(issue)
    needs_rendered_output = bool(
        config is not None
        and task_profile(config) in {"full_paper", "manuscript_revision"}
        and (
            str(config.get("word_output") or "none") == "docx"
            or str(config.get("pdf_output") or "none") == "pdf"
            or str(config.get("translation_package") or "none") == "zh"
        )
    )
    if outdir is not None and needs_rendered_output and importlib.util.find_spec("pypdf") is None:
        result.issues.append("missing Python dependency required for rendered PDF QA: pypdf")

    if outdir is not None:
        locks = inspect_workspace_locks(outdir)
        result.details["workspace_locks"] = [lock.as_dict() for lock in locks]
        for lock in locks:
            if lock.state == "active" and lock.pid == os.getpid():
                # Gate actions re-run the read-only status projection while
                # holding their own transition locks.  Record those locks but
                # never let the current process block itself.
                continue
            action = (
                "review `recover-lock OUTDIR`, then rerun with --confirm only if the owner is dead"
                if lock.recoverable
                else "do not remove it automatically"
            )
            result.issues.append(
                f"workspace lock {lock.path} is {lock.state}: {lock.reason}; {action}"
            )

    result.details["engine"] = "avereth_core"
    result.details["engine_version"] = FRAMEWORK_VERSION
    result.details["state_model"] = "eight-stage-local"
    if repair:
        result.details["repair"] = "deprecated-no-op; doctor is read-only in v6"
    return result


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _research_decision_projection(outdir: Path) -> tuple[str, dict[str, Any] | None]:
    decision = _json_object(outdir / "research_decision.json")
    if not decision:
        return "absent", None
    try:
        from research_decision import preclearance_readiness, project_decision_state
    except ImportError:
        return "invalid", None
    try:
        return project_decision_state(decision), preclearance_readiness(outdir, decision)
    except (OSError, ValueError, TypeError):
        return "invalid", None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def invalidate_output_receipt(outdir: Path) -> None:
    _write_receipt_state(
        outdir,
        kind="output",
        status="IN_PROGRESS",
        reason="output rendering and validation are in progress",
    )


def _write_receipt_state(
    outdir: Path,
    *,
    kind: str,
    status: str,
    reason: str = "",
    findings: list[Finding] | None = None,
) -> None:
    schema = AUDIT_RECEIPT_SCHEMA if kind == "audit" else OUTPUT_RECEIPT_SCHEMA
    json_rel = AUDIT_RECEIPT_REL if kind == "audit" else OUTPUT_RECEIPT_REL
    md_rel = AUDIT_RECEIPT_MD_REL if kind == "audit" else OUTPUT_RECEIPT_MD_REL
    payload: dict[str, Any] = {
        "schema_version": schema,
        "framework_version": FRAMEWORK_VERSION,
        "stage": kind,
        "status": status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if reason:
        payload["reason"] = reason
    if findings:
        payload["findings"] = [finding.as_dict() for finding in findings]
    _write_json(outdir / json_rel, payload)
    lines = [
        f"# Avereth {kind.title()} Receipt",
        "",
        f"Status: {status}",
        "",
    ]
    if reason:
        lines.append(f"Reason: {reason}")
    if findings:
        lines.extend(["", "## Findings", ""])
        lines.extend(f"- [{finding.code}] {finding.message}" for finding in findings)
    lines.append("")
    _atomic_write_text(outdir / md_rel, "\n".join(lines))


def invalidate_receipts_for_audit(outdir: Path) -> None:
    """Invalidate stale PASS receipts before any audit action can mutate reports."""

    _write_receipt_state(
        outdir,
        kind="audit",
        status="IN_PROGRESS",
        reason="academic audit actions are in progress",
    )
    if (outdir / OUTPUT_RECEIPT_REL).is_file():
        _write_receipt_state(
            outdir,
            kind="output",
            status="INVALIDATED",
            reason="academic audit rerun",
        )


def doctor_markdown(result: DoctorResult) -> str:
    lines = [
        "# CNKI-Paper Local Research Engine Doctor",
        "",
        f"Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Runtime",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in result.details.items())
    if result.issues:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in result.issues)
    lines.append("")
    return "\n".join(lines)


def write_passthrough(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)


def revision_reopen_stage(outdir: Path) -> str | None:
    """Return the declared revision boundary without treating it as a new public stage."""
    if task_profile(load_project_config(outdir)) != "manuscript_revision":
        return None
    try:
        payload = json.loads((outdir / REVISION_CONTRACT_REL).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    stage = canonical_workflow(payload.get("earliest_reopen_stage"))
    return stage if stage in STAGES else None


def load_project_config(outdir: Path) -> dict[str, Any]:
    return read_config(outdir).payload


def canonical_workflow(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def task_profile(config: dict[str, Any]) -> str:
    token = canonical_workflow(config.get("task_profile"))
    return TASK_PROFILE_ALIASES.get(token, token or "full_paper")


def scientific_runtime_groups_for_config(config: dict[str, Any]) -> tuple[str, ...]:
    """Project only the scientific contracts that this task can actually use."""

    profile = task_profile(config)
    groups = {"venue"}
    if config.get("legal_profile") == "chinese-law-v1":
        groups.add("legal")
    if profile != "manuscript_audit":
        groups.add("research")
    if profile in {"full_paper", "research_design", "manuscript_revision"}:
        groups.add("methods")
    return tuple(sorted(groups))


def direction_veto_summary(
    config: dict[str, Any] | None,
    *,
    available: bool,
) -> dict[str, Any]:
    """Describe the optional post-acquisition direction veto without gating research."""
    if not available:
        return {
            "status": "not-yet-available",
            "blocking": False,
            "excluded_directions": [],
            "issues": [],
            "formal_question_confirmation_still_required": True,
        }
    active = config if isinstance(config, dict) else {}
    raw = active.get("direction_veto")
    if raw in (None, {}):
        return {
            "status": "available",
            "blocking": False,
            "excluded_directions": [],
            "issues": [],
            "formal_question_confirmation_still_required": True,
        }
    if not isinstance(raw, dict):
        return {
            "status": "needs-review",
            "blocking": False,
            "excluded_directions": [],
            "issues": ["direction_veto must be an object when recorded"],
            "formal_question_confirmation_still_required": True,
        }
    status = canonical_workflow(raw.get("status"))
    excluded = raw.get("excluded_directions")
    values = (
        [str(item).strip() for item in excluded if str(item).strip()]
        if isinstance(excluded, list)
        else []
    )
    issues: list[str] = []
    if status not in {"recorded", "declined", "pending"}:
        issues.append("direction_veto.status must be recorded, declined, or pending")
    if status == "recorded" and not values:
        issues.append("a recorded direction veto must name at least one excluded direction")
    if status == "declined" and values:
        issues.append("a declined direction veto cannot also list excluded directions")
    if status in {"recorded", "declined"} and not str(
        raw.get("confirmation_evidence") or ""
    ).strip():
        issues.append("a direction-veto decision must retain user confirmation evidence")
    return {
        "status": "needs-review" if issues else (status or "available"),
        "blocking": False,
        "excluded_directions": values,
        "issues": issues,
        "formal_question_confirmation_still_required": True,
    }


def _receipt_bound_sources(outdir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = outdir / "reference_materials" / "literature_registry.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
        return {}, []
    if not isinstance(payload, dict):
        return {}, []
    selected: list[dict[str, Any]] = []
    for source in payload.get("sources") or []:
        if not isinstance(source, dict):
            continue
        raw_roles = source.get("roles") or source.get("role") or []
        if not isinstance(raw_roles, list):
            raw_roles = [raw_roles]
        roles = {canonical_workflow(item) for item in raw_roles if str(item).strip()}
        final_source = canonical_workflow(source.get("citation_scope")) == "final_source"
        if final_source or roles.intersection(RECEIPT_BOUND_SOURCE_ROLES):
            selected.append(source)
    selected.sort(key=lambda item: str(item.get("source_id") or ""))
    return payload, selected


def acquisition_binding_summary(outdir: Path) -> dict[str, Any]:
    """Bind only adopted/role-bearing sources, not unused discovery records."""
    registry, sources = _receipt_bound_sources(outdir)
    semantic_sources: list[dict[str, Any]] = []
    for source in sources:
        semantic = semantic_source_payload(source)
        semantic["role"] = source.get("role")
        semantic_sources.append(semantic)
    raw = json.dumps(
        {
            "publication_track": registry.get("publication_track"),
            "sources": semantic_sources,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "source_ids": [str(source.get("source_id") or "") for source in sources],
        "digest": hashlib.sha256(raw).hexdigest(),
    }


def receipt_bound_source_paths(outdir: Path) -> set[str]:
    """Return local artifacts for adopted/role-bearing sources only."""
    _, sources = _receipt_bound_sources(outdir)
    root = outdir.resolve()
    paths: set[str] = set()
    for source in sources:
        verification = (
            source.get("verification")
            if isinstance(source.get("verification"), dict)
            else {}
        )
        for raw in (source.get("local_file"), verification.get("ocr_text_file")):
            value = str(raw or "").strip()
            if not value:
                continue
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = root / candidate
            try:
                resolved = candidate.resolve()
                relative = resolved.relative_to(root).as_posix()
            except (OSError, ValueError):
                continue
            if resolved.is_file():
                paths.add(relative)
    return paths


def receipt_bound_material_paths(outdir: Path) -> set[str]:
    """Bind only hash-verified evidence files used by the selected F2 basis."""

    _base, registry, material_result = validate_material_contract(outdir, scope="research")
    _feasibility_base, feasibility, feasibility_result = validate_feasibility_contract(outdir)
    if registry is None or feasibility is None or material_result.errors or feasibility_result.errors:
        return set()
    selected_id = str(feasibility.get("selected_candidate_id") or "").strip().upper()
    assessment = next(
        (
            item
            for item in feasibility.get("candidate_assessments") or []
            if isinstance(item, dict)
            and str(item.get("candidate_id") or "").strip().upper() == selected_id
        ),
        None,
    )
    if assessment is None:
        return set()
    wanted = {
        (
            str(reference.get("material_id") or "").strip().upper(),
            str(probe_id or "").strip().upper(),
        )
        for reference in assessment.get("material_refs") or []
        if isinstance(reference, dict)
        for probe_id in reference.get("probe_ids") or []
    }
    paths: set[str] = set()
    for material in registry.get("materials") or []:
        if not isinstance(material, dict):
            continue
        material_id = str(material.get("material_id") or "").strip().upper()
        for probe in material.get("probes") or []:
            if not isinstance(probe, dict):
                continue
            probe_id = str(probe.get("probe_id") or "").strip().upper()
            if (material_id, probe_id) not in wanted:
                continue
            for evidence in probe.get("evidence_files") or []:
                if isinstance(evidence, dict):
                    relative = str(evidence.get("path") or "").strip().replace("\\", "/")
                    if relative and (outdir / relative).is_file():
                        paths.add(relative)
    return paths


def feasibility_binding_summary(outdir: Path) -> dict[str, Any]:
    reference, issues = feasibility_reference(outdir)
    return {
        "status": "PASS" if reference is not None else "BLOCKED",
        "reference": reference,
        "evidence_files": sorted(receipt_bound_material_paths(outdir)),
        "issues": issues,
    }


def artifact_manifest(
    outdir: Path,
    *,
    excludes: set[str],
    include_rendered: bool = True,
    bound_prefixes: tuple[str, ...] = OUTPUT_BOUND_PREFIXES,
) -> list[str]:
    """Return the declared, load-bearing files bound to a receipt.

    Operational notes, migration backups, caches, and unrelated scratch files are intentionally
    outside this manifest. New evidence, review, manuscript, and final-delivery files live in one
    of the bound roots/prefixes and therefore invalidate the relevant receipt.
    """
    if not outdir.is_dir():
        return []
    manifest: set[str] = set(receipt_bound_source_paths(outdir))
    manifest.update(receipt_bound_material_paths(outdir))
    manifest.update(manuscript_receipt_closure_paths(outdir))
    from commonplace_writing import receipt_paths as commonplace_receipt_paths
    manifest.update(commonplace_receipt_paths(outdir))
    from .infrastructure.legal_domain import receipt_paths as legal_receipt_paths
    manifest.update(legal_receipt_paths(outdir))
    for relative in RECEIPT_BOUND_ROOT_FILES:
        path = outdir / relative
        if path.is_file():
            manifest.add(relative)
    for path in outdir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(outdir).as_posix()
        if any(
            relative == prefix or relative.startswith(prefix)
            for prefix in bound_prefixes
        ):
            manifest.add(relative)
    return sorted(
        relative
        for relative in manifest
        if relative not in excludes
        and (include_rendered or not _rendered_delivery_path(relative))
        and relative not in RECEIPT_REBUILDABLE_VIEWS
        and relative not in RECEIPT_SEMANTIC_ONLY_FILES
        and not is_legacy_gate_view(relative)
    )


def artifact_fingerprint(
    outdir: Path,
    *,
    excludes: set[str],
    include_rendered: bool = True,
    bound_prefixes: tuple[str, ...] = OUTPUT_BOUND_PREFIXES,
) -> str:
    """Fingerprint the declared receipt manifest, not the entire workspace tree."""
    digest = hashlib.sha256()
    for relative in artifact_manifest(
        outdir,
        excludes=excludes,
        include_rendered=include_rendered,
        bound_prefixes=bound_prefixes,
    ):
        path = outdir / relative
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        try:
            with path.open("rb") as handle:
                while chunk := handle.read(1024 * 1024):
                    digest.update(chunk)
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\n")
    return digest.hexdigest()


def output_fingerprint(outdir: Path) -> str:
    return artifact_fingerprint(outdir, excludes=FINGERPRINT_EXCLUDES)


def audit_fingerprint(outdir: Path) -> str:
    return artifact_fingerprint(
        outdir,
        excludes=AUDIT_FINGERPRINT_EXCLUDES,
        include_rendered=False,
        bound_prefixes=AUDIT_BOUND_PREFIXES,
    )


def _manuscript_receipt_currentness_issue(
    outdir: Path,
    *,
    existing_lineage_only: bool = False,
) -> str:
    config = load_project_config(outdir)
    if not compiler_applies(config):
        return ""
    if existing_lineage_only and not any(
        (outdir / relative).is_file()
        for relative in (MANUSCRIPT_IR_REL, MANUSCRIPT_TRACE_REL)
    ):
        return ""
    issues = validate_manuscript(outdir, config)
    if not issues:
        return ""
    first = issues[0]
    return f"manuscript compiler currentness failed [{first.code}]: {first.message}"


def _read_schema(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
        return ""
    return str(payload.get("schema_version") or "") if isinstance(payload, dict) else ""


def _read_json_field(path: Path, field_name: str) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
        return ""
    return str(payload.get(field_name) or "") if isinstance(payload, dict) else ""


def integration_artifacts_present(outdir: Path) -> bool:
    return any(
        (outdir / relative).is_file()
        for relative in (
            Path("reference_materials/integrations/exa_runs/manifest.json"),
            Path("reference_materials/integrations/zotero_snapshot.json"),
        )
    )


def contract_metadata(outdir: Path) -> dict[str, Any]:
    acquisition_schema = _read_schema(
        outdir / "reference_materials" / "literature_registry.json"
    )
    literature_analysis_schema = _read_schema(outdir / "literature_analysis.json")
    literature_analysis_state = _read_json_field(
        outdir / "literature_analysis.json",
        "migration_status",
    )
    design_schema = _read_schema(outdir / "research_design.json")
    execution_schema = _read_schema(outdir / "method_execution.json")
    material_schema = _read_schema(outdir / "reference_materials" / "research_material_registry.json")
    feasibility_schema = _read_schema(outdir / "research_feasibility.json")
    families: list[str] = []
    try:
        design = json.loads((outdir / "research_design.json").read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, AttributeError):
        design = {}
    if isinstance(design, dict):
        if design_schema in {DESIGN_SCHEMA_V2, DESIGN_SCHEMA_V3, DESIGN_SCHEMA_V4}:
            for route in design.get("method_routes") or []:
                if isinstance(route, dict):
                    family = str(route.get("family") or "").strip()
                    if family and family not in families:
                        families.append(family)
        elif design_schema == DESIGN_SCHEMA_V1:
            old_design = design.get("design")
            if isinstance(old_design, dict):
                family = str(old_design.get("family") or "").strip()
                if family:
                    families.append(family)
    case_design_state = "unavailable"
    if design_schema in {DESIGN_SCHEMA_V3, DESIGN_SCHEMA_V4} and isinstance(design, dict):
        case_design = design.get("case_design")
        if isinstance(case_design, dict):
            case_design_state = str(case_design.get("applicability") or "missing")
        else:
            case_design_state = "missing"
    if design_schema == DESIGN_SCHEMA_V4:
        migration_state = (
            "current"
            if execution_schema in {"", EXECUTION_SCHEMA_V3}
            else (
                "execution-needs-v3-migration"
                if execution_schema in {EXECUTION_SCHEMA_V1, EXECUTION_SCHEMA_V2}
                else "execution-schema-unsupported"
            )
        )
    elif design_schema == DESIGN_SCHEMA_V3:
        migration_state = (
            "legacy-v3-v2-read-render-migrate-only"
            if execution_schema == EXECUTION_SCHEMA_V2
            else "design-v3-needs-v4-migration"
        )
    elif design_schema == DESIGN_SCHEMA_V2:
        migration_state = "design-v2-needs-migration"
    elif design_schema == DESIGN_SCHEMA_V1:
        migration_state = "design-v1-needs-migration"
    elif design_schema:
        migration_state = "future-or-unsupported-design-schema"
    else:
        migration_state = "design-missing"
    integration_enabled = integration_artifacts_present(outdir)
    if acquisition_schema == ACQUISITION_SCHEMA_V3:
        acquisition_migration_state = "current"
    elif acquisition_schema == ACQUISITION_SCHEMA_V2:
        acquisition_migration_state = (
            "acquisition-v2-needs-migration"
            if integration_enabled
            else "current-compatible-v2"
        )
    elif acquisition_schema == ACQUISITION_SCHEMA_V1:
        acquisition_migration_state = "acquisition-v1-needs-migration"
    elif acquisition_schema:
        acquisition_migration_state = "future-or-unsupported-acquisition-schema"
    else:
        acquisition_migration_state = "acquisition-missing"
    return {
        "acquisition_schema": acquisition_schema or "missing",
        "acquisition_migration_state": acquisition_migration_state,
        "integration_enabled": integration_enabled,
        "literature_analysis_schema": literature_analysis_schema or "missing",
        "literature_analysis_state": literature_analysis_state or "missing",
        "literature_analysis_digest": contract_digest(outdir / "literature_analysis.json"),
        "research_material_schema": material_schema or "missing",
        "research_feasibility_schema": feasibility_schema or "missing",
        "research_feasibility_digest": contract_digest(outdir / "research_feasibility.json"),
        "design_schema": design_schema or "missing",
        "execution_schema": execution_schema or "missing",
        "migration_state": migration_state,
        "case_design_state": case_design_state,
        "active_method_families": families,
        "dialogic_argument_digest": contract_digest(
            outdir / "dialogic_argument_map.md"
        ),
    }


def method_adapter_registry_digest(skills_dir: Path | None = None) -> str:
    active_skills_dir = skills_dir or Path(__file__).resolve().parents[3]
    path = (
        active_skills_dir
        / "empirical-research"
        / "references"
        / "method-adapter-registry.json"
    )
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def contract_digest(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def canonical_manuscript_binding(outdir: Path) -> dict[str, str]:
    """Bind the exact canonical source selected for academic audit."""

    try:
        return select_manuscript(outdir, load_project_config(outdir)).as_dict()
    except ManuscriptSelectionError:
        return {}


def literature_sufficiency_summary(outdir: Path, *, stage: str = "research") -> dict[str, Any]:
    if not (outdir / "literature_analysis.json").is_file():
        config = load_project_config(outdir)
        profile = task_profile(config)
        scene = canonical_workflow(config.get("scene") or "journal")
        minimum = fallback_floor(profile, scene)
        return {
            "status": "unassessed",
            "baseline_mode": "task-fallback",
            "hard_minimum": minimum,
            "qualified_scholarly_count": 0,
            "gap": minimum,
            "counting_note": (
                "no v2 content-verified literature analysis exists; manuscript references are not "
                "counted until their identities, relevance, and reading status are registered"
            ),
        }
    result, _ = validate_analysis(outdir, stage=stage)
    raw = result.stats.get("literature_sufficiency")
    summary = dict(raw) if isinstance(raw, dict) else {}
    if not summary:
        summary = {"status": "invalid", "gap": None, "qualified_scholarly_count": 0}
    summary["validation_ok"] = result.ok
    summary["blocking_issue_count"] = len(result.issues)
    return summary


def route_summary(outdir: Path, config: dict[str, Any] | None = None, *, stage: str = "research") -> dict[str, Any]:
    active = config if isinstance(config, dict) else load_project_config(outdir)
    profile = task_profile(active)
    if profile != "manuscript_revision":
        return {
            "profile": profile,
            "earliest_reopen_stage": None,
            "assurance_level": "full" if profile != "manuscript_audit" else "declared-by-audit",
            "change_classes": [],
            "valid": True,
            "issues": [],
        }
    contract, issues = load_and_validate_revision(outdir, stage=stage)
    summary = revision_route_plan(contract)
    summary.update(
        {
            "profile": profile,
            "schema_version": str(contract.get("schema_version") or "missing"),
            "contract_digest": contract_digest(outdir / REVISION_CONTRACT_REL),
            "valid": not issues,
            "issues": issues,
        }
    )
    return summary


def stage_semantic_summaries(outdir: Path) -> dict[str, Any]:
    """Bind receipts to compact stage meanings, not generated prose views."""
    config = load_project_config(outdir)
    config_read = read_config(outdir)
    config_digest = contract_digest(config_read.path) if config_read.path is not None else ""
    return {
        "intake": {
            "profile": task_profile(config),
            "config_digest": config_digest,
            "problem_orientation_digest": contract_digest(outdir / "problem_orientation.md"),
        },
        "acquisition": {
            "schema": _read_schema(outdir / "reference_materials" / "literature_registry.json"),
            "load_bearing_sources": acquisition_binding_summary(outdir),
            "selected_material_basis": feasibility_binding_summary(outdir),
        },
        "research": {
            "schema": _read_schema(outdir / "literature_analysis.json"),
            "analysis_digest": contract_digest(outdir / "literature_analysis.json"),
            "sufficiency": literature_sufficiency_summary(outdir, stage="research"),
            "feasibility": feasibility_binding_summary(outdir),
        },
        "design": {
            "schema": _read_schema(outdir / "research_design.json"),
            "digest": contract_digest(outdir / "research_design.json"),
        },
        "execution": {
            "schema": _read_schema(outdir / "method_execution.json"),
            "digest": contract_digest(outdir / "method_execution.json"),
        },
        "build": {
            "dialogue_digest": contract_digest(outdir / "dialogic_argument_map.md"),
            "canonical_manuscript": canonical_manuscript_binding(outdir),
            "build_run_digest": contract_digest(outdir / "build_run.json"),
        },
        "route": route_summary(outdir, config, stage="audit"),
    }


def dialogic_argument_summary(outdir: Path) -> dict[str, Any]:
    result = validate_dialogic_argument(outdir)
    return {
        "status": "PASS" if result.ok else "FAIL",
        "target_type": result.coverage.get("target_type", "missing"),
        "positions": int(result.coverage.get("positions", 0) or 0),
        "mapped_sources": int(result.coverage.get("mapped_sources", 0) or 0),
        "mapped_claims": int(result.coverage.get("mapped_claims", 0) or 0),
        "mapped_evidence": int(result.coverage.get("mapped_evidence", 0) or 0),
        "mapped_executions": int(result.coverage.get("mapped_executions", 0) or 0),
        "voice_units": int(result.coverage.get("voice_units", 0) or 0),
        "revision_rows": int(result.coverage.get("revision_rows", 0) or 0),
    }


def review_assurance_summary(outdir: Path) -> dict[str, Any]:
    return lifecycle_assurance_summary(outdir)


def review_assurance_status(outdir: Path) -> tuple[bool, list[str]]:
    summary = review_assurance_summary(outdir)
    return bool(summary.get("lifecycle_ready")), list(summary.get("issues") or [])


def write_audit_receipt(outdir: Path, *, passed: bool) -> bool:
    if not outdir.is_dir():
        return False
    if passed:
        completion = validate_audit_completion(outdir, config=load_project_config(outdir))
        passed = bool(completion.ok and review_assurance_summary(outdir).get("lifecycle_ready"))
    runtime_groups = scientific_runtime_groups_for_config(load_project_config(outdir))
    runtime_issues = scientific_runtime_issues(groups=runtime_groups)
    if passed and runtime_issues:
        passed = False
    metadata = contract_metadata(outdir)
    dialogue_summary = dialogic_argument_summary(outdir)
    review_summary = review_assurance_summary(outdir)
    semantic_summaries = stage_semantic_summaries(outdir)
    route = semantic_summaries["route"]
    literature_sufficiency = semantic_summaries["research"]["sufficiency"]
    manifest = artifact_manifest(
        outdir,
        excludes=AUDIT_FINGERPRINT_EXCLUDES,
        include_rendered=False,
        bound_prefixes=AUDIT_BOUND_PREFIXES,
    )
    payload = {
        "schema_version": AUDIT_RECEIPT_SCHEMA,
        "framework_version": FRAMEWORK_VERSION,
        "acquisition_schema_version": metadata["acquisition_schema"],
        "literature_analysis_schema_version": metadata["literature_analysis_schema"],
        "literature_analysis_state": metadata["literature_analysis_state"],
        "design_schema_version": metadata["design_schema"],
        "execution_schema_version": metadata["execution_schema"],
        "acquisition_binding": acquisition_binding_summary(outdir),
        "literature_analysis_digest": metadata["literature_analysis_digest"],
        "design_contract_digest": contract_digest(outdir / "research_design.json"),
        "execution_contract_digest": contract_digest(outdir / "method_execution.json"),
        "dialogic_argument_digest": contract_digest(outdir / "dialogic_argument_map.md"),
        "dialogic_argument_summary": dialogue_summary,
        "review_assurance_digest": contract_digest(outdir / REVIEW_ASSURANCE_REL),
        "review_assurance": review_summary,
        "canonical_manuscript": canonical_manuscript_binding(outdir),
        "route": route,
        "assurance_level": route.get("assurance_level", "unknown"),
        "literature_sufficiency": literature_sufficiency,
        "stage_semantic_summaries": semantic_summaries,
        "method_adapter_registry_digest": method_adapter_registry_digest(),
        "scientific_runtime_groups": list(runtime_groups),
        "scientific_runtime_digest": scientific_runtime_digest(groups=runtime_groups),
        "stage": "audit",
        "status": "PASS" if passed else "FAIL",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "artifact_manifest": manifest,
        "artifact_fingerprint": audit_fingerprint(outdir),
    }
    _write_json(outdir / AUDIT_RECEIPT_REL, payload)
    markdown = "\n".join(
        [
            "# CNKI-Paper Unified Audit Gate",
            "",
            f"Status: {payload['status']}",
            "",
            f"- schema_version: {payload['schema_version']}",
            f"- framework_version: {FRAMEWORK_VERSION}",
            f"- acquisition_schema_version: {payload['acquisition_schema_version']}",
            f"- literature_analysis_schema_version: {payload['literature_analysis_schema_version']}",
            f"- literature_analysis_state: {payload['literature_analysis_state']}",
            f"- design_schema_version: {payload['design_schema_version']}",
            f"- execution_schema_version: {payload['execution_schema_version']}",
            f"- acquisition_binding: {json.dumps(payload['acquisition_binding'], ensure_ascii=False, sort_keys=True)}",
            f"- literature_analysis_digest: {payload['literature_analysis_digest']}",
            f"- design_contract_digest: {payload['design_contract_digest']}",
            f"- execution_contract_digest: {payload['execution_contract_digest']}",
            f"- dialogic_argument_digest: {payload['dialogic_argument_digest']}",
            f"- dialogic_argument_summary: {json.dumps(payload['dialogic_argument_summary'], ensure_ascii=False, sort_keys=True)}",
            f"- review_assurance: {json.dumps(payload['review_assurance'], ensure_ascii=False, sort_keys=True)}",
            f"- route: {json.dumps(payload['route'], ensure_ascii=False, sort_keys=True)}",
            f"- assurance_level: {payload['assurance_level']}",
            f"- literature_sufficiency: {json.dumps(payload['literature_sufficiency'], ensure_ascii=False, sort_keys=True)}",
            f"- review_assurance_digest: {payload['review_assurance_digest']}",
            f"- method_adapter_registry_digest: {payload['method_adapter_registry_digest']}",
            f"- scientific_runtime_digest: {payload['scientific_runtime_digest']}",
            f"- scientific_runtime_groups: {','.join(payload['scientific_runtime_groups'])}",
            f"- checked_at: {payload['checked_at']}",
            f"- artifact_manifest_files: {len(payload['artifact_manifest'])}",
            f"- artifact_fingerprint: {payload['artifact_fingerprint']}",
            "",
        ]
    )
    _atomic_write_text(outdir / AUDIT_RECEIPT_MD_REL, markdown)
    return passed


def output_eligibility_status(
    outdir: Path,
    config: dict[str, Any] | None = None,
) -> GateResult:
    """Pure policy check that must pass before any final delivery is published."""

    active = dict(config if config is not None else load_project_config(outdir))
    if task_profile(active) != "manuscript_revision":
        return GateResult.pass_("output")
    summaries = stage_semantic_summaries(outdir)
    route = summaries["route"]
    sufficiency = summaries["research"]["sufficiency"]
    findings: list[Finding] = []
    if route.get("valid") is not True:
        findings.append(Finding("OUTPUT.REVISION_ROUTE", "revision route is missing or invalid"))
    if route.get("assurance_level") == "legacy_limited":
        findings.append(
            Finding(
                "OUTPUT.LEGACY_LIMITED",
                "legacy-limited revision evidence cannot receive a v6 output PASS",
            )
        )
    if sufficiency.get("status") != "pass":
        findings.append(
            Finding(
                "OUTPUT.LITERATURE_SUFFICIENCY",
                "revision literature sufficiency must pass before final publication",
            )
        )
    return GateResult.blocked("output", findings) if findings else GateResult.pass_("output")


def write_output_receipt(outdir: Path, *, passed: bool) -> bool:
    if not outdir.is_dir():
        return False
    audit_ok, _ = audit_receipt_status(outdir)
    config = load_project_config(outdir)
    semantic_summaries = stage_semantic_summaries(outdir)
    route = semantic_summaries["route"]
    literature_sufficiency = semantic_summaries["research"]["sufficiency"]
    eligibility = output_eligibility_status(outdir, config)
    passed = bool(passed and eligibility.ok)
    if passed:
        completion = validate_output_completion(outdir, config=config)
        passed = completion.ok
    passed = bool(passed and audit_ok)
    runtime_groups = scientific_runtime_groups_for_config(config)
    runtime_issues = scientific_runtime_issues(groups=runtime_groups)
    if passed and runtime_issues:
        passed = False
    metadata = contract_metadata(outdir)
    dialogue_summary = dialogic_argument_summary(outdir)
    review_summary = review_assurance_summary(outdir)
    manifest = artifact_manifest(outdir, excludes=FINGERPRINT_EXCLUDES)
    payload = {
        "schema_version": OUTPUT_RECEIPT_SCHEMA,
        "framework_version": FRAMEWORK_VERSION,
        "acquisition_schema_version": metadata["acquisition_schema"],
        "literature_analysis_schema_version": metadata["literature_analysis_schema"],
        "literature_analysis_state": metadata["literature_analysis_state"],
        "design_schema_version": metadata["design_schema"],
        "execution_schema_version": metadata["execution_schema"],
        "acquisition_binding": acquisition_binding_summary(outdir),
        "literature_analysis_digest": metadata["literature_analysis_digest"],
        "design_contract_digest": contract_digest(outdir / "research_design.json"),
        "execution_contract_digest": contract_digest(outdir / "method_execution.json"),
        "dialogic_argument_digest": contract_digest(outdir / "dialogic_argument_map.md"),
        "dialogic_argument_summary": dialogue_summary,
        "review_assurance_digest": contract_digest(outdir / REVIEW_ASSURANCE_REL),
        "review_assurance": review_summary,
        "route": route,
        "assurance_level": route.get("assurance_level", "unknown"),
        "literature_sufficiency": literature_sufficiency,
        "stage_semantic_summaries": semantic_summaries,
        "method_adapter_registry_digest": method_adapter_registry_digest(),
        "scientific_runtime_groups": list(runtime_groups),
        "scientific_runtime_digest": scientific_runtime_digest(groups=runtime_groups),
        "audit_receipt_digest": contract_digest(outdir / AUDIT_RECEIPT_REL),
        "canonical_manuscript": canonical_manuscript_binding(outdir),
        "output_run_digest": contract_digest(outdir / "output_run.json"),
        "final_manifest_digest": contract_digest(outdir / "final_artifact_manifest.json"),
        "render_qa_digest": contract_digest(outdir / "render_qa.json"),
        "stage": "output",
        "status": "PASS" if passed else "FAIL",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "artifact_manifest": manifest,
        "artifact_fingerprint": output_fingerprint(outdir),
    }
    _write_json(outdir / OUTPUT_RECEIPT_REL, payload)
    markdown = "\n".join(
        [
            "# CNKI-Paper Unified Output Gate",
            "",
            f"Status: {payload['status']}",
            "",
            f"- schema_version: {payload['schema_version']}",
            f"- framework_version: {FRAMEWORK_VERSION}",
            f"- acquisition_schema_version: {payload['acquisition_schema_version']}",
            f"- literature_analysis_schema_version: {payload['literature_analysis_schema_version']}",
            f"- literature_analysis_state: {payload['literature_analysis_state']}",
            f"- design_schema_version: {payload['design_schema_version']}",
            f"- execution_schema_version: {payload['execution_schema_version']}",
            f"- acquisition_binding: {json.dumps(payload['acquisition_binding'], ensure_ascii=False, sort_keys=True)}",
            f"- literature_analysis_digest: {payload['literature_analysis_digest']}",
            f"- design_contract_digest: {payload['design_contract_digest']}",
            f"- execution_contract_digest: {payload['execution_contract_digest']}",
            f"- dialogic_argument_digest: {payload['dialogic_argument_digest']}",
            f"- dialogic_argument_summary: {json.dumps(payload['dialogic_argument_summary'], ensure_ascii=False, sort_keys=True)}",
            f"- review_assurance: {json.dumps(payload['review_assurance'], ensure_ascii=False, sort_keys=True)}",
            f"- route: {json.dumps(payload['route'], ensure_ascii=False, sort_keys=True)}",
            f"- assurance_level: {payload['assurance_level']}",
            f"- literature_sufficiency: {json.dumps(payload['literature_sufficiency'], ensure_ascii=False, sort_keys=True)}",
            f"- review_assurance_digest: {payload['review_assurance_digest']}",
            f"- method_adapter_registry_digest: {payload['method_adapter_registry_digest']}",
            f"- scientific_runtime_digest: {payload['scientific_runtime_digest']}",
            f"- scientific_runtime_groups: {','.join(payload['scientific_runtime_groups'])}",
            f"- audit_receipt_digest: {payload['audit_receipt_digest']}",
            f"- checked_at: {payload['checked_at']}",
            f"- artifact_manifest_files: {len(payload['artifact_manifest'])}",
            f"- artifact_fingerprint: {payload['artifact_fingerprint']}",
            "",
        ]
    )
    _atomic_write_text(outdir / OUTPUT_RECEIPT_MD_REL, markdown)
    return passed


def audit_receipt_status(outdir: Path) -> tuple[bool, str]:
    receipt = read_receipt(outdir, "audit")
    if receipt.path is None:
        return False, "unified audit gate has not been run"
    if receipt.legacy:
        return False, "legacy v5 audit receipt is historical evidence only; run the v6 audit gate"
    payload = receipt.payload
    if not payload:
        return False, "unified audit gate receipt is invalid"
    if payload.get("status") != "PASS":
        return False, "last unified audit gate did not pass"
    if payload.get("schema_version") != AUDIT_RECEIPT_SCHEMA:
        return False, "unified audit gate receipt uses an unsupported schema version"
    if payload.get("framework_version") != FRAMEWORK_VERSION:
        return False, "unified audit gate receipt belongs to another framework version"
    manuscript_issue = _manuscript_receipt_currentness_issue(
        outdir,
        existing_lineage_only=True,
    )
    if manuscript_issue:
        return False, manuscript_issue
    metadata = contract_metadata(outdir)
    if payload.get("acquisition_schema_version") != metadata["acquisition_schema"]:
        return False, "acquisition schema changed after the unified audit gate"
    if payload.get("literature_analysis_schema_version") != metadata["literature_analysis_schema"]:
        return False, "literature-analysis schema changed after the unified audit gate"
    if payload.get("literature_analysis_state") != metadata["literature_analysis_state"]:
        return False, "literature-analysis migration state changed after the unified audit gate"
    if payload.get("design_schema_version") != metadata["design_schema"]:
        return False, "research-design schema changed after the unified audit gate"
    if payload.get("execution_schema_version") != metadata["execution_schema"]:
        return False, "method-execution schema changed after the unified audit gate"
    if payload.get("acquisition_binding") != acquisition_binding_summary(outdir):
        return False, "load-bearing source identity, permission, verification, role, or file binding changed after the unified audit gate"
    if payload.get("literature_analysis_digest") != metadata["literature_analysis_digest"]:
        return False, "critical reading or literature synthesis changed after the unified audit gate"
    if payload.get("design_contract_digest") != contract_digest(outdir / "research_design.json"):
        return False, "research-design content changed after the unified audit gate"
    if payload.get("execution_contract_digest") != contract_digest(outdir / "method_execution.json"):
        return False, "method-execution content changed after the unified audit gate"
    if payload.get("dialogic_argument_digest") != contract_digest(
        outdir / "dialogic_argument_map.md"
    ):
        return False, "dialogic argument map changed after the unified audit gate"
    if payload.get("dialogic_argument_summary") != dialogic_argument_summary(outdir):
        return False, "dialogic argument summary changed after the unified audit gate"
    if payload.get("review_assurance_digest") != contract_digest(outdir / REVIEW_ASSURANCE_REL):
        return False, "review assurance declaration changed after the unified audit gate"
    if payload.get("review_assurance") != review_assurance_summary(outdir):
        return False, "review assurance status changed after the unified audit gate"
    if payload.get("canonical_manuscript") != canonical_manuscript_binding(outdir):
        return False, "canonical manuscript path or content changed after the unified audit gate"
    if payload.get("method_adapter_registry_digest") != method_adapter_registry_digest():
        return False, "method adapter registry changed after the unified audit gate"
    runtime_groups = scientific_runtime_groups_for_config(load_project_config(outdir))
    if payload.get("scientific_runtime_groups") != list(runtime_groups):
        return False, "scientific runtime applicability changed after the unified audit gate"
    runtime_issues = scientific_runtime_issues(groups=runtime_groups)
    if runtime_issues:
        return False, "; ".join(runtime_issues)
    if payload.get("scientific_runtime_digest") != scientific_runtime_digest(groups=runtime_groups):
        return False, "scientific method, research-decision, or venue-overlay runtime changed after the unified audit gate"
    manuscript_issue = _manuscript_receipt_currentness_issue(outdir)
    if manuscript_issue:
        return False, manuscript_issue
    if payload.get("artifact_manifest") != artifact_manifest(
        outdir,
        excludes=AUDIT_FINGERPRINT_EXCLUDES,
        include_rendered=False,
        bound_prefixes=AUDIT_BOUND_PREFIXES,
    ):
        return False, "audited artifact manifest changed after the unified audit gate"
    if payload.get("artifact_fingerprint") != audit_fingerprint(outdir):
        return False, "audited artifacts changed after the unified audit gate; rerun the audit gate"
    if payload.get("stage_semantic_summaries") != stage_semantic_summaries(outdir):
        return False, "stage semantics or revision route changed after the unified audit gate"
    try:
        completion = validate_audit_completion(outdir, config=load_project_config(outdir))
    except (OSError, RuntimeError, ValueError) as exc:
        return False, f"audit completion validation could not run: {exc}"
    if not completion.ok:
        detail = "; ".join(
            f"{finding.code}: {finding.message}" for finding in completion.findings
        )
        return False, f"audit completion is no longer valid: {detail}"
    return True, ""


def output_receipt_status(outdir: Path) -> tuple[bool, str]:
    receipt = read_receipt(outdir, "output")
    if receipt.path is None:
        return False, "unified output gate has not been run"
    if receipt.legacy:
        return False, "legacy v5 output receipt is historical evidence only; run the v6 audit and output gates"
    payload = receipt.payload
    if not payload:
        return False, "unified output gate receipt is invalid"
    if payload.get("status") != "PASS":
        return False, "last unified output gate did not pass"
    if payload.get("schema_version") != OUTPUT_RECEIPT_SCHEMA:
        return False, "unified output gate receipt uses an unsupported schema version"
    if payload.get("framework_version") != FRAMEWORK_VERSION:
        return False, "unified output gate receipt belongs to another framework version"
    manuscript_issue = _manuscript_receipt_currentness_issue(
        outdir,
        existing_lineage_only=True,
    )
    if manuscript_issue:
        return False, manuscript_issue
    audit_ok, audit_issue = audit_receipt_status(outdir)
    if not audit_ok:
        return False, f"bound audit receipt is no longer valid: {audit_issue}"
    if payload.get("audit_receipt_digest") != contract_digest(
        outdir / AUDIT_RECEIPT_REL
    ):
        return False, "audit receipt changed after the unified output gate"
    metadata = contract_metadata(outdir)
    if payload.get("acquisition_schema_version") != metadata["acquisition_schema"]:
        return False, "acquisition schema changed after the unified output gate"
    if payload.get("literature_analysis_schema_version") != metadata["literature_analysis_schema"]:
        return False, "literature-analysis schema changed after the unified output gate"
    if payload.get("literature_analysis_state") != metadata["literature_analysis_state"]:
        return False, "literature-analysis migration state changed after the unified output gate"
    if payload.get("design_schema_version") != metadata["design_schema"]:
        return False, "research-design schema changed after the unified output gate"
    if payload.get("execution_schema_version") != metadata["execution_schema"]:
        return False, "method-execution schema changed after the unified output gate"
    if payload.get("acquisition_binding") != acquisition_binding_summary(outdir):
        return False, "load-bearing source identity, permission, verification, role, or file binding changed after the unified output gate"
    if payload.get("literature_analysis_digest") != metadata["literature_analysis_digest"]:
        return False, "critical reading or literature synthesis changed after the unified output gate"
    if payload.get("design_contract_digest") != contract_digest(outdir / "research_design.json"):
        return False, "research-design content changed after the unified output gate"
    if payload.get("execution_contract_digest") != contract_digest(outdir / "method_execution.json"):
        return False, "method-execution content changed after the unified output gate"
    if payload.get("dialogic_argument_digest") != contract_digest(
        outdir / "dialogic_argument_map.md"
    ):
        return False, "dialogic argument map changed after the unified output gate"
    if payload.get("dialogic_argument_summary") != dialogic_argument_summary(outdir):
        return False, "dialogic argument summary changed after the unified output gate"
    if payload.get("review_assurance_digest") != contract_digest(outdir / REVIEW_ASSURANCE_REL):
        return False, "review assurance declaration changed after the unified output gate"
    if payload.get("review_assurance") != review_assurance_summary(outdir):
        return False, "review assurance status changed after the unified output gate"
    if payload.get("method_adapter_registry_digest") != method_adapter_registry_digest():
        return False, "method adapter registry changed after the unified output gate"
    runtime_groups = scientific_runtime_groups_for_config(load_project_config(outdir))
    if payload.get("scientific_runtime_groups") != list(runtime_groups):
        return False, "scientific runtime applicability changed after the unified output gate"
    runtime_issues = scientific_runtime_issues(groups=runtime_groups)
    if runtime_issues:
        return False, "; ".join(runtime_issues)
    if payload.get("scientific_runtime_digest") != scientific_runtime_digest(groups=runtime_groups):
        return False, "scientific method, research-decision, or venue-overlay runtime changed after the unified output gate"
    if payload.get("canonical_manuscript") != canonical_manuscript_binding(outdir):
        return False, "canonical manuscript changed after the unified output gate"
    if payload.get("output_run_digest") != contract_digest(outdir / "output_run.json"):
        return False, "output run record changed after the unified output gate"
    if payload.get("final_manifest_digest") != contract_digest(
        outdir / "final_artifact_manifest.json"
    ):
        return False, "final artifact manifest changed after the unified output gate"
    if payload.get("render_qa_digest") != contract_digest(outdir / "render_qa.json"):
        return False, "render QA evidence changed after the unified output gate"
    if payload.get("artifact_manifest") != artifact_manifest(
        outdir,
        excludes=FINGERPRINT_EXCLUDES,
    ):
        return False, "output artifact manifest changed after the unified output gate"
    if payload.get("artifact_fingerprint") != output_fingerprint(outdir):
        return False, "artifacts changed after the unified output gate; rerun the output gate"
    if payload.get("stage_semantic_summaries") != stage_semantic_summaries(outdir):
        return False, "stage semantics or revision route changed after the unified output gate"
    eligibility = output_eligibility_status(outdir, load_project_config(outdir))
    if not eligibility.ok:
        detail = "; ".join(
            f"{finding.code}: {finding.message}" for finding in eligibility.findings
        )
        return False, f"output eligibility is no longer valid: {detail}"
    try:
        completion = validate_output_completion(outdir, config=load_project_config(outdir))
    except (OSError, RuntimeError, ValueError) as exc:
        return False, f"output completion validation could not run: {exc}"
    if not completion.ok:
        detail = "; ".join(
            f"{finding.code}: {finding.message}" for finding in completion.findings
        )
        return False, f"output completion is no longer valid: {detail}"
    return True, ""


@observe_gate
def gate_stage(outdir: Path, stage: str, skills_dir: Path, *, repair: bool = False) -> int:
    requested_stage = stage
    stage = canonical_stage(stage)
    doctor = run_doctor(skills_dir, repair=repair, outdir=outdir)
    if not doctor.ok:
        print(doctor_markdown(doctor))
        if stage == "audit":
            write_audit_receipt(outdir, passed=False)
        if stage == "output":
            write_output_receipt(outdir, passed=False)
        return 1

    applicability_read = read_config(outdir)
    if applicability_read.path is not None and not applicability_read.issues:
        applicability_profile = task_profile(applicability_read.payload)
        terminal = TASK_PROFILE_TERMINALS.get(applicability_profile)
        if terminal in STAGES and stage in STAGES and STAGES.index(stage) > STAGES.index(terminal):
            print(f"# CNKI-Paper Local Gate: {stage}\n\nStatus: NOT_APPLICABLE\n")
            print(
                f"Task profile `{applicability_profile}` terminates at `{terminal}`; "
                "no files were changed."
            )
            return 0

    stage_snapshot, _ = status_payload(outdir, skills_dir)
    earliest_stage = str(stage_snapshot.get("next_stage") or "intake")
    if (
        stage_snapshot.get("terminal_outcome") == "withdrawn"
        and stage in STAGES
        and STAGES.index(stage) > STAGES.index("research")
    ):
        print(f"# CNKI-Paper Local Gate: {stage}\n\nStatus: NOT_APPLICABLE\n")
        print(
            "Every registered research candidate was withdrawn. The workflow ended "
            "at research and did not generate a replacement topic or enter design."
        )
        return 0
    from .infrastructure.legal_domain import checks as legal_checks
    legal = legal_checks(outdir, stage)
    if legal["issues"]:
        print(f"# CNKI-Paper Local Gate: {stage}\n\nStatus: FAIL\n")
        for issue in legal["issues"]:
            print(f"- {issue['code']}: {issue['message']}")
        return 1
    if earliest_stage == "complete" or (
        earliest_stage in STAGES and STAGES.index(stage) < STAGES.index(earliest_stage)
    ):
        print(f"# CNKI-Paper Local Gate: {stage}\n\nStatus: PASS")
        print("\nThis stage is already current; no files were changed.")
        return 0
    if earliest_stage in STAGES and STAGES.index(stage) > STAGES.index(earliest_stage):
        print(f"# CNKI-Paper Local Gate: {stage}\n\nStatus: FAIL\n")
        print("## Blocking Issues\n")
        print(f"- earliest unresolved stage is {earliest_stage}; {stage} cannot bypass it")
        return 1

    if stage == "intake":
        config_read = read_config(outdir)
        config_issues = [*config_read.issues, *validate_workflow_config(config_read.payload)]
        if config_read.path is None or config_issues:
            print("# CNKI-Paper Local Gate: intake\n\nStatus: FAIL\n")
            print("## Blocking Issues\n")
            for issue in config_issues or ("workflow configuration is missing",):
                print(f"- {issue}")
            return 1
        profile = task_profile(config_read.payload)
        orientation_issues = validate_problem_orientation(
            outdir,
            "intake",
            task_profile=profile,
        )
        orientation_report = render_problem_orientation_report(outdir, "intake", orientation_issues)
        (outdir / "problem_orientation_check.md").write_text(orientation_report, encoding="utf-8")
        print(orientation_report, end="")
        if orientation_issues:
            return 1
        print("# CNKI-Paper Local Gate: intake\n\nStatus: PASS")
        return 0

    if stage == "acquisition":
        handoff_issues = acquisition_handoff_issues(outdir)
        if handoff_issues:
            print("# CNKI-Paper Local Gate: acquisition\n\nStatus: FAIL\n")
            print("## Blocking Issues\n")
            for issue in handoff_issues:
                print(f"- {issue}")
            return 1
        integration = validate_integration_artifacts(outdir)
        if integration["status"] != "PASS":
            print("# CNKI-Paper Local Gate: acquisition\n\nStatus: FAIL\n")
            print("## Blocking Issues\n")
            for issue in integration["issues"]:
                print(f"- {issue}")
            return 1
        _material_base, _material_payload, material_result = validate_material_contract(
            outdir,
            scope="acquisition",
        )
        if material_result.errors:
            print("# CNKI-Paper Local Gate: acquisition\n\nStatus: FAIL\n")
            print("## Blocking Issues\n")
            for issue in material_result.errors:
                print(f"- [{issue.code}] {issue.message}")
            return 1

    if stage == "audit":
        snapshot, _ = status_payload(outdir, skills_dir)
        next_stage = str(snapshot.get("next_stage") or "intake")
        if next_stage not in {"audit", "output", "complete"}:
            print("# CNKI-Paper Local Gate: audit\n\nStatus: FAIL\n")
            print("## Blocking Issues\n")
            print(f"- earliest unresolved stage is {next_stage}; audit cannot bypass it")
            return 1
        audit_started = False
        try:
            with audit_gate_lock(outdir):
                locked_snapshot, _ = status_payload(outdir, skills_dir)
                locked_next = str(locked_snapshot.get("next_stage") or "intake")
                if locked_next not in {"audit", "output", "complete"}:
                    print("# CNKI-Paper Local Gate: audit\n\nStatus: FAIL\n")
                    print("## Blocking Issues\n")
                    print(f"- earliest unresolved stage changed to {locked_next}; audit was not started")
                    return 1
                audit_started = True
                invalidate_receipts_for_audit(outdir)
                audit_config = load_project_config(outdir)
                if task_profile(audit_config) == "manuscript_revision":
                    audit_config = dict(audit_config)
                    audit_config["earliest_reopen_stage"] = revision_reopen_stage(outdir)
                result = run_audit_actions(
                    outdir,
                    skills_dir,
                    config=audit_config,
                )
                assurance_ok, assurance_issues = review_assurance_status(outdir)
                post_snapshot, _ = status_payload(outdir, skills_dir)
                post_next = str(post_snapshot.get("next_stage") or "intake")
                upstream_issues = []
                if post_next != "audit":
                    upstream_issues.append(
                        f"earliest stage changed to {post_next} while audit actions were running"
                    )
                result = finalize_audit_run_log(
                    outdir,
                    result,
                    assurance_issues=[] if assurance_ok else assurance_issues,
                    upstream_issues=upstream_issues,
                )
                passed = write_audit_receipt(outdir, passed=result.ok)
                if result.ok and not passed:
                    result = GateResult.fail(
                        "audit",
                        [Finding("AUDIT.RECEIPT_POLICY", "final audit receipt policy rejected the run")],
                    )
        except (OSError, RuntimeError) as exc:
            if audit_started:
                _write_receipt_state(
                    outdir,
                    kind="audit",
                    status="BLOCKED",
                    reason=str(exc),
                )
            print("# CNKI-Paper Local Gate: audit\n\nStatus: BLOCKED\n")
            print(f"- {exc}")
            return 2
        print("# CNKI-Paper Local Gate: audit")
        print()
        print(f"Status: {'PASS' if passed else 'FAIL'}")
        if result.findings or assurance_issues:
            print("\n## Blocking Issues\n")
            for finding in result.findings:
                print(f"- [{finding.code}] {finding.message}")
            for issue in assurance_issues:
                print(f"- {issue}")
        if passed and not review_assurance_summary(outdir).get("independent"):
            actual_mode = review_assurance_summary(outdir).get("mode", "undeclared")
            print(f"\nReview mode is {actual_mode}; do not describe this receipt as independent review.")
        return 0 if passed else 1

    if stage == "output":
        audit_ok, audit_issue = audit_receipt_status(outdir)
        if not audit_ok:
            print("# CNKI-Paper Local Gate: output\n\nStatus: FAIL")
            print(f"\n## Blocking Issues\n\n- {audit_issue}\n")
            print("Do not deliver artifacts until the hash-bound audit receipt is current.")
            write_output_receipt(outdir, passed=False)
            return 1
        eligibility = output_eligibility_status(outdir, load_project_config(outdir))
        if not eligibility.ok:
            print("# CNKI-Paper Local Gate: output\n\nStatus: BLOCKED\n")
            print("## Blocking Issues\n")
            for finding in eligibility.findings:
                print(f"- [{finding.code}] {finding.message}")
            return 2
        output_started = False
        try:
            with output_gate_lock(outdir):
                locked_audit_ok, locked_audit_issue = audit_receipt_status(outdir)
                if not locked_audit_ok:
                    print("# CNKI-Paper Local Gate: output\n\nStatus: FAIL")
                    print(f"\n## Blocking Issues\n\n- {locked_audit_issue}\n")
                    return 1
                output_started = True
                invalidate_output_receipt(outdir)
                result = run_output_actions(
                    outdir,
                    config=load_project_config(outdir),
                    prepublish_validator=lambda: audit_receipt_status(outdir),
                    receipt_signer=lambda: write_output_receipt(outdir, passed=True),
                )
                if not result.ok:
                    _write_receipt_state(
                        outdir,
                        kind="output",
                        status=result.status.value.upper(),
                        reason="output run did not complete",
                        findings=list(result.findings),
                    )
        except (OSError, RuntimeError) as exc:
            if output_started:
                _write_receipt_state(
                    outdir,
                    kind="output",
                    status="BLOCKED",
                    reason=str(exc),
                )
            print("# CNKI-Paper Local Gate: output\n\nStatus: BLOCKED\n")
            print(f"- {exc}")
            return 2
        print("# CNKI-Paper Local Gate: output")
        print()
        print(f"Status: {result.status.value.upper()}")
        if result.findings:
            print("\n## Blocking Issues\n")
            for finding in result.findings:
                print(f"- [{finding.code}] {finding.message}")
        if result.ok:
            return 0
        return 2 if result.status == GateStatus.BLOCKED else 1

    if stage == "build":
        active_config = load_project_config(outdir)
        if task_profile(active_config) == "manuscript_revision":
            active_config = dict(active_config)
            active_config["earliest_reopen_stage"] = revision_reopen_stage(outdir)
        prepared = None
        build_run_path = outdir / "build_run.json"
        restore_build_run = None
        build_run_replaced = False
        try:
            with build_gate_lock(outdir):
                locked_snapshot, _ = status_payload(outdir, skills_dir)
                locked_earliest = str(locked_snapshot.get("next_stage") or "intake")
                if locked_earliest != "build":
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    print("## Blocking Issues\n")
                    print(f"- earliest unresolved stage changed to {locked_earliest}; build was not started")
                    return 1
                previous_run = build_run_path.read_bytes() if build_run_path.is_file() else None

                def restore_build_run() -> None:
                    if previous_run is None:
                        if build_run_path.is_file():
                            build_run_path.unlink()
                        return
                    temporary = build_run_path.with_suffix(build_run_path.suffix + ".rollback")
                    temporary.write_bytes(previous_run)
                    temporary.replace(build_run_path)

                build_result, prepared = prepare_build(outdir, config=active_config)
                if not build_result.ok or prepared is None:
                    if prepared is not None:
                        rollback_preparation(prepared)
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    print("## Blocking Issues\n")
                    for finding in build_result.findings:
                        print(f"- [{finding.code}] {finding.message}")
                    return 1
                cnki_gate = None
                validator = skills_dir / "cnki-paper" / "scripts" / "codex_cnki_gate.py"
                if task_profile(active_config) != "manuscript_audit":
                    cnki_gate = run_python(
                        validator,
                        [str(outdir), "--stage", "build", "--read-only"],
                    )
                    if cnki_gate.returncode != 0:
                        rollback_preparation(prepared)
                        write_passthrough(cnki_gate)
                        return cnki_gate.returncode
                try:
                    current_selection = select_manuscript(outdir, active_config)
                except ManuscriptSelectionError as exc:
                    rollback_preparation(prepared)
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    print(f"- [BUILD.CANONICAL] {exc}")
                    return 1
                if current_selection.as_dict() != prepared.selection.as_dict():
                    rollback_preparation(prepared)
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    print("- [BUILD.INPUT_CHANGED] canonical manuscript changed while build was running")
                    return 1
                content_validator = validator if task_profile(active_config) != "manuscript_audit" else None
                recorded = record_build(
                    outdir,
                    current_selection,
                    config=active_config,
                    content_validator=content_validator,
                )
                if not recorded.ok:
                    restore_build_run()
                    rollback_preparation(prepared)
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    for finding in recorded.findings:
                        print(f"- [{finding.code}] {finding.message}")
                    return 1
                build_run_replaced = True
                current_run = build_run_status(
                    outdir,
                    active_config,
                    content_validator=content_validator,
                )
                post_snapshot, _ = status_payload(outdir, skills_dir)
                if not current_run.ok or str(post_snapshot.get("next_stage") or "") != "audit":
                    restore_build_run()
                    build_run_replaced = False
                    rollback_preparation(prepared)
                    print("# CNKI-Paper Local Gate: build\n\nStatus: FAIL\n")
                    print("- [BUILD.POSTCONDITION] build did not advance cleanly to audit")
                    return 1
                if cnki_gate is not None:
                    write_passthrough(cnki_gate)
                else:
                    print("# CNKI-Paper Local Gate: build\n\nStatus: PASS")
                return 0
        except (OSError, RuntimeError) as exc:
            if build_run_replaced and restore_build_run is not None:
                restore_build_run()
            if prepared is not None:
                rollback_preparation(prepared)
            print("# CNKI-Paper Local Gate: build\n\nStatus: BLOCKED\n")
            print(f"- {exc}")
            return 2

    metadata = contract_metadata(outdir)
    acquisition_schema = metadata["acquisition_schema"]
    if acquisition_schema == ACQUISITION_SCHEMA_V1 or (
        acquisition_schema == ACQUISITION_SCHEMA_V2
        and metadata["integration_enabled"]
    ):
        print(f"# CNKI-Paper Unified Gate: {stage}\n\nStatus: FAIL")
        print(
            "\n## Blocking Issues\n\n"
            f"- literature_registry.json still uses {acquisition_schema}; "
            "run cnki_acquisition.py migrate OUTDIR --dry-run --to v3, "
            "review the plan, then rerun with --apply.\n"
        )
        if stage == "audit":
            write_audit_receipt(outdir, passed=False)
        if stage == "output":
            write_output_receipt(outdir, passed=False)
        return 1

    cnki_gate = run_python(
        skills_dir / "cnki-paper" / "scripts" / "codex_cnki_gate.py",
        [str(outdir), "--stage", stage],
    )
    write_passthrough(cnki_gate)
    gate_returncode = cnki_gate.returncode
    if requested_stage != stage:
        print(f"Compatibility alias: {requested_stage} -> {stage}")
    return gate_returncode


def cnki_content_status(
    outdir: Path,
    skills_dir: Path,
    stage: str,
) -> tuple[bool, list[str]]:
    """Run the CNKI content gate in read-only mode before trusting later parent state."""
    script = skills_dir / "cnki-paper" / "scripts" / "codex_cnki_gate.py"
    if not script.is_file():
        # run_doctor owns missing-runtime failures. Keeping this neutral makes the helper unit-testable
        # when run_doctor is intentionally mocked and no synthetic skills tree is created.
        return False, ["CNKI-Paper content validator is missing"]
    result = run_python(script, [str(outdir), "--stage", stage, "--read-only"])
    if result.returncode == 0:
        return True, []
    lines = [
        line[2:].strip()
        for line in result.stdout.splitlines()
        if line.startswith("- ") and line[2:].strip()
    ]
    if not lines:
        detail = " ".join((result.stdout + "\n" + result.stderr).split())[-800:]
        lines = [detail or f"CNKI {stage} content gate failed"]
    return False, lines


def research_design_status(outdir: Path, skills_dir: Path, stage: str) -> tuple[bool, list[str]]:
    design_schema = _read_schema(outdir / "research_design.json")
    if design_schema != DESIGN_SCHEMA_V4:
        if design_schema in {DESIGN_SCHEMA_V1, DESIGN_SCHEMA_V2, DESIGN_SCHEMA_V3}:
            return False, [
                f"{design_schema} is a legacy read/render/migrate-only contract; "
                f"migrate to {DESIGN_SCHEMA_V4} before the active {stage} workflow"
            ]
        return False, [
            f"active {stage} workflow requires {DESIGN_SCHEMA_V4}; "
            f"found {design_schema or 'missing research_design.json'}"
        ]
    script = skills_dir / "cnki-paper" / "scripts" / "research_design.py"
    if not script.is_file():
        return False, ["research-design validator is missing"]
    result = run_python(script, ["validate", str(outdir), "--json", "--stage", stage])
    if result.returncode == 0:
        return True, []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = " ".join((result.stdout + "\n" + result.stderr).split())[-600:]
        return False, [detail or "research-design validation failed"]
    raw_issues = payload.get("issues") if isinstance(payload, dict) else None
    if not isinstance(raw_issues, list):
        return False, ["research-design validation failed"]
    issues: list[str] = []
    for issue in raw_issues:
        if isinstance(issue, dict):
            code = str(issue.get("code") or "RD.UNKNOWN")
            message = str(issue.get("message") or "research-design validation failed")
            issues.append(f"{code}: {message}")
        elif issue:
            issues.append(str(issue))
    return False, issues or ["research-design validation failed"]


def method_execution_status(
    outdir: Path,
    skills_dir: Path,
    stage: str = "execution",
) -> tuple[bool, list[str]]:
    execution_schema = _read_schema(outdir / "method_execution.json")
    if execution_schema != EXECUTION_SCHEMA_V3:
        if execution_schema in {EXECUTION_SCHEMA_V1, EXECUTION_SCHEMA_V2}:
            return False, [
                f"{execution_schema} is a legacy read/render/migrate-only contract; "
                f"migrate to {EXECUTION_SCHEMA_V3} before the active {stage} workflow"
            ]
        return False, [
            f"active {stage} workflow requires {EXECUTION_SCHEMA_V3}; "
            f"found {execution_schema or 'missing method_execution.json'}"
        ]
    script = skills_dir / "empirical-research" / "scripts" / "method_execution.py"
    if not script.is_file():
        return False, ["method-execution validator is missing"]
    result = run_python(
        script,
        ["validate", str(outdir), "--json", "--stage", stage],
    )
    if result.returncode == 0:
        return True, []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        detail = " ".join((result.stdout + "\n" + result.stderr).split())[-600:]
        return False, [detail or "method-execution validation failed"]
    raw_issues = payload.get("issues") if isinstance(payload, dict) else None
    if not isinstance(raw_issues, list):
        return False, ["method-execution validation failed"]
    issues: list[str] = []
    for issue in raw_issues:
        if isinstance(issue, dict):
            code = str(issue.get("code") or "ME.UNKNOWN")
            message = str(issue.get("message") or "method-execution validation failed")
            issues.append(f"{code}: {message}")
        elif issue:
            issues.append(str(issue))
    return False, issues or ["method-execution validation failed"]


def active_research_contract_issues(outdir: Path, *, stage: str) -> list[str]:
    """Keep legacy contracts observable without admitting them to active gates."""

    metadata = contract_metadata(outdir)
    pair = (metadata["design_schema"], metadata["execution_schema"])
    if pair == (DESIGN_SCHEMA_V4, EXECUTION_SCHEMA_V3):
        return []
    if pair == (DESIGN_SCHEMA_V3, EXECUTION_SCHEMA_V2):
        return [
            f"{DESIGN_SCHEMA_V3} + {EXECUTION_SCHEMA_V2} is read/render/migrate-only; "
            f"migrate to {DESIGN_SCHEMA_V4} + {EXECUTION_SCHEMA_V3} before {stage}"
        ]
    return [
        f"active {stage} workflow requires {DESIGN_SCHEMA_V4} + {EXECUTION_SCHEMA_V3}; "
        f"found {pair[0] or 'missing design'} + {pair[1] or 'missing execution'}; "
        f"migration_state={metadata['migration_state']}"
    ]


def execution_status(outdir: Path, skills_dir: Path) -> tuple[bool, list[str]]:
    contract_issues = active_research_contract_issues(outdir, stage="execution")
    if contract_issues:
        return False, contract_issues
    design_ok, issues = research_design_status(outdir, skills_dir, "execution")
    execution_ok, execution_issues = method_execution_status(outdir, skills_dir, "execution")
    issues = [*issues, *execution_issues]
    return design_ok and execution_ok and not issues, issues


def mark_profile_complete(payload: dict[str, Any], stage: str) -> None:
    payload["completed_stage"] = stage
    payload["next_stage"] = "complete"
    payload["next_checkpoint"] = None
    payload["is_complete"] = True


def attach_canonical_stages(payload: dict[str, Any], outdir: Path | None = None) -> dict[str, Any]:
    """Expose exactly the eight public controller stages, never parent internals."""
    if outdir is not None:
        from .infrastructure.legal_domain import apply_status
        apply_status(payload, outdir)
    next_stage = str(payload.get("next_stage") or "intake")
    terminal_stage = str(payload.get("terminal_stage") or "output")
    rows: list[dict[str, str]] = []
    route = payload.get("route_plan") if isinstance(payload.get("route_plan"), dict) else {}
    revision_stage = str(route.get("earliest_reopen_stage") or "")
    if payload.get("task_profile") == "manuscript_audit" and next_stage != "blocked":
        audit_rows = {
            "intake": "done" if next_stage != "intake" else "current",
            "acquisition": (
                "current" if next_stage == "acquisition" else "done" if next_stage in {"build", "audit", "complete"} else "pending"
            ),
            "research": "not_applicable",
            "design": "not_applicable",
            "execution": "not_applicable",
            "build": (
                "current" if next_stage == "build" else "reused" if next_stage in {"audit", "complete"} else "pending"
            ),
            "audit": "done" if next_stage == "complete" else "current" if next_stage == "audit" else "pending",
            "output": "not_applicable",
        }
        rows = [{"key": stage, "status": audit_rows[stage]} for stage in STAGES]
    elif (
        route.get("profile") == "manuscript_revision"
        and route.get("valid") is True
        and revision_stage in STAGES
    ):
        declared_reopen_index = STAGES.index(revision_stage)
        complete = bool(payload.get("is_complete")) or next_stage == "complete"
        current_index = STAGES.index(next_stage) if next_stage in STAGES else len(STAGES)
        effective_reopen_index = min(declared_reopen_index, current_index)
        terminal_index = STAGES.index(terminal_stage) if terminal_stage in STAGES else len(STAGES) - 1
        for index, stage in enumerate(STAGES):
            if complete and index > terminal_index:
                status = "not_applicable"
            elif index < (declared_reopen_index if complete else effective_reopen_index):
                status = "reused"
            elif complete:
                status = "done"
            elif index < current_index:
                status = "done"
            elif index == current_index:
                status = "current"
            else:
                status = "pending"
            rows.append({"key": stage, "status": status})
    elif bool(payload.get("is_complete")) or next_stage == "complete":
        terminal_index = (
            STAGES.index(terminal_stage) if terminal_stage in STAGES else len(STAGES) - 1
        )
        for index, stage in enumerate(STAGES):
            rows.append(
                {
                    "key": stage,
                    "status": "done" if index <= terminal_index else "not_applicable",
                }
            )
    elif next_stage in STAGES:
        current_index = STAGES.index(next_stage)
        terminal_index = (
            STAGES.index(terminal_stage) if terminal_stage in STAGES else len(STAGES) - 1
        )
        for index, stage in enumerate(STAGES):
            if index > terminal_index:
                status = "not_applicable"
            elif index < current_index:
                status = "done"
            elif index == current_index:
                status = "current"
            else:
                status = "pending"
            rows.append({"key": stage, "status": status})
    else:
        rows = [{"key": stage, "status": "pending"} for stage in STAGES]
        rows[0]["status"] = "blocked"
    payload["stages"] = rows
    phase_rows: list[dict[str, Any]] = []
    for phase in SEMANTIC_PHASE_ORDER:
        members = [row for row in rows if STAGE_TO_SEMANTIC_PHASE[row["key"]] == phase]
        statuses = [row["status"] for row in members]
        if "blocked" in statuses:
            phase_status = "blocked"
        elif "current" in statuses:
            phase_status = "current"
        elif "pending" in statuses:
            phase_status = "pending"
        elif statuses and all(status == "not_applicable" for status in statuses):
            phase_status = "not_applicable"
        elif "done" in statuses:
            phase_status = "done"
        else:
            phase_status = "reused"
        phase_rows.append(
            {
                "key": phase,
                "status": phase_status,
                "machine_stages": [row["key"] for row in members],
            }
        )
    payload["phases"] = phase_rows
    payload["next_phase"] = next(
        (row["key"] for row in phase_rows if row["status"] in {"blocked", "current"}),
        None,
    )
    return payload


def _finish_from_receipts(
    payload: dict[str, Any],
    outdir: Path,
    *,
    audit_only: bool = False,
) -> tuple[dict[str, Any], int]:
    """Advance audit/revision profiles using v6 semantic and delivery receipts."""
    audit_ok, audit_issue = audit_receipt_status(outdir)
    payload["audit_gate"] = "pass" if audit_ok else "pending"
    payload["review_route"] = workspace_review_route(outdir)
    if not audit_ok:
        payload["next_stage"] = "audit"
        payload["audit_gate_issue"] = audit_issue
        review_route = payload["review_route"]
        route_status = str(review_route.get("status") or "")
        action = str(review_route.get("action") or "")
        if route_status == "PLAN_REQUIRES_ACTION":
            if action in {
                "reopen_existing_full_paper_stage",
                "follow_authorized_revision_contract",
            }:
                earliest = str(review_route.get("effective_earliest_reopen_stage") or "")
                if earliest in {"research", "design", "execution", "build"}:
                    payload["next_stage"] = earliest
            payload["next_checkpoint"] = {
                "request_profile_expansion": "review_profile_expansion",
                "request_revision_contract_amendment": "review_revision_contract_amendment",
                "reopen_existing_full_paper_stage": "review_stage_reopen_plan",
                "follow_authorized_revision_contract": "review_repair_execution",
            }.get(action, "review_resolution")
        elif route_status == "AWAITING_VERIFICATION":
            payload["next_checkpoint"] = "review_independent_verification"
        elif route_status == "REQUIRES_ADJUDICATION":
            payload["next_checkpoint"] = "review_adjudication"
        return attach_canonical_stages(payload, outdir), 0
    if audit_only:
        mark_profile_complete(payload, "audit")
        return attach_canonical_stages(payload, outdir), 0

    output_ok, output_issue = output_receipt_status(outdir)
    payload["output_gate"] = "pass" if output_ok else "pending"
    if not output_ok:
        payload["next_stage"] = "output"
        payload["output_gate_issue"] = output_issue
        return attach_canonical_stages(payload, outdir), 0
    payload["next_stage"] = "complete"
    payload["is_complete"] = True
    return attach_canonical_stages(payload, outdir), 0


def _gate_result_issues(result: Any) -> list[str]:
    rendered: list[str] = []
    for item in getattr(result, "findings", ()):
        rendered.append(f"{item.code}: {item.message}")
    return rendered


def research_status(
    outdir: Path,
    config: dict[str, Any],
    skills_dir: Path,
) -> tuple[bool, list[str]]:
    """Pure research-stage projection; it never refreshes generated views."""

    issues = _gate_result_issues(local_artifact_gate(outdir, "research", config))
    focused = validate_registry(
        outdir,
        require_citations=True,
        check_index=True,
        require_exemplars=True,
    )
    issues.extend(str(issue) for issue in focused.issues)
    analysis, _ = validate_analysis(outdir, stage="research")
    issues.extend(str(issue) for issue in analysis.issues)
    _material_base, _material_payload, material_result = validate_material_contract(
        outdir,
        scope="research",
    )
    issues.extend(f"{issue.code}: {issue.message}" for issue in material_result.errors)
    _feasibility_base, _feasibility_payload, feasibility_result = validate_feasibility_contract(outdir)
    issues.extend(f"{issue.code}: {issue.message}" for issue in feasibility_result.errors)
    issues.extend(
        str(issue)
        for issue in validate_problem_orientation(
            outdir,
            "research",
            task_profile=task_profile(config),
        )
    )
    _, content_issues = cnki_content_status(outdir, skills_dir, "research")
    issues.extend(content_issues)
    return not issues, list(dict.fromkeys(issues))


def build_status(
    outdir: Path,
    config: dict[str, Any],
    skills_dir: Path,
) -> tuple[bool, list[str]]:
    """Pure build projection over the canonical manuscript and argument map."""

    profile = task_profile(config)
    reopen = str(config.get("earliest_reopen_stage") or "")
    issues = _gate_result_issues(local_artifact_gate(outdir, "build", config))
    schemas = contract_metadata(outdir)
    legacy_pair_present = (
        schemas["design_schema"],
        schemas["execution_schema"],
    ) == (DESIGN_SCHEMA_V3, EXECUTION_SCHEMA_V2)
    if profile != "manuscript_audit" or legacy_pair_present:
        issues.extend(active_research_contract_issues(outdir, stage="build"))
    content_validator = (
        None
        if profile == "manuscript_audit"
        else skills_dir / "cnki-paper" / "scripts" / "codex_cnki_gate.py"
    )
    issues.extend(
        _gate_result_issues(
            build_run_status(outdir, config, content_validator=content_validator)
        )
    )
    if profile == "manuscript_audit":
        return not issues, list(dict.fromkeys(issues))
    if not (profile == "manuscript_revision" and reopen == "build"):
        dialogue = validate_dialogic_argument(outdir)
        issues.extend(str(issue) for issue in dialogue.issues)
    _, content_issues = cnki_content_status(outdir, skills_dir, "build")
    issues.extend(content_issues)
    return not issues, list(dict.fromkeys(issues))


def status_payload(outdir: Path, skills_dir: Path, *, repair: bool = False) -> tuple[dict[str, Any], int]:
    """Return the normalized eight-state projection without writing or running audits."""

    doctor = run_doctor(skills_dir, repair=repair, outdir=outdir)
    config_read = read_config(outdir)
    intake_config_issues = (
        validate_workflow_config(config_read.payload)
        if config_read.path is not None
        else []
    )
    intake_owned_issues = {*intake_config_issues, *config_read.issues}
    runtime_doctor_issues = [
        issue for issue in doctor.issues if issue not in intake_owned_issues
    ]
    metadata = contract_metadata(outdir)
    payload: dict[str, Any] = {
        "framework_version": FRAMEWORK_VERSION,
        "doctor": "pass" if doctor.ok else "fail",
        "doctor_issues": doctor.issues,
        **metadata,
        "task_profile": "full_paper",
        "publication_track": "undeclared",
        "terminal_stage": "output",
        "next_stage": "intake",
        "next_checkpoint": None,
        "is_complete": False,
        "review_assurance": review_assurance_summary(outdir),
        "problem_orientation": "pending",
        "problem_reappraisal": "pending",
        "research_decision_state": "absent",
        "preclearance_readiness": None,
        "feasibility_state": "absent",
        "resource_unlock_state": None,
        "resource_blocker": None,
        "direction_veto": direction_veto_summary(None, available=False),
        "literature_sufficiency": literature_sufficiency_summary(outdir),
        "route_plan": route_summary(outdir),
        "review_route": workspace_review_route(outdir),
        "audit_gate": "pending",
        "output_gate": "pending",
    }
    decision_state, decision_readiness = _research_decision_projection(outdir)
    payload["research_decision_state"] = decision_state
    payload["preclearance_readiness"] = decision_readiness
    resource_state = resource_unlock_state(outdir, question_committed=decision_state == "cleared")
    payload["resource_unlock_state"] = resource_state
    payload["resource_blocker"] = resource_state.get("resource_blocker")
    payload["feasibility_state"] = (
        str((resource_state.get("feasibility_ref") or {}).get("verdict") or "absent")
        if isinstance(resource_state.get("feasibility_ref"), dict)
        else "absent"
    )
    if runtime_doctor_issues:
        payload["next_stage"] = "blocked"
        return attach_canonical_stages(payload, outdir), 1

    if config_read.path is None:
        return attach_canonical_stages(payload, outdir), 0
    if config_read.issues:
        payload["next_stage"] = "intake"
        payload["next_checkpoint"] = (
            "migration_reconcile"
            if any(
                token in issue.lower()
                for issue in config_read.issues
                for token in ("conflict", "retired")
            )
            else "workflow_config_repair"
        )
        payload["config_issues"] = list(config_read.issues)
        return attach_canonical_stages(payload, outdir), 0
    config = config_read.payload
    config_issues = intake_config_issues
    if config_issues:
        payload["next_stage"] = "intake"
        payload["next_checkpoint"] = "workflow_config"
        payload["config_issues"] = config_issues
        return attach_canonical_stages(payload, outdir), 0
    profile = task_profile(config)
    if profile not in TASK_PROFILE_TERMINALS:
        payload["next_stage"] = "blocked"
        payload["profile_issue"] = f"unsupported task_profile: {profile}"
        return attach_canonical_stages(payload, outdir), 1
    track = str(config.get("publication_track") or "").strip().lower().replace("_", "-")
    if track not in {"cnki-cn", "international-ssci", "mixed"}:
        payload["next_stage"] = "intake"
        payload["next_checkpoint"] = "publication_track"
        payload["config_issues"] = [
            "publication_track must be explicitly set to cnki-cn, international-ssci, or mixed"
        ]
        return attach_canonical_stages(payload, outdir), 0

    payload["task_profile"] = profile
    payload["publication_track"] = track
    payload["terminal_stage"] = TASK_PROFILE_TERMINALS[profile]
    payload["route_plan"] = route_summary(outdir, config, stage="research")
    payload["literature_sufficiency"] = literature_sufficiency_summary(outdir)
    if profile == "manuscript_revision" and payload["route_plan"].get("valid") is not True:
        payload["next_stage"] = str(payload["route_plan"].get("earliest_reopen_stage") or "intake")
        payload["next_checkpoint"] = "revision_contract"
        payload["revision_issues"] = list(payload["route_plan"].get("issues") or [])
        return attach_canonical_stages(payload, outdir), 0
    if profile == "manuscript_revision":
        config = dict(config)
        config["earliest_reopen_stage"] = payload["route_plan"].get("earliest_reopen_stage")

    orientation_issues = validate_problem_orientation(outdir, "intake", task_profile=profile)
    payload["problem_orientation"] = "pass" if not orientation_issues else "fail"
    payload["problem_orientation_issues"] = orientation_issues
    if orientation_issues:
        payload["next_stage"] = "intake"
        payload["next_checkpoint"] = "problem_orientation"
        return attach_canonical_stages(payload, outdir), 0

    handoff_issues = acquisition_handoff_issues(outdir)
    if handoff_issues:
        payload["acquisition"] = "fail"
        payload["acquisition_issues"] = handoff_issues
        payload["next_stage"] = "acquisition"
        return attach_canonical_stages(payload, outdir), 0

    integration = validate_integration_artifacts(outdir)
    payload["integration_validation"] = integration
    if integration["status"] != "PASS":
        payload["acquisition"] = "fail"
        payload["acquisition_issues"] = list(integration["issues"])
        payload["next_stage"] = "acquisition"
        return attach_canonical_stages(payload, outdir), 0

    _material_base, _material_payload, material_result = validate_material_contract(
        outdir,
        scope="acquisition",
    )
    payload["research_materials"] = "pass" if not material_result.errors else "fail"
    payload["research_material_issues"] = [
        f"{issue.code}: {issue.message}" for issue in material_result.errors
    ]
    if material_result.errors:
        payload["acquisition"] = "fail"
        payload["acquisition_issues"] = payload["research_material_issues"]
        payload["next_stage"] = "acquisition"
        payload["next_checkpoint"] = "material_availability_screen"
        return attach_canonical_stages(payload, outdir), 0

    if profile == "manuscript_audit":
        acquisition = validate_registry(
            outdir,
            require_citations=True,
            check_index=True,
            require_exemplars=False,
        )
        payload["acquisition"] = "pass" if acquisition.ok else "fail"
        payload["acquisition_issues"] = list(acquisition.issues)
        payload["acquisition_stats"] = acquisition.stats
        acquisition_schema_ok = metadata["acquisition_schema"] == ACQUISITION_SCHEMA_V3 or (
            metadata["acquisition_schema"] == ACQUISITION_SCHEMA_V2
            and not metadata["integration_enabled"]
        )
        if not acquisition.ok or not acquisition_schema_ok:
            if acquisition.ok:
                payload["acquisition"] = "fail"
                payload["acquisition_issues"].append(
                    "manuscript audit requires acquisition v2 identities, or v3 when integration artifacts are present"
                )
            payload["next_stage"] = "acquisition"
            return attach_canonical_stages(payload, outdir), 0
        acquisition_content_ok, acquisition_content_issues = cnki_content_status(
            outdir, skills_dir, "acquisition"
        )
        if not acquisition_content_ok:
            payload["acquisition"] = "fail"
            payload["acquisition_issues"] = acquisition_content_issues
            payload["next_stage"] = "acquisition"
            return attach_canonical_stages(payload, outdir), 0
        if not canonical_manuscript_binding(outdir):
            payload["next_stage"] = "build"
            payload["build_issues"] = [
                "declare exactly one canonical manuscript source before audit"
            ]
            return attach_canonical_stages(payload, outdir), 0
        return _finish_from_receipts(payload, outdir, audit_only=True)

    reopen = revision_reopen_stage(outdir) if profile == "manuscript_revision" else "research"
    if profile == "manuscript_revision" and reopen not in {"research", "design", "execution", "build"}:
        payload["next_stage"] = "intake"
        payload["next_checkpoint"] = "revision_contract"
        return attach_canonical_stages(payload, outdir), 0

    if profile != "manuscript_revision" or reopen == "research":
        acquisition = validate_registry(outdir, require_exemplars=False)
        payload["acquisition"] = "pass" if acquisition.ok else "fail"
        payload["acquisition_issues"] = list(acquisition.issues)
        payload["acquisition_stats"] = acquisition.stats
        acquisition_schema_ok = metadata["acquisition_schema"] == ACQUISITION_SCHEMA_V3 or (
            metadata["acquisition_schema"] == ACQUISITION_SCHEMA_V2
            and not metadata["integration_enabled"]
        )
        if not acquisition.ok or not acquisition_schema_ok:
            if acquisition.ok:
                payload["acquisition"] = "fail"
                payload["acquisition_issues"].append(
                    "acquisition must use v3 when integration artifacts are present; migrate explicitly"
                )
            payload["next_stage"] = "acquisition"
            return attach_canonical_stages(payload, outdir), 0
        acquisition_content_ok, acquisition_content_issues = cnki_content_status(
            outdir, skills_dir, "acquisition"
        )
        if not acquisition_content_ok:
            payload["acquisition"] = "fail"
            payload["acquisition_issues"] = acquisition_content_issues
            payload["next_stage"] = "acquisition"
            return attach_canonical_stages(payload, outdir), 0
        payload["direction_veto"] = direction_veto_summary(config, available=True)
        research_ok, research_issues = research_status(outdir, config, skills_dir)
        payload["research"] = "pass" if research_ok else "fail"
        payload["research_issues"] = research_issues
        if not research_ok:
            payload["next_stage"] = "research"
            pending_decision = _json_object(outdir / "research_decision.json")
            projected_state = str(payload.get("research_decision_state") or "absent")
            withdrawal_confirmation_missing = (
                str(pending_decision.get("disposition") or "") == "withdrawn"
                and not isinstance(pending_decision.get("withdrawal_confirmation"), dict)
            )
            confirmation_markers = (
                "confirmed_motivation",
                "confirmed motivation",
                "question confirmation",
            )
            if projected_state == "absent" and profile == "topic_selection":
                payload["next_checkpoint"] = "candidate_portfolio"
            elif withdrawal_confirmation_missing or projected_state == "withdrawn":
                payload["next_checkpoint"] = "withdrawal_confirmation"
            elif projected_state == "provisional":
                readiness = payload.get("preclearance_readiness")
                payload["next_checkpoint"] = (
                    str(readiness.get("next_checkpoint") or "candidate_portfolio")
                    if isinstance(readiness, dict)
                    else "candidate_portfolio"
                )
            elif projected_state == "focused":
                readiness = payload.get("preclearance_readiness")
                payload["next_checkpoint"] = (
                    str(readiness.get("next_checkpoint") or "research_evidence")
                    if isinstance(readiness, dict)
                    else "research_evidence"
                )
            elif projected_state in {"challenged", "reopened"}:
                payload["next_checkpoint"] = "research_evidence"
            else:
                payload["next_checkpoint"] = (
                    "question_confirmation"
                    if research_issues
                    and all(any(marker in issue.lower() for marker in confirmation_markers) for issue in research_issues)
                    else "research_evidence"
                )
            return attach_canonical_stages(payload, outdir), 0

        decision_payload = _json_object(outdir / "research_decision.json")
        if str(decision_payload.get("disposition") or "") == "withdrawn":
            payload["terminal_outcome"] = "withdrawn"
            payload["terminal_stage"] = "research"
            payload["selected_candidate_id"] = None
            payload["deliverable_status"] = "not_applicable"
            payload["audit_receipt_status"] = "not_applicable"
            payload["output_receipt_status"] = "not_applicable"
            mark_profile_complete(payload, "research")
            return attach_canonical_stages(payload, outdir), 0

    if profile == "topic_selection":
        mark_profile_complete(payload, "research")
        return attach_canonical_stages(payload, outdir), 0

    if profile != "manuscript_revision" or STAGES.index(reopen) <= STAGES.index("design"):
        design_ok, design_issues = research_design_status(outdir, skills_dir, "design")
        design_content_ok, design_content_issues = cnki_content_status(outdir, skills_dir, "design")
        design_ok = design_ok and design_content_ok
        design_issues = list(dict.fromkeys([*design_issues, *design_content_issues]))
        payload["research_design"] = "pass" if design_ok else "fail"
        payload["research_design_issues"] = design_issues
        if not design_ok:
            payload["next_stage"] = "design"
            return attach_canonical_stages(payload, outdir), 0

    if profile == "research_design":
        mark_profile_complete(payload, "design")
        return attach_canonical_stages(payload, outdir), 0

    if profile != "manuscript_revision" or STAGES.index(reopen) <= STAGES.index("execution"):
        execution_ok, execution_issues = execution_status(outdir, skills_dir)
        execution_content_ok, execution_content_issues = cnki_content_status(
            outdir, skills_dir, "execution"
        )
        execution_ok = execution_ok and execution_content_ok
        execution_issues = list(
            dict.fromkeys([*execution_issues, *execution_content_issues])
        )
        payload["execution"] = "pass" if execution_ok else "fail"
        payload["execution_issues"] = execution_issues
        if not execution_ok:
            payload["next_stage"] = "execution"
            return attach_canonical_stages(payload, outdir), 0
        reappraisal_issues = validate_problem_orientation(outdir, "execution", task_profile=profile)
        payload["problem_reappraisal"] = "pass" if not reappraisal_issues else "fail"
        payload["problem_reappraisal_issues"] = reappraisal_issues
        if reappraisal_issues:
            must_research = any("return to research" in str(issue) for issue in reappraisal_issues)
            payload["next_stage"] = "research" if must_research else "execution"
            payload["next_checkpoint"] = "problem_reopening" if must_research else "problem_reappraisal"
            return attach_canonical_stages(payload, outdir), 0

    build_ok, build_issues = build_status(outdir, config, skills_dir)
    payload["build"] = "pass" if build_ok else "fail"
    payload["build_issues"] = build_issues
    if not build_ok:
        payload["next_stage"] = "build"
        return attach_canonical_stages(payload, outdir), 0
    return _finish_from_receipts(payload, outdir)


def status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CNKI-Paper Local Research Engine Status",
        "",
        f"- framework_version: {payload.get('framework_version')}",
        f"- doctor: {payload.get('doctor')}",
        f"- task_profile: {payload.get('task_profile')}",
        f"- publication_track: {payload.get('publication_track')}",
        f"- terminal_stage: {payload.get('terminal_stage')}",
        f"- acquisition_schema: {payload.get('acquisition_schema')}",
        f"- acquisition_migration_state: {payload.get('acquisition_migration_state')}",
        f"- literature_analysis_schema: {payload.get('literature_analysis_schema')}",
        f"- literature_analysis_state: {payload.get('literature_analysis_state')}",
        f"- literature_analysis_digest: {payload.get('literature_analysis_digest') or 'missing'}",
        f"- design_schema: {payload.get('design_schema')}",
        f"- execution_schema: {payload.get('execution_schema')}",
        f"- migration_state: {payload.get('migration_state')}",
        f"- case_design_state: {payload.get('case_design_state')}",
        f"- active_method_families: {', '.join(payload.get('active_method_families') or []) or 'none'}",
        f"- dialogic_argument_digest: {payload.get('dialogic_argument_digest') or 'missing'}",
        f"- review_assurance: {(payload.get('review_assurance') or {}).get('mode', 'undeclared')}",
        f"- independent_review: {str(bool((payload.get('review_assurance') or {}).get('independent'))).lower()}",
        f"- literature_sufficiency: {(payload.get('literature_sufficiency') or {}).get('status', 'pending')}",
        f"- literature_qualified: {(payload.get('literature_sufficiency') or {}).get('qualified_scholarly_count', 0)}",
        f"- literature_minimum: {(payload.get('literature_sufficiency') or {}).get('effective_minimum', 'unknown')}",
        f"- literature_gap: {(payload.get('literature_sufficiency') or {}).get('gap', 'unknown')}",
        f"- revision_reopen_stage: {(payload.get('route_plan') or {}).get('earliest_reopen_stage') or 'none'}",
        f"- review_reopen_stage: {(payload.get('review_route') or {}).get('effective_earliest_reopen_stage') or 'none'}",
        f"- review_route_action: {(payload.get('review_route') or {}).get('action', 'none')}",
        f"- assurance_level: {(payload.get('route_plan') or {}).get('assurance_level', 'unknown')}",
        f"- problem_orientation: {payload.get('problem_orientation', 'pending')}",
        f"- problem_reappraisal: {payload.get('problem_reappraisal', 'pending')}",
        f"- acquisition: {payload.get('acquisition', 'pending')}",
        f"- direction_veto: {(payload.get('direction_veto') or {}).get('status', 'not-yet-available')} (optional, non-blocking)",
        f"- research: {payload.get('research', 'pending')}",
        f"- research_decision_state: {payload.get('research_decision_state', 'absent')}",
        f"- feasibility_state: {payload.get('feasibility_state', 'absent')}",
        f"- resource_unlock_phase: {(payload.get('resource_unlock_state') or {}).get('phase', 'pre_feasibility')}",
        f"- preclearance_ready: {str(bool((payload.get('preclearance_readiness') or {}).get('ready'))).lower()}",
        f"- research_design: {payload.get('research_design', 'pending')}",
        f"- execution: {payload.get('execution', 'pending')}",
        f"- audit_gate: {payload.get('audit_gate', 'pending')}",
        f"- output_gate: {payload.get('output_gate', 'pending')}",
        f"- next_stage: {payload.get('next_stage')}",
        f"- next_phase: {payload.get('next_phase') or 'none'}",
        f"- next_checkpoint: {payload.get('next_checkpoint') or 'none'}",
        f"- is_complete: {str(bool(payload.get('is_complete'))).lower()}",
    ]
    lines.extend(
        [
            "",
            "## Semantic Phases",
            "",
            "| Phase | Status | Machine stages |",
            "|---|---|---|",
            *[
                f"| {row.get('key')} | {row.get('status')} | {', '.join(row.get('machine_stages') or [])} |"
                for row in payload.get("phases") or []
            ],
            "",
            "## Canonical Stages",
            "",
            "| Stage | Status |",
            "|---|---|",
            *[
                f"| {row.get('key')} | {row.get('status')} |"
                for row in payload.get("stages") or []
            ],
        ]
    )
    issues = (
        list(payload.get("doctor_issues") or [])
        + list(payload.get("config_issues") or [])
        + list(payload.get("problem_orientation_issues") or [])
        + list(payload.get("acquisition_issues") or [])
        + list(payload.get("research_material_issues") or [])
        + list(payload.get("research_issues") or [])
        + list(payload.get("research_design_issues") or [])
        + list(payload.get("execution_issues") or [])
        + list(payload.get("build_issues") or [])
        + list(payload.get("problem_reappraisal_issues") or [])
    )
    for issue in payload.get("revision_issues") or []:
        if isinstance(issue, dict):
            issues.append(f"{issue.get('code', 'REV')}: {issue.get('message', 'invalid revision contract')}")
        elif issue:
            issues.append(str(issue))
    issues.extend(str(issue) for issue in (payload.get("review_route") or {}).get("issues") or [])
    if payload.get("profile_issue"):
        issues.append(str(payload["profile_issue"]))
    if payload.get("output_gate_issue"):
        issues.append(str(payload["output_gate_issue"]))
    if payload.get("audit_gate_issue"):
        issues.append(str(payload["audit_gate_issue"]))
    if issues:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in issues)
    lines.append("")
    return "\n".join(lines)


def _run_research_decision_command(args: argparse.Namespace, outdir: Path) -> int:
    """Controller-owned wrapper for every canonical research-decision mutation."""

    for path in ("research_decision.json", "novelty_clearance_check.md"):
        definition = ARTIFACTS_BY_PATH.get(path)
        if definition is None or definition.owner_stage != "research" or definition.authority.startswith("legacy"):
            print(f"research-decision write is not owned by the research stage: {path}", file=sys.stderr)
            return 2
    config_read = read_config(outdir)
    if args.apply and (
        config_read.path is None
        or config_read.issues
        or validate_workflow_config(config_read.payload)
    ):
        print("research-decision apply requires a valid workflow_config.json", file=sys.stderr)
        return 2
    try:
        from research_decision import (
            bind_command,
            challenge_command,
            migrate_command,
            project_decision_state,
            reopen_command,
            resolve_retained_command,
            rollback_command,
        )
    except ImportError as exc:
        print(f"research-decision controller is unavailable: {exc}", file=sys.stderr)
        return 2

    action = str(args.research_decision_action)
    if action == "bind":
        code = bind_command(outdir, apply=args.apply)
    elif action == "challenge":
        code = challenge_command(
            outdir,
            reason=args.reason,
            source=args.source,
            opened_at=args.opened_at,
            evidence_ids=list(args.evidence_id or []),
            question_version_id=args.question_version_id,
            apply=args.apply,
        )
    elif action == "reopen":
        code = reopen_command(
            outdir,
            challenge_id=args.challenge_id,
            question_file=args.question_file.resolve(),
            resolution=args.resolution,
            resolved_at=args.resolved_at,
            apply=args.apply,
        )
    elif action == "resolve-retained":
        code = resolve_retained_command(
            outdir,
            challenge_id=args.challenge_id,
            resolution=args.resolution,
            resolved_at=args.resolved_at,
            apply=args.apply,
        )
    elif action == "migrate":
        code = migrate_command(
            outdir,
            decision_file=args.decision_file.resolve(),
            apply=args.apply,
        )
    elif action == "rollback":
        code = rollback_command(outdir, args.manifest, apply=args.apply)
    else:
        raise AssertionError(action)

    if code == 0 and args.apply and action in {"challenge", "reopen", "resolve-retained"}:
        post = _json_object(outdir / "research_decision.json")
        projected = project_decision_state(post) if post else "invalid"
        expected = "challenged" if action == "challenge" else "reopened"
        if projected != expected:
            print(
                f"research-decision apply failed controller postcondition: expected {expected}, got {projected}",
                file=sys.stderr,
            )
            return 2
    return code


def _valid_mutation_config(outdir: Path) -> bool:
    config_read = read_config(outdir)
    return bool(
        config_read.path is not None
        and not config_read.issues
        and not validate_workflow_config(config_read.payload)
    )


def _run_research_material_command(args: argparse.Namespace, outdir: Path) -> int:
    definition = ARTIFACTS_BY_PATH.get("reference_materials/research_material_registry.json")
    if definition is None or not {"acquisition", "research"} <= set(definition.writable_stages):
        print("research-material registry ownership is not declared by the workflow registry", file=sys.stderr)
        return 2
    if getattr(args, "apply", False) and not _valid_mutation_config(outdir):
        print("research-material apply requires a valid workflow_config.json", file=sys.stderr)
        return 2
    from research_materials import (
        init_command,
        probe_command,
        rollback_command,
        validate_command,
    )

    action = str(args.research_material_action)
    if action == "init":
        return init_command(
            outdir,
            not_applicable=args.not_applicable,
            rationale=args.rationale,
            apply=args.apply,
        )
    if action == "validate":
        return validate_command(outdir, scope=args.scope, json_stdout=args.json)
    if action == "probe":
        return probe_command(
            outdir,
            material_id=args.material,
            adapter=args.adapter,
            sample=args.sample,
            performed_at=args.performed_at,
            candidate_digest=args.candidate_semantic_digest,
            question_digest=args.question_version_digest,
            failure_code=args.failure_code,
            details=args.details,
            fields=list(args.field or []),
            key_assessment=args.key_assessment,
            query_summary=args.query_summary,
            pagination_status=args.pagination_status,
            rate_limit_status=args.rate_limit_status,
            deduplication_status=args.deduplication_status,
            time_coverage=args.time_coverage,
            spatial_coverage=args.spatial_coverage,
            unit_coverage=args.unit_coverage,
            header_confirmed=args.header_confirmed,
            apply=args.apply,
        )
    if action == "rollback":
        return rollback_command(outdir, args.manifest, apply=args.apply)
    raise AssertionError(action)


def _run_research_feasibility_command(args: argparse.Namespace, outdir: Path) -> int:
    definition = ARTIFACTS_BY_PATH.get("research_feasibility.json")
    if definition is None or "research" not in definition.writable_stages:
        print("research-feasibility ownership is not declared by the workflow registry", file=sys.stderr)
        return 2
    if getattr(args, "apply", False) and not _valid_mutation_config(outdir):
        print("research-feasibility apply requires a valid workflow_config.json", file=sys.stderr)
        return 2
    from research_feasibility import (
        authorize_action,
        bind_command,
        reopen_command,
        resource_unlock_state as current_resource_state,
        rollback_command,
        validate_command,
    )

    action = str(args.research_feasibility_action)
    if action == "validate":
        return validate_command(outdir, json_stdout=args.json)
    if action == "bind":
        return bind_command(outdir, args.assessment, select=args.select, apply=args.apply)
    if action == "reopen":
        return reopen_command(outdir, reason=args.reason, apply=args.apply)
    if action == "rollback":
        return rollback_command(outdir, args.manifest, apply=args.apply)
    if action == "authorize":
        report = authorize_action(outdir, args.action, question_committed=args.question_committed)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "PASS" else 1
    if action == "resource-state":
        print(
            json.dumps(
                current_resource_state(outdir, question_committed=args.question_committed),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    raise AssertionError(action)


@observe_controller
def main() -> int:
    parser = SafeArgumentParser(prog="avereth", description=__doc__)
    parser.add_argument("--skills-dir", type=Path, default=default_skills_dir())
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("outdir", type=Path, nargs="?")
    doctor_parser.add_argument("--repair", action="store_true")
    doctor_parser.add_argument("--json", action="store_true")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("outdir", type=Path)
    status_parser.add_argument("--repair", action="store_true")
    status_parser.add_argument("--json", action="store_true")
    status_parser.add_argument("--write", action="store_true", help="Deprecated no-op; v6 status is always read-only")

    plan_parser = subparsers.add_parser(
        "plan",
        help="Project the earliest-stage references, adapters and allowed writes without mutation",
    )
    plan_parser.add_argument("outdir", type=Path)
    plan_parser.add_argument("--json", action="store_true")
    plan_parser.add_argument("--discovery-brief", help="Workspace-relative public discovery brief; read-only projection")
    scout_parser = subparsers.add_parser("scout-capture", help="Validate or capture unverified discovery candidates")
    scout_parser.add_argument("outdir", type=Path)
    scout_parser.add_argument("--discovery-brief", required=True)
    scout_parser.add_argument("--reference-action", choices=tuple(REFERENCE_ACTIONS))
    scout_parser.add_argument("--request-id", required=True)
    scout_parser.add_argument("--result", type=Path, required=True)
    scout_parser.add_argument("--apply", action="store_true", help="Primary-side candidate capture only; never registers sources")
    plan_parser.add_argument(
        "--reference-action", choices=tuple(REFERENCE_ACTIONS),
        help="Select reading sections for an action in the current stage; never changes gates",
    )
    plan_parser.add_argument(
        "--granularity",
        choices=("stage", "operation"),
        default="stage",
        help="Project either the stage contract or the current executable operation graph",
    )

    protocol_parser = subparsers.add_parser(
        "protocol",
        help="Compile, validate, or explicitly render the design-owned executable protocol",
    )
    protocol_actions = protocol_parser.add_subparsers(dest="protocol_action", required=True)
    protocol_compile = protocol_actions.add_parser("compile", help="Compile the action DAG without writing")
    protocol_compile.add_argument("outdir", type=Path)
    protocol_compile.add_argument("--json", action="store_true")
    protocol_validate = protocol_actions.add_parser("validate", help="Validate the complete OPR-to-STEP path")
    protocol_validate.add_argument("outdir", type=Path)
    protocol_validate.add_argument("--json", action="store_true")
    protocol_render = protocol_actions.add_parser("render", help="Refresh generated protocol views")
    protocol_render.add_argument("outdir", type=Path)

    manuscript_parser = subparsers.add_parser(
        "manuscript",
        help="Initialize, compile, prove, validate, or render the build-internal manuscript graph",
    )
    manuscript_actions = manuscript_parser.add_subparsers(dest="manuscript_action", required=True)
    manuscript_init = manuscript_actions.add_parser("init", help="Generate a global contract scaffold from registered authorities")
    manuscript_init.add_argument("outdir", type=Path)
    manuscript_init.add_argument("--apply", action="store_true", help="Write the scaffold; otherwise print it without mutation")
    manuscript_init.add_argument(
        "--profile",
        choices=MANUSCRIPT_PROFILES,
        default=None,
        help="Manuscript genre profile; defaults to workflow_config.manuscript_profile, else auto-detected from research_design.json method routes",
    )
    manuscript_compile = manuscript_actions.add_parser("compile", help="Compile Contract to MIR without writing")
    manuscript_compile.add_argument("outdir", type=Path)
    manuscript_compile.add_argument("--json", action="store_true")
    manuscript_validate = manuscript_actions.add_parser("validate", help="Validate current MIR, generated views, and stale state")
    manuscript_validate.add_argument("outdir", type=Path)
    manuscript_validate.add_argument("--json", action="store_true")
    manuscript_proof = manuscript_actions.add_parser(
        "prove-rebuild",
        help="Record per-Move transient proof for the current stale closure",
    )
    manuscript_proof.add_argument("outdir", type=Path)
    manuscript_proof.add_argument(
        "--entry",
        action="append",
        required=True,
        metavar="MOVE=KIND=RELATIVE_PATH",
        help=(
            "Repeat six times per rebuilt Move for prose_packet, writer_draft, "
            "clarity_draft, clarity_ledger, semantic_dispatch, and semantic_assurance; "
            "section_output is optional and must equal the assured clarity draft"
        ),
    )
    manuscript_proof.add_argument("--apply", action="store_true", required=True)
    manuscript_render = manuscript_actions.add_parser("render", help="Render MIR and deterministic views after validation")
    manuscript_render.add_argument("outdir", type=Path)
    manuscript_render.add_argument(
        "--baseline",
        action="store_true",
        help="Explicitly enable AMC once; legacy planning views are archived with SHA evidence before replacement",
    )
    manuscript_restore = manuscript_actions.add_parser(
        "restore-legacy",
        help="Verify or restore one recoverable pre-baseline planning-view archive",
    )
    manuscript_restore.add_argument("outdir", type=Path)
    manuscript_restore.add_argument("archive_manifest", type=Path)
    manuscript_restore.add_argument("--apply", action="store_true")

    next_parser = subparsers.add_parser(
        "next",
        help="Return the earliest executable research action without mutation",
    )
    next_parser.add_argument("outdir", type=Path)
    next_parser.add_argument("--json", action="store_true")
    next_parser.add_argument("--explain", action="store_true")

    gate_parser = subparsers.add_parser("gate")
    gate_parser.add_argument("outdir", type=Path)
    gate_parser.add_argument("--stage", choices=CLI_STAGES, required=True)
    gate_parser.add_argument("--repair", action="store_true")

    migrate_parser = subparsers.add_parser("migrate")
    migrate_parser.add_argument("outdir", type=Path)
    migrate_parser.add_argument("--from", dest="migration_source", choices=("legacy",), default="legacy")
    migrate_parser.add_argument("--to", choices=("7",), default="7")
    migrate_mode = migrate_parser.add_mutually_exclusive_group(required=True)
    migrate_mode.add_argument("--dry-run", action="store_true")
    migrate_mode.add_argument("--apply", action="store_true")
    migrate_mode.add_argument(
        "--rollback",
        type=Path,
        metavar="BACKUP_MANIFEST",
        help="Restore the pre-migration config from a verified backup manifest",
    )

    recover_parser = subparsers.add_parser(
        "recover-lock",
        help="Diagnose workspace locks; remove only confirmed stale local locks",
    )
    recover_parser.add_argument("outdir", type=Path)
    recover_parser.add_argument("--lock", action="append", choices=LOCK_NAMES, dest="locks")
    recover_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Remove locks only when their local owner PID is confirmed dead",
    )

    qa_parser = subparsers.add_parser(
        "record-render-qa",
        help="Record explicit visual review of the current staged output candidate",
    )
    qa_parser.add_argument("outdir", type=Path)
    qa_parser.add_argument("--reviewer-mode", choices=("human", "single_agent", "independent"), required=True)
    qa_parser.add_argument("--reviewed-by", default="")
    qa_parser.add_argument("--notes", default="")
    qa_parser.add_argument("--confirm-visual-review", action="store_true", required=True)

    decision_parser = subparsers.add_parser(
        "research-decision",
        help="Plan/apply/rollback candidate, novelty, and question-challenge mutations under the controller lock",
    )
    decision_actions = decision_parser.add_subparsers(
        dest="research_decision_action",
        required=True,
    )
    bind_parser = decision_actions.add_parser("bind")
    bind_parser.add_argument("outdir", type=Path)
    bind_parser.add_argument("--apply", action="store_true")
    challenge_parser = decision_actions.add_parser("challenge")
    challenge_parser.add_argument("outdir", type=Path)
    challenge_parser.add_argument("--reason", required=True)
    challenge_parser.add_argument("--source", required=True)
    challenge_parser.add_argument("--opened-at", required=True)
    challenge_parser.add_argument("--evidence-id", action="append", default=[])
    challenge_parser.add_argument("--question-version-id")
    challenge_parser.add_argument("--apply", action="store_true")
    reopen_parser = decision_actions.add_parser("reopen")
    reopen_parser.add_argument("outdir", type=Path)
    reopen_parser.add_argument("--challenge-id", required=True)
    reopen_parser.add_argument("--question-file", type=Path, required=True)
    reopen_parser.add_argument("--resolution", required=True)
    reopen_parser.add_argument("--resolved-at", required=True)
    reopen_parser.add_argument("--apply", action="store_true")
    retained_parser = decision_actions.add_parser("resolve-retained")
    retained_parser.add_argument("outdir", type=Path)
    retained_parser.add_argument("--challenge-id", required=True)
    retained_parser.add_argument("--resolution", required=True)
    retained_parser.add_argument("--resolved-at", required=True)
    retained_parser.add_argument("--apply", action="store_true")
    decision_migrate_parser = decision_actions.add_parser("migrate")
    decision_migrate_parser.add_argument("outdir", type=Path)
    decision_migrate_parser.add_argument("--decision-file", type=Path, required=True)
    decision_migrate_parser.add_argument("--apply", action="store_true")
    decision_rollback_parser = decision_actions.add_parser("rollback")
    decision_rollback_parser.add_argument("outdir", type=Path)
    decision_rollback_parser.add_argument("--manifest", type=Path, required=True)
    decision_rollback_parser.add_argument("--apply", action="store_true")

    material_parser = subparsers.add_parser(
        "research-materials",
        help="Validate and transactionally probe acquisition-owned material facts",
    )
    material_actions = material_parser.add_subparsers(dest="research_material_action", required=True)
    material_init = material_actions.add_parser("init")
    material_init.add_argument("outdir", type=Path)
    material_init.add_argument("--not-applicable", action="store_true")
    material_init.add_argument("--rationale", default="Material applicability requires explicit review before research.")
    material_init.add_argument("--apply", action="store_true")
    material_validate = material_actions.add_parser("validate")
    material_validate.add_argument("outdir", type=Path)
    material_validate.add_argument("--scope", choices=("acquisition", "research"), default="acquisition")
    material_validate.add_argument("--json", action="store_true")
    material_probe = material_actions.add_parser("probe")
    material_probe.add_argument("outdir", type=Path)
    material_probe.add_argument("--material", required=True)
    material_probe.add_argument("--adapter", choices=("local-file", "tabular", "api", "public-text", "archive", "human-subject", "restricted-data", "manual-evidence"), required=True)
    material_probe.add_argument("--sample", type=Path, required=True)
    material_probe.add_argument("--performed-at", default=datetime.now(timezone.utc).isoformat())
    material_probe.add_argument("--candidate-semantic-digest", required=True)
    material_probe.add_argument("--question-version-digest", required=True)
    material_probe.add_argument("--failure-code")
    material_probe.add_argument("--details", default="")
    material_probe.add_argument("--field", action="append", default=[])
    material_probe.add_argument("--key-assessment", default="")
    material_probe.add_argument("--query-summary", default="")
    material_probe.add_argument("--pagination-status", default="")
    material_probe.add_argument("--rate-limit-status", default="")
    material_probe.add_argument("--deduplication-status", default="")
    material_probe.add_argument("--time-coverage", default="{}")
    material_probe.add_argument("--spatial-coverage", default="{}")
    material_probe.add_argument("--unit-coverage", default="{}")
    material_probe.add_argument(
        "--header-confirmed",
        action="store_true",
        help="Confirm that a tabular CSV/TSV sample's first row contains field names",
    )
    material_probe.add_argument("--apply", action="store_true")
    material_rollback = material_actions.add_parser("rollback")
    material_rollback.add_argument("outdir", type=Path)
    material_rollback.add_argument("--manifest", type=Path, required=True)
    material_rollback.add_argument("--apply", action="store_true")

    feasibility_parser = subparsers.add_parser(
        "research-feasibility",
        help="Bind F2 minimum-viable-evidence judgments and inspect resource unlocks",
    )
    feasibility_actions = feasibility_parser.add_subparsers(dest="research_feasibility_action", required=True)
    feasibility_validate = feasibility_actions.add_parser("validate")
    feasibility_validate.add_argument("outdir", type=Path)
    feasibility_validate.add_argument("--json", action="store_true")
    feasibility_bind = feasibility_actions.add_parser("bind")
    feasibility_bind.add_argument("outdir", type=Path)
    feasibility_bind.add_argument("--assessment", type=Path, required=True)
    feasibility_bind.add_argument("--select", action="store_true")
    feasibility_bind.add_argument("--apply", action="store_true")
    feasibility_reopen = feasibility_actions.add_parser("reopen")
    feasibility_reopen.add_argument("outdir", type=Path)
    feasibility_reopen.add_argument("--reason", required=True)
    feasibility_reopen.add_argument("--apply", action="store_true")
    feasibility_rollback = feasibility_actions.add_parser("rollback")
    feasibility_rollback.add_argument("outdir", type=Path)
    feasibility_rollback.add_argument("--manifest", type=Path, required=True)
    feasibility_rollback.add_argument("--apply", action="store_true")
    feasibility_authorize = feasibility_actions.add_parser("authorize")
    feasibility_authorize.add_argument("outdir", type=Path)
    feasibility_authorize.add_argument("--action", required=True)
    feasibility_authorize.add_argument("--question-committed", action="store_true")
    feasibility_state = feasibility_actions.add_parser("resource-state")
    feasibility_state.add_argument("outdir", type=Path)
    feasibility_state.add_argument("--question-committed", action="store_true")

    args = parser.parse_args()
    skills_dir = args.skills_dir.resolve()
    if args.command == "doctor":
        doctor_outdir = args.outdir.resolve() if args.outdir is not None else None
        result = run_doctor(skills_dir, repair=args.repair, outdir=doctor_outdir)
        print(
            json.dumps(
                {"status": "PASS" if result.ok else "FAIL", "issues": result.issues, **result.details},
                ensure_ascii=False,
                indent=2,
            )
            if args.json
            else doctor_markdown(result)
        )
        return 0 if result.ok else 1

    outdir = args.outdir.resolve()
    if args.command == "manuscript":
        config_read = read_config(outdir)
        active_config = config_read.payload if config_read.path is not None else {}
        if args.manuscript_action == "init":
            try:
                contract = init_manuscript_contract(outdir, active_config, profile_id=args.profile)
                if args.apply:
                    output = write_initialized_contract(outdir, contract)
                    print(f"Initialized manuscript contract ({contract.get('genre_profile')}): {output}")
                else:
                    print(json.dumps(contract, ensure_ascii=False, indent=2))
            except ManuscriptCompilerError as exc:
                print(str(exc), file=sys.stderr)
                for issue in exc.issues:
                    print(f"[{issue.code}] {issue.message}", file=sys.stderr)
                return 2
            return 0
        if args.manuscript_action == "compile":
            result = compile_manuscript(outdir, active_config)
            payload = result.as_dict()
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"# Avereth Manuscript Compilation\n\nStatus: **{payload['status']}**")
                for issue in payload["issues"]:
                    print(f"- `{issue['code']}` {issue['message']}")
                if payload.get("stale"):
                    print(f"- Stale state: `{payload['stale'].get('status')}`")
            return 0 if result.valid else 1
        if args.manuscript_action == "validate":
            issues = validate_manuscript(outdir, active_config)
            payload = {
                "schema_version": "avereth-manuscript-validation/v1",
                "status": "PASS" if not issues else "FAIL",
                "issues": [issue.as_dict() for issue in issues],
            }
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(f"# Avereth Manuscript Validation\n\nStatus: **{payload['status']}**")
                for issue in payload["issues"]:
                    print(f"- `{issue['code']}` {issue['message']}")
            return 0 if not issues else 1
        if args.manuscript_action == "prove-rebuild":
            entries: list[tuple[str, str, str]] = []
            for raw in args.entry:
                parts = raw.split("=", 2)
                if len(parts) != 3 or not all(part.strip() for part in parts):
                    print("--entry must use MOVE=KIND=RELATIVE_PATH", file=sys.stderr)
                    return 2
                entries.append((parts[0].strip(), parts[1].strip(), parts[2].strip()))
            try:
                output = record_rebuild_proofs(outdir, active_config, entries)
            except ManuscriptCompilerError as exc:
                print(str(exc), file=sys.stderr)
                for issue in exc.issues:
                    print(f"[{issue.code}] {issue.message}", file=sys.stderr)
                return 2
            print(f"Recorded transient per-Move rebuild proof: {output}")
            return 0
        if args.manuscript_action == "restore-legacy":
            try:
                result = restore_legacy_archive(
                    outdir,
                    args.archive_manifest,
                    apply=args.apply,
                )
            except ManuscriptCompilerError as exc:
                print(str(exc), file=sys.stderr)
                for issue in exc.issues:
                    print(f"[{issue.code}] {issue.message}", file=sys.stderr)
                return 2
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.manuscript_action == "render":
            try:
                outputs = render_manuscript(outdir, active_config, baseline=args.baseline)
            except ManuscriptCompilerError as exc:
                print(str(exc), file=sys.stderr)
                for issue in exc.issues:
                    print(f"[{issue.code}] {issue.message}", file=sys.stderr)
                return 2
            for output in outputs:
                verb = "Archived legacy view" if output.parts[: len(LEGACY_ARCHIVE_ROOT_REL.parts)] == LEGACY_ARCHIVE_ROOT_REL.parts else "Rendered manuscript view"
                print(f"{verb}: {outdir / output}")
            return 0
        raise AssertionError(args.manuscript_action)
    if args.command == "protocol":
        if args.protocol_action == "validate":
            report = validate_protocol(outdir)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print(f"# Research Protocol Check\n\n- Status: **{report['status']}**")
                for issue in report.get("issues") or []:
                    print(f"- `{issue.get('code')}` {issue.get('message')}")
            return 0 if report.get("status") == "PASS" else 1
        if args.protocol_action == "compile":
            try:
                projection = compile_protocol(outdir)
            except ProtocolCompilerError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            print(
                json.dumps(projection, ensure_ascii=False, indent=2)
                if args.json
                else protocol_markdown(projection),
                end="" if not args.json else "\n",
            )
            return 0 if projection.get("valid") else 1
        if args.protocol_action == "render":
            try:
                outputs = render_protocol_views(outdir)
            except ProtocolCompilerError as exc:
                print(str(exc), file=sys.stderr)
                return 2
            for output in outputs:
                print(f"Rendered generated view: {output}")
            return 0
        raise AssertionError(args.protocol_action)
    if args.command == "next":
        try:
            projection = next_projection(outdir)
        except ProtocolCompilerError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(
            json.dumps(projection, ensure_ascii=False, indent=2)
            if args.json
            else next_markdown(projection),
            end="" if not args.json else "\n",
        )
        return 0 if not projection.get("issues") else 1
    if args.command == "research-materials":
        return _run_research_material_command(args, outdir)
    if args.command == "research-feasibility":
        return _run_research_feasibility_command(args, outdir)
    if args.command == "research-decision":
        return _run_research_decision_command(args, outdir)
    if args.command == "gate":
        return gate_stage(outdir, args.stage, skills_dir, repair=args.repair)
    if args.command == "status":
        payload, code = status_payload(outdir, skills_dir, repair=args.repair)
        markdown = status_markdown(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else markdown)
        if args.write:
            print("status --write is deprecated and intentionally does not mutate the workspace", file=sys.stderr)
        return code
    if args.command == "scout-capture":
        def accept_scout() -> dict[str, Any]:
            payload, _ = status_payload(outdir, skills_dir)
            active = read_config(outdir).payload
            plan = build_plan(payload, active, reference_action=args.reference_action,
                              discovery_context=load_discovery_context(outdir, args.discovery_brief))
            request = next((item for item in plan["delegation_requests"]
                            if item["request_id"] == args.request_id and item["role"] == "avereth_scout"), None)
            if request is None:
                raise ValueError("Scout request is no longer eligible at the current stage/input version")
            raw = args.result.read_bytes()
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError("Scout result exceeds 32 MiB")
            result = json.loads(raw.decode("utf-8-sig"))
            validate_candidate_result(request, result)
            return (capture_candidates(outdir, request, result) if args.apply else
                    {"status": "valid_candidates_only", "request_id": request["request_id"]})
        try:
            if args.apply:
                with exclusive_lock(outdir, ".avereth-transition.lock",
                                    "Workspace is busy; retry candidate capture later", operation="scout-capture"):
                    result = accept_scout()
            else:
                result = accept_scout()
        except (ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "plan":
        payload, code = status_payload(outdir, skills_dir)
        config_read = read_config(outdir)
        protocol: dict[str, Any] | None = None
        if args.granularity == "operation" and payload.get("next_stage") == "execution":
            try:
                protocol = compile_protocol(outdir)
            except ProtocolCompilerError as exc:
                protocol = {
                    "valid": False,
                    "issues": [
                        {
                            "code": "PROTOCOL.FACT_MISSING",
                            "message": str(exc),
                            "path": "research_design.json",
                        }
                    ],
                }
        try:
            plan = build_plan(
                payload,
                config_read.payload if config_read.path is not None else {},
                protocol=protocol,
                granularity=args.granularity,
                reference_action=args.reference_action,
                discovery_context=(load_discovery_context(outdir, args.discovery_brief)
                                   if args.discovery_brief else None),
            )
        except (ValueError, OSError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        record_runtime_event("reference_plan", stage=plan.get("next_stage"),
                             semantic_phase=plan.get("semantic_phase"),
                             reference_action=plan.get("reference_action"),
                             reference_requests=plan.get("reference_requests", []),
                             actual_read_bytes=None)
        print(json.dumps(plan, ensure_ascii=False, indent=2) if args.json else plan_markdown(plan))
        return code
    if args.command == "migrate":
        if args.migration_source != "legacy":
            raise AssertionError(args.migration_source)
        if args.rollback is not None:
            report, code = rollback_v6_migration(outdir, args.rollback)
        elif args.apply:
            report, code = apply_v6_migration(outdir)
        else:
            planned = v6_migration_plan(outdir)
            report, code = planned, 2 if planned.get("status") == "blocked" else 0
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    if args.command == "recover-lock":
        report = recover_workspace_locks(
            outdir,
            names=tuple(args.locks or LOCK_NAMES),
            confirm=args.confirm,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2 if args.confirm and report.get("refused") else 0
    if args.command == "record-render-qa":
        try:
            with output_gate_lock(outdir):
                report, code = record_visual_qa(
                    outdir,
                    reviewer_mode=args.reviewer_mode,
                    reviewed_by=args.reviewed_by,
                    notes=args.notes,
                )
        except RuntimeError as exc:
            report, code = {"status": "BLOCKED", "issues": [str(exc)]}, 2
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
