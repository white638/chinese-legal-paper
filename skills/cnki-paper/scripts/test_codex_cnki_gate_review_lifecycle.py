#!/usr/bin/env python3
"""Regression tests for the legacy Codex gate's v6 review delegation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import codex_cnki_gate
from avereth_core.version import VERSION


class CodexGateReviewLifecycleTests(unittest.TestCase):
    def _workspace(self, root: Path) -> Path:
        outdir = root / "paper_rewriting_output"
        manuscript = outdir / "final_paper" / "main.md"
        manuscript.parent.mkdir(parents=True)
        manuscript.write_text("# Paper\n\nReviewed prose.\n", encoding="utf-8")
        (outdir / "workflow_config.json").write_text(
            json.dumps(
                {
                    "schema_version": "avereth-workflow-config/v1",
                    "framework_version": VERSION,
                    "workflow": "rewrite_existing",
                    "task_profile": "full_paper",
                    "publication_track": "cnki-cn",
                    "scene": "journal",
                    "tier": "pro",
                    "output_language": "en",
                    "word_output": "none",
                    "pdf_output": "none",
                    "citation_mode": "author_year",
                    "word_font_policy": "default",
                    "prose_mode": "clear",
                    "canonical_manuscript": "final_paper/main.md",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return outdir

    def test_forged_pass_markdown_without_review_json_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = self._workspace(Path(tmp))
            (outdir / "structured_review.md").write_text(
                "# Structured Peer Review\n\nLifecycle recommendation: **PASS**\n",
                encoding="utf-8",
            )
            (outdir / "reviewer_audit.md").write_text(
                "# Reviewer-Aware Audit\n\nStatus: **PASS**\n",
                encoding="utf-8",
            )
            issues = codex_cnki_gate.check_audit_reports(outdir)
        self.assertTrue(
            any("JSON-authoritative review lifecycle" in issue for issue in issues),
            issues,
        )

    def test_stale_failed_audit_ledger_cannot_pass_live_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            outdir = self._workspace(Path(tmp))
            (outdir / "audit_run.json").write_text(
                json.dumps(
                    {
                        "schema_version": "avereth-audit-run/v1",
                        "status": "FAIL",
                        "canonical_manuscript": None,
                        "invocations": {"structured_review": 1, "reviewer_assurance": 1},
                        "actions": [
                            {
                                "name": "structured_review",
                                "returncode": 1,
                                "implementation_sha256": "0" * 64,
                            },
                            {
                                "name": "reviewer_assurance",
                                "returncode": 1,
                                "implementation_sha256": "0" * 64,
                            },
                        ],
                        "findings": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            issues = codex_cnki_gate.check_live_audits(outdir)
        joined = "\n".join(issues)
        self.assertIn("AUDIT.RUN_INVALID", joined)
        self.assertIn("AUDIT.ACTION_FAILED", joined)


if __name__ == "__main__":
    unittest.main()
