"""Synthetic evidence checks for automatic paired-loop input preparation."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from close_loop import close_loop, prepare_pairs, task_content
from decision_policy import PROSE_INTEGRITY_CHECKS
from execute_run import sha
from paired_eval import aggregate_repeats


class CloseLoopTests(unittest.TestCase):
    def setUp(self):
        from test_diagnose_runs import DiagnosticTests
        self.fixture = DiagnosticTests("test_same_revision_registered_ablation_has_diagnostics_only")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.paths = []
        for name, run in zip(("baseline", "candidate"), self.fixture.runs):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(run), encoding="utf-8")
            self.paths.append(path)

    def test_unconfigured_judge_remains_uncertain(self):
        result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "loop.json")
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertFalse(result["auto_promotion_eligible"])

    def test_automatic_judge_receives_bound_pair_inputs(self):
        config = self.root / "judges.json"
        config.write_text("{}")
        with patch("paired_eval.evaluate_pairs", return_value={"verdict": "UNCERTAIN", "auto_promotion_eligible": False}) as evaluate:
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "loop.json", judge_config=config)
        pair = evaluate.call_args.args[0][0]
        self.assertTrue(pair["baseline"])
        self.assertTrue(pair["materials"])
        self.assertTrue(pair["bindings"]["candidate"])
        self.assertEqual(sha(self.paths[0]), evaluate.call_args.kwargs["input_bindings"]["baseline_sha256"])
        self.assertEqual("UNCERTAIN", result["status"])

    def test_missing_costs_remain_unknown_without_suppressing_quality_judging(self):
        self.fixture.runs[1]["tasks"][0]["cost"]["tool_calls"] = None
        self.fixture.seal()
        pairs = prepare_pairs(self.fixture.manifest, *self.fixture.runs, self.root, self.root, self.fixture.result())
        self.assertEqual([], pairs[0]["uncertainties"])
        self.assertIsNone(pairs[0]["costs"]["candidate"]["tool_calls"])

    def test_workflow_manifest_is_replaced_by_bound_body_and_tampering_rejected(self):
        attempt = self.root / "attempt"
        workspace = attempt / "workspace"
        workspace.mkdir(parents=True)
        body = workspace / "paper.md"
        body.write_text("Actual synthetic body, not a filename list.", encoding="utf-8")
        output = attempt / "output.json"
        output.write_text(json.dumps({"schema_version": "avereth-workflow-output/v1", "artifacts": [{"path": "paper.md", "sha256": sha(body)}]}))
        row = {"output": {"path": "attempt/output.json", "sha256": sha(output)}}
        content, bindings = task_content(row, self.root, "output")
        self.assertIn("Actual synthetic body", content)
        self.assertIn("attempt/workspace/paper.md", bindings)
        body.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "changed"):
            task_content(row, self.root, "output")

    def test_baseline_factual_defect_does_not_reject_a_candidate_fix(self):
        self.fixture.runs[0]["tasks"][0]["factual_checks"]["no_fabricated_sources"] = "fail"
        self.fixture.seal()
        pairs = prepare_pairs(self.fixture.manifest, *self.fixture.runs, self.root, self.root, self.fixture.result())
        self.assertEqual([], pairs[0]["hard_failures"])
        self.assertEqual(["no_fabricated_sources"], pairs[0]["baseline_hard_failures"])

    def reseal(self):
        self.fixture.seal()
        for path, run in zip(self.paths, self.fixture.runs):
            path.write_text(json.dumps(run), encoding="utf-8")

    def register_efficiency(self, *, repeats=0):
        self.fixture.experiment.update(synthetic=True, execution={"repeat_on_uncertain": repeats}, target={"category": "efficiency", "metric": "tool_calls",
                                                               "direction": "decrease", "min_absolute_improvement": 1})
        self.fixture.runs[1]["tasks"][0]["cost"]["tool_calls"] = 0
        self.reseal()

    def test_registered_efficiency_closes_without_a_judge_configuration(self):
        self.register_efficiency()
        with patch("paired_eval._host_judge", side_effect=AssertionError("efficiency invoked a prose judge")):
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "efficiency.json")
        self.assertEqual("KEEP", result["status"])
        self.assertEqual("efficiency_gain", result["decision_basis"])
        self.assertFalse(result["quality_improvement_proven"])
        self.assertFalse(result["auto_promotion_eligible"])
        self.assertEqual(self.fixture.experiment["target"], result["paired"]["target"])
        self.assertEqual(0, result["paired"]["judge_calls"])
        self.assertEqual(sha(self.fixture.exp_path), result["inputs"]["experiment"]["sha256"])

    def test_post_execution_target_change_is_not_trusted(self):
        self.register_efficiency()
        self.fixture.experiment["target"]["min_absolute_improvement"] = .5
        self.fixture.exp_path.write_text(json.dumps(self.fixture.experiment), encoding="utf-8")
        with patch("paired_eval._host_judge", side_effect=AssertionError("unmatched target invoked judge")):
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "changed-target.json")
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertFalse(result["diagnostic"]["comparison_valid"])

    def test_same_factual_failure_code_is_not_a_new_regression(self):
        self.register_efficiency()
        for run in self.fixture.runs:
            run["tasks"][0]["factual_checks"]["no_fabricated_sources"] = "fail"
        self.reseal()
        result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "old-failure.json")
        self.assertEqual("KEEP", result["status"])
        self.assertEqual([], result["hard_regressions"])

    def test_selected_task_mismatch_prevents_judging(self):
        self.register_efficiency()
        self.fixture.runs[1]["tasks"] = []
        self.reseal()
        config = self.root / "diagnostic-judge.json"
        config.write_text(json.dumps({"soft_diagnostics": True, "primary": {"runner": "codex", "model": "synthetic", "family": "synthetic"}}))
        with patch("paired_eval._host_judge", side_effect=AssertionError("unmatched task set invoked judge")):
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "missing-task.json", judge_config=config)
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertEqual(0, result["paired"]["judge_calls"])

    def test_outcome_failure_is_a_completion_regression(self):
        self.register_efficiency()
        self.fixture.runs[1]["tasks"][0]["responsibility_coverage"]["question"] = "fail"
        self.reseal()
        result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "completion.json")
        self.assertEqual("REJECT", result["status"])
        self.assertEqual(["fixture"], result["paired"]["completion_regressions"])

    def declare_citation_check(self):
        self.fixture.manifest["tasks"][0]["hard_checks"] = ["citation_fidelity"]
        self.fixture.manifest_path.write_text(json.dumps(self.fixture.manifest), encoding="utf-8")
        self.fixture.manifest_sha = sha(self.fixture.manifest_path)
        self.fixture.experiment["manifest_sha256"] = self.fixture.manifest_sha

    def test_case_specific_check_is_required_and_missing_measurement_blocks_keep(self):
        self.register_efficiency()
        self.declare_citation_check()
        self.reseal()
        result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "missing-check.json")
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertIn("citation_fidelity", result["paired"]["pairs"][0]["required_hard_checks"])

    def test_bound_case_specific_failure_is_a_hard_regression(self):
        self.register_efficiency()
        self.declare_citation_check()
        self.fixture.runs[0]["tasks"][0]["factual_checks"]["citation_fidelity"] = "pass"
        self.fixture.runs[1]["tasks"][0]["factual_checks"]["citation_fidelity"] = "fail"
        self.reseal()
        result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "citation-failed.json")
        self.assertEqual("REJECT", result["status"])
        self.assertEqual([{"id": "fixture", "failure": "citation_fidelity"}], result["hard_regressions"])

    def register_prose(self):
        self.fixture.manifest["tasks"][0]["hard_checks"] = sorted(PROSE_INTEGRITY_CHECKS)
        self.fixture.manifest_path.write_text(json.dumps(self.fixture.manifest), encoding="utf-8")
        self.fixture.manifest_sha = sha(self.fixture.manifest_path)
        self.fixture.experiment.update(synthetic=True, manifest_sha256=self.fixture.manifest_sha,
                                       target={"category": "prose", "metric": "pairwise_preference", "direction": "increase",
                                               "min_win_margin": .2, "min_pairs": 1})
        for run in self.fixture.runs:
            run["tasks"][0]["factual_checks"].update({code: "pass" for code in PROSE_INTEGRITY_CHECKS})
        self.reseal()
        config = self.root / "prose-judge.json"
        config.write_text(json.dumps({"primary": {"runner": "codex", "model": "synthetic-model", "family": "synthetic-family"},
                                      "swap_check_rate": 0}), encoding="utf-8")
        return config

    def test_bound_canonical_prose_checks_can_support_registered_prose_gain(self):
        config = self.register_prose()
        def judge(spec, prompt):
            data = json.loads(prompt.split("DATA:\n", 1)[1])
            return {"context_id": "synthetic-prose-judge", "model": spec["model"],
                    "response": {"choice": "A" if "candidate" in data["A"] else "B", "confidence": .95,
                                 "rationale": "Synthetic comparison of the bound outputs.", "evidence": ["fixture candidate"]}}
        with patch("paired_eval._host_judge", side_effect=judge):
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "prose-pass.json", judge_config=config)
        self.assertEqual("KEEP", result["status"], result["paired"]["issues"])
        self.assertEqual("prose_gain", result["decision_basis"])
        self.assertEqual(1, result["paired"]["judge_calls"])
        self.assertFalse(result["auto_promotion_eligible"])

    def test_missing_actual_semantic_check_cannot_support_prose_gain(self):
        config = self.register_prose()
        del self.fixture.runs[1]["tasks"][0]["factual_checks"]["semantic_fidelity"]
        self.reseal()
        with patch("paired_eval._host_judge", side_effect=AssertionError("missing semantic check invoked a judge")):
            result = close_loop(*self.paths, self.fixture.exp_path, self.fixture.manifest_path, self.root / "semantic-missing.json", judge_config=config)
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertEqual(0, result["paired"]["judge_calls"])

    def round(self, number, *, candidate_calls=0, same_context=False, threshold=1):
        root = self.root / ("round-" + str(number))
        root.mkdir()
        for source in self.root.iterdir():
            if source.is_file():
                shutil.copy2(source, root / source.name)
        experiment = copy.deepcopy(self.fixture.experiment)
        experiment["target"]["min_absolute_improvement"] = threshold
        (root / "experiment.json").write_text(json.dumps(experiment), encoding="utf-8")
        paths = []
        for side, original in zip(("baseline", "candidate"), self.fixture.runs):
            run = copy.deepcopy(original)
            run["run_id"] = str(number) + "-" + side
            run["experiment_sha256"] = sha(root / "experiment.json")
            task = run["tasks"][0]
            if side == "candidate":
                task["cost"]["tool_calls"] = candidate_calls
            trace_path = root / task["trace"]["path"]
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
            trace["run_context"].update(run_id=run["run_id"], context_id=("same" if same_context else str(number)) + "-" + side)
            trace["measurements"] = task["cost"]
            trace_path.write_text(json.dumps(trace), encoding="utf-8")
            task["trace"]["sha256"] = sha(trace_path)
            assessment_path = root / task["assessment"]["path"]
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["trace_sha256"] = sha(trace_path)
            assessment_path.write_text(json.dumps(assessment), encoding="utf-8")
            task["assessment"]["sha256"] = sha(assessment_path)
            path = root / (side + ".json")
            path.write_text(json.dumps(run), encoding="utf-8")
            paths.append(path)
        output = root / "loop.json"
        result = close_loop(*paths, root / "experiment.json", root / "manifest.json", output)
        self.assertTrue(result["diagnostic"]["comparison_valid"], result["diagnostic"]["issues"])
        return {"path": str(output), "sha256": sha(output)}

    def test_repetition_retains_initial_uncertainty_and_later_keep(self):
        self.register_efficiency(repeats=1)
        reports = [self.round(1, candidate_calls=1), self.round(2)]
        result = aggregate_repeats(reports, 2)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertEqual(["UNCERTAIN", "KEEP"], [row["report"]["status"] for row in result["rounds"]])
        self.assertTrue(all(row["verified"] for row in result["rounds"]))
        self.assertFalse(result["auto_promotion_eligible"])

    def test_all_repeated_synthetic_wins_preserve_no_promotion(self):
        self.register_efficiency(repeats=1)
        result = aggregate_repeats([self.round(1), self.round(2)], 2)
        self.assertEqual("KEEP", result["verdict"], result["issues"])
        self.assertEqual("efficiency_gain", result["decision_basis"])
        self.assertFalse(result["auto_promotion_eligible"])

    def test_repetition_requires_different_bound_host_contexts(self):
        self.register_efficiency(repeats=1)
        result = aggregate_repeats([self.round(1, same_context=True), self.round(2, same_context=True)], 2)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertTrue(any("contexts" in issue for issue in result["issues"]))

    def test_repetition_cannot_change_registered_target_or_exceed_limit(self):
        self.register_efficiency(repeats=1)
        reports = [self.round(1), self.round(2, threshold=.5)]
        changed_target = aggregate_repeats(reports, 2)
        self.assertEqual("UNCERTAIN", changed_target["verdict"])
        self.assertTrue(any("same target" in issue for issue in changed_target["issues"]))
        result = aggregate_repeats(reports, 1)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertTrue(any("exceed" in issue for issue in result["issues"]))

    def test_repeated_round_file_tampering_is_not_a_verified_result(self):
        self.register_efficiency()
        binding = self.round(1)
        Path(binding["path"]).write_text("{}", encoding="utf-8")
        result = aggregate_repeats([binding], 1)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertFalse(result["rounds"][0]["verified"])

    def test_repeated_evidence_rechecks_outputs_after_original_loop(self):
        self.register_efficiency()
        binding = self.round(1)
        (self.root / "round-1" / "candidate-output.json").write_text("{}", encoding="utf-8")
        result = aggregate_repeats([binding], 1)
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertTrue(any("changed" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
