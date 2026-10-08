#!/usr/bin/env python3
"""Regression tests for cnki-method-execution/v1 and v2."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CNKI_SCRIPTS = REPO / "skills" / "cnki-paper" / "scripts"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


research_design = load_module("research_design_for_method_execution", CNKI_SCRIPTS / "research_design.py")
v2 = research_design._v2_module()
v3 = research_design._v3_module()
method_execution = load_module("method_execution_under_test", HERE / "method_execution.py")


def _replace_review(value):
    if isinstance(value, dict):
        return {key: _replace_review(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_review(item) for item in value]
    if isinstance(value, str) and value.startswith("needs-review"):
        return "已记录实际步骤、版本、适用边界与可复核位置。"
    return value


def confirmed_design(family: str) -> dict:
    payload = _replace_review(copy.deepcopy(v3.template_payload(family, v2)))
    payload["status"] = "confirmed"
    payload["research_questions"][0]["confirmation"] = {
        "status": "confirmed",
        "source": "user-message-2026-07-29",
        "confirmed_at": "2026-07-29T10:00:00+08:00",
    }
    route = payload["method_routes"][0]
    route["permissions"] = {
        "status": "public" if route["empirical"] else "not-required",
        "note": "材料权限与用途已经登记。",
    }
    route["ethics"] = {
        "status": "not-required",
        "note": "没有可识别个人或干预；边界变化时重新审查。",
    }
    route["reproducibility"] = {
        "status": "ready",
        "note": "版本、参数与复现命令均已冻结。",
    }
    route["evidence_separation"] = {
        "status": "separated",
        "note": "探索、建构和验证材料已经分离。",
    }
    route["sampling_or_selection"] = {
        "strategy": "按预先登记的纳入与排除规则选择。",
        "rationale": "选择逻辑对应问题并披露未覆盖对象。",
    }
    route["artifact_paths"] = {}
    case_design = payload["case_design"]
    if family == "historical":
        payload["case_design"] = copy.deepcopy(v3._case_design_template("normative"))
        case_design = payload["case_design"]
        case_design["rationale"] = "本历史研究不采用案例导向比较剖面。"
    elif case_design["applicability"] == "active":
        for case in case_design["cases"]:
            case["outcome_knowledge_at_selection"] = "unknown"
            for role in case["material_roles"]:
                role["independence"] = "separated"
    fields = route["method_fields"]
    if family == "quantitative":
        fields["task_type"] = "descriptive"
    elif family == "survey":
        fields["modes"] = ["questionnaire"]
    elif family == "review":
        fields["review_type"] = "narrative"
        fields["reporting_standard"] = "完整披露叙述式综述的检索与综合边界。"
    elif family == "experiment":
        fields["assignment_mechanism"] = "按入组顺序机械分配，不使用概率机制。"
        fields["randomization_verification"] = "分配记录表保留执行人、顺序和时间戳。"
    for declaration in payload["governance"].values():
        declaration["status"] = "declared"
        declaration["note"] = "已作出明确披露并保留审计记录。"
    payload["concepts"][0]["measurement"] = {
        "status": "documented",
        "note": "识别规则、误差来源和不适用条件已经记录。",
    }
    return payload


def complete_execution(base: Path, design: dict) -> dict:
    payload = copy.deepcopy(method_execution.scaffold_payload(design))
    payload["status"] = "complete"
    route = design["method_routes"][0]
    adapter = method_execution.load_registry()["families"][route["family"]]
    artifact_path = base / "artifacts" / f"{route['family']}.txt"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("registered execution artifact\n", encoding="utf-8")
    run = payload["runs"][0]
    run["status"] = "completed"
    run["actions"] = ["按登记方案执行分析并保存逐步日志。"]
    run["method_fields"] = {
        field: "已记录实际步骤、版本、结果与可复核位置。"
        for field in adapter["execution_fields"]
    }
    claim_type = design["claims"][0]["type"]
    run["artifacts"] = [
        {
            "id": "ART-001",
            "path": artifact_path.relative_to(base).as_posix(),
            "sha256": hashlib.sha256(artifact_path.read_bytes()).hexdigest(),
            "role": "结果与执行日志",
        }
    ]

    def register_artifact(identifier: str, name: str, content: str, role: str) -> str:
        path = base / "artifacts" / name
        path.write_text(content, encoding="utf-8", newline="")
        run["artifacts"].append(
            {
                "id": identifier,
                "path": path.relative_to(base).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "role": role,
            }
        )
        return identifier
    run["results"] = [
        {
            "id": "RES-001",
            "text": "在登记材料边界内得到与预定主张类型一致的结果。",
            "type": claim_type,
            "claim_ids": list(route["claim_ids"]),
            "evidence_ids": list(route["evidence_ids"]),
            "artifact_ids": ["ART-001"],
            "status": "supported",
            "allowed_interpretation": "仅限登记材料与时间范围内的描述。",
            "prohibited_interpretation": "不得解释为总体规律或因果效应。",
            "numeric_values": [],
            "case_ids": list(run["case_ids"]),
            "scope_condition_ids": list(run["scope_condition_ids"]),
            "comparison_ids": list(run["comparison_ids"]),
            "within_case_analysis_ids": list(run["within_case_analysis_ids"]),
        }
    ]
    case_execution = run["case_execution"]
    if case_execution["applicability"] == "active":
        case_execution["negative_case_review_status"] = "reviewed-none"
        case_execution["contradictory_result_status"] = "reviewed-none"
        case_execution["scope_review_status"] = "reviewed-none"
        if route["family"] == "process_tracing":
            case_execution["mechanism_traces"] = [
                {
                    "node": "机制节点一",
                    "observation": "观察到预先登记的过程痕迹。",
                    "diagnosticity": "该痕迹可区分主要竞争机制，但不单独证明完整机制。",
                    "outcome": "positive",
                    "evidence_ids": list(route["evidence_ids"]),
                }
            ]
        if route["family"] == "congruence_analysis":
            case_execution["theory_prediction_observation_matrix"] = [
                {
                    "theory": "竞争理论甲",
                    "prediction": "若理论甲成立，应观察到登记现象。",
                    "observation": "观察结果与预测部分一致。",
                    "fit": "qualified",
                    "evidence_ids": list(route["evidence_ids"]),
                }
            ]
    family = route["family"]
    if family == "experiment":
        diagnostic = register_artifact(
            "ART-DIAG",
            "assignment_diagnostic.json",
            '{"status":"supported","test":"allocation audit"}\n',
            "识别假设诊断",
        )
        estimate = register_artifact(
            "ART-ESTIMATE",
            "causal_estimate.json",
            '{"estimand":"registered contrast","estimate":0.1}\n',
            "估计对象与估计结果",
        )
        sensitivity = register_artifact(
            "ART-SENSITIVITY",
            "causal_sensitivity.json",
            '{"analysis":"registered alternative specification"}\n',
            "识别敏感性分析",
        )
        contract = copy.deepcopy(run["method_contract"])
        contract["identification_assumptions"][0].update(
            {
                "diagnostic_artifact_id": diagnostic,
                "status": "supported",
            }
        )
        contract["estimate_artifact_id"] = estimate
        contract["sensitivity_artifact_id"] = sensitivity
        run["method_contract"] = contract
        run["artifact_refs"] = [diagnostic, estimate, sensitivity]
        run["results"][0]["artifact_ids"].extend([estimate, sensitivity])
    elif family == "process_tracing":
        contract = copy.deepcopy(run["method_contract"])
        matrix = register_artifact(
            "ART-MECHANISM",
            "mechanism_matrix.csv",
            (
                "mechanism_node,theoretical_prediction,observation,diagnosticity,competing_mechanism,source_id\n"
                f"node-1,predicted trace,observed trace,discriminating,{contract['strongest_competing_mechanism']},SRC-001\n"
            ),
            "机制诊断证据矩阵",
        )
        independence = register_artifact(
            "ART-SOURCE-AUDIT",
            "source_independence.md",
            "# Source independence\n\nProduction context and transmission chain were audited.\n",
            "来源独立性审计",
        )
        contract.update(
            {
                "diagnostic_matrix_artifact_id": matrix,
                "source_independence_artifact_id": independence,
                "negative_evidence": [],
            }
        )
        run["method_contract"] = contract
        run["artifact_refs"] = [matrix, independence]
        run["results"][0]["artifact_ids"].extend([matrix, independence])
    elif family == "text_as_data":
        corpus = register_artifact(
            "ART-CORPUS",
            "corpus_manifest.jsonl",
            '{"item_id":"R1","document_id":"D1"}\n'
            '{"item_id":"R2","document_id":"D2"}\n'
            '{"item_id":"T1","document_id":"D3"}\n'
            '{"item_id":"T2","document_id":"D3"}\n'
            '{"item_id":"T3","document_id":"D4"}\n'
            '{"item_id":"T4","document_id":"D4"}\n',
            "冻结语料清单",
        )
        codebook = register_artifact(
            "ART-CODEBOOK",
            "codebook.yaml",
            "version: '1.0'\nconstruct: registered construct\nlabels: [A, B]\n",
            "冻结编码手册",
        )
        reference = register_artifact(
            "ART-REFERENCE",
            "reference_labels.csv",
            (
                "item_id,reference_label,evidence_locator,review_run_id,confidence,disagreement_status\n"
                "T1,A,corpus:T1,reference-model-01,0.98,no-disagreement\n"
                "T2,B,corpus:T2,reference-model-01,0.96,no-disagreement\n"
                "T3,A,corpus:T3,reference-model-02,0.91,resolved\n"
                "T4,B,corpus:T4,reference-model-02,0.95,no-disagreement\n"
            ),
            "冻结的独立模型参照标签",
        )
        reference_raw_1 = register_artifact(
            "ART-REFERENCE-RAW-1",
            "reference_run_01.jsonl",
            '{"item_id":"T1","label":"A","evidence":"corpus:T1"}\n'
            '{"item_id":"T2","label":"B","evidence":"corpus:T2"}\n',
            "独立参照运行一的原始输出",
        )
        reference_raw_2 = register_artifact(
            "ART-REFERENCE-RAW-2",
            "reference_run_02.jsonl",
            '{"item_id":"T3","label":"A","evidence":"corpus:T3"}\n'
            '{"item_id":"T4","label":"B","evidence":"corpus:T4"}\n',
            "独立参照运行二的原始输出",
        )
        reference_runs = register_artifact(
            "ART-REFERENCE-RUNS",
            "reference_run_manifest.json",
            json.dumps(
                {
                    "runs": [
                        {
                            "run_id": "reference-model-01",
                            "context_id": "ctx-reference-01",
                            "model_name": "example-research-model",
                            "model_revision": "rev-a",
                            "completed_at": "2026-08-16T08:00:00Z",
                            "system_prompt_sha256": "c" * 64,
                            "user_prompt_sha256": "d" * 64,
                            "output_artifact_id": reference_raw_1,
                            "blind_to_primary_output": True,
                        },
                        {
                            "run_id": "reference-model-02",
                            "context_id": "ctx-reference-02",
                            "model_name": "example-research-model",
                            "model_revision": "rev-b",
                            "completed_at": "2026-08-16T09:00:00Z",
                            "system_prompt_sha256": "e" * 64,
                            "user_prompt_sha256": "f" * 64,
                            "output_artifact_id": reference_raw_2,
                            "blind_to_primary_output": True,
                        },
                    ]
                },
                ensure_ascii=False,
            )
            + "\n",
            "独立参照运行的模型、上下文、提示词和输出绑定",
        )
        reference_evidence = register_artifact(
            "ART-REFERENCE-EVIDENCE",
            "reference_evidence.csv",
            (
                "item_id,source_artifact_id,evidence_locator,rationale,codebook_version\n"
                "T1,ART-CORPUS,corpus:T1,The claim meets the registered A rule,1.0\n"
                "T2,ART-CORPUS,corpus:T2,The claim meets the registered B rule,1.0\n"
                "T3,ART-CORPUS,corpus:T3,The claim meets the registered A rule,1.0\n"
                "T4,ART-CORPUS,corpus:T4,The claim meets the registered B rule,1.0\n"
            ),
            "逐项来源定位、理由和编码手册版本",
        )
        reference_review = register_artifact(
            "ART-REFERENCE-REVIEW",
            "reference_review.json",
            json.dumps(
                {
                    "reviewed_item_ids": ["T1", "T2", "T3", "T4"],
                    "resolution_rule": "Resolve against the frozen codebook and cited source span; exclude if unresolved.",
                    "unresolved_count": 0,
                    "adjudication_run_id": "reference-model-02",
                    "item_dispositions": {
                        "T3": "Resolved against the cited source span and frozen codebook."
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            "独立参照复核与分歧处置记录",
        )
        train = register_artifact(
            "ART-TRAIN",
            "train_manifest.csv",
            "item_id,document_id\nR1,D1\nR2,D2\n",
            "训练集身份清单",
        )
        test = register_artifact(
            "ART-TEST",
            "test_manifest.csv",
            "item_id,document_id\nT1,D3\nT2,D3\nT3,D4\nT4,D4\n",
            "独立测试集身份清单",
        )
        predictions = register_artifact(
            "ART-PREDICTIONS",
            "test_predictions.csv",
            "item_id,reference_label,predicted\nT1,A,A\nT2,B,B\nT3,A,B\nT4,B,B\n",
            "逐条测试集预测",
        )
        metrics = register_artifact(
            "ART-METRICS",
            "measurement_metrics.json",
            json.dumps(
                {
                    "n": 4,
                    "metric_semantics": "reference_agreement",
                    "agreement_rate": 0.75,
                    "macro_f1": 0.7333333333333334,
                    "micro_f1": 0.75,
                    "confusion_matrix": {
                        "A": {"A": 1, "B": 1},
                        "B": {"A": 0, "B": 2},
                    },
                    "per_class": {
                        "A": {
                            "support": 2,
                            "precision": 1.0,
                            "recall": 0.5,
                            "f1": 0.6666666666666666,
                        },
                        "B": {
                            "support": 2,
                            "precision": 0.6666666666666666,
                            "recall": 1.0,
                            "f1": 0.8,
                        },
                    },
                },
                ensure_ascii=False,
            )
            + "\n",
            "可复算的类别级测量指标",
        )
        errors = register_artifact(
            "ART-ERRORS",
            "error_analysis.md",
            "# Error analysis\n\nT3 was reviewed as the registered false negative/positive case.\n",
            "误判案例分析",
        )
        sensitivity = register_artifact(
            "ART-MEAS-SENS",
            "measurement_sensitivity.json",
            '{"dimension":"threshold","result":"reported without universal cutoff"}\n',
            "预处理与阈值敏感性",
        )
        validity = register_artifact(
            "ART-MEAS-VALIDITY",
            "measurement_validity.json",
            json.dumps(
                {
                    "dimensions": {
                        "content": {
                            "status": "needs-independent-review",
                            "rationale": "Codebook coverage is registered for independent interpretive review.",
                            "evidence_artifact_ids": ["ART-CODEBOOK"],
                        },
                        "construct": {
                            "status": "needs-independent-review",
                            "rationale": "Construct rules and exclusions require independent interpretive review.",
                            "evidence_artifact_ids": ["ART-CODEBOOK"],
                        },
                        "convergent": {
                            "status": "documented",
                            "rationale": "Frozen source-grounded reference labels provide a registered comparison.",
                            "evidence_artifact_ids": ["ART-REFERENCE", "ART-METRICS"],
                        },
                        "discriminant": {
                            "status": "documented",
                            "rationale": "Class-level errors are reported separately.",
                            "evidence_artifact_ids": ["ART-METRICS", "ART-ERRORS"],
                        },
                        "known_groups": {
                            "status": "not-applicable",
                            "rationale": "No theoretically known groups are claimed in this fixture.",
                            "evidence_artifact_ids": [],
                        },
                        "temporal": {
                            "status": "not-applicable",
                            "rationale": "This bounded fixture makes no temporal transport claim.",
                            "evidence_artifact_ids": [],
                        },
                        "institutional": {
                            "status": "not-applicable",
                            "rationale": "This bounded fixture makes no cross-institution claim.",
                            "evidence_artifact_ids": [],
                        },
                        "language": {
                            "status": "not-applicable",
                            "rationale": "This bounded fixture makes no cross-language claim.",
                            "evidence_artifact_ids": [],
                        },
                        "case": {
                            "status": "needs-independent-review",
                            "rationale": "Misclassified cases are exposed for independent interpretive review.",
                            "evidence_artifact_ids": ["ART-ERRORS"],
                        },
                    }
                },
                ensure_ascii=False,
            )
            + "\n",
            "分维度测量有效性证据",
        )
        run["method_contract"] = {
            "construct": {
                "name": "registered_construct",
                "definition": "A bounded construct defined before model execution.",
                "unit": "claim",
                "codebook_version": "1.0",
            },
            "unit_of_analysis": "claim",
            "split_plan": route["method_contract"]["split_plan"],
            "validation_plan": route["method_contract"]["validation_plan"],
            "corpus": {"manifest_artifact_id": corpus, "frozen": True},
            "codebook_artifact_id": codebook,
            "reference_standard": {
                "labels_artifact_id": reference,
                "sampling_strategy": "stratified",
                "run_count": 2,
                "reference_basis": "independent_model_review",
                "metric_semantics": "reference_agreement",
                "reference_run_ids": ["reference-model-01", "reference-model-02"],
                "independence": "separate contexts blind to the primary output",
                "frozen_at": "2026-08-16T10:00:00Z",
                "run_manifest_artifact_id": reference_runs,
                "evidence_artifact_id": reference_evidence,
                "review_artifact_id": reference_review,
            },
            "split": {
                "strategy": "document-grouped-holdout",
                "grouping_unit": "document_id",
                "train_manifest_artifact_id": train,
                "test_manifest_artifact_id": test,
            },
            "validation": {
                "predictions_artifact_id": predictions,
                "metrics_artifact_id": metrics,
                "error_analysis_artifact_id": errors,
            },
            "sensitivity": {
                "artifact_id": sensitivity,
                "dimensions": ["threshold"],
            },
            "validity": {"artifact_id": validity},
            "interpretation": {
                "allowed": "Measurement claims within the frozen corpus and codebook.",
                "prohibited": "No causal or population-attitude interpretation.",
            },
            "researcher_run": {
                "run_id": "primary-model-01",
                "context_id": "ctx-primary-01",
                "model_name": "example-research-model",
                "model_revision": "rev-primary",
                "run_date": "2026-08-17T00:00:00Z",
                "system_prompt_sha256": "a" * 64,
                "user_prompt_sha256": "b" * 64,
                "temperature": 0,
                "repeat_count": 2,
                "output_schema": "claim-label/v2",
                "retry_rule": "one schema-only retry",
                "repeat_consistency": "reported as stability, not accuracy",
                "reference_labels_artifact_id": reference,
                "evidence_trace_artifact_id": reference_evidence,
                "independent_review_artifact_id": reference_review,
            },
        }
        run["artifact_refs"] = [
            corpus,
            codebook,
            reference,
            reference_raw_1,
            reference_raw_2,
            reference_runs,
            reference_evidence,
            reference_review,
            train,
            test,
            predictions,
            metrics,
            errors,
            sensitivity,
            validity,
        ]
        run["results"][0]["artifact_ids"].extend(
            [predictions, metrics, errors, sensitivity, validity]
        )
    run["deviations"] = []
    run["negative_findings"] = []
    run["ethics_events"] = []
    if route["empirical"]:
        payload["software_environments"] = [
            {
                "id": "ENV-001",
                "runtime": "Python",
                "versions": "Python 3.12 and locked standard-library tool",
                "lock_or_capture": "environment manifest sha256 registered",
                "reproduction_command": "python reproduce.py",
            }
        ]
        run["software_environment_ids"] = ["ENV-001"]
    else:
        payload["software_environments"] = []
        run["software_environment_ids"] = []
    payload["reporting"] = {
        "outcome_inventory_status": "complete",
        "negative_findings_status": "reviewed-none",
        "deviations_status": "reviewed-none",
        "selective_reporting_declaration": "所有计划结果、偏离和负面发现均已逐项核对并登记。",
    }
    return payload


def workspace(family: str):
    temporary = tempfile.TemporaryDirectory()
    base = Path(temporary.name)
    design = confirmed_design(family)
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    execution = complete_execution(base, design)
    return temporary, base, design, execution


class MethodExecutionTests(unittest.TestCase):
    def test_every_registered_family_has_a_valid_execution(self) -> None:
        families = sorted(set(method_execution.load_registry()["families"]) - {"unresolved"})
        self.assertEqual(19, len(families))
        for family in families:
            with self.subTest(family=family):
                temporary, base, _, payload = workspace(family)
                with temporary:
                    result = method_execution.validate_payload(base, payload)
                    self.assertEqual([], result.errors, [issue.code for issue in result.issues])

    def test_every_family_has_required_fixture_mutations(self) -> None:
        """Exercise the six release fixture classes for every active adapter."""
        registry = method_execution.load_registry()
        families = sorted(set(registry["families"]) - {"unresolved"})
        for family in families:
            temporary, base, design, positive = workspace(family)
            with temporary, self.subTest(family=family):
                self.assertEqual(
                    [],
                    method_execution.validate_payload(base, positive).errors,
                    "positive",
                )

                keyword = copy.deepcopy(positive)
                keyword["runs"][0]["actions"] = ["执行执行执行执行执行执行"]
                self.assertIn(
                    "ME.CONTENT.REPETITIVE",
                    {
                        issue.code
                        for issue in method_execution.validate_payload(base, keyword).errors
                    },
                    "keyword-gaming",
                )

                mutation = copy.deepcopy(positive)
                required_field = registry["families"][family]["execution_fields"][0]
                mutation["runs"][0]["method_fields"].pop(required_field)
                self.assertIn(
                    "ME.METHOD.FIELD_MISSING",
                    {
                        issue.code
                        for issue in method_execution.validate_payload(base, mutation).errors
                    },
                    "single-field-mutation",
                )

                drift = copy.deepcopy(positive)
                drift["runs"][0]["route_family"] = "normative" if family != "normative" else "survey"
                self.assertIn(
                    "ME.DESIGN.DRIFT",
                    {
                        issue.code
                        for issue in method_execution.validate_payload(base, drift).errors
                    },
                    "design-execution-drift",
                )

                overreach = copy.deepcopy(positive)
                overreach["runs"][0]["inference_ceiling_observed"] = (
                    "无条件推广到所有总体并声称确定因果。"
                )
                self.assertIn(
                    "ME.INFERENCE.DRIFT",
                    {
                        issue.code
                        for issue in method_execution.validate_payload(base, overreach).errors
                    },
                    "inference-overreach",
                )

                legal_na = copy.deepcopy(positive)
                run = legal_na["runs"][0]
                run["status"] = "not-applicable"
                run["not_applicable_reason"] = "路线因已登记的材料不可得而合法终止。"
                run["method_fields"] = {}
                run["artifacts"] = []
                run["results"] = []
                run["software_environment_ids"] = []
                design["claims"][0]["status"] = "withdrawn"
                legal_na["design_sha256"] = method_execution._canonical_digest(design)
                (base / "research_design.json").write_text(
                    json.dumps(design, ensure_ascii=False),
                    encoding="utf-8",
                )
                self.assertEqual(
                    [],
                    method_execution.validate_payload(base, legal_na).errors,
                    "legal-non-applicability",
                )

    def test_scaffold_is_never_a_false_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            design = confirmed_design("survey")
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            payload = method_execution.scaffold_payload(design)
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.CONFIRMATION.MISSING", {issue.code for issue in result.errors})

    def test_repetitive_keyword_gaming_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("survey")
        with temporary:
            payload["runs"][0]["actions"] = ["执行执行执行执行执行执行"]
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.CONTENT.REPETITIVE", {issue.code for issue in result.errors})

    def test_design_route_hash_detects_post_execution_drift(self) -> None:
        temporary, base, design, payload = workspace("quantitative")
        with temporary:
            design["method_routes"][0]["method"] = "执行后偷偷更换的方法"
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.DESIGN.DRIFT", {issue.code for issue in result.errors})

    def test_artifact_content_hash_change_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("content_analysis")
        with temporary:
            (base / payload["runs"][0]["artifacts"][0]["path"]).write_text(
                "changed after registration\n",
                encoding="utf-8",
            )
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.ARTIFACT.HASH_CHANGED", {issue.code for issue in result.errors})

    def test_material_realization_is_bound_to_design_scope_and_artifacts(self) -> None:
        temporary, base, design, payload = workspace("quantitative")
        with temporary:
            design["material_plan"] = {
                "feasibility_basis_digest": "a" * 64,
                "allowed_question_boundary_digest": "b" * 64,
                "material_refs": [{"material_id": "MAT-001", "probe_ids": ["PROBE-001"]}],
                "time_scope": "2020-2025",
                "spatial_scope": "registered municipalities",
                "unit_scope": "municipality-year",
                "required_fields_or_roles": ["municipality", "year", "outcome"],
                "linkage_plan": "municipality and year form the registered linkage key",
                "variation_or_identification_plan": "observed within-boundary variation supports the registered descriptive contrast",
                "realization_rule": "execution must hash-bind the cleaned material artifact and disclose every scope change",
            }
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            payload["design_sha256"] = method_execution._canonical_digest(design)
            payload["feasibility_basis_digest"] = "a" * 64
            payload["material_realizations"] = [
                {
                    "material_id": "MAT-001",
                    "probe_ids": ["PROBE-001"],
                    "artifact_ids": ["ART-001"],
                    "status": "REALIZED",
                    "realized_scope": {
                        "time_scope": "2020-2025",
                        "spatial_scope": "registered municipalities",
                        "unit_scope": "municipality-year",
                        "required_fields_or_roles": ["municipality", "year", "outcome"],
                    },
                    "linkage_outcome": "registered municipality-year keys linked without unresolved duplicates",
                    "variation_or_identification_outcome": "the registered descriptive variation remained observable in the realized data",
                    "deviation_id": None,
                }
            ]
            self.assertEqual([], method_execution.validate_payload(base, payload).errors)
            payload["material_realizations"][0]["realized_scope"]["time_scope"] = "2024 only"
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.MATERIAL.SCOPE_DRIFT", {issue.code for issue in result.errors})

    def test_unregistered_number_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("quantitative")
        with temporary:
            payload["runs"][0]["results"][0]["numeric_values"] = [
                {"value": "42", "evidence_id": "EVD-999", "artifact_id": "ART-001"}
            ]
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.NUMBER.UNREGISTERED", {issue.code for issue in result.errors})

    def test_survey_result_cannot_be_relabelled_causal(self) -> None:
        temporary, base, _, payload = workspace("survey")
        with temporary:
            item = payload["runs"][0]["results"][0]
            item["type"] = "causal_effect"
            item["text"] = "问卷回归证明政策导致结果变化。"
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.INFERENCE.CAUSAL_OVERREACH", {issue.code for issue in result.errors})

    def test_process_tracing_supports_mechanism_not_causal_effect(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            design = confirmed_design("process_tracing")
            design["method_routes"][0]["function"] = "identification"
            design["claims"][0]["type"] = "causal_effect"
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            payload = complete_execution(base, design)
            payload["runs"][0]["results"][0]["type"] = "causal_effect"
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.INFERENCE.CAUSAL_OVERREACH", {issue.code for issue in result.errors})

            design["claims"][0]["type"] = "causal_mechanism"
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            payload = complete_execution(base, design)
            payload["runs"][0]["results"][0]["type"] = "causal_mechanism"
            result = method_execution.validate_payload(base, payload)
            self.assertNotIn(
                "ME.INFERENCE.CAUSAL_OVERREACH",
                {issue.code for issue in result.errors},
            )

    def test_fake_randomization_at_execution_is_blocked(self) -> None:
        temporary, base, design, payload = workspace("experiment")
        with temporary:
            route = design["method_routes"][0]
            route["method_fields"]["assignment_mechanism"] = "按计算机序列随机分配"
            route["method_fields"]["randomization_verification"] = "随机种子与分配代码已经冻结。"
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            run = payload["runs"][0]
            run["design_route_sha256"] = method_execution._canonical_digest(route)
            run["method_fields"]["assignment_audit"] = "研究团队口头表示确实随机。"
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.EXPERIMENT.RANDOMIZATION_UNVERIFIED",
                {issue.code for issue in result.errors},
            )

    def test_computational_split_leakage_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("computational")
        with temporary:
            payload["runs"][0]["method_fields"]["split_and_leakage_audit"] = (
                "发现训练集与测试集存在样本泄漏。"
            )
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.VALIDATION.LEAKAGE", {issue.code for issue in result.errors})

    def test_historical_false_independence_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("historical")
        with temporary:
            payload["runs"][0]["method_fields"]["transmission_audit"] = (
                "两份材料属于同源传递链，但仍作为独立证据。"
            )
            result = method_execution.validate_payload(base, payload)
            self.assertIn("ME.EVIDENCE.FALSE_INDEPENDENCE", {issue.code for issue in result.errors})

    def test_soft_method_judgments_remain_review_items(self) -> None:
        cases = (
            ("social_network", "dependence_aware_models", "把节点视为独立同分布。", "ME.REVIEW.NETWORK_DEPENDENCE"),
            ("qca", "truth_table", "所有研究一律采用固定阈值。", "ME.REVIEW.QCA_THRESHOLD"),
            ("grounded_theory", "saturation_evidence", "访谈达到20人即自动理论饱和。", "ME.REVIEW.SATURATION"),
        )
        for family, field, value, code in cases:
            with self.subTest(family=family):
                temporary, base, _, payload = workspace(family)
                with temporary:
                    payload["runs"][0]["method_fields"][field] = value
                    result = method_execution.validate_payload(base, payload)
                    self.assertEqual([], result.errors)
                    self.assertIn(code, {issue.code for issue in result.issues})

    def test_legal_non_applicability_does_not_force_empirical_artifacts(self) -> None:
        temporary, base, design, payload = workspace("conceptual")
        with temporary:
            run = payload["runs"][0]
            run["status"] = "not-applicable"
            run["not_applicable_reason"] = "该辅助路线在用户确认后撤销，未产生分析结果。"
            run["artifacts"] = []
            run["results"] = []
            run["method_fields"] = {}
            design["claims"][0]["status"] = "withdrawn"
            payload["design_sha256"] = method_execution._canonical_digest(design)
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            result = method_execution.validate_payload(base, payload)
            self.assertEqual([], result.errors, [issue.code for issue in result.issues])

    def test_not_applicable_route_cannot_silently_cover_an_active_claim(self) -> None:
        temporary, base, _, payload = workspace("conceptual")
        with temporary:
            run = payload["runs"][0]
            run["status"] = "not-applicable"
            run["not_applicable_reason"] = "材料不可得，路线终止。"
            run["artifacts"] = []
            run["results"] = []
            run["method_fields"] = {}
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.RESULT.UNREGISTERED_CLAIM",
                {issue.code for issue in result.errors},
            )

    def test_future_schema_is_safely_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = method_execution.validate_payload(
                Path(tmp),
                {
                    "schema_version": "cnki-method-execution/v99",
                    "design_schema_version": "cnki-research-design/v2",
                },
            )
            self.assertIn("ME.SCHEMA.FUTURE", {issue.code for issue in result.errors})

    def test_legacy_migration_is_dry_run_safe_backed_up_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            design = confirmed_design("conceptual")
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            legacy = "\n".join(
                (
                    "# Execution Record",
                    "",
                    "| Execution ID | Design ID | Method Action | Result |",
                    "|---|---|---|---|",
                    "| EXE-001 | DSN-001 | 旧分析动作 | 旧结果不得自动晋级 |",
                    "",
                )
            )
            (base / "execution_record.md").write_text(legacy, encoding="utf-8")
            before = sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))
            code, preview = method_execution.migrate_command(base, apply=False)
            after = sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))
            self.assertEqual(0, code)
            self.assertEqual(before, after)
            self.assertIn('"mode": "dry-run"', preview)
            code, _ = method_execution.migrate_command(base, apply=True)
            self.assertEqual(0, code)
            payload = json.loads((base / "method_execution.json").read_text(encoding="utf-8"))
            self.assertEqual("needs-review", payload["status"])
            self.assertEqual([], payload["runs"][0]["results"])
            backups = list((base / "migration" / "method_execution_v2").glob("*.legacy.md"))
            self.assertEqual(1, len(backups))
            snapshot = {
                path.relative_to(base).as_posix(): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            code, message = method_execution.migrate_command(base, apply=True)
            self.assertEqual(0, code)
            self.assertIn("already complete", message)
            repeated = {
                path.relative_to(base).as_posix(): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(snapshot, repeated)

    def test_legacy_execution_migration_preserves_unresolved_route_as_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            design = v3.migrate_payload(
                v2.migrate_v1_payload(research_design.migrate_payload("")),
                v2=v2,
            )
            self.assertEqual("unresolved", design["method_routes"][0]["family"])
            with self.assertRaises(method_execution.ExecutionContractError):
                method_execution.scaffold_payload(design)
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False),
                encoding="utf-8",
            )
            legacy = "\n".join(
                (
                    "# Execution Record",
                    "",
                    "| Execution ID | Design ID | Method Action | Result |",
                    "|---|---|---|---|",
                    "| EXE-001 | D01 | 旧路线动作 | 旧结果不得自动晋级 |",
                    "",
                )
            )
            (base / "execution_record.md").write_text(legacy, encoding="utf-8")
            code, _ = method_execution.migrate_command(base, apply=True)
            self.assertEqual(0, code)
            payload = json.loads(
                (base / "method_execution.json").read_text(encoding="utf-8")
            )
            self.assertEqual("needs-review", payload["status"])
            self.assertEqual("unresolved", payload["runs"][0]["route_family"])
            self.assertEqual([], payload["runs"][0]["results"])
            self.assertIn("needs-review", payload["runs"][0]["migration_note"])
            self.assertEqual(
                1,
                len(
                    list(
                        (base / "migration" / "method_execution_v2").glob(
                            "*.legacy.md"
                        )
                    )
                ),
            )

    def test_case_deletion_requires_a_registered_change(self) -> None:
        temporary, base, _, payload = workspace("comparative")
        with temporary:
            run = payload["runs"][0]
            run["case_ids"] = ["CAS-001"]
            run["case_execution"]["actual_case_ids"] = ["CAS-001"]
            run["results"][0]["case_ids"] = ["CAS-001"]
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.CASE.DESIGN_DRIFT",
                {issue.code for issue in result.errors},
            )
            run["case_execution"]["case_changes"] = [
                {
                    "case_id": "CAS-002",
                    "action": "excluded",
                    "reason": "登记材料在合法权限复核后不可用。",
                    "disposition": "收窄比较并披露选择偏离。",
                }
            ]
            result = method_execution.validate_payload(base, payload)
            self.assertNotIn(
                "ME.CASE.DESIGN_DRIFT",
                {issue.code for issue in result.errors},
            )

    def test_scope_condition_identity_drift_is_blocked(self) -> None:
        temporary, base, _, payload = workspace("case_study")
        with temporary:
            payload["runs"][0]["scope_condition_ids"] = []
            payload["runs"][0]["results"][0]["scope_condition_ids"] = []
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.CASE.DESIGN_DRIFT",
                {issue.code for issue in result.errors},
            )

    def test_process_tracing_cannot_omit_mechanism_traces(self) -> None:
        temporary, base, _, payload = workspace("process_tracing")
        with temporary:
            payload["runs"][0]["case_execution"]["mechanism_traces"] = []
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.CASE.MECHANISM_TRACES_MISSING",
                {issue.code for issue in result.errors},
            )

    def test_congruence_result_cannot_claim_a_mechanism(self) -> None:
        temporary, base, _, payload = workspace("congruence_analysis")
        with temporary:
            item = payload["runs"][0]["results"][0]
            item["type"] = "causal_mechanism"
            item["text"] = "一致性分析证明了唯一因果机制。"
            result = method_execution.validate_payload(base, payload)
            codes = {issue.code for issue in result.errors}
            self.assertIn("ME.INFERENCE.CAPABILITY_EXCEEDED", codes)
            self.assertIn("ME.INFERENCE.CAUSAL_OVERREACH", codes)

    def test_qca_configuration_cannot_be_rewritten_as_average_effect(self) -> None:
        temporary, base, _, payload = workspace("qca")
        with temporary:
            item = payload["runs"][0]["results"][0]
            item["text"] = "该组态估计了对所有案例相同的平均效应。"
            result = method_execution.validate_payload(base, payload)
            self.assertIn(
                "ME.INFERENCE.CONFIGURATION_AS_EFFECT",
                {issue.code for issue in result.errors},
            )

    def test_v1_case_execution_migration_never_rebinds_silently(self) -> None:
        temporary, base, _, current = workspace("process_tracing")
        with temporary:
            legacy = copy.deepcopy(current)
            legacy["schema_version"] = "cnki-method-execution/v1"
            legacy["design_schema_version"] = "cnki-research-design/v2"
            legacy.pop("design_sha256", None)
            legacy.pop("adapter_registry_sha256", None)
            for run in legacy["runs"]:
                for field_name in (
                    "case_ids",
                    "scope_condition_ids",
                    "comparison_ids",
                    "within_case_analysis_ids",
                    "case_execution",
                ):
                    run.pop(field_name, None)
                for item in run["results"]:
                    for field_name in (
                        "case_ids",
                        "scope_condition_ids",
                        "comparison_ids",
                        "within_case_analysis_ids",
                    ):
                        item.pop(field_name, None)
            original_run_id = legacy["runs"][0]["id"]
            original_hash = legacy["runs"][0]["artifacts"][0]["sha256"]
            (base / "method_execution.json").write_text(
                json.dumps(legacy, ensure_ascii=False),
                encoding="utf-8",
            )
            code, preview = method_execution.migrate_command(base, apply=False, to="v2")
            self.assertEqual(0, code)
            self.assertEqual(
                "needs-review",
                json.loads(preview)["payload"]["status"],
            )
            code, _ = method_execution.migrate_command(base, apply=True, to="v2")
            self.assertEqual(0, code)
            migrated = json.loads(
                (base / "method_execution.json").read_text(encoding="utf-8")
            )
            self.assertEqual(original_run_id, migrated["runs"][0]["id"])
            self.assertEqual(original_hash, migrated["runs"][0]["artifacts"][0]["sha256"])
            self.assertTrue(migrated["migration"]["case_sensitive"])
            self.assertTrue(migrated["design_sha256"].startswith("needs-review"))


if __name__ == "__main__":
    unittest.main()
