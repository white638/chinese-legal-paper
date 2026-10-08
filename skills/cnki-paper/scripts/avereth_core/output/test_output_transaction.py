from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from avereth_core.artifacts import sha256_file
from avereth_core.build.manuscript import select_manuscript
from avereth_core.models import GateResult
from avereth_core.output import run
from avereth_core.receipts import AUDIT_SCHEMA
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def config() -> dict[str, object]:
    return {
        "schema_version": WORKFLOW_CONFIG_SCHEMA,
        "framework_version": VERSION,
        "workflow": "rewrite_existing",
        "task_profile": "full_paper",
        "publication_track": "international-ssci",
        "scene": "journal",
        "tier": "pro",
        "output_language": "en",
        "word_output": "docx",
        "pdf_output": "none",
        "citation_mode": "author_year",
        "word_font_policy": "default",
        "prose_mode": "distinguished",
        "translation_package": "none",
        "submission_package": "none",
        "response_package": "none",
        "canonical_manuscript": "final_paper/main.md",
    }


class OutputTransactionTests(unittest.TestCase):
    def fixture(self, root: Path) -> tuple[dict[str, object], dict[str, object]]:
        active = config()
        canonical_path = root / "final_paper" / "main.md"
        canonical_path.parent.mkdir(parents=True)
        canonical_path.write_text("Audited manuscript body. " * 20, encoding="utf-8")
        selection = select_manuscript(root, active)
        write_json(root / "workflow_config.json", active)
        write_json(root / "audit_receipt.json", {
            "schema_version": AUDIT_SCHEMA,
            "framework_version": VERSION,
            "status": "PASS",
            "canonical_manuscript": selection.as_dict(),
        })
        candidate_root = root / run.CANDIDATE_DIR
        delivery = candidate_root / "final_paper" / "paper.docx"
        preview = candidate_root / "render_qa" / "word_preview.pdf"
        report = candidate_root / "reports" / "word_report.md"
        delivery.parent.mkdir(parents=True)
        preview.parent.mkdir(parents=True)
        report.parent.mkdir(parents=True)
        delivery.write_bytes(b"editable-word-delivery")
        preview.write_bytes(b"%PDF-1.4\n%%EOF")
        report.write_text("# Word Guard\n\nStatus: PASS\n", encoding="utf-8")
        candidate: dict[str, object] = {
            "schema_version": run.CANDIDATE_SCHEMA,
            "framework_version": VERSION,
            "canonical_manuscript": selection.as_dict(),
            "audit_receipt_sha256": sha256_file(root / "audit_receipt.json"),
            "output_policy": run._output_policy(root, active, selection.path),
            "deliveries": [{
                "path": "final_paper/paper.docx",
                "sha256": sha256_file(delivery),
                "size": delivery.stat().st_size,
            }],
            "qa_artifacts": [{
                "path": "render_qa/word_preview.pdf",
                "sha256": sha256_file(preview),
                "size": preview.stat().st_size,
                "pages": 1,
            }],
            "renderers": [{"name": "fixture"}],
        }
        write_json(candidate_root / "candidate_manifest.json", candidate)
        write_json(root / run.CANDIDATE_QA_REL, {
            "schema_version": run.QA_SCHEMA,
            "framework_version": VERSION,
            "status": "PASS",
            "candidate_manifest_digest": run._digest_json(candidate),
            "reviewed_targets": run._review_targets(candidate),
            "pages_reviewed": "all",
            "reviewer_mode": "human",
            "reviewed_by": "test-reviewer",
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        })
        return active, candidate

    def test_published_completion_survives_candidate_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            active, candidate = self.fixture(root)
            canonical = select_manuscript(root, active).as_dict()
            run._publish(
                root,
                candidate,
                canonical,
                {"status": "PASS"},
                config=active,
                required_guard_reports=("word_report.md",),
                receipt_signer=lambda: True,
            )
            self.assertTrue(run.validate_completion(root, config=active).ok)
            candidate_root = root / run.CANDIDATE_DIR
            shutil.rmtree(candidate_root)
            result = run.validate_completion(root, config=active)
            self.assertTrue(result.ok, [item.as_dict() for item in result.findings])

    def test_receipt_signer_failure_rolls_back_nested_publication(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            active, candidate = self.fixture(root)
            canonical = select_manuscript(root, active).as_dict()
            old_paths = {
                "final_paper/paper.docx": b"OLD-DOCX",
                "render_qa/word_preview.pdf": b"OLD-PREVIEW",
                "word_report.md": b"# Old\n\nStatus: PASS\n",
                "render_qa.json": b'{"status":"OLD-QA"}\n',
                "final_artifact_manifest.json": b'{"status":"OLD"}\n',
                "output_run.json": b'{"status":"OLD"}\n',
                "output_receipt.json": b'{"status":"PASS"}\n',
                "output_receipt.md": b"# Old\n\nStatus: PASS\n",
            }
            for relative, content in old_paths.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            write_json(root / "final_artifact_manifest.json", {
                "status": "PASS",
                "artifacts": [
                    {"path": "final_paper/paper.docx"},
                    {"path": "render_qa/word_preview.pdf"},
                    {"path": "word_report.md"},
                ],
            })
            old_paths["final_artifact_manifest.json"] = (root / "final_artifact_manifest.json").read_bytes()
            before = {relative: (root / relative).read_bytes() for relative in old_paths}
            with mock.patch("avereth_core.output.run.validate_completion", return_value=GateResult.pass_("output")):
                with self.assertRaisesRegex(RuntimeError, "rolled back"):
                    run._publish(
                        root,
                        candidate,
                        canonical,
                        {"status": "PASS"},
                        config=active,
                        required_guard_reports=("word_report.md",),
                        receipt_signer=lambda: False,
                    )
            after = {relative: (root / relative).read_bytes() for relative in old_paths}
            self.assertEqual(before, after)

    def test_managed_path_parser_rejects_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self.assertIsNone(run._safe_managed_relative(root, "render_qa/../../victim"))
            self.assertEqual(
                "translation_zh/paper.zh.docx",
                run._safe_managed_relative(root, "translation_zh/paper.zh.docx"),
            )

    def test_qa_payload_requires_identity_mode_and_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            _active, candidate = self.fixture(root)
            minimal = {
                "schema_version": run.QA_SCHEMA,
                "framework_version": VERSION,
                "status": "PASS",
                "candidate_manifest_digest": run._digest_json(candidate),
                "reviewed_targets": run._review_targets(candidate),
                "pages_reviewed": "all",
            }
            write_json(root / run.CANDIDATE_QA_REL, minimal)
            status = run._qa_status(root, candidate)
            self.assertFalse(status.ok)
            self.assertEqual(
                {"OUTPUT.QA_IDENTITY", "OUTPUT.QA_TIME"},
                {item.code for item in status.findings},
            )


if __name__ == "__main__":
    unittest.main()
