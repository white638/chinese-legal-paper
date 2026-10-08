#!/usr/bin/env python3
"""Focused tests for risk-routed isolated researcher collaboration."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import researcher_dispatch as dispatch


REGISTRY_PATH = Path(__file__).resolve().parent.parent / "references" / "method-adapter-registry.json"


def registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def design_and_step(operation: str, *, claim_type: str = "descriptive") -> tuple[dict, dict]:
    step = {
        "id": "STEP-001",
        "design_id": "DSN-001",
        "claim_ids": ["CLM-001"],
        "read_set": ["materials/units.json"],
        "procedure": {"operation": operation},
    }
    design = {
        "method_routes": [{"id": "DSN-001", "family": "content_analysis"}],
        "claims": [{"id": "CLM-001", "type": claim_type}],
    }
    return design, step


def write_json(base: Path, relative: str, payload: object) -> dict:
    path = base / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {
        "path": relative,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "role": "researcher-test",
    }


def research_output(
    role: str,
    labels: dict[str, str],
    tasks: list[str] | None = None,
) -> dict:
    return {
        "schema_version": dispatch.ARTIFACT_SCHEMA,
        "operation_id": "STEP-001",
        "role": role,
        "task_kinds": tasks or ["independent_coding"],
        "items": [
            {
                "item_id": identifier,
                "label": label,
                "evidence_locator": f"units.json#{identifier}",
                "rationale": f"The frozen rule assigns {label}.",
                "confidence": 0.9,
            }
            for identifier, label in labels.items()
        ],
    }


def valid_collaboration(base: Path) -> tuple[dict, dict, dict, dict, dict]:
    design, step = design_and_step("content_coding")
    active_registry = registry()
    decision = dispatch.compile_dispatch_decision(step, design, active_registry)
    artifacts: dict[str, dict] = {
        "ART-IN": write_json(
            base,
            "materials/units.json",
            {"items": [{"item_id": "I-001"}, {"item_id": "I-002"}]},
        ),
        "ART-A": write_json(base, "repro/a.json", research_output("Researcher A", {"I-001": "X", "I-002": "Y"})),
        "ART-B": write_json(base, "repro/b.json", research_output("Researcher B", {"I-001": "X", "I-002": "Y"})),
        "ART-MET": write_json(
            base,
            "repro/agreement.json",
            {
                "schema_version": dispatch.AGREEMENT_SCHEMA,
                "metric_semantics": "run_consistency",
                "n": 2,
                "percent_agreement": 1.0,
                "krippendorff_alpha_nominal": 1.0,
                "cohen_kappa": 1.0,
                "scott_pi": 1.0,
            },
        ),
        "ART-DIS": write_json(
            base,
            "repro/disagreements.json",
            {"schema_version": dispatch.DISAGREEMENT_SCHEMA, "items": []},
        ),
    }
    for identifier, artifact in artifacts.items():
        artifact["id"] = identifier
    scope = dispatch._scope_digest(["ART-IN"], artifacts)
    protocol = "a" * 64
    collaboration = {
        "schema_version": dispatch.COLLABORATION_SCHEMA,
        "decision_sha256": dispatch.canonical_digest(decision),
        "operation_id": "STEP-001",
        "mode": "isolated_multi",
        "task_kinds": ["independent_coding"],
        "frozen_input_artifact_ids": ["ART-IN"],
        "researcher_runs": [
            {
                "role": role,
                "run_id": run_id,
                "context_id": context_id,
                "model_name": "test-model",
                "model_revision": "2026-08-24",
                "reasoning_effort": "high",
                "prompt_sha256": prompt,
                "protocol_sha256": protocol,
                "input_artifact_ids": ["ART-IN"],
                "input_scope_sha256": scope,
                "output_artifact_id": output,
                "started_at": started,
                "completed_at": completed,
                "blind_to_peer_outputs": True,
                "blind_to_reference_labels": True,
                "sealed_first_output": True,
            }
            for role, run_id, context_id, prompt, output, started, completed in (
                ("Researcher A", "RUN-A", "CTX-A", "b" * 64, "ART-A", "2026-08-24T10:00:00+00:00", "2026-08-24T10:05:00+00:00"),
                ("Researcher B", "RUN-B", "CTX-B", "c" * 64, "ART-B", "2026-08-24T10:00:30+00:00", "2026-08-24T10:06:00+00:00"),
            )
        ],
        "task_records": [
            {
                "task_kind": "independent_coding",
                "status": "complete",
                "input_artifact_ids": ["ART-IN"],
                "output_artifact_ids": ["ART-A", "ART-B", "ART-MET", "ART-DIS"],
                "run_ids": ["RUN-A", "RUN-B"],
                "details": {"unit_manifest_artifact_id": "ART-IN"},
            },
            {
                "task_kind": "agreement_calculation",
                "status": "complete",
                "input_artifact_ids": ["ART-A", "ART-B"],
                "output_artifact_ids": ["ART-MET", "ART-DIS"],
                "run_ids": [],
                "details": {},
            }
        ],
        "agreement": {
            "status": "complete",
            "metric_semantics": "run_consistency",
            "metrics_artifact_id": "ART-MET",
            "disagreement_artifact_id": "ART-DIS",
        },
        "adjudication": {"status": "not_triggered"},
    }
    action = {
        "status": "accepted",
        "input_artifact_ids": ["ART-IN"],
        "output_artifact_ids": ["ART-A", "ART-B", "ART-MET", "ART-DIS"],
        "researcher_collaboration": collaboration,
    }
    return design, step, active_registry, artifacts, action


class ResearcherDispatchTests(unittest.TestCase):
    def test_unmapped_low_risk_operation_remains_single(self) -> None:
        design, step = design_and_step("corpus_freeze")
        decision = dispatch.compile_dispatch_decision(step, design, registry())
        self.assertEqual("single", decision["mode"])
        self.assertEqual([], decision["task_kinds"])

    def test_coding_operation_requires_isolated_researchers(self) -> None:
        design, step = design_and_step("content_coding")
        decision = dispatch.compile_dispatch_decision(step, design, registry())
        self.assertEqual("isolated_multi", decision["mode"])
        self.assertEqual(2, decision["independent_researcher_count"])
        self.assertEqual(["Researcher A", "Researcher B", "Adjudicator"], decision["roles"])

    def test_low_consequence_inference_audit_can_remain_single(self) -> None:
        design, step = design_and_step("content_inference_disposition")
        step["researcher_risk"] = {
            "epistemic_fit": "single_judgment",
            "interpretive_ambiguity": "low",
            "consequence_of_error": "low",
            "codebook_maturity": "not_applicable",
            "reference_basis": "not_applicable",
            "holdout_status": "not_applicable",
            "boundary_case_load": "low",
            "inference_distance": "direct",
            "rationale": "The claim is descriptive and directly read from one registered result.",
        }
        decision = dispatch.compile_dispatch_decision(step, design, registry())
        self.assertEqual("single", decision["mode"])
        self.assertEqual(["inference_audit"], decision["task_kinds"])

    def test_invalid_explicit_risk_is_rejected(self) -> None:
        issues = dispatch.validate_risk_profile(
            {"interpretive_ambiguity": "extreme", "rationale": "x"}
        )
        self.assertIn("RD.RESEARCHER_RISK.INVALID", {issue.code for issue in issues})

    def test_partial_explicit_risk_is_rejected(self) -> None:
        issues = dispatch.validate_risk_profile(
            {"interpretive_ambiguity": "high", "rationale": "Incomplete profile."}
        )
        self.assertIn("RD.RESEARCHER_RISK.INVALID", {issue.code for issue in issues})

    def test_not_applicable_risk_cannot_waive_independent_coding(self) -> None:
        design, step = design_and_step("content_coding")
        step["researcher_risk"] = {
            "epistemic_fit": "not_applicable",
            "interpretive_ambiguity": "low",
            "consequence_of_error": "low",
            "codebook_maturity": "stable",
            "reference_basis": "not_applicable",
            "holdout_status": "not_applicable",
            "boundary_case_load": "low",
            "inference_distance": "direct",
            "rationale": "Independent coding remains an operation-level requirement.",
        }
        decision = dispatch.compile_dispatch_decision(step, design, registry())
        self.assertEqual("isolated_multi", decision["mode"])
        self.assertIn("TASK.REQUIRES_INDEPENDENT_RUNS", decision["trigger_codes"])

    def test_explicit_low_risk_cannot_downgrade_high_consequence_claim(self) -> None:
        design, step = design_and_step(
            "causal_inference_disposition", claim_type="causal_effect"
        )
        step["researcher_risk"] = {
            "epistemic_fit": "single_judgment",
            "interpretive_ambiguity": "low",
            "consequence_of_error": "low",
            "codebook_maturity": "not_applicable",
            "reference_basis": "not_applicable",
            "holdout_status": "not_applicable",
            "boundary_case_load": "low",
            "inference_distance": "direct",
            "rationale": "The explicit profile cannot lower the registered claim-type floor.",
        }
        decision = dispatch.compile_dispatch_decision(step, design, registry())
        self.assertEqual("high", decision["risk_profile"]["consequence_of_error"])
        self.assertEqual("isolated_multi", decision["mode"])
        self.assertIn("RISK.INFERENCE_HIGH_CONSEQUENCE", decision["trigger_codes"])

    def test_valid_multi_researcher_record_recomputes_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertEqual([], issues)

    def test_same_context_and_hash_cannot_masquerade_as_independence(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            record = action["researcher_collaboration"]
            record["researcher_runs"][1]["context_id"] = "CTX-A"
            artifacts["ART-B"]["sha256"] = artifacts["ART-A"]["sha256"]
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertIn("ME.RESEARCHER.NOT_ISOLATED", {issue.code for issue in issues})

    def test_observed_disagreement_requires_separate_adjudication(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            artifacts["ART-B"] = write_json(
                base,
                "repro/b.json",
                research_output("Researcher B", {"I-001": "Z", "I-002": "Y"}),
            )
            artifacts["ART-B"]["id"] = "ART-B"
            artifacts["ART-DIS"] = write_json(
                base,
                "repro/disagreements.json",
                {
                    "schema_version": dispatch.DISAGREEMENT_SCHEMA,
                    "items": [{"item_id": "I-001"}],
                },
            )
            artifacts["ART-DIS"]["id"] = "ART-DIS"
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertIn("ME.RESEARCHER.ADJUDICATION_REQUIRED", {issue.code for issue in issues})

    def test_separate_adjudicator_resolves_exact_disagreement_set(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            artifacts["ART-B"] = write_json(
                base,
                "repro/b.json",
                research_output("Researcher B", {"I-001": "Z", "I-002": "Y"}),
            )
            artifacts["ART-DIS"] = write_json(
                base,
                "repro/disagreements.json",
                {
                    "schema_version": dispatch.DISAGREEMENT_SCHEMA,
                    "items": [{"item_id": "I-001"}],
                },
            )
            metrics = dispatch._nominal_metrics(
                [
                    {"I-001": "X", "I-002": "Y"},
                    {"I-001": "Z", "I-002": "Y"},
                ]
            )
            artifacts["ART-MET"] = write_json(
                base,
                "repro/agreement.json",
                {
                    "schema_version": dispatch.AGREEMENT_SCHEMA,
                    "metric_semantics": "run_consistency",
                    **metrics,
                },
            )
            artifacts["ART-ADJ"] = write_json(
                base,
                "repro/adjudication.json",
                research_output(
                    "Adjudicator",
                    {"I-001": "X"},
                    ["disagreement_adjudication"],
                ),
            )
            for identifier in ("ART-B", "ART-DIS", "ART-MET", "ART-ADJ"):
                artifacts[identifier]["id"] = identifier
            action["output_artifact_ids"].append("ART-ADJ")
            record = action["researcher_collaboration"]
            record["task_records"][0]["output_artifact_ids"].append("ART-ADJ")
            record["task_records"].append(
                {
                    "task_kind": "disagreement_adjudication",
                    "status": "complete",
                    "input_artifact_ids": ["ART-A", "ART-B", "ART-DIS"],
                    "output_artifact_ids": ["ART-ADJ"],
                    "run_ids": ["RUN-ADJ"],
                    "details": {},
                }
            )
            adjudicator_inputs = ["ART-A", "ART-B", "ART-DIS"]
            record["adjudication"] = {
                "status": "complete",
                "unresolved_count": 0,
                "run": {
                    "role": "Adjudicator",
                    "run_id": "RUN-ADJ",
                    "context_id": "CTX-ADJ",
                    "model_name": "test-model",
                    "model_revision": "2026-08-24",
                    "reasoning_effort": "high",
                    "prompt_sha256": "d" * 64,
                    "protocol_sha256": "a" * 64,
                    "input_artifact_ids": adjudicator_inputs,
                    "input_scope_sha256": dispatch._scope_digest(
                        adjudicator_inputs, artifacts
                    ),
                    "output_artifact_id": "ART-ADJ",
                    "started_at": "2026-08-24T10:07:00+00:00",
                    "completed_at": "2026-08-24T10:08:00+00:00",
                    "blind_to_reference_labels": True,
                },
            }
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertEqual([], issues)

    def test_holdout_reference_labels_cannot_enter_researcher_scope(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            step["procedure"]["operation"] = "reference_validation"
            decision = dispatch.compile_dispatch_decision(step, design, active_registry)
            tasks = decision["task_kinds"]
            primary_tasks = [
                task for task in tasks if task not in dispatch.ORCHESTRATION_TASKS
            ]
            artifacts["ART-A"] = write_json(
                base,
                "repro/a.json",
                research_output(
                    "Researcher A", {"I-001": "X", "I-002": "Y"}, primary_tasks
                ),
            )
            artifacts["ART-B"] = write_json(
                base,
                "repro/b.json",
                research_output(
                    "Researcher B", {"I-001": "X", "I-002": "Y"}, primary_tasks
                ),
            )
            artifacts["ART-LABEL"] = write_json(
                base,
                "materials/holdout-labels.json",
                {"items": [{"item_id": "I-001", "reference_label": "X"}]},
            )
            artifacts["ART-REFSET"] = write_json(
                base,
                "repro/reference-set.json",
                {
                    "schema_version": dispatch.REFERENCE_SET_SCHEMA,
                    "items": [{"item_id": "I-001", "reference_label": "X"}],
                },
            )
            for identifier in ("ART-A", "ART-B", "ART-LABEL", "ART-REFSET"):
                artifacts[identifier]["id"] = identifier
            action["input_artifact_ids"] = ["ART-IN", "ART-LABEL"]
            action["output_artifact_ids"].append("ART-REFSET")
            record = action["researcher_collaboration"]
            record["decision_sha256"] = dispatch.canonical_digest(decision)
            record["task_kinds"] = tasks
            record["frozen_input_artifact_ids"] = ["ART-IN", "ART-LABEL"]
            for run in record["researcher_runs"]:
                run["input_artifact_ids"] = ["ART-IN", "ART-LABEL"]
                run["input_scope_sha256"] = dispatch._scope_digest(
                    run["input_artifact_ids"], artifacts
                )
            record["task_records"] = [
                {
                    "task_kind": task,
                    "status": "complete",
                    "input_artifact_ids": ["ART-IN"],
                    "output_artifact_ids": action["output_artifact_ids"],
                    "run_ids": ["RUN-A", "RUN-B"],
                    "details": (
                        {"reference_set_artifact_id": "ART-REFSET"}
                        if task == "reference_set_construction"
                        else {
                            "holdout_manifest_artifact_id": "ART-IN",
                            "reference_labels_artifact_id": "ART-LABEL",
                        }
                        if task == "holdout_validation"
                        else {}
                    ),
                }
                for task in tasks
            ]
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertIn("ME.RESEARCHER.HOLDOUT_LEAKAGE", {issue.code for issue in issues})

    def test_missing_record_blocks_a_risk_routed_accepted_action(self) -> None:
        design, step = design_and_step("content_coding")
        issues = dispatch.validate_collaboration(
            Path.cwd(),
            action={"status": "accepted"},
            step=step,
            design=design,
            registry=registry(),
            artifacts={},
            path="runs[0].actions[0]",
        )
        self.assertEqual("ME.RESEARCHER.COLLABORATION_REQUIRED", issues[0].code)

    def test_missing_required_collaboration_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            design, step, active_registry, artifacts, action = valid_collaboration(base)
            del action["researcher_collaboration"]["agreement"]
            issues = dispatch.validate_collaboration(
                base,
                action=action,
                step=step,
                design=design,
                registry=active_registry,
                artifacts=artifacts,
                path="runs[0].actions[0]",
            )
            self.assertIn(
                "ME.RESEARCHER.COLLABORATION_INCOMPLETE",
                {issue.code for issue in issues},
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
