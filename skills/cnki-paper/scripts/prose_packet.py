#!/usr/bin/env python3
"""Compile a minimal, identity-bound ProsePacket for isolated manuscript writing.

The packet is a transient build view. It is deliberately not a workflow stage,
source registry, receipt, or completion authority. The compiler performs only
deterministic materiality checks; scholarly judgment still belongs to the
current CNKI-Paper build decision.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


LEGACY_SCHEMA_VERSION = "avereth-prose-packet/v1"
SCHEMA_VERSION = "avereth-prose-packet/v2"
SUPPORTED_SCHEMA_VERSIONS = frozenset({LEGACY_SCHEMA_VERSION, SCHEMA_VERSION})
CLARITY_LEDGER_SCHEMA_VERSION = "avereth-clarity-edit-ledger/v1"
SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION = "avereth-semantic-fidelity-review/v1"
SEMANTIC_FIDELITY_DISPATCH_SCHEMA_VERSION = "avereth-semantic-fidelity-dispatch/v1"
SEMANTIC_FIDELITY_ASSURANCE_SCHEMA_VERSION = "avereth-semantic-fidelity-assurance/v1"

LEGACY_ACTION_MAP = {
    "omit": "omit",
    "verb_only": "calibrated_verb",
    "state_once": "single_full_statement",
    "footnote": "footnote_or_cross_reference",
}
MANUSCRIPT_ACTIONS = frozenset(
    {
        "omit",
        "calibrated_verb",
        "positive_scope",
        "single_full_statement",
        "footnote_or_cross_reference",
        *LEGACY_ACTION_MAP,
    }
)
ACTIVE_ACTIONS = frozenset(LEGACY_ACTION_MAP.get(action, action) for action in MANUSCRIPT_ACTIONS) - {
    "omit"
}
REALIZATION_MODES = frozenset({"semantic", "verbatim", "legacy_exact"})
VERBATIM_REASONS = frozenset(
    {
        "direct_quote",
        "legal_text",
        "formal_hypothesis",
        "scale_item",
        "registered_definition",
        "user_locked",
    }
)
POLARITY_ALIASES = {
    "affirmative": "affirmative",
    "positive": "affirmative",
    "affirmed": "affirmative",
    "肯定": "affirmative",
    "negative": "negative",
    "negated": "negative",
    "否定": "negative",
    "mixed": "mixed",
    "混合": "mixed",
}
EXPLANATION_FUNCTIONS = frozenset(
    {
        "orient",
        "observable_change",
        "claim",
        "evidence",
        "evidence_role",
        "compare",
        "causal_step",
        "mechanism",
        "process",
        "warrant",
        "boundary",
        "implication",
        "meaning",
        "reader_update",
        "definition",
    }
)
CLARITY_ACTIONS = frozenset({"DELETE", "REPLACE", "MOVE", "BRIDGE", "DEFINE"})
POSITIVE_GROWTH_ACTIONS = frozenset({"BRIDGE", "DEFINE"})
CLARITY_SOURCE_KINDS = frozenset({"warrant", "explanation_path", "registered_term"})
SEMANTIC_FIDELITY_DIMENSIONS = (
    "canonical_to_draft",
    "draft_to_canonical",
    "subject_object_relation",
    "direction_polarity",
    "inferential_strength",
    "scope",
    "evidence_role",
    "boundary",
)
SEMANTIC_FIDELITY_REVIEW_KEYS = frozenset(
    {
        "schema_version",
        "review_run_id",
        "packet_sha256",
        "draft_sha256",
        "dimensions",
        "overall_status",
    }
)
SEMANTIC_FIDELITY_DIMENSION_KEYS = frozenset({"status", "reason"})
SEMANTIC_FIDELITY_DISPATCH_KEYS = frozenset(
    {
        "schema_version",
        "review_run_id",
        "input_scope",
        "packet_path",
        "packet_file_sha256",
        "packet_content_sha256",
        "draft_path",
        "draft_file_sha256",
        "draft_content_sha256",
        "prompt_path",
        "prompt_sha256",
        "review_output_path",
        "writer_context_id",
        "clarity_context_id",
    }
)
SEMANTIC_FIDELITY_ASSURANCE_KEYS = frozenset(
    {
        "schema_version",
        "review_run_id",
        "mode",
        "reviewer_context_id",
        "dispatch_manifest_path",
        "dispatch_manifest_sha256",
        "prompt_path",
        "prompt_sha256",
        "output_path",
        "output_sha256",
        "input_scope",
        "isolation_declared",
    }
)
DEFAULT_CLARITY_GROWTH_SOFT_LIMITS = {
    "section_ratio": 0.05,
    "paragraph_ratio": 0.15,
}
CLARITY_GROWTH_SOFT_LIMIT_KEYS = frozenset(DEFAULT_CLARITY_GROWTH_SOFT_LIMITS)
ANCHOR_PREFIXES: dict[str, frozenset[str]] = {
    "source": frozenset({"SRC", "CR", "SYN"}),
    "evidence": frozenset({"EVD", "EV"}),
    "design": frozenset({"DESIGN", "DSG"}),
    "method": frozenset({"DESIGN", "DSG", "EXE"}),
    "execution": frozenset({"EXE"}),
    "ethics": frozenset({"ETH"}),
    "responsibility": frozenset({"RESP"}),
}
CLAIM_PREFIXES = frozenset({"C", "CLM", "CLAIM"})
EVIDENCE_PREFIXES = frozenset({"SRC", "CR", "SYN", "EVD", "EV", "MAT", "DESIGN", "DSG", "EXE"})
RESULT_PREFIXES = frozenset({"RES"})
RESULT_USES = frozenset({"claim_support", "negative_or_null_report"})
EXECUTION_CLAIM_SECTION_ROLES = frozenset(
    {
        "abstract",
        "introduction",
        "background",
        "literature_review",
        "theory",
        "theoretical_framework",
        "method",
        "methods",
        "research_design",
        "results",
        "findings",
        "discussion",
        "limitations",
        "implications",
        "conclusion",
    }
)
REQUEST_TOP_LEVEL_KEYS = frozenset(
    {
        "section_role",
        "object",
        "claim",
        "evidence_items",
        "result_ids",
        "result_use",
        "warrant",
        "boundaries",
        "countervoices",
        "reader_question",
        "plain_core",
        "explanation_path",
        "reader_update",
        "target_length",
        "evidence_delta",
        "claim_delta",
        "clarity_growth_soft_limits",
        "rhetorical_task",
    }
)
PACKET_TOP_LEVEL_KEYS = frozenset(
    {
        "schema_version",
        "section_role",
        "object",
        "claim",
        "evidence_items",
        "result_ids",
        "result_use",
        "warrant",
        "required_boundaries",
        "material_countervoices",
        "reader_question",
        "plain_core",
        "explanation_path",
        "reader_update",
        "expression_budget",
        "source_digest",
        "target_length",
        "evidence_delta",
        "claim_delta",
        "rhetorical_task",
    }
)
CLAIM_KEYS = frozenset(
    {
        "id",
        "text",
        "canonical_proposition",
        "strength",
        "realization_mode",
        "verbatim_reason",
        "protected_atoms",
    }
)
PROTECTED_ATOM_KEYS = frozenset(
    {
        "subject",
        "relation",
        "direction",
        "polarity",
        "inferential_strength",
        "scope",
        "protected_literals",
        "protected_numbers",
        "citation_anchors",
    }
)
EVIDENCE_ITEM_KEYS = frozenset(
    {"id", "text", "locator", "citation_key", "evidence_function", "context_anchor"}
)
RHETORICAL_TASK_KEYS = frozenset(
    {"argument_action", "problem_state_before", "problem_state_after"}
)
ARGUMENT_ACTIONS = frozenset(
    {"POSE", "PRESS", "DISTINGUISH", "REVISE", "ADVANCE", "RESOLVE", "RETURN"}
)
CONTEXT_ANCHOR_KEYS = frozenset(
    {
        "anchor_id",
        "authority_ref",
        "type",
        "locator",
        "exact_span",
        "known_details",
        "original_problem",
        "logical_context",
        "protected_qualifiers",
        "manuscript_function",
        "status",
    }
)
CONTEXT_ANCHOR_TYPES = frozenset({"quotation", "scene", "case", "definition"})
CONTEXT_ANCHOR_BANK_COLUMNS = {
    "anchor_id": frozenset({"anchorid", "contextanchorid"}),
    "authority_ref": frozenset({"authorityref", "authorityreference"}),
    "type": frozenset({"type", "anchortype"}),
    "locator": frozenset({"locator"}),
    "content": frozenset({"exactspanknowndetails", "exactspanorknowndetails"}),
    "original_problem": frozenset({"originalproblem"}),
    "logical_context": frozenset({"logicalcontext"}),
    "protected_qualifiers": frozenset({"protectedqualifiers"}),
    "manuscript_function": frozenset({"manuscriptfunction"}),
    "status": frozenset({"status"}),
}
EXPLANATION_STEP_KEYS = frozenset({"step", "order", "function", "content", "anchor_id"})
BOUNDARY_KEYS = frozenset(
    {
        "boundary_id",
        "id",
        "anchor_type",
        "anchor_id",
        "materiality",
        "claim_id",
        "claim_delta",
        "claim_effect",
        "manuscript_action",
        "action",
        "preferred_realization",
        "activation_reason",
        "reason",
        "full_statement_location",
        "statement",
        "text",
        "required",
        "full_statement_once",
    }
)
COUNTERVOICE_KEYS = frozenset(
    {
        "id",
        "countervoice_id",
        "source_ids",
        "claim_id",
        "claim_delta",
        "claim_effect",
        "manuscript_action",
        "action",
        "preferred_realization",
        "activation_reason",
        "reason",
        "position",
        "discriminating_evidence",
        "full_statement_location",
        "materiality",
        "same_result",
        "same_stage",
    }
)
CLARITY_LEDGER_KEYS = frozenset({"schema_version", "scope", "actions"})
CLARITY_ACTION_KEYS = frozenset(
    {
        "action",
        "prose_delta",
        "claim_id",
        "source_kind",
        "source_anchor",
        "reader_understanding",
        "no_new_fact",
        "no_new_citation",
        "no_inference_strengthening",
    }
)
IDENTITY_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:SRC|CR|SYN|PO|C|CLM|CLAIM|EVD|EV|MAT|DESIGN|DSG|EXE|ETH|RESP)"
    r"-[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9])",
    re.IGNORECASE,
)
BOUNDARY_ID_RE = re.compile(r"^B-[A-Za-z0-9][A-Za-z0-9._-]*$", re.IGNORECASE)
FORBIDDEN_ACTIVATION_RE = re.compile(
    r"(?:可能.{0,6}(?:误解|误读)|为了?(?:更加)?全面|审稿人.{0,8}(?:质疑|可能)|"
    r"保持谨慎|显得谨慎|might be misunderstood|to be comprehensive|reviewer may|"
    r"sound cautious)",
    re.IGNORECASE,
)
CONTROL_PLANE_LEAK_RE = re.compile(
    r"(?:avereth-prose-packet|\.avereth-prose|Materiality Compiler|"
    r"research_notes(?:\.md)?|workflow_status|gate_failures|reviewer_persona|reviewer_prompts|full_audit|"
    r"candidate_boundaries|candidate_countervoices|unactivated_objections|"
    r"审稿人可能|为(?:了)?避免(?:误解|误读)|为了?(?:更加)?全面|保持谨慎|"
    r"reviewer may|to be comprehensive)",
    re.IGNORECASE,
)
CONTROL_METADATA_KEY_RE = re.compile(
    r"(?:reviewer|comment|response|rebuttal|workflow|gate|audit|persona|prompt|control[_-]?plane|"
    r"审稿|评审意见|回复信|答辩|工作流|闸门|审计)",
    re.IGNORECASE,
)
PROCESS_LANGUAGE_RE = re.compile(
    r"(?:(?:the\s+)?(?:reviewer|referee|editor)\s+"
    r"(?:asked|requested|commented|suggested|recommended|required|advised|may)|"
    r"peer\s+review\s+(?:asked|requested|commented|suggested|recommended|required|advised)|"
    r"response\s+letter|comment[- ]by[- ]comment|"
    r"according\s+to\s+(?:the\s+)?(?:reviewer|referee|editor)|"
    r"根据(?:匿名)?(?:审稿|评审|评议)(?:人)?(?:意见|建议)|"
    r"(?:审稿|评审|评议)(?:人)?(?:要求|指出|认为|建议|意见|评语|可能)|"
    r"(?:按|根据)?第[一二三四五六七八九十0-9]+轮(?:审稿|评审|评议)?意见"
    r"(?:补充|修改|调整|回应|如下)|回应(?:审稿|评审|评议)|回复信|逐条回复)",
    re.IGNORECASE,
)
NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d+(?:[.,]\d+)*(?:%|％)?")
LATEX_CITATION_RE = re.compile(
    r"\\(?:(?:auto|paren|text|foot|smart|super|no|[apfst]?vol)?cite[a-zA-Z]*)"
    r"\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}",
    re.IGNORECASE,
)
PANDOC_CITATION_RE = re.compile(r"\[([^\]]*@[^\]]+)\]")
BARE_PANDOC_CITATION_RE = re.compile(r"(?<![\w:./@-])@([\w:./-]+)")
NUMERIC_BRACKET_CITATION_RE = re.compile(
    r"\[\s*\d+\s*(?:(?:[-–—,，;；]\s*)\d+\s*)*\]"
)
SQUARE_AUTHOR_YEAR_CITATION_RE = re.compile(
    r"\[[^\]\n]{1,80}(?:18|19|20)\d{2}[a-z]?[^\]\n]{0,40}\]",
    re.IGNORECASE,
)
DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
AUTHOR_YEAR_CITATION_RE = re.compile(
    r"[（(][^()（）\n]{1,80}(?:18|19|20)\d{2}[a-z]?[^()（）\n]{0,40}[)）]",
    re.IGNORECASE,
)
QUOTATION_RE = re.compile(r"[“「『\"‘]([^”」』\"’\n]{2,})[”」』\"’]")
MARKDOWN_BLOCKQUOTE_RE = re.compile(r"(?m)^\s{0,3}>\s*(\S.*)$")
CAUSAL_ASSERTION_RE = re.compile(
    r"(?:直接)?(?:导致|造成|引发|决定了?|产生(?:了)?[^。！？\n]{0,20}(?:效果|效应|后果)|"
    r"证明[^。！？\n]{0,20}(?:因果|导致)|"
    r"(?:directly\s+)?causes?\b|\bleads?\s+to\b|\bresults?\s+in\b)",
    re.IGNORECASE,
)
CAUSAL_NEGATION_PREFIX_RE = re.compile(
    r"(?:并?不|未|没有|不会|未必|不一定|不能|无法|未能|不足以|不支持|"
    r"尚不能|尚无法|难以|不可|does\s+not|do\s+not|did\s+not|cannot|"
    r"can't|could\s+not|may\s+not|is\s+not|are\s+not)"
    r"(?:\s|据此|由此|直接|必然|充分|明确|被|予以){0,4}$",
    re.IGNORECASE,
)
CAUSAL_DOUBLE_NEGATION_PREFIX_RE = re.compile(
    r"(?:不能不|不得不|不会不|不可能不|并非不会|未尝不|无不|"
    r"并非没有|不是没有|并非无|不是无|不能没有|不可没有|cannot\s+not)"
    r"(?:\s|据此|由此|直接|必然|充分|明确){0,4}$",
    re.IGNORECASE,
)
CAUSAL_NO_EVIDENCE_PREFIX_RE = re.compile(
    r"(?:尚?无|没有|缺乏|不存在)(?:现有|充分|可靠|有效|直接|足够)?"
    r"(?:证据|依据|材料|识别)"
    r"(?:(?!但|却|然而|反而|不过|可是|仍然?|依然)[^，,；;。！？.!?]){0,32}$"
)
CLAIM_LATENCY = {"abstract": 0, "results": 0, "conclusion": 0, "introduction": 1}
GENERIC_DELTA = {
    "",
    "none",
    "n/a",
    "na",
    "无",
    "不变",
    "更谨慎",
    "保持谨慎",
    "clarify",
    "be careful",
}
SUPPORT_FILES = (
    "reference_materials/literature_registry.json",
    "literature_analysis.json",
    "research_design.json",
    "method_execution.json",
)
FORBIDDEN_PACKET_KEYS = frozenset(
    {
        "workflow_status",
        "gate_failures",
        "reviewer_persona",
        "reviewer_prompts",
        "full_audit",
        "research_notes",
        "research_notes.md",
        "candidate_boundaries",
        "candidate_countervoices",
        "unactivated_objections",
        "evidence_bank",
        "citation_support_bank",
        "source_inventory",
        "exa_manifest",
        "exa_run",
        "zotero_snapshot",
        "zotero_library",
        "references_bib",
    }
)


class ProsePacketError(ValueError):
    """Raised when a requested packet crosses an identity or prose-firewall boundary."""


class CanonicalResultClaims(dict[str, frozenset[str]]):
    """Result/claim permissions carrying their canonical eligibility snapshot."""

    def __init__(
        self,
        values: Mapping[str, Iterable[str]] | None = None,
        *,
        authority: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            {
                _text(result_id).upper(): frozenset(
                    _text(claim_id).upper()
                    for claim_id in claim_ids
                    if _text(claim_id)
                )
                for result_id, claim_ids in (values or {}).items()
                if _text(result_id)
            }
        )
        self.authority = dict(authority or {})


@dataclass(frozen=True)
class ClarityValidationResult:
    """Deterministic result for one evidence-bounded clarity edit."""

    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    delta: int
    growth_ratio: float

    @property
    def ok(self) -> bool:
        return not self.issues


def _text(value: Any) -> str:
    return str(value or "").strip()


def _ensure_allowed_fields(
    record: dict[str, Any], allowed: frozenset[str], *, field: str
) -> None:
    unexpected = set(record) - allowed
    if unexpected:
        raise ProsePacketError(
            f"{field} crosses the prose firewall with unsupported fields: "
            + ", ".join(sorted(unexpected))
        )
    leaked_keys = [key for key in record if CONTROL_METADATA_KEY_RE.search(str(key))]
    if leaked_keys:
        raise ProsePacketError(
            f"{field} crosses the prose firewall with control-plane metadata: "
            + ", ".join(sorted(leaked_keys))
        )


def _reject_process_language(value: Any, *, field: str) -> None:
    """Reject reviewer-response process language from writer-visible packet content."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "schema_version":
                continue
            _reject_process_language(nested, field=f"{field}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value, start=1):
            _reject_process_language(nested, field=f"{field}[{index}]")
    elif isinstance(value, str) and (
        PROCESS_LANGUAGE_RE.search(value) or CONTROL_PLANE_LEAK_RE.search(value)
    ):
        raise ProsePacketError(
            f"{field} crosses the prose firewall with control-plane or reviewer-response language"
        )


def _string_list(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ProsePacketError(f"{field} must be an array")
    compiled: list[str] = []
    for index, item in enumerate(value, start=1):
        text = _text(item)
        if not text:
            raise ProsePacketError(f"{field}[{index}] cannot be empty")
        if text in compiled:
            raise ProsePacketError(f"{field} must not contain duplicates: {text}")
        compiled.append(text)
    if not allow_empty and not compiled:
        raise ProsePacketError(f"{field} must contain at least one item")
    return compiled


def _prefix(identity: str) -> str:
    return identity.split("-", 1)[0].upper() if "-" in identity else ""


def _substantive(value: Any, minimum: int = 4) -> bool:
    compact = re.sub(r"\s+", "", _text(value)).casefold()
    return len(compact) >= minimum and compact not in GENERIC_DELTA


_METHOD_EXECUTION_MODULE: Any | None = None


def _method_execution_module() -> Any:
    """Load the execution authority without creating a second eligibility validator."""
    global _METHOD_EXECUTION_MODULE
    if _METHOD_EXECUTION_MODULE is not None:
        return _METHOD_EXECUTION_MODULE
    path = (
        Path(__file__).resolve().parents[2]
        / "empirical-research"
        / "scripts"
        / "method_execution.py"
    )
    module_name = "avereth_method_execution_authority"
    if module_name in sys.modules:
        _METHOD_EXECUTION_MODULE = sys.modules[module_name]
        return _METHOD_EXECUTION_MODULE
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load execution authority from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _METHOD_EXECUTION_MODULE = module
    return module


def _design_execution_claim_ids(workspace: Path) -> set[str]:
    """Read the execution-governed claim universe from canonical design routes."""

    path = workspace / "research_design.json"
    if not path.is_file():
        return set()
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    return {
        _text(claim_id).upper()
        for route in payload.get("method_routes") or []
        if isinstance(route, dict) and bool(route.get("empirical"))
        for claim_id in route.get("claim_ids") or []
        if _text(claim_id)
    }


def discover_execution_authority(workspace: Path) -> dict[str, Any] | None:
    """Return one canonical execution projection, including blocked state."""

    path = workspace / "method_execution.json"
    if not path.is_file():
        return None
    try:
        projection = _method_execution_module().downstream_eligibility(workspace)
    except Exception as exc:
        projection = {
            "schema_version": "cnki-method-downstream-eligibility/v1",
            "status": "BLOCKED",
            "issues": [{"code": "ME.ELIGIBILITY.VALIDATOR_FAILURE", "message": str(exc)}],
            "results": {},
        }
    if not isinstance(projection, dict):
        projection = {"status": "BLOCKED", "issues": [], "results": {}}
    authority = dict(projection)
    authority["execution_claim_ids"] = sorted(
        {
            _text(value).upper()
            for value in authority.get("execution_claim_ids") or []
            if _text(value)
        }
        | _design_execution_claim_ids(workspace)
    )
    if not isinstance(authority.get("results"), dict):
        authority["results"] = {}
    return authority


def discover_downstream_result_eligibility(
    workspace: Path,
) -> dict[str, dict[str, Any]] | None:
    """Project prose eligibility from the canonical v3 execution validator.

    ``None`` means no execution authority exists.  Once ``method_execution.json``
    exists, every parse, schema, or semantic failure closes the result boundary and
    returns an empty mapping; manuscript compilation never falls back to regex IDs.
    """
    authority = discover_execution_authority(workspace)
    if authority is None:
        return None
    if _text(authority.get("status")).upper() != "PASS":
        return {}
    results = authority.get("results")
    if not isinstance(results, dict):
        return {}
    return {
        _text(result_id).upper(): dict(record)
        for result_id, record in results.items()
        if _text(result_id) and isinstance(record, dict)
    }


def discover_accepted_result_claims(
    workspace: Path,
    *,
    allowed_use: str = "claim_support",
) -> CanonicalResultClaims | None:
    """Return canonical result-to-claim bindings for one permitted prose use.

    Retained dispositions may support the registered claim.  Narrowed or withdrawn
    claims are available only for explicit negative/null reporting and never support
    the original proposition.
    """
    if allowed_use not in RESULT_USES:
        raise ValueError(f"unsupported result use: {allowed_use}")
    authority = discover_execution_authority(workspace)
    if authority is None:
        return None
    projection = (
        authority.get("results")
        if _text(authority.get("status")).upper() == "PASS"
        and isinstance(authority.get("results"), dict)
        else {}
    )
    eligible: dict[str, frozenset[str]] = {}
    for result_id, record in projection.items():
        allowed_uses = {
            _text(item).lower() for item in record.get("allowed_uses") or [] if _text(item)
        }
        if allowed_use not in allowed_uses:
            continue
        claim_allowed_uses = record.get("claim_allowed_uses")
        if not isinstance(claim_allowed_uses, dict):
            continue
        claim_ids = {
            _text(claim_id).upper()
            for claim_id, uses in claim_allowed_uses.items()
            if _text(claim_id)
            and isinstance(uses, list)
            and allowed_use
            in {_text(use).lower() for use in uses if _text(use)}
        }
        if claim_ids:
            eligible[result_id] = frozenset(claim_ids)
    return CanonicalResultClaims(eligible, authority=authority)


def _canonical_result_authority_snapshot(
    accepted_result_claims: Mapping[str, Iterable[str]] | None,
    *,
    claim_id: str,
    result_ids: Iterable[str],
    result_use: str,
    section_role: str,
) -> dict[str, Any]:
    """Select the exact canonical result authority consumed by one packet.

    The snapshot deliberately excludes the whole execution/projection digest: an
    unrelated result may change without invalidating a packet that does not use it.
    The selected result records already bind their current attempts, artifacts,
    hashes, checks, MVMR status, dispositions, numeric locators, and allowed uses.
    """

    selected_ids = tuple(_text(value).upper() for value in result_ids if _text(value))
    if not isinstance(accepted_result_claims, CanonicalResultClaims):
        if selected_ids:
            raise ProsePacketError(
                "result_ids require canonical execution authority, not a caller-built result map"
            )
        return {}

    authority = accepted_result_claims.authority
    if not isinstance(authority, dict) or not authority:
        if selected_ids:
            raise ProsePacketError("result_ids require a non-empty canonical execution authority")
        return {}

    execution_claim_ids = {
        _text(value).upper()
        for value in authority.get("execution_claim_ids") or []
        if _text(value)
    }
    prospective_claim_ids = {
        _text(value).upper()
        for value in authority.get("prospective_claim_ids") or []
        if _text(value)
    }
    execution_claim = claim_id in execution_claim_ids
    prospective_exception = (
        section_role == "prospective_hypothesis" and claim_id in prospective_claim_ids
    )
    status = _text(authority.get("status")).upper()

    if execution_claim:
        if section_role not in EXECUTION_CLAIM_SECTION_ROLES and not prospective_exception:
            raise ProsePacketError(
                f"unsupported section_role for an execution-governed claim: {section_role}"
            )
        if status != "PASS":
            raise ProsePacketError(
                "execution-governed claims cannot enter prose while canonical execution eligibility is blocked"
            )
        if not selected_ids and not prospective_exception:
            raise ProsePacketError(
                f"{section_role} packets for execution-governed claim {claim_id} require an eligible result_id"
            )

    if not selected_ids:
        if not prospective_exception:
            return {}
        return {
            "schema_version": _text(authority.get("schema_version")),
            "design_sha256": _text(authority.get("design_sha256")),
            "adapter_registry_sha256": _text(authority.get("adapter_registry_sha256")),
            "claim_id": claim_id,
            "result_use": result_use,
            "prospective": True,
            "results": {},
        }

    if status != "PASS":
        raise ProsePacketError("result_ids cannot enter prose from a blocked execution projection")
    results = authority.get("results")
    if not isinstance(results, dict):
        raise ProsePacketError("canonical execution authority has no result projection")

    selected: dict[str, Any] = {}
    for result_id in selected_ids:
        record = results.get(result_id)
        if not isinstance(record, Mapping):
            raise ProsePacketError(f"canonical execution authority has no result record: {result_id}")
        allowed_uses = {
            _text(value).lower() for value in record.get("allowed_uses") or [] if _text(value)
        }
        claim_allowed = record.get("claim_allowed_uses")
        claim_uses = (
            {
                _text(value).lower()
                for value in claim_allowed.get(claim_id) or []
                if _text(value)
            }
            if isinstance(claim_allowed, Mapping)
            else set()
        )
        if result_use not in allowed_uses or result_use not in claim_uses:
            raise ProsePacketError(
                f"result {result_id} is not canonically eligible for {result_use} and claim {claim_id}"
            )
        selected[result_id] = json.loads(
            json.dumps(record, ensure_ascii=False, sort_keys=True)
        )

    return {
        "schema_version": _text(authority.get("schema_version")),
        "design_sha256": _text(authority.get("design_sha256")),
        "adapter_registry_sha256": _text(authority.get("adapter_registry_sha256")),
        "claim_id": claim_id,
        "result_use": result_use,
        "results": selected,
    }


def _packet_source_digest(
    packet: Mapping[str, Any], authority_snapshot: Mapping[str, Any]
) -> str:
    canonical = {
        "packet": {key: value for key, value in packet.items() if key != "source_digest"},
        "canonical_result_authority": dict(authority_snapshot),
    }
    payload = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _result_claims_for_payload(
    workspace: Path, payload: Any
) -> CanonicalResultClaims | None:
    result_use = "claim_support"
    if isinstance(payload, dict):
        candidate = _text(payload.get("result_use")).lower()
        if candidate in RESULT_USES:
            result_use = candidate
    return discover_accepted_result_claims(workspace, allowed_use=result_use)


def discover_verified_context_anchors(workspace: Path) -> dict[str, dict[str, Any]]:
    """Read valid Context Anchors from the evidence-bank projection."""

    path = workspace / "evidence_bank.md"
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return {}

    def cells(line: str) -> list[str]:
        return [
            item.replace(r"\|", "|").strip()
            for item in re.split(r"(?<!\\)\|", line.strip().strip("|"))
        ]

    def header_key(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", value.lower())

    for index, line in enumerate(lines[:-1]):
        separator = cells(lines[index + 1])
        if (
            not line.lstrip().startswith("|")
            or not separator
            or not all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in separator)
        ):
            continue
        headers = [header_key(value) for value in cells(line)]
        positions: dict[str, int] = {}
        for field, aliases in CONTEXT_ANCHOR_BANK_COLUMNS.items():
            position = next((number for number, value in enumerate(headers) if value in aliases), None)
            if position is None:
                break
            positions[field] = position
        if len(positions) != len(CONTEXT_ANCHOR_BANK_COLUMNS):
            continue
        anchors: dict[str, dict[str, Any]] = {}
        duplicates: set[str] = set()
        for row_line in lines[index + 2 :]:
            if not row_line.lstrip().startswith("|"):
                break
            row = cells(row_line)
            if max(positions.values()) >= len(row):
                continue
            values = {field: _text(row[position]) for field, position in positions.items()}
            anchor_id = values["anchor_id"].upper()
            anchor_type = values["type"].lower()
            if (
                not re.fullmatch(r"ANCHOR-[A-Z0-9][A-Z0-9._-]*", anchor_id)
                or anchor_type not in CONTEXT_ANCHOR_TYPES
                or values["status"].lower() != "content-verified"
                or any(not values[field] for field in CONTEXT_ANCHOR_BANK_COLUMNS)
            ):
                continue
            if anchor_id in anchors or anchor_id in duplicates:
                anchors.pop(anchor_id, None)
                duplicates.add(anchor_id)
            else:
                anchors[anchor_id] = values
        return anchors
    return {}


def validate_workspace_context_anchors(workspace: Path, payload: Any) -> None:
    """Bind every packet/request Context Anchor to its current evidence-bank row."""

    if not isinstance(payload, dict):
        return
    evidence_items = payload.get("evidence_items")
    if not isinstance(evidence_items, list):
        return
    anchors = discover_verified_context_anchors(workspace)

    def compact(value: Any) -> str:
        return " ".join(_text(value).split())

    def list_values(value: Any) -> list[str]:
        if isinstance(value, list):
            return [compact(item) for item in value if compact(item)]
        text = compact(value)
        if text.lower() in {"none", "n/a", "not-applicable", "无", "不适用"}:
            return []
        return [compact(item) for item in re.split(r"[;；,，]", text) if compact(item)]

    for index, item in enumerate(evidence_items, start=1):
        if not isinstance(item, dict) or item.get("context_anchor") is None:
            continue
        anchor = item.get("context_anchor")
        if not isinstance(anchor, dict):
            raise ProsePacketError(f"evidence_items[{index}].context_anchor must be an object")
        anchor_id = _text(anchor.get("anchor_id")).upper()
        anchor_type = _text(anchor.get("type")).lower()
        code = (
            "AP.QUOTE.CONTEXT_MISSING"
            if anchor_type in {"quotation", "definition"}
            else "AP.SCENE.UNBOUND"
        )
        registered = anchors.get(anchor_id)
        if registered is None or registered["type"].lower() != anchor_type:
            raise ProsePacketError(
                f"{code}: evidence_items[{index}] Context Anchor is absent from the content-verified evidence-bank projection"
            )
        expected = {
            "authority_ref": compact(anchor.get("authority_ref")).upper(),
            "locator": compact(anchor.get("locator")),
            "original_problem": compact(anchor.get("original_problem")),
            "logical_context": compact(anchor.get("logical_context")),
            "manuscript_function": compact(anchor.get("manuscript_function")),
        }
        actual = {
            field: compact(registered[field]).upper() if field == "authority_ref" else compact(registered[field])
            for field in expected
        }
        if actual != expected:
            raise ProsePacketError(
                f"{code}: evidence_items[{index}] Context Anchor drifts from its evidence-bank projection"
            )
        if list_values(anchor.get("protected_qualifiers")) != list_values(
            registered["protected_qualifiers"]
        ):
            raise ProsePacketError(
                f"AP.QUOTE.QUALIFIER_LOSS: evidence_items[{index}] Context Anchor qualifier set drifts from its evidence-bank projection"
            )
        content = compact(registered["content"])
        if anchor_type in {"quotation", "definition"}:
            content_matches = compact(anchor.get("exact_span")) == content
        else:
            content_matches = list_values(anchor.get("known_details")) == list_values(content)
        if not content_matches:
            raise ProsePacketError(
                f"{code}: evidence_items[{index}] Context Anchor content drifts from its evidence-bank projection"
            )


def discover_registered_ids(workspace: Path) -> frozenset[str]:
    """Read identities only from existing source/design/execution/build authorities.

    A v3 execution contract registers ``RES-*`` identities only after every bound
    action is accepted and every diagnostic passes.  Failed, unchecked, or orphaned
    results therefore cannot cross the build boundary merely because their text is
    present in ``method_execution.json``.
    """
    identities: set[str] = set()
    accepted_results = discover_accepted_result_claims(workspace)
    reportable_results = discover_accepted_result_claims(
        workspace, allowed_use="negative_or_null_report"
    )
    for relative in SUPPORT_FILES:
        path = workspace / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
        discovered = {match.group(0).upper() for match in IDENTITY_RE.finditer(text)}
        if relative == "method_execution.json":
            authority_status = (
                _text(accepted_results.authority.get("status")).upper()
                if isinstance(accepted_results, CanonicalResultClaims)
                else ""
            )
            if authority_status != "PASS":
                discovered = set()
            else:
                discovered = {
                    item for item in discovered if _prefix(item) not in RESULT_PREFIXES
                }
                discovered.update(accepted_results)
                discovered.update(reportable_results or {})
        identities.update(discovered)
    return frozenset(identities)


def identity_is_registered(identity: Any, registered_ids: Iterable[str]) -> bool:
    wanted = _text(identity).upper()
    return bool(wanted) and wanted in {item.upper() for item in registered_ids}


def _require_registered(
    identity: Any,
    registered_ids: frozenset[str],
    *,
    allowed_prefixes: frozenset[str],
    field: str,
) -> str:
    value = _text(identity).upper()
    if not value or _prefix(value) not in allowed_prefixes:
        raise ProsePacketError(f"{field} has an unsupported identity: {value or '<missing>'}")
    if value not in registered_ids:
        raise ProsePacketError(f"{field} is not registered in an authoritative workspace artifact: {value}")
    return value


def _activation_reason(record: dict[str, Any], *, field: str) -> str:
    reason = _text(record.get("activation_reason") or record.get("reason"))
    if not _substantive(reason, 6):
        raise ProsePacketError(f"{field}.activation_reason must state a material claim consequence")
    if FORBIDDEN_ACTIVATION_RE.search(reason):
        raise ProsePacketError(
            f"{field}.activation_reason relies on an imagined objection or generic caution"
        )
    return reason


def _claim_delta(record: dict[str, Any], *, field: str) -> str:
    if record.get("claim_delta") is not None and record.get("claim_effect") is not None and _text(
        record.get("claim_delta")
    ) != _text(record.get("claim_effect")):
        raise ProsePacketError(f"{field}.claim_delta and .claim_effect disagree")
    delta = _text(record.get("claim_delta") or record.get("claim_effect"))
    if not _substantive(delta, 5):
        raise ProsePacketError(f"{field}.claim_delta must name how the claim changes")
    return delta


def _strength_class(value: str) -> str:
    normalized = re.sub(r"[^a-z\u4e00-\u9fff]+", "", value.casefold())
    aliases = {
        "association": "association",
        "associational": "association",
        "相关": "association",
        "correlation": "association",
        "causal": "causal",
        "causality": "causal",
        "因果": "causal",
        "mechanism": "mechanism",
        "mechanistic": "mechanism",
        "机制": "mechanism",
        "descriptive": "descriptive",
        "description": "descriptive",
        "描述": "descriptive",
        "normative": "normative",
        "规范": "normative",
    }
    return aliases.get(normalized, normalized)


def _compile_claim(
    record: Any,
    *,
    registered_ids: frozenset[str],
    citation_anchors: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ProsePacketError("claim must be an object")
    _ensure_allowed_fields(record, CLAIM_KEYS, field="claim")
    claim_id = _require_registered(
        record.get("id"), registered_ids, allowed_prefixes=CLAIM_PREFIXES, field="claim.id"
    )
    proposition = _text(record.get("canonical_proposition") or record.get("text"))
    strength = _text(record.get("strength"))
    if not _substantive(proposition, 5) or not _substantive(strength, 3):
        raise ProsePacketError("claim text/canonical_proposition and strength must be substantive")

    supplied_mode = _text(record.get("realization_mode")).lower()
    mode = supplied_mode or "legacy_exact"
    if mode not in REALIZATION_MODES:
        raise ProsePacketError(
            f"claim.realization_mode must be one of {sorted(REALIZATION_MODES)}"
        )
    if mode == "legacy_exact" and supplied_mode:
        raise ProsePacketError(
            "claim.realization_mode=legacy_exact is reserved for requests that omit realization_mode"
        )

    compiled: dict[str, Any] = {
        "id": claim_id,
        "text": proposition,
        "canonical_proposition": proposition,
        "strength": strength,
        "realization_mode": mode,
    }
    if mode == "semantic":
        atoms = record.get("protected_atoms")
        if not isinstance(atoms, dict):
            raise ProsePacketError("semantic claim.protected_atoms must be an object")
        _ensure_allowed_fields(atoms, PROTECTED_ATOM_KEYS, field="claim.protected_atoms")
        missing = PROTECTED_ATOM_KEYS - set(atoms)
        if missing:
            raise ProsePacketError(
                "semantic claim.protected_atoms is missing: " + ", ".join(sorted(missing))
            )
        subject = _text(atoms.get("subject"))
        relation = _text(atoms.get("relation"))
        direction = _text(atoms.get("direction"))
        raw_polarity = _text(atoms.get("polarity")).lower()
        polarity = POLARITY_ALIASES.get(raw_polarity, "")
        inferential_strength = _text(atoms.get("inferential_strength")).lower()
        scope = _text(atoms.get("scope"))
        if not _substantive(subject, 2) or not _substantive(relation, 2):
            raise ProsePacketError("protected subject and relation must be substantive")
        if not _substantive(direction, 2):
            raise ProsePacketError("claim.protected_atoms.direction must be substantive")
        if not polarity:
            raise ProsePacketError(
                "claim.protected_atoms.polarity must be affirmative, negative, or mixed"
            )
        if not _substantive(inferential_strength, 3):
            raise ProsePacketError("claim.protected_atoms.inferential_strength must be substantive")
        if _strength_class(inferential_strength) != _strength_class(strength):
            raise ProsePacketError(
                "claim strength and protected inferential_strength must match"
            )
        if not _substantive(scope, 3) or scope.casefold() in {
            "all",
            "universal",
            "unbounded",
            "any",
            "全部",
            "所有",
            "无限",
        }:
            raise ProsePacketError("claim.protected_atoms.scope must state a bounded scope")
        literals = _string_list(
            atoms.get("protected_literals"), field="claim.protected_atoms.protected_literals"
        )
        numbers = _string_list(
            atoms.get("protected_numbers"), field="claim.protected_atoms.protected_numbers"
        )
        for number in numbers:
            if not NUMBER_RE.fullmatch(number):
                raise ProsePacketError(
                    f"claim.protected_atoms.protected_numbers contains an invalid number: {number}"
                )
        citations = _string_list(
            atoms.get("citation_anchors"), field="claim.protected_atoms.citation_anchors"
        )
        unregistered_citations = [
            citation for citation in citations if citation.casefold() not in citation_anchors
        ]
        if unregistered_citations:
            raise ProsePacketError(
                "claim.protected_atoms.citation_anchors are not registered by selected evidence: "
                + ", ".join(unregistered_citations)
            )
        compiled["protected_atoms"] = {
            "subject": subject,
            "relation": relation,
            "direction": direction,
            "polarity": polarity,
            "inferential_strength": inferential_strength,
            "scope": scope,
            "protected_literals": literals,
            "protected_numbers": numbers,
            "citation_anchors": citations,
        }
    elif mode == "verbatim":
        if record.get("protected_atoms") is not None:
            raise ProsePacketError("verbatim claims must not substitute protected_atoms for exact text")
        reason = _text(record.get("verbatim_reason")).lower()
        if reason not in VERBATIM_REASONS:
            raise ProsePacketError(
                f"claim.verbatim_reason must be one of {sorted(VERBATIM_REASONS)}"
            )
        compiled["verbatim_reason"] = reason
    elif record.get("protected_atoms") is not None or record.get("verbatim_reason") is not None:
        raise ProsePacketError(
            "legacy requests must omit protected_atoms and verbatim_reason or declare an explicit mode"
        )
    return compiled


def _compile_explanation_path(
    records: Any,
    *,
    registered_ids: frozenset[str],
    required: bool,
) -> list[dict[str, Any]]:
    if records is None and not required:
        return []
    if not isinstance(records, list) or not records:
        raise ProsePacketError("explanation_path must be a non-empty ordered array")
    compiled: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        field = f"explanation_path[{index}]"
        if not isinstance(record, dict):
            raise ProsePacketError(f"{field} must be an object")
        _ensure_allowed_fields(record, EXPLANATION_STEP_KEYS, field=field)
        if record.get("step") is not None and record.get("order") is not None and record.get(
            "step"
        ) != record.get("order"):
            raise ProsePacketError(f"{field}.step and .order disagree")
        step_number = record.get("step") if record.get("step") is not None else record.get("order")
        if (
            not isinstance(step_number, int)
            or isinstance(step_number, bool)
            or step_number != index
        ):
            raise ProsePacketError(
                f"{field}.step must be the consecutive one-based value {index}"
            )
        function = _text(record.get("function")).lower()
        if function not in EXPLANATION_FUNCTIONS:
            raise ProsePacketError(
                f"{field}.function must be one of {sorted(EXPLANATION_FUNCTIONS)}"
            )
        content = _text(record.get("content"))
        if not _substantive(content, 5):
            raise ProsePacketError(f"{field}.content must be substantive")
        step: dict[str, Any] = {
            "step": step_number,
            "function": function,
            "content": content,
        }
        if record.get("anchor_id") is not None:
            step["anchor_id"] = _require_registered(
                record.get("anchor_id"),
                registered_ids,
                allowed_prefixes=frozenset().union(*ANCHOR_PREFIXES.values(), CLAIM_PREFIXES),
                field=f"{field}.anchor_id",
            )
        compiled.append(step)
    functions = {step["function"] for step in compiled}
    if required and not functions.intersection({"evidence", "evidence_role", "compare"}):
        raise ProsePacketError("semantic explanation_path must contain an evidence-role step")
    if required and not functions.intersection(
        {"mechanism", "process", "warrant", "causal_step"}
    ):
        raise ProsePacketError("semantic explanation_path must contain a mechanism/process/warrant step")
    return compiled


def _compile_rhetorical_task(value: Any) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ProsePacketError("rhetorical_task must be an object")
    _ensure_allowed_fields(value, RHETORICAL_TASK_KEYS, field="rhetorical_task")
    missing = RHETORICAL_TASK_KEYS - set(value)
    if missing:
        raise ProsePacketError(
            "rhetorical_task is missing: " + ", ".join(sorted(missing))
        )
    action = _text(value.get("argument_action")).upper()
    before = _text(value.get("problem_state_before"))
    after = _text(value.get("problem_state_after"))
    if action not in ARGUMENT_ACTIONS:
        raise ProsePacketError("AP.MOTION.ACTION_INVALID: unsupported rhetorical_task.argument_action")
    if not _substantive(before, 5) or not _substantive(after, 5):
        raise ProsePacketError("AP.MOTION.STATE_INCOMPLETE: rhetorical_task states must be substantive")
    if before == after:
        raise ProsePacketError("AP.MOTION.NO_ADVANCE: rhetorical_task must change the problem state")
    return {
        "argument_action": action,
        "problem_state_before": before,
        "problem_state_after": after,
    }


def _compile_context_anchor(
    value: Any,
    *,
    evidence_text: str,
    registered_ids: frozenset[str],
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProsePacketError(f"{field} must be an object")
    _ensure_allowed_fields(value, CONTEXT_ANCHOR_KEYS, field=field)
    required = {
        "anchor_id",
        "authority_ref",
        "type",
        "locator",
        "original_problem",
        "logical_context",
        "protected_qualifiers",
        "manuscript_function",
        "status",
    }
    missing = required - set(value)
    if missing:
        raise ProsePacketError(f"{field} is missing: " + ", ".join(sorted(missing)))
    anchor_id = _text(value.get("anchor_id")).upper()
    if not re.fullmatch(r"ANCHOR-[A-Z0-9][A-Z0-9._-]*", anchor_id):
        raise ProsePacketError(f"{field}.anchor_id must use a stable ANCHOR-* identity")
    authority_ref = _require_registered(
        value.get("authority_ref"),
        registered_ids,
        allowed_prefixes=EVIDENCE_PREFIXES,
        field=f"{field}.authority_ref",
    )
    anchor_type = _text(value.get("type")).lower()
    if anchor_type not in CONTEXT_ANCHOR_TYPES:
        raise ProsePacketError(f"{field}.type must be one of {sorted(CONTEXT_ANCHOR_TYPES)}")
    locator = _text(value.get("locator"))
    if not locator:
        code = "AP.QUOTE.LOCATOR_MISSING" if anchor_type == "quotation" else "AP.SCENE.UNBOUND"
        raise ProsePacketError(f"{code}: {field}.locator is required")
    status = _text(value.get("status")).lower()
    if status != "content-verified":
        raise ProsePacketError(f"{field}.status must be content-verified")
    original_problem = _text(value.get("original_problem"))
    logical_context = _text(value.get("logical_context"))
    manuscript_function = _text(value.get("manuscript_function"))
    if not all(
        _substantive(item, 5)
        for item in (original_problem, logical_context, manuscript_function)
    ):
        raise ProsePacketError(f"{field} must preserve the original problem, logic, and manuscript function")
    qualifiers = _string_list(
        value.get("protected_qualifiers"),
        field=f"{field}.protected_qualifiers",
    )
    exact_span = _text(value.get("exact_span"))
    known_details = _string_list(
        value.get("known_details", []),
        field=f"{field}.known_details",
    )
    if anchor_type in {"quotation", "definition"}:
        if not exact_span:
            raise ProsePacketError(f"AP.QUOTE.CONTEXT_MISSING: {field}.exact_span is required")
        if exact_span not in evidence_text:
            raise ProsePacketError(f"AP.QUOTE.CONTEXT_MISSING: {field}.exact_span is not present in selected evidence")
    if anchor_type in {"scene", "case"} and not known_details:
        raise ProsePacketError(f"AP.SCENE.UNBOUND: {field}.known_details must not be empty")
    compiled: dict[str, Any] = {
        "anchor_id": anchor_id,
        "authority_ref": authority_ref,
        "type": anchor_type,
        "locator": locator,
        "original_problem": original_problem,
        "logical_context": logical_context,
        "protected_qualifiers": qualifiers,
        "manuscript_function": manuscript_function,
        "status": status,
    }
    if exact_span:
        compiled["exact_span"] = exact_span
    if known_details:
        compiled["known_details"] = known_details
    return compiled


def _compile_evidence_items(
    records: Any, *, registered_ids: frozenset[str], require_function: bool = False
) -> list[dict[str, Any]]:
    """Keep only selected, identity-bound evidence propositions needed for this unit."""
    if not isinstance(records, list) or not records:
        raise ProsePacketError("evidence_items must be a non-empty array")
    compiled: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        field = f"evidence_items[{index}]"
        if not isinstance(record, dict):
            raise ProsePacketError(f"{field} must be an object")
        _ensure_allowed_fields(record, EVIDENCE_ITEM_KEYS, field=field)
        evidence_id = _require_registered(
            record.get("id"),
            registered_ids,
            allowed_prefixes=EVIDENCE_PREFIXES,
            field=f"{field}.id",
        )
        if evidence_id in seen_ids:
            raise ProsePacketError("evidence_items must use unique registered IDs")
        seen_ids.add(evidence_id)
        evidence_text = _text(record.get("text"))
        if not _substantive(evidence_text, 6):
            raise ProsePacketError(
                f"{field}.text must contain the selected evidence proposition, value, or quotation"
            )
        item = {"id": evidence_id, "text": evidence_text}
        for optional in ("locator", "citation_key"):
            if optional not in record:
                continue
            value = _text(record.get(optional))
            if not value:
                raise ProsePacketError(f"{field}.{optional} cannot be empty when supplied")
            item[optional] = value
        evidence_function = _text(record.get("evidence_function"))
        if require_function and not _substantive(evidence_function, 3):
            raise ProsePacketError(f"{field}.evidence_function is required for semantic claims")
        if evidence_function:
            if PROCESS_LANGUAGE_RE.search(evidence_function):
                raise ProsePacketError(
                    f"{field}.evidence_function crosses the prose firewall with process language"
                )
            item["evidence_function"] = evidence_function
        elif not require_function:
            item["evidence_function"] = "supports_claim"
        context_anchor = record.get("context_anchor")
        contains_direct_quote = bool(
            QUOTATION_RE.search(evidence_text) or MARKDOWN_BLOCKQUOTE_RE.search(evidence_text)
        )
        if contains_direct_quote and context_anchor is None:
            raise ProsePacketError(
                f"AP.QUOTE.CONTEXT_MISSING: {field} contains a direct quotation without a Context Anchor"
            )
        if context_anchor is not None:
            item["context_anchor"] = _compile_context_anchor(
                context_anchor,
                evidence_text=evidence_text,
                registered_ids=registered_ids,
                field=f"{field}.context_anchor",
            )
        compiled.append(item)
    return compiled


def compile_clarity_growth_soft_limits(value: Any = None) -> dict[str, float]:
    """Validate configurable re-read thresholds without turning them into gates."""
    if value is None:
        return dict(DEFAULT_CLARITY_GROWTH_SOFT_LIMITS)
    if not isinstance(value, dict):
        raise ProsePacketError("clarity_growth_soft_limits must be an object")
    _ensure_allowed_fields(
        value,
        CLARITY_GROWTH_SOFT_LIMIT_KEYS,
        field="clarity_growth_soft_limits",
    )
    missing = CLARITY_GROWTH_SOFT_LIMIT_KEYS - set(value)
    if missing:
        raise ProsePacketError(
            "clarity_growth_soft_limits is missing required fields: "
            + ", ".join(sorted(missing))
        )
    compiled: dict[str, float] = {}
    for key in sorted(CLARITY_GROWTH_SOFT_LIMIT_KEYS):
        ratio = value.get(key)
        if (
            not isinstance(ratio, (int, float))
            or isinstance(ratio, bool)
            or not math.isfinite(ratio)
            or ratio <= 0
        ):
            raise ProsePacketError(
                f"clarity_growth_soft_limits.{key} must be a finite positive ratio"
            )
        compiled[key] = float(ratio)
    if compiled["section_ratio"] > compiled["paragraph_ratio"]:
        raise ProsePacketError(
            "clarity_growth_soft_limits.section_ratio cannot exceed paragraph_ratio"
        )
    return compiled


def clarity_growth_soft_limits_from_budget(budget: Any) -> dict[str, float]:
    if not isinstance(budget, dict):
        raise ProsePacketError("expression_budget must be an object")
    growth = budget.get("clarity_growth")
    if not isinstance(growth, dict):
        raise ProsePacketError("expression_budget.clarity_growth must be an object")
    return compile_clarity_growth_soft_limits(
        {
            "section_ratio": growth.get("section_soft_ratio"),
            "paragraph_ratio": growth.get("paragraph_soft_ratio"),
        }
    )


def canonical_expression_budget(
    section_role: str,
    realization_mode: str = "semantic",
    clarity_growth_soft_limits: Any = None,
    *,
    _legacy_surface_order: bool = False,
) -> dict[str, Any]:
    """Canonical budget; the private flag reconstructs historical v2 packets.

    New explicit modes organize text by argument function. Missing-mode legacy
    requests retain their old contract; validation never accepts a caller's
    arbitrary budget as authority for relaxing protected facts or boundaries.
    """
    exact_required = realization_mode in {"verbatim", "legacy_exact"}
    functional_order = realization_mode != "legacy_exact" and not _legacy_surface_order
    soft_limits = compile_clarity_growth_soft_limits(clarity_growth_soft_limits)
    budget = {
        "claim_latency": {
            "max_sentences_before_claim": None if functional_order else CLAIM_LATENCY.get(section_role),
            "exact_claim_text_required": exact_required,
        },
        "semantic_fidelity_gate_required": realization_mode == "semantic",
        "untriggered_objection_sentences": 0,
        "boundary_before_main_claim": None if functional_order else 0,
        "full_boundary_occurrences_per_id": 1,
        "clarity_growth": {
            "positive_growth_actions": ["BRIDGE", "DEFINE"],
            "section_soft_ratio": soft_limits["section_ratio"],
            "paragraph_soft_ratio": soft_limits["paragraph_ratio"],
            "requires": [
                "claim_id",
                "source_kind",
                "source_anchor",
                "reader_understanding",
                "no_new_fact",
                "no_new_citation",
                "no_inference_strengthening",
            ],
        },
    }
    if functional_order:
        budget["surface_order_policy"] = "argument_function"
    return budget


def legacy_expression_budget(section_role: str) -> dict[str, Any]:
    """Canonical v1 budget accepted only for reading old transient packets."""
    return {
        "writing_only_revision_net_growth": 0,
        "claim_latency": {
            "max_sentences_before_claim": CLAIM_LATENCY.get(section_role),
            "exact_claim_text_required": True,
        },
        "untriggered_objection_sentences": 0,
        "boundary_before_main_claim": 0,
        "full_boundary_occurrences_per_id": 1,
        "add_requires": ["claim_id", "evidence_or_design_anchor", "reader_update"],
    }


def _compile_boundary(
    record: Any,
    *,
    claim_id: str,
    registered_ids: frozenset[str],
    field: str,
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        raise ProsePacketError(f"{field} must be an object")
    _ensure_allowed_fields(record, BOUNDARY_KEYS, field=field)
    boundary_id = _text(record.get("boundary_id") or record.get("id")).upper()
    if not BOUNDARY_ID_RE.fullmatch(boundary_id):
        raise ProsePacketError(f"{field}.boundary_id must use a stable B-* identity")
    raw_action = _text(
        record.get("preferred_realization")
        or record.get("manuscript_action")
        or record.get("action")
    ).lower()
    if raw_action not in MANUSCRIPT_ACTIONS:
        raise ProsePacketError(
            f"{field}.preferred_realization must be one of {sorted(MANUSCRIPT_ACTIONS)}"
        )
    action = LEGACY_ACTION_MAP.get(raw_action, raw_action)
    if action == "omit":
        return None
    if record.get("required") is not None and record.get("required") is not True:
        raise ProsePacketError(f"{field}.required must be true for an activated boundary")
    if _text(record.get("materiality")).lower() != "load_bearing":
        raise ProsePacketError(f"{field} cannot enter prose without materiality=load_bearing")
    boundary_claim_id = _require_registered(
        record.get("claim_id"),
        registered_ids,
        allowed_prefixes=CLAIM_PREFIXES,
        field=f"{field}.claim_id",
    )
    if boundary_claim_id != claim_id:
        raise ProsePacketError(f"{field}.claim_id does not match the packet claim")
    anchor_type = _text(record.get("anchor_type")).lower()
    if anchor_type not in ANCHOR_PREFIXES:
        raise ProsePacketError(f"{field}.anchor_type is unsupported: {anchor_type or '<missing>'}")
    anchor_id = _require_registered(
        record.get("anchor_id"),
        registered_ids,
        allowed_prefixes=ANCHOR_PREFIXES[anchor_type],
        field=f"{field}.anchor_id",
    )
    location = _text(record.get("full_statement_location"))
    if action in {"single_full_statement", "footnote_or_cross_reference"} and not _substantive(location, 4):
        raise ProsePacketError(f"{field}.full_statement_location is required for {action}")
    claim_effect = _claim_delta(record, field=field)
    compiled = {
        "id": boundary_id,
        "anchor_type": anchor_type,
        "anchor_id": anchor_id,
        "claim_id": boundary_claim_id,
        "claim_delta": claim_effect,
        "claim_effect": claim_effect,
        "action": action,
        "preferred_realization": action,
        "required": True,
        "activation_reason": _activation_reason(record, field=field),
    }
    if location:
        compiled["full_statement_location"] = location
    statement = _text(record.get("statement") or record.get("text"))
    full_statement_once = action in {
        "positive_scope",
        "single_full_statement",
        "footnote_or_cross_reference",
    }
    if record.get("full_statement_once") is not None and record.get(
        "full_statement_once"
    ) is not full_statement_once:
        raise ProsePacketError(
            f"{field}.full_statement_once conflicts with preferred_realization"
        )
    compiled["full_statement_once"] = full_statement_once
    if full_statement_once and not _substantive(statement, 5):
        raise ProsePacketError(f"{field}.statement is required for {action}")
    if statement:
        compiled["statement"] = statement
    return compiled


def _compile_countervoice(
    record: Any,
    *,
    claim_id: str,
    registered_ids: frozenset[str],
    field: str,
) -> dict[str, Any] | None:
    if not isinstance(record, dict):
        raise ProsePacketError(f"{field} must be an object")
    _ensure_allowed_fields(record, COUNTERVOICE_KEYS, field=field)
    raw_action = _text(
        record.get("preferred_realization")
        or record.get("manuscript_action")
        or record.get("action")
    ).lower()
    action = LEGACY_ACTION_MAP.get(raw_action, raw_action)
    if action == "omit":
        return None
    if action not in ACTIVE_ACTIONS:
        raise ProsePacketError(f"{field}.manuscript_action is unsupported")
    if record.get("same_result") is not True or record.get("same_stage") is not True:
        raise ProsePacketError(f"{field} must address the same result and same stage")
    if _text(record.get("materiality")).lower() != "load_bearing":
        raise ProsePacketError(f"{field} cannot enter prose without materiality=load_bearing")
    linked_claim = _require_registered(
        record.get("claim_id"),
        registered_ids,
        allowed_prefixes=CLAIM_PREFIXES,
        field=f"{field}.claim_id",
    )
    if linked_claim != claim_id:
        raise ProsePacketError(f"{field}.claim_id does not match the packet claim")
    source_ids = record.get("source_ids")
    if not isinstance(source_ids, list) or not source_ids:
        raise ProsePacketError(f"{field}.source_ids must identify at least one registered source")
    sources = [
        _require_registered(
            source_id,
            registered_ids,
            allowed_prefixes=ANCHOR_PREFIXES["source"],
            field=f"{field}.source_ids",
        )
        for source_id in source_ids
    ]
    compiled = {
        "id": _text(record.get("id") or record.get("countervoice_id")).upper(),
        "source_ids": sources,
        "claim_id": linked_claim,
        "claim_delta": _claim_delta(record, field=field),
        "action": action,
        "preferred_realization": action,
        "activation_reason": _activation_reason(record, field=field),
        "position": _text(record.get("position")),
        "discriminating_evidence": _text(record.get("discriminating_evidence")),
    }
    if not _substantive(compiled["position"], 6) or not _substantive(
        compiled["discriminating_evidence"], 6
    ):
        raise ProsePacketError(f"{field} needs a source position and discriminating evidence")
    location = _text(record.get("full_statement_location"))
    if action in {"single_full_statement", "footnote_or_cross_reference"} and not _substantive(location, 4):
        raise ProsePacketError(f"{field}.full_statement_location is required for {action}")
    if location:
        compiled["full_statement_location"] = location
    return compiled


def compile_prose_packet(
    request: Any,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
    _legacy_surface_order: bool = False,
) -> dict[str, Any]:
    if not isinstance(request, dict):
        raise ProsePacketError("the materiality request must be a JSON object")
    _ensure_allowed_fields(request, REQUEST_TOP_LEVEL_KEYS, field="materiality request")
    registered = frozenset(_text(item).upper() for item in registered_ids if _text(item))
    raw_claim = request.get("claim")
    if not isinstance(raw_claim, dict):
        raise ProsePacketError("claim must be an object")
    raw_mode = _text(raw_claim.get("realization_mode")).lower() or "legacy_exact"
    evidence_items = _compile_evidence_items(
        request.get("evidence_items"),
        registered_ids=registered,
        require_function=raw_mode == "semantic",
    )
    citation_anchors = frozenset(
        value.casefold()
        for item in evidence_items
        for value in (_text(item.get("id")), _text(item.get("citation_key")))
        if value
    )
    claim = _compile_claim(
        raw_claim, registered_ids=registered, citation_anchors=citation_anchors
    )
    claim_id = claim["id"]
    object_text = _text(request.get("object"))
    warrant = _text(request.get("warrant"))
    reader_update = _text(request.get("reader_update"))
    if not all(
        (
            _substantive(object_text, 4),
            _substantive(warrant, 5),
            _substantive(reader_update, 5),
        )
    ):
        raise ProsePacketError("object, warrant, and reader_update must be substantive")

    semantic = claim["realization_mode"] == "semantic"
    reader_question = _text(request.get("reader_question"))
    plain_core = _text(request.get("plain_core"))
    if semantic and (
        not _substantive(reader_question, 5) or not _substantive(plain_core, 5)
    ):
        raise ProsePacketError(
            "semantic packets require substantive reader_question and plain_core"
        )
    if not reader_question:
        reader_question = f"What explains {object_text}?"
    if not plain_core:
        plain_core = claim["canonical_proposition"]
    explanation_path = _compile_explanation_path(
        request.get("explanation_path"), registered_ids=registered, required=semantic
    )
    if not explanation_path:
        explanation_path = [
            {
                "step": 1,
                "function": "claim",
                "content": claim["canonical_proposition"],
                "anchor_id": claim_id,
            }
        ]
        for item in evidence_items:
            explanation_path.append(
                {
                    "step": len(explanation_path) + 1,
                    "function": "evidence_role",
                    "content": item["text"],
                    "anchor_id": item["id"],
                }
            )
        explanation_path.extend(
            [
                {
                    "step": len(explanation_path) + 1,
                    "function": "warrant",
                    "content": warrant,
                },
                {
                    "step": len(explanation_path) + 2,
                    "function": "reader_update",
                    "content": reader_update,
                },
            ]
        )

    candidates = request.get("boundaries", [])
    if not isinstance(candidates, list):
        raise ProsePacketError("boundaries must be an array")
    boundaries: list[dict[str, Any]] = []
    seen_boundaries: set[str] = set()
    for index, record in enumerate(candidates, start=1):
        compiled = _compile_boundary(
            record,
            claim_id=claim_id,
            registered_ids=registered,
            field=f"boundaries[{index}]",
        )
        if compiled is None:
            continue
        if compiled["id"] in seen_boundaries:
            raise ProsePacketError(f"duplicate activated boundary ID: {compiled['id']}")
        seen_boundaries.add(compiled["id"])
        boundaries.append(compiled)

    countervoices_raw = request.get("countervoices", [])
    if not isinstance(countervoices_raw, list):
        raise ProsePacketError("countervoices must be an array")
    countervoices: list[dict[str, Any]] = []
    for index, record in enumerate(countervoices_raw, start=1):
        compiled = _compile_countervoice(
            record,
            claim_id=claim_id,
            registered_ids=registered,
            field=f"countervoices[{index}]",
        )
        if compiled is not None:
            countervoices.append(compiled)

    target_length = request.get("target_length")
    if target_length is not None and (
        not isinstance(target_length, int) or isinstance(target_length, bool) or target_length <= 0
    ):
        raise ProsePacketError("target_length must be a positive integer when supplied")
    section_role = _text(request.get("section_role")).lower()
    if not section_role:
        raise ProsePacketError("section_role is required")
    result_use = _text(request.get("result_use")).lower() or "claim_support"
    if result_use not in RESULT_USES:
        raise ProsePacketError(
            "result_use must be claim_support or negative_or_null_report"
        )
    result_ids = _string_list(request.get("result_ids", []), field="result_ids")
    result_ids = [
        _require_registered(
            result_id,
            registered,
            allowed_prefixes=RESULT_PREFIXES,
            field=f"result_ids[{index}]",
        )
        for index, result_id in enumerate(result_ids, start=1)
    ]
    authority_snapshot = _canonical_result_authority_snapshot(
        accepted_result_claims,
        claim_id=claim_id,
        result_ids=result_ids,
        result_use=result_use,
        section_role=section_role,
    )
    if accepted_result_claims is not None:
        accepted_map = {
            _text(result_id).upper(): {
                _text(item).upper() for item in claim_ids if _text(item)
            }
            for result_id, claim_ids in accepted_result_claims.items()
        }
        for result_id in result_ids:
            if result_id not in accepted_map:
                raise ProsePacketError(
                    "result_ids contains a result without canonical execution eligibility "
                    f"for {result_use}: {result_id}"
                )
            if claim_id not in accepted_map[result_id]:
                raise ProsePacketError(
                    f"result {result_id} is not bound to packet claim {claim_id}"
                )
        if section_role == "results" and not result_ids:
            raise ProsePacketError(
                "results packets in a v3 execution workspace require at least one accepted result_id"
            )
    clarity_growth_soft_limits = compile_clarity_growth_soft_limits(
        request.get("clarity_growth_soft_limits")
    )
    rhetorical_task = _compile_rhetorical_task(request.get("rhetorical_task"))
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "section_role": section_role,
        "object": object_text,
        "claim": claim,
        "evidence_items": evidence_items,
        "warrant": warrant,
        "required_boundaries": boundaries,
        "material_countervoices": countervoices,
        "reader_question": reader_question,
        "plain_core": plain_core,
        "explanation_path": explanation_path,
        "reader_update": reader_update,
        "expression_budget": canonical_expression_budget(
            section_role,
            claim["realization_mode"],
            clarity_growth_soft_limits,
            _legacy_surface_order=_legacy_surface_order,
        ),
    }
    if rhetorical_task is not None:
        packet["rhetorical_task"] = rhetorical_task
    if result_ids:
        packet["result_ids"] = result_ids
        packet["result_use"] = result_use
    if target_length is not None:
        packet["target_length"] = target_length
    for optional in ("evidence_delta", "claim_delta"):
        value = request.get(optional)
        if value is not None:
            allowed = EVIDENCE_PREFIXES if optional == "evidence_delta" else CLAIM_PREFIXES
            packet[optional] = _require_registered(
                value, registered, allowed_prefixes=allowed, field=optional
            )
    packet["source_digest"] = _packet_source_digest(packet, authority_snapshot)
    _reject_process_language(packet, field="ProsePacket")
    return packet


def validate_prose_packet(
    packet: Any,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    if not isinstance(packet, dict):
        return ["packet must be a JSON object"]
    issues: list[str] = []
    clarity_growth_soft_limits: dict[str, float] | None = None
    raw_budget = packet.get("expression_budget")
    # Shape selects one of two complete canonical contracts, not user-supplied
    # numbers. Old explicit v2 packets must retain their original digest.
    legacy_surface_order = not isinstance(raw_budget, dict) or "surface_order_policy" not in raw_budget
    schema = _text(packet.get("schema_version"))
    if schema not in SUPPORTED_SCHEMA_VERSIONS:
        issues.append(
            f"schema_version must be {SCHEMA_VERSION} or legacy {LEGACY_SCHEMA_VERSION}"
        )
    try:
        _ensure_allowed_fields(packet, PACKET_TOP_LEVEL_KEYS, field="packet")
        _reject_process_language(packet, field="ProsePacket")
        nested_specs = (
            ("claim", packet.get("claim"), CLAIM_KEYS, False),
            ("evidence_items", packet.get("evidence_items"), EVIDENCE_ITEM_KEYS, True),
            (
                "explanation_path",
                packet.get("explanation_path", [])
                if schema == LEGACY_SCHEMA_VERSION
                else packet.get("explanation_path"),
                EXPLANATION_STEP_KEYS,
                True,
            ),
            (
                "required_boundaries",
                packet.get("required_boundaries"),
                BOUNDARY_KEYS,
                True,
            ),
            (
                "material_countervoices",
                packet.get("material_countervoices"),
                COUNTERVOICE_KEYS,
                True,
            ),
        )
        for field, value, allowed, is_array in nested_specs:
            records = value if is_array else [value]
            if not isinstance(records, list):
                raise ProsePacketError(f"packet.{field} must be an array")
            for index, record in enumerate(records, start=1):
                item_field = f"packet.{field}[{index}]" if is_array else f"packet.{field}"
                if not isinstance(record, dict):
                    raise ProsePacketError(f"{item_field} must be an object")
                _ensure_allowed_fields(record, allowed, field=item_field)
                if field == "evidence_items" and record.get("context_anchor") is not None:
                    anchor = record.get("context_anchor")
                    if not isinstance(anchor, dict):
                        raise ProsePacketError(f"{item_field}.context_anchor must be an object")
                    _ensure_allowed_fields(
                        anchor,
                        CONTEXT_ANCHOR_KEYS,
                        field=f"{item_field}.context_anchor",
                    )
        if packet.get("rhetorical_task") is not None:
            task = packet.get("rhetorical_task")
            if not isinstance(task, dict):
                raise ProsePacketError("packet.rhetorical_task must be an object")
            _ensure_allowed_fields(task, RHETORICAL_TASK_KEYS, field="packet.rhetorical_task")
        claim_record = packet.get("claim")
        atoms = claim_record.get("protected_atoms") if isinstance(claim_record, dict) else None
        if atoms is not None:
            if not isinstance(atoms, dict):
                raise ProsePacketError("packet.claim.protected_atoms must be an object")
            _ensure_allowed_fields(
                atoms, PROTECTED_ATOM_KEYS, field="packet.claim.protected_atoms"
            )
        claim = dict(packet.get("claim") or {})
        if claim.get("realization_mode") == "legacy_exact":
            claim.pop("realization_mode", None)
        if schema == SCHEMA_VERSION:
            clarity_growth_soft_limits = clarity_growth_soft_limits_from_budget(
                packet.get("expression_budget")
            )
        reconstructed = {
            "section_role": packet.get("section_role"),
            "object": packet.get("object"),
            "claim": claim,
            "evidence_items": packet.get("evidence_items"),
            "result_ids": packet.get("result_ids"),
            "result_use": packet.get("result_use"),
            "warrant": packet.get("warrant"),
            "boundaries": [
                {
                    "boundary_id": item.get("id"),
                    "anchor_type": item.get("anchor_type"),
                    "anchor_id": item.get("anchor_id"),
                    "materiality": "load_bearing",
                    "claim_id": item.get("claim_id"),
                    "claim_delta": item.get("claim_delta"),
                    "claim_effect": item.get("claim_effect"),
                    "preferred_realization": item.get("preferred_realization") or item.get("action"),
                    "activation_reason": item.get("activation_reason"),
                    "full_statement_location": item.get("full_statement_location"),
                    "statement": item.get("statement"),
                    "required": item.get("required"),
                    "full_statement_once": item.get("full_statement_once"),
                }
                for item in packet.get("required_boundaries", [])
                if isinstance(item, dict)
            ],
            "countervoices": [
                {
                    **item,
                    "materiality": "load_bearing",
                    "same_result": True,
                    "same_stage": True,
                    "manuscript_action": item.get("action"),
                }
                for item in packet.get("material_countervoices", [])
                if isinstance(item, dict)
            ],
            "reader_question": packet.get("reader_question"),
            "plain_core": packet.get("plain_core"),
            "explanation_path": packet.get("explanation_path"),
            "reader_update": packet.get("reader_update"),
            "target_length": packet.get("target_length"),
            "evidence_delta": packet.get("evidence_delta"),
            "claim_delta": packet.get("claim_delta"),
            "clarity_growth_soft_limits": clarity_growth_soft_limits,
            "rhetorical_task": packet.get("rhetorical_task"),
        }
        reconstructed = {key: value for key, value in reconstructed.items() if value is not None}
        expected_packet = compile_prose_packet(
            reconstructed,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
            _legacy_surface_order=legacy_surface_order,
        )
        if schema == SCHEMA_VERSION and packet.get("source_digest") != expected_packet.get(
            "source_digest"
        ):
            issues.append(
                "source_digest does not match the canonical packet and selected result authority"
            )
    except ProsePacketError as exc:
        issues.append(str(exc))
    budget = packet.get("expression_budget")
    mode = _claim_realization_mode(packet)
    expected_budget = (
        legacy_expression_budget(_text(packet.get("section_role")).lower())
        if schema == LEGACY_SCHEMA_VERSION
        else canonical_expression_budget(
            _text(packet.get("section_role")).lower(),
            mode,
            clarity_growth_soft_limits,
            _legacy_surface_order=legacy_surface_order,
        )
    )
    if budget != expected_budget:
        issues.append("expression_budget must exactly match the canonical prose-cost contract")
    return issues


def _compact_prose(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value)).casefold()


def _exact_token_present(text: str, token: Any) -> bool:
    value = _text(token)
    if not value:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_.:/@-]){re.escape(value)}(?![A-Za-z0-9_.:/@-])",
        text,
    ) is not None


def _claim_realization_mode(packet: Any) -> str:
    if not isinstance(packet, dict) or packet.get("schema_version") == LEGACY_SCHEMA_VERSION:
        return "legacy_exact"
    claim = packet.get("claim")
    if not isinstance(claim, dict):
        return "legacy_exact"
    mode = _text(claim.get("realization_mode")).lower()
    return mode if mode in REALIZATION_MODES else "legacy_exact"


def validate_draft_fidelity(
    packet: Any,
    draft: str,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    """Check deterministic zero-loss invariants before and after clarity editing.

    Semantic preservation of subject/relation, polarity, direction, scope, and
    inference strength remains the separate Semantic Fidelity Gate. This
    deterministic gate protects only exact identities and payloads.
    """
    issues = [
        f"invalid ProsePacket: {issue}"
        for issue in validate_prose_packet(
            packet,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        )
    ]
    if not isinstance(packet, dict):
        return issues
    if not _text(draft):
        issues.append("draft is empty")
        return issues
    if CONTROL_PLANE_LEAK_RE.search(draft) or PROCESS_LANGUAGE_RE.search(draft):
        issues.append("draft leaks control-plane or unactivated defensive context")
    compact_draft = _compact_prose(draft)
    draft_numbers = set(NUMBER_RE.findall(draft))
    mode = _claim_realization_mode(packet)
    claim_text_raw = _text((packet.get("claim") or {}).get("text"))
    claim_text = _compact_prose(claim_text_raw)
    exact_claim = mode in {"verbatim", "legacy_exact"}
    if exact_claim and claim_text_raw and claim_text_raw not in draft:
        issues.append("the packet claim text is missing from the draft")
    latency = (packet.get("expression_budget") or {}).get("claim_latency")
    max_before = latency.get("max_sentences_before_claim") if isinstance(latency, dict) else None
    if exact_claim and claim_text and isinstance(max_before, int) and claim_text in compact_draft:
        sentences = [
            _compact_prose(item)
            for item in re.split(r"(?<=[。！？.!?])\s*", draft)
            if _text(item)
        ]
        claim_index = next(
            (index for index, sentence in enumerate(sentences) if claim_text in sentence), None
        )
        if claim_index is None or claim_index > max_before:
            issues.append(
                f"claim latency exceeds {max_before} sentence(s) before the packet claim"
            )
    claim_position = compact_draft.find(claim_text) if exact_claim and claim_text else -1
    if mode == "semantic":
        atoms = (packet.get("claim") or {}).get("protected_atoms") or {}
        strength = _text(atoms.get("inferential_strength")).lower()
        for literal in atoms.get("protected_literals", []):
            protected = _text(literal)
            if protected and protected not in draft:
                issues.append(f"protected literal is missing: {literal}")
        for number in atoms.get("protected_numbers", []):
            if _text(number) not in draft_numbers:
                issues.append(f"protected claim number is missing: {number}")
        for citation in atoms.get("citation_anchors", []):
            if not _exact_token_present(draft, citation):
                issues.append(f"protected claim citation anchor is missing: {citation}")
        subject = _compact_prose(atoms.get("subject"))
        relation = _compact_prose(atoms.get("relation"))
        causal_strengthening_found = False
        for sentence in re.split(r"(?<=[。！？.!?])\s*", draft):
            compact_sentence = _compact_prose(sentence)
            if subject and relation and subject in compact_sentence and relation in compact_sentence:
                if strength in {
                    "associational",
                    "association",
                    "correlational",
                    "相关",
                    "关联",
                }:
                    for causal_match in CAUSAL_ASSERTION_RE.finditer(sentence):
                        clause_prefix = re.split(
                            r"[，,；;。！？.!?]",
                            sentence[: causal_match.start()],
                        )[-1]
                        normalized_prefix = clause_prefix.rstrip()
                        if (
                            (
                                CAUSAL_NEGATION_PREFIX_RE.search(normalized_prefix)
                                or CAUSAL_NO_EVIDENCE_PREFIX_RE.search(normalized_prefix)
                            )
                            and not CAUSAL_DOUBLE_NEGATION_PREFIX_RE.search(normalized_prefix)
                        ):
                            continue
                        if not causal_strengthening_found:
                            issues.append(
                                "draft introduces causal assertion language beyond the protected associational strength"
                            )
                            causal_strengthening_found = True
                        break
                if claim_position < 0:
                    claim_position = compact_draft.find(compact_sentence)
    for index, item in enumerate(packet.get("evidence_items", []), start=1):
        if not isinstance(item, dict):
            continue
        evidence_id = _text(item.get("id")) or f"item-{index}"
        for number in sorted(set(NUMBER_RE.findall(_text(item.get("text"))))):
            if number not in draft_numbers:
                issues.append(f"protected number {number} from {evidence_id} is missing")
        locator = _text(item.get("locator"))
        if locator and _compact_prose(locator) not in compact_draft:
            issues.append(f"protected locator from {evidence_id} is missing: {locator}")
        citation_key = _text(item.get("citation_key"))
        if citation_key and not _exact_token_present(draft, citation_key):
            issues.append(
                f"protected citation_key from {evidence_id} is missing: {citation_key}"
            )
        context_anchor = item.get("context_anchor")
        if isinstance(context_anchor, dict):
            anchor_id = _text(context_anchor.get("anchor_id")) or "<missing>"
            anchor_type = _text(context_anchor.get("type")).lower()
            anchor_locator = _text(context_anchor.get("locator"))
            if anchor_locator and _compact_prose(anchor_locator) not in compact_draft:
                code = (
                    "AP.QUOTE.LOCATOR_MISSING"
                    if anchor_type in {"quotation", "definition"}
                    else "AP.SCENE.UNBOUND"
                )
                issues.append(f"{code}: Context Anchor {anchor_id} locator is missing from the draft")
            exact_span = _text(context_anchor.get("exact_span"))
            if exact_span and exact_span not in draft:
                issues.append(
                    f"AP.QUOTE.QUALIFIER_LOSS: Context Anchor {anchor_id} exact span is missing"
                )
            for qualifier in context_anchor.get("protected_qualifiers", []):
                if _text(qualifier) and _text(qualifier) not in draft:
                    issues.append(
                        f"AP.QUOTE.QUALIFIER_LOSS: Context Anchor {anchor_id} loses protected qualifier {qualifier}"
                    )
            for detail in context_anchor.get("known_details", []):
                if _text(detail) and _compact_prose(detail) not in compact_draft:
                    issues.append(
                        f"AP.SCENE.UNBOUND: Context Anchor {anchor_id} known detail is missing: {detail}"
                    )
    for boundary in packet.get("required_boundaries", []):
        if not isinstance(boundary, dict) or boundary.get("full_statement_once") is not True:
            continue
        boundary_id = _text(boundary.get("id")) or "<missing>"
        statement = _compact_prose(boundary.get("statement"))
        occurrences = compact_draft.count(statement) if statement else 0
        if occurrences != 1:
            issues.append(
                f"activated boundary {boundary_id} must appear exactly once; found {occurrences}"
            )
        elif claim_position >= 0:
            before_claim = compact_draft.find(statement) < claim_position
            functional_order = (packet.get("expression_budget") or {}).get("surface_order_policy") == "argument_function"
            location = _text(boundary.get("full_statement_location")).lower()
            # The old universal order is retained only for historical packets.
            # New packets retain an explicitly registered relative location;
            # other prose locations/dependencies remain part of semantic review.
            explicitly_after = location == "after_claim" or location.endswith("_after_claim")
            explicitly_before = location == "before_claim" or location.endswith("_before_claim")
            if before_claim and (not functional_order or explicitly_after):
                issues.append(
                    f"activated boundary {boundary_id} appears before the packet claim"
                )
            elif functional_order and explicitly_before and not before_claim:
                issues.append(
                    f"activated boundary {boundary_id} must precede the packet claim at its registered location"
                )
    return issues


def prose_units(text: str) -> int:
    return len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)) + len(
        re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?|\d+(?:\.\d+)?", text)
    )


def citation_like_anchors(text: str) -> set[str]:
    """Extract citation syntax that a clarity edit is not authorized to invent."""
    anchors: set[str] = set()
    for group in LATEX_CITATION_RE.findall(text):
        anchors.update(key.strip() for key in group.split(",") if key.strip())
    for group in PANDOC_CITATION_RE.findall(text):
        anchors.update(re.findall(r"@([\w:./-]+)", group))
    anchors.update(BARE_PANDOC_CITATION_RE.findall(text))
    anchors.update(re.sub(r"\s+", "", match) for match in NUMERIC_BRACKET_CITATION_RE.findall(text))
    anchors.update(
        re.sub(r"\s+", " ", match).strip().casefold()
        for match in SQUARE_AUTHOR_YEAR_CITATION_RE.findall(text)
    )
    anchors.update(match.casefold() for match in DOI_RE.findall(text))
    anchors.update(
        re.sub(r"\s+", " ", match).strip().casefold()
        for match in AUTHOR_YEAR_CITATION_RE.findall(text)
    )
    return anchors


def quotation_fragments(text: str) -> set[str]:
    fragments = QUOTATION_RE.findall(text) + MARKDOWN_BLOCKQUOTE_RE.findall(text)
    return {_compact_prose(fragment) for fragment in fragments if _compact_prose(fragment)}


def validate_clarity_delta_content(writer_draft: str, edited_draft: str) -> list[str]:
    """Reject deterministic additions that cannot be licensed by a clarity ledger."""
    issues: list[str] = []
    new_numbers = set(NUMBER_RE.findall(edited_draft)) - set(NUMBER_RE.findall(writer_draft))
    if new_numbers:
        issues.append(
            "clarity edit introduces unregistered number(s): "
            + ", ".join(sorted(new_numbers))
        )
    new_citations = citation_like_anchors(edited_draft) - citation_like_anchors(writer_draft)
    if new_citations:
        issues.append(
            "clarity edit introduces unregistered citation-like anchor(s): "
            + ", ".join(sorted(new_citations))
        )
    new_quotations = quotation_fragments(edited_draft) - quotation_fragments(writer_draft)
    if new_quotations:
        issues.append(
            "clarity edit introduces unregistered quotation(s): "
            + ", ".join(sorted(new_quotations))
        )
    return issues


def validate_compression(
    packet: Any,
    writer_draft: str,
    compressed_draft: str,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    """Preserve the legacy exact-and-zero-growth compression compatibility gate."""
    issues = [
        f"writer draft fidelity: {issue}"
        for issue in validate_draft_fidelity(
            packet,
            writer_draft,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        )
    ]
    issues.extend(
        f"compressed draft fidelity: {issue}"
        for issue in validate_draft_fidelity(
            packet,
            compressed_draft,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        )
    )
    delta = prose_units(compressed_draft) - prose_units(writer_draft)
    if delta > 0:
        issues.append(f"compression net prose growth must be <= 0; observed {delta}")
    return issues


def _clarity_source_is_bound(packet: dict[str, Any], source_kind: str, source_anchor: str) -> bool:
    if source_kind == "warrant":
        return source_anchor == "warrant"
    if source_kind == "explanation_path":
        valid: set[str] = set()
        for step in packet.get("explanation_path", []):
            if not isinstance(step, dict):
                continue
            step_number = step.get("step") if step.get("step") is not None else step.get("order")
            valid.add(f"explanation_path:{step_number}")
            anchor_id = _text(step.get("anchor_id")).upper()
            if anchor_id:
                valid.add(anchor_id)
        return source_anchor in valid or source_anchor.upper() in valid
    if source_kind == "registered_term":
        atoms = (packet.get("claim") or {}).get("protected_atoms") or {}
        return source_anchor in {_text(item) for item in atoms.get("protected_literals", [])}
    return False


def check_clarity(
    packet: Any,
    writer_draft: str,
    edited_draft: str,
    ledger: Any,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
) -> ClarityValidationResult:
    """Validate an evidence-bounded Clarity Editor pass.

    Growth ratios are configurable diagnostic warnings. Positive growth is
    blocking only when it lacks a grounded BRIDGE/DEFINE ledger.
    """
    issues = [
        f"writer draft fidelity: {issue}"
        for issue in validate_draft_fidelity(
            packet,
            writer_draft,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        )
    ]
    issues.extend(
        f"clarity draft fidelity: {issue}"
        for issue in validate_draft_fidelity(
            packet,
            edited_draft,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        )
    )
    issues.extend(validate_clarity_delta_content(writer_draft, edited_draft))
    delta = prose_units(edited_draft) - prose_units(writer_draft)
    baseline_units = prose_units(writer_draft)
    growth_ratio = delta / baseline_units if baseline_units else (1.0 if delta > 0 else 0.0)
    warnings: list[str] = []

    if not isinstance(ledger, dict):
        if delta > 0:
            issues.append(
                f"clarity edit has positive net prose growth ({delta}) without a valid ledger"
            )
        else:
            issues.append("clarity ledger must be an object")
        return ClarityValidationResult(tuple(issues), tuple(warnings), delta, growth_ratio)
    try:
        _ensure_allowed_fields(ledger, CLARITY_LEDGER_KEYS, field="clarity ledger")
    except ProsePacketError as exc:
        issues.append(str(exc))
    if ledger.get("schema_version") != CLARITY_LEDGER_SCHEMA_VERSION:
        issues.append(f"clarity ledger schema_version must be {CLARITY_LEDGER_SCHEMA_VERSION}")
    scope = _text(ledger.get("scope")).lower()
    if scope not in {"paragraph", "section"}:
        issues.append("clarity ledger scope must be paragraph or section")
    actions = ledger.get("actions")
    if not isinstance(actions, list):
        issues.append("clarity ledger actions must be an array")
        actions = []
    if delta > 0 and not actions:
        issues.append(
            f"clarity edit has positive net prose growth ({delta}) without BRIDGE/DEFINE actions"
        )

    packet_claim_id = _text((packet.get("claim") or {}).get("id")).upper() if isinstance(packet, dict) else ""
    registered = frozenset(_text(item).upper() for item in registered_ids if _text(item))
    ledger_delta = 0
    for index, record in enumerate(actions, start=1):
        field = f"clarity ledger.actions[{index}]"
        if not isinstance(record, dict):
            issues.append(f"{field} must be an object")
            continue
        try:
            _ensure_allowed_fields(record, CLARITY_ACTION_KEYS, field=field)
        except ProsePacketError as exc:
            issues.append(str(exc))
            continue
        action = _text(record.get("action")).upper()
        if action not in CLARITY_ACTIONS:
            issues.append(f"{field}.action must be one of {sorted(CLARITY_ACTIONS)}")
        prose_delta = record.get("prose_delta")
        if not isinstance(prose_delta, int) or isinstance(prose_delta, bool):
            issues.append(f"{field}.prose_delta must be an integer")
            continue
        ledger_delta += prose_delta
        if prose_delta > 0 and action not in POSITIVE_GROWTH_ACTIONS:
            issues.append(f"{field}: only BRIDGE or DEFINE may record positive prose growth")
        if action in POSITIVE_GROWTH_ACTIONS:
            claim_id = _text(record.get("claim_id")).upper()
            if claim_id != packet_claim_id or claim_id not in registered:
                issues.append(f"{field}.claim_id must match the registered packet Claim ID")
            source_kind = _text(record.get("source_kind")).lower()
            source_anchor = _text(record.get("source_anchor"))
            if source_kind not in CLARITY_SOURCE_KINDS:
                issues.append(
                    f"{field}.source_kind must be one of {sorted(CLARITY_SOURCE_KINDS)}"
                )
            elif not isinstance(packet, dict) or not _clarity_source_is_bound(
                packet, source_kind, source_anchor
            ):
                issues.append(f"{field}.source_anchor is not bound to the ProsePacket")
            if not _substantive(record.get("reader_understanding"), 6):
                issues.append(f"{field}.reader_understanding must state the reader gain")
            for confirmation in (
                "no_new_fact",
                "no_new_citation",
                "no_inference_strengthening",
            ):
                if record.get(confirmation) is not True:
                    issues.append(f"{field}.{confirmation} must be true")
    if ledger_delta != delta:
        issues.append(
            f"clarity ledger prose_delta total ({ledger_delta}) does not match actual delta ({delta})"
        )
    if delta > 0 and scope in {"paragraph", "section"}:
        soft_limits = dict(DEFAULT_CLARITY_GROWTH_SOFT_LIMITS)
        if isinstance(packet, dict) and packet.get("schema_version") == SCHEMA_VERSION:
            try:
                soft_limits = clarity_growth_soft_limits_from_budget(
                    packet.get("expression_budget")
                )
            except ProsePacketError:
                pass
        threshold = soft_limits[f"{scope}_ratio"]
        if growth_ratio > threshold:
            warnings.append(
                f"clarity {scope} growth ratio {growth_ratio:.1%} exceeds the soft {threshold:.0%} review threshold"
            )
    return ClarityValidationResult(tuple(issues), tuple(warnings), delta, growth_ratio)


def validate_clarity(
    packet: Any,
    writer_draft: str,
    edited_draft: str,
    ledger: Any,
    *,
    registered_ids: Iterable[str],
    accepted_result_claims: Mapping[str, Iterable[str]] | None = None,
) -> list[str]:
    """Compatibility-friendly blocking-issue view of :func:`check_clarity`."""
    return list(
        check_clarity(
            packet,
            writer_draft,
            edited_draft,
            ledger,
            registered_ids=registered_ids,
            accepted_result_claims=accepted_result_claims,
        ).issues
    )


def semantic_fidelity_digests(packet: Any, draft: str) -> tuple[str, str]:
    canonical_packet = json.dumps(
        packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return (
        hashlib.sha256(canonical_packet.encode("utf-8")).hexdigest(),
        hashlib.sha256(draft.encode("utf-8")).hexdigest(),
    )


def _validate_semantic_fidelity_judgment(
    packet: Any,
    draft: str,
    review: Any,
    *,
    registered_ids: Iterable[str],
    review_run_id: str,
) -> list[str]:
    """Validate judgment content after provenance has been established."""
    issues = [
        f"deterministic fidelity: {issue}"
        for issue in validate_draft_fidelity(
            packet, draft, registered_ids=registered_ids
        )
    ]
    if not isinstance(packet, dict) or _claim_realization_mode(packet) != "semantic":
        issues.append("Semantic Fidelity Gate applies only to v2 semantic packets")
    if not isinstance(review, dict):
        issues.append("semantic fidelity review must be a JSON object")
        return issues
    try:
        _ensure_allowed_fields(
            review,
            SEMANTIC_FIDELITY_REVIEW_KEYS,
            field="semantic fidelity review",
        )
    except ProsePacketError as exc:
        issues.append(str(exc))
    if review.get("schema_version") != SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION:
        issues.append(
            "semantic fidelity review schema_version must be "
            + SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION
        )
    if review.get("review_run_id") != review_run_id:
        issues.append("semantic fidelity review_run_id does not match dispatch")
    packet_sha256, draft_sha256 = semantic_fidelity_digests(packet, draft)
    if _text(review.get("packet_sha256")).lower() != packet_sha256:
        issues.append("semantic fidelity review packet_sha256 does not match the packet")
    if _text(review.get("draft_sha256")).lower() != draft_sha256:
        issues.append("semantic fidelity review draft_sha256 does not match the draft")

    dimensions = review.get("dimensions")
    if not isinstance(dimensions, dict):
        issues.append("semantic fidelity review dimensions must be an object")
        dimensions = {}
    missing = set(SEMANTIC_FIDELITY_DIMENSIONS) - set(dimensions)
    unexpected = set(dimensions) - set(SEMANTIC_FIDELITY_DIMENSIONS)
    if missing:
        issues.append(
            "semantic fidelity review is missing dimensions: "
            + ", ".join(sorted(missing))
        )
    if unexpected:
        issues.append(
            "semantic fidelity review has unsupported dimensions: "
            + ", ".join(sorted(unexpected))
        )
    for name in SEMANTIC_FIDELITY_DIMENSIONS:
        record = dimensions.get(name)
        field = f"semantic fidelity review.dimensions.{name}"
        if not isinstance(record, dict):
            issues.append(f"{field} must be an object")
            continue
        try:
            _ensure_allowed_fields(
                record,
                SEMANTIC_FIDELITY_DIMENSION_KEYS,
                field=field,
            )
        except ProsePacketError as exc:
            issues.append(str(exc))
        status = _text(record.get("status")).upper()
        if status not in {"PASS", "FAIL"}:
            issues.append(f"{field}.status must be PASS or FAIL")
        elif status != "PASS":
            issues.append(f"{field} did not pass")
        if not _substantive(record.get("reason"), 8):
            issues.append(f"{field}.reason must record the comparison finding")
    overall_status = _text(review.get("overall_status")).upper()
    if overall_status not in {"PASS", "FAIL"}:
        issues.append("semantic fidelity review overall_status must be PASS or FAIL")
    elif overall_status != "PASS":
        issues.append("semantic fidelity review overall_status did not pass")
    return issues


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ProsePacketError(f"cannot hash semantic fidelity artifact {path}: {exc}") from exc


def _workspace_relative(workspace: Path, path: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _semantic_artifact_path(workspace: Path, value: Any, *, field: str) -> Path:
    relative = _text(value).replace("\\", "/")
    if not relative or Path(relative).is_absolute():
        raise ProsePacketError(f"{field} must be a workspace-relative path")
    candidate = _inside_workspace(workspace, workspace / Path(relative))
    if _workspace_relative(workspace, candidate) != Path(relative).as_posix():
        raise ProsePacketError(f"{field} must be a normalized workspace-relative path")
    return candidate


def _semantic_exact_keys(
    record: Any, allowed: frozenset[str], *, field: str, issues: list[str]
) -> dict[str, Any]:
    if not isinstance(record, dict):
        issues.append(f"{field} must be a JSON object")
        return {}
    missing = set(allowed) - set(record)
    unexpected = set(record) - set(allowed)
    if missing:
        issues.append(f"{field} is missing fields: " + ", ".join(sorted(missing)))
    if unexpected:
        issues.append(f"{field} has unsupported fields: " + ", ".join(sorted(unexpected)))
    return record


def semantic_fidelity_review_prompt(
    packet: dict[str, Any],
    draft: str,
    *,
    review_run_id: str,
    packet_sha256: str,
    draft_sha256: str,
) -> str:
    dimensions = ", ".join(SEMANTIC_FIDELITY_DIMENSIONS)
    return (
        "You are an isolated Semantic Fidelity reviewer. Read only the writer-safe "
        "ProsePacket and candidate draft below. Test both directions: every canonical "
        "proposition must survive in the draft, and every substantive draft assertion "
        "must be licensed by the packet. Do not reward style, novelty, caution, or length. "
        "Return one JSON object only, with no Markdown. Use schema_version "
        f"{SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION}, review_run_id {review_run_id}, "
        f"packet_sha256 {packet_sha256}, draft_sha256 {draft_sha256}, overall_status PASS "
        "only when every dimension passes, and an exact dimensions object. Each dimension "
        "contains only status (PASS or FAIL) and a concrete comparison reason. Required "
        f"dimensions: {dimensions}.\n\nProsePacket:\n"
        + json.dumps(packet, ensure_ascii=False, indent=2)
        + "\n\nCandidate draft:\n"
        + draft
        + "\n"
    )


def dispatch_semantic_fidelity_review(
    workspace: Path,
    packet_path: Path,
    draft_path: Path,
    *,
    registered_ids: Iterable[str],
    writer_context_id: str,
    clarity_context_id: str,
    review_run_id: str | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    packet_path = _inside_workspace(workspace, packet_path)
    draft_path = _inside_workspace(workspace, draft_path)
    packet = _load_json(packet_path)
    try:
        draft = draft_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ProsePacketError(f"cannot read draft from {draft_path}: {exc}") from exc
    fidelity_issues = validate_draft_fidelity(
        packet,
        draft,
        registered_ids=registered_ids,
        accepted_result_claims=_result_claims_for_payload(workspace, packet),
    )
    if fidelity_issues:
        raise ProsePacketError(
            "semantic dispatch requires deterministic fidelity: " + "; ".join(fidelity_issues)
        )
    if _claim_realization_mode(packet) != "semantic":
        raise ProsePacketError("semantic dispatch requires a v2 semantic packet")
    contexts = (_text(writer_context_id), _text(clarity_context_id))
    if any(not value for value in contexts) or len(set(contexts)) != 2:
        raise ProsePacketError("writer and clarity context IDs must be non-empty and distinct")
    run_id = review_run_id or f"SEM-{uuid.uuid4().hex[:16].upper()}"
    if not re.fullmatch(r"SEM-[A-F0-9]{16}", run_id):
        raise ProsePacketError("semantic review_run_id must match SEM-<16 uppercase hex>")
    target = output_dir or (
        workspace / ".avereth-prose" / "semantic-fidelity" / run_id
    )
    target = _inside_workspace(workspace, target)
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ProsePacketError(f"semantic dispatch directory already exists: {target}") from exc
    packet_content_sha, draft_content_sha = semantic_fidelity_digests(packet, draft)
    prompt_path = target / "request.md"
    review_path = target / "review.json"
    manifest_path = target / "dispatch.json"
    prompt = semantic_fidelity_review_prompt(
        packet,
        draft,
        review_run_id=run_id,
        packet_sha256=packet_content_sha,
        draft_sha256=draft_content_sha,
    )
    prompt_path.write_text(prompt, encoding="utf-8")
    manifest = {
        "schema_version": SEMANTIC_FIDELITY_DISPATCH_SCHEMA_VERSION,
        "review_run_id": run_id,
        "input_scope": "packet_and_draft_only",
        "packet_path": _workspace_relative(workspace, packet_path),
        "packet_file_sha256": _file_sha256(packet_path),
        "packet_content_sha256": packet_content_sha,
        "draft_path": _workspace_relative(workspace, draft_path),
        "draft_file_sha256": _file_sha256(draft_path),
        "draft_content_sha256": draft_content_sha,
        "prompt_path": _workspace_relative(workspace, prompt_path),
        "prompt_sha256": _file_sha256(prompt_path),
        "review_output_path": _workspace_relative(workspace, review_path),
        "writer_context_id": contexts[0],
        "clarity_context_id": contexts[1],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "review_run_id": run_id,
        "manifest": _workspace_relative(workspace, manifest_path),
        "prompt": _workspace_relative(workspace, prompt_path),
        "review_output": _workspace_relative(workspace, review_path),
    }


def _validate_semantic_dispatch(
    workspace: Path,
    manifest_path: Path,
    manifest: Any,
    *,
    require_output: bool,
) -> tuple[list[str], dict[str, Any]]:
    issues: list[str] = []
    manifest = _semantic_exact_keys(
        manifest,
        SEMANTIC_FIDELITY_DISPATCH_KEYS,
        field="semantic dispatch",
        issues=issues,
    )
    assets: dict[str, Any] = {}
    if manifest.get("schema_version") != SEMANTIC_FIDELITY_DISPATCH_SCHEMA_VERSION:
        issues.append(
            "semantic dispatch schema_version must be "
            + SEMANTIC_FIDELITY_DISPATCH_SCHEMA_VERSION
        )
    run_id = _text(manifest.get("review_run_id"))
    if not re.fullmatch(r"SEM-[A-F0-9]{16}", run_id):
        issues.append("semantic dispatch review_run_id must match SEM-<16 uppercase hex>")
    if manifest.get("input_scope") != "packet_and_draft_only":
        issues.append("semantic dispatch input_scope must be packet_and_draft_only")
    contexts = (
        _text(manifest.get("writer_context_id")),
        _text(manifest.get("clarity_context_id")),
    )
    if any(not value for value in contexts) or len(set(contexts)) != 2:
        issues.append("semantic dispatch writer/clarity contexts must be non-empty and distinct")
    try:
        packet_path = _semantic_artifact_path(
            workspace, manifest.get("packet_path"), field="semantic dispatch.packet_path"
        )
        draft_path = _semantic_artifact_path(
            workspace, manifest.get("draft_path"), field="semantic dispatch.draft_path"
        )
        prompt_path = _semantic_artifact_path(
            workspace, manifest.get("prompt_path"), field="semantic dispatch.prompt_path"
        )
        review_path = _semantic_artifact_path(
            workspace,
            manifest.get("review_output_path"),
            field="semantic dispatch.review_output_path",
        )
        for label, path in (
            ("packet", packet_path),
            ("draft", draft_path),
            ("prompt", prompt_path),
        ):
            if not path.is_file():
                issues.append(f"semantic dispatch {label} artifact is missing")
        if require_output and not review_path.is_file():
            issues.append("semantic dispatch review output is missing")
        if packet_path.is_file() and _file_sha256(packet_path) != manifest.get(
            "packet_file_sha256"
        ):
            issues.append("semantic dispatch packet file SHA does not match")
        if draft_path.is_file() and _file_sha256(draft_path) != manifest.get(
            "draft_file_sha256"
        ):
            issues.append("semantic dispatch draft file SHA does not match")
        if prompt_path.is_file() and _file_sha256(prompt_path) != manifest.get(
            "prompt_sha256"
        ):
            issues.append("semantic dispatch prompt SHA does not match")
        packet = _load_json(packet_path) if packet_path.is_file() else {}
        draft = draft_path.read_text(encoding="utf-8-sig") if draft_path.is_file() else ""
        packet_content_sha, draft_content_sha = semantic_fidelity_digests(packet, draft)
        if packet_content_sha != manifest.get("packet_content_sha256"):
            issues.append("semantic dispatch packet content SHA does not match")
        if draft_content_sha != manifest.get("draft_content_sha256"):
            issues.append("semantic dispatch draft content SHA does not match")
        expected_prompt = semantic_fidelity_review_prompt(
            packet,
            draft,
            review_run_id=run_id,
            packet_sha256=packet_content_sha,
            draft_sha256=draft_content_sha,
        )
        if prompt_path.is_file() and prompt_path.read_text(encoding="utf-8") != expected_prompt:
            issues.append("semantic dispatch prompt is not the canonical packet-and-draft request")
        if manifest_path.parent.resolve() != prompt_path.parent.resolve() or (
            manifest_path.parent.resolve() != review_path.parent.resolve()
        ):
            issues.append("semantic dispatch artifacts must share one isolated run directory")
        assets.update(
            {
                "packet": packet,
                "draft": draft,
                "prompt_path": prompt_path,
                "review_path": review_path,
                "contexts": contexts,
                "run_id": run_id,
            }
        )
    except (OSError, ProsePacketError) as exc:
        issues.append(str(exc))
    return issues, assets


def create_semantic_fidelity_assurance(
    workspace: Path,
    manifest_path: Path,
    *,
    reviewer_context_id: str,
) -> dict[str, Any]:
    manifest_path = _inside_workspace(workspace, manifest_path)
    manifest = _load_json(manifest_path)
    issues, assets = _validate_semantic_dispatch(
        workspace, manifest_path, manifest, require_output=True
    )
    context_id = _text(reviewer_context_id)
    if not context_id or context_id in set(assets.get("contexts", ())):
        issues.append("semantic reviewer context must be non-empty and distinct from writer/clarity")
    if issues:
        raise ProsePacketError("cannot assure semantic review: " + "; ".join(issues))
    assurance_path = manifest_path.parent / "assurance.json"
    if assurance_path.exists():
        raise ProsePacketError(f"semantic assurance already exists: {assurance_path}")
    assurance = {
        "schema_version": SEMANTIC_FIDELITY_ASSURANCE_SCHEMA_VERSION,
        "review_run_id": assets["run_id"],
        "mode": "independent",
        "reviewer_context_id": context_id,
        "dispatch_manifest_path": _workspace_relative(workspace, manifest_path),
        "dispatch_manifest_sha256": _file_sha256(manifest_path),
        "prompt_path": _workspace_relative(workspace, assets["prompt_path"]),
        "prompt_sha256": _file_sha256(assets["prompt_path"]),
        "output_path": _workspace_relative(workspace, assets["review_path"]),
        "output_sha256": _file_sha256(assets["review_path"]),
        "input_scope": "packet_and_draft_only",
        "isolation_declared": True,
    }
    assurance_path.write_text(
        json.dumps(assurance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {
        "review_run_id": assets["run_id"],
        "assurance": _workspace_relative(workspace, assurance_path),
    }


def validate_semantic_fidelity_review(
    workspace: Path,
    manifest_path: Path,
    assurance_path: Path,
    *,
    registered_ids: Iterable[str],
) -> list[str]:
    """Validate dispatch, distinct-context assurance, raw output, and judgment."""
    issues: list[str] = []
    try:
        manifest_path = _inside_workspace(workspace, manifest_path)
        assurance_path = _inside_workspace(workspace, assurance_path)
        manifest = _load_json(manifest_path)
        assurance = _load_json(assurance_path)
    except ProsePacketError as exc:
        return [str(exc)]
    dispatch_issues, assets = _validate_semantic_dispatch(
        workspace, manifest_path, manifest, require_output=True
    )
    issues.extend(dispatch_issues)
    assurance = _semantic_exact_keys(
        assurance,
        SEMANTIC_FIDELITY_ASSURANCE_KEYS,
        field="semantic assurance",
        issues=issues,
    )
    if assurance.get("schema_version") != SEMANTIC_FIDELITY_ASSURANCE_SCHEMA_VERSION:
        issues.append(
            "semantic assurance schema_version must be "
            + SEMANTIC_FIDELITY_ASSURANCE_SCHEMA_VERSION
        )
    if assurance.get("review_run_id") != manifest.get("review_run_id"):
        issues.append("semantic assurance review_run_id does not match dispatch")
    if assurance.get("mode") != "independent":
        issues.append("semantic assurance mode must be independent")
    if assurance.get("input_scope") != "packet_and_draft_only":
        issues.append("semantic assurance input_scope must be packet_and_draft_only")
    if assurance.get("isolation_declared") is not True:
        issues.append("semantic assurance must declare isolation=true")
    expected_manifest_path = _workspace_relative(workspace, manifest_path)
    if assurance.get("dispatch_manifest_path") != expected_manifest_path or assurance.get(
        "dispatch_manifest_sha256"
    ) != _file_sha256(manifest_path):
        issues.append("semantic assurance does not bind the actual dispatch manifest")
    reviewer_context = _text(assurance.get("reviewer_context_id"))
    if not reviewer_context or reviewer_context in set(assets.get("contexts", ())):
        issues.append("semantic reviewer context must be distinct from writer/clarity contexts")
    prompt_path = assets.get("prompt_path")
    review_path = assets.get("review_path")
    if isinstance(prompt_path, Path):
        if assurance.get("prompt_path") != _workspace_relative(workspace, prompt_path) or assurance.get(
            "prompt_sha256"
        ) != _file_sha256(prompt_path):
            issues.append("semantic assurance does not bind the actual prompt")
    if isinstance(review_path, Path) and review_path.is_file():
        if assurance.get("output_path") != _workspace_relative(workspace, review_path) or assurance.get(
            "output_sha256"
        ) != _file_sha256(review_path):
            issues.append("semantic assurance does not bind the actual raw review output")
        review = _load_json(review_path)
        issues.extend(
            _validate_semantic_fidelity_judgment(
                assets.get("packet"),
                assets.get("draft", ""),
                review,
                registered_ids=registered_ids,
                review_run_id=_text(manifest.get("review_run_id")),
            )
        )
    return issues


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProsePacketError(f"cannot read JSON from {path}: {exc}") from exc


def _inside_workspace(workspace: Path, path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as exc:
        raise ProsePacketError("ProsePacket paths must stay inside the workspace") from exc
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("workspace", type=Path)
    compile_parser.add_argument("request", type=Path)
    compile_parser.add_argument("--output", type=Path)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("workspace", type=Path)
    validate_parser.add_argument("packet", type=Path)
    fidelity_parser = subparsers.add_parser("fidelity")
    fidelity_parser.add_argument("workspace", type=Path)
    fidelity_parser.add_argument("packet", type=Path)
    fidelity_parser.add_argument("draft", type=Path)
    semantic_dispatch_parser = subparsers.add_parser("semantic-dispatch")
    semantic_dispatch_parser.add_argument("workspace", type=Path)
    semantic_dispatch_parser.add_argument("packet", type=Path)
    semantic_dispatch_parser.add_argument("draft", type=Path)
    semantic_dispatch_parser.add_argument("--writer-context-id", required=True)
    semantic_dispatch_parser.add_argument("--clarity-context-id", required=True)
    semantic_dispatch_parser.add_argument("--review-run-id")
    semantic_dispatch_parser.add_argument("--output-dir", type=Path)
    semantic_assure_parser = subparsers.add_parser("semantic-assure")
    semantic_assure_parser.add_argument("workspace", type=Path)
    semantic_assure_parser.add_argument("manifest", type=Path)
    semantic_assure_parser.add_argument("--reviewer-context-id", required=True)
    semantic_parser = subparsers.add_parser("semantic-fidelity")
    semantic_parser.add_argument("workspace", type=Path)
    semantic_parser.add_argument("manifest", type=Path)
    semantic_parser.add_argument("assurance", type=Path)
    compression_parser = subparsers.add_parser("compression")
    compression_parser.add_argument("workspace", type=Path)
    compression_parser.add_argument("packet", type=Path)
    compression_parser.add_argument("writer_draft", type=Path)
    compression_parser.add_argument("compressed_draft", type=Path)
    clarity_parser = subparsers.add_parser("clarity")
    clarity_parser.add_argument("workspace", type=Path)
    clarity_parser.add_argument("packet", type=Path)
    clarity_parser.add_argument("writer_draft", type=Path)
    clarity_parser.add_argument("edited_draft", type=Path)
    clarity_parser.add_argument("ledger", type=Path)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    if not workspace.is_dir():
        print(f"FAIL: workspace does not exist: {workspace}")
        return 2
    registered = discover_registered_ids(workspace)
    try:
        if args.command == "compile":
            request_path = _inside_workspace(workspace, args.request)
            request_payload = _load_json(request_path)
            validate_workspace_context_anchors(workspace, request_payload)
            output = args.output or (workspace / ".avereth-prose" / "prose_packet.json")
            output = _inside_workspace(workspace, output)
            packet = compile_prose_packet(
                request_payload,
                registered_ids=registered,
                accepted_result_claims=_result_claims_for_payload(
                    workspace, request_payload
                ),
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            temporary = output.with_suffix(output.suffix + ".tmp")
            temporary.write_text(
                json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            temporary.replace(output)
            print(json.dumps({"status": "PASS", "packet": output.relative_to(workspace).as_posix()}, ensure_ascii=False))
            return 0
        if args.command == "semantic-dispatch":
            packet_argument = args.packet if args.packet.is_absolute() else workspace / args.packet
            draft_argument = args.draft if args.draft.is_absolute() else workspace / args.draft
            validate_workspace_context_anchors(
                workspace,
                _load_json(_inside_workspace(workspace, packet_argument)),
            )
            output_argument = args.output_dir
            if output_argument is not None and not output_argument.is_absolute():
                output_argument = workspace / output_argument
            result = dispatch_semantic_fidelity_review(
                workspace,
                packet_argument,
                draft_argument,
                registered_ids=registered,
                writer_context_id=args.writer_context_id,
                clarity_context_id=args.clarity_context_id,
                review_run_id=args.review_run_id,
                output_dir=output_argument,
            )
            print(json.dumps({"status": "PASS", **result}, ensure_ascii=False))
            return 0
        if args.command == "semantic-assure":
            manifest_argument = (
                args.manifest if args.manifest.is_absolute() else workspace / args.manifest
            )
            result = create_semantic_fidelity_assurance(
                workspace,
                manifest_argument,
                reviewer_context_id=args.reviewer_context_id,
            )
            print(json.dumps({"status": "PASS", **result}, ensure_ascii=False))
            return 0
        if args.command == "semantic-fidelity":
            manifest_argument = (
                args.manifest if args.manifest.is_absolute() else workspace / args.manifest
            )
            assurance_argument = (
                args.assurance
                if args.assurance.is_absolute()
                else workspace / args.assurance
            )
            issues = validate_semantic_fidelity_review(
                workspace,
                manifest_argument,
                assurance_argument,
                registered_ids=registered,
            )
            if issues:
                print("FAIL")
                for issue in issues:
                    print(f"- {issue}")
                return 1
            print("PASS")
            return 0
        packet_path = _inside_workspace(workspace, args.packet)
        packet = _load_json(packet_path)
        validate_workspace_context_anchors(workspace, packet)
        accepted_result_claims = _result_claims_for_payload(workspace, packet)
        if args.command == "fidelity":
            draft_path = _inside_workspace(workspace, args.draft)
            try:
                draft = draft_path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                raise ProsePacketError(f"cannot read draft from {draft_path}: {exc}") from exc
            issues = validate_draft_fidelity(
                packet,
                draft,
                registered_ids=registered,
                accepted_result_claims=accepted_result_claims,
            )
        elif args.command in {"compression", "clarity"}:
            writer_path = _inside_workspace(workspace, args.writer_draft)
            edited_argument = (
                args.compressed_draft if args.command == "compression" else args.edited_draft
            )
            edited_path = _inside_workspace(workspace, edited_argument)
            try:
                writer_draft = writer_path.read_text(encoding="utf-8-sig")
                edited_draft = edited_path.read_text(encoding="utf-8-sig")
            except OSError as exc:
                raise ProsePacketError(f"cannot read clarity input: {exc}") from exc
            if args.command == "compression":
                issues = validate_compression(
                    packet,
                    writer_draft,
                    edited_draft,
                    registered_ids=registered,
                    accepted_result_claims=accepted_result_claims,
                )
            else:
                ledger_path = _inside_workspace(workspace, args.ledger)
                result = check_clarity(
                    packet,
                    writer_draft,
                    edited_draft,
                    _load_json(ledger_path),
                    registered_ids=registered,
                    accepted_result_claims=accepted_result_claims,
                )
                issues = list(result.issues)
                for warning in result.warnings:
                    print(f"WARNING: {warning}")
        else:
            issues = validate_prose_packet(
                packet,
                registered_ids=registered,
                accepted_result_claims=accepted_result_claims,
            )
    except ProsePacketError as exc:
        print(f"FAIL: {exc}")
        return 1
    if issues:
        print("FAIL")
        for issue in issues:
            print(f"- {issue}")
        return 1
    if args.command == "fidelity" and _claim_realization_mode(packet) == "semantic":
        print("PASS: deterministic fidelity; Semantic Fidelity Gate remains required")
    else:
        print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
