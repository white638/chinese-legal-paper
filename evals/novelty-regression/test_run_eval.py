"""Original synthetic controls exercise the contract; no research accuracy is claimed."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from run_eval import RESPONSE_SCHEMA, binding, bound, compare, digest, evaluate, export_requests, import_responses, input_bound, load, prediction_records, response_issues


class NoveltyRegressionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        sources = []
        for index in range(6):
            name = "S" + str(index)
            quote = "SYNTHETIC observed relation " + str(index) + "."
            path = self.root / (name + ".txt")
            path.write_text(quote, encoding="utf-8")
            sources.append({"source_id": name, "title": "Synthetic source " + str(index), "url": "https://example.invalid/" + name,
                            "content": {"path": path.name, "sha256": binding(path)["sha256"]},
                            "locators": [{"locator": "p1", "exact_quote": quote}]})
        self.cases = {"schema_version": "avereth-novelty-regression-cases/v1", "synthetic": True, "bank_version": 1,
                      "sources": sources, "cases": [
                          {"id": "known", "family": "rename", "groundtruth_type": "source_derived_control",
                           "candidate_origin": "counterfactual_transform", "control_kind": "known_prior_claim",
                           "candidate_claim": sources[0]["locators"][0]["exact_quote"], "source_ids": ["S0"]},
                          {"id": "replication", "family": "replication", "groundtruth_type": "source_derived_control",
                           "candidate_origin": "counterfactual_transform", "control_kind": "replication_allowed",
                           "candidate_claim": "Collect new independent evidence for the synthetic relation.", "source_ids": ["S0"]}]}
        self.cases_path = self.save("cases.json", self.cases)
        self.anchor = {"source_id": "S0", "locator": "p1", "exact_quote": sources[0]["locators"][0]["exact_quote"],
                       "prior_claim": sources[0]["locators"][0]["exact_quote"]}
        self.annotations = {"schema_version": "avereth-novelty-reference/v1", "reference_kind": "automated_reference",
                            "synthetic": True, "cases_sha256": binding(self.cases_path)["sha256"], "annotations": []}
        for case_id, label in (("known", "non_novel"), ("replication", "legitimate_incremental")):
            self.annotations["annotations"].append({"case_id": case_id, "status": "complete", "expected_class": label,
                                                    "nearest_prior_work": ["S0"], "pseudo_diversity": case_id == "known",
                                                    "decisive_difference": "Synthetic known result or independent evidence.", "rationale": "Synthetic control definition.",
                                                    "anchors": [self.anchor], "confidence": 1, "disagreement": False})
        self.annotations_path = self.save("annotations.json", self.annotations)

    def save(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def execute(self, name, *, labels=None, confidence=.95, wrong_order=False, missing=False, refutation=None,
                experiment=None, family="synthetic-family", cases_path=None, model=None):
        model = model or ("synthetic-model" if family == "synthetic-family" else "synthetic-other-model")
        requests_path = self.root / (name + "-requests.json")
        requests = export_requests(cases_path or self.cases_path, requests_path, experiment=experiment)
        captures = []
        for index, request in enumerate(requests["requests"]):
            if missing and index == 0:
                continue
            label = (labels or {}).get(request["case_id"], "non_novel" if request["case_id"] == "known" else "legitimate_incremental")
            if wrong_order and request["case_id"] == "known" and request["order"] == "reverse":
                label = "potentially_novel"
            response = {"novelty_class": label, "nearest_prior_work": ["S0"], "delta_statement": "Synthetic independent evidence.",
                        "pseudo_diversity": request["case_id"] == "known", "confidence": confidence,
                        "rationale": "Synthetic source comparison.", "refutations": [refutation] if refutation and request["case_id"] == "known" else []}
            captured = {"request_id": request["request_id"], "request_sha256": request["request_sha256"],
                        "context_id": name + "-context-" + str(index), "model": model, "response": response}
            trace = self.save(name + "-trace-" + str(index) + ".json", {**{key: captured[key] for key in ("context_id", "model", "request_sha256")},
                                                                       "raw_output": json.dumps(response)})
            captured["trace"] = binding(trace)
            captures.append(captured)
        responses_path = self.save(name + "-responses.json", {"schema_version": "avereth-novelty-responses/v1", "synthetic": True,
                                                              "run_id": name, "model": model, "model_family": family, "captures": captures})
        predictions_path = self.root / (name + "-predictions.json")
        import_responses(requests_path, responses_path, predictions_path)
        return predictions_path

    def test_export_hides_reference_labels_and_tests_actual_distractor_order(self):
        result = export_requests(self.cases_path, self.root / "requests.json", max_cases=1)
        self.assertEqual(["known"], result["selected_ids"])
        self.assertEqual(2, len(result["requests"]))
        a, b = result["requests"]
        self.assertEqual(6, len(a["selected_source_ids"]))
        self.assertEqual(a["source_order"], list(reversed(b["source_order"])))
        data = json.loads(a["prompt"].split("DATA:\n", 1)[1])
        self.assertEqual({"candidate_claim", "sources"}, set(data))
        self.assertNotIn("expected_class", a["prompt"])

    def test_host_array_schema_uses_basic_items_with_local_cardinality_validation(self):
        self.assertEqual({"type": "array", "items": {"type": "string"}}, RESPONSE_SCHEMA["properties"]["nearest_prior_work"])
        predictions = load(self.execute("array-contract"))
        response = predictions["predictions"][0]["capture"]["response"]
        for nearest in (["S0", "S0"], ["S" + str(index) for index in range(6)]):
            self.assertTrue(any("up to five unique" in issue for issue in response_issues({**response, "nearest_prior_work": nearest})))

    def test_export_explains_verbatim_binding_fields_and_separates_translation(self):
        requests = export_requests(self.cases_path, self.root / "verbatim-requests.json", max_cases=1)
        for request in requests["requests"]:
            instruction = request["prompt"].split("DATA:\n", 1)[0]
            self.assertIn("prior_claim verbatim as a substring of exact_quote", instruction)
            self.assertIn("candidate_claim in full verbatim from DATA.candidate_claim", instruction)
            self.assertIn("translations only in rationale", instruction)

    def test_no_valid_captures_is_incomplete_with_full_unknown_denominators(self):
        requests_path = self.root / "empty-requests.json"
        export_requests(self.cases_path, requests_path)
        captures_path = self.save("empty-captures.json", {"schema_version": "avereth-novelty-responses/v1", "synthetic": True,
                                                         "run_id": "empty", "model": "synthetic-model", "model_family": "synthetic-family", "captures": []})
        predictions_path = self.root / "empty-predictions.json"
        import_responses(requests_path, captures_path, predictions_path)
        report = evaluate(self.cases_path, self.annotations_path, predictions_path)
        self.assertEqual("INCOMPLETE", report["measurement_status"])
        self.assertEqual({"required_primary_captures": 4, "valid_primary_captures": 0, "complete": False}, report["execution"])
        self.assertEqual(2, report["metrics"]["order_swap_instability"]["unknown"])
        self.assertIsNone(report["metrics"]["false_novelty_proxy"]["value"])
        self.assertFalse(report["auto_promotion_eligible"])

    def test_both_error_directions_and_complete_denominators(self):
        predictions = self.execute("wrong", labels={"known": "potentially_novel", "replication": "non_novel"})
        report = evaluate(self.cases_path, self.annotations_path, predictions)
        self.assertEqual(1, report["metrics"]["false_novelty_proxy"]["value"])
        self.assertEqual(1, report["metrics"]["false_rejection_proxy"]["value"])
        self.assertEqual(1, report["metrics"]["pseudo_diversity_escape_rate"]["value"])
        self.assertEqual(1, report["metrics"]["nearest_prior_recall_at_5"]["value"])
        self.assertFalse(report["auto_promotion_eligible"])

    def test_missing_order_is_unknown_and_remains_in_denominator(self):
        report = evaluate(self.cases_path, self.annotations_path, self.execute("missing", missing=True))
        self.assertEqual(1, report["metrics"]["false_novelty_proxy"]["denominator"])
        self.assertEqual(1, report["metrics"]["false_novelty_proxy"]["unknown"])
        self.assertIsNone(report["metrics"]["false_novelty_proxy"]["value"])
        self.assertEqual(2, report["metrics"]["order_swap_instability"]["denominator"])

    def test_nearest_reference_must_be_registered_not_inferred(self):
        self.annotations["annotations"][0]["nearest_prior_work"] = []
        self.save("annotations.json", self.annotations)
        report = evaluate(self.cases_path, self.annotations_path, self.execute("no-nearest"))
        self.assertIsNone(report["metrics"]["nearest_prior_recall_at_5"]["value"])
        self.assertEqual(1, report["metrics"]["nearest_prior_recall_at_5"]["unknown_eligibility"])

    def test_source_quote_and_specific_prior_claim_are_required_for_refutation(self):
        refutation = {**self.anchor, "candidate_claim": self.cases["cases"][0]["candidate_claim"], "verdict": "can_refute", "rationale": "Same exact synthetic claim."}
        supported = evaluate(self.cases_path, self.annotations_path, self.execute("supported", refutation=refutation))
        self.assertEqual(0, supported["metrics"]["unsupported_refutation_rate"]["value"])
        refutation["prior_claim"] = "An invented prior result absent from the source."
        unsupported = evaluate(self.cases_path, self.annotations_path, self.execute("unsupported", refutation=refutation))
        self.assertEqual(1, unsupported["metrics"]["unsupported_refutation_rate"]["value"])
        self.assertIsNone(unsupported["cases"][0]["predicted_class"])
        self.assertFalse(unsupported["cases"][0]["secondary_eligible"])
        self.assertTrue(unsupported["cases"][0]["issues"])

    def test_semantic_refutation_relation_without_reference_is_unknown(self):
        refutation = {**self.anchor, "candidate_claim": self.cases["cases"][0]["candidate_claim"], "verdict": "can_refute", "rationale": "An asserted semantic relationship."}
        refutation["prior_claim"] = "observed relation"
        report = evaluate(self.cases_path, self.annotations_path, self.execute("semantic", refutation=refutation))
        self.assertIsNone(report["metrics"]["unsupported_refutation_rate"]["value"])
        self.assertEqual(2, report["metrics"]["unsupported_refutation_rate"]["unknown"])

    def test_annotations_without_actual_source_anchor_are_not_a_reference(self):
        for row in self.annotations["annotations"]:
            row["anchors"] = []
        self.save("annotations.json", self.annotations)
        report = evaluate(self.cases_path, self.annotations_path, self.execute("unbound-reference"))
        self.assertTrue(all(not row["reference_verified"] for row in report["cases"]))
        self.assertIsNone(report["metrics"]["false_novelty_proxy"]["value"])

    def test_changed_trace_or_source_cannot_be_used_as_behavior_evidence(self):
        predictions = self.execute("bound")
        trace = self.root / "bound-trace-0.json"
        trace.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed"):
            prediction_records(predictions)

    def test_actual_source_swap_disagreement_is_recorded(self):
        report = evaluate(self.cases_path, self.annotations_path, self.execute("swap", wrong_order=True))
        self.assertEqual(.5, report["metrics"]["order_swap_instability"]["value"])
        self.assertIsNone(report["metrics"]["false_novelty_proxy"]["value"])

    def test_secondary_only_resolves_stable_low_confidence_and_uses_another_family(self):
        primary = self.execute("low", confidence=.5)
        secondary = self.execute("second", family="other-family")
        report = evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=secondary)
        self.assertTrue(all(row["secondary_used"] for row in report["cases"]))
        self.assertEqual(0, report["metrics"]["false_novelty_proxy"]["value"])
        with self.assertRaisesRegex(ValueError, "another model and declared family"):
            evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=self.execute("same-family"))

    def test_secondary_same_model_cannot_use_a_different_family_label(self):
        primary = self.execute("primary", confidence=.5)
        secondary = self.execute("renamed", family="other-family", model="synthetic-model")
        with self.assertRaisesRegex(ValueError, "another model and declared family"):
            evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=secondary)

    def test_secondary_invented_quote_cannot_resolve_uncertainty(self):
        primary = self.execute("primary", confidence=.5)
        refutation = {**self.anchor, "candidate_claim": self.cases["cases"][0]["candidate_claim"], "verdict": "can_refute", "rationale": "Synthetic comparison."}
        refutation["exact_quote"] = "An invented quotation."
        secondary = self.execute("invented", family="other-family", refutation=refutation)
        report = evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=secondary)
        self.assertFalse(report["cases"][0]["secondary_used"])
        self.assertIsNone(report["cases"][0]["predicted_class"])
        self.assertEqual(1, report["metrics"]["unsupported_refutation_rate"]["value"])

    def test_secondary_failure_remains_unknown_and_conflict_cannot_resolve(self):
        primary = self.execute("primary", confidence=.5)
        missing = self.execute("secondary-missing", family="other-family", missing=True)
        report = evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=missing)
        self.assertEqual(1, report["metrics"]["unsupported_refutation_rate"]["unknown_eligibility"])
        self.assertTrue(report["cases"][0]["issues"])
        conflict = self.execute("conflict", family="other-family", labels={"known": "potentially_novel"})
        report = evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=conflict)
        self.assertIsNone(report["cases"][0]["predicted_class"])

    def test_secondary_cannot_erase_primary_position_flip(self):
        primary = self.execute("flipped", wrong_order=True)
        secondary = self.execute("consistent", family="other-family")
        report = evaluate(self.cases_path, self.annotations_path, primary, secondary_predictions=secondary)
        self.assertFalse(report["cases"][0]["secondary_used"])
        self.assertIsNone(report["cases"][0]["predicted_class"])
        self.assertFalse(report["cases"][0]["secondary_eligible"])
        self.assertEqual("primary_order_flip", report["cases"][0]["secondary_reason"])

    def test_bound_checks_scope_before_reading_any_external_content(self):
        outer = self.save("external.txt", {"private": "content"})
        root = self.root / "permitted"
        root.mkdir()
        item = binding(outer)
        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError("must not read outside scope")):
            with self.assertRaisesRegex(ValueError, "escapes"):
                bound(root, item)
            with self.assertRaisesRegex(ValueError, "escapes"):
                input_bound(root, {**item, "path": "../external.txt"})
        self.assertEqual(outer, input_bound(root, item))

    def test_cannot_attach_posthoc_experiment_to_imported_predictions(self):
        predictions_path = self.execute("posthoc-edit")
        predictions = load(predictions_path)
        predictions["experiment"] = binding(self.experiment())
        self.save(predictions_path.name, predictions)
        with self.assertRaisesRegex(ValueError, "identities"):
            prediction_records(predictions_path)

    def test_unmeasured_delta_agreement_is_not_zero(self):
        report = evaluate(self.cases_path, self.annotations_path, self.execute("delta"))
        self.assertIsNone(report["metrics"]["delta_reference_agreement"]["value"])
        self.assertEqual(2, report["metrics"]["delta_reference_agreement"]["unknown"])

    def experiment(self):
        return self.save("experiment.json", {"schema_version": "avereth-novelty-experiment/v1", "cases_sha256": binding(self.cases_path)["sha256"],
                                             "annotations_sha256": binding(self.annotations_path)["sha256"], "selected_ids": ["known", "replication"],
                                             "target": {"metric": "false_novelty_proxy", "direction": "decrease", "min_absolute_improvement": .2},
                                             "guardrails": {key: {"max_increase": 0} for key in ("false_novelty_proxy", "false_rejection_proxy", "unsupported_refutation_rate",
                                                                                                   "pseudo_diversity_escape_rate", "order_swap_instability")}})

    def test_paired_synthetic_improvement_cannot_promote(self):
        experiment = self.experiment()
        old = self.execute("baseline", labels={"known": "potentially_novel"}, experiment=experiment)
        new = self.execute("candidate", experiment=experiment)
        result = compare(self.cases_path, self.annotations_path, old, new, experiment)
        self.assertEqual("KEEP", result["verdict"], result["issues"])
        self.assertEqual("engineering_proxy_gain", result["decision_basis"])
        self.assertFalse(result["auto_promotion_eligible"])

    def test_false_rejection_regression_prevents_one_sided_novelty_improvement(self):
        experiment = self.experiment()
        old = self.execute("base", labels={"known": "potentially_novel"}, experiment=experiment)
        new = self.execute("cand", labels={"replication": "non_novel"}, experiment=experiment)
        result = compare(self.cases_path, self.annotations_path, old, new, experiment)
        self.assertEqual("REJECT", result["verdict"])
        self.assertIn("false_rejection_proxy", result["guardrail_violations"])

    def test_posthoc_target_cannot_authorize_comparison(self):
        old, new = self.execute("post-old"), self.execute("post-new")
        result = compare(self.cases_path, self.annotations_path, old, new, self.experiment())
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertTrue(any("preregistered" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
