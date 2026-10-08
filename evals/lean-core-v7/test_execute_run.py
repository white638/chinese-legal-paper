"""Synthetic subprocess fixtures verify orchestration, never research quality."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execute_run import execute, init_spec, load_json, preflight, sha, utc
from trajectory_report import summarize


FAKE = r'''
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
request = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
def write(path, value):
    Path(path).write_text(json.dumps(value), encoding="utf-8")
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
if "--host" in sys.argv:
    print(json.dumps({"type": "fixture.host", "label": "synthetic subprocess"}))
    if "--fail" in sys.argv:
        print("synthetic failure", file=sys.stderr)
        raise SystemExit(7)
    write(request["output"], {"fixture": "synthetic output"})
    write(request["trace_output"], {"run_context": {**request["expected_context"], "started_at": datetime.now(timezone.utc).isoformat(), "context_id": "writer-" + request["expected_context"]["run_id"] + request["task"]["id"]},
        "events": [{"type": "synthetic.fixture"}], "status": "completed", "failure_reason": None,
        "execution_scope": "full_workflow", "workflow_evidence": ["synthetic evidence"],
        "measurements": {"wall_time_seconds": 0.02}, "output_sha256": digest(request["output"])})
else:
    print(json.dumps({"type": "fixture.review", "label": "synthetic subprocess"}))
    write(request["raw_review_output"], {"fixture": "Synthetic review, not scientific scoring."})
    write(request["assessment_output"], {"quality": {}, "factual_checks": {}, "diagnostics": {}, "responsibility_coverage": {},
        "evidence_notes": "Synthetic fixture judgments deliberately remain unknown.",
        "trace_sha256": request["trace_sha256"], "output_sha256": request["output_sha256"], "raw_review_sha256": digest(request["raw_review_output"]),
        "review_context": {"context_id": request.get("writer_context_id") if "--same-context" in sys.argv else "independent-review-" + request["task"]["id"],
                           "reviewer_id": request["reviewer_id"], "independence_basis": "Synthetic separate process"}})
'''


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = self.root / "code"
        (self.code / "skills/cnki-paper").mkdir(parents=True)
        (self.code / "skills/cnki-paper/SKILL.source.md").write_text("Synthetic fixture code", encoding="utf-8")
        for command in (["init", "--quiet"], ["add", "."], ["-c", "user.name=Fixture", "-c", "user.email=fixture@example.test", "commit", "--quiet", "-m", "fixture"]):
            subprocess.run(["git", "-C", str(self.code), *command], check=True, capture_output=True)
        revision = subprocess.run(["git", "-C", str(self.code), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
        self.manifest = {"tasks": [{"id": "fixture-1", "task": "Synthetic task one", "outcome_checks": ["Synthetic requirement"]},
                                    {"id": "fixture-2", "task": "Synthetic task two", "outcome_checks": ["Synthetic requirement"]}],
                         "quality_metrics": ["accuracy"], "cost_metrics": ["tool_calls"]}
        self.manifest_path = self.root / "manifest.json"
        self.write(self.manifest_path, self.manifest)
        self.config = {"model": "synthetic-model", "reasoning_effort": "medium", "host_version": "synthetic-host",
                       "tool_versions": {"synthetic-tool": "1"}, "prompt_version": "synthetic-prompt",
                       "evaluation_mode": "offline_fixed_materials", "source_access": {"network": "disabled"},
                       "budget": {"task_timeout_seconds": 5}}
        self.write(self.root / "effective-config.json", self.config)
        (self.root / "fake.py").write_text(FAKE, encoding="utf-8")
        self.spec = {"schema_version": "avereth-workflow-execution-spec/v1", "run_id": "synthetic-test-only", "side": "baseline",
                     "evidence_mode": "real_workflow", "code_root": str(self.code), "code_revision": revision,
                     "effective_config": self.binding("effective-config.json"), "task_timeout_seconds": 5,
                     "host": self.command("host"), "assessor": self.command("assessor"), "tasks": []}
        for task in self.manifest["tasks"]:
            prefix = task["id"]
            (self.root / (prefix + "-material.txt")).write_text("Synthetic material for orchestration tests.", encoding="utf-8")
            materials = {"schema_version": "avereth-material-snapshot/v1", "files": [{**self.binding(prefix + "-material.txt"),
                          "destination": "source.txt", "source_id": "synthetic-source", "role": "test-fixture",
                          "content_verified": True, "permission": "public_domain", "verification_notes": "Explicit synthetic test fixture"}]}
            self.write(self.root / (prefix + "-materials.json"), materials)
            self.write(self.root / (prefix + "-authorization.json"), {"task_prompt_sha256": hashlib.sha256(task["task"].encode()).hexdigest(),
                       "permitted_endpoint": {"kind": "profile_complete"}, "authority_evidence": "Synthetic test only"})
            self.spec["tasks"].append({"id": prefix, "materials": self.binding(prefix + "-materials.json"), "authorization": self.binding(prefix + "-authorization.json")})
        self.spec_path, self.exp_path, self.run_root = self.root / "spec.json", self.root / "experiment.json", self.root / "run"
        self.write(self.exp_path, {"schema_version": "avereth-paired-experiment/v1", "experiment_id": "synthetic-test-only",
                                  "registered_at": "2020-01-01T00:00:00Z", "manifest_sha256": sha(self.manifest_path),
                                  "baseline_config_sha256": self.spec["effective_config"]["sha256"], "candidate_config_sha256": self.spec["effective_config"]["sha256"],
                                  "allowed_config_changes": [], "evaluation_mode": "offline_fixed_materials"})
        experiment = load_json(self.exp_path)
        experiment["target"] = {"category": "efficiency", "metric": "tool_calls", "direction": "decrease", "min_absolute_improvement": 1}
        self.write(self.exp_path, experiment)
        self.save()

    def write(self, path, payload):
        path.write_text(json.dumps(payload), encoding="utf-8")

    def binding(self, name):
        return {"path": name, "sha256": sha(self.root / name)}

    def command(self, role, extra=None):
        argv = [sys.executable, str(self.root / "fake.py"), "{request}", "--host" if role == "host" else "--assess", *(extra or [])]
        self.write(self.root / (role + "-review.json"), {"argv_sha256": hashlib.sha256(json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
                   "reviewer": "Synthetic fixture", "evidence_notes": "Synthetic reviewed command", "sandbox_policy": "host_enforced", "network_policy": "disabled"})
        return {"argv": argv, "adapter_files": [self.binding("fake.py")], "review_record": self.binding(role + "-review.json"),
                "capabilities": ["full_workflow", "isolated_workspace", "raw_trace"],
                "reviewer_id": "synthetic-assessor", "independence_basis": "separate synthetic process"}

    def save(self):
        self.write(self.spec_path, self.spec)

    def check(self):
        self.save()
        return preflight(self.spec_path, self.exp_path, self.manifest_path)

    def run_suite(self, **kwargs):
        self.save()
        return execute(self.spec_path, self.exp_path, self.manifest_path, self.run_root, **kwargs)

    def test_preflight_accepts_clean_canonical_source_and_actual_material_files(self):
        self.assertEqual("ready_for_execution", self.check()["status"])

    def test_changed_materials_are_blocked_before_any_host_call(self):
        (self.root / "fixture-1-material.txt").write_text("changed", encoding="utf-8")
        with patch("execute_run.invoke") as invoke:
            result = self.run_suite()
        self.assertEqual("blocked", result["status"])
        self.assertEqual(2, result["required_tasks"])
        invoke.assert_not_called()

    def test_preflight_rejects_bypass_and_incomplete_capabilities(self):
        self.spec["host"]["argv"].append("--dangerously-bypass-approvals-and-sandbox")
        self.assertTrue(any("bypass" in issue for issue in self.check()["issues"]))
        self.spec["host"] = self.command("host")
        self.spec["host"]["capabilities"] = ["other"]
        self.assertTrue(any("full_workflow" in issue for issue in self.check()["issues"]))

    def test_dropped_task_or_dirty_code_prevents_execution(self):
        self.spec["tasks"].pop()
        self.assertEqual("blocked", self.check()["status"])
        (self.code / "untracked.txt").write_text("dirty")
        self.assertTrue(any("clean" in issue for issue in self.check()["issues"]))

    def test_real_subprocess_flow_is_isolated_resumable_and_not_quality_pass(self):
        result = self.run_suite()
        self.assertEqual(2, result["completed_tasks"])
        self.assertFalse(result["quality_passed"])
        self.assertTrue((self.run_root / "tasks/fixture-1/attempt-0001/workspace/materials/source.txt").is_file())
        first = {path: sha(path) for path in self.run_root.rglob("*") if path.is_file()}
        resumed = self.run_suite()
        self.assertEqual(2, resumed["completed_tasks"])
        self.assertFalse(any(self.run_root.rglob("attempt-0002")))
        self.assertTrue(all(sha(path) == digest for path, digest in first.items()))
        captured = load_json(self.run_root / result["captured_run"])
        self.assertNotIn("tool_calls", captured["tasks"][0]["cost"])

    def test_resume_rejects_changed_sealed_evidence(self):
        self.run_suite()
        (self.run_root / "tasks/fixture-1/attempt-0001/stdout.raw").write_text("changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.run_suite()

    def test_failed_tasks_stay_in_denominator_and_keep_raw_output(self):
        self.spec["host"] = self.command("host", ["--fail"])
        result = self.run_suite()
        self.assertEqual(2, result["required_tasks"])
        self.assertEqual(0, result["completed_tasks"])
        captured = load_json(self.run_root / result["captured_run"])
        self.assertEqual(2, len(captured["tasks"]))
        self.assertEqual("failed", captured["tasks"][0]["status"])
        self.assertIsNone(captured["tasks"][0]["model"])
        self.assertIn("synthetic failure", (self.run_root / "tasks/fixture-1/attempt-0001/stderr.raw").read_text())

    def test_shared_writer_reviewer_context_blocks_assessment(self):
        self.spec["assessor"] = self.command("assessor", ["--same-context"])
        result = self.run_suite()
        self.assertEqual("blocked", result["status"])
        self.assertEqual("blocked", result["records"][0]["review_status"])

    def test_operator_interrupt_does_not_start_more_models(self):
        with patch("execute_run.invoke", return_value={"started_at": utc(), "wall_time_seconds": 0.1, "failure_type": "operator_interruption", "returncode": None}) as invoke:
            result = self.run_suite()
        self.assertEqual(1, invoke.call_count)
        self.assertEqual(2, result["required_tasks"])
        self.assertEqual("not_started_after_operator_interruption", result["records"][1]["failure_type"])

    def test_scaffold_exposes_all_missing_frozen_tasks(self):
        frozen = Path(__file__).with_name("manifest.json")
        destination = self.root / "setup"
        init_spec(destination, frozen, self.code)
        result = preflight(destination / "execution-spec.json", destination / "experiment.json", destination / "selected-manifest.json")
        self.assertEqual(6, result["required_tasks"])
        self.assertEqual(0, result["ready_tasks"])
        self.assertEqual(6, sum("actual material snapshot" in issue for issue in result["issues"]))
        self.assertEqual("blocked", result["status"])

    def select_one(self):
        from selection import write_selection
        from run_records import selection_bindings
        bank = dict(self.manifest, bank_version=1)
        for task in bank["tasks"]:
            task.update(tags=["context"], failure_mode="synthetic", risk="low", hard_checks=["no_fabricated_sources"],
                        target_metrics=["tool_calls"], lifecycle={"status": "active", "origin": "synthetic"})
        bank_path = self.root / "bank.json"
        self.write(bank_path, bank)
        self.manifest_path = self.root / "selected-manifest.json"
        self.manifest = write_selection(bank_path, self.manifest_path, scope="smoke", max_cases=1)
        self.spec.update(selection_bindings(self.manifest))
        experiment = load_json(self.exp_path)
        experiment.update(manifest_sha256=sha(self.manifest_path), **selection_bindings(self.manifest))
        self.write(self.exp_path, experiment)

    def test_only_selected_case_materials_are_required_and_executed(self):
        self.select_one()
        (self.root / "fixture-2-material.txt").unlink()
        result = self.run_suite()
        self.assertEqual(1, result["required_tasks"])
        captured = load_json(self.run_root / result["captured_run"])
        self.assertEqual(["fixture-1"], [row["id"] for row in captured["tasks"]])
        self.assertEqual(self.spec["selection_sha256"], captured["selection_sha256"])
        self.assertFalse((self.run_root / "tasks/fixture-2").exists())

    def test_selected_failure_keeps_selection_and_denominator(self):
        self.select_one()
        self.spec["host"] = self.command("host", ["--fail"])
        result = self.run_suite()
        captured = load_json(self.run_root / result["captured_run"])
        self.assertEqual(1, len(captured["tasks"]))
        self.assertEqual("failed", captured["tasks"][0]["status"])
        self.assertEqual(self.spec["selection_sha256"], captured["tasks"][0]["selection_sha256"])

    def test_declared_instruction_variant_is_checked(self):
        self.config["instruction_variant"] = "unsupported"
        self.write(self.root / "effective-config.json", self.config)
        self.spec["effective_config"] = self.binding("effective-config.json")
        experiment = load_json(self.exp_path)
        experiment["baseline_config_sha256"] = self.spec["effective_config"]["sha256"]
        self.write(self.exp_path, experiment)
        self.assertTrue(any("instruction_variant" in issue for issue in self.check()["issues"]))

    def test_trajectory_keeps_unknowns_and_does_not_merge_task_local_defects(self):
        result = self.run_suite()
        captured = load_json(self.run_root / result["captured_run"])
        for index, row in enumerate(captured["tasks"]):
            path = self.run_root / row["trace"]["path"]
            trace = load_json(path)
            trace["events"] = [{"type": "gate.result", "gate_id": "gate-" + str(index), "status": "reported", "defect_ids": ["D1"]},
                               {"type": "gate.executed", "gate": "intake", "exit_code": 0}, {"type": "reference_plan", "reference_requests": [{"path": "protocol.md"}]}]
            self.write(path, trace)
            row["trace"]["sha256"] = sha(path)
        report = summarize(self.manifest, captured, self.run_root)
        self.assertIsNone(report["reads"]["observed_bytes"])
        self.assertEqual([1, 1], [row["defects_reported_only_by_this_gate"] for row in report["gates"] if row["gate_id"].startswith("gate-")])
        self.assertTrue(all(row["verified_marginal_quality_gain"] is None for row in report["gates"]))


if __name__ == "__main__":
    unittest.main()
