from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT = Path(__file__).with_name("results_validation_check.py")
SPEC = importlib.util.spec_from_file_location("results_validation_check_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)

EMPIRICAL_SCRIPTS = SCRIPT.resolve().parents[4] / "empirical-research" / "scripts"
if str(EMPIRICAL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(EMPIRICAL_SCRIPTS))
FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "results_validation_v3_fixtures",
    EMPIRICAL_SCRIPTS / "test_method_execution_v3.py",
)
assert FIXTURE_SPEC is not None and FIXTURE_SPEC.loader is not None
v3_fixtures = importlib.util.module_from_spec(FIXTURE_SPEC)
sys.modules[FIXTURE_SPEC.name] = v3_fixtures
FIXTURE_SPEC.loader.exec_module(v3_fixtures)

CNKI_SCRIPTS = SCRIPT.resolve().parents[3] / "scripts"
DESIGN_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "results_validation_design_v4_fixtures",
    CNKI_SCRIPTS / "test_research_design_v4.py",
)
assert DESIGN_FIXTURE_SPEC is not None and DESIGN_FIXTURE_SPEC.loader is not None
design_v4_fixtures = importlib.util.module_from_spec(DESIGN_FIXTURE_SPEC)
sys.modules[DESIGN_FIXTURE_SPEC.name] = design_v4_fixtures
DESIGN_FIXTURE_SPEC.loader.exec_module(design_v4_fixtures)


def _write_execution(base: Path, payload: dict) -> None:
    (base / "method_execution.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_registry(base: Path) -> None:
    path = base / "reference_materials" / "literature_registry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "cnki-acquisition/v1",
                "sources": [
                    {
                        "source_id": source_id,
                        "title": source_id,
                        "state": "content-verified",
                        "citation_scope": "final-source",
                        "verification": {
                            "method": "detail",
                            "support_claim": "已核验的真实来源为登记研究边界提供具体支撑。",
                        },
                    }
                    for source_id in ("S01", "S02")
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _canonical_v3_workspace():
    """Build a real, canonical-valid v4 design plus v3 execution ledger."""
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    design = design_v4_fixtures.confirmed_v4("survey")
    for operationalization in design["operationalizations"]:
        operationalization["material_ids"] = ["MAT-001"]
    for step in design["execution_blueprint"]["steps"]:
        step["material_ids"] = ["MAT-001"]

    legacy_design = v3_fixtures.fixtures.confirmed_design("survey")
    (base / "research_design.json").write_text(
        json.dumps(legacy_design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    legacy_execution = v3_fixtures.fixtures.complete_execution(base, legacy_design)
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_registry(base)

    authority = v3_fixtures.method_execution
    payload = authority.migrate_v2_payload(design, legacy_execution)
    payload["status"] = "complete"
    run = payload["runs"][0]
    run["status"] = "qualified"
    run["migration_status"] = "reviewed"
    route = design["method_routes"][0]
    run["design_route_sha256"] = authority._canonical_digest(route)
    run["inference_ceiling_observed"] = route["inference_ceiling"]
    run["prohibited_inferences_observed"] = route["prohibited_inferences"]
    result_record = run["results"][0]
    artifact = next(item for item in run["artifacts"] if item["id"] == "ART-001")
    mvmr_steps = [
        step
        for step in design["execution_blueprint"]["steps"]
        if step["run_kind"] == "mvmr"
    ]
    actions = []
    action_ids = []
    check_ids = []
    for index, step in enumerate(mvmr_steps, start=1):
        action_id = f"ACT-MVMR-{index:03d}"
        check_id = f"CHK-MVMR-{index:03d}"
        parameter_snapshot = {
            "format": authority.PARAMETER_SNAPSHOT_FORMAT,
            "kind": "parameters",
            "content": {
                "operation_id": step["id"],
                "run_kind": "mvmr",
                "procedure": step["procedure"],
            },
        }
        action_ids.append(action_id)
        check_ids.append(check_id)
        actions.append(
            {
                "id": action_id,
                "operation_id": step["id"],
                "attempt": 1,
                "run_kind": "mvmr",
                "status": "accepted",
                "started_from_design_sha256": payload["design_sha256"],
                "parameter_snapshot": parameter_snapshot,
                "parameter_snapshot_sha256": authority._canonical_digest(
                    parameter_snapshot
                ),
                "input_artifact_ids": ["ART-001"],
                "output_artifact_ids": ["ART-001"],
                "software_environment_id": "ENV-001",
                "check_results": [
                    {
                        "id": check_id,
                        "rule": "真实工件存在、定位可解析且散列一致。",
                        "status": "pass",
                        "diagnostic": "规范执行动作、真实分析单位与结果链接均已动态复核。",
                        "artifact_ids": ["ART-001"],
                    }
                ],
                "failure_code": "",
                "disposition_route": "continue",
                "deviation_id": "",
                "result_ids": ["RES-001"],
            }
        )
    run["actions"] = actions
    result_record["action_ids"] = action_ids
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
        "action_ids": action_ids,
        "artifact_ids": ["ART-001"],
        "check_result_ids": check_ids,
        "result_ids": ["RES-001"],
        "claim_disposition_ids": ["DSP-001"],
    }
    payload["material_realizations"] = [
        {
            "material_id": "MAT-001",
            "status": "REALIZED",
            "artifact_ids": ["ART-001"],
            "path": artifact["path"],
            "sha256": artifact["sha256"],
        }
    ]
    return temporary, base, design, payload


class CanonicalResultsValidationTests(unittest.TestCase):
    def test_missing_method_execution_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            result = checker.validate(base / "results_validation.md")
            self.assertFalse(result.ok)
            self.assertEqual("BLOCKED", result.projection_status)
            self.assertTrue(
                any("ME.FILE.MISSING" in finding for finding in result.findings),
                result.findings,
            )

    def test_fake_markdown_claim_and_number_cannot_create_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "# Fake derived view",
                        "",
                        "| Results Unit | Contribution Claim Tested | Result/Evidence |",
                        "|---|---|---|",
                        "| 4.2 | CLM-FAKE | 99.9 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = checker.validate(base / "results_validation.md")
            self.assertFalse(result.ok)
            self.assertEqual(0, result.mapped_rows)
            self.assertTrue(
                any("cannot override" in finding for finding in result.findings),
                result.findings,
            )

    def test_canonical_validation_blocked_cannot_be_overridden_by_fake_view(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            payload["runs"][0]["results"][0]["claim_ids"] = ["CLM-FAKE"]
            _write_execution(base, payload)
            (base / "results_validation.md").write_text(
                "| Results Unit | Contribution Claim Tested | Result/Evidence |\n"
                "|---|---|---|\n"
                "| 4.2 | CLM-FAKE | 99.9 |\n",
                encoding="utf-8",
            )
            result = checker.validate(base / "results_validation.md")
            self.assertFalse(result.ok)
            self.assertEqual("BLOCKED", result.projection_status)
            self.assertTrue(
                any("ME.RESULT" in finding for finding in result.findings),
                result.findings,
            )

    def test_valid_v3_projection_passes_without_markdown_authority(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            _write_execution(base, payload)
            projection = checker._method_execution_module().downstream_eligibility(base)
            self.assertEqual("PASS", projection["status"], projection.get("issues"))
            result = checker.validate(base / "results_validation.md")
            self.assertTrue(result.ok, result.findings)
            self.assertEqual("PASS", result.projection_status)
            self.assertEqual(1, result.mapped_rows)

    def test_pass_projection_with_no_allowed_use_still_fails_closed(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            run = payload["runs"][0]
            run["results"][0]["status"] = "withdrawn"
            run["claim_dispositions"][0]["status"] = "withdrawn"
            claim_id = run["claim_dispositions"][0]["claim_id"]
            run["claim_dispositions"][0]["route"] = f"withdraw:{claim_id}"
            _write_execution(base, payload)
            projection = checker._method_execution_module().downstream_eligibility(base)
            self.assertEqual("PASS", projection["status"], projection.get("issues"))
            self.assertEqual([], projection["results"]["RES-001"]["allowed_uses"])
            result = checker.validate(base / "results_validation.md")
            self.assertFalse(result.ok)
            self.assertEqual(0, result.mapped_rows)
            self.assertTrue(
                any("no result with non-empty allowed_uses" in finding for finding in result.findings),
                result.findings,
            )

    def test_renderer_carries_complete_canonical_result_identity(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            _write_execution(base, payload)
            projection = checker.canonical_projection(base)
            self.assertEqual("PASS", projection["status"], projection.get("issues"))
            view = checker.render_results_validation(projection)
            record = projection["results"]["RES-001"]
            claim_id = record["claim_ids"][0]
            action_id = record["action_ids"][0]
            artifact_id = record["artifact_ids"][0]
            self.assertIn("Derived view status: **PASS**", view)
            self.assertIn("RES-001", view)
            self.assertIn(claim_id, view)
            self.assertIn("claim_support", view)
            self.assertIn(action_id, view)
            self.assertIn(artifact_id, view)
            self.assertIn(record["artifact_sha256"][artifact_id], view)
            self.assertIn(record["authority_digest"], view)
            self.assertIn(
                record["action_attempts"][0]["parameter_snapshot_sha256"],
                view,
            )
            self.assertEqual(view, checker.render_results_validation(projection))

    def test_renderer_separates_domain_variables_from_identity_licenses(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            payload["runs"][0]["results"][0]["text"] = (
                "H3255 and H3256 are questionnaire variables, not workflow IDs."
            )
            _write_execution(base, payload)
            projection = checker.canonical_projection(base)
            self.assertEqual("PASS", projection["status"], projection.get("issues"))

            view = checker.render_results_validation(projection)
            identity_section, remainder = view.split("## Domain Result Statements", 1)
            narrative_section, _attempts = remainder.split("## Accepted Action Attempts", 1)

            self.assertIn("RES-001", identity_section)
            self.assertNotIn("Result Statement", identity_section)
            self.assertNotIn("H3255", identity_section)
            self.assertNotIn("H3256", identity_section)
            self.assertIn("Result Statement", narrative_section)
            self.assertIn("H3255", narrative_section)
            self.assertIn("H3256", narrative_section)
            self.assertIn("avereth:view-role=identity-projection", identity_section)
            self.assertIn(
                "avereth:view-role=domain-narrative; identity-columns=1; "
                "narrative-identity-authority=none",
                narrative_section,
            )

            results_path = base / "results_validation.md"
            results_path.write_text(view, encoding="utf-8")
            validation = checker.validate(results_path, projection=projection)
            self.assertTrue(validation.ok, validation.findings)

    def test_write_rebuilds_fake_markdown_from_one_projection_snapshot(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            _write_execution(base, payload)
            (base / "results_validation.md").write_text(
                "CLM-FAKE | RES-FAKE | 99.9\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                output_dir=str(base), markdown=False, json=False, write=True
            )
            with (
                mock.patch.object(checker, "parse_args", return_value=args),
                mock.patch.object(
                    checker,
                    "canonical_projection",
                    wraps=checker.canonical_projection,
                ) as projection_call,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = checker.main()
            self.assertEqual(0, exit_code)
            projection_call.assert_called_once_with(base)
            rebuilt = (base / "results_validation.md").read_text(encoding="utf-8")
            check_report = (base / "results_validation_check.md").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("CLM-FAKE", rebuilt)
            self.assertNotIn("RES-FAKE", rebuilt)
            self.assertIn("RES-001", rebuilt)
            self.assertIn("Status: **PASS**", check_report)

    def test_blocked_write_replaces_forged_view_with_blocking_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "results_validation.md").write_text(
                "CLM-FAKE | RES-FAKE | 99.9\n",
                encoding="utf-8",
            )
            args = SimpleNamespace(
                output_dir=str(base), markdown=False, json=False, write=True
            )
            with (
                mock.patch.object(checker, "parse_args", return_value=args),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                exit_code = checker.main()
            self.assertEqual(1, exit_code)
            rebuilt = (base / "results_validation.md").read_text(encoding="utf-8")
            self.assertNotIn("CLM-FAKE", rebuilt)
            self.assertNotIn("RES-FAKE", rebuilt)
            self.assertIn("Derived view status: **BLOCKED**", rebuilt)
            self.assertIn("ME.FILE.MISSING", rebuilt)

    def test_missing_artifact_hash_blocks_view_even_when_projection_says_pass(self) -> None:
        temporary, base, _design, payload = _canonical_v3_workspace()
        with temporary:
            _write_execution(base, payload)
            projection = copy.deepcopy(checker.canonical_projection(base))
            projection["results"]["RES-001"]["artifact_sha256"] = {}
            result = checker.validate(
                base / "results_validation.md",
                projection=projection,
            )
            view = checker.render_results_validation(projection)
            self.assertFalse(result.ok)
            self.assertTrue(
                any("no valid SHA-256 identity" in item for item in result.findings),
                result.findings,
            )
            self.assertIn("Derived view status: **BLOCKED**", view)
            self.assertNotIn("## Result–Claim–Use Licenses", view)


if __name__ == "__main__":
    unittest.main()
