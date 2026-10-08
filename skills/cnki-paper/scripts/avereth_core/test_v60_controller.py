from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

from avereth_core import cli
from avereth_core.artifacts import report_passed
from avereth_core.legacy import workspace_migration
from avereth_core.models import GateResult
from avereth_core.stages import STAGES
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA
from avereth_core.legacy.workspace_migration import ACQUISITION_HANDOFF_REL


SKILLS_DIR = Path(__file__).resolve().parents[3]


def tree_snapshot(root: Path) -> dict[str, tuple[int, int, str]]:
    payload: dict[str, tuple[int, int, str]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        stat = path.stat()
        payload[path.relative_to(root).as_posix()] = (
            stat.st_size,
            stat.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return payload


class ControllerV60Tests(unittest.TestCase):
    def test_public_state_model_is_exactly_eight_local_states(self) -> None:
        self.assertEqual(
            (
                "intake",
                "acquisition",
                "research",
                "design",
                "execution",
                "build",
                "audit",
                "output",
            ),
            STAGES,
        )

    def test_status_is_read_only_and_incomplete_config_belongs_to_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflow_config.json").write_text(
                json.dumps({
                    "framework_version": VERSION,
                    "schema_version": WORKFLOW_CONFIG_SCHEMA,
                }),
                encoding="utf-8",
            )
            before = tree_snapshot(root)
            payload, exit_code = cli.status_payload(root, SKILLS_DIR)
            self.assertEqual(0, exit_code)
            self.assertEqual("intake", payload["next_stage"])
            self.assertEqual("workflow_config", payload["next_checkpoint"])
            self.assertEqual(before, tree_snapshot(root))

    def test_malformed_config_is_repairable_intake_fact_not_runtime_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflow_config.json").write_text("{broken", encoding="utf-8")
            before = tree_snapshot(root)
            payload, exit_code = cli.status_payload(root, SKILLS_DIR)
            self.assertEqual(0, exit_code)
            self.assertEqual("intake", payload["next_stage"])
            self.assertEqual(before, tree_snapshot(root))

    def test_later_gate_cannot_bypass_intake_or_write_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = tree_snapshot(root)
            with redirect_stdout(StringIO()):
                exit_code = cli.gate_stage(root, "design", SKILLS_DIR)
            self.assertEqual(1, exit_code)
            self.assertEqual(before, tree_snapshot(root))

    def test_unresolved_migration_handoff_owns_acquisition_even_with_v2_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflow_config.json").write_text(json.dumps({
                "schema_version": WORKFLOW_CONFIG_SCHEMA,
                "framework_version": VERSION,
                "workflow": "rewrite_existing",
                "task_profile": "research_design",
                "publication_track": "cnki-cn",
                "scene": "report_review",
                "tier": "flash",
                "output_language": "zh",
                "word_output": "none",
                "pdf_output": "none",
                "citation_mode": "author_year",
                "word_font_policy": "default",
                "prose_mode": "clear",
                "translation_package": "none",
                "submission_package": "none",
                "response_package": "none",
            }), encoding="utf-8")
            registry = root / "reference_materials" / "literature_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(json.dumps({
                "schema_version": "cnki-acquisition/v2",
                "queries": [],
                "sources": [],
            }), encoding="utf-8")
            handoff = root / ACQUISITION_HANDOFF_REL
            handoff.parent.mkdir(parents=True)
            handoff_payload = {
                "schema_version": "avereth-acquisition-migration-handoff/v1",
                "framework_version": VERSION,
                "status": "needs_review",
                "source_config_sha256": "",
                "input_fields": {},
                "items": [],
            }
            handoff_payload["input_digest"] = workspace_migration._handoff_input_digest(handoff_payload)
            handoff.write_text(json.dumps(handoff_payload), encoding="utf-8")
            with (
                mock.patch.object(cli, "run_doctor", return_value=cli.DoctorResult()),
                mock.patch.object(cli, "validate_problem_orientation", return_value=[]),
            ):
                payload, exit_code = cli.status_payload(root, SKILLS_DIR)
            self.assertEqual(0, exit_code)
            self.assertEqual("acquisition", payload["next_stage"])
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_PENDING",
                " ".join(payload["acquisition_issues"]),
            )

    def test_declared_migration_handoff_cannot_be_bypassed_by_deleting_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflow_config.json").write_text(json.dumps({
                "schema_version": WORKFLOW_CONFIG_SCHEMA,
                "framework_version": VERSION,
                "workflow": "rewrite_existing",
                "task_profile": "research_design",
                "publication_track": "cnki-cn",
                "scene": "report_review",
                "tier": "flash",
                "output_language": "zh",
                "word_output": "none",
                "pdf_output": "none",
                "citation_mode": "author_year",
                "word_font_policy": "default",
                "prose_mode": "clear",
                "translation_package": "none",
                "submission_package": "none",
                "response_package": "none",
                "migration": {
                    "acquisition_handoff_required": True,
                    "acquisition_handoff_path": ACQUISITION_HANDOFF_REL.as_posix(),
                    "acquisition_handoff_fields": ["reference_paths"],
                    "acquisition_handoff_input_digest": "0" * 64,
                },
            }), encoding="utf-8")
            registry = root / "reference_materials" / "literature_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(json.dumps({
                "schema_version": "cnki-acquisition/v2",
                "queries": [],
                "sources": [],
            }), encoding="utf-8")
            with (
                mock.patch.object(cli, "run_doctor", return_value=cli.DoctorResult()),
                mock.patch.object(cli, "validate_problem_orientation", return_value=[]),
            ):
                payload, exit_code = cli.status_payload(root, SKILLS_DIR)
            self.assertEqual(0, exit_code)
            self.assertEqual("acquisition", payload["next_stage"])
            self.assertIn(
                "ACQUISITION.MIGRATION_HANDOFF_MISSING",
                " ".join(payload["acquisition_issues"]),
            )

    def test_migration_handoff_is_bound_into_audit_and_output_fingerprints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            handoff = root / ACQUISITION_HANDOFF_REL
            handoff.parent.mkdir(parents=True)
            handoff.write_text('{"status":"resolved","resolved_by":"first"}\n', encoding="utf-8")
            before_audit = cli.audit_fingerprint(root)
            before_output = cli.output_fingerprint(root)
            self.assertIn(
                ACQUISITION_HANDOFF_REL.as_posix(),
                cli.artifact_manifest(root, excludes=set()),
            )
            handoff.write_text('{"status":"resolved","resolved_by":"second"}\n', encoding="utf-8")
            self.assertNotEqual(before_audit, cli.audit_fingerprint(root))
            self.assertNotEqual(before_output, cli.output_fingerprint(root))

    def test_v2_remains_compatible_until_integration_artifacts_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "reference_materials" / "literature_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(
                '{"schema_version":"cnki-acquisition/v2","queries":[],"sources":[]}\n',
                encoding="utf-8",
            )
            metadata = cli.contract_metadata(root)
            self.assertFalse(metadata["integration_enabled"])
            self.assertEqual("current-compatible-v2", metadata["acquisition_migration_state"])

            manifest = (
                root
                / "reference_materials"
                / "integrations"
                / "exa_runs"
                / "manifest.json"
            )
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                '{"schema_version":"avereth-exa-manifest/v1","runs":[]}\n',
                encoding="utf-8",
            )
            metadata = cli.contract_metadata(root)
            self.assertTrue(metadata["integration_enabled"])
            self.assertEqual("acquisition-v2-needs-migration", metadata["acquisition_migration_state"])

    def test_v3_v2_research_pair_is_reported_as_legacy_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research_design.json").write_text(
                '{"schema_version":"cnki-research-design/v3"}\n',
                encoding="utf-8",
            )
            (root / "method_execution.json").write_text(
                '{"schema_version":"cnki-method-execution/v2"}\n',
                encoding="utf-8",
            )
            metadata = cli.contract_metadata(root)
            self.assertEqual(
                "legacy-v3-v2-read-render-migrate-only",
                metadata["migration_state"],
            )

    def test_execution_rejects_legacy_v3_v2_pair_before_active_validators(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research_design.json").write_text(
                '{"schema_version":"cnki-research-design/v3"}\n',
                encoding="utf-8",
            )
            (root / "method_execution.json").write_text(
                '{"schema_version":"cnki-method-execution/v2"}\n',
                encoding="utf-8",
            )
            with (
                mock.patch.object(cli, "research_design_status") as design_status,
                mock.patch.object(cli, "method_execution_status") as execution_status,
            ):
                ok, issues = cli.execution_status(root, SKILLS_DIR)
            self.assertFalse(ok)
            self.assertIn("read/render/migrate-only", " ".join(issues))
            design_status.assert_not_called()
            execution_status.assert_not_called()

    def test_execution_accepts_only_v4_v3_pair_as_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research_design.json").write_text(
                '{"schema_version":"cnki-research-design/v4"}\n',
                encoding="utf-8",
            )
            (root / "method_execution.json").write_text(
                '{"schema_version":"cnki-method-execution/v3"}\n',
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    cli,
                    "research_design_status",
                    return_value=(True, []),
                ) as design_status,
                mock.patch.object(
                    cli,
                    "method_execution_status",
                    return_value=(True, []),
                ) as execution_status,
            ):
                ok, issues = cli.execution_status(root, SKILLS_DIR)
            self.assertTrue(ok)
            self.assertEqual([], issues)
            design_status.assert_called_once_with(root, SKILLS_DIR, "execution")
            execution_status.assert_called_once_with(root, SKILLS_DIR, "execution")

    def test_build_projection_rejects_legacy_pair_for_active_and_audit_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "research_design.json").write_text(
                '{"schema_version":"cnki-research-design/v3"}\n',
                encoding="utf-8",
            )
            (root / "method_execution.json").write_text(
                '{"schema_version":"cnki-method-execution/v2"}\n',
                encoding="utf-8",
            )
            dialogue = mock.Mock(issues=[])
            with (
                mock.patch.object(
                    cli,
                    "local_artifact_gate",
                    return_value=GateResult.pass_("build"),
                ),
                mock.patch.object(
                    cli,
                    "build_run_status",
                    return_value=GateResult.pass_("build"),
                ),
                mock.patch.object(cli, "validate_dialogic_argument", return_value=dialogue),
                mock.patch.object(cli, "cnki_content_status", return_value=(True, [])),
            ):
                for profile in ("full_paper", "manuscript_audit"):
                    with self.subTest(profile=profile):
                        ok, issues = cli.build_status(
                            root,
                            {"task_profile": profile},
                            SKILLS_DIR,
                        )
                        self.assertFalse(ok)
                        self.assertIn("read/render/migrate-only", " ".join(issues))

    def test_invalid_integration_artifact_blocks_status_and_acquisition_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "workflow_config.json").write_text(
                json.dumps(
                    {
                        "schema_version": WORKFLOW_CONFIG_SCHEMA,
                        "framework_version": VERSION,
                        "workflow": "rewrite_existing",
                        "task_profile": "research_design",
                        "publication_track": "cnki-cn",
                        "scene": "report_review",
                        "tier": "flash",
                        "output_language": "zh",
                        "word_output": "none",
                        "pdf_output": "none",
                        "citation_mode": "author_year",
                        "word_font_policy": "default",
                        "prose_mode": "clear",
                        "translation_package": "none",
                        "submission_package": "none",
                        "response_package": "none",
                    }
                ),
                encoding="utf-8",
            )
            registry = root / "reference_materials" / "literature_registry.json"
            registry.parent.mkdir(parents=True)
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "cnki-acquisition/v3",
                        "queries": [
                            {
                                "query_id": "Q-EXA-001",
                                "channel": "Exa",
                                "run_artifact": "reference_materials/integrations/exa_runs/Q-EXA-001.json",
                                "run_sha256": "0" * 64,
                            }
                        ],
                        "sources": [],
                    }
                ),
                encoding="utf-8",
            )
            manifest = (
                root
                / "reference_materials"
                / "integrations"
                / "exa_runs"
                / "manifest.json"
            )
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{broken", encoding="utf-8")
            with (
                mock.patch.object(cli, "run_doctor", return_value=cli.DoctorResult()),
                mock.patch.object(cli, "validate_problem_orientation", return_value=[]),
            ):
                payload, exit_code = cli.status_payload(root, SKILLS_DIR)
                with redirect_stdout(StringIO()):
                    gate_exit = cli.gate_stage(root, "acquisition", SKILLS_DIR)
            self.assertEqual(0, exit_code)
            self.assertEqual("acquisition", payload["next_stage"])
            self.assertEqual("FAIL", payload["integration_validation"]["status"])
            self.assertEqual(1, gate_exit)

    def test_integration_support_and_references_bib_are_receipt_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            exa_manifest = (
                root
                / "reference_materials"
                / "integrations"
                / "exa_runs"
                / "manifest.json"
            )
            exa_manifest.parent.mkdir(parents=True)
            exa_manifest.write_text(
                '{"schema_version":"avereth-exa-manifest/v1","runs":[]}\n',
                encoding="utf-8",
            )
            exa_run = exa_manifest.parent / "Q-EXA-001.json"
            exa_run.write_text(
                '{"schema_version":"avereth-exa-run/v1","query_id":"Q-EXA-001"}\n',
                encoding="utf-8",
            )
            zotero_snapshot = (
                root
                / "reference_materials"
                / "integrations"
                / "zotero_snapshot.json"
            )
            zotero_snapshot.write_text(
                '{"schema_version":"avereth-zotero-snapshot/v1","items":[]}\n',
                encoding="utf-8",
            )
            references = root / "references.bib"
            references.write_text("@article{before, title={Before}}\n", encoding="utf-8")

            manifest = cli.artifact_manifest(root, excludes=set())
            for relative in (
                "reference_materials/integrations/exa_runs/manifest.json",
                "reference_materials/integrations/exa_runs/Q-EXA-001.json",
                "reference_materials/integrations/zotero_snapshot.json",
                "references.bib",
            ):
                self.assertIn(relative, manifest)

            before_audit = cli.audit_fingerprint(root)
            before_output = cli.output_fingerprint(root)
            references.write_text("@article{after, title={After}}\n", encoding="utf-8")
            self.assertNotEqual(before_audit, cli.audit_fingerprint(root))
            self.assertNotEqual(before_output, cli.output_fingerprint(root))

            after_bib_audit = cli.audit_fingerprint(root)
            after_bib_output = cli.output_fingerprint(root)
            zotero_snapshot.write_text(
                '{"schema_version":"avereth-zotero-snapshot/v1","items":[{}]}\n',
                encoding="utf-8",
            )
            self.assertNotEqual(after_bib_audit, cli.audit_fingerprint(root))
            self.assertNotEqual(after_bib_output, cli.output_fingerprint(root))

            after_snapshot_audit = cli.audit_fingerprint(root)
            after_snapshot_output = cli.output_fingerprint(root)
            exa_run.write_text(
                '{"schema_version":"avereth-exa-run/v1","query_id":"Q-EXA-CHANGED"}\n',
                encoding="utf-8",
            )
            self.assertNotEqual(after_snapshot_audit, cli.audit_fingerprint(root))
            self.assertNotEqual(after_snapshot_output, cli.output_fingerprint(root))

    def test_terminal_profile_always_marks_later_states_not_applicable(self) -> None:
        payload = cli.attach_canonical_stages({
            "task_profile": "topic_selection",
            "terminal_stage": "research",
            "next_stage": "acquisition",
            "is_complete": False,
        })
        states = {row["key"]: row["status"] for row in payload["stages"]}
        self.assertEqual("current", states["acquisition"])
        for stage in ("design", "execution", "build", "audit", "output"):
            self.assertEqual("not_applicable", states[stage])
        self.assertEqual("evidence", payload["next_phase"])
        self.assertEqual(
            ["scope", "evidence", "analysis", "manuscript", "verify"],
            [row["key"] for row in payload["phases"]],
        )
        self.assertEqual(
            ["acquisition", "research"],
            payload["phases"][1]["machine_stages"],
        )

    def test_revision_projection_uses_actual_earlier_failure_as_unique_current(self) -> None:
        payload = cli.attach_canonical_stages({
            "task_profile": "manuscript_revision",
            "terminal_stage": "output",
            "next_stage": "acquisition",
            "is_complete": False,
            "route_plan": {
                "profile": "manuscript_revision",
                "valid": True,
                "earliest_reopen_stage": "research",
            },
        })
        current = [row["key"] for row in payload["stages"] if row["status"] == "current"]
        self.assertEqual(["acquisition"], current)

    def test_completed_revision_preserves_reused_upstream_projection(self) -> None:
        payload = cli.attach_canonical_stages({
            "task_profile": "manuscript_revision",
            "terminal_stage": "output",
            "next_stage": "complete",
            "is_complete": True,
            "route_plan": {
                "profile": "manuscript_revision",
                "valid": True,
                "earliest_reopen_stage": "design",
            },
        })
        states = {row["key"]: row["status"] for row in payload["stages"]}
        for stage in ("intake", "acquisition", "research"):
            self.assertEqual("reused", states[stage])
        for stage in ("design", "execution", "build", "audit", "output"):
            self.assertEqual("done", states[stage])

    def test_completion_signers_fail_closed_without_run_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(cli.write_audit_receipt(root, passed=True))
            audit = json.loads((root / "audit_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("FAIL", audit["status"])
            self.assertFalse(cli.write_output_receipt(root, passed=True))
            output = json.loads((root / "output_receipt.json").read_text(encoding="utf-8"))
            self.assertEqual("FAIL", output["status"])

    def test_report_parser_requires_one_unambiguous_top_level_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.md"
            report.write_text("# Check\n\nStatus: PASS\n\n- Title check: PASS\n", encoding="utf-8")
            self.assertTrue(report_passed(report))
            report.write_text("# Check\n\nStatus: PASS\nStatus: FAILED\n", encoding="utf-8")
            self.assertFalse(report_passed(report))
            report.write_text("# Check\n\n```text\nStatus: PASS\n```\n", encoding="utf-8")
            self.assertFalse(report_passed(report))

    def test_completed_output_gate_is_idempotent_zero_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = tree_snapshot(root)
            with (
                mock.patch.object(cli, "run_doctor", return_value=GateResult.pass_("doctor")),
                mock.patch.object(cli, "status_payload", return_value=({"next_stage": "complete"}, 0)),
                mock.patch.object(cli, "invalidate_output_receipt") as invalidate,
                redirect_stdout(StringIO()),
            ):
                self.assertEqual(0, cli.gate_stage(root, "output", SKILLS_DIR))
            invalidate.assert_not_called()
            self.assertEqual(before, tree_snapshot(root))


if __name__ == "__main__":
    unittest.main()
