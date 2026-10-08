#!/usr/bin/env python3
"""Contract and adapter tests for cnki-research-design/v2."""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


research_design = load_module("research_design_v31_tests", HERE / "research_design.py")
v2 = research_design._v2_module()


def _replace_review(value):
    if isinstance(value, dict):
        return {key: _replace_review(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_review(item) for item in value]
    if isinstance(value, str) and value.startswith("needs-review"):
        return "已记录具体依据、适用边界、执行步骤与可复核位置。"
    return value


def confirmed_design(family: str = "quantitative") -> dict:
    payload = _replace_review(copy.deepcopy(v2.template_payload(family)))
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
    question = payload["research_questions"][0]
    question["confirmation"] = {
        "status": "confirmed",
        "source": "user-message-2026-07-29",
        "confirmed_at": "2026-07-29T10:00:00+08:00",
    }
    route = payload["method_routes"][0]
    route["permissions"] = {
        "status": "public" if route["empirical"] else "not-required",
        "note": "材料访问与许可条件已经逐项登记。",
    }
    route["ethics"] = {
        "status": "not-required",
        "note": "未涉及可识别个人或干预；如材料边界变化则重新审查。",
    }
    route["reproducibility"] = {
        "status": "ready",
        "note": "已记录版本、参数、环境和合法复现路径。",
    }
    route["evidence_separation"] = {
        "status": "separated",
        "note": "探索、建构与验证材料按清单分离并保留上游来源。",
    }
    route["sampling_or_selection"] = {
        "strategy": "按预先登记的纳入与排除规则选择材料。",
        "rationale": "选择逻辑对应研究问题，并明确未覆盖对象。",
    }
    route["artifact_paths"] = {}
    fields = route["method_fields"]
    if family == "quantitative":
        fields["task_type"] = "descriptive"
    elif family == "survey":
        fields["modes"] = ["questionnaire"]
    elif family == "review":
        fields["review_type"] = "narrative"
        fields["reporting_standard"] = "叙述式综述不冒充系统综述，完整披露检索与综合边界。"
    elif family == "experiment":
        fields["assignment_mechanism"] = "按入组顺序进行机械分配，未声称随机分配。"
        fields["randomization_verification"] = "分配记录表保留顺序、执行人和时间戳。"
    for declaration in payload["governance"].values():
        declaration["status"] = "declared"
        declaration["note"] = "已作出明确披露并保留可审计记录。"
    payload["concepts"][0]["measurement"] = {
        "status": "documented",
        "note": "概念识别规则、误差来源和不适用条件已经记录。",
    }
    return payload


def validate(payload: dict):
    result = research_design.ValidationResult()
    v2.validate_payload(Path("."), payload, stage="design", result=result)
    return result


class ResearchDesignV2Tests(unittest.TestCase):
    def test_every_registered_family_has_a_valid_route(self) -> None:
        registry = v2.load_adapter_registry()
        families = sorted(set(registry["families"]) - {"unresolved"})
        self.assertEqual(19, len(families))
        for family in families:
            with self.subTest(family=family):
                result = validate(confirmed_design(family))
                self.assertEqual([], result.errors, [issue.code for issue in result.issues])

    def test_template_is_v2_and_never_pretends_to_be_confirmed(self) -> None:
        template = v2.template_payload("historical")
        self.assertEqual("cnki-research-design/v2", template["schema_version"])
        self.assertEqual("needs-review", template["status"])
        result = validate(template)
        self.assertIn("RD.CONFIRMATION.MISSING", {issue.code for issue in result.errors})

    def test_keyword_only_gap_claim_cannot_pass_as_a_diagnosis(self) -> None:
        payload = confirmed_design("quantitative")
        payload["knowledge_state"]["gap_authenticity"] = (
            "知识、概念、理论、实证、方法、群体和实践空白全部存在。"
        )
        result = validate(payload)
        self.assertIn("RD.GAP.DIAGNOSIS", {issue.code for issue in result.errors})

    def test_design_cannot_silently_change_confirmed_gap_core(self) -> None:
        payload = confirmed_design("quantitative")
        question = payload["research_questions"][0]
        confirmed_gap = payload["knowledge_state"]["gap_authenticity"].replace(
            "Primary Locus=theory-explanation",
            "Primary Locus=scope-population",
        )
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "confirmed_motivation.md").write_text(
                "\n".join(
                    [
                        "# Confirmed Motivation",
                        "",
                        "| Field | Content |",
                        "|---|---|",
                        f"| Confirmed research question | {question['text']} |",
                        f"| Primary question type | {question['primary_type']} |",
                        f"| Gap Diagnosis | {confirmed_gap} |",
                    ]
                ),
                encoding="utf-8",
            )
            result = research_design.validate_payload(base, payload, stage="design")
            self.assertTrue(
                any(
                    issue.code == "RD.CONSISTENCY.DRIFT" and "gap" in issue.message.lower()
                    for issue in result.errors
                ),
                [issue.message for issue in result.errors],
            )

    def test_repetitive_keyword_gaming_is_blocked(self) -> None:
        payload = confirmed_design("survey")
        payload["method_routes"][0]["method_rationale"] = "抽样抽样抽样抽样抽样抽样"
        result = validate(payload)
        self.assertIn("RD.CONTENT.REPETITIVE", {issue.code for issue in result.errors})

    def test_fake_randomization_is_blocked(self) -> None:
        payload = confirmed_design("experiment")
        fields = payload["method_routes"][0]["method_fields"]
        fields["assignment_mechanism"] = "声称采用随机分配"
        fields["randomization_verification"] = "研究者表示确实随机"
        result = validate(payload)
        self.assertIn(
            "RD.EXPERIMENT.RANDOMIZATION_UNVERIFIED",
            {issue.code for issue in result.errors},
        )

    def test_auditable_randomization_is_legal(self) -> None:
        payload = confirmed_design("experiment")
        fields = payload["method_routes"][0]["method_fields"]
        fields["assignment_mechanism"] = "按计算机生成序列随机分配"
        fields["randomization_verification"] = "随机种子、分配代码和不可改写分配日志均已冻结。"
        result = validate(payload)
        self.assertNotIn(
            "RD.EXPERIMENT.RANDOMIZATION_UNVERIFIED",
            {issue.code for issue in result.errors},
        )

    def test_noncausal_quantitative_route_cannot_claim_identification(self) -> None:
        payload = confirmed_design("quantitative")
        route = payload["method_routes"][0]
        route["method_rationale"] = "普通回归识别了政策的因果效应。"
        result = validate(payload)
        self.assertIn("RD.CAUSAL.TASK_MISMATCH", {issue.code for issue in result.errors})

    def test_causal_capability_is_claim_specific_and_explicitly_declared(self) -> None:
        payload = confirmed_design("process_tracing")
        route = payload["method_routes"][0]
        route["function"] = "identification"
        claim = payload["claims"][0]
        claim["type"] = "causal_effect"
        result = validate(payload)
        self.assertIn("RD.CAUSAL.ROUTE_UNDECLARED", {issue.code for issue in result.errors})

        claim["type"] = "causal_mechanism"
        result = validate(payload)
        self.assertNotIn(
            "RD.CAUSAL.ROUTE_UNDECLARED",
            {issue.code for issue in result.errors},
        )

    def test_qca_fixed_threshold_is_review_not_fail(self) -> None:
        payload = confirmed_design("qca")
        payload["method_routes"][0]["method_fields"]["calibration_basis"] = (
            "所有研究一律使用固定阈值 0.8，不结合案例知识。"
        )
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertIn("RD.REVIEW.QCA_THRESHOLD", {issue.code for issue in result.issues})

    def test_grounded_saturation_count_is_review_not_fail(self) -> None:
        payload = confirmed_design("grounded_theory")
        payload["method_routes"][0]["method_fields"]["saturation_rationale"] = (
            "访谈达到20人即自动理论饱和。"
        )
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertIn("RD.REVIEW.SATURATION", {issue.code for issue in result.issues})

    def test_network_independence_assumption_is_reviewed(self) -> None:
        payload = confirmed_design("social_network")
        payload["method_routes"][0]["method_fields"]["dependence_structure"] = (
            "把所有节点视为相互独立同分布。"
        )
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertIn("RD.REVIEW.NETWORK_DEPENDENCE", {issue.code for issue in result.issues})

    def test_historical_shared_provenance_cannot_be_independent(self) -> None:
        payload = confirmed_design("historical")
        fields = payload["method_routes"][0]["method_fields"]
        fields["transmission_chain"] = "两份档案来自同源传递链。"
        fields["corroboration"] = "将这两份同源材料作为相互独立印证。"
        result = validate(payload)
        self.assertIn("RD.EVIDENCE.FALSE_INDEPENDENCE", {issue.code for issue in result.errors})

    def test_computational_overlap_cannot_be_held_out(self) -> None:
        payload = confirmed_design("computational")
        payload["method_routes"][0]["method_fields"]["train_validation_test"] = (
            "训练集与验证集共享同一批样本，但仍称为独立 held-out 验证。"
        )
        result = validate(payload)
        self.assertIn("RD.VALIDATION.LEAKAGE", {issue.code for issue in result.errors})

    def test_digital_trace_population_equivalence_is_reviewed(self) -> None:
        payload = confirmed_design("computational")
        payload["method_routes"][0]["inference_ceiling"] = "平台数据代表总体全部人口。"
        result = validate(payload)
        self.assertEqual([], result.errors)
        self.assertIn(
            "RD.REVIEW.DIGITAL_TRACE_COVERAGE",
            {issue.code for issue in result.issues},
        )

    def test_prisma_is_required_only_for_systematic_review(self) -> None:
        narrative = confirmed_design("review")
        self.assertEqual([], validate(narrative).errors)
        systematic = confirmed_design("review")
        systematic["method_routes"][0]["method_fields"]["review_type"] = "systematic"
        systematic["method_routes"][0]["method_fields"]["reporting_standard"] = (
            "仅提供普通叙述式说明。"
        )
        result = validate(systematic)
        self.assertIn("RD.REVIEW.PRISMA_MISSING", {issue.code for issue in result.errors})

    def test_literature_workflow_is_structured_for_every_design(self) -> None:
        payload = confirmed_design("survey")
        del payload["knowledge_state"]["search_scope"]
        result = validate(payload)
        self.assertIn("RD.FIELD.MISSING", {issue.code for issue in result.errors})

        payload = confirmed_design("survey")
        payload["knowledge_state"]["review_type"] = "systematic"
        result = validate(payload)
        self.assertIn("RD.REVIEW.ROUTE_MISSING", {issue.code for issue in result.errors})

    def test_concepts_require_a_real_recognition_rule_and_measurement_declaration(self) -> None:
        payload = confirmed_design("conceptual")
        payload["concepts"][0]["operationalization_or_recognition"] = []
        result = validate(payload)
        self.assertIn("RD.MEASUREMENT.MISSING", {issue.code for issue in result.errors})

        payload = confirmed_design("conceptual")
        payload["concepts"][0]["measurement"] = {}
        result = validate(payload)
        self.assertIn("RD.FIELD.MISSING", {issue.code for issue in result.errors})

    def test_multi_route_requires_real_integration(self) -> None:
        payload = confirmed_design("survey")
        second = copy.deepcopy(payload["method_routes"][0])
        second["id"] = "DSN-002"
        second["family"] = "content_analysis"
        second["role"] = "supporting"
        adapter = v2.load_adapter_registry()["families"]["content_analysis"]
        second["method_fields"] = {
            field: "已记录具体依据、适用边界、执行步骤与可复核位置。"
            for field in adapter["design_fields"]
        }
        payload["method_routes"].append(second)
        payload["claims"][0]["design_ids"].append("DSN-002")
        payload["evidence"][0]["design_ids"].append("DSN-002")
        payload["integration"]["route_order"].append("DSN-002")
        result = validate(payload)
        self.assertIn("RD.INTEGRATION.MISSING", {issue.code for issue in result.errors})

    def test_schema_cli_serves_all_versions_and_template_writes_v4(self) -> None:
        for version, expected in (
            ("v1", "cnki-research-design/v1"),
            ("v2", "cnki-research-design/v2"),
            ("v3", "cnki-research-design/v3"),
            ("v4", "cnki-research-design/v4"),
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(0, research_design.schema_command(version))
            self.assertEqual(
                expected,
                json.loads(output.getvalue())["properties"]["schema_version"]["const"],
            )
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "research_design.json"
            self.assertEqual(0, research_design.template_command("normative", target))
            self.assertEqual(
                "cnki-research-design/v4",
                json.loads(target.read_text(encoding="utf-8"))["schema_version"],
            )

    def test_v1_migration_preserves_confirmation_ids_paths_and_hashes(self) -> None:
        legacy = research_design.migrate_payload("")
        legacy["status"] = "confirmed"
        legacy["research_question"]["id"] = "RQ-LOCKED"
        legacy["design"]["id"] = "DSN-LOCKED"
        legacy["design"]["artifact_paths"] = {"code": "analysis/main.R"}
        legacy["artifact_fingerprints"] = [
            {"path": "analysis/main.R", "sha256": "a" * 64}
        ]
        legacy["concepts"][0]["source_ids"] = ["S001"]
        legacy["claims"][0]["source_ids"] = ["S001"]
        legacy["evidence"][0]["source_ids"] = ["S001"]

        migrated = v2.migrate_v1_payload(legacy)

        self.assertEqual("needs-review", migrated["status"])
        self.assertEqual("RQ-LOCKED", migrated["research_questions"][0]["id"])
        self.assertEqual(
            "confirmed",
            migrated["research_questions"][0]["confirmation"]["status"],
        )
        self.assertEqual("DSN-LOCKED", migrated["method_routes"][0]["id"])
        self.assertEqual(
            {"code": "analysis/main.R"},
            migrated["method_routes"][0]["artifact_paths"],
        )
        self.assertEqual(["S001"], migrated["concepts"][0]["source_ids"])
        self.assertEqual(["S001"], migrated["claims"][0]["source_ids"])
        self.assertEqual(["S001"], migrated["evidence"][0]["source_ids"])
        self.assertEqual(legacy["artifact_fingerprints"], migrated["artifact_fingerprints"])
        self.assertTrue(migrated["migration"]["user_confirmation_preserved"])

    def test_missing_legacy_claim_type_does_not_select_review_route(self) -> None:
        legacy = research_design.migrate_payload("")
        self.assertEqual("needs-review", legacy["design"]["claim_type"])
        self.assertEqual("needs-review", legacy["design"]["family"])
        migrated = v2.migrate_v1_payload(legacy)
        self.assertEqual("unresolved", migrated["method_routes"][0]["family"])
        self.assertEqual("needs-review", migrated["status"])

    def test_migration_dry_run_is_zero_write_apply_is_idempotent_and_future_blocks(self) -> None:
        legacy = research_design.migrate_payload("")
        legacy["status"] = "confirmed"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            contract = base / "research_design.json"
            original = json.dumps(legacy, ensure_ascii=False, indent=2) + "\n"
            contract.write_text(original, encoding="utf-8")

            code, preview = research_design.migrate_contract(base, apply=False, to="v2")
            self.assertEqual(0, code)
            self.assertEqual(original, contract.read_text(encoding="utf-8"))
            self.assertFalse((base / "migration").exists())
            self.assertEqual("dry-run", json.loads(preview)["mode"])

            code, _message = research_design.migrate_contract(base, apply=True, to="v2")
            self.assertEqual(0, code)
            migrated_once = contract.read_text(encoding="utf-8")
            code, message = research_design.migrate_contract(base, apply=True, to="v2")
            self.assertEqual(0, code)
            self.assertEqual(migrated_once, contract.read_text(encoding="utf-8"))
            self.assertIn("already complete", message)

        with tempfile.TemporaryDirectory() as tmp:
            contract = Path(tmp) / "research_design.json"
            contract.write_text(
                '{"schema_version":"cnki-research-design/v99"}',
                encoding="utf-8",
            )
            code, message = research_design.migrate_contract(Path(tmp), apply=True, to="v2")
            self.assertEqual(2, code)
            self.assertIn("future", message)
            self.assertEqual(
                '{"schema_version":"cnki-research-design/v99"}',
                contract.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
