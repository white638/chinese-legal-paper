"""Canonical v7 workflow configuration with conservative legacy reading."""

from __future__ import annotations

import json
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .version import VERSION, WORKFLOW_CONFIG_SCHEMA


WORKFLOW_CONFIG_REL = Path("workflow_config.json")
WORKFLOW_CONFIG_MD_REL = Path("workflow_config.md")
LEGACY_CONFIG_REL = Path("paper_spine_config.json")
LEGACY_CONFIG_MD_REL = Path("paper_spine_config.md")

TOPIC_ORIGIN_MODES = {"direction_first", "workspace_extension", "material_opportunity", "phenomenon_first"}
TOPIC_BRAINSTORM_DEPTHS = {"broad", "focused"}
TOPIC_WORKSPACE_POLICIES = {"quarantine_until_divergence", "declared_source_from_start"}
# Optional pin for the branch taste card (references/taste/branch-taste-cards.json);
# it never gates a stage, it only selects which four-flavour criteria the judge loads.
TOPIC_SELECTION_OPTIONAL_FIELDS = frozenset({"taste_card"})
TASTE_CARD_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DIRECTION_CONTRACT_FIELDS = (
    "current_user_goal",
    "field",
    "core_problem",
    "preferred_contribution",
    "object_scope",
    "must_preserve",
    "must_avoid",
    "acceptable_adjacency",
    "publication_track",
    "method_role",
    "workspace_role",
    "authority",
)
DIRECTION_CONTRACT_FIELD_SET = frozenset(DIRECTION_CONTRACT_FIELDS)


def effective_topic_selection_policy(payload: dict[str, Any]) -> dict[str, str]:
    """Return the safe topic-origin policy without mutating legacy configs.

    New intake writes this block explicitly.  A pre-v7.1 workspace that lacks
    it is read with the direction-first default so mere material presence can
    never opt it into a material-origin route.
    """

    declared = payload.get("topic_selection")
    declared = declared if isinstance(declared, dict) else {}
    origin_mode = str(declared.get("origin_mode") or "direction_first").strip()
    brainstorm_depth = str(declared.get("brainstorm_depth") or "broad").strip()
    workspace_policy = str(declared.get("workspace_policy") or "").strip()
    if not workspace_policy:
        workspace_policy = (
            "quarantine_until_divergence"
            if origin_mode == "direction_first"
            else "declared_source_from_start"
        )
    return {
        "origin_mode": origin_mode,
        "brainstorm_depth": brainstorm_depth,
        "workspace_policy": workspace_policy,
    }


def validate_workflow_config(payload: dict[str, Any]) -> list[str]:
    """Validate the stable v6 intake contract without writing anything."""

    issues: list[str] = []
    if "legal_profile" in payload and payload["legal_profile"] != "chinese-law-v1":
        issues.append("legal_profile must be chinese-law-v1 when declared")
    if payload.get("framework_version") != VERSION:
        issues.append(f"framework_version must be {VERSION}; migrate explicitly")
    if payload.get("schema_version") != WORKFLOW_CONFIG_SCHEMA:
        issues.append(f"schema_version must be {WORKFLOW_CONFIG_SCHEMA}; migrate explicitly")
    if payload.get("workflow") not in {"rewrite_existing", "build_from_materials"}:
        issues.append("workflow must be rewrite_existing or build_from_materials")
    profile = str(payload.get("task_profile") or "").strip().lower().replace("-", "_")
    if profile not in {"full_paper", "topic_selection", "research_design", "manuscript_audit", "manuscript_revision"}:
        issues.append("task_profile is missing or unsupported")
    if str(payload.get("publication_track") or "").strip().lower().replace("_", "-") not in {
        "cnki-cn", "international-ssci", "mixed"
    }:
        issues.append("publication_track must be cnki-cn, international-ssci, or mixed")
    if payload.get("scene") not in {"journal", "conference", "report_review", "competition"}:
        issues.append("scene must be journal, conference, report_review, or competition")
    if payload.get("tier") not in {"flash", "pro"}:
        issues.append("tier must be flash or pro")
    if payload.get("output_language") not in {"en", "zh"}:
        issues.append("output_language must be en or zh")
    if payload.get("word_output") not in {"none", "docx"}:
        issues.append("word_output must be none or docx")
    if payload.get("pdf_output") not in {"none", "pdf"}:
        issues.append("pdf_output must be none or pdf")
    if payload.get("word_output") == "none" and payload.get("pdf_output") == "none" and profile in {
        "full_paper", "manuscript_revision"
    }:
        issues.append("full delivery requires word_output=docx and/or pdf_output=pdf")
    if payload.get("citation_mode") not in {"numeric", "author_year", "footnote"}:
        issues.append("citation_mode must be numeric, author_year, or footnote")
    if payload.get("word_font_policy") not in {"default", "template", "skip"}:
        issues.append("word_font_policy must be default, template, or skip")
    if payload.get("prose_mode") not in {"clear", "distinguished"}:
        issues.append("prose_mode must be clear or distinguished")
    if payload.get("prose_conditioning", "none") not in {"none", "commonplace", "auto"}:
        issues.append("prose_conditioning must be none, commonplace, or auto")
    topic_selection = payload.get("topic_selection")
    if profile == "topic_selection" and topic_selection is None:
        issues.append(
            "task_profile=topic_selection requires an explicit topic_selection policy; "
            "migrate or rebuild the direction contract"
        )
        if not isinstance(payload.get("direction_contract"), dict):
            issues.append(
                "task_profile=topic_selection requires direction_contract; "
                "migrate or rebuild it from the current user request"
            )
    if topic_selection is not None:
        if profile != "topic_selection":
            issues.append("topic_selection policy is available only when task_profile=topic_selection")
        if not isinstance(topic_selection, dict):
            issues.append("topic_selection must be an object when declared")
        else:
            required_policy_fields = {
                "origin_mode",
                "brainstorm_depth",
                "workspace_policy",
            }
            extra_policy_fields = sorted(
                set(topic_selection) - required_policy_fields - TOPIC_SELECTION_OPTIONAL_FIELDS
            )
            taste_card = topic_selection.get("taste_card")
            if taste_card is not None and not (
                isinstance(taste_card, str) and TASTE_CARD_SLUG_RE.match(taste_card.strip())
            ):
                issues.append("topic_selection.taste_card must be a kebab-case branch taste-card slug")
            if extra_policy_fields:
                issues.append(
                    "topic_selection contains unauthorized fields: "
                    + ", ".join(str(item) for item in extra_policy_fields)
                )
            missing_policy_fields = sorted(required_policy_fields - set(topic_selection))
            if missing_policy_fields:
                issues.append(
                    "topic_selection lacks required fields: "
                    + ", ".join(missing_policy_fields)
                )
            policy = effective_topic_selection_policy(payload)
            if policy["origin_mode"] not in TOPIC_ORIGIN_MODES:
                issues.append("topic_selection.origin_mode is unsupported")
            if policy["brainstorm_depth"] not in TOPIC_BRAINSTORM_DEPTHS:
                issues.append("topic_selection.brainstorm_depth must be broad or focused")
            if policy["workspace_policy"] not in TOPIC_WORKSPACE_POLICIES:
                issues.append("topic_selection.workspace_policy is unsupported")
            if (
                policy["origin_mode"] == "direction_first"
                and policy["workspace_policy"] != "quarantine_until_divergence"
            ):
                issues.append(
                    "topic_selection.origin_mode=direction_first requires "
                    "workspace_policy=quarantine_until_divergence"
                )
            if (
                policy["origin_mode"] != "direction_first"
                and policy["workspace_policy"] != "declared_source_from_start"
            ):
                issues.append(
                    "workspace_extension/material_opportunity/phenomenon_first require "
                    "workspace_policy=declared_source_from_start"
                )
        direction = payload.get("direction_contract")
        if not isinstance(direction, dict):
            issues.append("declared topic_selection policy requires direction_contract")
        else:
            extra_direction_fields = sorted(
                str(key)
                for key in direction
                if key not in DIRECTION_CONTRACT_FIELD_SET
            )
            if extra_direction_fields:
                issues.append(
                    "direction_contract contains unauthorized fields: "
                    + ", ".join(extra_direction_fields)
                )
            for key, minimum in {
                "current_user_goal": 4,
                "field": 2,
                "core_problem": 4,
                "object_scope": 4,
            }.items():
                if len(str(direction.get(key) or "").strip()) < minimum:
                    issues.append(f"direction_contract.{key} is missing or too weak")
            contributions = direction.get("preferred_contribution")
            if (
                not isinstance(contributions, list)
                or not contributions
                or any(len(str(item or "").strip()) < 2 for item in contributions)
            ):
                issues.append("direction_contract.preferred_contribution must be a non-empty list")
            for key in ("must_preserve", "must_avoid"):
                value = direction.get(key)
                if not isinstance(value, list) or any(not str(item or "").strip() for item in value):
                    issues.append(f"direction_contract.{key} must be an array of non-empty strings")
            if direction.get("acceptable_adjacency") not in {"narrow", "medium", "broad"}:
                issues.append("direction_contract.acceptable_adjacency must be narrow, medium, or broad")
            if direction.get("publication_track") != payload.get("publication_track"):
                issues.append("direction_contract.publication_track must match workflow publication_track")
            if direction.get("method_role") not in {"open", "preferred", "fixed-by-user"}:
                issues.append("direction_contract.method_role is unsupported")
            expected_workspace_role = {
                "direction_first": "optional-after-divergence",
                "workspace_extension": "declared-extension-source",
                "material_opportunity": "declared-material-source",
                "phenomenon_first": "declared-phenomenon-source",
            }.get(effective_topic_selection_policy(payload)["origin_mode"])
            if direction.get("workspace_role") != expected_workspace_role:
                issues.append(
                    "direction_contract.workspace_role does not match topic_selection.origin_mode"
                )
            if direction.get("authority") != "current-user-request":
                issues.append("direction_contract.authority must be current-user-request")
    if "delegation_policy" in payload:
        from .application.delegation import delegation_policy
        try:
            delegation_policy(payload)
        except ValueError as exc:
            issues.append(str(exc))
    resource_policy = payload.get("resource_policy")
    if resource_policy is not None:
        if not isinstance(resource_policy, dict):
            issues.append("resource_policy must be an object when declared")
        else:
            for key in ("max_f1_metadata_queries", "max_f2_sample_bytes", "max_f2_probe_seconds"):
                value = resource_policy.get(key)
                if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                    issues.append(f"resource_policy.{key} must be a positive integer")
    translation = str(payload.get("translation_package") or "none").strip().lower()
    if translation not in {"none", "zh"}:
        issues.append("translation_package must be none or zh")
    if translation == "zh":
        if payload.get("output_language") != "en":
            issues.append("translation_package=zh requires output_language=en; a Chinese primary manuscript is not a translation route")
        if not str(payload.get("translation_source") or "").strip():
            issues.append("translation_package=zh requires translation_source")
        if not str(payload.get("translation_coverage_source") or "").strip():
            issues.append("translation_package=zh requires translation_coverage_source")
    submission = str(payload.get("submission_package") or "none").strip().lower()
    if submission not in {"none", "journal"}:
        issues.append("submission_package must be none or journal")
    if submission == "journal":
        if not str(payload.get("target_name") or "").strip():
            issues.append("submission_package=journal requires target_name")
        if not str(payload.get("submission_source_dir") or "").strip():
            issues.append("submission_package=journal requires submission_source_dir")
        if not str(payload.get("submission_contract") or "").strip():
            issues.append("submission_package=journal requires submission_contract")
        required = payload.get("submission_required_files")
        if not isinstance(required, list) or not required or any(not str(item or "").strip() for item in required):
            issues.append("submission_package=journal requires a non-empty submission_required_files list")
    response = str(payload.get("response_package") or "none").strip().lower()
    if response not in {"none", "review_response", "rebuttal"}:
        issues.append("response_package must be none, review_response, or rebuttal")
    if response != "none":
        if profile != "manuscript_revision":
            issues.append("formal response/rebuttal packaging requires task_profile=manuscript_revision")
        if not str(payload.get("response_source_dir") or "").strip():
            issues.append("formal response/rebuttal packaging requires response_source_dir")
        if not str(payload.get("response_review_source") or "").strip():
            issues.append("formal response/rebuttal packaging requires response_review_source")
        required = payload.get("response_required_files")
        if not isinstance(required, list) or not required or any(not str(item or "").strip() for item in required):
            issues.append("formal response/rebuttal packaging requires a non-empty response_required_files list")
    if profile not in {"full_paper", "manuscript_revision"} and any(
        value != "none" for value in (translation, submission, response)
    ):
        issues.append("deliverable packages are available only to full_paper or manuscript_revision profiles")
    canonical = str(payload.get("canonical_manuscript") or "").strip()
    legacy_alias = str(payload.get("citation_audit_manuscript") or "").strip()
    draft = str(payload.get("draft_path") or "").strip()
    if legacy_alias:
        issues.append("citation_audit_manuscript is a legacy alias; migrate it to canonical_manuscript")
    if canonical and draft:
        issues.append("canonical_manuscript and draft_path cannot both be active; choose one manuscript authority")
    if legacy_alias and draft:
        issues.append("citation_audit_manuscript and draft_path cannot both be active; choose one manuscript authority")
    return issues


@dataclass(frozen=True)
class ConfigRead:
    payload: dict[str, Any]
    path: Path | None
    legacy: bool = False
    issues: tuple[str, ...] = ()


def config_path(outdir: Path) -> Path | None:
    for relative in (WORKFLOW_CONFIG_REL, LEGACY_CONFIG_REL):
        candidate = outdir / relative
        if candidate.is_file():
            return candidate
    return None


def config_exists(outdir: Path) -> bool:
    return config_path(outdir) is not None


def read_config(outdir: Path) -> ConfigRead:
    current_path = outdir / WORKFLOW_CONFIG_REL
    legacy_path = outdir / LEGACY_CONFIG_REL
    path = current_path if current_path.is_file() else legacy_path if legacy_path.is_file() else None
    if path is None:
        return ConfigRead({}, None, False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return ConfigRead({}, path, path.name == LEGACY_CONFIG_REL.name, (f"invalid workflow config: {path.name}",))
    if not isinstance(payload, dict):
        payload = {}
    issues: list[str] = []
    if current_path.is_file() and legacy_path.is_file():
        try:
            legacy_payload = json.loads(legacy_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            legacy_payload = None
        migration = payload.get("migration") if isinstance(payload.get("migration"), dict) else {}
        retired_digest = str(migration.get("legacy_config_sha256") or "")
        current_legacy_digest = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
        if retired_digest:
            if current_legacy_digest != retired_digest:
                issues.append(
                    "retired paper_spine_config.json changed after migration; reconcile it explicitly"
                )
        elif not isinstance(legacy_payload, dict):
            issues.append("paper_spine_config.json is invalid while workflow_config.json also exists")
        else:
            ignored = {"framework_version", "migration"}
            current_semantic = {key: value for key, value in payload.items() if key not in ignored}
            legacy_semantic = {key: value for key, value in legacy_payload.items() if key not in ignored}
            if current_semantic != legacy_semantic:
                issues.append(
                    "workflow_config.json conflicts with paper_spine_config.json; migrate or reconcile explicitly"
                )
    return ConfigRead(payload, path, path.name == LEGACY_CONFIG_REL.name, tuple(issues))


def write_config(outdir: Path, payload: dict[str, Any]) -> Path:
    """Write only the v6 canonical name; legacy files are never overwritten."""

    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / WORKFLOW_CONFIG_REL
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def canonical_config_relative(outdir: Path) -> str:
    read = read_config(outdir)
    return read.path.name if read.path is not None else WORKFLOW_CONFIG_REL.name
