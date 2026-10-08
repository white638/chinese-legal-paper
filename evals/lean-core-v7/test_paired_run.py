"""Actual local synthetic subprocess repetitions exercise the bounded scheduler."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from execute_run import execute, load_json, sha
from paired_run import run_pair


class PairedRunTests(unittest.TestCase):
    def setUp(self):
        from test_execute_run import ExecutionTests
        self.fixture = ExecutionTests("test_only_selected_case_materials_are_required_and_executed")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.select_one()
        self.fixture.save()
        self.root = self.fixture.root
        self.candidate = self.root / "candidate-spec.json"
        spec = load_json(self.fixture.spec_path)
        config = {**self.fixture.config, "instruction_variant": "lean"}
        candidate_config = self.root / "candidate-config.json"
        candidate_config.write_text(json.dumps(config), encoding="utf-8")
        spec["effective_config"] = {"path": candidate_config.name, "sha256": sha(candidate_config)}
        self.candidate.write_text(json.dumps(spec), encoding="utf-8")
        experiment = load_json(self.fixture.exp_path)
        experiment.update(candidate_config_sha256=sha(candidate_config), allowed_config_changes=["/instruction_variant"])
        self.fixture.exp_path.write_text(json.dumps(experiment), encoding="utf-8")
        self.output = self.root / "paired-run"

    def paired(self, **kwargs):
        return run_pair(self.fixture.spec_path, self.candidate, self.fixture.exp_path, self.root / "bank.json", self.output,
                        scope="smoke", max_cases=1, **kwargs)

    def test_preflight_selects_one_without_any_model_execution(self):
        with patch("paired_run.execute") as executor:
            result = self.paired()
        self.assertEqual("NOT RUN", result["status"])
        self.assertEqual("preflight_only", result["reason"])
        self.assertEqual(1, result["selected_cases"])
        self.assertEqual(0, result["model_calls"])
        executor.assert_not_called()

    def test_uncertainty_runs_complete_new_pairs_and_keeps_all_attempts(self):
        with patch("paired_run.execute", wraps=execute) as executor:
            result = self.paired(perform_execution=True, repeat_on_uncertain=1)
        self.assertEqual(4, executor.call_count)
        self.assertEqual(2, len(result["rounds"]))
        self.assertEqual("UNCERTAIN", result["status"])
        self.assertFalse(result["auto_promotion_eligible"])
        traces = sorted(self.output.glob("round-*/**/host-trace.json"))
        self.assertEqual(4, len(traces))
        ids = [load_json(path)["run_context"]["context_id"] for path in traces]
        self.assertEqual(4, len(set(ids)))
        original = {path: sha(path) for path in self.output.rglob("*") if path.is_file()}
        with patch("paired_run.execute") as executor:
            resumed = self.paired(perform_execution=True, repeat_on_uncertain=1)
        executor.assert_not_called()
        self.assertEqual(2, len(resumed["rounds"]))
        self.assertTrue(all(sha(path) == digest for path, digest in original.items()))

    def test_repeat_budget_and_baseline_ref_are_enforced_before_execution(self):
        for repeat in (-1, 3, True):
            with self.assertRaisesRegex(ValueError, "limited"):
                self.paired(repeat_on_uncertain=repeat)
        with self.assertRaisesRegex(ValueError, "baseline_ref"):
            self.paired(baseline_code=self.fixture.code, baseline_ref="f" * 40)

    def test_selected_missing_materials_do_not_call_either_side(self):
        (self.root / "fixture-1-material.txt").unlink()
        with patch("paired_run.execute") as executor:
            result = self.paired(perform_execution=True)
        self.assertEqual("NOT RUN", result["status"])
        self.assertEqual("preflight_blocked", result["reason"])
        self.assertEqual(0, result["model_calls"])
        executor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
