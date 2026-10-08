#!/usr/bin/env python3
"""Regression tests for critical reading and literature synthesis."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "literature_analysis.py"
SPEC = importlib.util.spec_from_file_location("literature_analysis_under_test", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
analysis_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = analysis_module
SPEC.loader.exec_module(analysis_module)


class LiteratureAnalysisTests(unittest.TestCase):
    def test_v2_schema_asset_is_valid_and_matches_runtime(self) -> None:
        schema_path = (
            HERE.parent
            / "references"
            / "schemas"
            / "cnki-literature-analysis-v2.schema.json"
        )
        raw = schema_path.read_text(encoding="utf-8")
        schema = json.loads(raw)
        self.assertEqual(
            analysis_module.SCHEMA_VERSION,
            schema["properties"]["schema_version"]["const"],
        )
        self.assertNotIn("*** Add File", raw)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        (self.base / "reference_materials").mkdir()
        (self.base / "workflow_config.json").write_text(
            json.dumps({"task_profile": "full_paper"}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def source(self, source_id: str, *, method: str = "full-text") -> dict:
        return {
            "source_id": source_id,
            "channel": "publisher",
            "title": f"Source {source_id}",
            "publication_year": 2026,
            "query_ids": ["Q1"],
            "state": "content-verified",
            "citation_scope": "final-source",
            "doi": f"10.9999/{source_id.lower()}",
            "collected_at": "2026-08-15",
            "verification": {
                "method": method,
                "verified_at": "2026-08-15",
                "support_claim": "A bounded and concrete source claim used by the test fixture.",
            },
            "relevance": {
                "status": "mapped",
                "responsibilities": [
                    "claim",
                    "position",
                    "theory",
                    "counterargument",
                    "method",
                ],
            },
        }

    def write_registry(self, sources: list[dict]) -> dict:
        registry = {
            "schema_version": "cnki-acquisition/v2",
            "queries": [
                {"query_id": query_id, "status": "complete"}
                for query_id in ("Q1", "Q-SAT-1", "Q-SAT-2", "Q-EXHAUSTIVE-1")
            ],
            "sources": sources,
        }
        (self.base / "reference_materials" / "literature_registry.json").write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return registry

    def reading(
        self,
        source: dict,
        *,
        source_type: str = "empirical-quantitative",
        status: str = "complete",
    ) -> dict:
        level = analysis_module.evidence_level(source)
        criteria = [
            {
                "criterion_id": criterion,
                "status": "supported" if level == "full-text" else "unclear",
                "judgment": f"The record explicitly evaluates {criterion} within the available evidence.",
                "anchors": ["Methods section"] if level == "full-text" else [],
            }
            for criterion in sorted(analysis_module.APPRAISAL_CRITERIA[source_type])
        ]
        if level == "full-text":
            allowed = sorted(analysis_module.CLAIM_PERMISSIONS)
            forbidden: list[str] = []
            independent_status = "assessed"
            anchor_type = "figure"
            locator = "Figure 2"
            observation = "The plotted comparison is conditional and does not show a universal effect."
            missing: list[str] = []
        else:
            allowed = sorted(analysis_module.LIMITED_ALLOWED)
            forbidden = sorted(analysis_module.HEAVY_PERMISSIONS)
            independent_status = "not-assessable"
            anchor_type = "abstract" if level == "abstract" else "detail-page"
            locator = "Abstract"
            observation = "The author reports a conditional association in the available summary."
            missing = ["Full methods, results, tables, and discussion are unavailable."]
        return {
            "reading_id": f"CR-{source['source_id']}",
            "source_id": source["source_id"],
            "source_fingerprint": analysis_module.source_fingerprint(source),
            "source_type": source_type,
            "evidence_level": level,
            "status": status,
            "reading_depth": "core" if level == "full-text" else "background",
            "background_reading": (
                {
                    "purpose": "Report the author's published position within the available abstract boundary.",
                    "content_summary": "The abstract reports a conditional association.",
                    "use_boundary": "Do not infer methods, independent results, mechanism, or generalizability.",
                    "anchors": [
                        {
                            "anchor_type": anchor_type,
                            "locator": locator,
                            "observation": observation,
                        }
                    ],
                }
                if level != "full-text"
                else {}
            ),
            "analysis_sequence": list(analysis_module.ANALYSIS_SEQUENCE),
            "aerial_view": {
                "scope_and_design": "The paper examines a defined population with a comparative design.",
                "core_question_or_purpose": "Under what conditions does the proposed relationship hold?",
                "stated_gap_or_context": "Prior work does not distinguish the relevant boundary condition.",
            },
            "interrogation": {
                "method_or_argument_fit": "The design is appropriate for a conditional descriptive claim.",
                "independent_interpretation": {
                    "status": independent_status,
                    "judgment": "The available evidence supports only a bounded conditional interpretation.",
                    "anchors": [
                        {
                            "anchor_type": anchor_type,
                            "locator": locator,
                            "observation": observation,
                        }
                    ],
                },
                "appraisal": {
                    "profile": source_type,
                    "criteria": criteria,
                },
            },
            "verdict": {
                "author_conclusion": "The author concludes that the relationship is conditional.",
                "reader_author_comparison": "The reader agrees only within the stated population and measure.",
                "alternative_explanations": ["Selection into the observed group could explain part of the pattern."],
                "limitations": ["The design does not establish transportability beyond the observed setting."],
                "conflicts_of_interest": "Funding and declared interests were checked; no automatic validity inference is made.",
                "bounded_verdict": "Use for a conditional claim, not a universal conclusion.",
            },
            "claim_permissions": {
                "allowed": allowed,
                "forbidden": forbidden,
            },
            "missing_evidence": missing,
        }

    def background_reading(self, source: dict) -> dict:
        return {
            "reading_id": f"CR-{source['source_id']}",
            "source_id": source["source_id"],
            "source_fingerprint": analysis_module.source_fingerprint(source),
            "source_type": "empirical-quantitative",
            "evidence_level": "full-text",
            "status": "complete",
            "reading_depth": "background",
            "background_reading": {
                "purpose": "Provide bounded background for the established measurement context.",
                "content_summary": "The source documents how the measure is normally defined in this field.",
                "use_boundary": "Use only for background context, not method-quality or result adjudication.",
                "anchors": [
                    {
                        "anchor_type": "section",
                        "locator": "Section 2",
                        "observation": "The section defines the measure and its scope.",
                    }
                ],
            },
            "claim_permissions": {
                "allowed": sorted(analysis_module.LIMITED_ALLOWED),
                "forbidden": sorted(analysis_module.HEAVY_PERMISSIONS),
            },
        }

    def write_analysis(
        self,
        registry: dict,
        readings: list[dict],
        *,
        migration_status: str = "current",
        syntheses: list[dict] | None = None,
    ) -> dict:
        if syntheses is None:
            source_id = readings[0]["source_id"]
            level = readings[0]["evidence_level"]
            heavy = level == "full-text"
            syntheses = [
                {
                    "synthesis_id": "SYN-1",
                    "kind": "single-source-position",
                    "claim_class": "causal-mechanism" if heavy else "author-position",
                    "review_question": "Why does the relationship vary across settings?",
                    "proposition": "The source identifies a conditional rather than universal relationship.",
                    "source_links": [
                        {
                            "source_id": source_id,
                            "relation": "qualifies",
                            "use": "evidence" if heavy else "author-position",
                            "comparability": "partially-comparable",
                            "rationale": "The source directly addresses the stated boundary condition.",
                        }
                    ],
                    "comparability_basis": "The population and outcome definition are explicit but narrow.",
                    "appraisal_weighting": "The judgment follows the type-specific appraisal without an automatic score.",
                    "conflict_or_heterogeneity": "Observed variation can arise from the boundary condition and selection.",
                    "analyst_judgment": "The evidence supports a conditional claim within the observed setting.",
                    "residual_uncertainty": "Transportability to other populations remains unknown.",
                    "writing_role": "boundary",
                }
            ]
        final_ids = sorted(
            str(item.get("source_id"))
            for item in registry.get("sources", [])
            if isinstance(item, dict) and item.get("citation_scope") == "final-source"
        )
        core_ids = sorted(
            str(item.get("source_id"))
            for item in readings
            if item.get("reading_depth") == "core"
        )
        payload = {
            "schema_version": analysis_module.SCHEMA_VERSION,
            "registry_binding": {
                "source_ids": final_ids,
                "digest": analysis_module.registry_binding_digest(registry, final_ids),
            },
            "migration_status": migration_status,
            "review_scope": {
                "review_type": "embedded",
                "review_question": "Why does the relationship vary across settings?",
                "search_scope": "Registered scholarly sources relevant to the bounded paper question.",
                "inclusion_boundary": "Content-verified final sources that address the question.",
                "exclusion_boundary": "Discovery-only records and sources outside the research object.",
                "synthesis_logic": "Compare claims, evidence, design, conditions, and alternative explanations.",
                "reporting_standard": "not-applicable for an embedded review",
            },
            "source_readings": readings,
            "syntheses": syntheses,
            "literature_sufficiency": {
                "mode": "fallback",
                "screened_source_ids": final_ids,
                "final_source_ids": final_ids,
                "core_reading_source_ids": core_ids,
                "current_qualified_count": len(final_ids),
                "benchmark": {
                    "target_venue": "",
                    "article_type": "article",
                    "target_word_count": None,
                    "samples": [],
                },
                "coverage": {
                    key: {
                        "status": "covered",
                        "source_ids": final_ids[:1],
                        "synthesis_ids": ["SYN-1"],
                        "rationale": f"The mapped source and synthesis cover {key} for the bounded test question.",
                    }
                    for key in (
                        "major_positions",
                        "counterarguments",
                        "foundational_chain",
                        "recent_developments",
                        "method_responsibilities",
                    )
                },
                "saturation_rounds": [
                    {
                        "query_ids": ["Q-SAT-1"],
                        "purpose": "counterargument",
                        "new_major_position": False,
                        "new_decisive_evidence_type": False,
                        "new_sources_role": "verification",
                    },
                    {
                        "query_ids": ["Q-SAT-2"],
                        "purpose": "method responsibility",
                        "new_major_position": False,
                        "new_decisive_evidence_type": False,
                        "new_sources_role": "boundary",
                    },
                ],
                "exhaustive_corpus_exception": {
                    "requested": True,
                    "search_boundary": "Synthetic closed test corpus",
                    "query_ids": ["Q-EXHAUSTIVE-1"],
                    "eligibility_rule": "All scholarly works in the named closed corpus that address the test question.",
                    "exhaustion_evidence": "The complete corpus inventory and query log contain no additional eligible works.",
                    "eligible_total": len(final_ids),
                    "included_source_ids": final_ids,
                    "all_eligible_included": True,
                    "user_confirmed": True,
                    "confirmation_evidence": "unit-test fixture authorization",
                    "reason": "closed-corpus-exhausted",
                },
            },
        }
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return payload

    def test_full_text_reading_and_bounded_synthesis_pass(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        self.write_analysis(registry, [self.reading(source)])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])

    def test_optional_problem_arc_preserves_authority_and_branch_lineage(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        payload = self.write_analysis(registry, [self.reading(source)])
        payload["problem_arc"] = {
            "arc_id": "ARC-MAIN",
            "major_branch_ids": ["BRANCH-CONDITIONAL"],
            "states": [
                {
                    "state_id": "ARC-STATE-POSED",
                    "live_question": "Why does the relationship vary across settings?",
                    "provisional_answer": "The relationship may be universal.",
                    "pressure": "The registered source reports a conditional pattern.",
                    "transition_type": "PRESS",
                    "updated_problem": "Which boundary makes the relationship conditional?",
                    "residual_unknown": "The transportable boundary remains unknown.",
                    "authority_refs": ["S1", "CR-S1"],
                    "branch_id": "BRANCH-CONDITIONAL",
                },
                {
                    "state_id": "ARC-STATE-REVISED",
                    "live_question": "Which boundary makes the relationship conditional?",
                    "provisional_answer": "Selection may account for part of the pattern.",
                    "pressure": "The synthesis distinguishes selection from the focal boundary.",
                    "transition_type": "DISTINGUISH",
                    "updated_problem": "How much variation remains after selection is bounded?",
                    "residual_unknown": "Other populations remain unobserved.",
                    "authority_refs": ["SYN-1"],
                    "predecessor_state_refs": ["ARC-STATE-POSED"],
                    "branch_id": "BRANCH-CONDITIONAL",
                    "branch_disposition": "Retained as the bounded live explanation.",
                },
            ],
        }
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        self.assertEqual(2, result.stats["problem_arc_states"])

    def test_problem_arc_rejects_unregistered_transition_authority(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        payload = self.write_analysis(registry, [self.reading(source)])
        payload["problem_arc"] = {
            "arc_id": "ARC-MAIN",
            "states": [
                {
                    "state_id": "ARC-STATE-POSED",
                    "live_question": "Why does the relationship vary across settings?",
                    "provisional_answer": "The relationship may be universal.",
                    "pressure": "A claim needs to revise the provisional answer.",
                    "transition_type": "REVISE",
                    "updated_problem": "Which bounded explanation survives?",
                    "residual_unknown": "Transportability remains unknown.",
                    "authority_refs": ["S-GHOST"],
                }
            ],
        }
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertIn("AP.ARC.AUTHORITY_MISSING", {item.code for item in result.issues})

    def test_problem_arc_does_not_silently_drop_a_major_branch(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        payload = self.write_analysis(registry, [self.reading(source)])
        payload["problem_arc"] = {
            "arc_id": "ARC-MAIN",
            "major_branch_ids": ["BRANCH-COMPETING"],
            "states": [
                {
                    "state_id": "ARC-STATE-POSED",
                    "live_question": "Why does the relationship vary across settings?",
                    "provisional_answer": "A competing mechanism may explain it.",
                    "pressure": "The synthesis narrows but does not erase that mechanism.",
                    "transition_type": "PRESS",
                    "updated_problem": "Which mechanism remains plausible?",
                    "residual_unknown": "The competing mechanism is unresolved.",
                    "authority_refs": ["SYN-1"],
                    "branch_id": "BRANCH-COMPETING",
                }
            ],
        }
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertIn("AP.ARC.BRANCH_DROPPED", {item.code for item in result.issues})

    def test_background_source_uses_proportional_note_not_seven_step_core_form(self) -> None:
        core = self.source("S1")
        background = self.source("S2")
        registry = self.write_registry([core, background])
        background_record = self.background_reading(background)
        self.assertNotIn("aerial_view", background_record)
        self.assertNotIn("interrogation", background_record)
        self.assertNotIn("verdict", background_record)
        self.write_analysis(registry, [self.reading(core), background_record])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])

    def test_primary_material_may_be_final_but_does_not_count_as_scholarly_literature(self) -> None:
        scholarly = self.source("S1")
        primary = self.source("P1")
        primary["channel"] = "official"
        primary["material_role"] = "official-primary"
        registry = self.write_registry([scholarly, primary])
        payload = self.write_analysis(
            registry,
            [self.reading(scholarly), self.background_reading(primary)],
        )
        sufficiency = payload["literature_sufficiency"]
        sufficiency["current_qualified_count"] = 1
        sufficiency["exhaustive_corpus_exception"]["eligible_total"] = 1
        sufficiency["exhaustive_corpus_exception"]["included_source_ids"] = ["S1"]
        for entry in sufficiency["coverage"].values():
            entry["source_ids"] = ["S1"]
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        self.assertTrue(
            any("not counted toward the scholarly floor" in item.message for item in result.warnings)
        )

    def test_coverage_requires_synthesis_and_a_core_scholarly_reading(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        payload = self.write_analysis(registry, [self.reading(source)])
        payload["literature_sufficiency"]["coverage"]["counterarguments"][
            "synthesis_ids"
        ] = []
        payload["literature_sufficiency"]["core_reading_source_ids"] = []
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result, _ = analysis_module.validate_analysis(self.base)
        messages = [item.message for item in result.issues]
        self.assertTrue(any("synthesis identity" in item for item in messages))
        self.assertTrue(any("core reading" in item for item in messages))

    def test_saturation_rounds_must_be_distinct_registered_query_executions(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        payload = self.write_analysis(registry, [self.reading(source)])
        payload["literature_sufficiency"]["saturation_rounds"][1]["query_ids"] = [
            "Q-SAT-1",
            "Q-MISSING",
        ]
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        result, _ = analysis_module.validate_analysis(self.base)
        messages = [item.message for item in result.issues]
        self.assertTrue(any("missing or incomplete queries" in item for item in messages))
        self.assertTrue(any("distinct recorded query executions" in item for item in messages))

    def test_every_final_source_requires_a_reading(self) -> None:
        source_one = self.source("S1")
        source_two = self.source("S2")
        registry = self.write_registry([source_one, source_two])
        self.write_analysis(registry, [self.reading(source_one)])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.READING.COVERAGE" and "S2" in item.message for item in result.issues))

    def test_registry_and_source_changes_make_analysis_stale(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        self.write_analysis(registry, [self.reading(source)])
        source["title"] = "Changed source identity"
        self.write_registry([source])
        result, _ = analysis_module.validate_analysis(self.base)
        codes = {item.code for item in result.issues}
        self.assertIn("LA.REGISTRY.STALE", codes)
        self.assertIn("LA.READING.STALE", codes)

    def test_candidate_only_query_changes_do_not_invalidate_load_bearing_analysis(self) -> None:
        source = self.source("S1")
        candidate = self.source("C1")
        candidate["citation_scope"] = "candidate-only"
        candidate["state"] = "metadata-exported"
        registry = self.write_registry([source, candidate])
        self.write_analysis(registry, [self.reading(source)])
        candidate["title"] = "Retitled screened candidate"
        candidate["query_ids"] = ["Q-NEW"]
        self.write_registry([source, candidate])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])

    def test_abstract_reading_can_report_position_but_not_independent_results(self) -> None:
        core = self.source("S0")
        source = self.source("S1", method="abstract")
        registry = self.write_registry([core, source])
        core_reading = self.reading(core)
        reading = self.reading(source, source_type="other", status="limited")
        self.write_analysis(registry, [core_reading, reading])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])

        reading["claim_permissions"]["allowed"].append("causal-mechanism")
        reading["claim_permissions"]["forbidden"].remove("causal-mechanism")
        self.write_analysis(registry, [core_reading, reading])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.PERMISSION.FULLTEXT_REQUIRED" for item in result.issues))

    def test_abstract_cannot_be_load_bearing_synthesis_evidence(self) -> None:
        source = self.source("S1", method="detail")
        registry = self.write_registry([source])
        reading = self.reading(source, source_type="other", status="limited")
        payload = self.write_analysis(registry, [reading])
        payload["syntheses"][0]["source_links"][0]["use"] = "evidence"
        (self.base / "literature_analysis.json").write_text(json.dumps(payload), encoding="utf-8")
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.SYNTHESIS.FULLTEXT_REQUIRED" for item in result.issues))

    def test_independent_interpretation_must_precede_author_comparison(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        reading = self.reading(source)
        reading["analysis_sequence"] = list(reversed(reading["analysis_sequence"]))
        self.write_analysis(registry, [reading])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.READING.SEQUENCE" for item in result.issues))

    def test_source_type_requires_its_own_appraisal_criteria(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        reading = self.reading(source, source_type="theoretical-normative")
        reading["interrogation"]["appraisal"]["criteria"].pop()
        self.write_analysis(registry, [reading])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.APPRAISAL.TYPE_COVERAGE" for item in result.issues))

    def test_cross_source_identity_requires_multiple_sources(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        reading = self.reading(source)
        payload = self.write_analysis(registry, [reading])
        payload["syntheses"][0]["kind"] = "cross-source-synthesis"
        (self.base / "literature_analysis.json").write_text(json.dumps(payload), encoding="utf-8")
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(any(item.code == "LA.SYNTHESIS.CROSS_SOURCE" for item in result.issues))

    def test_design_knowledge_state_must_link_current_reading_and_synthesis_ids(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        self.write_analysis(registry, [self.reading(source)])
        design = {
            "schema_version": "cnki-research-design/v3",
            "knowledge_state": {
                "review_type": "embedded",
                "reading_records": "CR-OLD",
                "quality_appraisal": "No linked appraisal identity",
                "gap_authenticity": "No linked gap synthesis identity",
                "synthesis_logic": "SYN-OLD",
                "contradictory_evidence": "No linked synthesis identity",
            },
        }
        (self.base / "research_design.json").write_text(json.dumps(design), encoding="utf-8")
        result, _ = analysis_module.validate_analysis(self.base, stage="design")
        codes = {item.code for item in result.issues}
        self.assertIn("LA.DESIGN.LINK_MISSING", codes)
        self.assertIn("LA.DESIGN.LINK_UNKNOWN", codes)

        design["knowledge_state"].update(
            {
                "reading_records": "CR-S1 supplies the current source reading.",
                "quality_appraisal": "CR-S1 supplies the type-specific appraisal.",
                "gap_authenticity": "SYN-1 supplies the current gap diagnosis.",
                "synthesis_logic": "SYN-1 supplies the problem-led synthesis.",
                "contradictory_evidence": "SYN-1 records the current uncertainty and alternatives.",
            }
        )
        (self.base / "research_design.json").write_text(json.dumps(design), encoding="utf-8")
        result, _ = analysis_module.validate_analysis(self.base, stage="design")
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])

    def test_migration_scaffold_never_fabricates_completion(self) -> None:
        source = self.source("S1")
        self.write_registry([source])
        payload = analysis_module.scaffold(self.base, review_type="narrative", legacy_limited=False)
        self.assertEqual("needs-review", payload["migration_status"])
        self.assertEqual("needs-review", payload["source_readings"][0]["status"])
        self.assertEqual([], payload["syntheses"])

    def test_legacy_limited_is_audit_only_and_reports_reduced_assurance(self) -> None:
        source = self.source("S1")
        self.write_registry([source])
        payload = analysis_module.scaffold(self.base, review_type="embedded", legacy_limited=True)
        payload["review_scope"].update(
            {
                "review_question": "Audit the old manuscript without adding literature claims.",
                "search_scope": "Existing registered sources only.",
                "inclusion_boundary": "Existing cited sources.",
                "exclusion_boundary": "All newly discovered sources.",
                "synthesis_logic": "No new synthesis is introduced.",
            }
        )
        payload["legacy_declaration"]["limitation_note"] = "Critical-reading assurance was not reconstructed for this old manuscript."
        (self.base / "literature_analysis.json").write_text(json.dumps(payload), encoding="utf-8")

        result, _ = analysis_module.validate_analysis(self.base, stage="research")
        self.assertTrue(any(item.code == "LA.LEGACY.SCOPE" for item in result.issues))

        (self.base / "workflow_config.json").write_text(
            json.dumps({"task_profile": "manuscript_audit"}),
            encoding="utf-8",
        )
        result, analysis = analysis_module.validate_analysis(self.base, stage="audit")
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        self.assertTrue(any(item.code == "LA.LEGACY.REDUCED_ASSURANCE" for item in result.warnings))
        analysis_module.write_views(self.base, result, analysis)
        self.assertIn(analysis_module.GENERATED_MARKER, (self.base / "literature_analysis_check.md").read_text(encoding="utf-8"))


    # ---- verified citation edges -------------------------------------------

    def _write_registry_with_edges(self, sources: list[dict], edges: list[dict]) -> dict:
        registry = self.write_registry(sources)
        registry["edges"] = edges
        (self.base / "reference_materials" / "literature_registry.json").write_text(
            json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return registry

    def _rewrite_analysis(self, payload: dict) -> None:
        (self.base / "literature_analysis.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    @staticmethod
    def _cites(edge_id: str, source: str, target: str, **overrides) -> dict:
        edge = {
            "edge_id": edge_id,
            "from_source_id": source,
            "to_source_id": target,
            "relation": "cites",
            "evidence": "openalex",
            "verified_at": "2026-09-04",
        }
        edge.update(overrides)
        return edge

    def test_registry_without_edges_only_warns_that_coverage_is_self_reported(self) -> None:
        source = self.source("S1")
        registry = self.write_registry([source])
        self.write_analysis(registry, [self.reading(source)])
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        self.assertTrue(
            any("records no citation edges" in item.message for item in result.warnings),
            [item.as_dict() for item in result.warnings],
        )

    def test_foundational_chain_must_be_connected_by_verified_cites_edges(self) -> None:
        core = self.source("S1")
        chained = self.source("S2")
        registry = self._write_registry_with_edges(
            [core, chained],
            [self._cites("EDGE-001", "S1", "S2", relation="co-cited-with")],
        )
        payload = self.write_analysis(registry, [self.reading(core), self.background_reading(chained)])
        payload["literature_sufficiency"]["coverage"]["foundational_chain"]["source_ids"] = ["S1", "S2"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        messages = [item.message for item in result.issues]
        self.assertTrue(any("foundational_chain is not connected" in item for item in messages), messages)

    def test_verified_cites_edge_connects_the_foundational_chain(self) -> None:
        core = self.source("S1")
        chained = self.source("S2")
        registry = self._write_registry_with_edges([core, chained], [self._cites("EDGE-001", "S2", "S1")])
        payload = self.write_analysis(registry, [self.reading(core), self.background_reading(chained)])
        coverage = payload["literature_sufficiency"]["coverage"]
        coverage["foundational_chain"]["source_ids"] = ["S1", "S2"]
        coverage["foundational_chain"]["edge_ids"] = ["EDGE-001"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        summary = result.stats["literature_sufficiency"]["citation_edges"]
        self.assertEqual("verified", summary["foundational_chain"])
        self.assertEqual("self-reported", summary["counterarguments"])
        self.assertTrue(any("no critical-stance citation edge" in item.message for item in result.warnings))

    def test_critical_edge_with_quote_verifies_the_counter_position(self) -> None:
        core = self.source("S1")
        rival = self.source("S2")
        registry = self._write_registry_with_edges(
            [core, rival],
            [
                self._cites(
                    "EDGE-001",
                    "S2",
                    "S1",
                    evidence="full-text-read",
                    stance="critical",
                    context_quote="该文将奏折数量当作信息流量，忽略了内容层的失真问题。",
                )
            ],
        )
        payload = self.write_analysis(registry, [self.reading(core), self.background_reading(rival)])
        coverage = payload["literature_sufficiency"]["coverage"]
        coverage["counterarguments"]["source_ids"] = ["S1", "S2"]
        coverage["foundational_chain"]["source_ids"] = ["S1", "S2"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        summary = result.stats["literature_sufficiency"]["citation_edges"]
        self.assertEqual("verified", summary["counterarguments"])
        self.assertFalse(any("no critical-stance" in item.message for item in result.warnings))

    def test_unknown_coverage_edge_ids_and_bad_edges_block(self) -> None:
        core = self.source("S1")
        registry = self._write_registry_with_edges([core], [self._cites("EDGE-001", "S1", "GHOST")])
        payload = self.write_analysis(registry, [self.reading(core)])
        payload["literature_sufficiency"]["coverage"]["foundational_chain"]["edge_ids"] = ["EDGE-404"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        messages = " ".join(item.message for item in result.issues)
        self.assertIn("GHOST is not a registered Source ID", messages)
        self.assertIn("unknown citation edges: EDGE-404", messages)

    def test_synthesis_edge_ids_must_resolve_and_touch_the_linked_source(self) -> None:
        core = self.source("S1")
        other = self.source("S2")
        registry = self._write_registry_with_edges(
            [core, other],
            [
                self._cites("EDGE-001", "S2", "S1"),
                self._cites("EDGE-002", "S1", "S2", relation="co-cited-with"),
            ],
        )
        payload = self.write_analysis(registry, [self.reading(core), self.background_reading(other)])
        payload["literature_sufficiency"]["coverage"]["foundational_chain"]["source_ids"] = ["S1", "S2"]
        link = payload["syntheses"][0]["source_links"][0]
        link["edge_ids"] = ["EDGE-001"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        link["edge_ids"] = ["EDGE-404"]
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(
            any(item.code == "LA.SYNTHESIS.EDGE" and "unknown citation edge" in item.message for item in result.issues)
        )
        link["edge_ids"] = []
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(
            any(item.code == "LA.SYNTHESIS.EDGE" and "non-empty list" in item.message for item in result.issues)
        )

    def test_contradiction_claim_without_edge_warns_when_edges_exist(self) -> None:
        core = self.source("S1")
        other = self.source("S2")
        registry = self._write_registry_with_edges([core, other], [self._cites("EDGE-001", "S2", "S1")])
        payload = self.write_analysis(registry, [self.reading(core), self.background_reading(other)])
        payload["literature_sufficiency"]["coverage"]["foundational_chain"]["source_ids"] = ["S1", "S2"]
        payload["syntheses"][0]["source_links"][0]["relation"] = "contradicts"
        self._rewrite_analysis(payload)
        result, _ = analysis_module.validate_analysis(self.base)
        self.assertTrue(result.ok, [item.as_dict() for item in result.issues])
        self.assertTrue(
            any(
                item.code == "LA.SYNTHESIS.EDGE" and "asserted, not observed" in item.message
                for item in result.warnings
            ),
            [item.as_dict() for item in result.warnings],
        )


if __name__ == "__main__":
    unittest.main()
