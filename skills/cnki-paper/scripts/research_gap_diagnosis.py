#!/usr/bin/env python3
"""Parse and validate evidence-grounded research-gap diagnoses.

The contract deliberately lives inside the existing ``Gap Reality Check`` /
``knowledge_state.gap_authenticity`` text fields.  It does not add a seventh
taxonomy table, a new workflow state, or a semantic novelty score.  Machine
checks are limited to explicit structure and current ``SYN-*`` identities;
whether the diagnosed gap is intellectually consequential remains a review
judgment.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ANALYSIS_REL = Path("literature_analysis.json")

FIELD_ALIASES = {
    "status": {
        "status",
        "gap status",
        "diagnosis status",
        "状态",
        "空白状态",
        "诊断状态",
    },
    "primary_locus": {
        "primary locus",
        "gap locus",
        "primary gap locus",
        "locus",
        "主要落点",
        "空白落点",
        "主要空白落点",
    },
    "obstructions": {
        "obstruction",
        "obstructions",
        "why unresolved",
        "reason unresolved",
        "阻断原因",
        "无法下结论的原因",
        "未决原因",
    },
    "gap_claim": {
        "gap claim",
        "specific unknown",
        "gap statement",
        "空白命题",
        "具体未知",
        "未决命题",
    },
    "evidence_basis": {
        "evidence basis",
        "synthesis basis",
        "synthesis ids",
        "syn evidence",
        "证据基础",
        "综合依据",
        "syn证据",
    },
    "rival_explanations": {
        "rival explanations",
        "alternatives tested",
        "alternatives",
        "替代解释",
        "反替代检查",
        "替代项核验",
    },
    "research_responsibility": {
        "research responsibility",
        "design responsibility",
        "downstream responsibility",
        "研究责任",
        "设计责任",
        "下游责任",
    },
    "withdrawal_condition": {
        "withdrawal condition",
        "reclassification condition",
        "disconfirmation condition",
        "撤回条件",
        "改类条件",
        "收窄撤回条件",
    },
}

STATUS_ALIASES = {
    "author-stated": {"author-stated", "author stated", "作者自述"},
    "candidate": {"candidate", "provisional", "候选", "暂定"},
    "corroborated": {
        "corroborated",
        "evidence-grounded",
        "synthesis-corroborated",
        "经综合核验",
        "综合支持",
        "已核验",
    },
    "reclassified": {"reclassified", "改类", "重新分类"},
    "withdrawn": {"withdrawn", "撤回", "不成立"},
}

LOCUS_ALIASES = {
    "concept-measurement": {
        "concept-measurement",
        "concept/measurement",
        "conceptual",
        "concept",
        "概念测量",
        "概念/测量",
        "概念",
    },
    "theory-explanation": {
        "theory-explanation",
        "theory/explanation",
        "theoretical",
        "theory",
        "解释理论",
        "解释/理论",
        "理论",
    },
    "evidence": {"evidence", "empirical", "evidence/empirical", "证据", "实证"},
    "identification-method": {
        "identification-method",
        "identification/method",
        "methodological",
        "identification",
        "识别方法",
        "识别/方法",
        "方法",
    },
    "scope-population": {
        "scope-population",
        "scope/population/context",
        "population",
        "scope",
        "范围群体情境",
        "范围/群体/情境",
        "群体",
        "范围",
    },
    "action-practice": {
        "action-practice",
        "action/practice",
        "practical",
        "practice",
        "行动实践",
        "行动/实践",
        "实践",
    },
}

OBSTRUCTION_ALIASES = {
    "insufficient-or-imprecise": {
        "insufficient-or-imprecise",
        "insufficient/imprecise",
        "insufficient",
        "imprecise",
        "不足或不精确",
        "不足/不精确",
        "信息不足",
        "证据不足",
        "不精确",
    },
    "biased-coverage": {
        "biased-coverage",
        "biased coverage",
        "bias",
        "coverage bias",
        "覆盖偏倚",
        "证据偏倚",
        "偏倚",
    },
    "inconsistent-or-incomparable": {
        "inconsistent-or-incomparable",
        "inconsistent/incomparable",
        "inconsistent",
        "incomparable",
        "不一致或不可比",
        "不一致/不可比",
        "证据冲突",
        "不可比",
    },
    "misaligned-or-condition-changed": {
        "misaligned-or-condition-changed",
        "misaligned/condition-changed",
        "misaligned",
        "condition changed",
        "错配或条件变化",
        "错配/条件变化",
        "信息错配",
        "条件变化",
        "证据过时",
    },
}

GENERIC_VALUES = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "todo",
    "tbd",
    "placeholder",
    "待填",
    "待定",
    "暂无",
    "无",
}

SYNTHESIS_ID = re.compile(r"(?<![A-Za-z0-9_-])(SYN-[A-Za-z0-9][A-Za-z0-9._-]*)", re.IGNORECASE)
PAIR_SPLIT = re.compile(r"(?:<br\s*/?>|[；;\n\r]+)", re.IGNORECASE)


@dataclass(frozen=True)
class GapDiagnosis:
    status: str
    primary_locus: str
    obstructions: tuple[str, ...]
    gap_claim: str
    synthesis_ids: tuple[str, ...]
    rival_explanations: str
    research_responsibility: str
    withdrawal_condition: str

    def core_signature(self) -> tuple[str, tuple[str, ...], str, tuple[str, ...]]:
        """Return the problem identity that must survive question commitment."""
        return (
            self.primary_locus,
            self.obstructions,
            _comparison_text(self.gap_claim),
            self.synthesis_ids,
        )


def _normal(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip()


def _label_key(value: object) -> str:
    text = _normal(value).casefold()
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", text)


def _value_key(value: object) -> str:
    return _label_key(value)


def _comparison_text(value: object) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _normal(value).casefold())


def _alias_index(groups: dict[str, set[str]]) -> dict[str, str]:
    return {
        _value_key(alias): canonical
        for canonical, aliases in groups.items()
        for alias in aliases | {canonical}
    }


FIELD_INDEX = _alias_index(FIELD_ALIASES)
STATUS_INDEX = _alias_index(STATUS_ALIASES)
LOCUS_INDEX = _alias_index(LOCUS_ALIASES)
OBSTRUCTION_INDEX = _alias_index(OBSTRUCTION_ALIASES)


def _parse_pairs(text: str) -> tuple[dict[str, str], list[str]]:
    fields: dict[str, str] = {}
    issues: list[str] = []
    for fragment in PAIR_SPLIT.split(_normal(text)):
        fragment = fragment.strip()
        if not fragment:
            continue
        match = re.match(r"^\s*([^:=：=]{1,48})\s*[:：=]\s*(.*?)\s*$", fragment)
        if not match:
            issues.append(f"unlabelled fragment: {fragment[:48]}")
            continue
        label, value = match.groups()
        field = FIELD_INDEX.get(_label_key(label))
        if field is None:
            issues.append(f"unknown field label: {label.strip()}")
            continue
        if field in fields:
            issues.append(f"duplicate field: {field}")
            continue
        fields[field] = value.strip()
    return fields, issues


def _canonical_single(value: str, index: dict[str, str]) -> str | None:
    return index.get(_value_key(value))


def _canonical_many(value: str, index: dict[str, str]) -> tuple[str, ...] | None:
    whole = _canonical_single(value, index)
    if whole:
        return (whole,)
    parts = [
        item.strip()
        for item in re.split(r"\s*(?:,|，|、|\+|\band\b|以及|及)\s*", value, flags=re.IGNORECASE)
        if item.strip()
    ]
    canonical = [_canonical_single(item, index) for item in parts]
    if not parts or any(item is None for item in canonical):
        return None
    return tuple(dict.fromkeys(item for item in canonical if item))


def _substantive(value: str, minimum: int) -> bool:
    normalized = _comparison_text(value)
    return normalized not in {_comparison_text(item) for item in GENERIC_VALUES} and len(normalized) >= minimum


def synthesis_ids_from_analysis(base: Path) -> tuple[set[str], str | None]:
    """Load current synthesis identities without duplicating literature truth."""
    path = base / ANALYSIS_REL
    if not path.is_file():
        return set(), f"missing current synthesis registry: {ANALYSIS_REL.as_posix()}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return set(), f"cannot parse current synthesis registry: {exc}"
    syntheses = payload.get("syntheses") if isinstance(payload, dict) else None
    if not isinstance(syntheses, list):
        return set(), "literature_analysis.json has no syntheses list"
    identifiers = {
        _normal(item.get("synthesis_id")).upper()
        for item in syntheses
        if isinstance(item, dict) and _normal(item.get("synthesis_id"))
    }
    if not identifiers:
        return set(), "literature_analysis.json has no current SYN-* identity"
    return identifiers, None


def validate_gap_diagnosis(
    text: str,
    *,
    known_synthesis_ids: Iterable[str] | None = None,
    require_corroborated: bool = True,
    context: str = "gap diagnosis",
) -> tuple[GapDiagnosis | None, list[str]]:
    """Validate structure and identities, never the gap's intellectual value."""
    fields, parse_issues = _parse_pairs(text)
    issues = [f"{context}: {issue}" for issue in parse_issues]
    for field in FIELD_ALIASES:
        if not fields.get(field, "").strip():
            issues.append(f"{context}: missing field {field}")

    status = _canonical_single(fields.get("status", ""), STATUS_INDEX)
    if fields.get("status") and status is None:
        issues.append(f"{context}: unsupported status {fields['status']!r}")
    elif require_corroborated and status != "corroborated":
        issues.append(f"{context}: status must be corroborated before question commitment")

    locus = _canonical_single(fields.get("primary_locus", ""), LOCUS_INDEX)
    if fields.get("primary_locus") and locus is None:
        issues.append(
            f"{context}: primary_locus must name exactly one of concept-measurement, "
            "theory-explanation, evidence, identification-method, scope-population, or action-practice"
        )

    obstructions = _canonical_many(fields.get("obstructions", ""), OBSTRUCTION_INDEX)
    if fields.get("obstructions") and obstructions is None:
        issues.append(
            f"{context}: obstructions must use insufficiency/imprecision, biased coverage, "
            "inconsistency/incomparability, or mismatch/condition change"
        )

    for field, minimum in (
        ("gap_claim", 12),
        ("rival_explanations", 12),
        ("research_responsibility", 10),
        ("withdrawal_condition", 10),
    ):
        value = fields.get(field, "")
        if value and not _substantive(value, minimum):
            issues.append(f"{context}: {field} is placeholder-like or too underspecified")

    synthesis_ids = tuple(
        dict.fromkeys(match.group(1).upper() for match in SYNTHESIS_ID.finditer(fields.get("evidence_basis", "")))
    )
    if fields.get("evidence_basis") and not synthesis_ids:
        issues.append(f"{context}: evidence_basis must cite at least one SYN-* identity")
    if known_synthesis_ids is not None:
        known = {_normal(item).upper() for item in known_synthesis_ids}
        unknown = sorted(set(synthesis_ids) - known)
        if unknown:
            issues.append(f"{context}: unknown synthesis identities: {', '.join(unknown)}")

    diagnosis = None
    if status and locus and obstructions and synthesis_ids:
        diagnosis = GapDiagnosis(
            status=status,
            primary_locus=locus,
            obstructions=tuple(sorted(obstructions)),
            gap_claim=fields.get("gap_claim", "").strip(),
            synthesis_ids=tuple(sorted(synthesis_ids)),
            rival_explanations=fields.get("rival_explanations", "").strip(),
            research_responsibility=fields.get("research_responsibility", "").strip(),
            withdrawal_condition=fields.get("withdrawal_condition", "").strip(),
        )
    return diagnosis, list(dict.fromkeys(issues))


def extract_markdown_gap_field(text: str) -> str:
    """Return a Gap Diagnosis value from a simple Markdown Field/Content table."""
    aliases = {
        _label_key("Gap Diagnosis"),
        _label_key("Research Gap Diagnosis"),
        _label_key("研究空白诊断"),
        _label_key("空白诊断"),
    }
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip().replace(r"\|", "|") for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and _label_key(cells[0]) in aliases:
            return cells[1]
    return ""


def gap_core_matches(left: GapDiagnosis, right: GapDiagnosis) -> bool:
    return left.core_signature() == right.core_signature()
