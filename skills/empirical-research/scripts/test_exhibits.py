#!/usr/bin/env python3
"""Contract and integration tests for the optional empirical-exhibit layer."""

from __future__ import annotations

import copy
import contextlib
import csv
import hashlib
import importlib.util
import io
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

import method_execution
import test_method_execution_v3 as execution_fixtures
from exhibits import contract, exhibit as exhibit_cli, figure_map
from exhibits.render_bundle import render


HERE = Path(__file__).resolve().parent
REFERENCES = HERE.parent / "references" / "exhibits"
TEST_R_PACKAGES = {
    "jsonlite": "test",
    "ggplot2": "test",
    "svglite": "test",
    "ragg": "test",
    "systemfonts": "test",
}


def _load_build_exhibit_map():
    path = (
        HERE.parents[1]
        / "cnki-paper"
        / "scripts"
        / "avereth_core"
        / "build"
        / "exhibit_map.py"
    )
    spec = importlib.util.spec_from_file_location("build_exhibit_map_tests", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_exhibit_map = _load_build_exhibit_map()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, content: bytes) -> dict[str, str]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": path.as_posix(), "sha256": _sha256(path)}


def _asset_hash(relative: str) -> str:
    return _sha256(REFERENCES / relative)


def _minimal_pdf() -> bytes:
    header = b"%PDF-1.4\n"
    body = b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
    xref_offset = len(header) + len(body)
    xref = (
        b"xref\n0 2\n0000000000 65535 f \n"
        + f"{len(header):010d} 00000 n \n".encode("ascii")
    )
    trailer = (
        b"trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return header + body + xref + trailer


def _png_chunk(name: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + name
        + payload
        + struct.pack(">I", zlib.crc32(name + payload) & 0xFFFFFFFF)
    )


def _minimal_png() -> bytes:
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    scanline = zlib.compress(b"\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", scanline) + _png_chunk(b"IEND", b"")


def _spec(kind: str = "event_study") -> dict:
    recipe_names = {
        "coefficient_forest": "coefficient-forest.json",
        "event_study": "event-study.json",
        "marginal_effects": "marginal-effects.json",
        "predicted_probability": "predicted-probability.json",
        "trend_or_binscatter": "trend-or-binscatter.json",
        "regression_or_balance_table": "regression-or-balance-table.json",
    }
    payload = {
        "schema_version": contract.SPEC_SCHEMA_VERSION,
        "exhibit_id": "FIG-EVENT-001",
        "kind": kind,
        "placement": "main",
        "argument_role": "estimation",
        "source_result_ids": ["RES-001"],
        "quantity": "registered contrast",
        "unit": "percentage points",
        "confidence_levels": [0.95],
        "sample_n": 100,
        "style_profile": "international-polisci-econ",
        "style_profile_sha256": _asset_hash(
            "style-profiles/international-polisci-econ.json"
        ),
        "recipe_sha256": _asset_hash(f"recipes/{recipe_names[kind]}"),
        "formats": ["pdf", "svg", "png"],
        "caption_requirements": [
            "estimand",
            "uncertainty",
            "sample",
            "source result",
        ],
    }
    if kind == "event_study":
        payload.update(
            {
                "reference_value": 0,
                "reference_period": -1,
                "treatment_boundary": 0,
            }
        )
    if kind == "coefficient_forest":
        payload["reference_value"] = 0
    if kind in {"marginal_effects", "predicted_probability"}:
        payload["response_scale"] = (
            "probability" if kind == "predicted_probability" else "response"
        )
        payload["x_scale"] = (
            "ordered_category" if kind == "predicted_probability" else "continuous"
        )
    if kind == "trend_or_binscatter":
        payload["x_scale"] = "continuous"
    return payload


def _row(*, reference: bool = False) -> dict:
    row = {
        "schema_version": contract.DATA_SCHEMA_VERSION,
        "exhibit_id": "FIG-EVENT-001",
        "kind": "event_study",
        "quantity": "registered contrast",
        "term": "reference" if reference else "period zero",
        "x": -1 if reference else 0,
        "estimate": 0 if reference else 0.12,
        "std_error": "" if reference else 0.03,
        "conf_low": "" if reference else 0.0612,
        "conf_high": "" if reference else 0.1788,
        "confidence_level": 0.95,
        "model_label": "registered model",
        "group_label": "all units",
        "panel_label": "main",
        "is_reference": reference,
        "sample_n": 100,
        "estimand": "dynamic registered contrast",
        "unit": "percentage points",
        "vcov_type": "cluster robust",
        "cluster_level": "unit",
        "source_result_id": "RES-001",
        "source_numeric_locator": "" if reference else "json:/estimate",
        "std_error_locator": "" if reference else "json:/std_error",
        "conf_low_locator": "" if reference else "json:/conf_low",
        "conf_high_locator": "" if reference else "json:/conf_high",
        "sample_n_locator": "json:/sample_n",
        "line_type": "solid",
        "marker": "16",
        "color": "#111111",
    }
    return row


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def exhibit_workspace():
    temporary, base, design, payload = execution_fixtures.v3_workspace(
        include_full=True
    )
    run = payload["runs"][0]
    source_action = run["actions"][0]
    source_result = run["results"][0]
    evidence_id = source_result["evidence_ids"][0]

    numeric_path = base / "artifacts" / "registered-estimates.json"
    numeric_payload = {
        "estimate": 0.12,
        "std_error": 0.03,
        "conf_low": 0.0612,
        "conf_high": 0.1788,
        "sample_n": 100,
    }
    numeric_path.write_text(
        json.dumps(numeric_payload, sort_keys=True) + "\n", encoding="utf-8"
    )
    run["artifacts"].append(
        {
            "id": "ART-NUM-001",
            "path": numeric_path.relative_to(base).as_posix(),
            "sha256": _sha256(numeric_path),
            "role": "registered_numeric_result",
        }
    )
    source_action["output_artifact_ids"].append("ART-NUM-001")
    source_result["artifact_ids"].append("ART-NUM-001")
    exhibit_semantics = {
        "quantity": "registered contrast",
        "unit": "percentage points",
        "estimand": "dynamic registered contrast",
        "confidence_level": 0.95,
        "vcov_type": "cluster robust",
        "cluster_level": "unit",
    }
    source_result["numeric_values"] = [
        {
            "value": value,
            "locator": f"json:/{field}",
            "reproduction_command": "rerun the frozen registered model",
            "evidence_id": evidence_id,
            "artifact_id": "ART-NUM-001",
            "exhibit_semantics": copy.deepcopy(exhibit_semantics),
        }
        for field, value in numeric_payload.items()
    ]

    output_defs = [
        ("ART-EXH-DATA", "artifacts/fig-event-001/data.csv", "plot_data"),
        ("ART-EXH-PDF", "artifacts/fig-event-001/exhibit.pdf", "main_figure"),
        ("ART-EXH-SVG", "artifacts/fig-event-001/exhibit.svg", "main_figure"),
        ("ART-EXH-PNG", "artifacts/fig-event-001/exhibit.png", "figure_preview"),
        ("ART-EXH-LOG", "artifacts/fig-event-001/render_log.json", "render_log"),
    ]
    first_step = design["execution_blueprint"]["steps"][0]
    step = {
        "id": "STEP-EXHIBIT-001",
        "design_id": first_step["design_id"],
        "claim_ids": copy.deepcopy(first_step["claim_ids"]),
        "operationalization_ids": copy.deepcopy(
            first_step["operationalization_ids"]
        ),
        "material_ids": ["MAT-001"],
        "evidence_ids": copy.deepcopy(first_step["evidence_ids"]),
        "run_kind": "full",
        "goal": "Render a hash-bound event-study exhibit from the accepted result.",
        "read_set": [
            "research_design.json",
            "artifacts/registered-estimates.json",
        ],
        "write_set": [item[1] for item in output_defs],
        "procedure": {
            "adapter": "empirical-exhibits/v1",
            "operation": "exhibit_rendering",
            "parameters_ref": "Action.parameter_snapshot.content.exhibit_spec",
        },
        "researcher_risk": copy.deepcopy(first_step["researcher_risk"]),
        "expected_artifacts": [
            {"id": identifier, "path": path, "role": role}
            for identifier, path, role in output_defs
        ],
        "acceptance_checks": [
            {
                "id": "CHECK-EXHIBIT-001",
                "rule": "Every output is hash-bound to source Result values and the frozen ExhibitSpec.",
            }
        ],
        "on_failure": [
            {
                "code": "EXHIBIT.PROVENANCE.HASH_MISMATCH",
                "route": "replace-implementation",
            }
        ],
        "result_disposition": {
            "support": "Retain the exhibit as a projection of the source Result.",
            "contradict": "Replace the exhibit implementation.",
            "inconclusive": "Route the exhibit for human review.",
        },
        "preconditions": [
            {"step_id": item["id"], "required_status": "accepted"}
            for item in design["execution_blueprint"]["steps"]
            if item["run_kind"] == "mvmr"
        ],
    }
    design["execution_blueprint"]["steps"].append(step)
    design_digest = method_execution._canonical_digest(design)
    payload["design_sha256"] = design_digest
    for action in run["actions"]:
        action["started_from_design_sha256"] = design_digest

    spec = _spec()
    spec_digest = contract.canonical_digest(spec)
    backend_path = HERE / "exhibits" / "backends" / "r" / "render_exhibit.R"
    environment_snapshot = {
        "schema_version": contract.RENDER_ENV_SCHEMA_VERSION,
        "renderer": "r/generic-ggplot2-v1",
        "R": "R test fixture",
        "packages": copy.deepcopy(TEST_R_PACKAGES),
        "requested_fonts": {"base": "Liberation Serif"},
        "resolved_fonts": {"base": "Liberation Serif"},
        "backend_sha256": _sha256(backend_path),
        "style_profile_sha256": spec["style_profile_sha256"],
        "recipe_sha256": spec["recipe_sha256"],
    }
    data_path = base / output_defs[0][1]
    rows = [_row(reference=True), _row(reference=False)]
    _write_csv(data_path, rows)
    visual_contents = {
        "ART-EXH-PDF": _minimal_pdf(),
        "ART-EXH-SVG": b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>\n',
        "ART-EXH-PNG": _minimal_png(),
    }
    log_payload = {
        "schema_version": contract.RENDER_LOG_SCHEMA_VERSION,
        "exhibit_id": "FIG-EVENT-001",
        "renderer": "r/generic-ggplot2-v1",
        "R": "R test fixture",
        "packages": copy.deepcopy(TEST_R_PACKAGES),
        "requested_fonts": {"base": "Liberation Serif"},
        "resolved_fonts": {"base": "Liberation Serif"},
        "software_environment_id": "ENV-EXHIBIT-001",
        "software_environment": environment_snapshot,
        "software_environment_sha256": contract.canonical_digest(environment_snapshot),
        "inputs": {
            "spec_sha256": spec_digest,
            "data_sha256": _sha256(data_path),
            "style_sha256": spec["style_profile_sha256"],
            "recipe_sha256": spec["recipe_sha256"],
            "backend_sha256": _sha256(backend_path),
        },
        "outputs": [
            {
                "format": Path(relative).suffix.lstrip("."),
                "sha256": hashlib.sha256(visual_contents[identifier]).hexdigest(),
            }
            for identifier, relative, role in output_defs
            if role in contract.VISUAL_ROLES
        ],
        "render_checks": {
            "font_min_pt": 9,
            "requested_fonts_available": True,
            "font_fallback_used": False,
            "glyph_fallback_checked": False,
            "dpi": 320,
        },
    }
    contents = {
        **visual_contents,
        "ART-EXH-LOG": json.dumps(log_payload, sort_keys=True).encode("utf-8") + b"\n",
    }
    for _identifier, relative, _role in output_defs[1:]:
        _write(base / relative, contents[_identifier])

    for identifier, relative, role in output_defs:
        local = base / relative
        artifact = {
            "id": identifier,
            "path": relative,
            "sha256": _sha256(local),
            "role": role,
            "exhibit_id": spec["exhibit_id"],
            "kind": spec["kind"],
            "source_result_ids": ["RES-001"],
            "source_action_ids": [source_action["id"]],
            "renderer": "r/generic-ggplot2-v1",
            "native_adapter": "generic-normalized-data",
            "style_profile": spec["style_profile"],
            "spec_sha256": spec_digest,
            "format": Path(relative).suffix.lstrip("."),
            "placement": spec["placement"],
            "argument_role": spec["argument_role"],
        }
        if role in contract.VISUAL_ROLES:
            artifact["plot_data_artifact_id"] = "ART-EXH-DATA"
            artifact["render_checks"] = {
                "font_min_pt": 9,
                "requested_fonts_available": True,
                "font_fallback_used": False,
                "glyph_fallback_checked": False,
                "dpi": 320,
            }
        run["artifacts"].append(artifact)

    payload["software_environments"].append(
        {
            "id": "ENV-EXHIBIT-001",
            "runtime": "R test fixture",
            "versions": "Captured in exhibit_renderer",
            "lock_or_capture": "render_log software_environment_sha256",
            "reproduction_command": "Rscript render_exhibit.R",
            "exhibit_renderer": environment_snapshot,
        }
    )
    run["software_environment_ids"].append("ENV-EXHIBIT-001")

    snapshot = {
        "format": method_execution.PARAMETER_SNAPSHOT_FORMAT,
        "kind": "configuration",
        "content": {
            "operation": "exhibit_rendering",
            "procedure": copy.deepcopy(step["procedure"]),
            "exhibit_spec": spec,
        },
    }
    render_action = {
        "id": "ACT-EXHIBIT-001",
        "operation_id": step["id"],
        "attempt": 1,
        "run_kind": "full",
        "status": "accepted",
        "started_from_design_sha256": design_digest,
        "parameter_snapshot": snapshot,
        "parameter_snapshot_sha256": method_execution._canonical_digest(snapshot),
        "input_artifact_ids": ["ART-NUM-001"],
        "output_artifact_ids": [item[0] for item in output_defs],
        "software_environment_id": "ENV-EXHIBIT-001",
        "check_results": [
            {
                "id": "CHK-EXHIBIT-001",
                "rule": step["acceptance_checks"][0]["rule"],
                "status": "pass",
                "diagnostic": "Formats, hashes, numeric locators, semantics, and style metadata passed.",
                "artifact_ids": [item[0] for item in output_defs],
            }
        ],
        "failure_code": "",
        "disposition_route": "continue",
        "deviation_id": "",
        "result_ids": [],
    }
    run["actions"].append(render_action)
    (base / "research_design.json").write_text(
        json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return temporary, base, design, payload


class ExhibitContractTests(unittest.TestCase):
    def test_six_recipes_have_valid_hash_bound_specs(self) -> None:
        for kind in sorted(contract.EXHIBIT_KINDS):
            with self.subTest(kind=kind):
                spec = _spec(kind)
                self.assertEqual([], contract.validate_spec(spec))
                self.assertEqual([], contract.validate_spec_assets(spec))

    def test_valid_exhibit_integrates_without_changing_result_authority(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            source_result = copy.deepcopy(payload["runs"][0]["results"][0])
            validation = method_execution.validate_payload(base, payload)
            self.assertEqual(
                [],
                validation.errors,
                [(item.code, item.path) for item in validation.errors],
            )
            self.assertEqual(source_result, payload["runs"][0]["results"][0])
            self.assertEqual([], payload["runs"][0]["actions"][-1]["result_ids"])

    def test_numeric_drift_is_blocked(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            data_path = base / "artifacts/fig-event-001/data.csv"
            rows = [_row(reference=True), _row(reference=False)]
            rows[1]["estimate"] = 0.9
            _write_csv(data_path, rows)
            data_artifact = next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-DATA"
            )
            data_artifact["sha256"] = _sha256(data_path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.NUMERIC.DRIFT", codes)

    def test_render_log_invalidates_visuals_when_companion_data_changes(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            data_path = base / "artifacts/fig-event-001/data.csv"
            with data_path.open("a", encoding="utf-8") as handle:
                handle.write("\n")
            next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-DATA"
            )["sha256"] = _sha256(data_path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.RENDER_LOG_INVALID", codes)

    def test_render_log_binds_each_visual_output_sha(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            visual_path = base / "artifacts/fig-event-001/exhibit.svg"
            visual_path.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>\n',
                encoding="utf-8",
            )
            next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-SVG"
            )["sha256"] = _sha256(visual_path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.RENDER_LOG_INVALID", codes)

    def test_negative_standard_error_is_blocked_even_when_source_matches(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            data_path = base / "artifacts/fig-event-001/data.csv"
            rows = [_row(reference=True), _row(reference=False)]
            rows[1]["std_error"] = -0.03
            _write_csv(data_path, rows)
            data_artifact = next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-DATA"
            )
            data_artifact["sha256"] = _sha256(data_path)
            numeric = next(
                item
                for item in payload["runs"][0]["results"][0]["numeric_values"]
                if item["locator"] == "json:/std_error"
            )
            numeric["value"] = -0.03
            numeric_path = base / "artifacts/registered-estimates.json"
            numeric_payload = json.loads(numeric_path.read_text(encoding="utf-8"))
            numeric_payload["std_error"] = -0.03
            numeric_path.write_text(json.dumps(numeric_payload, sort_keys=True) + "\n", encoding="utf-8")
            numeric_artifact = next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-NUM-001"
            )
            numeric_artifact["sha256"] = _sha256(numeric_path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.NUMERIC.CI_MISMATCH", codes)

    def test_source_artifact_must_be_consumed(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            payload["runs"][0]["actions"][-1]["input_artifact_ids"] = []
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", codes)

    def test_unrelated_source_artifact_cannot_satisfy_numeric_lineage(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            payload["runs"][0]["actions"][-1]["input_artifact_ids"] = ["ART-001"]
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", codes)

    def test_style_hash_and_design_output_drift_are_blocked(self) -> None:
        temporary, base, design, payload = exhibit_workspace()
        with temporary:
            render_action = payload["runs"][0]["actions"][-1]
            spec = render_action["parameter_snapshot"]["content"]["exhibit_spec"]
            spec["style_profile_sha256"] = "0" * 64
            render_action["parameter_snapshot_sha256"] = method_execution._canonical_digest(
                render_action["parameter_snapshot"]
            )
            render_action["output_artifact_ids"].pop()
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.HASH_MISMATCH", codes)
            self.assertIn("EXHIBIT.PROVENANCE.OUTPUT_DRIFT", codes)

    def test_exhibit_step_cannot_bypass_contract_with_missing_or_future_spec(self) -> None:
        for replacement, expected_code in (
            (None, "EXHIBIT.SPEC.FIELD_MISSING"),
            ({**_spec(), "schema_version": "avereth-exhibit-spec/v99"}, "EXHIBIT.SPEC.SCHEMA_INVALID"),
        ):
            with self.subTest(expected_code=expected_code):
                temporary, base, _design, payload = exhibit_workspace()
                with temporary:
                    action = payload["runs"][0]["actions"][-1]
                    action["parameter_snapshot"]["content"]["exhibit_spec"] = replacement
                    action["parameter_snapshot_sha256"] = method_execution._canonical_digest(
                        action["parameter_snapshot"]
                    )
                    codes = {
                        item.code
                        for item in method_execution.validate_payload(base, payload).errors
                    }
                    self.assertIn(expected_code, codes)

    def test_render_action_cannot_create_a_scientific_result(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            payload["runs"][0]["actions"][-1]["result_ids"] = ["RES-001"]
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.CONTRACT.RESULT_FORBIDDEN", codes)

    def test_exhibit_step_and_action_parameter_binding_cannot_drift(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            action = payload["runs"][0]["actions"][-1]
            action["parameter_snapshot"]["content"]["operation"] = "other_operation"
            action["parameter_snapshot_sha256"] = method_execution._canonical_digest(
                action["parameter_snapshot"]
            )
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.CONTRACT.PARAMETER_BINDING_INVALID", codes)

    def test_declared_visual_format_must_match_file_signature(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            path = base / "artifacts/fig-event-001/exhibit.pdf"
            path.write_bytes(b"not a pdf")
            artifact = next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-PDF"
            )
            artifact["sha256"] = _sha256(path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.FORMAT.INVALID", codes)

    def test_truncated_signature_only_files_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            fixtures = {
                "pdf": b"%PDF-1.7\n",
                "png": b"\x89PNG\r\n\x1a\nfixture",
                "svg": b"<svg",
            }
            for declared_format, content in fixtures.items():
                path = base / f"bad.{declared_format}"
                path.write_bytes(content)
                self.assertFalse(contract._valid_file_format(path, declared_format))

    def test_well_formed_non_svg_xml_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.svg"
            path.write_text("<notsvg/>", encoding="utf-8")
            self.assertFalse(contract._valid_file_format(path, "svg"))

    def test_png_without_image_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.png"
            ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            path.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + _png_chunk(b"IHDR", ihdr)
                + _png_chunk(b"IEND", b"")
            )
            self.assertFalse(contract._valid_file_format(path, "png"))

    def test_pdf_startxref_must_target_an_xref_structure(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "bad.pdf"
            path.write_bytes(
                b"%PDF-1.4\n1 0 obj\nbanana\nendobj\nstartxref\n9\n%%EOF\n"
            )
            self.assertFalse(contract._valid_file_format(path, "pdf"))

    def test_data_and_render_log_formats_must_match_their_files(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            artifacts = payload["runs"][0]["artifacts"]
            next(item for item in artifacts if item["id"] == "ART-EXH-DATA")["format"] = "pdf"
            next(item for item in artifacts if item["id"] == "ART-EXH-LOG")["format"] = "svg"
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.FORMAT.INVALID", codes)

    def test_visual_role_must_match_kind_placement_and_format(self) -> None:
        temporary, base, design, payload = exhibit_workspace()
        with temporary:
            artifact = next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-PDF"
            )
            artifact["role"] = "main_table"
            step = next(
                item
                for item in design["execution_blueprint"]["steps"]
                if item["id"] == "STEP-EXHIBIT-001"
            )
            next(
                item
                for item in step["expected_artifacts"]
                if item["id"] == "ART-EXH-PDF"
            )["role"] = "main_table"
            digest = method_execution._canonical_digest(design)
            payload["design_sha256"] = digest
            for action in payload["runs"][0]["actions"]:
                action["started_from_design_sha256"] = digest
            (base / "research_design.json").write_text(
                json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.FORMAT.ROLE_MISMATCH", codes)

    def test_figure_map_refresh_preserves_author_content(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            prefill = figure_map.render_prefill(payload, execution_sha256="a" * 64)
            existing = "# Figure Asset Map\n\nAuthor note.\n"
            first = figure_map.update_document(existing, prefill)
            second = figure_map.update_document(first, prefill)
            self.assertEqual(first, second)
            self.assertIn("Author note.", first)
            self.assertIn("FIG-EVENT-001", first)
            self.assertIn("Execution SHA-256: `" + "a" * 64 + "`", first)

    def test_figure_map_projects_only_latest_attempt_per_operation(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            run = payload["runs"][0]
            retry = copy.deepcopy(run["actions"][-1])
            retry.update({"id": "ACT-EXHIBIT-002", "attempt": 2})
            run["actions"].append(retry)
            rendered = figure_map.render_prefill(payload)
            self.assertEqual(1, rendered.count("| FIG-EVENT-001 |"))
            self.assertIn("ACT-EXHIBIT-002", rendered)
            self.assertNotIn("ACT-EXHIBIT-001", rendered)

            retry["status"] = "failed"
            blocked_projection = figure_map.render_prefill(payload)
            self.assertNotIn("FIG-EVENT-001", blocked_projection)

    def test_figure_map_rejects_malformed_markers_and_preserves_outside_bytes(self) -> None:
        prefill = figure_map.render_prefill({"runs": []})
        malformed = (
            figure_map.START_MARKER,
            figure_map.END_MARKER,
            figure_map.START_MARKER + figure_map.START_MARKER + figure_map.END_MARKER,
            figure_map.END_MARKER + figure_map.START_MARKER,
        )
        for existing in malformed:
            with self.subTest(existing=existing), self.assertRaisesRegex(
                ValueError, "MAP_MARKERS_INVALID"
            ):
                figure_map.update_document(existing, prefill)

        prefix = "# Figure Asset Map\r\n\r\nAuthor before.\r\n"
        suffix = "\r\nAuthor after.  \r\n"
        existing = (
            prefix
            + figure_map.START_MARKER
            + "\nold\n"
            + figure_map.END_MARKER
            + suffix
        )
        updated = figure_map.update_document(existing, prefill)
        self.assertTrue(updated.startswith(prefix))
        self.assertTrue(updated.endswith(suffix))

    def test_build_owned_map_refresh_validates_and_preserves_author_content(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            (base / "workflow_config.json").write_text(
                json.dumps({"workflow": "build_from_materials"}), encoding="utf-8"
            )
            (base / "method_execution.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            (base / "figure_asset_map.md").write_text(
                "# Figure Asset Map\n\nAuthor placement note.\n", encoding="utf-8"
            )
            rendered = build_exhibit_map.refresh(base, write=True)
            with (base / "figure_asset_map.md").open(
                "r", encoding="utf-8", newline=""
            ) as handle:
                persisted = handle.read()
            self.assertEqual(
                rendered,
                persisted,
            )
            self.assertIn("Author placement note.", rendered)
            self.assertIn("FIG-EVENT-001", rendered)

    def test_build_owned_map_refresh_preserves_author_crlf_bytes(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            (base / "workflow_config.json").write_text(
                json.dumps({"workflow": "build_from_materials"}), encoding="utf-8"
            )
            (base / "method_execution.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            prefix = b"# Figure Asset Map\r\n\r\nAuthor before.  \r\n"
            map_path = base / "figure_asset_map.md"
            map_path.write_bytes(prefix)
            build_exhibit_map.refresh(base, write=True)
            self.assertTrue(map_path.read_bytes().startswith(prefix))

    def test_missing_rscript_fails_before_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            spec_path = base / "spec.json"
            data_path = base / "data.csv"
            outdir = base / "out"
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            _write_csv(data_path, [_row(reference=True), _row(reference=False)])
            with self.assertRaisesRegex(RuntimeError, "R_UNAVAILABLE"):
                render(
                    spec_path,
                    data_path,
                    outdir,
                    "ENV-EXHIBIT-001",
                    str(base / "missing-Rscript"),
                )
            self.assertFalse(outdir.exists())

    def test_render_cli_binds_environment_id_before_invoking_r(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            spec_path = base / "spec.json"
            data_path = base / "data.csv"
            outdir = base / "out"
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            _write_csv(data_path, [_row(reference=True), _row(reference=False)])
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                code = exhibit_cli.main(
                    [
                        "render",
                        "--spec",
                        str(spec_path),
                        "--data",
                        str(data_path),
                        "--out",
                        str(outdir),
                        "--environment-id",
                        "ENV-EXHIBIT-001",
                        "--rscript",
                        str(base / "missing-Rscript"),
                    ]
                )
            self.assertEqual(3, code)
            self.assertIn("R_UNAVAILABLE", error.getvalue())

    def test_exhibit_cli_fails_when_canonical_artifact_hash_drifts(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            (base / "method_execution.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            data_path = base / "artifacts/fig-event-001/data.csv"
            with data_path.open("a", encoding="utf-8") as handle:
                handle.write("\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = exhibit_cli.main(["validate", str(base), "--json"])
            response = json.loads(output.getvalue())
            self.assertEqual(1, code)
            self.assertEqual("FAIL", response["status"])
            self.assertIn(
                "ME.ARTIFACT.HASH_CHANGED",
                {item["code"] for item in response["blocking_issues"]},
            )

    def test_schema_assets_keep_custom_validator_versions_in_sync(self) -> None:
        schema_dir = HERE.parent / "references" / "schemas"
        spec_schema = json.loads(
            (schema_dir / "avereth-exhibit-spec-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        data_schema = json.loads(
            (schema_dir / "avereth-exhibit-data-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        environment_schema = json.loads(
            (schema_dir / "avereth-exhibit-renderer-environment-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        render_log_schema = json.loads(
            (schema_dir / "avereth-exhibit-render-log-v1.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            contract.SPEC_SCHEMA_VERSION,
            spec_schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            contract.DATA_SCHEMA_VERSION,
            data_schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(contract.EXHIBIT_KINDS, set(spec_schema["properties"]["kind"]["enum"]))
        self.assertEqual(
            contract.RENDER_ENV_SCHEMA_VERSION,
            environment_schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            contract.RENDER_LOG_SCHEMA_VERSION,
            render_log_schema["properties"]["schema_version"]["const"],
        )

    def test_custom_spec_validator_rejects_schema_invalid_scalar_types(self) -> None:
        mutations = {
            "quantity": 123,
            "unit": 456,
            "confidence_levels": ["0.95"],
            "caption_requirements": [7],
        }
        for field, replacement in mutations.items():
            with self.subTest(field=field):
                spec = _spec()
                spec[field] = replacement
                self.assertTrue(contract.validate_spec(spec))

    def test_malformed_spec_returns_structured_errors_in_full_validation(self) -> None:
        for field, replacement in (("confidence_levels", 0.95), ("formats", 123)):
            with self.subTest(field=field):
                temporary, base, _design, payload = exhibit_workspace()
                with temporary:
                    action = payload["runs"][0]["actions"][-1]
                    action["parameter_snapshot"]["content"]["exhibit_spec"][field] = replacement
                    action["parameter_snapshot_sha256"] = method_execution._canonical_digest(
                        action["parameter_snapshot"]
                    )
                    validation = method_execution.validate_payload(base, payload)
                    self.assertTrue(validation.errors)
                    self.assertTrue(
                        any(item.code.startswith("EXHIBIT.") for item in validation.errors)
                    )

    def test_spec_ids_and_event_time_use_renderer_compatible_forms(self) -> None:
        spec = _spec()
        spec["exhibit_id"] = "fig-lower"
        self.assertIn(
            "EXHIBIT.SPEC.ID_INVALID",
            {item.code for item in contract.validate_spec(spec)},
        )
        spec = _spec()
        spec["source_result_ids"] = ["res-001"]
        self.assertIn(
            "EXHIBIT.SPEC.SOURCE_INVALID",
            {item.code for item in contract.validate_spec(spec)},
        )
        spec = _spec()
        spec["reference_period"] = "baseline"
        self.assertIn(
            "EXHIBIT.SPEC.FIELD_INVALID",
            {item.code for item in contract.validate_spec(spec)},
        )
        spec = _spec()
        spec["formats"] = ["PDF", "PNG"]
        self.assertIn(
            "EXHIBIT.SPEC.FORMAT_UNSUPPORTED",
            {item.code for item in contract.validate_spec(spec)},
        )

    def test_source_registered_semantics_cannot_drift(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            numeric = payload["runs"][0]["results"][0]["numeric_values"][0]
            numeric["exhibit_semantics"]["unit"] = "index points"
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH", codes)

    def test_uncertainty_locator_semantics_cannot_drift(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            numeric = next(
                item
                for item in payload["runs"][0]["results"][0]["numeric_values"]
                if item["locator"] == "json:/conf_low"
            )
            numeric["exhibit_semantics"]["unit"] = "log odds"
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH", codes)

    def test_uncertainty_values_require_vcov_type(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            data_path = base / "artifacts/fig-event-001/data.csv"
            rows = [_row(reference=True), _row(reference=False)]
            for row in rows:
                row["vcov_type"] = ""
            _write_csv(data_path, rows)
            next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-DATA"
            )["sha256"] = _sha256(data_path)
            for numeric in payload["runs"][0]["results"][0]["numeric_values"]:
                numeric["exhibit_semantics"]["vcov_type"] = ""
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.SEMANTIC.UNCERTAINTY_UNDECLARED", codes)

    def test_sample_size_comparison_is_exact_for_large_counts(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            spec = _spec()
            spec["sample_n"] = 1_000_000_000
            row = _row(reference=False)
            row["sample_n"] = 1_000_000_001
            result = copy.deepcopy(payload["runs"][0]["results"][0])
            sample_numeric = next(
                item
                for item in result["numeric_values"]
                if item["locator"] == "json:/sample_n"
            )
            sample_numeric["value"] = 1_000_000_000
            issues = contract.validate_data_rows(
                [row],
                spec,
                {"RES-001": result},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn(
                "EXHIBIT.NUMERIC.SAMPLE_MISMATCH",
                {item.code for item in issues},
            )

    def test_r_environment_snapshot_is_bound_to_action_and_log(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            environment = next(
                item
                for item in payload["software_environments"]
                if item["id"] == "ENV-EXHIBIT-001"
            )
            environment["exhibit_renderer"]["R"] = "Python-only environment"
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH", codes)

    def test_r_environment_snapshot_cannot_be_an_empty_shell(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            minimal = {
                "schema_version": contract.RENDER_ENV_SCHEMA_VERSION,
                "renderer": "r/generic-ggplot2-v1",
            }
            environment = next(
                item
                for item in payload["software_environments"]
                if item["id"] == "ENV-EXHIBIT-001"
            )
            environment["exhibit_renderer"] = minimal
            log_path = base / "artifacts/fig-event-001/render_log.json"
            log = json.loads(log_path.read_text(encoding="utf-8"))
            log["software_environment"] = minimal
            log["software_environment_sha256"] = contract.canonical_digest(minimal)
            log_path.write_text(json.dumps(log, sort_keys=True) + "\n", encoding="utf-8")
            next(
                item
                for item in payload["runs"][0]["artifacts"]
                if item["id"] == "ART-EXH-LOG"
            )["sha256"] = _sha256(log_path)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH", codes)

    def test_source_result_must_use_current_accepted_action(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            run = payload["runs"][0]
            source = run["actions"][0]
            retry = copy.deepcopy(source)
            retry.update({"id": "ACT-SOURCE-RETRY", "attempt": 2, "status": "failed"})
            retry["check_results"] = []
            retry["failure_code"] = "SOURCE.RETRY.FAILED"
            retry["disposition_route"] = "review"
            retry["deviation_id"] = ""
            run["actions"].append(retry)
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.ACTION_NOT_ACCEPTED", codes)

    def test_exhibit_artifacts_reject_extra_source_actions(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            for artifact in payload["runs"][0]["artifacts"]:
                if artifact.get("exhibit_id") == "FIG-EVENT-001":
                    artifact["source_action_ids"].append("ACTION-BOGUS-999")
            codes = {
                item.code
                for item in method_execution.validate_payload(base, payload).errors
            }
            self.assertIn("EXHIBIT.PROVENANCE.ACTION_NOT_ACCEPTED", codes)

    def test_figure_map_skips_nonconsumable_runs(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            payload["runs"][0]["status"] = "withdrawn"
            self.assertNotIn("FIG-EVENT-001", figure_map.render_prefill(payload))

    def test_renderer_requires_a_fresh_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            spec_path = base / "spec.json"
            data_path = base / "data.csv"
            outdir = base / "out"
            outdir.mkdir()
            spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
            _write_csv(data_path, [_row(reference=True), _row(reference=False)])
            with self.assertRaisesRegex(RuntimeError, "OUTPUT_EXISTS"):
                render(
                    spec_path,
                    data_path,
                    outdir,
                    "ENV-EXHIBIT-001",
                    sys.executable,
                )

    def test_json_companion_root_exhibit_id_is_bound_to_spec(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            data_path = base / "data.json"
            data_path.write_text(
                json.dumps(
                    {
                        "schema_version": contract.DATA_SCHEMA_VERSION,
                        "exhibit_id": "FIG-OTHER-001",
                        "rows": [_row(reference=True)],
                    }
                ),
                encoding="utf-8",
            )
            rows, error = contract.read_exhibit_rows(
                base,
                {"path": "data.json"},
                "FIG-EVENT-001",
            )
            self.assertEqual([], rows)
            self.assertIn("exhibit_id differs", error)

    def test_csv_companion_rejects_duplicate_column_names(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            data_path = base / "data.csv"
            data_path.write_text(
                "schema_version,exhibit_id,estimate,estimate\n"
                "avereth-exhibit-data/v1,FIG-EVENT-001,999,0.12\n",
                encoding="utf-8",
            )
            rows, error = contract.read_exhibit_rows(
                base,
                {"path": "data.csv"},
                "FIG-EVENT-001",
            )
            self.assertEqual([], rows)
            self.assertIn("unique column names", error)

    def test_json_companion_rejects_schema_invalid_scalar_types(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw)
            data_path = base / "data.json"
            invalid = _row(reference=False)
            invalid.update(
                {
                    "estimate": "0.12",
                    "std_error": "0.03",
                    "conf_low": "0.0612",
                    "conf_high": "0.1788",
                    "confidence_level": "0.95",
                    "sample_n": "100",
                    "is_reference": "false",
                }
            )
            data_path.write_text(
                json.dumps(
                    {
                        "schema_version": contract.DATA_SCHEMA_VERSION,
                        "exhibit_id": "FIG-EVENT-001",
                        "rows": [invalid],
                    }
                ),
                encoding="utf-8",
            )
            rows, error = contract.read_exhibit_rows(
                base,
                {"path": "data.json"},
                "FIG-EVENT-001",
            )
            self.assertEqual([], rows)
            self.assertIn("must be a number", error)

    def test_csv_numeric_grammar_matches_r(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            rows = [_row(reference=True), _row(reference=False)]
            rows[1]["estimate"] = "0.1_2"
            issues = contract.validate_data_rows(
                rows,
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn("EXHIBIT.NUMERIC.DRIFT", {item.code for item in issues})

    def test_nonlinear_exhibits_require_explicit_x_scale(self) -> None:
        spec = _spec("predicted_probability")
        del spec["x_scale"]
        self.assertIn(
            "EXHIBIT.SPEC.X_SCALE_INVALID",
            {item.code for item in contract.validate_spec(spec)},
        )

    def test_series_style_is_stable_across_panels(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            first = _row(reference=False)
            first["panel_label"] = "A"
            second = copy.deepcopy(first)
            second.update({"panel_label": "B", "line_type": "dashed", "marker": "17"})
            issues = contract.validate_data_rows(
                [first, second],
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn("EXHIBIT.VISUAL.STYLE_INVALID", {item.code for item in issues})

    def test_style_values_must_come_from_selected_profile(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            row = _row(reference=False)
            row.update({"color": "#FFFFFF", "line_type": "longdash", "marker": "99"})
            issues = contract.validate_data_rows(
                [row],
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn("EXHIBIT.VISUAL.STYLE_INVALID", {item.code for item in issues})

    def test_panel_labels_cannot_mix_empty_and_named_values(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            first = _row(reference=False)
            first["panel_label"] = ""
            second = copy.deepcopy(first)
            second["panel_label"] = "A"
            issues = contract.validate_data_rows(
                [first, second],
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn("EXHIBIT.VISUAL.PANEL_LABEL_MIXED", {item.code for item in issues})

    def test_reference_flag_cannot_bypass_numeric_provenance(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            row = _row(reference=False)
            row.update(
                {
                    "is_reference": True,
                    "source_numeric_locator": "",
                    "estimate": 0.15,
                }
            )
            issues = contract.validate_data_rows(
                [row],
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            codes = {item.code for item in issues}
            self.assertIn("EXHIBIT.SEMANTIC.REFERENCE_INVALID", codes)
            self.assertIn("EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_MISSING", codes)

    def test_each_event_series_requires_exactly_one_reference_row(self) -> None:
        temporary, _base, _design, payload = exhibit_workspace()
        with temporary:
            rows = [_row(reference=True), _row(reference=False)]
            second_series = copy.deepcopy(rows[1])
            second_series["group_label"] = "subgroup"
            second_series["marker"] = "17"
            issues = contract.validate_data_rows(
                [*rows, second_series],
                _spec(),
                {"RES-001": payload["runs"][0]["results"][0]},
                {"ART-NUM-001"},
                "fixture",
            )
            self.assertIn(
                "EXHIBIT.SEMANTIC.REFERENCE_MISSING",
                {item.code for item in issues},
            )

    def test_current_accepted_actions_require_unique_exhibit_ids(self) -> None:
        actions = {}
        for index in (1, 2):
            action_id = f"ACT-EXHIBIT-{index:03d}"
            actions[action_id] = {
                "id": action_id,
                "operation_id": f"OP-EXHIBIT-{index:03d}",
                "attempt": 1,
                "status": "accepted",
                "parameter_snapshot": {"content": {"exhibit_spec": _spec()}},
                "result_ids": [],
                "input_artifact_ids": [],
                "output_artifact_ids": [],
                "software_environment_id": "",
            }
        issues = contract.validate_run_exhibits(
            Path.cwd(),
            {"claim_dispositions": []},
            actions=actions,
            artifacts={},
            results={},
            operations={},
            environments={},
            path="run",
        )
        self.assertIn(
            "EXHIBIT.PROVENANCE.EXHIBIT_ID_DUPLICATE",
            {item.code for item in issues},
        )


def _rebind_render_environment(base: Path, payload: dict, mutate) -> None:
    """Apply one mutation to the Action environment and the on-disk render log alike."""

    environment = next(
        item for item in payload["software_environments"] if item["id"] == "ENV-EXHIBIT-001"
    )
    log_path = base / "artifacts/fig-event-001/render_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    mutate(environment["exhibit_renderer"], log)
    log["software_environment"] = copy.deepcopy(environment["exhibit_renderer"])
    log["software_environment_sha256"] = contract.canonical_digest(log["software_environment"])
    log_path.write_text(json.dumps(log, sort_keys=True) + "\n", encoding="utf-8")
    for artifact in payload["runs"][0]["artifacts"]:
        if artifact.get("id") == "ART-EXH-LOG":
            artifact["sha256"] = _sha256(log_path)
        elif artifact.get("role") in contract.VISUAL_ROLES:
            artifact["render_checks"] = copy.deepcopy(log["render_checks"])


class ExhibitFontAndLabelTests(unittest.TestCase):
    def test_resolved_font_must_be_declared_by_style_profile(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            def mutate(environment: dict, log: dict) -> None:
                environment["resolved_fonts"] = {"base": "Comic Sans MS"}
                log["resolved_fonts"] = {"base": "Comic Sans MS"}
                log["render_checks"]["font_fallback_used"] = True

            _rebind_render_environment(base, payload, mutate)
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH", codes)

    def test_declared_fallback_font_is_accepted_and_bound(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            def mutate(environment: dict, log: dict) -> None:
                environment["resolved_fonts"] = {"base": "Times New Roman"}
                log["resolved_fonts"] = {"base": "Times New Roman"}
                log["render_checks"]["font_fallback_used"] = True

            _rebind_render_environment(base, payload, mutate)
            validation = method_execution.validate_payload(base, payload)
            exhibit_codes = {item.code for item in validation.errors if item.code.startswith("EXHIBIT.")}
            self.assertEqual(set(), exhibit_codes)

    def test_resolved_font_drift_between_action_and_log_is_blocked(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            environment = next(
                item for item in payload["software_environments"] if item["id"] == "ENV-EXHIBIT-001"
            )
            environment["exhibit_renderer"]["resolved_fonts"] = {"base": "Times New Roman"}
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH", codes)

    def test_font_fallback_flag_must_be_boolean(self) -> None:
        temporary, base, _design, payload = exhibit_workspace()
        with temporary:
            def mutate(environment: dict, log: dict) -> None:
                log["render_checks"]["font_fallback_used"] = "no"

            _rebind_render_environment(base, payload, mutate)
            codes = {item.code for item in method_execution.validate_payload(base, payload).errors}
            self.assertIn("EXHIBIT.VISUAL.FONT_UNAVAILABLE", codes)

    def test_axis_labels_are_optional_but_must_be_non_empty_strings(self) -> None:
        spec = _spec()
        spec["x_label"] = "相对期"
        spec["y_label"] = "登记效应（百分点）"
        self.assertEqual(
            [],
            [item for item in contract.validate_spec(spec) if item.path.endswith(("x_label", "y_label"))],
        )
        for field, value in (("x_label", ""), ("y_label", 12)):
            with self.subTest(field=field):
                broken = _spec()
                broken[field] = value
                paths = {item.path for item in contract.validate_spec(broken) if item.code == "EXHIBIT.SPEC.FIELD_INVALID"}
                self.assertIn(f"exhibit_spec.{field}", paths)

    def test_style_profiles_declare_fallback_chains_and_labels(self) -> None:
        for profile in sorted(contract.STYLE_PROFILES):
            with self.subTest(profile=profile):
                style = contract._style_profile(profile)
                self.assertTrue(style["fonts"]["base"])
                fallbacks = style["font_fallbacks"]["base"]
                self.assertTrue(fallbacks and all(isinstance(item, str) and item for item in fallbacks))
                self.assertNotIn(style["fonts"]["base"], fallbacks)
                for key in ("relative_period", "term", "observations", "note", "series_separator"):
                    self.assertTrue(style["labels"][key])


if __name__ == "__main__":
    unittest.main(verbosity=2)
