#!/usr/bin/env python3
"""Adversarial tests for the optional, privacy-preserving data check adapters."""

from __future__ import annotations

import importlib.util
import json
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from optional.quantitative_data import probe_adapters
from optional.quantitative_data.probe_adapters import profile_path
from optional.quantitative_data.probe_adapters import archive as archive_adapter
from optional.quantitative_data.probe_adapters import tabular as tabular_adapter


def error_codes(profile: dict) -> set[str]:
    return {str(row.get("code")) for row in profile.get("errors") or []}


class FilesystemAndTabularAdapterTests(unittest.TestCase):
    def test_missing_path_and_directory_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            missing = profile_path(base / "missing.csv")
            directory = profile_path(base)
            self.assertEqual("BLOCKED", missing["parse_status"])
            self.assertEqual("BLOCKED", directory["parse_status"])
            self.assertIn("FILE_NOT_FOUND", error_codes(missing))
            self.assertIn("NOT_A_REGULAR_FILE", error_codes(directory))

    def test_csv_is_row_bounded_and_does_not_emit_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            sentinel = "PRIVATE-VALUE-MUST-NOT-LEAK"
            path.write_text(
                "id,weight,note\n1,1.5," + sentinel + "\n1,2.5,second\n3,3.5,third\n",
                encoding="utf-8",
            )
            profile = profile_path(
                path,
                row_limit=2,
                key_fields=("id",),
                survey=True,
                header_confirmed=True,
            )
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual(2, profile["observed_rows"])
            self.assertEqual(2, profile["key_diagnostics"]["duplicate_key_rows"])
            self.assertIn("weight", profile["survey_design"]["weight_fields"])
            self.assertFalse(profile["raw_rows_embedded"])
            self.assertNotIn(sentinel, json.dumps(profile, ensure_ascii=False))

    def test_row_limit_is_clamped_by_registry_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.csv"
            path.write_text("id\n1\n2\n3\n", encoding="utf-8")
            with patch.object(probe_adapters, "MAX_BOUNDED_ROWS", 2):
                profile = profile_path(
                    path,
                    row_limit=1_000_000,
                    header_confirmed=True,
                )
            self.assertEqual(2, profile["observed_rows"])
            self.assertEqual(2, profile["effective_row_limit"])
            self.assertTrue(any("ROW_LIMIT_CLAMPED" in row for row in profile["warnings"]))

    def test_json_is_byte_capped_before_decode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "large.json"
            path.write_bytes(b"[" + b" " * 64 + b"]")
            with patch.object(tabular_adapter, "MAX_JSON_PARSE_BYTES", 16):
                profile = profile_path(path, row_limit=2)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("RESOURCE_LIMIT_EXCEEDED", error_codes(profile))
            self.assertEqual(0, profile["observed_rows"])

    def test_deep_json_is_blocked_without_a_recursion_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep.json"
            path.write_text("[" * 1100 + "0" + "]" * 1100, encoding="utf-8")
            with patch.object(tabular_adapter.json, "loads", side_effect=RecursionError):
                profile = profile_path(path, row_limit=1)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("RESOURCE_LIMIT_EXCEEDED", error_codes(profile))

    def test_csv_byte_cap_returns_only_fixed_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            marker = "PRIVATE-CSV-TAIL-MUST-NOT-LEAK"
            path = Path(tmp) / "bounded.csv"
            path.write_text("id,note\n1," + marker + "\n", encoding="utf-8")
            with patch.object(tabular_adapter, "MAX_CSV_SAMPLE_BYTES", 12):
                profile = profile_path(path, row_limit=10, header_confirmed=True)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("RESOURCE_LIMIT_EXCEEDED", error_codes(profile))
            self.assertNotIn(marker, json.dumps(profile, ensure_ascii=False))

    def test_ultra_wide_csv_is_rejected_before_stdlib_row_allocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "wide.csv"
            path.write_text(",".join(f"field{index}" for index in range(20)) + "\n", encoding="utf-8")
            with (
                patch.object(tabular_adapter, "MAX_PROFILE_COLUMNS", 5),
                patch.object(
                    tabular_adapter.csv,
                    "reader",
                    side_effect=AssertionError("CSV parser ran before width gate"),
                ),
            ):
                profile = profile_path(path, row_limit=1, header_confirmed=True)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("RESOURCE_LIMIT_EXCEEDED", error_codes(profile))
            self.assertEqual([], profile["variables"])

    def test_bare_midfield_quote_cannot_hide_delimiters_from_width_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quote-bypass.csv"
            path.write_text('a"x,b,c,d\n', encoding="utf-8")
            with (
                patch.object(tabular_adapter, "MAX_PROFILE_COLUMNS", 2),
                patch.object(
                    tabular_adapter.csv,
                    "reader",
                    side_effect=AssertionError("CSV parser ran after quote bypass"),
                ),
            ):
                profile = profile_path(path, row_limit=1, header_confirmed=True)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("RESOURCE_LIMIT_EXCEEDED", error_codes(profile))

    def test_small_json_is_bounded_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.json"
            sentinel = "PRIVATE-JSON-VALUE"
            path.write_text(
                json.dumps([{"id": 1, "note": sentinel}, {"id": 2, "note": "x"}]),
                encoding="utf-8",
            )
            profile = profile_path(path, row_limit=1, key_fields=("id",))
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual(1, profile["observed_rows"])
            self.assertTrue(profile["key_diagnostics"]["unique_in_bounded_sample"])
            self.assertNotIn(sentinel, json.dumps(profile, ensure_ascii=False))

    def test_json_dictionary_mode_indexes_keys_without_exposing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = "private-free-text-value"
            path = Path(tmp) / "dictionary.json"
            path.write_text(
                json.dumps([{"id": 1, "income": 10, "note": sentinel}]),
                encoding="utf-8",
            )
            profile = profile_path(path, row_limit=0)
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual("dictionary-metadata", profile["profile_scope"])
            self.assertEqual({"id", "income", "note"}, {item["name"] for item in profile["variables"]})
            self.assertEqual(0, profile["observed_rows"])
            self.assertNotIn(sentinel, json.dumps(profile, ensure_ascii=False))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "openpyxl is unavailable")
    def test_xlsx_uses_read_only_bounded_rows(self) -> None:
        from openpyxl import Workbook

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.xlsx"
            workbook = Workbook(write_only=False)
            sheet = workbook.active
            sheet.append(["id", "value"])
            for index in range(20):
                sheet.append([index, f"value-{index}"])
            workbook.save(path)
            workbook.close()

            profile = profile_path(
                path,
                row_limit=3,
                key_fields=("id",),
                header_confirmed=True,
            )
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual("openpyxl-read-only", profile["parser_backend"])
            self.assertEqual(3, profile["observed_rows"])
            self.assertEqual(20, profile["file_row_count"])
            self.assertTrue(profile["capabilities"]["bounded_row_read"])

    def test_header_dependent_formats_fail_closed_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first_row_values = ("ALICE", "123-45-6789")
            for suffix in (".csv", ".tsv", ".xlsx", ".xlsm"):
                with self.subTest(suffix=suffix):
                    path = base / f"headerless{suffix}"
                    separator = "\t" if suffix == ".tsv" else ","
                    path.write_text(separator.join(first_row_values) + "\n", encoding="utf-8")
                    profile = profile_path(path, row_limit=5, key_fields=("id",))
                    serialized = json.dumps(profile, ensure_ascii=False)
                    self.assertEqual("BLOCKED", profile["parse_status"])
                    self.assertIn("HEADER_CONFIRMATION_REQUIRED", error_codes(profile))
                    self.assertEqual([], profile["variables"])
                    self.assertEqual([], profile["key_diagnostics"]["observed_fields"])
                    self.assertEqual(0, profile["observed_rows"])
                    for value in first_row_values:
                        self.assertNotIn(value, serialized)

    def test_sav_and_sas_are_explicitly_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("sample.sav", "sample.sas7bdat", "sample.xpt"):
                path = base / name
                path.write_bytes(b"not parsed")
                profile = profile_path(path)
                self.assertEqual("BLOCKED", profile["parse_status"], name)
                self.assertIn("UNSUPPORTED_FORMAT", error_codes(profile), name)
                self.assertFalse(profile["capabilities"]["full_file_fallback_allowed"])

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas is unavailable")
    def test_dta_dictionary_mode_does_not_call_row_reader(self) -> None:
        import pandas as pd
        from pandas.io.stata import StataReader

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.dta"
            pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}).to_stata(
                path,
                write_index=False,
            )
            def forbidden_read(self, nrows=None, **kwargs):
                raise AssertionError("row reader called")

            with (
                patch.object(StataReader, "read", forbidden_read),
                patch.object(
                    StataReader,
                    "value_labels",
                    side_effect=AssertionError("value-label tables were read"),
                ),
            ):
                profile = profile_path(path, row_limit=0, key_fields=("id",))
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual("dictionary-metadata", profile["profile_scope"])
            self.assertEqual(0, profile["observed_rows"])
            self.assertTrue(profile["capabilities"]["bounded_row_read"])

    @unittest.skipUnless(importlib.util.find_spec("pandas"), "pandas is unavailable")
    def test_dta_row_probe_passes_explicit_nrows_bound(self) -> None:
        import pandas as pd
        from pandas.io.stata import StataReader

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.dta"
            pd.DataFrame({"id": [1, 2, 3], "value": [10, 20, 30]}).to_stata(
                path,
                write_index=False,
            )
            original = StataReader.read
            observed_nrows: list[int | None] = []

            def bounded_read(self, nrows=None, **kwargs):
                observed_nrows.append(nrows)
                return original(self, nrows=nrows, **kwargs)

            with patch.object(StataReader, "read", bounded_read):
                profile = profile_path(path, row_limit=1, key_fields=("id",))
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual(1, profile["observed_rows"])
            self.assertEqual([1], observed_nrows)


class ZipManifestSecurityTests(unittest.TestCase):
    def make_zip(self, base: Path, members: list[tuple[str, bytes]], *, deflated: bool = False) -> Path:
        path = base / "sample.zip"
        compression = zipfile.ZIP_DEFLATED if deflated else zipfile.ZIP_STORED
        with zipfile.ZipFile(path, "w", compression=compression) as archive:
            for name, payload in members:
                archive.writestr(name, payload)
        return path

    def test_zip_manifest_is_read_without_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = self.make_zip(base, [("folder/data.csv", b"id\n1\n")])
            before = sorted(item.name for item in base.iterdir())
            profile = profile_path(path)
            after = sorted(item.name for item in base.iterdir())
            self.assertEqual("PASS", profile["parse_status"])
            self.assertEqual(before, after)
            self.assertFalse(profile["archive_extracted"])
            self.assertFalse(profile["archive_policy"]["member_streams_opened"])
            self.assertEqual("folder/data.csv", profile["archive_manifest"][0]["path"])

    def test_zip_path_traversal_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(Path(tmp), [("../escape.csv", b"x")])
            profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_PATH_TRAVERSAL", error_codes(profile))

    def test_nested_archive_is_listed_but_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(Path(tmp), [("inner.zip", b"not opened")])
            profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("NESTED_ARCHIVE_UNSUPPORTED", error_codes(profile))
            self.assertTrue(profile["archive_manifest"][0]["nested_archive"])

    def test_member_count_limit_truncates_receipt_and_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(Path(tmp), [(f"{index}.txt", b"x") for index in range(3)])
            with patch.object(archive_adapter, "MAX_ARCHIVE_MEMBERS", 2):
                profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_MEMBER_LIMIT_EXCEEDED", error_codes(profile))
            self.assertTrue(profile["archive_manifest_truncated"])
            self.assertEqual([], profile["archive_manifest"])

    def test_member_count_preflight_runs_before_zipfile_allocation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(
                Path(tmp), [(f"{index}.txt", b"x") for index in range(3)]
            )
            with (
                patch.object(archive_adapter, "MAX_ARCHIVE_MEMBERS", 2),
                patch.object(
                    archive_adapter.zipfile,
                    "ZipFile",
                    side_effect=AssertionError("ZipFile opened before member-count gate"),
                ),
            ):
                profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_MEMBER_LIMIT_EXCEEDED", error_codes(profile))

    def test_falsified_eocd_member_count_cannot_bypass_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(
                Path(tmp), [(f"{index}.txt", b"x") for index in range(4)]
            )
            raw = bytearray(path.read_bytes())
            eocd = raw.rfind(b"PK\x05\x06")
            self.assertGreaterEqual(eocd, 0)
            struct.pack_into("<H", raw, eocd + 8, 1)
            struct.pack_into("<H", raw, eocd + 10, 1)
            path.write_bytes(raw)
            with (
                patch.object(archive_adapter, "MAX_ARCHIVE_MEMBERS", 2),
                patch.object(
                    archive_adapter.zipfile,
                    "ZipFile",
                    side_effect=AssertionError("ZipFile opened before verified count gate"),
                ),
            ):
                profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_MEMBER_LIMIT_EXCEEDED", error_codes(profile))

    def test_total_uncompressed_limit_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(Path(tmp), [("large.txt", b"1234567890")])
            with patch.object(archive_adapter, "MAX_TOTAL_UNCOMPRESSED_BYTES", 5):
                profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_TOTAL_SIZE_LIMIT_EXCEEDED", error_codes(profile))

    def test_compression_ratio_limit_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self.make_zip(Path(tmp), [("zeros.bin", b"0" * 10_000)], deflated=True)
            with patch.object(archive_adapter, "MAX_COMPRESSION_RATIO", 2.0):
                profile = profile_path(path)
            self.assertEqual("BLOCKED", profile["parse_status"])
            self.assertIn("ARCHIVE_COMPRESSION_RATIO_EXCEEDED", error_codes(profile))

    def test_rar_and_7z_do_not_use_machine_specific_tools(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ("sample.rar", "sample.7z"):
                path = base / name
                path.write_bytes(b"not parsed")
                profile = profile_path(path)
                self.assertEqual("BLOCKED", profile["parse_status"], name)
                self.assertIn("UNSUPPORTED_FORMAT", error_codes(profile), name)
                self.assertEqual("none", profile["parser_backend"])


if __name__ == "__main__":
    unittest.main()
