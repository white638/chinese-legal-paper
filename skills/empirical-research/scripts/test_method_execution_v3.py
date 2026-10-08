#!/usr/bin/env python3
"""Focused regression tests for cnki-method-execution/v3 provenance gates."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import test_method_execution as fixtures


method_execution = fixtures.method_execution
CNKI_SCRIPTS = Path(__file__).resolve().parents[2] / "cnki-paper" / "scripts"
if str(CNKI_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(CNKI_SCRIPTS))
import test_research_design_v4 as v4_fixtures


def v4_design() -> dict:
    design = copy.deepcopy(v4_fixtures.confirmed_v4("survey"))
    for operationalization in design["operationalizations"]:
        operationalization["material_ids"] = ["MAT-001"]
    for step in design["execution_blueprint"]["steps"]:
        step["material_ids"] = ["MAT-001"]
        step["read_set"] = ["research_design.json", "materials/MAT-001.txt"]
    return design


def write_empty_registry(base: Path) -> None:
    path = base / "reference_materials" / "literature_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"schema_version": "cnki-acquisition/v1", "sources": []},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def v3_workspace(*, include_full: bool = False):
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    legacy_design = fixtures.confirmed_design("survey")
    (base / "research_design.json").write_text(
        json.dumps(legacy_design, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    legacy_execution = fixtures.complete_execution(base, legacy_design)
    design = v4_design()
    write_empty_registry(base)
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    payload = copy.deepcopy(method_execution.migrate_v2_payload(design, legacy_execution))
    payload["status"] = "complete"
    run = payload["runs"][0]
    route = design["method_routes"][0]
    run["design_route_sha256"] = method_execution._canonical_digest(route)
    run["inference_ceiling_observed"] = route["inference_ceiling"]
    run["prohibited_inferences_observed"] = route["prohibited_inferences"]
    run["status"] = "completed" if include_full else "qualified"
    run["migration_status"] = "reviewed"
    result_record = run["results"][0]
    steps = [
        step
        for step in design["execution_blueprint"]["steps"]
        if step["run_kind"] == "mvmr" or include_full
    ]
    actions: list[dict] = []
    mvmr_action_ids: list[str] = []
    mvmr_artifact_ids: list[str] = []
    mvmr_check_ids: list[str] = []
    for index, step in enumerate(steps, start=1):
        artifact_id = "ART-001" if index == 1 else f"ART-ACT-{index:03d}"
        if index > 1:
            artifact_path = f"artifacts/action-{index:03d}.txt"
            local = base / artifact_path
            local.parent.mkdir(parents=True, exist_ok=True)
            content = f"unit-{index}: accepted {step['id']}\n"
            local.write_text(content, encoding="utf-8")
            run["artifacts"].append(
                {
                    "id": artifact_id,
                    "path": artifact_path,
                    "sha256": hashlib.sha256(local.read_bytes()).hexdigest(),
                    "role": step["expected_artifacts"][0]["role"],
                }
            )
        action_id = f"ACT-{index:03d}"
        check_id = f"CHK-ACT-{index:03d}"
        parameter_snapshot = {
            "format": method_execution.PARAMETER_SNAPSHOT_FORMAT,
            "kind": "parameters",
            "content": {
                "operation_id": step["id"],
                "run_kind": step["run_kind"],
                "procedure": copy.deepcopy(step["procedure"]),
            },
        }
        action = {
            "id": action_id,
            "operation_id": step["id"],
            "attempt": 1,
            "run_kind": step["run_kind"],
            "status": "accepted",
            "started_from_design_sha256": payload["design_sha256"],
            "parameter_snapshot": parameter_snapshot,
            "parameter_snapshot_sha256": method_execution._canonical_digest(
                parameter_snapshot
            ),
            "input_artifact_ids": [],
            "output_artifact_ids": [artifact_id],
            "software_environment_id": "ENV-001",
            "check_results": [
                {
                    "id": check_id,
                    "rule": step["acceptance_checks"][0]["rule"],
                    "status": "pass",
                    "diagnostic": "真实材料、分析单位、工件散列和登记步骤均可复核。",
                    "artifact_ids": [artifact_id],
                }
            ],
            "failure_code": "",
            "disposition_route": "continue",
            "deviation_id": "",
            "result_ids": ["RES-001"] if index == 1 else [],
        }
        actions.append(action)
        if step["run_kind"] == "mvmr":
            mvmr_action_ids.append(action_id)
            mvmr_artifact_ids.append(artifact_id)
            mvmr_check_ids.append(check_id)
    run["actions"] = actions
    result_record["action_ids"] = [actions[0]["id"]]
    claim_id = run["claim_ids"][0]
    run["claim_dispositions"] = [
        {
            "id": "DSP-001",
            "claim_id": claim_id,
            "result_ids": ["RES-001"],
            "status": "retained",
            "reason": "真实 MVMR 结果支持在登记边界内保留主张。",
            "route": "continue",
        }
    ]
    run["minimum_viable_run"] = {
        "status": "accepted",
        "material_id": "MAT-001",
        "analysis_unit": {
            "id": "UNIT-001",
            "material_id": "MAT-001",
            "unit_type": "survey response",
            "locator": "artifact:ART-001#text:line=1",
        },
        "extraction_or_coding": {
            "kind": "coding",
            "rule": "按冻结的 survey 编码规则提取一个真实响应单位。",
            "artifact_id": "ART-001",
        },
        "action_ids": mvmr_action_ids,
        "artifact_ids": mvmr_artifact_ids,
        "check_result_ids": mvmr_check_ids,
        "result_ids": ["RES-001"],
        "claim_disposition_ids": ["DSP-001"],
    }
    material_path = base / "materials" / "MAT-001.txt"
    material_path.parent.mkdir(parents=True, exist_ok=True)
    material_content = "MAT-001 source response with a stable acquisition identity.\n"
    material_path.write_text(material_content, encoding="utf-8")
    payload["material_realizations"] = [
        {
            "material_id": "MAT-001",
            "status": "REALIZED",
            "path": "materials/MAT-001.txt",
            "sha256": hashlib.sha256(material_path.read_bytes()).hexdigest(),
            "artifact_ids": mvmr_artifact_ids,
        }
    ]
    return temporary, base, design, payload


class MethodExecutionV3Tests(unittest.TestCase):
    def test_contribution_uses_real_accepted_execution_and_detects_artifact_drift(self) -> None:
        import problem_orientation_check
        from test_problem_orientation_check import write_knowledge_fixture

        prior = "Existing evidence suggests a relationship across all observed contexts."
        posterior = "Observed variation restricts that relationship to the documented scope."
        baseline = {"origin": "retrospective", "judgement": prior, "source_refs": ["CNKI-R003"]}
        prepared_design = v4_design()
        prepared_design["knowledge_baseline"] = baseline
        with mock.patch(f"{__name__}.v4_design", return_value=prepared_design):
            temporary, base, design, execution = v3_workspace(include_full=True)
        with temporary:
            write_knowledge_fixture(base, prior, posterior)
            update = json.loads((base / "method_execution.json").read_text(encoding="utf-8"))["knowledge_update"]
            update["claim_ids"] = execution["runs"][0]["claim_ids"]
            execution["knowledge_update"] = update
            (base / "research_design.json").write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
            (base / "method_execution.json").write_text(json.dumps(execution, ensure_ascii=False), encoding="utf-8")
            values = {"reader prior": prior, "reader posterior": posterior}
            self.assertEqual([], problem_orientation_check.knowledge_update_issues(base, values))
            artifact = execution["runs"][0]["artifacts"][0]
            (base / artifact["path"]).write_text("changed execution content", encoding="utf-8")
            self.assertTrue(any("method execution is not accepted" in item for item in problem_orientation_check.knowledge_update_issues(base, values)))

    def test_every_registered_family_scaffold_is_incrementally_valid(self) -> None:
        families = sorted(
            set(v4_fixtures.v2.load_adapter_registry()["families"])
            - {"unresolved"}
        )
        self.assertEqual(19, len(families))
        for family in families:
            with self.subTest(family=family), tempfile.TemporaryDirectory() as raw:
                base = Path(raw)
                design = copy.deepcopy(v4_fixtures.confirmed_v4(family))
                write_empty_registry(base)
                (base / "research_design.json").write_text(
                    json.dumps(design, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                payload = method_execution.scaffold_payload(design)
                validation = method_execution.validate_incremental_payload(base, payload)
                self.assertEqual(
                    [],
                    validation.errors,
                    [(item.code, item.path) for item in validation.errors],
                )

    def test_valid_v3_binds_real_mvmr_to_accepted_action_and_result(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            validation = method_execution.validate_payload(base, payload)
            self.assertEqual([], validation.errors, [(item.code, item.path) for item in validation.errors])

    def test_canonical_execution_gate_enforces_risk_routed_collaboration(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        forced = {
            "schema_version": "avereth-researcher-dispatch-decision/v1",
            "mode": "isolated_multi",
        }
        with temporary, mock.patch.object(
            method_execution.researcher_dispatch,
            "compile_dispatch_decision",
            return_value=forced,
        ):
            validation = method_execution.validate_payload(base, payload)
        self.assertIn(
            "ME.RESEARCHER.COLLABORATION_REQUIRED",
            {item.code for item in validation.errors},
        )

    def test_incremental_validation_keeps_present_action_errors(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["actions"][0].pop("parameter_snapshot_sha256")
            validation = method_execution.validate_incremental_payload(base, payload)
            self.assertIn(
                "ME.ACTION.FIELD_MISSING",
                {item.code for item in validation.errors},
            )

    def test_parameter_snapshot_content_is_bound_to_declared_hash(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            action = payload["runs"][0]["actions"][0]
            action["parameter_snapshot"]["content"]["operation_id"] = (
                "STEP-FORGED"
            )
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("ME.ACTION.PARAMETER_SNAPSHOT_HASH_MISMATCH", codes)

    def test_parameter_snapshot_schema_and_custom_validator_are_parity_locked(self) -> None:
        schema = json.loads(
            method_execution.SCHEMA_ASSET_PATH_V3.read_text(encoding="utf-8")
        )
        action_schema = schema["$defs"]["action"]
        snapshot_schema = schema["$defs"]["parameterSnapshot"]
        self.assertIn("parameter_snapshot", action_schema["required"])
        self.assertEqual(
            {"$ref": "#/$defs/parameterSnapshot"},
            action_schema["properties"]["parameter_snapshot"],
        )
        self.assertEqual(
            {"format", "kind", "content"}, set(snapshot_schema["required"])
        )
        self.assertEqual(
            method_execution.PARAMETER_SNAPSHOT_FORMAT,
            snapshot_schema["properties"]["format"]["const"],
        )
        self.assertEqual(
            method_execution.PARAMETER_SNAPSHOT_KINDS,
            set(snapshot_schema["properties"]["kind"]["enum"]),
        )
        self.assertEqual(
            {"type": "object", "minProperties": 1},
            snapshot_schema["properties"]["content"],
        )
        self.assertFalse(snapshot_schema["additionalProperties"])

        mutations = (
            lambda action: action.pop("parameter_snapshot"),
            lambda action: action.__setitem__(
                "parameter_snapshot",
                {
                    "format": "unversioned-json",
                    "kind": "parameters",
                    "content": {"operation_id": action["operation_id"]},
                },
            ),
            lambda action: action.__setitem__(
                "parameter_snapshot",
                {
                    "format": method_execution.PARAMETER_SNAPSHOT_FORMAT,
                    "kind": "parameters",
                    "content": {},
                },
            ),
            lambda action: action["parameter_snapshot"].__setitem__(
                "unhashed_note", "must not be accepted"
            ),
            lambda action: action["parameter_snapshot"]["content"].__setitem__(
                "non_finite", float("nan")
            ),
        )
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                temporary, base, _design, payload = v3_workspace()
                with temporary:
                    mutate(payload["runs"][0]["actions"][0])
                    codes = {
                        item.code
                        for item in method_execution.validate_payload(
                            base, payload
                        ).errors
                    }
                    self.assertIn("ME.ACTION.PARAMETER_SNAPSHOT_INVALID", codes)

    def test_incremental_validation_does_not_defer_accepted_mvmr_locator_error(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["minimum_viable_run"]["analysis_unit"][
                "locator"
            ] = "artifact:ART-001#text:line=999999"
            validation = method_execution.validate_incremental_payload(base, payload)
            self.assertIn(
                "ME.MVMR.UNIT_LOCATOR_INVALID",
                {item.code for item in validation.errors},
            )

    def test_mvmr_requires_real_material_hash_and_declared_lineage(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            realization = payload["material_realizations"][0]
            realization["sha256"] = "0" * 64
            realization["artifact_ids"] = []
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("ME.MATERIAL.HASH_CHANGED", codes)
            self.assertIn("ME.MVMR.MATERIAL_LINEAGE_BROKEN", codes)

    def test_completed_run_requires_accepted_actions_for_every_blueprint_step(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["status"] = "completed"
            validation = method_execution.validate_payload(base, payload)
            codes = {item.code for item in validation.errors}
            self.assertIn("ME.ACTION.COMPLETED_ROUTE_INCOMPLETE", codes)

    def test_qualified_run_may_stop_after_an_accepted_mvmr(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            self.assertEqual("qualified", payload["runs"][0]["status"])
            validation = method_execution.validate_payload(base, payload)
            self.assertEqual([], validation.errors, [(item.code, item.path) for item in validation.errors])

    def test_failed_action_cannot_produce_formal_result(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            action = payload["runs"][0]["actions"][0]
            action.update(
                {
                    "status": "failed",
                    "failure_code": "REPRO.ENVIRONMENT_FAILURE",
                    "disposition_route": "replace-implementation",
                    "deviation_id": "DEV-001",
                }
            )
            payload["runs"][0]["deviations"] = [
                {
                    "id": "DEV-001",
                    "planned": "Run with the frozen environment.",
                    "actual": "Environment failed before an accepted output.",
                    "reason": "Runtime dependency was unavailable.",
                    "classification": "REPRO.ENVIRONMENT_FAILURE",
                    "disposition": "replace-implementation",
                    "action_id": "ACT-MVMR-001",
                    "failure_code": "REPRO.ENVIRONMENT_FAILURE",
                    "disposition_route": "replace-implementation",
                    "affected_claim_ids": payload["runs"][0]["claim_ids"],
                }
            ]
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("ME.ACTION.RESULT_FORBIDDEN", codes)
            self.assertIn("ME.RESULT.ACTION_NOT_ACCEPTED", codes)

    def test_attempt_is_append_only_per_operation(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            duplicate = copy.deepcopy(payload["runs"][0]["actions"][0])
            duplicate["id"] = "ACT-MVMR-002"
            duplicate["check_results"][0]["id"] = "CHK-MVMR-002"
            duplicate["result_ids"] = []
            payload["runs"][0]["actions"].append(duplicate)
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("ME.ACTION.ATTEMPT_OVERWRITE", codes)

    def test_full_action_cannot_be_accepted_without_accepted_mvmr(self) -> None:
        temporary, base, _design, payload = v3_workspace(include_full=True)
        with temporary:
            payload["runs"][0]["actions"][0]["status"] = "superseded"
            payload["runs"][0]["actions"][0]["result_ids"] = []
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("ME.ACTION.FULL_BEFORE_MVMR", codes)

    def test_full_action_waits_for_every_required_mvmr_even_if_one_is_accepted(self) -> None:
        temporary, base, design, payload = v3_workspace(include_full=True)
        with temporary:
            second_mvmr = copy.deepcopy(design["execution_blueprint"]["steps"][0])
            second_mvmr["id"] = "STEP-MVMR-002"
            second_mvmr["procedure"]["operation"] = "second-pilot-check"
            design["execution_blueprint"]["steps"].insert(1, second_mvmr)
            digest = method_execution._canonical_digest(design)
            payload["design_sha256"] = digest
            for action in payload["runs"][0]["actions"]:
                action["started_from_design_sha256"] = digest
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("ME.ACTION.FULL_BEFORE_MVMR", codes)

    def test_null_result_requires_claim_narrowing_or_withdrawal(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["results"][0]["status"] = "null"
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("ME.CLAIM.NEGATIVE_UNDISPOSED", codes)

    def test_downstream_eligibility_retained_claim_can_support_and_report(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            projection = method_execution.downstream_eligibility(base, payload)
            self.assertEqual("PASS", projection["status"], projection["issues"])
            result = projection["results"]["RES-001"]
            claim_id = payload["runs"][0]["claim_ids"][0]
            self.assertEqual("retained", result["claim_dispositions"][claim_id])
            self.assertEqual(
                ["claim_support", "result_report"],
                result["claim_allowed_uses"][claim_id],
            )
            self.assertEqual(
                ["claim_support", "result_report"],
                result["allowed_uses"],
            )

    def test_downstream_eligibility_narrowed_or_withdrawn_negative_cannot_support_claim(self) -> None:
        for disposition_status, route_prefix in (("narrowed", "narrow"), ("withdrawn", "withdraw")):
            with self.subTest(disposition_status=disposition_status):
                temporary, base, _design, payload = v3_workspace()
                with temporary:
                    run = payload["runs"][0]
                    claim_id = run["claim_ids"][0]
                    run["status"] = "negative"
                    run["results"][0]["status"] = "negative"
                    run["claim_dispositions"][0].update(
                        {
                            "status": disposition_status,
                            "route": f"{route_prefix}:{claim_id}",
                        }
                    )
                    projection = method_execution.downstream_eligibility(base, payload)
                    self.assertEqual("PASS", projection["status"], projection["issues"])
                    result = projection["results"]["RES-001"]
                    self.assertEqual(disposition_status, result["claim_dispositions"][claim_id])
                    self.assertNotIn("claim_support", result["allowed_uses"])
                    self.assertEqual(
                        ["negative_or_null_report"],
                        result["claim_allowed_uses"][claim_id],
                    )

    def test_nonconsumable_result_cannot_retain_claim(self) -> None:
        for result_status in ("withdrawn", "not-applicable"):
            with self.subTest(result_status=result_status):
                temporary, base, _design, payload = v3_workspace()
                with temporary:
                    payload["runs"][0]["results"][0]["status"] = result_status
                    projection = method_execution.downstream_eligibility(base, payload)
                    self.assertEqual("BLOCKED", projection["status"])
                    self.assertIn(
                        "ME.CLAIM.NONCONSUMABLE_RETAINED",
                        {item["code"] for item in projection["issues"]},
                    )

    def test_supported_result_with_withdrawn_claim_has_zero_allowed_uses(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            run = payload["runs"][0]
            claim_id = run["claim_ids"][0]
            run["claim_dispositions"][0].update(
                {"status": "withdrawn", "route": f"withdraw:{claim_id}"}
            )
            projection = method_execution.downstream_eligibility(base, payload)
            self.assertEqual("PASS", projection["status"], projection["issues"])
            self.assertEqual([], projection["results"]["RES-001"]["allowed_uses"])

    def test_duplicate_claim_result_disposition_is_order_independent(self) -> None:
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                temporary, base, _design, payload = v3_workspace()
                with temporary:
                    run = payload["runs"][0]
                    claim_id = run["claim_ids"][0]
                    duplicate = {
                        "id": "DSP-002",
                        "claim_id": claim_id,
                        "result_ids": ["RES-001"],
                        "status": "withdrawn",
                        "reason": "A second disposition must never overwrite the first.",
                        "route": f"withdraw:{claim_id}",
                    }
                    run["claim_dispositions"].append(duplicate)
                    if reverse:
                        run["claim_dispositions"].reverse()
                    projection = method_execution.downstream_eligibility(base, payload)
                    self.assertEqual("BLOCKED", projection["status"])
                    self.assertIn(
                        "ME.CLAIM.DISPOSITION_DUPLICATE",
                        {item["code"] for item in projection["issues"]},
                    )

    def test_withdrawn_run_never_projects_historical_results(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["status"] = "withdrawn"
            projection = method_execution.downstream_eligibility(base, payload)
            self.assertEqual("PASS", projection["status"], projection["issues"])
            self.assertEqual({}, projection["results"])

    def test_latest_failed_attempt_invalidates_old_accepted_result_authority(self) -> None:
        temporary, base, design, payload = v3_workspace()
        with temporary:
            run = payload["runs"][0]
            old = run["actions"][0]
            step = design["execution_blueprint"]["steps"][0]
            failure = step["on_failure"][0]
            retry = copy.deepcopy(old)
            retry.update(
                {
                    "id": "ACT-RETRY-002",
                    "attempt": 2,
                    "status": "failed",
                    "output_artifact_ids": [],
                    "check_results": [],
                    "failure_code": failure["code"],
                    "disposition_route": failure["route"],
                    "deviation_id": "DEV-RETRY-002",
                    "result_ids": [],
                }
            )
            run["actions"].append(retry)
            run["deviations"].append(
                {
                    "id": "DEV-RETRY-002",
                    "planned": "Repeat the frozen first operation.",
                    "actual": "The latest immutable attempt failed.",
                    "reason": "Registered failure route was triggered.",
                    "classification": failure["code"],
                    "disposition": failure["route"],
                    "action_id": retry["id"],
                    "failure_code": failure["code"],
                    "disposition_route": failure["route"],
                    "affected_claim_ids": run["claim_ids"],
                }
            )
            projection = method_execution.downstream_eligibility(base, payload)
            self.assertEqual("BLOCKED", projection["status"])
            self.assertIn(
                "ME.MVMR.ACTION_INVALID",
                {item["code"] for item in projection["issues"]},
            )

    def test_downstream_eligibility_blocks_invalid_canonical_payload(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            payload["runs"][0]["actions"][0]["check_results"][0]["status"] = "fail"
            projection = method_execution.downstream_eligibility(base, payload)
            self.assertEqual("BLOCKED", projection["status"])
            self.assertEqual({}, projection["results"])
            self.assertIn(
                "ME.ACTION.CHECK_FAILED",
                {item["code"] for item in projection["issues"]},
            )

    def test_downstream_eligibility_blocks_invalid_json_without_fallback(self) -> None:
        temporary, base, _design, _payload = v3_workspace()
        with temporary:
            (base / method_execution.EXECUTION_REL).write_text("{", encoding="utf-8")
            projection = method_execution.downstream_eligibility(base)
            self.assertEqual("BLOCKED", projection["status"])
            self.assertEqual({}, projection["results"])
            self.assertEqual("ME.JSON.INVALID", projection["issues"][0]["code"])

    def test_v2_migration_preserves_id_and_hash_but_not_action_authority(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        with temporary:
            base = Path(temporary.name)
            legacy_design = fixtures.confirmed_design("survey")
            (base / "research_design.json").write_text(json.dumps(legacy_design, ensure_ascii=False), encoding="utf-8")
            legacy = fixtures.complete_execution(base, legacy_design)
            design = v4_design()
            migrated = method_execution.migrate_v2_payload(design, legacy)
            self.assertEqual("cnki-method-execution/v3", migrated["schema_version"])
            self.assertEqual("needs-review", migrated["status"])
            self.assertEqual(legacy["runs"][0]["id"], migrated["runs"][0]["id"])
            self.assertEqual(legacy["runs"][0]["artifacts"][0]["sha256"], migrated["runs"][0]["artifacts"][0]["sha256"])
            self.assertEqual([], migrated["runs"][0]["actions"])
            self.assertEqual([], migrated["runs"][0]["results"][0]["action_ids"])
            self.assertEqual("unchecked", migrated["runs"][0]["minimum_viable_run"]["status"])
            self.assertEqual(legacy["runs"][0]["actions"], migrated["migration"]["legacy_actions"][0]["actions"])

    def test_cli_v3_migration_is_review_only_and_content_addressed(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        with temporary:
            base = Path(temporary.name)
            legacy_design = fixtures.confirmed_design("survey")
            (base / "research_design.json").write_text(json.dumps(legacy_design, ensure_ascii=False), encoding="utf-8")
            legacy = fixtures.complete_execution(base, legacy_design)
            (base / "method_execution.json").write_text(
                json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            design = v4_design()
            (base / "research_design.json").write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
            code, preview_text = method_execution.migrate_command(base, apply=False, to="v3")
            self.assertEqual(0, code)
            preview = json.loads(preview_text)
            self.assertEqual("cnki-method-execution/v3", preview["schema_version"])
            self.assertFalse(Path(preview["backup"]).exists())
            code, _message = method_execution.migrate_command(base, apply=True, to="v3")
            self.assertEqual(0, code)
            self.assertTrue(Path(preview["backup"]).is_file())
            migrated = json.loads((base / "method_execution.json").read_text(encoding="utf-8"))
            self.assertEqual("needs-review", migrated["status"])
            self.assertEqual([], migrated["runs"][0]["actions"])

    def test_v3_render_emits_deterministic_pilot_trace_and_disposition_views(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            method_execution.render_record(base, payload)
            paths = [
                base / method_execution.VIEW_REL,
                base / method_execution.PILOT_VIEW_REL,
                base / method_execution.ACTION_RESULT_VIEW_REL,
                base / method_execution.CLAIM_DISPOSITION_VIEW_REL,
            ]
            first = {path.name: path.read_bytes() for path in paths}
            method_execution.render_record(base, payload)
            self.assertEqual(first, {path.name: path.read_bytes() for path in paths})
            for path in paths:
                self.assertIn(
                    method_execution.GENERATED_MARKER,
                    path.read_text(encoding="utf-8"),
                )
            self.assertIn("RES-001", (base / method_execution.ACTION_RESULT_VIEW_REL).read_text(encoding="utf-8"))
            self.assertIn("DSP-001", (base / method_execution.CLAIM_DISPOSITION_VIEW_REL).read_text(encoding="utf-8"))

    def test_v3_render_separates_workflow_identities_from_domain_narratives(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            run = payload["runs"][0]
            run["actions"][0]["check_results"][0]["diagnostic"] = (
                "H3253 is a questionnaire variable used by this action check."
            )
            run["results"][0]["text"] = "H3255 and H3256 form the bounded result."
            run["negative_findings"] = [
                {
                    "id": "NEG-001",
                    "text": "H3240 does not support the competing interpretation.",
                    "reported_in": "analysis_or_results",
                    "claim_ids": [run["claim_ids"][0]],
                    "evidence_ids": [run["evidence_ids"][0]],
                }
            ]

            validation = method_execution.validate_payload(base, payload)
            self.assertEqual(
                [],
                validation.errors,
                [(item.code, item.path) for item in validation.errors],
            )

            # Deviation prose uses the same rendering boundary. It is added only
            # after canonical validation because a valid v3 deviation must bind a
            # failed action, which is outside this projection-focused fixture.
            run["deviations"] = [
                {"id": "DEV-001", "actual": "H3256 required a bounded deviation."}
            ]
            method_execution.render_record(base, payload)
            record = (base / method_execution.VIEW_REL).read_text(encoding="utf-8")
            identity_section, narrative_section = record.split("## Domain narratives", 1)

            for variable in ("H3253", "H3240", "H3255", "H3256"):
                self.assertNotIn(variable, identity_section)
                self.assertIn(variable, narrative_section)
            for identity in ("ACT-001", "RES-001", "NEG-001", "DEV-001"):
                self.assertIn(identity, identity_section)
            self.assertIn("avereth:view-role=identity-projection", identity_section)
            self.assertIn(
                "avereth:view-role=domain-narrative; identity-columns=1,3; "
                "narrative-identity-authority=none",
                narrative_section,
            )
            self.assertIn("Claim dispositions", record)
            self.assertIn("Design contract SHA-256", record)

    def test_v3_render_refuses_to_overwrite_any_hand_maintained_view(self) -> None:
        temporary, base, _design, payload = v3_workspace()
        with temporary:
            manual = base / method_execution.PILOT_VIEW_REL
            manual.write_text("hand-maintained pilot", encoding="utf-8")
            with self.assertRaisesRegex(method_execution.ExecutionContractError, "Refusing"):
                method_execution.render_record(base, payload)
            self.assertEqual("hand-maintained pilot", manual.read_text(encoding="utf-8"))
            self.assertFalse((base / method_execution.VIEW_REL).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
