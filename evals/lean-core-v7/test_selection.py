"""Versioned bank and selected-denominator contracts use synthetic local data."""
import copy
import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from run_records import load_json, selection_bindings, selection_issues
from selection import digest, evolve, file_sha, select, validate_bank, validate_selection, write_selection


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.bank_path = Path(__file__).with_name("manifest.json")
        self.bank = load_json(self.bank_path)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def selection(self, **kwargs):
        return select(self.bank, file_sha(self.bank_path), **kwargs)

    def test_old_case_identity_and_balance_are_retained_as_bank_assets(self):
        validate_bank(self.bank)
        self.assertEqual(30, len(self.bank["tasks"]))
        self.assertTrue(all(task["lifecycle"]["origin"] == "legacy_curated_capability" for task in self.bank["tasks"]))
        self.assertEqual("fixtures_frozen_model_runs_pending", self.bank["evaluation_status"])

    def test_scopes_have_real_case_limits(self):
        self.assertEqual(2, len(self.selection(scope="smoke")["tasks"]))
        self.assertEqual(6, len(self.selection()["tasks"]))
        self.assertEqual(30, len(self.selection(scope="broader")["tasks"]))
        for scope, limit in (("smoke", 4), ("targeted", 2), ("targeted", 9), ("broader", 0)):
            with self.assertRaises(ValueError):
                self.selection(scope=scope, max_cases=limit)

    def test_tags_exclusions_and_diff_impacts_change_actual_selection(self):
        selected = self.selection(tags=["prose"], exclude_tags=["quantitative"], max_cases=3)
        self.assertEqual(3, len(selected["tasks"]))
        self.assertTrue(all("prose" in task["tags"] and "quantitative" not in task["tags"] for task in selected["tasks"]))
        impacted = self.selection(changed_paths=["scripts/reference_plan.py"], max_cases=3)
        self.assertIn("reference-loading", impacted["selection"]["impacted_tags"])
        with self.assertRaisesRegex(ValueError, "NOT RUN"):
            self.selection(tags=["nonexistent-capability"])
        with self.assertRaisesRegex(ValueError, "NOT RUN"):
            self.selection(changed_paths=["unmapped.asset"])

    def test_main_instruction_surfaces_route_to_actual_targeted_cases(self):
        for path in ("skills/cnki-paper/SKILL.source.md", "entrypoints/avereth.source.md", "agent-specs/avereth.agent.toml"):
            selected = self.selection(changed_paths=[path], max_cases=3)
            self.assertEqual(3, len(selected["tasks"]))
            self.assertTrue({"routing", "context", "permissions", "checkpoint"} <= set(selected["selection"]["impacted_tags"]))

    def test_novelty_component_selects_contribution_and_collision_tasks(self):
        for path in ("skills/cnki-paper/scripts/novelty_delta.py", "evals/novelty-regression/run_eval.py"):
            selected = self.selection(changed_paths=[path], max_cases=3)
            self.assertEqual(3, len(selected["tasks"]))
            self.assertTrue(all("novelty" in task["tags"] for task in selected["tasks"]))
        self.assertGreaterEqual(self.bank["bank_version"], 2)

    def test_selection_is_deterministic_and_binds_actual_source_snapshot(self):
        first = write_selection(self.bank_path, self.root / "selected.json", tags=["citation"], max_cases=3)
        self.assertEqual(first["selection"], self.selection(tags=["citation"], max_cases=3)["selection"])
        validate_selection(first, self.root)
        with self.assertRaises(FileExistsError):
            write_selection(self.bank_path, self.root / "selected.json", tags=["citation"], max_cases=3)
        (self.root / first["source_bank"]["path"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "source bank"):
            validate_selection(first, self.root)

    def test_selected_task_or_rule_tampering_is_detected(self):
        for field in ("task", "rule"):
            selected = self.selection(max_cases=3)
            if field == "task":
                selected["tasks"][0]["task"] = "changed task"
            else:
                selected["selection"]["max_cases"] = 8
            with self.assertRaises(ValueError):
                validate_selection(selected)

    def test_both_sides_must_bind_same_selection_and_legacy_is_readable(self):
        manifest = self.selection(max_cases=3)
        fields = selection_bindings(manifest)
        self.assertEqual([], selection_issues(manifest, fields))
        self.assertTrue(selection_issues(manifest, {**fields, "selection_sha256": "changed"}))
        self.assertEqual([], selection_issues({"tasks": []}, {}))
        self.assertTrue(selection_issues({"tasks": []}, fields))

    def test_archive_needs_explicit_complete_deterministic_coverage(self):
        case = self.bank["tasks"][0]
        with self.assertRaisesRegex(ValueError, "coverage"):
            evolve(self.bank, archive_id=case["id"], coverage={"consecutive_successes": 100})
        coverage = {"evidence": {"path": "fixture.json", "sha256": "synthetic"}, "validator": "synthetic-test", "reason": "Synthetic complete coverage", "covers_hard_checks": case["hard_checks"]}
        archived = evolve(self.bank, archive_id=case["id"], coverage=coverage)
        self.assertEqual(self.bank["bank_version"] + 1, archived["bank_version"])
        self.assertEqual("archived", archived["tasks"][0]["lifecycle"]["status"])
        self.assertNotIn(case["id"], select(archived, digest(archived), scope="broader")["selection"]["selected_ids"])
        self.assertEqual("active", self.bank["tasks"][0]["lifecycle"]["status"])

    def test_new_case_adds_version_without_changing_prior_cases(self):
        case = copy.deepcopy(self.bank["tasks"][0])
        case["id"] = "NEW-SYNTHETIC-CASE"
        case["lifecycle"] = {"status": "active", "origin": "observed_failure"}
        with self.assertRaisesRegex(ValueError, "original evidence"):
            evolve(self.bank, case=case)
        case["lifecycle"]["origin_evidence"] = "Synthetic original fixture record"
        evolved = evolve(self.bank, case=case)
        self.assertEqual(31, len(evolved["tasks"]))
        self.assertEqual(self.bank["tasks"], evolved["tasks"][:-1])
        self.assertEqual(self.bank["bank_version"] + 1, evolved["bank_version"])

    def test_cli_cannot_add_claimed_failure_without_original_record(self):
        case = copy.deepcopy(self.bank["tasks"][0])
        case.update(id="CLAIMED-FAILURE", lifecycle={"status": "active", "origin": "observed_failure", "origin_evidence": {"path": "missing.json", "sha256": "claimed"}})
        path = self.root / "case.json"
        path.write_text(json.dumps(case), encoding="utf-8")
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("selection.py")), str(self.bank_path), "--add-case", str(path), "--output", str(self.root / "new-bank.json")], capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertIn("actual original failure record", result.stdout)
        self.assertFalse((self.root / "new-bank.json").exists())


if __name__ == "__main__":
    unittest.main()
