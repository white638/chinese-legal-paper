from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from avereth_core.audit.integrity import run


class IntegrityAuditTests(unittest.TestCase):
    def _run_markdown(self, text: str):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        outdir = Path(holder.name)
        manuscript = outdir / "final_paper" / "main.md"
        manuscript.parent.mkdir(parents=True)
        manuscript.write_text(text, encoding="utf-8")
        return run(outdir, manuscript, write=False)

    def test_author_response_language_is_a_hard_failure(self) -> None:
        for text in (
            "为回应审稿人的意见，本文新增了机制说明。",
            "根据匿名评议意见调整该段。",
            "按第二轮意见补充如下。",
            "The referee requested this addition.",
            "Peer review suggested this addition.",
        ):
            with self.subTest(text=text):
                result = self._run_markdown(text)
                self.assertFalse(result.ok)
                self.assertIn(
                    "INTEGRITY.REVIEW_PROCESS_LEAK",
                    {item.code for item in result.findings},
                )

    def test_internal_writer_view_is_a_hard_failure(self) -> None:
        result = self._run_markdown("The Writer-safe View supplies this paragraph.")
        self.assertFalse(result.ok)
        self.assertIn("INTEGRITY.CONTROL_ARTIFACT_LEAK", {item.code for item in result.findings})

    def test_peer_review_can_remain_the_research_object(self) -> None:
        result = self._run_markdown(
            "The study compares reviewer disagreement across journals and explains its institutional sources."
        )
        self.assertTrue(result.ok, result.findings)

    def test_docx_reader_text_is_checked(self) -> None:
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        outdir = Path(holder.name)
        manuscript = outdir / "final_paper" / "main.docx"
        manuscript.parent.mkdir(parents=True)
        document_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body><w:p><w:r><w:t>In response to the reviewer comment, we added this sentence.</w:t>'
            '</w:r></w:p></w:body></w:document>'
        )
        with zipfile.ZipFile(manuscript, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
        result = run(outdir, manuscript, write=False)
        self.assertFalse(result.ok)
        self.assertIn("INTEGRITY.REVIEW_PROCESS_LEAK", {item.code for item in result.findings})


if __name__ == "__main__":
    unittest.main()
