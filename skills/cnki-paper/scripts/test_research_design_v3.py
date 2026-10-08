#!/usr/bin/env python3
"""Contract, capability, and migration tests for cnki-research-design/v3."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


research_design = load_module("research_design_v32_tests", HERE / "research_design.py")
v2 = research_design._v2_module()
v3 = research_design._v3_module()


def _replace_review(value):
    if isinstance(value, dict):
        return {key: _replace_review(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_review(item) for item in value]
    if isinstance(value, str) and value.startswith("needs-review"):
        return "已登记具体事实、边界、理由与可复核位置。"
    return value


def confirmed_design(family: str) -> dict:
    payload = _replace_review(copy.deepcopy(v3.template_payload(family, v2)))
    payload["status"] = "confirmed"
    payload["knowledge_state"]["gap_authenticity"] = (
        "Status=corroborated；Primary Locus=theory-explanation；"
        "Obstruction=inconsistent-or-incomparable；"
        "Gap Claim=在相同制度压力下，现有理论仍不能区分资源约束何时改变执行机制；"
        "Evidence Basis=SYN-GAP-1 综合了支持、负例与可比性判断；"
        "Rival Explanations=已检查发表时滞、术语错配、相邻覆盖及仅因对象新而低命中；"
        "Research Responsibility=比较同一结果并检验两种解释的区分性预期；"
        "Withdrawal Condition=若差异完全由统计口径或不可比时期造成则撤回该空白"
    )
    payload["research_questions"][0]["confirmation"] = {
        "status": "confirmed",
        "source": "user-message-2026-07-30",
        "confirmed_at": "2026-07-30T10:00:00+08:00",
    }
    route = payload["method_routes"][0]
    route["permissions"] = {
        "status": "public" if route["empirical"] else "not-required",
        "note": "材料访问、使用和传播权限已经登记。",
    }
    route["ethics"] = {
        "status": "not-required",
        "note": "未涉及可识别个人或干预；边界改变时重新审查。",
    }
    route["reproducibility"] = {
        "status": "ready",
        "note": "版本、参数、环境与合法复现路径已经冻结。",
    }
    route["evidence_separation"] = {
        "status": "separated",
        "note": "理论形成、测量建构和独立评价材料已经区分。",
    }
    route["sampling_or_selection"] = {
        "strategy": "依据预先登记的总体、边界与纳入排除规则选择。",
        "rationale": "选择服务于理论目的，并披露未覆盖对象。",
    }
    route["artifact_paths"] = {}
    fields = route["method_fields"]
    if family == "quantitative":
        fields["task_type"] = "descriptive"
    elif family == "survey":
        fields["modes"] = ["questionnaire"]
    elif family == "review":
        fields["review_type"] = "narrative"
    elif family == "experiment":
        fields["assignment_mechanism"] = "按计算机生成序列随机分配。"
        fields["randomization_verification"] = "随机种子、分配代码和分配日志均已冻结。"
    for declaration in payload["governance"].values():
        declaration["status"] = "declared"
        declaration["note"] = "已经披露并保留可审计记录。"
    payload["concepts"][0]["measurement"] = {
        "status": "documented",
        "note": "概念识别、误差来源和不适用条件已经登记。",
    }
    if family == "historical":
        payload["case_design"] = copy.deepcopy(v3._case_design_template("normative"))
        payload["case_design"]["rationale"] = "本历史研究不采用案例导向剖面。"
    elif payload["case_design"]["applicability"] == "active":
        for case in payload["case_design"]["cases"]:
            case["outcome_knowledge_at_selection"] = "unknown"
            for role in case["material_roles"]:
                role["independence"] = "separated"
    return payload


def validate(payload: dict):
    result = research_design.ValidationResult()
    v3.validate_payload(Path("."), payload, stage="design", result=result, v2=v2)
    return result


class ResearchDesignV3Tests(unittest.TestCase):
    def test_every_registered_family_has_a_coherent_v3_route(self) -> None:
        families = sorted(set(v2.load_adapter_registry()["families"]) - {"unresolved"})
        self.assertEqual(19, len(families))
        for family in families:
            with self.subTest(family=family):
                result = validate(confirmed_design(family))
                self.assertEqual([], result.errors, [issue.code for issue in result.issues])

    def test_general_case_study_cannot_claim_mechanism(self) -> None:
        payload = confirmed_design("case_study")
        payload["claims"][0]["type"] = "causal_mechanism"
        payload["method_routes"][0]["function"] = "identification"
        result = validate(payload)
        self.assertIn(
            "RD.CLAIM.CAPABILITY_EXCEEDED",
            {issue.code for issue in result.errors},
        )

    def test_process_tracing_requires_registered_mechanism_analysis(self) -> None:
        payload = confirmed_design("process_tracing")
        payload["case_design"]["within_case_analyses"] = []
        payload["case_design"]["integration"]["within_case_analysis_ids"] = []
        result = validate(payload)
        codes = {issue.code for issue in result.errors}
        self.assertIn("RD.CASE.PROCESS_TRACING_MISSING", codes)
        self.assertIn("RD.CLAIM.MECHANISM_TRACE_MISSING", codes)

    def test_congruence_cannot_be_relabelled_as_mechanism(self) -> None:
        payload = confirmed_design("congruence_analysis")
        payload["claims"][0]["type"] = "causal_mechanism"
        payload["method_routes"][0]["function"] = "identification"
        result = validate(payload)
        self.assertIn(
            "RD.CLAIM.CAPABILITY_EXCEEDED",
            {issue.code for issue in result.errors},
        )

    def test_qca_configuration_is_not_an_average_effect(self) -> None:
        payload = confirmed_design("qca")
        self.assertEqual([], validate(payload).errors)
        payload["claims"][0]["type"] = "causal_effect"
        result = validate(payload)
        self.assertIn(
            "RD.CLAIM.CAPABILITY_EXCEEDED",
            {issue.code for issue in result.errors},
        )

    def test_cross_case_design_needs_two_distinct_cases(self) -> None:
        payload = confirmed_design("comparative")
        payload["case_design"]["comparisons"][0]["case_ids"] = ["CAS-001"]
        result = validate(payload)
        self.assertIn(
            "RD.CASE.CROSS_CASE_COUNT",
            {issue.code for issue in result.errors},
        )

    def test_outcome_aware_selection_is_review_not_hard_failure(self) -> None:
        payload = confirmed_design("case_study")
        payload["case_design"]["cases"][0]["outcome_knowledge_at_selection"] = "known"
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertIn(
            "RD.REVIEW.CASE_OUTCOME_AWARE_SELECTION",
            {issue.code for issue in result.issues},
        )

    def test_case_boundary_and_time_are_hard_facts(self) -> None:
        payload = confirmed_design("case_study")
        payload["case_design"]["cases"][0]["time_scope"] = ""
        result = validate(payload)
        self.assertIn(
            "RD.CASE.BOUNDARY_MISSING",
            {issue.code for issue in result.errors},
        )

    def test_case_ids_are_global_and_prefix_typed(self) -> None:
        payload = confirmed_design("comparative")
        payload["case_design"]["cases"][1]["id"] = "CAS-001"
        result = validate(payload)
        self.assertIn("RD.ID.DUPLICATE", {issue.code for issue in result.errors})

    def test_same_material_cannot_construct_and_independently_validate(self) -> None:
        payload = confirmed_design("case_study")
        roles = payload["case_design"]["cases"][0]["material_roles"]
        roles[:] = [
            {
                "material_id": "MAT-001",
                "role": "theory_generation",
                "independence": "shared-source-disclosed",
            },
            {
                "material_id": "MAT-001",
                "role": "validation",
                "independence": "independent",
            },
        ]
        result = validate(payload)
        self.assertIn(
            "RD.CASE.MATERIAL_CIRCULARITY",
            {issue.code for issue in result.errors},
        )

    def test_noncase_route_has_legal_explicit_nonapplicability(self) -> None:
        payload = confirmed_design("normative")
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertEqual("not-applicable", payload["case_design"]["applicability"])

    def test_case_route_cannot_use_nonapplicability_escape(self) -> None:
        payload = confirmed_design("case_study")
        payload["case_design"] = copy.deepcopy(v3._case_design_template("normative"))
        result = validate(payload)
        self.assertIn(
            "RD.CASE.APPLICABILITY_MISMATCH",
            {issue.code for issue in result.errors},
        )

    def test_v2_migration_is_conservative_and_preserves_stable_ids(self) -> None:
        legacy_noncase = v2.template_payload("normative")
        legacy_noncase["status"] = "confirmed"
        legacy_noncase["research_questions"][0]["id"] = "RQ-LOCKED"
        migrated_noncase = v3.migrate_payload(legacy_noncase, v2=v2)
        self.assertEqual("RQ-LOCKED", migrated_noncase["research_questions"][0]["id"])
        self.assertEqual("not-applicable", migrated_noncase["case_design"]["applicability"])

        legacy_case = v2.template_payload("qca")
        legacy_case["method_routes"][0]["id"] = "DSN-LOCKED"
        migrated_case = v3.migrate_payload(legacy_case, v2=v2)
        self.assertEqual("DSN-LOCKED", migrated_case["method_routes"][0]["id"])
        self.assertEqual("needs-review", migrated_case["case_design"]["applicability"])
        self.assertEqual([], migrated_case["case_design"]["cases"])

    def test_v3_render_emits_six_generated_views(self) -> None:
        payload = confirmed_design("comparative")
        with tempfile.TemporaryDirectory() as tmp:
            written = v3.render_views(
                Path(tmp),
                payload,
                allow_unmanaged_replace=False,
                v2=v2,
            )
            self.assertEqual(6, len(written))
            case_view = Path(tmp) / "case_design_matrix.md"
            self.assertIn(research_design.GENERATED_MARKER, case_view.read_text(encoding="utf-8"))
            self.assertIn("CMP-001", case_view.read_text(encoding="utf-8"))

    def test_v3_schema_asset_and_default_template(self) -> None:
        schema = json.loads(v3.SCHEMA_ASSET_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            "cnki-research-design/v3",
            schema["properties"]["schema_version"]["const"],
        )
        template = v3.template_payload("process_tracing", v2)
        self.assertEqual("cnki-research-design/v3", template["schema_version"])
        self.assertEqual("needs-review", template["status"])
        self.assertEqual("active", template["case_design"]["applicability"])

    def test_cross_artifact_id_parser_recognizes_v3_and_legacy_ids(self) -> None:
        found = research_design._artifact_internal_ids(
            "RQ-001 C1 T01 EV-02 DSN-001 CUN-LOCAL CAS-NORTH "
            "SCP-TIME CMP-PAIR WCA-TRACE"
        )
        self.assertEqual(
            {
                "RQ-001",
                "C1",
                "T01",
                "EV-02",
                "DSN-001",
                "CUN-LOCAL",
                "CAS-NORTH",
                "SCP-TIME",
                "CMP-PAIR",
                "WCA-TRACE",
            },
            found,
        )

    def test_causal_prohibition_is_not_an_assertive_causal_claim(self) -> None:
        self.assertFalse(
            research_design._has_assertive_causal_text(
                "该材料不得写成严格因果识别，也不能证明长期因果效果。"
            )
        )
        self.assertTrue(
            research_design._has_assertive_causal_text(
                "该材料证明制度安排导致结果改善。"
            )
        )


if __name__ == "__main__":
    unittest.main()
