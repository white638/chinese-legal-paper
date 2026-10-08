from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from lxml import etree


HERE = Path(__file__).resolve().parent
WORK_SCRIPTS = HERE.parents[1]
PACKAGE_SCRIPTS = WORK_SCRIPTS
if not (PACKAGE_SCRIPTS / "avereth_core/__init__.py").is_file():
    configured = os.environ.get("AVERETH_SOURCE_SCRIPTS")
    if not configured:
        raise RuntimeError("AVERETH_SOURCE_SCRIPTS is required outside the repository test tree")
    PACKAGE_SCRIPTS = Path(configured)
sys.path.insert(0, str(PACKAGE_SCRIPTS))
import avereth_core.output  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "avereth_core.output.render_quote_test_impl",
    HERE / "render.py",
)
render = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = render
SPEC.loader.exec_module(render)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = {"w": W_NS}


def make_docx(path: Path, text: str) -> None:
    document = (
        f'<w:document xmlns:w="{W_NS}"><w:body><w:p><w:r><w:t>{text}</w:t>'
        "</w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(path, "w") as package:
        package.writestr("[Content_Types].xml", "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\"/>")
        package.writestr("word/document.xml", document)


def quote_hints(path: Path) -> list[str | None]:
    with zipfile.ZipFile(path) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    hints: list[str | None] = []
    for run in root.findall(".//w:r", W):
        text = "".join(node.text or "" for node in run.findall("w:t", W))
        if text not in {"“", "”"}:
            continue
        fonts = run.find("w:rPr/w:rFonts", W)
        hints.append(None if fonts is None else fonts.get(f"{{{W_NS}}}hint"))
    return hints


class TestRenderQuoteFonts(unittest.TestCase):
    def test_pandoc_route_normalizes_before_validation(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "paper.md"
            source.write_text("placeholder", encoding="utf-8")
            template = root / "pandoc-output.docx"
            destination = root / "paper.docx"
            make_docx(template, "Smith wrote “institutional trust”.")

            def fake_run(command, **_kwargs):
                shutil.copy2(template, Path(command[-1]))
                return 0, "ok"

            renderers = []
            with patch.object(render, "_which", return_value="pandoc"), \
                    patch.object(render, "_run", side_effect=fake_run), \
                    patch.object(render, "_renderer_version", return_value="test"):
                finding = render._render_docx(source, destination, renderers)
            self.assertIsNone(finding)
            self.assertEqual(quote_hints(destination), ["default", "default"])
            self.assertEqual([item["name"] for item in renderers], ["pandoc", "quote-font-normalizer"])

    def test_lossless_docx_copy_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = root / "source.docx"
            destination = root / "copy.docx"
            make_docx(source, "Smith wrote “institutional trust”.")
            before = source.read_bytes()
            renderers = []
            finding = render._render_docx(source, destination, renderers)
            self.assertIsNone(finding)
            self.assertEqual(destination.read_bytes(), before)
            self.assertEqual([item["name"] for item in renderers], ["lossless-docx-copy"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
