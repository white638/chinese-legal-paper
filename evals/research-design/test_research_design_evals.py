#!/usr/bin/env python3
"""Executable fixture harness for the CNKI-Paper v3 research-design evaluator."""

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
REPO_ROOT = HERE.parents[1]
SUPPORT_PATH = REPO_ROOT / "skills" / "cnki-paper" / "scripts" / "test_research_design.py"
V3_SUPPORT_PATH = REPO_ROOT / "skills" / "cnki-paper" / "scripts" / "test_research_design_v3.py"


def _load_support():
    spec = importlib.util.spec_from_file_location("research_design_eval_support", SUPPORT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load fixture materializer: {SUPPORT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


SUPPORT = _load_support()
CHECKER = SUPPORT.research_design


def _load_v3_support():
    spec = importlib.util.spec_from_file_location("research_design_v3_eval_support", V3_SUPPORT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load v3 fixture materializer: {V3_SUPPORT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


V3_SUPPORT = _load_v3_support()


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((HERE / "cases" / name).read_text(encoding="utf-8"))


POSITIVE = _load_fixture("positive.json")
KEYWORD_GAMING = _load_fixture("keyword-gaming.json")
MUTATIONS = _load_fixture("mutations.json")


def _decode_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_pointer(document: Any, pointer: str) -> tuple[Any, str | int]:
    if not pointer.startswith("/") or pointer == "/":
        raise AssertionError(f"Fixture paths must be non-root JSON Pointers: {pointer!r}")
    tokens = [_decode_pointer_token(token) for token in pointer[1:].split("/")]
    current = document
    for token in tokens[:-1]:
        if isinstance(current, list):
            current = current[int(token)]
        else:
            current = current[token]
    final: str | int = int(tokens[-1]) if isinstance(current, list) else tokens[-1]
    return current, final


def _apply_operation(payload: dict[str, Any], operation: dict[str, Any]) -> None:
    assert operation["op"] == "replace", operation
    parent, key = _resolve_pointer(payload, operation["path"])
    actual = parent[key]
    assert actual == operation["from"], (
        f"{operation['path']} base drifted: expected {operation['from']!r}, got {actual!r}"
    )
    parent[key] = copy.deepcopy(operation["value"])


def _materialize(workspace: Path, fixture_set: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    SUPPORT.write_registry(workspace, *fixture_set["registry_source_ids"])
    payload = SUPPORT.base_contract(**case["base_contract"])
    if payload["design"]["empirical"]:
        SUPPORT.create_empirical_artifacts(workspace, payload)
    for entry in case.get("workspace_files", []):
        path = workspace / entry["path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry["content"], encoding="utf-8")
    for operation in case["operations"]:
        _apply_operation(payload, operation)
    (workspace / "research_design.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def _error_codes(result) -> set[str]:
    return {issue.code for issue in result.errors}


def _case_id(case: dict[str, Any]) -> str:
    return case["id"]


class ResearchDesignEvalTests(unittest.TestCase):
    def test_legacy_fixture_sets_remain_explicit_v1_regressions(self) -> None:
        expected = "skills/cnki-paper/scripts/test_research_design.py::base_contract"
        for fixture_set in (POSITIVE, KEYWORD_GAMING, MUTATIONS):
            with self.subTest(schema=fixture_set["schema"]):
                self.assertEqual(
                    "cnki-research-design-executable-fixtures/v1",
                    fixture_set["schema"],
                )
                self.assertEqual(expected, fixture_set["materializer"])
                self.assertTrue(fixture_set["registry_source_ids"])
                self.assertTrue(fixture_set["cases"])

    def test_current_v3_materializer_and_typed_routes_are_live(self) -> None:
        for family in ("quantitative", "process_tracing", "text_as_data", "normative"):
            with self.subTest(family=family):
                payload = V3_SUPPORT.confirmed_design(family)
                result = V3_SUPPORT.validate(payload)
                self.assertEqual("cnki-research-design/v3", payload["schema_version"])
                self.assertEqual([], result.errors, [issue.code for issue in result.issues])
                route = payload["method_routes"][0]
                if family in {"process_tracing", "text_as_data"}:
                    self.assertTrue(route["method_contract_schema"])
                    self.assertTrue(route["method_contract"])

    def test_positive_fixtures_pass(self) -> None:
        for case in POSITIVE["cases"]:
            with self.subTest(case=_case_id(case)), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                payload = _materialize(workspace, POSITIVE, case)
                self.assertEqual(CHECKER.SCHEMA_VERSION, payload["schema_version"])
                self.assertLessEqual(
                    {"research_question", "knowledge_state", "epistemic_position", "design"},
                    payload.keys(),
                )
                self.assertLessEqual(
                    {"concepts", "claims", "evidence", "alternatives", "falsification_conditions"},
                    payload.keys(),
                )
                result = CHECKER.validate_payload(workspace, payload, stage=case["stage"])
                self.assertEqual(case["expected_status"], result.status, result.issues)
                self.assertEqual("PASS", result.status)
                self.assertEqual([], result.errors)

    def test_keyword_gaming_fixtures_are_blocked(self) -> None:
        for case in KEYWORD_GAMING["cases"]:
            with self.subTest(case=_case_id(case)), tempfile.TemporaryDirectory() as tmp:
                workspace = Path(tmp)
                payload = _materialize(workspace, KEYWORD_GAMING, case)
                result = CHECKER.validate_payload(workspace, payload, stage=case["stage"])
                codes = _error_codes(result)
                self.assertEqual(case["expected_status"], result.status)
                self.assertEqual("FAIL", result.status)
                self.assertLessEqual(set(case["expected_codes"]), codes)

    def test_single_condition_mutations_hit_expected_codes(self) -> None:
        for case in MUTATIONS["cases"]:
            with self.subTest(case=_case_id(case)), tempfile.TemporaryDirectory() as tmp:
                self.assertEqual(1, len(case["operations"]))
                workspace = Path(tmp)
                payload = _materialize(workspace, MUTATIONS, case)
                result = CHECKER.validate_payload(workspace, payload, stage=case["stage"])
                codes = _error_codes(result)
                self.assertEqual("FAIL", result.status)
                self.assertIn(case["expected_code"], codes)


if __name__ == "__main__":
    unittest.main()
