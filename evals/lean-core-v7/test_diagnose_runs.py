"""Synthetic fixtures check reporting contracts, not research quality."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from capture_run import capture
from compare_runs import EXTRA_COST_METRICS, FACTUAL_CHECKS, compare
from diagnose_runs import CONTEXT_FIELDS, DIAGNOSTICS, diagnose
from run_records import bind_file


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"tasks": [{"id": "fixture", "task": "Synthetic prompt", "outcome_checks": ["question", "counterargument", "limitation"]}],
                         "quality_metrics": ["accuracy"], "cost_metrics": ["tool_calls"]}
        self.manifest_path = self.root / "manifest.json"
        self.manifest_sha = self.write(self.manifest_path.name, self.manifest)["sha256"]
        self.exp_path = self.root / "experiment.json"
        self.configs = [self.write(label + "-config.json", {"rerank": {"enabled": enabled}, "budget": 10}) for label, enabled in (("baseline", False), ("candidate", True))]
        self.experiment = {"schema_version": "avereth-paired-experiment/v1", "experiment_id": "synthetic-test-only",
                           "registered_at": "2026-09-06T09:00:00Z", "manifest_sha256": self.manifest_sha,
                           "baseline_config_sha256": self.configs[0]["sha256"], "candidate_config_sha256": self.configs[1]["sha256"],
                           "evaluation_mode": "offline_fixed_materials", "allowed_config_changes": ["/rerank/enabled"]}
        self.runs = []
        for label, config in zip(("baseline", "candidate"), self.configs):
            materials = self.write(label + "-materials.json", {"fixture": "identical synthetic materials"})
            row = {"id": "fixture", "status": "completed", "failure_reason": None, "materials": materials,
                   "output": self.write(label + "-output.json", {"fixture": label}),
                   "model": "synthetic-model", "reasoning_effort": "fixture", "host_version": "fixture-host-v1",
                   "tool_versions": {"fixture-tool": "1"}, "prompt_version": "fixture-prompt-v1",
                   "evaluation_mode": "offline_fixed_materials", "material_snapshot_sha256": materials["sha256"],
                   "task_prompt_sha256": hashlib.sha256(b"Synthetic prompt").hexdigest(), "quality": {"accuracy": 3},
                   "cost": {k: 1 for k in ("tool_calls", *EXTRA_COST_METRICS)},
                   "factual_checks": {k: "pass" for k in FACTUAL_CHECKS}, "diagnostics": {k: 1 for k in DIAGNOSTICS},
                   "responsibility_coverage": {"question": "pass", "counterargument": "pass", "limitation": "pass"}}
            self.runs.append({"run_id": label, "code_revision": "same-fixture-revision", "effective_config": config, "tasks": [row]})
        self.seal()

    def write(self, name, payload):
        (self.root / name).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return bind_file(self.root, name)

    def seal(self):
        self.exp_sha = self.write("experiment.json", self.experiment)["sha256"]
        for run in self.runs:
            run["experiment_sha256"] = self.exp_sha
            for row in run["tasks"]:
                context = {k: row[k] for k in CONTEXT_FIELDS}
                context.update(run_id=run["run_id"], code_revision=run["code_revision"], started_at="2026-09-06T10:00:00Z",
                               effective_config_sha256=run["effective_config"]["sha256"])
                row["trace"] = self.write(run["run_id"] + "-trace.json", {"run_context": context, "events": ["synthetic event"],
                                         "measurements": row["cost"], "status": row["status"], "failure_reason": row.get("failure_reason"),
                                         "output_sha256": row["output"]["sha256"]})
                assessment = {k: row[k] for k in ("quality", "factual_checks", "diagnostics", "responsibility_coverage")}
                assessment["evidence_notes"] = "Synthetic test evidence; no real model or expert judgment."
                assessment["trace_sha256"] = row["trace"]["sha256"]
                assessment["output_sha256"] = row["output"]["sha256"]
                row["assessment"] = self.write(run["run_id"] + "-assessment.json", assessment)

    def result(self):
        return diagnose(self.manifest, self.experiment, *self.runs, self.root, self.root,
                        manifest_sha256=self.manifest_sha, experiment_sha256=self.exp_sha)

    def test_same_revision_registered_ablation_has_diagnostics_only(self):
        result = self.result()
        self.assertTrue(result["comparison_valid"], result["issues"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["receipt_issued"])
        self.assertEqual("not_comparable", compare(self.manifest, *self.runs, self.root, self.root)["status"])

    def test_baseline_factual_failure_remains_visible_with_fix(self):
        self.runs[0]["tasks"][0]["factual_checks"][FACTUAL_CHECKS[0]] = "fail"
        self.seal()
        result = self.result()
        self.assertTrue(result["comparison_valid"], result["issues"])
        self.assertEqual("fixed", result["pairs"][0]["factual_checks"][FACTUAL_CHECKS[0]]["change"])
        self.assertEqual("incomplete_or_rejected", compare(self.manifest, *self.runs, self.root, self.root)["status"])

    def test_candidate_regression_is_not_hidden_by_cost(self):
        row = self.runs[1]["tasks"][0]
        row["quality"]["accuracy"] = 1
        row["cost"]["tool_calls"] = 0
        row["factual_checks"][FACTUAL_CHECKS[0]] = "fail"
        self.seal()
        pair = self.result()["pairs"][0]
        self.assertEqual(-2, pair["quality"]["accuracy"]["delta"])
        self.assertEqual("regressed", pair["factual_checks"][FACTUAL_CHECKS[0]]["change"])

    def test_failed_runs_are_counted_and_unmeasured_cost_is_unknown(self):
        row = self.runs[1]["tasks"][0]
        row.update(status="interrupted", failure_reason="Synthetic interruption", quality={}, cost={})
        self.seal()
        result = self.result()
        self.assertTrue(result["comparison_valid"], result["issues"])
        self.assertEqual(1, result["completion"]["candidate"]["interrupted"])
        self.assertEqual(0, result["completion"]["candidate"]["completed"])
        self.assertIsNone(result["pairs"][0]["cost"]["tool_calls"]["delta"])

    def test_removed_task_is_not_a_better_completion_rate(self):
        self.runs[1]["tasks"] = []
        result = self.result()
        self.assertFalse(result["comparison_valid"])
        self.assertEqual(1, result["completion"]["candidate"]["required"])
        self.assertEqual(1, result["completion"]["candidate"]["missing"])

    def test_task_requirements_supply_coverage_denominator(self):
        self.runs[1]["tasks"][0]["responsibility_coverage"] = {"question": "pass"}
        self.seal()
        result = self.result()["pairs"][0]["responsibility_coverage"][1]
        self.assertEqual({"required": 3, "satisfied": 1, "failed": 0, "unknown": 2}, result)

    def test_changed_trace_or_config_invalidates_deltas(self):
        for evidence in (self.runs[1]["effective_config"], self.runs[1]["tasks"][0]["trace"]):
            original = evidence["sha256"]
            evidence["sha256"] = "changed"
            result = self.result()
            self.assertFalse(result["comparison_valid"])
            self.assertIsNone(result["pairs"][0]["quality"]["accuracy"]["delta"])
            evidence["sha256"] = original

    def test_undeclared_configuration_change_is_rejected(self):
        self.runs[1]["effective_config"] = self.write("candidate-config.json", {"rerank": {"enabled": True}, "budget": 20})
        self.experiment["candidate_config_sha256"] = self.runs[1]["effective_config"]["sha256"]
        self.seal()
        self.assertFalse(self.result()["comparison_valid"])

    def test_posthoc_registration_is_rejected(self):
        self.experiment["registered_at"] = "2026-09-06T11:00:00Z"
        self.seal()
        self.assertFalse(self.result()["comparison_valid"])

    def test_online_and_offline_are_separate(self):
        self.runs[1]["tasks"][0]["evaluation_mode"] = "online_retrieval"
        self.seal()
        self.assertFalse(self.result()["comparison_valid"])

    def test_metrics_cannot_be_edited_away_from_assessment_or_trace(self):
        self.runs[1]["tasks"][0]["quality"]["accuracy"] = 4
        self.runs[1]["tasks"][0]["cost"]["tool_calls"] = 0
        self.assertFalse(self.result()["comparison_valid"])

    def test_replaced_output_with_fresh_file_hash_is_still_not_the_assessed_output(self):
        self.runs[1]["tasks"][0]["output"] = self.write("candidate-output.json", {"fixture": "different output"})
        self.assertFalse(self.result()["comparison_valid"])

    def test_capture_derives_conditions_and_cost_from_existing_exports(self):
        row = self.runs[0]["tasks"][0]
        spec = {"effective_config": self.runs[0]["effective_config"]["path"], "tasks": [{"id": "fixture", **{k: row[k]["path"] for k in ("trace", "assessment", "materials", "output")}}]}
        captured = capture(spec, self.root, self.exp_path)
        self.assertEqual(self.runs[0], {k: v for k, v in captured.items() if k != "schema_version"})
        self.assertNotIn("input_tokens", captured["tasks"][0]["cost"])

    def test_case_specific_hard_checks_are_preserved_and_unknown_blocks_acceptance(self):
        self.manifest["tasks"][0]["hard_checks"] = ["numbers_consistent"]
        result = self.result()
        self.assertEqual("unknown", result["pairs"][0]["factual_checks"]["numbers_consistent"]["candidate"])
        self.assertEqual("incomplete_or_rejected", compare(self.manifest, *self.runs, self.root, self.root)["status"])
        self.runs[0]["tasks"][0]["factual_checks"]["numbers_consistent"] = "pass"
        self.runs[1]["tasks"][0]["factual_checks"]["numbers_consistent"] = "fail"
        self.seal()
        self.assertEqual("regressed", self.result()["pairs"][0]["factual_checks"]["numbers_consistent"]["change"])
        row = self.runs[1]["tasks"][0]
        spec = {"effective_config": self.runs[1]["effective_config"]["path"], "tasks": [{"id": "fixture", **{key: row[key]["path"] for key in ("trace", "assessment", "materials", "output")}}]}
        captured = capture(spec, self.root, self.exp_path)
        self.assertEqual("fail", captured["tasks"][0]["factual_checks"]["numbers_consistent"])

    def test_diagnostic_exit_zero_does_not_mean_quality_pass(self):
        self.runs[1]["tasks"] = []
        for label, run in zip(("baseline", "candidate"), self.runs):
            self.write(label + ".json", run)
        output = self.root / "diagnostic.json"
        run = subprocess.run([sys.executable, str(Path(__file__).with_name("diagnose_runs.py")),
                              str(self.root / "baseline.json"), str(self.root / "candidate.json"),
                              "--experiment", str(self.exp_path), "--manifest", str(self.manifest_path), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stderr)
        result = json.loads(output.read_text(encoding="utf-8"))
        self.assertFalse(result["comparison_valid"])
        self.assertFalse(result["receipt_issued"])


if __name__ == "__main__":
    unittest.main()
