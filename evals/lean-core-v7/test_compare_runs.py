import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from compare_runs import CONDITIONS, EXTRA_COST_METRICS, FACTUAL_CHECKS, compare


class PairedRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = {"tasks": [{"id": "test-only", "task": "Fixture prompt"}], "quality_metrics": ["accuracy"], "cost_metrics": ["tool_calls"]}
        self.runs = []
        for label in ("baseline", "candidate"):
            evidence = {}
            for key in ("trace", "assessment", "materials"):
                content = "Shared synthetic material fixture" if key == "materials" else f"Synthetic test-only {label} {key}"
                filename = label + "-" + key + ".txt"
                (self.root / filename).write_text(content, encoding="utf-8")
                evidence[key] = {"path": filename, "sha256": hashlib.sha256(content.encode()).hexdigest()}
            self.runs.append({"run_id": label, "code_revision": label, "tasks": [{
                "id": "test-only", "status": "completed", **evidence,
                **{key: "same" for key in CONDITIONS},
                "material_snapshot_sha256": evidence["materials"]["sha256"],
                "task_prompt_sha256": hashlib.sha256(b"Fixture prompt").hexdigest(),
                "quality": {"accuracy": 3},
                "cost": {key: 1 for key in ["tool_calls", *EXTRA_COST_METRICS]},
                "factual_checks": {key: "pass" for key in FACTUAL_CHECKS},
            }]})

    def run_comparison(self):
        return compare(self.manifest, *self.runs, self.root, self.root)

    def test_paired_evidence_requires_review_not_automatic_gate_removal(self):
        self.assertEqual("review_required", self.run_comparison()["status"])

    def test_factual_failure_cannot_be_offset_by_lower_cost(self):
        item = self.runs[1]["tasks"][0]
        item["factual_checks"][FACTUAL_CHECKS[0]] = "fail"
        item["cost"] = {key: 0 for key in item["cost"]}
        self.assertEqual("incomplete_or_rejected", self.run_comparison()["status"])

    def test_missing_trace_or_metrics_never_counts_as_zero(self):
        del self.runs[1]["tasks"][0]["cost"]["wall_time_seconds"]
        self.assertEqual("incomplete_or_rejected", self.run_comparison()["status"])
        self.runs[1]["tasks"][0]["trace"]["sha256"] = "changed"
        self.assertTrue(any("trace" in issue for issue in self.run_comparison()["issues"]))

    def test_model_changes_and_quality_regressions_are_separate(self):
        self.runs[1]["tasks"][0]["model"] = "different"
        self.assertEqual("not_comparable", self.run_comparison()["status"])
        self.runs[1]["tasks"][0]["model"] = "same"
        self.runs[1]["tasks"][0]["quality"]["accuracy"] = 2
        self.assertEqual("quality_regression", self.run_comparison()["status"])

    def test_duplicated_or_missing_frozen_tasks_are_rejected(self):
        self.runs[1]["tasks"].append(copy.deepcopy(self.runs[1]["tasks"][0]))
        self.assertEqual("incomplete_or_rejected", self.run_comparison()["status"])


if __name__ == "__main__":
    unittest.main()
