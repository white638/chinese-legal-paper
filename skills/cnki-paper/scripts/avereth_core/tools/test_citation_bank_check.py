from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("citation_bank_check.py")
SPEC = importlib.util.spec_from_file_location("citation_bank_check_under_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = checker
SPEC.loader.exec_module(checker)


class CitationBankCoveragePolicyTests(unittest.TestCase):
    def test_candidate_count_and_recency_are_warnings_not_hard_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citation_support_bank.md"
            path.write_text(
                "\n".join(
                    [
                        "# Citation Support Bank",
                        "",
                        "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Citation Scope | Verification Note |",
                        "|---|---|---|---|---|---|---|---|---|---|---|---|",
                        "| S01 | Journal article with DOI 10.1000/example | 1998 | foundational | theory | This verified article supplies a concrete and bounded theoretical claim sentence for the paper. | It directly addresses the stated mechanism. | https://example.org/article | Web | yes | final-source | archived detail verification |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = checker.validate(path, 20, 3, 3, 0.80)
            self.assertTrue(result.ok, result.findings)
            self.assertEqual([], result.findings)
            self.assertEqual(2, len(result.warnings))

    def test_candidate_only_row_does_not_need_a_load_bearing_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citation_support_bank.md"
            path.write_text(
                "\n".join(
                    [
                        "# Citation Support Bank",
                        "",
                        "| Candidate ID | Reference/BibTeX | Year | Recency | Supports Section | Support Claim Sentence | Why This Paper Fits | Source | Source Channel | Verified | Citation Scope | Verification Note |",
                        "|---|---|---|---|---|---|---|---|---|---|---|---|",
                        "| S01 | Candidate title | 2026 | recent | screening |  |  | https://example.org/candidate | Web | no | candidate-only | screening/export 2026-07-29 |",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            result = checker.validate(path, 20, 3, 3, 0.80)
            self.assertTrue(result.ok, result.findings)


if __name__ == "__main__":
    unittest.main()
