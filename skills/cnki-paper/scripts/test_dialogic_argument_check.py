#!/usr/bin/env python3
"""Regression tests for the dialogic-argument identity gate."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
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


dialogue = load_module("dialogic_argument_check", "dialogic_argument_check.py")


VALID_MAP = """# Dialogic Argument Map

## Dialogue Contract

| Field | Content |
|---|---|
| Controlling Dialogue/Unknown | 数字平台是否会自动改善部门回应，还是其效果取决于责任配置 |
| Response Target Type | explicit-dispute |
| Final Author Position | 平台接入的作用受部门责任配置约束 |
| Response Mode | agree-and-qualify |
| Central Contribution | 本文把平台平均效应推进为受责任配置约束的条件机制 |
| Contribution Claim IDs | CLM-001 |
| Strongest Countervoice | 技术接入已足以解释回应改善，不必引入组织条件 |
| Strongest Countervoice Position ID | POS-02 |
| Who Cares | 研究数字治理的学者需要区分接入效果与组织条件 |
| So What | 若忽略责任配置，理论会误判平台作用，政策也会错配改革抓手 |
| Missing Voice Disposition | 尚缺一线工作人员声音，正文将其登记为材料边界而不代言 |
| Forbidden Reading | 不得写成平台必然改善治理或责任配置具有普遍因果效应 |

## Position–Response Map

| Position ID | Fair Summary | Source IDs | Relation/Response | Claim IDs | Evidence IDs | Execution IDs | Concession/Difference | Counterevidence/Boundary | Status |
|---|---|---|---|---|---|---|---|---|---|
| POS-01 | 一类研究认为平台接入可以通过信息整合缩短回应时间 | SRC-001 | agree-and-qualify | CLM-001 | EVD-001 | EXE-001 | 接受信息整合可能有效，但不同权责结构下效果并不相同 | 单市观察材料只支持条件关系，不支持普遍因果 | PASS |
| POS-02 | 另一类研究认为技术接入本身是改善回应的主要来源 | SRC-002 | disagree | CLM-001 | EVD-001 | EXE-001 | 承认技术能力是必要条件，但反对把它视为充分条件 | 同平台部门差异构成判别证据，外推仍受样本限制 | PASS |

## Section Voice Map

| Manuscript Unit | Prior/Source Voice | Attribution/Position IDs | Author Move | Evidence/Warrant | Transition/Payoff | Status |
|---|---|---|---|---|---|---|
| 摘要 | 既有研究通常强调平台接入的平均改善 | POS-01; POS-02 | 用条件机制限定平均效应 | CLM-001; EVD-001 | 读者首先获得本文增量与边界 | PASS |
| 引言 | 两种解释对技术是否充分存在分歧 | POS-01; POS-02 | 公允归纳后提出责任配置问题 | SRC-001; SRC-002 | 从文献分歧推进到可检验问题 | PASS |
| 结果 | 前述两种解释产生不同经验预期 | POS-01; POS-02 | 报告判别结果并保留负面证据 | EVD-001; EXE-001 | 从结果进入机制和反方处置 | PASS |
| 结论 | 平均效应说与技术充分说都解释了部分现象 | POS-01; POS-02 | 让步后收束为有范围的条件判断 | CLM-001; EVD-001 | 说明理论与政策为何都需修正 | PASS |

## Substantive Revision Delta

| Discovery | Initial Claim/Location | Why It Failed | Revised Claim | Source/Evidence Recheck | Propagated Changes | Unintended Implication Fixed | Status |
|---|---|---|---|---|---|---|---|
| 同平台部门仍有明显差异 | 引言末段原称平台接入改善回应 | 原主张把必要条件误写成充分条件 | 平台作用受责任配置约束 | SRC-001; SRC-002; EVD-001 | 摘要末句；引言末段；结论首段 | 删除技术决定论和普遍因果暗示 | REVISED |

Overall Status: PASS
"""


class DialogicArgumentTests(unittest.TestCase):
    def make_workspace(self, base: Path, map_text: str = VALID_MAP) -> None:
        reference_dir = base / "reference_materials"
        reference_dir.mkdir(parents=True)
        (reference_dir / "literature_registry.json").write_text(
            json.dumps(
                {
                    "schema_version": "cnki-acquisition/v2",
                    "sources": [
                        {"source_id": "SRC-001"},
                        {"source_id": "SRC-002"},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "research_design.json").write_text(
            json.dumps(
                {
                    "schema_version": "cnki-research-design/v3",
                    "claims": [{"id": "CLM-001", "status": "active"}],
                    "evidence": [{"id": "EVD-001"}],
                    "method_routes": [{"id": "DSN-001"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "method_execution.json").write_text(
            json.dumps(
                {
                    "schema_version": "cnki-method-execution/v2",
                    "runs": [{"id": "EXE-001"}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (base / "confirmed_motivation.md").write_text(
            """# Confirmed Motivation

| Field | Content |
|---|---|
| Controlling Dialogue/Unknown | 数字平台是否会自动改善部门回应，还是其效果取决于责任配置 |
| Response Target Type | explicit-dispute |
| Position/Source IDs | SRC-001; SRC-002 |
| Initial Author Response | 接受平台可能改善回应，但把其效果限定为受责任配置约束 |
| Strongest Countervoice | 技术接入已足以解释回应改善，不必引入组织条件 |
| Who Cares | 数字治理研究者与改革设计者 |
| So What | 错判作用条件会同时损害理论解释和改革设计 |
| Missing Voice | 尚缺一线工作人员声音，作为材料边界登记 |
""",
            encoding="utf-8",
        )
        (base / "confirmed_contribution.md").write_text(
            """# Confirmed Contribution

| Field | Content |
|---|---|
| Main Contribution Statement | 本文把平台平均效应推进为受责任配置约束的条件机制 |
| Active Claim IDs | CLM-001 |
""",
            encoding="utf-8",
        )
        (base / "dialogic_argument_map.md").write_text(
            map_text,
            encoding="utf-8",
        )

    def check(self, map_text: str = VALID_MAP):
        temp = tempfile.TemporaryDirectory()
        base = Path(temp.name)
        self.make_workspace(base, map_text)
        return temp, base, dialogue.validate_dialogic_argument(base)

    def test_complete_identity_chain_passes(self) -> None:
        temp, _, result = self.check()
        try:
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(2, result.coverage["positions"])
            self.assertEqual(4, result.coverage["voice_units"])
            self.assertEqual(0, result.coverage["problem_arc_rows"])
        finally:
            temp.cleanup()

    def test_problem_arc_projection_is_optional_but_identity_bound_when_present(self) -> None:
        temp, base, _ = self.check()
        try:
            (base / "literature_analysis.json").write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-literature-analysis/v2",
                        "problem_arc": {
                            "arc_id": "ARC-MAIN",
                            "states": [
                                {
                                    "state_id": "ARC-STATE-01",
                                    "live_question": "平台接入是否足以解释回应改善",
                                    "provisional_answer": "平台接入本身可能足以解释改善",
                                    "pressure": "同平台部门差异对充分条件说形成压力",
                                    "transition_type": "DISTINGUISH",
                                    "updated_problem": "责任配置如何限定平台接入的作用",
                                    "residual_unknown": "外部场景是否呈现相同边界仍未知",
                                    "authority_refs": ["SRC-001", "SRC-002"],
                                    "branch_id": "BRANCH-CONDITIONAL",
                                    "branch_disposition": "保留为正文的条件机制分支",
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            projection = """
## Problem Arc Projection

| State ID | Live Question | Argument Action | Updated Problem | Authority Refs | Branch/Disposition | Status |
|---|---|---|---|---|---|---|
| ARC-STATE-01 | 平台接入是否足以解释回应改善 | DISTINGUISH | 责任配置如何限定平台接入的作用 | SRC-001; SRC-002 | BRANCH-CONDITIONAL；保留为正文的条件机制分支 | PASS |

"""
            map_text = VALID_MAP.replace("Overall Status: PASS", projection + "Overall Status: PASS")
            (base / "dialogic_argument_map.md").write_text(map_text, encoding="utf-8")
            result = dialogue.validate_dialogic_argument(base)
            self.assertTrue(result.ok, result.issues)
            self.assertEqual(1, result.coverage["problem_arc_rows"])

            damaged = map_text.replace(
                "| SRC-001; SRC-002 | BRANCH-CONDITIONAL",
                "| SRC-001 | BRANCH-CONDITIONAL",
            )
            (base / "dialogic_argument_map.md").write_text(damaged, encoding="utf-8")
            result = dialogue.validate_dialogic_argument(base)
            self.assertTrue(
                any("AP.ARC.AUTHORITY_MISSING" in issue for issue in result.issues),
                result.issues,
            )
        finally:
            temp.cleanup()

    def test_canonical_problem_arc_cannot_be_omitted_from_dialogic_projection(self) -> None:
        temp, base, _ = self.check()
        try:
            (base / "literature_analysis.json").write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-literature-analysis/v2",
                        "problem_arc": {
                            "arc_id": "ARC-MAIN",
                            "states": [
                                {
                                    "state_id": "ARC-STATE-01",
                                    "live_question": "平台接入是否足以解释回应改善",
                                    "transition_type": "PRESS",
                                    "updated_problem": "责任配置是否限定平台作用",
                                    "authority_refs": ["SRC-001"],
                                }
                            ],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = dialogue.validate_dialogic_argument(base)
            self.assertTrue(
                any("AP.ARC.PROJECTION_MISSING" in issue for issue in result.issues),
                result.issues,
            )
        finally:
            temp.cleanup()

    def test_unknown_source_id_does_not_satisfy_identity_gate(self) -> None:
        text = VALID_MAP.replace(
            "| SRC-002 | disagree |",
            "| SRC-999 | disagree |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertFalse(result.ok)
            self.assertTrue(any("no registered Source ID" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_unknown_short_form_claim_and_evidence_ids_are_rejected(self) -> None:
        text = VALID_MAP.replace(
            "| CLM-001 | EVD-001 | EXE-001 |",
            "| CLM-001; C999 | EVD-001; EV-999 | EXE-001 |",
            1,
        )
        temp, _, result = self.check(text)
        try:
            self.assertFalse(result.ok)
            self.assertTrue(
                any("unknown Claim IDs: C999" in issue for issue in result.issues)
            )
            self.assertTrue(
                any("unknown Evidence IDs: EV-999" in issue for issue in result.issues)
            )
        finally:
            temp.cleanup()

    def test_unresolved_status_blocks_map(self) -> None:
        text = VALID_MAP.replace(
            "| POS-02 | 另一类研究认为技术接入本身是改善回应的主要来源 | SRC-002 | disagree | CLM-001 | EVD-001 | EXE-001 | 承认技术能力是必要条件，但反对把它视为充分条件 | 同平台部门差异构成判别证据，外推仍受样本限制 | PASS |",
            "| POS-02 | 另一类研究认为技术接入本身是改善回应的主要来源 | SRC-002 | disagree | CLM-001 | EVD-001 | EXE-001 | 承认技术能力是必要条件，但反对把它视为充分条件 | 同平台部门差异构成判别证据，外推仍受样本限制 | OPEN |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(any("unresolved status" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_unresolved_marker_in_non_status_cell_blocks_map(self) -> None:
        text = VALID_MAP.replace(
            "同平台部门差异构成判别证据，外推仍受样本限制 | PASS |",
            "TODO evidence remains unresolved but this row claims closure | PASS |",
            1,
        )
        temp, _, result = self.check(text)
        try:
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "Position–Response row 2 contains unresolved markers in: boundary"
                    in issue
                    for issue in result.issues
                ),
                result.issues,
            )
        finally:
            temp.cleanup()

    def test_unresolved_marker_in_contract_blocks_map(self) -> None:
        text = VALID_MAP.replace(
            "| Missing Voice Disposition | 尚缺一线工作人员声音，正文将其登记为材料边界而不代言 |",
            "| Missing Voice Disposition | NEEDS-REVIEW before the missing voice can be closed |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertFalse(result.ok)
            self.assertTrue(
                any(
                    "Dialogue Contract contains unresolved markers in: missing voice"
                    in issue
                    for issue in result.issues
                ),
                result.issues,
            )
        finally:
            temp.cleanup()

    def test_false_explicit_dispute_with_one_position_is_rejected(self) -> None:
        start = VALID_MAP.index("| POS-02 |")
        end = VALID_MAP.index("\n\n## Section Voice Map", start)
        text = VALID_MAP[:start] + VALID_MAP[end:]
        temp, _, result = self.check(text)
        try:
            self.assertTrue(any("at least two" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_explicit_dispute_cannot_reuse_one_source_for_both_positions(self) -> None:
        text = VALID_MAP.replace(
            "| SRC-002 | disagree |",
            "| SRC-001 | disagree |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(
                any("two distinct registered Source IDs" in issue for issue in result.issues)
            )
        finally:
            temp.cleanup()

    def test_strongest_countervoice_must_resolve_to_position(self) -> None:
        text = VALID_MAP.replace(
            "| Strongest Countervoice Position ID | POS-02 |",
            "| Strongest Countervoice Position ID | POS-99 |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(
                any("countervoice Position ID" in issue for issue in result.issues)
            )
        finally:
            temp.cleanup()

    def test_generic_stakes_do_not_pass_by_keyword(self) -> None:
        text = VALID_MAP.replace(
            "| Who Cares | 研究数字治理的学者需要区分接入效果与组织条件 |",
            "| Who Cares | 无 |",
        ).replace(
            "| So What | 若忽略责任配置，理论会误判平台作用，政策也会错配改革抓手 |",
            "| So What | 待定 |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(any("who cares" in issue for issue in result.issues))
            self.assertTrue(any("so what" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_voice_rows_must_attribute_registered_position(self) -> None:
        text = VALID_MAP.replace(
            "| 摘要 | 既有研究通常强调平台接入的平均改善 | POS-01; POS-02 |",
            "| 摘要 | 既有研究通常强调平台接入的平均改善 | 作者认为 |",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(any("Position ID attribution" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_substantive_revision_must_propagate(self) -> None:
        text = VALID_MAP.replace(
            "摘要末句；引言末段；结论首段",
            "引言末段",
        )
        temp, _, result = self.check(text)
        try:
            self.assertTrue(any("propagation to two locations" in issue for issue in result.issues))
        finally:
            temp.cleanup()

    def test_confirmed_motivation_drift_is_rejected(self) -> None:
        temp, base, _ = self.check()
        try:
            motivation = (base / "confirmed_motivation.md").read_text(encoding="utf-8")
            (base / "confirmed_motivation.md").write_text(
                motivation.replace("explicit-dispute", "literature-omission"),
                encoding="utf-8",
            )
            result = dialogue.validate_dialogic_argument(base)
            self.assertTrue(
                any("differs from confirmed_motivation.md" in issue for issue in result.issues)
            )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
