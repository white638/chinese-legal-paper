#!/usr/bin/env python3
"""Adversarial v6.2 tests for material facts, F2 judgment, and resource fuses."""

from __future__ import annotations

import copy
import re
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import research_feasibility as rf
import research_materials as rm
import research_design_v3 as rd3
import research_decision as rd
from test_research_decision import make_workspace, write_json


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def refresh_feasibility(base: Path, payload: dict) -> None:
    live, issues = rf.selected_live_basis(base, payload)
    if issues:
        raise AssertionError(issues)
    payload["selected_assessment_digest"] = live["selected_assessment_digest"]
    payload["material_basis_digest"] = live["material_basis_digest"]
    payload["basis_digest"] = live["basis_digest"]


class DesignResult:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, code: str, severity: str, message: str, path: str) -> None:
        self.rows.append((code, severity, message, path))


def exact_material_plan(base: Path) -> dict:
    feasibility = read_json(base / rf.FEASIBILITY_REL)
    assessment = feasibility["candidate_assessments"][0]
    boundary = assessment["allowed_question_boundary"]
    reference, issues = rf.feasibility_reference(base)
    if reference is None:
        raise AssertionError(issues)
    return {
        "feasibility_basis_digest": reference["basis_digest"],
        "allowed_question_boundary_digest": rm.canonical_digest(boundary),
        "material_refs": copy.deepcopy(assessment["material_refs"]),
        "time_scope": boundary["time_scope"],
        "spatial_scope": boundary["spatial_scope"],
        "unit_scope": boundary["unit_scope"],
        "required_fields_or_roles": copy.deepcopy(boundary["required_fields_or_roles"]),
        "linkage_plan": "government and year form the registered comparison linkage",
        "variation_or_identification_plan": "visibility and investment variation support only the bounded registered contrast",
        "realization_rule": "hash-bind realized material artifacts and register every scope deviation",
    }


class ResearchMaterialsFeasibilityTests(unittest.TestCase):
    def test_registered_material_and_f2_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            self.assertEqual([], rm.validate_contract(base, scope="research")[2].errors)
            self.assertEqual([], rf.validate_contract(base)[2].errors)

    def test_missing_material_registry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = rm.validate_contract(Path(tmp), scope="acquisition")[2]
            self.assertIn("RM.FILE.MISSING", {item.code for item in result.errors})

    def test_secret_values_are_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rm.REGISTRY_REL)
            payload["materials"][0]["api_token"] = "must-not-be-stored"
            result = rm.validate_registry(base, payload)
            self.assertIn("RM.SECRET.FORBIDDEN", {item.code for item in result.errors})

    def test_material_identity_must_resolve_to_source_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rm.REGISTRY_REL)
            payload["materials"][0]["source_ids"] = ["S-NOT-REGISTERED"]
            result = rm.validate_registry(base, payload)
            self.assertIn("RM.MATERIAL.SOURCE_UNKNOWN", {item.code for item in result.errors})

    def test_pass_probe_requires_hash_bound_actual_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rm.REGISTRY_REL)
            payload["materials"][0]["probes"][0]["evidence_files"] = []
            result = rm.validate_registry(base, payload)
            self.assertIn("RM.PROBE.NO_ACTUAL_EVIDENCE", {item.code for item in result.errors})

    def test_uninspectable_evidence_path_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rm.REGISTRY_REL)
            with patch.object(rm, "_sha256", side_effect=OSError("denied")):
                result = rm.validate_registry(base, payload)
            self.assertIn("RM.EVIDENCE.RESOURCE", {item.code for item in result.errors})

    def test_failure_cache_reuses_unchanged_post_failure_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            missing = base / "reference_materials" / "probe_samples" / "absent.csv"
            kwargs = dict(
                material_id="MAT-001",
                adapter="tabular",
                sample=missing,
                performed_at="2026-08-20T08:00:00+00:00",
                candidate_digest="a" * 64,
                question_digest="b" * 64,
                failure_code="NO_ACTUAL_ACCESS",
                details="bounded sample could not be obtained",
                fields=[],
                key_assessment="",
                query_summary="",
                pagination_status="",
                rate_limit_status="",
                deduplication_status="",
                time_coverage="{}",
                spatial_coverage="{}",
                unit_coverage="{}",
                apply=True,
            )
            with redirect_stdout(StringIO()):
                first = rm.probe_command(base, **kwargs)
                second = rm.probe_command(base, **kwargs)
            self.assertEqual(1, first)
            self.assertEqual(1, second)
            current = read_json(base / rm.REGISTRY_REL)
            self.assertEqual(1, len(current["failures"]))
            self.assertEqual(2, len(current["materials"][0]["probes"]))

    def test_conditional_f2_is_valid_but_does_not_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rf.FEASIBILITY_REL)
            payload["status"] = "CONDITIONAL"
            payload["candidate_assessments"][0]["verdict"] = "CONDITIONAL"
            payload["candidate_assessments"][0]["dimensions"]["cost_and_time"] = "CONDITIONAL"
            refresh_feasibility(base, payload)
            write_json(base / rf.FEASIBILITY_REL, payload)
            self.assertEqual([], rf.validate_contract(base)[2].errors)
            state = rf.resource_unlock_state(base)
            self.assertEqual("pre_feasibility", state["phase"])
            self.assertIn("bulk_download", state["blocked_actions"])

    def test_critical_dimension_veto_cannot_be_overridden_by_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            payload = read_json(base / rf.FEASIBILITY_REL)
            payload["candidate_assessments"][0]["dimensions"]["actual_access"] = "BLOCKED"
            refresh_feasibility(base, payload)
            result = rf.validate_feasibility(base, payload)
            self.assertIn("RF.CRITICAL.VETO", {item.code for item in result.errors})

    def test_unselected_material_change_does_not_stale_selected_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            before = read_json(base / rf.FEASIBILITY_REL)
            registry = read_json(base / rm.REGISTRY_REL)
            extra = copy.deepcopy(registry["materials"][0])
            extra["material_id"] = "MAT-002"
            extra["material_locator"] = {"catalog_id": "UNUSED", "version": "1"}
            extra["probes"][0]["probe_id"] = "PROBE-002"
            registry["materials"].append(extra)
            write_json(base / rm.REGISTRY_REL, registry)
            result = rf.validate_feasibility(base, before)
            self.assertEqual([], result.errors)

    def test_selected_evidence_mutation_stales_f2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            sample = base / "reference_materials" / "probe_samples" / "local_investment.csv"
            sample.write_text(sample.read_text(encoding="utf-8") + "C,2024,high,11\n", encoding="utf-8")
            result = rf.validate_contract(base)[2]
            self.assertTrue(
                {"RF.MATERIAL.CONTRACT", "RF.BASIS.MISSING"} & {item.code for item in result.errors}
            )

    def test_not_applicable_cannot_hide_registered_materials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            registry = read_json(base / rm.REGISTRY_REL)
            registry["applicability"] = {
                "status": "NOT_APPLICABLE",
                "rationale": "Attempted escape despite an existing empirical material plan.",
            }
            result = rm.validate_registry(base, registry, scope="research")
            self.assertIn("RM.APPLICABILITY.CONFLICT", {item.code for item in result.errors})

    def test_human_subject_probe_cannot_pass_before_ethics_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            registry = read_json(base / rm.REGISTRY_REL)
            material = registry["materials"][0]
            material["material_type"] = "interview"
            material["access"]["ethics_status"] = "PENDING"
            result = rm.validate_registry(base, registry, scope="research")
            self.assertIn("RM.PROBE.ETHICS", {item.code for item in result.errors})

    def test_probe_sample_over_resource_limit_is_failed_and_cached(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            config = read_json(base / "workflow_config.json")
            config["resource_policy"] = {
                "max_f1_metadata_queries": 2,
                "max_f2_sample_bytes": 8,
                "max_f2_probe_seconds": 30,
            }
            write_json(base / "workflow_config.json", config)
            sample = base / "reference_materials" / "probe_samples" / "oversized.csv"
            sample.write_text("id,value\n1,oversized\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                code = rm.probe_command(
                    base,
                    material_id="MAT-001",
                    adapter="tabular",
                    sample=sample,
                    performed_at="2026-08-20T08:00:00+00:00",
                    candidate_digest="c" * 64,
                    question_digest="d" * 64,
                    failure_code=None,
                    details="",
                    fields=[],
                    key_assessment="",
                    query_summary="",
                    pagination_status="",
                    rate_limit_status="",
                    deduplication_status="",
                    time_coverage="{}",
                    spatial_coverage="{}",
                    unit_coverage="{}",
                    apply=True,
                )
            self.assertEqual(1, code)
            current = read_json(base / rm.REGISTRY_REL)
            self.assertEqual("COST_EXCEEDS_POLICY", current["failures"][-1]["failure_code"])

    def test_resource_unlock_has_three_phases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            make_workspace(base)
            post_f2 = rf.resource_unlock_state(base, question_committed=False)
            committed = rf.resource_unlock_state(base, question_committed=True)
            self.assertEqual("post_feasibility", post_f2["phase"])
            self.assertNotIn("manuscript_drafting", post_f2["allowed_actions"])
            self.assertEqual("post_commitment", committed["phase"])
            self.assertIn("manuscript_drafting", committed["allowed_actions"])

    def test_design_material_plan_must_match_exact_f2_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            decision = make_workspace(base)
            write_json(base / rd.DECISION_REL, decision)
            design = {"material_plan": exact_material_plan(base)}
            passed = DesignResult()
            rd3._validate_material_plan(base, design, passed)
            self.assertEqual([], passed.rows)
            design["material_plan"]["time_scope"] = "unbounded future period"
            failed = DesignResult()
            rd3._validate_material_plan(base, design, failed)
            self.assertIn("RD.MATERIAL_PLAN.STALE", {row[0] for row in failed.rows})


class ProbeCliSignatureTests(unittest.TestCase):
    """The controller CLI forwards every probe option as a keyword argument.

    Regression: ``avereth research-materials probe --header-confirmed`` used to
    raise ``TypeError`` because ``probe_command`` lacked the parameter the CLI
    passed, so no probe could be recorded through the controller at all.
    """

    def test_probe_command_accepts_every_cli_forwarded_keyword(self) -> None:
        import inspect

        from avereth_core import cli

        source = inspect.getsource(cli._run_research_material_command)
        call = source[source.index("probe_command(") :]
        call = call[: call.index(")" + chr(10))]
        forwarded = set(re.findall(r"^\s*([a-z_]+)=", call, flags=re.MULTILINE))
        accepted = set(inspect.signature(rm.probe_command).parameters)
        self.assertTrue(forwarded, "expected the CLI to forward keyword arguments to probe_command")
        self.assertLessEqual(forwarded - {"outdir"}, accepted, f"CLI forwards unknown keywords: {sorted(forwarded - accepted)}")
        self.assertIn("header_confirmed", accepted)


if __name__ == "__main__":
    unittest.main()
