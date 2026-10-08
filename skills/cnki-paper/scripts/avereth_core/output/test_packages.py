from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from avereth_core.build.manuscript import ManuscriptSelection
from avereth_core.config import validate_workflow_config
from avereth_core.output.policy import delivery_relatives, preview_relatives
from avereth_core.output.response import build_response_package
from avereth_core.output.submission import build_submission_package
from avereth_core.output.translation import _language_and_parity_findings, build_translation_package
from avereth_core.version import VERSION, WORKFLOW_CONFIG_SCHEMA


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_docx(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f'<w:body><w:p><w:r><w:t>{escaped}</w:t></w:r></w:p></w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr("word/document.xml", document)


def base_config(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
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
    }
    payload.update(updates)
    return payload


class PackageTests(unittest.TestCase):
    def selection(self, root: Path, text: str = "English source text " * 50 + " 10.1000/example") -> ManuscriptSelection:
        path = root / "final_paper" / "main.md"
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        return ManuscriptSelection(path, "final_paper/main.md", sha(path))

    def test_package_configuration_is_fail_closed(self) -> None:
        config = base_config(translation_package="zh", translation_source="translation_materials/paper.zh.md")
        issues = validate_workflow_config(config)
        self.assertIn("translation_package=zh requires translation_coverage_source", issues)
        config = base_config(
            submission_package="journal",
            submission_source_dir="submission_materials",
            submission_required_files=["cover_letter.md"],
        )
        self.assertIn("submission_package=journal requires submission_contract", validate_workflow_config(config))
        config = base_config(
            task_profile="full_paper",
            response_package="review_response",
            response_source_dir="response_materials",
            response_review_source="reviews/reviewer.md",
            response_required_files=["response_letter.md"],
        )
        self.assertIn(
            "formal response/rebuttal packaging requires task_profile=manuscript_revision",
            validate_workflow_config(config),
        )

    def test_translation_package_requires_distinct_bound_chinese_source(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = self.selection(root)
            translated = root / "translation_materials" / "paper.zh.md"
            translated.parent.mkdir()
            translated.write_text("这是经过人工复核的中文译稿。" * 80 + " 10.1000/example", encoding="utf-8")
            coverage = root / "translation_materials" / "coverage.json"
            coverage.write_text(json.dumps({
                "schema_version": "avereth-translation-coverage/v1",
                "status": "confirmed",
                "source_sha256": canonical.sha256,
                "translation_sha256": sha(translated),
                "reviewed_by": "thread-test",
                "units": [{"kind": "section", "source_anchor": "whole manuscript", "translation_anchor": "全文", "status": "final"}],
            }), encoding="utf-8")
            config = base_config(
                translation_package="zh",
                translation_source="translation_materials/paper.zh.md",
                translation_coverage_source="translation_materials/coverage.json",
            )
            candidate = root / ".avereth-output-candidate"
            candidate.mkdir()

            def fake_docx(_source: Path, destination: Path, renderers: list[dict[str, object]]):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"editable-docx")
                renderers.append({"name": "fake-docx"})
                return None

            def fake_preview(_source: Path, destination: Path, renderers: list[dict[str, object]]):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF")
                renderers.append({"name": "fake-preview"})
                return None

            with mock.patch("avereth_core.output.translation._render_docx", side_effect=fake_docx), mock.patch(
                "avereth_core.output.translation._render_word_preview", side_effect=fake_preview
            ), mock.patch("avereth_core.output.translation._pdf_pages", return_value=1):
                outcome = build_translation_package(root, candidate, canonical, config)
            self.assertTrue(outcome.result.ok, [item.as_dict() for item in outcome.result.findings])
            self.assertEqual(
                {
                    "translation_zh/paper.zh.docx",
                    "translation_zh/translation_coverage.md",
                    "translation_zh/translation_manifest.json",
                },
                {item["path"] for item in outcome.deliveries},
            )
            self.assertEqual(["render_qa/translation_preview.pdf"], [item["path"] for item in outcome.qa_artifacts])
            self.assertTrue((candidate / "reports" / "translation_guard.md").is_file())
            self.assertEqual(tuple(sorted(item["path"] for item in outcome.deliveries)), tuple(sorted(
                relative for relative in delivery_relatives(config, canonical.path) if relative.startswith("translation_zh/")
            )))
            self.assertIn("render_qa/translation_preview.pdf", preview_relatives(config))

    def test_author_year_translation_cannot_drop_citations(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = self.selection(root, "Substantive English argument (Smith, 2020). " * 100)
            translated = root / "translation_materials" / "paper.zh.md"
            translated.parent.mkdir()
            translated.write_text("这是经过人工复核但错误删除全部作者年份引文的中文译稿。" * 100, encoding="utf-8")
            coverage = root / "translation_materials" / "coverage.json"
            coverage.write_text(json.dumps({
                "schema_version": "avereth-translation-coverage/v1",
                "status": "confirmed",
                "source_sha256": canonical.sha256,
                "translation_sha256": sha(translated),
                "reviewed_by": "thread-test",
                "units": [{"kind": "section", "source_anchor": "whole manuscript", "translation_anchor": "全文", "status": "final"}],
            }), encoding="utf-8")
            config = base_config(
                citation_mode="author_year",
                translation_package="zh",
                translation_source="translation_materials/paper.zh.md",
                translation_coverage_source="translation_materials/coverage.json",
            )
            candidate = root / ".avereth-output-candidate"
            candidate.mkdir()
            outcome = build_translation_package(root, candidate, canonical, config)
            self.assertFalse(outcome.result.ok)
            self.assertIn(
                "OUTPUT.TRANSLATION_CITATION_PARITY",
                {item.code for item in outcome.result.findings},
            )

    def test_translation_cannot_add_citation_identities_and_accepts_full_width_punctuation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            translated = root / "translated.md"
            source.write_text("Substantive English argument without citations. " * 100, encoding="utf-8")
            translated.write_text(
                "这是经过完整人工复核的中文实质论证。" * 100
                + "（Fabricated，2025） https://doi.org/10.9999/fake",
                encoding="utf-8",
            )
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertTrue(metrics["unexpected_stable_tokens"])

            source.write_text("Substantive English argument (Smith, 2020). " * 100, encoding="utf-8")
            translated.write_text("这是经过完整人工复核的中文实质论证（Smith，2020）。" * 100, encoding="utf-8")
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertEqual([], metrics["missing_stable_tokens"])
            self.assertEqual([], metrics["unexpected_stable_tokens"])

    def test_author_year_parity_supports_cjk_authors_without_treating_month_dates_as_citations(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.md"
            translated = root / "translated.md"
            source.write_text("Substantive English discussion (张三, 2020). " * 100, encoding="utf-8")
            translated.write_text("这是完整的中文实质论证，但错误删除了中文作者年份引文。" * 100, encoding="utf-8")
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertTrue(metrics["missing_stable_tokens"])

            source.write_text("Substantive English discussion prepared in (May 2020). " * 100, encoding="utf-8")
            translated.write_text("这是在2020年5月完成的完整中文实质论证。" * 100, encoding="utf-8")
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertEqual(0, metrics["stable_tokens"])

            source.write_text(
                "Substantive discussion (Müller, 2020) and (García, 2021). " * 100,
                encoding="utf-8",
            )
            translated.write_text("这是完整的中文实质论证，但错误删除了重音拉丁作者引文。" * 100, encoding="utf-8")
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertEqual(200, sum(
                int(token.rsplit(" x", 1)[1]) if " x" in token else 1
                for token in metrics["missing_stable_tokens"]
                if token.startswith("author-year:")
            ))

            source.write_text(
                "The schedule mentions (Spring 2020), (the 2020 survey), "
                "(from 2018 to 2020), and (pre-2020) material. " * 100,
                encoding="utf-8",
            )
            translated.write_text("译文如实改写了春季、调查期和前后年份等普通时间表达。" * 100, encoding="utf-8")
            findings, metrics = _language_and_parity_findings(source, translated, "author_year")
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_IDENTITY_REQUIRED", {item.code for item in findings})
            self.assertEqual(0, metrics["stable_tokens"])

            source.write_text(
                "Substantive discussion (Smith 2020), (Müller 2021), and (张三 2022). " * 100,
                encoding="utf-8",
            )
            translated.write_text(
                "完整中文论证保留（Smith 2020）、（Müller 2021）与（张三 2022）。" * 100,
                encoding="utf-8",
            )
            allowed = {
                "author-year:smith:2020",
                "author-year:müller:2021",
                "author-year:张三:2022",
            }
            findings, metrics = _language_and_parity_findings(source, translated, "author_year", allowed)
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})
            self.assertNotIn("OUTPUT.TRANSLATION_CITATION_IDENTITY_REQUIRED", {item.code for item in findings})
            self.assertEqual(300, metrics["stable_tokens"])

            translated.write_text("完整中文论证删除了全部无逗号作者年份引文。" * 100, encoding="utf-8")
            findings, _ = _language_and_parity_findings(source, translated, "author_year", allowed)
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in findings})

    def test_footnote_translation_cannot_keep_marker_but_drop_citation_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source_md = root / "source.md"
            translated_md = root / "translated.md"
            source_md.write_text("English evidence body. " * 40 + "[^1]\n\n[^1]: Smith (2020).", encoding="utf-8")
            translated_md.write_text("这是完整的中文译文正文。" * 80 + "[^1]\n\n[^1]: 普通说明。", encoding="utf-8")
            md_findings, _ = _language_and_parity_findings(source_md, translated_md, "footnote")
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in md_findings})

            source_tex = root / "source.tex"
            translated_tex = root / "translated.tex"
            source_tex.write_text("English evidence body. " * 40 + r"\footnote{Smith (2020).}", encoding="utf-8")
            translated_tex.write_text("这是完整的中文译文正文。" * 80 + r"\footnote{普通说明。}", encoding="utf-8")
            tex_findings, _ = _language_and_parity_findings(source_tex, translated_tex, "footnote")
            self.assertIn("OUTPUT.TRANSLATION_CITATION_PARITY", {item.code for item in tex_findings})

            chicago = "John Smith, Title, Journal 12, no. 3 (2018): 10-12."
            source_md.write_text("English evidence body. " * 40 + f"[^1]\n\n[^1]: {chicago}", encoding="utf-8")
            unresolved_md, _ = _language_and_parity_findings(source_md, translated_md, "footnote")
            self.assertIn("OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE", {item.code for item in unresolved_md})
            source_tex.write_text("English evidence body. " * 40 + rf"\footnote{{{chicago}}}", encoding="utf-8")
            unresolved_tex, _ = _language_and_parity_findings(source_tex, translated_tex, "footnote")
            self.assertIn("OUTPUT.TRANSLATION_FOOTNOTE_UNVERIFIABLE", {item.code for item in unresolved_tex})

    def test_submission_contract_drives_exact_files_without_global_highlight_rules(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = self.selection(root)
            candidate = root / ".avereth-output-candidate"
            manuscript = candidate / "final_paper" / "paper.docx"
            manuscript.parent.mkdir(parents=True)
            manuscript.write_bytes(b"docx")
            materials = root / "submission_materials"
            materials.mkdir()
            (materials / "cover_letter.md").write_text("Dear Editor,\n" + "Substantive cover letter. " * 8, encoding="utf-8")
            contract = root / "submission_materials" / "contract.json"
            contract.write_text(json.dumps({
                "schema_version": "avereth-submission-contract/v1",
                "status": "confirmed",
                "target_name": "Example Journal",
                "language": "en",
                "required_files": ["cover_letter.md"],
                "confirmed_by": "author-test",
            }), encoding="utf-8")
            config = base_config(
                target_name="Example Journal",
                submission_package="journal",
                submission_source_dir="submission_materials",
                submission_contract="submission_materials/contract.json",
                submission_required_files=["cover_letter.md"],
            )
            outcome = build_submission_package(root, candidate, canonical, config)
            self.assertTrue(outcome.result.ok, [item.as_dict() for item in outcome.result.findings])
            paths = {item["path"] for item in outcome.deliveries}
            self.assertEqual({
                "submission_package/paper.docx",
                "submission_package/cover_letter.md",
                "submission_package/submission_manifest.json",
            }, paths)
            self.assertNotIn("submission_package/highlights.md", paths)

    def test_submission_docx_must_be_valid_placeholder_free_and_visually_reviewable(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = self.selection(root)
            candidate = root / ".avereth-output-candidate"
            manuscript = candidate / "final_paper" / "paper.docx"
            manuscript.parent.mkdir(parents=True)
            manuscript.write_bytes(b"primary-docx")
            materials = root / "submission_materials"
            materials.mkdir()
            cover = materials / "cover_letter.en.docx"
            cover.write_bytes(b"NOT-A-DOCX TODO PLACEHOLDER")
            contract = materials / "contract.json"
            contract.write_text(json.dumps({
                "schema_version": "avereth-submission-contract/v1",
                "status": "confirmed",
                "target_name": "Example Journal",
                "language": "en",
                "required_files": ["cover_letter.en.docx"],
                "confirmed_by": "author-test",
            }), encoding="utf-8")
            config = base_config(
                target_name="Example Journal",
                submission_package="journal",
                submission_source_dir="submission_materials",
                submission_contract="submission_materials/contract.json",
                submission_required_files=["cover_letter.en.docx"],
            )
            invalid = build_submission_package(root, candidate, canonical, config)
            self.assertFalse(invalid.result.ok)
            self.assertIn("OUTPUT.SUBMISSION_WORD_INVALID", {item.code for item in invalid.result.findings})

            write_docx(cover, "Dear Editor, this is a complete and placeholder-free cover letter for review.")

            def fake_preview(_source: Path, destination: Path, renderers: list[dict[str, object]]):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"%PDF-1.4\n%%EOF")
                renderers.append({"name": "fake-preview"})
                return None

            with mock.patch("avereth_core.output.submission._render_word_preview", side_effect=fake_preview), mock.patch(
                "avereth_core.output.submission._pdf_pages", return_value=1
            ):
                valid = build_submission_package(root, candidate, canonical, config)
            self.assertTrue(valid.result.ok, [item.as_dict() for item in valid.result.findings])
            expected_preview = "render_qa/submission_package/cover_letter.en.docx.pdf"
            self.assertEqual([expected_preview], [item["path"] for item in valid.qa_artifacts])
            self.assertIn(expected_preview, preview_relatives(config))

    def test_formal_response_binds_review_confirmation_and_revised_manuscript(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            canonical = self.selection(root)
            candidate = root / ".avereth-output-candidate"
            manuscript = candidate / "final_paper" / "paper.docx"
            manuscript.parent.mkdir(parents=True)
            manuscript.write_bytes(b"revised-docx")
            review = root / "reviews" / "reviewer.md"
            review.parent.mkdir()
            review.write_text("CMT-1 Please clarify the mechanism.", encoding="utf-8")
            materials = root / "response_materials"
            materials.mkdir()
            (materials / "response_letter.md").write_text("CMT-1 We clarified the mechanism with bounded evidence.", encoding="utf-8")
            (materials / "change_log.md").write_text("CMT-1 Revised manuscript section 2, lines 10-18.", encoding="utf-8")
            (root / "review_comment_confirmation.json").write_text(json.dumps({
                "schema_version": "avereth-review-comment-confirmation/v1",
                "status": "confirmed",
                "confirmed_by": "author-test",
                "comment_ids": ["CMT-1"],
                "review_source_sha256": sha(review),
            }), encoding="utf-8")
            config = base_config(
                task_profile="manuscript_revision",
                response_package="review_response",
                response_source_dir="response_materials",
                response_review_source="reviews/reviewer.md",
                response_required_files=["response_letter.md", "change_log.md"],
            )
            outcome = build_response_package(root, candidate, canonical, config)
            self.assertTrue(outcome.result.ok, [item.as_dict() for item in outcome.result.findings])
            manifest = json.loads((candidate / "review_response" / "response_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(canonical.as_dict(), manifest["canonical_manuscript"])
            self.assertEqual(sha(review), manifest["review_source"]["sha256"])
            confirmation = root / "review_comment_confirmation.json"
            confirmation.write_text(json.dumps({
                "schema_version": "avereth-review-comment-confirmation/v1",
                "status": "confirmed",
                "comment_ids": ["CMT-1"],
                "review_source_sha256": sha(review),
            }), encoding="utf-8")
            unconfirmed = build_response_package(root, candidate, canonical, config)
            self.assertFalse(unconfirmed.result.ok)
            self.assertIn("OUTPUT.RESPONSE_CONFIRMATION", {item.code for item in unconfirmed.result.findings})
            confirmation.write_text(json.dumps({
                "schema_version": "avereth-review-comment-confirmation/v1",
                "status": "confirmed",
                "confirmed_by": "author-test",
                "comment_ids": ["CMT-1"],
                "review_source_sha256": sha(review),
            }), encoding="utf-8")
            (materials / "response_letter.md").write_text("CMT-1 needs-author", encoding="utf-8")
            failed = build_response_package(root, candidate, canonical, config)
            self.assertFalse(failed.result.ok)
            self.assertIn("OUTPUT.RESPONSE_PLACEHOLDER", {item.code for item in failed.result.findings})


if __name__ == "__main__":
    unittest.main()
