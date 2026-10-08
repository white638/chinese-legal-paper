#!/usr/bin/env python3
"""Compile, route, and verify the internal peer-review lifecycle.

Raw reviewer Markdown remains immutable evidence.  This module compiles those
outputs into ``review_findings.json`` and treats ``review_resolution.json`` as
the only adjudication/closure authority.  The human-readable structured review,
reviewer audit, and revision plan are deterministic views of those two JSON
contracts; they are never independent sources of completion truth.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from revision_contract import (
    STAGE_RANK,
    load_and_validate as load_and_validate_revision_contract,
    route_for_change_classes,
    validate_revision_contract,
)

try:  # package import in the controller
    from . import structured_review
    from ._engine_utils import markdown_tables
except ImportError:  # direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import structured_review  # type: ignore
    from _engine_utils import markdown_tables  # type: ignore


LEGACY_FINDINGS_SCHEMA = "avereth-review-findings/v2"
LEGACY_RESOLUTION_SCHEMA = "avereth-review-resolution/v1"
FINDINGS_SCHEMA = "avereth-review-findings/v3"
RESOLUTION_SCHEMA = "avereth-review-resolution/v2"
ASSURANCE_SCHEMA = "cnki-review-assurance/v2"
DISPATCH_SCHEMA = "avereth-review-dispatch/v2"

ROLE_FILES = {
    "methods": ("methods_reviewer.md", "methods_review_output.md", "MET"),
    "contribution": ("contribution_reviewer.md", "contribution_review_output.md", "CON"),
    "clarity": ("clarity_reviewer.md", "clarity_review_output.md", "CLR"),
}
ROLE_ORDER = tuple(ROLE_FILES)

SEVERITIES = ("CRITICAL", "MAJOR", "MINOR", "OBSERVATION")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")
REPAIR_KINDS = (
    "TEXT_EDIT",
    "ADD_EVIDENCE",
    "RERUN_ANALYSIS",
    "REDESIGN",
    "REOPEN_RESEARCH",
    "NARROW_CLAIM",
    "REMOVE_CLAIM",
    "NO_ACTION",
)
OWNER_STAGES = ("research", "design", "execution", "build")
DISCOVERY_CLASSES = (
    "BASELINE",
    "UNRESOLVED_EXISTING",
    "REVISION_REGRESSION",
    "NEW_MATERIAL",
    "OPTIONAL_POLISH",
)
MATERIALITIES = ("BLOCKING", "NON_BLOCKING")
TEXT_ACTIONS = ("DELETE", "REPLACE", "MOVE", "ADD", "NO_ACTION")
MAPPING_STATES = ("exact", "inferred", "unresolved", "not_applicable")
RESOLUTION_STATES = (
    "OPEN",
    "PLANNED",
    "APPLIED",
    "VERIFIED",
    "MERGED",
    "REJECTED",
    "WAIVED",
    "REOPENED",
)
TERMINAL_STATES = frozenset({"VERIFIED", "MERGED", "REJECTED", "WAIVED"})
SEVERITY_RANK = {severity: index for index, severity in enumerate(SEVERITIES)}
DECISION_BY_STATUS = {
    "OPEN": "PENDING",
    "PLANNED": "ACCEPTED",
    "APPLIED": "ACCEPTED",
    "VERIFIED": "ACCEPTED",
    "MERGED": "MERGED",
    "REJECTED": "REJECTED",
    "WAIVED": "WAIVED",
    "REOPENED": "PENDING",
}
SCIENTIFIC_REPAIRS = frozenset(
    {"ADD_EVIDENCE", "RERUN_ANALYSIS", "REDESIGN", "REOPEN_RESEARCH"}
)
ARTIFACT_KIND_BY_REPAIR = {
    "ADD_EVIDENCE": "evidence",
    "RERUN_ANALYSIS": "execution",
    "REDESIGN": "design",
    "REOPEN_RESEARCH": "research",
}
ARTIFACT_ALLOWED_ROOTS = {
    "execution": (
        "analysis/",
        "results/",
        "execution/",
        "execution_artifacts/",
        "artifacts/",
        "artifacts/execution/",
        "empirical/",
        "repro/",
        "output/tables/",
        "output/figures/",
        "data/processed/",
    ),
    "evidence": (
        "reference_materials/",
        "materials/",
        "evidence/",
        "artifacts/evidence/",
    ),
    "design": (
        "design_artifacts/",
        "artifacts/design/",
        "analysis/design/",
    ),
    "research": (
        "reference_materials/",
        "materials/",
        "research_artifacts/",
        "artifacts/research/",
    ),
}
RERUN_ARTIFACT_DENIED_PATHS = frozenset(
    {
        "workflow_config.json",
        "revision_contract.json",
        "research_design.json",
        "method_execution.json",
        "literature_analysis.json",
        "research_decision.json",
        "research_feasibility.json",
        "review_assurance.json",
        "review_findings.json",
        "review_resolution.json",
        "structured_review.md",
        "reviewer_audit.md",
        "revision_plan.md",
        "audit_run.json",
        "audit_receipt.json",
        "output_run.json",
        "output_receipt.json",
        "claim_register.md",
        "evidence_bank.md",
        "claim_evidence_scope_matrix.md",
        "writing_rationale_matrix.md",
        "reference_materials/literature_registry.json",
        "reference_materials/research_material_registry.json",
        "reference_materials/source_index.md",
        "reference_materials/citation_support_bank.md",
    }
)
STAGE_INDEX = dict(STAGE_RANK)

REPAIR_CHANGE_CLASS = {
    "TEXT_EDIT": "surface",
    "ADD_EVIDENCE": "evidence",
    "RERUN_ANALYSIS": "execution",
    "REDESIGN": "design",
    "REOPEN_RESEARCH": "evidence",
    "NARROW_CLAIM": "argument",
    "REMOVE_CLAIM": "argument",
    "NO_ACTION": "argument",
}


def _repair_change_class(repair_kind: str, text_action: str = "") -> str:
    if repair_kind == "TEXT_EDIT" and text_action == "ADD":
        return "argument"
    return REPAIR_CHANGE_CLASS.get(repair_kind, "argument")
PROPAGATION_TARGETS = (
    "abstract",
    "introduction",
    "analysis_or_results",
    "conclusion",
    "figures_tables",
    "response_materials",
)

ID_PATTERNS = {
    "claim_ids": re.compile(
        r"(?<![A-Za-z0-9])(?:C|CLM|CLAIM)-[A-Za-z0-9][A-Za-z0-9._-]*",
        re.IGNORECASE,
    ),
    "evidence_ids": re.compile(
        r"(?<![A-Za-z0-9])(?:SRC|CR|SYN|EVD|EV)-[A-Za-z0-9][A-Za-z0-9._-]*",
        re.IGNORECASE,
    ),
    "design_ids": re.compile(
        r"(?<![A-Za-z0-9])(?:DESIGN|DSG)-[A-Za-z0-9][A-Za-z0-9._-]*",
        re.IGNORECASE,
    ),
    "execution_ids": re.compile(
        r"(?<![A-Za-z0-9])EXE-[A-Za-z0-9][A-Za-z0-9._-]*",
        re.IGNORECASE,
    ),
}

SUPPORT_FILES = structured_review.REVIEW_MAPPING_INPUTS

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "references" / "schemas"

ALLOWED_TRANSITIONS = {
    "OPEN": {"PLANNED", "MERGED", "REJECTED", "WAIVED"},
    "PLANNED": {"APPLIED", "MERGED", "REJECTED", "WAIVED"},
    "APPLIED": {"VERIFIED", "REOPENED"},
    "VERIFIED": {"REOPENED"},
    "REOPENED": {"PLANNED", "APPLIED"},
    "MERGED": set(),
    "REJECTED": set(),
    "WAIVED": {"REOPENED"},
}


@dataclass
class LifecycleResult:
    ok: bool
    findings: list[str] = field(default_factory=list)
    generated: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class ReviewLifecycleError(ValueError):
    """Raised when immutable review inputs cannot be compiled safely."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError:
        return ""


def _stable_manuscript_unit_id(quoted_span: str) -> str:
    normalized = _normalize_space(quoted_span)
    return "MSU-" + sha256_text(normalized)[:16].upper()


def finding_key(finding: dict[str, Any]) -> str:
    """Return a deterministic cross-cycle identity independent of issue wording."""
    mapping = finding.get("identity_mapping") if isinstance(finding.get("identity_mapping"), dict) else {}
    action = finding.get("recommended_action") if isinstance(finding.get("recommended_action"), dict) else {}
    source = finding.get("source") if isinstance(finding.get("source"), dict) else {}
    locator = finding.get("manuscript_locator") if isinstance(finding.get("manuscript_locator"), dict) else {}
    payload = {
        "role": str(source.get("reviewer_role") or ""),
        "category": str(finding.get("category") or ""),
        "repair_kind": str(action.get("repair_kind") or ""),
        "claim_ids": sorted(str(item) for item in mapping.get("claim_ids") or []),
        "evidence_ids": sorted(str(item) for item in mapping.get("evidence_ids") or []),
        "design_ids": sorted(str(item) for item in mapping.get("design_ids") or []),
        "execution_ids": sorted(str(item) for item in mapping.get("execution_ids") or []),
        "manuscript_unit_id": str(
            locator.get("manuscript_unit_id")
            or _stable_manuscript_unit_id(str(locator.get("quoted_span") or ""))
        ),
    }
    digest = sha256_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return "RFK-" + digest[:24].upper()


def _materiality(severity: str, discovery_class: str) -> str:
    if discovery_class == "OPTIONAL_POLISH" or severity == "OBSERVATION":
        return "NON_BLOCKING"
    if severity in {"CRITICAL", "MAJOR"}:
        return "BLOCKING"
    if severity == "MINOR" and discovery_class == "REVISION_REGRESSION":
        return "BLOCKING"
    return "NON_BLOCKING"


def _occurrence(finding: dict[str, Any], *, run_id: str, cycle_id: str | None) -> dict[str, Any]:
    source = finding.get("source") if isinstance(finding.get("source"), dict) else {}
    locator = finding.get("manuscript_locator") if isinstance(finding.get("manuscript_locator"), dict) else {}
    return {
        "run_id": run_id,
        "cycle_id": cycle_id,
        "reviewer_role": source.get("reviewer_role"),
        "output_path": source.get("output_path"),
        "output_sha256": source.get("output_sha256"),
        "source_block_sha256": source.get("source_block_sha256"),
        "manuscript_unit_id": locator.get("manuscript_unit_id"),
        "location": locator.get("location"),
    }


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


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


def _schema_pointer(root: dict[str, Any], reference: str) -> dict[str, Any] | None:
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
    schema: dict[str, Any],
    *,
    root: dict[str, Any],
    path: str,
) -> list[str]:
    """Validate the Draft-2020 subset used by the registered review schemas."""
    if "$ref" in schema:
        resolved = _schema_pointer(root, str(schema.get("$ref") or ""))
        if resolved is None:
            return [f"{path}: unresolved schema reference {schema.get('$ref')}"]
        return _schema_node_issues(value, resolved, root=root, path=path)

    issues: list[str] = []
    alternatives = schema.get("anyOf")
    if isinstance(alternatives, list):
        if not any(
            isinstance(option, dict)
            and not _schema_node_issues(value, option, root=root, path=path)
            for option in alternatives
        ):
            issues.append(f"{path}: value does not match any allowed schema shape")
            return issues

    expected_type = schema.get("type")
    if isinstance(expected_type, str):
        type_ok = _schema_type_matches(value, expected_type)
    elif isinstance(expected_type, list):
        type_ok = any(
            isinstance(item, str) and _schema_type_matches(value, item)
            for item in expected_type
        )
    else:
        type_ok = True
    if not type_ok:
        issues.append(f"{path}: expected JSON type {expected_type}")
        return issues

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
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, (int, float)) and value < minimum:
            issues.append(f"{path}: number is below {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            issues.append(f"{path}: number is above {maximum}")

    if isinstance(value, dict):
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    issues.append(f"{path}: missing required property {key}")
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, child_schema in properties.items():
                if key in value and isinstance(child_schema, dict):
                    issues.extend(
                        _schema_node_issues(
                            value[key], child_schema, root=root, path=f"{path}.{key}"
                        )
                    )
            if schema.get("additionalProperties") is False:
                for key in sorted(set(value) - set(properties)):
                    issues.append(f"{path}: unexpected property {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                additional_schema = schema["additionalProperties"]
                for key in sorted(set(value) - set(properties)):
                    issues.extend(
                        _schema_node_issues(
                            value[key],
                            additional_schema,
                            root=root,
                            path=f"{path}.{key}",
                        )
                    )

    if isinstance(value, list):
        minimum = schema.get("minItems")
        maximum = schema.get("maxItems")
        if isinstance(minimum, int) and len(value) < minimum:
            issues.append(f"{path}: array has fewer than {minimum} items")
        if isinstance(maximum, int) and len(value) > maximum:
            issues.append(f"{path}: array has more than {maximum} items")
        if schema.get("uniqueItems") is True:
            identities = [
                json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                for item in value
            ]
            if len(identities) != len(set(identities)):
                issues.append(f"{path}: array items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                issues.extend(
                    _schema_node_issues(
                        item, item_schema, root=root, path=f"{path}[{index}]"
                    )
                )

    all_of = schema.get("allOf")
    if isinstance(all_of, list):
        for constraint in all_of:
            if not isinstance(constraint, dict):
                continue
            condition = constraint.get("if")
            if isinstance(condition, dict):
                condition_matches = not _schema_node_issues(
                    value, condition, root=root, path=path
                )
                branch = constraint.get("then" if condition_matches else "else")
                if isinstance(branch, dict):
                    issues.extend(_schema_node_issues(value, branch, root=root, path=path))
            else:
                issues.extend(_schema_node_issues(value, constraint, root=root, path=path))
    return issues


def _registered_schema_issues(
    payload: dict[str, Any], schema_filename: str, label: str
) -> list[str]:
    try:
        schema = json.loads((SCHEMA_DIR / schema_filename).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        return [f"{label}: registered schema is unavailable or invalid: {exc}"]
    if not isinstance(schema, dict):
        return [f"{label}: registered schema root must be an object"]
    return [
        f"{label} schema: {issue}"
        for issue in _schema_node_issues(payload, schema, root=schema, path="$")
    ]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def _workspace_path(outdir: Path, relative: str) -> Path | None:
    """Resolve a slash-normalized workspace path without accepting traversal."""
    candidate = (outdir / Path(relative.replace("\\", "/"))).resolve()
    try:
        return candidate if candidate.is_relative_to(outdir.resolve()) else None
    except (OSError, ValueError):
        return None


def _markdown_table_cell(value: Any) -> str:
    """Render one untrusted JSON value without changing Markdown table shape."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    escaped = html.escape(text, quote=False)
    return escaped.replace("\\", "&#92;").replace("|", "&#124;").replace("\n", "<br>")


def _markdown_table_row(*values: Any) -> str:
    return "| " + " | ".join(_markdown_table_cell(value) for value in values) + " |"


def _label(block: str, name: str) -> str:
    match = re.search(rf"(?im)^\s*{re.escape(name)}\s*[:：]\s*(.*?)\s*$", block)
    return match.group(1).strip() if match else ""


def _clean_quoted_span(value: str) -> str:
    stripped = value.strip()
    pairs = (("`", "`"), ('"', '"'), ("“", "”"), ("'", "'"))
    for start, end in pairs:
        if stripped.startswith(start) and stripped.endswith(end) and len(stripped) > 2:
            return stripped[len(start):-len(end)].strip()
    return stripped


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _quote_in_manuscript(quoted_span: str, manuscript_text: str) -> bool:
    if not quoted_span:
        return False
    return quoted_span in manuscript_text or _normalize_space(quoted_span) in _normalize_space(manuscript_text)


def _ids_in(text: str) -> dict[str, list[str]]:
    return {
        key: sorted({match.group(0).upper() for match in pattern.finditer(text)})
        for key, pattern in ID_PATTERNS.items()
    }


def _merge_ids(*collections: dict[str, list[str]]) -> dict[str, list[str]]:
    return {
        key: sorted({item for collection in collections for item in collection.get(key, [])})
        for key in ID_PATTERNS
    }


def _internal_identity_mapping(
    outdir: Path,
    *,
    block: str,
    location: str,
    quoted_span: str,
    severity: str,
    repair_kind: str,
    text_action: str,
) -> dict[str, Any]:
    exact_collections: list[dict[str, list[str]]] = []
    inferred_collections: list[dict[str, list[str]]] = []
    normalized_quote = _normalize_space(quoted_span)
    location_tokens = [
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9_-]{4,}|[\u3400-\u9fff]{2,}", location)
    ]
    for relative in SUPPORT_FILES:
        path = outdir / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
        except OSError:
            continue
        lines = text.splitlines()
        for index, line in enumerate(lines):
            normalized_line = _normalize_space(line)
            if normalized_quote and normalized_quote in normalized_line:
                window = "\n".join(lines[max(0, index - 1): index + 2])
                exact_collections.append(_ids_in(window))
                continue
            lowered = line.casefold()
            if location_tokens and sum(token in lowered for token in location_tokens) >= min(2, len(location_tokens)):
                window = "\n".join(lines[max(0, index - 1): index + 2])
                inferred_collections.append(_ids_in(window))

    exact = _merge_ids(*exact_collections) if exact_collections else _ids_in("")
    if any(exact.values()):
        return {**exact, "mapping_status": "exact", "mapping_basis": "quoted-span-support-row"}
    inferred = _merge_ids(*inferred_collections) if inferred_collections else _ids_in("")
    if any(inferred.values()):
        return {**inferred, "mapping_status": "inferred", "mapping_basis": "locator-support-row"}
    if severity in {"MINOR", "OBSERVATION"} and (
        repair_kind == "NO_ACTION"
        or (repair_kind == "TEXT_EDIT" and text_action != "ADD")
    ):
        return {
            **_ids_in(""),
            "mapping_status": "not_applicable",
            "mapping_basis": "surface-only-finding",
        }
    return {
        **_ids_in(""),
        "mapping_status": "unresolved",
        "mapping_basis": "no-registered-identity-match",
    }


def _parse_rubric_rows(text: str) -> list[dict[str, str]]:
    for table in markdown_tables(text):
        if not table or [cell.strip().casefold() for cell in table[0]] != [
            "dimension id",
            "applicability",
            "score",
            "reason",
            "manuscript location",
        ]:
            continue
        rows: list[dict[str, str]] = []
        for row in table[1:]:
            if len(row) != 5:
                continue
            rows.append(
                {
                    "dimension_id": row[0].strip(),
                    "applicability": row[1].strip().upper(),
                    "score": row[2].strip(),
                    "reason": row[3].strip(),
                    "manuscript_location": row[4].strip(),
                }
            )
        return rows
    return []


def _source_heading(block: str) -> str:
    match = re.search(r"(?m)^#{1,6}\s+(.+?)\s*$", block)
    return match.group(1).strip() if match else "Finding"


def _parse_finding(
    outdir: Path,
    *,
    role: str,
    context_id: str,
    output_relative: str,
    output_sha256: str,
    block: str,
    manuscript_text: str,
) -> dict[str, Any]:
    finding_id = _label(block, "Finding ID").upper()
    severity = _label(block, "Severity").upper()
    confidence = _label(block, "Confidence").upper()
    category = _label(block, "Category")
    location = _label(block, "Location")
    quoted_span = _clean_quoted_span(_label(block, "Quoted Span"))
    problem = _label(block, "Issue")
    reader_consequence = _label(block, "Reader Consequence")
    repair_kind = _label(block, "Repair Kind").upper()
    owner_stage = _label(block, "Owner Stage").casefold()
    text_action = _label(block, "Text Action").upper()
    recommended_action = _label(block, "Recommended Action")
    delta_raw = _label(block, "Net Word Delta")

    _, _, prefix = ROLE_FILES[role]
    if not re.fullmatch(rf"REV-{prefix}-\d{{3}}", finding_id):
        raise ReviewLifecycleError(
            f"{output_relative}: Finding ID must match REV-{prefix}-NNN, got {finding_id or '<empty>'}"
        )
    if severity not in SEVERITIES:
        raise ReviewLifecycleError(f"{finding_id}: invalid Severity {severity or '<empty>'}")
    if confidence not in CONFIDENCES:
        raise ReviewLifecycleError(f"{finding_id}: invalid Confidence {confidence or '<empty>'}")
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", category):
        raise ReviewLifecycleError(f"{finding_id}: Category must be a stable snake_case identifier")
    if repair_kind not in REPAIR_KINDS:
        raise ReviewLifecycleError(f"{finding_id}: invalid Repair Kind {repair_kind or '<empty>'}")
    if owner_stage not in OWNER_STAGES:
        raise ReviewLifecycleError(f"{finding_id}: invalid Owner Stage {owner_stage or '<empty>'}")
    if text_action not in TEXT_ACTIONS:
        raise ReviewLifecycleError(f"{finding_id}: invalid Text Action {text_action or '<empty>'}")
    if not location or not quoted_span or not problem or not reader_consequence or not recommended_action:
        raise ReviewLifecycleError(f"{finding_id}: location, quoted span, issue, consequence, and action are required")
    if not structured_review._contains_location(location):
        raise ReviewLifecycleError(
            f"{finding_id}: Location must identify a section, paragraph, page, line, table, or figure"
        )
    if not _quote_in_manuscript(quoted_span, manuscript_text):
        raise ReviewLifecycleError(f"{finding_id}: Quoted Span is not present in the reviewed manuscript")
    try:
        net_word_delta = int(delta_raw)
    except ValueError as exc:
        raise ReviewLifecycleError(f"{finding_id}: Net Word Delta must be an integer") from exc
    if text_action in {"DELETE", "REPLACE"} and net_word_delta > 0:
        raise ReviewLifecycleError(f"{finding_id}: {text_action} cannot have positive net growth")
    if text_action in {"MOVE", "NO_ACTION"} and net_word_delta != 0:
        raise ReviewLifecycleError(f"{finding_id}: {text_action} requires Net Word Delta 0")
    if text_action == "ADD" and net_word_delta <= 0:
        raise ReviewLifecycleError(f"{finding_id}: ADD requires a positive Net Word Delta")
    if text_action == "ADD" and repair_kind == "TEXT_EDIT":
        if owner_stage != "build":
            raise ReviewLifecycleError(
                f"{finding_id}: evidence-bounded TEXT_EDIT ADD must use Owner Stage build"
            )
        if not re.search(r"\b(?:BRIDGE|DEFINE)\b", recommended_action, re.IGNORECASE):
            raise ReviewLifecycleError(
                f"{finding_id}: TEXT_EDIT ADD must propose BRIDGE or DEFINE under the expression budget"
            )
    if repair_kind == "NO_ACTION" and text_action != "NO_ACTION":
        raise ReviewLifecycleError(f"{finding_id}: NO_ACTION repair requires Text Action NO_ACTION")
    change_class = _repair_change_class(repair_kind, text_action)
    routed_stage = route_for_change_classes([change_class])
    if STAGE_RANK[owner_stage] > STAGE_RANK[routed_stage]:
        raise ReviewLifecycleError(
            f"{finding_id}: Owner Stage {owner_stage} is later than the existing "
            f"revision-contract route {routed_stage} for {repair_kind}"
        )

    mapping = _internal_identity_mapping(
        outdir,
        block=block,
        location=location,
        quoted_span=quoted_span,
        severity=severity,
        repair_kind=repair_kind,
        text_action=text_action,
    )
    item = {
        "finding_id": finding_id,
        "source": {
            "reviewer_role": role,
            "context_id": context_id,
            "output_path": output_relative,
            "output_sha256": output_sha256,
            "source_heading": _source_heading(block),
            "source_block_sha256": sha256_text(block),
        },
        "severity": severity,
        "confidence": confidence,
        "category": category,
        "manuscript_locator": {
            "location": location,
            "quoted_span": quoted_span,
            "quoted_span_sha256": sha256_text(_normalize_space(quoted_span)),
            "manuscript_unit_id": _stable_manuscript_unit_id(quoted_span),
        },
        "identity_mapping": mapping,
        "problem": problem,
        "reader_consequence": reader_consequence,
        "recommended_action": {
            "repair_kind": repair_kind,
            "text_action": text_action,
            "owner_stage": owner_stage,
            "change_class": change_class,
            "instruction": recommended_action,
            "net_word_delta": net_word_delta,
        },
    }
    item["finding_key"] = finding_key(item)
    item["first_seen_run_id"] = ""
    item["last_seen_cycle_id"] = None
    item["materiality"] = _materiality(severity, "BASELINE")
    item["discovery_class"] = "BASELINE"
    item["lineage"] = {
        "same_as": None,
        "refines": None,
        "caused_by_batch": None,
        "reopened_from": None,
    }
    item["occurrences"] = []
    return item


def _validate_manifest(outdir: Path, manifest: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if manifest.get("schema_version") != DISPATCH_SCHEMA:
        issues.append(f"review_manifest schema must be {DISPATCH_SCHEMA}")
    review_run_id = str(manifest.get("review_run_id") or "")
    if not re.fullmatch(r"REV-[A-F0-9]{16}", review_run_id):
        issues.append("review_manifest review_run_id must match REV-<16 uppercase hex>")
    canonical = manifest.get("canonical_manuscript")
    canonical_sha = str(manifest.get("canonical_sha256") or "")
    path = _workspace_path(outdir, str(canonical or ""))
    if path is None or not path.is_file():
        issues.append("review_manifest canonical manuscript is missing or outside the workspace")
    elif sha256_file(path) != canonical_sha:
        issues.append("review_manifest canonical manuscript SHA does not match the current reviewed snapshot")
    prompt_digests = manifest.get("prompt_digests")
    if not isinstance(prompt_digests, dict):
        issues.append("review_manifest prompt_digests must be an object")
    else:
        for relative, expected in prompt_digests.items():
            target = _workspace_path(outdir, str(relative))
            if target is None or not target.is_file() or sha256_file(target) != str(expected):
                issues.append(f"review prompt digest mismatch: {relative}")
    expected_inputs = structured_review.review_input_digests(outdir)
    if manifest.get("input_digests") != expected_inputs:
        issues.append(
            "review dispatch inputs changed; archive this run and dispatch a new review_run_id"
        )
    return issues


def _validate_assurance(
    outdir: Path,
    assurance: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    issues = _registered_schema_issues(
        assurance,
        "cnki-review-assurance-v2.schema.json",
        "review_assurance.json",
    )
    if assurance.get("schema_version") != ASSURANCE_SCHEMA:
        issues.append(
            f"new review runs require {ASSURANCE_SCHEMA}; v1 is read-only legacy evidence and needs review"
        )
    if assurance.get("review_run_id") != manifest.get("review_run_id"):
        issues.append("review assurance review_run_id does not match review_manifest")
    manuscript = assurance.get("manuscript") if isinstance(assurance.get("manuscript"), dict) else {}
    if manuscript.get("path") != manifest.get("canonical_manuscript") or manuscript.get("sha256") != manifest.get("canonical_sha256"):
        issues.append("review assurance does not bind the review_manifest manuscript path and SHA")
    mode = str(assurance.get("mode") or "")
    if mode not in {"independent", "single_agent"}:
        issues.append("review assurance mode must be independent or single_agent")
    reviewers = assurance.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 3:
        issues.append("review assurance requires exactly three reviewer records")
        reviewers = []
    by_role: dict[str, dict[str, Any]] = {}
    for item in reviewers:
        if not isinstance(item, dict):
            issues.append("review assurance contains a non-object reviewer record")
            continue
        role = str(item.get("role") or "")
        if role not in ROLE_FILES or role in by_role:
            issues.append(f"review assurance reviewer role is missing, duplicate, or invalid: {role or '<empty>'}")
            continue
        by_role[role] = item
        prompt_name, output_name, _ = ROLE_FILES[role]
        expected_prompt = f"review_prompts/{prompt_name}"
        expected_output = f"review_prompts/{output_name}"
        if item.get("prompt_path") != expected_prompt or item.get("output_path") != expected_output:
            issues.append(f"{role} reviewer must bind the canonical prompt and output paths")
        for field_name, expected_relative in (("prompt_sha256", expected_prompt), ("output_sha256", expected_output)):
            target = _workspace_path(outdir, expected_relative)
            expected_digest = sha256_file(target) if target and target.is_file() else ""
            if not expected_digest or item.get(field_name) != expected_digest:
                issues.append(f"{role} reviewer {field_name} does not match the actual file")
        if not str(item.get("context_id") or "").strip():
            issues.append(f"{role} reviewer context_id is empty")
        isolation_declared = item.get("isolation_declared")
        if mode == "independent" and isolation_declared is not True:
            issues.append(f"{role} reviewer must declare isolation=true in independent mode")
        if mode == "single_agent" and isolation_declared is not False:
            issues.append(f"{role} reviewer must declare isolation=false in single_agent mode")
        expected_scope = (
            "manuscript_and_sanitized_confirmed_semantics"
            if role == "contribution"
            else "manuscript_only"
        )
        if item.get("input_scope") != expected_scope:
            issues.append(f"{role} reviewer input_scope must be {expected_scope}")
    if set(by_role) != set(ROLE_FILES):
        issues.append("review assurance must cover methods, contribution, and clarity exactly once")
    contexts = [str(by_role[role].get("context_id") or "") for role in ROLE_ORDER if role in by_role]
    if mode == "independent" and (len(contexts) != 3 or len(set(contexts)) != 3):
        issues.append("independent provenance requires three distinct context_id values")
    paths = [str(by_role[role].get("output_path") or "") for role in ROLE_ORDER if role in by_role]
    digests = [str(by_role[role].get("output_sha256") or "") for role in ROLE_ORDER if role in by_role]
    if len(paths) != 3 or len(set(paths)) != 3:
        issues.append("review outputs must use three distinct paths")
    if len(digests) != 3 or any(not value for value in digests):
        issues.append("review outputs must have three non-empty SHA-256 digests")
    elif mode == "independent" and len(set(digests)) != 3:
        issues.append("independent provenance requires three distinct output SHA-256 digests")
    return issues, by_role


def assurance_summary(outdir: Path) -> dict[str, Any]:
    """Read review provenance while keeping v1 historical and fail-closed.

    ``valid`` means the file is readable as historical evidence.  Only
    ``lifecycle_ready`` authorizes a new audit receipt; no v1 field is upgraded
    or used to infer Severity, closure, manuscript identity, or independence.
    """
    path = outdir / "review_assurance.json"
    assurance = _load_json(path)
    if assurance is None:
        return {
            "schema_version": "missing" if not path.exists() else "invalid",
            "mode": "undeclared" if not path.exists() else "invalid",
            "independent": False,
            "valid": not path.exists(),
            "lifecycle_ready": False,
            "status": "needs_review",
            "reviewer_count": 0,
            "issues": [
                "review provenance was not declared"
                if not path.exists()
                else "review_assurance.json is not valid JSON"
            ],
        }
    schema = str(assurance.get("schema_version") or "")
    reviewers = [item for item in assurance.get("reviewers") or [] if isinstance(item, dict)]
    if schema == "cnki-review-assurance/v1":
        return {
            "schema_version": schema,
            "mode": str(assurance.get("mode") or "undeclared"),
            "independent": False,
            "valid": True,
            "lifecycle_ready": False,
            "status": "legacy_read_only_needs_review",
            "reviewer_count": len(reviewers),
            "issues": [
                "cnki-review-assurance/v1 is read-only historical evidence; dispatch a v2 review run"
            ],
        }
    manifest = _load_json(outdir / "review_prompts" / "review_manifest.json")
    if manifest is None:
        issues = ["review_prompts/review_manifest.json is missing or invalid"]
    else:
        issues, _ = _validate_assurance(outdir, assurance, manifest)
        registry = _load_json(outdir / "review_findings.json")
        if registry is not None and _existing_registry_is_current(outdir, registry, assurance):
            reviewed = registry.get("manuscript") if isinstance(registry.get("manuscript"), dict) else {}
            if (
                manifest.get("review_run_id") != registry.get("review_run_id")
                or manifest.get("canonical_manuscript") != reviewed.get("path")
                or manifest.get("canonical_sha256") != reviewed.get("sha256")
            ):
                issues.append("dispatch manifest no longer matches the immutable Finding registry")
        else:
            issues.extend(_validate_manifest(outdir, manifest))
    mode = str(assurance.get("mode") or "undeclared")
    return {
        "schema_version": schema or "invalid",
        "review_run_id": str(assurance.get("review_run_id") or ""),
        "mode": mode,
        "independent": mode == "independent" and not issues,
        "valid": not issues,
        "lifecycle_ready": schema == ASSURANCE_SCHEMA and not issues,
        "status": "ready" if schema == ASSURANCE_SCHEMA and not issues else "needs_review",
        "reviewer_count": len(reviewers),
        "issues": issues,
    }


def _existing_registry_is_current(
    outdir: Path,
    registry: dict[str, Any],
    assurance: dict[str, Any],
) -> bool:
    if registry.get("schema_version") != FINDINGS_SCHEMA:
        return False
    if _registered_schema_issues(
        registry,
        "avereth-review-findings-v3.schema.json",
        "review_findings.json",
    ):
        return False
    if registry.get("review_run_id") != assurance.get("review_run_id"):
        return False
    provenance = registry.get("provenance") if isinstance(registry.get("provenance"), dict) else {}
    mode = str(assurance.get("mode") or "")
    if provenance.get("mode") != mode:
        return False
    if provenance.get("provenance_independence") is not (mode == "independent"):
        return False
    if provenance.get("review_assurance_sha256") != sha256_file(outdir / "review_assurance.json"):
        return False
    manifest = _load_json(outdir / "review_prompts" / "review_manifest.json")
    if manifest is None:
        return False
    manifest_inputs = manifest.get("input_digests")
    if registry.get("input_digests") != manifest_inputs:
        return False
    sources = registry.get("source_reviews")
    if not isinstance(sources, list) or len(sources) != 3:
        return False
    assurance_reviewers = {
        str(item.get("role") or ""): item
        for item in assurance.get("reviewers") or []
        if isinstance(item, dict)
    }
    for source in sources:
        if not isinstance(source, dict):
            return False
        reviewer = assurance_reviewers.get(str(source.get("role") or ""))
        if reviewer is None or any(
            source.get(field) != reviewer.get(field)
            for field in (
                "context_id",
                "prompt_path",
                "prompt_sha256",
                "output_path",
                "output_sha256",
                "input_scope",
                "isolation_declared",
            )
        ):
            return False
        if source.get("isolation_declared") is not (mode == "independent"):
            return False
        path = _workspace_path(outdir, str(source.get("output_path") or ""))
        if path is None or not path.is_file() or sha256_file(path) != source.get("output_sha256"):
            return False
    return True


def _raw_finding_projection(block: str) -> dict[str, Any]:
    repair_kind = _label(block, "Repair Kind").upper()
    text_action = _label(block, "Text Action").upper()
    delta_raw = _label(block, "Net Word Delta")
    try:
        net_word_delta: int | str = int(delta_raw)
    except ValueError:
        net_word_delta = delta_raw
    quoted_span = _clean_quoted_span(_label(block, "Quoted Span"))
    return {
        "finding_id": _label(block, "Finding ID").upper(),
        "severity": _label(block, "Severity").upper(),
        "confidence": _label(block, "Confidence").upper(),
        "category": _label(block, "Category"),
        "location": _label(block, "Location"),
        "quoted_span": quoted_span,
        "quoted_span_sha256": sha256_text(_normalize_space(quoted_span)),
        "problem": _label(block, "Issue"),
        "reader_consequence": _label(block, "Reader Consequence"),
        "repair_kind": repair_kind,
        "change_class": _repair_change_class(repair_kind, text_action),
        "owner_stage": _label(block, "Owner Stage").casefold(),
        "text_action": text_action,
        "instruction": _label(block, "Recommended Action"),
        "net_word_delta": net_word_delta,
        "source_heading": _source_heading(block),
        "source_block_sha256": sha256_text(block),
    }


def _raw_projection_issues(outdir: Path, registry: dict[str, Any]) -> list[str]:
    """Prove that every immutable raw Finding appears once and unchanged."""
    issues: list[str] = []
    sources = {
        str(item.get("role") or ""): item
        for item in registry.get("source_reviews") or []
        if isinstance(item, dict)
    }
    if set(sources) != set(ROLE_FILES):
        issues.append("review_findings source_reviews must cover the three roles exactly once")
    findings = [item for item in registry.get("findings") or [] if isinstance(item, dict)]
    root_findings = [
        item for item in findings
        if str((item.get("source") or {}).get("output_path") or "").startswith("review_prompts/")
        and "/cycles/" not in str((item.get("source") or {}).get("output_path") or "")
    ]
    by_block: dict[str, dict[str, Any]] = {}
    for item in root_findings:
        source = item.get("source") if isinstance(item.get("source"), dict) else {}
        digest = str(source.get("source_block_sha256") or "")
        if not digest or digest in by_block:
            issues.append("review_findings contains a missing or duplicate source_block_sha256")
        else:
            by_block[digest] = item
    seen_blocks: set[str] = set()
    for role, (_, output_name, _) in ROLE_FILES.items():
        relative = f"review_prompts/{output_name}"
        path = outdir / relative
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            issues.append(f"raw reviewer output is missing: {relative}")
            continue
        source = sources.get(role, {})
        actual_rubric = _parse_rubric_rows(text)
        if source.get("verdict") != structured_review._review_verdict(text):
            issues.append(f"{role}: source verdict differs from the immutable raw output")
        if source.get("rubric") != actual_rubric:
            issues.append(f"{role}: rubric projection differs from the immutable raw output")
        blocks = [
            block
            for block in structured_review._extract_finding_blocks(text)
            if structured_review._is_substantive_finding(block)
        ]
        for block in blocks:
            raw = _raw_finding_projection(block)
            digest = str(raw["source_block_sha256"])
            seen_blocks.add(digest)
            item = by_block.get(digest)
            if item is None:
                issues.append(f"{role}: raw Finding {raw['finding_id'] or digest} was omitted from review_findings")
                continue
            source_identity = item.get("source") if isinstance(item.get("source"), dict) else {}
            locator = item.get("manuscript_locator") if isinstance(item.get("manuscript_locator"), dict) else {}
            action = item.get("recommended_action") if isinstance(item.get("recommended_action"), dict) else {}
            projected = {
                "finding_id": item.get("finding_id"),
                "severity": item.get("severity"),
                "confidence": item.get("confidence"),
                "category": item.get("category"),
                "location": locator.get("location"),
                "quoted_span": locator.get("quoted_span"),
                "quoted_span_sha256": locator.get("quoted_span_sha256"),
                "problem": item.get("problem"),
                "reader_consequence": item.get("reader_consequence"),
                "repair_kind": action.get("repair_kind"),
                "change_class": action.get("change_class"),
                "owner_stage": action.get("owner_stage"),
                "text_action": action.get("text_action"),
                "instruction": action.get("instruction"),
                "net_word_delta": action.get("net_word_delta"),
                "source_heading": source_identity.get("source_heading"),
                "source_block_sha256": source_identity.get("source_block_sha256"),
            }
            if projected != raw:
                issues.append(f"{raw['finding_id']}: compiled Finding differs from its immutable source block")
            if (
                source_identity.get("reviewer_role") != role
                or source_identity.get("output_path") != relative
                or source_identity.get("output_sha256") != sha256_file(path)
            ):
                issues.append(f"{raw['finding_id']}: source identity differs from the immutable reviewer output")
    if seen_blocks != set(by_block):
        invented = sorted(set(by_block) - seen_blocks)
        if invented:
            issues.append("review_findings contains Finding block(s) absent from raw outputs: " + ", ".join(invented))
    return issues


def _identity_mapping_issues(outdir: Path, finding: dict[str, Any]) -> list[str]:
    finding_id = str(finding.get("finding_id") or "<unknown>")
    mapping = finding.get("identity_mapping") if isinstance(finding.get("identity_mapping"), dict) else {}
    status = str(mapping.get("mapping_status") or "")
    issues: list[str] = []
    if status not in MAPPING_STATES:
        return [f"{finding_id}: invalid identity mapping status {status or '<empty>'}"]
    known = _ids_in("\n".join(
        path.read_text(encoding="utf-8-sig", errors="ignore")
        for relative in SUPPORT_FILES
        if (path := outdir / relative).is_file()
    ))
    mapped_count = 0
    for key in ID_PATTERNS:
        values = mapping.get(key)
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
            issues.append(f"{finding_id}: identity_mapping.{key} must be a list of stable IDs")
            continue
        mapped_count += len(values)
        unknown = sorted(set(values) - set(known[key]))
        if unknown:
            issues.append(f"{finding_id}: identity_mapping.{key} contains unregistered IDs: {', '.join(unknown)}")
    severity = str(finding.get("severity") or "")
    if status in {"exact", "inferred"} and mapped_count == 0:
        issues.append(f"{finding_id}: {status} mapping must contain at least one registered identity")
    if severity in {"CRITICAL", "MAJOR"} and status not in {"exact", "inferred"}:
        issues.append(f"{finding_id}: Critical/Major identity mapping must be exact or inferred")
    if status == "not_applicable" and (
        severity not in {"MINOR", "OBSERVATION"}
        or str((finding.get("recommended_action") or {}).get("repair_kind") or "") not in {"TEXT_EDIT", "NO_ACTION"}
    ):
        issues.append(f"{finding_id}: not_applicable mapping is allowed only for surface Minor/Observation findings")

    source = finding.get("source") if isinstance(finding.get("source"), dict) else {}
    output = _workspace_path(outdir, str(source.get("output_path") or ""))
    expected_mapping: dict[str, Any] | None = None
    if output is not None and output.is_file():
        try:
            raw_text = output.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            raw_text = ""
        for block in structured_review._extract_finding_blocks(raw_text):
            if sha256_text(block) != source.get("source_block_sha256"):
                continue
            raw = _raw_finding_projection(block)
            expected_mapping = _internal_identity_mapping(
                outdir,
                block=block,
                location=str(raw.get("location") or ""),
                quoted_span=str(raw.get("quoted_span") or ""),
                severity=str(raw.get("severity") or ""),
                repair_kind=str(raw.get("repair_kind") or ""),
                text_action=str(raw.get("text_action") or ""),
            )
            break
    if expected_mapping is None:
        issues.append(f"{finding_id}: cannot rederive identity mapping from its immutable source block")
    elif mapping != expected_mapping:
        issues.append(
            f"{finding_id}: identity mapping differs from the deterministic compiler projection"
        )
    return issues


def compile_findings(
    outdir: Path,
    review_dir: Path,
    manuscript_path: Path,
    *,
    write: bool = False,
) -> LifecycleResult:
    findings_path = outdir / "review_findings.json"
    manifest = _load_json(review_dir / "review_manifest.json")
    assurance = _load_json(outdir / "review_assurance.json")
    issues: list[str] = []
    if manifest is None:
        return LifecycleResult(False, ["review_prompts/review_manifest.json is missing or invalid"])
    if assurance is None:
        return LifecycleResult(False, ["review_assurance.json is missing or invalid"])

    existing = _load_json(findings_path)
    if existing is not None and _existing_registry_is_current(outdir, existing, assurance):
        generated: list[str] = []
        if write:
            generated.extend(ensure_resolution_scaffold(outdir, existing))
        return LifecycleResult(True, generated=generated, metrics={"reused": True, "finding_count": len(existing.get("findings") or [])})
    if existing is not None:
        return LifecycleResult(
            False,
            ["review_findings.json already exists but no longer matches immutable reviewer inputs; archive the prior run and dispatch a new review_run_id"],
        )

    issues.extend(_validate_manifest(outdir, manifest))
    assurance_issues, reviewers = _validate_assurance(outdir, assurance, manifest)
    issues.extend(assurance_issues)
    if manuscript_path.resolve() != (_workspace_path(outdir, str(manifest.get("canonical_manuscript") or "")) or Path()).resolve():
        issues.append("compile manuscript path does not match the dispatched canonical manuscript")
    if sha256_file(manuscript_path) != manifest.get("canonical_sha256"):
        issues.append("compile manuscript SHA does not match the dispatched review snapshot")
    if issues:
        return LifecycleResult(False, issues)

    validation = structured_review.validate_independence(review_dir)
    if not validation.get("ok"):
        return LifecycleResult(False, list(validation.get("findings") or []), metrics=validation)
    manuscript_text = structured_review.manuscript_text_content(manuscript_path)
    source_reviews: list[dict[str, Any]] = []
    compiled_findings: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    try:
        for role in ROLE_ORDER:
            _, output_name, _ = ROLE_FILES[role]
            relative = f"review_prompts/{output_name}"
            path = outdir / relative
            text = path.read_text(encoding="utf-8-sig")
            reviewer = reviewers[role]
            verdict = structured_review._review_verdict(text)
            blocks = [
                block
                for block in structured_review._extract_finding_blocks(text)
                if structured_review._is_substantive_finding(block)
            ]
            source_reviews.append(
                {
                    "role": role,
                    "verdict": verdict,
                    "context_id": reviewer["context_id"],
                    "prompt_path": reviewer["prompt_path"],
                    "prompt_sha256": reviewer["prompt_sha256"],
                    "output_path": relative,
                    "output_sha256": reviewer["output_sha256"],
                    "input_scope": reviewer["input_scope"],
                    "isolation_declared": reviewer["isolation_declared"],
                    "rubric": _parse_rubric_rows(text),
                }
            )
            for block in blocks:
                item = _parse_finding(
                    outdir,
                    role=role,
                    context_id=str(reviewer["context_id"]),
                    output_relative=relative,
                    output_sha256=str(reviewer["output_sha256"]),
                    block=block,
                    manuscript_text=manuscript_text,
                )
                if item["finding_id"] in seen_ids:
                    raise ReviewLifecycleError(f"duplicate Finding ID: {item['finding_id']}")
                seen_ids.add(item["finding_id"])
                item["first_seen_run_id"] = str(manifest["review_run_id"])
                item["occurrences"] = [
                    _occurrence(item, run_id=str(manifest["review_run_id"]), cycle_id=None)
                ]
                compiled_findings.append(item)
    except (OSError, KeyError, ReviewLifecycleError) as exc:
        return LifecycleResult(False, [str(exc)], metrics=validation)

    venue_contract = structured_review.venue_contract_state(outdir)
    venue_rows = [
        row
        for source in source_reviews
        if source.get("role") == "contribution"
        for row in source.get("rubric") or []
        if isinstance(row, dict) and row.get("dimension_id") == "CON-VENUE-FIT"
    ]
    if len(venue_rows) != 1:
        return LifecycleResult(False, ["Contribution review must contain exactly one CON-VENUE-FIT row"])
    if venue_rows[0].get("applicability") != venue_contract["applicability"]:
        return LifecycleResult(
            False,
            [
                "CON-VENUE-FIT applicability does not match the verified venue contract: "
                f"expected {venue_contract['applicability']}"
            ],
        )

    verdicts = {item["role"]: item["verdict"] for item in source_reviews}
    if not compiled_findings and set(verdicts.values()) != {"PASS"}:
        return LifecycleResult(False, ["zero findings is legal only when all three source verdicts are PASS"])
    status = "NO_MATERIAL_OBJECTIONS" if not compiled_findings else "HAS_FINDINGS"
    registry = {
        "schema_version": FINDINGS_SCHEMA,
        "review_run_id": manifest["review_run_id"],
        "root_review_run_id": manifest["review_run_id"],
        "status": status,
        "manuscript": {
            "path": manifest["canonical_manuscript"],
            "sha256": manifest["canonical_sha256"],
        },
        "input_digests": dict(manifest.get("input_digests") or {}),
        "venue_contract": venue_contract,
        "provenance": {
            "mode": assurance["mode"],
            "provenance_independence": assurance["mode"] == "independent",
            "review_assurance_sha256": sha256_file(outdir / "review_assurance.json"),
            "textual_overlap": {
                "metric": "diagnostic_only",
                "textual_diversity_score": validation.get("textual_diversity_score", 0),
                "pairwise_similarities": validation.get("pairwise_similarities", {}),
                "warnings": validation.get("warnings", []),
            },
        },
        "source_reviews": source_reviews,
        "findings": compiled_findings,
    }
    shape_issues = _registered_schema_issues(
        registry,
        "avereth-review-findings-v3.schema.json",
        "review_findings.json",
    )
    if shape_issues:
        return LifecycleResult(False, shape_issues, metrics=validation)
    generated: list[str] = []
    if write:
        _atomic_json(findings_path, registry)
        generated.append("review_findings.json")
        generated.extend(ensure_resolution_scaffold(outdir, registry))
    return LifecycleResult(
        True,
        generated=generated,
        metrics={"reused": False, "finding_count": len(compiled_findings), "status": status},
    )


def _earliest_stage(item: dict[str, Any]) -> str:
    action = item.get("recommended_action") if isinstance(item.get("recommended_action"), dict) else {}
    repair_kind = str(action.get("repair_kind") or "TEXT_EDIT")
    text_action = str(action.get("text_action") or "")
    change_class = str(
        action.get("change_class") or _repair_change_class(repair_kind, text_action)
    )
    routed = route_for_change_classes([change_class])
    owner = str(action.get("owner_stage") or routed)
    if owner not in STAGE_RANK:
        return routed
    return min((routed, owner), key=lambda stage: STAGE_RANK[stage])


def review_route_plan(
    registry: dict[str, Any],
    resolution: dict[str, Any] | None,
    *,
    profile: str = "full_paper",
    revision_contract: dict[str, Any] | None = None,
    outdir: Path | None = None,
) -> dict[str, Any]:
    """Derive a plan only; never mutate a revision contract or upstream artifact."""
    by_id = _resolution_by_id(resolution)
    pending: list[dict[str, Any]] = []
    routable: list[dict[str, Any]] = []
    awaiting_verification: list[dict[str, Any]] = []
    unplanned: list[dict[str, Any]] = []
    repair_items: list[dict[str, Any]] = []
    for finding in registry.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        finding_id = str(finding.get("finding_id") or "")
        row = by_id.get(finding_id, {})
        lifecycle_status = str(row.get("status") or "OPEN")
        action = finding.get("recommended_action") if isinstance(finding.get("recommended_action"), dict) else {}
        repair_kind = str(action.get("repair_kind") or "TEXT_EDIT")
        text_action = str(action.get("text_action") or "")
        change_class = str(
            action.get("change_class") or _repair_change_class(repair_kind, text_action)
        )
        route_item = {
            "finding_id": finding_id,
            "finding_key": str(finding.get("finding_key") or ""),
            "status": lifecycle_status,
            "repair_kind": repair_kind,
            "change_class": change_class,
            "owner_stage": str(action.get("owner_stage") or "build"),
            "effective_stage": _earliest_stage(finding),
        }
        if lifecycle_status in {"PLANNED", "APPLIED", "VERIFIED", "REOPENED"} or isinstance(
            row.get("change"), dict
        ):
            repair_items.append(route_item)
        if lifecycle_status in TERMINAL_STATES or finding.get("materiality") == "NON_BLOCKING":
            continue
        pending.append(route_item)
        if lifecycle_status in {"PLANNED", "REOPENED"}:
            routable.append(route_item)
        elif lifecycle_status == "APPLIED":
            awaiting_verification.append(route_item)
        else:
            unplanned.append(route_item)
    if routable:
        routed = route_for_change_classes(item["change_class"] for item in routable)
        earliest = min(
            [routed, *(item["effective_stage"] for item in routable)],
            key=lambda stage: STAGE_RANK[stage],
        )
    else:
        earliest = None
    normalized_profile = str(profile or "full_paper").strip().lower().replace("-", "_")
    issues: list[str] = []
    linked = False
    if repair_items and normalized_profile == "manuscript_audit":
        issues.append(
            "manuscript_audit is read-only: expand authority to manuscript_revision or full_paper before applying repairs"
        )
    elif repair_items and normalized_profile == "manuscript_revision":
        if not isinstance(revision_contract, dict):
            issues.append("review repairs require an explicitly authorized revision_contract amendment")
        else:
            if outdir is None:
                contract_issues = validate_revision_contract(revision_contract, stage="audit")
                issues.append(
                    "revision_contract baseline snapshot cannot be verified without the revision workspace"
                )
            else:
                loaded_contract, contract_issues = load_and_validate_revision_contract(
                    outdir, stage="audit"
                )
                if loaded_contract != revision_contract:
                    issues.append(
                        "revision_contract argument does not equal the workspace authority"
                    )
            if contract_issues:
                issues.extend(
                    f"{item.get('code', 'REV')}: {item.get('message', 'invalid revision contract')}"
                    for item in contract_issues
                )
            authorized_finding_keys = {
                str(key)
                for item in revision_contract.get("requested_changes") or []
                if isinstance(item, dict)
                for key in item.get("target_finding_keys") or []
            }
            missing = sorted(
                item["finding_id"]
                for item in repair_items
                if item["finding_key"] not in authorized_finding_keys
            )
            if missing:
                issues.append(
                    "revision_contract does not explicitly authorize Finding ID(s): " + ", ".join(missing)
                )
            baseline = (
                revision_contract.get("baseline")
                if isinstance(revision_contract.get("baseline"), dict)
                else {}
            )
            reviewed = registry.get("manuscript") if isinstance(registry.get("manuscript"), dict) else {}
            baseline_path = str(baseline.get("path") or "").replace("\\", "/")
            reviewed_path = str(reviewed.get("path") or "").replace("\\", "/")
            if baseline_path != reviewed_path or baseline.get("sha256") != reviewed.get("sha256"):
                issues.append(
                    "revision_contract baseline path/SHA must equal the reviewed manuscript identity"
                )

            changes_by_finding_key = {
                str(key): item
                for item in revision_contract.get("requested_changes") or []
                if isinstance(item, dict)
                for key in item.get("target_finding_keys") or []
            }
            affected = (
                revision_contract.get("affected_identities")
                if isinstance(revision_contract.get("affected_identities"), dict)
                else {}
            )
            manuscript_units = {
                str(item).replace("\\", "/")
                for item in affected.get("manuscript_units") or []
            }
            if reviewed_path and reviewed_path not in manuscript_units:
                issues.append(
                    "revision_contract affected_identities.manuscript_units must include the reviewed manuscript"
                )
            findings_by_id = {
                str(item.get("finding_id") or ""): item
                for item in registry.get("findings") or []
                if isinstance(item, dict)
            }
            identity_groups = {
                "claim_ids": "claim_ids",
                "evidence_ids": "source_ids",
                "design_ids": "design_ids",
                "execution_ids": "execution_ids",
            }
            for route_item in repair_items:
                finding_id = route_item["finding_id"]
                request = changes_by_finding_key.get(route_item["finding_key"])
                if request is None:
                    continue
                if str(request.get("change_class") or "").strip().lower() != route_item["change_class"]:
                    issues.append(
                        f"revision_contract {finding_id} change_class must be {route_item['change_class']}"
                    )
                mapping = findings_by_id.get(finding_id, {}).get("identity_mapping")
                if not isinstance(mapping, dict):
                    mapping = {}
                for mapping_key, contract_key in identity_groups.items():
                    required_ids = {str(item) for item in mapping.get(mapping_key) or []}
                    authorized_ids = {str(item) for item in affected.get(contract_key) or []}
                    uncovered = sorted(required_ids - authorized_ids)
                    if uncovered:
                        issues.append(
                            f"revision_contract {finding_id} does not authorize mapped {mapping_key}: "
                            + ", ".join(uncovered)
                        )
            contract_route = min(
                (
                    route_for_change_classes(item["change_class"] for item in repair_items),
                    *(item["effective_stage"] for item in repair_items),
                ),
                key=lambda stage: STAGE_RANK[stage],
            )
            declared = str(revision_contract.get("earliest_reopen_stage") or "")
            if declared not in STAGE_RANK or STAGE_RANK[declared] > STAGE_RANK[contract_route]:
                issues.append(
                    f"revision_contract route must be expanded to {contract_route}; current route is {declared or '<missing>'}"
                )
            linked = not issues
    if routable:
        action = (
            "request_profile_expansion"
            if normalized_profile == "manuscript_audit"
            else "request_revision_contract_amendment"
            if normalized_profile == "manuscript_revision" and not linked
            else "reopen_existing_full_paper_stage"
            if normalized_profile == "full_paper"
            else "follow_authorized_revision_contract"
        )
        route_status = "PLAN_REQUIRES_ACTION"
    elif awaiting_verification:
        action = "await_independent_verification"
        route_status = "AWAITING_VERIFICATION"
    elif unplanned:
        action = "adjudicate_and_plan_review_findings"
        route_status = "REQUIRES_ADJUDICATION"
    else:
        action = "none"
        route_status = "NO_ACTIVE_REPAIRS"
    return {
        "status": route_status,
        "profile": normalized_profile,
        "finding_ids": [item["finding_id"] for item in pending],
        "routable_finding_ids": [item["finding_id"] for item in routable],
        "awaiting_verification_ids": [
            item["finding_id"] for item in awaiting_verification
        ],
        "unplanned_finding_ids": [item["finding_id"] for item in unplanned],
        "authorization_finding_ids": [item["finding_id"] for item in repair_items],
        "change_classes": sorted({item["change_class"] for item in routable}),
        "effective_earliest_reopen_stage": earliest,
        "revision_contract_linked": linked,
        "action": action,
        "issues": issues,
        "routes": routable,
    }


def workspace_review_route(outdir: Path) -> dict[str, Any]:
    registry = _load_json(outdir / "review_findings.json")
    resolution = _load_json(outdir / "review_resolution.json")
    config = _load_json(outdir / "workflow_config.json") or {}
    if registry is None:
        return {
            "status": "NOT_COMPILED",
            "profile": str(config.get("task_profile") or "full_paper"),
            "finding_ids": [],
            "change_classes": [],
            "effective_earliest_reopen_stage": None,
            "revision_contract_linked": False,
            "action": "compile_review_findings",
            "issues": [],
            "routes": [],
        }
    return review_route_plan(
        registry,
        resolution,
        profile=str(config.get("task_profile") or "full_paper"),
        revision_contract=_load_json(outdir / "revision_contract.json"),
        outdir=outdir,
    )


def ensure_resolution_scaffold(outdir: Path, registry: dict[str, Any]) -> list[str]:
    path = outdir / "review_resolution.json"
    if path.exists():
        return []
    no_findings = registry.get("status") == "NO_MATERIAL_OBJECTIONS"
    blocking_keys = [
        str(item.get("finding_key") or "")
        for item in registry.get("findings") or []
        if isinstance(item, dict) and item.get("materiality") == "BLOCKING"
    ]
    optional_keys = [
        str(item.get("finding_key") or "")
        for item in registry.get("findings") or []
        if isinstance(item, dict) and item.get("materiality") == "NON_BLOCKING"
    ]
    resolutions: list[dict[str, Any]] = []
    for item in registry.get("findings") or []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "")
        resolutions.append(
            {
                "finding_id": item.get("finding_id"),
                "finding_key": item.get("finding_key"),
                "status": "OPEN",
                "decision": "PENDING",
                "original_severity": severity,
                "final_severity": severity,
                "earliest_reopen_stage": _earliest_stage(item),
                "adjudication": None,
                "merge_target_finding_id": None,
                "authorization": None,
                "change": None,
                "verification": None,
                "history": [],
                "reopen_count": 0,
                "root_cause_analysis": None,
            }
        )
    payload = {
        "schema_version": RESOLUTION_SCHEMA,
        "review_run_id": registry.get("review_run_id"),
        "findings_sha256": (
            sha256_file(outdir / "review_findings.json")
            or sha256_text(json.dumps(registry, ensure_ascii=False, sort_keys=True))
        ),
        "status": "NO_MATERIAL_OBJECTIONS" if no_findings else "ACTIVE" if blocking_keys else "CLOSED",
        "resolutions": resolutions,
        "revision_batches": [],
        "review_cycles": [],
        "optional_backlog": optional_keys,
        "convergence": {
            "status": "FROZEN" if no_findings or not blocking_keys else "ACTIVE",
            "latest_cycle_id": None,
            "active_blocking_finding_keys": blocking_keys,
            "root_cause_required_finding_keys": [],
        },
    }
    _atomic_json(path, payload)
    return ["review_resolution.json"]


def _refresh_convergence(registry: dict[str, Any], resolution: dict[str, Any]) -> None:
    by_id = _resolution_by_id(resolution)
    active = sorted(
        str(item.get("finding_key") or "")
        for item in registry.get("findings") or []
        if isinstance(item, dict)
        and item.get("materiality") == "BLOCKING"
        and str(by_id.get(str(item.get("finding_id") or ""), {}).get("status") or "OPEN") not in TERMINAL_STATES
    )
    backlog = sorted(
        str(item.get("finding_key") or "")
        for item in registry.get("findings") or []
        if isinstance(item, dict)
        and item.get("materiality") == "NON_BLOCKING"
        and str(by_id.get(str(item.get("finding_id") or ""), {}).get("status") or "OPEN") not in TERMINAL_STATES
    )
    root_fields = {
        "instruction_failure", "owner_stage_check", "rewrite_scope",
        "claim_or_evidence_change", "reviewer_conflict", "next_strategy"
    }
    root_required = sorted(
        str(item.get("finding_key") or "")
        for item in resolution.get("resolutions") or []
        if isinstance(item, dict)
        and int(item.get("reopen_count") or 0) >= 2
        and (
            not isinstance(item.get("root_cause_analysis"), dict)
            or any(not str(item["root_cause_analysis"].get(field) or "").strip() for field in root_fields)
        )
    )
    cycles = [item for item in resolution.get("review_cycles") or [] if isinstance(item, dict)]
    latest = cycles[-1] if cycles else None
    frozen = not active and (latest is None or latest.get("result") == "PASS")
    resolution["optional_backlog"] = backlog
    resolution["convergence"] = {
        "status": "ROOT_CAUSE_REQUIRED" if root_required else "FROZEN" if frozen else "ACTIVE",
        "latest_cycle_id": latest.get("cycle_id") if latest else None,
        "active_blocking_finding_keys": active,
        "root_cause_required_finding_keys": root_required,
    }
    if registry.get("status") == "NO_MATERIAL_OBJECTIONS" and not cycles:
        resolution["status"] = "NO_MATERIAL_OBJECTIONS"
    else:
        resolution["status"] = "CLOSED" if frozen else "ACTIVE"


def _next_finding_id(registry: dict[str, Any], role: str) -> str:
    code = ROLE_FILES[role][2]
    numbers = [
        int(match.group(1))
        for item in registry.get("findings") or []
        if isinstance(item, dict)
        for match in [re.fullmatch(rf"REV-{code}-([0-9]{{3}})", str(item.get("finding_id") or ""))]
        if match
    ]
    return f"REV-{code}-{(max(numbers) if numbers else 0) + 1:03d}"


def compile_review_cycle(
    outdir: Path,
    cycle_id: str,
    manuscript_path: Path,
    *,
    write: bool = False,
) -> LifecycleResult:
    registry = _load_json(outdir / "review_findings.json")
    resolution = _load_json(outdir / "review_resolution.json")
    cycle_dir = outdir / "review_prompts" / "cycles" / cycle_id
    manifest = _load_json(cycle_dir / "review_cycle_manifest.json")
    assurance = _load_json(cycle_dir / "cycle_assurance.json")
    if registry is None or registry.get("schema_version") != FINDINGS_SCHEMA:
        return LifecycleResult(False, [f"delta cycle requires {FINDINGS_SCHEMA}"])
    if resolution is None or resolution.get("schema_version") != RESOLUTION_SCHEMA:
        return LifecycleResult(False, [f"delta cycle requires {RESOLUTION_SCHEMA}"])
    if manifest is None or manifest.get("schema_version") != "avereth-review-cycle-dispatch/v1":
        return LifecycleResult(False, ["review_cycle_manifest.json is missing or invalid"])
    if assurance is None or assurance.get("schema_version") != "avereth-review-cycle-assurance/v1":
        return LifecycleResult(False, ["cycle_assurance.json is missing or invalid"])
    issues: list[str] = []
    if manifest.get("cycle_id") != cycle_id or assurance.get("cycle_id") != cycle_id:
        issues.append("cycle IDs disagree")
    if manifest.get("root_review_run_id") != registry.get("root_review_run_id"):
        issues.append("cycle does not descend from the root review run")
    if sha256_file(manuscript_path) != manifest.get("after_manuscript_sha256"):
        issues.append("cycle manuscript SHA does not equal the dispatched current manuscript")
    for relative, expected in (manifest.get("prompt_digests") or {}).items():
        target = _workspace_path(outdir, str(relative))
        if target is None or not target.is_file() or sha256_file(target) != expected:
            issues.append(f"cycle prompt changed: {relative}")
    reviewers = assurance.get("reviewers") if isinstance(assurance.get("reviewers"), list) else []
    by_role = {
        str(item.get("role") or ""): item
        for item in reviewers
        if isinstance(item, dict)
    }
    dispatched = [str(item) for item in manifest.get("dispatched_reviewers") or []]
    if set(by_role) != set(dispatched):
        issues.append("cycle assurance must cover each dispatched reviewer exactly once")
    contexts: list[str] = []
    reviewer_outputs: list[dict[str, Any]] = []
    role_results: dict[str, str] = {
        str(role): "PASS" for role in manifest.get("reused_reviewers") or []
    }
    parsed: list[tuple[dict[str, Any], str, str, str]] = []
    blocked_cycle = assurance.get("result") == "BLOCKED"
    if blocked_cycle and not str(assurance.get("block_reason") or "").strip():
        issues.append("BLOCKED cycle requires block_reason")
    for role in dispatched:
        reviewer = by_role.get(role, {})
        context_id = str(reviewer.get("context_id") or "").strip()
        if not context_id:
            issues.append(f"{role}: context_id is required")
        contexts.append(context_id)
        expected_prompt = f"review_prompts/cycles/{cycle_id}/{role}_delta_reviewer.md"
        expected_output = f"review_prompts/cycles/{cycle_id}/{role}_delta_output.md"
        if reviewer.get("prompt_path") != expected_prompt or reviewer.get("output_path") != expected_output:
            issues.append(f"{role}: cycle prompt/output path is not canonical")
            continue
        prompt = _workspace_path(outdir, expected_prompt)
        output = _workspace_path(outdir, expected_output)
        if prompt is None or not prompt.is_file() or sha256_file(prompt) != reviewer.get("prompt_sha256"):
            issues.append(f"{role}: prompt SHA mismatch")
        if blocked_cycle and (output is None or not output.is_file()):
            continue
        if output is None or not output.is_file() or sha256_file(output) != reviewer.get("output_sha256"):
            issues.append(f"{role}: immutable cycle output is missing or changed")
            continue
        text = output.read_text(encoding="utf-8-sig")
        verdict = structured_review._review_verdict(text)
        blocks = [
            block for block in structured_review._extract_finding_blocks(text)
            if structured_review._is_substantive_finding(block)
        ]
        if verdict not in {"PASS", "FINDINGS"}:
            issues.append(f"{role}: cycle output requires one PASS or FINDINGS verdict")
        if verdict == "PASS" and blocks:
            issues.append(f"{role}: PASS cycle output cannot contain Findings")
        if verdict == "FINDINGS" and not blocks:
            issues.append(f"{role}: FINDINGS cycle output must contain Findings")
        role_results[role] = verdict
        reviewer_outputs.append(
            {"role": role, "path": expected_output, "sha256": sha256_file(output), "context_id": context_id}
        )
        for block in blocks:
            try:
                item = _parse_finding(
                    outdir,
                    role=role,
                    context_id=context_id,
                    output_relative=expected_output,
                    output_sha256=sha256_file(output),
                    block=block,
                    manuscript_text=structured_review.manuscript_text_content(manuscript_path),
                )
            except ReviewLifecycleError as exc:
                issues.append(str(exc))
                continue
            discovery = _label(block, "Discovery Class").upper()
            related_key = _label(block, "Related Finding Key").upper()
            changed_unit = _label(block, "Changed Unit ID").upper()
            why_new = _label(block, "Why Newly Discoverable")
            if discovery not in DISCOVERY_CLASSES[1:]:
                issues.append(f"{role}: delta Finding requires a valid Discovery Class")
            if changed_unit not in set(manifest.get("reviewed_unit_ids") or []):
                issues.append(f"{role}: delta Finding must bind a changed unit from the impact")
            if discovery == "NEW_MATERIAL" and (not why_new or why_new.upper() == "N/A"):
                issues.append(f"{role}: NEW_MATERIAL requires Why Newly Discoverable")
            parsed.append((item, discovery, related_key, changed_unit))
    if assurance.get("mode") == "independent" and len(contexts) != len(set(contexts)):
        issues.append("independent cycle reviewers require distinct contexts")
    if issues:
        return LifecycleResult(False, issues)

    existing_by_key = {
        str(item.get("finding_key") or ""): item
        for item in registry.get("findings") or []
        if isinstance(item, dict)
    }
    resolutions = resolution.get("resolutions") if isinstance(resolution.get("resolutions"), list) else []
    resolution_by_key = {
        str(item.get("finding_key") or ""): item
        for item in resolutions
        if isinstance(item, dict)
    }
    reopened: list[str] = []
    new_keys: list[str] = []
    for item, discovery, related_key, changed_unit in parsed:
        local_finding_id = str(item.get("finding_id") or "")
        computed_key = str(item.get("finding_key") or "")
        target_key = related_key if related_key not in {"", "N/A"} else computed_key
        existing = existing_by_key.get(target_key)
        if discovery == "UNRESOLVED_EXISTING" and existing is None:
            return LifecycleResult(False, [f"UNRESOLVED_EXISTING does not resolve to a known finding_key: {target_key}"])
        if existing is not None:
            if target_key != computed_key:
                decisions = assurance.get("lineage_decisions") if isinstance(assurance.get("lineage_decisions"), dict) else {}
                decision = decisions.get(local_finding_id) if isinstance(decisions.get(local_finding_id), dict) else {}
                if not (
                    decision.get("target_finding_key") == target_key
                    and decision.get("deterministic_basis") == "identity_graph"
                    and str(decision.get("decided_by") or "").strip()
                    and str(decision.get("context_id") or "").strip()
                    and str(decision.get("reason") or "").strip()
                ):
                    return LifecycleResult(
                        False,
                        [
                            f"{local_finding_id}: cross-key same_as requires deterministic identity-graph "
                            "basis plus an explicit editor lineage decision"
                        ],
                    )
            existing["last_seen_cycle_id"] = cycle_id
            existing["occurrences"].append(
                _occurrence(item, run_id=str(registry.get("root_review_run_id") or ""), cycle_id=cycle_id)
            )
            row = resolution_by_key.get(target_key)
            if row is not None:
                prior = str(row.get("status") or "OPEN")
                if prior in {"APPLIED", "VERIFIED", "WAIVED"}:
                    row.setdefault("history", []).append(
                        {"from": prior, "to": "REOPENED", "by": "delta-cycle", "at": cycle_id}
                    )
                    row["status"] = "REOPENED"
                    row["decision"] = "PENDING"
                    row["reopen_count"] = int(row.get("reopen_count") or 0) + 1
                reopened.append(target_key)
            continue

        item["finding_id"] = _next_finding_id(registry, str((item.get("source") or {}).get("reviewer_role") or ""))
        item["finding_key"] = computed_key
        item["first_seen_run_id"] = str(registry.get("root_review_run_id") or registry.get("review_run_id") or "")
        item["last_seen_cycle_id"] = cycle_id
        item["discovery_class"] = discovery
        item["materiality"] = _materiality(str(item.get("severity") or ""), discovery)
        item["lineage"] = {
            "same_as": None,
            "refines": None,
            "caused_by_batch": manifest.get("batch_id") if discovery == "REVISION_REGRESSION" else None,
            "reopened_from": None,
        }
        item["occurrences"] = [
            _occurrence(item, run_id=str(registry.get("root_review_run_id") or ""), cycle_id=cycle_id)
        ]
        registry.setdefault("findings", []).append(item)
        existing_by_key[computed_key] = item
        severity = str(item.get("severity") or "")
        row = {
            "finding_id": item["finding_id"], "finding_key": computed_key,
            "status": "OPEN", "decision": "PENDING",
            "original_severity": severity, "final_severity": severity,
            "earliest_reopen_stage": _earliest_stage(item), "adjudication": None,
            "merge_target_finding_id": None, "authorization": None,
            "change": None, "verification": None, "history": [],
            "reopen_count": 0, "root_cause_analysis": None,
        }
        resolutions.append(row)
        resolution_by_key[computed_key] = row
        new_keys.append(computed_key)
    registry["status"] = "HAS_FINDINGS" if registry.get("findings") else "NO_MATERIAL_OBJECTIONS"
    cycle_result = "BLOCKED" if blocked_cycle else "FINDINGS" if any(value == "FINDINGS" for value in role_results.values()) else "PASS"
    closed_keys = [
        str(item.get("finding_key") or "")
        for item in resolutions
        if isinstance(item, dict) and item.get("status") in TERMINAL_STATES
    ]
    impact_rel = str(manifest.get("impact_path") or "")
    cycle = {
        "schema_version": "avereth-review-cycle/v1",
        "cycle_id": cycle_id,
        "batch_id": manifest.get("batch_id"),
        "parent_cycle_id": manifest.get("parent_cycle_id"),
        "mode": manifest.get("mode"),
        "before_manuscript_sha256": manifest.get("before_manuscript_sha256"),
        "after_manuscript_sha256": manifest.get("after_manuscript_sha256"),
        "impact_path": impact_rel,
        "impact_sha256": manifest.get("impact_sha256"),
        "reviewed_unit_ids": manifest.get("reviewed_unit_ids") or [],
        "required_reviewers": manifest.get("required_reviewers") or [],
        "dispatched_reviewers": manifest.get("dispatched_reviewers") or [],
        "reused_reviewers": manifest.get("reused_reviewers") or [],
        "reused_from_cycles": manifest.get("reused_from_cycles") or {},
        "role_input_digests": manifest.get("role_input_digests") or {},
        "role_results": role_results,
        "result": cycle_result,
        "closed_finding_keys": sorted(set(closed_keys)),
        "reopened_finding_keys": sorted(set(reopened)),
        "new_finding_keys": sorted(set(new_keys)),
        "reviewer_outputs": reviewer_outputs,
        "block_reason": str(assurance.get("block_reason") or "") if blocked_cycle else "",
    }
    resolution["resolutions"] = resolutions
    resolution.setdefault("review_cycles", []).append(cycle)
    resolution["findings_sha256"] = sha256_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
    batch_record = {
        "batch_id": manifest.get("batch_id"),
        "before_manuscript_sha256": manifest.get("before_manuscript_sha256"),
        "after_manuscript_sha256": manifest.get("after_manuscript_sha256"),
        "impact_path": impact_rel,
        "impact_sha256": manifest.get("impact_sha256"),
        "promotion_count": 1,
        "cycle_ids": [cycle_id],
    }
    existing_batch = next(
        (item for item in resolution.setdefault("revision_batches", []) if isinstance(item, dict) and item.get("batch_id") == manifest.get("batch_id")),
        None,
    )
    if existing_batch is None:
        resolution["revision_batches"].append(batch_record)
    else:
        existing_batch.setdefault("cycle_ids", []).append(cycle_id)
    _refresh_convergence(registry, resolution)
    if write:
        _atomic_json(outdir / "review_findings.json", registry)
        resolution["findings_sha256"] = sha256_file(outdir / "review_findings.json")
        _atomic_json(outdir / "review_resolution.json", resolution)
        render_views(outdir, registry, resolution)
    return LifecycleResult(cycle_result == "PASS", [] if cycle_result == "PASS" else [f"review cycle {cycle_id} recorded {cycle_result}"], generated=["review_findings.json", "review_resolution.json"], metrics={"cycle": cycle})


def _registered_scientific_artifacts(
    outdir: Path,
    kind: str,
) -> tuple[list[dict[str, str]], str]:
    """Return artifact identities from the stage authority that owns each kind."""
    records: list[dict[str, str]] = []
    if kind == "execution":
        authority = "method_execution.json runs[].artifacts"
        payload = _load_json(outdir / "method_execution.json") or {}
        for run in payload.get("runs") or []:
            if not isinstance(run, dict):
                continue
            run_id = str(run.get("id") or "").strip()
            for artifact in run.get("artifacts") or []:
                if not isinstance(artifact, dict):
                    continue
                records.append(
                    {
                        "artifact_id": str(artifact.get("id") or "").strip(),
                        "path": str(artifact.get("path") or "").replace("\\", "/").strip(),
                        "sha256": str(artifact.get("sha256") or "").strip(),
                        "owner_id": run_id,
                    }
                )
        return records, authority

    if kind in {"evidence", "research"}:
        authority = (
            "reference_materials/literature_registry.json sources or "
            "research_material_registry.json probe evidence_files"
        )
        literature = _load_json(outdir / "reference_materials" / "literature_registry.json") or {}
        for source in literature.get("sources") or []:
            if not isinstance(source, dict):
                continue
            records.append(
                {
                    "artifact_id": str(source.get("source_id") or "").strip(),
                    "path": str(source.get("local_file") or "").replace("\\", "/").strip(),
                    "sha256": str(source.get("sha256") or "").strip(),
                    "owner_id": str(source.get("source_id") or "").strip(),
                }
            )
        materials = _load_json(
            outdir / "reference_materials" / "research_material_registry.json"
        ) or {}
        for material in materials.get("materials") or []:
            if not isinstance(material, dict):
                continue
            for probe in material.get("probes") or []:
                if not isinstance(probe, dict):
                    continue
                probe_id = str(probe.get("probe_id") or "").strip()
                for artifact in probe.get("evidence_files") or []:
                    if not isinstance(artifact, dict):
                        continue
                    records.append(
                        {
                            "artifact_id": probe_id,
                            "path": str(artifact.get("path") or "").replace("\\", "/").strip(),
                            "sha256": str(artifact.get("sha256") or "").strip(),
                            "owner_id": str(material.get("material_id") or "").strip(),
                        }
                    )
        return records, authority

    authority = "research_design.json artifact_fingerprints"
    design = _load_json(outdir / "research_design.json") or {}
    for artifact in design.get("artifact_fingerprints") or []:
        if not isinstance(artifact, dict):
            continue
        records.append(
            {
                "artifact_id": str(
                    artifact.get("artifact_id") or artifact.get("id") or ""
                ).strip(),
                "path": str(artifact.get("path") or "").replace("\\", "/").strip(),
                "sha256": str(artifact.get("sha256") or "").strip(),
                "owner_id": "research_design.json",
            }
        )
    return records, authority


def _verify_artifacts(
    outdir: Path,
    artifacts: Any,
    finding_id: str,
    repair_kind: str,
    affected_execution_ids: Any,
    issues: list[str],
) -> None:
    if not isinstance(artifacts, list) or not artifacts:
        issues.append(f"{finding_id}: scientific repair requires at least one rerun artifact")
        return
    expected_kind = ARTIFACT_KIND_BY_REPAIR.get(repair_kind, "")
    registered, authority = _registered_scientific_artifacts(outdir, expected_kind)
    affected_runs = {
        str(value).strip()
        for value in affected_execution_ids or []
        if str(value).strip()
    } if isinstance(affected_execution_ids, list) else set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            issues.append(f"{finding_id}: rerun artifact must be an object")
            continue
        artifact_id = str(artifact.get("artifact_id") or "").strip()
        kind = str(artifact.get("kind") or "").strip()
        relative = str(artifact.get("path") or "").replace("\\", "/").strip()
        artifact_sha = str(artifact.get("sha256") or "").strip()
        if not artifact_id:
            issues.append(f"{finding_id}: rerun artifact requires artifact_id")
        if kind != expected_kind:
            issues.append(
                f"{finding_id}: {repair_kind} rerun artifact kind must be {expected_kind}"
            )
        if (
            relative in RERUN_ARTIFACT_DENIED_PATHS
            or relative.startswith("review_prompts/")
            or relative.startswith("final_paper/")
            or relative.startswith(".avereth-")
        ):
            issues.append(
                f"{finding_id}: rerun artifact cannot reuse a controller, prompt, raw review, "
                f"derived view, or canonical manuscript file: {relative}"
            )
        allowed_roots = ARTIFACT_ALLOWED_ROOTS.get(expected_kind, ())
        if relative and not any(relative.startswith(root) for root in allowed_roots):
            issues.append(
                f"{finding_id}: {repair_kind} artifact path must use an allowed "
                f"{expected_kind} artifact root: {relative}"
            )
        target = _workspace_path(outdir, relative)
        if target is None or not target.is_file():
            issues.append(f"{finding_id}: rerun artifact is missing or outside the workspace: {relative}")
        elif artifact_sha != sha256_file(target):
            issues.append(f"{finding_id}: rerun artifact SHA mismatch: {relative}")
        matches = [
            record
            for record in registered
            if record["artifact_id"] == artifact_id
            and record["path"] == relative
            and record["sha256"] == artifact_sha
        ]
        if not matches:
            issues.append(
                f"{finding_id}: {repair_kind} artifact must exactly match {authority}: "
                f"{artifact_id or '<missing>'} {relative or '<missing>'}"
            )
        elif repair_kind == "RERUN_ANALYSIS" and affected_runs and not any(
            record["owner_id"] in affected_runs for record in matches
        ):
            issues.append(
                f"{finding_id}: RERUN_ANALYSIS artifact is not owned by an affected Execution ID"
            )


def _verification_artifact_issues(
    output: Path,
    *,
    finding_id: str,
    review_run_id: str,
    before_sha: str,
    current_sha: str,
    method: str,
    remaining_boundary: str,
    verified_by: str,
    verifier_context: str,
) -> list[str]:
    """Bind the verifier's own artifact to the exact closure decision."""
    try:
        text = output.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return [f"{finding_id}: verification output must be a readable text contract"]
    labels = {
        "Review Run ID": review_run_id,
        "Finding ID": finding_id,
        "Before Manuscript SHA-256": before_sha,
        "Verified Manuscript SHA-256": current_sha,
        "Verification Method": method,
        "Remaining Boundary": remaining_boundary,
        "Verification Result": "PASS",
        "Verified By": verified_by,
        "Verifier Context ID": verifier_context,
    }
    artifact_issues: list[str] = []
    for label, expected in labels.items():
        matches = re.findall(
            rf"(?im)^\s*{re.escape(label)}\s*[:：]\s*(.*?)\s*$",
            text,
        )
        if len(matches) != 1:
            artifact_issues.append(
                f"{finding_id}: verification artifact requires exactly one {label} binding"
            )
            continue
        if matches[0].strip() != expected:
            artifact_issues.append(
                f"{finding_id}: verification artifact {label} does not match the resolution"
            )
    return artifact_issues


def _validate_post_revision_review(
    outdir: Path,
    resolution: dict[str, Any],
    *,
    reviewed_sha: str,
    current_sha: str,
    issues: list[str],
) -> None:
    """Bind every changed manuscript state to an explicit delta/full re-review."""
    review = resolution.get("post_revision_review")
    if current_sha == reviewed_sha:
        if review is not None:
            issues.append(
                "post_revision_review must be null when the canonical manuscript still equals the reviewed snapshot"
            )
        return
    if not isinstance(review, dict):
        issues.append(
            "changed canonical manuscript requires a hash-bound DELTA or FULL post_revision_review"
        )
        return
    if review.get("review_run_id") != resolution.get("review_run_id"):
        issues.append("post_revision_review review_run_id does not match the resolution")
    mode = str(review.get("mode") or "")
    if mode not in {"DELTA", "FULL"}:
        issues.append("post_revision_review mode must be DELTA or FULL")
    if review.get("before_manuscript_sha256") != reviewed_sha:
        issues.append("post_revision_review before SHA must equal the originally reviewed manuscript")
    if review.get("after_manuscript_sha256") != current_sha:
        issues.append("post_revision_review after SHA must equal the current canonical manuscript")
    changed_locations = review.get("changed_locations")
    if not isinstance(changed_locations, list) or not changed_locations or any(
        not str(item).strip() for item in changed_locations
    ):
        issues.append("post_revision_review requires concrete changed_locations")
        changed_locations = []
    declared_locations = {
        _normalize_space(str(item)) for item in changed_locations if str(item).strip()
    }
    verified_locations = {
        _normalize_space(str(location))
        for row in resolution.get("resolutions") or []
        if isinstance(row, dict) and row.get("status") == "VERIFIED"
        for change in [row.get("change")]
        if isinstance(change, dict)
        for location in change.get("changed_locations") or []
        if str(location).strip()
    }
    omitted_verified_locations = sorted(verified_locations - declared_locations)
    if omitted_verified_locations:
        issues.append(
            f"post_revision_review {mode or '<invalid>'} changed_locations omit VERIFIED "
            "change locations: " + ", ".join(omitted_verified_locations)
        )
    scope = str(review.get("scope") or "").strip()
    reviewed_by = str(review.get("reviewed_by") or "").strip()
    context_id = str(review.get("reviewer_context_id") or "").strip()
    if not scope:
        issues.append("post_revision_review requires a substantive scope declaration")
    if not reviewed_by or not context_id:
        issues.append("post_revision_review requires reviewer identity and context")
    if review.get("result") != "PASS":
        issues.append("post_revision_review result must be PASS")

    relative = str(review.get("output_path") or "").replace("\\", "/")
    if relative != "review_prompts/post_revision_review_output.md":
        issues.append(
            "post_revision_review output must be review_prompts/post_revision_review_output.md"
        )
    output = _workspace_path(outdir, relative)
    if output is None or not output.is_file():
        issues.append("post_revision_review output is missing or outside the workspace")
        return
    if review.get("output_sha256") != sha256_file(output):
        issues.append("post_revision_review output SHA mismatch")
        return
    try:
        text = output.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        issues.append("post_revision_review output must be a readable text contract")
        return
    labels = {
        "Review Run ID": str(resolution.get("review_run_id") or ""),
        "Review Mode": mode,
        "Before Manuscript SHA-256": reviewed_sha,
        "Reviewed Manuscript SHA-256": current_sha,
        "Changed Locations": " | ".join(str(item).strip() for item in changed_locations),
        "Review Scope": scope,
        "Review Result": "PASS",
        "Reviewed By": reviewed_by,
        "Reviewer Context ID": context_id,
    }
    for label, expected in labels.items():
        matches = re.findall(
            rf"(?im)^\s*{re.escape(label)}\s*[:：]\s*(.*?)\s*$",
            text,
        )
        if len(matches) != 1:
            issues.append(
                f"post_revision_review artifact requires exactly one {label} binding"
            )
        elif matches[0].strip() != expected:
            issues.append(f"post_revision_review artifact {label} does not match JSON")


def _validate_review_cycles(
    outdir: Path,
    registry: dict[str, Any],
    resolution: dict[str, Any],
    *,
    reviewed_sha: str,
    current_sha: str,
    issues: list[str],
) -> None:
    cycles = resolution.get("review_cycles")
    if not isinstance(cycles, list):
        issues.append("review_cycles must be an array")
        return
    seen: set[str] = set()
    previous_id: str | None = None
    previous_after = reviewed_sha
    for index, cycle in enumerate(cycles, start=1):
        if not isinstance(cycle, dict):
            issues.append(f"review cycle {index} must be an object")
            continue
        cycle_id = str(cycle.get("cycle_id") or "")
        if not re.fullmatch(r"RC-[0-9]{3}", cycle_id) or cycle_id in seen:
            issues.append(f"review cycle {index} requires a unique RC-NNN cycle_id")
        seen.add(cycle_id)
        if cycle.get("parent_cycle_id") != previous_id:
            issues.append(f"{cycle_id or index}: parent_cycle_id must preserve the append-only cycle chain")
        if cycle.get("before_manuscript_sha256") != previous_after:
            issues.append(f"{cycle_id or index}: before SHA must equal the prior reviewed state")
        after_sha = str(cycle.get("after_manuscript_sha256") or "")
        if not re.fullmatch(r"[a-f0-9]{64}", after_sha):
            issues.append(f"{cycle_id or index}: after SHA is invalid")
        result = str(cycle.get("result") or "")
        if result not in {"PASS", "FINDINGS", "BLOCKED"}:
            issues.append(f"{cycle_id or index}: result must be PASS, FINDINGS, or BLOCKED")
        mode = str(cycle.get("mode") or "")
        if mode not in {"DELTA", "FULL"}:
            issues.append(f"{cycle_id or index}: mode must be DELTA or FULL")
        impact_rel = str(cycle.get("impact_path") or "").replace("\\", "/")
        impact_path = _workspace_path(outdir, impact_rel)
        impact = _load_json(impact_path) if impact_path is not None else None
        if impact is None or sha256_file(impact_path) != cycle.get("impact_sha256"):
            issues.append(f"{cycle_id or index}: revision impact is missing or changed")
            impact = {}
        if impact.get("batch_id") != cycle.get("batch_id"):
            issues.append(f"{cycle_id or index}: impact batch_id mismatch")
        reviewed_units = {str(item) for item in cycle.get("reviewed_unit_ids") or []}
        changed_units = {str(item) for item in impact.get("changed_unit_ids") or []}
        if changed_units - reviewed_units:
            issues.append(f"{cycle_id or index}: reviewed units omit actual changed units")
        required = [str(item) for item in impact.get("required_reviewers") or []]
        if cycle.get("required_reviewers") != required:
            issues.append(f"{cycle_id or index}: required_reviewers must equal revision impact routing")
        dispatched = [str(item) for item in cycle.get("dispatched_reviewers") or []]
        reused = [str(item) for item in cycle.get("reused_reviewers") or []]
        if set(dispatched) & set(reused) or set(dispatched) | set(reused) != set(required):
            issues.append(f"{cycle_id or index}: dispatched/reused reviewers must partition required_reviewers")
        reused_from = cycle.get("reused_from_cycles") if isinstance(cycle.get("reused_from_cycles"), dict) else {}
        prior_by_id = {
            str(item.get("cycle_id") or ""): item
            for item in cycles[: index - 1]
            if isinstance(item, dict)
        }
        if set(reused_from) != set(reused):
            issues.append(f"{cycle_id or index}: reused_from_cycles must cover every reused reviewer")
        for role in reused:
            prior = prior_by_id.get(str(reused_from.get(role) or ""), {})
            prior_inputs = prior.get("role_input_digests") if isinstance(prior.get("role_input_digests"), dict) else {}
            prior_results = prior.get("role_results") if isinstance(prior.get("role_results"), dict) else {}
            current_inputs = cycle.get("role_input_digests") if isinstance(cycle.get("role_input_digests"), dict) else {}
            if prior_results.get(role) != "PASS" or prior_inputs.get(role) != current_inputs.get(role):
                issues.append(f"{cycle_id or index}: reused {role} reviewer lacks an identical prior PASS input")
        outputs = cycle.get("reviewer_outputs")
        if not isinstance(outputs, list):
            issues.append(f"{cycle_id or index}: reviewer_outputs must be an array")
            outputs = []
        output_roles: set[str] = set()
        for output in outputs:
            if not isinstance(output, dict):
                issues.append(f"{cycle_id or index}: invalid reviewer output record")
                continue
            role = str(output.get("role") or "")
            output_roles.add(role)
            relative = str(output.get("path") or "").replace("\\", "/")
            target = _workspace_path(outdir, relative)
            if target is None or not target.is_file() or sha256_file(target) != output.get("sha256"):
                issues.append(f"{cycle_id or index}: immutable {role or '<unknown>'} cycle output changed")
        if result != "BLOCKED" and output_roles != set(dispatched):
            issues.append(f"{cycle_id or index}: reviewer outputs must cover every dispatched reviewer exactly once")
        elif result == "BLOCKED" and not output_roles <= set(dispatched):
            issues.append(f"{cycle_id or index}: BLOCKED cycle contains an undeclared reviewer output")
        if mode == "DELTA" and bool(impact.get("full_review_required")):
            issues.append(f"{cycle_id or index}: full-review impact cannot use DELTA mode")
        previous_id = cycle_id
        previous_after = after_sha
    if current_sha == reviewed_sha:
        if cycles:
            issues.append("review_cycles must be empty while the canonical manuscript equals the root snapshot")
    elif not cycles:
        issues.append("changed canonical manuscript requires an append-only review cycle")
    elif previous_after != current_sha:
        issues.append("latest review cycle does not bind the current canonical manuscript")
    elif resolution.get("status") == "CLOSED" and str(cycles[-1].get("result") or "") != "PASS":
        issues.append("a CLOSED resolution requires the latest review cycle to PASS")

    convergence = resolution.get("convergence")
    if not isinstance(convergence, dict):
        issues.append("convergence must be an object")
        return
    expected_latest = str(cycles[-1].get("cycle_id") or "") if cycles else None
    if convergence.get("latest_cycle_id") != expected_latest:
        issues.append("convergence.latest_cycle_id must equal the append-only cycle tip")
    active_keys = {
        str(finding.get("finding_key") or "")
        for finding in registry.get("findings") or []
        if isinstance(finding, dict)
        and finding.get("materiality") == "BLOCKING"
        and str(_resolution_by_id(resolution).get(str(finding.get("finding_id") or ""), {}).get("status") or "OPEN") not in TERMINAL_STATES
    }
    if set(convergence.get("active_blocking_finding_keys") or []) != active_keys:
        issues.append("convergence.active_blocking_finding_keys is stale")
    root_fields = {
        "instruction_failure", "owner_stage_check", "rewrite_scope",
        "claim_or_evidence_change", "reviewer_conflict", "next_strategy"
    }
    root_required = {
        str(item.get("finding_key") or "")
        for item in resolution.get("resolutions") or []
        if isinstance(item, dict)
        and int(item.get("reopen_count") or 0) >= 2
        and (
            not isinstance(item.get("root_cause_analysis"), dict)
            or any(not str(item["root_cause_analysis"].get(field) or "").strip() for field in root_fields)
        )
    }
    if set(convergence.get("root_cause_required_finding_keys") or []) != root_required:
        issues.append("convergence.root_cause_required_finding_keys is stale")
    expected_convergence = (
        "ROOT_CAUSE_REQUIRED"
        if root_required
        else "FROZEN"
        if not active_keys and (current_sha == reviewed_sha or (cycles and cycles[-1].get("result") == "PASS"))
        else "ACTIVE"
    )
    if convergence.get("status") != expected_convergence:
        issues.append(f"convergence.status must be {expected_convergence}")


def _validate_history(item: dict[str, Any], finding_id: str, issues: list[str]) -> None:
    history = item.get("history")
    status = str(item.get("status") or "")
    if status == "OPEN" and history in (None, []):
        return
    if not isinstance(history, list) or not history:
        issues.append(f"{finding_id}: non-OPEN resolution requires transition history")
        return
    previous = "OPEN"
    seen_states: list[str] = []
    for index, event in enumerate(history, start=1):
        if not isinstance(event, dict):
            issues.append(f"{finding_id}: history event {index} must be an object")
            continue
        from_state = str(event.get("from") or "")
        to_state = str(event.get("to") or "")
        if from_state != previous or to_state not in ALLOWED_TRANSITIONS.get(previous, set()):
            issues.append(f"{finding_id}: invalid transition {from_state or previous}->{to_state or '<empty>'}")
        if not str(event.get("by") or "").strip() or not str(event.get("at") or "").strip():
            issues.append(f"{finding_id}: every history event requires by and at")
        previous = to_state
        seen_states.append(to_state)
    if previous != status:
        issues.append(f"{finding_id}: history terminal state does not match status {status}")
    if status == "VERIFIED" and not ({"APPLIED", "VERIFIED"} <= set(seen_states)):
        issues.append(f"{finding_id}: VERIFIED requires APPLIED then VERIFIED history")


def _adjudication_complete(item: dict[str, Any]) -> bool:
    adjudication = item.get("adjudication")
    return bool(
        isinstance(adjudication, dict)
        and str(adjudication.get("changed_by") or "").strip()
        and str(adjudication.get("context_id") or "").strip()
        and str(adjudication.get("reason") or "").strip()
    )


def _validate_verified(
    outdir: Path,
    finding: dict[str, Any],
    resolution: dict[str, Any],
    current_sha: str,
    issues: list[str],
) -> None:
    finding_id = str(finding.get("finding_id") or "")
    severity = str(finding.get("severity") or "")
    final_severity = str(resolution.get("final_severity") or "")
    high_impact = severity in {"CRITICAL", "MAJOR"} or final_severity in {"CRITICAL", "MAJOR"}
    change = resolution.get("change")
    if not isinstance(change, dict):
        issues.append(f"{finding_id}: VERIFIED requires change evidence")
        return
    before_sha = str(change.get("before_manuscript_sha256") or "")
    after_sha = str(change.get("after_manuscript_sha256") or "")
    expected_before = str(resolution.get("_expected_before_sha") or "")
    if before_sha != expected_before:
        issues.append(f"{finding_id}: before manuscript SHA must match the reviewed snapshot")
    if after_sha != current_sha:
        issues.append(f"{finding_id}: after manuscript SHA must match the current canonical manuscript")
    if not before_sha or before_sha == after_sha:
        issues.append(f"{finding_id}: VERIFIED requires an actual manuscript delta")
    if str((finding.get("recommended_action") or {}).get("repair_kind") or "") == "NO_ACTION":
        issues.append(
            f"{finding_id}: NO_ACTION cannot close through APPLIED/VERIFIED; use a reasoned adjudication state"
        )
    changed_locations = change.get("changed_locations")
    if not isinstance(changed_locations, list) or not any(str(value).strip() for value in changed_locations):
        issues.append(f"{finding_id}: VERIFIED requires changed_locations")
    applied_by = str(change.get("applied_by") or "").strip()
    applier_context = str(change.get("applier_context_id") or "").strip()
    if not applied_by or not applier_context:
        issues.append(f"{finding_id}: VERIFIED requires applied_by and applier_context_id")
    if not str(change.get("change_summary") or "").strip():
        issues.append(f"{finding_id}: VERIFIED requires a substantive change_summary")
    if high_impact:
        checks = change.get("propagation_checks")
        by_target = {
            str(item.get("target") or ""): item
            for item in checks or []
            if isinstance(item, dict)
        } if isinstance(checks, list) else {}
        missing_targets = sorted(set(PROPAGATION_TARGETS) - set(by_target))
        if missing_targets:
            issues.append(
                f"{finding_id}: Critical/Major change evidence lacks propagation checks for "
                + ", ".join(missing_targets)
            )
        for target in PROPAGATION_TARGETS:
            row = by_target.get(target)
            if row is None:
                continue
            status = str(row.get("status") or "")
            if status not in {"CHECKED", "NOT_APPLICABLE"}:
                issues.append(f"{finding_id}: propagation target {target} has invalid status")
            if status == "CHECKED" and not str(row.get("evidence") or "").strip():
                issues.append(f"{finding_id}: propagation target {target} requires location evidence")
            if status == "NOT_APPLICABLE" and not str(row.get("reason") or "").strip():
                issues.append(f"{finding_id}: propagation target {target} requires an N/A reason")

    mapping = finding.get("identity_mapping") if isinstance(finding.get("identity_mapping"), dict) else {}
    for key in ID_PATTERNS:
        mapped = set(mapping.get(key) or [])
        if not mapped:
            continue
        change_key = "affected_" + key
        affected = set(change.get(change_key) or [])
        missing = sorted(mapped - affected)
        if missing:
            issues.append(
                f"{finding_id}: change evidence does not cover every mapped {key}: "
                + ", ".join(missing)
            )

    repair_kind = str((finding.get("recommended_action") or {}).get("repair_kind") or "")
    if repair_kind in SCIENTIFIC_REPAIRS:
        _verify_artifacts(
            outdir,
            change.get("rerun_artifacts"),
            finding_id,
            repair_kind,
            change.get("affected_execution_ids"),
            issues,
        )

    verification = resolution.get("verification")
    if not isinstance(verification, dict):
        issues.append(f"{finding_id}: VERIFIED requires verification evidence")
        return
    if verification.get("result") != "PASS":
        issues.append(f"{finding_id}: verification result must be PASS")
    if not str(verification.get("method") or "").strip():
        issues.append(f"{finding_id}: verification method is required")
    if not str(verification.get("remaining_boundary") or "").strip():
        issues.append(f"{finding_id}: verification remaining_boundary is required")
    if verification.get("verified_against_sha256") != current_sha:
        issues.append(f"{finding_id}: verifier did not check the current canonical manuscript SHA")
    verifier_context = str(verification.get("verifier_context_id") or "").strip()
    if not str(verification.get("verified_by") or "").strip() or not verifier_context:
        issues.append(f"{finding_id}: verification requires verified_by and verifier_context_id")
    if high_impact and applier_context and verifier_context == applier_context:
        issues.append(f"{finding_id}: Critical/Major verifier context must differ from applier context")
    if high_impact and applied_by and str(verification.get("verified_by") or "").strip() == applied_by:
        issues.append(f"{finding_id}: Critical/Major verifier identity must differ from applied_by")
    output_relative = str(verification.get("output_path") or "")
    normalized_output_relative = output_relative.replace("\\", "/")
    expected_output_relative = f"review_prompts/verifications/{finding_id}.md"
    if normalized_output_relative != expected_output_relative:
        issues.append(
            f"{finding_id}: verification output must be the dedicated artifact {expected_output_relative}"
        )
    output = _workspace_path(outdir, output_relative)
    if output is None or not output.is_file():
        issues.append(f"{finding_id}: verification output is missing or outside the workspace")
    elif verification.get("output_sha256") != sha256_file(output):
        issues.append(f"{finding_id}: verification output SHA mismatch")
    else:
        issues.extend(
            _verification_artifact_issues(
                output,
                finding_id=finding_id,
                review_run_id=str(resolution.get("_review_run_id") or ""),
                before_sha=before_sha,
                current_sha=current_sha,
                method=str(verification.get("method") or "").strip(),
                remaining_boundary=str(verification.get("remaining_boundary") or "").strip(),
                verified_by=str(verification.get("verified_by") or "").strip(),
                verifier_context=verifier_context,
            )
        )


def validate_lifecycle(
    outdir: Path,
    manuscript_path: Path,
    *,
    require_views: bool = True,
) -> LifecycleResult:
    registry = _load_json(outdir / "review_findings.json")
    resolution = _load_json(outdir / "review_resolution.json")
    issues: list[str] = []
    if registry is None or registry.get("schema_version") != FINDINGS_SCHEMA:
        return LifecycleResult(False, [f"review_findings.json must use {FINDINGS_SCHEMA}"])
    if resolution is None or resolution.get("schema_version") != RESOLUTION_SCHEMA:
        return LifecycleResult(False, [f"review_resolution.json must use {RESOLUTION_SCHEMA}"])
    shape_issues = [
        *_registered_schema_issues(
            registry,
            "avereth-review-findings-v3.schema.json",
            "review_findings.json",
        ),
        *_registered_schema_issues(
            resolution,
            "avereth-review-resolution-v2.schema.json",
            "review_resolution.json",
        ),
    ]
    if shape_issues:
        return LifecycleResult(False, shape_issues)
    if resolution.get("review_run_id") != registry.get("review_run_id"):
        issues.append("review_resolution review_run_id does not match review_findings")
    if resolution.get("findings_sha256") != sha256_file(outdir / "review_findings.json"):
        issues.append("review_resolution does not bind the exact review_findings.json SHA-256")

    assurance = _load_json(outdir / "review_assurance.json")
    manifest = _load_json(outdir / "review_prompts" / "review_manifest.json")
    if assurance is None or manifest is None:
        issues.append("review assurance and dispatch manifest must remain available")
    else:
        assurance_issues, _ = _validate_assurance(outdir, assurance, manifest)
        issues.extend(assurance_issues)
        current_inputs_changed = manifest.get("input_digests") != structured_review.review_input_digests(outdir)
        cycles = resolution.get("review_cycles") if isinstance(resolution.get("review_cycles"), list) else []
        if current_inputs_changed and not (cycles and cycles[-1].get("mode") == "FULL"):
            issues.append(
                "root review inputs changed without a current FULL review cycle"
            )
        if manifest.get("review_run_id") != registry.get("review_run_id"):
            issues.append("review registry no longer matches the dispatch manifest")
        if not _existing_registry_is_current(outdir, registry, assurance):
            issues.append("review registry provenance no longer equals the v2 assurance declaration")

    raw_validation = structured_review.validate_independence(outdir / "review_prompts")
    issues.extend(str(issue) for issue in raw_validation.get("findings") or [])
    issues.extend(_raw_projection_issues(outdir, registry))
    if registry.get("venue_contract") != structured_review.venue_contract_state(outdir):
        issues.append("verified venue contract changed after Finding compilation; redispatch review")

    for source in registry.get("source_reviews") or []:
        if not isinstance(source, dict):
            issues.append("review_findings source_reviews contains a non-object record")
            continue
        target = _workspace_path(outdir, str(source.get("output_path") or ""))
        if target is None or not target.is_file() or sha256_file(target) != source.get("output_sha256"):
            issues.append(f"raw reviewer output changed or is missing: {source.get('output_path')}")

    findings = [item for item in registry.get("findings") or [] if isinstance(item, dict)]
    finding_keys = [str(item.get("finding_key") or "") for item in findings]
    duplicate_keys = sorted({key for key in finding_keys if key and finding_keys.count(key) > 1})
    if duplicate_keys:
        issues.append("review_findings repeats stable finding_key(s): " + ", ".join(duplicate_keys))
    for finding in findings:
        if finding.get("finding_key") != finding_key(finding):
            issues.append(f"{finding.get('finding_id')}: finding_key differs from deterministic identity")
        discovery = str(finding.get("discovery_class") or "")
        materiality = str(finding.get("materiality") or "")
        if discovery not in DISCOVERY_CLASSES or materiality not in MATERIALITIES:
            issues.append(f"{finding.get('finding_id')}: invalid discovery_class or materiality")
        if materiality != _materiality(str(finding.get("severity") or ""), discovery):
            issues.append(f"{finding.get('finding_id')}: materiality differs from convergence policy")
        issues.extend(_identity_mapping_issues(outdir, finding))
    source_verdicts = {
        str(item.get("role") or ""): str(item.get("verdict") or "")
        for item in registry.get("source_reviews") or []
        if isinstance(item, dict)
    }
    reviewed_identity = registry.get("manuscript") or {}
    canonical_manuscript = _workspace_path(
        outdir, str(reviewed_identity.get("path") or "")
    )
    if canonical_manuscript is None or not canonical_manuscript.is_file():
        issues.append("review registry canonical manuscript is missing or outside the workspace")
        current_sha = ""
    else:
        if manuscript_path.resolve() != canonical_manuscript.resolve():
            issues.append(
                "lifecycle validation manuscript must equal the registry canonical manuscript path"
            )
        current_sha = sha256_file(canonical_manuscript)
    reviewed_sha = str(reviewed_identity.get("sha256") or "")

    if registry.get("status") == "NO_MATERIAL_OBJECTIONS":
        if findings:
            issues.append("NO_MATERIAL_OBJECTIONS registry cannot contain findings")
        if set(source_verdicts) != set(ROLE_FILES) or set(source_verdicts.values()) != {"PASS"}:
            issues.append("NO_MATERIAL_OBJECTIONS requires all three immutable source verdicts to be PASS")
        if resolution.get("status") != "NO_MATERIAL_OBJECTIONS" or resolution.get("resolutions") not in ([], None):
            issues.append("zero-finding resolution must be NO_MATERIAL_OBJECTIONS with no rows")
        if current_sha != reviewed_sha:
            issues.append("zero-finding PASS is stale because the canonical manuscript changed after review")
    else:
        if registry.get("status") != "HAS_FINDINGS" or not findings:
            issues.append("non-empty review registry must use HAS_FINDINGS")
        rows = resolution.get("resolutions")
        if not isinstance(rows, list):
            rows = []
            issues.append("review_resolution resolutions must be an array")
        row_ids = [
            str(item.get("finding_id") or "")
            for item in rows
            if isinstance(item, dict)
        ]
        duplicate_ids = sorted(
            finding_id
            for finding_id in set(row_ids)
            if finding_id and row_ids.count(finding_id) > 1
        )
        if duplicate_ids:
            issues.append(
                "review resolution repeats Finding ID(s): " + ", ".join(duplicate_ids)
            )
        by_id = {
            str(item.get("finding_id") or ""): item
            for item in rows
            if isinstance(item, dict)
        }
        expected_ids = {str(item.get("finding_id") or "") for item in findings}
        if set(by_id) != expected_ids:
            missing = sorted(expected_ids - set(by_id))
            extra = sorted(set(by_id) - expected_ids)
            if missing:
                issues.append("review resolution omitted Finding ID(s): " + ", ".join(missing))
            if extra:
                issues.append("review resolution invented Finding ID(s): " + ", ".join(extra))
        for finding in findings:
            finding_id = str(finding.get("finding_id") or "")
            item = by_id.get(finding_id)
            if item is None:
                continue
            status = str(item.get("status") or "")
            original = str(finding.get("severity") or "")
            final = str(item.get("final_severity") or "")
            if item.get("finding_key") != finding.get("finding_key"):
                issues.append(f"{finding_id}: resolution finding_key must match review_findings")
            if item.get("original_severity") != original:
                issues.append(f"{finding_id}: original severity must be copied exactly from review_findings")
            if final not in SEVERITIES:
                issues.append(f"{finding_id}: invalid final severity {final or '<empty>'}")
            if final != original and not _adjudication_complete(item):
                issues.append(f"{finding_id}: severity change requires changed_by, context_id, and adjudication reason")
            expected_stage = _earliest_stage(finding)
            actual_stage = str(item.get("earliest_reopen_stage") or "")
            if actual_stage not in OWNER_STAGES or STAGE_INDEX.get(actual_stage, 99) > STAGE_INDEX.get(expected_stage, 99):
                issues.append(f"{finding_id}: earliest_reopen_stage cannot be later than {expected_stage}")
            mapping = finding.get("identity_mapping") if isinstance(finding.get("identity_mapping"), dict) else {}
            if original in {"CRITICAL", "MAJOR"} and mapping.get("mapping_status") == "unresolved":
                issues.append(f"{finding_id}: Critical/Major identity mapping is unresolved")
            if status not in RESOLUTION_STATES:
                issues.append(f"{finding_id}: invalid resolution status {status or '<empty>'}")
                continue
            expected_decision = DECISION_BY_STATUS[status]
            if item.get("decision") != expected_decision:
                issues.append(
                    f"{finding_id}: {status} requires decision {expected_decision}"
                )
            _validate_history(item, finding_id, issues)
            reopen_events = sum(
                1
                for event in item.get("history") or []
                if isinstance(event, dict) and event.get("to") == "REOPENED"
            )
            if int(item.get("reopen_count") or 0) != reopen_events:
                issues.append(f"{finding_id}: reopen_count must equal REOPENED transition history")
            if reopen_events >= 2:
                diagnosis = item.get("root_cause_analysis")
                required_fields = {
                    "instruction_failure", "owner_stage_check", "rewrite_scope",
                    "claim_or_evidence_change", "reviewer_conflict", "next_strategy"
                }
                if not isinstance(diagnosis, dict) or any(
                    not str(diagnosis.get(field) or "").strip() for field in required_fields
                ):
                    issues.append(f"{finding_id}: second reopen requires a complete root_cause_analysis")
            if status not in TERMINAL_STATES and finding.get("materiality") == "BLOCKING":
                issues.append(f"{finding_id}: resolution is not closed ({status})")
            if status == "VERIFIED":
                item["_expected_before_sha"] = reviewed_sha
                item["_review_run_id"] = str(resolution.get("review_run_id") or "")
                _validate_verified(outdir, finding, item, current_sha, issues)
                item.pop("_expected_before_sha", None)
                item.pop("_review_run_id", None)
            elif status == "APPLIED":
                change = item.get("change") if isinstance(item.get("change"), dict) else {}
                before_sha = str(change.get("before_manuscript_sha256") or "")
                after_sha = str(change.get("after_manuscript_sha256") or "")
                if not change:
                    issues.append(f"{finding_id}: APPLIED requires change evidence")
                else:
                    if before_sha != reviewed_sha or after_sha != current_sha:
                        issues.append(
                            f"{finding_id}: APPLIED change evidence must bind the reviewed and current manuscript SHA"
                        )
                    if not before_sha or before_sha == after_sha:
                        issues.append(f"{finding_id}: APPLIED requires an actual manuscript delta")
                if str((finding.get("recommended_action") or {}).get("repair_kind") or "") == "NO_ACTION":
                    issues.append(
                        f"{finding_id}: NO_ACTION cannot enter APPLIED; use a reasoned adjudication state"
                    )
            elif status == "MERGED":
                target_id = str(item.get("merge_target_finding_id") or "")
                if target_id not in expected_ids or target_id == finding_id:
                    issues.append(f"{finding_id}: MERGED requires another valid merge target Finding ID")
                elif str(by_id.get(target_id, {}).get("status") or "") not in TERMINAL_STATES:
                    issues.append(f"{finding_id}: merge target {target_id} is not closed")
                else:
                    target_severity = str(by_id.get(target_id, {}).get("final_severity") or "")
                    if (
                        final in SEVERITY_RANK
                        and target_severity in SEVERITY_RANK
                        and SEVERITY_RANK[target_severity] > SEVERITY_RANK[final]
                    ):
                        issues.append(
                            f"{finding_id}: merge target {target_id} has a lower final severity"
                        )
                if not _adjudication_complete(item):
                    issues.append(f"{finding_id}: MERGED requires a traceable duplicate-finding adjudication")
            elif status == "REJECTED" and not _adjudication_complete(item):
                issues.append(f"{finding_id}: REJECTED requires a traceable adjudication")
            elif status == "WAIVED":
                if original == "CRITICAL" or final == "CRITICAL":
                    issues.append(f"{finding_id}: Critical findings cannot be WAIVED")
                authorization = item.get("authorization")
                if not (
                    isinstance(authorization, dict)
                    and str(authorization.get("authorized_by") or "").strip()
                    and str(authorization.get("authorization_evidence") or "").strip()
                    and str(authorization.get("risk_statement") or "").strip()
                ):
                    issues.append(f"{finding_id}: WAIVED requires authorization evidence and risk statement")

        merge_targets = {
            str(item.get("finding_id") or ""): str(item.get("merge_target_finding_id") or "")
            for item in rows
            if isinstance(item, dict) and item.get("status") == "MERGED"
        }
        reported_cycles: set[frozenset[str]] = set()
        for start in merge_targets:
            path: list[str] = []
            current = start
            while current in merge_targets:
                if current in path:
                    cycle = path[path.index(current):]
                    identity = frozenset(cycle)
                    if identity not in reported_cycles:
                        reported_cycles.add(identity)
                        issues.append(
                            "review resolution MERGED cycle is forbidden: "
                            + " -> ".join([*cycle, cycle[0]])
                        )
                    break
                path.append(current)
                current = merge_targets[current]

        blocking_ids = {
            str(item.get("finding_id") or "")
            for item in findings
            if item.get("materiality") == "BLOCKING"
        }
        all_terminal = all(
            str(by_id.get(finding_id, {}).get("status") or "") in TERMINAL_STATES
            for finding_id in blocking_ids
        )
        expected_resolution_status = "CLOSED" if all_terminal else "ACTIVE"
        if resolution.get("status") != expected_resolution_status:
            issues.append(
                f"review_resolution status must be {expected_resolution_status} for its Finding states"
            )
        expected_backlog = sorted(
            str(item.get("finding_key") or "")
            for item in findings
            if item.get("materiality") == "NON_BLOCKING"
            and str(by_id.get(str(item.get("finding_id") or ""), {}).get("status") or "OPEN") not in TERMINAL_STATES
        )
        if sorted(str(item) for item in resolution.get("optional_backlog") or []) != expected_backlog:
            issues.append("optional_backlog must equal the unresolved non-blocking Finding keys")

    _validate_review_cycles(
        outdir,
        registry,
        resolution,
        reviewed_sha=reviewed_sha,
        current_sha=current_sha,
        issues=issues,
    )

    if require_views:
        expected_views = {
            "structured_review.md": render_structured_review(registry, resolution),
            "reviewer_audit.md": render_reviewer_audit(registry, resolution),
            "revision_plan.md": render_revision_plan(registry, resolution, outdir=outdir),
        }
        for relative, expected in expected_views.items():
            try:
                actual = (outdir / relative).read_text(encoding="utf-8-sig")
            except OSError:
                actual = ""
            if actual.rstrip() != expected.rstrip():
                issues.append(f"{relative} is missing or is not the current JSON-derived view")

    config = _load_json(outdir / "workflow_config.json") or {}
    route = review_route_plan(
        registry,
        resolution,
        profile=str(config.get("task_profile") or "full_paper"),
        revision_contract=_load_json(outdir / "revision_contract.json"),
        outdir=outdir,
    )
    issues.extend(
        "review profile authorization: " + str(issue)
        for issue in route.get("issues") or []
    )
    metrics = {
        "review_run_id": registry.get("review_run_id"),
        "registry_status": registry.get("status"),
        "finding_count": len(findings),
        "recommendation": lifecycle_recommendation(registry, resolution),
        "review_route": route,
    }
    return LifecycleResult(not issues, issues, metrics=metrics)


def _resolution_by_id(resolution: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(resolution, dict):
        return {}
    return {
        str(item.get("finding_id") or ""): item
        for item in resolution.get("resolutions") or []
        if isinstance(item, dict)
    }


def lifecycle_recommendation(registry: dict[str, Any], resolution: dict[str, Any] | None) -> str:
    findings = [item for item in registry.get("findings") or [] if isinstance(item, dict)]
    if not findings:
        return "PASS"
    by_id = _resolution_by_id(resolution)
    unresolved: list[str] = []
    for finding in findings:
        if finding.get("materiality") == "NON_BLOCKING":
            continue
        row = by_id.get(str(finding.get("finding_id") or ""), {})
        status = str(row.get("status") or "OPEN")
        if status not in TERMINAL_STATES:
            original = str(finding.get("severity") or "")
            final = str(row.get("final_severity") or "")
            if final in SEVERITIES and (final == original or _adjudication_complete(row)):
                unresolved.append(final)
            else:
                unresolved.append(original)
    if "CRITICAL" in unresolved:
        return "BLOCK"
    if "MAJOR" in unresolved:
        return "MAJOR_REVISION"
    if unresolved:
        return "MINOR_REVISION"
    return "PASS"


def render_structured_review(registry: dict[str, Any], resolution: dict[str, Any] | None) -> str:
    by_id = _resolution_by_id(resolution)
    lines = [
        "# Structured Peer Review",
        "",
        f"- Schema: `{_markdown_table_cell(registry.get('schema_version', ''))}`",
        f"- Review run: `{_markdown_table_cell(registry.get('review_run_id', ''))}`",
        f"- Manuscript: `{_markdown_table_cell((registry.get('manuscript') or {}).get('path', ''))}`",
        f"- Manuscript SHA-256: `{_markdown_table_cell((registry.get('manuscript') or {}).get('sha256', ''))}`",
        f"- Registry status: **{_markdown_table_cell(registry.get('status', ''))}**",
        f"- Lifecycle recommendation: **{_markdown_table_cell(lifecycle_recommendation(registry, resolution))}**",
        "",
        "## Source Verdicts",
        "",
        "| Reviewer | Verdict | Context ID | Output | Output SHA-256 |",
        "|---|---|---|---|---|",
    ]
    for source in registry.get("source_reviews") or []:
        if not isinstance(source, dict):
            continue
        lines.append(
            _markdown_table_row(
                source.get("role", ""),
                source.get("verdict", ""),
                source.get("context_id", ""),
                source.get("output_path", ""),
                source.get("output_sha256", ""),
            )
        )
    overlap = ((registry.get("provenance") or {}).get("textual_overlap") or {})
    lines.extend(
        [
            "",
            "## Provenance and Textual Overlap",
            "",
            f"- Provenance mode: `{_markdown_table_cell((registry.get('provenance') or {}).get('mode', ''))}`",
            f"- Provenance independence: `{str(bool((registry.get('provenance') or {}).get('provenance_independence'))).lower()}`",
            f"- Textual diversity score: `{_markdown_table_cell(overlap.get('textual_diversity_score', 0))}` (diagnostic only)",
            "",
            "## Findings",
            "",
        ]
    )
    findings = [item for item in registry.get("findings") or [] if isinstance(item, dict)]
    if not findings:
        lines.extend(
            [
                "Status: **NO_MATERIAL_OBJECTIONS**",
                "",
                "All three immutable reviewer outputs returned PASS with zero findings. No objection was manufactured.",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "| Finding ID | Finding Key | Reviewer | Severity | Materiality | Discovery | Location | Mapping | Repair | Owner | Resolution |",
                "|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for item in findings:
            fid = str(item.get("finding_id") or "")
            source = item.get("source") or {}
            locator = item.get("manuscript_locator") or {}
            mapping = item.get("identity_mapping") or {}
            action = item.get("recommended_action") or {}
            row = by_id.get(fid, {})
            lines.append(
                _markdown_table_row(
                    fid,
                    item.get("finding_key", ""),
                    source.get("reviewer_role", ""),
                    item.get("severity", ""),
                    item.get("materiality", ""),
                    item.get("discovery_class", ""),
                    locator.get("location", ""),
                    mapping.get("mapping_status", ""),
                    action.get("repair_kind", ""),
                    action.get("owner_stage", ""),
                    row.get("status", "OPEN"),
                )
            )
        for item in findings:
            fid = str(item.get("finding_id") or "")
            locator = item.get("manuscript_locator") or {}
            action = item.get("recommended_action") or {}
            mapping = item.get("identity_mapping") or {}
            lines.extend(
                [
                    "",
                    f"### {_markdown_table_cell(fid)}",
                    "",
                    f"- Original severity: **{_markdown_table_cell(item.get('severity', ''))}**; confidence: **{_markdown_table_cell(item.get('confidence', ''))}**",
                    f"- Stable key: `{_markdown_table_cell(item.get('finding_key', ''))}`; materiality: **{_markdown_table_cell(item.get('materiality', ''))}**; discovery: `{_markdown_table_cell(item.get('discovery_class', ''))}`",
                    f"- Category: `{_markdown_table_cell(item.get('category', ''))}`",
                    f"- Location: {_markdown_table_cell(locator.get('location', ''))}",
                    f"- Quoted span SHA-256: `{_markdown_table_cell(locator.get('quoted_span_sha256', ''))}`",
                    f"- Issue: {_markdown_table_cell(item.get('problem', ''))}",
                    f"- Reader consequence: {_markdown_table_cell(item.get('reader_consequence', ''))}",
                    f"- Identity mapping: `{_markdown_table_cell(mapping.get('mapping_status', ''))}`; claims={_markdown_table_cell(mapping.get('claim_ids', []))}; evidence={_markdown_table_cell(mapping.get('evidence_ids', []))}; designs={_markdown_table_cell(mapping.get('design_ids', []))}; executions={_markdown_table_cell(mapping.get('execution_ids', []))}",
                    f"- Repair route: `{_markdown_table_cell(action.get('repair_kind', ''))}` → `{_markdown_table_cell(action.get('owner_stage', ''))}`; text action `{_markdown_table_cell(action.get('text_action', ''))}`; net word delta `{_markdown_table_cell(action.get('net_word_delta', 0))}`",
                    f"- Recommended action: {_markdown_table_cell(action.get('instruction', ''))}",
                    f"- Resolution status: **{_markdown_table_cell(by_id.get(fid, {}).get('status', 'OPEN'))}**",
                ]
            )
    lines.extend(
        [
            "",
            "## Editor Synthesis",
            "",
            "The lifecycle recommendation is derived from unresolved Finding severities. Reviewer scores are diagnostic and cannot offset a Critical or Major finding.",
            "",
        ]
    )
    return "\n".join(lines)


def render_reviewer_audit(registry: dict[str, Any], resolution: dict[str, Any] | None) -> str:
    by_id = _resolution_by_id(resolution)
    lines = [
        "# Reviewer-Aware Audit",
        "",
        f"- Review run: `{_markdown_table_cell(registry.get('review_run_id', ''))}`",
        f"- Status: **{_markdown_table_cell(registry.get('status', ''))}**",
        f"- Lifecycle recommendation: **{_markdown_table_cell(lifecycle_recommendation(registry, resolution))}**",
        "",
        "## Reviewer Value Map",
        "",
        "| Reviewer | Dimension ID | Applicability | Score | Reason | Manuscript Location |",
        "|---|---|---|---:|---|---|",
    ]
    for source in registry.get("source_reviews") or []:
        if not isinstance(source, dict):
            continue
        for row in source.get("rubric") or []:
            if not isinstance(row, dict):
                continue
            score = row.get("score") if row.get("score") not in {"", None} else "N/A"
            lines.append(
                _markdown_table_row(
                    source.get("role", ""),
                    row.get("dimension_id", ""),
                    row.get("applicability", ""),
                    score,
                    row.get("reason", ""),
                    row.get("manuscript_location", ""),
                )
            )
    lines.extend(["", "## Reviewer Objection Register", ""])
    findings = [item for item in registry.get("findings") or [] if isinstance(item, dict)]
    if not findings:
        lines.append("Status: **NO_MATERIAL_OBJECTIONS**")
        lines.append("")
        lines.append("Source verdicts: Methods=PASS; Contribution=PASS; Clarity=PASS.")
    else:
        lines.extend(
            [
                "| Finding ID | Source | Original Severity | Final Severity | Location | Repair Kind | Owner Stage | Mapping | Status | Resolution Evidence | Verification |",
                "|---|---|---|---|---|---|---|---|---|---|---|",
            ]
        )
        for item in findings:
            fid = str(item.get("finding_id") or "")
            row = by_id.get(fid, {})
            action = item.get("recommended_action") or {}
            locator = item.get("manuscript_locator") or {}
            mapping = item.get("identity_mapping") or {}
            change = row.get("change") if isinstance(row.get("change"), dict) else {}
            verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
            adjudication = row.get("adjudication") if isinstance(row.get("adjudication"), dict) else {}
            authorization = row.get("authorization") if isinstance(row.get("authorization"), dict) else {}
            evidence_parts: list[str] = []
            if adjudication:
                evidence_parts.append(
                    "adjudicated by "
                    f"{adjudication.get('changed_by', '')} [{adjudication.get('context_id', '')}]: "
                    f"{adjudication.get('reason', '')}"
                )
            if row.get("merge_target_finding_id"):
                evidence_parts.append(f"merged into {row.get('merge_target_finding_id')}")
            if authorization:
                evidence_parts.append(
                    "waived by "
                    f"{authorization.get('authorized_by', '')}; evidence="
                    f"{authorization.get('authorization_evidence', '')}; risk="
                    f"{authorization.get('risk_statement', '')}"
                )
            if change.get("change_summary"):
                evidence_parts.append(str(change.get("change_summary")))
            resolution_evidence = "; ".join(evidence_parts) or "—"
            verification_evidence = (
                f"{verification.get('result', '')} by {verification.get('verified_by', '')} "
                f"[{verification.get('verifier_context_id', '')}] @ {verification.get('output_path', '')}"
                if verification
                else "—"
            )
            lines.append(
                _markdown_table_row(
                    fid,
                    (item.get("source") or {}).get("reviewer_role", ""),
                    item.get("severity", ""),
                    row.get("final_severity", item.get("severity", "")),
                    locator.get("location", ""),
                    action.get("repair_kind", ""),
                    action.get("owner_stage", ""),
                    mapping.get("mapping_status", ""),
                    row.get("status", "OPEN"),
                    resolution_evidence,
                    verification_evidence,
                )
            )

    cycles = resolution.get("review_cycles") if isinstance(resolution, dict) else []
    lines.extend(["", "## Review Convergence Cycles", ""])
    if isinstance(cycles, list) and cycles:
        lines.extend([
            "| Cycle | Batch | Parent | Mode | Required | Reused | Result | New | Reopened |",
            "|---|---|---|---|---|---|---|---|---|",
        ])
        for cycle in cycles:
            if not isinstance(cycle, dict):
                continue
            lines.append(_markdown_table_row(
                cycle.get("cycle_id", ""), cycle.get("batch_id", ""),
                cycle.get("parent_cycle_id") or "root", cycle.get("mode", ""),
                cycle.get("required_reviewers", []), cycle.get("reused_reviewers", []),
                cycle.get("result", ""), cycle.get("new_finding_keys", []),
                cycle.get("reopened_finding_keys", []),
            ))
    else:
        lines.append("- No revision cycle: the canonical manuscript still equals the root review snapshot.")
    convergence = resolution.get("convergence") if isinstance(resolution, dict) else {}
    lines.extend([
        "",
        f"- Convergence: **{_markdown_table_cell((convergence or {}).get('status', ''))}**",
        f"- Active blocking keys: {_markdown_table_cell((convergence or {}).get('active_blocking_finding_keys', []))}",
        f"- Optional backlog: {_markdown_table_cell((resolution or {}).get('optional_backlog', []))}",
    ])

    venue_rows = [
        row
        for source in registry.get("source_reviews") or []
        if isinstance(source, dict)
        for row in source.get("rubric") or []
        if isinstance(row, dict) and row.get("dimension_id") == "CON-VENUE-FIT"
    ]
    lines.extend(["", "## Editorial Fit Assessment", ""])
    if venue_rows:
        row = venue_rows[0]
        lines.extend(
            [
                f"- Applicability: **{_markdown_table_cell(row.get('applicability', ''))}**",
                f"- Diagnostic score: `{_markdown_table_cell(row.get('score') or 'N/A')}`",
                f"- Evidence-grounded reason: {_markdown_table_cell(row.get('reason', ''))}",
                f"- Manuscript location: {_markdown_table_cell(row.get('manuscript_location', ''))}",
            ]
        )
    else:
        lines.append("- Applicability: **BLOCKED** — the canonical Contribution rubric row is missing.")
    lines.append("")
    return "\n".join(lines)


def render_revision_plan(
    registry: dict[str, Any],
    resolution: dict[str, Any] | None,
    *,
    outdir: Path | None = None,
) -> str:
    by_id = _resolution_by_id(resolution)
    config = _load_json(outdir / "workflow_config.json") if outdir is not None else None
    profile = str((config or {}).get("task_profile") or "full_paper")
    contract = _load_json(outdir / "revision_contract.json") if outdir is not None else None
    route = review_route_plan(
        registry,
        resolution,
        profile=profile,
        revision_contract=contract,
        outdir=outdir,
    )
    lines = [
        "# Review Revision Plan",
        "",
        f"- Review run: `{_markdown_table_cell(registry.get('review_run_id', ''))}`",
        "- Authority: plan-only derived view; it does not mutate `revision_contract.json` or any upstream fact source.",
        f"- Task profile: `{_markdown_table_cell(route['profile'])}`",
        f"- Effective earliest reopen stage: `{_markdown_table_cell(route['effective_earliest_reopen_stage'] or 'none')}`",
        f"- Required action: `{_markdown_table_cell(route['action'])}`",
        "- Apply rule: review this plan, then explicitly create or amend an authorized `revision_contract.json`; no review command applies it automatically.",
        "",
        "| Finding ID | Repair Kind | Owner Stage | Earliest Reopen Stage | Claim IDs | Evidence IDs | Design IDs | Execution IDs | Resolution Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for item in registry.get("findings") or []:
        if not isinstance(item, dict):
            continue
        fid = str(item.get("finding_id") or "")
        action = item.get("recommended_action") or {}
        mapping = item.get("identity_mapping") or {}
        row = by_id.get(fid, {})
        lines.append(
            _markdown_table_row(
                fid,
                action.get("repair_kind", ""),
                action.get("owner_stage", ""),
                row.get("earliest_reopen_stage", action.get("owner_stage", "")),
                ", ".join(mapping.get("claim_ids") or []) or "—",
                ", ".join(mapping.get("evidence_ids") or []) or "—",
                ", ".join(mapping.get("design_ids") or []) or "—",
                ", ".join(mapping.get("execution_ids") or []) or "—",
                row.get("status", "OPEN"),
            )
        )
    lines.append("")
    if route["issues"]:
        lines.extend(["## Routing Issues", ""])
        lines.extend(f"- {_markdown_table_cell(issue)}" for issue in route["issues"])
        lines.append("")
    return "\n".join(lines)


def render_views(
    outdir: Path,
    registry: dict[str, Any],
    resolution: dict[str, Any] | None,
) -> list[str]:
    views = {
        "structured_review.md": render_structured_review(registry, resolution),
        "reviewer_audit.md": render_reviewer_audit(registry, resolution),
        "revision_plan.md": render_revision_plan(registry, resolution, outdir=outdir),
    }
    for relative, content in views.items():
        _atomic_write(outdir / relative, content.rstrip() + "\n")
    return list(views)


def default_manuscript(outdir: Path) -> Path:
    manifest = _load_json(outdir / "review_prompts" / "review_manifest.json")
    if manifest:
        candidate = _workspace_path(outdir, str(manifest.get("canonical_manuscript") or ""))
        if candidate is not None:
            return candidate
    for relative in (
        "final_paper/main.tex",
        "final_paper/main.md",
        "final_paper/main.docx",
        "final_paper/manuscript.md",
        "final_paper/manuscript.docx",
    ):
        candidate = outdir / relative
        if candidate.is_file():
            return candidate
    return outdir / "final_paper" / "main.tex"


def migrate_review_lifecycle(outdir: Path, *, apply: bool = False) -> LifecycleResult:
    registry = _load_json(outdir / "review_findings.json")
    resolution = _load_json(outdir / "review_resolution.json")
    if registry is None or resolution is None:
        return LifecycleResult(False, ["review_findings.json and review_resolution.json are required"])
    if registry.get("schema_version") == FINDINGS_SCHEMA and resolution.get("schema_version") == RESOLUTION_SCHEMA:
        return LifecycleResult(True, metrics={"mode": "already-current"})
    if registry.get("schema_version") != LEGACY_FINDINGS_SCHEMA or resolution.get("schema_version") != LEGACY_RESOLUTION_SCHEMA:
        return LifecycleResult(False, ["migration accepts only the v2 findings plus v1 resolution pair"])
    if resolution.get("post_revision_review") is not None:
        return LifecycleResult(
            False,
            [
                "legacy post_revision_review cannot be inferred as a v2 review cycle; "
                "preserve it as history and dispatch a new hash-bound cycle"
            ],
        )
    migrated_registry = json.loads(json.dumps(registry))
    root_run = str(registry.get("review_run_id") or "")
    migrated_registry["schema_version"] = FINDINGS_SCHEMA
    migrated_registry["root_review_run_id"] = root_run
    for item in migrated_registry.get("findings") or []:
        if not isinstance(item, dict):
            continue
        locator = item.get("manuscript_locator") if isinstance(item.get("manuscript_locator"), dict) else {}
        locator["manuscript_unit_id"] = _stable_manuscript_unit_id(str(locator.get("quoted_span") or ""))
        item["manuscript_locator"] = locator
        item["finding_key"] = finding_key(item)
        item["first_seen_run_id"] = root_run
        item["last_seen_cycle_id"] = None
        item["discovery_class"] = "BASELINE"
        item["materiality"] = _materiality(str(item.get("severity") or ""), "BASELINE")
        item["lineage"] = {"same_as": None, "refines": None, "caused_by_batch": None, "reopened_from": None}
        item["occurrences"] = [_occurrence(item, run_id=root_run, cycle_id=None)]
    key_by_id = {
        str(item.get("finding_id") or ""): str(item.get("finding_key") or "")
        for item in migrated_registry.get("findings") or []
        if isinstance(item, dict)
    }
    migrated_resolution = json.loads(json.dumps(resolution))
    migrated_resolution["schema_version"] = RESOLUTION_SCHEMA
    migrated_resolution.pop("post_revision_review", None)
    for row in migrated_resolution.get("resolutions") or []:
        if not isinstance(row, dict):
            continue
        row["finding_key"] = key_by_id.get(str(row.get("finding_id") or ""), "")
        row["reopen_count"] = sum(
            1 for event in row.get("history") or []
            if isinstance(event, dict) and event.get("to") == "REOPENED"
        )
        row["root_cause_analysis"] = None
    migrated_resolution["revision_batches"] = []
    migrated_resolution["review_cycles"] = []
    migrated_resolution["optional_backlog"] = []
    migrated_resolution["convergence"] = {
        "status": "ACTIVE", "latest_cycle_id": None,
        "active_blocking_finding_keys": [], "root_cause_required_finding_keys": []
    }
    _refresh_convergence(migrated_registry, migrated_resolution)
    generated: list[str] = []
    if apply:
        backup_dir = outdir / "migration" / "review_convergence_v66"
        if backup_dir.exists():
            return LifecycleResult(False, ["review convergence migration backup already exists"])
        backup_dir.mkdir(parents=True)
        _atomic_json(backup_dir / "review_findings.v2.json", registry)
        _atomic_json(backup_dir / "review_resolution.v1.json", resolution)
        _atomic_json(outdir / "review_findings.json", migrated_registry)
        migrated_resolution["findings_sha256"] = sha256_file(outdir / "review_findings.json")
        _atomic_json(outdir / "review_resolution.json", migrated_resolution)
        render_views(outdir, migrated_registry, migrated_resolution)
        generated = ["review_findings.json", "review_resolution.json", "structured_review.md", "reviewer_audit.md", "revision_plan.md"]
    return LifecycleResult(True, generated=generated, metrics={"mode": "apply" if apply else "dry-run", "from": [LEGACY_FINDINGS_SCHEMA, LEGACY_RESOLUTION_SCHEMA], "to": [FINDINGS_SCHEMA, RESOLUTION_SCHEMA]})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compile and verify Avereth review lifecycle contracts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("command", choices=("compile", "cycle", "validate", "render", "migrate"), nargs="?", default="validate")
    parser.add_argument("--review-dir", default="review_prompts")
    parser.add_argument("--manuscript")
    parser.add_argument("--cycle-id")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outdir = Path(args.output_dir).resolve()
    manuscript = Path(args.manuscript).resolve() if args.manuscript else default_manuscript(outdir).resolve()
    if args.command == "compile":
        result = compile_findings(
            outdir,
            (outdir / args.review_dir).resolve(),
            manuscript,
            write=args.write,
        )
    elif args.command == "cycle":
        if not args.cycle_id:
            result = LifecycleResult(False, ["cycle command requires --cycle-id"])
        else:
            result = compile_review_cycle(
                outdir,
                args.cycle_id,
                manuscript,
                write=args.write,
            )
    elif args.command == "migrate":
        result = migrate_review_lifecycle(outdir, apply=args.apply)
    elif args.command == "render":
        registry = _load_json(outdir / "review_findings.json")
        if registry is None:
            result = LifecycleResult(False, ["review_findings.json is missing or invalid"])
        else:
            generated = render_views(outdir, registry, _load_json(outdir / "review_resolution.json")) if args.write else []
            result = LifecycleResult(True, generated=generated)
    else:
        if args.write:
            registry = _load_json(outdir / "review_findings.json")
            if registry is not None:
                ensure_resolution_scaffold(outdir, registry)
                render_views(outdir, registry, _load_json(outdir / "review_resolution.json"))
        result = validate_lifecycle(outdir, manuscript)
    payload = {
        "ok": result.ok,
        "findings": result.findings,
        "generated": result.generated,
        "metrics": result.metrics,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
