from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from avereth_core.application import protocol_compiler as compiler


def step(identifier: str, *, kind: str, preconditions: list[str], write: str) -> dict:
    return {
        "id": identifier,
        "design_id": "DSN-001",
        "run_kind": kind,
        "goal": f"execute {identifier}",
        "claim_ids": ["CLM-001"],
        "operationalization_ids": ["OPR-001"],
        "material_ids": ["MAT-001"],
        "evidence_ids": ["EVD-001"],
        "read_set": ["research_design.json"],
        "write_set": [write],
        "preconditions": [
            {"step_id": value, "required_status": "accepted"}
            for value in preconditions
        ],
        "procedure": {
            "adapter": "test-adapter",
            "operation": identifier.lower(),
            "parameters_ref": "/method_routes/0/method_fields",
        },
        "expected_artifacts": [{"id": f"ART-{identifier}", "role": "test", "path": write}],
        "acceptance_checks": [{"id": f"CHK-{identifier}", "rule": "artifact has a locator"}],
        "on_failure": [{"code": "REPRO.ENVIRONMENT_FAILED", "route": "replace-implementation"}],
        "result_disposition": {
            "support": "retain:CLM-001",
            "contradict": "narrow:CLM-001",
            "inconclusive": "human-review",
        },
    }


def design() -> dict:
    return {
        "schema_version": compiler.DESIGN_SCHEMA,
        "status": "confirmed",
        "method_routes": [{"id": "DSN-001", "family": "survey"}],
        "execution_blueprint": {
            "schema_version": "method-operation/v1",
            "steps": [
                step("STEP-001", kind="mvmr", preconditions=[], write="repro/pilot.json"),
                step("STEP-002", kind="full", preconditions=["STEP-001"], write="repro/full-a.json"),
                step("STEP-003", kind="full", preconditions=["STEP-001"], write="repro/full-b.json"),
            ],
        },
    }


def accepted_action(step_id: str, attempt: int = 1) -> dict:
    return {
        "id": f"ACT-{step_id[5:]}-{attempt}",
        "operation_id": step_id,
        "attempt": attempt,
        "status": "accepted",
    }


def execution(payload: dict, *actions: dict) -> dict:
    return {
        "schema_version": compiler.EXECUTION_SCHEMA,
        "design_sha256": compiler.canonical_digest(payload),
        "runs": [{"actions": list(actions)}],
    }


class ProtocolCompilerTests(unittest.TestCase):
    def compile(self, payload: dict, actual: dict | None = None) -> dict:
        with (
            tempfile.TemporaryDirectory() as raw,
            mock.patch.object(compiler, "_protocol_validation_issues", return_value=[]),
            mock.patch.object(compiler, "_execution_validation_issues", return_value=[]),
        ):
            return compiler.compile_protocol(Path(raw), design=payload, execution=actual)

    def test_mvmr_is_the_only_initial_action(self) -> None:
        payload = design()
        result = self.compile(payload)
        self.assertEqual("STEP-001", result["next_executable_action"])
        self.assertEqual(["STEP-001"], result["runnable_action_ids"])
        full = next(item for item in result["work_items"] if item["id"] == "STEP-002")
        self.assertIn("MVMR:DSN-001", full["blocked_by"])

    def test_accepted_mvmr_unlocks_parallel_safe_full_actions(self) -> None:
        payload = design()
        actual = execution(payload, accepted_action("STEP-001"))
        result = self.compile(payload, actual)
        self.assertEqual(["STEP-002", "STEP-003"], result["runnable_action_ids"])
        self.assertEqual([["STEP-002", "STEP-003"]], result["parallel_safe_groups"])

    def test_every_mvmr_for_design_must_be_accepted_before_full_unlocks(self) -> None:
        payload = design()
        payload["execution_blueprint"]["steps"].insert(
            1,
            step(
                "STEP-004",
                kind="mvmr",
                preconditions=["STEP-001"],
                write="repro/pilot-b.json",
            ),
        )
        result = self.compile(payload, execution(payload, accepted_action("STEP-001")))
        self.assertEqual(["STEP-004"], result["runnable_action_ids"])
        full = next(item for item in result["work_items"] if item["id"] == "STEP-002")
        self.assertIn("MVMR:DSN-001", full["blocked_by"])

    def test_support_status_is_projected_from_canonical_registry(self) -> None:
        result = self.compile(design())
        self.assertEqual(
            "experimental_method_support",
            result["method_support_by_design"]["DSN-001"],
        )

    def test_protocol_projects_isolated_researchers_for_coding(self) -> None:
        payload = design()
        payload["execution_blueprint"]["steps"][0]["procedure"]["operation"] = "content_coding"
        result = self.compile(payload)
        first = result["work_items"][0]["researcher_dispatch"]
        self.assertEqual("isolated_multi", first["mode"])
        self.assertEqual(2, first["independent_researcher_count"])
        self.assertIn("independent_coding", first["task_kinds"])
        self.assertEqual(
            first,
            result["researcher_dispatch_by_operation"]["STEP-001"],
        )

    def test_protocol_keeps_low_risk_direct_inference_audit_single(self) -> None:
        payload = design()
        first = payload["execution_blueprint"]["steps"][0]
        first["procedure"]["operation"] = "content_inference_disposition"
        first["researcher_risk"] = {
            "epistemic_fit": "single_judgment",
            "interpretive_ambiguity": "low",
            "consequence_of_error": "low",
            "codebook_maturity": "not_applicable",
            "reference_basis": "not_applicable",
            "holdout_status": "not_applicable",
            "boundary_case_load": "low",
            "inference_distance": "direct",
            "rationale": "A direct descriptive disposition has a low error consequence.",
        }
        result = self.compile(payload)
        dispatch = result["work_items"][0]["researcher_dispatch"]
        self.assertEqual("single", dispatch["mode"])
        self.assertEqual(["inference_audit"], dispatch["task_kinds"])
        self.assertTrue(
            all(
                item["method_support_status"] == "experimental_method_support"
                for item in result["work_items"]
            )
        )

    def test_read_write_conflict_splits_parallel_group(self) -> None:
        payload = design()
        payload["execution_blueprint"]["steps"][2]["read_set"].append("repro/full-a.json")
        actual = execution(payload, accepted_action("STEP-001"))
        result = self.compile(payload, actual)
        self.assertEqual([["STEP-002"], ["STEP-003"]], result["parallel_safe_groups"])

    def test_failed_action_projects_typed_route(self) -> None:
        payload = design()
        failure = {
            "id": "ACT-001-1",
            "operation_id": "STEP-001",
            "attempt": 1,
            "status": "failed",
            "failure_code": "REPRO.ENVIRONMENT_FAILED",
            "disposition_route": "replace-implementation",
        }
        result = self.compile(payload, execution(payload, failure))
        item = next(value for value in result["work_items"] if value["id"] == "STEP-001")
        self.assertEqual("replace-implementation", item["failure_route"])
        self.assertTrue(item["runnable"])

    def test_design_change_invalidates_compiled_protocol(self) -> None:
        payload = design()
        actual = execution(payload, accepted_action("STEP-001"))
        changed = copy.deepcopy(payload)
        changed["status"] = "needs-review"
        result = self.compile(changed, actual)
        self.assertTrue(result["invalidated_by_design_change"])
        self.assertFalse(result["valid"])
        self.assertEqual([], result["runnable_action_ids"])

    def test_compile_is_read_only(self) -> None:
        payload = design()
        with (
            tempfile.TemporaryDirectory() as raw,
            mock.patch.object(compiler, "_protocol_validation_issues", return_value=[]),
            mock.patch.object(compiler, "_execution_validation_issues", return_value=[]),
        ):
            base = Path(raw)
            before = list(base.rglob("*"))
            compiler.compile_protocol(base, design=payload, execution=None)
            self.assertEqual(before, list(base.rglob("*")))

    def test_canonical_validator_blocks_forged_accepted_action(self) -> None:
        empirical_scripts = Path(__file__).resolve().parents[4] / "empirical-research" / "scripts"
        if str(empirical_scripts) not in sys.path:
            sys.path.insert(0, str(empirical_scripts))
        import test_method_execution_v3 as execution_fixtures

        temporary, base, _payload_design, payload = execution_fixtures.v3_workspace()
        with temporary, mock.patch.object(
            compiler,
            "_protocol_validation_issues",
            return_value=[],
        ):
            forged = payload["runs"][0]["actions"][0]
            forged.pop("parameter_snapshot_sha256")
            forged["output_artifact_ids"] = []
            forged["check_results"] = []
            (base / "method_execution.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = compiler.compile_protocol(base)

        codes = {item["code"] for item in result["issues"]}
        self.assertIn("ME.ACTION.PARAMETERS_UNFROZEN", codes)
        self.assertIn("ME.ACTION.OUTPUT_MISSING", codes)
        self.assertIn("ME.ACTION.UNCHECKED", codes)
        self.assertFalse(result["valid"])
        self.assertEqual([], result["runnable_action_ids"])
        self.assertTrue(all(item["execution_status"] == "pending" for item in result["work_items"]))

    def test_real_scaffold_unlocks_first_mvmr_without_final_completion(self) -> None:
        empirical_scripts = Path(__file__).resolve().parents[4] / "empirical-research" / "scripts"
        if str(empirical_scripts) not in sys.path:
            sys.path.insert(0, str(empirical_scripts))
        import test_method_execution_v3 as execution_fixtures

        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            payload_design = execution_fixtures.v4_design()
            execution_fixtures.write_empty_registry(base)
            (base / "research_design.json").write_text(
                json.dumps(payload_design, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            authority = compiler._method_execution_module()
            actual = authority.scaffold_payload(payload_design)
            result = compiler.compile_protocol(
                base,
                design=payload_design,
                execution=actual,
            )

        first = payload_design["execution_blueprint"]["steps"][0]["id"]
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual(first, result["next_executable_action"])
        self.assertEqual([first], result["runnable_action_ids"])

    def test_real_partial_ledger_unlocks_only_the_next_mvmr(self) -> None:
        empirical_scripts = Path(__file__).resolve().parents[4] / "empirical-research" / "scripts"
        if str(empirical_scripts) not in sys.path:
            sys.path.insert(0, str(empirical_scripts))
        import test_method_execution_v3 as execution_fixtures

        temporary, base, payload_design, actual = execution_fixtures.v3_workspace()
        with temporary:
            run = actual["runs"][0]
            run["actions"] = [run["actions"][0]]
            run["actions"][0]["result_ids"] = []
            run["results"] = []
            run["claim_dispositions"] = []
            run["status"] = "planned"
            actual["status"] = "needs-review"
            run["minimum_viable_run"] = {
                "status": "unchecked",
                "material_id": "",
                "analysis_unit": {"id": "", "material_id": "", "unit_type": "", "locator": ""},
                "extraction_or_coding": {"kind": "", "rule": "", "artifact_id": ""},
                "action_ids": [],
                "artifact_ids": [],
                "check_result_ids": [],
                "result_ids": [],
                "claim_disposition_ids": [],
            }
            result = compiler.compile_protocol(
                base,
                design=payload_design,
                execution=actual,
            )

        second = payload_design["execution_blueprint"]["steps"][1]["id"]
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual([second], result["runnable_action_ids"])

    def test_real_accepted_mvmr_unlocks_full_only_after_all_mvmr_steps(self) -> None:
        empirical_scripts = Path(__file__).resolve().parents[4] / "empirical-research" / "scripts"
        if str(empirical_scripts) not in sys.path:
            sys.path.insert(0, str(empirical_scripts))
        import test_method_execution_v3 as execution_fixtures

        temporary, base, payload_design, actual = execution_fixtures.v3_workspace()
        with temporary:
            result = compiler.compile_protocol(
                base,
                design=payload_design,
                execution=actual,
            )

        first_full = next(
            step["id"]
            for step in payload_design["execution_blueprint"]["steps"]
            if step["run_kind"] == "full"
        )
        self.assertTrue(result["valid"], result["issues"])
        self.assertEqual([first_full], result["runnable_action_ids"])

    def test_malformed_accepted_mvmr_never_unlocks_full(self) -> None:
        empirical_scripts = Path(__file__).resolve().parents[4] / "empirical-research" / "scripts"
        if str(empirical_scripts) not in sys.path:
            sys.path.insert(0, str(empirical_scripts))
        import test_method_execution_v3 as execution_fixtures

        temporary, base, payload_design, actual = execution_fixtures.v3_workspace()
        with temporary:
            actual["runs"][0]["minimum_viable_run"]["analysis_unit"][
                "locator"
            ] = "artifact:ART-001#text:line=999999"
            result = compiler.compile_protocol(
                base,
                design=payload_design,
                execution=actual,
            )

        self.assertFalse(result["valid"])
        self.assertEqual([], result["runnable_action_ids"])
        self.assertIn(
            "ME.MVMR.UNIT_LOCATOR_INVALID",
            {item["code"] for item in result["issues"]},
        )


if __name__ == "__main__":
    unittest.main()
