#!/usr/bin/env python3
"""Validate CNKI-Paper's dialogic argument map and identity links.

The checker deliberately judges only structure, registered identities,
cross-artifact consistency, and unresolved state. Fairness, voice, and
persuasiveness belong to isolated reviewers.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MAP_REL = Path("dialogic_argument_map.md")
REPORT_REL = Path("dialogic_argument_check.md")

GENERIC = {
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
UNRESOLVED = re.compile(
    r"(?:\bOPEN\b|\bFAIL\b|\bBLOCKED\b|\bTODO\b|\bTBD\b|\bVERIFY\b|"
    r"\bNEEDS[- ]?REVIEW\b|未解决|待修|待改|待核|失败|阻塞)",
    re.IGNORECASE,
)
PASS_STATUS = re.compile(
    r"^(?:PASS|CLOSED|RESOLVED|REVISED|JUSTIFIED|通过|已关闭|已解决|已修订|有据保留)$",
    re.IGNORECASE,
)

TARGET_TYPES = {
    "explicitdispute": "explicit-dispute",
    "明确争论": "explicit-dispute",
    "显性争论": "explicit-dispute",
    "commonassumption": "common-assumption",
    "共同假定": "common-assumption",
    "共享假定": "common-assumption",
    "literatureomission": "literature-omission",
    "文献遗漏": "literature-omission",
    "文献未解问题": "literature-omission",
}
RESPONSE_MODES = {
    "agree": "agree",
    "同意": "agree",
    "disagree": "disagree",
    "反对": "disagree",
    "agreeandqualify": "agree-and-qualify",
    "同意并限定": "agree-and-qualify",
    "有条件同意": "agree-and-qualify",
    "既同意又保留": "agree-and-qualify",
    "reframe": "reframe",
    "重构": "reframe",
    "重新界定": "reframe",
    "synthesize": "synthesize",
    "综合": "synthesize",
    "整合": "synthesize",
    "extend": "extend",
    "推进": "extend",
    "扩展": "extend",
}


@dataclass
class IdentitySets:
    sources: set[str] = field(default_factory=set)
    claims: set[str] = field(default_factory=set)
    evidence: set[str] = field(default_factory=set)
    designs: set[str] = field(default_factory=set)
    executions: set[str] = field(default_factory=set)


@dataclass
class CheckResult:
    map_path: Path
    issues: list[str] = field(default_factory=list)
    coverage: dict[str, int | str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def weak(value: Any, minimum: int = 4) -> bool:
    cleaned = normalize(value)
    return (
        not cleaned
        or cleaned in {normalize(item) for item in GENERIC}
        or cleaned.startswith("needsreview")
        or len(cleaned) < minimum
    )


def status_ok(value: str) -> bool:
    return bool(PASS_STATUS.fullmatch(value.strip())) and not UNRESOLVED.search(value)


def unresolved_fields(values: dict[str, str], *, exclude: set[str] | None = None) -> list[str]:
    """Return structured fields that still carry an explicit unresolved marker."""
    skipped = exclude or set()
    return [
        label
        for label, value in values.items()
        if label not in skipped and UNRESOLVED.search(value or "")
    ]


def split_row(line: str) -> list[str]:
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith(r"\|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def separator(line: str) -> bool:
    cells = split_row(line)
    return bool(cells) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells
    )


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    found: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index < len(lines) - 1:
        if lines[index].lstrip().startswith("|") and separator(lines[index + 1]):
            headers = split_row(lines[index])
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                if not separator(lines[index]):
                    row = split_row(lines[index])
                    if len(row) < len(headers):
                        row += [""] * (len(headers) - len(row))
                    if any(cell.strip() for cell in row):
                        rows.append(row[: len(headers)])
                index += 1
            found.append((headers, rows))
            continue
        index += 1
    return found


def column(headers: list[str], aliases: set[str]) -> int | None:
    targets = {normalize(alias) for alias in aliases}
    for index, header in enumerate(headers):
        candidate = normalize(header)
        if candidate in targets:
            return index
    return None


def find_table(
    text: str,
    columns: dict[str, set[str]],
) -> tuple[list[list[str]], dict[str, int]] | None:
    for headers, rows in tables(text):
        indexes = {name: column(headers, aliases) for name, aliases in columns.items()}
        if all(index is not None for index in indexes.values()):
            return rows, {
                name: int(index)
                for name, index in indexes.items()
                if index is not None
            }
    return None


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def collect_identities(base: Path) -> IdentitySets:
    identities = IdentitySets()
    registry = read_json(base / "reference_materials" / "literature_registry.json")
    for source in registry.get("sources") or []:
        if isinstance(source, dict) and str(source.get("source_id") or "").strip():
            identities.sources.add(str(source["source_id"]).strip())

    design = read_json(base / "research_design.json")
    for claim in design.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        if str(claim.get("status") or "").strip().lower() in {
            "inactive",
            "superseded",
            "withdrawn",
        }:
            continue
        if str(claim.get("id") or "").strip():
            identities.claims.add(str(claim["id"]).strip())
    for evidence in design.get("evidence") or []:
        if isinstance(evidence, dict) and str(evidence.get("id") or "").strip():
            identities.evidence.add(str(evidence["id"]).strip())
    for route in design.get("method_routes") or []:
        if isinstance(route, dict) and str(route.get("id") or "").strip():
            identities.designs.add(str(route["id"]).strip())
    old_design = design.get("design")
    if isinstance(old_design, dict) and str(old_design.get("id") or "").strip():
        identities.designs.add(str(old_design["id"]).strip())

    execution = read_json(base / "method_execution.json")
    for run in execution.get("runs") or []:
        if isinstance(run, dict) and str(run.get("id") or "").strip():
            identities.executions.add(str(run["id"]).strip())
    return identities


def ids_in_text(value: str, known: set[str]) -> set[str]:
    return {
        identifier
        for identifier in known
        if re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(identifier)}(?![A-Za-z0-9_.-])",
            value,
            re.IGNORECASE,
        )
    }


def id_like_tokens(value: str, kind: str) -> set[str]:
    patterns = {
        "source": r"(?<![A-Za-z0-9_.-])(?:(?:SRC|CNKI|WEB)[-_]?[A-Za-z0-9][A-Za-z0-9._-]*|S[-_]?\d[A-Za-z0-9._-]*)(?![A-Za-z0-9_.-])",
        "claim": r"(?<![A-Za-z0-9_.-])(?:CLM[-_]?[A-Za-z0-9][A-Za-z0-9._-]*|C\d[A-Za-z0-9._-]*)(?![A-Za-z0-9_.-])",
        "evidence": r"(?<![A-Za-z0-9_.-])(?:EVD[-_]?[A-Za-z0-9][A-Za-z0-9._-]*|EV[-_]?\d[A-Za-z0-9._-]*)(?![A-Za-z0-9_.-])",
        "execution": r"(?<![A-Za-z0-9_.-])EXE[-_]?[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9_.-])",
        "position": r"(?<![A-Za-z0-9_.-])POS[-_]?[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9_.-])",
    }
    return {
        match.group(0)
        for match in re.finditer(patterns[kind], value, re.IGNORECASE)
    }


def unknown_id_tokens(value: str, known: set[str], kind: str) -> set[str]:
    normalized_known = {normalize(item) for item in known}
    return {
        token
        for token in id_like_tokens(value, kind)
        if normalize(token) not in normalized_known
    }


def field_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for headers, rows in tables(text):
        field_index = column(headers, {"field", "字段", "项目"})
        content_index = column(headers, {"content", "内容"})
        if field_index is None or content_index is None:
            continue
        for row in rows:
            if field_index < len(row) and content_index < len(row):
                key = normalize(row[field_index])
                if key and key not in values:
                    values[key] = row[content_index].strip()
    return values


def field_value(values: dict[str, str], aliases: set[str]) -> str:
    targets = {normalize(alias) for alias in aliases}
    for key, value in values.items():
        if key in targets:
            return value
    candidates = [
        (min(abs(len(target) - len(key)) for target in targets), value)
        for key, value in values.items()
        if any(target in key or key in target for target in targets)
    ]
    return min(candidates, default=(0, ""))[1]


def compatible_text(left: str, right: str) -> bool:
    a, b = normalize(left), normalize(right)
    return bool(a and b and (a in b or b in a))


def canonical_target(value: str) -> str | None:
    return TARGET_TYPES.get(normalize(value))


def canonical_response(value: str) -> str | None:
    return RESPONSE_MODES.get(normalize(value))


CONTRACT_FIELDS = {
    "controlling dialogue": {
        "controlling dialogue/unknown",
        "controlling dispute/unknown",
        "主控争论或未知",
        "核心争论未知",
    },
    "target type": {
        "response target type",
        "dialogue target type",
        "回应对象类型",
        "对话对象类型",
    },
    "final position": {
        "final author position",
        "final position",
        "最终作者立场",
        "最终立场",
    },
    "response mode": {"response mode", "回应方式", "回应模式"},
    "central contribution": {
        "central contribution",
        "main contribution statement",
        "核心贡献",
        "中心贡献",
    },
    "claim ids": {
        "contribution claim ids",
        "active claim ids",
        "贡献主张编号",
        "主张编号",
    },
    "countervoice": {
        "strongest countervoice",
        "strongest objection",
        "最强反方",
        "最强异议",
    },
    "countervoice position": {
        "strongest countervoice position id",
        "countervoice position id",
        "最强反方立场编号",
    },
    "who cares": {"who cares", "谁会关心", "关切读者"},
    "so what": {"so what", "意义何在", "为何重要"},
    "missing voice": {
        "missing voice disposition",
        "missing voice",
        "遗漏声音处置",
        "遗漏声音",
    },
    "forbidden reading": {
        "forbidden reading",
        "claims to avoid",
        "禁止解读",
        "禁止主张",
    },
}

POSITION_COLUMNS = {
    "id": {"position id", "立场编号"},
    "summary": {"fair summary", "公允归纳", "公允摘要"},
    "sources": {"source ids", "来源编号", "source id"},
    "response": {"relation/response", "response mode", "关系回应", "回应方式"},
    "claims": {"claim ids", "主张编号"},
    "evidence": {"evidence ids", "证据编号"},
    "executions": {"execution ids", "执行编号"},
    "concession": {
        "concession/difference",
        "concession and difference",
        "让步差异",
        "承认与差异",
    },
    "boundary": {
        "counterevidence/boundary",
        "counterevidence and boundary",
        "反证边界",
        "反证与边界",
    },
    "status": {"status", "状态"},
}

VOICE_COLUMNS = {
    "unit": {"manuscript unit", "稿件单元", "章节单元"},
    "source_voice": {
        "prior/source voice",
        "prior or source voice",
        "前人来源声音",
        "前人或来源声音",
    },
    "attribution": {
        "attribution/position ids",
        "attribution and position ids",
        "归属立场编号",
        "归属与立场编号",
    },
    "author_move": {"author move", "作者动作", "作者回应"},
    "warrant": {
        "evidence/warrant",
        "evidence and warrant",
        "证据担保",
        "证据与担保",
    },
    "transition": {
        "transition/payoff",
        "transition and payoff",
        "承接读者所得",
        "承接与读者所得",
    },
    "status": {"status", "状态"},
}

REVISION_COLUMNS = {
    "discovery": {"discovery", "new discovery", "新发现", "发现"},
    "initial": {
        "initial claim/location",
        "initial claim and location",
        "原主张位置",
        "初始主张与位置",
    },
    "failure": {"why it failed", "失效原因", "为何不成立"},
    "revised": {"revised claim", "修订后主张", "新主张"},
    "recheck": {
        "source/evidence recheck",
        "source and evidence recheck",
        "来源证据复核",
        "来源与证据复核",
    },
    "propagation": {
        "propagated changes",
        "propagated locations",
        "传播修改",
        "联动修改",
    },
    "implication": {
        "unintended implication fixed",
        "unintended implication",
        "意外含义修复",
        "非预期含义修复",
    },
    "status": {"status", "状态"},
}

PROBLEM_ARC_COLUMNS = {
    "state": {"state id", "problem state id", "问题状态编号"},
    "before": {"live question", "problem state before", "此前问题状态"},
    "action": {"argument action", "transition type", "论证动作", "转化类型"},
    "after": {"updated problem", "problem state after", "更新后问题"},
    "authority": {"authority refs", "transition authority", "权威引用"},
    "branch": {"branch/disposition", "branch and disposition", "分支及处置"},
    "status": {"status", "状态"},
}


def validate_problem_arc_projection(base: Path, text: str, result: CheckResult) -> int:
    """Bind an optional dialogic projection to the canonical literature Problem Arc."""

    analysis = read_json(base / "literature_analysis.json")
    arc = analysis.get("problem_arc") if isinstance(analysis.get("problem_arc"), dict) else None
    projection = find_table(text, PROBLEM_ARC_COLUMNS)
    if arc is None:
        if projection is not None:
            result.issues.append(
                "AP.ARC.AUTHORITY_MISSING: Problem Arc Projection has no canonical literature_analysis.json problem_arc"
            )
        return 0
    states = [item for item in arc.get("states") or [] if isinstance(item, dict)]
    if projection is None:
        result.issues.append(
            "AP.ARC.PROJECTION_MISSING: dialogic_argument_map.md omits the canonical Problem Arc Projection"
        )
        return 0
    rows, indexes = projection
    expected = {
        str(item.get("state_id") or "").strip(): item
        for item in states
        if str(item.get("state_id") or "").strip()
    }
    seen: set[str] = set()
    for number, row in enumerate(rows, start=1):
        values = {
            label: row[index] if index < len(row) else ""
            for label, index in indexes.items()
        }
        state_id = values.get("state", "").strip()
        if state_id not in expected:
            result.issues.append(
                f"AP.ARC.AUTHORITY_MISSING: Problem Arc row {number} references unknown state {state_id or '<missing>'}"
            )
            continue
        if state_id in seen:
            result.issues.append(f"AP.ARC.ORDER_INVALID: Problem Arc repeats {state_id}")
            continue
        seen.add(state_id)
        state = expected[state_id]
        if not compatible_text(str(state.get("live_question") or ""), values.get("before", "")):
            result.issues.append(f"AP.ARC.PROJECTION_DRIFT: {state_id} live question differs from literature analysis")
        if normalize(state.get("transition_type")) != normalize(values.get("action")):
            result.issues.append(f"AP.ARC.PROJECTION_DRIFT: {state_id} argument action differs from literature analysis")
        if not compatible_text(str(state.get("updated_problem") or ""), values.get("after", "")):
            result.issues.append(f"AP.ARC.PROJECTION_DRIFT: {state_id} updated problem differs from literature analysis")
        authority_cell = values.get("authority", "")
        for authority in state.get("authority_refs") or []:
            if str(authority or "").strip() and not re.search(
                rf"(?<![A-Za-z0-9_.-]){re.escape(str(authority))}(?![A-Za-z0-9_.-])",
                authority_cell,
                re.IGNORECASE,
            ):
                result.issues.append(
                    f"AP.ARC.AUTHORITY_MISSING: {state_id} omits transition authority {authority}"
                )
        branch_id = str(state.get("branch_id") or "").strip()
        disposition = str(state.get("branch_disposition") or "").strip()
        branch_cell = values.get("branch", "")
        if branch_id and branch_id not in branch_cell:
            result.issues.append(f"AP.ARC.BRANCH_DROPPED: {state_id} omits branch {branch_id}")
        if disposition and not compatible_text(disposition, branch_cell):
            result.issues.append(f"AP.ARC.BRANCH_DROPPED: {state_id} omits its branch disposition")
        if not status_ok(values.get("status", "")):
            result.issues.append(f"Problem Arc row {number} has unresolved status")
    missing = sorted(set(expected) - seen)
    if missing:
        result.issues.append(
            "AP.ARC.PROJECTION_MISSING: Problem Arc Projection omits canonical states: "
            + ", ".join(missing)
        )
    return len(rows)


def validate_dialogic_argument(base: Path) -> CheckResult:
    base = base.resolve()
    path = base / MAP_REL
    result = CheckResult(map_path=path)
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        result.issues.append("missing dialogic_argument_map.md")
        return result
    if not re.search(
        r"Overall Status:\s*(?:\*\*)?PASS\b|总体状态[:：]\s*(?:\*\*)?通过",
        text,
        re.IGNORECASE,
    ):
        result.issues.append("dialogic_argument_map.md does not record Overall Status: PASS")

    identities = collect_identities(base)
    if not identities.sources:
        result.issues.append("literature registry exposes no Source IDs for the dialogic map")
    if not identities.claims:
        result.issues.append("research_design.json exposes no active Claim IDs for the dialogic map")
    if not identities.evidence:
        result.issues.append("research_design.json exposes no Evidence IDs for the dialogic map")
    if not identities.executions:
        result.issues.append("method_execution.json exposes no Execution IDs for the dialogic map")

    contract_values = field_values(text)
    contract: dict[str, str] = {}
    for label, aliases in CONTRACT_FIELDS.items():
        value = field_value(contract_values, aliases)
        contract[label] = value
        if weak(value, 3):
            result.issues.append(f"Dialogue Contract has no usable {label}")
    unresolved_contract = unresolved_fields(contract)
    if unresolved_contract:
        result.issues.append(
            "Dialogue Contract contains unresolved markers in: "
            + ", ".join(unresolved_contract)
        )
    target_type = canonical_target(contract.get("target type", ""))
    if target_type is None:
        result.issues.append("Dialogue Contract response target type is unsupported")
    response_mode = canonical_response(contract.get("response mode", ""))
    if response_mode is None:
        result.issues.append("Dialogue Contract response mode is unsupported")
    contract_claims = ids_in_text(contract.get("claim ids", ""), identities.claims)
    if not contract_claims:
        result.issues.append("Dialogue Contract has no registered contribution Claim ID")
    unknown_contract_claims = unknown_id_tokens(
        contract.get("claim ids", ""),
        identities.claims,
        "claim",
    )
    if unknown_contract_claims:
        result.issues.append(
            "Dialogue Contract references unknown Claim IDs: "
            + ", ".join(sorted(unknown_contract_claims))
        )

    position_table = find_table(text, POSITION_COLUMNS)
    position_ids: set[str] = set()
    mapped_sources: set[str] = set()
    mapped_claims: set[str] = set()
    mapped_evidence: set[str] = set()
    mapped_executions: set[str] = set()
    if position_table is None:
        result.issues.append("dialogic_argument_map.md is missing the Position–Response Map")
        position_rows: list[list[str]] = []
        position_indexes: dict[str, int] = {}
    else:
        position_rows, position_indexes = position_table
        for number, row in enumerate(position_rows, start=1):
            values = {
                label: row[index] if index < len(row) else ""
                for label, index in position_indexes.items()
            }
            empty = [
                label
                for label, value in values.items()
                if label != "status" and weak(value, 3)
            ]
            if empty:
                result.issues.append(
                    f"Position–Response row {number} has weak or empty fields: {', '.join(empty)}"
                )
            if not status_ok(values.get("status", "")):
                result.issues.append(
                    f"Position–Response row {number} has unresolved status"
                )
            unresolved_cells = unresolved_fields(values, exclude={"status"})
            if unresolved_cells:
                result.issues.append(
                    f"Position–Response row {number} contains unresolved markers in: "
                    + ", ".join(unresolved_cells)
                )
            position_id = values.get("id", "").strip()
            if not re.fullmatch(r"POS[-_]?\d{2,}", position_id, re.IGNORECASE):
                result.issues.append(
                    f"Position–Response row {number} has invalid Position ID {position_id!r}"
                )
            elif normalize(position_id) in {normalize(item) for item in position_ids}:
                result.issues.append(
                    f"Position–Response row {number} repeats Position ID {position_id}"
                )
            else:
                position_ids.add(position_id)
            source_links = ids_in_text(values.get("sources", ""), identities.sources)
            claim_links = ids_in_text(values.get("claims", ""), identities.claims)
            evidence_links = ids_in_text(values.get("evidence", ""), identities.evidence)
            execution_links = ids_in_text(
                values.get("executions", ""),
                identities.executions,
            )
            mapped_sources.update(source_links)
            mapped_claims.update(claim_links)
            mapped_evidence.update(evidence_links)
            mapped_executions.update(execution_links)
            for label, links in (
                ("Source", source_links),
                ("Claim", claim_links),
                ("Evidence", evidence_links),
                ("Execution", execution_links),
            ):
                if not links:
                    result.issues.append(
                        f"Position–Response row {number} has no registered {label} ID"
                    )
            for label, cell, known, kind in (
                ("Source", values.get("sources", ""), identities.sources, "source"),
                ("Claim", values.get("claims", ""), identities.claims, "claim"),
                ("Evidence", values.get("evidence", ""), identities.evidence, "evidence"),
                (
                    "Execution",
                    values.get("executions", ""),
                    identities.executions,
                    "execution",
                ),
            ):
                unknown = unknown_id_tokens(cell, known, kind)
                if unknown:
                    result.issues.append(
                        f"Position–Response row {number} references unknown {label} IDs: "
                        + ", ".join(sorted(unknown))
                    )
            if canonical_response(values.get("response", "")) is None:
                result.issues.append(
                    f"Position–Response row {number} has unsupported relation/response"
                )
    if not position_rows:
        result.issues.append("Position–Response Map has no usable rows")
    if target_type == "explicit-dispute" and len(position_ids) < 2:
        result.issues.append(
            "explicit-dispute requires at least two registered literature positions"
        )
    if target_type == "explicit-dispute" and len(mapped_sources) < 2:
        result.issues.append(
            "explicit-dispute requires at least two distinct registered Source IDs"
        )
    countervoice_position = contract.get("countervoice position", "").strip()
    if not any(
        normalize(countervoice_position) == normalize(position_id)
        for position_id in position_ids
    ):
        result.issues.append(
            "Dialogue Contract strongest countervoice Position ID does not resolve to the position map"
        )
    if contract_claims and not contract_claims.issubset(mapped_claims):
        result.issues.append(
            "Dialogue Contract contribution Claim IDs are not all represented in the position map"
        )

    voice_table = find_table(text, VOICE_COLUMNS)
    voice_rows: list[list[str]] = []
    if voice_table is None:
        result.issues.append("dialogic_argument_map.md is missing the Section Voice Map")
    else:
        voice_rows, voice_indexes = voice_table
        if len(voice_rows) < 4:
            result.issues.append(
                f"Section Voice Map has {len(voice_rows)} rows; expected at least 4 manuscript units"
            )
        for number, row in enumerate(voice_rows, start=1):
            values = {
                label: row[index] if index < len(row) else ""
                for label, index in voice_indexes.items()
            }
            empty = [
                label
                for label, value in values.items()
                if label != "status"
                and weak(value, 2 if label == "unit" else 3)
            ]
            if empty:
                result.issues.append(
                    f"Section Voice row {number} has weak or empty fields: {', '.join(empty)}"
                )
            if not status_ok(values.get("status", "")):
                result.issues.append(f"Section Voice row {number} has unresolved status")
            unresolved_cells = unresolved_fields(values, exclude={"status"})
            if unresolved_cells:
                result.issues.append(
                    f"Section Voice row {number} contains unresolved markers in: "
                    + ", ".join(unresolved_cells)
                )
            if not ids_in_text(values.get("attribution", ""), position_ids):
                result.issues.append(
                    f"Section Voice row {number} has no registered Position ID attribution"
                )
            unknown_positions = unknown_id_tokens(
                values.get("attribution", ""),
                position_ids,
                "position",
            )
            if unknown_positions:
                result.issues.append(
                    f"Section Voice row {number} references unknown Position IDs: "
                    + ", ".join(sorted(unknown_positions))
                )
            warrant = values.get("warrant", "")
            if not (
                ids_in_text(warrant, identities.sources)
                or ids_in_text(warrant, identities.claims)
                or ids_in_text(warrant, identities.evidence)
                or ids_in_text(warrant, identities.executions)
            ):
                result.issues.append(
                    f"Section Voice row {number} has no registered identity in Evidence/Warrant"
                )
            for label, known, kind in (
                ("Source", identities.sources, "source"),
                ("Claim", identities.claims, "claim"),
                ("Evidence", identities.evidence, "evidence"),
                ("Execution", identities.executions, "execution"),
            ):
                unknown = unknown_id_tokens(warrant, known, kind)
                if unknown:
                    result.issues.append(
                        f"Section Voice row {number} Evidence/Warrant references unknown "
                        f"{label} IDs: " + ", ".join(sorted(unknown))
                    )

    revision_table = find_table(text, REVISION_COLUMNS)
    revision_rows: list[list[str]] = []
    if revision_table is None:
        result.issues.append(
            "dialogic_argument_map.md is missing the Substantive Revision Delta"
        )
    else:
        revision_rows, revision_indexes = revision_table
        if not revision_rows:
            result.issues.append("Substantive Revision Delta has no usable row")
        for number, row in enumerate(revision_rows, start=1):
            values = {
                label: row[index] if index < len(row) else ""
                for label, index in revision_indexes.items()
            }
            empty = [
                label
                for label, value in values.items()
                if label != "status" and weak(value, 3)
            ]
            if empty:
                result.issues.append(
                    f"Substantive Revision row {number} has weak or empty fields: {', '.join(empty)}"
                )
            if not status_ok(values.get("status", "")):
                result.issues.append(
                    f"Substantive Revision row {number} has unresolved status"
                )
            unresolved_cells = unresolved_fields(values, exclude={"status"})
            if unresolved_cells:
                result.issues.append(
                    f"Substantive Revision row {number} contains unresolved markers in: "
                    + ", ".join(unresolved_cells)
                )
            if not (
                ids_in_text(values.get("recheck", ""), identities.sources)
                or ids_in_text(values.get("recheck", ""), identities.evidence)
            ):
                result.issues.append(
                    f"Substantive Revision row {number} has no registered Source/Evidence ID recheck"
                )
            for label, known, kind in (
                ("Source", identities.sources, "source"),
                ("Evidence", identities.evidence, "evidence"),
            ):
                unknown = unknown_id_tokens(values.get("recheck", ""), known, kind)
                if unknown:
                    result.issues.append(
                        f"Substantive Revision row {number} references unknown {label} IDs: "
                        + ", ".join(sorted(unknown))
                    )
            propagation = values.get("propagation", "")
            propagation_items = [
                item.strip()
                for item in re.split(r"[;；]", propagation)
                if not weak(item, 2)
            ]
            local_only = re.search(
                r"(?:local[- ]only|仅限本处|局部修改).{4,}",
                propagation,
                re.IGNORECASE,
            )
            if len(propagation_items) < 2 and not local_only:
                result.issues.append(
                    f"Substantive Revision row {number} does not register propagation to two locations "
                    "or justify a local-only change"
                )

    confirmed = field_values(
        (base / "confirmed_motivation.md").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        if (base / "confirmed_motivation.md").is_file()
        else ""
    )
    confirmed_target = field_value(
        confirmed,
        {
            "response target type",
            "dialogue target type",
            "回应对象类型",
            "对话对象类型",
        },
    )
    if canonical_target(confirmed_target) != target_type:
        result.issues.append(
            "Dialogue Contract response target type differs from confirmed_motivation.md"
        )
    confirmed_dialogue = field_value(
        confirmed,
        {
            "controlling dialogue/unknown",
            "controlling dispute/unknown",
            "主控争论或未知",
            "核心争论未知",
        },
    )
    if not compatible_text(confirmed_dialogue, contract.get("controlling dialogue", "")):
        result.issues.append(
            "Dialogue Contract controlling dialogue/unknown differs from confirmed_motivation.md"
        )
    confirmed_sources = ids_in_text(
        field_value(
            confirmed,
            {
                "position/source ids",
                "literature position/source ids",
                "文献立场及source ids",
                "立场来源编号",
            },
        ),
        identities.sources,
    )
    if not confirmed_sources or not confirmed_sources.issubset(mapped_sources):
        result.issues.append(
            "confirmed motivation Position/Source IDs are not represented in the position map"
        )

    contribution = field_values(
        (base / "confirmed_contribution.md").read_text(
            encoding="utf-8",
            errors="ignore",
        )
        if (base / "confirmed_contribution.md").is_file()
        else ""
    )
    contribution_claims = ids_in_text(
        field_value(
            contribution,
            {"active claim ids", "claim ids", "活动主张编号", "主张编号"},
        ),
        identities.claims,
    )
    if contribution_claims and contribution_claims != contract_claims:
        result.issues.append(
            "Dialogue Contract contribution Claim IDs differ from confirmed_contribution.md"
        )
    contribution_statement = field_value(
        contribution,
        {
            "main contribution statement",
            "central contribution",
            "核心贡献陈述",
            "核心贡献",
        },
    )
    if contribution_statement and not compatible_text(
        contribution_statement,
        contract.get("central contribution", ""),
    ):
        result.issues.append(
            "Dialogue Contract central contribution differs from confirmed_contribution.md"
        )

    problem_arc_rows = validate_problem_arc_projection(base, text, result)

    result.coverage = {
        "target_type": target_type or "invalid",
        "response_mode": response_mode or "invalid",
        "positions": len(position_rows),
        "mapped_sources": len(mapped_sources),
        "mapped_claims": len(mapped_claims),
        "mapped_evidence": len(mapped_evidence),
        "mapped_executions": len(mapped_executions),
        "voice_units": len(voice_rows),
        "revision_rows": len(revision_rows),
        "problem_arc_rows": problem_arc_rows,
    }
    result.issues = list(dict.fromkeys(result.issues))
    return result


def render_report(result: CheckResult) -> str:
    lines = [
        "# Dialogic Argument Check",
        "",
        f"Map: {result.map_path.name}",
        "",
        f"Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Coverage",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in result.coverage.items())
    if result.issues:
        lines.extend(["", "## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in result.issues)
        lines.extend(
            [
                "",
                "Resolve identities, missing fields, cross-artifact drift, and OPEN states. "
                "Fairness, voice, and persuasion still require isolated review.",
            ]
        )
    else:
        lines.extend(
            [
                "",
                "All registered positions, voices, claims, evidence, executions, and "
                "substantive-revision propagation are structurally closed. Qualitative "
                "fairness and persuasiveness remain reviewer judgments.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = validate_dialogic_argument(args.path)
    report = render_report(result)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "PASS" if result.ok else "FAIL",
                    "issues": result.issues,
                    "coverage": result.coverage,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(report, end="")
    if args.write:
        destination = args.path.resolve() / REPORT_REL
        destination.write_text(report, encoding="utf-8")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
