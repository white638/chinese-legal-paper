#!/usr/bin/env python3
"""Dispatch and validate immutable strict-v2 peer-review source outputs.

Reviewers receive only their authorized generated prompt and report observable
manuscript locations, quotations, problems, consequences, and repair routes.
They never own internal evidence identities or the editor synthesis.  The
separate review lifecycle compiler maps validated raw outputs into the canonical
Finding registry and derives every human-readable review view from JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import secrets
import sys
import unicodedata
import zipfile
from xml.etree import ElementTree
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from _engine_utils import (
    markdown_tables,
    normalize_tex,
    read_text,
    split_paragraphs,
)
from revision_contract import manuscript_units

SECTION_RE = re.compile(r"\\(?:section|subsection|subsubsection)\*?\{([^{}]+)\}", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Stage 5g: scene-aware reviewer personas
# ---------------------------------------------------------------------------

SCENE_VALID = {"journal", "conference", "report_review", "competition"}

# These controller-owned files are not shown to reviewers, but they are inputs
# to the internal identity mapper.  Dispatch binds any that exist so a later
# mapper run cannot silently use a different authority snapshot.
REVIEW_MAPPING_INPUTS = (
    "claim_register.md",
    "writing_rationale_matrix.md",
    "evidence_bank.md",
    "claim_evidence_scope_matrix.md",
    "research_design.json",
    "method_execution.json",
)
DELTA_AGENT_FILENAMES = {
    "methods": "avereth_methods.toml",
    "contribution": "avereth_contribution.toml",
    "clarity": "avereth_clarity.toml",
}
DELTA_ROLE_RESPONSIBILITIES = {
    "methods": (
        "Evaluate methodological clarity, reproducibility, assumptions, research design, "
        "evidence boundaries, and whether the reported analysis supports the stated inference."
    ),
    "contribution": (
        "Evaluate the evidence-grounded contribution, gap-question-answer alignment, claim "
        "strength and scope, material countervoices, reader update, and venue fit."
    ),
    "clarity": (
        "Evaluate evidence-grounded structure, explanation, voice attribution, transitions, direct "
        "positive formulation, and whether the revised manuscript reads as one coherent argument."
    ),
}

WRITING_REVIEW_GUIDANCE = {
    "clarity": (
        "Judge recoverable reasoning, not a fixed prose sequence. The reconstruction order in this "
        "review is not a mandated sentence order: evidence, a contextual quotation, a question, a "
        "verified scene, or a conceptual distinction may open a paragraph. Do not require every "
        "paragraph to begin with a short summary, force opening variety, or reward shorter sentences "
        "as such; a clear long sentence may carry a dependent inference better than fragments. "
        "Distinguish adjacent concepts by their conditions and evidentiary consequences. Recover "
        "who acts, under what conditions, and with what result where the object permits it. "
        "Material may perform a key argumentative step before the author interprets it; recover "
        "what it changes without demanding a stock sentence after each quotation. Compare texts "
        "at a specified structural level, including conditions, differences, and explanatory gain; "
        "word similarity is not structural equivalence, and analogy is not independent corroboration. "
        "A critique must identify an explanatory failure, missing premise, or internal consequence, "
        "and address the argument rather than the author's character. Apply these questions only "
        "within the authorized review scope. Do not score quotation, hook, metaphor, sentence-length "
        "or abstract-word counts."
    ),
    "contribution": (
        "Locate the genuine puzzle, tension, or consequential unknown, the concepts needed to "
        "understand it, and any relevant competing explanation. Recover what the argument adds, "
        "revises, rejects, or reorganizes in existing knowledge. Do not manufacture a paradox or "
        "opponent for descriptive, historical, or normative work. Conceptual distinctions and "
        "cross-text comparisons must change an evidence-grounded judgment; explain their conditions, "
        "differences, and explanatory gain. Analogy alone is not independent corroboration, and "
        "shared wording is not proof of an equivalent structure. Keep criticism directed at "
        "concepts, evidence, and explanations rather than people. Assess only authorized inputs."
    ),
}

# CNKI-PAPER DIALOGIC-REVIEW COMPAT: fair response increment and isolated voice recovery
# CNKI-PAPER OBJECT-FIRST REVIEW COMPAT: object/problem/answer/evidence before author positioning
SCENE_PERSONA_DEFAULTS: dict[str, dict[str, str]] = {
    "journal": {
        "methods": "Focus on originality, method rigor, evidence strength, reproducibility, and fit for the target journal.",
        "contribution": "Assess the contribution's response increment over fairly represented prior positions, its material reader updates, citation credibility, any qualifying same-result countervoice, and alignment with journal standards.",
        "clarity": "Clean-read the final manuscript only. First recover what happened, why it happened, how the evidence supports that explanation, and what understanding changes; then assess object/problem/answer/evidence, positive formulation, voice, structure, and revision cleanliness.",
        "venue_hint": "journal",
    },
    "conference": {
        "methods": "Focus on novelty, technical contribution, correctness under time-limited presentation constraints, and clarity for a conference audience.",
        "contribution": "Assess whether the response to prior work adds a compelling, properly scoped increment, handles any qualifying same-result countervoice, and gives the conference audience an evidence-grounded reason to care.",
        "clarity": "Clean-read the final manuscript only. First recover what happened, why it happened, how the evidence supports that explanation, and what understanding changes; then assess object/problem/answer/evidence, positive formulation, concise presentation, and revision cleanliness.",
        "venue_hint": "conference",
    },
    "report_review": {
        "methods": "Focus on coverage, logic, source synthesis, readability, and practical value for the report's stated purpose.",
        "contribution": "Assess whether the report fairly synthesizes source positions, adds a defensible response, addresses the strongest alternative, and delivers clear practical stakes.",
        "clarity": "Clean-read the final report only. First recover what happened, why it happened, how the evidence supports that explanation, and what understanding changes; then assess object/problem/answer/evidence, positive formulation, organization, and revision cleanliness.",
        "venue_hint": "report or review",
    },
    "competition": {
        "methods": "Focus on rubric alignment, deliverable completeness, visual/result clarity, innovation claim, and adherence to competition constraints.",
        "contribution": "Assess the innovation claim as a response increment over credible alternatives, its evidence-grounded stakeholder payoff, any qualifying same-result countervoice, and fit with competition criteria.",
        "clarity": "Clean-read the final entry only. First recover what happened, why it happened, how the evidence supports that explanation, and what understanding changes; then assess object/answer/evidence, positive formulation, presentation, and revision cleanliness.",
        "venue_hint": "competition",
    },
}


@dataclass
class ReviewerPersona:
    role: str           # methods | contribution | clarity
    title: str = ""
    venue_context: str = ""
    standards: str = ""
    red_flags: str = ""
    review_style: str = ""


@dataclass
class ReviewFinding:
    id: str
    reviewer_role: str              # methods | contribution | clarity | editor
    severity: str                   # CRITICAL | MAJOR | MINOR | OBSERVATION
    what: str                       # what was found
    rationale_row: str | None       # which rationale matrix row(s) this maps to
    evidence_status: str            # supported / missing / weak / n/a
    evidence_detail: str            # which evidence (or why missing)
    revision_command: str           # concrete action: "In paragraph 3, replace X with Y because Z"
    teaching_note: str              # why this revision pattern matters


@dataclass
class ReviewerSection:
    role: str
    title: str
    focus: str
    rubric_dimensions: list[str]
    findings: list[ReviewFinding] = field(default_factory=list)


@dataclass
class EditorSynthesis:
    agreement_points: list[str] = field(default_factory=list)
    disagreement_points: list[str] = field(default_factory=list)
    revision_priority: list[str] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class StructuredReviewReport:
    manuscript_path: str
    sections: list[dict] = field(default_factory=list)
    reviewers: list[ReviewerSection] = field(default_factory=list)
    editor: EditorSynthesis | None = None
    total_findings: int = 0
    reviewer_personas: list[ReviewerPersona] = field(default_factory=list)
    persona_warnings: list[str] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        return sum(1 for r in self.reviewers for f in r.findings if f.severity == "CRITICAL")


def load_reviewer_personas(out_dir: Path) -> tuple[list[ReviewerPersona], list[str]]:
    warnings: list[str] = []
    config = {}
    config_path = out_dir / "workflow_config.json"
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _default_personas("journal"), warnings
    if not config:
        return _default_personas("journal"), warnings
    scene = str(config.get("scene", "journal"))
    if scene not in SCENE_VALID:
        scene = "journal"
    target_name = str(config.get("target_name", "")).strip()
    defs = SCENE_PERSONA_DEFAULTS.get(scene, SCENE_PERSONA_DEFAULTS["journal"])
    venue_hint = defs.get("venue_hint", scene)
    personas: list[ReviewerPersona] = []
    for role_key in ("methods", "contribution", "clarity"):
        p = ReviewerPersona(
            role=role_key,
            title=f"{role_key.title()} Reviewer ({venue_hint})",
            venue_context=f"Target context: {target_name}" if target_name else f"Target venue type: {venue_hint}.",
            standards=defs.get(role_key, ""),
            review_style="Scene-aware structured review.",
        )
        personas.append(p)
    rp = config.get("reviewer_persona")
    if rp is not None:
        if isinstance(rp, str) and rp.strip():
            for p in personas:
                p.review_style = rp.strip()
        elif isinstance(rp, dict):
            for role_key in ("methods", "contribution", "clarity"):
                override = rp.get(role_key)
                if isinstance(override, str) and override.strip():
                    for p in personas:
                        if p.role == role_key:
                            p.review_style = override.strip()
                elif override is not None:
                    warnings.append(f"reviewer_persona['{role_key}']: expected string, ignored.")
        else:
            warnings.append(f"reviewer_persona: expected string or dict, got {type(rp).__name__} — ignored.")
    return personas, warnings


def _default_personas(scene: str = "journal") -> list[ReviewerPersona]:
    if scene not in SCENE_VALID:
        scene = "journal"
    defs = SCENE_PERSONA_DEFAULTS[scene]
    venue_hint = defs.get("venue_hint", scene)
    personas: list[ReviewerPersona] = []
    for role_key in ("methods", "contribution", "clarity"):
        personas.append(ReviewerPersona(
            role=role_key,
            title=f"{role_key.title()} Reviewer ({venue_hint})",
            venue_context=f"Target venue type: {venue_hint}.",
            standards=defs.get(role_key, ""),
            review_style="Scene-aware structured review.",
        ))
    return personas


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Structured peer review for CNKI-Paper manuscripts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--manuscript", help="Path to .tex manuscript (default: final_paper/main.tex under output_dir)")
    parser.add_argument("--dispatch", action="store_true", help="Generate independent reviewer prompts for multi-agent dispatch")
    parser.add_argument("--dispatch-delta", action="store_true", help="Generate impact-routed incremental reviewer prompts")
    parser.add_argument("--impact-manifest", help="Path to avereth-revision-impact/v1 JSON")
    parser.add_argument("--cycle-id", help="Explicit RC-NNN identifier; otherwise use the next append-only cycle")
    parser.add_argument("--validate", help="Validate an existing review file (single) or directory (multi-agent)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write structured_review.md")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# section extraction and rationale matrix parsing
# ---------------------------------------------------------------------------

def manuscript_text_content(manuscript_path: Path) -> str:
    if manuscript_path.suffix.lower() != ".docx":
        return read_text(manuscript_path)
    try:
        with zipfile.ZipFile(manuscript_path) as archive:
            root = ElementTree.fromstring(archive.read("word/document.xml"))
    except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
        return ""
    return "\n".join(
        node.text or ""
        for node in root.iter()
        if node.tag.endswith("}t") and (node.text or "").strip()
    )


def extract_sections(manuscript_path: Path) -> list[dict]:
    raw = manuscript_text_content(manuscript_path)
    sections: list[dict] = []
    if manuscript_path.suffix.lower() == ".tex":
        parts = SECTION_RE.split(raw)
        if len(parts) > 1:
            for i in range(1, len(parts), 2):
                title = parts[i].strip()
                body = normalize_tex(parts[i + 1]) if i + 1 < len(parts) else ""
                paras = split_paragraphs(body)
                sections.append({"title": title, "paragraphs": paras, "word_count": sum(len(p.split()) for p in paras)})
            return sections
    text = normalize_tex(raw) if manuscript_path.suffix.lower() == ".tex" else raw
    paras = split_paragraphs(text)
    sections.append({"title": "Full Manuscript", "paragraphs": paras, "word_count": sum(len(p.split()) for p in paras)})
    return sections


def parse_rationale_matrix(out_dir: Path) -> list[dict]:
    matrix_path = out_dir / "writing_rationale_matrix.md"
    if not matrix_path.exists():
        return []
    text = matrix_path.read_text(encoding="utf-8", errors="ignore")
    tables = markdown_tables(text)
    if not tables:
        return []
    rows = tables[0]
    if len(rows) < 2:
        return []
    header = rows[0]
    result: list[dict] = []
    for i, row in enumerate(rows[1:], start=1):
        entry: dict = {"row_id": str(i)}
        for j, cell in enumerate(row):
            if j < len(header):
                entry[header[j].lower()] = cell
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# evidence bank check helper
# ---------------------------------------------------------------------------

def check_evidence_available(out_dir: Path) -> dict[str, bool]:
    evidence_path = out_dir / "evidence_bank.md"
    if not evidence_path.exists():
        return {"exists": False, "has_content": False}
    text = evidence_path.read_text(encoding="utf-8", errors="ignore")
    return {"exists": True, "has_content": len(text) > 300}


# ---------------------------------------------------------------------------
# review generation (prepares structure — LLM fills findings)
# ---------------------------------------------------------------------------

def generate_structured_review(out_dir: Path, manuscript_path: Path,
                             personas: list[ReviewerPersona] | None = None,
                             persona_warnings: list[str] | None = None) -> StructuredReviewReport:
    sections = extract_sections(manuscript_path)
    if personas is None:
        personas = _default_personas("journal")
    if persona_warnings is None:
        persona_warnings = []

    report = StructuredReviewReport(str(manuscript_path), sections=sections,
                                    reviewer_personas=personas, persona_warnings=persona_warnings)

    # ---- Methods Reviewer ----
    methods = ReviewerSection(
        role="methods",
        title="Methods & Reproducibility Reviewer",
        focus=(
            "Assess methodological clarity, reproducibility, assumption justification, "
            "experimental design quality, and whether material boundaries are accurate, "
            "concentrated, and non-redundant."
        ),
        rubric_dimensions=[
            "Method description completeness (1=insufficient detail to replicate, 5=fully replicable)",
            "Assumption justification (1=unstated, 5=explicit with rationale)",
            "Experimental design (1=flawed, 5=rigorous)",
            "Boundary accuracy and concentration (1=material limits omitted, vague, or repeated, 5=accurate, load-bearing, concentrated, and non-redundant)",
        ],
    )

    # ---- Contribution Reviewer ----
    contribution = ReviewerSection(
        role="contribution",
        title="Contribution & Novelty Reviewer",
        focus=(
            "Assess whether the contribution is clearly stated, properly scoped, and "
            "preserves the confirmed outcome, unit, and case/material facts; "
            "preserves supplied predicate strength and every decisive requested deliverable; "
            "adequately differentiated from a fair account of prior positions, supported "
            "by evidence while preserving design, execution, scope, and adverse-result "
            "constraints; responsive to any activated material countervoice through discriminating "
            "predictions without inventing one; keeps the confirmed gap diagnosis, research question, actual answer, "
            "and contribution aligned; and is consequential for identifiable readers."
        ),
        rubric_dimensions=[
            "Contribution clarity (1=vague, 5=crystal clear)",
            "Load-bearing fact-card closure (1=final/payoff sentences rename, alter, or contradict the claim, 5=speaker/result object/predicate strength/scope/epistemic status remain stable)",
            "Requested-deliverable completeness (1=decisive output omitted, 5=all material obligations closed without unrelated quotas)",
            "Response increment and gap-question-contribution alignment (1=labels, question, answer, or contribution drift, 5=current evidence supports one material chain)",
            "Evidence-to-claim strength (1=unsupported assertion, 5=conclusive evidence)",
            "Statistical claim ownership when comparison/inference is present (1=test object shifted or fields invented, 5=actual comparison/uncertainty/test preserved)",
            "Additive identity and adverse-evidence preservation (1=dialogue labels displace research constraints, 5=design/execution/scope/negative results remain traceable)",
            "Material reader update (1=generic or invented, 5=every supported update states the reader, changed default/action, cost, and stopping boundary; zero is valid when the result supports none)",
            "Activated material countervoice handling (1=a real alternative is ignored or an imagined one is added, 5=each same-result/same-stage alternative is fairly handled with discriminating evidence; zero is valid when none qualifies)",
            "Venue appropriateness (1=mismatched, 5=perfect fit for venue)",
        ],
    )

    # ---- Clarity Reviewer ----
    clarity = ReviewerSection(
        role="clarity",
        title="Structure & Clarity Reviewer",
        focus=(
            "Assess organization, argument flow, readability, figure/table integration, "
            "section transitions, substantive explanation, positive formulation, and "
            "revision cleanliness. Recover what happened, why it happened, how the "
            "evidence supports the explanation, and what understanding changes before "
            "assessing author positioning, response, and payoff."
        ),
        rubric_dimensions=[
            "Overall narrative structure (1=author process/framework obscures object/problem/answer/evidence, 5=object/problem/answer/evidence form the main line)",
            "Section transitions (1=author-process scaffolding interrupts object/evidence, 5=object/evidence questions hand off smoothly)",
            "Research-object and voice recovery (1=object or voices obscured, 5=object and voices unambiguous)",
            "Substantive-answer before author-response/payoff recovery (1=self-explanation dominates or answer is missing, 5=answer is recoverable before positioning)",
            "Figure/table quality and integration (1=poor/cluttered, 5=excellent)",
            "Object-first writing clarity (1=author refusals/process dominate, 5=objects, actions, evidence, judgments, and necessary boundaries are direct)",
            "Substantive explanation (1=claims or evidence are merely listed, 5=what/why/how-evidence-supports/reader-update are recoverable)",
            "Positive formulation (1=author-intent defenses or caveat-first negation dominate, 5=claims and scope are stated directly while real negative results and limits remain)",
            "Revision cleanliness (1=comment order, implicit rebuttal sequence, or patch seams remain visible, 5=the final manuscript reads as one designed argument)",
        ],
    )
    report.reviewers = [methods, contribution, clarity]

    # ---- Editor Synthesis ----
    report.editor = EditorSynthesis(
        agreement_points=["[LLM: identify material agreement, or state none]"],
        disagreement_points=["[LLM: note any conflicting reviewer assessments]"],
        revision_priority=[
            "[LLM: rank only material revisions; use PASS when none are warranted]",
        ],
        recommendation="[DERIVED: PASS / MINOR_REVISION / MAJOR_REVISION / BLOCK from Finding status]",
    )
    report.total_findings = sum(len(r.findings) for r in report.reviewers)

    return report


# ---------------------------------------------------------------------------
# validation (checks an LLM-produced review for completeness)
# ---------------------------------------------------------------------------

REVIEW_SIMILARITY_THRESHOLD = 0.62
MIN_SUBSTANTIVE_CJK_CHARS = 16
MIN_SUBSTANTIVE_LATIN_WORDS = 8

# CNKI-PAPER STRUCTURED-REVIEW CONTRACT: complete inputs and exact rubric dimensions
RUBRIC_TABLE_HEADER = (
    "Dimension ID",
    "Applicability",
    "Score",
    "Reason",
    "Manuscript Location",
)
REVIEW_OUTPUT_ROLE = {
    "methods_review_output.md": "methods",
    "contribution_review_output.md": "contribution",
    "clarity_review_output.md": "clarity",
}
REVIEW_RUBRICS: dict[str, tuple[tuple[str, str], ...]] = {
    "methods": (
        ("MET-METHOD-COMPLETENESS", "Method description completeness (1=insufficient, 5=fully replicable)"),
        ("MET-ASSUMPTION-JUSTIFICATION", "Assumption justification (1=unstated, 5=explicit with rationale)"),
        ("MET-EXPERIMENTAL-DESIGN", "Experimental design (1=flawed, 5=rigorous)"),
        ("MET-LIMITATIONS", "Boundary accuracy and concentration (1=material limits omitted, vague, or repeated, 5=accurate, load-bearing, concentrated, and non-redundant)"),
    ),
    "contribution": (
        ("CON-CONTRIBUTION-CLARITY", "Contribution clarity (1=vague, 5=crystal clear)"),
        ("CON-FACT-CARD-CLOSURE", "Load-bearing fact-card closure (1=final/payoff sentences rename, alter, or contradict the claim, 5=speaker/result object/predicate strength/scope/epistemic status remain stable)"),
        ("CON-DELIVERABLE-COMPLETENESS", "Requested-deliverable completeness (1=decisive output omitted, 5=all material obligations closed without unrelated quotas)"),
        ("CON-RESPONSE-INCREMENT", "Response increment and gap-question-contribution alignment (1=labels or claims drift, 5=one evidence-grounded material chain)"),
        ("CON-EVIDENCE-CLAIM-STRENGTH", "Evidence-to-claim strength (1=unsupported, 5=conclusive)"),
        ("CON-STATISTICAL-CLAIM-OWNERSHIP", "Statistical claim ownership when comparison/inference is present (1=test object shifted or fields invented, 5=actual comparison/uncertainty/test preserved)"),
        ("CON-IDENTITY-ADVERSE-EVIDENCE", "Additive identity and adverse-evidence preservation (1=lost, 5=fully traceable)"),
        ("CON-READER-PAYOFF", "Material reader update (1=generic/invented, 5=each supported update names the reader, changed default/action, cost, and stopping boundary; zero is valid when none is supported)"),
        ("CON-COUNTERVOICE", "Activated material countervoice handling (1=real alternative ignored or imagined one added, 5=each same-result/same-stage alternative is fair and discriminated; zero is valid when none qualifies)"),
        ("CON-VENUE-FIT", "Venue appropriateness (1=mismatched, 5=perfect fit)"),
    ),
    "clarity": (
        ("CLR-OVERALL-STRUCTURE", "Overall structure (1=author process/framework obscures object/problem/answer/evidence, 5=object/problem/answer/evidence form the main line)"),
        ("CLR-SECTION-TRANSITIONS", "Section transitions (1=author-process scaffolding interrupts object/evidence, 5=object/evidence questions hand off smoothly)"),
        ("CLR-VOICE-RECOVERY", "Research-object and Who-says-what recovery (1=object or voices obscured, 5=object and voices unambiguous)"),
        ("CLR-RESPONSE-PAYOFF", "Substantive-answer before author-response and payoff recovery (1=self-explanation dominates or answer is missing, 5=answer is recoverable before positioning)"),
        ("CLR-FIGURE-TABLE-INTEGRATION", "Figure/table integration (1=poor, 5=excellent)"),
        ("CLR-WRITING-CLARITY", "Object-first writing clarity (1=author refusals/process dominate, 5=objects, actions, evidence, judgments, and necessary boundaries are direct)"),
        ("CLR-SUBSTANTIVE-EXPLANATION", "Substantive explanation (1=claims or evidence are merely listed, 5=what happened, why, how the evidence supports it, and the reader update are recoverable)"),
        ("CLR-POSITIVE-FORMULATION", "Positive formulation (1=author-intent defenses or caveat-first negation dominate, 5=claims and scope are direct while real negative results and limits remain)"),
        ("CLR-REVISION-CLEANLINESS", "Revision cleanliness (1=comment order, implicit rebuttal sequence, or patch seams remain visible, 5=the final manuscript reads as one designed argument)"),
    ),
}

_OVERALL_SCORE_RE = re.compile(
    r"(?im)^[^\n]*(?:overall\s+(?:score|rating)|总体评分|总评分|综合评分)"
    r"\s*[:：-]\s*([1-5])\s*/\s*5(?:\s|[^\d].*)?$"
)
_REVIEW_VERDICT_RE = re.compile(
    r"(?im)^\s*(?:Review Verdict|评审结论)\s*[:：]\s*(PASS|FINDINGS)\s*$"
)
_ACTION_RE = re.compile(
    r"(?im)^\s*Text Action\s*[:：]\s*(DELETE|REPLACE|MOVE|ADD|NO_ACTION)\s*$"
)
_FINDING_ID_LINE_RE = re.compile(r"(?im)^\s*Finding ID\s*[:：]\s*([^\n]+?)\s*$")
_SEVERITY_LINE_RE = re.compile(r"(?im)^\s*Severity\s*[:：]\s*([^\n]+?)\s*$")
_CONFIDENCE_LINE_RE = re.compile(r"(?im)^\s*Confidence\s*[:：]\s*([^\n]+?)\s*$")
_CATEGORY_LINE_RE = re.compile(r"(?im)^\s*Category\s*[:：]\s*([^\n]+?)\s*$")
_LOCATION_LINE_RE = re.compile(r"(?im)^\s*Location\s*[:：]\s*([^\n]+?)\s*$")
_QUOTED_SPAN_LINE_RE = re.compile(r"(?im)^\s*Quoted Span\s*[:：]\s*([^\n]+?)\s*$")
_ISSUE_LINE_RE = re.compile(r"(?im)^\s*Issue\s*[:：]\s*([^\n]+?)\s*$")
_READER_CONSEQUENCE_LINE_RE = re.compile(
    r"(?im)^\s*Reader Consequence\s*[:：]\s*([^\n]+?)\s*$"
)
_REPAIR_KIND_LINE_RE = re.compile(r"(?im)^\s*Repair Kind\s*[:：]\s*([^\n]+?)\s*$")
_OWNER_STAGE_LINE_RE = re.compile(r"(?im)^\s*Owner Stage\s*[:：]\s*([^\n]+?)\s*$")
_RECOMMENDED_ACTION_LINE_RE = re.compile(
    r"(?im)^\s*Recommended Action\s*[:：]\s*([^\n]+?)\s*$"
)
_NET_WORD_DELTA_RE = re.compile(
    r"(?im)^\s*Net Word Delta\s*[:：]\s*([+-]?\d+)\s*$"
)
_CLAIM_ID_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:C|CLM|CLAIM)-[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_EVIDENCE_DESIGN_ANCHOR_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:SRC|CR|SYN|EVD|EV|DESIGN|DSG|EXE)-"
    r"[A-Za-z0-9][A-Za-z0-9._-]*(?![A-Za-z0-9])",
    re.IGNORECASE,
)
_FINDING_HEADING_RE = re.compile(
    r"(?im)^[ \t]*(?:#{1,6}[ \t]*|[-*+][ \t]*)?"
    r"(?:finding|issue|concern|comment|发现|问题|意见)"
    r"[ \t]*(?:#|第)?[ \t]*(?:\d{1,2}|[一二三四五六七八九十]+)?"
    r"[ \t]*(?:[：:、.)）\-–—]|$)"
)
_INTERNAL_CONTRACT_METADATA_LABEL_RE = re.compile(
    r"(?i)^(?:schema(?:[_ ]version)?|workflow(?:[_ ]stage|[_ ]status)?|"
    r"(?:audit |output )?receipt|(?:content |basis |input )?(?:sha-?256|digest)|"
    r"(?:review |workflow )?run[_ ]id|context[_ ]id|"
    r"(?:problem orientation|claim|evidence|design|execution|source)[_ ]ids?)$"
)
_V2_FINDING_HEADING_RE = re.compile(
    r"(?im)^#{1,6}\s+(?:Finding|发现|问题|意见)\s+(?:\d{1,3}|[一二三四五六七八九十]+)\s*$"
)
_STRICT_V2_FINDING_HEADING_RE = re.compile(
    r"(?i)^Finding\s+(\d{1,3})$"
)
_MARKDOWN_HEADING_RE = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)\s*$")
_LIST_ITEM_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)(?P<marker>"
    r"\d{1,2}[.)、]|[（(]\d{1,2}[)）]|[-*+])"
    r"[ \t]+(?P<body>.+)$"
)
_NUMBERED_ITEM_RE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)(?P<marker>"
    r"\d{1,2}[.)、]|[（(]\d{1,2}[)）])"
    r"[ \t]+(?P<body>.+)$"
)
_FINDINGS_SECTION_TERMS = (
    "finding",
    "specific finding",
    "issue",
    "concern",
    "主要发现",
    "实质发现",
    "评审意见",
    "审稿意见",
    "主要问题",
    "问题清单",
)
_LOCATION_PATTERNS = (
    re.compile(
        r"(?i)(?:manuscript\s+)?location\s*[:：]\s*"
        r"[^\n|]{2,100}"
    ),
    re.compile(
        r"(?:稿内|原文|论文|文中)?(?:位置|定位)\s*[:：]\s*"
        r"[^\n|]{2,100}"
    ),
    re.compile(
        r"第\s*[0-9一二三四五六七八九十百零两]+\s*"
        r"(?:章|节|小节|部分|段|页|行)"
    ),
    re.compile(
        r"(?i)\b(?:section|chapter|paragraph|para\.?|page|p\.|"
        r"lines?|table|figure|appendix|footnote)\s*"
        r"(?:no\.?\s*)?[A-Za-z0-9一二三四五六七八九十]+"
        r"(?:[.\-–—][A-Za-z0-9一二三四五六七八九十]+)*"
    ),
    re.compile(
        r"(?:摘要|引言|导论|文献综述|理论框架|研究设计|研究方法|"
        r"方法|结果|讨论|结论|附录)(?:部分|章节|一节|小节|"
        r"第\s*[0-9一二三四五六七八九十百零两]+\s*段)"
    ),
    re.compile(
        r"(?i)(?:\b(?:in|at)\s+(?:the\s+)?"
        r"(?:abstract|introduction|literature\s+review|theoretical\s+framework|"
        r"methods?|results?|discussion|conclusion)\b|"
        r"\b(?:abstract|introduction|literature\s+review|theoretical\s+framework|"
        r"methods?|results?|discussion|conclusion)\s+section\b)"
    ),
)


def _unicode_review_canon(text: str) -> tuple[str, set[str], set[str]]:
    """Return Unicode-safe compact text, character 4-grams, and Latin tokens."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = re.sub(r"```.*?```", " ", normalized, flags=re.DOTALL)
    normalized = re.sub(r"https?://\S+", " ", normalized)
    compact = "".join(char for char in normalized if char.isalnum())
    if not compact:
        return "", set(), set()
    n = 4 if len(compact) >= 4 else len(compact)
    grams = {
        compact[index:index + n]
        for index in range(0, len(compact) - n + 1)
    }
    latin_tokens = set(re.findall(r"[a-z0-9]+", normalized))
    return compact, grams, latin_tokens


def _review_similarity(a: str, b: str) -> float:
    """Compare reviews without discarding Han or other non-Latin scripts."""
    compact_a, grams_a, tokens_a = _unicode_review_canon(a)
    compact_b, grams_b, tokens_b = _unicode_review_canon(b)
    if not compact_a or not compact_b:
        return 0.0
    gram_score = (
        len(grams_a & grams_b) / len(grams_a | grams_b)
        if grams_a or grams_b else 0.0
    )
    token_score = (
        len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
        if tokens_a or tokens_b else 0.0
    )
    sequence_score = SequenceMatcher(None, compact_a, compact_b).ratio()
    # Character n-grams carry most weight because they work for both Chinese
    # and English and still catch copied passages whose paragraphs were moved.
    return round(
        (gram_score * 0.65) + (sequence_score * 0.25) + (token_score * 0.10),
        4,
    )


def _has_identifiable_score(text: str) -> bool:
    return _OVERALL_SCORE_RE.search(text) is not None


def _contains_location(text: str) -> bool:
    return any(pattern.search(text) for pattern in _LOCATION_PATTERNS)


def _is_substantive_finding(text: str) -> bool:
    cleaned = re.sub(r"https?://\S+", " ", text)
    cleaned = re.sub(r"[#*_`>|~\[\](){}]", " ", cleaned)
    cleaned = re.sub(
        r"(?i)(?:manuscript\s+)?location|稿内位置|原文位置|论文位置|位置|定位",
        " ",
        cleaned,
    )
    cjk_count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", cleaned))
    latin_words = re.findall(r"[A-Za-z]+(?:['’-][A-Za-z]+)?", cleaned)
    alnum_count = sum(char.isalnum() for char in cleaned)
    return (
        cjk_count >= MIN_SUBSTANTIVE_CJK_CHARS
        or len(latin_words) >= MIN_SUBSTANTIVE_LATIN_WORDS
        or alnum_count >= 32
    )


def _finding_section_region(text: str) -> str | None:
    headings = list(_MARKDOWN_HEADING_RE.finditer(text))
    for index, match in enumerate(headings):
        title = re.sub(r"[*_`]", "", match.group(2)).strip().casefold()
        if len(match.group(1)) != 2 or title != "findings":
            continue
        level = len(match.group(1))
        end = len(text)
        for following in headings[index + 1:]:
            if len(following.group(1)) <= level:
                end = following.start()
                break
        return text[match.end():end]
    return None


def _strict_findings_section_issues(role_file: str, text: str) -> list[str]:
    """Require one exact Findings container and keep every issue heading inside it."""
    headings = list(_MARKDOWN_HEADING_RE.finditer(text))
    sections = [
        (index, match)
        for index, match in enumerate(headings)
        if len(match.group(1)) == 2
        and re.sub(r"[*_`]", "", match.group(2)).strip().casefold() == "findings"
    ]
    if len(sections) != 1:
        return [
            f"[RD.REVIEW.FINDINGS_SECTION_INVALID] {role_file}: strict v2 requires exactly one exact `## Findings` section."
        ]
    index, section = sections[0]
    start = section.end()
    end = len(text)
    for following in headings[index + 1:]:
        if len(following.group(1)) <= 2:
            end = following.start()
            break
    issues: list[str] = []
    for issue_heading in _FINDING_HEADING_RE.finditer(text):
        if not (start <= issue_heading.start() < end):
            issues.append(
                f"[RD.REVIEW.FINDING_OUTSIDE_SECTION] {role_file}: every Finding/Issue/Concern heading must be inside `## Findings`."
            )
            break
    return issues


def _blocks_from_matches(text: str, matches: list[re.Match[str]]) -> list[str]:
    return [
        text[match.start():(matches[index + 1].start() if index + 1 < len(matches) else len(text))].strip()
        for index, match in enumerate(matches)
    ]


def _list_blocks(text: str, *, numbered_only: bool = False) -> list[str]:
    matcher = _NUMBERED_ITEM_RE if numbered_only else _LIST_ITEM_RE
    matches = list(matcher.finditer(text))
    if not matches:
        return []
    min_indent = min(len(match.group("indent").expandtabs(4)) for match in matches)
    top_level = [
        match for match in matches
        if len(match.group("indent").expandtabs(4)) == min_indent
    ]
    return _blocks_from_matches(text, top_level)


def _table_finding_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    for table in markdown_tables(text):
        if len(table) < 2:
            continue
        header = " ".join(table[0]).casefold()
        has_finding_column = any(
            term in header
            for term in ("finding", "issue", "concern", "发现", "问题", "意见")
        )
        has_location_column = any(
            term in header
            for term in ("location", "section", "paragraph", "位置", "章节", "段落")
        )
        if has_finding_column and has_location_column:
            blocks.extend(" | ".join(row) for row in table[1:] if any(cell.strip() for cell in row))
    return blocks


def _extract_finding_blocks(text: str) -> list[str]:
    v2_explicit = list(_V2_FINDING_HEADING_RE.finditer(text))
    if v2_explicit:
        blocks = _blocks_from_matches(text, v2_explicit)
        explicit = []
    else:
        explicit = list(_FINDING_HEADING_RE.finditer(text))
    if explicit:
        blocks = _blocks_from_matches(text, explicit)
    elif not v2_explicit:
        blocks = _table_finding_blocks(text)
        if not blocks:
            region = _finding_section_region(text)
            blocks = _list_blocks(region) if region is not None else _list_blocks(text, numbered_only=True)

    unique: list[str] = []
    seen: set[str] = set()
    for block in blocks:
        normalized = "".join(
            char for char in unicodedata.normalize("NFKC", block).casefold()
            if char.isalnum()
        )
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(block)
    return unique


def _strict_finding_heading_issues(role_file: str, text: str) -> list[str]:
    """Reject mixed headings that could be swallowed into a valid v2 block."""
    region = _finding_section_region(text)
    if region is None:
        return []
    headings = [
        (len(match.group(1)), re.sub(r"[*_`]", "", match.group(2)).strip())
        for match in _MARKDOWN_HEADING_RE.finditer(region)
    ]
    issues: list[str] = []
    numbers: list[int] = []
    for level, title in headings:
        match = _STRICT_V2_FINDING_HEADING_RE.fullmatch(title)
        if level != 3 or match is None:
            issues.append(
                f"[RD.REVIEW.FINDING_HEADING_INVALID] {role_file}: every heading inside "
                f"`## Findings` must use exact `### Finding N`; found `{title}`."
            )
            continue
        numbers.append(int(match.group(1)))
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        issues.append(
            f"[RD.REVIEW.FINDING_HEADING_SEQUENCE] {role_file}: Finding headings must be numbered 1..N exactly once."
        )
    return issues


_STRICT_FINDING_FIELD_LINE_RE = re.compile(
    r"(?i)^\s*(?:Finding ID|Severity|Confidence|Category|Location|Quoted Span|Issue|"
    r"Reader Consequence|Repair Kind|Owner Stage|Text Action|Recommended Action|"
    r"Net Word Delta|Recommendation)\s*[:：]"
)
_EXPLICIT_NO_FINDINGS_RE = re.compile(
    r"(?i)^\s*(?:none|n/?a|no findings?|no material objections?)\.?\s*$"
)


def _strict_finding_region_issues(role_file: str, text: str) -> list[str]:
    """Reject substantive Findings prose that no exact v2 block can project."""
    region = _finding_section_region(text)
    if region is None:
        return []
    exact_headings = list(_V2_FINDING_HEADING_RE.finditer(region))
    residual: list[str] = []
    for line in region.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if _STRICT_V2_FINDING_HEADING_RE.fullmatch(
            re.sub(r"^#{1,6}\s+", "", stripped)
        ):
            continue
        if _STRICT_FINDING_FIELD_LINE_RE.match(stripped):
            continue
        if not exact_headings and _EXPLICIT_NO_FINDINGS_RE.fullmatch(stripped):
            continue
        residual.append(stripped)
    residual_text = "\n".join(residual)
    if _is_substantive_finding(residual_text):
        return [
            f"[RD.REVIEW.FINDING_REGION_UNPROJECTED] {role_file}: substantive text inside "
            "`## Findings` must be inside exact `### Finding N` labelled blocks; "
            f"unprojected text begins `{_preview_finding(residual_text)}`."
        ]
    return []


def _preview_finding(text: str, limit: int = 100) -> str:
    preview = re.sub(r"\s+", " ", text).strip()
    return preview if len(preview) <= limit else preview[:limit - 3] + "..."


def _review_verdict(text: str) -> str | None:
    matches = _REVIEW_VERDICT_RE.findall(text)
    if len(matches) != 1:
        return None
    return matches[0].upper()


def _validate_finding_action(
    role_file: str, block: str, index: int
) -> tuple[list[str], int | None, str | None]:
    findings: list[str] = []
    preview = _preview_finding(block)
    action_matches = _ACTION_RE.findall(block)
    delta_match = _NET_WORD_DELTA_RE.search(block)
    action = action_matches[0].upper() if len(action_matches) == 1 else None

    if action is None:
        findings.append(
            f"[RD.REVIEW.ACTION_INVALID] {role_file}: finding {index} requires exactly "
            f"one Text Action: DELETE|REPLACE|MOVE|ADD|NO_ACTION: `{preview}`."
        )

    required_labels = (
        ("Finding ID", _FINDING_ID_LINE_RE),
        ("Severity", _SEVERITY_LINE_RE),
        ("Confidence", _CONFIDENCE_LINE_RE),
        ("Category", _CATEGORY_LINE_RE),
        ("Location", _LOCATION_LINE_RE),
        ("Quoted Span", _QUOTED_SPAN_LINE_RE),
        ("Issue", _ISSUE_LINE_RE),
        ("Reader Consequence", _READER_CONSEQUENCE_LINE_RE),
        ("Repair Kind", _REPAIR_KIND_LINE_RE),
        ("Owner Stage", _OWNER_STAGE_LINE_RE),
        ("Recommended Action", _RECOMMENDED_ACTION_LINE_RE),
    )
    values: dict[str, str] = {}
    for label, pattern in required_labels:
        match = pattern.search(block)
        value = match.group(1).strip() if match else ""
        values[label] = value
        if not value:
            findings.append(
                f"[RD.REVIEW.FIELD_MISSING] {role_file}: finding {index} requires `{label}:` with substantive content."
            )

    role = REVIEW_OUTPUT_ROLE.get(role_file, "")
    prefix = {"methods": "MET", "contribution": "CON", "clarity": "CLR"}.get(role, "")
    if prefix and not re.fullmatch(rf"REV-{prefix}-\d{{3}}", values.get("Finding ID", "").upper()):
        findings.append(
            f"[RD.REVIEW.FINDING_ID_INVALID] {role_file}: finding {index} must use `REV-{prefix}-NNN`."
        )
    if values.get("Severity", "").upper() not in {"CRITICAL", "MAJOR", "MINOR", "OBSERVATION"}:
        findings.append(
            f"[RD.REVIEW.SEVERITY_INVALID] {role_file}: finding {index} requires CRITICAL|MAJOR|MINOR|OBSERVATION."
        )
    if values.get("Confidence", "").upper() not in {"HIGH", "MEDIUM", "LOW"}:
        findings.append(
            f"[RD.REVIEW.CONFIDENCE_INVALID] {role_file}: finding {index} requires HIGH|MEDIUM|LOW."
        )
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,63}", values.get("Category", "")):
        findings.append(
            f"[RD.REVIEW.CATEGORY_INVALID] {role_file}: finding {index} Category must be stable snake_case."
        )
    if values.get("Location") and not _contains_location(values["Location"]):
        findings.append(
            f"[RD.REVIEW.FINDING_LOCATION_INVALID] {role_file}: finding {index} "
            "Location must itself identify a section, paragraph, page, line, table, or figure."
        )
    repair_kind = values.get("Repair Kind", "").upper()
    allowed_repairs = {
        "TEXT_EDIT", "ADD_EVIDENCE", "RERUN_ANALYSIS", "REDESIGN",
        "REOPEN_RESEARCH", "NARROW_CLAIM", "REMOVE_CLAIM", "NO_ACTION",
    }
    if repair_kind not in allowed_repairs:
        findings.append(
            f"[RD.REVIEW.REPAIR_KIND_INVALID] {role_file}: finding {index} has invalid Repair Kind."
        )
    owner_stage = values.get("Owner Stage", "").casefold()
    if owner_stage not in {"research", "design", "execution", "build"}:
        findings.append(
            f"[RD.REVIEW.OWNER_STAGE_INVALID] {role_file}: finding {index} requires research|design|execution|build."
        )

    delta = int(delta_match.group(1)) if delta_match else None
    if delta is None:
        findings.append(
            f"[RD.REVIEW.NET_WORD_DELTA_MISSING] {role_file}: finding {index} requires an integer Net Word Delta."
        )
    elif action in {"DELETE", "REPLACE"} and delta > 0:
        findings.append(
            f"[RD.REVIEW.NET_GROWTH_INVALID] {role_file}: {action} finding {index} cannot have positive net growth."
        )
    elif action == "MOVE" and delta != 0:
        findings.append(
            f"[RD.REVIEW.NET_GROWTH_INVALID] {role_file}: MOVE finding {index} must have Net Word Delta 0."
        )
    elif action == "ADD" and delta <= 0:
        findings.append(
            f"[RD.REVIEW.NET_GROWTH_INVALID] {role_file}: ADD finding {index} must declare a positive Net Word Delta."
        )
    elif action == "NO_ACTION" and delta != 0:
        findings.append(
            f"[RD.REVIEW.NET_GROWTH_INVALID] {role_file}: NO_ACTION finding {index} must have Net Word Delta 0."
        )
    if repair_kind == "NO_ACTION" and action not in {None, "NO_ACTION"}:
        findings.append(
            f"[RD.REVIEW.REPAIR_ACTION_MISMATCH] {role_file}: NO_ACTION repair requires Text Action NO_ACTION."
        )
    if action == "ADD" and repair_kind == "TEXT_EDIT":
        if owner_stage != "build":
            findings.append(
                f"[RD.REVIEW.REPAIR_ACTION_MISMATCH] {role_file}: evidence-bounded TEXT_EDIT ADD must use Owner Stage build."
            )
        if not re.search(r"\b(?:BRIDGE|DEFINE)\b", values.get("Recommended Action", ""), re.IGNORECASE):
            findings.append(
                f"[RD.REVIEW.REPAIR_ACTION_MISMATCH] {role_file}: TEXT_EDIT ADD must propose a BRIDGE or DEFINE subject to the build expression budget."
            )
    if _CLAIM_ID_RE.search(block) or _EVIDENCE_DESIGN_ANCHOR_RE.search(block):
        findings.append(
            f"[RD.REVIEW.INTERNAL_ID_FORBIDDEN] {role_file}: finding {index} must not "
            "invent Claim/Evidence/Design/Execution IDs; the internal mapper owns those identities."
        )
    return findings, delta, action


def _rubric_header_key(cell: str) -> str:
    return re.sub(r"\s+", " ", cell).strip().casefold()


def _validate_rubric_dimension_table(
    role_file: str, text: str
) -> tuple[list[str], dict]:
    findings: list[str] = []
    role = REVIEW_OUTPUT_ROLE.get(role_file)
    if role is None:
        return (
            [f"[RD.REVIEW.ROLE_UNKNOWN] {role_file}: no rubric contract is defined."],
            {
                "rubric_complete": False,
                "rubric_dimensions_expected": 0,
                "rubric_dimensions_valid": 0,
            },
        )

    rubric = REVIEW_RUBRICS[role]
    expected_ids = tuple(dimension_id for dimension_id, _ in rubric)
    expected_set = set(expected_ids)
    expected_header = tuple(_rubric_header_key(cell) for cell in RUBRIC_TABLE_HEADER)
    candidate_tables = [
        table
        for table in markdown_tables(text)
        if table
        and any(
            _rubric_header_key(cell) == expected_header[0]
            for cell in table[0]
        )
    ]
    if not candidate_tables:
        findings.append(
            f"[RD.REVIEW.RUBRIC_TABLE_MISSING] {role_file}: exactly one rubric table "
            "with header `Dimension ID | Applicability | Score | Reason | Manuscript Location` is required."
        )
        return findings, {
            "rubric_complete": False,
            "rubric_dimensions_expected": len(expected_ids),
            "rubric_dimensions_valid": 0,
        }
    if len(candidate_tables) != 1:
        findings.append(
            f"[RD.REVIEW.RUBRIC_TABLE_COUNT] {role_file}: found "
            f"{len(candidate_tables)} rubric dimension tables; exactly one is required."
        )

    table = candidate_tables[0]
    actual_header = tuple(_rubric_header_key(cell) for cell in table[0])
    if actual_header != expected_header:
        findings.append(
            f"[RD.REVIEW.RUBRIC_HEADER_INVALID] {role_file}: rubric header must be "
            "exactly `Dimension ID | Applicability | Score | Reason | Manuscript Location`."
        )

    seen: set[str] = set()
    valid_ids: set[str] = set()
    for row_number, row in enumerate(table[1:], start=1):
        if len(row) != len(RUBRIC_TABLE_HEADER):
            findings.append(
                f"[RD.REVIEW.RUBRIC_ROW_INVALID] {role_file}: rubric row {row_number} "
                "must contain exactly five cells."
            )
            continue
        dimension_id, applicability, score, reason, location = (cell.strip() for cell in row)
        if dimension_id in seen:
            findings.append(
                f"[RD.REVIEW.RUBRIC_DIMENSION_DUPLICATE] {role_file}: duplicate "
                f"dimension ID `{dimension_id}`."
            )
        seen.add(dimension_id)
        if dimension_id not in expected_set:
            findings.append(
                f"[RD.REVIEW.RUBRIC_DIMENSION_UNKNOWN] {role_file}: unknown "
                f"dimension ID `{dimension_id or '<empty>'}`."
            )
            continue

        row_valid = True
        applicability = applicability.upper()
        if applicability not in {"APPLICABLE", "NOT_APPLICABLE", "BLOCKED"}:
            findings.append(
                f"[RD.REVIEW.RUBRIC_APPLICABILITY_INVALID] {role_file}: `{dimension_id}` "
                "must use APPLICABLE|NOT_APPLICABLE|BLOCKED."
            )
            row_valid = False
        elif applicability == "APPLICABLE" and re.fullmatch(r"[1-5]", score) is None:
            findings.append(
                f"[RD.REVIEW.RUBRIC_SCORE_INVALID] {role_file}: applicable `{dimension_id}` "
                f"must have an integer score from 1 to 5, got `{score or '<empty>'}`."
            )
            row_valid = False
        elif applicability != "APPLICABLE" and score.casefold() not in {"n/a", "na", "not applicable"}:
            findings.append(
                f"[RD.REVIEW.RUBRIC_SCORE_INVALID] {role_file}: non-applicable or blocked "
                f"`{dimension_id}` must use N/A, got `{score or '<empty>'}`."
            )
            row_valid = False
        if not _is_substantive_finding(reason):
            findings.append(
                f"[RD.REVIEW.RUBRIC_REASON_WEAK] {role_file}: `{dimension_id}` "
                "requires a substantive reason."
            )
            row_valid = False
        if applicability == "APPLICABLE" and not _contains_location(location):
            findings.append(
                f"[RD.REVIEW.RUBRIC_LOCATION_MISSING] {role_file}: `{dimension_id}` "
                "requires a manuscript section, paragraph, page, line, table, or figure location."
            )
            row_valid = False
        elif applicability != "APPLICABLE" and location.casefold() not in {"n/a", "na", "not applicable"}:
            findings.append(
                f"[RD.REVIEW.RUBRIC_LOCATION_INVALID] {role_file}: non-applicable or blocked "
                f"`{dimension_id}` must use N/A for Manuscript Location."
            )
            row_valid = False
        if row_valid and dimension_id not in valid_ids:
            valid_ids.add(dimension_id)

    missing_ids = [dimension_id for dimension_id in expected_ids if dimension_id not in seen]
    if missing_ids:
        findings.append(
            f"[RD.REVIEW.RUBRIC_DIMENSION_MISSING] {role_file}: missing dimension "
            f"ID(s): {', '.join(missing_ids)}."
        )

    return findings, {
        "rubric_complete": not findings and valid_ids == expected_set,
        "rubric_dimensions_expected": len(expected_ids),
        "rubric_dimensions_valid": len(valid_ids),
    }


def _validate_reviewer_output(role_file: str, text: str) -> tuple[list[str], dict]:
    output_findings: list[str] = []

    rubric_findings, rubric_metrics = _validate_rubric_dimension_table(role_file, text)
    output_findings.extend(rubric_findings)

    verdict = _review_verdict(text)
    if verdict is None:
        output_findings.append(
            f"[RD.REVIEW.VERDICT_INVALID] {role_file}: use exactly one `Review Verdict: PASS|FINDINGS` line."
        )

    output_findings.extend(_strict_findings_section_issues(role_file, text))
    output_findings.extend(_strict_finding_heading_issues(role_file, text))
    output_findings.extend(_strict_finding_region_issues(role_file, text))

    blocks = _extract_finding_blocks(text)
    substantive = [block for block in blocks if _is_substantive_finding(block)]
    def valid_location(block: str) -> bool:
        match = _LOCATION_LINE_RE.search(block)
        return bool(match and _contains_location(match.group(1)))

    valid = [block for block in substantive if valid_location(block)]
    missing_locations = [block for block in substantive if not valid_location(block)]

    for index, block in enumerate(missing_locations, start=1):
        output_findings.append(
            f"[RD.REVIEW.FINDING_LOCATION_MISSING] {role_file}: substantive finding "
            f"{index} has no manuscript location: `{_preview_finding(block)}`."
        )
    if verdict == "PASS" and substantive:
        output_findings.append(
            f"[RD.REVIEW.PASS_WITH_FINDINGS] {role_file}: PASS is legal only with zero findings."
        )
    if verdict == "FINDINGS" and not substantive:
        output_findings.append(
            f"[RD.REVIEW.FINDINGS_MISSING] {role_file}: FINDINGS requires at least one substantive finding."
        )

    net_delta = 0
    actions: list[str] = []
    finding_ids: list[str] = []
    for index, block in enumerate(substantive, start=1):
        action_findings, delta, action = _validate_finding_action(role_file, block, index)
        output_findings.extend(action_findings)
        id_match = _FINDING_ID_LINE_RE.search(block)
        if id_match:
            finding_ids.append(id_match.group(1).strip().upper())
        if delta is not None:
            net_delta += delta
        if action is not None:
            actions.append(action)
    if actions and "ADD" not in actions and net_delta > 0:
        output_findings.append(
            f"[RD.REVIEW.WRITING_ONLY_NET_GROWTH] {role_file}: writing-only actions have "
            f"positive aggregate Net Word Delta {net_delta}."
        )
    if len(finding_ids) != len(set(finding_ids)):
        output_findings.append(
            f"[RD.REVIEW.FINDING_ID_DUPLICATE] {role_file}: Finding IDs must be unique within the source review."
        )

    metrics = {
        "score_found": _has_identifiable_score(text),
        "review_verdict": verdict,
        "finding_candidates": len(blocks),
        "substantive_findings": len(substantive),
        "located_substantive_findings": len(valid),
        "net_word_delta": net_delta,
        "actions": actions,
        **rubric_metrics,
    }
    return output_findings, metrics

def validate_review(review_path: Path) -> dict:
    if not review_path.exists():
        return {"ok": False, "findings": ["Review file not found"]}

    text = review_path.read_text(encoding="utf-8", errors="ignore")
    findings: list[str] = []

    required_sections = [
        "Methods & Reproducibility Reviewer",
        "Contribution & Novelty Reviewer",
        "Structure & Clarity Reviewer",
        "Editor Synthesis",
    ]
    for section in required_sections:
        if section not in text:
            findings.append(f"Missing section: {section}")

    placeholders = ["[LLM:", "[FINDING REQUIRED]", "[PRIORITY REQUIRED]",
                    "[AGREEMENT REQUIRED]", "[SCORE REQUIRED]"]
    for ph in placeholders:
        if ph in text:
            findings.append(f"Unfilled placeholder: {ph}")

    # Check for evidence-status tags
    if "evidence_status" not in text.lower() and "supported" not in text.lower():
        findings.append("Review should reference evidence status for key claims")

    return {"ok": not findings, "findings": findings}


def validate_independence(review_dir: Path) -> dict:
    """Validate three outputs and diagnose textual overlap.

    Provenance independence is established by ``review_assurance.json`` context
    and digest identities, never by surface-text dissimilarity.  Similarity is
    retained only as a copied-template/cross-contamination diagnostic.
    """
    if not review_dir.is_dir():
        return {"ok": False, "findings": ["Not a directory"], "textual_diversity_score": 0}

    roles = ["methods_review_output.md", "contribution_review_output.md", "clarity_review_output.md"]
    texts: dict[str, str] = {}
    for role_file in roles:
        path = review_dir / role_file
        if not path.exists():
            return {"ok": False, "findings": [f"Missing: {role_file}"], "textual_diversity_score": 0}
        texts[role_file] = path.read_text(encoding="utf-8", errors="ignore")

    findings: list[str] = []
    warnings: list[str] = []
    integrity: dict[str, dict] = {}
    for role_file in roles:
        role_findings, role_metrics = _validate_reviewer_output(role_file, texts[role_file])
        findings.extend(role_findings)
        integrity[role_file] = role_metrics

    pairs = [(roles[0], roles[1]), (roles[0], roles[2]), (roles[1], roles[2])]
    scores: list[float] = []

    for a, b in pairs:
        sim = _review_similarity(texts[a], texts[b])
        scores.append(sim)
        if sim >= REVIEW_SIMILARITY_THRESHOLD:
            warnings.append(
                f"[RD.REVIEW.TEXTUAL_OVERLAP] {a} and {b}: Unicode 4-gram "
                f"similarity = {sim:.2f}, at or above the {REVIEW_SIMILARITY_THRESHOLD:.2f} "
                "diagnostic threshold; inspect for copied analysis or template contamination."
            )

    # Check for cross-reference contamination
    role_aliases = {
        "methods_review_output.md": ("methods reviewer", "方法评审", "方法审稿人"),
        "contribution_review_output.md": ("contribution reviewer", "贡献评审", "贡献审稿人"),
        "clarity_review_output.md": ("clarity reviewer", "结构评审", "清晰度评审"),
    }
    for role_file in roles:
        canon_text = unicodedata.normalize("NFKC", texts[role_file]).casefold()
        for other_file, aliases in role_aliases.items():
            if other_file == role_file:
                continue
            for alias in aliases:
                if alias.casefold() in canon_text:
                    findings.append(
                        f"[RD.REVIEW.CROSS_CONTAMINATION] {role_file}: references another "
                        f"reviewer's role (`{alias}`)."
                    )
                    break

    avg_sim = sum(scores) / len(scores) if scores else 0
    return {
        "ok": not findings,
        "findings": findings,
        "warnings": warnings,
        "textual_diversity_score": round(1.0 - avg_sim, 2),
        "pairwise_similarities": {f"{a} vs {b}": round(s, 4) for (a, b), s in zip(pairs, scores, strict=False)},
        "review_integrity": integrity,
    }


def venue_contract_state(out_dir: Path) -> dict[str, str]:
    """Project Venue Fit applicability from verified acquisition identities."""
    try:
        config = json.loads((out_dir / "workflow_config.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        config = {}
    if not isinstance(config, dict):
        config = {}
    scene = str(config.get("scene") or "journal").strip().lower().replace("-", "_")
    target_name = str(config.get("target_name") or "").strip()
    if not target_name:
        state = "NOT_APPLICABLE" if scene == "report_review" else "BLOCKED"
        return {
            "applicability": state,
            "target_name": "",
            "basis": (
                "report/review work declares no target venue"
                if state == "NOT_APPLICABLE"
                else "workflow_config.json declares no target_name"
            ),
        }
    try:
        from cnki_acquisition import validate_registry

        validation = validate_registry(
            out_dir,
            require_citations=False,
            check_index=False,
            require_exemplars=True,
        )
        valid_examples = (
            int(validation.stats.get("target_examples", 0) or 0)
            if validation.ok
            else 0
        )
    except (ImportError, OSError, RuntimeError, TypeError, ValueError):
        valid_examples = 0
    if valid_examples < 1:
        return {
            "applicability": "BLOCKED",
            "target_name": target_name,
            "basis": "no role-valid target-example passed the acquisition contract",
        }
    return {
        "applicability": "APPLICABLE",
        "target_name": target_name,
        "basis": "target_name plus a role-valid target-example passed the acquisition contract",
    }


def reviewer_visible_contract(text: str) -> str:
    """Return a semantic projection, not a copy of the controller contract.

    Confirmation prose and substantive field values remain visible.  Rows whose
    only purpose is machine identity/provenance are removed, and any internal ID
    embedded in a semantic row is withheld.  Reviewers therefore receive enough
    meaning to test the manuscript without gaining access to controller-owned
    Claim/Evidence/Design/Execution identities or completion state.
    """
    projected: list[str] = []
    for line in re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).splitlines():
        stripped = line.strip()
        label = ""
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if cells:
                label = re.sub(r"[`*_]", "", cells[0]).strip()
        else:
            labelled = re.match(r"^\s*(?:[-*+]\s*)?([^:：]{1,80})[:：]", line)
            if labelled:
                label = re.sub(r"[`*_]", "", labelled.group(1)).strip()
        if label and _INTERNAL_CONTRACT_METADATA_LABEL_RE.fullmatch(label):
            continue
        visible = _CLAIM_ID_RE.sub("[INTERNAL_CLAIM_ID_WITHHELD]", line)
        visible = _EVIDENCE_DESIGN_ANCHOR_RE.sub(
            "[INTERNAL_ANCHOR_ID_WITHHELD]", visible
        )
        projected.append(visible)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(projected)).strip()


def review_input_digests(out_dir: Path) -> dict[str, str]:
    """Hash every authoritative input frozen by a v2 review dispatch.

    Confirmation contracts are mandatory dispatch inputs.  Configuration,
    acquisition identity, and mapper support files are included whenever they
    exist; additions, removals, or edits after dispatch therefore require a new
    review run instead of being absorbed silently by compilation or audit.
    """
    identities: list[str] = [
        "confirmed_motivation.md",
        "confirmed_contribution.md",
    ]
    optional = [
        "workflow_config.json",
        "reference_materials/literature_registry.json",
        *REVIEW_MAPPING_INPUTS,
    ]
    identities.extend(relative for relative in optional if (out_dir / relative).is_file())
    return {
        relative: (
            hashlib.sha256((out_dir / relative).read_bytes()).hexdigest()
            if (out_dir / relative).is_file()
            else ""
        )
        for relative in identities
    }


def dispatch_review(out_dir: Path, manuscript_path: Path,
                    personas: list[ReviewerPersona] | None = None) -> dict:
    """Generate three independent reviewer prompt files for multi-agent execution."""
    prompts_dir = out_dir / "review_prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    protected_inputs = [
        out_dir / "review_assurance.json",
        out_dir / "review_findings.json",
        out_dir / "review_resolution.json",
        *(prompts_dir / output_name for output_name in REVIEW_OUTPUT_ROLE),
    ]
    existing = [path.relative_to(out_dir).as_posix() for path in protected_inputs if path.exists()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite an existing review run; archive its immutable raw outputs "
            "and canonical JSON first: " + ", ".join(existing)
        )

    if personas is None:
        personas = _default_personas("journal")

    manuscript_text = manuscript_text_content(manuscript_path)
    if not manuscript_text.strip():
        raise ValueError(f"manuscript is missing or empty: {manuscript_path}")
    resolved_manuscript = manuscript_path.resolve()
    try:
        manuscript_relative = resolved_manuscript.relative_to(out_dir.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("manuscript must resolve inside the output directory") from exc
    manuscript_sha256 = hashlib.sha256(resolved_manuscript.read_bytes()).hexdigest()
    venue_contract = venue_contract_state(out_dir)

    confirmed_contracts: dict[str, str] = {}
    for contract_name in ("confirmed_motivation.md", "confirmed_contribution.md"):
        contract_path = out_dir / contract_name
        if not contract_path.is_file():
            raise FileNotFoundError(
                f"Contribution Reviewer requires this confirmed semantic authority: {contract_path}"
            )
        confirmed_contracts[contract_name] = contract_path.read_text(
            encoding="utf-8", errors="strict"
        )
    dispatch_seed = "\n".join(
        (
            "avereth-review-dispatch/v2",
            manuscript_sha256,
            hashlib.sha256(confirmed_contracts["confirmed_motivation.md"].encode("utf-8")).hexdigest(),
            hashlib.sha256(confirmed_contracts["confirmed_contribution.md"].encode("utf-8")).hexdigest(),
            json.dumps(venue_contract, ensure_ascii=False, sort_keys=True),
        )
    )
    dispatch_input_sha256 = hashlib.sha256(dispatch_seed.encode("utf-8")).hexdigest()
    review_run_id = f"REV-{secrets.token_hex(8).upper()}"

    reviewer_configs = [
        {
            "file": "methods_reviewer.md",
            "role": "Methods & Reproducibility Reviewer",
            "role_key": "methods",
            "focus": (
                "Assess methodological clarity, reproducibility, assumption "
                "justification, experimental design, and whether material method/evidence "
                "boundaries are accurate, concentrated, and non-redundant."
            ),
            "rubric": REVIEW_RUBRICS["methods"],
        },
        {
            "file": "contribution_reviewer.md",
            "role": "Contribution & Novelty Reviewer",
            "role_key": "contribution",
            "focus": (
                "Assess novelty, significance, differentiation from prior work, "
                "evidence-to-claim strength, any activated material countervoice, and the "
                "specific reader stakes of the response while preserving design, "
                "execution, scope, adverse-result constraints, and the confirmed "
                "outcome, unit, case/material facts, predicate strength, explicit "
                "deliverable obligations, and the gap-question-answer-contribution chain."
            ),
            "rubric": REVIEW_RUBRICS["contribution"],
            "role_instruction": (
                "Recover one load-bearing fact card from the manuscript and its confirmed "
                "contract. For every voice, keep speaker, result object, predicate strength, "
                "scope, and epistemic status together with the unit, case/material facts, "
                "known relation, and remaining unknown. Do not replace the stated outcome "
                "with an adjacent construct, assume an unverified shared treatment, task, "
                "or mechanism, turn support into proof, or turn a supplied improvement into "
                "mere association without evidence. Minimum sufficient means every decisive "
                "deliverable and boundary is closed, not the shortest account; unrelated "
                "framework detail cannot compensate for an omitted "
                "original-report identity, numerical method, working-paper version/review "
                "status, exact downgrade trigger, or directly usable revision when material. "
                "Run one closure pass over final, payoff, and boundary sentences for result "
                "renaming, silent strengthening/weakening, voice mixing, or contradiction. "
                "When a statistical comparison or inferential claim is present, recover the "
                "actual estimand, comparison, point estimate, available uncertainty, and the "
                "test to which significance belongs; do not invent fields for descriptive "
                "numbers, and a within-group test does not establish a group difference, "
                "interaction, or sequence effect. "
                "Test whether its summary is fair and state the author's exact response "
                "increment. Compare the confirmed Gap Diagnosis with the manuscript's gap "
                "claim, research question, actual answer, and contribution; reject taxonomy "
                "labels, low search yield, or 'filling a gap' as substitutes for a specific "
                "evidence-grounded increment, and require reclassification or withdrawal to "
                "propagate. Verify that design/execution/scope identities and negative or "
                "cross-case results survive the framing. For a countervoice to enter the "
                "manuscript, require registered source support, the same result and analytic "
                "stage, a material change to the current claim, and discriminating evidence; "
                "otherwise keep it backstage. Zero activated manuscript countervoices is valid. "
                "For every activated material countervoice, explain how it could reproduce the "
                "same observation, name evidence that would separate the accounts, and separate "
                "what the author accepts, rejects, and leaves unresolved, then give the "
                "bounded sentence usable now. Prefer a same-outcome common cause over "
                "abstract incomparability when available. Review only the reader updates the "
                "result can actually support; zero, one, or several are valid. For each retained "
                "update, state the current default, changed action, cost or side effect, and "
                "stopping boundary. Never invent a second audience or policy relevance. When "
                "exact quotation, attribution, local context, or citation-ready text depends "
                "on location, preserve the available page, timestamp, paragraph, provision, "
                "table, or archive locator without inventing one. Do not infer novelty from "
                "novelty words or dialogue labels alone."
            ),
        },
        {
            "file": "clarity_reviewer.md",
            "role": "Structure & Clarity Reviewer",
            "role_key": "clarity",
            "focus": (
                "Assess organization, argument flow, figure/table integration, "
                "section transitions, substantive explanation, positive formulation, "
                "and revision cleanliness. Recover what happened, why it happened, how "
                "the evidence supports that explanation, and what understanding changes "
                "before assessing voice attribution, author response, and payoff."
            ),
            "rubric": REVIEW_RUBRICS["clarity"],
            "role_instruction": (
                "Use only the manuscript text embedded below, which is complete. You are not given "
                "and must not seek confirmed_motivation.md, confirmed_contribution.md, "
                "academic_prose_audit.md, dialogic_argument_map.md, configuration, or any "
                "other planning artifact. Do not consult academic_prose_audit.md, "
                "dialogic_argument_map.md, or planning files. "
                "Treat the embedded final manuscript as a clean read: do not infer or reconstruct "
                "the review process that produced it. For every load-bearing unit, first recover "
                "four answers: what happened; why it happened; how the evidence supports that "
                "explanation rather than merely accompanying it; and what understanding changes. "
                "Then recover, in this order, the research object, concrete problem, "
                "substantive answer, strongest evidence, and inference boundary. Only then "
                "test argument focus within the supplied manuscript scope: state the central question and the supported reader update "
                "in one sentence each, allowing an unresolved or negative answer. Compare these "
                "across the introduction, analysis, and conclusion; locate a substantive change "
                "of question or inference as `AP.FOCUS.DRIFT`. Where a material alternative "
                "is present in the supplied text, assess whether evidence or reasoning can "
                "distinguish it. Independently assess how the grounds support the answer; "
                "a missing inferential bridge is `AP.FOCUS.WARRANT_GAP`. "
                "Do not invent an opponent or require mutually exclusive explanations. Apply a "
                "section deletion test: what specific step in the argument, evidence assessment, "
                "or reader understanding would be lost? Flag a removable tangent as "
                "`AP.FOCUS.ORPHAN`; preserve necessary context, definitions, methods, scope, "
                "negative results, and genuine uncertainty. Flag their harmful compression as "
                "`AP.FOCUS.OVERPRUNED`. Judge the shortest sufficient argument, without word "
                "quotas or requiring multiple reviewers to agree. Then "
                "restate who says what, how the author's voice enters, how quotations/"
                "paraphrases are attributed, and why the response matters. In the abstract, "
                "introduction, core analysis/results, and conclusion, flag any unit where "
                "author intentions, refusals, framework names, simulated reviewer replies, "
                "or audit language displace the object, evidence, and substantive judgment. "
                "Apply the paragraph object test: mentally remove sentences that only say "
                "what this paper/study does or refuses to do; if the remaining unit no longer "
                "states what happened to the object, what the evidence shows, and what judgment "
                "follows, record a located finding. Name the first manuscript location where "
                "the reader learns more about what the paper refuses than about the research "
                "object or evidence; explicitly say none if no such location exists. "
                "When a negative result, contrast, disclaimer, concession, hedge, or author-intent "
                "sentence appears, classify it as a genuine negative empirical result, useful "
                "conceptual distinction, unnecessary author-intent protection, necessary scope, a "
                "real method/evidence limit, evidence-based qualification, legal/ethical boundary, "
                "or necessary author responsibility. Preserve genuine negative results, useful "
                "conceptual contrasts, and legal/ethical limits. Flag unnecessary protection and "
                "caveat-first scope that delay the substantive claim; recommend positive scope where "
                "the same boundary can be stated directly. Also flag any confidence edit that deletes "
                "a necessary boundary. Do not score the manuscript by counting negative words. "
                "Test revision cleanliness even when no reviewer is named: flag an implicit "
                "objection-concession-reply-qualification sequence, a paragraph order that mirrors "
                "comment order, repeated full boundaries, or a locally inserted definition/bridge "
                "whose terminology, reference, or logic does not connect to the surrounding unit. "
                "A clean manuscript must be understandable without revealing the sequence of comments "
                "that shaped it. "
                "Recover the live problem before and after each load-bearing unit. Flag a catalogue "
                "that merely lists positions (`AP.ARC.CATALOGUE_ONLY`), an unexplained historical or "
                "logical inevitability (`AP.ARC.FALSE_TELEOLOGY`), or a unit that leaves the problem "
                "unchanged (`AP.MOTION.NO_ADVANCE`). Judge suspense epistemically: flag an artificial "
                "withholding of an available answer (`AP.HOOK.ARTIFICIAL`) or a later answer that pays "
                "the hook without deepening the question (`AP.HOOK.NO_DEEPENING`). Flag a quotation "
                "used as ornament rather than evidence or reasoning (`AP.QUOTE.DECORATIVE`) and a "
                "unit whose sources displace the author's analytic voice (`AP.VOICE.SOURCE_DOMINATED`). "
                "At closure, distinguish a productive return from mere repetition "
                "(`AP.CLOSURE.REPETITION_ONLY`) and from an elevated conclusion unsupported by the "
                "manuscript evidence (`AP.CLOSURE.UNGROUNDED_ELEVATION`). If a title uses metaphor, "
                "allusion, wordplay, a question, or symmetry, require a body passage that explains "
                "the substantive relation; do not accept decorative resonance. Use these AP codes as "
                "the Finding `Category` when applicable. "
                "A retained risky sentence must use KEEP-WITH-MATERIAL-ANCHOR: identify the "
                "observable manuscript or evidence span, claim delta, single full-statement "
                "location, and deduplication record. The internal mapper records stable IDs later; "
                "do not request or invent them. Generic caution is not an anchor. "
                "Material countervoice dispositions may be recoverable from fair attribution, "
                "discriminating evidence, a calibrated claim, and its boundary; do not demand "
                "four explicit rebuttal slots. Treat any point you cannot recover as a located "
                "clarity finding."
            ),
        },
    ]

    file_list: list[str] = []
    for cfg in reviewer_configs:
        # Look up persona for this role
        persona = next((p for p in personas if p.role == cfg["role_key"]), None)
        persona_block = ""
        if persona and cfg["role_key"] != "clarity":
            persona_block = (
                f"## Reviewer Persona\n\n"
                f"**Venue context:** {persona.venue_context}\n\n"
                f"**Standards:** {persona.standards}\n\n"
                f"**Review style:** {persona.review_style}\n\n"
                f"Do not fabricate specific submission rules for the target venue. "
                f"Only use what is known from the research stage or user-provided materials.\n\n"
            )

        contract_block = ""
        if cfg["role_key"] == "contribution":
            contract_block = (
                "## Sanitized Confirmed Motivation Semantic Context\n\n"
                f"{reviewer_visible_contract(confirmed_contracts['confirmed_motivation.md'])}\n\n"
                "## Sanitized Confirmed Contribution Semantic Context\n\n"
                f"{reviewer_visible_contract(confirmed_contracts['confirmed_contribution.md'])}\n\n"
                "Controller-owned Claim/Evidence/Design/Execution IDs are withheld; do not "
                "invent them in the review.\n\n"
                "## Verified Venue Contract\n\n"
                f"Applicability: {venue_contract['applicability']}\n\n"
                f"Target: {venue_contract['target_name'] or 'N/A'}\n\n"
                f"Basis: {venue_contract['basis']}\n\n"
            )

        prompt = (
            f"# {cfg['role']}\n\n"
            f"{persona_block}"
            f"## Role\n\n{cfg['focus']}\n\n"
            f"**IMPORTANT:** You are an independent reviewer. Do NOT read or "
            f"reference the other reviewers' work. Your assessment must stand "
            f"entirely on its own. Do not mention what other reviewers might say.\n\n"
            f"{cfg.get('role_instruction', '')}\n\n"
            f"{WRITING_REVIEW_GUIDANCE.get(cfg['role_key'], '')}\n\n"
            f"{contract_block}"
            f"## Rubric Dimensions\n\n"
        )
        for dimension_id, label in cfg["rubric"]:
            prompt += f"- `{dimension_id}` — {label}\n"
        rubric_rows = "".join(
            f"| {dimension_id} | [APPLICABLE|NOT_APPLICABLE|BLOCKED] | [1-5 or N/A] | [substantive reason] | "
            "[manuscript section/paragraph/page/line/table/figure] |\n"
            for dimension_id, _ in cfg["rubric"]
        )
        prompt += (
            f"\n## Complete Manuscript\n\n{manuscript_text}\n\n"
            f"## Required Output Contract\n\n"
            f"1. You may include `Overall Score: N/5` as diagnostic context, but the "
            f"score is optional and never offsets a Critical or Major Finding.\n"
            f"2. Include exactly one rubric table with this exact five-column header. "
            f"Use every listed Dimension ID exactly once; do not add, rename, combine, "
            f"or omit dimensions. Use APPLICABLE only when the manuscript and authorized "
            f"inputs trigger the dimension; then give an integer Score from 1 to 5 plus a "
            f"substantive reason and manuscript location. Use NOT_APPLICABLE when the paper "
            f"does not trigger the dimension, or BLOCKED when it is applicable but the "
            f"authorized input omits the needed material; both use Score N/A and Location N/A. "
            f"Venue fit must use the exact Applicability declared in this prompt's Verified "
            f"Venue Contract; a target name or general venue impression cannot upgrade it.\n\n"
            f"| Dimension ID | Applicability | Score | Reason | Manuscript Location |\n"
            f"|---|---|---:|---|---|\n"
            f"{rubric_rows}\n"
            f"3. Write exactly one verdict line: `Review Verdict: PASS` when no material "
            f"revision is warranted, otherwise `Review Verdict: FINDINGS`. PASS with zero "
            f"findings is valid; do not invent issues to meet a count or word-length norm.\n"
            f"4. Under `## Findings`, include one `### Finding N` block for each real issue "
            f"and none for PASS. Number role-local Finding IDs as "
            f"`REV-{'MET' if cfg['role_key'] == 'methods' else 'CON' if cfg['role_key'] == 'contribution' else 'CLR'}-001`, "
            f"`-002`, and so on. Every block must contain these exact labelled lines: "
            f"`Finding ID:`, `Severity: CRITICAL|MAJOR|MINOR|OBSERVATION`, "
            f"`Confidence: HIGH|MEDIUM|LOW`, `Category:` (stable snake_case), `Location:`, "
            f"`Quoted Span:` (an exact, short manuscript span), `Issue:`, "
            f"`Reader Consequence:`, `Repair Kind: TEXT_EDIT|ADD_EVIDENCE|RERUN_ANALYSIS|REDESIGN|REOPEN_RESEARCH|NARROW_CLAIM|REMOVE_CLAIM|NO_ACTION`, "
            f"`Owner Stage: research|design|execution|build`, "
            f"`Text Action: DELETE|REPLACE|MOVE|ADD|NO_ACTION`, `Recommended Action:`, "
            f"and `Net Word Delta:`. Do not invent Claim/Evidence/Design/Execution IDs: "
            f"the internal mapper adds those identities after review. DELETE and REPLACE "
            f"cannot have positive delta; MOVE and NO_ACTION must be zero; ADD requires a "
            f"positive delta supported by a real evidence/design change, or `Repair Kind: TEXT_EDIT` "
            f"with `Owner Stage: build` and a proposed `BRIDGE`/`DEFINE` that a later expression-budget "
            f"gate must bind to an existing warrant, explanation step, or registered term. A scientific repair "
            f"must use its real repair kind and owner stage, not be disguised as wording.\n"
            f"5. Recommend: Accept / Minor Revision / Major Revision / Reject.\n"
            f"6. Write your review in clear, structured Markdown.\n\n"
            f"Write only your review. Do NOT produce other files.\n"
        )
        out_path = prompts_dir / cfg["file"]
        out_path.write_text(prompt, encoding="utf-8")
        file_list.append(str(out_path.relative_to(out_dir)))

    # Write dispatch instructions for the main Codex thread.
    dispatch_md = (
        "# Review Dispatch Instructions\n\n"
        "Launch **three isolated sub-agents in parallel** using the current Codex collaboration facility. "
        "Each agent reads only its own prompt file and the manuscript — "
        "they must NOT see each other's outputs or the other prompts.\n\n"
        "### Agent 1: Methods Reviewer\n"
        "Read `review_prompts/methods_reviewer.md` and produce `review_prompts/methods_review_output.md`\n\n"
        "### Agent 2: Contribution Reviewer\n"
        "Read `review_prompts/contribution_reviewer.md` and produce `review_prompts/contribution_review_output.md`\n\n"
        "### Agent 3: Clarity Reviewer\n"
        "Read `review_prompts/clarity_reviewer.md` and produce `review_prompts/clarity_review_output.md`\n\n"
        "### After all three complete:\n"
        "Write `review_assurance.json` as `cnki-review-assurance/v2`, using review run "
        f"`{review_run_id}`, the canonical manuscript path/SHA from `review_manifest.json`, "
        "the three real context IDs, exact prompt/output paths and SHA-256 values, each "
        "role's declared input scope, and the truthful `independent` or `single_agent` mode. "
        "Set every `isolation_declared` to true only for independent mode; set every one "
        "to false for single_agent mode. "
        "Then validate the reviewer outputs and run `review_lifecycle.py ... compile --write`. "
        "Do not hand-write Editor Synthesis or reviewer_audit.md; both are JSON-derived views.\n"
    )
    (prompts_dir / "dispatch.md").write_text(dispatch_md, encoding="utf-8")

    input_digests = review_input_digests(out_dir)
    prompt_digests = {
        relative: hashlib.sha256((out_dir / relative).read_bytes()).hexdigest()
        for relative in [*file_list, "review_prompts/dispatch.md"]
    }
    (prompts_dir / "review_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "avereth-review-dispatch/v2",
                "review_run_id": review_run_id,
                "dispatch_input_sha256": dispatch_input_sha256,
                "canonical_manuscript": manuscript_relative,
                "canonical_sha256": manuscript_sha256,
                "input_digests": input_digests,
                "prompt_digests": prompt_digests,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "status": "dispatched",
        "prompts_dir": str(prompts_dir.relative_to(out_dir)),
        "files": file_list,
        "canonical_manuscript": manuscript_relative,
        "canonical_sha256": manuscript_sha256,
        "review_run_id": review_run_id,
    }


def _load_object(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _path_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def _delta_reviewer_implementation_digest(role: str) -> str:
    """Bind dispatcher semantics and the installed/source reviewer definition."""
    paths = [Path(__file__).resolve()]
    try:
        suite_root = Path(__file__).resolve().parents[5]
    except IndexError:
        suite_root = Path()
    agent_name = DELTA_AGENT_FILENAMES.get(role)
    if agent_name:
        agent_path = suite_root / "agents" / agent_name
        if agent_path.is_file():
            paths.append(agent_path)
    projection = [
        {"path": path.name, "sha256": _path_sha256(path)}
        for path in paths
    ]
    return hashlib.sha256(
        json.dumps(projection, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _delta_role_input_digest(
    out_dir: Path,
    *,
    role: str,
    role_impact: dict,
    changed_text: str,
    full_manuscript_text: str,
    dependency_context: str,
    role_semantics: str,
) -> str:
    """Hash the exact semantic projection shown to one cycle reviewer."""
    projection = {
        "schema_version": "avereth-review-delta-input/v2",
        "role": role,
        "revision_impact": role_impact,
        "changed_units": changed_text,
        "complete_manuscript": full_manuscript_text,
        "dependency_context": dependency_context,
        "sanitized_confirmed_semantics": role_semantics,
        "reviewer_implementation_sha256": _delta_reviewer_implementation_digest(role),
    }
    return hashlib.sha256(
        json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _delta_dependency_context(out_dir: Path, impact: dict, role: str) -> str:
    if role == "clarity":
        return ""
    identity_values = {
        str(item)
        for key in (
            "affected_claim_ids", "affected_evidence_ids", "affected_design_ids",
            "affected_execution_ids"
        )
        for item in impact.get(key) or []
    }
    relative_files = ["claim_register.md", "evidence_bank.md", "writing_rationale_matrix.md"]
    if role == "methods":
        relative_files.extend(["research_design.json", "method_execution.json"])
    excerpts: list[str] = []
    for relative in relative_files:
        path = out_dir / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        selected = [line for line in text.splitlines() if not identity_values or any(value in line for value in identity_values)]
        if not selected and relative.endswith(".json"):
            selected = text.splitlines()[:80]
        if selected:
            visible = reviewer_visible_contract("\n".join(selected[:160]))
            if visible:
                excerpts.append(f"### {relative}\n" + visible)
    return "\n\n".join(excerpts)


def _next_cycle_id(out_dir: Path) -> str:
    resolution = _load_object(out_dir / "review_resolution.json")
    ids = [
        str(item.get("cycle_id") or "")
        for item in resolution.get("review_cycles") or []
        if isinstance(item, dict)
    ]
    numbers = [int(item.split("-")[-1]) for item in ids if re.fullmatch(r"RC-[0-9]{3}", item)]
    return f"RC-{(max(numbers) if numbers else 0) + 1:03d}"


def dispatch_delta_review(
    out_dir: Path,
    manuscript_path: Path,
    impact_path: Path,
    *,
    cycle_id: str | None = None,
) -> dict:
    """Generate the minimum reviewer prompt set authorized by revision impact."""
    registry = _load_object(out_dir / "review_findings.json")
    resolution = _load_object(out_dir / "review_resolution.json")
    impact = _load_object(impact_path)
    if registry.get("schema_version") != "avereth-review-findings/v3":
        raise ValueError("delta dispatch requires avereth-review-findings/v3")
    if resolution.get("schema_version") != "avereth-review-resolution/v2":
        raise ValueError("delta dispatch requires avereth-review-resolution/v2")
    if impact.get("schema_version") != "avereth-revision-impact/v1" or impact.get("preflight_status") != "PASS":
        raise ValueError("delta dispatch requires a passing avereth-revision-impact/v1")
    if hashlib.sha256(manuscript_path.read_bytes()).hexdigest() != impact.get("after_sha256"):
        raise ValueError("impact after SHA does not equal the canonical manuscript")
    resolved_cycle = cycle_id or _next_cycle_id(out_dir)
    if not re.fullmatch(r"RC-[0-9]{3}", resolved_cycle):
        raise ValueError("cycle_id must use RC-NNN")
    if any(
        isinstance(item, dict) and item.get("cycle_id") == resolved_cycle
        for item in resolution.get("review_cycles") or []
    ):
        raise FileExistsError(f"review cycle already exists: {resolved_cycle}")
    cycle_dir = out_dir / "review_prompts" / "cycles" / resolved_cycle
    if cycle_dir.exists():
        raise FileExistsError(f"cycle directory already exists: {cycle_dir}")
    full_review = bool(impact.get("full_review_required"))
    required = [str(item) for item in impact.get("required_reviewers") or []]
    if not required or any(role not in REVIEW_RUBRICS for role in required):
        raise ValueError("impact required_reviewers is empty or invalid")
    if full_review and required != ["methods", "contribution", "clarity"]:
        raise ValueError("FULL review requires methods, contribution, and clarity in canonical order")
    cycle_dir.mkdir(parents=True)

    changed_ids = [str(item) for item in impact.get("changed_unit_ids") or []]
    context_by_id = {
        str(item.get("unit_id") or ""): item
        for item in impact.get("changed_unit_context") or []
        if isinstance(item, dict)
    }
    context_blocks: list[str] = []
    for unit_id in changed_ids:
        item = context_by_id.get(unit_id) or {}
        before = item.get("before") if isinstance(item.get("before"), dict) else None
        after = item.get("after") if isinstance(item.get("after"), dict) else None
        lines = [f"### {unit_id}"]
        if before:
            lines.extend(
                [
                    f"Before [{before.get('section') or 'document'}]:",
                    str(before.get("text") or before.get("preview") or ""),
                ]
            )
        if after:
            lines.extend(
                [
                    f"After [{after.get('section') or 'document'}]:",
                    str(after.get("text") or after.get("preview") or ""),
                ]
            )
        context_blocks.append("\n".join(lines))
    changed_text = "\n\n".join(context_blocks)
    if not changed_text:
        raise ValueError("no changed manuscript unit can be recovered from the canonical manuscript")
    full_manuscript_text = manuscript_text_content(manuscript_path) if full_review else ""
    if full_review and not full_manuscript_text.strip():
        raise ValueError("full review requires a readable complete canonical manuscript")

    previous_cycles = [item for item in resolution.get("review_cycles") or [] if isinstance(item, dict)]
    role_input_digests: dict[str, str] = {}
    reused: list[str] = []
    reused_from_cycles: dict[str, str] = {}
    dispatched: list[str] = []
    prompt_digests: dict[str, str] = {}
    files: list[str] = []
    confirmed = ""
    for relative in ("confirmed_motivation.md", "confirmed_contribution.md"):
        path = out_dir / relative
        if path.is_file():
            confirmed += f"\n\n### {relative}\n{reviewer_visible_contract(path.read_text(encoding='utf-8-sig'))}"
    for role in required:
        dependency_context = _delta_dependency_context(out_dir, impact, role)
        role_semantics = confirmed if role == "contribution" else ""
        role_impact = {
            "change_classes": impact.get("change_classes") or [],
            "impact_radius": impact.get("impact_radius"),
            "full_review_required": full_review,
        }
        role_digest = _delta_role_input_digest(
            out_dir,
            role=role,
            role_impact=role_impact,
            changed_text=changed_text,
            full_manuscript_text=full_manuscript_text,
            dependency_context=dependency_context,
            role_semantics=role_semantics,
        )
        role_input_digests[role] = role_digest
        for prior in reversed(previous_cycles):
            prior_inputs = prior.get("role_input_digests") if isinstance(prior.get("role_input_digests"), dict) else {}
            prior_results = prior.get("role_results") if isinstance(prior.get("role_results"), dict) else {}
            if prior_inputs.get(role) == role_digest and prior_results.get(role) == "PASS":
                reused.append(role)
                reused_from_cycles[role] = str(prior.get("cycle_id") or "")
                break
        if role in reused:
            continue
        dispatched.append(role)
        role_code = "MET" if role == "methods" else "CON" if role == "contribution" else "CLR"
        role_rubric = "\n".join(
            f"- `{dimension_id}` — {label}"
            for dimension_id, label in REVIEW_RUBRICS[role]
        )
        scope_instruction = (
            "Review the complete canonical manuscript under your role rubric. The changed "
            "units and dependency context identify the revision trigger but do not limit the "
            "review scope. Classify every issue as UNRESOLVED_EXISTING, REVISION_REGRESSION, "
            "NEW_MATERIAL, or OPTIONAL_POLISH."
            if full_review
            else
            "Review only the changed manuscript units and the dependency context below. "
            "Do not assess or infer omitted, unchanged manuscript text. Classify every issue "
            "as UNRESOLVED_EXISTING, REVISION_REGRESSION, NEW_MATERIAL, or OPTIONAL_POLISH."
        )
        manuscript_block = (
            f"## Complete Canonical Manuscript\n\n{full_manuscript_text}\n\n"
            if full_review else ""
        )
        prompt = (
            f"# {role.title()} {'Full' if full_review else 'Incremental'} Reviewer\n\n"
            f"Cycle ID: {resolved_cycle}\n\n"
            f"Root Review Run ID: {registry.get('root_review_run_id') or registry.get('review_run_id')}\n\n"
            f"{scope_instruction} NEW_MATERIAL must explain why the root review could not reasonably "
            "have discovered it, which changed unit exposes it, and why it is blocking. OPTIONAL_POLISH "
            "is non-blocking. Do not restate an existing issue under new wording.\n\n"
            f"## Role Responsibility\n\n{DELTA_ROLE_RESPONSIBILITIES[role]}\n\n"
            f"{WRITING_REVIEW_GUIDANCE.get(role, '')}\n\n"
            f"## Role Rubric\n\n{role_rubric}\n\n"
            f"## Revision Impact Projection\n\n```json\n{json.dumps(role_impact, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## Changed Units\n\n{changed_text}\n\n"
            f"{manuscript_block}"
            f"## Dependency Closure\n\n{dependency_context or 'No additional dependency context is authorized for this role.'}\n\n"
            f"## Sanitized Confirmed Semantics\n\n{role_semantics or 'Not authorized for this role.'}\n\n"
            "## Required Output\n\n"
            "Write `Review Verdict: PASS` or `Review Verdict: FINDINGS`. For FINDINGS, use one "
            f"`### Finding N` block per issue and role-local IDs beginning `REV-{role_code}-001`. "
            "Each block must contain the strict v2 labelled lines plus `Discovery Class:`, "
            "`Related Finding Key:` (RFK-... or N/A), `Changed Unit ID:`, and "
            "`Why Newly Discoverable:` (required for NEW_MATERIAL, otherwise N/A). "
            "Do not invent internal IDs. Write only the review.\n"
        )
        prompt_rel = f"review_prompts/cycles/{resolved_cycle}/{role}_delta_reviewer.md"
        prompt_path = out_dir / prompt_rel
        prompt_path.write_text(prompt, encoding="utf-8")
        prompt_digests[prompt_rel] = hashlib.sha256(prompt_path.read_bytes()).hexdigest()
        files.append(prompt_rel)
    manifest = {
        "schema_version": "avereth-review-cycle-dispatch/v1",
        "cycle_id": resolved_cycle,
        "root_review_run_id": registry.get("root_review_run_id") or registry.get("review_run_id"),
        "batch_id": impact.get("batch_id"),
        "parent_cycle_id": previous_cycles[-1].get("cycle_id") if previous_cycles else None,
        "mode": "FULL" if full_review else "DELTA",
        "before_manuscript_sha256": impact.get("before_sha256"),
        "after_manuscript_sha256": impact.get("after_sha256"),
        "impact_path": impact_path.resolve().relative_to(out_dir.resolve()).as_posix(),
        "impact_sha256": hashlib.sha256(impact_path.read_bytes()).hexdigest(),
        "reviewed_unit_ids": changed_ids,
        "required_reviewers": required,
        "dispatched_reviewers": dispatched,
        "reused_reviewers": reused,
        "reused_from_cycles": reused_from_cycles,
        "role_input_digests": role_input_digests,
        "prompt_digests": prompt_digests,
    }
    manifest_path = cycle_dir / "review_cycle_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "dispatched", "cycle_id": resolved_cycle, "files": files, **manifest}


def validate_review_manifest(out_dir: Path, review_dir: Path, manuscript_path: Path) -> list[str]:
    manifest_path = review_dir / "review_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return ["review_manifest.json is missing or invalid; redispatch reviews for the canonical manuscript"]
    issues: list[str] = []
    if manifest.get("schema_version") != "avereth-review-dispatch/v2":
        issues.append("review manifest uses an unsupported schema")
    findings_registry: dict = {}
    try:
        findings_registry = json.loads((out_dir / "review_findings.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, TypeError):
        findings_registry = {}
    current_registry = findings_registry.get("schema_version") in {
        "avereth-review-findings/v2", "avereth-review-findings/v3"
    }
    if current_registry:
        reviewed = findings_registry.get("manuscript") or {}
        if manifest.get("canonical_manuscript") != reviewed.get("path"):
            issues.append("review manifest path no longer matches the immutable Finding registry")
        if manifest.get("canonical_sha256") != reviewed.get("sha256"):
            issues.append("review manifest SHA no longer matches the immutable Finding registry")
        if manifest.get("review_run_id") != findings_registry.get("review_run_id"):
            issues.append("review manifest review_run_id no longer matches the Finding registry")
    else:
        resolved = manuscript_path.resolve()
        try:
            relative = resolved.relative_to(out_dir.resolve()).as_posix()
        except ValueError:
            return ["canonical review manuscript is outside the output directory"]
        digest = hashlib.sha256(resolved.read_bytes()).hexdigest() if resolved.is_file() else ""
        if manifest.get("canonical_manuscript") != relative:
            issues.append("review outputs were dispatched for a different canonical manuscript path")
        if manifest.get("canonical_sha256") != digest:
            issues.append("canonical manuscript changed before Finding compilation")
    expected_inputs = review_input_digests(out_dir)
    if manifest.get("input_digests") != expected_inputs:
        resolution = _load_object(out_dir / "review_resolution.json")
        cycles = [item for item in resolution.get("review_cycles") or [] if isinstance(item, dict)]
        if not (cycles and cycles[-1].get("mode") == "FULL"):
            issues.append(
                "root review inputs changed without a current FULL review cycle"
            )
    prompt_digests = manifest.get("prompt_digests")
    if not isinstance(prompt_digests, dict) or not prompt_digests:
        issues.append("review manifest does not bind dispatched prompt files")
    else:
        for relative, expected in prompt_digests.items():
            path = out_dir / str(relative)
            actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
            if actual != expected:
                issues.append(f"dispatched review prompt changed: {relative}")
    return issues


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: StructuredReviewReport) -> str:
    lines = [
        "# Structured Peer Review",
        "",
        f"- Manuscript: `{report.manuscript_path}`",
        f"- Sections: {len(report.sections)}",
        f"- Total findings: {report.total_findings} ({report.critical_count} critical)",
        "",
        "> Each finding maps to a rationale matrix row, links to evidence status, "
        "and provides a concrete revision command — not just 'improve this'.",
        "",
    ]

    # Reviewer Personas section
    if report.reviewer_personas:
        lines.append("## Reviewer Personas")
        lines.append("")
        for p in report.reviewer_personas:
            lines.append(f"### {p.title}")
            lines.append(f"- **Context:** {p.venue_context}")
            lines.append(f"- **Standards:** {p.standards}")
            if p.red_flags:
                lines.append(f"- **Red flags:** {p.red_flags}")
            lines.append(f"- **Style:** {p.review_style}")
            lines.append("")
        if report.persona_warnings:
            lines.append("### Persona Warnings")
            lines.append("")
            for w in report.persona_warnings:
                lines.append(f"- {w}")
            lines.append("")

    lines.extend([
        "---",
        "",
    ])

    # Reviewers
    for reviewer in report.reviewers:
        lines.append(f"## {reviewer.title}")
        lines.append("")
        lines.append(f"**Focus:** {reviewer.focus}")
        lines.append("")
        lines.append("### Scoring Rubric (1-5)")
        lines.append("")
        for dim in reviewer.rubric_dimensions:
            lines.append(f"- {dim}")
        lines.append("")

        if not reviewer.findings:
            lines.append("*No findings — this reviewer has nothing to flag.*")
            lines.append("")
            lines.append("---")
            lines.append("")
            continue

        lines.append("### Findings")
        lines.append("")
        lines.append("| ID | Severity | What | Rationale Row | Evidence | Revision Command |")
        lines.append("|---|---|---|---|---|---|")
        for f in reviewer.findings:
            lines.append(
                f"| {f.id} | {f.severity} | {f.what[:80]} | {f.rationale_row or '—'} | "
                f"{f.evidence_status} | {f.revision_command[:100]} |"
            )
        lines.append("")

        for f in reviewer.findings:
            if f.severity == "OBSERVATION":
                continue
            icon = "🔴" if f.severity == "CRITICAL" else "🟡" if f.severity == "MAJOR" else "🔵"
            lines.append(f"#### {icon} {f.id}")
            lines.append("")
            lines.append(f"**Finding:** {f.what}")
            lines.append("")
            if f.rationale_row:
                lines.append(f"**Rationale matrix row:** {f.rationale_row} — compare against the planned function, "
                             "motivation link, and evidence anchor in writing_rationale_matrix.md.")
                lines.append("")
            lines.append(f"**Evidence status:** {f.evidence_status}")
            if f.evidence_detail:
                lines.append(f"  {f.evidence_detail}")
            lines.append("")
            lines.append(f"**Revision command:** {f.revision_command}")
            lines.append("")
            if f.teaching_note:
                lines.append(f"> {f.teaching_note}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Editor Synthesis
    if report.editor:
        ed = report.editor
        lines.append("## Editor Synthesis")
        lines.append("")
        lines.append("### Points of Agreement")
        lines.append("")
        for point in ed.agreement_points:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("### Points of Disagreement")
        lines.append("")
        for point in ed.disagreement_points:
            lines.append(f"- {point}")
        lines.append("")
        lines.append("### Revision Priority")
        lines.append("")
        lines.append("> Ordered by impact: fixing item 1 improves the paper more than fixing item 5.")
        lines.append("")
        for i, item in enumerate(ed.revision_priority, start=1):
            lines.append(f"{i}. {item}")
        lines.append("")
        lines.append(f"**Recommendation:** {ed.recommendation}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    manuscript_path = Path(args.manuscript) if args.manuscript else out_dir / "final_paper" / "main.tex"

    personas, persona_warnings = load_reviewer_personas(out_dir)

    if args.dispatch:
        if not manuscript_path.exists():
            print(f"Manuscript not found: {manuscript_path}", file=sys.stderr)
            return 2
        result = dispatch_review(out_dir, manuscript_path, personas)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.dispatch_delta:
        if not manuscript_path.exists():
            print(f"Manuscript not found: {manuscript_path}", file=sys.stderr)
            return 2
        if not args.impact_manifest:
            print("--dispatch-delta requires --impact-manifest", file=sys.stderr)
            return 2
        try:
            result = dispatch_delta_review(
                out_dir,
                manuscript_path,
                Path(args.impact_manifest),
                cycle_id=args.cycle_id,
            )
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.validate:
        validate_path = Path(args.validate)
        if validate_path.is_dir():
            result = validate_independence(validate_path)
            manifest_issues = validate_review_manifest(out_dir, validate_path, manuscript_path)
            if manifest_issues:
                result["ok"] = False
                result.setdefault("findings", []).extend(manifest_issues)
        else:
            result = validate_review(validate_path)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    report = generate_structured_review(out_dir, manuscript_path, personas, persona_warnings)

    if args.json:
        print(json.dumps({
            "manuscript": str(manuscript_path),
            "sections": len(report.sections),
            "total_findings": report.total_findings,
            "critical": report.critical_count,
            "reviewers": [
                {"role": r.role, "findings_count": len(r.findings)}
                for r in report.reviewers
            ],
            "reviewer_personas": [
                {"role": p.role, "title": p.title, "venue_context": p.venue_context,
                 "standards": p.standards, "review_style": p.review_style}
                for p in report.reviewer_personas
            ],
            "persona_warnings": report.persona_warnings,
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(report))

    if args.write:
        report_path = out_dir / "structured_review.md"
        report_path.write_text(to_markdown(report), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
