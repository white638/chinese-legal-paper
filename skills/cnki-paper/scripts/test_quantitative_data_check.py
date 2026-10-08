from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from optional.quantitative_data import quantitative_data_check as check


class QuantitativeDataCheckTests(unittest.TestCase):
    def test_obtained_sample_returns_compact_card_without_path_or_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.csv"
            sample.write_text("id,outcome\n1,3\n2,4\n", encoding="utf-8")

            card = check.build_data_feasibility_card(
                sample,
                source_name="Survey sample",
                access_route="public_download",
                official_or_user_source="official",
                required_variables=("id", "outcome"),
                unit_of_analysis="respondent",
                row_limit=10,
                header_confirmed=True,
            )

            feasibility = card["data_feasibility"]
            self.assertEqual("sample_verified", feasibility["status"])
            self.assertEqual("public_download", feasibility["candidate_sources"][0]["access_route"])
            self.assertRegex(feasibility["candidate_sources"][0]["file_sha256"], r"^[a-f0-9]{64}$")
            rendered = str(card)
            self.assertNotIn(str(sample), rendered)
            self.assertNotIn("1,3", rendered)
            self.assertNotEqual("ready", feasibility["status"])

    def test_missing_required_variable_stays_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.csv"
            sample.write_text("id,outcome\n1,3\n", encoding="utf-8")

            card = check.build_data_feasibility_card(
                sample,
                source_name="Survey sample",
                required_variables=("id", "treatment"),
                header_confirmed=True,
            )

            feasibility = card["data_feasibility"]
            self.assertEqual("unverified", feasibility["status"])
            self.assertIn("treatment", " ".join(feasibility["main_risks"]))

    def test_no_declared_requirements_only_verifies_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.csv"
            sample.write_text("id,outcome\n1,3\n", encoding="utf-8")

            card = check.build_data_feasibility_card(
                sample,
                source_name="Survey sample",
                header_confirmed=True,
            )

            self.assertEqual("metadata_verified", card["data_feasibility"]["status"])

    def test_unknown_access_route_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.csv"
            sample.write_text("id\n1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                check.build_data_feasibility_card(
                    sample,
                    source_name="Survey sample",
                    access_route="catalog",
                    header_confirmed=True,
                )

    def test_documented_direct_script_entrypoint_works(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sample = Path(temporary) / "sample.csv"
            sample.write_text("id,outcome\n1,3\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(check.__file__).resolve()),
                    str(sample),
                    "--source-name",
                    "Survey sample",
                    "--required-variable",
                    "id",
                    "--header-confirmed",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )

            self.assertEqual(0, result.returncode, result.stderr)
            card = json.loads(result.stdout)
            self.assertEqual("sample_verified", card["data_feasibility"]["status"])


if __name__ == "__main__":
    unittest.main()
