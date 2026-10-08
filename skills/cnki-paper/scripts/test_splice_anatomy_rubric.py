#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""splice_anatomy_rubric 单测（仅标准库）。运行：python test_splice_anatomy_rubric.py"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import splice_anatomy_rubric as s  # noqa: E402

FAKE_ANATOMY = """# 假解剖文件

## 3. 维度

正文。

---

## 4. 顶刊质量量规（评审 / 自检打分表）

| 维度 | 退稿档（0） | 合格档（1） | 顶刊档（2） |
|---|---|---|---|
| 3.1 问题意识 | 空话 | 缺张力 | 自带张力 |

**判读**：承重四维全部 ≥1。

---

## 5. 变体

后文不应被截进量规。
"""

FAKE_PROMPT = """# Contribution & Novelty Reviewer

## Verified Venue Contract

Applicability: BLOCKED

## Required Output Contract

| Dimension ID | Applicability | Score | Reason | Manuscript Location |
|---|---|---:|---|---|
| CON-01 | [APPLICABLE|NOT_APPLICABLE|BLOCKED] | [1-5 or N/A] | [reason] | [location] |

Under `## Findings`, include one standard v2 `### Finding N` block for each real issue.

## Instructions

Write only your review.
"""


class TestExtract(unittest.TestCase):
    def test_extracts_section4_only(self):
        rubric = s.extract_rubric(FAKE_ANATOMY)
        self.assertIn("顶刊质量量规", rubric)
        self.assertIn("| 3.1 问题意识 |", rubric)
        self.assertIn("**判读**", rubric)
        self.assertNotIn("## 5.", rubric)
        self.assertNotIn("后文不应被截进量规", rubric)
        # 尾部分隔线应被剥掉
        self.assertFalse(rubric.rstrip().endswith("---"))

    def test_missing_section_raises(self):
        with self.assertRaises(ValueError):
            s.extract_rubric("# 空文件\n\n## 3. 别的节\n")

    def test_real_anatomy_file_parses(self):
        """回归：真实 anatomy 文件的 §4 必须能被截出（标题措辞变了要同步改脚本）。"""
        real = s.DEFAULT_ANATOMY
        self.assertTrue(real.exists(), f"缺 {real}")
        rubric = s.extract_rubric(real.read_text(encoding="utf-8"))
        self.assertIn("退稿档", rubric)
        self.assertIn("承重", rubric)
        self.assertIn("语言凝练度", rubric)
        self.assertIn("读者可读性", rubric)
        self.assertNotIn("## 5", rubric)


class TestSplice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.anatomy = root / "anatomy.md"
        self.anatomy.write_text(FAKE_ANATOMY, encoding="utf-8")
        prompts = root / "out" / "review_prompts"
        prompts.mkdir(parents=True)
        self.target = prompts / "contribution_reviewer.md"
        self.target.write_text(FAKE_PROMPT, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_then_idempotent(self):
        self.assertEqual(s.splice(self.target, self.anatomy), "applied")
        text = self.target.read_text(encoding="utf-8")
        self.assertEqual(text.count(s.BEGIN), 1)
        self.assertIn("| 3.1 问题意识 |", text)
        self.assertIn("价值优先", text)          # 评审纪律注入
        self.assertIn("抬档路径", text)
        self.assertIn("定性反馈不折算机械分数", text)
        self.assertIn("第一次阅读", text)
        self.assertIn("Write only your review.", text)  # 原提示词未被破坏
        self.assertIn(
            "| Dimension ID | Applicability | Score | Reason | Manuscript Location |",
            text,
        )
        self.assertIn("Applicability: BLOCKED", text)
        # 重跑：无变化
        self.assertEqual(s.splice(self.target, self.anatomy), "unchanged")
        self.assertEqual(self.target.read_text(encoding="utf-8").count(s.BEGIN), 1)

    def test_v2_contract_guards_are_injected_without_replacing_prompt(self):
        s.splice(self.target, self.anatomy)
        text = self.target.read_text(encoding="utf-8")

        # anatomy 0/1/2 只能是补充诊断，不能恢复旧版“取代 rubric”的协议。
        self.assertIn("仅作补充诊断，绝不取代 v2 rubric", text)
        self.assertIn("## Supplemental Anatomy Diagnostic", text)
        self.assertNotIn("以本八维量规取代上方英文 Rubric", text)

        # v2 五列表仍是唯一主 rubric，且 anatomy 分数不能冒充其 1-5 Score。
        exact_header = "Dimension ID | Applicability | Score | Reason | Manuscript Location"
        self.assertGreaterEqual(text.count(exact_header), 2)
        self.assertIn("不得把 anatomy 的 0/1/2 分数填入", text)

        # material issue 必须进入标准 Finding block，不能停留在 anatomy 评语中。
        self.assertIn("任何 material issue 都必须进入", text)
        self.assertIn("`### Finding N` block", text)
        self.assertIn("`Finding ID:`", text)
        self.assertIn("`Net Word Delta:`", text)
        self.assertIn("不能替代 Finding block", text)
        self.assertIn("anatomy 分数单独裁决 Review Verdict", text)
        self.assertIn("不能建立 anatomy 专属回退门", text)

        # Venue Fit 适用性只继承已核验 target contract；anatomy 无权升级。
        self.assertIn("Venue Fit 的 Applicability 只由", text)
        self.assertIn("已核验 target contract", text)
        self.assertIn("Verified Venue Contract", text)
        self.assertIn("都不能新建、升级或覆盖该适用性", text)

    def test_update_on_anatomy_change(self):
        s.splice(self.target, self.anatomy)
        self.anatomy.write_text(FAKE_ANATOMY.replace("空话", "空洞套话"), encoding="utf-8")
        self.assertEqual(s.splice(self.target, self.anatomy), "updated")
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("空洞套话", text)
        self.assertNotIn("| 空话 |", text)
        self.assertEqual(text.count(s.BEGIN), 1)

    def test_check_only_writes_nothing(self):
        before = self.target.read_text(encoding="utf-8")
        self.assertEqual(s.splice(self.target, self.anatomy, check_only=True), "would-apply")
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)
        s.splice(self.target, self.anatomy)
        self.assertEqual(s.splice(self.target, self.anatomy, check_only=True), "unchanged")


if __name__ == "__main__":
    unittest.main(verbosity=2)
