"""Exercise the selected manuscript, real helper process and cache inputs."""
import importlib
import json
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from avereth_core.artifacts import sha256_file

run_all = importlib.import_module("avereth_core.audit.run_all")
SKILLS = Path(run_all.__file__).resolve().parents[4]


class PageEvidenceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        final = self.root / "final_paper"
        final.mkdir()
        self.manuscript = final / "main.md"
        self.manuscript.write_text("Canonical manuscript with no pinpoint citations.", encoding="utf-8")
        (final / "main.tex").write_text(r"\footnote{Old source, 第99页}", encoding="utf-8")
        self.config = {"scene": "report_review", "canonical_manuscript": "final_paper/main.md"}

    def action(self):
        return next(a for a in run_all._actions(self.root, SKILLS, self.config, self.manuscript) if a.name == "page_evidence")

    def test_canonical_markdown_is_audited_and_report_is_written(self):
        selected = run_all._select_canonical_manuscript(self.root, self.config)
        self.assertEqual(self.manuscript, selected)
        code, detail = run_all._run(self.action())
        self.assertEqual(0, code, detail)
        report = (self.root / "page_evidence_audit.md").read_text(encoding="utf-8")
        self.assertIn("NOT_APPLICABLE", report)
        self.assertIn(str(self.manuscript), report)
        self.assertNotIn("全部", report)

    def test_pinpoint_citations_without_a_bank_cannot_skip_the_action(self):
        self.manuscript.write_text("Unknown work, 第12页", encoding="utf-8")
        self.config["page_evidence_required"] = False
        code, _ = run_all._run(self.action())
        self.assertEqual(1, code)
        self.assertIn("NO-EVIDENCE", (self.root / "page_evidence_audit.md").read_text(encoding="utf-8"))

    def test_docx_footnotes_are_in_scope(self):
        self.manuscript = self.manuscript.with_suffix(".docx")
        with zipfile.ZipFile(self.manuscript, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="w"><w:body><w:p><w:r><w:t>Text</w:t></w:r></w:p></w:body></w:document>')
            archive.writestr("word/footnotes.xml", '<w:footnotes xmlns:w="w"><w:footnote><w:p><w:r><w:t>Unknown source, 第12页</w:t></w:r></w:p></w:footnote></w:footnotes>')
        code, _ = run_all._run(self.action())
        self.assertEqual(1, code)

    def test_tex_inline_pinpoint_commands_are_in_scope(self):
        self.manuscript = self.manuscript.with_suffix(".tex")
        for citation in (r"\parencite[p. 12]{SRC-01}", r"\cite[12]{SRC-01}"):
            self.manuscript.write_text(citation, encoding="utf-8")
            code, _ = run_all._run(self.action())
            self.assertEqual(1, code)

    def test_evidence_files_and_shared_implementation_invalidate_cache(self):
        artifacts = self.root / "evidence"
        artifacts.mkdir()
        image = artifacts / "page.png"
        image.write_bytes(b"synthetic image fixture")
        pdf = artifacts / "source.pdf"
        pdf.write_bytes(b"synthetic source artifact fixture")
        registry = self.root / "reference_materials/literature_registry.json"
        registry.parent.mkdir()
        registry.write_text(json.dumps({"sources": [{"source_id": "SRC-01", "local_file": "evidence/source.pdf"}]}), encoding="utf-8")
        (self.root / "evidence_bank.md").write_text(
            "## Page Evidence\n| Evidence ID | Work (Edition-locked) | Locator | Quote Snippet | Tier | Evidence Source | Evidence File | Status | Source ID |\n"
            "|---|---|---|---|---|---|---|---|---|\n"
            "| PE-01 | Study | 第1页 | bounded source quotation | A | https://example.org | evidence/page.png | verified | SRC-01 |\n", encoding="utf-8")
        helper_dir = self.root / "helpers"
        shutil.copytree(SKILLS / "page-evidence/scripts", helper_dir, ignore=shutil.ignore_patterns("__pycache__"))
        action = run_all.Action("page_evidence", helper_dir / "page_evidence_audit.py", (str(self.root),))
        report = self.root / "page_evidence_audit.md"
        report.write_text("Status: PASS\n", encoding="utf-8")
        previous = {"status": "PASS", "actions": [{"name": "page_evidence", "returncode": 0,
                    "input_digest": run_all._action_input_digest(action, self.root, self.manuscript),
                    "implementation_sha256": sha256_file(action.script), "revision_impact_sha256": "",
                    "output_artifacts": [{"path": report.name, "sha256": sha256_file(report)}]}]}
        self.assertIsNotNone(run_all._cached_action_record(previous, action, self.root, self.manuscript))
        for path in (image, pdf, helper_dir / "evidence_contract.py", helper_dir / "pdf_locate.py", report):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"\n# changed\n")
                self.assertIsNone(run_all._cached_action_record(previous, action, self.root, self.manuscript))
                path.write_bytes(original)
        image.unlink()
        self.assertIsNone(run_all._cached_action_record(previous, action, self.root, self.manuscript))


if __name__ == "__main__":
    unittest.main()
