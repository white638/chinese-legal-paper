#!/usr/bin/env python3
"""Behavioral tests for the explanation-first academic-prose pipeline."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "academic_prose_generation_eval", HERE / "run_generation_eval.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load run_generation_eval.py")
generation_eval = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = generation_eval
SPEC.loader.exec_module(generation_eval)


CORE_BEHAVIORS = {
    "semantic_paraphrase",
    "negative_result",
    "epistemic_calibration",
    "revision_cleanliness",
    "clarity_bridge",
    "boundary_deduplication",
    "actor_visibility",
}


class ExplanationFirstGenerationPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = generation_eval.load_corpus()
        cls.report = generation_eval.run_offline_evaluation(cls.corpus)
        cls.cases = {case["id"]: case for case in cls.corpus["cases"]}
        cls.results = {result["id"]: result for result in cls.report["results"]}

    def test_offline_pipeline_passes_without_credentials_or_quality_quota(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            report = generation_eval.run_offline_evaluation(self.corpus)
        self.assertEqual("PASS", report["status"], report["failures"])
        self.assertTrue(all(item["status"] == "PASS" for item in report["results"]))
        self.assertTrue(CORE_BEHAVIORS.issubset(report["behaviors_exercised"]))
        for retired_metric in (
            "confirmed_defensive_samples",
            "median_prose_unit_reduction",
            "prose_unit_reduction_target",
            "prose_unit_reduction_target_met",
            "quality_score",
            "novelty_score",
        ):
            self.assertNotIn(retired_metric, report)

    def test_defensive_claim_is_semantically_rewritten_not_copied(self) -> None:
        result = self.results["semantic-defensive-claim-rewrite"]
        case = self.cases[result["id"]]
        claim = result["packet"]["claim"]["canonical_proposition"]
        self.assertEqual("semantic", result["packet_mode"])
        self.assertNotIn(claim, result["candidate"])
        self.assertNotIn("本文并不试图", result["candidate"])
        self.assertTrue(result["candidate"].startswith(result["packet"]["plain_core"]))
        for atom in case["required_text"]:
            self.assertIn(atom, result["candidate"])

    def test_true_negative_result_retains_negative_polarity(self) -> None:
        result = self.results["negative-result-polarity-survives"]
        atoms = result["packet"]["claim"]["protected_atoms"]
        self.assertEqual("negative", atoms["polarity"])
        self.assertEqual("null", atoms["direction"])
        self.assertEqual("null_result", atoms["inferential_strength"])
        self.assertIn("未显著提高", result["candidate"])
        self.assertIn("未获样本支持", result["candidate"])

    def test_association_does_not_drift_to_causation_direction_or_scope(self) -> None:
        result = self.results["association-strength-direction-scope-stable"]
        case = self.cases[result["id"]]
        atoms = result["packet"]["claim"]["protected_atoms"]
        self.assertEqual("association", atoms["inferential_strength"])
        self.assertEqual("positive", atoms["direction"])
        self.assertIn(case["required_scope_text"], result["candidate"])
        for literal in ("2019", "2023", "相关", r"\cite{local-results-103}"):
            self.assertIn(literal, result["candidate"])
        for overclaim in case["forbidden_text"]:
            self.assertNotIn(overclaim, result["candidate"])

    def test_reviewer_comment_is_firewalled_and_leaves_no_patch_seam(self) -> None:
        case = self.cases["review-comment-translates-to-writer-safe-delta"]
        result = self.results[case["id"]]
        probe = copy.deepcopy(case["request"])
        probe[case["firewall_probe_key"]] = "审稿人认为机制解释不足"
        with self.assertRaises(generation_eval.ProsePacketError):
            generation_eval.compile_prose_packet(
                probe, registered_ids=case["registered_ids"]
            )
        self.assertIsNone(generation_eval.REVIEW_PROCESS_LEAK_RE.search(result["candidate"]))
        self.assertIsNone(generation_eval.PATCH_SEAM_RE.search(result["candidate"]))
        for leaked_marker in ("审稿人", "为回应", "修改稿", "这一质疑"):
            self.assertNotIn(leaked_marker, result["candidate"])
        self.assertIn("责任确认由多部门协商转为牵头部门判定", result["candidate"])

    def test_registered_bridge_may_grow_locally_without_new_fact_or_citation(self) -> None:
        result = self.results["registered-warrant-bridge-allows-local-growth"]
        action = result["clarity_ledger"]["actions"][0]
        self.assertGreater(result["clarity_delta"], 0)
        self.assertLessEqual(result["clarity_growth_ratio"], 0.15)
        self.assertEqual([], result["clarity_warnings"])
        self.assertEqual("BRIDGE", action["action"])
        self.assertEqual("explanation_path", action["source_kind"])
        self.assertEqual("explanation_path:3", action["source_anchor"])
        self.assertTrue(action["no_new_fact"])
        self.assertTrue(action["no_new_citation"])
        self.assertTrue(action["no_inference_strengthening"])
        self.assertEqual(
            set(),
            generation_eval._new_numbers(result["writer_draft"], result["candidate"]),
        )
        self.assertEqual(
            set(),
            generation_eval._new_citations(result["writer_draft"], result["candidate"]),
        )

        bad_ledger = copy.deepcopy(result["clarity_ledger"])
        bad_ledger["actions"][0]["action"] = "REPLACE"
        bad = generation_eval.check_clarity(
            result["packet"],
            result["writer_draft"],
            result["candidate"],
            bad_ledger,
            registered_ids=self.cases[result["id"]]["registered_ids"],
        )
        self.assertTrue(any("only BRIDGE or DEFINE" in issue for issue in bad.issues))

    def test_english_explanation_is_not_misclassified_as_a_citation(self) -> None:
        before = "Evidence establishes the observed association."
        after = before + " This mechanism clarifies the coordination process."
        self.assertEqual(set(), generation_eval._new_citations(before, after))
        self.assertEqual(
            {"new-source"},
            generation_eval._new_citations(after, after + r" \cite{new-source}"),
        )

    def test_boundary_id_is_positive_single_and_after_the_claim(self) -> None:
        result = self.results["boundary-positive-scope-once-after-claim"]
        case = self.cases[result["id"]]
        boundaries = [
            item
            for item in result["packet"]["required_boundaries"]
            if item["id"] == case["expected_boundary_id"]
        ]
        self.assertEqual(1, len(boundaries))
        self.assertEqual("positive_scope", boundaries[0]["preferred_realization"])
        boundary_text = case["expected_boundary_text"]
        self.assertEqual(1, result["candidate"].count(boundary_text))
        self.assertGreater(
            result["candidate"].find(boundary_text),
            result["candidate"].find(result["packet"]["plain_core"]),
        )

    def test_actor_restoration_preserves_registered_terms(self) -> None:
        result = self.results["nominalization-restores-actors-and-terms"]
        for actor in ("市级专班", "牵头部门", "参与单位"):
            self.assertIn(actor, result["candidate"])
        for term in ("事项移交权", "跨部门协调"):
            self.assertIn(term, result["candidate"])
        self.assertIn("直接调度", result["candidate"])

    def test_verbatim_mode_remains_an_explicit_compatibility_exception(self) -> None:
        result = self.results["verbatim-formal-hypothesis-remains-exact"]
        claim = result["packet"]["claim"]
        self.assertEqual("verbatim", claim["realization_mode"])
        self.assertEqual("formal_hypothesis", claim["verbatim_reason"])
        self.assertIn(claim["canonical_proposition"], result["candidate"])

    def test_static_trigger_and_mastery_sets_encode_all_seven_behaviors(self) -> None:
        trigger_cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
        mastery_cases = json.loads(
            (HERE / "mastery_cases.json").read_text(encoding="utf-8")
        )
        trigger_ids = {case["id"] for case in trigger_cases}
        mastery_ids = {case["id"] for case in mastery_cases}
        self.assertTrue(
            {
                "explanation-first-defensive-claim-trigger",
                "necessary-negative-result-is-not-defense",
                "association-with-positive-scope-is-calibrated",
                "review-response-register-is-frontstage-leak",
                "warrant-bridge-is-substantive-not-padding",
                "positive-scope-boundary-after-claim",
                "actor-restored-with-term-preserved",
            }.issubset(trigger_ids)
        )
        self.assertTrue(
            {
                "semantic-paraphrase-removes-author-defense",
                "negative-result-remains-negative-and-explained",
                "association-does-not-become-causation",
                "review-comment-becomes-clean-research-logic",
                "registered-warrant-bridge-may-grow-locally",
                "boundary-is-positive-concentrated-and-post-claim",
                "nominalization-restores-actor-without-term-loss",
                "problem-arc-changes-the-live-question",
                "problem-arc-refuses-false-teleology",
                "thought-move-distinguishes-before-it-advances",
                "epistemic-hook-delays-only-the-registered-answer",
                "epistemic-hook-payment-deepens-the-question",
                "quotation-keeps-context-and-does-analytic-work",
                "source-voice-does-not-displace-author-analysis",
                "scene-return-changes-the-opening-understanding",
                "closure-stays-grounded-in-the-evidence-chain",
                "title-resonance-is-explained-in-the-body",
            }.issubset(mastery_ids)
        )

    def test_live_blind_prompt_is_credential_gated_and_review_required_fails(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            report = generation_eval.run_live_blind(self.corpus)
        self.assertEqual("SKIP", report["status"])
        self.assertEqual("credentialed-live-blind", report["mode"])
        self.assertEqual(
            1,
            generation_eval.exit_code_for_report(
                {"status": "REVIEW_REQUIRED"}, live_blind=True
            ),
        )
        self.assertEqual(
            0,
            generation_eval.exit_code_for_report(
                {"status": "EVIDENCE_READY"}, live_blind=True
            ),
        )


if __name__ == "__main__":
    unittest.main()
