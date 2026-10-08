"""Tests for the R-free three-line table projection of exhibit companion data."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from exhibits import contract, exhibit as exhibit_cli, table_emit
from test_exhibits import _asset_hash, _write_csv


def _table_spec(profile: str = "international-polisci-econ") -> dict:
    return {
        "schema_version": contract.SPEC_SCHEMA_VERSION,
        "exhibit_id": "TAB-MAIN-001",
        "kind": "regression_or_balance_table",
        "placement": "main",
        "argument_role": "estimation",
        "source_result_ids": ["RES-001"],
        "quantity": "registered effect",
        "unit": "percentage points",
        "confidence_levels": [0.95],
        "style_profile": profile,
        "style_profile_sha256": _asset_hash(f"style-profiles/{profile}.json"),
        "recipe_sha256": _asset_hash("recipes/regression-or-balance-table.json"),
        "formats": ["pdf", "svg", "png"],
        "caption_requirements": ["estimand", "uncertainty", "sample", "source result"],
    }


def _table_row(term: str, model: str, estimate: float, *, std_error: str | float = 0.03, sample_n: int = 100) -> dict:
    return {
        "schema_version": contract.DATA_SCHEMA_VERSION,
        "exhibit_id": "TAB-MAIN-001",
        "kind": "regression_or_balance_table",
        "quantity": "registered effect",
        "term": term,
        "x": "",
        "estimate": estimate,
        "std_error": std_error,
        "conf_low": "",
        "conf_high": "",
        "confidence_level": 0.95,
        "model_label": model,
        "group_label": "",
        "panel_label": "",
        "is_reference": False,
        "sample_n": sample_n,
        "estimand": "registered average effect",
        "unit": "percentage points",
        "vcov_type": "cluster robust",
        "cluster_level": "province",
        "source_result_id": "RES-001",
        "source_numeric_locator": f"json:/{model}/{term}",
        "line_type": "solid",
        "marker": "16",
        "color": "",
    }


def _rows() -> list[dict]:
    return [
        _table_row("Treatment", "Model 1", 0.12),
        _table_row("Treatment", "Model 2", 0.1, sample_n=98),
        _table_row("Control mean", "Model 1", 1234.0, std_error=""),
        _table_row("Control mean", "Model 2", 1200.0, std_error="", sample_n=98),
    ]


class TableEmitTests(unittest.TestCase):
    def test_markdown_projection_keeps_numbers_notes_and_provenance(self) -> None:
        spec = _table_spec()
        text = table_emit.build_table(spec, _rows(), fmt="md", data_sha256="ab" * 32)
        lines = text.splitlines()
        self.assertTrue(lines[0].startswith("<!-- avereth-exhibit TAB-MAIN-001;"))
        self.assertIn(f"spec_sha256={contract.canonical_digest(spec)}", lines[0])
        self.assertIn("data_sha256=" + "ab" * 32, lines[0])
        self.assertIn("| Variable | Model 1 | Model 2 |", lines)
        self.assertIn("| Treatment | 0.120 | 0.100 |", lines)
        self.assertIn("|  | (0.030) | (0.030) |", lines)
        self.assertIn("| Control mean | 1234 | 1200 |", lines)
        self.assertIn("| Observations | 100 | 98 |", lines)
        note = lines[-1]
        self.assertTrue(note.startswith("Note: Standard errors in parentheses"))
        self.assertIn("Clustered by: province", note)
        self.assertIn("Confidence level: 0.95", note)
        self.assertNotIn("sha256", note)

    def test_chinese_profile_uses_chinese_labels(self) -> None:
        text = table_emit.build_table(_table_spec("cn-social-science"), _rows(), fmt="md")
        self.assertIn("| 变量 | Model 1 | Model 2 |", text)
        self.assertIn("| 样本量 | 100 | 98 |", text)
        self.assertIn("注: 括号内为标准误", text)

    def test_tex_projection_is_booktabs_and_escapes_text(self) -> None:
        rows = _rows()
        rows[0]["term"] = "Treatment_x & share"
        rows[1]["term"] = "Treatment_x & share"
        text = table_emit.build_table(_table_spec(), rows, fmt="tex")
        self.assertTrue(text.startswith("% avereth-exhibit TAB-MAIN-001;"))
        for rule in ("\\toprule", "\\midrule", "\\bottomrule", "\\begin{tabular}{lrr}"):
            self.assertIn(rule, text)
        self.assertIn("Treatment\\_x \\& share & 0.120 & 0.100 \\\\", text)
        self.assertIn("Observations & 100 & 98 \\\\", text)

    def test_confidence_intervals_are_used_when_standard_errors_are_absent(self) -> None:
        rows = [_table_row("Treatment", "Model 1", 0.12, std_error="")]
        rows[0]["conf_low"] = 0.0612
        rows[0]["conf_high"] = 0.1788
        text = table_emit.build_table(_table_spec(), rows, fmt="md")
        self.assertIn("|  | [0.061, 0.179] |", text)
        self.assertIn("Confidence intervals in brackets", text)

    def test_non_table_kinds_and_duplicate_cells_are_rejected(self) -> None:
        spec = _table_spec()
        spec["kind"] = "event_study"
        with self.assertRaisesRegex(ValueError, "KIND_UNSUPPORTED"):
            table_emit.build_table(spec, _rows(), fmt="md")
        rows = _rows()
        rows.append(_table_row("Treatment", "Model 1", 0.5))
        with self.assertRaisesRegex(ValueError, "duplicate cell"):
            table_emit.build_table(_table_spec(), rows, fmt="md")
        with self.assertRaisesRegex(ValueError, "FORMAT.INVALID"):
            table_emit.build_table(_table_spec(), _rows(), fmt="docx")

    def test_cli_writes_projection_and_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            spec_path = base / "spec.json"
            data_path = base / "data.csv"
            out_path = base / "table.md"
            spec_path.write_text(json.dumps(_table_spec()), encoding="utf-8")
            _write_csv(data_path, _rows())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = exhibit_cli.main(
                    ["table", "--spec", str(spec_path), "--data", str(data_path), "--out", str(out_path)]
                )
            self.assertEqual(0, code)
            report = json.loads(output.getvalue())
            self.assertEqual("TAB-MAIN-001", report["exhibit_id"])
            self.assertEqual(4, report["rows"])
            self.assertTrue(out_path.is_file())
            self.assertIn("| Observations | 100 | 98 |", out_path.read_text(encoding="utf-8"))
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = exhibit_cli.main(
                    ["table", "--spec", str(spec_path), "--data", str(data_path), "--out", str(out_path)]
                )
            self.assertEqual(3, code)
            self.assertIn("OUTPUT_EXISTS", error.getvalue())

    def test_rows_must_belong_to_the_spec(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            data_path = base / "data.csv"
            rows = _rows()
            rows[1]["exhibit_id"] = "TAB-OTHER-001"
            _write_csv(data_path, rows)
            with self.assertRaisesRegex(ValueError, "does not belong"):
                table_emit.load_rows(data_path, _table_spec())


if __name__ == "__main__":
    unittest.main(verbosity=2)
