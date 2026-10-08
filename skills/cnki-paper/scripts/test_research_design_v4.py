#!/usr/bin/env python3
"""Contract, migration, and path tests for cnki-research-design/v4."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


research_design = load_module("research_design_v4_tests", HERE / "research_design.py")
v2 = research_design._v2_module()
v3 = research_design._v3_module()
v4 = research_design._v4_module()
v3_tests = load_module("research_design_v3_fixture", HERE / "test_research_design_v3.py")


def confirmed_v4(family: str = "process_tracing") -> dict:
    payload = copy.deepcopy(v3_tests.confirmed_design(family))
    payload["schema_version"] = v4.SCHEMA_VERSION
    payload["operationalizations"] = v4._operationalizations_for_payload(payload)
    payload["execution_blueprint"] = v4._blueprint_for_payload(payload)
    payload = v3_tests._replace_review(payload)
    for operationalization in payload["operationalizations"]:
        operationalization["material_ids"] = ["MAT-001"]
    for step in payload["execution_blueprint"]["steps"]:
        step["material_ids"] = ["MAT-001"]
    return payload


def validate(payload: dict):
    result = research_design.ValidationResult()
    v4.validate_payload(
        Path("."),
        payload,
        stage="design",
        result=result,
        v2=v2,
        v3=v3,
    )
    return result


class ResearchDesignV4Tests(unittest.TestCase):
    def test_v4_refuses_a_legacy_registry_without_operation_contracts(self) -> None:
        with self.assertRaisesRegex(
            v4.V4ContractError, "cnki-method-adapter-registry/v3"
        ):
            v4.operation_profile(
                "survey",
                {
                    "schema_version": "cnki-method-adapter-registry/v2",
                    "families": {"survey": {}},
                },
            )

    def test_every_registered_family_compiles_a_complete_v4_blueprint(self) -> None:
        families = sorted(set(v2.load_adapter_registry()["families"]) - {"unresolved"})
        self.assertEqual(19, len(families))
        for family in families:
            with self.subTest(family=family):
                result = validate(confirmed_v4(family))
                self.assertEqual(
                    [],
                    result.errors,
                    [(item.code, item.path) for item in result.errors],
                )

    def test_complete_claim_to_action_path_passes(self) -> None:
        result = validate(confirmed_v4())
        self.assertEqual([], result.errors, [(item.code, item.path) for item in result.errors])

    def test_every_active_claim_needs_operationalization(self) -> None:
        payload = confirmed_v4()
        payload["operationalizations"] = []
        result = validate(payload)
        codes = {item.code for item in result.errors}
        self.assertIn("RD.OPR.MISSING", codes)
        self.assertIn("RD.OPR.CLAIM_UNCOVERED", codes)

    def test_free_text_cannot_replace_structured_step(self) -> None:
        payload = confirmed_v4()
        payload["execution_blueprint"]["steps"][0] = "run the pilot"
        result = validate(payload)
        self.assertIn("RD.PROTOCOL.STEP_INVALID", {item.code for item in result.errors})

    def test_full_execution_must_depend_on_mvmr(self) -> None:
        payload = confirmed_v4()
        full = next(
            item
            for item in payload["execution_blueprint"]["steps"]
            if item["run_kind"] == "full"
        )
        full["preconditions"] = []
        result = validate(payload)
        self.assertIn(
            "RD.PROTOCOL.MVMR_NOT_PRECONDITION",
            {item.code for item in result.errors},
        )

    def test_generated_blueprints_finish_every_mvmr_before_full_execution(self) -> None:
        payload = confirmed_v4("survey")
        seen_full = False
        for step in payload["execution_blueprint"]["steps"]:
            if step["run_kind"] == "full":
                seen_full = True
            else:
                self.assertFalse(seen_full, step["id"])
            for artifact in step["expected_artifacts"]:
                self.assertRegex(artifact["id"], r"^[A-Z][A-Z0-9_-]{1,31}$")

    def test_mvmr_cannot_depend_on_a_full_run_operation(self) -> None:
        payload = confirmed_v4("survey")
        mvmr = [
            item
            for item in payload["execution_blueprint"]["steps"]
            if item["run_kind"] == "mvmr"
        ]
        full = next(
            item
            for item in payload["execution_blueprint"]["steps"]
            if item["run_kind"] == "full"
        )
        mvmr[-1]["preconditions"] = [
            {"step_id": full["id"], "required_status": "accepted"}
        ]
        result = validate(payload)
        self.assertIn("RD.PROTOCOL.MVMR_AFTER_FULL", {item.code for item in result.errors})

    def test_failure_namespace_and_route_are_typed(self) -> None:
        payload = confirmed_v4()
        payload["execution_blueprint"]["steps"][0]["on_failure"] = [
            {"code": "UNKNOWN.FAIL", "route": "make-something-up"}
        ]
        result = validate(payload)
        codes = {item.code for item in result.errors}
        self.assertIn("RD.PROTOCOL.FAILURE_CODE_UNKNOWN", codes)
        self.assertIn("RD.PROTOCOL.FAILURE_ROUTE_INVALID", codes)

    def test_invalid_researcher_risk_profile_fails_design(self) -> None:
        payload = confirmed_v4("content_analysis")
        payload["execution_blueprint"]["steps"][0]["researcher_risk"][
            "interpretive_ambiguity"
        ] = "extreme"
        result = validate(payload)
        self.assertIn(
            "RD.RESEARCHER_RISK.INVALID",
            {item.code for item in result.errors},
        )

    def test_v3_migration_preserves_ids_but_never_accepts_protocol(self) -> None:
        legacy = v3_tests.confirmed_design("survey")
        legacy["research_questions"][0]["id"] = "RQ-LOCKED"
        migrated = v4.migrate_payload(legacy, v2=v2, v3=v3)
        self.assertEqual(v4.SCHEMA_VERSION, migrated["schema_version"])
        self.assertEqual("needs-review", migrated["status"])
        self.assertEqual("RQ-LOCKED", migrated["research_questions"][0]["id"])
        self.assertTrue(
            all(
                str(item["goal"]).startswith("needs-review")
                for item in migrated["execution_blueprint"]["steps"]
            )
        )

    def test_v4_render_adds_two_generated_protocol_views(self) -> None:
        payload = confirmed_v4("comparative")
        with tempfile.TemporaryDirectory() as raw:
            written = v4.render_views(
                Path(raw),
                payload,
                allow_unmanaged_replace=False,
                v2=v2,
                v3=v3,
            )
            self.assertEqual(8, len(written))
            for name in ("operationalization_matrix.md", "execution_protocol.md"):
                text = (Path(raw) / name).read_text(encoding="utf-8")
                self.assertIn(v4.GENERATED_MARKER, text)

    def test_v4_schema_and_default_template(self) -> None:
        schema = json.loads(v4.SCHEMA_ASSET_PATH.read_text(encoding="utf-8"))
        self.assertEqual(v4.SCHEMA_VERSION, schema["properties"]["schema_version"]["const"])
        template = v4.template_payload("normative", v2, v3)
        self.assertEqual(v4.SCHEMA_VERSION, template["schema_version"])
        self.assertTrue(template["operationalizations"])
        self.assertTrue(template["execution_blueprint"]["steps"])


if __name__ == "__main__":
    unittest.main()
