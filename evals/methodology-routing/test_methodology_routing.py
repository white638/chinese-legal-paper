#!/usr/bin/env python3
"""Execute the registry-wide semantic cases declared in cases.json."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUPPORT_PATH = (
    REPO
    / "skills"
    / "empirical-research"
    / "scripts"
    / "test_method_execution.py"
)


def _load_support():
    spec = importlib.util.spec_from_file_location(
        "methodology_routing_execution_support",
        SUPPORT_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load fixture materializer: {SUPPORT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SUPPORT = _load_support()
MANIFEST: dict[str, Any] = json.loads(
    (HERE / "cases.json").read_text(encoding="utf-8")
)
TEMPLATES = {item["id"]: item for item in MANIFEST["case_templates"]}
FAMILY_ERROR_CASES = MANIFEST["family_error_cases"]
REGISTRY = SUPPORT.method_execution.load_registry()


def _result_codes(result) -> set[str]:
    return {issue.code for issue in result.errors}


def _unsupported_claim_workspace(family: str, attempted_claim_type: str):
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    design = SUPPORT.confirmed_design(family)
    design["claims"][0]["type"] = attempted_claim_type
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    execution = SUPPORT.complete_execution(base, design)
    return temporary, base, design, execution


def _apply_mutation(
    family: str,
    family_row: dict[str, Any],
    template: dict[str, Any],
    design: dict[str, Any],
    execution: dict[str, Any],
    base: Path,
) -> None:
    mutation = template["mutation"]
    operator = mutation["operator"]
    if operator == "none":
        return
    run = execution["runs"][0]
    if operator == "replace-actions":
        run["actions"] = copy.deepcopy(mutation["value"])
        return
    if operator == "remove-first-required-execution-field":
        required = REGISTRY["families"][family]["execution_fields"][0]
        run["method_fields"].pop(required)
        return
    if operator == "withdraw-route-not-applicable":
        run["status"] = "not-applicable"
        run["not_applicable_reason"] = (
            "路线因已登记的材料不可得而合法终止，相关主张已经撤回。"
        )
        run["method_fields"] = {}
        run["artifacts"] = []
        run["results"] = []
        run["software_environment_ids"] = []
        design["claims"][0]["status"] = "withdrawn"
        execution["design_sha256"] = SUPPORT.method_execution._canonical_digest(design)
        (base / "research_design.json").write_text(
            json.dumps(design, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return
    if operator == "replace-result-claim-type":
        attempted = family_row["inference_overreach"]["attempted_claim_type"]
        if design["claims"][0]["type"] != attempted:
            raise AssertionError("unsupported-claim workspace was not materialized correctly")
        if run["results"][0]["type"] != attempted:
            raise AssertionError("execution result does not preserve the attempted claim type")
        return
    raise AssertionError(f"Unsupported methodology mutation operator: {operator}")


def _apply_family_error_mutation(case: dict[str, Any], execution: dict[str, Any]) -> None:
    mutation = case["mutation"]
    if mutation.get("operator") != "replace-method-field":
        raise AssertionError(
            f"Unsupported family-specific mutation operator: {mutation.get('operator')}"
        )
    target = mutation.get("target", "")
    prefix = "runs[].method_fields."
    if not isinstance(target, str) or not target.startswith(prefix):
        raise AssertionError(f"Family-specific mutation target is invalid: {target!r}")
    field_name = target.removeprefix(prefix)
    execution["runs"][0]["method_fields"][field_name] = copy.deepcopy(
        mutation["value"]
    )


class MethodologyRoutingEvalTests(unittest.TestCase):
    def test_manifest_cases_execute(self) -> None:
        """Materialize every family/template pair and assert validator outcomes."""

        for family_row in MANIFEST["families"]:
            family = family_row["family"]
            for template_id in family_row["case_templates"]:
                template = TEMPLATES[template_id]
                case_id = f"{family}:{template_id}"
                if template["role"] == "inference-overreach":
                    temporary, base, design, execution = _unsupported_claim_workspace(
                        family,
                        family_row["inference_overreach"]["attempted_claim_type"],
                    )
                else:
                    temporary, base, design, execution = SUPPORT.workspace(family)
                with self.subTest(case=case_id), temporary:
                    _apply_mutation(
                        family,
                        family_row,
                        template,
                        design,
                        execution,
                        base,
                    )
                    result = SUPPORT.method_execution.validate_payload(base, execution)
                    expected = template["expected"]
                    self.assertEqual(expected["status"], result.status, result.issues)
                    self.assertLessEqual(set(expected["codes"]), _result_codes(result))

    def test_family_specific_error_cases_execute(self) -> None:
        """Execute every non-generic method-family mutation against the runtime validator."""

        for case in FAMILY_ERROR_CASES:
            family = case["family"]
            temporary, base, _, execution = SUPPORT.workspace(family)
            with self.subTest(case=case["id"]), temporary:
                _apply_family_error_mutation(case, execution)
                result = SUPPORT.method_execution.validate_payload(base, execution)
                expected = case["expected"]
                self.assertEqual(expected["status"], result.status, result.issues)
                self.assertLessEqual(set(expected["codes"]), _result_codes(result))


if __name__ == "__main__":
    unittest.main()
