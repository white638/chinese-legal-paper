#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_method_maturity import (  # noqa: E402
    DEFAULT_REGISTRY,
    check,
    validate_maturity,
)


def _load_registry() -> dict:
    return json.loads((ROOT / DEFAULT_REGISTRY).read_text(encoding="utf-8"))


def _load_profile(registry: dict, family: str) -> dict:
    asset = registry["families"][family]["operation_profile_asset"]
    path = ROOT / "skills" / "empirical-research" / asset
    return json.loads(path.read_text(encoding="utf-8"))


class MethodMaturityCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load_registry()

    def validate(self, registry=None, *, overrides=None):
        return validate_maturity(
            ROOT,
            registry if registry is not None else self.registry,
            profile_overrides=overrides,
        )

    def test_checked_in_registry_has_19_distinct_experimental_profiles(self) -> None:
        report = check(ROOT)
        self.assertEqual((), report.issues)
        self.assertEqual(19, len(report.methods))
        self.assertEqual(
            {"experimental_method_support"},
            {item.declared_support_status for item in report.methods},
        )
        self.assertEqual(19, len({item.profile_asset for item in report.methods}))

    def test_maturity_is_cumulative_and_does_not_inflate_broad_adapters(self) -> None:
        report = self.validate()
        levels = {item.family: item.level for item in report.methods}
        self.assertEqual(3, levels["process_tracing"])
        self.assertEqual(3, levels["text_as_data"])
        self.assertEqual(1, levels["quantitative"])
        self.assertEqual(1, levels["survey"])
        self.assertEqual({1: 17, 3: 2}, dict(report.levels))
        quantitative = next(
            item for item in report.methods if item.family == "quantitative"
        )
        self.assertIn("typed_contract", quantitative.blocked_by)

    def test_production_ready_below_l4_fails_closed(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["families"]["process_tracing"][
            "declared_support_status"
        ] = "production_ready"
        report = self.validate(registry)
        self.assertTrue(
            any(
                "process_tracing" in issue
                and "production_ready" in issue
                and "L4 is required" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_placeholder_evidence_does_not_promote_to_l4(self) -> None:
        profile = _load_profile(self.registry, "process_tracing")
        profile["maturity_evidence"]["positive_case"] = {
            "asset": "evals/missing-positive.json"
        }
        profile["maturity_evidence"]["negative_case"] = {
            "asset": "evals/missing-negative.json"
        }
        profile["maturity_evidence"]["worked_example"] = {
            "asset": "examples/missing-worked-example.json"
        }
        report = self.validate(overrides={"process_tracing": profile})
        item = next(
            method for method in report.methods if method.family == "process_tracing"
        )
        self.assertEqual(3, item.level)
        self.assertIn("mvmr_examples", item.blocked_by)

    def test_profile_family_identity_mismatch_is_rejected(self) -> None:
        profile = _load_profile(self.registry, "survey")
        profile["family"] = "experiment"
        report = self.validate(overrides={"survey": profile})
        self.assertTrue(
            any(
                "family 'survey' operation profile identifies family 'experiment'" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_mvmr_operations_must_be_declared_by_the_profile(self) -> None:
        profile = _load_profile(self.registry, "qca")
        profile["minimum_viable_run"]["required_operation_kinds"].append(
            "unregistered_threshold_magic"
        )
        report = self.validate(overrides={"qca": profile})
        self.assertTrue(
            any(
                "qca" in issue and "undeclared operations" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_missing_structured_design_fields_stays_l0(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["families"]["text_as_data"]["design_fields"] = []
        report = self.validate(registry)
        item = next(
            method for method in report.methods if method.family == "text_as_data"
        )
        self.assertEqual(0, item.level)
        self.assertIn("structured_design_fields", item.blocked_by)

    def test_two_families_cannot_share_one_operation_profile_asset(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["families"]["survey"]["operation_profile_asset"] = registry[
            "families"
        ]["experiment"]["operation_profile_asset"]
        report = self.validate(registry)
        self.assertTrue(
            any("share operation profile asset" in issue for issue in report.issues),
            report.issues,
        )


if __name__ == "__main__":
    unittest.main()
