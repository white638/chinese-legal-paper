#!/usr/bin/env python3
"""Cross-contract acceptance tests for executable research protocols."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
CNKI_SCRIPTS = REPO / "skills" / "cnki-paper" / "scripts"
EMPIRICAL_SCRIPTS = REPO / "skills" / "empirical-research" / "scripts"
for directory in (CNKI_SCRIPTS, EMPIRICAL_SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


execution_fixtures = load_module(
    "research_protocol_execution_fixtures",
    EMPIRICAL_SCRIPTS / "test_method_execution_v3.py",
)
design_fixtures = load_module(
    "research_protocol_design_fixtures",
    CNKI_SCRIPTS / "test_research_design_v4.py",
)

from avereth_core.application import plan_service, protocol_compiler  # noqa: E402
import prose_packet  # noqa: E402


CASES = json.loads((Path(__file__).with_name("cases.json")).read_text(encoding="utf-8"))


def materiality_request(payload: dict) -> dict:
    run = payload["runs"][0]
    result = run["results"][0]
    claim_id = result["claim_ids"][0]
    evidence_id = result["evidence_ids"][0]
    return {
        "section_role": "results",
        "object": "已登记研究主张的最小可行方法运行",
        "claim": {
            "id": claim_id,
            "text": result["text"],
            "strength": result["type"],
        },
        "evidence_items": [
            {
                "id": evidence_id,
                "text": "真实材料、定位、分析单位和散列工件共同支持该结果。",
            }
        ],
        "result_ids": [result["id"]],
        "warrant": "该结果仅来自通过全部诊断并被接受的方法动作。",
        "boundaries": [],
        "countervoices": [],
        "reader_update": "主张处置由可复核的执行结果决定。",
    }


def executable_workspace():
    """Build one internally valid v4→v3→protocol→prose fixture from real contracts."""
    temporary, base, _legacy_design, execution = execution_fixtures.v3_workspace()
    design = design_fixtures.confirmed_v4("survey")
    design["operationalizations"][0]["material_ids"] = ["MAT-001"]
    for step in design["execution_blueprint"]["steps"]:
        step["material_ids"] = ["MAT-001"]
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    payload = copy.deepcopy(execution)
    digest = execution_fixtures.method_execution._canonical_digest(design)
    payload["design_sha256"] = digest
    run = payload["runs"][0]
    run["design_route_sha256"] = execution_fixtures.method_execution._canonical_digest(
        design["method_routes"][0]
    )
    run["inference_ceiling_observed"] = design["method_routes"][0]["inference_ceiling"]
    run["prohibited_inferences_observed"] = design["method_routes"][0]["prohibited_inferences"]
    actions: list[dict] = []
    artifacts: list[dict] = []
    action_ids: list[str] = []
    artifact_ids: list[str] = []
    check_ids: list[str] = []
    for index, step in enumerate(
        [
            item
            for item in design["execution_blueprint"]["steps"]
            if item["run_kind"] == "mvmr"
        ],
        start=1,
    ):
        action_id = f"ACT-E2E-{index:03d}"
        artifact_id = f"ART-E2E-{index:03d}"
        check_id = f"CHK-E2E-{index:03d}"
        expected = step["expected_artifacts"][0]
        artifact_path = base / expected["path"]
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(
            {"operation": step["procedure"]["operation"], "locator": f"unit-{index}"},
            ensure_ascii=False,
            sort_keys=True,
        )
        artifact_path.write_text(content, encoding="utf-8")
        artifacts.append(
            {
                "id": artifact_id,
                "path": expected["path"],
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "role": expected["role"],
            }
        )
        parameter_snapshot = {
            "format": execution_fixtures.method_execution.PARAMETER_SNAPSHOT_FORMAT,
            "kind": "parameters",
            "content": {
                "method_fields": copy.deepcopy(run["method_fields"]),
                "operation_id": step["id"],
                "procedure": copy.deepcopy(step["procedure"]),
            },
        }
        actions.append(
            {
                "id": action_id,
                "operation_id": step["id"],
                "attempt": 1,
                "run_kind": "mvmr",
                "status": "accepted",
                "started_from_design_sha256": digest,
                "parameter_snapshot": parameter_snapshot,
                "parameter_snapshot_sha256": (
                    execution_fixtures.method_execution._canonical_digest(
                        parameter_snapshot
                    )
                ),
                "input_artifact_ids": [],
                "output_artifact_ids": [artifact_id],
                "software_environment_id": "ENV-001",
                "check_results": [
                    {
                        "id": check_id,
                        "rule": step["acceptance_checks"][0]["rule"],
                        "status": "pass",
                        "diagnostic": "工件存在、定位可解析且散列与登记值一致。",
                        "artifact_ids": [artifact_id],
                    }
                ],
                "failure_code": "",
                "disposition_route": "continue",
                "deviation_id": "",
                "result_ids": ["RES-001"],
            }
        )
        action_ids.append(action_id)
        artifact_ids.append(artifact_id)
        check_ids.append(check_id)
    run["actions"] = actions
    run["artifacts"] = artifacts
    payload["material_realizations"][0]["artifact_ids"] = artifact_ids
    run["results"][0]["action_ids"] = action_ids
    run["results"][0]["artifact_ids"] = artifact_ids
    run["minimum_viable_run"] = {
        "status": "accepted",
        "material_id": "MAT-001",
        "analysis_unit": {
            "id": "UNIT-001",
            "material_id": "MAT-001",
            "unit_type": "survey response",
            "locator": "artifact:ART-E2E-001#json:/locator",
        },
        "extraction_or_coding": {
            "kind": "coding",
            "rule": "按冻结的问卷编码规则提取一个真实响应单位。",
            "artifact_id": artifact_ids[0],
        },
        "action_ids": action_ids,
        "artifact_ids": artifact_ids,
        "check_result_ids": check_ids,
        "result_ids": ["RES-001"],
        "claim_disposition_ids": ["DSP-001"],
    }
    (base / "method_execution.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return temporary, base, design, payload


class ResearchProtocolEvals(unittest.TestCase):
    def test_eval_manifest_covers_positive_negative_boundary_drift_and_e2e(self) -> None:
        self.assertEqual("avereth-research-protocol-evals/v1", CASES["schema_version"])
        self.assertEqual(11, len(CASES["cases"]))
        self.assertEqual(
            {"positive", "negative", "boundary", "drift", "negative-result", "release", "end-to-end"},
            {item["kind"] for item in CASES["cases"]},
        )

    def test_positive_chain_compiles_mvmr_to_full_and_accepted_result_to_prose(self) -> None:
        temporary, base, design, execution = executable_workspace()
        with temporary:
            validation = execution_fixtures.method_execution.validate_payload(base, execution)
            self.assertEqual([], validation.errors)

            plan = protocol_compiler.compile_protocol(
                base,
                design=design,
                execution=execution,
            )
            self.assertEqual("avereth-research-protocol/v1", plan["schema_version"])
            operation_plan = plan_service.build_plan(
                {
                    "next_stage": "execution",
                    "task_profile": "full_paper",
                    "publication_track": "cnki-cn",
                },
                protocol=plan,
                granularity="operation",
            )
            first_full = next(
                item["id"]
                for item in design["execution_blueprint"]["steps"]
                if item["run_kind"] == "full"
            )
            self.assertEqual("avereth-plan/v2", operation_plan["schema_version"])
            self.assertEqual(first_full, operation_plan["next_executable_action"])
            self.assertIn(first_full, operation_plan["runnable_action_ids"])

            registered = prose_packet.discover_registered_ids(base)
            accepted = prose_packet.discover_accepted_result_claims(base)
            packet = prose_packet.compile_prose_packet(
                materiality_request(execution),
                registered_ids=registered,
                accepted_result_claims=accepted,
            )
            self.assertEqual(["RES-001"], packet["result_ids"])
            self.assertEqual([], prose_packet.validate_prose_packet(
                packet,
                registered_ids=registered,
                accepted_result_claims=accepted,
            ))

    def test_failed_action_result_is_excluded_from_the_build_registry(self) -> None:
        temporary, base, _design, execution = executable_workspace()
        with temporary:
            failed = copy.deepcopy(execution)
            action = failed["runs"][0]["actions"][0]
            action["status"] = "failed"
            action["check_results"][0]["status"] = "fail"
            action["failure_code"] = "REPRO.ENVIRONMENT_FAILURE"
            action["disposition_route"] = "replace-implementation"
            action["deviation_id"] = "DEV-001"
            (base / "method_execution.json").write_text(
                json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            registered = prose_packet.discover_registered_ids(base)
            self.assertNotIn("RES-001", registered)
            with self.assertRaisesRegex(prose_packet.ProsePacketError, "not registered"):
                prose_packet.compile_prose_packet(
                    materiality_request(failed),
                    registered_ids=registered,
                    accepted_result_claims=prose_packet.discover_accepted_result_claims(base),
                )

    def test_design_drift_invalidates_all_runnable_operations(self) -> None:
        temporary, base, design, execution = executable_workspace()
        with temporary:
            changed = copy.deepcopy(design)
            changed["status"] = "needs-review"
            plan = protocol_compiler.compile_protocol(
                base,
                design=changed,
                execution=execution,
            )
            self.assertTrue(plan["invalidated_by_design_change"])
            self.assertFalse(plan["valid"])
            self.assertEqual([], plan["runnable_action_ids"])

    def test_structured_step_and_negative_result_gates_remain_executable(self) -> None:
        design = design_fixtures.confirmed_v4()
        design["execution_blueprint"]["steps"][0] = "run the pilot"
        codes = {item.code for item in design_fixtures.validate(design).errors}
        self.assertIn("RD.PROTOCOL.STEP_INVALID", codes)

        temporary, base, _design, execution = execution_fixtures.v3_workspace()
        with temporary:
            execution["runs"][0]["results"][0]["status"] = "negative"
            codes = {
                item.code
                for item in execution_fixtures.method_execution.validate_payload(base, execution).errors
            }
            self.assertIn("ME.CLAIM.NEGATIVE_UNDISPOSED", codes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
