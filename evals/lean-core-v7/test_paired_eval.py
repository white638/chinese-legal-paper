"""Synthetic judges test engineering decisions; they are not live quality evidence."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from paired_eval import aggregate_repeats, evaluate_pairs

DEFAULT_TARGET = object()


class PairedEvalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = {"primary": {"runner": "codex", "model": "model-one", "family": "family-one"},
                       "secondary": {"runner": "claude", "model": "model-two", "family": "family-two"},
                       "swap_check_rate": 0, "seed": 31}
        self.pair = {"id": "test-01", "task": "Explain the supplied observation.", "materials": "A source supports a bounded conclusion.",
                     "baseline": "SUPPORTED old", "candidate": "SUPPORTED better", "hard_failures": [], "uncertainties": [],
                     "writer_context_ids": ["writer-old", "writer-new"],
                     "hard_checks_complete": True, "prose_checks_complete": True,
                     "completion": {"baseline": True, "candidate": True},
                     "costs": {"baseline": {"input_tokens": 100}, "candidate": {"input_tokens": 80}},
                     "bindings": {"baseline": "synthetic", "candidate": "synthetic"}}
        self.calls = []
        self.target = {"category": "prose", "metric": "pairwise_preference", "direction": "increase", "min_win_margin": .2, "min_pairs": 1}
        self.efficiency = {"category": "efficiency", "metric": "input_tokens", "direction": "decrease", "min_relative_improvement": .1}

    def judge(self, spec, prompt):
        self.calls.append((spec, prompt))
        data = json.loads(prompt.split("DATA:\n", 1)[1])
        choice = "A" if data["A"].endswith("better") else "B"
        return self.reply(spec, choice)

    def reply(self, spec, choice, confidence=.9, context=None):
        return {"context_id": context or "judge-" + str(len(self.calls)), "model": spec["model"],
                "response": {"choice": choice, "confidence": confidence, "rationale": "Bounded comparison of evidence use.",
                             "evidence": ["The source supports the narrower explanation."]}}

    def evaluate(self, pairs=None, judge=None, config=None, target=DEFAULT_TARGET):
        return evaluate_pairs(pairs or [self.pair], config or self.config, self.root / "result",
                              synthetic=True, judge=judge or self.judge, target=self.target if target is DEFAULT_TARGET else target)

    def test_clear_winner_uses_one_judge_and_has_no_human_dependency(self):
        result = self.evaluate()
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual(1, len(self.calls))
        self.assertFalse(result["auto_promotion_eligible"])
        self.assertEqual("optional", result["human_review"])
        data = json.loads(self.calls[0][1].split("DATA:\n", 1)[1])
        self.assertEqual({"A", "B", "task", "materials"}, set(data))
        self.assertNotIn("model-one", self.calls[0][1])

    def test_candidate_hard_failure_skips_all_judges(self):
        self.pair["hard_failures"] = ["semantic fidelity failed"]
        result = self.evaluate()
        self.assertEqual("REJECT", result["verdict"])
        self.assertEqual(0, len(self.calls))

    def test_missing_evidence_remains_uncertain_without_model_calls(self):
        self.pair["uncertainties"] = ["material hash changed"]
        result = self.evaluate()
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertFalse(self.calls)

    def test_untrusted_failure_record_does_not_establish_a_regression(self):
        self.pair["uncertainties"] = ["assessment hash changed"]
        self.pair["hard_failures"] = ["failure from the unbound assessment"]
        self.assertEqual("UNCERTAIN", self.evaluate()["verdict"])

    def test_difficult_sample_escalates_only_to_other_family(self):
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            data = json.loads(prompt.split("DATA:\n", 1)[1])
            choice = "UNCERTAIN" if spec["model"] == "model-one" else "A" if data["A"].endswith("better") else "B"
            return self.reply(spec, choice)
        result = self.evaluate(judge=judge)
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual(3, len(self.calls))
        self.assertEqual(["family-one", "family-two", "family-two"], [s["family"] for s, _ in self.calls])

    def test_same_family_cannot_satisfy_escalation(self):
        self.config["secondary"]["family"] = "family-one"
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            return self.reply(spec, "UNCERTAIN")
        result = self.evaluate(judge=judge)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertEqual(1, len(self.calls))

    def test_position_bias_in_both_judges_cannot_promote(self):
        self.config["swap_check_rate"] = 1
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            return self.reply(spec, "A")
        result = self.evaluate(judge=judge)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertEqual(4, len(self.calls))
        self.assertEqual("flip", result["pairs"][0]["position_check"])

    def test_writer_cannot_judge_itself(self):
        self.config.pop("secondary")
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            return self.reply(spec, "A", context="writer-old")
        result = self.evaluate(judge=judge)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertIn("fresh context", result["pairs"][0]["issues"][0])

    def test_malformed_or_missing_rationale_is_uncertain(self):
        self.config.pop("secondary")
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            reply = self.reply(spec, "A")
            reply["response"]["evidence"] = []
            return reply
        self.assertEqual("UNCERTAIN", self.evaluate(judge=judge)["verdict"])

    def test_registered_efficiency_gain_keeps_without_prose_judging(self):
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            return self.reply(spec, "TIE")
        result = self.evaluate(judge=judge, target=self.efficiency)
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual([], self.calls)
        self.assertEqual("efficiency_gain", result["decision_basis"])
        self.assertFalse(result["quality_improvement_proven"])
        self.assertEqual(-20, result["costs"]["input_tokens"]["delta"])

    def test_unknown_cost_is_not_zero(self):
        self.pair["costs"]["candidate"]["input_tokens"] = None
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            return self.reply(spec, "TIE")
        result = self.evaluate(judge=judge, target=self.efficiency)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertIsNone(result["costs"]["input_tokens"]["candidate"])

    def test_review_records_are_preserved_and_cannot_be_overwritten(self):
        result = self.evaluate()
        review = result["pairs"][0]["reviews"][0]
        self.assertTrue((self.root / "result" / review["request"]["path"]).is_file())
        self.assertTrue((self.root / "result" / review["response"]["path"]).is_file())
        with self.assertRaises(FileExistsError):
            self.evaluate()

    def test_task_regressions_remain_visible(self):
        other = copy.deepcopy(self.pair)
        other.update(id="test-02", baseline="SUPPORTED better", candidate="SUPPORTED old")
        result = self.evaluate(pairs=[self.pair, other])
        self.assertEqual(1, result["summary"]["candidate_wins"])
        self.assertEqual(1, result["summary"]["baseline_wins"])
        self.assertEqual("REJECT", result["pairs"][1]["verdict"])

    def test_missing_target_does_not_keep_a_stylistic_preference(self):
        self.config["soft_diagnostics"] = True
        result = self.evaluate(target=None)
        self.assertEqual(1, result["summary"]["candidate_wins"])
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertIsNone(result["decision_basis"])

    def test_unchanged_hard_error_is_not_new_but_cannot_support_prose(self):
        self.pair["hard_failures"] = self.pair["baseline_hard_failures"] = ["same_error"]
        result = self.evaluate()
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertEqual([], result["hard_regressions"])
        self.assertEqual([], self.calls)

    def test_unchanged_hard_error_can_be_retained_in_an_efficiency_comparison(self):
        self.pair["hard_failures"] = self.pair["baseline_hard_failures"] = ["same_error"]
        result = self.evaluate(target=self.efficiency)
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual([], result["hard_regressions"])

    def test_completion_regression_rejects_even_with_cost_improvement(self):
        self.pair["completion"]["candidate"] = False
        result = self.evaluate(target=self.efficiency)
        self.assertEqual("REJECT", result["verdict"])
        self.assertEqual(["test-01"], result["completion_regressions"])

    def test_unknown_checks_or_completion_cannot_promote(self):
        self.pair["completion"]["candidate"] = None
        self.pair["hard_checks_complete"] = False
        result = self.evaluate(target=self.efficiency)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertFalse(self.calls)

    def test_tiny_cost_improvement_below_registered_threshold_is_uncertain(self):
        self.pair["costs"]["candidate"]["input_tokens"] = 99
        self.assertEqual("UNCERTAIN", self.evaluate(target=self.efficiency)["verdict"])

    def test_registered_target_deterioration_rejects(self):
        self.pair["costs"]["candidate"]["input_tokens"] = 120
        self.assertEqual("REJECT", self.evaluate(target=self.efficiency)["verdict"])

    def test_integrity_gain_uses_actual_failure_difference(self):
        self.pair["baseline_hard_failures"] = ["source_error", "number_error"]
        self.pair["hard_failures"] = ["source_error"]
        target = {"category": "integrity", "metric": "hard_failure_count", "direction": "decrease", "min_absolute_improvement": 1}
        result = self.evaluate(target=target)
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual("integrity_gain", result["decision_basis"])

    def test_reliability_gain_uses_verified_completion(self):
        self.pair["completion"]["baseline"] = False
        target = {"category": "reliability", "metric": "task_completion_rate", "direction": "increase", "min_absolute_improvement": .5}
        result = self.evaluate(target=target)
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual("reliability_gain", result["decision_basis"])

    def test_close_sixteen_to_fourteen_vote_remains_uncertain(self):
        pairs = []
        for index in range(30):
            pair = copy.deepcopy(self.pair)
            pair["id"] = str(index)
            if index >= 16:
                pair["baseline"], pair["candidate"] = pair["candidate"], pair["baseline"]
            pairs.append(pair)
        result = self.evaluate(pairs=pairs)
        self.assertEqual(16, result["summary"]["candidate_wins"])
        self.assertEqual(14, result["summary"]["baseline_wins"])
        self.assertEqual("UNCERTAIN", result["verdict"])

    def test_secondary_agreement_cannot_erase_primary_position_flip(self):
        self.config["swap_check_rate"] = 1
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            data = json.loads(prompt.split("DATA:\n", 1)[1])
            choice = "A" if spec["family"] == "family-one" else "A" if data["A"].endswith("better") else "B"
            return self.reply(spec, choice)
        self.assertEqual("UNCERTAIN", self.evaluate(judge=judge)["verdict"])

    def test_only_requested_soft_judge_is_an_engineering_dependency(self):
        result = self.evaluate(config={"primary": None}, target=self.efficiency)
        self.assertEqual("KEEP", result["verdict"])
        self.assertFalse(result["pairs"][0]["review_requested"])

    def test_requested_unconfigured_soft_judge_remains_uncertain(self):
        result = self.evaluate(config={"soft_diagnostics": True}, target=self.efficiency)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertTrue(result["pairs"][0]["review_requested"])
        self.assertFalse(self.calls)

    def test_clear_negative_soft_preference_does_not_override_efficiency_target(self):
        self.config["soft_diagnostics"] = True
        def judge(spec, prompt):
            self.calls.append((spec, prompt))
            data = json.loads(prompt.split("DATA:\n", 1)[1])
            return self.reply(spec, "A" if data["A"].endswith("old") else "B")
        result = self.evaluate(judge=judge, target=self.efficiency)
        self.assertEqual(1, result["summary"]["baseline_wins"])
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual("efficiency_gain", result["decision_basis"])


if __name__ == "__main__":
    unittest.main()
