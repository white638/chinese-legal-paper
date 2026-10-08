"""Deterministic research-judgment regressions, not model-quality measurements."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import problem_orientation_check as contribution
import prose_packet
import research_decision
import taste_cards
import taste_exemplars
import taste_judge
import topic_packet
from avereth_core import workflow_registry
from test_problem_orientation_check import accepted_authority, write_knowledge_fixture
from test_taste_judge import _candidate, _response, prefer_candidate, proposal_provenance
import test_topic_packet as topic_fixtures


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class CalibrationCases(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.values = {"reader prior": "The previous explanation applies throughout the sampled scope.", "reader posterior": "The accepted comparison limits the explanation to resource-rich organizations."}
        write_knowledge_fixture(self.base, self.values["reader prior"], self.values["reader posterior"])
        patcher = mock.patch("prose_packet.discover_execution_authority", side_effect=accepted_authority)
        self.authority = patcher.start()
        self.addCleanup(patcher.stop)

    def change_update(self, **changes):
        payload = read(self.base / "method_execution.json")
        payload["knowledge_update"].update(changes)
        write(self.base / "method_execution.json", payload)

    def issues(self):
        return contribution.knowledge_update_issues(self.base, self.values)

    def test_boundary_refinement_is_a_supported_update(self):
        self.assertEqual([], self.issues())

    def test_synonym_restatement_is_not_rescued_by_wording(self):
        self.change_update(semantic_assessment={"status": "restatement", "rationale": "The sentence rearranges words without changing scope or evidential confidence."})
        self.assertTrue(any("restatement" in issue for issue in self.issues()))

    def test_same_conclusion_can_gain_evidential_confidence(self):
        self.values["reader posterior"] = self.values["reader prior"]
        self.change_update(supported_update=self.values["reader prior"], kind="description-measurement")
        self.assertEqual([], self.issues())

    def test_unsupported_semantic_assessment_is_not_accepted(self):
        self.change_update(semantic_assessment={"status": "uncertain", "rationale": "Evidence cannot distinguish the proposed update from the baseline."})
        self.assertTrue(self.issues())

    def test_unknown_source_id_is_rejected(self):
        self.assertTrue(contribution.source_reference_issues(self.base, ["SRC-999"]))

    def test_fake_doi_is_rejected(self):
        self.assertTrue(contribution.source_reference_issues(self.base, ["10.1234/nonexistent"]))

    def test_real_doi_alias_resolves(self):
        self.assertEqual([], contribution.source_reference_issues(self.base, ["https://doi.org/10.1000/baseline"]))

    def test_unregistered_synthesis_is_rejected(self):
        self.assertTrue(contribution.source_reference_issues(self.base, ["SYN-999"]))

    def test_synthesis_links_and_source_content_resolve(self):
        self.assertEqual([], contribution.source_reference_issues(self.base, ["SYN-02"]))

    def test_synthesis_cannot_link_outside_its_bound_sources(self):
        from literature_analysis import registry_binding_digest
        path = self.base / "literature_analysis.json"
        payload = read(path)
        payload["registry_binding"] = {"source_ids": [], "digest": registry_binding_digest(read(self.base / "reference_materials/literature_registry.json"), [])}
        write(path, payload)
        self.assertTrue(any("outside its registry binding" in issue for issue in self.issues()))

    def test_malformed_synthesis_collection_returns_diagnostic(self):
        path = self.base / "literature_analysis.json"
        payload = read(path)
        payload["syntheses"] = None
        write(path, payload)
        self.assertTrue(any("syntheses must" in issue for issue in self.issues()))

    def test_lexical_overlap_is_only_an_advisory(self):
        self.values["reader posterior"] = self.values["reader prior"]
        self.change_update(supported_update=self.values["reader prior"])
        report = contribution.render_report(self.base, "build", self.issues())
        self.assertIn("Status: PASS", report)
        self.assertIn("Advisory", report)

    def test_source_artifact_mutation_invalidates_update(self):
        (self.base / "reference_materials/baseline.txt").write_text("changed", encoding="utf-8")
        self.assertTrue(any("hash" in issue for issue in self.issues()))

    def test_registry_mutation_invalidates_synthesis(self):
        path = self.base / "reference_materials/literature_registry.json"
        payload = read(path)
        payload["sources"][0]["title"] = "Changed source identity"
        write(path, payload)
        self.assertTrue(any("stale" in issue for issue in self.issues()))

    def test_discovery_only_source_cannot_support_update(self):
        path = self.base / "reference_materials/literature_registry.json"
        payload = read(path)
        payload["sources"][0]["citation_scope"] = "candidate-only"
        write(path, payload)
        self.assertTrue(any("final-source" in issue for issue in self.issues()))

    def test_source_retraction_cannot_be_ignored(self):
        path = self.base / "reference_materials/literature_registry.json"
        payload = read(path)
        payload["sources"][0]["verification"]["retraction_status"] = "retracted"
        write(path, payload)
        self.assertTrue(any("retracted" in issue for issue in self.issues()))

    def test_failed_execution_cannot_be_rescued_by_contribution(self):
        self.authority.side_effect = lambda *_: {"status": "BLOCKED", "results": {}}
        self.assertTrue(any("method execution" in issue for issue in self.issues()))

    def test_result_id_must_resolve_to_accepted_execution(self):
        self.change_update(result_ids=["RES-999"])
        self.assertTrue(any("not accepted" in issue for issue in self.issues()))

    def test_update_claim_must_be_bound_to_the_accepted_result(self):
        self.change_update(claim_ids=["CLM-999"])
        self.assertTrue(any("not supported" in issue for issue in self.issues()))

    def test_null_result_does_not_automatically_prove_no_effect(self):
        self.change_update(kind="negative-result", null_interpretation="no-effect")
        self.assertTrue(any("nonsignificance" in issue for issue in self.issues()))

    def test_honest_inconclusive_result_can_be_reported(self):
        self.change_update(kind="negative-result", null_interpretation="inconclusive")
        self.assertEqual([], self.issues())

    def test_same_data_rerun_is_not_independent_replication(self):
        self.change_update(kind="independent-replication", replication={"independent_material": False, "independence_basis": "The same observations were passed through the script again."})
        self.assertTrue(any("independent replication" in issue for issue in self.issues()))

    def test_historical_baseline_does_not_become_prospective(self):
        self.change_update(baseline_origin="contemporaneous")
        self.assertTrue(any("baseline origin" in issue for issue in self.issues()))

    def test_missing_historical_baseline_is_not_fabricated(self):
        write(self.base / "research_design.json", {})
        before = (self.base / "research_design.json").read_bytes()
        self.assertTrue(any("missing historical priors" in issue for issue in self.issues()))
        self.assertEqual(before, (self.base / "research_design.json").read_bytes())

    def test_contribution_markdown_cannot_own_a_different_result(self):
        self.values["reader posterior"] = "A more spectacular but unsupported result."
        self.assertTrue(any("canonical JSON" in issue for issue in self.issues()))

    def test_malformed_result_references_are_diagnostics(self):
        self.change_update(result_ids=[{}])
        self.assertTrue(self.issues())


class TasteCalibrationCases(unittest.TestCase):
    def setUp(self):
        self.registry = taste_cards.load_registry()
        self.card = taste_cards.card_by_slug(self.registry, "comparative-politics")
        self.shortlist = {role: [{"record_id": role.upper(), "title": f"Distinct {role} topic", "abstract": "An argument whose quality must be assessed from its actual content.", "cited_by": number}] for role, number in (("positive", 9999), ("negative", 0), ("middle", 40))}

    def plan(self, variant="base", *, origin="contemporaneous"):
        candidate = _candidate("CAND-01", "When do accountability reforms fail?", "Refine the scope of the accountability explanation.")
        reference = {"ref_id": "REF-01", "identifier": "sample-plan", "comparison_view": {"maturity": "proposal", "origin": origin, "provenance": proposal_provenance(), "question": "Which allocation rule changes local compliance?", "update": "Distinguish allocation rules under comparable conditions."}}
        return taste_judge.build_plan(card=self.card, registry=self.registry, candidates=[candidate], references=[reference], variant=variant)

    def test_anonymous_prompt_does_not_reveal_sampling_strata(self):
        prompt = taste_exemplars.selection_prompt(self.card, self.shortlist, pick_positive=3, pick_negative=2)
        for leaked in ("A 组", "B 组", "最多引用", "引用最少", "9999", "POSITIVE", "NEGATIVE", "MIDDLE"):
            self.assertNotIn(leaked, prompt)

    def test_low_citation_sample_can_be_positive(self):
        pool = taste_exemplars.anonymous_pool(self.shortlist)
        low = next(key for key, item in pool.items() if item["record_id"] == "NEGATIVE")
        response = {"positive": [{"record_id": low, "why": "The evidence in the abstract establishes a precise and consequential question."}], "negative": [], "uncertain": [{"record_id": key, "why": "The supplied abstract does not establish enough evidence for a stable judgment."} for key in pool if key != low], "rejected": []}
        self.assertEqual([], taste_exemplars.selection_issues(response, self.shortlist, pick_positive=3, pick_negative=2))

    def test_every_sample_can_receive_uncertain_without_negative_quota(self):
        response = {"positive": [], "negative": [], "uncertain": [{"record_id": key, "why": "The material is insufficient to judge the actual depth of the argument."} for key in taste_exemplars.anonymous_pool(self.shortlist)], "rejected": []}
        self.assertEqual([], taste_exemplars.selection_issues(response, self.shortlist, pick_positive=3, pick_negative=2))

    def test_card_registration_does_not_require_negative_examples(self):
        card = copy.deepcopy(self.card)
        card["exemplar_selection"] = {"protocol": taste_exemplars.SELECTION_PROTOCOL}
        card["exemplars"] = {"positive": [{"title": "Registered example"}], "negative": []}
        self.assertEqual("exemplars-registered", taste_cards.card_status(card))
        self.assertEqual("unvalidated", taste_cards.exemplar_calibration_status(card))

    def test_old_registered_card_remains_unreviewed(self):
        card = copy.deepcopy(self.card)
        card.pop("exemplar_selection", None)
        card["exemplars"] = {"positive": [{"title": "Historical example"}], "negative": []}
        self.assertEqual("legacy-unreviewed", taste_cards.exemplar_calibration_status(card))

    def test_original_proposal_does_not_require_published_title_and_claim(self):
        view = self.plan()["references"][0]["comparison_view"]
        entry = taste_judge._pool_entry("original-plan", "", "", "references", view)
        self.assertIsNotNone(entry)
        self.assertEqual(view, entry["comparison_view"])
        self.assertEqual(view["question"], entry["title"])

    def test_metadata_cannot_self_certify_a_calibrated_judge(self):
        payload = {"schema_version": taste_judge.SCHEMA_VERSION, "authority": "signal-not-gate", "calibration_status": "calibrated", "decision_policy": "rank", "judgements": []}
        self.assertTrue(any("opinions-only" in issue for issue in taste_judge.judgement_issues(payload)))

    def test_identical_view_fields_and_individual_analyses(self):
        plan = self.plan()
        prompt = taste_judge.judge_prompt(plan, plan["items"][0], self.card)
        self.assertNotIn("问题家族", prompt)
        self.assertNotIn("CAND-01", prompt)
        for field in taste_judge.VIEW_FIELDS:
            self.assertEqual(2, prompt.count(field + "："))
        self.assertIn("one_analysis", prompt)
        self.assertIn("two_analysis", prompt)

    def test_reconstructed_proposal_cannot_be_an_independent_comparator(self):
        plan = self.plan(origin="retrospective")
        item = plan["items"][0]
        self.assertEqual([], item["pairs"])
        self.assertFalse(item["unavailable_pairs"][0]["comparable"])
        with self.assertRaises(ValueError):
            taste_judge.judgement_from_response(item, _response(["P1"], "one"))

    def test_uncertainty_is_not_counted_as_a_loss(self):
        item = self.plan()["items"][0]
        result = taste_judge.judgement_from_response(item, _response(["P1"], "uncertain"))
        self.assertEqual(1, result["abstentions"])
        self.assertEqual("uncertain", result["pairs"][0]["preferred"])
        self.assertEqual([], taste_judge.rank([result]))

    def test_order_swap_keeps_text_and_reverses_position(self):
        first, second = self.plan(), self.plan("order-swap")
        self.assertEqual(first["items"][0]["comparison_view"], second["items"][0]["comparison_view"])
        self.assertNotEqual(first["items"][0]["pairs"][0]["candidate_position"], second["items"][0]["pairs"][0]["candidate_position"])

    def test_positional_preference_is_measured_on_the_same_pair(self):
        base = self.plan()["items"][0]
        swapped = self.plan("order-swap")["items"][0]
        summary = taste_judge.probe_summary([taste_judge.judgement_from_response(base, _response(["P1"], "one"))], [taste_judge.judgement_from_response(swapped, _response(["P1"], "one"))], variant="order-swap")
        self.assertTrue(summary["position_inconsistent"])
        self.assertEqual(1, summary["flips"])

    def test_content_change_is_not_automatically_style_bias(self):
        item = self.plan()["items"][0]
        base = taste_judge.judgement_from_response(item, _response(["P1"], "one"))
        changed = taste_judge.judgement_from_response(item, _response(["P1"], "two"))
        summary = taste_judge.probe_summary([base], [changed], variant="hot-strip")
        self.assertEqual(1, summary["flips"])
        self.assertEqual("unverified", summary["semantic_status"])
        self.assertFalse(summary["shortcut_suspected"])


class DiscoveryAndNotesCases(unittest.TestCase):
    def test_narrow_portfolio_can_use_actual_alternatives_and_stopping_reason(self):
        self.assertTrue(research_decision._narrow_exemption_valid({"actual_alternatives": ["The timing alternative is already answered by the registered comparison."], "stopping_reason": "The only remaining feasible question targets the documented anomaly; additional variants would repeat the same inferential target."}))

    def test_narrow_portfolio_cannot_pass_with_placeholder_reason(self):
        self.assertFalse(research_decision._narrow_exemption_valid({"actual_alternatives": [], "stopping_reason": "TODO"}))

    def test_phenomenon_entry_uses_only_authorized_materials(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            helper = topic_fixtures.TopicPacketCounterfactualTests()
            config = helper._intake(base, origin_mode="phenomenon_first")
            (base / "authorized.txt").write_text("Observed classification changed before the outcome changed.", encoding="utf-8")
            (base / "private.txt").write_text("UNAUTHORIZED_CANARY", encoding="utf-8")
            packet = topic_packet.build_packet(config, current_user_request="Explore this authorized anomaly.", compiled_at="2026-09-05T12:00:00Z", declared_workspace_scope=["authorized.txt"])
            projection = topic_packet.declared_material_projection(packet, base)
            prompt = topic_packet.canonical_generation_prompt(packet, next(iter(topic_packet.GENERATION_LANE_INSTRUCTIONS)), projection)
            self.assertNotIn("UNAUTHORIZED_CANARY", prompt)
            self.assertIn("not a negative value signal", prompt)
            self.assertEqual("phenomenon_first", research_decision.generation_lane_for_origin(packet["origin_mode"]))
            (base / "authorized.txt").write_text("Changed observation.", encoding="utf-8")
            self.assertNotEqual(projection, topic_packet.declared_material_projection(packet, base))

    def test_direction_entry_does_not_opt_into_material_exposure(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = topic_fixtures.TopicPacketCounterfactualTests()._intake(base)
            packet = topic_packet.build_packet(config, current_user_request="Explore explanations independently.", compiled_at="2026-09-05T12:00:00Z", literature_reconnaissance=topic_fixtures.synthetic_recon())
            with self.assertRaises(ValueError):
                topic_packet.canonical_generation_prompt(packet, next(iter(topic_packet.GENERATION_LANE_INSTRUCTIONS)), [{"path": "private.txt", "sha256": "a" * 64, "content": "hidden"}])

    def test_notes_cannot_register_writer_claims_or_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "research_notes.md").write_text("CLM-999 RES-999 EVD-999: hypothetical effect of 78 percent", encoding="utf-8")
            self.assertEqual(frozenset(), prose_packet.discover_registered_ids(base))
            self.assertNotIn("research_notes.md", prose_packet.SUPPORT_FILES)

    def test_notes_are_optional_and_not_receipt_dependencies(self):
        note = workflow_registry.artifact_definition("research_notes.md")
        self.assertFalse(note.required_stages)
        self.assertFalse(note.receipt_bindings)
        self.assertNotIn("build", note.writable_stages)


if __name__ == "__main__":
    unittest.main()
