from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "citation_integrity_audit_under_test", HERE / "citation_integrity_audit.py"
)
assert SPEC is not None and SPEC.loader is not None
audit_module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = audit_module
SPEC.loader.exec_module(audit_module)


def write_fixture(
    root: Path,
    *,
    citations: str = r"Evidence \cite{smith2024}.",
    bib_entries: str | None = None,
    scope: str = "final-source",
    channel: str = "Crossref",
    source: str = "https://doi.org/10.1234/example",
    support_claim: str = "This source supports the bounded claim.",
) -> tuple[Path, Path, Path]:
    final = root / "paper_rewriting_output" / "final_paper"
    final.mkdir(parents=True)
    tex = final / "main.tex"
    tex.write_text(citations, encoding="utf-8")
    if bib_entries is None:
        bib_entries = """@article{smith2024,
  author={Smith, Jane},
  title={Reliable Citation Identity Checks},
  year={2024},
  doi={10.1234/example}
}
"""
    bib = final / "references.bib"
    bib.write_text(bib_entries, encoding="utf-8")
    bank = final.parent / "citation_support_bank.md"
    bank.write_text(
        "\n".join(
            [
                "| Candidate ID | Reference/BibTeX | Source Channel | Citation Scope | Source | Verified | Verification Note | Support Claim Sentence |",
                "|---|---|---|---|---|---|---|---|",
                f"| smith2024 | @article{{smith2024, title={{Reliable Citation Identity Checks}}}} | {channel} | {scope} | {source} | yes | official metadata checked | {support_claim} |",
            ]
        ),
        encoding="utf-8",
    )
    return tex, bib, bank


def crossref_work(title: str = "Reliable Citation Identity Checks", author: str = "Smith") -> dict:
    return {
        "status": "ok",
        "message": {
            "title": [title],
            "author": [{"family": author}],
            "issued": {"date-parts": [[2024]]},
        },
    }


def openalex_work(title: str = "Reliable Citation Identity Checks", author: str = "Jane Smith") -> dict:
    return {
        "id": "https://openalex.org/W1",
        "display_name": title,
        "publication_year": 2024,
        "authorships": [{"author": {"display_name": author}}],
    }


class CitationIntegrityAuditTests(unittest.TestCase):
    def temp_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_latex_bibtex_final_subset_passes_and_unused_library_is_advisory(self) -> None:
        extra = """@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}, doi={10.1234/example}}
@article{unused2024, author={Jones, A.}, title={Unused Work}, year={2024}}
"""
        tex, bib, bank = write_fixture(self.temp_root(), bib_entries=extra)
        result = audit_module.audit(tex, bib=bib, bank=bank)
        self.assertTrue(result.ok, result.blocking)
        self.assertEqual(["smith2024"], result.printed_reference_keys)
        self.assertEqual(["unused2024"], result.unused_library_keys)

    def test_missing_bibliography_entry_is_blocking(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root(), citations=r"\cite{missing}")
        result = audit_module.audit(tex, bib=bib, bank=bank)
        self.assertFalse(result.ok)
        self.assertTrue(any("missing from the bibliography" in item for item in result.blocking))

    def test_embedded_bibitem_not_cited_is_blocking(self) -> None:
        root = self.temp_root()
        tex = root / "main.tex"
        tex.write_text(
            r"\cite{used}\begin{thebibliography}{9}\bibitem{used} Used.\bibitem{orphan} Orphan.\end{thebibliography}",
            encoding="utf-8",
        )
        result = audit_module.audit(tex)
        self.assertFalse(result.ok)
        self.assertTrue(any("orphan" in item for item in result.blocking))

    def test_candidate_only_and_missing_claim_are_blocking(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root(), scope="candidate-only", support_claim="")
        result = audit_module.audit(tex, bib=bib, bank=bank)
        self.assertFalse(result.ok)
        joined = " ".join(result.blocking)
        self.assertIn("forbidden scope", joined)
        self.assertIn("no support-claim", joined)

    def test_duplicate_actual_doi_is_blocking(self) -> None:
        entries = """@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}, doi={10.1234/example}}
@article{copy2024, author={Smith, Jane}, title={Same Work Alias}, year={2024}, doi={10.1234/example}}
"""
        tex, bib, _bank = write_fixture(
            self.temp_root(), citations=r"\cite{smith2024,copy2024}", bib_entries=entries
        )
        result = audit_module.audit(tex, bib=bib)
        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate DOI" in item for item in result.style))

    def test_resolving_doi_to_wrong_work_is_blocking(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root())
        result = audit_module.audit(
            tex, bib=bib, bank=bank, verify_online=True,
            fetcher=lambda _url: crossref_work("A Completely Different Work"),
        )
        self.assertFalse(result.ok)
        self.assertEqual("DOI RESOLVES TO DIFFERENT WORK", result.identity[0].status)

    def test_crossref_missing_openalex_doi_fallback_can_verify(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root())

        def fetch(url: str) -> dict:
            if "api.crossref.org/works/" in url and "?" not in url:
                return {"_http_status": 404}
            if "openalex.org/works/https" in url:
                return openalex_work()
            raise AssertionError(url)

        result = audit_module.audit(tex, bib=bib, bank=bank, verify_online=True, fetcher=fetch)
        self.assertTrue(result.ok, result.blocking)
        self.assertEqual("VERIFIED", result.identity[0].status)
        self.assertIn("OpenAlex DOI", result.identity[0].first_pass)

    def test_publication_second_pass_empty_can_mark_likely_fabricated(self) -> None:
        entries = "@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}}"
        tex, bib, _bank = write_fixture(self.temp_root(), bib_entries=entries, source="")

        def empty(url: str) -> dict:
            return {"results": []} if "openalex" in url else {"message": {"items": []}}

        result = audit_module.audit(
            tex, bib=bib, verify_online=True, publication_mode=True, fetcher=empty
        )
        self.assertFalse(result.ok)
        self.assertEqual("LIKELY FABRICATED", result.identity[0].status)
        self.assertEqual("completed-empty", result.identity[0].second_pass)

    def test_publication_network_failure_is_not_checked_not_fabricated(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root())
        result = audit_module.audit(
            tex, bib=bib, bank=bank, verify_online=True,
            publication_mode=True, fetcher=lambda _url: None,
        )
        self.assertFalse(result.ok)
        self.assertEqual("NOT CHECKED", result.identity[0].status)
        self.assertNotIn("FABRICATED", result.identity[0].status)

    def test_cnki_non_doi_final_source_chain_is_not_misclassified(self) -> None:
        entries = "@article{smith2024, author={张三}, title={中文治理研究}, year={2024}}"
        tex, bib, bank = write_fixture(
            self.temp_root(), bib_entries=entries, channel="CNKI",
            source="https://kns.cnki.net/kcms2/article/abstract?v=stable",
        )
        result = audit_module.audit(
            tex, bib=bib, bank=bank, verify_online=True, publication_mode=True,
            fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("CNKI should not call external indexes")),
        )
        self.assertTrue(result.ok, result.blocking)
        self.assertEqual("SOURCE CHAIN VERIFIED", result.identity[0].status)

    def test_non_doi_chinese_publisher_source_is_not_called_fabricated(self) -> None:
        entries = "@article{smith2024, author={张三}, title={中文治理研究}, year={2024}}"
        tex, bib, bank = write_fixture(
            self.temp_root(), bib_entries=entries, channel="Publisher",
            source="https://publisher.example.cn/article/123",
        )

        def empty(url: str) -> dict:
            return {"results": []} if "openalex" in url else {"message": {"items": []}}

        result = audit_module.audit(
            tex, bib=bib, bank=bank, verify_online=True, publication_mode=True, fetcher=empty
        )
        self.assertFalse(result.ok)  # author verification remains a publication gate
        self.assertEqual("NEEDS AUTHOR VERIFICATION", result.identity[0].status)
        self.assertNotIn("FABRICATED", result.identity[0].status)

    def test_markdown_explicit_keys_are_checked_bidirectionally(self) -> None:
        root = self.temp_root()
        md = root / "paper.md"
        md.write_text(
            "Claim [@smith2024].\n\n## References\n\n[smith2024]: Smith (2024). Reliable Citation Identity Checks.\n",
            encoding="utf-8",
        )
        result = audit_module.audit(md)
        self.assertTrue(result.ok, result.blocking)
        self.assertEqual(["smith2024"], result.citation_keys)
        self.assertEqual(["smith2024"], result.printed_reference_keys)

    def test_docx_citation_field_with_exported_bib_is_supported(self) -> None:
        root = self.temp_root()
        docx = root / "paper.docx"
        xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:instrText>CITATION smith2024</w:instrText></w:r></w:p></w:body></w:document>"""
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr("word/document.xml", xml)
        bib = root / "references.bib"
        bib.write_text(
            "@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}}",
            encoding="utf-8",
        )
        result = audit_module.audit(docx, bib=bib)
        self.assertTrue(result.ok, result.blocking)
        self.assertEqual(["smith2024"], result.citation_keys)

    def test_plain_docx_without_stable_citation_fields_is_blocking(self) -> None:
        root = self.temp_root()
        docx = root / "paper.docx"
        xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
<w:p><w:r><w:t>Visible prose with an unkeyed citation (Smith, 2024).</w:t></w:r></w:p>
</w:body></w:document>"""
        with zipfile.ZipFile(docx, "w") as archive:
            archive.writestr("word/document.xml", xml)
        result = audit_module.audit(docx)
        self.assertFalse(result.ok)
        self.assertTrue(any("no stable in-text citation keys" in item for item in result.blocking))

    def test_explicit_nocite_candidate_only_is_printed_and_blocking(self) -> None:
        extra = """@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}, doi={10.1234/example}}
@article{candidate2024, author={Jones, Alex}, title={Candidate Work}, year={2024}}
"""
        tex, bib, bank = write_fixture(
            self.temp_root(),
            citations=r"Evidence \cite{smith2024}. \nocite{candidate2024}",
            bib_entries=extra,
        )
        with bank.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n| candidate2024 | @article{candidate2024, title={Candidate Work}} | Crossref | "
                "candidate-only | https://example.org/candidate | no | screening only | Candidate claim. |\n"
            )
        result = audit_module.audit(tex, bib=bib, bank=bank)
        self.assertFalse(result.ok)
        self.assertIn("candidate2024", result.printed_reference_keys)
        self.assertTrue(any("candidate2024" in item and "not cited" in item for item in result.blocking))
        self.assertTrue(any("candidate2024" in item and "forbidden scope" in item for item in result.blocking))
        self.assertIn("candidate2024", {item.key for item in result.identity})

    def test_nocite_all_candidate_only_is_printed_and_blocking(self) -> None:
        extra = """@article{smith2024, author={Smith, Jane}, title={Reliable Citation Identity Checks}, year={2024}, doi={10.1234/example}}
@article{candidate2024, author={Jones, Alex}, title={Candidate Work}, year={2024}}
"""
        tex, bib, bank = write_fixture(
            self.temp_root(),
            citations=r"Evidence \cite{smith2024}. \nocite{*}",
            bib_entries=extra,
        )
        with bank.open("a", encoding="utf-8") as stream:
            stream.write(
                "\n| candidate2024 | @article{candidate2024, title={Candidate Work}} | Crossref | "
                "candidate-only | https://example.org/candidate | no | screening only | Candidate claim. |\n"
            )
        result = audit_module.audit(tex, bib=bib, bank=bank)
        self.assertFalse(result.ok)
        self.assertEqual(["candidate2024", "smith2024"], result.printed_reference_keys)
        self.assertTrue(any("candidate2024" in item and "not cited" in item for item in result.blocking))
        self.assertTrue(any("candidate2024" in item and "forbidden scope" in item for item in result.blocking))
        self.assertIn("candidate2024", {item.key for item in result.identity})

    def test_write_target_moves_above_final_paper(self) -> None:
        tex, _bib, _bank = write_fixture(self.temp_root())
        expected = tex.parent.parent / "citation_integrity_audit.md"
        self.assertEqual(expected.resolve(), audit_module.report_output_path(tex).resolve())

    def test_report_has_unified_sections_and_pure_status_line(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root())
        result = audit_module.audit(tex, bib=bib, bank=bank)
        text = audit_module.markdown_report(result)
        self.assertIn("\nStatus: PASS\n", text)
        self.assertIn("## Actual Citation / Reference Parity", text)
        self.assertIn("## Source Identity and Existence", text)
        self.assertIn("## Style / Duplicate Diagnostics", text)
        self.assertIn("## Unresolved / Author Verification", text)

    def test_cli_write_creates_root_report_and_returns_success(self) -> None:
        tex, bib, bank = write_fixture(self.temp_root())
        with mock.patch.object(
            sys,
            "argv",
            [
                "citation_integrity_audit.py", str(tex), "--bib", str(bib),
                "--bank", str(bank), "--write",
            ],
        ), redirect_stdout(io.StringIO()):
            self.assertEqual(0, audit_module.main())
        report = tex.parent.parent / "citation_integrity_audit.md"
        self.assertTrue(report.is_file())
        self.assertIn("Status: PASS", report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
