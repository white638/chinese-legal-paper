#!/usr/bin/env python3
"""Regression tests for the CNKI-Paper v3 research-design contract."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    path = HERE / filename
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


research_design = load_module("research_design", "research_design.py")
research_quality = load_module("research_quality_check_for_v3_test", "research_quality_check.py")


def write_registry(base: Path, *source_ids: str) -> None:
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
                            "support_claim": "已从详情页或原文核验的具体支撑内容。",
                        },
                    }
                    for source_id in source_ids
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def base_contract(
    *,
    family: str = "quantitative_causal",
    claim_type: str = "causal_effect",
    question_type: str = "explanatory",
) -> dict:
    task_fields = {
        "descriptive": {
            "descriptive_increment": "重建既有统计无法区分的政策执行类型及其演变。",
            "reconstruction_boundary": "只还原2012—2025年同类地方政策，不外推其他制度。",
        },
        "explanatory": {
            "relation": "解释制度激励在资源约束下为何产生方向相反的执行结果。",
            "discriminating_expectations": "资源约束与领导偏好机制对关键时序和负例产生不同预期。",
        },
        "predictive": {
            "forecast_target": "地方政策执行差异",
            "horizon": "2026—2030年",
            "baseline": "2021—2025年历史趋势",
            "uncertainty": "报告情景区间与模型不确定性。",
            "validation": "按年度留出数据回测预测表现。",
            "updating": "新年度数据到达后按预登记规则更新。",
        },
        "operational": {
            "actor": "地方政府执行部门",
            "goal": "提高政策执行一致性",
            "constraints": "财政和法定权限约束",
            "levers": "流程校准与资源调度",
            "feasibility": "以既有机构权限和预算评估可行性。",
            "evaluation": "用跨地区执行偏差及成本评价。",
        },
        "normative": {
            "normative_premises": "程序公平具有独立价值且行政效率不能取消基本权利。",
            "strongest_objection": "效率损失可能损害公共服务的实质公平。",
            "institutional_constraints": "现行预算、程序和问责制度限定可行方案。",
        },
    }[question_type]
    question_text = {
        "descriptive": "2012—2025年地方政策执行结果呈现何种结构与演变特征？",
        "explanatory": "相似制度条件下为何会形成方向相反的执行结果？",
        "predictive": "到2030年资源约束下的地方政策执行差异将如何变化？",
        "operational": "地方政府如何在财政约束下改善政策执行一致性？",
        "normative": "地方政府是否应以程序公平优先约束政策执行效率？",
    }[question_type]
    payload = {
        "schema_version": research_design.SCHEMA_VERSION,
        "status": "confirmed",
        "research_question": {
            "id": "RQ01",
            "text": question_text,
            "primary_type": question_type,
            "answer_task": "回答既有知识尚不能解释的关系，并区分竞争性答案。",
            "otipr": {
                "object": "同类地方政策执行过程",
                "time": "2012—2025年",
                "issue": "政策执行差异",
                "perspective": "制度激励理论",
                "relation": {
                    "strength": "strong" if question_type in {"explanatory", "predictive"} else "weak",
                    "statement": "资源约束改变制度激励与执行结果之间的关系。",
                },
            },
            "task_fields": task_fields,
        },
        "knowledge_state": {
            "known": "既有研究反复发现制度激励与执行结果相关，但结论具有条件性。",
            "unknown": "相似制度条件下仍出现方向相反的执行结果，现有研究未解释差异。",
            "gap_authenticity": "对象已有研究；真实缺口是资源约束何时改变激励机制，而非对象新、论文少、发表时滞或术语错配。",
            "maturity": "发展期：概念和基本关系较稳定，但竞争解释的机制证据仍不完整。",
            "expected_contribution": "识别资源约束触发机制及其失效条件，解释平均关系为何在部分场景失效。",
        },
        "epistemic_position": {
            "paradigm": "后实证主义；承认测量与识别的不确定性。",
            "research_logic": "mixed",
            "method_rationale": "先由异常归纳竞争解释，再用预登记的区分性观察检验。",
        },
        "design": {
            "id": "D01",
            "family": family,
            "claim_type": claim_type,
            "empirical": family in research_design.EMPIRICAL_FAMILIES,
            "method": {
                "quantitative_causal": "面板准实验与异质性分析",
                "case_process": "比较案例与过程追踪",
                "text_content": "可复核的文本内容分析",
                "interpretive": "情境化诠释分析",
                "descriptive": "类型学描述",
                "theory_generation": "理论生成",
                "normative": "规范论证",
                "review": "结构化文献综合",
            }[family],
            "method_rationale": "设计产生回答主张所需的比较、过程或材料证据，并保留失败条件。",
            "units": "同类地方政策过程；制度功能和时间窗一致。",
            "time_scope": "2012—2025年",
            "inference_ceiling": "结论限于所登记总体、案例或语料边界，不推断跨制度普遍效应。",
            "evidence_boundary": "只使用登记来源、预定样本和2012—2025年材料回答该问题。",
            "limitations": "不可观测差异仍可能存在，将报告敏感性分析并收窄外推。",
            "permissions": {"status": "confirmed", "note": "仅用合法取得材料"},
            "ethics": {"status": "exempt", "note": "不处理可识别个人信息"},
            "reproducibility": {"status": "ready", "note": "脚本、日志和环境说明齐全"},
            "evidence_separation": {
                "status": "separated",
                "rationale": "理论构建材料与主要检验材料按时间和来源分开。",
            },
            "reporting_plan": {
                "negative_findings": "报告不支持、反向和边界结果。",
                "deviations": "逐项登记相对预分析计划的偏离及理由。",
            },
            "artifact_paths": {},
        },
        "concepts": [
            {
                "id": "C01",
                "name": "制度激励",
                "definition": "正式制度改变行动者收益与成本预期的可观察安排。",
                "boundary": "不把一般政治口号或事后结果同义改称制度激励。",
                "source_ids": ["S01"],
                "operationalization": [
                    {
                        "indicator": "制度规则生效前后的激励强度指数",
                        "measurement": "依据预公开编码规则合成并保留原始分项。",
                        "data_source_ids": ["S01"],
                    }
                ],
                "measurement": {
                    "reliability": "双人独立编码并报告一致性；行政指标核对修订记录。",
                    "validity": "与理论定义、替代指标和已知事件进行内容与收敛效度核对。",
                },
            }
        ],
        "claims": [
            {
                "id": "CL01",
                "text": {
                    "causal_effect": "在所登记政策和时期内，资源约束削弱制度激励对执行结果的平均因果效应。",
                    "causal_mechanism": "在所比较案例中，资源约束经由投入变化形成执行差异的机制得到过程证据支持。",
                    "descriptive": "冻结语料中的政策执行表述形成三种可复核类型，并呈现跨时变化。",
                    "association": "制度激励强度与执行结果在登记样本中稳定相关。",
                    "prediction": "登记模型可在既定时域内预测执行差异并报告不确定性。",
                    "operational": "流程校准是登记约束下改善执行一致性的可评价方案。",
                    "interpretive": "行动者在资源约束语境中将制度信号理解为差异化行动理由。",
                    "theory_generation": "材料支持一个受边界约束的制度激励理论命题。",
                    "normative": "在登记制度约束下，程序公平应优先于边际效率收益。",
                    "review_synthesis": "登记文献形成可检验的知识地图和未来研究命题。",
                }[claim_type],
                "type": claim_type,
                "concept_ids": ["C01"],
                "evidence_ids": ["E01"],
                "source_ids": ["S01"],
                "allowed_scope": "所登记地方、政策类型和2012—2025年观察窗。",
                "prohibited_scope": "不声称适用于所有制度、地区或历史时期。",
            }
        ],
        "evidence": [
            {
                "id": "E01",
                "kind": "registered-records",
                "description": "制度规则、资源和执行结果的版本化面板记录。",
                "source_ids": ["S01"],
                "location": "empirical/data_source_log.md",
                "time_scope": "2012—2025年",
                "supports_claim_ids": ["CL01"],
            }
        ],
        "hypotheses": [],
        "framework": {
            "id": "AF01",
            "type": "mechanism",
            "description": "制度信号改变行动预期，资源约束再改变投入，从而影响执行结果。",
            "origin": "prior-and-revised",
        },
        "alternatives": [
            {
                "id": "ALT01",
                "text": "领导偏好可能同时改变资源分配和执行结果。",
                "discriminating_evidence": "领导更替时序和安慰剂结果可区分该解释。",
            }
        ],
        "falsification_conditions": [
            {
                "id": "FAL01",
                "condition": "处理前趋势不平行或安慰剂期出现同等效应。",
                "response": "不作因果解释，改报描述关联并重新设计。",
            }
        ],
        "sampling": {
            "population": "符合政策类型定义的全部地方执行单元。",
            "frame": "版本化行政名录与政策生效清单。",
            "unit": "地方—政策—年度。",
            "strategy": "按预公开规则构建全量面板并记录排除。",
            "rationale": "抽样框直接覆盖目标总体且可核对缺失。",
            "limitations": "退出或漏报单元可能造成选择偏差，单列敏感性分析。",
        },
        "routes": {},
        "artifact_fingerprints": [],
    }
    if family == "quantitative_causal":
        payload["routes"][family] = {
            "estimand": "政策生效对执行结果的平均处理效应及资源约束异质性。",
            "temporal_order": "处理发生在结果测量之前，保留至少三期处理前观察。",
            "comparison_or_counterfactual": "以尚未处理的同类单元构造同期反事实并检验共同趋势。",
            "identification_assumptions": ["共同趋势", "无预期性处理", "无同时发生的差异冲击"],
            "diagnostics": "事件研究、共同支持和影响点诊断。",
            "robustness": "替代窗口、替代指标、安慰剂和敏感性分析。",
            "uncertainty": "报告聚类稳健区间、多重检验调整和效应分布。",
        }
    elif family == "case_process":
        payload["routes"][family] = {
            "case_selection": "选择制度条件相似但结果相反的核心和对照案例。",
            "timeline": "逐案登记关键节点前后的文件、行动和结果时间线。",
            "mechanism_nodes": [
                "制度信号改变行动预期",
                "资源约束改变投入",
                "投入差异形成结果",
            ],
            "evidence_diagnosticity": "按证据对各竞争机制的独特预测评定诊断力。",
            "competing_mechanisms": "领导偏好机制预测变化紧随领导更替而非资源冲击。",
            "negative_evidence": "主动检索缺失环节、反向案例和竞争机制独有观察。",
            "scope_conditions": "同类政策、相近制度权限和登记时间窗。",
        }
    elif family == "text_content":
        payload["routes"][family] = {
            "corpus_manifest": [
                {
                    "id": "COR01",
                    "source_ids": ["S01"],
                    "version": "2025-12-31 freeze",
                    "inclusion": "按机构、文种、时期和主题规则纳入",
                }
            ],
            "unit_of_analysis": "以政策条款为编码单位，文件为语境单位。",
            "versions_and_preprocessing": "保留原始版本、去重日志、分词词典和全部转换摘要。",
            "codebook": "登记变量定义、正反例、冲突裁决和版本号。",
            "reliability_or_model_validation": "双人编码留出集并报告一致性与错误类别。",
            "context_boundary": "模型输出只解释冻结语料中的话语结构，不推断行动者真实动机。",
        }
    elif family == "interpretive":
        payload["routes"][family] = {
            "actor_meaning_and_context": "结合行动者原话、制度处境与互动顺序解释意义。",
            "researcher_reflexivity": "登记材料接触位置、先入理解和反例修订过程。",
        }
        payload["design"]["evidence_separation"] = {
            "status": "same-material-no-independent-test",
            "rationale": "同一材料用于形成诠释，不宣称独立验证或因果确认。",
        }
    return payload


def create_empirical_artifacts(base: Path, payload: dict) -> None:
    family = payload["design"]["family"]
    keys = (
        research_design.DESIGN_EMPIRICAL_ARTIFACTS
        | research_design.BUILD_EMPIRICAL_ARTIFACTS
        | research_design.DESIGN_BRANCH_ARTIFACTS[family]
        | research_design.BUILD_BRANCH_ARTIFACTS[family]
    )
    for key in keys:
        relative = Path("empirical") / f"{key}.md"
        path = base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {key}\n\n已登记的实质内容。\n", encoding="utf-8")
        payload["design"]["artifact_paths"][key] = relative.as_posix()


class ResearchDesignTests(unittest.TestCase):
    def workspace(self, family: str = "quantitative_causal", claim_type: str = "causal_effect", question_type: str = "explanatory"):
        temporary = tempfile.TemporaryDirectory()
        base = Path(temporary.name)
        write_registry(base, "S01", "S02")
        payload = base_contract(family=family, claim_type=claim_type, question_type=question_type)
        if payload["design"]["empirical"]:
            create_empirical_artifacts(base, payload)
        return temporary, base, payload

    def test_valid_quantitative_contract_passes_and_writes_all_reports_and_views(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            (base / "research_design.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.assertEqual(0, research_design.validate_command(base, write=True, json_stdout=True))
            for relative in (
                "knowledge_design_matrix.md",
                "concept_register.md",
                "claim_evidence_scope_matrix.md",
                "research_design_check.json",
                "research_design_check.md",
            ):
                self.assertTrue((base / relative).is_file(), relative)
            report = json.loads((base / "research_design_check.json").read_text(encoding="utf-8"))
            self.assertEqual("PASS", report["status"])
            self.assertEqual([], [issue for issue in report["issues"] if issue["severity"] == "ERROR"])

    def test_generated_matrix_remains_readable_by_legacy_quality_checker(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            research_design.render_views(base, payload)
            issues = research_quality.check_protocol(base / "knowledge_design_matrix.md")
            self.assertEqual([], issues)

    def test_case_process_and_text_content_routes_pass_without_hypotheses(self) -> None:
        for family, claim_type, question_type in (
            ("case_process", "causal_mechanism", "explanatory"),
            ("text_content", "descriptive", "descriptive"),
        ):
            temporary, base, payload = self.workspace(family, claim_type, question_type)
            with temporary:
                self.assertEqual([], payload["hypotheses"])
                result = research_design.validate_payload(base, payload)
                self.assertEqual([], result.errors, (family, result.issues))

    def test_interpretive_route_passes_without_empirical_artifacts_or_hypotheses(self) -> None:
        temporary, base, payload = self.workspace("interpretive", "interpretive", "explanatory")
        with temporary:
            self.assertFalse(payload["design"]["empirical"])
            self.assertEqual([], payload["hypotheses"])
            result = research_design.validate_payload(base, payload)
            self.assertEqual([], result.errors)
            self.assertIn("RD.RISK.CONSTRUCTION_REUSE", {issue.code for issue in result.issues})

    def test_unknown_source_and_duplicate_id_use_stable_codes(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["claims"][0]["source_ids"] = ["S99"]
            payload["claims"].append(dict(payload["claims"][0]))
            result = research_design.validate_payload(base, payload)
            codes = {issue.code for issue in result.issues}
            self.assertIn("RD.SOURCE.UNKNOWN", codes)
            self.assertIn("RD.ID.DUPLICATE", codes)

    def test_ids_are_globally_unique_and_internal_references_must_resolve(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["design"]["id"] = "RQ01"
            payload["claims"][0]["evidence_ids"] = ["E99"]
            result = research_design.validate_payload(base, payload)
            codes = {issue.code for issue in result.errors}
            self.assertIn("RD.ID.DUPLICATE", codes)
            self.assertIn("RD.ID.UNRESOLVED", codes)

    def test_existing_cross_artifacts_are_checked_for_lock_and_id_drift(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            (base / "confirmed_motivation.md").write_text(
                "# Confirmed Motivation\n\n另一个完全不同的问题。\n\n主类型：规范性\n",
                encoding="utf-8",
            )
            (base / "confirmed_contribution.md").write_text(
                "# Confirmed Contribution\n\n未登记任何活动主张编号。\n",
                encoding="utf-8",
            )
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "# Results",
                        "",
                        "| Results Unit | Claim | Evidence |",
                        "|---|---|---|",
                        "| R1 | CL99 | 未登记结果 |",
                        "| R2 | 无编号主张 | 无编号证据 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload, stage="design")
            codes = [issue.code for issue in result.errors]
            self.assertGreaterEqual(codes.count("RD.CONSISTENCY.DRIFT"), 3)
            self.assertIn("RD.ID.UNRESOLVED", codes)

    def test_bearing_row_claim_evidence_pair_must_match_contract_both_ways(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "| Design ID | Claim ID | Evidence ID | Result |",
                        "|---|---|---|---|",
                        "| D01 | CL01 | E01 | 有边界的结果 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            valid = research_design.validate_payload(base, payload)
            self.assertNotIn(
                "RD.CONSISTENCY.CONTRADICTION",
                {issue.code for issue in valid.errors},
            )
            payload["claims"][0]["evidence_ids"] = []
            contradictory = research_design.validate_payload(base, payload)
            self.assertIn(
                "RD.CONSISTENCY.CONTRADICTION",
                {issue.code for issue in contradictory.errors},
            )

    def test_id_bound_bearing_row_cannot_upgrade_noncausal_claim(self) -> None:
        temporary, base, payload = self.workspace("interpretive", "interpretive", "explanatory")
        with temporary:
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "| Claim ID | Evidence ID | Interpretation |",
                        "|---|---|---|",
                        "| CL01 | E01 | 该材料证明制度信号导致执行结果改善 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload)
            self.assertIn("RD.CAUSAL.OVERCLAIM", {issue.code for issue in result.errors})

    def test_documented_hyphenated_id_prefixes_resolve_across_artifacts(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["research_question"]["id"] = "RQ-001"
            payload["design"]["id"] = "DSN-001"
            payload["framework"]["id"] = "AF-001"
            payload["concepts"][0]["id"] = "CON-001"
            payload["claims"][0]["id"] = "CLM-001"
            payload["claims"][0]["concept_ids"] = ["CON-001"]
            payload["claims"][0]["evidence_ids"] = ["EVD-001"]
            payload["evidence"][0]["id"] = "EVD-001"
            payload["evidence"][0]["supports_claim_ids"] = ["CLM-001"]
            payload["alternatives"][0]["id"] = "ALT-001"
            payload["falsification_conditions"][0]["id"] = "FAL-001"
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "| Design ID | Claim ID | Evidence ID | Result |",
                        "|---|---|---|---|",
                        "| DSN-001 | CLM-001 | EVD-001 | 有边界的结果 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload, stage="design")
            self.assertNotIn("RD.ID.UNRESOLVED", {issue.code for issue in result.errors})

    def test_boundary_causal_ethics_repro_and_drift_codes(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["design"]["evidence_boundary"] = ""
            payload["routes"]["quantitative_causal"]["comparison_or_counterfactual"] = ""
            payload["design"]["ethics"]["status"] = ""
            payload["design"]["reproducibility"]["status"] = ""
            fingerprinted = base / "confirmed_motivation.md"
            fingerprinted.write_text("current", encoding="utf-8")
            payload["artifact_fingerprints"] = [
                {"path": "confirmed_motivation.md", "sha256": hashlib.sha256(b"old").hexdigest()}
            ]
            result = research_design.validate_payload(base, payload)
            codes = {issue.code for issue in result.issues}
            self.assertTrue(
                {
                    "RD.BOUNDARY.MISSING",
                    "RD.CAUSAL.NO_COUNTERFACTUAL",
                    "RD.ETHICS.MISSING",
                    "RD.REPRO.MISSING",
                    "RD.CONSISTENCY.DRIFT",
                }.issubset(codes)
            )

    def test_causal_language_on_noncausal_route_is_overclaim(self) -> None:
        temporary, base, payload = self.workspace("interpretive", "interpretive", "explanatory")
        with temporary:
            payload["claims"][0]["text"] = "材料证明制度激励导致所有地区必然出现相同结果。"
            result = research_design.validate_payload(base, payload)
            codes = {issue.code for issue in result.issues}
            self.assertIn("RD.CAUSAL.ROUTE_UNDECLARED", codes)
            self.assertIn("RD.CAUSAL.OVERCLAIM", codes)
            self.assertIn("RD.REVIEW.EXTRAPOLATION", codes)

    def test_build_rejects_candidate_source_represented_as_verified(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            registry_path = base / "reference_materials" / "literature_registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            registry["sources"][0].update(
                {
                    "state": "discovered",
                    "citation_scope": "candidate-only",
                    "verification": {},
                }
            )
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload, stage="execution")
            self.assertIn(
                "RD.SOURCE.UNVERIFIED_AS_VERIFIED",
                {issue.code for issue in result.errors},
            )

    def test_valid_quantitative_contract_passes_every_cumulative_stage(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            for stage in ("design", "execution", "build", "audit", "output"):
                result = research_design.validate_payload(base, payload, stage=stage)
                self.assertEqual([], result.errors, (stage, result.issues))
            self.assertEqual(
                [],
                research_design.validate_payload(base, payload, stage="contribution").errors,
            )

    def test_execution_rejects_load_bearing_number_without_evidence_id(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            (base / "results_validation.md").write_text(
                "\n".join(
                    [
                        "# Results Validation",
                        "",
                        "| Results Unit | Claim ID | Result |",
                        "|---|---|---|",
                        "| R1 | CL01 | 处理效应为4.2个百分点 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload, stage="execution")
            self.assertIn("RD.NUMBER.UNREGISTERED", {issue.code for issue in result.errors})

    def test_audit_rejects_omitted_registered_null_result(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["reporting"] = {
                "results": {
                    "E01": {"status": "null", "included": False},
                }
            }
            result = research_design.validate_payload(base, payload, stage="audit")
            self.assertIn("RD.REPORT.SELECTIVE", {issue.code for issue in result.errors})

    def test_review_items_do_not_set_nonzero_status_but_unconfirmed_status_does(self) -> None:
        temporary, base, payload = self.workspace("interpretive", "interpretive", "explanatory")
        with temporary:
            result = research_design.validate_payload(base, payload)
            self.assertEqual("PASS", result.status)
            self.assertIn(
                "RD.RISK.CONSTRUCTION_REUSE",
                {issue.code for issue in result.issues if issue.severity == "WARNING"},
            )
            payload["status"] = "needs-review"
            result = research_design.validate_payload(base, payload)
            self.assertEqual("FAIL", result.status)
            self.assertIn("RD.CONFIRMATION.MISSING", {issue.code for issue in result.errors})

    def test_empirical_artifact_paths_are_required_and_must_exist(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            payload["design"]["artifact_paths"]["model_log"] = "empirical/missing-model-log.md"
            result = research_design.validate_payload(base, payload, stage="build")
            self.assertIn("RD.ARTIFACT.MISSING", {issue.code for issue in result.errors})

    def test_design_stage_does_not_require_result_artifacts_but_build_does(self) -> None:
        temporary, base, payload = self.workspace()
        with temporary:
            for key in (
                research_design.BUILD_EMPIRICAL_ARTIFACTS
                | research_design.BUILD_BRANCH_ARTIFACTS["quantitative_causal"]
            ):
                payload["design"]["artifact_paths"].pop(key, None)
            payload["design"]["reproducibility"]["status"] = "planned"
            design_result = research_design.validate_payload(base, payload, stage="design")
            self.assertEqual([], design_result.errors)
            execution_result = research_design.validate_payload(base, payload, stage="execution")
            execution_codes = {issue.code for issue in execution_result.errors}
            self.assertIn("RD.ARTIFACT.MISSING", execution_codes)
            self.assertIn("RD.REPRO.MISSING", execution_codes)

    def test_migrate_dry_run_writes_nothing_apply_backs_up_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_registry(base, "S01")
            legacy = "\n".join(
                [
                    "# Knowledge Design Matrix",
                    "",
                    "| 字段 | 内容 | 证据/理由 |",
                    "|---|---|---|",
                    "| 已知命题与可信程度 | 已有研究发现制度激励与执行结果相关。 | S01 |",
                    "| 未知、争议或经验异常 | 相似制度下结果相反。 | S01 |",
                    "| 研究问题 | 相似制度下为何形成相反结果？ | S01 |",
                    "| 研究问题主类型 | 解释性 | 按答案任务分类 |",
                    "| O-T-I-P-R 研究问题卡 | O=地方政策；T=2012—2025；I=执行差异；P=制度激励；R=强关系：资源约束改变结果 | S01 |",
                    "| 主张类型 | 因果机制 | S01 |",
                    "| 设计选择及匹配理由 | 比较案例与过程追踪 | 观察机制节点 |",
                    "| 推断上限 | 只解释所比较案例。 | S01 |",
                    "",
                ]
            )
            matrix = base / "knowledge_design_matrix.md"
            matrix.write_text(legacy, encoding="utf-8")
            before = sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))
            code, preview = research_design.migrate_contract(base, apply=False)
            after = sorted(path.relative_to(base).as_posix() for path in base.rglob("*"))
            self.assertEqual(0, code)
            self.assertEqual(before, after)
            self.assertIn('"mode": "dry-run"', preview)

            code, _ = research_design.migrate_contract(base, apply=True)
            self.assertEqual(0, code)
            contract = json.loads((base / "research_design.json").read_text(encoding="utf-8"))
            self.assertEqual("needs-review", contract["status"])
            backups = list((base / "migration" / "research_design_v3").glob("*.v2.md"))
            self.assertEqual(1, len(backups))
            self.assertEqual(legacy, backups[0].read_text(encoding="utf-8"))
            self.assertIn(research_design.GENERATED_MARKER, matrix.read_text(encoding="utf-8"))

            snapshot = {
                path.relative_to(base).as_posix(): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            code, message = research_design.migrate_contract(base, apply=True)
            self.assertEqual(0, code)
            self.assertIn("already complete", message)
            repeated = {
                path.relative_to(base).as_posix(): path.read_bytes()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(snapshot, repeated)

    def test_future_schema_blocks_migration_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "research_design.json").write_text(
                json.dumps({"schema_version": "cnki-research-design/v99"}),
                encoding="utf-8",
            )
            code, message = research_design.migrate_contract(base, apply=False)
            self.assertEqual(2, code)
            self.assertIn("future", message)
            self.assertEqual(2, research_design.render_command(base))
            self.assertEqual(
                1,
                research_design.validate_command(base, write=True, json_stdout=True),
            )
            self.assertFalse((base / "research_design_check.json").exists())
            self.assertFalse((base / "knowledge_design_matrix.md").exists())

    def test_any_unsupported_schema_is_read_only_even_with_write_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_registry(base, "S01")
            (base / "sentinel.txt").write_text("unchanged", encoding="utf-8")
            (base / "research_design.json").write_text(
                json.dumps({"schema_version": "other-design/v1"}),
                encoding="utf-8",
            )
            before = {
                path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(
                1,
                research_design.validate_command(base, write=True, json_stdout=True),
            )
            after = {
                path.relative_to(base).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in base.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_portable_schema_asset_is_locked_to_validator_enums(self) -> None:
        schema = json.loads(research_design.SCHEMA_ASSET_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            research_design.SCHEMA_VERSION,
            schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            research_design.FAMILIES,
            set(schema["$defs"]["design"]["properties"]["family"]["enum"]),
        )
        self.assertEqual(
            research_design.CLAIM_TYPES,
            set(schema["$defs"]["claim"]["properties"]["type"]["enum"]),
        )
        self.assertEqual(
            research_design.QUESTION_TYPES,
            set(schema["$defs"]["research_question"]["properties"]["primary_type"]["enum"]),
        )
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(0, research_design.schema_command())
        self.assertEqual(
            research_design.SCHEMA_VERSION,
            json.loads(output.getvalue())["properties"]["schema_version"]["const"],
        )

    def test_cli_json_shape_and_error_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_registry(base, "S01")
            payload = base_contract()
            create_empirical_artifacts(base, payload)
            payload["claims"][0]["source_ids"] = ["S99"]
            (base / "research_design.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            self.assertEqual(
                1,
                research_design.main(["validate", str(base), "--json", "--write"]),
            )
            report = json.loads((base / "research_design_check.json").read_text(encoding="utf-8"))
            self.assertEqual("FAIL", report["status"])
            self.assertIn(
                "RD.SOURCE.UNKNOWN",
                {issue["code"] for issue in report["issues"]},
            )


if __name__ == "__main__":
    unittest.main()
