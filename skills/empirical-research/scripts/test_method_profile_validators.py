#!/usr/bin/env python3
"""Executable positive and adversarial checks for every nontrivial typed profile."""

from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from validators import causal_design, event_history, institutional_grammar, network, text_alignment
from validators.common import ValidationContext


class TypedProfileValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def context(self, schema: str, contract: dict, files: dict[str, str], *, narrowed: bool = False):
        artifacts = {}
        refs = []
        for identifier, content in files.items():
            path = self.base / "artifacts" / (identifier.lower() + (".csv" if content.startswith("csv:") else ".txt"))
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = content[4:] if content.startswith("csv:") else content
            path.write_text(payload, encoding="utf-8", newline="")
            artifacts[identifier] = {
                "id": identifier,
                "path": path.relative_to(self.base).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "role": "typed-profile fixture",
            }
            refs.append(identifier)
        run = {
            "artifact_refs": refs,
            "inference_disposition": {
                "status": "narrowed" if narrowed else "retained",
                "reason_codes": ["FIXTURE_DIAGNOSTIC"] if narrowed else [],
                "failed_diagnostic_ids": ["FIXTURE"] if narrowed else [],
                "allowed_claim_types": ["descriptive"] if narrowed else ["causal_effect"],
                "prohibited_interpretations": ["causal"] if narrowed else [],
            },
        }
        return ValidationContext(
            base=self.base,
            schema_id=schema,
            contract=contract,
            route={"family": "quantitative"},
            run=run,
            artifacts=artifacts,
            path="runs[0]",
        )

    @staticmethod
    def codes(findings) -> set[str]:
        return {finding.code for finding in findings}

    def causal_core(self) -> tuple[dict, dict[str, str]]:
        files = {"ART-DIAG": "supported\n", "ART-EST": "estimate\n", "ART-SENS": "sensitivity\n"}
        contract = {
            "estimand": {"quantity": "ATT", "population": "eligible units", "contrast": "treated versus untreated", "time_horizon": "one year"},
            "unit_of_treatment": "document",
            "unit_of_analysis": "document",
            "independence_unit": "document",
            "counterfactual": {"comparison_state": "untreated", "comparison_population": "eligible controls", "time_basis": "same period"},
            "identification_assumptions": [{"id": "ASM-1", "statement": "registered identifying assumption", "status": "supported", "diagnostic_artifact_id": "ART-DIAG"}],
            "estimate_artifact_id": "ART-EST",
            "sensitivity_artifact_id": "ART-SENS",
        }
        return contract, files

    def test_causal_panel_profile_reaches_validator(self) -> None:
        contract, files = self.causal_core()
        files["ART-PARALLEL"] = "parallel-trends diagnostic\n"
        contract.update({
            "treatment_cohorts": "staggered cohorts",
            "control_group": "not-yet-treated",
            "pre_treatment_window": "four periods",
            "spillover_plan": "bounded interference audit",
            "clustering_level": "assignment unit",
            "alternative_timing_plan": "registered timing shifts",
            "placebo_plan": "pre-treatment placebo",
            "parallel_trends": {"status": "not-rejected", "window": "t-4 to t-1", "diagnostic_artifact_id": "ART-PARALLEL"},
        })
        ctx = self.context("causal-panel/v1", contract, files)
        self.assertEqual(set(), self.codes(causal_design.validate(ctx)))
        contract["parallel_trends"]["status"] = "failed"
        self.assertIn("ME.INFERENCE.PARALLEL_TRENDS_FAILED", self.codes(causal_design.validate(ctx)))

    def test_text_matching_overlap_forces_exploratory_ceiling(self) -> None:
        contract, files = self.causal_core()
        files.update(
            {
                "ART-BEFORE": "balance before\n",
                "ART-AFTER": "balance after\n",
                "ART-MATCHES": "csv:match_id,treated_id,control_id,distance,evidence_locator\nM1,T1,C1,0.12,corpus:M1\n",
                "ART-MATCH-REVIEW": '{"review_run_id":"match-review-01","primary_output_artifact_id":"ART-MATCHES","reviewed_item_ids":["M1"],"resolution_rule":"check frozen threshold and source evidence","unresolved_count":0}\n',
                "ART-MATCH-RUNS": '{"runs":[{"role":"primary","run_id":"match-primary-01","context_id":"ctx-match-primary","model_name":"research-model","model_revision":"rev-a","completed_at":"2026-08-16T08:00:00Z","system_prompt_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","user_prompt_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","output_artifact_id":"ART-MATCHES"},{"role":"independent_review","run_id":"match-review-01","context_id":"ctx-match-review","model_name":"research-model","model_revision":"rev-b","completed_at":"2026-08-16T09:00:00Z","system_prompt_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","user_prompt_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","output_artifact_id":"ART-MATCH-REVIEW"}]}\n',
                "ART-MATCH-DISAGREE": "csv:item_id,status,resolution,evidence_locator\nM1,no-disagreement,confirmed,corpus:M1\n",
            }
        )
        contract.update({
            "matching_unit": "document",
            "text_representation": "frozen representation",
            "distance_function": "registered cosine distance",
            "matching_threshold": "predeclared threshold",
            "template_handling": "common templates removed",
            "matches_artifact_id": "ART-MATCHES",
            "balance_before_artifact_id": "ART-BEFORE",
            "balance_after_artifact_id": "ART-AFTER",
            "independent_match_validation_artifact_id": "ART-MATCH-REVIEW",
            "researcher_run_manifest_artifact_id": "ART-MATCH-RUNS",
            "match_disagreement_artifact_id": "ART-MATCH-DISAGREE",
            "data_role_separation": {"status": "overlap-disclosed-exploratory"},
        })
        retained = self.context("text-matching/v2", contract, files)
        self.assertIn("ME.INFERENCE.OVERLAP_NOT_DOWNGRADED", self.codes(causal_design.validate(retained)))
        narrowed = self.context("text-matching/v2", contract, files, narrowed=True)
        self.assertNotIn("ME.INFERENCE.OVERLAP_NOT_DOWNGRADED", self.codes(causal_design.validate(narrowed)))
        contract["independent_match_validation_artifact_id"] = "ART-MATCHES"
        self.assertIn(
            "ME.INFERENCE.TEXT_MATCH.REVIEW_NOT_INDEPENDENT",
            self.codes(causal_design.validate(self.context("text-matching/v2", contract, files, narrowed=True))),
        )

    def test_event_history_profile_checks_time_and_effective_unit(self) -> None:
        files = {
            "ART-DATA": "csv:id,start,stop,event\nB1,0,3,committee\n",
            "ART-DIAG": "diagnostics\n",
            "ART-EST": "estimate\n",
            "ART-SENS": "sensitivity\n",
        }
        contract = {
            "estimand": {"quantity": "cause-specific hazard", "population": "bill families", "contrast": "signalled versus unsignalled", "time_horizon": "one congress"},
            "unit_of_treatment": "bill_family",
            "unit_of_analysis": "bill_family_period",
            "independence_unit": "bill_family",
            "time_origin": "introduction",
            "censoring_rule": "end of congress",
            "clustering_level": "bill_family",
            "event_types": ["committee", "passage"],
            "data": {"artifact_id": "ART-DATA", "start_column": "start", "stop_column": "stop", "event_column": "event", "id_column": "id"},
            "diagnostics_artifact_id": "ART-DIAG",
            "estimate_artifact_id": "ART-EST",
            "sensitivity_artifact_id": "ART-SENS",
            "effective_sample_size": {"n": 1, "unit": "bill_family"},
        }
        ctx = self.context("event-history/v1", contract, files)
        self.assertEqual(set(), self.codes(event_history.validate(ctx)))
        contract["effective_sample_size"]["unit"] = "sentence"
        self.assertIn("ME.INFERENCE.PSEUDO_REPLICATION", self.codes(event_history.validate(ctx)))

    def test_text_alignment_profile_blocks_reversed_direction(self) -> None:
        files = {
            "ART-SOURCE": "source manifest\n",
            "ART-TARGET": "target manifest\n",
            "ART-MATCH": "csv:source_id,target_id,source_time,target_time,similarity,boilerplate_status,shared_source_status\nS1,T1,2025-01-01,2026-01-01,0.8,removed,audited-no-common-source\n",
            "ART-SENS": "threshold sensitivity\n",
            "ART-ALIGN-REVIEW": '{"review_run_id":"align-review-01","primary_output_artifact_id":"ART-MATCH","reviewed_item_ids":["S1::T1"],"resolution_rule":"check source spans and registered threshold","unresolved_count":0}\n',
            "ART-ALIGN-RUNS": '{"runs":[{"role":"primary","run_id":"align-primary-01","context_id":"ctx-align-primary","model_name":"research-model","model_revision":"rev-a","completed_at":"2026-08-16T08:00:00Z","system_prompt_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","user_prompt_sha256":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","output_artifact_id":"ART-MATCH"},{"role":"independent_review","run_id":"align-review-01","context_id":"ctx-align-review","model_name":"research-model","model_revision":"rev-b","completed_at":"2026-08-16T09:00:00Z","system_prompt_sha256":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","user_prompt_sha256":"dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd","output_artifact_id":"ART-ALIGN-REVIEW"}]}\n',
            "ART-ALIGN-DISAGREE": "csv:item_id,status,resolution,evidence_locator\nS1::T1,no-disagreement,confirmed,source:S1-target:T1\n",
        }
        contract = {
            "alignment_unit": "clause",
            "direction_rule": "source-precedes-target",
            "boilerplate_policy": "remove templates",
            "third_source_policy": "audit common sources",
            "translation_policy": "record language chain",
            "threshold_plan": {"selection_basis": "source-grounded independent reference sample", "sensitivity_range": "0.6-0.9"},
            "source_manifest_artifact_id": "ART-SOURCE",
            "target_manifest_artifact_id": "ART-TARGET",
            "matches_artifact_id": "ART-MATCH",
            "threshold_sensitivity_artifact_id": "ART-SENS",
            "independent_validation_artifact_id": "ART-ALIGN-REVIEW",
            "researcher_run_manifest_artifact_id": "ART-ALIGN-RUNS",
            "disagreement_log_artifact_id": "ART-ALIGN-DISAGREE",
        }
        ctx = self.context("text-alignment/v2", contract, files)
        self.assertEqual(set(), self.codes(text_alignment.validate(ctx)))
        match = self.base / ctx.artifacts["ART-MATCH"]["path"]
        match.write_text("source_id,target_id,source_time,target_time,similarity,boilerplate_status,shared_source_status\nS1,T1,2027-01-01,2026-01-01,0.8,removed,audited-no-common-source\n", encoding="utf-8")
        ctx.artifacts["ART-MATCH"]["sha256"] = hashlib.sha256(match.read_bytes()).hexdigest()
        self.assertIn("ME.ALIGNMENT.DIRECTION_VIOLATION", self.codes(text_alignment.validate(ctx)))

    def test_institutional_grammar_profile_separates_conflict_types(self) -> None:
        fields = ["actor", "deontic", "action", "object", "condition", "exception", "enforcement_body", "consequence"]
        files = {
            "ART-PARSED": "csv:" + ",".join(fields) + "\nagency,must,report,data,when requested,none,authority,penalty\n",
            "ART-MATCH": "csv:source_clause_id,target_clause_id,category\nC1,C2,procedural_gap\n",
            "ART-AMB": "ambiguity review\n",
            "ART-SENS": "matching sensitivity\n",
        }
        contract = {
            "clause_unit": "legal clause",
            "ambiguity_policy": "independent model adjudication with evidence trace",
            "grammar_fields": fields,
            "match_categories": ["full_alignment", "partial_alignment", "functional_equivalence", "parallel_compatible", "procedural_gap", "substantive_conflict", "indeterminate"],
            "parsed_clauses_artifact_id": "ART-PARSED",
            "clause_matches_artifact_id": "ART-MATCH",
            "ambiguity_review_artifact_id": "ART-AMB",
            "sensitivity_artifact_id": "ART-SENS",
        }
        ctx = self.context("institutional-grammar/v1", contract, files)
        self.assertEqual(set(), self.codes(institutional_grammar.validate(ctx)))
        contract["match_categories"].append("single_compatibility_score")
        self.assertIn("ME.INSTITUTIONAL_GRAMMAR.CATEGORY_INVALID", self.codes(institutional_grammar.validate(ctx)))

    def test_discourse_network_profile_cannot_be_coword_network(self) -> None:
        files = {
            "ART-EDGES": "csv:actor,claim,position,time,source\nA1,C1,support,2026-01-01,S1\n",
            "ART-DEP": "dependence diagnostics\n",
            "ART-PROV": "source provenance\n",
        }
        contract = {
            "network_kind": "actor-claim-position",
            "edge_schema": ["actor", "claim", "position", "time", "source"],
            "network_boundary": "registered actors and claims",
            "dependence_plan": "network-aware uncertainty",
            "source_identity_policy": "source production chains audited",
            "edges_artifact_id": "ART-EDGES",
            "dependence_diagnostics_artifact_id": "ART-DEP",
            "source_provenance_artifact_id": "ART-PROV",
        }
        ctx = self.context("discourse-network/v1", contract, files)
        self.assertEqual(set(), self.codes(network.validate(ctx)))
        contract["network_kind"] = "co-word"
        self.assertIn("ME.DISCOURSE_NETWORK.COWORD_CONFLATION", self.codes(network.validate(ctx)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
