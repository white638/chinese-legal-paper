#!/usr/bin/env python3
"""Regression tests for the problem-led workflow contract."""

from __future__ import annotations

import importlib.util
import hashlib
import json
from unittest import mock
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent


def load_module():
    path = HERE / "problem_orientation_check.py"
    spec = importlib.util.spec_from_file_location("problem_orientation_check", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


problem = load_module()


def write_orientation(base: Path, *, method_role: str = "feasibility-only；方法与数据服从问题") -> None:
    (base / "problem_orientation.md").write_text(
        """# Problem Orientation

| Field | Content |
|---|---|
| Orientation ID | PO-01 |
| Practical encounter | 地方公开项目清单显示相似财政压力下出现了不同投资选择。 |
| Affected actors | 地方决策者、公共服务使用者与承担财政风险的居民。 |
| Tension or unknown | 同一考核制度下项目偏好仍不一致，单一激励解释无法消解该异常。 |
| Why it matters | 若不能解释差异，就无法判断考核改革究竟改变了何种治理行为。 |
| Common-sense or imported frame at risk | 经济激励会自动产生一致政策反应这一常识性判断可能需要修正。 |
| What could change our mind | 若跨地区材料显示差异完全由口径造成，就撤回或改写当前定向。 |
| Origin | user-provided and practice-observation |
| Epistemic status | provisional; user-provided context, not verified fact |
| Researcher position and access | 可接近公开预算与政策过程材料，但缺少内部决策记录。 |
| Method/data role | """ + method_role + """ |
| Confirmation source | 用户本轮题面与明确任务记录。 |
""",
        encoding="utf-8",
    )


WORKING_TITLE = "增长考核何以塑造地方大型项目投资偏好"


def write_research_commitments(
    base: Path,
    *,
    title_authority: str = "user-approved-working；用户确认的工作标题",
    title_revision_rule: str = "reconfirm-if-substantive；实质性改题必须由用户再次确认",
) -> None:
    (base / "motivation_options_after_research.md").write_text(
        """# Options

| Option | Problem Orientation IDs | Problem Warrant |
|---|---|---|
| O1 | PO-01 | 解释相同制度下的差异可修正激励必然产生同质反应的常识判断。 |
""",
        encoding="utf-8",
    )
    (base / "confirmed_motivation.md").write_text(
        """# Confirmed Motivation

| Field | Content |
|---|---|
| Problem Orientation IDs | PO-01 |
| Why the problem remains worth pursuing | 定向补检后，既有研究仍不能解释相同制度压力下的异质选择。 |
| Non-trivial answer test | 回答必须识别改变激励作用方向的条件，而非再次证明存在考核压力。 |
| Working Title | """ + WORKING_TITLE + """ |
| Title Authority | """ + title_authority + """ |
| Title Function | question-led；问题导向 |
| Title Claim Boundary | 标题只压缩问题，不预断结果、机制成立、因果方向或概念创新。 |
| Title Revision Rule | """ + title_revision_rule + """ |
""",
        encoding="utf-8",
    )


def write_knowledge_fixture(base, prior, posterior):
    from literature_analysis import registry_binding_digest
    refs = base / "reference_materials"
    refs.mkdir(exist_ok=True)
    content = refs / "baseline.txt"
    content.write_text("A synthetic prior study for deterministic tests, not research evidence.", encoding="utf-8")
    registry = {"sources": [{"source_id": "CNKI-R003", "doi": "10.1000/baseline", "state": "content-verified", "citation_scope": "final-source", "local_file": "reference_materials/baseline.txt", "sha256": hashlib.sha256(content.read_bytes()).hexdigest(), "verification": {"method": "full-text"}}]}
    (refs / "literature_registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (base / "literature_analysis.json").write_text(json.dumps({"registry_binding": {"source_ids": ["CNKI-R003"], "digest": registry_binding_digest(registry, ["CNKI-R003"])}, "syntheses": [{"synthesis_id": "SYN-02", "source_links": [{"source_id": "CNKI-R003"}]}]}), encoding="utf-8")
    (base / "research_design.json").write_text(json.dumps({"knowledge_baseline": {"origin": "retrospective", "judgement": prior, "source_refs": ["CNKI-R003", "SYN-02"]}}, ensure_ascii=False), encoding="utf-8")
    (base / "method_execution.json").write_text(json.dumps({"knowledge_update": {
        "kind": "boundary-refinement", "baseline_origin": "retrospective", "supported_update": posterior,
        "work_performed": "Checked comparable observations across the documented fiscal boundary.",
        "result_interpretation": "The accepted results narrow the scope of the existing explanation.",
        "limitations": "The evidence does not establish transfer beyond these observations.",
        "semantic_assessment": {"status": "supported", "rationale": "Scope changes are linked to evidence rather than a change of phrasing."},
        "result_ids": ["RES-001"], "claim_ids": ["CLM-01"]
    }}, ensure_ascii=False), encoding="utf-8")


def accepted_authority(*_args):
    return {"status": "PASS", "results": {"RES-001": {"allowed_uses": ["claim_support", "negative_or_null_report"], "claim_allowed_uses": {"CLM-01": ["claim_support", "negative_or_null_report"]}}}}


def write_execution_reappraisal(
    base: Path,
    disposition: str = "retain：执行结果保留问题并收窄范围",
    gain: str = "结果识别了财政约束改变可见性激励作用的条件，而非只复述考核影响行为。",
    *,
    prior: str = "读过近五年文献的读者会默认考核压力越大，基层越倾向于形式合规，与财政状况无关。",
    displaced: str = "CNKI-R003（既有考核—合规研究）与 SYN-02 的读者须把财政约束纳入条件。",
    title_disposition: str = "retain：保留工作标题",
    calibrated_title: str = WORKING_TITLE,
    title_basis: str = "EXE-01、CLM-01 与 EV-01 的结果和边界均未要求改写标题承诺。",
    title_user_decision: str = "not-required-retained；保留原题，无实质变更。",
) -> None:
    write_knowledge_fixture(base, prior, gain)
    (base / "confirmed_contribution.md").write_text(
        """# Confirmed Contribution

## Calibration Receipt

| Field | Content |
|---|---|
| Problem disposition after execution | """ + disposition + """ |
| Reader Prior | """ + prior + """ |
| Reader Posterior | """ + gain + """ |
| Displaced Source | """ + displaced + """ |
| Title disposition after execution | """ + title_disposition + """ |
| Evidence-Calibrated Title | """ + calibrated_title + """ |
| Title Revision Basis | """ + title_basis + """ |
| Title User Decision | """ + title_user_decision + """ |
""",
        encoding="utf-8",
    )


class ProblemOrientationTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("prose_packet.discover_execution_authority", side_effect=accepted_authority)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_problem_led_orientation_passes_before_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            self.assertEqual([], problem.validate_problem_orientation(base, "intake"))

    def test_method_first_orientation_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base, method_role="现成回归模型决定并驱动研究问题")
            issues = problem.validate_problem_orientation(base, "intake")
            self.assertTrue(any("tools cannot warrant" in issue or "determine" in issue for issue in issues))

    def test_research_commitment_resolves_problem_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            self.assertEqual([], problem.validate_problem_orientation(base, "research"))

    def test_unknown_orientation_link_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            path = base / "confirmed_motivation.md"
            path.write_text(path.read_text(encoding="utf-8").replace("PO-01", "PO-99"), encoding="utf-8")
            issues = problem.validate_problem_orientation(base, "research")
            self.assertTrue(any("unknown problem orientations" in issue for issue in issues))

    def test_reopen_is_honest_but_blocks_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                "reopen：结果显示原问题只会得到常识性答案",
                title_disposition="reopen：标题随问题一并重开",
                calibrated_title="待用户重新确认的问题与标题",
                title_user_decision="pending renewed user confirmation；等待用户重新确认",
            )
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("return to research" in issue for issue in issues))

    def test_retain_with_nontrivial_gain_passes_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(base)
            self.assertEqual([], problem.validate_problem_orientation(base, "execution"))

    def test_execution_title_basis_accepts_research_design_evd_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                title_basis=(
                    "执行证据EXE-01／主张CLM-01／证据EVD-001的结果和边界均未要求改写标题承诺。"
                ),
            )
            self.assertEqual([], problem.validate_problem_orientation(base, "execution"))

    def test_explicitly_trivial_result_cannot_be_retained_for_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                disposition="retain：方法执行成功，继续写作",
                gain="没有认识增量，只是常识性结论。",
            )
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("no beyond-common-sense gain" in issue for issue in issues))

    def test_lexical_overlap_does_not_decide_contribution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            same = "考核压力越大，基层越倾向于形式合规。"
            write_execution_reappraisal(base, prior=same, gain="基层在考核压力越大时越倾向于形式合规。")
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertFalse(any("polished mediocrity" in issue for issue in issues))
            write_execution_reappraisal(base, prior=same, gain=same)
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertFalse(any("polished mediocrity" in issue for issue in issues))
            write_execution_reappraisal(base, disposition="reopen：先验后验相同，回 research 重新确认问题", prior=same, gain=same)
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertFalse(any("polished mediocrity" in issue for issue in issues))

    def test_displaced_source_must_resolve_to_an_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(base, displaced="无")
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertFalse(any("unresolved" in issue for issue in issues))
            write_execution_reappraisal(base, displaced="某位学者的既有研究需要更新其判断。")
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("must name a registered Source ID" in issue for issue in issues))
            write_execution_reappraisal(base, displaced="INTL-R011 与 https://doi.org/10.1093/sf/soae001 的读者须更新。")
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("unresolved" in issue for issue in issues))

    def test_evidence_calibrated_title_change_requires_user_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                title_disposition="narrow：按证据收窄标题",
                calibrated_title="财政约束下增长考核何以塑造地方大型项目投资偏好",
                title_basis="EXE-01、CLM-01 与 EV-01 只支持财政约束范围内的结果，因此收窄标题。",
                title_user_decision="editorial adjustment only",
            )
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("requires explicit user confirmation" in issue for issue in issues))

    def test_evidence_calibrated_title_change_passes_after_user_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                title_disposition="narrow：按证据收窄标题",
                calibrated_title="财政约束下增长考核何以塑造地方大型项目投资偏好",
                title_basis="EXE-01、CLM-01 与 EV-01 只支持财政约束范围内的结果，因此收窄标题。",
                title_user_decision="user-confirmed；用户确认收窄后的标题。",
            )
            self.assertEqual([], problem.validate_problem_orientation(base, "execution"))

    def test_user_fixed_title_cannot_change_without_explicit_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(
                base,
                title_authority="user-fixed；用户指定原题",
                title_revision_rule="locked；锁定",
            )
            write_execution_reappraisal(
                base,
                title_disposition="revise：证据后修订",
                calibrated_title="财政约束下增长考核何以塑造地方大型项目投资偏好",
                title_basis="EXE-01、CLM-01 与 EV-01 要求按证据范围改写标题。",
                title_user_decision="user-confirmed；用户确认新标题。",
            )
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("without an explicit user unlock" in issue for issue in issues))

    def test_user_fixed_title_can_change_after_confirmed_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(
                base,
                title_authority="user-fixed；用户指定原题",
                title_revision_rule="locked；锁定",
            )
            write_execution_reappraisal(
                base,
                title_disposition="revise：证据后修订",
                calibrated_title="财政约束下增长考核何以塑造地方大型项目投资偏好",
                title_basis="EXE-01、CLM-01 与 EV-01 要求按证据范围改写标题。",
                title_user_decision="user-confirmed unlock；用户确认并解锁原题，同意改题。",
            )
            self.assertEqual([], problem.validate_problem_orientation(base, "execution"))

    def test_title_revision_basis_must_link_execution_claim_and_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            write_orientation(base)
            write_research_commitments(base)
            write_execution_reappraisal(
                base,
                title_basis="EV-01 的证据表明标题范围可以保留。",
            )
            issues = problem.validate_problem_orientation(base, "execution")
            self.assertTrue(any("lacks registered identities" in issue for issue in issues))

    def test_manuscript_audit_does_not_retrofit_orientation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                [],
                problem.validate_problem_orientation(Path(tmp), "audit", task_profile="manuscript_audit"),
            )


if __name__ == "__main__":
    unittest.main()
