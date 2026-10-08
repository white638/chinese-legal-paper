"""Synthetic contract tests do not claim real model or expert assessments."""
import copy
from contextlib import redirect_stdout
import importlib
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

from evaluate import COSTS, compare, main, prepare_pairs
import test_factorial


class PairedTests(unittest.TestCase):
    def setUp(self):
        fixture = test_factorial.FactorialTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root, self.asset = fixture.root, fixture.asset
        self.manual = fixture.experiment
        self.record = {"schema_version": "avereth-commonplace-paired/v1", "synthetic": True,
                       "target": {"category": "prose", "metric": "pairwise_preference", "direction": "increase", "min_win_margin": .2, "min_pairs": 1},
                       "tasks": [{"id": "writing-1", "task": "SYNTHETIC: write from the bounded evidence.",
                                  "cells": {key: fixture.experiment["cells"][key] for key in ("C", "D")}}]}
        for label, cell in self.record["tasks"][0]["cells"].items():
            cell["hard_checks"] = {key: self.asset(label + "-" + key + ".json", {"output_sha256": cell["output"]["sha256"], "status": "PASS"})
                                   for key in ("claims_supported", "protected_facts_preserved", "citation_metadata_valid", "task_completion")}

    def evaluate(self, callback):
        return compare(self.record, self.root, self.root / "evaluation", evaluator=callback)

    def test_default_pair_uses_central_automated_judge_without_human_or_ten_metrics(self):
        for cell in self.record["tasks"][0]["cells"].values():
            del cell["metrics"]
        calls = []
        def automated(pairs, config, output, **kwargs):
            calls.append((pairs, kwargs))
            return {"verdict": "UNCERTAIN", "auto_promotion_eligible": False}
        result = self.evaluate(automated)
        self.assertEqual(1, len(calls))
        pair, flags = calls[0][0][0], calls[0][1]
        self.assertTrue(flags["synthetic"])
        self.assertEqual("Synthetic output C", pair["baseline"])
        self.assertEqual("Synthetic output D", pair["candidate"])
        self.assertEqual("optional", result["commonplace_comparison"]["human_review"])
        self.assertTrue(all(value is None for value in pair["metrics"]["candidate"].values()))

    def test_invalid_binding_never_spends_a_judge_call(self):
        (self.root / "D.txt").write_text("changed", encoding="utf-8")
        result = self.evaluate(lambda *a, **k: self.fail("judge called for untrusted artifacts"))
        self.assertEqual("UNCERTAIN", result["verdict"])
        self.assertFalse(result["auto_promotion_eligible"])

    def test_candidate_failure_is_preserved_for_central_hard_gate(self):
        cell = self.record["tasks"][0]["cells"]["D"]
        cell["semantic_review"] = self.asset("failure.json", {"output_sha256": cell["output"]["sha256"], "status": "FAIL"})
        pairs, issues = prepare_pairs(self.record, self.root)
        self.assertFalse(issues)
        self.assertEqual(["semantic_fidelity"], pairs[0]["hard_failures"])

    def test_review_is_uncertain_and_cannot_be_treated_as_pass(self):
        cell = self.record["tasks"][0]["cells"]["D"]
        cell["borrowing_check"] = self.asset("review.json", {"output_sha256": cell["output"]["sha256"], "status": "REVIEW"})
        pairs, issues = prepare_pairs(self.record, self.root)
        self.assertFalse(issues)
        self.assertFalse(pairs[0]["hard_checks_complete"])
        self.assertFalse(pairs[0]["prose_checks_complete"])

    def test_baseline_failure_is_recorded_without_becoming_candidate_failure(self):
        cell = self.record["tasks"][0]["cells"]["C"]
        cell["semantic_review"] = self.asset("baseline-failure.json", {"output_sha256": cell["output"]["sha256"], "status": "FAIL"})
        pairs, issues = prepare_pairs(self.record, self.root)
        self.assertFalse(issues)
        self.assertFalse(pairs[0]["hard_failures"])
        self.assertEqual(["semantic_fidelity"], pairs[0]["baseline_hard_failures"])

    def test_hash_bound_trace_preserves_missing_cost_as_null(self):
        cell = self.record["tasks"][0]["cells"]["D"]
        cell["trace"] = self.asset("trace.json", {"output_sha256": cell["output"]["sha256"],
                                                 "measurements": {"input_tokens": 57, "tool_calls": False, "retries": -1}})
        pairs, issues = prepare_pairs(self.record, self.root)
        self.assertFalse(issues)
        self.assertEqual(57, pairs[0]["costs"]["candidate"]["input_tokens"])
        self.assertIsNone(pairs[0]["costs"]["candidate"]["tool_calls"])
        self.assertIsNone(pairs[0]["costs"]["candidate"]["retries"])
        self.assertEqual(dict.fromkeys(COSTS), pairs[0]["costs"]["baseline"])

    def test_mismatched_material_model_and_budget_are_invalid(self):
        for key, value in (("evidence_sha256", "f" * 64), ("model_revision", "other"), ("budget", {"tokens": 500})):
            with self.subTest(key=key):
                record = copy.deepcopy(self.record)
                record["tasks"][0]["cells"]["D"][key] = value
                self.assertTrue(prepare_pairs(record, self.root)[1])

    def test_five_real_tasks_required_without_relabeling_fixture_as_real_result(self):
        self.record["synthetic"] = False
        self.assertTrue(prepare_pairs(self.record, self.root)[1])

    def test_duplicate_context_and_ignored_factorial_cells_are_invalid(self):
        cells = self.record["tasks"][0]["cells"]
        cells["D"]["writer_context_id"] = cells["C"]["writer_context_id"]
        self.assertTrue(prepare_pairs(self.record, self.root)[1])
        cells["A"] = copy.deepcopy(cells["C"])
        self.assertTrue(prepare_pairs(self.record, self.root)[1])

    def test_optional_hard_check_binds_current_output(self):
        cell = self.record["tasks"][0]["cells"]["D"]
        cell["hard_checks"] = {"citations": self.asset("citations.json", {"output_sha256": "f" * 64, "status": "PASS"})}
        self.assertTrue(prepare_pairs(self.record, self.root)[1])

    def test_path_escape_is_invalid(self):
        self.record["tasks"][0]["cells"]["D"]["output"]["path"] = "../outside.txt"
        self.assertTrue(prepare_pairs(self.record, self.root)[1])

    def test_cli_requires_explicit_manual_research_for_four_cells(self):
        path = self.root / "factorial.json"
        path.write_text(json.dumps({"schema_version": "avereth-commonplace-factorial/v1", "synthetic": True}), encoding="utf-8")
        run = subprocess.run([sys.executable, str(Path(__file__).with_name("evaluate.py")), str(path)], capture_output=True, text=True)
        self.assertEqual(2, run.returncode)
        self.assertIn("--manual-research", run.stdout)

    def test_cli_exit_codes_follow_actual_paired_verdicts(self):
        lean = str(Path(__file__).resolve().parents[1] / "lean-core-v7")
        if lean not in sys.path:
            sys.path.insert(0, lean)
        paired = importlib.import_module("paired_eval")
        self.record["judge_config"] = {"primary": {"runner": "codex", "model": "synthetic-one", "family": "synthetic-family"},
                                       "swap_check_rate": 0}
        path = self.root / "paired.json"
        path.write_text(json.dumps(self.record), encoding="utf-8")
        for verdict, expected, suffix in (("KEEP", 0, "D"), ("REJECT", 1, "C"), ("UNCERTAIN", 2, None)):
            with self.subTest(verdict=verdict):
                def judge(spec, prompt):
                    data = json.loads(prompt.split("DATA:\n", 1)[1])
                    choice = "UNCERTAIN" if suffix is None else "A" if data["A"].endswith(suffix) else "B"
                    return {"context_id": "synthetic-cli-judge", "model": spec["model"],
                            "response": {"choice": choice, "confidence": 0.95,
                                         "rationale": "Synthetic comparison for CLI contract validation.",
                                         "evidence": ["Synthetic output C", "Synthetic output D"]}}
                output = self.root / (verdict + ".json")
                with patch.object(paired, "_host_judge", side_effect=judge), redirect_stdout(io.StringIO()):
                    code = main([str(path), "--output", str(output)])
                report = json.loads(output.read_text(encoding="utf-8"))
                self.assertEqual(verdict, report["verdict"])
                self.assertEqual(expected, code)
                self.assertFalse(report["auto_promotion_eligible"])

    def test_cli_invalid_json_exit_code_preserves_manual_compatibility(self):
        path = self.root / "invalid.json"
        path.write_text("{", encoding="utf-8")
        for flags, expected in (([], 2), (["--manual-research"], 1)):
            with self.subTest(flags=flags), redirect_stdout(io.StringIO()) as captured:
                code = main([str(path), *flags])
            self.assertEqual(expected, code)
            self.assertEqual("INCOMPLETE_OR_INVALID", json.loads(captured.getvalue())["status"])

    def test_manual_cli_accepts_four_cells_without_human_review(self):
        del self.manual["blind_review"]
        path = self.root / "manual.json"
        path.write_text(json.dumps(self.manual), encoding="utf-8")
        run = subprocess.run([sys.executable, str(Path(__file__).with_name("evaluate.py")), str(path), "--manual-research"],
                             capture_output=True, text=True)
        self.assertEqual(0, run.returncode, run.stdout + run.stderr)
        result = json.loads(run.stdout)
        self.assertEqual("SYNTHETIC_CONTRACT_ONLY", result["status"])
        self.assertFalse(result["default_promotion"])

    def test_central_judge_integration_cannot_promote_synthetic_winner(self):
        calls = []
        def judge(spec, prompt):
            calls.append(prompt)
            data = json.loads(prompt.split("DATA:\n", 1)[1])
            return {"context_id": "synthetic-judge-" + str(len(calls)), "model": spec["model"],
                    "response": {"choice": "A" if data["A"].endswith("D") else "B", "confidence": 0.95,
                                 "rationale": "Synthetic comparison for interface validation.",
                                 "evidence": ["Synthetic output D"]}}
        config = {"primary": {"runner": "codex", "model": "synthetic-one", "family": "synthetic-family"},
                  "swap_check_rate": 0}
        result = compare(self.record, self.root, self.root / "central", judge_config=config, judge=judge,
                         input_bindings={"synthetic_contract": True})
        self.assertEqual("KEEP", result["verdict"])
        self.assertEqual(1, len(calls))
        self.assertFalse(result["auto_promotion_eligible"])

    def test_central_rejects_hard_failure_without_model_call(self):
        cell = self.record["tasks"][0]["cells"]["D"]
        cell["borrowing_check"] = self.asset("hard-failure.json", {"output_sha256": cell["output"]["sha256"], "status": "FAIL"})
        result = compare(self.record, self.root, self.root / "central-fail",
                         judge_config={"primary": {"runner": "codex", "model": "synthetic-one", "family": "synthetic-family"}},
                         judge=lambda *args: self.fail("hard failure invoked a judge"))
        self.assertEqual("REJECT", result["verdict"])

    def test_missing_required_prose_check_cannot_promote(self):
        del self.record["tasks"][0]["cells"]["D"]["hard_checks"]["citation_metadata_valid"]
        result = compare(self.record, self.root, self.root / "missing-prose-check",
                         judge_config={"primary": {"runner": "codex", "model": "synthetic-one", "family": "synthetic-family"}},
                         judge=lambda *args: self.fail("unchecked prose invoked a judge"))
        self.assertEqual("UNCERTAIN", result["verdict"])

    def test_commonplace_target_is_explicit_and_not_inferred_from_name(self):
        del self.record["target"]
        result = compare(self.record, self.root, self.root / "missing-target",
                         judge=lambda *args: self.fail("missing target invoked a judge"))
        self.assertEqual("UNCERTAIN", result["verdict"])


if __name__ == "__main__":
    unittest.main()
