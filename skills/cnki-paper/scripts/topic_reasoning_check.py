#!/usr/bin/env python3
"""Validate the empirical-theoretical, inductive-deductive topic-selection loop."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from research_quality_check import (
    classify_question_type,
    column,
    normalize,
    parse_otipr,
    question_design_matches,
    question_is_answerable,
    relation_strength,
    tables,
    weak,
)
from problem_orientation_check import check_orientation_contract, orientation_ids
from research_gap_diagnosis import (
    synthesis_ids_from_analysis,
    validate_gap_diagnosis,
)
from cnki_acquisition import (
    canonical_doi,
    canonical_token,
    canonical_url,
    content_verification_complete,
    is_cnki_url,
    is_international_academic_channel,
    is_international_content_channel,
    normalized_roles,
    resolve_publication_track,
)


LEDGER_COLUMNS = {
    "id": {"input id", "输入编号", "输入id"},
    "layer": {"source layer", "来源层", "输入层"},
    "content": {"content", "内容", "线索或理论"},
    "status": {"epistemic status", "认识状态", "证据状态"},
    "trace": {"trace", "溯源", "来源记录"},
}

CANDIDATE_COLUMNS = {
    "option": {"option", "选项", "方向"},
    "orientation_ids": {"problem orientation ids", "problem orientation id", "问题定向编号"},
    "problem_warrant": {"problem warrant", "why worth pursuing", "问题根据", "问题价值"},
    "input_ids": {"input ids", "输入编号", "输入ids"},
    "inductive": {"inductive pattern/anomaly", "归纳模式异常", "归纳模式或异常"},
    "prior_lens": {"prior lens disclosed", "先验视角", "理论先见"},
    "theory": {"theory & assumptions", "理论与前提", "理论及前提"},
    "deductive": {"deductive proposition", "演绎命题", "理论预期"},
    "confirm": {"confirming observation", "支持性观察", "预期观察"},
    "disconfirm": {"disconfirming observation", "反证观察", "否证观察"},
    "tension": {"empirical-theory tension", "经验理论张力", "经验与理论张力"},
    "revision": {"iteration/revision", "循环修订", "迭代修订"},
    "collision": {
        "collision trace",
        "collision search",
        "cnki collision trace",
        "international collision trace",
        "撞车检索",
        "撞车核验",
        "知网撞车核验",
        "国际撞车核验",
        "cnki撞车",
    },
    "feasibility": {"data feasibility", "材料可行性", "数据可行性"},
    "topic": {"provisional title", "provisional topic", "候选标题", "候选题", "暂定题目"},
    "title_contract": {
        "title function / claim boundary",
        "title function and claim boundary",
        "标题功能与主张边界",
        "标题功能主张边界",
    },
    "question": {"provisional research question", "research question", "候选研究问题", "暂定研究问题"},
    "question_type": {"primary question type", "question type", "研究问题主类型", "问题主类型"},
    "otipr": {"o-t-i-p-r", "otipr", "研究问题卡"},
    "boundary": {"inference boundary", "推断边界", "主张边界"},
    "gap_reality": {"gap reality check", "真实空白核验", "空白真实性", "研究空白真实性"},
    "outcome_design": {
        "outcome unit & comparison design",
        "结果单位与比较设计",
        "因变量与比较设计",
        "结果与比较设计",
    },
}

MULTI_OUTCOME_QUESTION = re.compile(
    r"有些.{0,40}有些|有的.{0,40}有的|为何有些|为什么有些|why\s+(?:do\s+)?some",
    re.IGNORECASE,
)
OUTCOME_MARKER = re.compile(
    r"单一结果|同一结果|结果变量|因变量|结果形式|制度形式|以.{0,24}为(?:结果|因变量)|"
    r"single\s+outcome|same\s+outcome|dependent\s+variable|outcome\s+(?:variable|form)",
    re.IGNORECASE,
)
COMPARISON_MARKER = re.compile(
    r"比较|对照|反事实|多案例|多类|不同路径|跨案例|核心案例.{0,20}对照|"
    r"compar|contrast|counterfactual|multiple\s+case|across\s+case",
    re.IGNORECASE,
)
NO_COMPARISON = re.compile(
    r"不(?:设|作|做|进行).{0,8}(?:比较|对照|反事实)|没有.{0,8}(?:比较|对照|反事实)|"
    r"无.{0,8}(?:比较|对照|反事实)|no\s+(?:comparison|comparator|counterfactual)|only\s+one\s+case",
    re.IGNORECASE,
)
TELEOLOGICAL_MARKER = re.compile(r"停留|跨越|落地|remain|leap|land", re.IGNORECASE)
TEMPORAL_EVIDENCE = re.compile(
    r"真实阶段|同一过程|时间顺序|时序|先后|阶段性证据|连续观察|跨时|"
    r"temporal|sequence|stage\s+evidence|longitudinal",
    re.IGNORECASE,
)

LAYER_LABELS = {
    "practice_experience": {
        "practiceexperience",
        "userexperience",
        "实践经验",
        "实践材料",
        "用户材料",
        "用户经验",
    },
    "memory_experience": {"memoryexperience", "记忆经验", "预训练经验"},
    "web_experience": {"webexperience", "网络经验", "网上经验", "网络材料"},
    "memory_theory": {"memorytheory", "记忆理论", "预训练理论"},
    "cnki_theory": {"cnkitheory", "知网理论", "cnki理论"},
    "international_theory": {
        "internationaltheory",
        "intltheory",
        "ssciliterature",
        "international literature",
        "国际理论",
        "外文理论",
        "国际文献",
        "外文文献",
    },
}


def classify_layer(value: str) -> str | None:
    candidate = normalize(value)
    for layer, aliases in LAYER_LABELS.items():
        if any(normalize(alias) in candidate or candidate in normalize(alias) for alias in aliases if candidate):
            return layer
    return None


def find_table(text: str, groups: dict[str, set[str]]) -> tuple[list[str], list[list[str]]] | None:
    for headers, rows in tables(text):
        if all(column(headers, aliases) is not None for aliases in groups.values()):
            return headers, rows
    return None


def required_theory_layers(publication_track: str) -> set[str]:
    if publication_track == "international-ssci":
        return {"international_theory"}
    if publication_track == "mixed":
        return {"cnki_theory", "international_theory"}
    return {"cnki_theory"}


def has_international_literature_identity(value: str) -> bool:
    """Require a scholarly identity, not a generic URL or the word 'international'."""
    return bool(
        re.search(
            r"\b10\.\d{4,9}/|doi\.org|openalex|scholar(?:\.google)?|crossref|"
            r"publisher|journal.?site|lawful.?oa|legal.?oa|institutional.?repositor|"
            r"出版社|期刊官网|合法.?oa|机构仓储|"
            r"\b(?:INTL[-_]?[A-Z]?|SRC[-_]?|S)[-_]?\d{2,}\b",
            value,
            re.IGNORECASE,
        )
    )


def load_literature_registry(base: Path) -> tuple[dict, str | None]:
    path = base / "reference_materials" / "literature_registry.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}, (
            "topic reasoning cannot resolve literature identities because "
            "reference_materials/literature_registry.json is missing or invalid"
        )
    if not isinstance(payload, dict):
        return {}, "topic reasoning literature registry must be a JSON object"
    sources = payload.get("sources")
    queries = payload.get("queries")
    if not isinstance(sources, list) or not isinstance(queries, list):
        return payload, "topic reasoning literature registry must contain source and query lists"
    return payload, None


def trace_has_token(trace: str, token: str) -> bool:
    if not token:
        return False
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9._-]){re.escape(token)}(?![A-Za-z0-9._-])",
            trace,
            re.IGNORECASE,
        )
    )


def trace_urls(trace: str) -> set[str]:
    return {
        canonical_url(raw.rstrip(".,，。；;"))
        for raw in re.findall(r"https?://[^\s<>|；;，,。]+", trace, re.IGNORECASE)
        if canonical_url(raw.rstrip(".,，。；;"))
    }


def trace_matches_source(trace: str, source: dict) -> bool:
    source_id = str(source.get("source_id") or "").strip()
    if trace_has_token(trace, source_id):
        return True
    doi = canonical_doi(source.get("doi")) or canonical_doi(source.get("url"))
    if doi and doi.lower() in trace.lower():
        return True
    urls = trace_urls(trace)
    verification = source.get("verification")
    if not isinstance(verification, dict):
        verification = {}
    source_urls = {
        canonical_url(source.get("url")),
        canonical_url(verification.get("content_url")),
    }
    return bool(urls.intersection(url for url in source_urls if url))


def trace_matches_query(trace: str, query: dict) -> bool:
    query_id = str(query.get("query_id") or "").strip()
    if trace_has_token(trace, query_id):
        return True
    query_url = canonical_url(query.get("url"))
    return bool(query_url and query_url in trace_urls(trace))


def registered_theory_trace(
    trace: str, sources: list[dict], ecosystem: str
) -> bool:
    for source in sources:
        if not isinstance(source, dict) or "theory" not in normalized_roles(source):
            continue
        channel = canonical_token(source.get("channel"))
        if ecosystem == "cnki":
            eligible_channel = channel == "cnki" and is_cnki_url(source.get("url"))
        else:
            eligible_channel = is_international_content_channel(channel)
        if (
            eligible_channel
            and content_verification_complete(source)
            and trace_matches_source(trace, source)
        ):
            return True
    return False


def registered_collision_trace(
    trace: str, sources: list[dict], queries: list[dict], ecosystem: str
) -> bool:
    for source in sources:
        if not isinstance(source, dict):
            continue
        channel = canonical_token(source.get("channel"))
        if ecosystem == "cnki":
            eligible_channel = channel == "cnki" and is_cnki_url(source.get("url"))
        else:
            eligible_channel = is_international_content_channel(channel)
        if (
            eligible_channel
            and content_verification_complete(source)
            and trace_matches_source(trace, source)
        ):
            return True
    for query in queries:
        if not isinstance(query, dict):
            continue
        channel = canonical_token(query.get("channel"))
        purpose = canonical_token(query.get("purpose"))
        if ecosystem == "cnki":
            eligible_channel = channel == "cnki" and is_cnki_url(query.get("url"))
        else:
            eligible_channel = is_international_academic_channel(channel)
        if (
            eligible_channel
            and purpose in {"collision", "sota"}
            and canonical_token(query.get("status")) == "complete"
            and trace_matches_query(trace, query)
        ):
            return True
    return False


def publication_track_for_artifact(path: Path) -> str:
    base = path.parent
    config = {}
    try:
        config = json.loads((base / "workflow_config.json").read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        config = {}
    try:
        registry = json.loads(
            (base / "reference_materials" / "literature_registry.json").read_text(
                encoding="utf-8-sig"
            )
        )
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        registry = {}
    return resolve_publication_track(
        config if isinstance(config, dict) else {},
        registry if isinstance(registry, dict) else {},
    )


def indexes(headers: list[str], groups: dict[str, set[str]]) -> dict[str, int]:
    result = {label: column(headers, aliases) for label, aliases in groups.items()}
    assert all(index is not None for index in result.values())
    return {label: int(index) for label, index in result.items()}


def candidate_records(path: Path) -> dict[str, dict[str, str]]:
    """Project stable candidate identities for the canonical research decision.

    The Markdown matrix remains the research-stage reasoning workspace.  This
    projection deliberately exposes only identities and question/title facts;
    the later selection or withdrawal decision belongs to
    ``research_decision.json``.
    """

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    table = find_table(text, CANDIDATE_COLUMNS)
    if table is None:
        return {}
    headers, rows = table
    idx = indexes(headers, CANDIDATE_COLUMNS)
    records: dict[str, dict[str, str]] = {}
    for row in rows:
        if not any(not weak(cell, minimum=1) for cell in row):
            continue
        option = row[idx["option"]].strip()
        if not option or option in records:
            continue
        records[option] = {
            "topic": row[idx["topic"]].strip(),
            "question": row[idx["question"]].strip(),
            "question_type": row[idx["question_type"]].strip(),
            "orientation_ids": row[idx["orientation_ids"]].strip(),
            "gap_reality": row[idx["gap_reality"]].strip(),
            "boundary": row[idx["boundary"]].strip(),
        }
    return records


def check_ledger(
    text: str,
    publication_track: str = "cnki-cn",
    registry_sources: list[dict] | None = None,
) -> tuple[list[str], dict[str, str]]:
    table = find_table(text, LEDGER_COLUMNS)
    if table is None:
        return ["topic matrix is missing the five-column input ledger"], {}
    headers, rows = table
    idx = indexes(headers, LEDGER_COLUMNS)
    issues: list[str] = []
    layers_by_id: dict[str, str] = {}
    counts = {layer: 0 for layer in LAYER_LABELS}
    registry_sources = registry_sources or []

    for number, row in enumerate(rows, start=1):
        input_id = row[idx["id"]].strip().upper()
        layer_text = row[idx["layer"]].strip()
        content = row[idx["content"]].strip()
        status = row[idx["status"]].strip()
        trace = row[idx["trace"]].strip()
        if weak(input_id, minimum=3) or not re.fullmatch(r"[A-Z]{2,3}\d{1,3}", input_id):
            issues.append(f"input ledger row {number} has an invalid Input ID")
            continue
        if input_id in layers_by_id:
            issues.append(f"input ledger repeats Input ID: {input_id}")
        layer = classify_layer(layer_text)
        if layer is None:
            issues.append(f"input ledger row {number} has an unknown source layer")
            continue
        layers_by_id[input_id] = layer
        counts[layer] += 1
        if weak(content, minimum=8):
            issues.append(f"input ledger row {number} has weak content")
        if weak(status, minimum=4) or weak(trace, minimum=4):
            issues.append(f"input ledger row {number} lacks epistemic status or trace")

        marked_verified = bool(re.search(r"(?:^|\b)verified(?:$|\b)|已核验|已验证|事实证据", status, re.IGNORECASE))
        marked_unverified = bool(re.search(r"unverified|hypothesis|candidate|待核|未核验|候选", status, re.IGNORECASE))
        if layer == "memory_experience":
            if not re.search(r"hypothesis|unverified|待核|未核验|假设", status, re.IGNORECASE) or (marked_verified and not marked_unverified):
                issues.append(f"{input_id} memory experience must remain hypothesis-only/unverified")
        elif layer == "practice_experience":
            if not re.search(r"user.?provided|situated|practice|context|用户提供|实践观察|情境材料", status, re.IGNORECASE):
                issues.append(f"{input_id} practice experience must disclose user-provided or situated-context status")
            if not re.search(r"user|message|prompt|local|field|interview|用户|题面|本轮|本地|访谈|田野|路径", trace, re.IGNORECASE):
                issues.append(f"{input_id} practice experience needs a user, task, fieldnote, interview, or local-path trace")
        elif layer == "memory_theory":
            if not re.search(r"theory.?candidate|candidate|候选|待核", status, re.IGNORECASE) or (marked_verified and not marked_unverified):
                issues.append(f"{input_id} memory theory must remain a theory candidate until source verification")
        elif layer == "web_experience":
            if not re.search(r"traceable|context|可追溯|情境材料", status, re.IGNORECASE):
                issues.append(f"{input_id} web experience must be marked traceable-context")
            if not re.search(r"https?://", trace, re.IGNORECASE) or not re.search(r"20\d{2}-\d{2}-\d{2}", trace):
                issues.append(f"{input_id} web experience needs a URL and ISO collection date")
        elif layer == "cnki_theory":
            if not re.search(r"verified|已核验|已验证", status, re.IGNORECASE):
                issues.append(f"{input_id} CNKI theory must be literature-verified")
            if not re.search(r"cnki|知网|\b[SC]\d+\b|https?://", trace, re.IGNORECASE):
                issues.append(f"{input_id} CNKI theory lacks a Source ID or CNKI trace")
            if not re.search(r"摘要|详情|全文|abstract|detail|pdf", trace, re.IGNORECASE) or not re.search(
                r"20\d{2}-\d{2}-\d{2}", trace
            ):
                issues.append(f"{input_id} CNKI theory must record verification level and ISO date")
            if not registered_theory_trace(trace, registry_sources, "cnki"):
                issues.append(
                    f"{input_id} CNKI theory trace does not resolve to a content-verified registered CNKI source with role=theory"
                )
        elif layer == "international_theory":
            if not re.search(r"verified|已核验|已验证", status, re.IGNORECASE):
                issues.append(
                    f"{input_id} international theory must be literature-verified"
                )
            if not has_international_literature_identity(trace):
                issues.append(
                    f"{input_id} international theory lacks a DOI/publisher/lawful-OA or Source ID trace"
                )
            if not re.search(
                r"摘要|详情|全文|abstract|detail|full.?text|pdf", trace, re.IGNORECASE
            ) or not re.search(r"20\d{2}-\d{2}-\d{2}", trace):
                issues.append(
                    f"{input_id} international theory must record verification level and ISO date"
                )
            if not registered_theory_trace(trace, registry_sources, "international"):
                issues.append(
                    f"{input_id} international theory trace does not resolve to a content-verified registered international source with role=theory"
                )

    if counts["practice_experience"] + counts["web_experience"] < 1:
        issues.append("input ledger has no traceable practice/web experience anchor")
    for layer in sorted(required_theory_layers(publication_track)):
        if counts[layer] < 1:
            label = "CNKI" if layer == "cnki_theory" else "international"
            issues.append(
                f"input ledger has no content-verified {label} theory anchor required by publication_track={publication_track}"
            )
    return issues, layers_by_id


def check_candidates(
    text: str,
    layers_by_id: dict[str, str],
    known_orientation_ids: set[str],
    publication_track: str = "cnki-cn",
    registry_sources: list[dict] | None = None,
    registry_queries: list[dict] | None = None,
    known_synthesis_ids: set[str] | None = None,
) -> list[str]:
    table = find_table(text, CANDIDATE_COLUMNS)
    if table is None:
        return ["topic matrix is missing the full inductive-deductive candidate table"]
    headers, rows = table
    idx = indexes(headers, CANDIDATE_COLUMNS)
    usable = [row for row in rows if any(not weak(cell, minimum=1) for cell in row)]
    issues: list[str] = []
    registry_sources = registry_sources or []
    registry_queries = registry_queries or []
    if not usable:
        issues.append("topic matrix has no usable candidate options")

    for number, row in enumerate(usable, start=1):
        option = row[idx["option"]].strip() or str(number)
        for label, position in idx.items():
            minimum = 2 if label in {"option", "question_type"} else (4 if label in {"input_ids", "orientation_ids"} else 8)
            if weak(row[position], minimum=minimum):
                issues.append(f"topic option {option} has weak or missing {label}")

        linked_orientations = orientation_ids(row[idx["orientation_ids"]])
        if not linked_orientations:
            issues.append(f"topic option {option} has no PO-* problem-orientation link")
        elif not linked_orientations.issubset(known_orientation_ids):
            issues.append(
                f"topic option {option} references unknown problem orientations: "
                + ", ".join(sorted(linked_orientations - known_orientation_ids))
            )

        used_ids = {item.upper() for item in re.findall(r"\b[A-Za-z]{2,3}\d{1,3}\b", row[idx["input_ids"]])}
        unknown = sorted(used_ids - set(layers_by_id))
        if unknown:
            issues.append(f"topic option {option} references unknown Input IDs: {', '.join(unknown)}")
        used_layers = {layers_by_id[item] for item in used_ids if item in layers_by_id}
        if not used_layers.intersection({"practice_experience", "web_experience"}):
            issues.append(f"topic option {option} has no traceable practice/web experience anchor")
        for required_layer in sorted(required_theory_layers(publication_track)):
            if required_layer not in used_layers:
                label = "CNKI" if required_layer == "cnki_theory" else "international"
                issues.append(
                    f"topic option {option} has no content-verified {label} theory anchor required by publication_track={publication_track}"
                )

        theory = normalize(row[idx["theory"]])
        deduction = normalize(row[idx["deductive"]])
        if theory and deduction == theory:
            issues.append(f"topic option {option} merely repeats its theory as the deductive proposition")
        if not re.search(r"如果|若|则|越.+越|导致|影响|提高|降低|预期|条件|if|when|lead|increase|decrease|expect", row[idx["deductive"]], re.IGNORECASE):
            issues.append(f"topic option {option} has no directional or conditional deductive proposition")
        if normalize(row[idx["confirm"]]) == normalize(row[idx["disconfirm"]]):
            issues.append(f"topic option {option} uses the same observation for confirmation and disconfirmation")
        if not re.search(r"冲突|张力|异常|不一致|解释不足|超出|边界|无法|反常|mismatch|tension|anomaly", row[idx["tension"]], re.IGNORECASE):
            issues.append(f"topic option {option} does not state a genuine empirical-theoretical tension")
        if not re.search(r"修正|收缩|边界|淘汰|改写|调整|新增|保留|revision|revise|narrow|drop", row[idx["revision"]], re.IGNORECASE):
            issues.append(f"topic option {option} does not record an actual iteration/revision decision")
        collision = row[idx["collision"]]
        has_cnki_collision = registered_collision_trace(
            collision, registry_sources, registry_queries, "cnki"
        )
        has_international_collision = registered_collision_trace(
            collision, registry_sources, registry_queries, "international"
        )
        has_date = bool(re.search(r"20\d{2}-\d{2}-\d{2}", collision))
        collision_ok = has_date and (
            has_cnki_collision
            if publication_track == "cnki-cn"
            else has_international_collision
            if publication_track == "international-ssci"
            else has_cnki_collision and has_international_collision
        )
        if not collision_ok:
            issues.append(
                f"topic option {option} lacks a dated collision trace for publication_track={publication_track}"
            )

        title_contract = row[idx["title_contract"]]
        if not re.search(
            r"question.?led|claim.?neutral|问题(?:导向|型)|主张中性|中性标题",
            title_contract,
            re.IGNORECASE,
        ):
            issues.append(
                f"topic option {option} title function must be question-led or claim-neutral before execution"
            )
        if re.search(
            r"claim.?led|finding.?led|result.?led|结论先行|发现先行|结果先行|主张先行",
            title_contract,
            re.IGNORECASE,
        ):
            issues.append(
                f"topic option {option} uses a result- or claim-led title before evidence exists"
            )
        if not re.search(
            r"不(?:预断|预设|承诺|宣称|越出)|不得|边界|仅|只|without|does not|no unverified|boundary",
            title_contract,
            re.IGNORECASE,
        ):
            issues.append(
                f"topic option {option} title contract does not state a pre-evidence claim boundary"
            )

        question_text = row[idx["question"]]
        if not question_is_answerable(question_text):
            issues.append(f"topic option {option} does not state an answerable provisional research question")
        question_type, question_type_matches = classify_question_type(row[idx["question_type"]])
        if not question_type_matches:
            issues.append(f"topic option {option} does not use one of the five research-question types")
        elif question_type is None:
            issues.append(f"topic option {option} names multiple research-question types without one primary type")

        otipr = parse_otipr(row[idx["otipr"]])
        for component in ("object", "time", "issue", "perspective", "relation"):
            if component not in otipr or weak(otipr.get(component, ""), minimum=2):
                issues.append(f"topic option {option} O-T-I-P-R card lacks a substantive {component}")
        relation = relation_strength(otipr.get("relation", "")) if otipr else None
        if otipr and relation is None:
            issues.append(f"topic option {option} must mark its relation as 强关系/strong or 弱关系/weak")
        if question_type in {"explanatory", "predictive"} and relation != "strong":
            issues.append(f"topic option {option} uses a {question_type} question without a strong relation")

        gap_reality = row[idx["gap_reality"]]
        _diagnosis, gap_issues = validate_gap_diagnosis(
            gap_reality,
            known_synthesis_ids=known_synthesis_ids,
            context=f"topic option {option} gap diagnosis",
        )
        issues.extend(gap_issues)

        topic_text = " ".join((row[idx["topic"]], question_text))
        outcome_design = row[idx["outcome_design"]]
        design_fit_text = " ".join(
            (
                question_text,
                row[idx["otipr"]],
                outcome_design,
                row[idx["feasibility"]],
                row[idx["boundary"]],
            )
        )
        if question_type and not question_design_matches(question_type, design_fit_text):
            issues.append(f"topic option {option} does not match its {question_type} answer task to a usable design")
        if (question_type in {"explanatory", "predictive"} or MULTI_OUTCOME_QUESTION.search(question_text)) and not OUTCOME_MARKER.search(outcome_design):
            issues.append(f"topic option {option} does not define one common outcome")
        if not re.search(r"单位|对象|案例|个案|场景|国家|地区|组织|政策过程|unit|case|object", outcome_design, re.IGNORECASE):
            issues.append(f"topic option {option} does not define the unit of analysis")
        if MULTI_OUTCOME_QUESTION.search(topic_text) and (
            not COMPARISON_MARKER.search(outcome_design) or NO_COMPARISON.search(outcome_design)
        ):
            issues.append(f"topic option {option} asks a some-versus-some question without a comparative design")
        if TELEOLOGICAL_MARKER.search(topic_text):
            temporal_basis = " ".join(
                row[idx[label]]
                for label in ("inductive", "revision", "boundary", "outcome_design")
            )
            if not TEMPORAL_EVIDENCE.search(temporal_basis):
                issues.append(
                    f"topic option {option} uses teleological stage language without evidence of a real temporal sequence"
                )
    return list(dict.fromkeys(issues))


def check_topic_reasoning(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [f"missing topic-reasoning artifact: {path.name}"]
    publication_track = publication_track_for_artifact(path)
    registry, registry_issue = load_literature_registry(path.parent)
    registry_sources = [
        source for source in registry.get("sources", []) if isinstance(source, dict)
    ]
    registry_queries = [
        query for query in registry.get("queries", []) if isinstance(query, dict)
    ]
    orientation_issues, known_orientations = check_orientation_contract(path.parent)
    known_synthesis_ids, synthesis_issue = synthesis_ids_from_analysis(path.parent)
    ledger_issues, layers = check_ledger(
        text, publication_track, registry_sources
    )
    issues = (
        ([registry_issue] if registry_issue else [])
        + orientation_issues
        + ledger_issues
        + check_candidates(
            text,
            layers,
            known_orientations,
            publication_track,
            registry_sources,
            registry_queries,
            known_synthesis_ids,
        )
        + ([synthesis_issue] if synthesis_issue else [])
    )
    decision_path = path.parent / "research_decision.json"
    if decision_path.is_file():
        try:
            from research_decision import validate_payload as validate_research_decision

            decision = json.loads(decision_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError, ImportError) as exc:
            issues.append(f"research-decision binding is invalid: {exc}")
        else:
            if not isinstance(decision, dict):
                issues.append("research-decision binding must be a JSON object")
            else:
                decision_result = validate_research_decision(
                    path.parent,
                    decision,
                    check_views=False,
                )
                issues.extend(
                    f"research-decision binding [{item.code}] {item.message}"
                    for item in decision_result.errors
                )
    return list(dict.fromkeys(issues))


def render_report(
    artifact: Path, issues: list[str], publication_track: str = "cnki-cn"
) -> str:
    lines = ["# Topic Induction-Deduction Check", "", f"Artifact: `{artifact.name}`", ""]
    if issues:
        lines.extend(["Status: FAIL", "", "## Blocking Issues"])
        lines.extend(f"- {issue}" for issue in issues)
        lines.extend(
            [
                "",
                f"Do not recommend a final topic until both reasoning channels, a traceable practice/web anchor, and the verified theory/collision anchors required by publication_track={publication_track} pass. Model-memory layers are optional.",
            ]
        )
    else:
        lines.extend(
            [
                "Status: PASS",
                "",
                f"Every topic option is linked to a problem orientation, a traceable practice/web anchor and verified literature required by publication_track={publication_track}; it also completes induction, deduction, falsification, revision, collision, real-gap, question-type, O-T-I-P-R, design, and pre-evidence title-contract checks. Model memory is optional and remains non-evidentiary.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Avereth workspace or topic_induction_deduction_matrix.md")
    parser.add_argument("--markdown", action="store_true", help="Compatibility flag; output is Markdown by default")
    parser.add_argument("--write", action="store_true", help="Write topic_reasoning_check.md beside the matrix")
    args = parser.parse_args()

    artifact = args.path if args.path.suffix.lower() == ".md" else args.path / "topic_induction_deduction_matrix.md"
    issues = check_topic_reasoning(artifact)
    report = render_report(artifact, issues, publication_track_for_artifact(artifact))
    print(report, end="")
    if args.write:
        (artifact.parent / "topic_reasoning_check.md").write_text(report, encoding="utf-8")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
