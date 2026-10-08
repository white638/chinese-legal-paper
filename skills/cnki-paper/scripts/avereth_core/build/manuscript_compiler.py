"""Avereth Manuscript Compiler (AMC), a derived build-stage projection.

AMC compiles a global manuscript contract into a section/move dependency graph.
It never owns research facts, controller state, receipts, or completion truth.
The local ProsePacket v2 firewall remains the only handoff to isolated prose
agents; this module plans and synchronizes units above that unchanged boundary.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import stat
import sys
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree

from ..version import VERSION
from .manuscript import ManuscriptSelectionError, select_manuscript


CONTRACT_SCHEMA_VERSION = "avereth-manuscript-contract/v1"
IR_SCHEMA_VERSION = "avereth-manuscript-ir/v1"
TRACE_SCHEMA_VERSION = "avereth-manuscript-trace/v1"
STALE_SCHEMA_VERSION = "avereth-manuscript-stale/v1"
REBUILD_SCHEMA_VERSION = "avereth-manuscript-rebuild-proof/v1"
LEGACY_ARCHIVE_SCHEMA_VERSION = "avereth-manuscript-legacy-view-archive/v1"
PROFILE_SCHEMA_VERSION = "avereth-manuscript-profile/v1"
SUPPORTED_PROFILE = "empirical-social-science"
HUMANITIES_PROFILE = "humanities-argument"
# Installed manuscript profiles: genre id -> profile file under references/manuscript-profiles.
PROFILE_FILES: dict[str, str] = {
    SUPPORTED_PROFILE: "empirical-social-science-v1.json",
    HUMANITIES_PROFILE: "humanities-argument-v1.json",
}
SUPPORTED_PROFILES: tuple[str, ...] = tuple(PROFILE_FILES)
# research_design.json method_routes[].family values that never carry data/estimation sections.
NON_EMPIRICAL_DESIGN_FAMILIES = frozenset({"interpretive", "normative", "theory_generation", "review"})
CONFIG_PROFILE_KEY = "manuscript_profile"

MANUSCRIPT_ROOT_REL = Path(".avereth-prose/manuscript")
CONTRACT_REL = MANUSCRIPT_ROOT_REL / "manuscript_contract.json"
IR_REL = MANUSCRIPT_ROOT_REL / "manuscript_ir.json"
STALE_REL = MANUSCRIPT_ROOT_REL / "stale_manifest.json"
REBUILD_REL = MANUSCRIPT_ROOT_REL / "rebuild_manifest.json"
LEGACY_ARCHIVE_ROOT_REL = MANUSCRIPT_ROOT_REL / "legacy-view-archives"
TRACE_REL = Path("manuscript_trace_manifest.json")

VIEW_RELS = (
    Path("section_blueprints.md"),
    Path("writing_rationale_matrix.md"),
    Path("promise_delivery_matrix.md"),
    Path("claim_lifecycle_matrix.md"),
    Path("reader_state_report.md"),
    Path("cross_section_sync_report.md"),
)

RELATIONS = frozenset(
    {
        "motivates",
        "defines",
        "operationalizes",
        "tests",
        "supports",
        "qualifies",
        "contradicts",
        "updates",
        "summarizes",
        "visualizes",
        "returns_to",
    }
)
ARGUMENT_ACTIONS = frozenset(
    {"POSE", "PRESS", "DISTINGUISH", "REVISE", "ADVANCE", "RESOLVE", "RETURN"}
)
EPISTEMIC_HOOK_DELAY_SPANS = frozenset(
    {"same_move", "same_section", "next_answer_section"}
)
SECTION_FOCUS_FIELDS = ("argument_role", "serves_promise_refs", "if_removed")
PROOF_FIELDS = ("required_authority_refs", "warrant", "failure_consequence")
PROOF_BASIS_KINDS = frozenset({"evidence", "source", "material", "result", "design", "literature"})
LIFECYCLE_STAGES = (
    "introduced",
    "motivated",
    "specified",
    "operationalized",
    "evaluated",
    "interpreted",
    "summarized",
)
IDENTITY_GROUPS = {
    "research_question": "research_question_ref",
    "claims": "main_claim_refs",
    "contribution": "contribution_refs",
    "design": "design_refs",
    "results": "result_refs",
    "scope": "scope_refs",
    "literature": "literature_refs",
}
INFERENCE_RANK = {
    "descriptive": 1,
    "interpretive": 1,
    "operational": 1,
    "normative": 1,
    "review_synthesis": 1,
    "association": 2,
    "associational": 2,
    "prediction": 2,
    "predictive": 2,
    "causal_mechanism": 3,
    "causal_effect": 3,
}
IDENTITY_GATE_CODES = {
    "research_question": "MS-RQ-IDENTITY",
    "claims": "MS-CLAIM-IDENTITY",
    "contribution": "MS-CONTRIBUTION-IDENTITY",
    "design": "MS-DESIGN-IDENTITY",
    "results": "MS-RESULT-IDENTITY",
    "scope": "MS-SCOPE-IDENTITY",
    "literature": "MS-LITERATURE-IDENTITY",
}
REBUILD_EVIDENCE_KINDS = frozenset(
    {
        "prose_packet",
        "writer_draft",
        "clarity_draft",
        "clarity_ledger",
        "semantic_dispatch",
        "semantic_assurance",
        "section_output",
    }
)
REBUILD_OUTPUT_KINDS = frozenset({"writer_draft", "clarity_draft", "section_output"})
REBUILD_REQUIRED_KINDS = frozenset(
    {
        "prose_packet",
        "writer_draft",
        "clarity_draft",
        "clarity_ledger",
        "semantic_dispatch",
        "semantic_assurance",
    }
)
DERIVED_AUTHORITY_PREFIXES = (
    ".avereth-prose/",
    "final_paper/",
    "submission_package/",
    "review_prompts/",
    "review_outputs/",
    "review_response/",
    "translation_en/",
    "translation_zh/",
)

# Scientific authority paths are an implementation-controlled allowlist, not a
# contract-controlled escape hatch.  Every path is also checked against the
# typed workflow registry and must remain canonical and pre-build.
AUTHORITY_SOURCE_RULES: Mapping[str, Mapping[str, Mapping[str, Any]]] = {
    "research_question": {
        "confirmed_motivation.md": {"selector_type": "whole_file"},
    },
    "claim": {
        "research_design.json": {
            "selector_type": "json_object_id",
            "containers": frozenset({"claims", "hypotheses", "propositions"}),
            "id_keys": frozenset({"id", "claim_id", "hypothesis_id", "proposition_id"}),
        },
    },
    "evidence": {
        "research_design.json": {
            "selector_type": "json_object_id",
            "containers": frozenset({"evidence"}),
            "id_keys": frozenset({"id", "evidence_id"}),
        },
    },
    "source": {
        "reference_materials/literature_registry.json": {
            "selector_type": "json_object_id",
            "containers": frozenset({"sources"}),
            "id_keys": frozenset({"id", "source_id"}),
        },
    },
    "material": {
        "reference_materials/research_material_registry.json": {
            "selector_type": "json_object_id",
            "containers": frozenset({"materials"}),
            "id_keys": frozenset({"id", "material_id"}),
        },
    },
    "contribution": {
        "confirmed_contribution.md": {"selector_type": "whole_file"},
    },
    "design": {
        "research_design.json": {"selector_type": "whole_file"},
    },
    "result": {
        "method_execution.json": {
            "selector_type": "json_object_id",
            "containers": frozenset({"results"}),
            "id_keys": frozenset({"id", "result_id"}),
        },
    },
    "scope": {
        "research_design.json": {"selector_type": "whole_file"},
    },
    "literature": {
        "literature_analysis.json": {"selector_type": "whole_file"},
    },
}


class ManuscriptCompilerError(ValueError):
    """Raised when a compiler action would create or accept an invalid view."""

    def __init__(self, message: str, issues: Iterable["CompilerIssue"] = ()) -> None:
        super().__init__(message)
        self.issues = tuple(issues)


@dataclass(frozen=True)
class CompilerIssue:
    code: str
    message: str
    path: str = ""

    def as_dict(self) -> dict[str, str]:
        payload = {"code": self.code, "message": self.message}
        if self.path:
            payload["path"] = self.path
        return payload


@dataclass(frozen=True)
class Compilation:
    contract: dict[str, Any] | None
    profile: dict[str, Any] | None
    ir: dict[str, Any] | None
    issues: tuple[CompilerIssue, ...]
    stale: dict[str, Any]

    @property
    def valid(self) -> bool:
        return self.ir is not None and not self.issues and self.stale.get("status") == "CURRENT"

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "avereth-manuscript-compilation/v1",
            "status": "PASS" if self.valid else "FAIL",
            "issues": [issue.as_dict() for issue in self.issues],
            "stale": self.stale,
            "ir": self.ir,
        }


def compiler_applies(config: Mapping[str, Any] | None) -> bool:
    """Return whether AMC is mandatory for the active profile.

    Legacy manuscript-audit workspaces can remain audit-only because they may
    lack reconstructable design/execution authorities. Full-paper and revision
    builds must explicitly initialize and baseline AMC after migration.
    """

    profile = str((config or {}).get("task_profile") or "full_paper").strip()
    return profile in {"full_paper", "manuscript_revision"}


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[3]


def profile_path(profile_id: str = SUPPORTED_PROFILE) -> Path:
    file_name = PROFILE_FILES.get(str(profile_id or "").strip() or SUPPORTED_PROFILE)
    if file_name is None:
        raise ManuscriptCompilerError(
            f"unsupported manuscript profile: {profile_id}; supported: {', '.join(SUPPORTED_PROFILES)}"
        )
    return _skill_root() / "references" / "manuscript-profiles" / file_name


def select_profile_id(config: Mapping[str, Any] | None, design: Mapping[str, Any] | None) -> str:
    """Choose the manuscript profile for a new contract.

    An explicit ``workflow_config.manuscript_profile`` always wins. Otherwise a
    research design whose primary method routes are all non-empirical
    (interpretive, normative, theory_generation, review, or ``empirical: false``)
    selects the humanities-argument profile. Any empirical route, or a design
    without typed routes, keeps the empirical social-science profile so existing
    workspaces are unaffected. Historical or case-process work that argues from
    sources rather than estimates must opt in explicitly.
    """

    explicit = str((config or {}).get(CONFIG_PROFILE_KEY) or "").strip()
    if explicit:
        if explicit not in PROFILE_FILES:
            raise ManuscriptCompilerError(
                f"unsupported manuscript profile: {explicit}; supported: {', '.join(SUPPORTED_PROFILES)}"
            )
        return explicit
    routes = [item for item in ((design or {}).get("method_routes") or []) if isinstance(item, dict)]
    primary = [item for item in routes if str(item.get("role") or "").strip() in {"", "primary"}] or routes
    if primary and all(
        item.get("empirical") is False or str(item.get("family") or "").strip() in NON_EMPIRICAL_DESIGN_FAMILIES
        for item in primary
    ):
        return HUMANITIES_PROFILE
    return SUPPORTED_PROFILE


def implementation_paths() -> tuple[Path, ...]:
    """Files whose changes invalidate a recorded build action."""

    root = _skill_root()
    return (
        Path(__file__).resolve(),
        *(profile_path(profile_id) for profile_id in SUPPORTED_PROFILES),
        root / "references" / "schemas" / "avereth-manuscript-contract-v1.schema.json",
        root / "references" / "schemas" / "avereth-manuscript-ir-v1.schema.json",
        root / "references" / "schemas" / "avereth-manuscript-rebuild-proof-v1.schema.json",
    )


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def _is_reparse_point(path: Path) -> bool:
    try:
        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _safe_workspace_path(outdir: Path, raw: str | Path) -> Path:
    root = outdir.resolve()
    candidate = Path(raw)
    unresolved = candidate if candidate.is_absolute() else outdir / candidate
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path must stay inside the paper workspace") from exc
    try:
        relative_unresolved = unresolved.absolute().relative_to(Path(outdir).absolute())
    except ValueError:
        relative_unresolved = resolved.relative_to(root)
    current = Path(outdir).absolute()
    for part in relative_unresolved.parts[:-1]:
        current /= part
        if not current.exists() or not _is_reparse_point(current):
            continue
        try:
            current.resolve().relative_to(root)
        except ValueError as exc:
            raise ValueError("path crosses a junction or reparse point outside the paper workspace") from exc
    return resolved


def _canonical_workspace_relative(outdir: Path, raw: str | Path) -> Path:
    """Return a workspace-relative path after physical-path containment checks.

    Temporary workspace roots can have multiple spellings on supported CI
    platforms (for example, /var versus /private/var or an 8.3 Windows alias).
    Always compare the physically resolved candidate with the physically
    resolved root; `_safe_workspace_path` retains the fail-closed symlink,
    junction, and reparse-point boundary.
    """

    root = Path(outdir).resolve()
    resolved = _safe_workspace_path(outdir, raw)
    try:
        return resolved.relative_to(root)
    except ValueError as exc:  # Defensive closure if platform resolution drifts.
        raise ValueError("path must stay inside the paper workspace") from exc


def _schema_type_matches(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _schema_pointer(root: Mapping[str, Any], reference: str) -> Mapping[str, Any] | None:
    if not reference.startswith("#/"):
        return None
    current: Any = root
    for token in reference[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or token not in current:
            return None
        current = current[token]
    return current if isinstance(current, dict) else None


def _schema_node_issues(
    value: Any,
    schema: Mapping[str, Any],
    *,
    root: Mapping[str, Any],
    path: str,
) -> list[str]:
    reference = schema.get("$ref")
    if isinstance(reference, str):
        resolved = _schema_pointer(root, reference)
        if resolved is None:
            return [f"{path}: unresolved schema reference {reference}"]
        return _schema_node_issues(value, resolved, root=root, path=path)
    alternatives = schema.get("oneOf") or schema.get("anyOf")
    if isinstance(alternatives, list):
        matches = [
            option
            for option in alternatives
            if isinstance(option, dict)
            and not _schema_node_issues(value, option, root=root, path=path)
        ]
        expected = 1 if "oneOf" in schema else None
        if not matches or (expected == 1 and len(matches) != 1):
            return [f"{path}: value does not match the registered alternative schema shape"]
        return []
    issues: list[str] = []
    expected_type = schema.get("type")
    type_ok = (
        _schema_type_matches(value, expected_type)
        if isinstance(expected_type, str)
        else any(_schema_type_matches(value, item) for item in expected_type if isinstance(item, str))
        if isinstance(expected_type, list)
        else True
    )
    if not type_ok:
        return [f"{path}: expected JSON type {expected_type}"]
    if "const" in schema and value != schema["const"]:
        issues.append(f"{path}: value must equal {schema['const']!r}")
    allowed = schema.get("enum")
    if isinstance(allowed, list) and value not in allowed:
        issues.append(f"{path}: value is not in the registered enum")
    if isinstance(value, str):
        minimum = schema.get("minLength")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(f"{path}: string is shorter than {minimum}")
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.search(pattern, value) is None:
            issues.append(f"{path}: string does not match {pattern}")
        if schema.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is None or parsed.tzinfo is None:
                issues.append(f"{path}: string is not an RFC 3339 date-time")
    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    issues.append(f"{path}: missing required property {key}")
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, child in properties.items():
                if key in value and isinstance(child, dict):
                    issues.extend(_schema_node_issues(value[key], child, root=root, path=f"{path}.{key}"))
            if schema.get("additionalProperties") is False:
                for key in sorted(set(value) - set(properties)):
                    issues.append(f"{path}: unexpected property {key}")
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(f"{path}: array has fewer than {minimum} items")
        if schema.get("uniqueItems") is True:
            canonical = [json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in value]
            if len(canonical) != len(set(canonical)):
                issues.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(_schema_node_issues(item, item_schema, root=root, path=f"{path}[{index}]"))
    return issues


def _registered_schema_issues(
    payload: Mapping[str, Any],
    *,
    schema_name: str,
    code: str,
    artifact_path: Path,
) -> list[CompilerIssue]:
    path = _skill_root() / "references" / "schemas" / schema_name
    try:
        schema = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [CompilerIssue(code, f"registered schema is unavailable: {exc}")]
    return [
        CompilerIssue(code, message, artifact_path.as_posix())
        for message in _schema_node_issues(payload, schema, root=schema, path="$")
    ]


def _contract_schema_issues(contract: Mapping[str, Any]) -> list[CompilerIssue]:
    return _registered_schema_issues(
        contract,
        schema_name="avereth-manuscript-contract-v1.schema.json",
        code="MS-CONTRACT-SCHEMA",
        artifact_path=CONTRACT_REL,
    )


def _rebuild_schema_issues(payload: Mapping[str, Any]) -> list[CompilerIssue]:
    return _registered_schema_issues(
        payload,
        schema_name="avereth-manuscript-rebuild-proof-v1.schema.json",
        code="MS-REBUILD-PROOF-SCHEMA",
        artifact_path=REBUILD_REL,
    )


def _text(value: Any) -> str:
    return str(value or "").strip()


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _unique_id_issues(items: list[Any], key: str, label: str) -> list[CompilerIssue]:
    issues: list[CompilerIssue] = []
    values: list[str] = []
    for index, item in enumerate(items):
        value = _text(item.get(key)) if isinstance(item, dict) else ""
        if not value:
            issues.append(CompilerIssue("MS-CONTRACT-SHAPE", f"{label} requires {key}", f"{label}[{index}]"))
        else:
            values.append(value)
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        issues.append(CompilerIssue("MS-DUPLICATE-ID", f"duplicate {label} identities: {', '.join(duplicates)}"))
    return issues


def _recursive_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _recursive_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _recursive_objects(child)


def _objects_with_id(payload: Any, identifier: str, keys: list[str]) -> list[dict[str, Any]]:
    return [
        item
        for item in _recursive_objects(payload)
        if any(_text(item.get(key)) == identifier for key in keys)
    ]


def _objects_in_named_collections(
    payload: Any,
    identifier: str,
    *,
    containers: frozenset[str],
    keys: frozenset[str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for item in _recursive_objects(payload):
        for container_name in containers:
            records = item.get(container_name)
            if not isinstance(records, list):
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                if any(_text(record.get(key)) == identifier for key in keys):
                    matches.append(record)
    # A nested collection can be reached through more than one recursive parent
    # only by object identity; remove such traversal duplicates without merging
    # genuinely distinct records carrying the same registered identifier.
    unique: list[dict[str, Any]] = []
    seen: set[int] = set()
    for record in matches:
        marker = id(record)
        if marker not in seen:
            seen.add(marker)
            unique.append(record)
    return unique


def _canonical_claim_semantics(record: Mapping[str, Any]) -> dict[str, Any] | None:
    proposition = _text(
        record.get("canonical_proposition")
        or record.get("statement")
        or record.get("text")
    )
    strength = _text(record.get("strength") or record.get("type")).lower()
    raw_atoms = record.get("protected_atoms")
    if not proposition or not strength or not isinstance(raw_atoms, dict):
        return None
    scalar_fields = (
        "subject",
        "relation",
        "direction",
        "polarity",
        "inferential_strength",
        "scope",
    )
    list_fields = ("protected_literals", "protected_numbers", "citation_anchors")
    if any(not _text(raw_atoms.get(field)) for field in scalar_fields):
        return None
    if any(not isinstance(raw_atoms.get(field), list) for field in list_fields):
        return None
    atoms: dict[str, Any] = {
        field: _text(raw_atoms.get(field)).lower()
        if field in {"polarity", "inferential_strength"}
        else _text(raw_atoms.get(field))
        for field in scalar_fields
    }
    atoms.update(
        {
            field: [_text(value) for value in _list(raw_atoms.get(field))]
            for field in list_fields
        }
    )
    return {
        "canonical_proposition": proposition,
        "strength": strength,
        "protected_atoms": atoms,
    }


def _collection_ids(payload: Mapping[str, Any], container_key: str) -> list[str]:
    identifier_keys = {
        "claims": ("id", "claim_id"),
        "hypotheses": ("id", "hypothesis_id", "claim_id"),
        "propositions": ("id", "proposition_id", "claim_id"),
        "results": ("id", "result_id"),
    }.get(container_key, ("id", f"{container_key.rstrip('s')}_id"))
    values: list[str] = []
    for item in _recursive_objects(payload):
        container = item.get(container_key)
        if not isinstance(container, list):
            continue
        for record in container:
            if not isinstance(record, dict):
                continue
            identifier = next(
                (_text(record.get(key)) for key in identifier_keys if _text(record.get(key))),
                "",
            )
            if identifier:
                values.append(identifier)
    return list(dict.fromkeys(values))


def _resolve_authority(
    outdir: Path,
    binding: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, CompilerIssue | None]:
    ref_id = _text(binding.get("ref_id"))
    authority_kind = _text(binding.get("authority_kind"))
    source_raw = _text(binding.get("source_path"))
    try:
        source = _safe_workspace_path(outdir, source_raw)
    except ValueError as exc:
        return None, CompilerIssue("MS-AUTHORITY-PATH", str(exc), source_raw)
    relative_source = _canonical_workspace_relative(outdir, source).as_posix()
    normalized_source = relative_source.casefold()
    if any(
        normalized_source == prefix.casefold().rstrip("/")
        or normalized_source.startswith(prefix.casefold())
        for prefix in DERIVED_AUTHORITY_PREFIXES
    ):
        return None, CompilerIssue(
            "MS-AUTHORITY-DERIVED",
            "scientific authority cannot point into transient, manuscript, review, or generated-delivery output",
            source_raw,
        )
    try:
        from ..workflow_registry import ARTIFACT_DEFINITIONS, STAGE_ORDER

        definitions = {item.path.casefold(): item for item in ARTIFACT_DEFINITIONS}
        definition = definitions.get(normalized_source)
    except (ImportError, AttributeError):
        definition = None
        STAGE_ORDER = ()
    rules = AUTHORITY_SOURCE_RULES.get(authority_kind, {})
    rule = next(
        (value for path, value in rules.items() if path.casefold() == normalized_source),
        None,
    )
    if definition is None or rule is None:
        return None, CompilerIssue(
            "MS-AUTHORITY-SOURCE",
            "scientific authority must use the implementation-controlled (authority_kind, registry path, selector) allowlist",
            source_raw,
        )
    if (
        definition.authority != "canonical"
        or definition.owner_stage not in STAGE_ORDER
        or STAGE_ORDER.index(definition.owner_stage) >= STAGE_ORDER.index("build")
    ):
        return None, CompilerIssue(
            "MS-AUTHORITY-SOURCE",
            "scientific authority must be a canonical workflow artifact owned before build",
            source_raw,
        )
    if not source.is_file() or source.stat().st_size <= 0:
        return None, CompilerIssue("MS-AUTHORITY-MISSING", f"authority file is missing or empty for {ref_id}", source_raw)
    selector = binding.get("selector") if isinstance(binding.get("selector"), dict) else {}
    selector_type = _text(selector.get("type"))
    if selector_type != rule.get("selector_type"):
        return None, CompilerIssue(
            "MS-AUTHORITY-SOURCE",
            f"{authority_kind} authority at {relative_source} requires selector type {rule.get('selector_type')}",
            source_raw,
        )
    selected: Any = None
    if selector_type == "whole_file":
        selector_digest = _sha256(source)
    elif selector_type == "json_object_id":
        try:
            payload = _read_json(source)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return None, CompilerIssue("MS-AUTHORITY-JSON", f"cannot parse authority JSON for {ref_id}: {exc}", source_raw)
        identifier = _text(selector.get("id"))
        if identifier != ref_id:
            return None, CompilerIssue(
                "MS-AUTHORITY-IDENTITY",
                f"{authority_kind} selector id {identifier or '<missing>'} must exactly equal binding ref_id {ref_id or '<missing>'}",
                source_raw,
            )
        keys = frozenset(
            _text(value) for value in _list(selector.get("id_keys")) if _text(value)
        )
        allowed_keys = rule.get("id_keys")
        containers = rule.get("containers")
        if (
            not isinstance(allowed_keys, frozenset)
            or not isinstance(containers, frozenset)
            or not keys
            or not keys.issubset(allowed_keys)
        ):
            return None, CompilerIssue(
                "MS-AUTHORITY-SOURCE",
                f"{authority_kind} selector id_keys do not match the registered identity kind",
                source_raw,
            )
        matches = _objects_in_named_collections(
            payload,
            identifier,
            containers=containers,
            keys=keys,
        )
        if len(matches) != 1:
            return None, CompilerIssue(
                "MS-AUTHORITY-SELECTOR",
                f"authority selector for {ref_id} resolved {len(matches)} objects; expected exactly one",
                source_raw,
            )
        selected = matches[0]
        selected_identities = {
            key: _text(selected.get(key))
            for key in sorted(allowed_keys)
            if _text(selected.get(key))
        }
        conflicting_identities = {
            key: value
            for key, value in selected_identities.items()
            if value != ref_id
        }
        if not selected_identities or conflicting_identities:
            detail = ", ".join(
                f"{key}={value}" for key, value in conflicting_identities.items()
            ) or "no registered identity field"
            return None, CompilerIssue(
                "MS-AUTHORITY-IDENTITY",
                f"selected {authority_kind} authority for {ref_id} has ambiguous registered identity fields: {detail}",
                source_raw,
            )
        selector_digest = _digest(selected)
    else:
        return None, CompilerIssue("MS-AUTHORITY-SELECTOR", f"unsupported selector for {ref_id}: {selector_type or '<missing>'}", source_raw)
    snapshot: dict[str, Any] = {
        "ref_id": ref_id,
        "authority_kind": authority_kind,
        "source_path": relative_source,
        "source_sha256": _sha256(source),
        "selector": dict(selector),
        "selector_digest": selector_digest,
    }
    if authority_kind == "claim" and isinstance(selected, dict):
        semantics = _canonical_claim_semantics(selected)
        if semantics is None:
            return None, CompilerIssue(
                "MS-CLAIM-SEMANTICS",
                f"Claim authority {ref_id} must register canonical proposition, strength, and complete protected_atoms before semantic prose rebuilding",
                source_raw,
            )
        snapshot["claim_semantic_digest"] = _digest(semantics)
    if authority_kind == "design" and source.suffix.lower() == ".json":
        try:
            design_payload = _read_json(source)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            design_payload = {}
        snapshot["formal_claim_refs"] = list(
            dict.fromkeys(
                _collection_ids(design_payload, "hypotheses")
                + _collection_ids(design_payload, "propositions")
            )
        )
    strength_field = _text(selector.get("inference_strength_field"))
    if strength_field and isinstance(selected, dict):
        snapshot["inference_ceiling"] = _text(selected.get(strength_field)).lower()
    return snapshot, None


def _identity_values(contract: Mapping[str, Any], group: str) -> list[str]:
    identity = contract.get("global_identity") if isinstance(contract.get("global_identity"), dict) else {}
    field = IDENTITY_GROUPS[group]
    raw = identity.get(field)
    return [_text(raw)] if field == "research_question_ref" else [_text(value) for value in _list(raw) if _text(value)]


def _context_anchor_bindings(outdir: Path) -> dict[str, str]:
    """Read valid Context Anchor bindings from the existing evidence-bank projection."""

    path = outdir / "evidence_bank.md"
    try:
        lines = path.read_text(encoding="utf-8-sig", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return {}

    def cells(line: str) -> list[str]:
        text = line.strip().strip("|")
        return [item.replace(r"\|", "|").strip() for item in re.split(r"(?<!\\)\|", text)]

    for index, line in enumerate(lines[:-1]):
        separator_cells = cells(lines[index + 1])
        if (
            not line.lstrip().startswith("|")
            or not separator_cells
            or not all(re.fullmatch(r":?-{3,}:?", value.replace(" ", "")) for value in separator_cells)
        ):
            continue
        headers = cells(line)
        normalized = [re.sub(r"[^a-z0-9]+", "", value.lower()) for value in headers]
        aliases = {
            "anchor": {"anchorid", "contextanchorid"},
            "authority": {"authorityref", "authorityreference"},
            "type": {"type", "anchortype"},
            "locator": {"locator"},
            "content": {"exactspanknowndetails", "exactspanorknowndetails"},
            "problem": {"originalproblem"},
            "logic": {"logicalcontext"},
            "qualifiers": {"protectedqualifiers"},
            "function": {"manuscriptfunction"},
            "status": {"status"},
        }
        positions: dict[str, int] = {}
        for label, candidates in aliases.items():
            position = next((number for number, value in enumerate(normalized) if value in candidates), None)
            if position is None:
                break
            positions[label] = position
        if len(positions) != len(aliases):
            continue
        bindings: dict[str, str] = {}
        duplicates: set[str] = set()
        for row_line in lines[index + 2 :]:
            if not row_line.lstrip().startswith("|"):
                break
            row = cells(row_line)
            if max(positions.values()) >= len(row):
                continue
            status = _text(row[positions["status"]]).lower()
            if status not in {"content-verified", "内容已核验"}:
                continue
            anchor_type = _text(row[positions["type"]]).lower()
            if anchor_type not in {"scene", "case", "场景", "案例"}:
                continue
            required_values = (
                row[positions["locator"]],
                row[positions["content"]],
                row[positions["problem"]],
                row[positions["logic"]],
                row[positions["qualifiers"]],
                row[positions["function"]],
            )
            if any(not _text(value) for value in required_values):
                continue
            anchor_id = _text(row[positions["anchor"]]).upper()
            authority_ref = _text(row[positions["authority"]])
            if anchor_id and authority_ref:
                if anchor_id in bindings or anchor_id in duplicates:
                    bindings.pop(anchor_id, None)
                    duplicates.add(anchor_id)
                else:
                    bindings[anchor_id] = authority_ref
        return bindings
    return {}


def _validate_contract(
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    snapshots: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
    context_anchors: Mapping[str, str] | None = None,
) -> list[CompilerIssue]:
    issues: list[CompilerIssue] = []
    if contract.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        issues.append(CompilerIssue("MS-CONTRACT-SCHEMA", f"manuscript contract must use {CONTRACT_SCHEMA_VERSION}", CONTRACT_REL.as_posix()))
    if contract.get("compiler_mode") != "build_projection":
        issues.append(CompilerIssue("MS-CONTRACT-AUTHORITY", "compiler_mode must be build_projection; AMC cannot become a scientific authority"))
    genre_profile = _text(contract.get("genre_profile"))
    if genre_profile not in PROFILE_FILES:
        issues.append(
            CompilerIssue(
                "MS-PROFILE",
                f"unsupported manuscript profile: {genre_profile or '<missing>'}; supported: {', '.join(SUPPORTED_PROFILES)}",
            )
        )
    if profile.get("schema_version") != PROFILE_SCHEMA_VERSION or _text(profile.get("profile_id")) != genre_profile:
        issues.append(CompilerIssue("MS-PROFILE", "installed manuscript profile does not match the contract genre_profile"))
    compatible_versions = {
        _text(value) for value in _list(profile.get("compatible_contract_versions")) if _text(value)
    } or {_text(profile.get("profile_version"))}
    if _text(contract.get("profile_version")) not in compatible_versions:
        issues.append(CompilerIssue("MS-PROFILE-DRIFT", "contract profile_version differs from the installed profile"))

    bindings = _list(contract.get("authority_bindings"))
    sections = _list(contract.get("sections"))
    moves = _list(contract.get("moves"))
    promises = _list(contract.get("promises"))
    edges = _list(contract.get("cross_section_edges"))
    lifecycles = _list(contract.get("claim_lifecycle"))
    issues.extend(_unique_id_issues(bindings, "ref_id", "authority_bindings"))
    issues.extend(_unique_id_issues(sections, "section_id", "sections"))
    issues.extend(_unique_id_issues(moves, "move_id", "moves"))
    issues.extend(_unique_id_issues(promises, "promise_id", "promises"))
    issues.extend(_unique_id_issues(edges, "edge_id", "cross_section_edges"))
    if issues:
        return issues

    authority_ids = {_text(item.get("ref_id")) for item in bindings if isinstance(item, dict)}
    section_by_id = {_text(item.get("section_id")): item for item in sections if isinstance(item, dict)}
    move_by_id = {_text(item.get("move_id")): item for item in moves if isinstance(item, dict)}
    promise_by_id = {_text(item.get("promise_id")): item for item in promises if isinstance(item, dict)}
    profile_sections = {
        _text(item.get("semantic_role")): item
        for item in _list(profile.get("sections"))
        if isinstance(item, dict)
    }
    section_roles = [_text(item.get("semantic_role")) for item in sections if isinstance(item, dict)]
    expected_roles = list(profile_sections)
    if sorted(section_roles) != sorted(expected_roles) or len(section_roles) != len(set(section_roles)):
        issues.append(CompilerIssue("MS-SECTION-COVERAGE", "contract must contain each profile semantic_role exactly once"))
    section_order = {
        _text(item.get("section_id")): index
        for index, item in enumerate(sections)
        if isinstance(item, dict)
    }
    move_order = {
        _text(item.get("move_id")): index
        for index, item in enumerate(moves)
        if isinstance(item, dict)
    }

    global_identity = contract.get("global_identity") if isinstance(contract.get("global_identity"), dict) else {}
    expected_authority_kinds = {
        "research_question": "research_question",
        "claims": "claim",
        "contribution": "contribution",
        "design": "design",
        "results": "result",
        "scope": "scope",
        "literature": "literature",
    }
    for group, field in IDENTITY_GROUPS.items():
        refs = _identity_values(contract, group)
        if not refs:
            issues.append(CompilerIssue("MS-GLOBAL-IDENTITY", f"global_identity.{field} must be non-empty"))
        unknown = sorted(set(refs) - authority_ids)
        if unknown:
            issues.append(CompilerIssue("MS-UNKNOWN-AUTHORITY", f"global_identity.{field} references unknown authorities: {', '.join(unknown)}"))
        wrong_kind = sorted(
            ref
            for ref in refs
            if ref in snapshots
            and snapshots[ref].get("authority_kind") != expected_authority_kinds[group]
        )
        if wrong_kind:
            issues.append(
                CompilerIssue(
                    IDENTITY_GATE_CODES[group],
                    f"global_identity.{field} binds the wrong authority_kind: {', '.join(wrong_kind)}",
                )
            )
    research_ref = _text(global_identity.get("research_question_ref"))
    if research_ref and snapshots.get(research_ref, {}).get("authority_kind") != "research_question":
        issues.append(CompilerIssue("MS-RQ-IDENTITY", "research_question_ref must resolve to a research_question authority"))
    expected_claims = set(_identity_values(contract, "claims"))
    scientific_order = [_text(value) for value in _list(contract.get("scientific_commitment_order"))]
    expected_scientific_order = [_text(value) for value in _list(profile.get("scientific_commitment_order"))]
    if scientific_order != expected_scientific_order or len(scientific_order) != len(set(scientific_order)):
        issues.append(
            CompilerIssue(
                "MS-SCIENTIFIC-ORDER",
                "scientific_commitment_order must exactly match the installed profile",
            )
        )
    render_order = [_text(value) for value in _list(contract.get("render_order"))]
    expected_render_order = [_text(value) for value in _list(profile.get("render_order"))]
    if (
        render_order != expected_render_order
        or len(render_order) != len(set(render_order))
        or set(render_order) != set(section_roles)
    ):
        issues.append(
            CompilerIssue(
                "MS-RENDER-ORDER",
                "render_order must be unique, cover every semantic Section role, and exactly match the installed profile",
            )
        )

    ordered_sections = [item for item in sections if isinstance(item, dict)]
    narrative = contract.get("narrative_contract") if isinstance(contract.get("narrative_contract"), dict) else {}
    initial_state = _list(narrative.get("initial_reader_state"))
    final_state = _list(narrative.get("final_reader_update"))
    if not ordered_sections:
        issues.append(CompilerIssue("MS-SECTION-COVERAGE", "sections must not be empty"))
    else:
        if _list(ordered_sections[0].get("reader_state_before")) != initial_state:
            issues.append(CompilerIssue("MS-READER-STATE", "first section reader_state_before must equal narrative initial_reader_state"))
        for previous, current in zip(ordered_sections, ordered_sections[1:]):
            if _text(previous.get("reader_state_after_id")) != _text(current.get("reader_state_before_id")):
                issues.append(CompilerIssue("MS-READER-STATE", f"reader state ID breaks between {_text(previous.get('section_id'))} and {_text(current.get('section_id'))}"))
            if _list(previous.get("reader_state_after")) != _list(current.get("reader_state_before")):
                issues.append(CompilerIssue("MS-READER-STATE", f"reader state content breaks between {_text(previous.get('section_id'))} and {_text(current.get('section_id'))}"))
        if _list(ordered_sections[-1].get("reader_state_after")) != final_state:
            issues.append(CompilerIssue("MS-READER-STATE", "last section reader_state_after must equal narrative final_reader_update"))

    referenced_moves: list[str] = []
    for section in ordered_sections:
        section_id = _text(section.get("section_id"))
        role = _text(section.get("semantic_role"))
        for field in ("reader_state_before", "required_update", "reader_state_after"):
            if not _list(section.get(field)):
                issues.append(CompilerIssue("MS-READER-STATE", f"{section_id}.{field} must be non-empty"))
        if not _text(section.get("reader_question")):
            issues.append(CompilerIssue("MS-READER-STATE", f"{section_id}.reader_question must be non-empty"))
        move_refs = [_text(value) for value in _list(section.get("move_refs"))]
        referenced_moves.extend(move_refs)
        unknown = sorted(set(move_refs) - set(move_by_id))
        if unknown:
            issues.append(CompilerIssue("MS-MOVE-COVERAGE", f"{section_id} references unknown moves: {', '.join(unknown)}"))
        required_types = {
            _text(value.get("move_type"))
            for value in _list(profile_sections.get(role, {}).get("required_moves"))
            if isinstance(value, dict)
        }
        actual_types = {
            _text(move_by_id[ref].get("move_type"))
            for ref in move_refs
            if ref in move_by_id
        }
        missing_types = sorted(required_types - actual_types)
        if missing_types:
            issues.append(CompilerIssue("MS-MOVE-COVERAGE", f"{section_id} is missing required moves: {', '.join(missing_types)}"))
    if sorted(referenced_moves) != sorted(move_by_id):
        issues.append(CompilerIssue("MS-MOVE-COVERAGE", "every move must belong to exactly one section"))

    for move_id, move in move_by_id.items():
        section_ref = _text(move.get("section_ref"))
        if section_ref not in section_by_id or move_id not in _list(section_by_id.get(section_ref, {}).get("move_refs")):
            issues.append(CompilerIssue("MS-MOVE-COVERAGE", f"{move_id} section_ref is inconsistent"))
        if not _text(move.get("prose_packet_role")):
            issues.append(
                CompilerIssue(
                    "MS-MOVE-PACKET-ROLE",
                    f"{move_id} must declare the ProsePacket section role used by its build handoff",
                )
            )
        authority_refs = {_text(value) for value in _list(move.get("authority_refs"))}
        if not authority_refs:
            issues.append(CompilerIssue("MS-GLOBAL-IDENTITY", f"{move_id} must bind at least one authority"))
        unknown = sorted(authority_refs - authority_ids)
        if unknown:
            issues.append(CompilerIssue("MS-UNKNOWN-AUTHORITY", f"{move_id} references unknown authorities: {', '.join(unknown)}"))
        claim_refs = {_text(value) for value in _list(move.get("claim_refs"))}
        ghost_claims = sorted((claim_refs - expected_claims) | (claim_refs - authority_refs))
        if ghost_claims:
            issues.append(
                CompilerIssue(
                    "MS-NO-GHOST-CLAIM",
                    f"{move_id} carries unregistered or authority-unbound Claim refs: {', '.join(ghost_claims)}",
                )
            )
        for dependency in [_text(value) for value in _list(move.get("dependency_refs"))]:
            if dependency not in move_by_id:
                issues.append(CompilerIssue("MS-DEPENDENCY", f"{move_id} has unknown dependency {dependency}"))
        for promise_ref in [_text(value) for value in _list(move.get("promise_refs")) + _list(move.get("delivery_refs"))]:
            if promise_ref not in promise_by_id:
                issues.append(CompilerIssue("MS-PROMISE-DELIVERY", f"{move_id} references unknown promise {promise_ref}"))
        strength = _text(move.get("inference_strength")).lower()
        if strength and strength != "inherit":
            for claim_ref in [_text(value) for value in _list(move.get("claim_refs"))]:
                ceiling = _text(snapshots.get(claim_ref, {}).get("inference_ceiling")).lower()
                if ceiling and strength in INFERENCE_RANK and ceiling in INFERENCE_RANK and INFERENCE_RANK[strength] > INFERENCE_RANK[ceiling]:
                    issues.append(CompilerIssue("MS-CLAIM-STRENGTHENING", f"{move_id} raises {claim_ref} from {ceiling} to {strength}"))
        action = _text(move.get("argument_action")).upper()
        before = _text(move.get("problem_state_before"))
        after = _text(move.get("problem_state_after"))
        if action and action not in ARGUMENT_ACTIONS:
            issues.append(CompilerIssue("AP.MOTION.ACTION_INVALID", f"{move_id} has unsupported argument_action {action}"))
        if any((action, before, after)) and not all((action, before, after)):
            issues.append(
                CompilerIssue(
                    "AP.MOTION.STATE_INCOMPLETE",
                    f"{move_id} must bind argument_action with both problem_state_before and problem_state_after",
                )
            )
        if before and after and before == after:
            issues.append(CompilerIssue("AP.MOTION.NO_ADVANCE", f"{move_id} leaves the registered problem state unchanged"))
        scene = move.get("verified_scene")
        if scene is not None:
            if not isinstance(scene, dict):
                issues.append(CompilerIssue("AP.SCENE.UNBOUND", f"{move_id}.verified_scene must be an object"))
            else:
                scene_authority = _text(scene.get("authority_ref"))
                scene_anchor = _text(scene.get("anchor_id")).upper()
                anchor_authority = _text((context_anchors or {}).get(scene_anchor))
                if (
                    not scene_anchor
                    or scene_authority not in authority_refs
                    or not anchor_authority
                    or anchor_authority != scene_authority
                ):
                    issues.append(
                        CompilerIssue(
                            "AP.SCENE.UNBOUND",
                            f"{move_id} verified scene must bind an Anchor ID and one of the Move's registered authorities",
                        )
                    )
        resonance = _text(move.get("resonance_device")).lower()
        if resonance and resonance != "none":
            body_move = _text(move.get("body_explanation_move_ref"))
            body_authorities = {
                _text(value)
                for value in _list(move_by_id.get(body_move, {}).get("authority_refs"))
            }
            if (
                body_move not in move_by_id
                or body_move == move_id
                or authority_refs.isdisjoint(body_authorities)
            ):
                issues.append(
                    CompilerIssue(
                        "AP.TITLE.BODY_ANCHOR_MISSING",
                        f"{move_id} uses {resonance} but has no valid distinct Body Explanation Move",
                    )
                )

    rhetorical_profile = (
        profile.get("rhetorical_architecture")
        if isinstance(profile.get("rhetorical_architecture"), dict)
        else {}
    )
    distinguished = _text((config or {}).get("prose_mode")).lower() == "distinguished"
    current_contract = _text(contract.get("profile_version")) == _text(profile.get("profile_version"))
    if distinguished and current_contract:
        required_types = {
            _text(value)
            for value in _list(rhetorical_profile.get("distinguished_thought_move_types"))
            if _text(value)
        }
        for move_id, move in move_by_id.items():
            if _text(move.get("move_type")) in required_types and not all(
                _text(move.get(field))
                for field in ("argument_action", "problem_state_before", "problem_state_after")
            ):
                issues.append(
                    CompilerIssue(
                        "AP.MOTION.STATE_INCOMPLETE",
                        f"distinguished Move {move_id} must register its before-state, argument action, and after-state",
                    )
                )

    for promise_id, promise in promise_by_id.items():
        source = _text(promise.get("source_move_ref"))
        deliveries = [_text(value) for value in _list(promise.get("delivery_move_refs"))]
        if source not in move_by_id or not deliveries or any(value not in move_by_id for value in deliveries):
            issues.append(CompilerIssue("MS-PROMISE-DELIVERY", f"{promise_id} must bind one valid source and one or more valid delivery moves"))
        promised_authorities = {_text(value) for value in _list(promise.get("authority_refs"))}
        if not promised_authorities or not promised_authorities.issubset(authority_ids):
            issues.append(CompilerIssue("MS-PROMISE-DELIVERY", f"{promise_id} has missing or unknown authority refs"))
        for delivery in deliveries:
            delivered = {_text(value) for value in _list(move_by_id.get(delivery, {}).get("authority_refs"))}
            if delivered.isdisjoint(promised_authorities):
                issues.append(CompilerIssue("MS-PROMISE-DELIVERY", f"{promise_id} delivery {delivery} shares no promised authority identity"))
        if _text(promise.get("promise_type")).lower() == "epistemic_hook":
            if not deliveries:
                issues.append(CompilerIssue("AP.HOOK.UNPAID", f"{promise_id} has no delivery Move"))
                continue
            delay_span = _text(promise.get("delay_span")).lower()
            if delay_span not in EPISTEMIC_HOOK_DELAY_SPANS:
                issues.append(CompilerIssue("AP.HOOK.OVERDELAY", f"{promise_id} must declare a profile-supported delay_span"))
            source_section = _text(move_by_id.get(source, {}).get("section_ref"))
            source_index = section_order.get(source_section, -1)
            max_distance = int(rhetorical_profile.get("epistemic_hook_max_section_distance") or 3)
            for delivery in deliveries:
                delivery_section = _text(move_by_id.get(delivery, {}).get("section_ref"))
                delivery_index = section_order.get(delivery_section, -1)
                if (
                    move_order.get(delivery, -1) < move_order.get(source, -1)
                    or (delivery == source and delay_span != "same_move")
                ):
                    issues.append(CompilerIssue("AP.HOOK.ORDER_INVALID", f"{promise_id} delivery {delivery} does not follow its source Move"))
                    continue
                distance = delivery_index - source_index
                if (
                    (delay_span == "same_move" and delivery != source)
                    or (delay_span == "same_section" and distance != 0)
                    or (
                        delay_span == "next_answer_section"
                        and (distance <= 0 or distance > max_distance)
                    )
                ):
                    issues.append(
                        CompilerIssue(
                            "AP.HOOK.OVERDELAY",
                            f"{promise_id} delivery {delivery} exceeds its {delay_span} delay contract",
                        )
                    )

    lifecycle_by_claim = {
        _text(item.get("claim_ref")): item
        for item in lifecycles
        if isinstance(item, dict)
    }
    if set(lifecycle_by_claim) != expected_claims:
        issues.append(CompilerIssue("MS-CLAIM-LIFECYCLE", "claim_lifecycle must contain exactly one record for every main Claim ref"))
    for claim_ref, lifecycle in lifecycle_by_claim.items():
        for stage in LIFECYCLE_STAGES:
            refs = [_text(value) for value in _list(lifecycle.get(stage))]
            if not refs or any(ref not in move_by_id for ref in refs):
                issues.append(CompilerIssue("MS-CLAIM-LIFECYCLE", f"{claim_ref}.{stage} must bind one or more valid moves"))
            elif any(claim_ref not in _list(move_by_id[ref].get("claim_refs")) for ref in refs):
                issues.append(CompilerIssue("MS-CLAIM-LIFECYCLE", f"{claim_ref}.{stage} move does not carry the Claim identity"))
    formal_claims = {
        _text(value)
        for snapshot in snapshots.values()
        for value in _list(snapshot.get("formal_claim_refs"))
        if _text(value)
    }
    undisposed_formal = sorted(formal_claims - expected_claims)
    if undisposed_formal:
        issues.append(
            CompilerIssue(
                "MS-HYPOTHESIS-DISPOSITION",
                "registered hypotheses/propositions must enter the main Claim lifecycle: "
                + ", ".join(undisposed_formal),
            )
        )

    issues.extend(_validate_argument_focus(contract, profile, snapshots))
    graph_dependencies = _graph_dependencies(contract)
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source = _text(edge.get("source_ref"))
        target = _text(edge.get("target_ref"))
        relation = _text(edge.get("relation"))
        if source not in move_by_id or target not in move_by_id:
            issues.append(CompilerIssue("MS-DEPENDENCY", f"edge {_text(edge.get('edge_id'))} references an unknown move"))
        elif source == target:
            issues.append(CompilerIssue("MS-DEPENDENCY", f"edge {_text(edge.get('edge_id'))} cannot be self-referential"))
        elif relation != "returns_to":
            graph_dependencies[target].add(source)
        if relation not in RELATIONS:
            issues.append(CompilerIssue("MS-DEPENDENCY", f"unsupported edge relation: {relation}"))
        if relation == "returns_to" and source in move_by_id and target in move_by_id:
            source_scene = move_by_id[source].get("verified_scene")
            target_scene = move_by_id[target].get("verified_scene")
            edge_anchor = _text(edge.get("anchor_id"))
            source_anchor = _text(source_scene.get("anchor_id")) if isinstance(source_scene, dict) else ""
            target_anchor = _text(target_scene.get("anchor_id")) if isinstance(target_scene, dict) else ""
            if not source_anchor or not target_anchor:
                issues.append(CompilerIssue("AP.SCENE.UNBOUND", f"returns_to edge {_text(edge.get('edge_id'))} requires verified scenes at both Moves"))
            elif len({edge_anchor, source_anchor, target_anchor}) != 1:
                issues.append(CompilerIssue("AP.CLOSURE.ANCHOR_MISMATCH", f"returns_to edge {_text(edge.get('edge_id'))} does not preserve one Context Anchor"))
            if move_order.get(source, -1) <= move_order.get(target, -1):
                issues.append(CompilerIssue("AP.CLOSURE.ORDER_INVALID", f"returns_to edge {_text(edge.get('edge_id'))} must run from a later Move back to an earlier scene"))
    if move_by_id and _topological_order(graph_dependencies) is None:
        issues.append(CompilerIssue("MS-DEPENDENCY-CYCLE", "move dependency graph contains a cycle"))

    role_authorities: dict[str, set[str]] = {}
    for role in section_roles:
        section = next((item for item in ordered_sections if _text(item.get("semantic_role")) == role), {})
        refs: set[str] = set()
        for move_ref in _list(section.get("move_refs")):
            refs.update(_text(value) for value in _list(move_by_id.get(_text(move_ref), {}).get("authority_refs")))
        role_authorities[role] = refs
    sync_requirements = profile.get("sync_requirements") if isinstance(profile.get("sync_requirements"), dict) else {}
    for group, required_roles in sync_requirements.items():
        if group not in IDENTITY_GROUPS:
            continue
        required_refs = set(_identity_values(contract, group))
        for role in _list(required_roles):
            missing = sorted(required_refs - role_authorities.get(_text(role), set()))
            if missing:
                issues.append(CompilerIssue(IDENTITY_GATE_CODES[group], f"section role {role} omits global {group} identities: {', '.join(missing)}"))
    return issues


def _proof_obligations(contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        item for item in _list(contract.get("promises"))
        if isinstance(item, dict) and _text(item.get("promise_type")).lower() == "proof_obligation"
    ]


def _validate_argument_focus(
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    snapshots: Mapping[str, Mapping[str, Any]],
) -> list[CompilerIssue]:
    """Check declared argument coverage, without deciding whether a claim is true."""
    issues: list[CompilerIssue] = []
    moves = {_text(item.get("move_id")): item for item in _list(contract.get("moves")) if isinstance(item, dict)}
    promises = {_text(item.get("promise_id")): item for item in _list(contract.get("promises")) if isinstance(item, dict)}
    obligations = _proof_obligations(contract)
    obligation_ids = {_text(item.get("promise_id")) for item in obligations}
    main_claims = set(_identity_values(contract, "claims"))
    identity = contract.get("global_identity") if isinstance(contract.get("global_identity"), dict) else {}
    question = _text(identity.get("research_question_ref"))
    focused_sections = [
        item for item in _list(contract.get("sections"))
        if isinstance(item, dict) and any(field in item for field in SECTION_FOCUS_FIELDS)
    ]
    if obligations or focused_sections:
        narrative = contract.get("narrative_contract") if isinstance(contract.get("narrative_contract"), dict) else {}
        throughline = " ".join(_text(narrative.get("central_throughline")).split())
        template = " ".join(_text(profile.get("central_throughline")).split())
        if template and throughline == template:
            issues.append(CompilerIssue("MS-FOCUS-TEMPLATE", "argument focus requires a question-specific central_throughline, not the genre template"))
    for promise_id, promise in promises.items():
        if promise_id not in obligation_ids and any(field in promise for field in PROOF_FIELDS):
            issues.append(CompilerIssue("MS-PROOF-SHAPE", f"{promise_id} proof fields require promise_type=proof_obligation"))
    for obligation in obligations:
        promise_id = _text(obligation.get("promise_id"))
        required = {_text(value) for value in _list(obligation.get("required_authority_refs"))}
        authorities = {_text(value) for value in _list(obligation.get("authority_refs"))}
        claims = required & main_claims
        if not required or any(not _text(obligation.get(field)) for field in ("warrant", "failure_consequence")):
            issues.append(CompilerIssue("MS-PROOF-SHAPE", f"{promise_id} requires explicit authorities, warrant, and failure_consequence"))
        if question not in authorities or not claims or not required.issubset(authorities):
            issues.append(CompilerIssue("MS-PROOF-IDENTITY", f"{promise_id} must bind the current question and required main Claims within its authority_refs"))
        if not any(snapshots.get(ref, {}).get("authority_kind") in PROOF_BASIS_KINDS for ref in required):
            issues.append(CompilerIssue("MS-PROOF-BASIS", f"{promise_id} requires an evidence, result, source, material, design, or literature basis"))
        source = moves.get(_text(obligation.get("source_move_ref")), {})
        source_authorities = {_text(value) for value in _list(source.get("authority_refs"))}
        if not ({question} | claims).issubset(source_authorities) or promise_id not in _list(source.get("promise_refs")):
            issues.append(CompilerIssue("MS-PROOF-SOURCE", f"{promise_id} source Move must carry its question, required Claims, and promise backlink"))
        covered: set[str] = set()
        for delivery_ref in _list(obligation.get("delivery_move_refs")):
            delivery = moves.get(_text(delivery_ref), {})
            delivered = {_text(value) for value in _list(delivery.get("authority_refs"))}
            covered.update(delivered)
            if promise_id not in _list(delivery.get("delivery_refs")) or delivered.isdisjoint(required):
                issues.append(CompilerIssue("MS-PROOF-DELIVERY", f"{promise_id} delivery {delivery_ref} must carry a required authority and the obligation backlink"))
        if not required.issubset(covered):
            issues.append(CompilerIssue("MS-PROOF-COVERAGE", f"{promise_id} deliveries omit required authorities: {', '.join(sorted(required - covered))}"))
    for section in focused_sections:
        section_id = _text(section.get("section_id"))
        if any(field not in section for field in SECTION_FOCUS_FIELDS) or not _text(section.get("if_removed")):
            issues.append(CompilerIssue("MS-FOCUS-SHAPE", f"{section_id} must declare argument_role, serves_promise_refs, and if_removed together"))
        refs = {_text(value) for value in _list(section.get("serves_promise_refs"))}
        if not refs.issubset(promises):
            issues.append(CompilerIssue("MS-FOCUS-IDENTITY", f"{section_id} serves unknown promises: {', '.join(sorted(refs - set(promises)))}"))
        if _text(section.get("argument_role")) == "core_argument":
            owned_moves = set(_list(section.get("move_refs")))
            delivered_here = {
                ref for ref in refs & obligation_ids
                if owned_moves.intersection(_list(promises[ref].get("delivery_move_refs")))
            }
            if not delivered_here:
                issues.append(CompilerIssue("MS-FOCUS-ORPHAN", f"{section_id} core_argument must deliver a declared proof obligation in this section"))
    return issues


def _topological_order(dependencies: Mapping[str, set[str]]) -> list[str] | None:
    remaining = {node: set(values) for node, values in dependencies.items()}
    order: list[str] = []
    while remaining:
        ready = sorted(node for node, values in remaining.items() if not values)
        if not ready:
            return None
        for node in ready:
            order.append(node)
            remaining.pop(node)
        for values in remaining.values():
            values.difference_update(ready)
    return order


def _orphaned_lineage_paths(outdir: Path) -> list[str]:
    lineage: set[str] = set()
    for relative in (STALE_REL, REBUILD_REL):
        if _safe_workspace_path(outdir, relative).is_file():
            lineage.add(relative.as_posix())
    trace_path = _safe_workspace_path(outdir, TRACE_REL)
    if trace_path.is_file():
        try:
            if _read_json(trace_path).get("schema_version") == TRACE_SCHEMA_VERSION:
                lineage.add(TRACE_REL.as_posix())
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            pass
    for relative in VIEW_RELS:
        path = _safe_workspace_path(outdir, relative)
        try:
            prefix = path.read_text(encoding="utf-8-sig")[:160] if path.is_file() else ""
        except (OSError, UnicodeError):
            prefix = ""
        if "GENERATED BY AVERETH MANUSCRIPT COMPILER" in prefix:
            lineage.add(relative.as_posix())
    archive_root = _safe_workspace_path(outdir, LEGACY_ARCHIVE_ROOT_REL)
    if archive_root.exists() and any(archive_root.rglob("*")):
        lineage.add(LEGACY_ARCHIVE_ROOT_REL.as_posix())
    for relative in (Path("build_run.json"), Path("audit_receipt.json"), Path("output_receipt.json")):
        path = _safe_workspace_path(outdir, relative)
        try:
            record = _read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
        serialized = json.dumps(record, ensure_ascii=False, sort_keys=True)
        if (
            _text(record.get("framework_version")) == VERSION
            and TRACE_REL.as_posix() in serialized
        ):
            lineage.add(relative.as_posix())
    return sorted(lineage)


def _prior_lineage_issue(outdir: Path, payload: Mapping[str, Any]) -> CompilerIssue | None:
    trace_path = _safe_workspace_path(outdir, TRACE_REL)
    stale_path = _safe_workspace_path(outdir, STALE_REL)
    try:
        trace = _read_json(trace_path)
        stale = _read_json(stale_path)
        stale_text = stale_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return CompilerIssue(
            "MS-IR-ORPHANED",
            f"an existing MIR requires intact trace and stale lineage: {exc}",
            IR_REL.as_posix(),
        )
    if trace.get("schema_version") != TRACE_SCHEMA_VERSION or stale.get("schema_version") != STALE_SCHEMA_VERSION:
        return CompilerIssue(
            "MS-IR-DRIFT",
            "existing MIR trace/stale lineage uses an unsupported schema",
            IR_REL.as_posix(),
        )
    ir_path = _safe_workspace_path(outdir, IR_REL)
    if (
        trace.get("manuscript_ir")
        != {"path": IR_REL.as_posix(), "sha256": _sha256(ir_path)}
        or trace.get("stale_manifest")
        != {"path": STALE_REL.as_posix(), "sha256": _sha256(stale_path)}
    ):
        return CompilerIssue(
            "MS-IR-DRIFT",
            "existing MIR or stale manifest no longer matches the recorded trace SHA",
            IR_REL.as_posix(),
        )
    expected_trace = _trace_manifest(payload, render_markdown_views(payload), stale_text)
    if trace != expected_trace:
        return CompilerIssue(
            "MS-IR-DRIFT",
            "existing trace no longer binds the prior MIR source digest, contract, profile, authorities, manuscript, and generated projections",
            TRACE_REL.as_posix(),
        )
    if (
        stale.get("current_status") != "CURRENT"
        or stale.get("contract_sha256") != payload.get("contract", {}).get("sha256")
        or stale.get("ir_source_digest") != payload.get("source_digest")
        or stale.get("manuscript_binding") != payload.get("manuscript_binding")
    ):
        return CompilerIssue(
            "MS-IR-DRIFT",
            "existing stale manifest does not bind the prior MIR identity",
            STALE_REL.as_posix(),
        )
    proof_binding = stale.get("rebuild_proof") if isinstance(stale.get("rebuild_proof"), dict) else {}
    resolved_change = stale.get("resolved_change") if isinstance(stale.get("resolved_change"), dict) else {}
    if proof_binding:
        if proof_binding.get("path") != REBUILD_REL.as_posix():
            return CompilerIssue(
                "MS-IR-DRIFT",
                "existing stale lineage points to a non-canonical rebuild proof",
                STALE_REL.as_posix(),
            )
        proof_path = _safe_workspace_path(outdir, REBUILD_REL)
        if not proof_path.is_file() or _sha256(proof_path) != proof_binding.get("sha256"):
            return CompilerIssue(
                "MS-IR-DRIFT",
                "existing rebuild proof changed or disappeared from the prior lineage",
                REBUILD_REL.as_posix(),
            )
        proof_issues, verified = _rebuild_proof_issues(outdir, payload, resolved_change)
        if proof_issues or verified != proof_binding:
            return CompilerIssue(
                "MS-IR-DRIFT",
                "existing rebuild proof or one of its leaf artifacts is no longer valid",
                REBUILD_REL.as_posix(),
            )
    elif stale.get("status") == "RESOLVED" and resolved_change.get("stale_move_refs"):
        return CompilerIssue(
            "MS-IR-DRIFT",
            "resolved stale lineage lost its required rebuild-proof binding",
            STALE_REL.as_posix(),
        )
    return None


def _load_previous_ir(outdir: Path) -> tuple[dict[str, Any] | None, CompilerIssue | None]:
    path = _safe_workspace_path(outdir, IR_REL)
    if not path.is_file():
        orphaned = _orphaned_lineage_paths(outdir)
        if orphaned:
            return None, CompilerIssue(
                "MS-IR-ORPHANED",
                "AMC lineage exists without manuscript_ir.json; restore or explicitly migrate it instead of re-baselining: "
                + ", ".join(orphaned),
                IR_REL.as_posix(),
            )
        return None, None
    try:
        payload = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return None, CompilerIssue("MS-IR-INVALID", f"existing MIR cannot be read: {exc}", IR_REL.as_posix())
    if payload.get("schema_version") != IR_SCHEMA_VERSION:
        return None, CompilerIssue("MS-IR-INVALID", f"existing MIR must use {IR_SCHEMA_VERSION}", IR_REL.as_posix())
    lineage_issue = _prior_lineage_issue(outdir, payload)
    if lineage_issue:
        return None, lineage_issue
    return payload, None


def _optional_manuscript_binding(outdir: Path, config: Mapping[str, Any] | None) -> dict[str, str]:
    try:
        return select_manuscript(outdir, dict(config or {})).as_dict()
    except ManuscriptSelectionError:
        return {}


def _graph_dependencies(contract: Mapping[str, Any]) -> dict[str, set[str]]:
    moves = {
        _text(item.get("move_id")): item
        for item in _list(contract.get("moves"))
        if isinstance(item, dict)
    }
    dependencies = {
        move_id: {_text(value) for value in _list(move.get("dependency_refs"))}
        for move_id, move in moves.items()
    }
    for edge in _list(contract.get("cross_section_edges")):
        if not isinstance(edge, dict):
            continue
        source = _text(edge.get("source_ref"))
        target = _text(edge.get("target_ref"))
        if (
            _text(edge.get("relation")) != "returns_to"
            and source in moves
            and target in moves
            and source != target
        ):
            dependencies[target].add(source)
    for obligation in _proof_obligations(contract):
        source = _text(obligation.get("source_move_ref"))
        for value in _list(obligation.get("delivery_move_refs")):
            target = _text(value)
            if source in moves and target in moves and source != target:
                dependencies[target].add(source)
    return dependencies


def _compile_ir(
    outdir: Path,
    contract: dict[str, Any],
    profile: dict[str, Any],
    snapshots: list[dict[str, Any]],
    config: Mapping[str, Any] | None,
) -> dict[str, Any]:
    snapshot_by_id = {_text(item.get("ref_id")): item for item in snapshots}
    moves = {
        _text(item.get("move_id")): item
        for item in _list(contract.get("moves"))
        if isinstance(item, dict)
    }
    dependencies = _graph_dependencies(contract)
    order = _topological_order(dependencies) or sorted(moves)
    obligations = _proof_obligations(contract)
    sections_by_id = {
        _text(item.get("section_id")): item
        for item in _list(contract.get("sections")) if isinstance(item, dict)
    }
    compiled_moves: dict[str, dict[str, Any]] = {}
    for move_id in order:
        move = moves[move_id]
        contract_digest = _digest(move)
        authority_digests = {
            ref: snapshot_by_id.get(ref, {}).get("selector_digest", "")
            for ref in sorted(_text(value) for value in _list(move.get("authority_refs")))
        }
        dependency_outputs = {
            ref: compiled_moves.get(ref, {}).get("output_digest", "")
            for ref in sorted(dependencies.get(move_id, set()))
        }
        source_inputs = {
            "contract": contract_digest,
            "authorities": authority_digests,
            "dependencies": dependency_outputs,
        }
        bound_obligations = [
            item for item in obligations
            if move_id == _text(item.get("source_move_ref")) or move_id in _list(item.get("delivery_move_refs"))
        ]
        section = sections_by_id.get(_text(move.get("section_ref")), {})
        section_focus = {field: section[field] for field in SECTION_FOCUS_FIELDS if field in section}
        # Focus changes affect the corresponding prose closure, while legacy inputs retain their digests.
        if bound_obligations or section_focus:
            source_inputs["argument_focus"] = {
                "obligations": bound_obligations,
                "section": section_focus,
                "throughline": (contract.get("narrative_contract") or {}).get("central_throughline"),
            }
        source_digest = _digest(source_inputs)
        output_digest = _digest(
            {
                "move_id": move_id,
                "source_digest": source_digest,
                "move_type": move.get("move_type"),
                "section_ref": move.get("section_ref"),
            }
        )
        compiled_moves[move_id] = {
            "contract": move,
            "contract_digest": contract_digest,
            "source_digest": source_digest,
            "output_digest": output_digest,
        }
    section_nodes: list[dict[str, Any]] = []
    for section in _list(contract.get("sections")):
        if not isinstance(section, dict):
            continue
        contract_digest = _digest(section)
        move_outputs = {
            ref: compiled_moves.get(_text(ref), {}).get("output_digest", "")
            for ref in _list(section.get("move_refs"))
        }
        source_digest = _digest({"contract": contract_digest, "moves": move_outputs})
        section_nodes.append(
            {
                "contract": section,
                "contract_digest": contract_digest,
                "source_digest": source_digest,
                "output_digest": _digest(
                    {
                        "section_id": section.get("section_id"),
                        "source_digest": source_digest,
                    }
                ),
            }
        )
    contract_path = outdir / CONTRACT_REL
    installed_profile = profile_path(_text(contract.get("genre_profile")) or SUPPORTED_PROFILE)
    ir: dict[str, Any] = {
        "schema_version": IR_SCHEMA_VERSION,
        "compiler_version": VERSION,
        "control_plane": "cnki-paper",
        "owner_stage": "build",
        "authority_class": "derived_projection",
        "contract": {"path": CONTRACT_REL.as_posix(), "sha256": _sha256(contract_path)},
        "profile": {
            "path": installed_profile.relative_to(_skill_root()).as_posix(),
            "sha256": _sha256(installed_profile),
        },
        "global_identity": contract.get("global_identity"),
        "narrative_contract": contract.get("narrative_contract"),
        "authority_snapshot": sorted(snapshots, key=lambda item: _text(item.get("ref_id"))),
        "sections": section_nodes,
        "moves": [compiled_moves[move_id] for move_id in order],
        "claim_lifecycle": contract.get("claim_lifecycle"),
        "promises": contract.get("promises"),
        "cross_section_edges": contract.get("cross_section_edges"),
        "scientific_commitment_order": contract.get("scientific_commitment_order"),
        "render_order": contract.get("render_order"),
        "manuscript_binding": _optional_manuscript_binding(outdir, config),
        "source_digest": "",
        "status": "CURRENT",
    }
    ir["source_digest"] = _digest({key: value for key, value in ir.items() if key != "source_digest"})
    return ir


def _stale_projection(previous: dict[str, Any] | None, current: dict[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    current_moves = {
        _text(item.get("contract", {}).get("move_id")): item
        for item in _list(current.get("moves"))
        if isinstance(item, dict)
    }
    current_sections = {
        _text(item.get("contract", {}).get("section_id")): item
        for item in _list(current.get("sections"))
        if isinstance(item, dict)
    }
    if previous is None:
        return {
            "schema_version": STALE_SCHEMA_VERSION,
            "status": "BASELINE_REQUIRED",
            "changed_authority_refs": [],
            "direct_stale_move_refs": sorted(current_moves),
            "stale_move_refs": sorted(current_moves),
            "stale_section_refs": sorted(current_sections),
            "manuscript_changed": bool(current.get("manuscript_binding")),
            "manuscript_only_drift": False,
            "contract_changed": False,
        }
    previous_snapshots = {
        _text(item.get("ref_id")): _digest(item)
        for item in _list(previous.get("authority_snapshot"))
        if isinstance(item, dict)
    }
    current_snapshots = {
        _text(item.get("ref_id")): _digest(item)
        for item in _list(current.get("authority_snapshot"))
        if isinstance(item, dict)
    }
    changed_authorities = sorted(
        ref
        for ref in set(previous_snapshots) | set(current_snapshots)
        if previous_snapshots.get(ref) != current_snapshots.get(ref)
    )
    previous_moves = {
        _text(item.get("contract", {}).get("move_id")): item
        for item in _list(previous.get("moves"))
        if isinstance(item, dict)
    }
    previous_sections = {
        _text(item.get("contract", {}).get("section_id")): item
        for item in _list(previous.get("sections"))
        if isinstance(item, dict)
    }
    direct: set[str] = set()
    for move_id, node in current_moves.items():
        old = previous_moves.get(move_id)
        refs = {_text(value) for value in _list(node.get("contract", {}).get("authority_refs"))}
        if old is None or node.get("contract_digest") != old.get("contract_digest") or refs.intersection(changed_authorities):
            direct.add(move_id)
    direct.update(set(previous_moves) - set(current_moves))
    contract_changed = previous.get("contract") != current.get("contract")
    if contract_changed:
        direct.update(current_moves)
    changed_sections = {
        section_id
        for section_id, node in current_sections.items()
        if previous_sections.get(section_id, {}).get("contract_digest") != node.get("contract_digest")
    }
    for move_id, node in current_moves.items():
        if _text(node.get("contract", {}).get("section_ref")) in changed_sections:
            direct.add(move_id)
    manuscript_changed = previous.get("manuscript_binding") != current.get("manuscript_binding")
    manuscript_only_drift = manuscript_changed and not changed_authorities and not direct
    if manuscript_only_drift:
        direct.update(current_moves)
    dependencies = _graph_dependencies(contract)
    dependents: dict[str, set[str]] = {move_id: set() for move_id in current_moves}
    for target, sources in dependencies.items():
        for source in sources:
            dependents.setdefault(source, set()).add(target)
    closure = {move for move in direct if move in current_moves}
    frontier = list(closure)
    while frontier:
        source = frontier.pop()
        for target in dependents.get(source, set()):
            if target not in closure:
                closure.add(target)
                frontier.append(target)
    stale_sections = sorted(
        {
            _text(current_moves[move].get("contract", {}).get("section_ref"))
            for move in closure
            if move in current_moves
        }
    )
    status = "STALE" if changed_authorities or direct or manuscript_changed else "CURRENT"
    return {
        "schema_version": STALE_SCHEMA_VERSION,
        "status": status,
        "changed_authority_refs": changed_authorities,
        "direct_stale_move_refs": sorted(direct),
        "stale_move_refs": sorted(closure),
        "stale_section_refs": stale_sections,
        "manuscript_changed": manuscript_changed,
        "manuscript_only_drift": manuscript_only_drift,
        "contract_changed": contract_changed,
    }


def compile_workspace(outdir: Path, config: Mapping[str, Any] | None = None) -> Compilation:
    """Compile current authorities in memory without mutating the workspace."""

    outdir = outdir.resolve()
    contract_path = outdir / CONTRACT_REL
    if not contract_path.is_file():
        issue = CompilerIssue(
            "MS-CONTRACT-MISSING",
            "initialize AMC explicitly with `avereth.py manuscript init OUTDIR --apply`, review the contract, then run `manuscript render OUTDIR --baseline`",
            CONTRACT_REL.as_posix(),
        )
        return Compilation(None, None, None, (issue,), {"schema_version": STALE_SCHEMA_VERSION, "status": "UNAVAILABLE"})
    try:
        contract = _read_json(contract_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        issue = CompilerIssue("MS-CONTRACT-INVALID", f"cannot read manuscript contract: {exc}", CONTRACT_REL.as_posix())
        return Compilation(None, None, None, (issue,), {"schema_version": STALE_SCHEMA_VERSION, "status": "UNAVAILABLE"})
    try:
        profile = _read_json(profile_path(_text(contract.get("genre_profile")) or SUPPORTED_PROFILE))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, ManuscriptCompilerError) as exc:
        issue = CompilerIssue("MS-PROFILE", str(exc))
        return Compilation(contract, None, None, (issue,), {"schema_version": STALE_SCHEMA_VERSION, "status": "UNAVAILABLE"})
    issues: list[CompilerIssue] = _contract_schema_issues(contract)
    snapshots: list[dict[str, Any]] = []
    for binding in _list(contract.get("authority_bindings")):
        if not isinstance(binding, dict):
            issues.append(CompilerIssue("MS-CONTRACT-SHAPE", "authority binding must be an object"))
            continue
        snapshot, issue = _resolve_authority(outdir, binding)
        if issue:
            issues.append(issue)
        elif snapshot is not None:
            snapshots.append(snapshot)
    snapshot_by_id = {_text(item.get("ref_id")): item for item in snapshots}
    issues.extend(
        _validate_contract(
            contract,
            profile,
            snapshot_by_id,
            config,
            _context_anchor_bindings(outdir),
        )
    )
    previous, previous_issue = _load_previous_ir(outdir)
    if previous_issue:
        issues.append(previous_issue)
    if issues:
        return Compilation(contract, profile, None, tuple(issues), {"schema_version": STALE_SCHEMA_VERSION, "status": "INVALID"})
    ir = _compile_ir(outdir, contract, profile, snapshots, config)
    stale = _stale_projection(previous, ir, contract)
    return Compilation(contract, profile, ir, (), stale)


def _md(value: Any) -> str:
    text = _text(value).replace("\\", "\\\\").replace("|", "\\|")
    return " ".join(text.splitlines())


def _refs(values: Iterable[Any]) -> str:
    rendered = ", ".join(_text(value) for value in values if _text(value))
    return rendered or "not-applicable"


def _move_rhetorical_binding(move: Mapping[str, Any]) -> str:
    bindings: list[str] = []
    resonance = _text(move.get("resonance_device"))
    body_move = _text(move.get("body_explanation_move_ref"))
    if resonance:
        bindings.append(f"title:{resonance}->{body_move or 'missing'}")
    scene = move.get("verified_scene")
    if isinstance(scene, dict):
        bindings.append(
            "scene:{anchor}@{authority}".format(
                anchor=_text(scene.get("anchor_id")) or "missing",
                authority=_text(scene.get("authority_ref")) or "missing",
            )
        )
    return "; ".join(bindings) or "not-applicable"


def _generated_header(title: str, ir: Mapping[str, Any]) -> list[str]:
    return [
        "<!-- GENERATED BY AVERETH MANUSCRIPT COMPILER; DO NOT EDIT -->",
        f"# {title}",
        "",
        "Status: **PASS**",
        "",
        f"- MIR Source Digest: `{_text(ir.get('source_digest'))}`",
        "- Authority: derived build projection; scientific facts remain in registered upstream authorities.",
        "- Stage: build (not a ninth stage or completion receipt).",
        "",
    ]


def render_markdown_views(ir: Mapping[str, Any]) -> dict[Path, str]:
    """Render the human views deterministically from a validated MIR."""

    section_nodes = _list(ir.get("sections"))
    move_nodes = _list(ir.get("moves"))
    moves = {
        _text(node.get("contract", {}).get("move_id")): node.get("contract", {})
        for node in move_nodes
        if isinstance(node, dict)
    }
    sections = [node.get("contract", {}) for node in section_nodes if isinstance(node, dict)]
    rhetorical_projection = bool(
        any(
            any(
                _text(move.get(field))
                for field in (
                    "argument_action",
                    "problem_state_before",
                    "problem_state_after",
                    "resonance_device",
                    "body_explanation_move_ref",
                )
            )
            or isinstance(move.get("verified_scene"), dict)
            for move in moves.values()
        )
        or any(
            _text(item.get("promise_type")).lower() == "epistemic_hook"
            for item in _list(ir.get("promises"))
            if isinstance(item, dict)
        )
        or any(
            _text(item.get("relation")) == "returns_to"
            for item in _list(ir.get("cross_section_edges"))
            if isinstance(item, dict)
        )
    )

    blueprints = _generated_header("Section Blueprints", ir)
    for section in sections:
        blueprints.extend(
            [
                f"## {_md(section.get('display_heading'))} (`{_md(section.get('section_id'))}`)",
                "",
                f"- Semantic Role: `{_md(section.get('semantic_role'))}`",
                f"- Section Family: `{_md(section.get('section_family'))}`",
                f"- Reader State Before: {_md('; '.join(_list(section.get('reader_state_before'))))}",
                f"- Reader Question: {_md(section.get('reader_question'))}",
                f"- Required Update: {_md('; '.join(_list(section.get('required_update'))))}",
                f"- Reader State After: {_md('; '.join(_list(section.get('reader_state_after'))))}",
                f"- Section Dependencies: {_refs(_list(section.get('dependencies')))}",
                "",
            ]
        )
        blueprints.extend(
            [
                "| Move ID | Move Type | Argument Action | Problem State Before | Problem State After | Planned Function | Authority Refs | Dependency Refs | Rhetorical Binding |",
                "|---|---|---|---|---|---|---|---|---|",
            ]
            if rhetorical_projection
            else [
                "| Move ID | Move Type | Planned Function | Authority Refs | Dependency Refs |",
                "|---|---|---|---|---|",
            ]
        )
        for move_ref in _list(section.get("move_refs")):
            move = moves.get(_text(move_ref), {})
            if rhetorical_projection:
                blueprints.append(
                    f"| `{_md(move_ref)}` | `{_md(move.get('move_type'))}` | {_md(move.get('argument_action') or 'not-applicable')} | {_md(move.get('problem_state_before') or 'not-applicable')} | {_md(move.get('problem_state_after') or 'not-applicable')} | {_md(move.get('planned_function'))} | {_md(_refs(_list(move.get('authority_refs'))))} | {_md(_refs(_list(move.get('dependency_refs'))))} | {_md(_move_rhetorical_binding(move))} |"
                )
            else:
                blueprints.append(
                    f"| `{_md(move_ref)}` | `{_md(move.get('move_type'))}` | {_md(move.get('planned_function'))} | {_md(_refs(_list(move.get('authority_refs'))))} | {_md(_refs(_list(move.get('dependency_refs'))))} |"
                )
        blueprints.append("")

    rationale = _generated_header("Writing Rationale Matrix", ir)
    identity = ir.get("global_identity") if isinstance(ir.get("global_identity"), dict) else {}
    rationale.extend(
        [
            "| Row ID | Manuscript Unit | Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Text Move | Final Text Check |",
            "|---|---|---|---|---|---|---|---|---|",
            f"| `MS-000` | Whole-manuscript framework | {_md(ir.get('narrative_contract', {}).get('central_throughline'))} | {_md(identity.get('research_question_ref'))} | Registered literature synthesis identities: {_md(_refs(_list(identity.get('literature_refs'))))} | Contracted {_md(Path(_text(ir.get('profile', {}).get('path'))).name.rsplit('-v', 1)[0] or 'manuscript')} profile | Global identities: {_md(_refs(sum([_list(value) if isinstance(value, list) else [value] for value in identity.values()], [])))} | Compile the full section and dependency graph before local ProsePacket realization. | PASS: whole-paper framework, identities, lifecycle, and dependency graph compiled. |",
        ]
    )
    section_by_id = {_text(section.get("section_id")): section for section in sections}
    for index, node in enumerate(move_nodes, start=1):
        move = node.get("contract", {}) if isinstance(node, dict) else {}
        section = section_by_id.get(_text(move.get("section_ref")), {})
        rationale.append(
            "| `{row}` | {unit} | {function} | {motivation} | {reference} | {venue} | {evidence} | {planned} | {check} |".format(
                row=_md(move.get("move_id")),
                unit=_md(f"{section.get('display_heading')} / {move.get('move_type')}"),
                function=_md(move.get("planned_function")),
                motivation=_md(_refs(_list(move.get("promise_refs")) or [identity.get("research_question_ref")])),
                reference=_md("registered literature and profile move contract: " + _refs(_list(identity.get("literature_refs")))),
                venue=_md("venue profile inherited by the global manuscript contract"),
                evidence=_md(_refs(_list(move.get("authority_refs"))),),
                planned=_md(f"Answer: {move.get('reader_question')} Update: {move.get('required_update')}"),
                check="PASS: structural authority and dependency contract compiled; prose fidelity remains separately gated by ProsePacket v2.",
            )
        )
    rationale.append("")

    focused_sections = [section for section in sections if any(field in section for field in SECTION_FOCUS_FIELDS)]
    if focused_sections:
        rationale.extend([
            "## Section argument responsibilities",
            "",
            "| Section | Argument Role | Serves Promises | Consequence of Removal | Status |",
            "|---|---|---|---|---|",
        ])
        for section in focused_sections:
            rationale.append(
                f"| `{_md(section.get('section_id'))}` | {_md(section.get('argument_role'))} | {_md(_refs(_list(section.get('serves_promise_refs'))))} | {_md(section.get('if_removed'))} | REGISTERED; necessity requires manuscript review |"
            )
        rationale.append("")

    promises_view = _generated_header("Promise-Delivery Matrix", ir)
    promises_view.extend(
        [
            "| Promise ID | Type | Tension Authority | Source Move | Delivery Moves | Delay Span | Resolution Type | Deepening Review | Status |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        if rhetorical_projection
        else [
            "| Promise ID | Type | Source Move | Delivery Moves | Authority Refs | Status |",
            "|---|---|---|---|---|---|",
        ]
    )
    for promise in _list(ir.get("promises")):
        if isinstance(promise, dict):
            if rhetorical_projection:
                promises_view.append(
                    f"| `{_md(promise.get('promise_id'))}` | {_md(promise.get('promise_type'))} | {_md(_refs(_list(promise.get('authority_refs'))))} | `{_md(promise.get('source_move_ref'))}` | {_md(_refs(_list(promise.get('delivery_move_refs'))))} | {_md(promise.get('delay_span') or 'not-applicable')} | {_md(promise.get('resolution_type') or 'not-applicable')} | {'REVIEW-REQUIRED' if _text(promise.get('promise_type')).lower() == 'epistemic_hook' else 'not-applicable'} | PASS |"
                )
            else:
                promises_view.append(
                    f"| `{_md(promise.get('promise_id'))}` | {_md(promise.get('promise_type'))} | `{_md(promise.get('source_move_ref'))}` | {_md(_refs(_list(promise.get('delivery_move_refs'))))} | {_md(_refs(_list(promise.get('authority_refs'))))} | PASS |"
                )
    promises_view.append("")

    obligations = _proof_obligations(ir)
    if obligations:
        promises_view.extend([
            "## Proof obligation coverage",
            "",
            "Coverage checks registered identities and delivery links. Negative or inconclusive results can discharge an inquiry; coverage does not establish the truth of a Claim.",
            "",
            "| Obligation | Required Authorities | Warrant | Consequence of Failure | Status |",
            "|---|---|---|---|---|",
        ])
        for obligation in obligations:
            promises_view.append(
                f"| `{_md(obligation.get('promise_id'))}` | {_md(_refs(_list(obligation.get('required_authority_refs'))))} | {_md(obligation.get('warrant'))} | {_md(obligation.get('failure_consequence'))} | COVERED; inferential adequacy requires evidence review |"
            )
        promises_view.append("")

    lifecycle_view = _generated_header("Claim Lifecycle Matrix", ir)
    lifecycle_view.extend(
        [
            "| Claim Ref | Introduced | Motivated | Specified | Operationalized | Evaluated | Interpreted | Summarized | Status |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
    )
    for lifecycle in _list(ir.get("claim_lifecycle")):
        if isinstance(lifecycle, dict):
            lifecycle_view.append(
                "| `{claim}` | {values} | PASS |".format(
                    claim=_md(lifecycle.get("claim_ref")),
                    values=" | ".join(_md(_refs(_list(lifecycle.get(stage)))) for stage in LIFECYCLE_STAGES),
                )
            )
    lifecycle_view.append("")

    reader_view = _generated_header("Reader-State Report", ir)
    reader_view.extend(
        [
            "| Section | State Before | Reader Question | Required Update | State After | Status |",
            "|---|---|---|---|---|---|",
        ]
    )
    for section in sections:
        reader_view.append(
            f"| `{_md(section.get('section_id'))}` {_md(section.get('display_heading'))} | {_md('; '.join(_list(section.get('reader_state_before'))))} | {_md(section.get('reader_question'))} | {_md('; '.join(_list(section.get('required_update'))))} | {_md('; '.join(_list(section.get('reader_state_after'))))} | PASS |"
        )
    reader_view.append("")

    sync_view = _generated_header("Cross-Section Sync Report", ir)
    sync_view.extend(
        [
            "| Gate | Check | Status |",
            "|---|---|---|",
            "| `MS-RQ-IDENTITY` | Abstract, introduction, results, and conclusion retain the same research-question authority. | PASS |",
            "| `MS-CLAIM-IDENTITY` | Title and all load-bearing sections retain every global Claim identity. | PASS |",
            "| `MS-DESIGN-IDENTITY` | Abstract, introduction, methods, and results retain the same design identity. | PASS |",
            "| `MS-RESULT-IDENTITY` | Result identities propagate to abstract, introduction preview, discussion, conclusion, and supporting expression. | PASS |",
            "| `MS-CONTRIBUTION-IDENTITY` | Introduction promises are delivered in abstract, discussion, and conclusion. | PASS |",
            "| `MS-SCOPE-IDENTITY` | Title and all evidence/interpretation sections retain the same scope identity. | PASS |",
            "| `MS-PROMISE-DELIVERY` | Every registered promise has one source and one or more authority-overlapping deliveries. | PASS |",
        ]
    )
    if rhetorical_projection:
        sync_view.extend(
            [
                "| `AP-HOOK-CLOSURE` | Every declared epistemic hook has a valid order, bounded delay, and registered delivery; substantive deepening remains a Clean Read judgment. | PASS |",
                "| `AP-THOUGHT-MOVE` | Declared thought Moves preserve the before-state, action, and after-state relation without producing new facts. | PASS |",
                "| `AP-TITLE-BODY` | Every declared title resonance device points to a distinct Body Explanation Move. | PASS |",
                "| `AP-SCENE-RETURN` | Every declared returns_to edge preserves one verified Context Anchor and points from a later Move to an earlier scene. | PASS |",
            ]
        )
    sync_view.extend(
        [
            "| `MS-CLAIM-LIFECYCLE` | Every main Claim completes introduced through summarized. | PASS |",
            "| `MS-READER-STATE` | Adjacent reader-state identities and content form one continuous chain. | PASS |",
            "| `MS-INTERNAL-ID-LEAK` | Internal identities remain in this build projection and must not enter reader-facing prose. | PASS |",
            "",
        ]
    )
    return {
        Path("section_blueprints.md"): "\n".join(blueprints).rstrip() + "\n",
        Path("writing_rationale_matrix.md"): "\n".join(rationale).rstrip() + "\n",
        Path("promise_delivery_matrix.md"): "\n".join(promises_view).rstrip() + "\n",
        Path("claim_lifecycle_matrix.md"): "\n".join(lifecycle_view).rstrip() + "\n",
        Path("reader_state_report.md"): "\n".join(reader_view).rstrip() + "\n",
        Path("cross_section_sync_report.md"): "\n".join(sync_view).rstrip() + "\n",
    }


def _move_nodes(ir: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        _text(item.get("contract", {}).get("move_id")): item
        for item in _list(ir.get("moves"))
        if isinstance(item, dict)
    }


def _rebuild_binding(ir: Mapping[str, Any], stale: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "contract_sha256": ir.get("contract", {}).get("sha256"),
        "authority_digest": _digest(ir.get("authority_snapshot")),
        "ir_source_digest": ir.get("source_digest"),
        "manuscript_binding": ir.get("manuscript_binding"),
        "stale_move_refs": sorted(_text(value) for value in _list(stale.get("stale_move_refs"))),
    }


def _rebuild_evidence(
    outdir: Path,
    artifact: str | Path,
    kind: str,
) -> tuple[dict[str, str] | None, CompilerIssue | None]:
    evidence_kind = _text(kind)
    if evidence_kind not in REBUILD_EVIDENCE_KINDS:
        return None, CompilerIssue(
            "MS-REBUILD-PROOF",
            "rebuild evidence kind must be one of: " + ", ".join(sorted(REBUILD_EVIDENCE_KINDS)),
        )
    try:
        path = _safe_workspace_path(outdir, artifact)
        relative = _canonical_workspace_relative(outdir, path)
    except (OSError, ValueError) as exc:
        return None, CompilerIssue("MS-REBUILD-PROOF", str(exc), _text(artifact))
    if not path.is_file() or path.stat().st_size <= 0:
        return None, CompilerIssue("MS-REBUILD-PROOF", "rebuild evidence is missing or empty", relative.as_posix())
    if not relative.parts or relative.parts[0] != ".avereth-prose":
        return None, CompilerIssue(
            "MS-REBUILD-PROOF",
            "rebuild evidence must be a transient packet, draft, or section output under .avereth-prose/",
            relative.as_posix(),
        )
    forbidden = {CONTRACT_REL, IR_REL, STALE_REL, REBUILD_REL}
    if relative in forbidden or relative.parts[: len(LEGACY_ARCHIVE_ROOT_REL.parts)] == LEGACY_ARCHIVE_ROOT_REL.parts:
        return None, CompilerIssue(
            "MS-REBUILD-PROOF",
            "compiler metadata or a legacy archive cannot prove prose rebuilding",
            relative.as_posix(),
        )
    json_kinds = {
        "prose_packet",
        "clarity_ledger",
        "semantic_dispatch",
        "semantic_assurance",
    }
    if evidence_kind in json_kinds:
        try:
            payload = _read_json(path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            return None, CompilerIssue("MS-REBUILD-PROOF", f"cannot read {evidence_kind} evidence: {exc}", relative.as_posix())
        expected_schemas = {
            "prose_packet": "avereth-prose-packet/v2",
            "clarity_ledger": "avereth-clarity-edit-ledger/v1",
            "semantic_dispatch": "avereth-semantic-fidelity-dispatch/v1",
            "semantic_assurance": "avereth-semantic-fidelity-assurance/v1",
        }
        if payload.get("schema_version") != expected_schemas[evidence_kind]:
            return None, CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{evidence_kind} evidence must use {expected_schemas[evidence_kind]}",
                relative.as_posix(),
            )
    elif path.suffix.lower() not in {".md", ".txt", ".tex"}:
        return None, CompilerIssue(
            "MS-REBUILD-PROOF",
            "draft and section-output evidence must be inspectable prose text",
            relative.as_posix(),
        )
    return {
        "evidence_kind": evidence_kind,
        "evidence_path": relative.as_posix(),
        "evidence_sha256": _sha256(path),
    }, None


def _load_prose_packet_runtime() -> Any:
    """Load the installed firewall implementation without creating new authority."""

    module_name = "avereth_manuscript_compiler_prose_packet_runtime"
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).resolve().parents[2] / "prose_packet.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ProsePacket runtime from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(module_name, None)
        raise
    return module


def _docx_visible_text(path: Path) -> str:
    """Extract visible OOXML text without narrowing canonical DOCX support."""

    members = ("word/document.xml", "word/footnotes.xml", "word/endnotes.xml")
    fragments: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            if any(item.flag_bits & 0x1 for item in archive.infolist()):
                raise ValueError("encrypted DOCX packages are not inspectable build evidence")
            names = set(archive.namelist())
            if members[0] not in names:
                raise ValueError("DOCX package is missing word/document.xml")
            for member in members:
                if member not in names:
                    continue
                root = ElementTree.fromstring(archive.read(member))
                for node in root.iter():
                    local = node.tag.rsplit("}", 1)[-1]
                    if local == "t" and node.text:
                        fragments.append(node.text)
                    elif local in {"tab", "br", "cr", "p", "tr"}:
                        fragments.append(" ")
    except (OSError, KeyError, RuntimeError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise ValueError(f"canonical DOCX cannot be inspected: {exc}") from exc
    text = "".join(fragments)
    if not text.strip():
        raise ValueError("canonical DOCX contains no inspectable visible text")
    return text


def _canonical_manuscript_text(outdir: Path, binding: Mapping[str, Any]) -> str:
    raw = _text(binding.get("path"))
    if not raw:
        raise ValueError("canonical manuscript binding has no path")
    path = _safe_workspace_path(outdir, raw)
    if not path.is_file():
        raise ValueError("canonical manuscript is missing")
    if path.suffix.lower() == ".docx":
        return _docx_visible_text(path)
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"canonical manuscript cannot be read as text: {exc}") from exc


def _packet_for_move_issues(
    outdir: Path,
    packet_path: Path,
    move_ref: str,
    move: Mapping[str, Any],
    authority_snapshots: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, Any, frozenset[str], Any, list[CompilerIssue]]:
    issues: list[CompilerIssue] = []
    relative = _canonical_workspace_relative(outdir, packet_path).as_posix()
    try:
        packet = _read_json(packet_path)
        runtime = _load_prose_packet_runtime()
        registered = runtime.discover_registered_ids(outdir)
        result_use = _text(packet.get("result_use")).lower() or "claim_support"
        accepted = runtime.discover_accepted_result_claims(outdir, allowed_use=result_use)
        packet_issues = runtime.validate_prose_packet(
            packet,
            registered_ids=registered,
            accepted_result_claims=accepted,
        )
    except Exception as exc:
        return None, None, frozenset(), None, [
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} ProsePacket cannot be validated by the installed firewall: {exc}",
                relative,
            )
        ]
    for message in packet_issues:
        issues.append(
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} ProsePacket is invalid: {message}",
                relative,
            )
        )
    contract = move.get("contract") if isinstance(move.get("contract"), dict) else {}
    expected_role = _text(contract.get("prose_packet_role")).lower()
    actual_role = _text(packet.get("section_role")).lower()
    if not expected_role or actual_role != expected_role:
        issues.append(
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} packet section_role {actual_role or '<missing>'} does not match its Move contract role {expected_role or '<missing>'}",
                relative,
            )
        )
    expected_question = _text(contract.get("reader_question"))
    if _text(packet.get("reader_question")) != expected_question:
        issues.append(
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} packet reader_question does not exactly bind the Move reader_question",
                relative,
            )
        )
    expected_update = _text(contract.get("required_update"))
    if _text(packet.get("reader_update")) != expected_update:
        issues.append(
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} packet reader_update does not exactly bind the Move required_update/planned_function",
                relative,
            )
        )
    claim = packet.get("claim") if isinstance(packet.get("claim"), dict) else {}
    packet_claim = _text(claim.get("id")).upper()
    move_claims = {_text(value).upper() for value in _list(contract.get("claim_refs")) if _text(value)}
    if move_claims and packet_claim not in move_claims:
        issues.append(
            CompilerIssue(
                "MS-REBUILD-PROOF",
                f"{move_ref} packet Claim {packet_claim or '<missing>'} does not intersect its registered Move Claim refs",
                relative,
            )
        )
    packet_semantics = _canonical_claim_semantics(claim)
    expected_semantic_digest = _text(
        authority_snapshots.get(packet_claim, {}).get("claim_semantic_digest")
    )
    verbatim_matches = False
    if claim.get("realization_mode") == "verbatim":
        # Exact text has no semantic atoms in ProsePacket. Bind it to the same
        # validated authority selector instead of inventing a weaker authority.
        snapshot = authority_snapshots.get(packet_claim, {})
        try:
            source = _safe_workspace_path(outdir, _text(snapshot.get("source_path")))
            selector = snapshot.get("selector", {})
            rules = AUTHORITY_SOURCE_RULES["claim"]
            rule = next((rule for path, rule in rules.items()
                         if path.casefold() == _text(snapshot.get("source_path")).casefold()), {})
            matches = _objects_in_named_collections(
                _read_json(source), packet_claim,
                containers=rule.get("containers", frozenset()),
                keys=frozenset(_list(selector.get("id_keys"))),
            )
            if (snapshot.get("authority_kind") == "claim" and selector.get("id") == packet_claim
                    and _sha256(source) == snapshot.get("source_sha256") and len(matches) == 1):
                selected = matches[0]
                verbatim_matches = (
                    _digest(selected) == snapshot.get("selector_digest")
                    and _text(claim.get("text")) == _text(selected.get("canonical_proposition")
                                                        or selected.get("statement") or selected.get("text"))
                    and _text(claim.get("strength")).lower() == _text(selected.get("strength") or selected.get("type")).lower()
                )
        except (OSError, ValueError, TypeError, KeyError):
            verbatim_matches = False
    if not verbatim_matches and (
        packet_semantics is None
        or not expected_semantic_digest
        or _digest(packet_semantics) != expected_semantic_digest
    ):
        issues.append(
            CompilerIssue(
                "MS-CLAIM-SEMANTICS",
                f"{move_ref} packet canonical proposition, strength, or protected atoms do not match the registered Claim authority",
                relative,
            )
        )
    return packet, runtime, frozenset(registered), accepted, issues


def _rebuild_items_issues(
    outdir: Path,
    ir: Mapping[str, Any],
    stale: Mapping[str, Any],
    raw_items: Iterable[Any],
    *,
    require_full_coverage: bool,
) -> list[CompilerIssue]:
    outdir = outdir.resolve()
    issues: list[CompilerIssue] = []
    moves = _move_nodes(ir)
    authority_snapshots = {
        _text(item.get("ref_id")).upper(): item
        for item in _list(ir.get("authority_snapshot"))
        if isinstance(item, dict) and _text(item.get("ref_id"))
    }
    binding = _rebuild_binding(ir, stale)
    current_manuscript = ir.get("manuscript_binding") if isinstance(ir.get("manuscript_binding"), dict) else {}
    try:
        manuscript_text = _canonical_manuscript_text(outdir, current_manuscript)
    except ValueError as exc:
        manuscript_text = ""
        issues.append(
            CompilerIssue(
                "MS-MANUSCRIPT-READ",
                str(exc),
                _text(current_manuscript.get("path")),
            )
        )
    compact_manuscript = "".join(manuscript_text.split()).casefold()
    stale_refs = {_text(value) for value in _list(stale.get("stale_move_refs"))}
    by_move: dict[str, Mapping[str, Any]] = {}
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            issues.append(CompilerIssue("MS-REBUILD-PROOF", "rebuild proof items must be objects", REBUILD_REL.as_posix()))
            continue
        move_ref = _text(raw_item.get("move_ref"))
        if not move_ref or move_ref in by_move:
            issues.append(CompilerIssue("MS-REBUILD-PROOF", "rebuild proof has a missing or duplicate move_ref", REBUILD_REL.as_posix()))
            continue
        if move_ref not in stale_refs or move_ref not in moves:
            issues.append(CompilerIssue("MS-REBUILD-PROOF", f"{move_ref} is not in the current stale Move closure", REBUILD_REL.as_posix()))
            continue
        by_move[move_ref] = raw_item
    if require_full_coverage:
        missing = sorted(stale_refs - set(by_move))
        if missing:
            issues.append(
                CompilerIssue(
                    "MS-STALE-UNREBUILT",
                    "per-Move rebuild proof does not cover the stale closure: " + ", ".join(missing),
                    REBUILD_REL.as_posix(),
                )
            )

    path_owner: dict[str, str] = {}
    digest_owner: dict[str, str] = {}
    for move_ref in sorted(by_move):
        item = by_move[move_ref]
        node = moves[move_ref]
        contract = node.get("contract") if isinstance(node.get("contract"), dict) else {}
        if item.get("section_ref") != contract.get("section_ref"):
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"{move_ref} proof binds the wrong Section"))
        if item.get("move_source_digest") != node.get("source_digest"):
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"{move_ref} proof binds an obsolete Move source digest"))
        if item.get("contract_sha256") != binding["contract_sha256"] or item.get("authority_digest") != binding["authority_digest"]:
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"{move_ref} proof does not bind current contract/authority digests"))
        if item.get("manuscript_sha256") != current_manuscript.get("sha256"):
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"{move_ref} proof does not bind the current canonical manuscript"))

        raw_evidence = _list(item.get("evidence_items"))
        evidence_by_kind: dict[str, dict[str, str]] = {}
        evidence_paths: dict[str, Path] = {}
        for evidence_item in raw_evidence:
            if not isinstance(evidence_item, dict):
                issues.append(CompilerIssue("MS-REBUILD-PROOF", f"{move_ref} evidence_items must contain objects"))
                continue
            kind = _text(evidence_item.get("evidence_kind"))
            if not kind or kind in evidence_by_kind:
                issues.append(CompilerIssue("MS-REBUILD-PROOF", f"{move_ref} has a missing or duplicate evidence kind"))
                continue
            evidence, evidence_issue = _rebuild_evidence(
                outdir,
                _text(evidence_item.get("evidence_path")),
                kind,
            )
            if evidence_issue:
                issues.append(evidence_issue)
                continue
            assert evidence is not None
            relative = evidence["evidence_path"]
            owner = path_owner.get(relative)
            if owner is not None:
                issues.append(
                    CompilerIssue(
                        "MS-REBUILD-PROOF",
                        f"rebuild evidence path {relative} is reused by {owner} and {move_ref}; every Move requires distinct evidence",
                        relative,
                    )
                )
            else:
                path_owner[relative] = move_ref
            digest = evidence["evidence_sha256"]
            if kind in {"prose_packet", "writer_draft", "clarity_draft", "section_output"}:
                digest_move = digest_owner.get(digest)
                if digest_move is not None and digest_move != move_ref:
                    issues.append(
                        CompilerIssue(
                            "MS-REBUILD-PROOF",
                            f"identical rebuild evidence is reused by {digest_move} and {move_ref}",
                            relative,
                        )
                    )
                else:
                    digest_owner[digest] = move_ref
            if evidence_item.get("evidence_sha256") != digest:
                issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"{move_ref} rebuild evidence changed after recording", relative))
            evidence_by_kind[kind] = evidence
            evidence_paths[kind] = outdir / Path(relative)

        required_kinds = REBUILD_REQUIRED_KINDS
        if "prose_packet" in evidence_paths:
            try:
                raw_packet = _read_json(evidence_paths["prose_packet"])
                if isinstance(raw_packet.get("claim"), dict) and raw_packet["claim"].get("realization_mode") == "verbatim":
                    required_kinds = required_kinds - {"semantic_dispatch", "semantic_assurance"}
            except (OSError, ValueError, TypeError):
                pass  # The regular packet validator below reports the failure.
        missing_kinds = sorted(required_kinds - set(evidence_by_kind))
        if missing_kinds:
            issues.append(
                CompilerIssue(
                    "MS-STALE-UNREBUILT",
                    f"{move_ref} lacks the complete ProsePacket -> Writer -> Clarity -> Semantic Fidelity proof chain: "
                    + ", ".join(missing_kinds),
                    REBUILD_REL.as_posix(),
                )
            )
            continue
        packet, runtime, registered, accepted, packet_issues = _packet_for_move_issues(
            outdir,
            evidence_paths["prose_packet"],
            move_ref,
            node,
            authority_snapshots,
        )
        issues.extend(packet_issues)
        if packet is None or runtime is None or packet_issues:
            continue
        writer_path = evidence_paths["writer_draft"]
        clarity_path = evidence_paths["clarity_draft"]
        ledger_path = evidence_paths["clarity_ledger"]
        locked = packet.get("claim", {}).get("realization_mode") == "verbatim"
        try:
            writer_draft = writer_path.read_text(encoding="utf-8-sig")
            clarity_draft = clarity_path.read_text(encoding="utf-8-sig")
            ledger = _read_json(ledger_path)
            if not locked:
                dispatch_path = evidence_paths["semantic_dispatch"]
                assurance_path = evidence_paths["semantic_assurance"]
                dispatch = _read_json(dispatch_path)
                assurance = _read_json(assurance_path)
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            issues.append(
                CompilerIssue(
                    "MS-REBUILD-PROOF",
                    f"{move_ref} proof-chain artifact cannot be read: {exc}",
                    REBUILD_REL.as_posix(),
                )
            )
            continue

        for label, draft, path in (
            ("writer_draft", writer_draft, writer_path),
            ("clarity_draft", clarity_draft, clarity_path),
        ):
            try:
                fidelity_issues = runtime.validate_draft_fidelity(
                    packet,
                    draft,
                    registered_ids=registered,
                    accepted_result_claims=accepted,
                )
            except Exception as exc:
                fidelity_issues = [str(exc)]
            for message in fidelity_issues:
                issues.append(
                    CompilerIssue(
                        "MS-REBUILD-PROOF",
                        f"{move_ref} {label} is not faithful to its ProsePacket: {message}",
                        _canonical_workspace_relative(outdir, path).as_posix(),
                    )
                )
        try:
            clarity_issues = runtime.validate_clarity(
                packet,
                writer_draft,
                clarity_draft,
                ledger,
                registered_ids=registered,
                accepted_result_claims=accepted,
            )
        except Exception as exc:
            clarity_issues = [str(exc)]
        for message in clarity_issues:
            issues.append(
                CompilerIssue(
                    "MS-REBUILD-PROOF",
                    f"{move_ref} Clarity gate did not pass: {message}",
                    _canonical_workspace_relative(outdir, ledger_path).as_posix(),
                )
            )

        if locked:
            if writer_draft.strip() != packet["claim"]["text"].strip() or clarity_draft != writer_draft:
                issues.append(CompilerIssue(
                    "MS-REBUILD-PROOF", f"{move_ref} locked Move must preserve exactly its authority text without added sentences or Clarity rewriting",
                    _canonical_workspace_relative(outdir, clarity_path).as_posix(),
                ))
        else:
            expected_packet_rel = _canonical_workspace_relative(
                outdir, evidence_paths["prose_packet"]
            ).as_posix()
            expected_clarity_rel = _canonical_workspace_relative(outdir, clarity_path).as_posix()
            expected_dispatch_rel = _canonical_workspace_relative(outdir, dispatch_path).as_posix()
            if (
                dispatch.get("packet_path") != expected_packet_rel
                or dispatch.get("draft_path") != expected_clarity_rel
                or assurance.get("dispatch_manifest_path") != expected_dispatch_rel
            ):
                issues.append(
                    CompilerIssue(
                        "MS-REBUILD-PROOF",
                        f"{move_ref} semantic assurance does not bind this exact ProsePacket and Clarity draft",
                        _canonical_workspace_relative(outdir, dispatch_path).as_posix(),
                    )
                )
            try:
                semantic_issues = runtime.validate_semantic_fidelity_review(
                    outdir,
                    dispatch_path,
                    assurance_path,
                    registered_ids=registered,
                )
            except Exception as exc:
                semantic_issues = [str(exc)]
            for message in semantic_issues:
                issues.append(
                    CompilerIssue(
                        "MS-REBUILD-PROOF",
                        f"{move_ref} Semantic Fidelity assurance did not pass: {message}",
                        _canonical_workspace_relative(outdir, assurance_path).as_posix(),
                    )
                )

        compact_draft = "".join(clarity_draft.split()).casefold()
        if not compact_draft or compact_draft not in compact_manuscript:
            issues.append(
                CompilerIssue(
                    "MS-STALE-UNREBUILT",
                    f"{move_ref} semantically assured Clarity output is not realized in the current canonical manuscript",
                    _canonical_workspace_relative(outdir, clarity_path).as_posix(),
                )
            )
        section_output = evidence_by_kind.get("section_output")
        if section_output is not None and section_output.get("evidence_sha256") != evidence_by_kind["clarity_draft"].get("evidence_sha256"):
            issues.append(
                CompilerIssue(
                    "MS-REBUILD-PROOF",
                    f"{move_ref} optional section_output must be byte-identical to the semantically assured Clarity draft",
                    _canonical_workspace_relative(
                        outdir, evidence_paths["section_output"]
                    ).as_posix(),
                )
            )
    return issues


def record_rebuild_proofs(
    outdir: Path,
    config: Mapping[str, Any] | None,
    entries: Iterable[tuple[str, str, str | Path]],
) -> Path:
    """Bind explicit per-Move rebuild evidence to the current stale closure.

    This is transient build proof only. It is neither a stage receipt nor a
    scientific authority and cannot advance the controller by itself.
    """

    outdir = outdir.resolve()
    compilation = compile_workspace(outdir, config)
    if compilation.issues or compilation.ir is None:
        raise ManuscriptCompilerError("cannot record rebuild proof for an invalid manuscript contract", compilation.issues)
    stale_refs = set(_text(value) for value in _list(compilation.stale.get("stale_move_refs")))
    previous, previous_issue = _load_previous_ir(outdir)
    if previous_issue:
        raise ManuscriptCompilerError("cannot record rebuild proof against an invalid prior MIR", (previous_issue,))
    if previous is None or not stale_refs:
        raise ManuscriptCompilerError(
            "rebuild proof is accepted only for an existing stale MIR",
            (CompilerIssue("MS-REBUILD-PROOF", "baseline or current workspaces do not accept rebuild proof"),),
        )
    current_manuscript = compilation.ir.get("manuscript_binding")
    previous_manuscript = previous.get("manuscript_binding")
    if not isinstance(current_manuscript, dict) or not current_manuscript.get("sha256"):
        raise ManuscriptCompilerError(
            "rebuild proof requires a current canonical manuscript binding",
            (CompilerIssue("MS-REBUILD-PROOF", "canonical manuscript is missing"),),
        )
    if current_manuscript == previous_manuscript:
        raise ManuscriptCompilerError(
            "the canonical manuscript has not changed after the stale authority or contract update",
            (CompilerIssue("MS-STALE-UNREBUILT", "rebuild affected prose before recording per-Move proof"),),
        )
    moves = _move_nodes(compilation.ir)
    binding = _rebuild_binding(compilation.ir, compilation.stale)
    proof_path = _safe_workspace_path(outdir, REBUILD_REL)
    existing: dict[str, Any] = {}
    try:
        candidate = _read_json(proof_path)
        if all(candidate.get(key) == value for key, value in binding.items()):
            existing = candidate
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        existing = {}
    items = {
        _text(item.get("move_ref")): dict(item)
        for item in _list(existing.get("items"))
        if isinstance(item, dict) and _text(item.get("move_ref"))
    }
    entry_list = list(entries)
    if not entry_list:
        raise ManuscriptCompilerError(
            "at least one per-Move rebuild proof entry is required",
            (CompilerIssue("MS-REBUILD-PROOF", "provide MOVE, evidence kind, and artifact path"),),
        )
    issues: list[CompilerIssue] = []
    for raw_move, kind, artifact in entry_list:
        move_ref = _text(raw_move)
        if move_ref not in stale_refs or move_ref not in moves:
            issues.append(CompilerIssue("MS-REBUILD-PROOF", f"{move_ref or '<missing>'} is not in the current stale Move closure"))
            continue
        evidence, issue = _rebuild_evidence(outdir, artifact, kind)
        if issue:
            issues.append(issue)
            continue
        node = moves[move_ref]
        prior = items.get(move_ref, {})
        evidence_by_kind = {
            _text(item.get("evidence_kind")): dict(item)
            for item in _list(prior.get("evidence_items"))
            if isinstance(item, dict) and _text(item.get("evidence_kind"))
        }
        evidence_by_kind[_text(kind)] = dict(evidence or {})
        items[move_ref] = {
            "move_ref": move_ref,
            "section_ref": node.get("contract", {}).get("section_ref"),
            "move_source_digest": node.get("source_digest"),
            "evidence_items": [evidence_by_kind[key] for key in sorted(evidence_by_kind)],
            "contract_sha256": binding["contract_sha256"],
            "authority_digest": binding["authority_digest"],
            "manuscript_sha256": current_manuscript.get("sha256"),
        }
    if issues:
        raise ManuscriptCompilerError("invalid per-Move rebuild proof", issues)
    payload = {
        "schema_version": REBUILD_SCHEMA_VERSION,
        "control_plane": "cnki-paper",
        "owner_stage": "build",
        "authority_class": "transient_build_proof",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **binding,
        "items": [items[key] for key in sorted(items)],
    }
    proof_issues = _rebuild_schema_issues(payload)
    proof_issues.extend(
        _rebuild_items_issues(
            outdir,
            compilation.ir,
            compilation.stale,
            payload["items"],
            require_full_coverage=False,
        )
    )
    if proof_issues:
        raise ManuscriptCompilerError("invalid per-Move rebuild proof", proof_issues)
    _atomic_write_many(outdir, {REBUILD_REL: json.dumps(payload, ensure_ascii=False, indent=2) + "\n"})
    return proof_path


def _rebuild_proof_issues(
    outdir: Path,
    ir: Mapping[str, Any],
    stale: Mapping[str, Any],
) -> tuple[list[CompilerIssue], dict[str, str]]:
    path = _safe_workspace_path(outdir, REBUILD_REL)
    try:
        payload = _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return [CompilerIssue("MS-STALE-UNREBUILT", f"per-Move rebuild proof is missing or invalid: {exc}", REBUILD_REL.as_posix())], {}
    issues: list[CompilerIssue] = []
    issues.extend(_rebuild_schema_issues(payload))
    binding = _rebuild_binding(ir, stale)
    if payload.get("schema_version") != REBUILD_SCHEMA_VERSION:
        issues.append(CompilerIssue("MS-REBUILD-PROOF", f"rebuild proof must use {REBUILD_SCHEMA_VERSION}", REBUILD_REL.as_posix()))
    for key, expected in binding.items():
        if payload.get(key) != expected:
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", f"rebuild proof no longer binds current {key}", REBUILD_REL.as_posix()))
    if payload.get("authority_class") != "transient_build_proof" or payload.get("owner_stage") != "build":
        issues.append(CompilerIssue("MS-REBUILD-PROOF", "rebuild proof cannot be a scientific authority or stage receipt", REBUILD_REL.as_posix()))
    issues.extend(
        _rebuild_items_issues(
            outdir,
            ir,
            stale,
            _list(payload.get("items")),
            require_full_coverage=True,
        )
    )
    proof_binding = {"path": REBUILD_REL.as_posix(), "sha256": _sha256(path)} if not issues else {}
    return issues, proof_binding


def receipt_closure_paths(outdir: Path) -> tuple[str, ...]:
    """Expand the trace -> stale -> proof -> leaf closure for receipt hashing.

    Declared missing leaves remain in the returned manifest so fingerprinting
    hashes them as unreadable instead of silently dropping their identity.
    """

    outdir = outdir.resolve()
    trace_path = _safe_workspace_path(outdir, TRACE_REL)
    try:
        trace = _read_json(trace_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return ()
    if trace.get("schema_version") != TRACE_SCHEMA_VERSION:
        return ()
    paths: set[str] = {
        TRACE_REL.as_posix(),
        CONTRACT_REL.as_posix(),
        IR_REL.as_posix(),
        STALE_REL.as_posix(),
    }
    stale_path = _safe_workspace_path(outdir, STALE_REL)
    try:
        stale = _read_json(stale_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return tuple(sorted(paths))
    proof_binding = stale.get("rebuild_proof") if isinstance(stale.get("rebuild_proof"), dict) else {}
    if proof_binding.get("path") != REBUILD_REL.as_posix():
        return tuple(sorted(paths))
    paths.add(REBUILD_REL.as_posix())
    proof_path = _safe_workspace_path(outdir, REBUILD_REL)
    try:
        proof = _read_json(proof_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return tuple(sorted(paths))

    evidence_by_kind: dict[str, list[str]] = {}
    for item in _list(proof.get("items")):
        if not isinstance(item, dict):
            continue
        for evidence in _list(item.get("evidence_items")):
            if not isinstance(evidence, dict):
                continue
            raw = _text(evidence.get("evidence_path"))
            kind = _text(evidence.get("evidence_kind"))
            try:
                normalized = _canonical_workspace_relative(outdir, raw).as_posix()
            except (OSError, ValueError):
                continue
            if normalized != Path(raw).as_posix():
                continue
            paths.add(normalized)
            evidence_by_kind.setdefault(kind, []).append(normalized)

    nested_keys = {
        "semantic_dispatch": (
            "packet_path",
            "draft_path",
            "prompt_path",
            "review_output_path",
        ),
        "semantic_assurance": (
            "dispatch_manifest_path",
            "prompt_path",
            "output_path",
        ),
    }
    for kind, keys in nested_keys.items():
        for relative in evidence_by_kind.get(kind, []):
            try:
                payload = _read_json(_safe_workspace_path(outdir, relative))
            except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
                continue
            for key in keys:
                raw = _text(payload.get(key))
                try:
                    normalized = _canonical_workspace_relative(outdir, raw).as_posix()
                except (OSError, ValueError):
                    continue
                if normalized == Path(raw).as_posix():
                    paths.add(normalized)
    return tuple(sorted(paths))


def _archive_legacy_views(
    outdir: Path,
    replacements: Mapping[Path, str],
) -> tuple[Path, ...]:
    # Baseline is only legal without any AMC lineage. Archive every ordinary
    # legacy target that would be replaced; an AMC marker or valid AMC trace
    # without its MIR is rejected earlier as orphaned lineage, not overwritten.
    legacy = [
        relative
        for relative in (*VIEW_RELS, TRACE_REL)
        if _safe_workspace_path(outdir, relative).is_file()
    ]
    if not legacy:
        return ()
    archive_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    destination_rel = LEGACY_ARCHIVE_ROOT_REL / archive_id
    destination = _safe_workspace_path(outdir, destination_rel)
    staging = _safe_workspace_path(
        outdir,
        MANUSCRIPT_ROOT_REL / f".legacy-archive-{uuid.uuid4().hex}",
    )
    staging.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    try:
        for relative in legacy:
            source = _safe_workspace_path(outdir, relative)
            archived = staging / relative
            archived.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, archived)
            entries.append(
                {
                    "original_path": relative.as_posix(),
                    "archived_path": (destination_rel / relative).as_posix(),
                    "sha256": _sha256(source),
                    "bytes": source.stat().st_size,
                    "replacement_sha256": hashlib.sha256(
                        replacements[relative].encode("utf-8")
                    ).hexdigest(),
                }
            )
        manifest = {
            "schema_version": LEGACY_ARCHIVE_SCHEMA_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "reason": "explicit AMC baseline preserved every pre-existing target before first trusted MIR render",
            "entries": entries,
        }
        manifest_path = staging / "archive_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="",
        )
        _safe_workspace_path(outdir, destination_rel.parent).mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return tuple(
        [destination_rel / "archive_manifest.json"]
        + [destination_rel / relative for relative in legacy]
    )


def _atomic_write_bytes(outdir: Path, files: Mapping[Path, bytes]) -> None:
    staging = _safe_workspace_path(
        outdir,
        MANUSCRIPT_ROOT_REL / f".restore-{uuid.uuid4().hex}",
    )
    staging.mkdir(parents=True, exist_ok=False)
    backups: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        staged: dict[Path, Path] = {}
        for relative, content in files.items():
            destination = _safe_workspace_path(outdir, relative)
            temporary = staging / relative.as_posix().replace("/", "__")
            temporary.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_bytes(content)
            staged[destination] = temporary
            backups[destination] = destination.read_bytes() if destination.is_file() else None
        for destination, temporary in staged.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, destination)
            replaced.append(destination)
    except Exception:
        for destination in reversed(replaced):
            original = backups[destination]
            if original is None:
                destination.unlink(missing_ok=True)
            else:
                rollback = staging / f"rollback-{uuid.uuid4().hex}"
                rollback.write_bytes(original)
                os.replace(rollback, destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def restore_legacy_archive(
    outdir: Path,
    manifest_path: str | Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Verify and optionally restore a baseline archive without overwriting drift."""

    outdir = outdir.resolve()
    try:
        manifest_file = _safe_workspace_path(outdir, manifest_path)
        manifest_relative = _canonical_workspace_relative(outdir, manifest_file).as_posix()
        manifest_file.relative_to(_safe_workspace_path(outdir, LEGACY_ARCHIVE_ROOT_REL))
        manifest = _read_json(manifest_file)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManuscriptCompilerError(
            "legacy archive restore manifest is invalid",
            (CompilerIssue("MS-LEGACY-RESTORE", str(exc), _text(manifest_path)),),
        ) from exc
    if manifest.get("schema_version") != LEGACY_ARCHIVE_SCHEMA_VERSION:
        raise ManuscriptCompilerError(
            "legacy archive restore manifest is invalid",
            (CompilerIssue("MS-LEGACY-RESTORE", f"manifest must use {LEGACY_ARCHIVE_SCHEMA_VERSION}", manifest_relative),),
        )
    entries = _list(manifest.get("entries"))
    issues: list[CompilerIssue] = []
    restore_files: dict[Path, bytes] = {}
    receipt_entries: list[dict[str, str]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            issues.append(CompilerIssue("MS-LEGACY-RESTORE", "archive entry must be an object", manifest_relative))
            continue
        original_raw = Path(_text(raw.get("original_path")))
        archived_raw = Path(_text(raw.get("archived_path")))
        try:
            original = _safe_workspace_path(outdir, original_raw)
            archived = _safe_workspace_path(outdir, archived_raw)
            archived.relative_to(manifest_file.parent.resolve())
            original_rel = _canonical_workspace_relative(outdir, original)
            archived_rel = _canonical_workspace_relative(outdir, archived)
            if original_rel not in {*VIEW_RELS, TRACE_REL}:
                raise ValueError("archive entry targets a path outside the registered legacy-view set")
        except ValueError as exc:
            issues.append(CompilerIssue("MS-LEGACY-RESTORE", str(exc), archived_raw.as_posix()))
            continue
        if not archived.is_file() or _sha256(archived) != raw.get("sha256"):
            issues.append(CompilerIssue("MS-LEGACY-RESTORE", "archived source is missing or has drifted", archived_rel.as_posix()))
            continue
        expected_replacement = _text(raw.get("replacement_sha256"))
        if not original.is_file() or not expected_replacement or _sha256(original) != expected_replacement:
            issues.append(
                CompilerIssue(
                    "MS-LEGACY-RESTORE-DRIFT",
                    "restore target no longer matches the exact AMC replacement recorded at baseline",
                    original_rel.as_posix(),
                )
            )
            continue
        restored = archived.read_bytes()
        restore_files[original_rel] = restored
        receipt_entries.append(
            {
                "path": original_rel.as_posix(),
                "archived_path": archived_rel.as_posix(),
                "before_sha256": expected_replacement,
                "after_sha256": hashlib.sha256(restored).hexdigest(),
            }
        )
    if not entries:
        issues.append(CompilerIssue("MS-LEGACY-RESTORE", "archive manifest contains no restorable entries", manifest_relative))
    if issues:
        raise ManuscriptCompilerError("legacy archive restore refused", issues)
    payload: dict[str, Any] = {
        "schema_version": "avereth-manuscript-legacy-view-restore/v1",
        "status": "APPLIED" if apply else "READY",
        "archive_manifest": {"path": manifest_relative, "sha256": _sha256(manifest_file)},
        "entries": receipt_entries,
    }
    if apply:
        payload["restored_at"] = datetime.now(timezone.utc).isoformat()
        restore_receipt = manifest_file.parent / "restore_manifest.json"
        restore_receipt_rel = _canonical_workspace_relative(outdir, restore_receipt)
        payload["restore_manifest"] = restore_receipt_rel.as_posix()
        restore_files[restore_receipt_rel] = (
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        ).encode("utf-8")
        _atomic_write_bytes(outdir, restore_files)
    return payload


def _stale_manifest(
    ir: Mapping[str, Any],
    stale_before: Mapping[str, Any],
    baseline: bool,
    rebuild_proof: Mapping[str, str] | None = None,
    resolved_change: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": STALE_SCHEMA_VERSION,
        "status": "BASELINED" if baseline else "RESOLVED",
        "current_status": "CURRENT",
        "contract_sha256": ir.get("contract", {}).get("sha256"),
        "ir_source_digest": ir.get("source_digest"),
        "manuscript_binding": ir.get("manuscript_binding"),
        "rebuild_proof": dict(rebuild_proof or {}),
        "resolved_change": dict(resolved_change if resolved_change is not None else stale_before),
    }


def _trace_manifest(ir: Mapping[str, Any], views: Mapping[Path, str], stale_text: str) -> dict[str, Any]:
    ir_text = json.dumps(ir, ensure_ascii=False, indent=2) + "\n"
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "compiler_version": VERSION,
        "control_plane": "cnki-paper",
        "owner_stage": "build",
        "authority_class": "derived_projection",
        "contract": ir.get("contract"),
        "manuscript_ir": {"path": IR_REL.as_posix(), "sha256": hashlib.sha256(ir_text.encode("utf-8")).hexdigest()},
        "stale_manifest": {"path": STALE_REL.as_posix(), "sha256": hashlib.sha256(stale_text.encode("utf-8")).hexdigest()},
        "profile": ir.get("profile"),
        "manuscript_binding": ir.get("manuscript_binding"),
        "authority_snapshot": ir.get("authority_snapshot"),
        "section_digests": {
            _text(node.get("contract", {}).get("section_id")): node.get("output_digest")
            for node in _list(ir.get("sections"))
            if isinstance(node, dict)
        },
        "move_digests": {
            _text(node.get("contract", {}).get("move_id")): node.get("output_digest")
            for node in _list(ir.get("moves"))
            if isinstance(node, dict)
        },
        "generated_views": [
            {"path": path.as_posix(), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
            for path, text in sorted(views.items(), key=lambda item: item[0].as_posix())
        ],
    }


def _atomic_write_many(outdir: Path, files: Mapping[Path, str]) -> None:
    staging = _safe_workspace_path(
        outdir,
        MANUSCRIPT_ROOT_REL / f".render-{uuid.uuid4().hex}",
    )
    staging.mkdir(parents=True, exist_ok=False)
    backups: dict[Path, bytes | None] = {}
    replaced: list[Path] = []
    try:
        staged: dict[Path, Path] = {}
        for relative, content in files.items():
            destination = _safe_workspace_path(outdir, relative)
            temporary = staging / relative.as_posix().replace("/", "__")
            temporary.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(content, encoding="utf-8", newline="")
            staged[destination] = temporary
            backups[destination] = destination.read_bytes() if destination.is_file() else None
        for destination, temporary in staged.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, destination)
            replaced.append(destination)
    except Exception:
        for destination in reversed(replaced):
            original = backups[destination]
            if original is None:
                destination.unlink(missing_ok=True)
            else:
                rollback = staging / f"rollback-{uuid.uuid4().hex}"
                rollback.write_bytes(original)
                os.replace(rollback, destination)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def render_workspace(
    outdir: Path,
    config: Mapping[str, Any] | None = None,
    *,
    baseline: bool = False,
) -> tuple[Path, ...]:
    """Render MIR and all generated views after explicit baseline/rebuild checks."""

    outdir = outdir.resolve()
    compilation = compile_workspace(outdir, config)
    if compilation.issues or compilation.ir is None:
        raise ManuscriptCompilerError("manuscript compilation failed", compilation.issues)
    previous, previous_issue = _load_previous_ir(outdir)
    if previous_issue:
        raise ManuscriptCompilerError("existing manuscript IR is invalid", (previous_issue,))
    if previous is None and not baseline:
        raise ManuscriptCompilerError(
            "first AMC render requires --baseline; this is the explicit migration/enable boundary",
            (CompilerIssue("MS-BASELINE-REQUIRED", "review the initialized contract and rerun render with --baseline"),),
        )
    if previous is not None and baseline:
        raise ManuscriptCompilerError(
            "--baseline cannot overwrite an existing MIR",
            (CompilerIssue("MS-BASELINE-EXISTS", "use ordinary render after rebuilding the reported stale closure"),),
        )
    stale_before = compilation.stale
    rebuild_proof: dict[str, str] = {}
    resolved_change: Mapping[str, Any] | None = None
    if previous is not None and stale_before.get("stale_move_refs"):
        previous_manuscript = previous.get("manuscript_binding") if isinstance(previous.get("manuscript_binding"), dict) else {}
        current_manuscript = compilation.ir.get("manuscript_binding") if isinstance(compilation.ir.get("manuscript_binding"), dict) else {}
        if not current_manuscript.get("sha256") or previous_manuscript.get("sha256") == current_manuscript.get("sha256"):
            raise ManuscriptCompilerError(
                "authority or contract changes made manuscript moves stale, but the canonical manuscript did not change",
                (
                    CompilerIssue(
                        "MS-STALE-UNREBUILT",
                        "rebuild the affected moves/sections before refreshing AMC: " + ", ".join(stale_before.get("stale_move_refs") or []),
                    ),
                ),
            )
        proof_issues, rebuild_proof = _rebuild_proof_issues(outdir, compilation.ir, stale_before)
        if proof_issues:
            raise ManuscriptCompilerError(
                "authority or contract changes require explicit per-Move rebuild proof; a manuscript byte change alone is insufficient",
                proof_issues,
            )
    elif previous is not None:
        try:
            prior_stale = _read_json(_safe_workspace_path(outdir, STALE_REL))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ManuscriptCompilerError(
                "existing MIR lost its stale/proof lineage during render",
                (
                    CompilerIssue(
                        "MS-IR-ORPHANED",
                        str(exc),
                        STALE_REL.as_posix(),
                    ),
                ),
            ) from exc
        prior_proof = prior_stale.get("rebuild_proof") if isinstance(prior_stale.get("rebuild_proof"), dict) else {}
        prior_change = prior_stale.get("resolved_change") if isinstance(prior_stale.get("resolved_change"), dict) else {}
        if prior_proof and prior_change.get("stale_move_refs"):
            proof_issues, verified_binding = _rebuild_proof_issues(outdir, compilation.ir, prior_change)
            if proof_issues:
                raise ManuscriptCompilerError(
                    "previous rebuild evidence is no longer current and cannot be discarded by a no-op render",
                    proof_issues,
                )
            rebuild_proof = verified_binding
            resolved_change = prior_change
    ir = compilation.ir
    views = render_markdown_views(ir)
    stale_payload = _stale_manifest(
        ir,
        stale_before,
        baseline,
        rebuild_proof,
        resolved_change=resolved_change,
    )
    stale_text = json.dumps(stale_payload, ensure_ascii=False, indent=2) + "\n"
    trace_payload = _trace_manifest(ir, views, stale_text)
    files: dict[Path, str] = {
        IR_REL: json.dumps(ir, ensure_ascii=False, indent=2) + "\n",
        STALE_REL: stale_text,
        TRACE_REL: json.dumps(trace_payload, ensure_ascii=False, indent=2) + "\n",
        **views,
    }
    archived = _archive_legacy_views(outdir, files) if baseline else ()
    _atomic_write_many(outdir, files)
    return tuple(sorted((*files, *archived), key=lambda path: path.as_posix()))


def validate_workspace(outdir: Path, config: Mapping[str, Any] | None = None) -> list[CompilerIssue]:
    """Validate current MIR, generated views, manuscript binding, and stale closure."""

    outdir = outdir.resolve()
    compilation = compile_workspace(outdir, config)
    issues = list(compilation.issues)
    if compilation.ir is None:
        return issues
    if compilation.stale.get("status") != "CURRENT":
        issues.append(
            CompilerIssue(
                "MS-STALE",
                "MIR is stale; affected moves: " + ", ".join(compilation.stale.get("stale_move_refs") or []),
                IR_REL.as_posix(),
            )
        )
        return issues
    ir_path = outdir / IR_REL
    try:
        recorded_ir = _read_json(ir_path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        return issues + [CompilerIssue("MS-IR-MISSING", f"cannot read rendered MIR: {exc}", IR_REL.as_posix())]
    if recorded_ir != compilation.ir:
        issues.append(CompilerIssue("MS-IR-DRIFT", "rendered MIR differs from the current deterministic compilation", IR_REL.as_posix()))
        return issues
    from commonplace_writing import validate_workspace_runs
    try:
        config_path = outdir / "workflow_config.json"
        active_config = dict(config) if config is not None else (_read_json(config_path) if config_path.exists() else {})
        if active_config.get("prose_conditioning", "none") in {"auto", "commonplace"} or (outdir / ".avereth-prose/commonplace_runs.json").exists():
            current_text = _canonical_manuscript_text(outdir, recorded_ir.get("manuscript_binding", {}))
            for message in validate_workspace_runs(outdir, recorded_ir, active_config, current_text):
                issues.append(CompilerIssue("MS-COMMONPLACE", message, ".avereth-prose/commonplace_runs.json"))
    except (OSError, ValueError, TypeError, KeyError) as exc:
        issues.append(CompilerIssue("MS-COMMONPLACE", str(exc), ".avereth-prose/commonplace_runs.json"))
    expected_views = render_markdown_views(recorded_ir)
    for relative, expected in expected_views.items():
        path = outdir / relative
        try:
            actual = path.read_text(encoding="utf-8-sig")
        except OSError:
            actual = ""
        if actual != expected:
            issues.append(CompilerIssue("MS-VIEW-DRIFT", "generated manuscript view is missing or was hand-edited", relative.as_posix()))
    stale_path = outdir / STALE_REL
    try:
        stale_payload = _read_json(stale_path)
        stale_text = stale_path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        issues.append(CompilerIssue("MS-STALE-MANIFEST", f"cannot read stale manifest: {exc}", STALE_REL.as_posix()))
        return issues
    if (
        stale_payload.get("schema_version") != STALE_SCHEMA_VERSION
        or stale_payload.get("current_status") != "CURRENT"
        or stale_payload.get("contract_sha256") != recorded_ir.get("contract", {}).get("sha256")
        or stale_payload.get("ir_source_digest") != recorded_ir.get("source_digest")
        or stale_payload.get("manuscript_binding") != recorded_ir.get("manuscript_binding")
    ):
        issues.append(CompilerIssue("MS-STALE-MANIFEST", "stale manifest does not bind the current contract, MIR, and manuscript", STALE_REL.as_posix()))
    proof_binding = stale_payload.get("rebuild_proof") if isinstance(stale_payload.get("rebuild_proof"), dict) else {}
    if proof_binding:
        try:
            proof_path = _safe_workspace_path(outdir, _text(proof_binding.get("path")))
        except ValueError as exc:
            issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", str(exc), STALE_REL.as_posix()))
        else:
            if not proof_path.is_file() or _sha256(proof_path) != proof_binding.get("sha256"):
                issues.append(CompilerIssue("MS-REBUILD-PROOF-STALE", "resolved rebuild proof changed or disappeared", REBUILD_REL.as_posix()))
            else:
                resolved_change = stale_payload.get("resolved_change") if isinstance(stale_payload.get("resolved_change"), dict) else {}
                if not resolved_change.get("stale_move_refs"):
                    issues.append(
                        CompilerIssue(
                            "MS-REBUILD-PROOF-STALE",
                            "stale manifest lost the resolved Move closure needed to revalidate rebuild evidence",
                            STALE_REL.as_posix(),
                        )
                    )
                else:
                    evidence_issues, verified_binding = _rebuild_proof_issues(
                        outdir,
                        recorded_ir,
                        resolved_change,
                    )
                    issues.extend(evidence_issues)
                    if not evidence_issues and verified_binding != proof_binding:
                        issues.append(
                            CompilerIssue(
                                "MS-REBUILD-PROOF-STALE",
                                "stale manifest rebuild-proof binding differs from the revalidated proof",
                                STALE_REL.as_posix(),
                            )
                        )
    expected_trace = _trace_manifest(recorded_ir, expected_views, stale_text)
    try:
        actual_trace = _read_json(outdir / TRACE_REL)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        issues.append(CompilerIssue("MS-TRACE-MISSING", f"cannot read manuscript trace manifest: {exc}", TRACE_REL.as_posix()))
    else:
        if actual_trace != expected_trace:
            issues.append(CompilerIssue("MS-TRACE-DRIFT", "manuscript trace manifest differs from the current compiled graph and views", TRACE_REL.as_posix()))
    return issues


def _json_ids(payload: Mapping[str, Any], container_key: str) -> list[str]:
    return _collection_ids(payload, container_key)


def init_contract(
    outdir: Path,
    config: Mapping[str, Any] | None = None,
    profile_id: str | None = None,
) -> dict[str, Any]:
    """Create an in-memory empirical contract from existing authority identities.

    The initializer copies no scientific propositions. It creates local aliases
    for whole-file authorities and selectors for existing Claim/Result objects.
    """

    outdir = outdir.resolve()
    required = {
        "question": Path("confirmed_motivation.md"),
        "literature": Path("literature_analysis.json"),
        "design": Path("research_design.json"),
        "execution": Path("method_execution.json"),
        "contribution": Path("confirmed_contribution.md"),
    }
    source_registry = Path("reference_materials/literature_registry.json")
    material_registry = Path("reference_materials/research_material_registry.json")
    missing = [relative.as_posix() for relative in required.values() if not (outdir / relative).is_file()]
    if missing:
        raise ManuscriptCompilerError(
            "AMC initialization requires current research/design/execution authorities",
            (CompilerIssue("MS-INIT-AUTHORITY-MISSING", "missing: " + ", ".join(missing)),),
        )
    try:
        design = _read_json(outdir / required["design"])
        execution = _read_json(outdir / required["execution"])
        sources = _read_json(outdir / source_registry) if (outdir / source_registry).is_file() else {}
        materials = _read_json(outdir / material_registry) if (outdir / material_registry).is_file() else {}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManuscriptCompilerError(f"cannot initialize AMC from authority JSON: {exc}") from exc
    selected_profile = _text(profile_id) or select_profile_id(config, design)
    try:
        profile = _read_json(profile_path(selected_profile))
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise ManuscriptCompilerError(f"cannot read manuscript profile {selected_profile}: {exc}") from exc
    ordinary_claim_ids = _json_ids(design, "claims")
    hypothesis_ids = _json_ids(design, "hypotheses")
    proposition_ids = _json_ids(design, "propositions")
    claim_ids = list(dict.fromkeys(ordinary_claim_ids + hypothesis_ids + proposition_ids))
    evidence_ids = _json_ids(design, "evidence")
    source_ids = _json_ids(sources, "sources")
    material_ids = _json_ids(materials, "materials")
    result_ids = _json_ids(execution, "results")
    if not claim_ids or not result_ids:
        raise ManuscriptCompilerError(
            "AMC initialization needs at least one registered Claim and one registered Result",
            (CompilerIssue("MS-INIT-IDENTITY-MISSING", "research_design.json claims[] and method_execution.json results[] must be non-empty"),),
        )
    bindings: list[dict[str, Any]] = [
        {"ref_id": "RQ-MAIN", "authority_kind": "research_question", "source_path": required["question"].as_posix(), "selector": {"type": "whole_file"}},
        {"ref_id": "DESIGN-MAIN", "authority_kind": "design", "source_path": required["design"].as_posix(), "selector": {"type": "whole_file"}},
        {"ref_id": "CONTRIBUTION-MAIN", "authority_kind": "contribution", "source_path": required["contribution"].as_posix(), "selector": {"type": "whole_file"}},
        {"ref_id": "SCOPE-MAIN", "authority_kind": "scope", "source_path": required["design"].as_posix(), "selector": {"type": "whole_file"}},
        {"ref_id": "LITERATURE-MAIN", "authority_kind": "literature", "source_path": required["literature"].as_posix(), "selector": {"type": "whole_file"}},
    ]
    for claim_id in claim_ids:
        id_keys = ["id", "claim_id"]
        if claim_id in hypothesis_ids:
            id_keys.append("hypothesis_id")
        if claim_id in proposition_ids:
            id_keys.append("proposition_id")
        bindings.append(
            {
                "ref_id": claim_id,
                "authority_kind": "claim",
                "source_path": required["design"].as_posix(),
                "selector": {
                    "type": "json_object_id",
                    "id": claim_id,
                    "id_keys": id_keys,
                    "inference_strength_field": "type",
                },
            }
        )
    for evidence_id in evidence_ids:
        bindings.append(
            {
                "ref_id": evidence_id,
                "authority_kind": "evidence",
                "source_path": required["design"].as_posix(),
                "selector": {"type": "json_object_id", "id": evidence_id, "id_keys": ["id", "evidence_id"]},
            }
        )
    for source_id in source_ids:
        bindings.append(
            {
                "ref_id": source_id,
                "authority_kind": "source",
                "source_path": source_registry.as_posix(),
                "selector": {"type": "json_object_id", "id": source_id, "id_keys": ["id", "source_id"]},
            }
        )
    for material_id in material_ids:
        bindings.append(
            {
                "ref_id": material_id,
                "authority_kind": "material",
                "source_path": material_registry.as_posix(),
                "selector": {"type": "json_object_id", "id": material_id, "id_keys": ["id", "material_id"]},
            }
        )
    for result_id in result_ids:
        bindings.append(
            {
                "ref_id": result_id,
                "authority_kind": "result",
                "source_path": required["execution"].as_posix(),
                "selector": {"type": "json_object_id", "id": result_id, "id_keys": ["id", "result_id"]},
            }
        )
    groups = {
        "research_question": ["RQ-MAIN"],
        "claims": claim_ids,
        "contribution": ["CONTRIBUTION-MAIN"],
        "design": ["DESIGN-MAIN"],
        "results": result_ids,
        "scope": ["SCOPE-MAIN"],
        "literature": ["LITERATURE-MAIN"],
    }
    sections: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    previous_section = ""
    for section_template in _list(profile.get("sections")):
        if not isinstance(section_template, dict):
            continue
        move_refs: list[str] = []
        previous_move = ""
        for move_template in _list(section_template.get("required_moves")):
            if not isinstance(move_template, dict):
                continue
            move_id = _text(move_template.get("move_id"))
            authority_groups = [_text(value) for value in _list(move_template.get("authority_groups"))]
            authority_refs = list(dict.fromkeys(ref for group in authority_groups for ref in groups.get(group, [])))
            claim_refs = [ref for ref in authority_refs if ref in claim_ids]
            moves.append(
                {
                    "move_id": move_id,
                    "section_ref": _text(section_template.get("section_id")),
                    "move_type": _text(move_template.get("move_type")),
                    "prose_packet_role": _text(section_template.get("prose_packet_role")),
                    "planned_function": _text(move_template.get("planned_function")),
                    "reader_question": _text(section_template.get("reader_question")),
                    "required_update": _text(move_template.get("planned_function")),
                    "authority_refs": authority_refs,
                    "claim_refs": claim_refs,
                    "dependency_refs": [previous_move] if previous_move else [],
                    "promise_refs": [],
                    "delivery_refs": [],
                    "inference_strength": "inherit",
                }
            )
            move_refs.append(move_id)
            previous_move = move_id
        section = {
            key: section_template.get(key)
            for key in (
                "section_id",
                "semantic_role",
                "section_family",
                "display_heading",
                "reader_state_before_id",
                "reader_state_before",
                "reader_question",
                "required_update",
                "reader_state_after_id",
                "reader_state_after",
            )
        }
        section["dependencies"] = [previous_section] if previous_section else []
        section["move_refs"] = move_refs
        sections.append(section)
        previous_section = _text(section.get("section_id"))
    promises: list[dict[str, Any]] = []
    move_by_id = {_text(move.get("move_id")): move for move in moves}
    for template in _list(profile.get("promise_templates")):
        if not isinstance(template, dict):
            continue
        promise_id = _text(template.get("promise_id"))
        authority_refs = list(
            dict.fromkeys(
                ref
                for group in [_text(value) for value in _list(template.get("authority_groups"))]
                for ref in groups.get(group, [])
            )
        )
        promise = {
            "promise_id": promise_id,
            "promise_type": _text(template.get("promise_type")),
            "source_move_ref": _text(template.get("source_move_ref")),
            "authority_refs": authority_refs,
            "delivery_move_refs": [_text(value) for value in _list(template.get("delivery_move_refs"))],
        }
        promises.append(promise)
        move_by_id[promise["source_move_ref"]]["promise_refs"].append(promise_id)
        for delivery in promise["delivery_move_refs"]:
            move_by_id[delivery]["delivery_refs"].append(promise_id)
    edges = [dict(item) for item in _list(profile.get("edge_templates")) if isinstance(item, dict)]
    for edge in edges:
        source = _text(edge.get("source_ref"))
        target = _text(edge.get("target_ref"))
        if source and target and source not in move_by_id[target]["dependency_refs"]:
            move_by_id[target]["dependency_refs"].append(source)
    lifecycle_template = profile.get("claim_lifecycle") if isinstance(profile.get("claim_lifecycle"), dict) else {}
    lifecycles = [
        {"claim_ref": claim_id, **{stage: list(_list(lifecycle_template.get(stage))) for stage in LIFECYCLE_STAGES}}
        for claim_id in claim_ids
    ]
    active = dict(config or {})
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "contract_id": "AMC-EMPIRICAL-001" if selected_profile == SUPPORTED_PROFILE else "AMC-HUMANITIES-001",
        "compiler_mode": "build_projection",
        "genre_profile": selected_profile,
        "profile_version": _text(profile.get("profile_version")),
        "venue_profile": _text(active.get("target_journal") or active.get("scene") or f"generic-{selected_profile}"),
        "output_language": _text(active.get("output_language") or "zh-CN"),
        "authority_bindings": bindings,
        "global_identity": {
            "research_question_ref": "RQ-MAIN",
            "main_claim_refs": claim_ids,
            "contribution_refs": ["CONTRIBUTION-MAIN"],
            "design_refs": ["DESIGN-MAIN"],
            "result_refs": result_ids,
            "scope_refs": ["SCOPE-MAIN"],
            "literature_refs": ["LITERATURE-MAIN"],
        },
        "narrative_contract": {
            "initial_reader_state": profile.get("initial_reader_state"),
            "final_reader_update": profile.get("final_reader_update"),
            "central_throughline": profile.get("central_throughline"),
        },
        "sections": sections,
        "moves": moves,
        "claim_lifecycle": lifecycles,
        "promises": promises,
        "cross_section_edges": edges,
        "scientific_commitment_order": profile.get("scientific_commitment_order"),
        "render_order": profile.get("render_order"),
    }


def write_initialized_contract(outdir: Path, contract: Mapping[str, Any]) -> Path:
    outdir = outdir.resolve()
    path = _safe_workspace_path(outdir, CONTRACT_REL)
    if path.exists():
        raise ManuscriptCompilerError(
            "manuscript contract already exists; initialization never overwrites it",
            (CompilerIssue("MS-CONTRACT-EXISTS", "edit the existing contract or preserve it before starting a new workspace", CONTRACT_REL.as_posix()),),
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    os.replace(temporary, path)
    return path
