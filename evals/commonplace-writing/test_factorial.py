"""Entirely synthetic experiment records; no expert or model results are claimed."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from factorial import FACTORS, METRICS, compare, validate_experiment


class FactorialTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        def asset(name, text):
            raw = text if isinstance(text, str) else json.dumps(text)
            path = self.root / name
            path.write_text(raw, encoding="utf-8")
            return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.asset = asset
        inputs = {name: asset(name + ".txt", "SYNTHETIC " + name) for name in ("question", "evidence", "mir")}
        cells = {}
        for label, (deep, cp) in FACTORS.items():
            output = asset(label + ".txt", "Synthetic output " + label)
            cells[label] = {"deep_reading": deep, "commonplace": cp, "inputs": inputs,
                            **{key + "_sha256": value["sha256"] for key, value in inputs.items()},
                            "model_revision": "synthetic-test", "budget": {"tokens": 1000}, "seed": 1,
                            "prompt": asset(label + "-prompt.txt", "synthetic prompt " + label), "output": output,
                            "writer_context_id": "synthetic-" + label, "metrics": {k: 1 for k in METRICS},
                            **{key: asset(label + key + ".json", {"status": "PASS", "output_sha256": output["sha256"]}) for key in ("semantic_review", "borrowing_check")}}
        review = asset("review.json", {"preference": "Y", "reviewer_context_id": "synthetic-reviewer", "reviewer_kind": "human_domain_expert",
                                       "input_scope": "anonymous_C_D_outputs_only", "rationale": "Synthetic test declaration, not an actual expert assessment.",
                                       "output_hashes": {"X": cells["C"]["output"]["sha256"], "Y": cells["D"]["output"]["sha256"]}})
        self.experiment = {"schema_version": "avereth-commonplace-factorial/v1", "synthetic": True, "cells": cells,
                           "blind_review": {"label_to_cell": {"X": "C", "Y": "D"}, "artifact": review}}

    def test_synthetic_record_cannot_claim_promotion(self):
        result = compare(self.experiment, self.root)
        self.assertEqual("SYNTHETIC_CONTRACT_ONLY", result["status"])
        self.assertFalse(result["default_promotion"])

    def test_mismatched_evidence_budget_model_and_factors_fail(self):
        for key, value in (("evidence_sha256", "f" * 64), ("budget", {"tokens": 2000}), ("model_revision", "different"), ("deep_reading", False)):
            with self.subTest(key=key):
                record = copy.deepcopy(self.experiment)
                record["cells"]["D"][key] = value
                self.assertTrue(validate_experiment(record, self.root))

    def test_human_review_is_optional(self):
        del self.experiment["blind_review"]
        result = compare(self.experiment, self.root)
        self.assertEqual("SYNTHETIC_CONTRACT_ONLY", result["status"])
        self.assertIsNone(result["blind_preference"])
        self.assertFalse(result["default_promotion"])

    def test_modified_output_invalidates_review(self):
        (self.root / "D.txt").write_text("changed", encoding="utf-8")
        self.assertTrue(validate_experiment(self.experiment, self.root))

    def test_semantic_failure_cannot_be_offset_by_style_scores(self):
        self.experiment["cells"]["D"]["metrics"]["semantic_fidelity"] = 0
        self.assertTrue(validate_experiment(self.experiment, self.root))

    def test_missing_metric_cannot_hide_overlap(self):
        del self.experiment["cells"]["D"]["metrics"]["rare_single_source_overlap"]
        self.assertTrue(validate_experiment(self.experiment, self.root))


if __name__ == "__main__":
    unittest.main()
