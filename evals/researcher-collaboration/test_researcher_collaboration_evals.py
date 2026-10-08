#!/usr/bin/env python3
"""Regression evals for v6.7 risk routing and artifact-only researcher roles."""

from __future__ import annotations

import json
import sys
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "empirical-research" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import researcher_dispatch as dispatch  # noqa: E402


class ResearcherCollaborationEvals(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(
            (Path(__file__).with_name("cases.json")).read_text(encoding="utf-8")
        )["cases"]
        cls.registry = json.loads(
            (
                ROOT
                / "skills"
                / "empirical-research"
                / "references"
                / "method-adapter-registry.json"
            ).read_text(encoding="utf-8")
        )

    def test_risk_routing_cases(self) -> None:
        for case in self.cases:
            with self.subTest(case=case["id"]):
                step = {
                    "id": "STEP-001",
                    "design_id": "DSN-001",
                    "claim_ids": ["CLM-001"],
                    "read_set": ["materials/frozen.json"],
                    "procedure": {"operation": case["operation"]},
                }
                if "researcher_risk" in case:
                    step["researcher_risk"] = case["researcher_risk"]
                design = {
                    "method_routes": [{"id": "DSN-001", "family": case["family"]}],
                    "claims": [{"id": "CLM-001", "type": case["claim_type"]}],
                }
                decision = dispatch.compile_dispatch_decision(
                    step, design, self.registry
                )
                self.assertEqual(case["expected_mode"], decision["mode"])
                self.assertEqual(case["expected_tasks"], decision["task_kinds"])
                self.assertEqual(
                    2 if decision["mode"] == "isolated_multi" else 1,
                    decision["independent_researcher_count"],
                )
                if case.get("expected_trigger"):
                    self.assertIn(case["expected_trigger"], decision["trigger_codes"])

    def test_dispatch_decision_is_deterministic(self) -> None:
        case = self.cases[1]
        step = {
            "id": "STEP-001",
            "design_id": "DSN-001",
            "claim_ids": ["CLM-001"],
            "read_set": ["materials/frozen.json"],
            "procedure": {"operation": case["operation"]},
        }
        design = {
            "method_routes": [{"id": "DSN-001", "family": case["family"]}],
            "claims": [{"id": "CLM-001", "type": case["claim_type"]}],
        }
        first = dispatch.compile_dispatch_decision(step, design, self.registry)
        second = dispatch.compile_dispatch_decision(step, design, self.registry)
        self.assertEqual(dispatch.canonical_digest(first), dispatch.canonical_digest(second))

    def test_researcher_agents_are_artifact_only_and_identity_neutral(self) -> None:
        for name in (
            "avereth_researcher.agent.toml",
            "avereth_adjudicator.agent.toml",
        ):
            with self.subTest(agent=name):
                payload = tomllib.loads(
                    (ROOT / "agent-specs" / name).read_text(encoding="utf-8")
                )
                instructions = payload["instructions"].casefold()
                self.assertIn("avereth-research-artifact/v1", instructions)
                self.assertIn("do not add an identity statement", instructions)
                self.assertIn("do not edit files", instructions)
                self.assertEqual("read_only", payload["permission_profile"])

    def test_extra_narrative_field_is_rejected(self) -> None:
        payload = {
            "schema_version": dispatch.ARTIFACT_SCHEMA,
            "operation_id": "STEP-001",
            "role": "Researcher A",
            "task_kinds": ["independent_coding"],
            "items": [
                {
                    "item_id": "UNIT-001",
                    "label": "included",
                    "evidence_locator": "materials/frozen.json#UNIT-001",
                    "rationale": "The frozen rule applies.",
                    "confidence": 0.9,
                }
            ],
            "identity_statement": "not a research artifact",
        }
        issues, _ = dispatch._validate_research_artifact(
            payload,
            operation_id="STEP-001",
            role="Researcher A",
            task_kinds=["independent_coding"],
            path="artifact:test",
        )
        self.assertIn(
            "ME.RESEARCHER.OUTPUT_NOT_ARTIFACT_ONLY",
            {issue.code for issue in issues},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
