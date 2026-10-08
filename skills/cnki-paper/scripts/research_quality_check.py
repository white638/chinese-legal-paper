#!/usr/bin/env python3
"""Validate CNKI-Paper's knowledge-state, claim, and research-design alignment."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from research_gap_diagnosis import validate_gap_diagnosis


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

UNIVERSAL_FIELDS = {
    "known knowledge": {"已知命题与可信程度", "已知命题", "我们已经知道什么", "known knowledge"},
    "unknown or anomaly": {"未知争议或经验异常", "未知争议", "经验异常", "还要认识什么", "unknown anomaly"},
    "gap authenticity": {
        "空白真实性与低研究替代解释",
        "真实研究空白",
        "空白真实性",
        "gap authenticity",
    },
    "knowledge maturity": {"知识成熟度", "知识积累阶段", "knowledge maturity"},
    "research question": {"研究问题", "research question"},
    "question type": {"研究问题主类型", "问题主类型", "research question type", "primary question type"},
    "otipr": {
        "o-t-i-p-r 研究问题卡",
        "otipr 研究问题卡",
        "o-t-i-p-r",
        "otipr",
        "research question card",
    },
    "new knowledge": {"预期新增知识", "新增知识", "knowledge contribution", "new knowledge"},
    "claim type": {"主张类型", "知识主张类型", "claim type"},
    "theory and concepts": {"理论视角与核心概念", "理论与概念", "theory concepts"},
    "unit and comparability": {"分析单位对象与可比性", "分析单位与可比性", "unit comparability"},
    "scope conditions": {"范围条件与边界", "范围条件", "适用边界", "scope conditions"},
    "design fit": {"设计选择及匹配理由", "研究设计与匹配理由", "design fit"},
    "variation comparison counterfactual": {
        "变异比较或反事实",
        "变异与比较",
        "比较与反事实",
        "variation comparison counterfactual",
    },
    "alternatives": {"替代解释或反对论证", "替代解释", "反对论证", "alternatives"},
    "falsification": {"可证伪或修订条件", "可证伪条件", "修订条件", "falsification"},
    "inference ceiling": {"推断上限", "主张上限", "inference ceiling"},
    "limitations": {"设计局限及补救", "设计局限", "局限与补救", "limitations"},
}

BRANCH_FIELDS = {
    "descriptive": {
        "concept and classification": {"概念与分类规则", "概念分类规则", "concept classification"},
        "comparison and variation": {"比较基准与变异", "比较与变异", "comparison variation"},
    },
    "interpretive": {
        "actor meaning and context": {"行动者意义与语境", "行动者意义", "meaning context"},
        "researcher reflexivity": {"研究者位置与反身性", "研究者反身性", "researcher reflexivity"},
    },
    "causal_effect": {
        "cause result direction": {"原因结果与方向", "因与果及方向", "cause outcome direction"},
        "temporal order": {"时间顺序", "因果时序", "temporal order"},
        "counterfactual identification": {"反事实与识别", "反事实识别", "counterfactual identification"},
        "effect form heterogeneity": {"效应形式与异质性", "效应形式", "effect heterogeneity"},
    },
    "causal_mechanism": {
        "mechanism chain": {"机制链与可观察含义", "机制链", "mechanism chain"},
        "process evidence": {"过程证据", "过程观察", "process evidence"},
        "competing mechanism": {"竞争机制", "替代机制", "competing mechanism"},
    },
    "normative": {
        "normative premises": {"规范前提", "价值前提", "normative premises"},
        "reasoning chain": {"规范推理链", "推理链", "reasoning chain"},
        "strongest objection": {"最强反方论证", "反方论证", "strongest objection"},
        "institutional constraints": {"经验与制度约束", "制度约束", "empirical institutional constraints"},
    },
    "review_theory": {
        "corpus rules": {"语料范围与纳入规则", "纳入规则", "corpus inclusion"},
        "synthesis logic": {"综合逻辑", "综述逻辑", "synthesis logic"},
        "testable output": {"可检验命题或知识地图", "可检验命题", "知识地图", "testable proposition"},
    },
}

QUESTION_BRANCH_FIELDS = {
    "descriptive": {
        "descriptive increment and reconstruction boundary": {
            "描述增量与还原边界",
            "描述增量",
            "还原边界",
            "descriptive increment reconstruction boundary",
        },
    },
    "explanatory": {
        "relation and discriminating expectations": {
            "待解释关系与区分性预期",
            "待解释关系",
            "区分性预期",
            "relation discriminating expectations",
        },
    },
    "predictive": {
        "forecast target horizon and baseline": {
            "预测对象、时域与基线",
            "预测对象时域与基线",
            "预测时域与基线",
            "forecast target horizon baseline",
        },
        "uncertainty validation and updating": {
            "不确定性、验证与更新",
            "不确定性验证与更新",
            "预测验证与更新",
            "uncertainty validation updating",
        },
    },
    "operational": {
        "actor goal and constraints": {
            "行动主体、目标与约束",
            "行动主体目标与约束",
            "主体目标与约束",
            "actor goal constraints",
        },
        "levers feasibility and evaluation": {
            "行动杠杆、可行性与评价标准",
            "行动杠杆可行性与评价标准",
            "杠杆与评价标准",
            "levers feasibility evaluation",
        },
    },
    "normative": {},
}

CLAIM_PATTERNS = {
    "causal_mechanism": r"因果机制|机制解释|causal\s*mechanism",
    "causal_effect": r"因果效应|效应估计|causal\s*effect",
    "normative": r"规范论证|规范性论证|normative",
    "interpretive": r"诠释(?:/理解)?|解释性理解|interpretive|interpretation",
    "descriptive": r"描述(?:/概念)?|概念研究|类型学|分类研究|descriptive|conceptual",
    "review_theory": r"理论/综述|理论综述|文献综述|review|theoretical",
}

QUESTION_TYPE_PATTERNS = {
    "descriptive": r"描述性|descriptive",
    "explanatory": r"解释性|explanatory",
    "predictive": r"预测性|predictive|forecasting",
    "operational": r"操作性|实践指导|operational",
    "normative": r"规范性|normative",
}

QUESTION_TYPE_LABELS = {
    "描述性": "descriptive",
    "descriptive": "descriptive",
    "解释性": "explanatory",
    "explanatory": "explanatory",
    "预测性": "predictive",
    "predictive": "predictive",
    "forecasting": "predictive",
    "操作性": "operational",
    "实践指导": "operational",
    "operational": "operational",
    "规范性": "normative",
    "normative": "normative",
}

QUESTION_CLAIM_COMPATIBILITY = {
    "descriptive": {"descriptive", "interpretive", "review_theory"},
    "explanatory": {"causal_effect", "causal_mechanism", "interpretive", "review_theory"},
    "predictive": {"descriptive", "causal_effect", "causal_mechanism", "review_theory"},
    "operational": {"causal_effect", "causal_mechanism", "normative", "review_theory"},
    "normative": {"normative"},
}

QUESTION_TASK_PATTERNS = {
    "descriptive": re.compile(r"还原|重建|分类|事实|演变|呈现|概念边界|描述增量|reconstruct|classif|describe", re.IGNORECASE),
    "explanatory": re.compile(r"原因|机制|影响|关系|条件|导致|解释|竞争|cause|mechanism|affect|explain", re.IGNORECASE),
    "predictive": re.compile(r"未来|预测|时域|基线|情景|概率|不确定|校验|验证|更新|forecast|horizon|baseline|uncertaint", re.IGNORECASE),
    "operational": re.compile(r"行动主体|目标|约束|杠杆|方案|措施|路径|改善|提升|评价标准|可行性|actor|goal|constraint|intervention|evaluation", re.IGNORECASE),
    "normative": re.compile(r"应该|应当|应否|正当|原则|权利|责任|价值|规范前提|反方|ought|should|justice|right", re.IGNORECASE),
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


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", value.lower())


def classify_question_type(value: str) -> tuple[str | None, list[str]]:
    matches = [
        family
        for family, pattern in QUESTION_TYPE_PATTERNS.items()
        if re.search(pattern, value, re.IGNORECASE)
    ]
    matches = list(dict.fromkeys(matches))
    primary_match = re.search(
        r"(?:主类型|primary(?:\s+question)?\s+type)\s*[:=：]?\s*"
        r"(描述性|解释性|预测性|操作性|实践指导|规范性|descriptive|explanatory|predictive|forecasting|operational|normative)",
        value,
        re.IGNORECASE,
    )
    if primary_match:
        primary = QUESTION_TYPE_LABELS.get(primary_match.group(1).lower())
        return primary, matches
    return (matches[0] if len(matches) == 1 else None), matches


def parse_otipr(value: str) -> dict[str, str]:
    aliases = {
        "o": "object",
        "object": "object",
        "对象": "object",
        "t": "time",
        "time": "time",
        "时间": "time",
        "i": "issue",
        "issue": "issue",
        "领域": "issue",
        "问题领域": "issue",
        "p": "perspective",
        "perspective": "perspective",
        "视角": "perspective",
        "r": "relation",
        "relation": "relation",
        "关系": "relation",
    }
    cleaned = re.sub(r"<br\s*/?>", "；", value, flags=re.IGNORECASE)
    result: dict[str, str] = {}
    for segment in re.split(r"[；;|\n]+", cleaned):
        match = re.match(
            r"\s*(O|Object|对象|T|Time|时间|I|Issue|领域|问题领域|P|Perspective|视角|R|Relation|关系)"
            r"\s*[:=：]\s*(.+?)\s*$",
            segment,
            re.IGNORECASE,
        )
        if not match:
            continue
        label = aliases.get(match.group(1).lower(), aliases.get(match.group(1)))
        if label:
            result[label] = match.group(2).strip()
    return result


def relation_strength(value: str) -> str | None:
    strong = bool(re.search(r"强关系|strong\s*(?:relation|relationship)|(?:^|[：:])\s*强(?:[：:]|$)", value, re.IGNORECASE))
    weak_relation = bool(re.search(r"弱关系|weak\s*(?:relation|relationship)|(?:^|[：:])\s*弱(?:[：:]|$)", value, re.IGNORECASE))
    if strong == weak_relation:
        return None
    return "strong" if strong else "weak"


def question_is_answerable(value: str) -> bool:
    if weak(value, minimum=6):
        return False
    return bool(
        re.search(
            r"[？?]|为什么|为何|何以|如何|什么|是否|应否|应该|应当|将.{0,20}(?:怎样|如何|何种)|"
            r"哪(?:些|种|个)|谁|多大|何种程度|在何种条件|why|what|how|whether|should|will",
            value,
            re.IGNORECASE,
        )
    )


def question_design_matches(question_type: str, value: str) -> bool:
    pattern = QUESTION_TASK_PATTERNS.get(question_type)
    return bool(pattern and pattern.search(value))


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
            current.append(char)
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
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


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
    for index, header in enumerate(headers):
        candidate = normalize(header)
        if any(target in candidate or candidate in target for target in targets if target and candidate):
            return index
    return None


def find_matrix(text: str) -> tuple[list[str], list[list[str]]] | None:
    for headers, rows in tables(text):
        if (
            column(headers, {"字段", "field", "项目"}) is not None
            and column(headers, {"内容", "content"}) is not None
            and column(headers, {"证据理由", "证据/理由", "evidence reason", "basis"}) is not None
        ):
            return headers, rows
    return None


def weak(value: str, *, minimum: int = 4) -> bool:
    cleaned = normalize(value)
    generic = {normalize(item) for item in GENERIC}
    return not cleaned or cleaned in generic or len(cleaned) < minimum


def field_row(rows: list[list[str]], field_index: int, aliases: set[str]) -> list[str] | None:
    targets = {normalize(alias) for alias in aliases}
    exact = [row for row in rows if field_index < len(row) and normalize(row[field_index]) in targets]
    if exact:
        return exact[0]
    candidates = []
    for row in rows:
        if field_index >= len(row):
            continue
        field = normalize(row[field_index])
        if any(target in field or field in target for target in targets if target and field):
            candidates.append(row)
    return candidates[0] if candidates else None


def claim_families(value: str) -> list[str]:
    return [family for family, pattern in CLAIM_PATTERNS.items() if re.search(pattern, value, re.IGNORECASE)]


def maturity(value: str) -> str | None:
    if re.search(r"探索期|探索阶段|explor", value, re.IGNORECASE):
        return "exploratory"
    if re.search(r"发展期|发展阶段|积累期|积累阶段|develop", value, re.IGNORECASE):
        return "developing"
    if re.search(r"成熟期|成熟阶段|mature", value, re.IGNORECASE):
        return "mature"
    return None


def check_protocol(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [f"missing knowledge-design artifact: {path.name}"]
    matrix = find_matrix(text)
    if matrix is None:
        return ["knowledge_design_matrix.md must contain a Field/Content/Evidence-Reason table"]

    headers, rows = matrix
    field_index = column(headers, {"字段", "field", "项目"})
    content_index = column(headers, {"内容", "content"})
    evidence_index = column(headers, {"证据理由", "证据/理由", "evidence reason", "basis"})
    assert field_index is not None and content_index is not None and evidence_index is not None

    issues: list[str] = []
    located: dict[str, list[str]] = {}
    for label, aliases in UNIVERSAL_FIELDS.items():
        row = field_row(rows, field_index, aliases)
        if row is None:
            issues.append(f"knowledge-design matrix is missing universal field: {label}")
            continue
        located[label] = row
        content = row[content_index] if content_index < len(row) else ""
        evidence = row[evidence_index] if evidence_index < len(row) else ""
        minimum = 2 if label in {"knowledge maturity", "claim type", "question type"} else 6
        if weak(content, minimum=minimum):
            issues.append(f"knowledge-design field has weak or placeholder content: {label}")
        if weak(evidence, minimum=3):
            issues.append(f"knowledge-design field has no usable evidence/reason: {label}")

    for label in ("known knowledge", "unknown or anomaly", "gap authenticity"):
        row = located.get(label)
        if row:
            evidence = row[evidence_index]
            if not re.search(r"\b[SC]\d+\b|https?://|cnki|知网|[\w.-]+\.md\b", evidence, re.IGNORECASE):
                issues.append(f"{label} must cite a source ID, CNKI/URL trace, or named .md artifact")

    gap_row = located.get("gap authenticity")
    if gap_row:
        gap_text = gap_row[content_index]
        # Frozen v1 matrices remain readable diagnostic views.  Current topic
        # and v2/v3 design gates require the explicit two-axis contract; this
        # legacy checker validates it when present but does not pretend it can
        # reconstruct missing labels from old prose.
        if re.search(
            r"(?:status|gap\s*status|diagnosis\s*status|状态|空白状态|诊断状态)\s*[:：=]",
            gap_text,
            re.IGNORECASE,
        ):
            _diagnosis, gap_issues = validate_gap_diagnosis(
                gap_text,
                context="gap authenticity",
            )
            issues.extend(gap_issues)

    maturity_row = located.get("knowledge maturity")
    maturity_value = maturity(maturity_row[content_index]) if maturity_row else None
    if maturity_row and maturity_value is None:
        issues.append("knowledge maturity must be explicitly classified as 探索期, 发展期, or 成熟期")

    question_type_row = located.get("question type")
    question_type_value = question_type_row[content_index] if question_type_row else ""
    question_type, question_type_matches = classify_question_type(question_type_value)
    if question_type_row and not question_type_matches:
        issues.append("research question type must use one of the five question families")
    elif question_type_row and question_type is None:
        issues.append("research question type names multiple families without identifying one primary type")

    otipr_row = located.get("otipr")
    otipr = parse_otipr(otipr_row[content_index]) if otipr_row else {}
    for component in ("object", "time", "issue", "perspective", "relation"):
        if component not in otipr or weak(otipr.get(component, ""), minimum=2):
            issues.append(f"O-T-I-P-R research-question card is missing a substantive {component}")
    relation = relation_strength(otipr.get("relation", "")) if otipr else None
    if otipr and relation is None:
        issues.append("O-T-I-P-R relation must be explicitly marked 强关系/strong or 弱关系/weak")
    if question_type in {"explanatory", "predictive"} and relation != "strong":
        issues.append(f"{question_type} research question must declare a strong relation")

    claim_row = located.get("claim type")
    families = claim_families(claim_row[content_index]) if claim_row else []
    if claim_row and not families:
        issues.append("claim type must use one of the six protocol families")
    if len(families) > 1 and not re.search(r"主|primary", claim_row[content_index], re.IGNORECASE):
        issues.append("claim type names multiple families without identifying one primary family")
    family = families[0] if families else None
    if question_type and family and family not in QUESTION_CLAIM_COMPATIBILITY[question_type]:
        issues.append(f"{question_type} research question is not aligned with the selected {family} claim family")

    if family:
        for label, aliases in BRANCH_FIELDS[family].items():
            row = field_row(rows, field_index, aliases)
            if row is None:
                issues.append(f"{family} claim is missing branch field: {label}")
                continue
            content = row[content_index] if content_index < len(row) else ""
            evidence = row[evidence_index] if evidence_index < len(row) else ""
            if weak(content, minimum=6):
                issues.append(f"{family} branch field has weak content: {label}")
            if weak(evidence, minimum=3):
                issues.append(f"{family} branch field has no usable evidence/reason: {label}")

    question_branch_text: list[str] = []
    if question_type:
        for label, aliases in QUESTION_BRANCH_FIELDS[question_type].items():
            row = field_row(rows, field_index, aliases)
            if row is None:
                issues.append(f"{question_type} research question is missing question-type field: {label}")
                continue
            content = row[content_index] if content_index < len(row) else ""
            evidence = row[evidence_index] if evidence_index < len(row) else ""
            question_branch_text.extend((content, evidence))
            if weak(content, minimum=6):
                issues.append(f"{question_type} question-type field has weak content: {label}")
            if weak(evidence, minimum=3):
                issues.append(f"{question_type} question-type field has no usable evidence/reason: {label}")

    design_row = located.get("design fit")
    variation_row = located.get("variation comparison counterfactual")
    unit_row = located.get("unit and comparability")
    design_text = " ".join(
        row[index]
        for row in (design_row, variation_row)
        if row
        for index in (content_index, evidence_index)
        if index < len(row)
    )
    if family == "causal_effect" and maturity_value == "exploratory":
        if not re.search(r"先导|预研究|分阶段|先.{0,6}(描述|概念|测量)|pilot|既有.{0,8}(理论|证据|测量)", design_text, re.IGNORECASE):
            issues.append("exploratory-stage causal-effect design needs a staged pilot/concept-measurement foundation")
    if family == "causal_effect" and re.search(r"单一?案例|单案例|single\s*case", design_text, re.IGNORECASE):
        if not re.search(r"跨时|多时点|子案例|组内|前后|比较|反事实|中断|断点|DID|RDD|合成控制", design_text, re.IGNORECASE):
            issues.append("single-case causal-effect claim lacks real within-case, temporal, comparative, or counterfactual variation")
    if family == "causal_mechanism" and re.search(r"单一?案例|单案例|single\s*case", design_text, re.IGNORECASE):
        if not re.search(r"过程追踪|过程证据|跨时|多时点|子案例|组内|前后|时序|within.case|process.trac|temporal|subcase", design_text, re.IGNORECASE):
            issues.append("single-case causal-mechanism claim lacks within-case process or temporal variation")

    question_row = located.get("research question")
    if question_row:
        question_text = question_row[content_index]
        if not question_is_answerable(question_text):
            issues.append("research question must be an answerable question rather than a title or topic label")
        if re.search(r"重要意义|鲜有研究|填补空白|研究现状", question_text) and not re.search(
            r"为什么|为何|如何|何以|是否|在何种|什么条件|何者", question_text
        ):
            issues.append("research question reads as importance/gap rhetoric rather than an answerable question")

        comparison_design_text = " ".join(
            row[index]
            for row in (unit_row, design_row, variation_row)
            if row
            for index in (content_index, evidence_index)
            if index < len(row)
        )
        question_fit_text = " ".join(
            [
                question_text,
                question_type_row[evidence_index] if question_type_row else "",
                otipr_row[content_index] if otipr_row else "",
                comparison_design_text,
                " ".join(question_branch_text),
            ]
        )
        if question_type and not question_design_matches(question_type, question_fit_text):
            issues.append(f"{question_type} research question does not state the answer task and matching design")
        if MULTI_OUTCOME_QUESTION.search(question_text):
            if not OUTCOME_MARKER.search(comparison_design_text):
                issues.append("some-versus-some research question does not define one common outcome")
            if not COMPARISON_MARKER.search(comparison_design_text) or NO_COMPARISON.search(comparison_design_text):
                issues.append("some-versus-some research question lacks a comparative design")
        if TELEOLOGICAL_MARKER.search(question_text) and not TEMPORAL_EVIDENCE.search(comparison_design_text):
            issues.append("research question uses teleological stage language without evidence of a real temporal sequence")
    return list(dict.fromkeys(issues))


def render_report(artifact: Path, issues: list[str]) -> str:
    lines = ["# Research Quality Check", "", f"Artifact: `{artifact.name}`", ""]
    if issues:
        lines.extend(["Status: FAIL", "", "## Blocking Issues"])
        lines.extend(f"- {issue}" for issue in issues)
        lines.extend(["", "Return to research/contribution and repair the knowledge-claim-design alignment."])
    else:
        lines.extend(
            [
                "Status: PASS",
                "",
                "The knowledge state, five-part research-question card, question and claim types, gap authenticity, design, alternatives, falsification rule, and inference ceiling are aligned.",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Avereth workspace or knowledge_design_matrix.md")
    parser.add_argument("--markdown", action="store_true", help="Compatibility flag; output is Markdown by default")
    parser.add_argument("--write", action="store_true", help="Write research_quality_check.md beside the matrix")
    args = parser.parse_args()

    artifact = args.path if args.path.suffix.lower() == ".md" else args.path / "knowledge_design_matrix.md"
    issues = check_protocol(artifact)
    report = render_report(artifact, issues)
    print(report, end="")
    if args.write:
        (artifact.parent / "research_quality_check.md").write_text(report, encoding="utf-8")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
