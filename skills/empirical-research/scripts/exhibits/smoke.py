#!/usr/bin/env python3
"""Render every M1 recipe and style through the real R backend."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from .contract import DATA_SCHEMA_VERSION, SPEC_SCHEMA_VERSION, _valid_file_format
from .render_bundle import render


ROOT = Path(__file__).resolve().parents[2]
EXHIBITS = ROOT / "references" / "exhibits"
KINDS = (
    "coefficient_forest",
    "event_study",
    "marginal_effects",
    "predicted_probability",
    "trend_or_binscatter",
    "regression_or_balance_table",
)
PROFILES = ("international-polisci-econ", "cn-social-science")
RECIPE_FILES = {
    "coefficient_forest": "coefficient-forest.json",
    "event_study": "event-study.json",
    "marginal_effects": "marginal-effects.json",
    "predicted_probability": "predicted-probability.json",
    "trend_or_binscatter": "trend-or-binscatter.json",
    "regression_or_balance_table": "regression-or-balance-table.json",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _labels(profile: str) -> dict[str, str]:
    if profile == "cn-social-science":
        return {
            "quantity": "登记效应",
            "unit": "百分点",
            "term": "政策效应",
            "model": "登记模型",
            "group": "全部样本",
            "panel_a": "总体",
            "panel_b": "分组",
            "estimand": "登记的平均效应",
        }
    return {
        "quantity": "registered effect",
        "unit": "percentage points",
        "term": "policy effect",
        "model": "registered model",
        "group": "all units",
        "panel_a": "pooled",
        "panel_b": "subgroup",
        "estimand": "registered average effect",
    }


def _spec(kind: str, profile: str, index: int) -> dict:
    labels = _labels(profile)
    style = EXHIBITS / "style-profiles" / f"{profile}.json"
    recipe = EXHIBITS / "recipes" / RECIPE_FILES[kind]
    spec = {
        "schema_version": SPEC_SCHEMA_VERSION,
        "exhibit_id": f"FIG-SMOKE-{index:03d}",
        "kind": kind,
        "placement": "main",
        "argument_role": "estimation",
        "source_result_ids": [f"RES-SMOKE-{index:03d}"],
        "quantity": labels["quantity"],
        "unit": labels["unit"],
        "confidence_levels": [0.95],
        "sample_n": 100,
        "style_profile": profile,
        "style_profile_sha256": _sha256(style),
        "recipe_sha256": _sha256(recipe),
        "formats": ["pdf", "svg", "png"],
        "caption_requirements": ["estimand", "uncertainty", "sample", "source result"],
    }
    if kind == "coefficient_forest":
        spec["reference_value"] = 0
    if kind == "event_study":
        spec.update({"reference_value": 0, "reference_period": -1, "treatment_boundary": 0})
    if kind in {"marginal_effects", "predicted_probability"}:
        spec["response_scale"] = "probability" if kind == "predicted_probability" else "response"
        spec["x_scale"] = "ordered_category" if kind == "predicted_probability" else "continuous"
    if kind == "trend_or_binscatter":
        spec["x_scale"] = "continuous"
    return spec


def _rows(spec: dict, profile: str) -> list[dict]:
    kind = spec["kind"]
    labels = _labels(profile)
    if kind == "predicted_probability":
        points: list[tuple[object, float]] = [("01", 0.25), ("02", 0.45), ("03", 0.68)]
    elif kind == "event_study":
        points = [(-1, 0.0), (0, 0.12), (1, 0.18)]
    else:
        points = [(0, 0.08), (1, 0.12), (2, 0.18)]
    panels = [labels["panel_a"], labels["panel_b"]] if kind == "trend_or_binscatter" else [labels["panel_a"]]
    rows: list[dict] = []
    for panel_index, panel in enumerate(panels):
        for point_index, (x, estimate) in enumerate(points):
            adjusted = estimate + panel_index * 0.02
            is_reference = kind == "event_study" and x == -1
            if is_reference:
                adjusted = 0.0
            rows.append(
                {
                    "schema_version": DATA_SCHEMA_VERSION,
                    "exhibit_id": spec["exhibit_id"],
                    "kind": kind,
                    "quantity": spec["quantity"],
                    "term": f"{labels['term']} {point_index + 1}",
                    "x": x,
                    "estimate": adjusted,
                    "std_error": 0.03,
                    "conf_low": max(0.0, adjusted - 0.0588) if kind == "predicted_probability" else adjusted - 0.0588,
                    "conf_high": min(1.0, adjusted + 0.0588) if kind == "predicted_probability" else adjusted + 0.0588,
                    "confidence_level": 0.95,
                    "model_label": labels["model"],
                    "group_label": labels["group"],
                    "panel_label": panel,
                    "is_reference": is_reference,
                    "sample_n": 100,
                    "estimand": labels["estimand"],
                    "unit": spec["unit"],
                    "vcov_type": "cluster robust",
                    "cluster_level": "unit",
                    "source_result_id": spec["source_result_ids"][0],
                    "source_numeric_locator": f"json:/estimate/{panel_index}/{point_index}",
                    "std_error_locator": f"json:/std_error/{panel_index}/{point_index}",
                    "conf_low_locator": f"json:/conf_low/{panel_index}/{point_index}",
                    "conf_high_locator": f"json:/conf_high/{panel_index}/{point_index}",
                    "sample_n_locator": "json:/sample_n",
                    "line_type": "solid",
                    "marker": "16",
                    "color": "",
                }
            )
    return rows


def _png_dimensions_and_dpi(path: Path) -> tuple[int, int, float | None]:
    payload = path.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("EXHIBIT.FORMAT.INVALID: PNG signature is invalid")
    width, height = struct.unpack(">II", payload[16:24])
    offset = 8
    dpi: float | None = None
    while offset + 12 <= len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk = payload[offset + 8 : offset + 8 + length]
        if chunk_type == b"pHYs" and len(chunk) == 9 and chunk[8] == 1:
            pixels_per_metre = struct.unpack(">I", chunk[:4])[0]
            dpi = pixels_per_metre * 0.0254
            break
        offset += 12 + length
    return width, height, dpi


def _inspect_output(output: Path, report: dict, style: dict, environment_id: str) -> None:
    expected = {"exhibit.pdf": "pdf", "exhibit.svg": "svg", "exhibit.png": "png"}
    if {path.name for path in output.iterdir()} != {*expected, "render_log.json"}:
        raise RuntimeError("EXHIBIT.RENDERER.OUTPUT_UNDECLARED: smoke output inventory differs")
    for name, declared_format in expected.items():
        if not _valid_file_format(output / name, declared_format):
            raise RuntimeError(f"EXHIBIT.FORMAT.INVALID: {name} does not match {declared_format}")
    root = ET.parse(output / "exhibit.svg").getroot()
    if root.tag.rsplit("}", 1)[-1].casefold() != "svg":
        raise RuntimeError("EXHIBIT.FORMAT.INVALID: SVG is not parseable")
    width, height, dpi = _png_dimensions_and_dpi(output / "exhibit.png")
    expected_width = round(float(style["width_inches"]) * float(style["dpi"]))
    expected_height = round(float(style["height_inches"]) * float(style["dpi"]))
    if abs(width - expected_width) > 1 or abs(height - expected_height) > 1:
        raise RuntimeError("EXHIBIT.VISUAL.DIMENSION_MISMATCH: PNG pixel dimensions differ from style")
    if dpi is None or abs(dpi - float(style["dpi"])) > 1:
        raise RuntimeError("EXHIBIT.VISUAL.DPI_TOO_LOW: PNG metadata does not preserve configured DPI")
    render_log = json.loads((output / "render_log.json").read_text(encoding="utf-8"))
    if (
        render_log.get("software_environment_id") != environment_id
        or render_log.get("software_environment") != report.get("software_environment")
        or render_log.get("software_environment_sha256") != report.get("software_environment_sha256")
        or render_log.get("render_checks") != report.get("render_checks")
    ):
        raise RuntimeError("EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH: render report and log differ")


def run_smoke() -> dict:
    completed: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix="avereth-exhibit-smoke-") as raw:
        base = Path(raw)
        index = 0
        for profile in PROFILES:
            style_path = EXHIBITS / "style-profiles" / f"{profile}.json"
            style = json.loads(style_path.read_text(encoding="utf-8"))
            for kind in KINDS:
                index += 1
                case = base / f"case-{index:03d}"
                case.mkdir()
                spec_path = case / "spec.json"
                data_path = case / "data.csv"
                output = case / "output"
                spec = _spec(kind, profile, index)
                spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                rows = _rows(spec, profile)
                with data_path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                    writer.writeheader()
                    writer.writerows(rows)
                environment_id = f"ENV-SMOKE-{index:03d}"
                report = render(spec_path, data_path, output, environment_id)
                _inspect_output(output, report, style, environment_id)
                completed.append({"kind": kind, "profile": profile})
    return {
        "status": "PASS",
        "renderer": "r/generic-ggplot2-v1",
        "cases": len(completed),
        "kinds": sorted({item["kind"] for item in completed}),
        "profiles": sorted({item["profile"] for item in completed}),
        "formats": ["pdf", "png", "svg"],
    }


def main() -> int:
    try:
        result = run_smoke()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, ET.ParseError) as exc:
        print(str(exc))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
