from __future__ import annotations

import json
import unittest
from collections import Counter
from pathlib import Path


MANIFEST = Path(__file__).with_name("manifest.json")


class LeanCoreManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.tasks = [item for item in cls.payload["tasks"] if (item.get("lifecycle") or {}).get("origin") == "legacy_curated_capability"]

    def test_bank_retains_thirty_balanced_legacy_capabilities(self) -> None:
        self.assertEqual(30, len(self.tasks))
        counts = Counter(item["category"] for item in self.tasks)
        self.assertEqual(6, len(counts))
        self.assertEqual({5}, set(counts.values()))
        self.assertEqual(30, len({item["id"] for item in self.tasks}))
        all_ids = [item["id"] for item in self.payload["tasks"]]
        self.assertEqual(len(all_ids), len(set(all_ids)))

    def test_versioned_bank_metadata_is_valid(self) -> None:
        from selection import validate_bank
        validate_bank(self.payload)

    def test_prose_cases_require_bound_content_and_fidelity_checks(self) -> None:
        for task in self.payload["tasks"]:
            if "prose" in task["tags"]:
                self.assertTrue(
                    {"claims_supported", "protected_facts_preserved",
                     "citation_metadata_valid", "semantic_fidelity"}
                    <= set(task["hard_checks"]), task["id"],
                )
                self.assertIn("pairwise_preference", task["target_metrics"])
            else:
                self.assertNotIn("semantic_fidelity", task["hard_checks"], task["id"])

    def test_quality_and_cost_metrics_are_both_present(self) -> None:
        self.assertGreaterEqual(len(self.payload["quality_metrics"]), 5)
        self.assertEqual(
            {
                "context_files_loaded",
                "context_bytes_loaded",
                "tool_calls",
                "agent_calls",
                "persistent_artifacts_created",
            },
            set(self.payload["cost_metrics"]),
        )

    def test_data_check_is_triggered_only_for_quantitative_category(self) -> None:
        for task in self.tasks:
            required = set(task["required_capabilities"])
            forbidden = set(task["must_not_default"])
            if task["category"] == "quantitative_topic_and_design":
                self.assertIn("quantitative-data-check", required, task["id"])
                self.assertIn("global-data-catalog", forbidden, task["id"])
                self.assertIn("automatic-data-matching", forbidden, task["id"])
            else:
                self.assertNotIn("quantitative-data-check", required, task["id"])
                self.assertIn("quantitative-data-check", forbidden, task["id"])

    def test_default_agent_and_artifact_budgets_follow_lean_targets(self) -> None:
        for task in self.tasks:
            self.assertLessEqual(task["max_default_agents"], 2, task["id"])
            self.assertLessEqual(task["max_core_artifacts"], 8, task["id"])
            if task["max_default_agents"] == 2:
                self.assertTrue(
                    {"reviewer-on-demand", "researcher-on-demand"}
                    & set(task["required_capabilities"]),
                    task["id"],
                )


if __name__ == "__main__":
    unittest.main()
