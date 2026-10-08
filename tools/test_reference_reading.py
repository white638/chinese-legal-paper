from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tools.reference_reading import reading_metrics, section_text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/cnki-paper/scripts"))
from avereth_core.application.plan_service import build_plan
from avereth_core.workflow_registry import REFERENCE_ACTIONS


class ReferenceReadingTests(unittest.TestCase):
    def test_fences_subsections_and_overlap_do_not_distort_measurement(self):
        text = "# Document\n## A\nfirst\n```text\n## B\n```\n### Child\nsecond\n## B\nlast\n"
        selected = section_text(text, ["A", "Child"])
        self.assertIn("second", selected)
        self.assertNotIn("last", selected)
        self.assertEqual(1, selected.count("second"))
        with self.assertRaises(ValueError):
            section_text(text, ["missing"])

    def test_all_action_sections_resolve_in_the_current_source(self):
        for action, (stage, _) in REFERENCE_ACTIONS.items():
            for language, method in (("en", "quantitative"), ("zh", "historical")):
                for profile, conditioning in (("full_paper", "none"), ("full_paper", "commonplace"), ("manuscript_revision", "commonplace"), ("full_paper", "auto"), ("manuscript_revision", "auto")):
                    with self.subTest(action=action, language=language, profile=profile, conditioning=conditioning):
                        plan = build_plan(
                            {"next_stage": stage, "task_profile": profile, "publication_track": "mixed"},
                            {"output_language": language, "method_family": method, "prose_conditioning": conditioning},
                            reference_action=action,
                        )
                        metrics = reading_metrics(ROOT / "skills", plan["reference_requests"])
                        self.assertGreater(metrics["selected_utf8_bytes"], 0)

    def test_cnki_discovery_and_registration_keep_source_constraints_without_output_instructions(self):
        reference = "cnki-paper/references/cnki-operations.md"
        text = (ROOT / "skills" / reference).read_text(encoding="utf-8")
        for action in ("discover", "register-source", "topic-portfolio"):
            stage = REFERENCE_ACTIONS[action][0]
            plan = build_plan({"next_stage": stage, "publication_track": "cnki-cn"}, reference_action=action)
            request = next(row for row in plan["reference_requests"] if row["path"] == reference)
            selected = section_text(text, request["sections"])
            with self.subTest(action=action):
                self.assertIn("## 1. 验证码协议", selected)
                self.assertIn("## 6. PDF 下载与机构权限", selected)
                self.assertIn("不能替代", selected)
                self.assertNotIn("## 8. 正式输出与渲染 QA", selected)
                self.assertNotIn("## 8b. docx 投稿格式修复（OOXML）", selected)
                self.assertNotIn("## 10. Zotero 推送（可选）", selected)
                if action == "register-source":
                    self.assertIn("Citation Scope=candidate-only", selected)
                    self.assertIn("## 5. 同源 fetch 批量抓摘要", selected)
                else:
                    self.assertIn("零也不自动证明原创", selected)
                    self.assertNotIn("### 4.1 已验证导出参数", selected)

    def test_commonplace_reads_harvesting_or_realization_contract_without_rollout_evaluation(self):
        reference = "cnki-paper/references/commonplace-writing.md"
        text = (ROOT / "skills" / reference).read_text(encoding="utf-8")
        for stage in ("research", "build", "audit"):
            plan = build_plan({"next_stage": stage}, {"prose_conditioning": "commonplace"})
            request = next(row for row in plan["reference_requests"] if row["path"] == reference)
            selected = section_text(text, request["sections"])
            with self.subTest(stage=stage):
                self.assertIn("ProsePacket 独占事实", selected)
                self.assertIn("conventional_bundle", selected)
                self.assertIn("不同文章、不同内容和独立作者", selected)
                self.assertIn("不能把作者专有概念包装成通用术语", selected)
                self.assertNotIn("## 5. 评测与默认推广", selected)
                if stage == "research":
                    self.assertIn("全文阅读与来源核验", selected)
                    self.assertIn("synthetic=true", selected)
                    self.assertNotIn("## 3. 共同体短语与检索", selected)
                else:
                    self.assertIn("## 4. 借用检查与现有正文链", selected)
                    self.assertIn("不能靠 REVIEW 记录覆盖", selected)
                    self.assertIn("现有 audit receipt", selected)
                    self.assertIn("active index", selected)
                    self.assertNotIn("## 2. 研究阶段摘录", selected)
                    if stage == "build":
                        self.assertIn("COMMONPLACE_MISS", selected)

    def test_revision_reading_keeps_scope_and_legacy_limits_at_each_active_stage(self):
        reference = "cnki-paper/references/controlled-revision.md"
        text = (ROOT / "skills" / reference).read_text(encoding="utf-8")
        for stage in ("intake", "acquisition", "research", "design", "execution", "build", "audit"):
            plan = build_plan({"next_stage": stage, "task_profile": "manuscript_revision"})
            request = next(row for row in plan["reference_requests"] if row["path"] == reference)
            selected = section_text(text, request["sections"])
            with self.subTest(stage=stage):
                self.assertIn("revision_contract.json", selected)
                self.assertIn("新增文献、新主张、范围和标题实质变化必须回 research", selected)
                self.assertIn("不得取得 output PASS", selected)
                self.assertIn("旧 `cnki-manuscript-revision/v1` 只能读取和审计", selected)
                if stage in {"intake", "build"}:
                    self.assertIn("## 命令入口", selected)
                else:
                    self.assertNotIn("## 命令入口", selected)


if __name__ == "__main__":
    unittest.main()
