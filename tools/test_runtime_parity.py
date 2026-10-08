from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.runtime_parity import compare


class RuntimeParityTests(unittest.TestCase):
    def test_runtime_parity_excludes_tests_caches_and_node_modules(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            for base in (source, installed):
                (base / "skill" / "scripts").mkdir(parents=True)
                (base / "skill" / "scripts" / "run.py").write_text("print('ok')\n", encoding="utf-8")
            (source / "skill" / "scripts" / "test_run.py").write_text("ignored\n", encoding="utf-8")
            (installed / "skill" / "node_modules").mkdir()
            (installed / "skill" / "node_modules" / "local.js").write_text("ignored\n", encoding="utf-8")

            payload = compare(source, installed)
            self.assertEqual("PASS", payload["status"])

    def test_runtime_parity_reports_content_mismatch_and_extra(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            (source / "skill").mkdir(parents=True)
            (installed / "skill").mkdir(parents=True)
            (source / "skill" / "run.py").write_text("one\n", encoding="utf-8")
            (installed / "skill" / "run.py").write_text("two\n", encoding="utf-8")
            (installed / "skill" / "stale.md").write_text("stale\n", encoding="utf-8")
            (installed / ".system").mkdir()
            (installed / ".system" / "unmanaged.md").write_text("ignored\n", encoding="utf-8")

            payload = compare(source, installed)
            self.assertEqual("FAIL", payload["status"])
            self.assertEqual(["skill/run.py"], payload["mismatch"])
            self.assertEqual(["skill/stale.md"], payload["extra"])

    def test_runtime_parity_rejects_tests_and_caches_in_install_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            installed = root / "installed"
            (source / "skill").mkdir(parents=True)
            (installed / "skill" / "scripts" / "__pycache__").mkdir(parents=True)
            (source / "skill" / "run.py").write_text("same\n", encoding="utf-8")
            (installed / "skill" / "run.py").write_text("same\n", encoding="utf-8")
            (installed / "skill" / "scripts" / "test_run.py").write_text("test\n", encoding="utf-8")
            (installed / "skill" / "scripts" / "__pycache__" / "run.pyc").write_text(
                "cache\n",
                encoding="utf-8",
            )

            payload = compare(source, installed)
            self.assertEqual("FAIL", payload["status"])
            self.assertIn("skill/scripts/test_run.py", payload["forbidden"])
            self.assertIn("skill/scripts/__pycache__", payload["forbidden"])


if __name__ == "__main__":
    unittest.main()
