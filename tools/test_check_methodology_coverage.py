#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from check_methodology_coverage import (  # noqa: E402
    DEFAULT_CASES,
    DEFAULT_REGISTRY,
    check,
    validate_coverage,
)


def _load(relative: Path) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class MethodologyCoverageCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = _load(DEFAULT_REGISTRY)
        self.manifest = _load(DEFAULT_CASES)

    def validate(self, registry=None, manifest=None):
        return validate_coverage(
            ROOT,
            registry if registry is not None else self.registry,
            manifest if manifest is not None else self.manifest,
        )

    def test_checked_in_registry_has_executable_semantic_coverage(self) -> None:
        report = check(ROOT)
        self.assertEqual((), report.issues)
        self.assertEqual(19, len(report.executable_families))
        self.assertEqual(136, report.instantiated_case_count)

    def test_new_executable_registry_family_fails_closed(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["families"]["new_executable_family"] = copy.deepcopy(
            registry["families"]["conceptual"]
        )
        registry["claim_capabilities"]["new_executable_family"] = ["descriptive"]
        report = self.validate(registry=registry)
        self.assertIn(
            "executable registry family lacks coverage: new_executable_family",
            report.issues,
        )

    def test_new_core_contract_requires_structured_executable_declaration(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["method_contracts"]["new-contract/v1"] = copy.deepcopy(
            registry["method_contracts"]["causal-design/v1"]
        )
        registry["families"]["quantitative"]["method_contract_profiles"].append(
            "new-contract/v1"
        )
        report = self.validate(registry=registry)
        self.assertIn(
            "typed method profile lacks structured executable coverage: new-contract/v1",
            report.issues,
        )

    def test_two_family_error_labels_cannot_hide_the_same_failure(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        cases = [
            item
            for item in manifest["family_error_cases"]
            if item["family"] == "survey"
        ]
        first, duplicate = cases
        duplicate["failure_mode"] = first["failure_mode"]
        duplicate["mutation"] = copy.deepcopy(first["mutation"])
        duplicate["expected"] = copy.deepcopy(first["expected"])
        report = self.validate(manifest=manifest)
        for identity in ("failure_mode", "mutation", "expected_codes"):
            self.assertTrue(
                any(
                    "family-specific error cases are not distinct" in issue
                    and identity in issue
                    for issue in report.issues
                ),
                (identity, report.issues),
            )

    def test_generic_templates_do_not_satisfy_family_error_minimum(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        manifest["family_error_cases"] = [
            case
            for case in manifest["family_error_cases"]
            if case["family"] != "survey"
        ]
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any(
                "survey" in issue
                and "0 non-generic family-specific error cases" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_family_case_code_must_belong_to_runtime_semantic_validator(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        case = next(
            item
            for item in manifest["family_error_cases"]
            if item["family"] == "survey"
        )
        case["expected"]["codes"] = ["ME.TEXT_AS_DATA.SENTIMENT_AS_STANCE"]
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any(
                case["id"] in issue and "outside 'survey'" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_family_case_applicability_must_be_exact(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        case = next(
            item
            for item in manifest["family_error_cases"]
            if item["family"] == "qca"
        )
        case["applicability"]["families"].append("quantitative")
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any(case["id"] in issue and "applicability" in issue for issue in report.issues),
            report.issues,
        )

    def test_family_case_cannot_mutate_another_family_field(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        case = next(
            item
            for item in manifest["family_error_cases"]
            if item["family"] == "normative"
        )
        case["mutation"]["target"] = "runs[].method_fields.split_audit"
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any(
                case["id"] in issue and "field not owned by 'normative'" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_inference_case_must_attempt_a_registry_disallowed_claim(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        quantitative = next(
            row for row in manifest["families"] if row["family"] == "quantitative"
        )
        quantitative["inference_overreach"]["attempted_claim_type"] = "causal_effect"
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any(
                "quantitative" in issue
                and "is not an overreach" in issue
                and "causal_effect" in issue
                for issue in report.issues
            ),
            report.issues,
        )

    def test_case_template_must_resolve_to_a_declared_source_variant(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        templates = {item["id"]: item for item in manifest["case_templates"]}
        templates["repetitive-content"]["source_variant"] = "invented-error-label"
        report = self.validate(manifest=manifest)
        self.assertTrue(
            any("invented-error-label" in issue and "not declared" in issue for issue in report.issues),
            report.issues,
        )

    def test_boundary_role_cannot_be_omitted(self) -> None:
        manifest = copy.deepcopy(self.manifest)
        survey = next(row for row in manifest["families"] if row["family"] == "survey")
        survey["case_templates"].remove("legal-non-applicability")
        report = self.validate(manifest=manifest)
        self.assertIn(
            "family 'survey' lacks required semantic roles: boundary",
            report.issues,
        )

    def test_migration_only_registry_family_is_not_treated_as_executable(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["families"]["retired_migration_route"] = {
            "migration_only": True,
            "design_fields": ["legacy_family"],
        }
        report = self.validate(registry=registry)
        self.assertNotIn("retired_migration_route", report.executable_families)
        self.assertFalse(
            any("retired_migration_route" in issue for issue in report.issues),
            report.issues,
        )


if __name__ == "__main__":
    unittest.main()
