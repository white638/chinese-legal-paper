"""Adversarial and positive tests with synthetic text and actual local PDFs."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fitz

from evidence_contract import (BASE_COLUMNS, BINDING_COLUMNS, KEYS, cell, digest,
                               parse_evidence, source_digest, strict_text)
from page_evidence_audit import audit, match_row, row_issues, verdict
from pdf_locate import PdfIndex, locate, normalize


class LocateTests(unittest.TestCase):
    def test_sign_and_comparison_collision_is_only_a_candidate(self):
        left = "The statistics show p<0.05 and beta=-0.15"
        right = "The statistics show p>0.05 and beta=0.15"
        self.assertEqual(normalize(left), normalize(right))
        hit = locate([PdfIndex.from_pages([left])], right)
        self.assertTrue(hit["found"])
        self.assertEqual("review_required", hit["candidates"][0]["fidelity"])

    def test_whitespace_and_fullwidth_are_allowed(self):
        self.assertEqual("located", locate([PdfIndex.from_pages(["Reliable\n source ＡＢＣ"])], "Reliable source ABC")["status"])
        self.assertEqual(strict_text("研究\n表明"), strict_text("研究表明"))

    def test_protected_characters_survive(self):
        for left, right in [("01234567.89", "0123456789"), ("12345678%", "12345678"),
                            ("12345678²", "123456782"), ("variable x₁", "variable x1"),
                            ("does not apply", "does apply"), ("10-12345678", "1012345678")]:
            with self.subTest(left=left):
                result = locate([PdfIndex.from_pages([left])], right)
                self.assertNotEqual("located", result["status"])

    def test_numeric_substring_does_not_drop_leading_sign(self):
        self.assertEqual("VERIFY", locate([PdfIndex.from_pages(["-12345678"])], "12345678")["status"])

    def test_empty_short_and_punctuation_are_safe(self):
        idx = PdfIndex.from_pages(["", "A full readable sentence"])
        for q in ("", "!?!", "abc"):
            self.assertFalse(locate([idx], q, min_len=0)["found"])
            self.assertEqual([], idx.find(normalize(q)) if not normalize(q) else [])

    def test_all_occurrences_and_original_spans_are_preserved(self):
        text = "Shared exact quote. Shared exact quote."
        result = locate([PdfIndex.from_pages([text]), PdfIndex.from_pages([text])], "Shared exact quote")
        self.assertEqual(4, result["occurrences"])
        self.assertEqual("VERIFY", result["status"])
        for hit in result["candidates"]:
            self.assertEqual("Shared exact quote", text[hit["raw_start"]:hit["raw_end"]])

    def test_pdf_sequence_is_not_publication_pagination(self):
        idx = PdfIndex.from_pages(["A faithful quote sample"])
        hit = idx.candidates("A faithful quote sample")[0]
        self.assertIsNone(hit["printed_start"])
        self.assertEqual("pdf-index", hit["page_source"])

    def test_cross_page_gaps_need_review(self):
        idx = PdfIndex.from_pages(["First half sentence FOOTER", "HEADER second half sentence"])
        result = locate([idx], "First half sentence second half sentence")
        self.assertTrue(result["found"])
        self.assertEqual("VERIFY", result["status"])


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "reference_materials").mkdir()
        self.pdf = self.root / "reference_materials/source.pdf"
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "The statistics show p<0.05 and beta=-0.15")
        doc.save(self.pdf)
        doc.close()
        self.source = {"source_id": "SRC-01", "title": "Study Alpha", "publication_year": 2020,
                       "publisher": "Example Press", "edition": "2nd", "local_file": "reference_materials/source.pdf",
                       "sha256": digest(self.pdf), "url": "https://example.org/source"}
        self.registry = self.root / "reference_materials/literature_registry.json"
        self.registry.write_text(json.dumps({"sources": [self.source]}), encoding="utf-8")
        self.quote = "The statistics show p<0.05 and beta=-0.15"
        hit = PdfIndex(self.pdf).candidates(self.quote)[0]
        self.row = dict(zip(KEYS, ["PE-01", "Study Alpha, Example Press, 2020, 2nd", "PDF 第1页", self.quote,
                                  "B", "reference_materials/source.pdf#p1-1", "reference_materials/source.pdf", "verified",
                                  "SRC-01", source_digest(self.source), digest(self.pdf), "pdf", "1-1", "pdf-index",
                                  f"{hit['raw_start']}:{hit['raw_end']}"]))
        self.manuscript = self.root / "main.md"
        self.manuscript.write_text(f'“{self.quote}” [@SRC-01, PDF 第1页]\n', encoding="utf-8")

    def write_bank(self):
        text = "## Page Evidence\n| " + " | ".join((*BASE_COLUMNS, *BINDING_COLUMNS)) + " |\n"
        text += "|" + "---|" * len(KEYS) + "\n| " + " | ".join(cell(self.row[k]) for k in KEYS) + " |\n"
        (self.root / "evidence_bank.md").write_text(text, encoding="utf-8")
        return parse_evidence(text)[0]

    def run_audit(self):
        self.write_bank()
        return audit(self.root, self.manuscript)

    def test_verified_bound_pdf_is_usable(self):
        self.assertEqual("PASS", self.run_audit()["status"])

    def test_exact_status_parser_rejects_substrings(self):
        for status in ("unverified", "VERIFY", "not_verified", "verified later", "unknown", ""):
            self.row["status"] = status
            with self.subTest(status=status):
                self.assertEqual("FAIL", self.run_audit()["status"])

    def test_same_page_wrong_source_cannot_match(self):
        self.write_bank()
        self.manuscript.write_text("Unrelated Book (1999), PDF 第1页", encoding="utf-8")
        self.assertEqual("NO-EVIDENCE", audit(self.root, self.manuscript)["findings"][0]["verdict"])

    def test_source_version_change_invalidates_binding(self):
        self.source["edition"] = "3rd"
        self.registry.write_text(json.dumps({"sources": [self.source]}), encoding="utf-8")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_changed_and_deleted_pdf_invalidate_verification(self):
        self.pdf.write_bytes(self.pdf.read_bytes() + b"\nchanged")
        self.assertEqual("FAIL", self.run_audit()["status"])
        self.pdf.unlink()
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_full_quote_change_is_rejected(self):
        self.row["quote"] = self.quote.replace("<", ">").replace("=-", "=")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_manuscript_quote_cannot_borrow_correct_evidence(self):
        self.manuscript.write_text(f'“{self.quote.replace("<", ">") }” [@SRC-01, PDF 第1页]', encoding="utf-8")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_pdf_pages_cannot_be_used_as_publication_pages(self):
        self.row["locator"] = "第1页"
        self.row["locator_kind"] = "publication"
        self.manuscript.write_text("[@SRC-01, 第1页]", encoding="utf-8")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_publication_offset_requires_observed_basis(self):
        self.row.update(locator="第23页", locator_kind="publication", page_basis="start-page=23: publisher metadata and page footer")
        self.manuscript.write_text("[@SRC-01, 第23页]", encoding="utf-8")
        self.assertEqual("PASS", self.run_audit()["status"])
        self.row["locator"] = "第24页"
        self.manuscript.write_text("[@SRC-01, 第24页]", encoding="utf-8")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_tier_a_image_binding_and_missing_image(self):
        image = self.root / "page.png"
        with fitz.open(self.pdf) as doc:
            doc[0].get_pixmap().save(image)
        self.row.update(tier="A", file="page.png", source=self.source["url"], artifact_sha256=digest(image),
                        page_basis="Observed original page and matching second edition")
        self.assertEqual("PASS", self.run_audit()["status"])
        image.unlink()
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_legacy_row_is_readable_but_not_currently_verified(self):
        for key in KEYS[8:]:
            self.row[key] = ""
        row = self.write_bank()
        self.assertEqual("UNVERIFIED", verdict(row, self.root, [self.source]))

    def test_no_citations_is_explicitly_not_applicable(self):
        self.manuscript.write_text("A statement with no page citation.", encoding="utf-8")
        self.assertEqual("NOT_APPLICABLE", audit(self.root, self.manuscript)["status"])

    def test_missing_evidence_bank_is_a_failure(self):
        self.assertEqual("FAIL", audit(self.root, self.manuscript)["status"])

    def test_partial_page_range_does_not_cover_whole_citation(self):
        self.manuscript.write_text("[@SRC-01, PDF 第1-2页]", encoding="utf-8")
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_locator_text_must_agree_with_its_declared_kind(self):
        self.row["locator"] = "第1页"
        self.assertEqual("FAIL", self.run_audit()["status"])

    def test_locator_cli_never_emits_verified(self):
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("pdf_locate.py")), str(self.pdf),
                                 "--quote", self.quote, "--markdown"], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("| VERIFY |", result.stdout)
        self.assertNotIn("| verified |", result.stdout)


if __name__ == "__main__":
    unittest.main()
