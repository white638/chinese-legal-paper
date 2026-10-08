#!/usr/bin/env python3
"""Adversarial regression tests for the canonical research-stage decision."""

from __future__ import annotations

import argparse
import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import ExitStack, redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import research_decision as rd  # noqa: E402
import research_feasibility as rf  # noqa: E402
import research_design_v3 as design_v3  # noqa: E402
import codex_cnki_gate as content_gate  # noqa: E402
import problem_orientation_check as orientation_gate  # noqa: E402
import topic_packet as topic_packet_gate  # noqa: E402
from test_topic_packet_recon import synthetic_recon  # noqa: E402
from avereth_core import cli as controller  # noqa: E402
from avereth_core.application.plan_service import build_plan  # noqa: E402
from avereth_core.config import validate_workflow_config  # noqa: E402
from avereth_core.legacy import workspace_migration  # noqa: E402
from avereth_core.tools import intake_wizard  # noqa: E402
from avereth_core.version import VERSION  # noqa: E402


MATRIX_HEADERS = [
    "Option",
    "Problem Orientation IDs",
    "Problem Warrant",
    "Input IDs",
    "Inductive Pattern/Anomaly",
    "Prior Lens Disclosed",
    "Theory & Assumptions",
    "Deductive Proposition",
    "Confirming Observation",
    "Disconfirming Observation",
    "Empirical-Theory Tension",
    "Iteration/Revision",
    "Collision Trace",
    "Data Feasibility",
    "Provisional Title",
    "Title Function / Claim Boundary",
    "Provisional Research Question",
    "Primary Question Type",
    "O-T-I-P-R",
    "Inference Boundary",
    "Gap Reality Check",
    "Outcome Unit & Comparison Design",
]

QUESTION_1 = "Why do otherwise similar local governments make different public investment choices?"
QUESTION_2 = "How do public reporting rules change the visibility of local investment choices?"
TITLE_1 = "Institutional pressure and divergent local investment choices"
TITLE_2 = "Reporting rules and the visibility of local investment choices"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def workflow_config(track: str = "international-ssci") -> dict:
    return {
        "schema_version": "avereth-workflow-config/v1",
        "framework_version": VERSION,
        "workflow": "build_from_materials",
        "task_profile": "topic_selection",
        "publication_track": track,
        "scene": "journal",
        "tier": "pro",
        "output_language": "en",
        "word_output": "none",
        "pdf_output": "none",
        "citation_mode": "author_year",
        "word_font_policy": "default",
        "prose_mode": "clear",
    }


def write_orientation(base: Path) -> None:
    (base / "problem_orientation.md").write_text(
        """# Problem Orientation

| Field | Content |
|---|---|
| Orientation ID | PO-01 |
| Practical encounter | Comparable local governments choose visibly different public investments. |
| Affected actors | Local officials, service users, and residents bearing fiscal risk. |
| Tension or unknown | A common incentive account does not explain the observed divergence. |
| Why it matters | The divergence changes how institutional reform should be evaluated. |
| Common-sense or imported frame at risk | Uniform incentives are often assumed to produce uniform responses. |
| What could change our mind | Comparable records showing only coding artifacts would withdraw the orientation. |
| Origin | user-provided practice observation |
| Epistemic status | provisional user-provided context |
| Researcher position and access | Public budgets and policy records are accessible, internal deliberations are not. |
| Method/data role | feasibility-only; methods and data remain subordinate to the problem. |
| Confirmation source | user message in the current task |
""",
        encoding="utf-8",
    )


def matrix_row(option: str, title: str, question: str, boundary: str) -> list[str]:
    return [
        option,
        "PO-01",
        "The unresolved divergence has independent theoretical and practical consequences.",
        "IN-01",
        "Similar formal incentives coexist with different observable choices.",
        "The institutional-incentive lens is provisional rather than treated as fact.",
        "Visibility and accountability may condition incentive effects.",
        "Higher public visibility changes which investment choices are politically useful.",
        "Visible choices should vary with reporting exposure.",
        "No variation under different reporting exposure would disconfirm the account.",
        "Uniform-incentive theory conflicts with divergent observed choices.",
        "The question was narrowed to observable institutional differences.",
        "Q-COLLISION-1; S-COLL-1; SYN-COLL-1",
        "Public budgets and reporting rules are accessible for bounded comparison.",
        title,
        "Question-led title that promises no result, mechanism, or causal conclusion.",
        question,
        "explanatory",
        "O local governments; T recent period; I investment choice; P institutional visibility; R strong conditional relation",
        boundary,
        "SYN-COLL-1 identifies an unresolved conditional claim after the strongest collision.",
        "Local-government choice is the outcome; matched institutional comparisons define the contrast.",
    ]


def write_matrix(base: Path) -> None:
    rows = [
        matrix_row("O1", TITLE_1, QUESTION_1, "Bounded to observed local governments and the registered period."),
        matrix_row("O2", TITLE_2, QUESTION_2, "Bounded to reporting-rule changes and observable public records."),
    ]
    lines = [
        "# Topic Induction-Deduction Matrix",
        "",
        "| " + " | ".join(MATRIX_HEADERS) + " |",
        "|" + "|".join("---" for _ in MATRIX_HEADERS) + "|",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
    (base / "topic_induction_deduction_matrix.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def query(query_id: str, channel: str, candidate: str = "CAND-01") -> dict:
    return {
        "query_id": query_id,
        "purpose": "collision",
        "status": "complete",
        "channel": channel,
        "query": "strongest collision search for divergent local investment choices",
        "result_count": 12,
        "candidate_ids": [candidate],
    }


def source(source_id: str, query_id: str, *, state: str = "pdf-downloaded") -> dict:
    return {
        "source_id": source_id,
        "title": f"Registered collision evidence {source_id}",
        "channel": "publisher",
        "state": state,
        "query_ids": [query_id],
        "citation_scope": "candidate-only",
        "verification": {
            "method": "pdf",
            "verified_at": "2026-08-16",
            "support_claim": "The full text establishes a directly comparable answer and identification boundary.",
        },
    }


def write_evidence(base: Path, track: str = "international-ssci") -> None:
    queries = [query("Q-COLLISION-1", "google-scholar")]
    sources = [source("S-COLL-1", "Q-COLLISION-1")]
    syntheses = [
        {
            "synthesis_id": "SYN-COLL-1",
            "candidate_ids": ["CAND-01"],
            "source_links": [{"source_id": "S-COLL-1"}],
            "adjudication": "The source supplies the strongest answer overlap but leaves a conditional claim unresolved.",
        }
    ]
    if track == "mixed":
        queries.append(query("Q-CNKI-COLLISION-1", "cnki"))
        sources.append(source("S-CNKI-COLL-1", "Q-CNKI-COLLISION-1"))
        syntheses.append(
            {
                "synthesis_id": "SYN-CNKI-COLL-1",
                "candidate_ids": ["CAND-01"],
                "source_links": [{"source_id": "S-CNKI-COLL-1"}],
                "adjudication": "The Chinese-track source tests the same bounded unresolved claim.",
            }
        )
    write_json(
        base / "reference_materials" / "literature_registry.json",
        {
            "schema_version": "cnki-acquisition/v2",
            "publication_track": track,
            "queries": queries,
            "sources": sources,
        },
    )
    write_json(
        base / "literature_analysis.json",
        {"schema_version": "cnki-literature-analysis/v2", "syntheses": syntheses},
    )


def write_commitment(base: Path, question: str = QUESTION_1) -> None:
    (base / "confirmed_motivation.md").write_text(
        f"""# Confirmed Motivation

| Field | Content |
|---|---|
| Problem Orientation IDs | PO-01 |
| Why the problem remains worth pursuing | The strongest collision leaves a consequential conditional claim unresolved. |
| Non-trivial answer test | The answer must distinguish observable implications rather than restate divergence. |
| Confirmed Research Question | {question} |
| Working Title | {TITLE_1} |
| Title Authority | user-approved-working |
| Title Function | question-led |
| Title Claim Boundary | The title does not promise a result, mechanism, concept, or causal conclusion. |
| Title Revision Rule | reconfirm-if-substantive |
| Confirmation Source | user message CONF-COMMIT |
""",
        encoding="utf-8",
    )


def question_version(question_id: str, text: str, *, status: str = "active", version: int = 1) -> dict:
    return {
        "id": question_id,
        "version": version,
        "status": status,
        "text": text,
        "primary_type": "explanatory",
        "answer_task": "Explain the registered divergence by comparing observable institutional implications.",
        "otipr": {
            "object": "local governments",
            "time": "registered recent period",
            "issue": "divergent public investment choices",
            "perspective": "institutional visibility",
            "relation": {"strength": "strong", "statement": "visibility conditions incentive effects"},
        },
        "task_fields": {"explanandum": "divergent choices", "comparison": "institutional visibility"},
        "scope": "Observed local governments and the registered period only.",
    }


def pivot_conditions(met: bool = False) -> dict:
    return {
        name: {
            "met": met,
            "evidence": "Registered materials provide a substantive adjudication for this pivot condition.",
        }
        for name in rd.PIVOT_CONDITIONS
    }


def c2_contract() -> dict:
    return {
        "collision_severity": "limited",
        "overlap_vector": {
            "object": "partial",
            "question_or_estimand": "different",
            "theory_or_mechanism": "different",
            "unit_case_time_scope": "overlapping",
            "materials_and_identification_logic": "different",
            "existing_answer": "different",
            "claimed_contribution": "different",
        },
        "unresolved_claim": "Whether institutional visibility changes the direction of incentive effects remains unresolved.",
        "severity_rationale": "The strongest source overlaps in object and scope but asks and answers a different question.",
        "adjudication": "Retain the bounded question while prohibiting claims of an entirely untouched field.",
        "disposition": "retain",
        "pivot_conditions": pivot_conditions(False),
        "decorative_difference_only": False,
    }


def c3_contract(status: str = "cleared", confirmation: str | None = "CONF-HARD-1") -> dict:
    return {
        "status": status,
        "bounded_novelty_basis": "The contribution is the unresolved conditional distinction, not the general topic.",
        "contribution_boundary": "Claims remain limited to registered cases, materials, and observable implications.",
        "non_novel_elements": ["Institutional incentives and investment choices are already studied."],
        "allowed_claims": ["The registered conditional distinction remains open to empirical adjudication."],
        "prohibited_claims": ["No claim that the topic, method, or setting is wholly unprecedented."],
        "zero_hit_claim_prohibited": True,
        "human_confirmation_ref": confirmation,
    }


def candidate_one(track: str = "international-ssci") -> dict:
    query_ids = ["Q-COLLISION-1"]
    source_ids = ["S-COLL-1"]
    synthesis_ids = ["SYN-COLL-1"]
    if track == "mixed":
        query_ids.append("Q-CNKI-COLLISION-1")
        source_ids.append("S-CNKI-COLL-1")
        synthesis_ids.append("SYN-CNKI-COLL-1")
    return {
        "id": "CAND-01",
        "topic_option_id": "O1",
        "status": "selected",
        "provisional_title": TITLE_1,
        "orientation_ids": ["PO-01"],
        "focus_rationale": "This candidate best preserves the consequential unresolved distinction and feasible evidence boundary.",
        "c0_candidate_map": {
            "disposition": "retain",
            "rationale": "Retain as primary because it combines the strongest theoretical consequence and observable test.",
        },
        "c1_collision_evidence": {
            "query_ids": query_ids,
            "source_ids": source_ids,
            "synthesis_ids": synthesis_ids,
            "strongest_collision_source_id": "S-COLL-1",
            "track_coverage": "Completed the publication-track collision search and adjudicated its strongest positive hit.",
            "checked_at": "2026-08-16",
        },
        "c2_overlap_adjudication": c2_contract(),
        "c3_novelty_clearance": c3_contract(),
        "question_versions": [question_version("CAND-01-RQ-V1", QUESTION_1)],
        "active_question_version_id": "CAND-01-RQ-V1",
    }


def candidate_two() -> dict:
    return {
        "id": "CAND-02",
        "topic_option_id": "O2",
        "status": "alternate",
        "provisional_title": TITLE_2,
        "orientation_ids": ["PO-01"],
        "focus_rationale": "Retain as an explicit alternate because it asks a distinct reporting-process question.",
        "c0_candidate_map": {
            "disposition": "defer",
            "rationale": "Defer while preserving it as a real alternative rather than an invented quota-filling option.",
        },
        "c1_collision_evidence": None,
        "c2_overlap_adjudication": None,
        "c3_novelty_clearance": None,
        "question_versions": [question_version("CAND-02-RQ-V1", QUESTION_2, status="draft")],
        "active_question_version_id": None,
    }


def write_material_feasibility(base: Path, track: str = "international-ssci") -> None:
    sample = base / "reference_materials" / "probe_samples" / "local_investment.csv"
    sample.parent.mkdir(parents=True, exist_ok=True)
    sample.write_text("government,year,visibility,investment\nA,2024,high,10\nB,2024,low,7\n", encoding="utf-8")
    sample_sha = rd.hashlib.sha256(sample.read_bytes()).hexdigest()
    write_json(
        base / "reference_materials" / "research_material_registry.json",
        {
            "schema_version": "avereth-research-material-registry/v1",
            "registry_id": "MATREG-001",
            "probe_implementation_version": "research-material-probe/v1",
            "applicability": {
                "status": "APPLICABLE",
                "rationale": "The question requires observable comparative administrative records.",
            },
            "materials": [
                {
                    "material_id": "MAT-001",
                    "material_type": "structured_dataset",
                    "source_ids": ["S-COLL-1"],
                    "material_locator": {"catalog_id": "LOCAL-INVESTMENT-TEST", "version": "2026-08"},
                    "access": {
                        "status": "VERIFIED",
                        "credential_required": False,
                        "credential_ref": None,
                        "permission_status": "NOT_REQUIRED",
                        "legal_basis": "Public administrative records",
                        "ethics_status": "NOT_REQUIRED",
                    },
                    "probes": [
                        {
                            "probe_id": "PROBE-001",
                            "performed_at": "2026-08-16T06:00:00+00:00",
                            "adapter": "tabular",
                            "status": "PASS",
                            "format": "csv",
                            "parse_status": "PASS",
                            "observed_rows": 2,
                            "observed_documents": 0,
                            "observed_fields": ["government", "year", "visibility", "investment"],
                            "key_assessment": "government and year form the comparison key",
                            "query_summary": "bounded local-government records",
                            "pagination_status": "not applicable",
                            "rate_limit_status": "not applicable",
                            "deduplication_status": "not applicable",
                            "time_coverage": {"from": 2024, "to": 2024},
                            "spatial_coverage": {"units": ["A", "B"]},
                            "unit_coverage": {"unit": "local government"},
                            "evidence_files": [
                                {
                                    "path": sample.relative_to(base).as_posix(),
                                    "sha256": sample_sha,
                                    "role": "probe-sample",
                                }
                            ],
                            "errors": [],
                        }
                    ],
                }
            ],
            "failures": [],
        },
    )
    selected = candidate_one(track)
    question = selected["question_versions"][0]
    assessment = {
        "candidate_id": "CAND-01",
        "topic_option_id": "O1",
        "question_version_id": "CAND-01-RQ-V1",
        "question_text": QUESTION_1,
        "candidate_semantic_digest": rd.feasibility_candidate_digest(selected, question),
        "required_observations": [
            "Comparable local-government investment choices",
            "Variation in observable institutional visibility",
        ],
        "material_refs": [{"material_id": "MAT-001", "probe_ids": ["PROBE-001"]}],
        "dimensions": {name: "PASS" for name in rf.DIMENSIONS},
        "critical_dimensions": [
            "actual_access",
            "legal_and_ethics",
            "coverage",
            "required_fields_or_roles",
            "variation_or_identification",
        ],
        "verdict": "PASS",
        "allowed_question_boundary": {
            "statement": "Claims are limited to the observed local governments and registered period.",
            "allowed_claim_types": ["descriptive", "association"],
            "time_scope": "2024",
            "spatial_scope": "registered local governments A and B",
            "unit_scope": "local government",
            "required_fields_or_roles": ["government", "year", "visibility", "investment"],
            "material_ids": ["MAT-001"],
        },
        "fallbacks": [],
        "rationale": "The verified sample contains the units, fields, and variation required by the bounded question.",
        "assessed_at": "2026-08-16T07:00:00+00:00",
    }
    feasibility = {
        "schema_version": rf.SCHEMA_VERSION,
        "feasibility_id": "FEAS-001",
        "status": "PASS",
        "selected_candidate_id": "CAND-01",
        "question_version_id": "CAND-01-RQ-V1",
        "candidate_assessments": [assessment],
        "selected_assessment_digest": None,
        "material_basis_digest": None,
        "basis_digest": None,
        "invalidation_archive": [],
    }
    live, issues = rf.selected_live_basis(base, feasibility)
    if issues:
        raise AssertionError(issues)
    feasibility["selected_assessment_digest"] = live["selected_assessment_digest"]
    feasibility["material_basis_digest"] = live["material_basis_digest"]
    feasibility["basis_digest"] = live["basis_digest"]
    write_json(base / "research_feasibility.json", feasibility)


def cleared_payload(base: Path, track: str = "international-ssci") -> dict:
    payload = {
        "schema_version": rd.SCHEMA_VERSION,
        "decision_id": "RDEC-001",
        "decision_version": 1,
        "disposition": "cleared",
        "selected_candidate_id": "CAND-01",
        "no_automatic_replacement": True,
        "clearance_basis_digest": None,
        "selected_candidate_subgraph": {},
        "selected_candidate_subgraph_digest": rd.canonical_digest({}),
        "confirmed_motivation_ref": None,
        "soft_focus_confirmation": {
            "confirmation_id": "CONF-FOCUS-1",
            "status": "confirmed",
            "source": "user message selecting the primary and alternate",
            "confirmed_at": "2026-08-16T08:00:00+00:00",
            "primary_candidate_id": "CAND-01",
            "alternate_candidate_ids": ["CAND-02"],
        },
        "hard_clearance_confirmation": None,
        "withdrawal_confirmation": None,
        "confirmation_archive": [],
        "historical_commitment_disposition": None,
        "candidates": [candidate_one(track), candidate_two()],
        "question_challenges": [],
    }
    self_issues = rd.bind_selected_candidate_subgraph(base, payload)
    if self_issues:
        raise AssertionError(self_issues)
    payload["hard_clearance_confirmation"] = {
        "confirmation_id": "CONF-HARD-1",
        "status": "confirmed",
        "source": "user message approving bounded novelty clearance",
        "confirmed_at": "2026-08-17T08:00:00+00:00",
        "candidate_id": "CAND-01",
        "question_version_id": "CAND-01-RQ-V1",
        "basis_sha256": payload["clearance_basis_digest"],
    }
    self_issues = rd.bind_selected_candidate_subgraph(base, payload)
    if self_issues:
        raise AssertionError(self_issues)
    return payload


def make_workspace(base: Path, track: str = "international-ssci") -> dict:
    config = workflow_config(track)
    config["task_profile"] = "research_design"
    write_json(base / "workflow_config.json", config)
    write_orientation(base)
    write_matrix(base)
    write_evidence(base, track)
    write_material_feasibility(base, track)
    write_commitment(base)
    return cleared_payload(base, track)


def direction_contract(track: str = "international-ssci") -> dict:
    return {
        "current_user_goal": "Generate a direction-led portfolio before choosing one topic.",
        "field": "public administration",
        "core_problem": "Explain divergent public choices under apparently similar institutions.",
        "preferred_contribution": ["mechanism", "scope condition"],
        "object_scope": "Local governments and public institutions in comparable settings.",
        "must_preserve": ["problem-led topic formation"],
        "must_avoid": ["dataset-led title variants"],
        "acceptable_adjacency": "medium",
        "publication_track": track,
        "method_role": "open",
        "workspace_role": "optional-after-divergence",
        "authority": "current-user-request",
    }


def topic_workflow_config(track: str = "international-ssci") -> dict:
    config = workflow_config(track)
    config["topic_selection"] = {
        "origin_mode": "direction_first",
        "brainstorm_depth": "broad",
        "workspace_policy": "quarantine_until_divergence",
    }
    config["direction_contract"] = direction_contract(track)
    return config


def intake_args(*, materials_dir: str, origin_mode: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(
        output_dir=Path("paper_rewriting_output"),
        workflow="build_from_materials",
        task_profile="topic_selection",
        publication_track="international-ssci",
        scene="journal",
        tier="pro",
        output_language="en",
        word_output="none",
        pdf_output="none",
        word_font_policy="default",
        citation_mode="author_year",
        prose_mode="clear",
        translation_package="none",
        translation_source="",
        translation_coverage_source="",
        submission_package="none",
        submission_source_dir="",
        submission_contract="",
        submission_required_file=[],
        response_package="none",
        response_source_dir="",
        response_review_source="",
        response_required_file=[],
        target_name="",
        canonical_manuscript="",
        materials_dir=materials_dir,
        draft_path="",
        user_motivation="Generate several serious topic directions before selection.",
        special_requirement=[],
        topic_origin_mode=origin_mode,
        brainstorm_depth=None,
        current_user_goal="Generate several serious topic directions before selection.",
        direction_field="public administration",
        core_problem="Explain divergent public choices under similar institutions.",
        preferred_contribution=["mechanism"],
        object_scope="Comparable local governments and public institutions.",
        must_preserve=["problem-led topic formation"],
        must_avoid=["dataset-led title variants"],
        acceptable_adjacency="medium",
        method_role="open",
        no_interactive=True,
    )


def _portfolio_candidate(index: int, *, finalist: bool, selected: bool) -> dict:
    profiles = {
        1: {
            "family": "incentive-visibility",
            "question": QUESTION_1,
            "signature": {
                "research_object": "municipal investment authorities",
                "phenomenon": "divergent investment choices under comparable incentives",
                "mechanism_or_tension": "institutional visibility changes incentive interpretation",
                "unit_of_analysis": "local government decision episode",
                "temporal_logic": "contemporaneous institutional comparison",
                "contribution_type": "conditional mechanism explanation",
                "evidence_logic": "comparative observable implications",
            },
        },
        2: {
            "family": "reporting-process",
            "question": QUESTION_2,
            "signature": {
                "research_object": "administrative reporting chains",
                "phenomenon": "selective escalation of adverse implementation signals",
                "mechanism_or_tension": "career protection conflicts with accurate upward reporting",
                "unit_of_analysis": "bureaucratic reporting event",
                "temporal_logic": "signal movement across sequential review levels",
                "contribution_type": "organizational process explanation",
                "evidence_logic": "within-process trace comparison",
            },
        },
        3: {
            "family": "cross-level-accountability",
            "question": "When do citizen complaints alter agency priorities rather than remain symbolic participation?",
            "signature": {
                "research_object": "complaint-handling agencies and citizen claimants",
                "phenomenon": "unequal translation of complaints into agency priorities",
                "mechanism_or_tension": "participatory responsiveness conflicts with organizational triage",
                "unit_of_analysis": "citizen-agency claim episode",
                "temporal_logic": "feedback from complaint intake to agenda revision",
                "contribution_type": "cross-level accountability mechanism",
                "evidence_logic": "linked claimant and organizational process evidence",
            },
        },
        4: {
            "family": "historical-layering",
            "question": "How does institutional layering produce durable implementation differences after formal rules converge?",
            "signature": {
                "research_object": "administrative systems with convergent formal rules",
                "phenomenon": "persistent implementation divergence after legal harmonization",
                "mechanism_or_tension": "new rules interact with inherited organizational routines",
                "unit_of_analysis": "institutional development sequence",
                "temporal_logic": "historical layering across reform periods",
                "contribution_type": "process account of institutional persistence",
                "evidence_logic": "comparative historical sequence evidence",
            },
        },
        5: {
            "family": "concept-measurement",
            "question": "Which forms of administrative burden are obscured when compliance is measured only by completion rates?",
            "signature": {
                "research_object": "public service users facing compliance requirements",
                "phenomenon": "hidden burdens despite apparently successful completion",
                "mechanism_or_tension": "completion metrics conceal learning and psychological costs",
                "unit_of_analysis": "individual service-use encounter",
                "temporal_logic": "burden accumulation across application stages",
                "contribution_type": "conceptual and measurement reconstruction",
                "evidence_logic": "item-level construct and process validation",
            },
        },
        6: {
            "family": "negative-case",
            "question": "Why do some high-capacity agencies fail to coordinate during routine cross-boundary crises?",
            "signature": {
                "research_object": "high-capacity agencies in cross-boundary crises",
                "phenomenon": "coordination failure despite abundant formal capacity",
                "mechanism_or_tension": "jurisdictional ownership undermines available coordination resources",
                "unit_of_analysis": "interagency crisis response",
                "temporal_logic": "coordination breakdown during escalation",
                "contribution_type": "negative-case theory correction",
                "evidence_logic": "deviant-case process tracing",
            },
        },
        7: {
            "family": "policy-feedback-boundary",
            "question": "Under what conditions does repeated policy contact weaken rather than strengthen institutional trust?",
            "signature": {
                "research_object": "recurring beneficiaries of public programs",
                "phenomenon": "declining trust after repeated policy contact",
                "mechanism_or_tension": "benefit receipt conflicts with perceived procedural disrespect",
                "unit_of_analysis": "person-program relationship",
                "temporal_logic": "cumulative feedback across repeated encounters",
                "contribution_type": "boundary condition for policy feedback theory",
                "evidence_logic": "longitudinal within-person comparison",
            },
        },
    }
    profile = profiles[index]
    if index == 1:
        candidate = candidate_one()
    elif index == 2:
        candidate = candidate_two()
    else:
        question = profile["question"]
        candidate = {
            "id": f"CAND-{index:02d}",
            "topic_option_id": f"O{index}",
            "status": "alternate",
            "provisional_title": question.rstrip("?"),
            "orientation_ids": ["PO-01"],
            "focus_rationale": "Retain as a substantively different screened problem, not a title or dataset variant.",
            "c0_candidate_map": {
                "disposition": "defer",
                "rationale": "Keep screened until the portfolio comparison identifies the strongest finalists.",
            },
            "c1_collision_evidence": None,
            "c2_overlap_adjudication": None,
            "c3_novelty_clearance": None,
            "question_versions": [
                question_version(f"CAND-{index:02d}-RQ-V1", question, status="draft")
            ],
            "active_question_version_id": None,
        }
    question_text = candidate["question_versions"][0]["text"]
    nearest = 2 if index == 1 else 1
    candidate.update(
        {
            "maturity": "selected" if selected else "finalist" if finalist else "screened",
            "seed_ids": [f"SEED-{index:02d}"],
            "generation_lane": "direction_only",
            "candidate_family": profile["family"],
            "portfolio_bucket": (
                "high-risk-high-reward"
                if index == 3
                else "adjacent-extension"
                if index in {2, 5}
                else "core-fit"
            ),
            "research_question": question_text,
            "direction_fit": {
                "topic": {
                    "verdict": "strong",
                    "basis": ["current_user_goal", "field"],
                    "rationale": "The candidate remains inside the authorized public-administration topic direction.",
                },
                "problem": {
                    "verdict": "strong" if index in {1, 2, 3} else "moderate",
                    "basis": ["core_problem", "object_scope"],
                    "rationale": "The candidate preserves the focal explanatory problem and authorized object scope.",
                },
                "contribution": {
                    "verdict": "strong",
                    "basis": ["preferred_contribution", "publication_track"],
                    "rationale": "The proposed answer advances the requested explanatory contribution on the declared track.",
                },
                "trajectory": {
                    "verdict": "strong" if index in {1, 2, 3} else "moderate",
                    "basis": ["acceptable_adjacency", "method_role"],
                    "rationale": "The candidate remains on an authorized research trajectory without material anchoring.",
                },
            },
            "workspace_relation": {
                "role": "incidental",
                "ablation_result": "survives",
                "anchor_risk": "low",
                "rationale": "The question remains coherent when all workspace materials are removed.",
                "material_refs": [],
            },
            "semantic_signature": profile["signature"],
            "potential_contribution": (
                f"Candidate {index} could revise how public-administration theory "
                "explains the focal institutional response."
            ),
            "largest_uncertainty_or_failure_risk": (
                f"Candidate {index} may fail if its proposed explanatory tension "
                "does not survive direct comparison with the nearest alternative."
            ),
            "why_worth_deep_review": (
                f"Candidate {index} merits deep review because the answer would "
                "change both the explanatory claim and its observable implications."
            ),
            "distinctness": {
                "nearest_candidate_id": f"CAND-{nearest:02d}",
                "difference_dimensions": ["phenomenon", "mechanism_or_tension"],
                "rationale": "The nearest option asks about a different phenomenon and explanatory tension.",
            },
        }
    )
    return candidate


def activate_topic_portfolio(base: Path, payload: dict, *, cleared: bool = True) -> dict:
    config = topic_workflow_config()
    write_json(base / "workflow_config.json", config)
    packet = topic_packet_gate.build_packet(
        config,
        current_user_request="Generate a broad direction-led topic portfolio for public administration.",
        compiled_at="2026-08-15T08:00:00+00:00",
        literature_reconnaissance=synthetic_recon(),
    )
    seeds = [
        {
            "seed_id": f"SEED-{index:02d}",
            "candidate_family": f"problem-family-{((index - 1) % 7) + 1}",
            "problem": f"Problem seed {index} explains a distinct consequential public-choice pattern.",
            "anomaly_or_unknown": f"Unknown pattern {index} survives the initial direction-only comparison.",
            "why_it_matters": f"Resolving seed {index} changes the explanation of institutional response.",
            "potential_disconfirmation": f"Evidence pattern {index} would disconfirm this problem framing.",
        }
        for index in range(1, 13)
    ]
    scheduler = topic_packet_gate.TopicGenerationScheduler._for_test(
        packet,
        test_capture=lambda _bounded_input: json.dumps(seeds, ensure_ascii=False),
        test_run_id="topic-generation-run-01",
        test_model_revision="test-model-revision",
        test_context_id="direction-generator-A",
    )
    receipt = scheduler.run(
        lane_id="core_mechanism_boundary",
        dispatched_at="2026-08-15T08:40:00+00:00",
        issued_at="2026-08-15T08:50:00+00:00",
    )
    seal = scheduler.seal(
        generation_receipts=[receipt],
        sealed_at="2026-08-15T09:00:00+00:00",
    )
    candidates = [
        _portfolio_candidate(
            index,
            finalist=index in {1, 2},
            selected=cleared and index == 1,
        )
        for index in range(1, 8)
    ]
    presented_ids = [f"CAND-{index:02d}" for index in range(1, 8)]
    assignments = {candidate_id: [] for candidate_id in presented_ids}
    seed_dispositions = []
    for index in range(1, 13):
        candidate_id = f"CAND-{((index - 1) % 7) + 1:02d}"
        seed_id = f"SEED-{index:02d}"
        assignments[candidate_id].append(seed_id)
        seed_dispositions.append(
            {
                "seed_id": seed_id,
                "disposition": "retain" if index <= 7 else "merge",
                "candidate_id": candidate_id,
                "rationale": "This sealed seed either anchors or substantively augments the assigned candidate core.",
            }
        )
    for candidate in candidates:
        candidate["seed_ids"] = assignments[candidate["id"]]
    screening_output = {
        "seed_dispositions": seed_dispositions,
        "candidate_cores": [rd.candidate_screened_core(item) for item in candidates],
    }
    screening_scheduler = rd.TopicScreeningScheduler._for_test(
        packet,
        seal,
        test_capture=lambda _bounded_input: json.dumps(
            screening_output,
            ensure_ascii=False,
        ),
        test_run_id="topic-screening-run-01",
        test_model_revision="test-screening-model",
        test_context_id="controlled-screening-context",
    )
    screening_receipt = screening_scheduler.run(
        issued_at="2026-08-15T09:10:00+00:00",
    )
    pair_reviews = [
        {
            "left_candidate_id": left,
            "right_candidate_id": right,
            "relation": "load-bearing-distinct",
            "difference_dimensions": ["phenomenon", "mechanism_or_tension"],
            "rationale": "The bounded questions address different phenomena and explanatory tensions, not a numbered, geographic, temporal, data, or method variant.",
        }
        for left_index, left in enumerate(presented_ids)
        for right in presented_ids[left_index + 1 :]
    ]
    semantic_scheduler = rd.TopicSemanticReviewScheduler._for_test(
        test_capture=lambda _bounded_input: json.dumps(
            pair_reviews,
            ensure_ascii=False,
        ),
        test_run_id="topic-semantic-review-run-01",
        test_model_revision="test-semantic-review-model",
        test_context_id="independent-semantic-review-context",
    )
    semantic_receipt = semantic_scheduler.run(
        candidates=candidates,
        presented_candidate_ids=presented_ids,
        direction_contract=config["direction_contract"],
        issued_at="2026-08-15T09:45:00+00:00",
    )
    payload["candidates"] = candidates
    payload["exploration"] = {
        "schema_version": "avereth-topic-exploration/v1",
        "topic_packet": packet,
        "seed_seal": seal,
        "screening_receipt": screening_receipt,
        "workspace_materials_admitted_at": "2026-08-15T09:30:00+00:00",
        "attempted_families": [f"problem-family-{index}" for index in range(1, 8)],
        "presented_candidate_ids": presented_ids,
        "material_opportunity_candidate_ids": [],
        "material_discovery_receipts": [],
        "finalist_candidate_ids": ["CAND-01", "CAND-02"],
        "semantic_review_receipt": semantic_receipt,
        "portfolio_audit": {
            "status": "PASS",
            "audited_at": "2026-08-15T10:00:00+00:00",
            "candidate_count": 7,
            "family_count": 7,
            "main_candidate_count": 7,
            "material_branch_candidate_count": 0,
            "semantic_review_receipt_sha256": semantic_receipt["receipt_sha256"],
        },
        "decision_roles": {
            "most_robust": "CAND-01",
            "most_balanced": "CAND-02",
            "highest_originality": "CAND-03",
        },
        "narrow_direction_exemption": None,
    }
    if not cleared:
        payload["disposition"] = "pending"
        payload["soft_focus_confirmation"] = None
        payload["hard_clearance_confirmation"] = None
    bind_issues = rd.bind_selected_candidate_subgraph(base, payload)
    if bind_issues:
        raise AssertionError(bind_issues)
    if cleared:
        payload["hard_clearance_confirmation"]["basis_sha256"] = payload[
            "clearance_basis_digest"
        ]
        bind_issues = rd.bind_selected_candidate_subgraph(base, payload)
        if bind_issues:
            raise AssertionError(bind_issues)
    return payload


def refresh_semantic_review(
    payload: dict,
    *,
    overrides: dict[tuple[str, str], str] | None = None,
) -> None:
    exploration = payload["exploration"]
    presented_ids = sorted(
        {
            *exploration["presented_candidate_ids"],
            *exploration["material_opportunity_candidate_ids"],
        }
    )
    overrides = {
        tuple(sorted(key)): value for key, value in (overrides or {}).items()
    }
    pairs = []
    for left_index, left in enumerate(presented_ids):
        for right in presented_ids[left_index + 1 :]:
            relation = overrides.get((left, right), "load-bearing-distinct")
            pairs.append(
                {
                    "left_candidate_id": left,
                    "right_candidate_id": right,
                    "relation": relation,
                    "difference_dimensions": (
                        ["phenomenon", "mechanism_or_tension"]
                        if relation == "load-bearing-distinct"
                        else []
                    ),
                    "rationale": (
                        "Independent review finds the two bounded questions equivalent despite superficial numbering or synonymous wording."
                        if relation == "equivalent"
                        else "Independent review finds different phenomena and explanatory tensions in the bounded questions."
                    ),
                }
            )
    scheduler = rd.TopicSemanticReviewScheduler._for_test(
        test_capture=lambda _bounded_input: json.dumps(pairs, ensure_ascii=False),
        test_run_id="refreshed-semantic-review-run",
        test_model_revision="test-semantic-review-model",
        test_context_id="refreshed-independent-semantic-context",
    )
    receipt = scheduler.run(
        candidates=payload["candidates"],
        presented_candidate_ids=presented_ids,
        direction_contract=exploration["topic_packet"]["direction_contract"],
        issued_at="2026-08-15T09:46:00+00:00",
    )
    exploration["semantic_review_receipt"] = receipt
    exploration["portfolio_audit"]["semantic_review_receipt_sha256"] = receipt[
        "receipt_sha256"
    ]
    exploration["portfolio_audit"]["candidate_count"] = len(presented_ids)
    exploration["portfolio_audit"]["family_count"] = len(
        {
            item["candidate_family"]
            for item in payload["candidates"]
            if item["id"] in presented_ids
        }
    )
    exploration["portfolio_audit"]["main_candidate_count"] = len(
        exploration["presented_candidate_ids"]
    )
    exploration["portfolio_audit"]["material_branch_candidate_count"] = len(
        exploration["material_opportunity_candidate_ids"]
    )


def codes(result: rd.ValidationResult) -> set[str]:
    return {item.code for item in result.errors}


class FakeDesignResult:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, code: str, severity: str, message: str, path: str) -> None:
        self.rows.append((code, severity, message, path))


class ResearchDecisionTests(unittest.TestCase):
    def test_screening_focus_requires_decisive_reasons_in_existing_fields(self) -> None:
        for origin in sorted(topic_packet_gate.ORIGIN_MODES):
            with self.subTest(origin=origin):
                prompt = rd.screening_prompt({"origin_mode": origin}, {})
                for instruction in (
                    "Make a non-compensatory judgment",
                    "do not average scores",
                    "In each seed disposition rationale, give the decisive reason",
                    "In why_worth_deep_review, explain which consequential judgment remains open",
                    "In largest_uncertainty_or_failure_risk, identify the weakest load-bearing link",
                    "A tractable but unresolved check can justify deeper review",
                    "Preserve descriptive, historical, normative, and synthesis questions",
                    "compatible explanations may coexist",
                    "drop seeds whose load-bearing direction fit is weak or unsupported",
                ):
                    self.assertIn(instruction, prompt)
                self.assertNotIn("return weak or uncertain", prompt)
                self.assertEqual(
                    "avereth-topic-screening-protocol/v2",
                    rd.screening_protocol({"origin_mode": origin})["schema_version"],
                )

    def test_legacy_screening_prompt_and_protocol_hashes_remain_exact(self) -> None:
        cases = (
            ("direction_first", False,
             "2184aa728c9ec702d31c5ac884ddcf16da019f38e2125800c300cd0555a81a64",
             "74657fb80e15585bcb0255c6a8287bd6fd819ba13d1a5164ce2f04aedd9ee6ed"),
            ("direction_first", True,
             "c2c5834bc59ec1e9d9bbd48150da103b807f9d5e6adc840f1be39d5f88aaee02",
             "74657fb80e15585bcb0255c6a8287bd6fd819ba13d1a5164ce2f04aedd9ee6ed"),
            ("material_opportunity", False,
             "866c9654bce087d795c0149f9fb9cde92e206d9514ac6bd39a5a89f371c300fc",
             "1c274d144604aa036df62883cf9f9bce3f2223666282b7dd030d493ace361964"),
            ("phenomenon_first", True,
             "d0cedbee9dd10ddc14ba2ab184dba9497da7e323dd43e43bd792b9835acc2fe7",
             "1c274d144604aa036df62883cf9f9bce3f2223666282b7dd030d493ace361964"),
        )
        for origin, with_recon, prompt_sha, protocol_sha in cases:
            with self.subTest(origin=origin, recon=with_recon):
                packet = {"origin_mode": origin}
                if with_recon:
                    packet[topic_packet_gate.RECON_INPUT_KEY] = synthetic_recon()
                seal = {
                    "packet_sha256": "b" * 64,
                    "sealed_at": "2026-08-15T09:00:00Z",
                    "seed_portfolio_sha256": "c" * 64,
                    "seeds": [],
                }
                version = rd.LEGACY_SCREENING_PROTOCOL_SCHEMA_VERSION
                prompt = rd.screening_prompt(packet, seal, protocol_version=version)
                self.assertEqual(prompt_sha, rd.hashlib.sha256(prompt.encode("utf-8")).hexdigest())
                self.assertEqual(
                    protocol_sha,
                    rd.canonical_digest(rd.screening_protocol(packet, protocol_version=version)),
                )
                self.assertNotEqual(prompt, rd.screening_prompt(packet, seal))

    def test_signed_legacy_topic_receipts_remain_readable_and_cannot_change_protocol(self) -> None:
        def legacy_default(function, version):
            def call(*args, **kwargs):
                kwargs.setdefault("protocol_version", version)
                return function(*args, **kwargs)
            return call

        for origin in ("direction_first", "material_opportunity"):
            with self.subTest(origin=origin), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                config = topic_workflow_config()
                config["topic_selection"]["origin_mode"] = origin
                config["topic_selection"]["brainstorm_depth"] = "focused"
                config["direction_contract"]["workspace_role"] = (
                    topic_packet_gate.WORKSPACE_ROLE_BY_ORIGIN[origin]
                )
                scope = []
                if origin != "direction_first":
                    config["topic_selection"]["workspace_policy"] = "declared_source_from_start"
                    scope = ["source.txt"]
                    (base / "source.txt").write_text("Synthetic bounded material.", encoding="utf-8")
                packet = topic_packet_gate.build_packet(
                    config,
                    current_user_request="Identify the consequential unknown in institutional responses.",
                    compiled_at="2026-08-15T08:00:00Z",
                    declared_workspace_scope=scope,
                    literature_reconnaissance=synthetic_recon(),
                )
                core = rd.candidate_screened_core(_portfolio_candidate(1, finalist=False, selected=False))
                core["generation_lane"] = rd.generation_lane_for_origin(origin)
                seeds = [{
                    "seed_id": "SEED-01",
                    "candidate_family": core["candidate_family"],
                    "problem": core["research_question"],
                    "anomaly_or_unknown": "The recorded institutional comparison leaves the response pattern unresolved.",
                    "why_it_matters": "Resolving this unknown changes the scope of the institutional explanation.",
                    "potential_disconfirmation": "A comparable historical record could require revising the proposed boundary.",
                }]
                output = {
                    "seed_dispositions": [{
                        "seed_id": "SEED-01", "disposition": "retain", "candidate_id": "CAND-01",
                        "rationale": "The consequential unresolved boundary has a feasible comparative check.",
                    }],
                    "candidate_cores": [core],
                }
                with ExitStack() as stack:
                    for module, names, version in (
                        (topic_packet_gate, ("generation_protocol", "canonical_generation_prompt"),
                         topic_packet_gate.LEGACY_GENERATION_PROTOCOL_SCHEMA_VERSION),
                        (rd, ("screening_protocol", "screening_input_projection", "screening_prompt"),
                         rd.LEGACY_SCREENING_PROTOCOL_SCHEMA_VERSION),
                    ):
                        for name in names:
                            stack.enter_context(mock.patch.object(
                                module, name, legacy_default(getattr(module, name), version)
                            ))
                    generation = topic_packet_gate.TopicGenerationScheduler._for_test(
                        packet, workspace_root=base, test_capture=lambda _input: json.dumps(seeds)
                    )
                    receipt = generation.run(
                        lane_id="core_problem", dispatched_at="2026-08-15T08:40:00Z",
                        issued_at="2026-08-15T08:50:00Z",
                    )
                    seal = generation.seal(
                        generation_receipts=[receipt], sealed_at="2026-08-15T09:00:00Z"
                    )
                    screening = rd.TopicScreeningScheduler._for_test(
                        packet, seal, workspace_root=base,
                        test_capture=lambda _input: json.dumps(output),
                    )
                    screening_receipt = screening.run(issued_at="2026-08-15T09:10:00Z")

                before = copy.deepcopy((packet, seal, screening_receipt))
                materials = topic_packet_gate.declared_material_projection(packet, base)
                for projection in (None, materials):
                    self.assertEqual([], topic_packet_gate.validate_generation_receipt(
                        packet, receipt, verification_key=generation._signing_key,
                        material_projection=projection,
                    ))
                self.assertEqual([], topic_packet_gate.validate_seed_seal(
                    packet, seal, material_projection=materials
                ))
                self.assertEqual([], rd.validate_screening_receipt(packet, seal, screening_receipt)[0])
                self.assertEqual(before, (packet, seal, screening_receipt))

                current_generation_sha = topic_packet_gate.canonical_digest(
                    topic_packet_gate.generation_protocol(packet)
                )
                current_screening_sha = rd.canonical_digest(rd.screening_protocol(packet))
                self.assertNotEqual(current_generation_sha, receipt["protocol_sha256"])
                self.assertNotEqual(current_screening_sha, screening_receipt["protocol_sha256"])
                for protocol_sha in (current_generation_sha, "0" * 64):
                    changed = {**receipt, "protocol_sha256": protocol_sha}
                    issues = topic_packet_gate.validate_generation_receipt(
                        packet, changed, verification_key=generation._signing_key,
                        material_projection=materials,
                    )
                    self.assertTrue(any("prompt_sha256" in item or "unsupported" in item for item in issues), issues)
                for protocol_sha in (current_screening_sha, "0" * 64):
                    changed = {**screening_receipt, "protocol_sha256": protocol_sha}
                    issues, _ = rd.validate_screening_receipt(packet, seal, changed)
                    self.assertIn("screening input digest is stale", issues)
                    self.assertIn("screening prompt digest is stale", issues)

                current_dispatch = topic_packet_gate.build_generation_dispatch(
                    packet, lane_id="core_problem", run_id="current-run",
                    model_revision="current-model", context_id="current-context",
                    dispatched_at="2026-08-15T09:20:00Z", material_projection=materials,
                )
                self.assertEqual(current_generation_sha, current_dispatch["protocol_sha256"])
                current_screening = rd.TopicScreeningScheduler._for_test(
                    packet, seal, workspace_root=base,
                    test_capture=lambda _input: json.dumps(output),
                    test_context_id="current-screening-context",
                ).run(issued_at="2026-08-15T09:20:00Z")
                self.assertEqual(current_screening_sha, current_screening["protocol_sha256"])
                self.assertEqual([], rd.validate_screening_receipt(packet, seal, current_screening)[0])

    @staticmethod
    def _legacy_topic_packet() -> dict:
        packet = topic_packet_gate.build_packet(
            topic_workflow_config(),
            current_user_request="Generate a direction-led topic portfolio.",
            compiled_at="2026-08-15T08:00:00+00:00",
            literature_reconnaissance=synthetic_recon(),
        )
        packet.pop(topic_packet_gate.RECON_INPUT_KEY)
        packet["allowed_inputs"].remove(topic_packet_gate.RECON_INPUT_KEY)
        packet["packet_sha256"] = topic_packet_gate.canonical_digest(
            topic_packet_gate.packet_projection(packet)
        )
        return json.loads(json.dumps(packet))

    def test_legacy_packet_cannot_start_a_screening_host_run(self) -> None:
        packet = self._legacy_topic_packet()
        self.assertEqual([], topic_packet_gate.validate_packet(packet))
        with mock.patch.object(rd, "run_codex_exec_isolated") as host_run:
            with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                rd.TopicScreeningScheduler.from_codex_exec(
                    packet, {}, model_revision="fixture-model",
                    key_store=topic_packet_gate.TopicSchedulerKeyStore(),
                )
            host_run.assert_not_called()

    def test_legacy_packet_cannot_start_a_material_discovery_host_run(self) -> None:
        packet = self._legacy_topic_packet()
        self.assertEqual([], topic_packet_gate.validate_packet(packet))
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(rd, "run_codex_exec_isolated") as host_run:
                with self.assertRaisesRegex(ValueError, "legacy packets are read-only"):
                    rd.TopicMaterialDiscoveryScheduler.from_codex_exec(
                        packet, {}, {}, workspace_root=Path(tmp), material_path="unread.txt",
                        model_revision="fixture-model",
                        key_store=topic_packet_gate.TopicSchedulerKeyStore(),
                    )
                host_run.assert_not_called()

    def test_production_codex_adapter_reaches_generation_and_semantic_receipts(self) -> None:
        """Exercise the real production factories with only the host process mocked."""

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            key_store_path = temporary_root / "controlled" / "topic-keys.json"
            config = topic_workflow_config()
            packet = topic_packet_gate.build_packet(
                config,
                current_user_request="Generate a broad direction-led topic portfolio for public administration.",
                compiled_at="2026-08-15T08:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )
            seeds = [
                {
                    "seed_id": "SEED-01",
                    "candidate_family": "institutional-response",
                    "problem": "Comparable reforms produce divergent organizational responses.",
                    "anomaly_or_unknown": "Uniform mandates do not explain the observed divergence.",
                    "why_it_matters": "The answer changes how accountability reform is understood.",
                    "potential_disconfirmation": "Responses converge after enforcement discretion is measured.",
                },
                {
                    "seed_id": "SEED-02",
                    "candidate_family": "administrative-boundary",
                    "problem": "Accountability effects may reverse across administrative levels.",
                    "anomaly_or_unknown": "A shared rule can centralize one level and decentralize another.",
                    "why_it_matters": "The boundary determines whether the explanation travels.",
                    "potential_disconfirmation": "Comparable levels exhibit the same authority shift.",
                },
            ]
            candidates = [
                _portfolio_candidate(
                    index,
                    finalist=index in {1, 2},
                    selected=False,
                )
                for index in range(1, 3)
            ]
            presented_ids = ["CAND-01", "CAND-02"]
            screening_output = {
                "seed_dispositions": [
                    {
                        "seed_id": f"SEED-{index:02d}",
                        "disposition": "retain",
                        "candidate_id": f"CAND-{index:02d}",
                        "rationale": "The sealed seed directly anchors this controlled candidate core.",
                    }
                    for index in range(1, 3)
                ],
                "candidate_cores": [
                    rd.candidate_screened_core(candidate)
                    for candidate in candidates
                ],
            }
            pair_reviews = [
                {
                    "left_candidate_id": left,
                    "right_candidate_id": right,
                    "relation": "load-bearing-distinct",
                    "difference_dimensions": ["phenomenon", "mechanism_or_tension"],
                    "rationale": "The bounded questions address different phenomena and explanatory tensions.",
                }
                for left_index, left in enumerate(presented_ids)
                for right in presented_ids[left_index + 1 :]
            ]
            discovery_candidate = _portfolio_candidate(
                3,
                finalist=False,
                selected=False,
            )
            discovery_candidate["seed_ids"] = []
            discovery_candidate["generation_lane"] = "material_discovery"
            discovery_candidate["portfolio_bucket"] = "material-opportunity"
            discovery_output = {
                "candidate_core": rd.candidate_screened_core(discovery_candidate),
                "anomaly": "The bounded material exposes a previously unseen reversal in implementation response.",
                "previously_unseen": True,
                "comparison_rationale": "The reversal and its explanatory tension do not occur in either sealed seed or screened core.",
            }
            captures = [
                ("codex-production-generation-context", seeds),
                ("codex-production-screening-context", screening_output),
                ("codex-production-semantic-context", pair_reviews),
                ("codex-production-discovery-context", discovery_output),
            ]
            commands: list[list[str]] = []
            prompts: list[str] = []

            def controlled_codex_exec(command: list[str], **kwargs: object) -> mock.Mock:
                context_id, output = captures[len(commands)]
                commands.append(list(command))
                prompts.append(str(kwargs.get("input") or ""))
                self.assertEqual("codex", command[0])
                self.assertEqual("exec", command[1])
                self.assertIn("--ephemeral", command)
                self.assertIn("--ignore-user-config", command)
                self.assertEqual(command[command.index("skip_host_skill_discovery") - 1], "--enable")
                self.assertIn("--ignore-rules", command)
                self.assertIn("--skip-git-repo-check", command)
                self.assertIn("read-only", command)
                self.assertNotIn("--add-dir", command)
                cwd = Path(str(kwargs["cwd"])).resolve()
                self.assertNotEqual(temporary_root.resolve(), cwd)
                output_path = Path(
                    command[command.index("--output-last-message") + 1]
                )
                output_path.write_text(
                    json.dumps(output, ensure_ascii=False),
                    encoding="utf-8",
                )
                event = {"type": "thread.started", "thread_id": context_id}
                return mock.Mock(
                    returncode=0,
                    stdout=json.dumps(event) + "\n",
                    stderr="",
                )

            with mock.patch.dict(
                topic_packet_gate.os.environ,
                {"AVERETH_TOPIC_SCHEDULER_KEY_STORE": str(key_store_path)},
            ), mock.patch.object(
                topic_packet_gate.subprocess,
                "run",
                side_effect=controlled_codex_exec,
            ):
                packet_path = temporary_root / "topic-packet.json"
                seal_path = temporary_root / "seed-seal.json"
                write_json(packet_path, packet)
                with redirect_stdout(io.StringIO()):
                    host_seal_rc = topic_packet_gate.main(
                        [
                            "host-seal",
                            str(packet_path),
                            "--model-revision",
                            "controlled-codex-model-v1",
                            "--lane-id",
                            "core_mechanism_boundary",
                            "--dispatched-at",
                            "2026-08-15T08:40:00+00:00",
                            "--issued-at",
                            "2026-08-15T08:50:00+00:00",
                            "--sealed-at",
                            "2026-08-15T09:00:00+00:00",
                            # Minimal two-seed plumbing fixture: below the broad
                            # window the seal precheck enforces, and narrow enough
                            # that bind would require an exemption anyway.
                            "--allow-seed-breadth-exemption",
                            "--output",
                            str(seal_path),
                        ]
                    )
                self.assertEqual(0, host_seal_rc)
                seed_seal = json.loads(seal_path.read_text(encoding="utf-8"))
                topic_packet_gate._ACTIVE_KEY_STORES.pop(
                    seed_seal["scheduler_key_id"],
                    None,
                )
                self.assertEqual(
                    [],
                    topic_packet_gate.validate_seed_seal(packet, seed_seal),
                )
                self.assertNotIn("scheduler_replay_key", seed_seal)
                self.assertNotIn("key_b64", json.dumps(seed_seal))

                workspace = temporary_root / "workspace"
                workspace.mkdir()
                write_json(workspace / "workflow_config.json", config)
                write_json(
                    workspace / "research_decision.json",
                    {
                        "candidates": [],
                        "exploration": {
                            "topic_packet": packet,
                            "seed_seal": seed_seal,
                        },
                    },
                )
                screening_path = temporary_root / "screening-receipt.json"
                with redirect_stdout(io.StringIO()):
                    screening_rc = rd.main(
                        [
                            "host-screen",
                            str(workspace),
                            "--model-revision",
                            "controlled-codex-model-v1",
                            "--issued-at",
                            "2026-08-15T09:10:00+00:00",
                            "--output",
                            str(screening_path),
                        ]
                    )
                self.assertEqual(0, screening_rc)
                screening_receipt = json.loads(
                    screening_path.read_text(encoding="utf-8")
                )
                write_json(
                    workspace / "research_decision.json",
                    {
                        "candidates": candidates,
                        "exploration": {
                            "topic_packet": packet,
                            "seed_seal": seed_seal,
                            "screening_receipt": screening_receipt,
                            "presented_candidate_ids": presented_ids,
                        },
                    },
                )
                semantic_path = temporary_root / "semantic-receipt.json"
                with redirect_stdout(io.StringIO()):
                    semantic_rc = rd.main(
                        [
                            "semantic-review",
                            str(workspace),
                            "--model-revision",
                            "controlled-codex-model-v1",
                            "--issued-at",
                            "2026-08-15T09:45:00+00:00",
                            "--output",
                            str(semantic_path),
                        ]
                    )
                self.assertEqual(0, semantic_rc)
                semantic_receipt = json.loads(
                    semantic_path.read_text(encoding="utf-8")
                )
                topic_packet_gate._ACTIVE_KEY_STORES.pop(
                    semantic_receipt["scheduler_key_id"],
                    None,
                )
                semantic_issues, semantic_pairs = rd.validate_semantic_review_receipt(
                    candidates,
                    presented_ids,
                    seed_seal,
                    screening_receipt,
                    config["direction_contract"],
                    semantic_receipt,
                )
                self.assertEqual([], semantic_issues)
                self.assertEqual(1, len(semantic_pairs))

                material_path = workspace / "declared" / "discovery.txt"
                material_path.parent.mkdir(parents=True)
                material_path.write_text(
                    "A bounded implementation reversal appears in the declared source.",
                    encoding="utf-8",
                )
                discovery_path = temporary_root / "discovery-receipt.json"
                with redirect_stdout(io.StringIO()):
                    discovery_rc = rd.main(
                        [
                            "material-discovery",
                            str(workspace),
                            "--material-path",
                            material_path.relative_to(workspace).as_posix(),
                            "--model-revision",
                            "controlled-codex-model-v1",
                            "--issued-at",
                            "2026-08-15T09:50:00+00:00",
                            "--output",
                            str(discovery_path),
                        ]
                    )
                self.assertEqual(0, discovery_rc)
                discovery_receipt = json.loads(
                    discovery_path.read_text(encoding="utf-8")
                )
                discovery_issues, discovery_core = rd.validate_material_discovery_receipt(
                    workspace,
                    packet,
                    seed_seal,
                    screening_receipt,
                    discovery_receipt,
                )
                self.assertEqual([], discovery_issues)
                self.assertEqual("CAND-03", discovery_core["candidate_id"])

            self.assertEqual(4, len(commands))
            self.assertEqual(
                topic_packet_gate.canonical_generation_prompt(
                    packet,
                    "core_mechanism_boundary",
                ),
                prompts[0],
            )
            self.assertEqual(
                rd.screening_prompt(packet, seed_seal),
                prompts[1],
            )
            self.assertEqual(
                rd.semantic_review_prompt(
                    rd.candidate_portfolio_projection(candidates, presented_ids),
                    config["direction_contract"],
                ),
                prompts[2],
            )
            discovery_projection, _ = rd._material_discovery_input(
                packet,
                seed_seal,
                screening_receipt,
                workspace,
                material_path.relative_to(workspace).as_posix(),
            )
            self.assertEqual(
                rd.material_discovery_prompt(discovery_projection),
                prompts[3],
            )
            key_store_payload = json.loads(key_store_path.read_text(encoding="utf-8"))
            self.assertEqual(4, len(key_store_payload["sessions"]))

    def test_topic_receipt_schema_matches_runtime_exact_fields(self) -> None:
        schema = json.loads(rd.SCHEMA_ASSET.read_text(encoding="utf-8"))
        definitions = schema["$defs"]
        generation = definitions["generation_receipt"]
        self.assertEqual(
            topic_packet_gate.GENERATION_RECEIPT_KEYS,
            set(generation["required"]),
        )
        self.assertEqual(set(generation["required"]), set(generation["properties"]))
        seed_seal = definitions["seed_seal"]
        expected_seal_fields = {
            "schema_version",
            "packet_sha256",
            "sealed_at",
            "scheduler_session_id",
            "scheduler_key_id",
            "generation_receipts",
            "seed_count",
            "seeds",
            "seed_portfolio_sha256",
        }
        self.assertEqual(expected_seal_fields, set(seed_seal["required"]))
        self.assertEqual(set(seed_seal["required"]), set(seed_seal["properties"]))
        semantic = definitions["semantic_review_receipt"]
        self.assertEqual(
            rd.SEMANTIC_REVIEW_RECEIPT_FIELDS,
            set(semantic["required"]),
        )
        self.assertEqual(set(semantic["required"]), set(semantic["properties"]))
        screening = definitions["screening_receipt"]
        self.assertEqual(
            rd.SCREENING_RECEIPT_FIELDS,
            set(screening["required"]),
        )
        self.assertEqual(set(screening["required"]), set(screening["properties"]))
        discovery = definitions["material_discovery_receipt"]
        self.assertEqual(
            rd.MATERIAL_DISCOVERY_RECEIPT_FIELDS,
            set(discovery["required"]),
        )
        self.assertEqual(set(discovery["required"]), set(discovery["properties"]))
        pair_review = definitions["semantic_pair_review"]
        self.assertEqual(rd.SEMANTIC_PAIR_FIELDS, set(pair_review["required"]))
        self.assertEqual(set(pair_review["required"]), set(pair_review["properties"]))
        exploration = definitions["exploration"]
        self.assertIn("semantic_review_receipt", exploration["required"])
        audit = exploration["properties"]["portfolio_audit"]
        self.assertIn("semantic_review_receipt_sha256", audit["required"])
        candidate = definitions["candidate"]
        for field in rd.SCREENED_DECISION_SUMMARY_FIELDS:
            self.assertIn(field, candidate["properties"])
        self.assertEqual(
            {
                "seed_ids",
                "generation_lane",
                "candidate_family",
                "portfolio_bucket",
                "research_question",
                "direction_fit",
                "workspace_relation",
                "semantic_signature",
                "distinctness",
                *rd.SCREENED_DECISION_SUMMARY_FIELDS,
            },
            set(candidate["allOf"][0]["then"]["required"]),
        )
        schema_text = json.dumps(schema, ensure_ascii=False)
        self.assertNotIn("generation_contexts", schema_text)
        self.assertNotIn("semantic_signature_dimensions", schema_text)
        self.assertNotIn("scheduler_replay_key", schema_text)

    def test_production_codex_timeout_is_fail_closed_before_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store_path = Path(temporary) / "controlled-topic-keys.json"
            packet = topic_packet_gate.build_packet(
                topic_workflow_config(),
                current_user_request="Generate direction-only public-administration topic seeds.",
                compiled_at="2026-08-15T08:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )
            with mock.patch.dict(
                topic_packet_gate.os.environ,
                {"AVERETH_TOPIC_SCHEDULER_KEY_STORE": str(store_path)},
            ), mock.patch.object(
                topic_packet_gate.subprocess,
                "run",
                side_effect=topic_packet_gate.subprocess.TimeoutExpired(
                    cmd=["codex", "exec"],
                    timeout=1,
                ),
            ):
                scheduler = topic_packet_gate.TopicGenerationScheduler.from_codex_exec(
                    packet,
                    model_revision="controlled-codex-model-v1",
                    timeout_seconds=1,
                )
                with self.assertRaisesRegex(
                    ValueError,
                    r"BLOCKED: timed out after 1 seconds; no receipt or seed seal was issued",
                ):
                    scheduler.run(
                        lane_id="core_mechanism_boundary",
                        dispatched_at="2026-08-15T08:40:00+00:00",
                        issued_at="2026-08-15T08:50:00+00:00",
                    )
            store = json.loads(store_path.read_text(encoding="utf-8"))
            sessions = list(store["sessions"].values())
            self.assertEqual(1, len(sessions))
            self.assertEqual({}, sessions[0]["receipts"])

    def test_topic_intake_defaults_to_direction_first_regardless_of_materials(self) -> None:
        for materials_dir in ("", "reference_materials", "D:/large-local-dataset"):
            with self.subTest(materials_dir=materials_dir):
                config = intake_wizard.build_config(
                    intake_args(materials_dir=materials_dir)
                )
                self.assertEqual(
                    {
                        "origin_mode": "direction_first",
                        "brainstorm_depth": "broad",
                        "workspace_policy": "quarantine_until_divergence",
                    },
                    config["topic_selection"],
                )
                self.assertEqual(
                    "optional-after-divergence",
                    config["direction_contract"]["workspace_role"],
                )
                self.assertEqual([], validate_workflow_config(config))

        explicit = intake_wizard.build_config(
            intake_args(
                materials_dir="reference_materials",
                origin_mode="material_opportunity",
            )
        )
        self.assertEqual("material_opportunity", explicit["topic_selection"]["origin_mode"])
        self.assertEqual(
            "declared-material-source",
            explicit["direction_contract"]["workspace_role"],
        )
        self.assertEqual([], validate_workflow_config(explicit))

        invalid = copy.deepcopy(topic_workflow_config())
        invalid["topic_selection"]["workspace_policy"] = "declared_source_from_start"
        self.assertIn(
            "topic_selection.origin_mode=direction_first requires "
            "workspace_policy=quarantine_until_divergence",
            validate_workflow_config(invalid),
        )
        missing_policy = copy.deepcopy(topic_workflow_config())
        missing_policy["topic_selection"].pop("brainstorm_depth")
        self.assertIn(
            "topic_selection lacks required fields: brainstorm_depth",
            validate_workflow_config(missing_policy),
        )
        bare_topic_profile = workflow_config()
        bare_issues = validate_workflow_config(bare_topic_profile)
        self.assertIn(
            "task_profile=topic_selection requires an explicit topic_selection policy; "
            "migrate or rebuild the direction contract",
            bare_issues,
        )
        self.assertIn(
            "task_profile=topic_selection requires direction_contract; "
            "migrate or rebuild it from the current user request",
            bare_issues,
        )

    def test_topic_profile_cannot_delete_new_fields_to_restore_legacy_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config.pop("topic_selection")
            config.pop("direction_contract")
            write_json(config_path, config)
            payload["exploration"] = None
            issue_codes = codes(rd.validate_payload(base, payload))
            self.assertIn("RDEC.TOPIC_POLICY.MISSING", issue_codes)
            self.assertIn("RDEC.DIRECTION.MISSING", issue_codes)
            self.assertIn("RDEC.PORTFOLIO.MISSING", issue_codes)

    def test_v701_topic_workspace_requires_explicit_v710_migration(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["framework_version"] = "7.0.1"
            write_json(config_path, config)
            self.assertIn(
                "RDEC.WORKFLOW.MIGRATION_REQUIRED",
                codes(rd.validate_payload(base, payload)),
            )

    def test_screened_candidates_remain_lightweight_until_finalist_maturity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=True)
            screened = payload["candidates"][2]
            self.assertEqual("screened", screened["maturity"])
            self.assertIsNone(screened["c1_collision_evidence"])
            self.assertIsNone(screened["c2_overlap_adjudication"])
            self.assertIsNone(screened["c3_novelty_clearance"])
            self.assertNotIn(
                screened["topic_option_id"],
                {
                    item["topic_option_id"]
                    for item in payload["candidates"][:2]
                },
            )
            self.assertEqual([], rd.validate_payload(base, payload).errors)

            payload["candidates"][1]["maturity"] = "screened"
            self.assertIn(
                "RDEC.CANDIDATE.FINALIST_MATURITY",
                codes(rd.validate_payload(base, payload)),
            )
            payload["candidates"][1]["maturity"] = "finalist"
            screened["maturity"] = "seed"
            self.assertIn(
                "RDEC.CANDIDATE.MATURITY",
                codes(rd.validate_payload(base, payload)),
            )
            screened["maturity"] = "selected"
            self.assertIn(
                "RDEC.CANDIDATE.SELECTED_MATURITY",
                codes(rd.validate_payload(base, payload)),
            )

    def test_portfolio_rejects_object_time_variants_without_load_bearing_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            left = payload["candidates"][0]["semantic_signature"]
            right = payload["candidates"][1]["semantic_signature"]
            for field in rd.LOAD_BEARING_DIFFERENCE_DIMENSIONS:
                right[field] = left[field]
            right["research_object"] = "another province-level governance object"
            right["temporal_logic"] = "another calendar period only"
            payload["candidates"][1]["distinctness"]["difference_dimensions"] = [
                "research_object",
                "temporal_logic",
            ]
            refresh_semantic_review(
                payload,
                overrides={("CAND-01", "CAND-02"): "equivalent"},
            )
            issue_codes = {
                issue.code for issue in rd.topic_portfolio_issues(base, payload)
            }
            self.assertIn("RDEC.PORTFOLIO.PSEUDO_DIVERSITY", issue_codes)
            self.assertIn("RDEC.PORTFOLIO.DECORATIVE_DIFFERENCE", issue_codes)

    def test_c0_merge_resolves_uncertain_semantic_pair(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            refresh_semantic_review(
                payload,
                overrides={("CAND-01", "CAND-02"): "uncertain"},
            )
            issue_codes = {
                issue.code for issue in rd.topic_portfolio_issues(base, payload)
            }
            self.assertIn("RDEC.PORTFOLIO.SEMANTIC_REVIEW_UNRESOLVED", issue_codes)

            merged = payload["candidates"][1]
            merged["status"] = "withdrawn"
            merged["c0_candidate_map"] = {
                "disposition": "merge",
                "merge_into_candidate_id": "CAND-01",
                "rationale": "independent semantic review could not separate the pair; folded into CAND-01",
            }
            issue_codes = {
                issue.code for issue in rd.topic_portfolio_issues(base, payload)
            }
            self.assertNotIn("RDEC.PORTFOLIO.SEMANTIC_REVIEW_UNRESOLVED", issue_codes)
            self.assertNotIn("RDEC.PORTFOLIO.DECORATIVE_DIFFERENCE", issue_codes)

            merged["c0_candidate_map"]["merge_into_candidate_id"] = "CAND-03"
            issue_codes = {
                issue.code for issue in rd.topic_portfolio_issues(base, payload)
            }
            self.assertIn("RDEC.PORTFOLIO.SEMANTIC_REVIEW_UNRESOLVED", issue_codes)

    def test_direction_first_material_dependency_is_separated_and_sha_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            candidate = payload["candidates"][6]
            candidate["workspace_relation"]["ablation_result"] = "depends"
            candidate["portfolio_bucket"] = "material-opportunity"
            candidate["generation_lane"] = "material_opportunity"
            issue_codes = {
                issue.code for issue in rd.topic_portfolio_issues(base, payload)
            }
            self.assertIn("RDEC.PORTFOLIO.MATERIAL_DEPENDENCY", issue_codes)

            material = base / "reference_materials" / "material-opportunity.txt"
            material.parent.mkdir(parents=True, exist_ok=True)
            material.write_text("bounded material opportunity", encoding="utf-8")
            candidate["seed_ids"] = []
            candidate["generation_lane"] = "material_discovery"
            for assessment in candidate["direction_fit"].values():
                assessment["verdict"] = "strong"
            candidate["workspace_relation"].update(
                {
                    "role": "support",
                    "anchor_risk": "high",
                    "rationale": "This separate opportunity exists only because the declared material is available.",
                    "material_refs": [
                        {
                            "path": material.relative_to(base).as_posix(),
                            "sha256": rd.hashlib.sha256(material.read_bytes()).hexdigest(),
                        }
                    ],
                }
            )
            exploration = payload["exploration"]
            exploration["presented_candidate_ids"].remove("CAND-07")
            exploration["material_opportunity_candidate_ids"] = ["CAND-07"]
            exploration["portfolio_audit"]["candidate_count"] = 7
            exploration["portfolio_audit"]["family_count"] = 7
            exploration["portfolio_audit"]["main_candidate_count"] = 6
            exploration["portfolio_audit"]["material_branch_candidate_count"] = 1
            screening_output = {
                "seed_dispositions": [
                    (
                        {
                            **dict(item),
                            "disposition": "drop",
                            "candidate_id": None,
                            "rationale": "This seed was dropped before the controlled main portfolio was finalized.",
                        }
                        if item["seed_id"] == "SEED-07"
                        else dict(item)
                    )
                    for item in exploration["screening_receipt"]["seed_dispositions"]
                ],
                "candidate_cores": [
                    rd.candidate_screened_core(item)
                    for item in payload["candidates"][:6]
                ],
            }
            screening_scheduler = rd.TopicScreeningScheduler._for_test(
                exploration["topic_packet"],
                exploration["seed_seal"],
                test_capture=lambda _bounded_input: json.dumps(
                    screening_output,
                    ensure_ascii=False,
                ),
                test_context_id="material-branch-rescreening-context",
            )
            exploration["screening_receipt"] = screening_scheduler.run(
                issued_at="2026-08-15T09:11:00+00:00",
            )
            self.assertIn(
                "RDEC.MATERIAL_DISCOVERY.BRANCH",
                {
                    issue.code
                    for issue in rd.topic_portfolio_issues(base, payload)
                },
            )
            discovery_output = {
                "candidate_core": rd.candidate_screened_core(candidate),
                "anomaly": "The bounded material exposes an unexpected implementation reversal across comparable administrative settings.",
                "previously_unseen": True,
                "comparison_rationale": "No sealed seed or screened core contains this material-specific reversal or its explanatory tension.",
            }
            discovery_scheduler = rd.TopicMaterialDiscoveryScheduler._for_test(
                exploration["topic_packet"],
                exploration["seed_seal"],
                exploration["screening_receipt"],
                workspace_root=base,
                material_path=material.relative_to(base).as_posix(),
                test_capture=lambda _bounded_input: json.dumps(
                    discovery_output,
                    ensure_ascii=False,
                ),
                test_context_id="controlled-material-discovery-context",
            )
            exploration["material_discovery_receipts"] = [
                discovery_scheduler.run(issued_at="2026-08-15T09:40:00+00:00")
            ]
            refresh_semantic_review(payload)
            exploration["workspace_materials_admitted_at"] = None
            self.assertIn(
                "RDEC.MATERIAL_ADMISSION.MISSING",
                {
                    issue.code
                    for issue in rd.topic_portfolio_issues(base, payload)
                },
            )
            exploration["workspace_materials_admitted_at"] = "2026-08-15T09:30:00+00:00"
            self.assertEqual([], rd.topic_portfolio_issues(base, payload))

            missing_distinctness = copy.deepcopy(payload)
            missing_distinctness["candidates"][6].pop("distinctness")
            self.assertIn(
                "RDEC.CANDIDATE.DISTINCTNESS",
                {
                    issue.code
                    for issue in rd.topic_portfolio_issues(
                        base,
                        missing_distinctness,
                    )
                },
            )

            duplicate_branch = copy.deepcopy(payload)
            refresh_semantic_review(
                duplicate_branch,
                overrides={("CAND-01", "CAND-07"): "equivalent"},
            )
            self.assertIn(
                "RDEC.PORTFOLIO.PSEUDO_DIVERSITY",
                {
                    issue.code
                    for issue in rd.topic_portfolio_issues(
                        base,
                        duplicate_branch,
                    )
                },
            )

            material.write_text("changed material opportunity", encoding="utf-8")
            issues = rd.topic_portfolio_issues(base, payload)
            self.assertIn(
                "RDEC.WORKSPACE_RELATION.LOCAL_STALE",
                {issue.code for issue in issues},
            )
            self.assertFalse([issue for issue in issues if issue.severity == "ERROR"])

    def test_live_direction_change_invalidates_sealed_topic_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            config_path = base / "workflow_config.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["direction_contract"]["core_problem"] = (
                "Explain a newly authorized direction with different substantive stakes."
            )
            write_json(config_path, config)
            self.assertIn(
                "RDEC.DIRECTION.STALE",
                codes(rd.validate_payload(base, payload)),
            )

    def test_hard_cleared_primary_requires_selected_maturity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=True)
            self.assertEqual([], rd.validate_payload(base, payload).errors)
            payload["candidates"][0]["maturity"] = "finalist"
            self.assertIn(
                "RDEC.CANDIDATE.SELECTED_MATURITY",
                codes(rd.validate_payload(base, payload)),
            )

    def test_generated_report_exposes_space_map_and_three_decision_roles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=True)
            result = rd.validate_payload(base, payload)
            report = rd.render_novelty_report(
                payload,
                result,
                rd.preclearance_readiness(base, payload),
            )
            self.assertIn("## Research-space map", report)
            self.assertIn("Most robust: `CAND-01`", report)
            self.assertIn("Most balanced: `CAND-02`", report)
            self.assertIn("Highest originality: `CAND-03`", report)
            self.assertIn("Load-bearing difference", report)
            self.assertIn("Direction rationale", report)
            self.assertIn("Material role and ablation", report)
            self.assertIn("Potential contribution", report)
            self.assertIn("Largest uncertainty / failure risk", report)
            self.assertIn("Why worth deep review", report)
            self.assertIn(
                "Candidate 1 could revise how public-administration theory",
                report,
            )
            self.assertIn(
                "Candidate 1 may fail if its proposed explanatory tension",
                report,
            )
            self.assertIn(
                "Candidate 1 merits deep review because the answer would",
                report,
            )
            self.assertIn("## Finalist collision and novelty depth", report)
            material_candidate = copy.deepcopy(payload["candidates"][-1])
            material_candidate.update(
                {
                    "id": "CAND-08",
                    "topic_option_id": "O8",
                    "candidate_family": "material-opportunity-family",
                    "portfolio_bucket": "material-opportunity",
                    "generation_lane": "material_opportunity",
                }
            )
            payload["candidates"].append(material_candidate)
            payload["exploration"]["material_opportunity_candidate_ids"] = [
                "CAND-08"
            ]
            material_report = rd.render_novelty_report(payload, result)
            self.assertIn("### Separate material-opportunity branch", material_report)
            self.assertIn(
                "Problem family: material-opportunity-family",
                material_report,
            )
            self.assertIn("Potential contribution:", material_report)
            self.assertIn("Largest uncertainty / failure risk:", material_report)
            self.assertIn("Why worth deep review:", material_report)

    def test_screened_candidates_require_user_visible_decision_summaries(self) -> None:
        for field in rd.SCREENED_DECISION_SUMMARY_FIELDS:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary)
                payload = activate_topic_portfolio(
                    base,
                    make_workspace(base),
                    cleared=False,
                )
                payload["candidates"][0].pop(field)
                errors = rd.validate_payload(base, payload).errors
                self.assertTrue(
                    any(
                        item.code == "RDEC.CANDIDATE.DECISION_SUMMARY"
                        and item.path.endswith("." + field)
                        for item in errors
                    )
                )

    def test_provisional_topic_route_blocks_soft_focus_until_portfolio_is_sealed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = activate_topic_portfolio(base, make_workspace(base), cleared=False)
            payload["exploration"] = None
            readiness = rd.preclearance_readiness(base, payload)
            self.assertEqual("candidate_portfolio", readiness["next_checkpoint"])
            self.assertIn(
                "RDEC.PORTFOLIO.MISSING",
                {item["code"] for item in readiness["issues"]},
            )

    def test_challenge_schema_encodes_lifecycle_branches(self) -> None:
        schema = json.loads(rd.SCHEMA_ASSET.read_text(encoding="utf-8"))
        challenge = schema["$defs"]["challenge"]
        statuses = {
            item["if"]["properties"]["status"]["const"]
            for item in challenge["allOf"]
        }
        self.assertEqual(
            {"open", "resolved-retained", "resolved-revised", "withdrawn"},
            statuses,
        )
        self.assertTrue(challenge["properties"]["evidence_ids"]["uniqueItems"])

    def test_cleared_contract_and_pdf_downloaded_source_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            self.assertEqual("cleared", rd.project_decision_state(payload))
            self.assertEqual([], rd.validate_payload(base, payload).errors)
            self.assertEqual(
                payload["clearance_basis_digest"],
                payload["hard_clearance_confirmation"]["basis_sha256"],
            )

    def test_six_state_projection_is_mutually_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cleared = make_workspace(base)
            provisional = copy.deepcopy(cleared)
            provisional["disposition"] = "pending"
            provisional["soft_focus_confirmation"] = None
            focused = copy.deepcopy(provisional)
            focused["soft_focus_confirmation"] = copy.deepcopy(cleared["soft_focus_confirmation"])
            challenged = rd._challenge_payload(
                cleared,
                reason="A newly registered collision challenges the active answer boundary.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-1"],
                question_version_id=None,
            )
            reopened = rd._resolve_retained_payload(
                challenged,
                challenge_id="CH-001",
                resolution="The original question is retained but must receive renewed bounded clearance.",
                resolved_at="2026-08-19T08:00:00+00:00",
            )
            withdrawn = copy.deepcopy(cleared)
            withdrawn["disposition"] = "withdrawn"
            observed = {
                rd.project_decision_state(item)
                for item in (provisional, focused, challenged, reopened, cleared, withdrawn)
            }
            self.assertEqual(
                {"provisional", "focused", "challenged", "reopened", "cleared", "withdrawn"},
                observed,
            )

    def test_provisional_and_focused_do_not_fabricate_future_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            payload["disposition"] = "pending"
            payload["soft_focus_confirmation"] = None
            selected = payload["candidates"][0]
            selected["c0_candidate_map"] = None
            selected["c1_collision_evidence"] = None
            selected["c2_overlap_adjudication"] = None
            selected["c3_novelty_clearance"] = None
            payload["hard_clearance_confirmation"] = None
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            provisional_codes = codes(rd.validate_payload(base, payload))
            self.assertIn("RDEC.PRECLEAR.PROVISIONAL", provisional_codes)
            self.assertNotIn("RDEC.C1.MISSING", provisional_codes)
            payload["soft_focus_confirmation"] = {
                "confirmation_id": "CONF-FOCUS-2",
                "status": "confirmed",
                "source": "user soft-focus message",
                "confirmed_at": "2026-08-16T09:00:00+00:00",
                "primary_candidate_id": "CAND-01",
                "alternate_candidate_ids": ["CAND-02"],
            }
            selected["c0_candidate_map"] = candidate_one()["c0_candidate_map"]
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            focused_codes = codes(rd.validate_payload(base, payload))
            self.assertIn("RDEC.PRECLEAR.FOCUSED", focused_codes)
            self.assertNotIn("RDEC.C1.MISSING", focused_codes)
            readiness = rd.preclearance_readiness(base, payload)
            self.assertFalse(readiness["ready"])
            self.assertEqual("research_evidence", readiness["next_checkpoint"])
            self.assertIn("RDEC.C1.MISSING", {item["code"] for item in readiness["issues"]})

    def test_confirmed_motivation_is_conditional_not_generic_research_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            payload["disposition"] = "pending"
            payload["soft_focus_confirmation"] = None
            payload["hard_clearance_confirmation"] = None
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            write_json(base / rd.DECISION_REL, payload)
            (base / "confirmed_motivation.md").unlink()
            issues = orientation_gate.check_question_commitment(base, {"PO-01"})
            self.assertFalse(any("missing confirmed_motivation.md" in issue for issue in issues))
            self.assertFalse(content_gate.confirmed_motivation_required("pending"))
            self.assertFalse(content_gate.confirmed_motivation_required("withdrawn"))
            self.assertTrue(content_gate.confirmed_motivation_required("cleared"))
            self.assertTrue(content_gate.confirmed_motivation_required("reopen"))

    def test_complete_focused_science_routes_to_hard_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            payload["disposition"] = "pending"
            payload["hard_clearance_confirmation"] = None
            payload["candidates"][0]["c3_novelty_clearance"]["status"] = "standby"
            payload["candidates"][0]["c3_novelty_clearance"]["human_confirmation_ref"] = None
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            readiness = rd.preclearance_readiness(base, payload)
            self.assertTrue(readiness["ready"], readiness["issues"])
            self.assertEqual("hard_clearance_confirmation", readiness["next_checkpoint"])

    def test_c1_rejects_fake_verification_and_accepts_google_scholar_track(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["sources"][0]["state"] = "content-verified"
            registry["sources"][0]["verification"].pop("support_claim")
            write_json(registry_path, registry)
            invalid = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C1.SOURCE_UNVERIFIED", codes(invalid))
            registry["sources"][0] = source("S-COLL-1", "Q-COLLISION-1")
            write_json(registry_path, registry)
            self.assertNotIn("RDEC.C1.TRACK_COVERAGE", codes(rd.validate_payload(base, payload)))

    def test_mixed_track_uses_cnki_and_google_scholar_channel_ssot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base, "mixed")
            self.assertNotIn("RDEC.C1.TRACK_COVERAGE", codes(rd.validate_payload(base, payload)))

    def test_unrelated_query_and_synthesis_cannot_fill_c1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["queries"].append(query("Q-OTHER", "google-scholar", "CAND-02"))
            registry["sources"].append(source("S-OTHER", "Q-OTHER"))
            write_json(registry_path, registry)
            analysis_path = base / "literature_analysis.json"
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["syntheses"].append(
                {
                    "synthesis_id": "SYN-OTHER",
                    "candidate_ids": ["CAND-02"],
                    "source_links": [{"source_id": "S-OTHER"}],
                    "adjudication": "Valid but unrelated synthesis for the alternate candidate.",
                }
            )
            write_json(analysis_path, analysis)
            selected_c1 = payload["candidates"][0]["c1_collision_evidence"]
            selected_c1.update(
                {
                    "query_ids": ["Q-OTHER"],
                    "source_ids": ["S-OTHER"],
                    "synthesis_ids": ["SYN-OTHER"],
                    "strongest_collision_source_id": "S-OTHER",
                }
            )
            result = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C1.QUERY_CANDIDATE_BINDING", codes(result))
            self.assertIn("RDEC.C1.SYNTHESIS_CANDIDATE_BINDING", codes(result))

    def test_synthesis_must_link_declared_and_strongest_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            analysis_path = base / "literature_analysis.json"
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["syntheses"][0]["source_links"] = [{"source_id": "S-NOT-C1"}]
            write_json(analysis_path, analysis)
            result = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C1.SYNTHESIS_SOURCE_BINDING", codes(result))
            self.assertIn("RDEC.C1.STRONGEST_SYNTHESIS", codes(result))

    def test_overlap_vector_blocks_severity_downgrade_attack(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            c2 = payload["candidates"][0]["c2_overlap_adjudication"]
            c2["overlap_vector"].update(
                {
                    "question_or_estimand": "same",
                    "existing_answer": "same",
                    "unit_case_time_scope": "overlapping",
                    "theory_or_mechanism": "same",
                    "materials_and_identification_logic": "same",
                }
            )
            c2["collision_severity"] = "limited"
            c2["disposition"] = "retain"
            result = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C2.SEVERITY_UNDERSTATED", codes(result))

    def test_substantial_collision_cannot_reframe_on_decorative_difference(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            c2 = payload["candidates"][0]["c2_overlap_adjudication"]
            c2["collision_severity"] = "substantial"
            c2["disposition"] = "reframe"
            c2["pivot_conditions"] = pivot_conditions(True)
            c2["decorative_difference_only"] = True
            result = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C2.PIVOT_BLOCKED", codes(result))

    def test_single_real_candidate_needs_reason_not_a_fabricated_alternate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            matrix_path = base / "topic_induction_deduction_matrix.md"
            matrix_path.write_text(
                "\n".join(
                    line
                    for line in matrix_path.read_text(encoding="utf-8").splitlines()
                    if not line.startswith("| O2 |")
                )
                + "\n",
                encoding="utf-8",
            )
            payload["candidates"] = [payload["candidates"][0]]
            payload["soft_focus_confirmation"]["alternate_candidate_ids"] = []
            payload["hard_clearance_confirmation"] = None
            payload["candidates"][0]["c0_candidate_map"].pop(
                "no_comparable_alternative_reason",
                None,
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            payload["hard_clearance_confirmation"] = {
                "confirmation_id": "CONF-HARD-1",
                "status": "confirmed",
                "source": "user message approving bounded novelty clearance",
                "confirmed_at": "2026-08-17T08:00:00+00:00",
                "candidate_id": "CAND-01",
                "question_version_id": "CAND-01-RQ-V1",
                "basis_sha256": payload["clearance_basis_digest"],
            }
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            self.assertIn("RDEC.C0.NO_ALTERNATIVE_REASON", codes(rd.validate_payload(base, payload)))
            payload["candidates"][0]["c0_candidate_map"]["no_comparable_alternative_reason"] = (
                "The portfolio search found no genuinely comparable alternative; adding one would be artificial."
            )
            payload["hard_clearance_confirmation"] = None
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            payload["hard_clearance_confirmation"] = {
                "confirmation_id": "CONF-HARD-SINGLE",
                "status": "confirmed",
                "source": "user approved the one-candidate bounded clearance",
                "confirmed_at": "2026-08-17T09:00:00+00:00",
                "candidate_id": "CAND-01",
                "question_version_id": "CAND-01-RQ-V1",
                "basis_sha256": payload["clearance_basis_digest"],
            }
            payload["candidates"][0]["c3_novelty_clearance"]["human_confirmation_ref"] = (
                "CONF-HARD-SINGLE"
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            self.assertEqual([], rd.validate_payload(base, payload).errors)

    def test_selected_subgraph_ignores_nonselected_and_background_edits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            payload["decision_version"] += 1
            payload["candidates"][1]["focus_rationale"] += " Additional alternate-only reasoning."
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["queries"].append(
                {
                    "query_id": "Q-BACKGROUND",
                    "purpose": "citation",
                    "status": "complete",
                    "channel": "google-scholar",
                    "result_count": 3,
                }
            )
            registry["sources"].append(source("S-BACKGROUND", "Q-BACKGROUND"))
            write_json(registry_path, registry)
            result = rd.validate_payload(base, payload)
            self.assertNotIn("RDEC.SUBGRAPH.STALE", codes(result))
            self.assertNotIn("RDEC.CLEARANCE_BASIS.STALE", codes(result))

    def test_selected_matrix_and_problem_orientation_changes_stale_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            matrix = base / "topic_induction_deduction_matrix.md"
            matrix.write_text(
                matrix.read_text(encoding="utf-8").replace(
                    "Bounded to observed local governments and the registered period.",
                    "Bounded to a substantively narrower set of selected local governments.",
                ),
                encoding="utf-8",
            )
            self.assertIn("RDEC.SUBGRAPH.STALE", codes(rd.validate_payload(base, payload)))

    def test_old_hard_confirmation_cannot_be_reused_for_new_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            old_basis = payload["hard_clearance_confirmation"]["basis_sha256"]
            matrix = base / "topic_induction_deduction_matrix.md"
            matrix.write_text(
                matrix.read_text(encoding="utf-8").replace(
                    "Bounded to observed local governments and the registered period.",
                    "Bounded to a newly narrowed institutional subset and period.",
                ),
                encoding="utf-8",
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            self.assertNotEqual(old_basis, payload["clearance_basis_digest"])
            self.assertIn("RDEC.HARD_CLEARANCE.BASIS", codes(rd.validate_payload(base, payload)))
            write_matrix(base)
            orientation = base / "problem_orientation.md"
            orientation.write_text(
                orientation.read_text(encoding="utf-8").replace(
                    "Uniform incentives are often assumed to produce uniform responses.",
                    "Uniform incentives and public visibility are jointly assumed to produce uniform responses.",
                ),
                encoding="utf-8",
            )
            self.assertIn("RDEC.SUBGRAPH.STALE", codes(rd.validate_payload(base, payload)))

    def test_new_collision_source_stales_and_bind_cannot_wash_it_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            write_json(base / rd.DECISION_REL, payload)
            rd.write_views(base, payload, rd.validate_payload(base, payload), allow_unmanaged_replace=True)
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["sources"].append(source("S-COLL-2", "Q-COLLISION-1"))
            write_json(registry_path, registry)
            stale = rd.validate_payload(base, payload)
            self.assertIn("RDEC.C1.SOURCE_COVERAGE", codes(stale))
            self.assertIn("RDEC.SUBGRAPH.STALE", codes(stale))
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = rd.bind_command(base, apply=False)
            self.assertEqual(2, code)
            self.assertIn("bind refused", stderr.getvalue())

    def test_new_basis_requires_challenge_and_fresh_hard_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            original = make_workspace(base)
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["sources"].append(source("S-COLL-2", "Q-COLLISION-1"))
            write_json(registry_path, registry)
            challenged = rd._challenge_payload(
                original,
                reason="The new collision source changes the bounded novelty basis.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-2"],
                question_version_id=None,
            )
            rd._synchronize_challenge_dependencies(base, challenged)
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, challenged))
            self.assertEqual("challenged", rd.project_decision_state(challenged))
            self.assertIsNone(challenged["hard_clearance_confirmation"])
            self.assertEqual("CONF-HARD-1", challenged["confirmation_archive"][0]["confirmation_id"])
            reopened = rd._resolve_retained_payload(
                challenged,
                challenge_id="CH-001",
                resolution="Retain the question but adjudicate the new collision and renew clearance.",
                resolved_at="2026-08-19T08:00:00+00:00",
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, reopened))
            renewed = copy.deepcopy(reopened)
            renewed["disposition"] = "cleared"
            renewed["candidates"][0]["c3_novelty_clearance"]["status"] = "cleared"
            renewed["candidates"][0]["c3_novelty_clearance"]["human_confirmation_ref"] = "CONF-HARD-2"
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, renewed))
            renewed["hard_clearance_confirmation"] = {
                "confirmation_id": "CONF-HARD-2",
                "status": "confirmed",
                "source": "user renewed clearance after reviewing the new collision",
                "confirmed_at": "2026-08-20T08:00:00+00:00",
                "candidate_id": "CAND-01",
                "question_version_id": "CAND-01-RQ-V1",
                "basis_sha256": renewed["clearance_basis_digest"],
            }
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, renewed))
            self.assertEqual([], rd.validate_payload(base, renewed).errors)

    def test_challenge_evidence_ids_resolve_candidate_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            challenged = rd._challenge_payload(
                payload,
                reason="Registered collision evidence challenges the active answer boundary.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["Q-COLLISION-1", "SYN-COLL-1"],
                question_version_id=None,
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, challenged))
            valid_codes = codes(rd.validate_payload(base, challenged))
            self.assertFalse(
                {code for code in valid_codes if code.startswith("RDEC.CHALLENGE.EVIDENCE")}
            )
            attacked = copy.deepcopy(challenged)
            attacked["question_challenges"][0]["evidence_ids"] = ["BOGUS"]
            self.assertIn(
                "RDEC.CHALLENGE.EVIDENCE_UNKNOWN",
                codes(rd.validate_payload(base, attacked)),
            )
            write_json(base / rd.DECISION_REL, payload)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(
                    2,
                    rd.challenge_command(
                        base,
                        reason="A purported collision should be rejected when its identity is bogus.",
                        source="user-directed adversarial review",
                        opened_at="2026-08-18T08:00:00+00:00",
                        evidence_ids=["BOGUS"],
                        question_version_id=None,
                        apply=False,
                    ),
                )

    def test_open_and_resolved_retained_challenge_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            challenged = rd._challenge_payload(
                payload,
                reason="A registered collision requires explicit question review.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-1"],
                question_version_id=None,
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, challenged))
            valid_open_codes = codes(rd.validate_payload(base, challenged))
            self.assertNotIn("RDEC.CHALLENGE.OPEN_STATE", valid_open_codes)
            self.assertNotIn("RDEC.CHALLENGE.OPEN_TARGET", valid_open_codes)
            forged_open = copy.deepcopy(challenged)
            forged_open["question_challenges"][0]["resolution"] = (
                "Premature resolution injected while status remains open."
            )
            self.assertIn(
                "RDEC.CHALLENGE.OPEN_STATE",
                codes(rd.validate_payload(base, forged_open)),
            )
            retained = rd._resolve_retained_payload(
                challenged,
                challenge_id="CH-001",
                resolution="The original question is retained subject to renewed clearance.",
                resolved_at="2026-08-19T08:00:00+00:00",
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, retained))
            retained_codes = codes(rd.validate_payload(base, retained))
            self.assertNotIn("RDEC.CHALLENGE.RETAINED_SUCCESSOR", retained_codes)
            self.assertNotIn("RDEC.CHALLENGE.RETAINED_TARGET", retained_codes)
            forged_retained = copy.deepcopy(retained)
            forged_retained["question_challenges"][0][
                "successor_question_version_id"
            ] = "CAND-02-RQ-V1"
            self.assertIn(
                "RDEC.CHALLENGE.RETAINED_SUCCESSOR",
                codes(rd.validate_payload(base, forged_retained)),
            )
            stale_target = copy.deepcopy(retained)
            stale_target["candidates"][0]["question_versions"][0]["status"] = "challenged"
            stale_target["candidates"][0]["active_question_version_id"] = None
            self.assertIn(
                "RDEC.CHALLENGE.RETAINED_TARGET",
                codes(rd.validate_payload(base, stale_target)),
            )

    def test_resolved_revised_requires_same_candidate_higher_successor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            challenged = rd._challenge_payload(
                payload,
                reason="The active question must be revised after registered collision review.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-1"],
                question_version_id=None,
            )
            question_input = question_version(
                "discarded",
                "Why does public visibility condition otherwise similar local investment choices?",
                status="draft",
                version=99,
            )
            for generated_field in ("id", "version", "status"):
                question_input.pop(generated_field)
            revised = rd._reopen_payload(
                challenged,
                challenge_id="CH-001",
                question_input=question_input,
                resolution="The revised question separates the conditional observable implication.",
                resolved_at="2026-08-19T08:00:00+00:00",
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, revised))
            valid_codes = codes(rd.validate_payload(base, revised))
            self.assertNotIn("RDEC.CHALLENGE.SUCCESSOR", valid_codes)
            self.assertNotIn("RDEC.CHALLENGE.SUCCESSOR_VERSION", valid_codes)
            self.assertNotIn("RDEC.CHALLENGE.REVISED_ORIGINAL", valid_codes)
            self.assertNotIn("RDEC.CHALLENGE.SUCCESSOR_STATUS", valid_codes)
            wrong_owner = copy.deepcopy(revised)
            wrong_owner["question_challenges"][0][
                "successor_question_version_id"
            ] = "CAND-02-RQ-V1"
            self.assertIn(
                "RDEC.CHALLENGE.SUCCESSOR",
                codes(rd.validate_payload(base, wrong_owner)),
            )
            non_increasing = copy.deepcopy(revised)
            non_increasing["question_challenges"][0][
                "successor_question_version_id"
            ] = "CAND-01-RQ-V1"
            self.assertIn(
                "RDEC.CHALLENGE.SUCCESSOR_VERSION",
                codes(rd.validate_payload(base, non_increasing)),
            )
            active_original = copy.deepcopy(revised)
            active_original["candidates"][0]["question_versions"][0]["status"] = "active"
            self.assertIn(
                "RDEC.CHALLENGE.REVISED_ORIGINAL",
                codes(rd.validate_payload(base, active_original)),
            )
            withdrawn_successor = copy.deepcopy(revised)
            withdrawn_successor["candidates"][0]["question_versions"][1]["status"] = "withdrawn"
            self.assertIn(
                "RDEC.CHALLENGE.SUCCESSOR_STATUS",
                codes(rd.validate_payload(base, withdrawn_successor)),
            )

    def test_withdrawn_challenge_closes_candidate_and_question_without_successor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            challenged = rd._challenge_payload(
                payload,
                reason="Collision adjudication requires withdrawing this candidate question.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-1"],
                question_version_id=None,
            )
            candidate = challenged["candidates"][0]
            candidate["status"] = "withdrawn"
            candidate["active_question_version_id"] = None
            candidate["question_versions"][0]["status"] = "withdrawn"
            challenge = challenged["question_challenges"][0]
            challenge.update(
                {
                    "status": "withdrawn",
                    "resolution": "The candidate question is withdrawn without an automatic successor.",
                    "resolved_at": "2026-08-19T08:00:00+00:00",
                    "successor_question_version_id": None,
                }
            )
            valid_codes = codes(rd.validate_payload(base, challenged))
            self.assertFalse(
                {
                    code
                    for code in valid_codes
                    if code.startswith("RDEC.CHALLENGE.WITHDRAWN")
                }
            )
            forged = copy.deepcopy(challenged)
            forged_candidate = forged["candidates"][0]
            forged_candidate["status"] = "selected"
            forged_candidate["question_versions"][0]["status"] = "challenged"
            forged_candidate["active_question_version_id"] = "CAND-01-RQ-V1"
            forged["question_challenges"][0][
                "successor_question_version_id"
            ] = "CAND-01-RQ-V1"
            attacked_codes = codes(rd.validate_payload(base, forged))
            self.assertIn("RDEC.CHALLENGE.WITHDRAWN_CANDIDATE", attacked_codes)
            self.assertIn("RDEC.CHALLENGE.WITHDRAWN_QUESTION", attacked_codes)
            self.assertIn("RDEC.CHALLENGE.WITHDRAWN_ACTIVE", attacked_codes)
            self.assertIn("RDEC.CHALLENGE.WITHDRAWN_SUCCESSOR", attacked_codes)
            wrong_time = copy.deepcopy(challenged)
            wrong_time["question_challenges"][0]["resolved_at"] = (
                "2026-08-17T08:00:00+00:00"
            )
            self.assertIn(
                "RDEC.CHALLENGE.TIME_ORDER",
                codes(rd.validate_payload(base, wrong_time)),
            )

    def test_withdrawal_requires_user_confirmation_and_never_needs_commitment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            (base / "confirmed_motivation.md").unlink()
            payload.update(
                {
                    "disposition": "withdrawn",
                    "selected_candidate_id": None,
                    "terminal_reason": "Every real candidate is blocked or merged after collision adjudication.",
                    "soft_focus_confirmation": None,
                    "hard_clearance_confirmation": None,
                    "withdrawal_confirmation": None,
                    "confirmed_motivation_ref": None,
                }
            )
            for candidate in payload["candidates"]:
                candidate["status"] = "withdrawn"
                candidate["c0_candidate_map"] = {
                    "disposition": "drop",
                    "rationale": "Collision adjudication blocks this candidate without authorizing an automatic replacement.",
                }
                candidate["c1_collision_evidence"] = None
                candidate["c2_overlap_adjudication"] = None
                candidate["c3_novelty_clearance"] = None
                candidate["active_question_version_id"] = None
                for question in candidate["question_versions"]:
                    question["status"] = "withdrawn"
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            self.assertIn("RDEC.WITHDRAWAL_CONFIRMATION.MISSING", codes(rd.validate_payload(base, payload)))
            payload["withdrawal_confirmation"] = {
                "confirmation_id": "CONF-WITHDRAW-1",
                "status": "confirmed",
                "source": "user explicitly approved terminating research without replacement",
                "confirmed_at": "2026-08-18T08:00:00+00:00",
                "all_candidates_withdrawn": True,
                "no_replacement": True,
            }
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            result = rd.validate_payload(base, payload)
            self.assertEqual([], result.errors)
            self.assertIn("Status: NOT_APPLICABLE", rd.render_novelty_report(payload, result))

    def _apply_challenge(self, base: Path) -> tuple[dict, dict, bytes, bytes]:
        before = make_workspace(base)
        write_json(base / rd.DECISION_REL, before)
        rd.write_views(base, before, rd.validate_payload(base, before), allow_unmanaged_replace=True)
        after = rd._challenge_payload(
            before,
            reason="A registered collision warrants reopening the active question boundary.",
            source="user-directed adversarial review",
            opened_at="2026-08-18T08:00:00+00:00",
            evidence_ids=["S-COLL-1"],
            question_version_id=None,
        )
        self.assertEqual([], rd.bind_selected_candidate_subgraph(base, after))
        manifest = rd._apply_mutation(base, before, after, "challenge")
        return (
            after,
            manifest,
            (base / rd.DECISION_REL).read_bytes(),
            (base / rd.NOVELTY_REPORT_REL).read_bytes(),
        )

    def test_apply_mutation_allows_only_the_expected_reopen_preflight_gap(self) -> None:
        def revised_question(challenged: dict) -> dict:
            question_input = question_version(
                "discarded",
                "Why does public visibility condition otherwise similar local investment choices?",
                status="draft",
                version=99,
            )
            for generated_field in ("id", "version", "status"):
                question_input.pop(generated_field)
            return rd._reopen_payload(
                challenged,
                challenge_id="CH-001",
                question_input=question_input,
                resolution="The revised question separates the conditional observable implication.",
                resolved_at="2026-08-19T08:00:00+00:00",
            )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            challenged, _manifest, _decision, _report = self._apply_challenge(base)
            reopened = revised_question(challenged)
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, reopened))
            self.assertEqual(
                {"RDEC.F2.QUESTION", "RDEC.REOPEN.REQUIRED"},
                {item.code for item in rd.validate_payload(base, reopened, check_views=False).errors},
            )

            manifest = rd._apply_mutation(base, challenged, reopened, "reopen")
            current = json.loads((base / rd.DECISION_REL).read_text(encoding="utf-8"))
            self.assertEqual("reopen", manifest["operation"])
            self.assertEqual("reopened", rd.project_decision_state(current))
            self.assertIsNone(current["candidates"][0]["active_question_version_id"])

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            challenged, _manifest, challenged_bytes, _report = self._apply_challenge(base)
            forged = revised_question(challenged)
            forged["schema_version"] = "forged-research-decision/v1"
            with self.assertRaisesRegex(RuntimeError, "RDEC.SCHEMA"):
                rd._apply_mutation(base, challenged, forged, "reopen")
            self.assertEqual(challenged_bytes, (base / rd.DECISION_REL).read_bytes())

    def test_apply_mutation_failure_restores_decision_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            before = make_workspace(base)
            write_json(base / rd.DECISION_REL, before)
            rd.write_views(base, before, rd.validate_payload(base, before), allow_unmanaged_replace=True)
            original_decision = (base / rd.DECISION_REL).read_bytes()
            original_report = (base / rd.NOVELTY_REPORT_REL).read_bytes()
            after = rd._challenge_payload(
                before,
                reason="A collision challenges the active bounded answer.",
                source="user-directed review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_ids=["S-COLL-1"],
                question_version_id=None,
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, after))
            original_replace = rd._replace_file
            calls = 0

            def fail_second(source_path: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("injected report publication failure")
                original_replace(source_path, destination)

            with mock.patch.object(rd, "_replace_file", side_effect=fail_second):
                with self.assertRaises(RuntimeError):
                    rd._apply_mutation(base, before, after, "challenge")
            self.assertEqual(original_decision, (base / rd.DECISION_REL).read_bytes())
            self.assertEqual(original_report, (base / rd.NOVELTY_REPORT_REL).read_bytes())

    def test_rollback_rejects_race_and_corrupt_backup_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _after, manifest, applied_decision, applied_report = self._apply_challenge(base)
            manifest_path = base / manifest["manifest"]
            report_path = base / rd.NOVELTY_REPORT_REL
            report_path.write_bytes(applied_report + b"race")
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(2, rd.rollback_command(base, manifest_path, apply=True))
            self.assertEqual(applied_decision, (base / rd.DECISION_REL).read_bytes())
            self.assertEqual(applied_report + b"race", report_path.read_bytes())

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _after, manifest, applied_decision, applied_report = self._apply_challenge(base)
            manifest_path = base / manifest["manifest"]
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            second_backup = base / data["files"][1]["backup"]
            second_backup.write_bytes(second_backup.read_bytes() + b"corrupt")
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(2, rd.rollback_command(base, manifest_path, apply=True))
            self.assertEqual(applied_decision, (base / rd.DECISION_REL).read_bytes())
            self.assertEqual(applied_report, (base / rd.NOVELTY_REPORT_REL).read_bytes())

    def test_rollback_second_replace_failure_recovers_applied_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _after, manifest, applied_decision, applied_report = self._apply_challenge(base)
            manifest_path = base / manifest["manifest"]
            original_replace = rd._replace_file
            calls = 0

            def fail_second(source_path: Path, destination: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise RuntimeError("injected second rollback replace failure")
                original_replace(source_path, destination)

            with mock.patch.object(rd, "_replace_file", side_effect=fail_second):
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    self.assertEqual(2, rd.rollback_command(base, manifest_path, apply=True))
            self.assertEqual(applied_decision, (base / rd.DECISION_REL).read_bytes())
            self.assertEqual(applied_report, (base / rd.NOVELTY_REPORT_REL).read_bytes())

    def test_rollback_path_boundary_and_successful_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            _after, manifest, applied_decision, applied_report = self._apply_challenge(base)
            manifest_path = base / manifest["manifest"]
            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["files"][0]["path"] = "../research_decision.json"
            tampered_path = manifest_path.with_name("tampered.json")
            write_json(tampered_path, tampered)
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(2, rd.rollback_command(base, tampered_path, apply=True))
            self.assertEqual(applied_decision, (base / rd.DECISION_REL).read_bytes())
            self.assertEqual(applied_report, (base / rd.NOVELTY_REPORT_REL).read_bytes())
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                self.assertEqual(0, rd.rollback_command(base, manifest_path, apply=True))
            restored = json.loads((base / rd.DECISION_REL).read_text(encoding="utf-8"))
            self.assertEqual("cleared", rd.project_decision_state(restored))

    def test_design_binds_narrow_subgraph_not_global_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            write_json(base / rd.DECISION_REL, payload)
            design = {
                "research_decision_ref": rd.design_reference(payload),
                "research_questions": [
                    {
                        "role": "primary",
                        "text": QUESTION_1,
                        "primary_type": "explanatory",
                    }
                ],
            }
            payload["decision_version"] += 1
            payload["candidates"][1]["focus_rationale"] += " Non-selected edit."
            write_json(base / rd.DECISION_REL, payload)
            result = FakeDesignResult()
            design_v3._validate_research_decision_reference(base, design, result)
            self.assertNotIn("RD.RESEARCH_DECISION.STALE", {row[0] for row in result.rows})
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["sources"].append(source("S-COLL-2", "Q-COLLISION-1"))
            write_json(registry_path, registry)
            stale = FakeDesignResult()
            design_v3._validate_research_decision_reference(base, design, stale)
            self.assertIn("RD.RESEARCH_DECISION.INVALID", {row[0] for row in stale.rows})

    def test_every_preclear_state_is_blocked_at_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            design = {
                "research_decision_ref": rd.design_reference(payload),
                "research_questions": [
                    {"role": "primary", "text": QUESTION_1, "primary_type": "explanatory"}
                ],
            }
            for disposition, soft in (("pending", None), ("pending", payload["soft_focus_confirmation"])):
                candidate = copy.deepcopy(payload)
                candidate["disposition"] = disposition
                candidate["soft_focus_confirmation"] = copy.deepcopy(soft)
                candidate["hard_clearance_confirmation"] = None
                self.assertEqual([], rd.bind_selected_candidate_subgraph(base, candidate))
                write_json(base / rd.DECISION_REL, candidate)
                result = FakeDesignResult()
                design_v3._validate_research_decision_reference(base, design, result)
                self.assertIn("RD.RESEARCH_DECISION.NOT_CLEARED", {row[0] for row in result.rows})

    def test_controller_projection_and_plan_route_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            payload["disposition"] = "pending"
            payload["hard_clearance_confirmation"] = None
            payload["candidates"][0]["c3_novelty_clearance"].update(
                {"status": "standby", "human_confirmation_ref": None}
            )
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            write_json(base / rd.DECISION_REL, payload)
            state, readiness = controller._research_decision_projection(base)
            self.assertEqual("focused", state)
            self.assertTrue(readiness["ready"])
            status = {
                "next_stage": "research",
                "next_checkpoint": readiness["next_checkpoint"],
                "task_profile": "topic_selection",
                "publication_track": "international-ssci",
                "terminal_stage": "research",
                "research_decision_state": state,
                "preclearance_readiness": readiness,
            }
            plan = build_plan(status, workflow_config())
            self.assertEqual("focused", plan["research_decision_state"])
            self.assertTrue(plan["preclearance_readiness"]["ready"])
            self.assertTrue(plan["user_decision_required"])
            self.assertFalse(plan["can_run_gate"])

    def test_fresh_topic_status_routes_to_candidate_portfolio_before_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            write_json(base / "workflow_config.json", topic_workflow_config())
            doctor = mock.Mock(ok=True, issues=[])
            registry = mock.Mock(ok=True, issues=[], stats={})
            material = mock.Mock(errors=[])
            with mock.patch.object(
                controller,
                "run_doctor",
                return_value=doctor,
            ), mock.patch.object(
                controller,
                "contract_metadata",
                return_value={
                    "acquisition_schema": controller.ACQUISITION_SCHEMA_V2,
                    "integration_enabled": False,
                },
            ), mock.patch.object(
                controller,
                "validate_problem_orientation",
                return_value=[],
            ), mock.patch.object(
                controller,
                "acquisition_handoff_issues",
                return_value=[],
            ), mock.patch.object(
                controller,
                "validate_integration_artifacts",
                return_value={"status": "PASS", "issues": []},
            ), mock.patch.object(
                controller,
                "validate_material_contract",
                return_value=(base, {}, material),
            ), mock.patch.object(
                controller,
                "validate_registry",
                return_value=registry,
            ), mock.patch.object(
                controller,
                "cnki_content_status",
                return_value=(True, []),
            ), mock.patch.object(
                controller,
                "research_status",
                return_value=(False, ["research decision is missing"]),
            ):
                status, rc = controller.status_payload(base, HERE.parent)
            self.assertEqual(0, rc)
            self.assertEqual("topic_selection", status["task_profile"])
            self.assertEqual("absent", status["research_decision_state"])
            self.assertEqual("research", status["next_stage"])
            self.assertEqual("candidate_portfolio", status["next_checkpoint"])

    def test_controller_wrapper_applies_challenge_and_returns_research_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            commitment_before = (base / rd.MOTIVATION_REL).read_bytes()
            write_json(base / rd.DECISION_REL, payload)
            rd.write_views(base, payload, rd.validate_payload(base, payload), allow_unmanaged_replace=True)
            args = argparse.Namespace(
                research_decision_action="challenge",
                apply=True,
                reason="A registered collision requires a renewed bounded novelty decision.",
                source="user-directed adversarial review",
                opened_at="2026-08-18T08:00:00+00:00",
                evidence_id=["S-COLL-1"],
                question_version_id=None,
            )
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = controller._run_research_decision_command(args, base)
            self.assertEqual(0, code)
            current = json.loads((base / rd.DECISION_REL).read_text(encoding="utf-8"))
            self.assertEqual("challenged", rd.project_decision_state(current))
            self.assertIsNone(current["hard_clearance_confirmation"])
            self.assertEqual(commitment_before, (base / rd.MOTIVATION_REL).read_bytes())

    def test_public_cli_parser_exposes_research_decision_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = make_workspace(base)
            write_json(base / rd.DECISION_REL, payload)
            rd.write_views(base, payload, rd.validate_payload(base, payload), allow_unmanaged_replace=True)
            argv = [
                "avereth.py",
                "research-decision",
                "challenge",
                str(base),
                "--reason",
                "A registered collision requires bounded-question review.",
                "--source",
                "user-directed adversarial review",
                "--opened-at",
                "2026-08-18T08:00:00+00:00",
            ]
            with mock.patch.object(sys, "argv", argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(0, controller.main())
            current = json.loads((base / rd.DECISION_REL).read_text(encoding="utf-8"))
            self.assertEqual("cleared", rd.project_decision_state(current))

    def test_v60_workspace_without_decision_reopens_research_and_preserves_commitment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_commitment(base)
            write_json(
                base / "reference_materials" / "literature_registry.json",
                {"schema_version": "cnki-acquisition/v2"},
            )
            write_json(base / "literature_analysis.json", {"schema_version": "cnki-literature-analysis/v2"})
            write_json(base / "research_design.json", {"schema_version": "cnki-research-design/v4"})
            write_json(base / "method_execution.json", {"schema_version": "cnki-method-execution/v3"})
            before = (base / "confirmed_motivation.md").read_bytes()
            self.assertEqual(
                "acquisition",
                workspace_migration._earliest_reopen(base, workflow_config()),
            )
            self.assertEqual(before, (base / "confirmed_motivation.md").read_bytes())

    def test_claude_agent_declared_two_phase_flow_reaches_semantic_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            key_store_path = temporary_root / "controlled" / "topic-keys.json"
            config = topic_workflow_config()
            packet = topic_packet_gate.build_packet(
                config,
                current_user_request="Generate a broad direction-led topic portfolio.",
                compiled_at="2026-08-15T08:00:00+00:00",
                literature_reconnaissance=synthetic_recon(),
            )
            seeds = [
                {
                    "seed_id": "SEED-01",
                    "candidate_family": "institutional-response",
                    "problem": "Comparable reforms produce divergent organizational responses.",
                    "anomaly_or_unknown": "Uniform mandates do not explain the divergence.",
                    "why_it_matters": "The answer changes how reform is understood.",
                    "potential_disconfirmation": "Responses converge after discretion is measured.",
                },
                {
                    "seed_id": "SEED-02",
                    "candidate_family": "administrative-boundary",
                    "problem": "Effects may reverse across administrative levels.",
                    "anomaly_or_unknown": "One rule centralizes one level and decentralizes another.",
                    "why_it_matters": "The boundary determines whether the explanation travels.",
                    "potential_disconfirmation": "Comparable levels exhibit the same shift.",
                },
            ]
            candidates = [
                _portfolio_candidate(index, finalist=True, selected=False)
                for index in range(1, 3)
            ]
            presented_ids = ["CAND-01", "CAND-02"]
            screening_output = {
                "seed_dispositions": [
                    {
                        "seed_id": f"SEED-{index:02d}",
                        "disposition": "retain",
                        "candidate_id": f"CAND-{index:02d}",
                        "rationale": "The sealed seed anchors this controlled candidate core.",
                    }
                    for index in range(1, 3)
                ],
                "candidate_cores": [rd.candidate_screened_core(item) for item in candidates],
            }
            pair_reviews = [
                {
                    "left_candidate_id": "CAND-01",
                    "right_candidate_id": "CAND-02",
                    "relation": "load-bearing-distinct",
                    "difference_dimensions": ["phenomenon", "mechanism_or_tension"],
                    "rationale": "The questions address different phenomena and tensions.",
                }
            ]
            environment = {
                "AVERETH_HOST": "claude",
                "AVERETH_TOPIC_SCHEDULER_KEY_STORE": str(key_store_path),
            }
            with mock.patch.dict(topic_packet_gate.os.environ, environment):
                packet_path = temporary_root / "topic-packet.json"
                seal_path = temporary_root / "seed-seal.json"
                write_json(packet_path, packet)
                generation_dir = temporary_root / "agent-generation"
                seal_args = [
                    "host-seal",
                    str(packet_path),
                    "--model-revision",
                    "declared-session-model-v1",
                    "--lane-id",
                    "core_mechanism_boundary",
                    "--dispatched-at",
                    "2026-08-15T08:40:00+00:00",
                    "--issued-at",
                    "2026-08-15T08:50:00+00:00",
                    "--sealed-at",
                    "2026-08-15T09:00:00+00:00",
                    # Minimal two-seed plumbing fixture; see the codex adapter test.
                    "--allow-seed-breadth-exemption",
                    "--runner",
                    "agent-declared",
                    "--output",
                    str(seal_path),
                ]
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        topic_packet_gate.main(
                            [*seal_args, "--emit-prompts", str(generation_dir)]
                        ),
                    )
                manifest = json.loads(
                    (generation_dir / "manifest.json").read_text(encoding="utf-8")
                )
                entry = manifest["steps"]["core_mechanism_boundary"]
                (generation_dir / entry["response_path"]).write_text(
                    json.dumps(seeds, ensure_ascii=False), encoding="utf-8"
                )
                (generation_dir / entry["context_path"]).write_text(
                    "agent-generation-context", encoding="utf-8"
                )
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        topic_packet_gate.main(
                            [*seal_args, "--responses", str(generation_dir)]
                        ),
                    )
                seed_seal = json.loads(seal_path.read_text(encoding="utf-8"))
                topic_packet_gate._ACTIVE_KEY_STORES.pop(
                    seed_seal["scheduler_key_id"], None
                )
                self.assertEqual([], topic_packet_gate.validate_seed_seal(packet, seed_seal))

                workspace = temporary_root / "workspace"
                workspace.mkdir()
                write_json(workspace / "workflow_config.json", config)
                write_json(
                    workspace / "research_decision.json",
                    {
                        "candidates": [],
                        "exploration": {"topic_packet": packet, "seed_seal": seed_seal},
                    },
                )
                screening_dir = temporary_root / "agent-screening"
                screening_path = temporary_root / "screening-receipt.json"
                screen_args = [
                    "host-screen",
                    str(workspace),
                    "--model-revision",
                    "declared-session-model-v1",
                    "--issued-at",
                    "2026-08-15T09:10:00+00:00",
                    "--runner",
                    "agent-declared",
                    "--output",
                    str(screening_path),
                ]
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        rd.main([*screen_args, "--emit-prompts", str(screening_dir)]),
                    )
                (screening_dir / "screening.response.json").write_text(
                    json.dumps(screening_output, ensure_ascii=False), encoding="utf-8"
                )
                (screening_dir / "screening.context.txt").write_text(
                    "agent-screening-context", encoding="utf-8"
                )
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        rd.main([*screen_args, "--responses", str(screening_dir)]),
                    )
                screening_receipt = json.loads(
                    screening_path.read_text(encoding="utf-8")
                )
                screening_issues, _ = rd.validate_screening_receipt(
                    packet, seed_seal, screening_receipt
                )
                self.assertEqual([], screening_issues)

                write_json(
                    workspace / "research_decision.json",
                    {
                        "candidates": candidates,
                        "exploration": {
                            "topic_packet": packet,
                            "seed_seal": seed_seal,
                            "screening_receipt": screening_receipt,
                            "presented_candidate_ids": presented_ids,
                        },
                    },
                )
                semantic_dir = temporary_root / "agent-semantic"
                semantic_path = temporary_root / "semantic-receipt.json"
                semantic_args = [
                    "semantic-review",
                    str(workspace),
                    "--model-revision",
                    "declared-session-model-v1",
                    "--issued-at",
                    "2026-08-15T09:45:00+00:00",
                    "--runner",
                    "agent-declared",
                    "--output",
                    str(semantic_path),
                ]
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        rd.main([*semantic_args, "--emit-prompts", str(semantic_dir)]),
                    )
                (semantic_dir / "semantic-review.response.json").write_text(
                    json.dumps(pair_reviews, ensure_ascii=False), encoding="utf-8"
                )
                (semantic_dir / "semantic-review.context.txt").write_text(
                    "agent-semantic-context", encoding="utf-8"
                )
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(
                        0,
                        rd.main([*semantic_args, "--responses", str(semantic_dir)]),
                    )
                semantic_receipt = json.loads(
                    semantic_path.read_text(encoding="utf-8")
                )
                topic_packet_gate._ACTIVE_KEY_STORES.pop(
                    semantic_receipt["scheduler_key_id"], None
                )
                semantic_issues, semantic_pairs = rd.validate_semantic_review_receipt(
                    candidates,
                    presented_ids,
                    seed_seal,
                    screening_receipt,
                    config["direction_contract"],
                    semantic_receipt,
                )
                self.assertEqual([], semantic_issues)
                self.assertEqual(1, len(semantic_pairs))


if __name__ == "__main__":
    unittest.main()
