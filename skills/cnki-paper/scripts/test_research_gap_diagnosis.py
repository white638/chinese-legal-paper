#!/usr/bin/env python3
"""Forward and adversarial tests for the research-gap diagnosis contract."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
PATH = HERE / "research_gap_diagnosis.py"
SPEC = importlib.util.spec_from_file_location("research_gap_diagnosis_under_test", PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {PATH}")
gap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = gap
SPEC.loader.exec_module(gap)


def valid_gap(
    *,
    locus: str = "theory-explanation",
    obstruction: str = "inconsistent-or-incomparable",
    synthesis: str = "SYN-GAP-1",
) -> str:
    return (
        f"Status=corroborated；Primary Locus={locus}；Obstruction={obstruction}；"
        "Gap Claim=在相同制度压力下，现有理论仍不能区分资源约束何时改变项目选择机制；"
        f"Evidence Basis={synthesis} 综合了支持、负例与可比性判断；"
        "Rival Explanations=已检查发表时滞、术语错配、相邻覆盖及仅因对象新而低命中；"
        "Research Responsibility=比较同一结果并检验两种解释的区分性预期；"
        "Withdrawal Condition=若差异完全由统计口径或不可比时期造成则撤回该空白"
    )


class ResearchGapDiagnosisTests(unittest.TestCase):
    def test_evidence_grounded_two_axis_diagnosis_passes(self) -> None:
        diagnosis, issues = gap.validate_gap_diagnosis(
            valid_gap(), known_synthesis_ids={"SYN-GAP-1"}
        )
        self.assertEqual([], issues)
        self.assertIsNotNone(diagnosis)
        self.assertEqual("theory-explanation", diagnosis.primary_locus)

    def test_seven_labels_without_a_specific_unknown_cannot_game_gate(self) -> None:
        text = (
            "知识空白、概念空白、理论空白、实证空白、方法空白、群体空白和实践空白全部存在；"
            "已排除发表时滞、术语错配和低贡献。"
        )
        _diagnosis, issues = gap.validate_gap_diagnosis(
            text, known_synthesis_ids={"SYN-GAP-1"}
        )
        self.assertTrue(any("missing field" in item for item in issues), issues)

    def test_few_papers_or_new_object_is_not_a_diagnosis(self) -> None:
        text = valid_gap().replace(
            "在相同制度压力下，现有理论仍不能区分资源约束何时改变项目选择机制",
            "论文很少",
        )
        _diagnosis, issues = gap.validate_gap_diagnosis(text)
        self.assertTrue(any("gap_claim" in item for item in issues), issues)

    def test_unknown_synthesis_identity_is_rejected(self) -> None:
        _diagnosis, issues = gap.validate_gap_diagnosis(
            valid_gap(synthesis="SYN-INVENTED"),
            known_synthesis_ids={"SYN-GAP-1"},
        )
        self.assertTrue(any("unknown synthesis" in item for item in issues), issues)

    def test_knowledge_is_umbrella_not_a_primary_locus(self) -> None:
        _diagnosis, issues = gap.validate_gap_diagnosis(valid_gap(locus="knowledge"))
        self.assertTrue(any("primary_locus" in item for item in issues), issues)

    def test_design_core_cannot_drift_after_confirmation(self) -> None:
        confirmed, issues = gap.validate_gap_diagnosis(valid_gap())
        changed, changed_issues = gap.validate_gap_diagnosis(
            valid_gap(locus="scope-population", obstruction="biased-coverage")
        )
        self.assertEqual([], issues + changed_issues)
        self.assertFalse(gap.gap_core_matches(confirmed, changed))

    def test_current_synthesis_ids_are_loaded_from_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "literature_analysis.json").write_text(
                json.dumps({"syntheses": [{"synthesis_id": "SYN-GAP-1"}]}),
                encoding="utf-8",
            )
            identifiers, issue = gap.synthesis_ids_from_analysis(base)
            self.assertIsNone(issue)
            self.assertEqual({"SYN-GAP-1"}, identifiers)


if __name__ == "__main__":
    unittest.main()
