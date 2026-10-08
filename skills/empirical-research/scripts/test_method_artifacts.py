#!/usr/bin/env python3
"""Adversarial tests for artifact-verified method contracts."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import method_contract_loader
import test_method_execution as fixtures
import validate_method_artifacts


CORE_CONTRACTS_UNDER_EXECUTABLE_TEST = (
    "causal-design/v1",
    "causal-panel/v1",
    "discourse-network/v1",
    "event-history/v1",
    "institutional-grammar/v1",
    "process-tracing/v1",
    "text-alignment/v2",
    "text-as-data/measurement-v2",
    "text-matching/v2",
)


def codes(base, payload) -> set[str]:
    return {
        item.code
        for item in fixtures.method_execution.validate_payload(base, payload).errors
    }


def standalone_codes(base, design, payload) -> set[str]:
    return {
        item.code
        for item in validate_method_artifacts.validate_run_contract(
            base,
            design["method_routes"][0],
            payload["runs"][0],
            path="runs[0]",
        )
        if item.severity == "ERROR"
    }


def artifact(run: dict, identifier: str) -> dict:
    return next(item for item in run["artifacts"] if item["id"] == identifier)


def rewrite(base, run: dict, identifier: str, content: str) -> None:
    item = artifact(run, identifier)
    path = base / item["path"]
    path.write_text(content, encoding="utf-8", newline="")
    item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def claim_measurement_supplement() -> dict:
    return {
        "schema_version": "avereth-public-text-politics/claim-measurement/v2",
        "profile_id": "claim_measurement",
        "construct": {
            "name": "security_frame",
            "definition": (
                "A claim that frames an issue as a threat requiring protective public action."
            ),
            "unit": "claim",
            "codebook_version": "1.2",
            "codebook": "ART-CODEBOOK",
        },
        "corpus": {
            "manifest": "ART-CORPUS",
            "frozen_at": "2026-08-17T00:00:00Z",
        },
        "annotation": {
            "reference_labels": "ART-REFERENCE",
            "sampling_strategy": "stratified by institution and year",
            "reference_runs": [
                {
                    "run_id": "reference-model-01",
                    "context_id": "ctx-reference-01",
                    "model_name": "example-research-model",
                    "model_revision": "rev-a",
                    "output": "ART-REFERENCE-RAW-1",
                    "blind_to_primary": True,
                },
                {
                    "run_id": "reference-model-02",
                    "context_id": "ctx-reference-02",
                    "model_name": "example-research-model",
                    "model_revision": "rev-b",
                    "output": "ART-REFERENCE-RAW-2",
                    "blind_to_primary": True,
                },
            ],
            "run_manifest": "ART-REFERENCE-RUNS",
            "evidence_trace": "ART-REFERENCE-EVIDENCE",
            "independent_review": "ART-REFERENCE-REVIEW",
        },
        "split": {
            "independent_validation": True,
            "grouping_unit": "document_id",
            "development_manifest": "ART-TRAIN",
            "validation_manifest": "ART-TEST",
        },
        "validation": {
            "predictions": "ART-PREDICTIONS",
            "metrics": "ART-METRICS",
            "error_analysis": "ART-ERRORS",
            "sensitivity": "ART-MEAS-SENS",
            "class_metrics_required": True,
        },
        "interpretation": {
            "allowed": ["Report validated claim-level frame prevalence."],
            "prohibited": ["Treat predictions as unqualified ground truth."],
        },
    }


def public_text_workspace():
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    design = fixtures.confirmed_design("text_as_data")
    route = design["method_routes"][0]
    route["supplemental_profile_id"] = "claim_measurement"
    route["supplemental_contract"] = claim_measurement_supplement()
    route["artifact_refs"] = [
        "ART-CODEBOOK",
        "ART-CORPUS",
        "ART-REFERENCE",
        "ART-REFERENCE-RAW-1",
        "ART-REFERENCE-RAW-2",
        "ART-REFERENCE-RUNS",
        "ART-REFERENCE-EVIDENCE",
        "ART-REFERENCE-REVIEW",
        "ART-TRAIN",
        "ART-TEST",
        "ART-PREDICTIONS",
        "ART-METRICS",
        "ART-ERRORS",
        "ART-MEAS-SENS",
    ]
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    payload = fixtures.complete_execution(base, design)
    return temporary, base, design, payload


class ArtifactVerifiedMethodTests(unittest.TestCase):
    def test_declared_core_contract_coverage_matches_the_sole_registry(self) -> None:
        registry_contracts = set(
            fixtures.method_execution.load_registry()["method_contracts"]
        )
        self.assertEqual(
            registry_contracts,
            set(CORE_CONTRACTS_UNDER_EXECUTABLE_TEST),
        )
        self.assertEqual(
            len(CORE_CONTRACTS_UNDER_EXECUTABLE_TEST),
            len(set(CORE_CONTRACTS_UNDER_EXECUTABLE_TEST)),
        )

    def test_design_phase_executes_nested_core_schema_rules(self) -> None:
        temporary, base, design, _ = public_text_workspace()
        with temporary:
            result = fixtures.research_design.validate_payload(base, design, stage="design")
            self.assertFalse(
                {
                    item.code
                    for item in result.errors
                    if item.code.startswith("RD.METHOD_CONTRACT.SCHEMA_")
                }
            )
            malformed = copy.deepcopy(design)
            del malformed["method_routes"][0]["method_contract"]["construct"]["definition"]
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, malformed, stage="design"
                ).errors
            }
            self.assertIn("RD.METHOD_CONTRACT.SCHEMA_REQUIRED", observed)
            malformed = copy.deepcopy(design)
            malformed["method_routes"][0]["method_contract"]["construct"]["unit"] = [
                "claim"
            ]
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, malformed, stage="design"
                ).errors
            }
            self.assertIn("RD.METHOD_CONTRACT.SCHEMA_TYPE", observed)

    def test_design_phase_executes_core_enum_and_nested_required_rules(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        with temporary:
            base = Path(temporary.name)
            design = fixtures.confirmed_design("content_analysis")
            route = design["method_routes"][0]
            route.update(
                {
                    "method_contract_schema": "text-alignment/v2",
                    "method_contract_revision": "1",
                    "method_profile": "semantic-alignment",
                    "method_contract": {
                        "alignment_unit": "clause-pair",
                        "direction_rule": "future-source-causes-past-target",
                        "boilerplate_policy": "remove registered templates",
                        "third_source_policy": "audit shared upstream sources",
                        "translation_policy": "register translation chain",
                        "threshold_plan": {"selection_basis": "source-grounded reference pairs"},
                    },
                    "artifact_refs": [],
                }
            )
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn("RD.METHOD_CONTRACT.SCHEMA_ENUM", observed)
            self.assertIn("RD.METHOD_CONTRACT.SCHEMA_REQUIRED", observed)

    def test_public_text_supplement_runs_through_core_runtime(self) -> None:
        temporary, base, design, payload = public_text_workspace()
        with temporary:
            design_codes = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertFalse({code for code in design_codes if code.startswith("PTP.")})
            self.assertNotIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_ARTIFACT_REF_MISSING",
                design_codes,
            )
            self.assertEqual(set(), codes(base, payload))

    def test_public_text_supplement_rejects_schema_and_authority_overreach(self) -> None:
        temporary, base, _, payload = public_text_workspace()
        with temporary:
            run = payload["runs"][0]
            run["supplemental_contract"]["annotation"]["reference_runs"][1][
                "blind_to_primary"
            ] = False
            self.assertIn("PTP.CLAIM.SELF_VALIDATION", codes(base, payload))
            for reserved_key in sorted(method_contract_loader.RESERVED_SUPPLEMENTAL_KEYS):
                with self.subTest(reserved_key=reserved_key):
                    run["supplemental_contract"] = claim_measurement_supplement()
                    run["supplemental_contract"][reserved_key] = "rogue override"
                    self.assertIn(
                        "ME.SUPPLEMENTAL.RESERVED_AUTHORITY",
                        codes(base, payload),
                    )

    def test_supplemental_registry_entry_cannot_register_a_validator(self) -> None:
        registry = copy.deepcopy(method_contract_loader.load_registry())
        entry = registry["method_contracts"]["text-as-data/measurement-v2"][
            "supplemental_profiles"
        ][0]
        entry["validator"] = "rogue_supplemental_dispatch"
        with self.assertRaises(method_contract_loader.ContractLoaderError):
            method_contract_loader.supplemental_profile(
                registry,
                "text-as-data/measurement-v2",
                "1",
                "claim_measurement",
            )

    def test_supplemental_profile_must_map_globally_to_one_core(self) -> None:
        registry = copy.deepcopy(method_contract_loader.load_registry())
        duplicate = copy.deepcopy(
            registry["method_contracts"]["text-as-data/measurement-v2"][
                "supplemental_profiles"
            ][0]
        )
        registry["method_contracts"]["text-alignment/v2"][
            "supplemental_profiles"
        ].append(duplicate)
        with self.assertRaises(method_contract_loader.ContractLoaderError):
            method_contract_loader.supplemental_profile_binding(
                registry,
                "claim_measurement",
            )

    def test_unregistered_supplemental_profile_fails_closed(self) -> None:
        temporary, base, _, payload = public_text_workspace()
        with temporary:
            payload["runs"][0]["supplemental_profile_id"] = "rogue_profile"
            self.assertIn(
                "ME.SUPPLEMENTAL.PROFILE_UNREGISTERED",
                codes(base, payload),
            )

    def test_public_text_supplement_requires_registered_artifact_ids(self) -> None:
        temporary, base, _, payload = public_text_workspace()
        with temporary:
            payload["runs"][0]["artifact_refs"].remove("ART-CODEBOOK")
            self.assertIn(
                "ME.SUPPLEMENTAL.ARTIFACT_REF_MISSING",
                codes(base, payload),
            )

    def test_supplemental_schema_id_cannot_replace_core_contract_id(self) -> None:
        temporary, base, design, payload = public_text_workspace()
        with temporary:
            supplemental_schema_id = (
                "avereth-public-text-politics/claim-measurement/v2"
            )
            design["method_routes"][0]["method_contract_schema"] = supplemental_schema_id
            design_observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn("RD.METHOD_CONTRACT.SCHEMA_UNKNOWN", design_observed)
            payload["runs"][0]["method_contract_schema"] = supplemental_schema_id
            self.assertIn("ME.CONTRACT.SCHEMA_UNKNOWN", codes(base, payload))

    def test_design_supplemental_requires_registered_core_before_early_return(self) -> None:
        temporary, base, design, _ = public_text_workspace()
        with temporary:
            route = design["method_routes"][0]
            route["method_contract_schema"] = ""
            route["method_contract_revision"] = ""
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_CORE_MISSING",
                observed,
            )
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_CORE_REVISION_MISSING",
                observed,
            )
            route["method_contract_schema"] = "text-alignment/v2"
            route["method_contract_revision"] = "1"
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_CORE_MISMATCH",
                observed,
            )

    def test_execution_supplemental_requires_registered_core_before_early_return(self) -> None:
        temporary, base, design, payload = public_text_workspace()
        with temporary:
            run = payload["runs"][0]
            run["method_contract_schema"] = ""
            run["method_contract_revision"] = ""
            observed = standalone_codes(base, design, payload)
            self.assertIn("ME.SUPPLEMENTAL.CORE_MISSING", observed)
            self.assertIn("ME.SUPPLEMENTAL.CORE_REVISION_MISSING", observed)
            run["method_contract_schema"] = "text-alignment/v2"
            run["method_contract_revision"] = "1"
            self.assertIn(
                "ME.SUPPLEMENTAL.CORE_MISMATCH",
                standalone_codes(base, design, payload),
            )

    def test_supplemental_contract_only_cannot_bypass_design_early_return(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            design = fixtures.confirmed_design("content_analysis")
            route = design["method_routes"][0]
            route.pop("supplemental_profile_id", None)
            route["method_contract_schema"] = ""
            route["method_contract_revision"] = ""
            route["supplemental_contract"] = {"rogue": "ignored"}
            observed = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_PROFILE_MISSING", observed
            )
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_CORE_MISSING", observed
            )
            self.assertIn(
                "RD.METHOD_CONTRACT.SUPPLEMENTAL_CORE_REVISION_MISSING",
                observed,
            )

    def test_supplemental_contract_only_cannot_bypass_any_execution_early_return(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            route = {
                "family": "content_analysis",
                "method_contract_schema": "",
                "method_contract_revision": "",
                "method_contract": {},
                "artifact_refs": [],
                "supplemental_contract": {"rogue": "ignored"},
            }
            for status in ("complete", "not-applicable", "withdrawn"):
                with self.subTest(status=status):
                    run = {
                        "status": status,
                        "method_contract_schema": "",
                        "method_contract_revision": "",
                        "method_contract": {},
                        "artifact_refs": [],
                        "supplemental_contract": {"rogue": "ignored"},
                    }
                    observed = {
                        item.code
                        for item in validate_method_artifacts.validate_run_contract(
                            base,
                            route,
                            run,
                            path="runs[0]",
                        )
                        if item.severity == "ERROR"
                    }
                    self.assertIn(
                        "ME.SUPPLEMENTAL.DESIGN_PROFILE_MISSING", observed
                    )
                    self.assertIn("ME.SUPPLEMENTAL.PROFILE_MISSING", observed)
                    self.assertIn(
                        "ME.SUPPLEMENTAL.DESIGN_CORE_MISSING", observed
                    )
                    self.assertIn("ME.SUPPLEMENTAL.CORE_MISSING", observed)

    def test_supplemental_core_presence_is_encoded_in_both_schemas(self) -> None:
        design_schema = json.loads(
            fixtures.research_design.SCHEMA_ASSET_PATH_V3.read_text(encoding="utf-8")
        )
        execution_schema = json.loads(
            fixtures.method_execution.SCHEMA_ASSET_PATH_V2.read_text(encoding="utf-8")
        )
        design_then = design_schema["properties"]["method_routes"]["items"][
            "allOf"
        ][0]["then"]
        execution_then = execution_schema["$defs"]["run"]["allOf"][0]["then"]
        expected = {
            "supplemental_profile_id",
            "method_contract_schema",
            "method_contract_revision",
        }
        self.assertTrue(expected.issubset(set(design_then["required"])))
        self.assertTrue(expected.issubset(set(execution_then["required"])))
        design_triggers = design_schema["properties"]["method_routes"]["items"][
            "allOf"
        ][0]["if"]["anyOf"]
        execution_triggers = execution_schema["$defs"]["run"]["allOf"][0][
            "if"
        ]["anyOf"]
        self.assertIn({"required": ["supplemental_contract"]}, design_triggers)
        self.assertIn({"required": ["supplemental_contract"]}, execution_triggers)

    def test_valid_text_measurement_recomputes(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            self.assertEqual(set(), codes(base, payload))

    def test_standalone_validator_rejects_tampered_predictions_hash(self) -> None:
        temporary, base, design, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            prediction = artifact(run, "ART-PREDICTIONS")
            (base / prediction["path"]).write_text(
                "item_id,reference_label,predicted\nT1,A,A\n",
                encoding="utf-8",
            )
            self.assertIn(
                "ME.ARTIFACT.HASH_CHANGED",
                standalone_codes(base, design, payload),
            )

    def test_standalone_validator_rejects_tampered_metrics_hash(self) -> None:
        temporary, base, design, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            metrics = artifact(run, "ART-METRICS")
            (base / metrics["path"]).write_text(
                '{"n": 999, "metric_semantics": "reference_agreement", "agreement_rate": 1.0}\n',
                encoding="utf-8",
            )
            self.assertIn(
                "ME.ARTIFACT.HASH_CHANGED",
                standalone_codes(base, design, payload),
            )

    def test_free_text_cannot_replace_measurement_artifacts(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            run["method_contract"] = {"validation_results": "模型表现可靠"}
            observed = codes(base, payload)
            self.assertIn("ME.MEASUREMENT.CORPUS_MISSING", observed)
            self.assertIn("ME.MEASUREMENT.VALIDATION_MISSING", observed)

    def test_item_and_document_leakage_are_blocked(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            rewrite(
                base,
                run,
                "ART-TRAIN",
                "item_id,document_id\nT1,D1\nR2,D3\n",
            )
            observed = codes(base, payload)
            self.assertIn("ME.MEASUREMENT.SPLIT_OVERLAP", observed)
            self.assertIn("ME.MEASUREMENT.GROUP_LEAKAGE", observed)

    def test_metrics_are_recomputed_from_predictions(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            declared = {
                "n": 4,
                "metric_semantics": "reference_agreement",
                "agreement_rate": 0.99,
                "macro_f1": 0.99,
                "micro_f1": 0.99,
                "confusion_matrix": {"A": {"A": 2, "B": 0}, "B": {"A": 0, "B": 2}},
                "per_class": {
                    "A": {"support": 2, "precision": 0.99, "recall": 0.99, "f1": 0.99},
                    "B": {"support": 2, "precision": 0.99, "recall": 0.99, "f1": 0.99},
                },
            }
            rewrite(base, run, "ART-METRICS", json.dumps(declared) + "\n")
            self.assertIn("ME.MEASUREMENT.METRIC_MISMATCH", codes(base, payload))

    def test_accuracy_only_cannot_hide_minority_classes(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            rewrite(
                base,
                run,
                "ART-METRICS",
                json.dumps({"n": 4, "metric_semantics": "reference_agreement", "agreement_rate": 0.75, "macro_f1": 0.7333333333333334, "micro_f1": 0.75, "confusion_matrix": {"A": {"A": 1, "B": 1}, "B": {"A": 0, "B": 2}}}) + "\n",
            )
            self.assertIn("ME.MEASUREMENT.CLASS_METRICS_MISSING", codes(base, payload))

    def test_low_but_consistent_metrics_do_not_trigger_universal_cutoff(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            rewrite(
                base,
                run,
                "ART-PREDICTIONS",
                "item_id,reference_label,predicted\nT1,A,B\nT2,B,A\nT3,A,B\nT4,B,A\n",
            )
            declared = {
                "n": 4,
                "metric_semantics": "reference_agreement",
                "agreement_rate": 0.0,
                "macro_f1": 0.0,
                "micro_f1": 0.0,
                "confusion_matrix": {
                    "A": {"A": 0, "B": 2},
                    "B": {"A": 2, "B": 0},
                },
                "per_class": {
                    "A": {"support": 2, "precision": 0.0, "recall": 0.0, "f1": 0.0},
                    "B": {"support": 2, "precision": 0.0, "recall": 0.0, "f1": 0.0},
                },
            }
            rewrite(base, run, "ART-METRICS", json.dumps(declared) + "\n")
            self.assertEqual(set(), codes(base, payload))

    def test_incomplete_researcher_run_record_is_blocked(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            payload["runs"][0]["method_contract"]["researcher_run"] = {
                "model_name": "example-model"
            }
            self.assertIn("ME.MEASUREMENT.RESEARCHER_RUN_INCOMPLETE", codes(base, payload))

    def test_primary_run_cannot_serve_as_its_own_reference(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            contract = payload["runs"][0]["method_contract"]
            contract["researcher_run"]["run_id"] = "reference-model-01"
            self.assertIn("ME.MEASUREMENT.REVIEW_NOT_INDEPENDENT", codes(base, payload))

    def test_model_researcher_contract_has_no_human_identity_gate(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            contract = payload["runs"][0]["method_contract"]
            serialized = json.dumps(contract, ensure_ascii=False).casefold()
            self.assertNotIn("human_", serialized)
            self.assertNotIn("identity_type", serialized)
            self.assertEqual(set(), codes(base, payload))

    def test_empty_reference_and_prediction_artifacts_fail_closed(self) -> None:
        cases = (
            (
                "ART-REFERENCE",
                "item_id,reference_label,evidence_locator,review_run_id,confidence,disagreement_status\n",
                "ME.MEASUREMENT.REFERENCE_SCHEMA",
            ),
            (
                "ART-PREDICTIONS",
                "item_id,reference_label,predicted\n",
                "ME.MEASUREMENT.PREDICTION_SCHEMA",
            ),
        )
        for identifier, content, expected in cases:
            with self.subTest(identifier=identifier):
                temporary, base, _, payload = fixtures.workspace("text_as_data")
                with temporary:
                    rewrite(base, payload["runs"][0], identifier, content)
                    self.assertIn(expected, codes(base, payload))

    def test_reference_and_prediction_identity_sets_fail_closed(self) -> None:
        cases = (
            (
                "ART-REFERENCE",
                "item_id,reference_label,evidence_locator,review_run_id,confidence,disagreement_status\n"
                "T1,A,corpus:T1,reference-model-01,0.9,no-disagreement\n"
                "T1,A,corpus:T1,reference-model-01,0.9,no-disagreement\n"
                "T3,A,corpus:T3,reference-model-02,0.9,resolved\n"
                "T4,B,corpus:T4,reference-model-02,0.9,no-disagreement\n",
                "ME.MEASUREMENT.REFERENCE_DUPLICATE",
            ),
            (
                "ART-PREDICTIONS",
                "item_id,reference_label,predicted\nT1,A,A\nT1,A,A\nT3,A,B\nT4,B,B\n",
                "ME.MEASUREMENT.PREDICTION_DUPLICATE",
            ),
            (
                "ART-PREDICTIONS",
                "item_id,reference_label,predicted\nT1,A,A\nT2,B,B\nT3,A,B\nT5,B,B\n",
                "ME.MEASUREMENT.TEST_COUNT_MISMATCH",
            ),
        )
        for identifier, content, expected in cases:
            with self.subTest(identifier=identifier, expected=expected):
                temporary, base, _, payload = fixtures.workspace("text_as_data")
                with temporary:
                    rewrite(base, payload["runs"][0], identifier, content)
                    self.assertIn(expected, codes(base, payload))

    def test_reference_provenance_overlap_is_blocked(self) -> None:
        scenarios = ("context", "blind", "output-id", "output-hash", "reference-artifact")
        for scenario in scenarios:
            with self.subTest(scenario=scenario):
                temporary, base, _, payload = fixtures.workspace("text_as_data")
                with temporary:
                    run = payload["runs"][0]
                    contract = run["method_contract"]
                    expected = "ME.MEASUREMENT.REVIEW_NOT_INDEPENDENT"
                    if scenario == "context":
                        contract["researcher_run"]["context_id"] = "ctx-reference-01"
                    elif scenario in {"blind", "output-id", "reference-artifact"}:
                        manifest_item = artifact(run, "ART-REFERENCE-RUNS")
                        manifest = json.loads(
                            (base / manifest_item["path"]).read_text(encoding="utf-8")
                        )
                        if scenario == "blind":
                            manifest["runs"][0]["blind_to_primary_output"] = False
                            expected = "ME.MEASUREMENT.REFERENCE_RUN_NOT_INDEPENDENT"
                        elif scenario == "output-id":
                            manifest["runs"][0]["output_artifact_id"] = "ART-PREDICTIONS"
                            expected = "ME.MEASUREMENT.SELF_VALIDATION"
                        else:
                            manifest["runs"][0]["output_artifact_id"] = "ART-REFERENCE"
                            expected = "ME.MEASUREMENT.PROVENANCE_OVERLAP"
                        rewrite(
                            base,
                            run,
                            "ART-REFERENCE-RUNS",
                            json.dumps(manifest) + "\n",
                        )
                    else:
                        prediction_item = artifact(run, "ART-PREDICTIONS")
                        prediction_content = (base / prediction_item["path"]).read_text(
                            encoding="utf-8"
                        )
                        rewrite(base, run, "ART-REFERENCE-RAW-1", prediction_content)
                        expected = "ME.MEASUREMENT.SELF_VALIDATION"
                    self.assertIn(expected, codes(base, payload))

    def test_reference_must_be_frozen_before_primary_evaluation(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            contract = payload["runs"][0]["method_contract"]
            contract["researcher_run"]["run_date"] = contract["reference_standard"][
                "frozen_at"
            ]
            self.assertIn("ME.MEASUREMENT.REVIEW_NOT_FROZEN", codes(base, payload))

    def test_model_reference_cannot_be_reported_as_accuracy(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            metrics_item = artifact(run, "ART-METRICS")
            declared = json.loads(
                (base / metrics_item["path"]).read_text(encoding="utf-8")
            )
            declared["accuracy"] = declared["agreement_rate"]
            rewrite(base, run, "ART-METRICS", json.dumps(declared) + "\n")
            self.assertIn("ME.MEASUREMENT.FALSE_ACCURACY", codes(base, payload))

        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            run["method_contract"]["reference_standard"]["metric_semantics"] = (
                "external_accuracy"
            )
            metrics_item = artifact(run, "ART-METRICS")
            declared = json.loads(
                (base / metrics_item["path"]).read_text(encoding="utf-8")
            )
            declared["metric_semantics"] = "external_accuracy"
            declared["accuracy"] = declared.pop("agreement_rate")
            rewrite(base, run, "ART-METRICS", json.dumps(declared) + "\n")
            self.assertIn("ME.MEASUREMENT.FALSE_ACCURACY", codes(base, payload))

    def test_reference_manifest_and_evidence_are_structurally_bound(self) -> None:
        cases = ("manifest-context", "evidence-locator", "low-confidence", "unresolved")
        for scenario in cases:
            with self.subTest(scenario=scenario):
                temporary, base, _, payload = fixtures.workspace("text_as_data")
                with temporary:
                    run = payload["runs"][0]
                    if scenario == "manifest-context":
                        item = artifact(run, "ART-REFERENCE-RUNS")
                        manifest = json.loads(
                            (base / item["path"]).read_text(encoding="utf-8")
                        )
                        del manifest["runs"][0]["context_id"]
                        rewrite(base, run, "ART-REFERENCE-RUNS", json.dumps(manifest) + "\n")
                        expected = "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID"
                    elif scenario == "evidence-locator":
                        rewrite(
                            base,
                            run,
                            "ART-REFERENCE-EVIDENCE",
                            "item_id,source_artifact_id,evidence_locator,rationale,codebook_version\n"
                            "T1,ART-CORPUS,,registered rationale,1.0\n"
                            "T2,ART-CORPUS,corpus:T2,registered rationale,1.0\n"
                            "T3,ART-CORPUS,corpus:T3,registered rationale,1.0\n"
                            "T4,ART-CORPUS,corpus:T4,registered rationale,1.0\n",
                        )
                        expected = "ME.MEASUREMENT.REFERENCE_EVIDENCE_INVALID"
                    else:
                        reference_item = artifact(run, "ART-REFERENCE")
                        content = (base / reference_item["path"]).read_text(encoding="utf-8")
                        if scenario == "low-confidence":
                            content = content.replace(
                                "T1,A,corpus:T1,reference-model-01,0.98,no-disagreement",
                                "T1,A,corpus:T1,reference-model-01,0.50,no-disagreement",
                            )
                        else:
                            content = content.replace(
                                "T1,A,corpus:T1,reference-model-01,0.98,no-disagreement",
                                "T1,A,corpus:T1,reference-model-01,0.98,unresolved",
                            )
                        rewrite(base, run, "ART-REFERENCE", content)
                        expected = "ME.MEASUREMENT.REFERENCE_REVIEW_UNRESOLVED"
                    self.assertIn(expected, codes(base, payload))

    def test_active_contract_assets_have_no_human_identity_gate(self) -> None:
        registry = method_contract_loader.load_registry()
        active_assets: set[Path] = set()
        for spec in registry["method_contracts"].values():
            active_assets.add(method_contract_loader.EMPIRICAL_ROOT / spec["asset"])
            for supplemental in spec.get("supplemental_profiles", []):
                active_assets.add(
                    method_contract_loader.EMPIRICAL_ROOT / supplemental["schema_asset"]
                )
                active_assets.add(
                    method_contract_loader.EMPIRICAL_ROOT / supplemental["profile_asset"]
                )
        forbidden = (
            "human_reference",
            "human_validation",
            "human_gold",
            "needs-human-review",
            "llm_run-not-human",
        )
        for path in sorted(active_assets):
            with self.subTest(path=path.name):
                content = path.read_text(encoding="utf-8-sig").casefold()
                self.assertFalse(
                    [token for token in forbidden if token in content],
                    path.as_posix(),
                )

    def test_retired_v1_contract_requires_explicit_migration(self) -> None:
        temporary, base, design, payload = fixtures.workspace("text_as_data")
        with temporary:
            route = design["method_routes"][0]
            route["method_contract_schema"] = "text-as-data/measurement-v1"
            design_codes = {
                item.code
                for item in fixtures.research_design.validate_payload(
                    base, design, stage="design"
                ).errors
            }
            self.assertIn("RD.METHOD_CONTRACT.MIGRATION_REQUIRED", design_codes)
            payload["runs"][0]["method_contract_schema"] = (
                "text-as-data/measurement-v1"
            )
            self.assertIn(
                "ME.CONTRACT.MIGRATION_REQUIRED",
                standalone_codes(base, design, payload),
            )

    def test_every_validity_dimension_is_explicit(self) -> None:
        temporary, base, _, payload = fixtures.workspace("text_as_data")
        with temporary:
            run = payload["runs"][0]
            validity = json.loads(
                (base / artifact(run, "ART-MEAS-VALIDITY")["path"]).read_text(encoding="utf-8")
            )
            validity["dimensions"].pop("language")
            rewrite(base, run, "ART-MEAS-VALIDITY", json.dumps(validity) + "\n")
            self.assertIn(
                "ME.MEASUREMENT.VALIDITY_DIMENSION_MISSING",
                codes(base, payload),
            )

    def test_causal_effect_requires_estimand_and_counterfactual(self) -> None:
        temporary, base, _, payload = fixtures.workspace("experiment")
        with temporary:
            payload["runs"][0]["method_contract"] = {
                "estimate_artifact_id": "ART-ESTIMATE",
                "sensitivity_artifact_id": "ART-SENSITIVITY",
            }
            observed = codes(base, payload)
            self.assertIn("ME.INFERENCE.ESTIMAND_MISSING", observed)
            self.assertIn("ME.INFERENCE.COUNTERFACTUAL_MISSING", observed)

    def test_failed_identification_diagnostic_requires_narrowing(self) -> None:
        temporary, base, _, payload = fixtures.workspace("experiment")
        with temporary:
            payload["runs"][0]["method_contract"]["identification_assumptions"][0][
                "status"
            ] = "failed"
            self.assertIn(
                "ME.INFERENCE.DIAGNOSTIC_FAILED_NOT_NARROWED",
                codes(base, payload),
            )
            payload["runs"][0]["inference_ceiling_observed"] = (
                "descriptive comparison only after failed diagnostic"
            )
            payload["runs"][0]["inference_disposition"].update(
                {
                    "status": "narrowed",
                    "reason_codes": ["IDENTIFICATION_DIAGNOSTIC_FAILED"],
                    "failed_diagnostic_ids": ["ASM-001"],
                }
            )
            self.assertNotIn(
                "ME.INFERENCE.DIAGNOSTIC_FAILED_NOT_NARROWED",
                codes(base, payload),
            )

    def test_sentence_count_cannot_replace_independence_unit(self) -> None:
        temporary, base, _, payload = fixtures.workspace("experiment")
        with temporary:
            payload["runs"][0]["method_contract"]["effective_sample_size"] = {
                "n": 1000,
                "unit": "sentence",
            }
            self.assertIn("ME.INFERENCE.PSEUDO_REPLICATION", codes(base, payload))

    def test_process_tracing_must_test_strongest_rival(self) -> None:
        temporary, base, _, payload = fixtures.workspace("process_tracing")
        with temporary:
            run = payload["runs"][0]
            rewrite(
                base,
                run,
                "ART-MECHANISM",
                (
                    "mechanism_node,theoretical_prediction,observation,diagnosticity,competing_mechanism,source_id\n"
                    "node-1,predicted,observed,weak,a different rival,SRC-001\n"
                ),
            )
            self.assertIn("ME.PROCESS_TRACING.RIVAL_UNTESTED", codes(base, payload))

    def test_registered_number_requires_locator_and_reproduction_command(self) -> None:
        temporary, base, _, payload = fixtures.workspace("quantitative")
        with temporary:
            result = payload["runs"][0]["results"][0]
            result["numeric_values"] = [
                {
                    "value": "42",
                    "evidence_id": result["evidence_ids"][0],
                    "artifact_id": "ART-001",
                }
            ]
            self.assertIn("ME.NUMBER.NOT_RECOMPUTABLE", codes(base, payload))

    def test_json_locator_reproduces_registered_number(self) -> None:
        temporary, base, _, payload = fixtures.workspace("quantitative")
        with temporary:
            run = payload["runs"][0]
            item = artifact(run, "ART-001")
            path = base / "artifacts" / "numbers.json"
            path.write_text('{"estimate":42}\n', encoding="utf-8")
            item["path"] = path.relative_to(base).as_posix()
            item["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            result = run["results"][0]
            result["numeric_values"] = [
                {
                    "value": 42,
                    "evidence_id": result["evidence_ids"][0],
                    "artifact_id": "ART-001",
                    "locator": "json:/estimate",
                    "reproduction_command": "python reproduce.py",
                }
            ]
            self.assertEqual(set(), codes(base, payload))
            result["numeric_values"][0]["value"] = 41
            self.assertIn("ME.NUMBER.VALUE_MISMATCH", codes(base, payload))


if __name__ == "__main__":
    unittest.main()
