#!/usr/bin/env python3
"""Validate the problem-led orientation and its later commitments."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


STAGES = ("intake", "acquisition", "research", "design", "execution", "build", "audit", "output")
GENERIC = {"", "-", "--", "n/a", "na", "none", "null", "todo", "tbd", "placeholder", "待定", "无"}


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def meaningful(value: str, minimum: int = 4) -> bool:
    token = normalize(value)
    return len(token) >= minimum and token not in {normalize(item) for item in GENERIC}


def parse_tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    lines = text.splitlines()
    found: list[tuple[list[str], list[list[str]]]] = []
    index = 0
    while index + 1 < len(lines):
        if "|" not in lines[index] or "|" not in lines[index + 1]:
            index += 1
            continue
        separator = [cell.strip() for cell in lines[index + 1].strip().strip("|").split("|")]
        if not separator or not all(re.fullmatch(r":?-{3,}:?", cell) for cell in separator):
            index += 1
            continue
        headers = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
        rows: list[list[str]] = []
        cursor = index + 2
        while cursor < len(lines) and "|" in lines[cursor]:
            row = [cell.strip() for cell in lines[cursor].strip().strip("|").split("|")]
            if len(row) < len(headers):
                row.extend([""] * (len(headers) - len(row)))
            rows.append(row)
            cursor += 1
        found.append((headers, rows))
        index = cursor
    return found


def column(headers: list[str], aliases: set[str]) -> int | None:
    normalized_aliases = {normalize(alias) for alias in aliases}
    for index, header in enumerate(headers):
        candidate = normalize(header)
        if candidate in normalized_aliases:
            return index
    return None


def field_table(text: str, required_aliases: dict[str, set[str]]) -> tuple[dict[str, str], list[str]]:
    for headers, rows in parse_tables(text):
        field_index = column(headers, {"field", "字段", "项目"})
        content_index = column(headers, {"content", "内容"})
        if field_index is None or content_index is None:
            continue
        raw = {
            normalize(row[field_index]): row[content_index].strip()
            for row in rows
            if max(field_index, content_index) < len(row)
        }
        resolved: dict[str, str] = {}
        for label, aliases in required_aliases.items():
            resolved[label] = next(
                (
                    value
                    for key, value in raw.items()
                    if any(normalize(alias) in key for alias in aliases)
                ),
                "",
            )
        return resolved, []
    return {}, ["required Field/Content table is missing"]


ORIENTATION_FIELDS = {
    "orientation ids": {"orientation id", "problem orientation id", "问题定向编号", "问题原点编号"},
    "practical encounter": {"practical encounter", "实践遭遇", "实践触发", "现实触发"},
    "affected actors": {"affected actors", "相关行动者", "受影响者", "涉及主体"},
    "tension or unknown": {"tension or unknown", "张力或未知", "矛盾或未知", "核心困惑"},
    "why it matters": {"why it matters", "为何重要", "问题意义", "为什么值得研究"},
    "frame at risk": {
        "common-sense or imported frame at risk",
        "common sense or imported frame at risk",
        "待检验的常识或移植框架",
        "可能失效的常识或外来框架",
    },
    "revision trigger": {"what could change our mind", "什么会改变判断", "修订触发", "反证触发"},
    "origin": {"origin", "问题来源", "定向来源"},
    "epistemic status": {"epistemic status", "认识状态", "证据状态"},
    "researcher position": {"researcher position and access", "研究者位置与接近性", "研究者位置"},
    "method data role": {"method/data role", "method and data role", "方法数据角色", "方法与数据角色"},
    "confirmation source": {"confirmation source", "确认来源", "用户确认来源"},
}

CONFIRMATION_FIELDS = {
    "orientation ids": {"problem orientation ids", "problem orientation id", "问题定向编号", "问题原点编号"},
    "warrant": {"why the problem remains worth pursuing", "问题为何仍值得追问", "问题根据", "问题价值复核"},
    "nontrivial test": {"non-trivial answer test", "nontrivial answer test", "非平凡答案判准", "超越常识判准"},
    "working title": {"working title", "confirmed working title", "工作标题", "确认标题"},
    "title authority": {"title authority", "标题权限", "标题权属"},
    "title function": {"title function", "标题功能"},
    "title claim boundary": {"title claim boundary", "标题主张边界", "标题边界"},
    "title revision rule": {"title revision rule", "标题修订规则", "改题规则"},
}

EXECUTION_FIELDS = {
    "problem disposition": {
        "problem disposition after execution",
        "problem disposition",
        "执行后问题处置",
        "问题处置",
    },
    "reader prior": {"reader prior", "读者先验", "先验判断"},
    "reader posterior": {"reader posterior", "读者后验", "后验判断"},
    "displaced source": {"displaced source", "被迫更新的来源", "被更新的来源", "被替换的来源"},
    "title disposition": {
        "title disposition after execution",
        "post-execution title disposition",
        "执行后标题处置",
        "标题处置",
    },
    "evidence calibrated title": {
        "evidence-calibrated title",
        "evidence calibrated title",
        "证据校准标题",
        "执行后标题",
    },
    "title revision basis": {
        "title revision basis",
        "标题修订依据",
        "标题处置依据",
    },
    "title user decision": {
        "title user decision",
        "user title decision",
        "标题用户决定",
        "用户标题确认",
    },
}

TITLE_BASIS_ID_PATTERNS = {
    "execution": re.compile(
        r"(?<![A-Za-z0-9_.-])EXE[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
    "claim": re.compile(
        r"(?<![A-Za-z0-9_.-])(?:CLM|CLAIM)[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
    "evidence": re.compile(
        r"(?<![A-Za-z0-9_.-])(?:EVIDENCE|EVD|EV)[-_]?\d{1,4}(?![A-Za-z0-9_.-])",
        re.IGNORECASE,
    ),
}


def canonical_title_authority(value: str) -> str | None:
    if re.search(r"user.?fixed|用户固定|用户指定|原题锁定", value, re.IGNORECASE):
        return "user-fixed"
    if re.search(r"user.?approved.?working|用户确认(?:的)?工作标题|用户批准(?:的)?工作标题", value, re.IGNORECASE):
        return "user-approved-working"
    return None


def canonical_title_function(value: str) -> str | None:
    if re.search(r"question.?led|问题(?:导向|型)", value, re.IGNORECASE):
        return "question-led"
    if re.search(r"claim.?neutral|主张中性|中性标题", value, re.IGNORECASE):
        return "claim-neutral"
    return None


def canonical_title_revision_rule(value: str) -> str | None:
    if re.search(r"reconfirm.?if.?substantive|实质(?:性)?改题.*(?:重|再)确认|实质变更.*(?:重|再)确认", value, re.IGNORECASE):
        return "reconfirm-if-substantive"
    if re.search(r"(?:^|\b)locked\b|锁定|不得改题", value, re.IGNORECASE):
        return "locked"
    return None


def canonical_title_disposition(value: str) -> str | None:
    patterns = (
        ("withdraw", r"withdraw|撤回|弃题"),
        ("reopen", r"reopen|重开|重新确认"),
        ("narrow", r"narrow|收窄|缩题"),
        ("revise", r"revise|修改|修订|改题"),
        ("retain", r"retain|保留|维持"),
    )
    for label, pattern in patterns:
        if re.search(pattern, value, re.IGNORECASE):
            return label
    return None


def same_title(left: str, right: str) -> bool:
    return bool(normalize(left)) and normalize(left) == normalize(right)


def orientation_ids(value: str) -> set[str]:
    return {item.upper() for item in re.findall(r"\bPO[-_]?\d{1,3}\b", value, re.IGNORECASE)}


def check_orientation_contract(base: Path) -> tuple[list[str], set[str]]:
    path = base / "problem_orientation.md"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ["missing problem_orientation.md; establish a problem orientation before systematic acquisition"], set()
    values, issues = field_table(text, ORIENTATION_FIELDS)
    if issues:
        return ["problem_orientation.md " + issue for issue in issues], set()
    for label, value in values.items():
        if not meaningful(value, 2 if label == "orientation ids" else 4):
            issues.append(f"problem_orientation.md has no usable {label}")
    known_ids = orientation_ids(values.get("orientation ids", ""))
    if not known_ids:
        issues.append("problem_orientation.md must assign at least one stable PO-* Orientation ID")
    origin = values.get("origin", "")
    if origin and not re.search(
        r"user|practice|observation|source|hypothesis|用户|实践|观察|来源|假设",
        origin,
        re.IGNORECASE,
    ):
        issues.append("problem_orientation.md origin must disclose whether it is user-, practice-, source-, or hypothesis-led")
    status = values.get("epistemic status", "")
    if status and not re.search(
        r"provisional|hypothesis|source.?backed|user.?provided|暂定|假设|来源支持|用户提供",
        status,
        re.IGNORECASE,
    ):
        issues.append("problem_orientation.md must state a conservative epistemic status")
    role = values.get("method data role", "")
    if role and not re.search(
        r"feasibility.?only|not.?selected|subordinate|可行性.{0,6}(?:约束|判断)|尚未选择|服从问题|不作为.{0,8}(?:选题|问题).{0,4}依据",
        role,
        re.IGNORECASE,
    ):
        issues.append("method/data role must be feasibility-only or not-selected; tools cannot warrant the problem")
    if role and re.search(
        r"method|model|data|方法|模型|数据",
        role,
        re.IGNORECASE,
    ) and re.search(
        r"决定|生成|设定|驱动|define|determine|drive|generate",
        role,
        re.IGNORECASE,
    ):
        issues.append("problem_orientation.md makes a method, model, or available data determine the research problem")
    confirmation = values.get("confirmation source", "")
    if confirmation and not re.search(
        r"user|prompt|message|current task|用户|题面|本轮|确认|任务记录|会议",
        confirmation,
        re.IGNORECASE,
    ):
        issues.append("problem_orientation.md confirmation source is not user- or task-traceable")
    return list(dict.fromkeys(issues)), known_ids


def check_option_links(base: Path, known_ids: set[str]) -> list[str]:
    path = base / "motivation_options_after_research.md"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ["missing motivation_options_after_research.md for problem-orientation linkage"]
    for headers, rows in parse_tables(text):
        option_index = column(headers, {"option", "选项"})
        orientation_index = column(headers, {"problem orientation ids", "problem orientation id", "问题定向编号"})
        warrant_index = column(headers, {"problem warrant", "why worth pursuing", "问题根据", "问题价值"})
        if option_index is None or orientation_index is None or warrant_index is None:
            continue
        issues: list[str] = []
        usable = 0
        for number, row in enumerate(rows, start=1):
            if max(option_index, orientation_index, warrant_index) >= len(row):
                continue
            option = row[option_index].strip()
            if not meaningful(option, 1):
                continue
            usable += 1
            linked = orientation_ids(row[orientation_index])
            if not linked:
                issues.append(f"motivation option {option or number} has no PO-* problem-orientation link")
            elif not linked.issubset(known_ids):
                issues.append(
                    f"motivation option {option or number} references unknown problem orientations: "
                    + ", ".join(sorted(linked - known_ids))
                )
            if not meaningful(row[warrant_index], 8):
                issues.append(f"motivation option {option or number} has no substantive problem warrant")
        if not usable:
            issues.append("motivation options contain no usable problem-oriented choices")
        return issues
    return [
        "motivation_options_after_research.md must include Option, Problem Orientation IDs, and Problem Warrant columns"
    ]


def check_question_commitment(base: Path, known_ids: set[str]) -> list[str]:
    decision_path = base / "research_decision.json"
    decision_errors: list[str] = []
    decision_payload: dict | None = None
    if decision_path.is_file():
        try:
            from research_decision import validate_payload as validate_research_decision

            loaded = json.loads(decision_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, ImportError) as exc:
            decision_errors.append(f"research_decision.json is invalid: {exc}")
        else:
            if not isinstance(loaded, dict):
                decision_errors.append("research_decision.json must contain one object")
            else:
                decision_payload = loaded
                decision_result = validate_research_decision(base, loaded, check_views=False)
                decision_errors.extend(
                    f"research_decision.json [{item.code}] {item.message}"
                    for item in decision_result.errors
                )
    if decision_payload is not None and str(decision_payload.get("disposition") or "") in {
        "pending",
        "withdrawn",
    }:
        # A provisional/focused portfolio has no final commitment yet, and an
        # all-withdrawn project may terminate before one ever existed.
        return list(dict.fromkeys(decision_errors))

    path = base / "confirmed_motivation.md"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ["missing confirmed_motivation.md for the problem commitment"]
    values, issues = field_table(text, CONFIRMATION_FIELDS)
    if issues:
        return ["confirmed_motivation.md " + issue for issue in issues]
    for label, value in values.items():
        if not meaningful(value, 4):
            issues.append(f"confirmed_motivation.md has no usable {label}")
    linked = orientation_ids(values.get("orientation ids", ""))
    if not linked:
        issues.append("confirmed_motivation.md must retain at least one PO-* problem-orientation ID")
    elif not linked.issubset(known_ids):
        issues.append(
            "confirmed_motivation.md references unknown problem orientations: "
            + ", ".join(sorted(linked - known_ids))
        )
    authority = canonical_title_authority(values.get("title authority", ""))
    if authority is None:
        issues.append("title authority must be user-fixed or user-approved-working")
    title_function = canonical_title_function(values.get("title function", ""))
    if title_function is None:
        issues.append("title function must be question-led or claim-neutral at the problem commitment")
    if re.search(
        r"claim.?led|finding.?led|result.?led|结论先行|发现先行|结果先行|主张先行",
        values.get("title function", ""),
        re.IGNORECASE,
    ):
        issues.append("working title cannot be result- or claim-led before execution")
    boundary = values.get("title claim boundary", "")
    if boundary and not (
        re.search(r"不(?:预断|预设|承诺|宣称|越出)|不得|仅|只|without|does not|no unverified", boundary, re.IGNORECASE)
        and re.search(r"结果|发现|机制|概念|因果|证据|result|finding|mechanism|concept|causal|evidence", boundary, re.IGNORECASE)
    ):
        issues.append(
            "title claim boundary must say which unverified result, mechanism, concept, or causal claim the working title does not promise"
        )
    revision_rule = canonical_title_revision_rule(values.get("title revision rule", ""))
    if revision_rule is None:
        issues.append("title revision rule must be locked or reconfirm-if-substantive")
    if authority == "user-fixed" and revision_rule != "locked":
        issues.append("a user-fixed title must remain locked until the user explicitly unlocks it")
    issues.extend(decision_errors)
    return list(dict.fromkeys(issues))


def markdown_section(text: str, titles: set[str]) -> str:
    wanted = {normalize(title) for title in titles}
    lines = text.splitlines()
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line.strip())
        if not match:
            continue
        if start is None and normalize(match.group(2)) in wanted:
            start = index + 1
            level = len(match.group(1))
            continue
        if start is not None and len(match.group(1)) <= level:
            return "\n".join(lines[start:index])
    return "\n".join(lines[start:]) if start is not None else ""


NO_SOURCE_PATTERN = re.compile(r"(?:无|没有|无来源|none|na|n/a|null|nil)")


def same_judgement(prior: str, posterior: str) -> bool:
    """Report lexical overlap only; this is not a semantic contribution verdict."""

    left = normalize(prior)
    right = normalize(posterior)
    if not left or not right:
        return False
    return left == right or right in left


def load_authority_object(base: Path, relative: str) -> dict:
    try:
        payload = json.loads((base / relative).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"{relative} cannot be read: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{relative} must be one object")
    return payload


def source_reference_issues(base: Path, references: list[str]) -> list[str]:
    """Resolve identities to canonical source records and their saved content."""
    import hashlib
    from literature_analysis import all_sources, registry_binding_digest

    try:
        registry = load_authority_object(base, "reference_materials/literature_registry.json")
    except ValueError as exc:
        return [str(exc)]
    sources = all_sources(registry)
    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list) or len(sources) != len(raw_sources):
        return ["literature registry contains malformed or duplicate source identities"]
    aliases: dict[str, list[str]] = {}

    def key(value: str) -> str:
        return re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value.strip(), flags=re.IGNORECASE).rstrip(".,;，。；").casefold()

    for sid, source in sources.items():
        for value in (sid, source.get("doi"), source.get("url")):
            if value:
                aliases.setdefault(key(str(value)), []).append(sid)
    issues: list[str] = []
    resolved: set[str] = set()
    syntheses = None
    bound_source_ids: set[str] = set()
    for reference in references:
        if reference.upper().startswith("SYN-"):
            if syntheses is None:
                try:
                    analysis = load_authority_object(base, "literature_analysis.json")
                except ValueError as exc:
                    issues.append(str(exc))
                    syntheses = {}
                else:
                    binding = analysis.get("registry_binding") or {}
                    bound_ids = binding.get("source_ids") if isinstance(binding, dict) else None
                    if not isinstance(bound_ids, list) or any(not isinstance(sid, str) or sid not in sources for sid in bound_ids):
                        issues.append("synthesis source binding is missing or unresolved")
                    elif binding.get("digest") != registry_binding_digest(registry, bound_ids):
                        issues.append("synthesis source binding is stale")
                    else:
                        bound_source_ids = set(bound_ids)
                    raw_syntheses = analysis.get("syntheses")
                    if not isinstance(raw_syntheses, list) or any(not isinstance(item, dict) for item in raw_syntheses):
                        issues.append("syntheses must be a list of registered objects")
                        raw_syntheses = []
                    syntheses = {str(item.get("synthesis_id")): item for item in raw_syntheses}
                    if len(syntheses) != len(raw_syntheses):
                        issues.append("duplicate synthesis identities")
            synthesis = syntheses.get(reference)
            if not synthesis:
                issues.append(f"unresolved contribution source: {reference}")
                continue
            links = synthesis.get("source_links") or []
            if not isinstance(links, list) or not links:
                issues.append(f"{reference} has no registered source links")
                links = []
            for link in links:
                sid = str(link.get("source_id") or "") if isinstance(link, dict) else ""
                if sid not in sources:
                    issues.append(f"{reference} has unresolved source link {sid}")
                else:
                    if sid not in bound_source_ids:
                        issues.append(f"{reference} source {sid} is outside its registry binding")
                    resolved.add(sid)
        else:
            matches = set(aliases.get(key(reference), []))
            if len(matches) != 1:
                issues.append(f"unresolved or ambiguous contribution source: {reference}")
            resolved.update(matches)
    for sid in sorted(resolved):
        source = sources[sid]
        verification = source.get("verification")
        verification = verification if isinstance(verification, dict) else {}
        # A downloaded PDF ranks above bare content verification in the acquisition contract
        # (STATE_RANK); accept every state at or above content-verified so the two gates agree.
        try:
            from cnki_acquisition import STATE_RANK, canonical_token
            state_ok = STATE_RANK.get(canonical_token(source.get("state")), -1) >= STATE_RANK["content-verified"]
        except Exception:  # pragma: no cover - fallback to the strict token
            state_ok = source.get("state") == "content-verified"
        if source.get("citation_scope") != "final-source" or not state_ok:
            issues.append(f"{sid} is not a current content-verified final-source")
        if verification.get("retraction_status") in {"retracted", "withdrawn"}:
            issues.append(f"{sid} is retracted or withdrawn")
        relative = str(source.get("local_file") or "")
        digest = str(source.get("sha256") or source.get("file_sha256") or "").lower()
        path = (base / relative).resolve()
        if not relative or not path.is_relative_to(base.resolve()) or not path.is_file():
            issues.append(f"{sid} lacks a saved source artifact within the workspace")
        elif not re.fullmatch(r"[0-9a-f]{64}", digest) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            issues.append(f"{sid} source artifact hash is missing or stale")
    return list(dict.fromkeys(issues))


CONTRIBUTION_KINDS = {
    "explanation-revision", "boundary-refinement", "independent-replication",
    "negative-result", "description-measurement", "conceptual-normative",
}


def knowledge_update_issues(base: Path, values: dict[str, str]) -> list[str]:
    """Check evidence bindings; semantic assessment remains an explicit judgment."""
    from prose_packet import discover_execution_authority

    try:
        design = load_authority_object(base, "research_design.json")
        execution = load_authority_object(base, "method_execution.json")
    except ValueError as exc:
        return [str(exc) + "; contribution calibration requires an evidence-bounded knowledge update"]
    baseline = design.get("knowledge_baseline")
    update = execution.get("knowledge_update")
    if not isinstance(baseline, dict) or not isinstance(update, dict):
        return ["contribution calibration requires research_design.knowledge_baseline and method_execution.knowledge_update; missing historical priors must be marked retrospective or unknown, never backfilled as prospective"]
    issues: list[str] = []
    origin = str(baseline.get("origin") or "")
    if origin not in {"contemporaneous", "retrospective", "unknown"}:
        issues.append("knowledge_baseline.origin must be contemporaneous, retrospective, or unknown")
    prior = str(baseline.get("judgement") or "").strip()
    posterior = str(update.get("supported_update") or "").strip()
    if prior != values.get("reader prior") or posterior != values.get("reader posterior"):
        issues.append("contribution Markdown prior/posterior must equal the canonical JSON projection")
    for field in ("work_performed", "result_interpretation", "supported_update", "limitations"):
        if not meaningful(str(update.get(field) or ""), 8):
            issues.append(f"knowledge_update.{field} needs a substantive account")
    kind = str(update.get("kind") or "")
    if kind not in CONTRIBUTION_KINDS:
        issues.append("knowledge_update.kind is unsupported")
    if update.get("baseline_origin") != origin:
        issues.append("knowledge_update must preserve the declared baseline origin")
    refs = baseline.get("source_refs")
    if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or not ref for ref in refs):
        issues.append("knowledge_baseline.source_refs must list actual Source, SYN, DOI, or URL identities")
    else:
        issues.extend(source_reference_issues(base, refs))
    assessment = update.get("semantic_assessment")
    if not isinstance(assessment, dict) or assessment.get("status") != "supported" or not meaningful(str(assessment.get("rationale") or ""), 12):
        issues.append("knowledge update is restatement, uncertain, or lacks a supported semantic assessment; wording alone cannot establish gain")
    results = update.get("result_ids")
    claims = update.get("claim_ids")
    if (not isinstance(results, list) or not results or not isinstance(claims, list) or not claims
        or any(not isinstance(value, str) or not value for value in results + claims)
        or len(results) != len(set(results)) or len(claims) != len(set(claims))):
        issues.append("knowledge_update requires accepted result_ids and claim_ids")
        return issues
    authority = discover_execution_authority(base)
    if not isinstance(authority, dict) or authority.get("status") != "PASS":
        issues.append("method execution is not accepted; contribution language cannot override method failure")
        return issues
    eligible = authority.get("results") or {}
    use = "negative_or_null_report" if update.get("kind") == "negative-result" else "claim_support"
    linked_claims: set[str] = set()
    for rid in results:
        result = eligible.get(rid)
        if not isinstance(result, dict) or use not in result.get("allowed_uses", []):
            issues.append(f"knowledge update result {rid} is not accepted for {use}")
            continue
        linked_claims.update(cid for cid, uses in (result.get("claim_allowed_uses") or {}).items() if use in uses)
    if not set(claims).issubset(linked_claims):
        issues.append("knowledge_update claims are not supported by the referenced accepted results")
    if update.get("kind") == "negative-result":
        if str(update.get("null_interpretation")) not in {"inconclusive", "bounded-effect", "explanation-excluded"}:
            issues.append("negative results need null_interpretation; nonsignificance alone is not no-effect evidence")
        if update.get("null_interpretation") != "inconclusive" and not meaningful(str(update.get("null_basis") or ""), 20):
            issues.append("a bounded effect or excluded explanation requires an explicit precision/test basis")
    if update.get("kind") == "independent-replication":
        replication = update.get("replication") or {}
        if not isinstance(replication, dict) or replication.get("independent_material") is not True or not meaningful(str(replication.get("independence_basis") or ""), 20):
            issues.append("independent replication requires new independent material and an auditable independence basis; rerunning the same data is insufficient")
    if origin == "contemporaneous":
        from datetime import datetime
        try:
            recorded = datetime.fromisoformat(str(baseline.get("recorded_at") or "").replace("Z", "+00:00"))
            starts = [datetime.fromisoformat(str(action.get("started_at") or "").replace("Z", "+00:00")) for run in execution.get("runs", []) for action in run.get("actions", [])]
            if recorded.tzinfo is None or not starts or any(start.tzinfo is None or recorded > start for start in starts):
                raise ValueError("baseline follows exposure or execution")
        except (ValueError, TypeError):
            issues.append("contemporaneous baseline needs a timestamp before every recorded action; otherwise mark retrospective or unknown")
    return list(dict.fromkeys(issues))


def check_execution_reappraisal(base: Path) -> list[str]:
    path = base / "confirmed_contribution.md"
    try:
        text = path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ["missing confirmed_contribution.md for post-execution problem reappraisal"]
    section = markdown_section(
        text,
        {"Calibration Receipt", "Contribution Calibration", "贡献校准凭证", "贡献校准"},
    )
    values, issues = field_table(section, EXECUTION_FIELDS)
    if issues:
        return ["confirmed_contribution.md Calibration Receipt " + issue for issue in issues]
    for label, value in values.items():
        if not meaningful(value, 4):
            issues.append(f"Contribution Calibration Receipt has no usable {label}")
    disposition = values.get("problem disposition", "")
    prior = values.get("reader prior", "")
    gain = values.get("reader posterior", "")
    displaced = values.get("displaced source", "")
    problem_reopened_or_withdrawn = bool(re.search(r"reopen|withdraw|重开|重新确认|撤回", disposition, re.IGNORECASE))
    if not problem_reopened_or_withdrawn:
        issues.extend(knowledge_update_issues(base, values))
    if displaced and not NO_SOURCE_PATTERN.fullmatch(normalize(displaced)):
        identities = re.findall(r"https?://[^\s，。；、（）()<>|\u4e00-\u9fff]+|10\.\d{4,}/[^\s，。；、（）()<>|\u4e00-\u9fff]+|(?:CNKI|INTL|SRC|SYN)-[A-Za-z0-9][A-Za-z0-9._-]*|(?<![A-Za-z0-9])S\d+", displaced)
        if not identities:
            issues.append("displaced source must name a registered Source ID, DOI, URL, or SYN-* identity")
        else:
            issues.extend(source_reference_issues(base, identities))
    if disposition and not re.search(
        r"retain|refine|reopen|withdraw|保留|细化|修正|重开|重新确认|撤回",
        disposition,
        re.IGNORECASE,
    ):
        issues.append("problem disposition must explicitly retain, refine, reopen, or withdraw the confirmed problem")
    if re.search(r"reopen|withdraw|重开|重新确认|撤回", disposition, re.IGNORECASE):
        issues.append(
            "post-execution problem disposition requires reopening or withdrawal; stop build and return to research for renewed user confirmation"
        )
    explicit_no_gain = re.search(
        r"\bno (?:substantive |nontrivial )?gain\b|\bmerely repeats? common sense\b|"
        r"没有(?:实质|非平凡|认识)?增量|未超越常识|(?<!非)仅重复常识|只是常识(?:性)?结论|"
        r"(?<!非)只(?:是|能)?(?:复述|验证|证明)(?:了)?常识",
        gain,
        re.IGNORECASE,
    )
    if explicit_no_gain and not re.search(
        r"reopen|withdraw|重开|重新确认|撤回",
        disposition,
        re.IGNORECASE,
    ):
        issues.append(
            "post-execution record explicitly reports no beyond-common-sense gain; retain/refine cannot enter build, so reopen or withdraw the problem"
        )
    motivation_path = base / "confirmed_motivation.md"
    try:
        motivation_text = motivation_path.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        motivation_values = {}
    else:
        motivation_values, _motivation_issues = field_table(motivation_text, CONFIRMATION_FIELDS)

    working_title = motivation_values.get("working title", "")
    calibrated_title = values.get("evidence calibrated title", "")
    title_disposition = canonical_title_disposition(values.get("title disposition", ""))
    if title_disposition is None:
        issues.append("title disposition must explicitly retain, narrow, revise, reopen, or withdraw the working title")
    titles_match = same_title(working_title, calibrated_title)
    if title_disposition == "retain" and not titles_match:
        issues.append("title disposition is retain, but the evidence-calibrated title differs from the confirmed working title")
    if title_disposition in {"narrow", "revise"} and titles_match:
        issues.append(f"title disposition is {title_disposition}, but no title change is recorded")

    problem_reopened = bool(re.search(r"reopen|withdraw|重开|重新确认|撤回", disposition, re.IGNORECASE))
    if problem_reopened and title_disposition not in {"reopen", "withdraw"}:
        issues.append("a reopened or withdrawn problem must also reopen or withdraw the title contract")
    if title_disposition in {"reopen", "withdraw"}:
        issues.append(
            "post-execution title disposition requires reopening or withdrawal; stop build and return to research for renewed user confirmation"
        )

    revision_basis = values.get("title revision basis", "")
    if revision_basis and not re.search(
        r"evidence|result|finding|boundary|scope|证据|结果|发现|边界|范围",
        revision_basis,
        re.IGNORECASE,
    ):
        issues.append("title revision basis must be evidence-, result-, or boundary-based rather than method- or journal-led")
    if revision_basis:
        missing_title_ids = [
            identity
            for identity, pattern in TITLE_BASIS_ID_PATTERNS.items()
            if not pattern.search(revision_basis)
        ]
        if missing_title_ids:
            issues.append(
                "title revision basis lacks registered identities: "
                + ", ".join(missing_title_ids)
            )
    if revision_basis and re.search(
        r"method novelty|model novelty|journal attractiveness|技术新|方法新|模型新|期刊偏好|更易发表|吸引眼球",
        revision_basis,
        re.IGNORECASE,
    ):
        issues.append("method novelty or journal attractiveness cannot justify a substantive title revision")

    user_decision = values.get("title user decision", "")
    changed = bool(working_title and calibrated_title and not titles_match)
    if changed and not re.search(
        r"user.?confirm|user.?approv|approved by user|用户确认|用户同意|用户批准",
        user_decision,
        re.IGNORECASE,
    ):
        issues.append("a changed post-execution title requires explicit user confirmation")
    authority = canonical_title_authority(motivation_values.get("title authority", ""))
    revision_rule = canonical_title_revision_rule(motivation_values.get("title revision rule", ""))
    if changed and (authority == "user-fixed" or revision_rule == "locked") and not re.search(
        r"unlock|override|解锁|解除锁定|同意改题|同意变更|覆盖原题",
        user_decision,
        re.IGNORECASE,
    ):
        issues.append("the user-fixed or locked title changed without an explicit user unlock or override")
    if not changed and title_disposition == "retain" and not re.search(
        r"not.?required.?retained|retained|无需重确认|保留原题|用户确认保留",
        user_decision,
        re.IGNORECASE,
    ):
        issues.append("a retained title must record not-required-retained or a user decision")
    return issues


def validate_problem_orientation(base: Path, stage: str, *, task_profile: str = "full_paper") -> list[str]:
    if task_profile == "manuscript_audit":
        return []
    if stage not in STAGES:
        return [f"unsupported problem-orientation stage: {stage}"]
    issues, known_ids = check_orientation_contract(base)
    index = STAGES.index(stage)
    if index >= STAGES.index("research"):
        issues.extend(check_option_links(base, known_ids))
        issues.extend(check_question_commitment(base, known_ids))
    if index >= STAGES.index("execution"):
        issues.extend(check_execution_reappraisal(base))
    return list(dict.fromkeys(issues))


def render_report(base: Path, stage: str, issues: list[str]) -> str:
    lines = ["# Problem Orientation Check", "", f"Stage: `{stage}`", ""]
    if issues:
        lines.extend(["Status: FAIL", "", "## Blocking Issues", ""])
        lines.extend(f"- {issue}" for issue in issues)
    else:
        lines.extend(
            [
                "Status: PASS",
                "",
                "The workflow is anchored in a traceable problem orientation; methods and available data remain subordinate to the problem, and the title contract is calibrated from question commitment to post-execution evidence.",
            ]
        )
    if stage in {"build", "execution"}:
        try:
            baseline = load_authority_object(base, "research_design.json").get("knowledge_baseline") or {}
            update = load_authority_object(base, "method_execution.json").get("knowledge_update") or {}
        except ValueError:
            pass
        else:
            if isinstance(baseline, dict) and isinstance(update, dict) and same_judgement(str(baseline.get("judgement") or ""), str(update.get("supported_update") or "")):
                lines.extend(["", "Advisory: prior/posterior wording overlaps; review the supported change in scope or evidential confidence. Lexical overlap does not decide contribution."])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument(
        "--task-profile",
        choices=("full_paper", "topic_selection", "research_design", "manuscript_audit"),
        default="full_paper",
    )
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    base = args.outdir.resolve()
    issues = validate_problem_orientation(base, args.stage, task_profile=args.task_profile)
    report = render_report(base, args.stage, issues)
    print(report, end="")
    if args.write:
        (base / "problem_orientation_check.md").write_text(report, encoding="utf-8")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
