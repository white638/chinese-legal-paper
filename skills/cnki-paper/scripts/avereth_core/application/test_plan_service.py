from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from avereth_core import cli
from avereth_core import workflow_registry as registry
from avereth_core.application.plan_service import PLAN_SCHEMA, build_plan


class PlanServiceTests(unittest.TestCase):
    def test_plan_is_stable_and_uses_earliest_stage_only(self) -> None:
        status = {"task_profile": "full_paper", "publication_track": "mixed", "terminal_stage": "output", "next_stage": "research", "next_checkpoint": "research_evidence"}
        config = {"workflow": "build_from_materials", "publication_track": "mixed"}
        first = build_plan(status, config)
        second = build_plan(status, config)
        self.assertEqual(first, second)
        self.assertEqual(PLAN_SCHEMA, first["schema_version"])
        self.assertEqual("research", first["next_stage"])
        self.assertEqual("evidence", first["semantic_phase"])
        self.assertIn("intl-search", first["required_adapters"])
        self.assertIn("cnki-acquisition-adapters", first["required_adapters"])
        self.assertIn("confirmed_motivation.md", first["allowed_writes"])
        self.assertNotIn("research_design.json", first["allowed_writes"])
        skills_dir = Path(cli.__file__).resolve().parents[3]
        self.assertTrue(all((skills_dir / relative).is_file() for relative in first["required_references"]))

    def test_quantitative_data_check_is_opt_in_and_stage_bounded(self) -> None:
        status = {
            "task_profile": "full_paper",
            "publication_track": "international-ssci",
            "terminal_stage": "output",
            "next_stage": "research",
        }
        ordinary = build_plan(status, {"method_family": "historical"})
        self.assertEqual("single", ordinary["researcher_dispatch_mode"])
        self.assertNotIn("quantitative-data-check", ordinary["required_adapters"])
        self.assertNotIn(
            "cnki-paper/references/quantitative-data-check.md",
            ordinary["required_references"],
        )

        quantitative = build_plan(status, {"method_family": "quantitative"})
        self.assertIn("quantitative-data-check", quantitative["required_adapters"])
        self.assertIn(
            "cnki-paper/references/quantitative-data-check.md",
            quantitative["required_references"],
        )

    def test_confirmation_and_complete_plans_cannot_run_a_gate(self) -> None:
        confirmation = build_plan({"next_stage": "research", "next_checkpoint": "question_confirmation", "task_profile": "topic_selection", "publication_track": "cnki-cn", "terminal_stage": "research"})
        self.assertTrue(confirmation["user_decision_required"])
        self.assertFalse(confirmation["can_run_gate"])
        complete = build_plan({"next_stage": "complete", "task_profile": "topic_selection", "publication_track": "cnki-cn", "terminal_stage": "research"})
        self.assertEqual([], complete["allowed_writes"])
        self.assertFalse(complete["can_run_gate"])

        reappraisal = build_plan({"next_stage": "execution", "next_checkpoint": "problem_reappraisal", "task_profile": "full_paper", "publication_track": "cnki-cn", "terminal_stage": "output"})
        self.assertTrue(reappraisal["user_decision_required"])
        self.assertFalse(reappraisal["can_run_gate"])

    def test_revision_plan_declares_controlled_revision_reference(self) -> None:
        plan = build_plan({"next_stage": "research", "task_profile": "manuscript_revision", "publication_track": "international-ssci", "terminal_stage": "output"})
        self.assertIn("cnki-paper/references/controlled-revision.md", plan["required_references"])

    def test_intake_writes_exclude_legacy_and_non_revision_contracts(self) -> None:
        ordinary = build_plan({"next_stage": "intake", "task_profile": "full_paper", "publication_track": "cnki-cn", "terminal_stage": "output"})
        self.assertNotIn("revision_contract.json", ordinary["allowed_writes"])
        self.assertFalse(any(artifact.authority.startswith("legacy") and artifact.path in ordinary["allowed_writes"] for artifact in registry.ARTIFACT_DEFINITIONS))
        revision = build_plan({"next_stage": "intake", "task_profile": "manuscript_revision", "publication_track": "cnki-cn", "terminal_stage": "output"})
        self.assertIn("revision_contract.json", revision["allowed_writes"])

    def test_build_writes_use_explicit_canonical_and_route_narrowing(self) -> None:
        config = {"task_profile": "full_paper", "workflow": "build_from_materials", "canonical_manuscript": "final_paper/main.md"}
        ordinary = build_plan({"next_stage": "build", "task_profile": "full_paper", "publication_track": "cnki-cn", "terminal_stage": "output"}, config)
        self.assertIn("final_paper/main.md", ordinary["allowed_writes"])
        self.assertNotIn("final_paper/main.tex", ordinary["allowed_writes"])
        self.assertIn("source_inventory.md", ordinary["allowed_writes"])

        audit = build_plan({"next_stage": "build", "task_profile": "manuscript_audit", "publication_track": "cnki-cn", "terminal_stage": "audit"}, {**config, "task_profile": "manuscript_audit"})
        self.assertEqual(["final_paper/main.md"], audit["allowed_writes"])
        revision = build_plan({"next_stage": "build", "task_profile": "manuscript_revision", "publication_track": "cnki-cn", "terminal_stage": "output", "route_plan": {"earliest_reopen_stage": "build"}}, {**config, "task_profile": "manuscript_revision"})
        self.assertEqual(["final_paper/main.md"], revision["allowed_writes"])

    def test_cli_plan_does_not_write_an_empty_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            outdir = Path(raw)
            before = list(outdir.rglob("*"))
            skills_dir = Path(cli.__file__).resolve().parents[3]
            argv = ["avereth.py", "--skills-dir", str(skills_dir), "plan", str(outdir), "--json"]
            with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
                code = cli.main()
            self.assertEqual(0, code)
            self.assertEqual(before, list(outdir.rglob("*")))

    def test_operation_granularity_projects_protocol_without_owning_state(self) -> None:
        protocol = {
            "valid": True,
            "next_executable_action": "STEP-001",
            "runnable_action_ids": ["STEP-001"],
            "parallel_safe_groups": [["STEP-001"]],
            "issues": [],
            "work_items": [
                {
                    "id": "STEP-001",
                    "run_kind": "mvmr",
                    "execution_status": "pending",
                    "runnable": True,
                    "procedure": {"operation": "pilot"},
                    "researcher_dispatch": {"mode": "isolated_multi"},
                }
            ],
        }
        plan = build_plan(
            {
                "next_stage": "execution",
                "task_profile": "full_paper",
                "publication_track": "cnki-cn",
                "terminal_stage": "output",
            },
            granularity="operation",
            protocol=protocol,
        )
        self.assertEqual("avereth-plan/v2", plan["schema_version"])
        self.assertEqual("STEP-001", plan["next_executable_action"])
        self.assertEqual(["STEP-001"], plan["runnable_action_ids"])
        self.assertEqual("STEP-001", plan["work_items"][0]["id"])
        self.assertEqual("isolated_multi", plan["researcher_dispatch_mode"])

    def test_action_changes_reads_without_changing_authority(self) -> None:
        status = {"next_stage": "research", "task_profile": "full_paper", "publication_track": "international-ssci"}
        synthesis = build_plan(status)
        reading = build_plan(status, reference_action="critical-reading")
        self.assertNotEqual(synthesis["reference_requests"], reading["reference_requests"])
        for field in ("next_stage", "allowed_writes", "can_run_gate", "user_decision_required", "required_adapters"):
            self.assertEqual(synthesis[field], reading[field], field)
        with self.assertRaisesRegex(ValueError, "not available in stage"):
            build_plan(status, reference_action="output")

    def test_language_and_method_bound_conditional_reads(self) -> None:
        for stage in ("build", "audit", "output"):
            status = {"next_stage": stage, "task_profile": "full_paper", "publication_track": "international-ssci"}
            english = build_plan(status, {"output_language": "en", "method_family": "quantitative"})
            self.assertNotIn("cnki-paper/references/cn-journal-conventions.md", english["required_references"])
            chinese = build_plan(status, {"output_language": "zh"})
            self.assertIn("cnki-paper/references/cn-journal-conventions.md", chinese["required_references"])
            cn_track = build_plan({**status, "publication_track": "cnki-cn"}, {"output_language": "en", "language": "zh"})
            self.assertNotIn("cnki-paper/references/cn-journal-conventions.md", cn_track["required_references"])
            mixed_track = build_plan({**status, "publication_track": "mixed"}, {"output_language": "zh"})
            self.assertIn("cnki-paper/references/cn-journal-conventions.md", mixed_track["required_references"])
        historical = build_plan({"next_stage": "research"}, {"method_family": "historical"})
        self.assertIn("cnki-paper/references/primary-source-citation.md", historical["required_references"])

    def test_primary_source_sections_follow_the_current_stage(self) -> None:
        expected = {"acquisition": "3. 版本选择与著录", "build": "7. 转引规则", "audit": "10. 史料引用自检清单与 page-evidence 分级对应"}
        for stage, section in expected.items():
            plan = build_plan({"next_stage": stage}, {"method_families": ["historical", "quantitative"]})
            request = next(item for item in plan["reference_requests"] if item["path"].endswith("primary-source-citation.md"))
            self.assertIn(section, request["sections"])

    def test_output_reads_only_output_section(self) -> None:
        plan = build_plan({"next_stage": "output", "publication_track": "international-ssci", "task_profile": "full_paper"})
        self.assertEqual(1, len(plan["reference_requests"]))
        request = plan["reference_requests"][0]
        self.assertEqual("cnki-paper/references/workflow-playbook.md", request["path"])
        self.assertEqual(["阶段 7：output — 候选渲染、真实视觉复核与事务发布"], request["sections"])

    def test_topic_profile_reads_the_single_protocol(self) -> None:
        plan = build_plan({"next_stage": "research", "task_profile": "topic_selection"})
        self.assertEqual("topic-portfolio", plan["reference_action"])
        self.assertIn("cnki-paper/references/topic-selection-protocol.md", plan["required_references"])

    def test_finished_and_blocked_plans_do_not_request_reading(self) -> None:
        for stage in ("complete", "blocked"):
            plan = build_plan({"next_stage": stage})
            self.assertEqual([], plan["required_references"])
            self.assertEqual([], plan["reference_requests"])


if __name__ == "__main__":
    unittest.main()
