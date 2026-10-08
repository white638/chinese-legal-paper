#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from lxml import etree


HERE = Path(__file__).resolve().parent
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W = {"w": W_NS}


def qn(local: str) -> str:
    return f"{{{W_NS}}}{local}"


def bundled_node() -> Path | None:
    explicit = os.environ.get("CODEX_NODE")
    candidates = [
        Path(explicit) if explicit else None,
        Path(shutil.which("node") or "") if shutil.which("node") else None,
        Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe",
    ]
    return next((path for path in candidates if path and path.is_file()), None)


def quote_runs(root):
    result = []
    for run in root.findall(".//w:r", W):
        text = "".join(node.text or "" for node in run.findall("w:t", W))
        if text not in {"“", "”", "‘", "’"}:
            continue
        rfonts = run.find("w:rPr/w:rFonts", W)
        result.append((text, None if rfonts is None else rfonts.get(qn("hint")), rfonts))
    return result


class TestTex2DocxQuoteFonts(unittest.TestCase):
    def test_explicit_and_automatic_quotes_generate_correct_runs(self):
        node = bundled_node()
        if node is None:
            self.skipTest("Node.js is unavailable")
        source = r"""\documentclass{ctexart}
\title{\textbf{标题\zhquote{制度}}}
\author{作者}
\begin{document}
\maketitle

他说：“制度有效。” Smith wrote “institutional trust”.

本文使用\enquote{public value}，并讨论\zhquote{公共价值}。\footnote{Smith called it “trust”.}

Smith wrote ‘O’Connor’s account’.
\end{document}
"""
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            tex = root / "main.tex"
            content = root / "content.json"
            output = root / "paper.docx"
            tex.write_text(source, encoding="utf-8")
            subprocess.run([sys.executable, str(HERE / "parse_tex.py"), str(tex), str(content)], check=True)
            parsed = json.loads(content.read_text(encoding="utf-8"))
            self.assertIn("\ue010制度\ue011", parsed["title"])
            self.assertTrue(any("\ue012public value\ue013" in block["text"] for block in parsed["blocks"]))

            environment = os.environ.copy()
            subprocess.run(
                [str(node), str(HERE / "build_docx.js"), str(content), str(output)],
                check=True,
                env=environment,
            )
            with zipfile.ZipFile(output) as package:
                document = etree.fromstring(package.read("word/document.xml"))
                footnotes = etree.fromstring(package.read("word/footnotes.xml"))

            self.assertNotIn("\ue010", "".join(document.itertext()))
            title = document.find(".//w:body/w:p", W)
            title_quotes = quote_runs(title)
            self.assertEqual([(char, hint) for char, hint, _ in title_quotes],
                             [("“", "eastAsia"), ("”", "eastAsia")])
            self.assertTrue(all(fonts.get(qn("eastAsia")) == "SimHei" for _, _, fonts in title_quotes))

            body_quotes = quote_runs(document)[2:]
            hints = [(char, hint) for char, hint, _ in body_quotes]
            self.assertIn(("“", "eastAsia"), hints)
            self.assertIn(("“", "default"), hints)
            self.assertTrue(all(len(text) == 1 for text, _, _ in body_quotes))
            self.assertEqual(
                [(char, hint) for char, hint, _ in quote_runs(document) if char in {"‘", "’"}],
                [("‘", "default"), ("’", "default"), ("’", "default"), ("’", "default")],
            )
            self.assertEqual(
                [(char, hint) for char, hint, _ in quote_runs(footnotes)],
                [("“", "default"), ("”", "default")],
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
