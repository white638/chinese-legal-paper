from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("word_guard_quote_test", HERE / "word_guard.py")
word_guard = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = word_guard
SPEC.loader.exec_module(word_guard)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def package(path: Path, document_body: str, extra: dict[str, str] | None = None) -> None:
    document = (
        f'<w:document xmlns:w="{W_NS}"><w:body>{document_body}</w:body></w:document>'
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")
        archive.writestr("word/document.xml", document)
        for name, xml in (extra or {}).items():
            archive.writestr(name, xml)


def run(text: str, hint: str | None = None) -> str:
    rpr = "" if hint is None else f'<w:rPr><w:rFonts w:hint="{hint}"/></w:rPr>'
    return f"<w:r>{rpr}<w:t>{text}</w:t></w:r>"


class TestWordQuoteGuard(unittest.TestCase):
    def test_reversed_quote_and_apostrophe_hints_are_errors(self):
        body = (
            f"<w:p>{run('他说：')}{run('“', 'default')}{run('制度')}{run('”', 'default')}</w:p>"
            f"<w:p>{run('Smith wrote ')}{run('“', 'eastAsia')}{run('trust')}{run('”', 'eastAsia')}</w:p>"
            f"<w:p>{run('O’Connor', 'eastAsia')}</w:p>"
        )
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.docx"
            package(path, body)
            errors, warnings = word_guard.quote_font_findings(path)
        joined = "\n".join(errors)
        self.assertIn("WORD.QUOTE_FONT_MISMATCH", joined)
        self.assertIn("WORD.APOSTROPHE_FONT_MISMATCH", joined)
        self.assertIn("WORD.QUOTE_RUN_NOT_SPLIT", joined)
        self.assertEqual(warnings, [])

    def test_correct_hints_pass_in_document_and_footer(self):
        body = f"<w:p>{run('他说：')}{run('“', 'eastAsia')}{run('制度')}{run('”', 'eastAsia')}</w:p>"
        footer = (
            f'<w:ftr xmlns:w="{W_NS}"><w:p>{run("Smith wrote ")}{run("“", "default")}'
            f'{run("trust")}{run("”", "default")}</w:p></w:ftr>'
        )
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "good.docx"
            package(path, body, {"word/footer1.xml": footer})
            errors, warnings = word_guard.quote_font_findings(path)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_unpaired_quote_is_a_warning_not_a_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "ambiguous.docx"
            package(path, f"<w:p>{run('“', 'default')}</w:p>")
            errors, warnings = word_guard.quote_font_findings(path)
            result = word_guard.check_docx(
                path,
                min_chars=0,
                font_policy="template",
                require_title=False,
            )
        self.assertEqual(errors, [])
        self.assertTrue(any("WORD.QUOTE_LOCALE_AMBIGUOUS" in item for item in warnings))
        self.assertTrue(result.ok)
        self.assertTrue(any("WORD.QUOTE_LOCALE_AMBIGUOUS" in item for item in result.warnings))


if __name__ == "__main__":
    unittest.main(verbosity=2)
