"""Protect recorded baseline prompts without running a model or external service."""

import hashlib
import json
import unittest
from pathlib import Path


BASE = Path(__file__).parent / "baseline-6450aae"
JUDGE_BASE = Path(__file__).parent / "baseline-fae2cbf"


class FrozenBaselineTests(unittest.TestCase):
    def test_captured_files_match_frozen_hashes(self):
        manifest = json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("6450aae02b8b6f99db8feeb979a572419f35a79f", manifest["source_commit"])
        for name, digest in manifest["capture_sha256"].items():
            self.assertEqual(digest, hashlib.sha256((BASE / name).read_bytes()).hexdigest(), name)

    def test_baseline_exposes_strata_and_requires_negative_quota(self):
        prompt = (BASE / "selection.prompt.md").read_text(encoding="utf-8")
        schema = json.loads((BASE / "selection.schema.json").read_text(encoding="utf-8"))
        self.assertIn("A 组在同刊同年队列中长期获得最多引用", prompt)
        self.assertIn("B 组在同刊同年队列中引用最少", prompt)
        self.assertEqual(1, schema["properties"]["negative"]["minItems"])

    def test_baseline_uses_asymmetric_candidate_and_result_fields(self):
        prompt = (BASE / "judge.prompt.md").read_text(encoding="utf-8")
        self.assertIn("问题家族", prompt)
        self.assertIn("预期贡献", prompt)
        self.assertIn("结论", prompt)


class FrozenJudgeInputTests(unittest.TestCase):
    def test_exact_cli_capture_bytes_and_manifest_are_preserved(self):
        manifest = json.loads((JUDGE_BASE / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("fae2cbf09fc5d394bf1a0dd15b587294fad2e667", manifest["source_commit"])
        self.assertIn("no model responses", manifest["evidence_kind"])
        self.assertEqual(
            set(manifest["capture_sha256"]),
            {path.relative_to(JUDGE_BASE).as_posix() for path in JUDGE_BASE.rglob("*") if path.is_file() and path != JUDGE_BASE / "manifest.json"},
        )
        for name, digest in manifest["capture_sha256"].items():
            self.assertEqual(digest, hashlib.sha256((JUDGE_BASE / name).read_bytes()).hexdigest(), name)
        self.assertFalse(list(JUDGE_BASE.rglob("*.response.json")))

    def test_baseline_dispatches_even_when_all_pairs_are_incomparable(self):
        inventory = json.loads((JUDGE_BASE / "input-availability.json").read_text(encoding="utf-8"))
        published = inventory["cases"]["published-results"]
        self.assertEqual(0, published["comparable_pairs"])
        self.assertEqual(2, published["noncomparable_pairs"])
        self.assertEqual(1, published["emitted_prompt_count"])
        self.assertEqual("not_measured", inventory["production_reference_absence_frequency"])
        self.assertEqual("not_measured", inventory["research_quality_effect"])
        plan = json.loads((JUDGE_BASE / "published-results/base.taste_judge.plan.json").read_text(encoding="utf-8"))
        self.assertTrue(all(pair["comparable"] is False for item in plan["items"] for pair in item["pairs"]))

    def test_registered_explanations_do_not_reach_baseline_prompt(self):
        inventory = json.loads((JUDGE_BASE / "input-availability.json").read_text(encoding="utf-8"))
        for case in inventory["cases"].values():
            self.assertEqual(8, case["card_exemplar_count"])
            self.assertEqual(0, case["verbatim_exemplar_explanations_in_emitted_prompts"])
        prompt = next((JUDGE_BASE / "original-proposals").glob("*.prompt.md")).read_text(encoding="utf-8")
        self.assertIn("symmetric-assessment/v2", prompt)
        self.assertIn("厚度未见就填 unclear", prompt)


if __name__ == "__main__":
    unittest.main()
