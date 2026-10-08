#!/usr/bin/env python3
"""Validate optional empirical-exhibit extensions inside execution v3.

The module is deliberately authority-free: callers supply the already parsed
run-local Action, Result, and Artifact maps.  It never writes a workspace or
derives scientific results from a visual file.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
import zlib
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


SPEC_SCHEMA_VERSION = "avereth-exhibit-spec/v1"
DATA_SCHEMA_VERSION = "avereth-exhibit-data/v1"
STYLE_SCHEMA_VERSION = "avereth-exhibit-style/v1"
RENDER_ENV_SCHEMA_VERSION = "avereth-exhibit-renderer-environment/v1"
RENDER_LOG_SCHEMA_VERSION = "avereth-exhibit-render-log/v1"
RENDERER_ID = "r/generic-ggplot2-v1"
RENDERER_PACKAGES = {"jsonlite", "ggplot2", "svglite", "ragg", "systemfonts"}
ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")
SHA256_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")
NUMBER_TOKEN_PATTERN = re.compile(
    r"^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$"
)

EXHIBIT_KINDS = {
    "coefficient_forest",
    "event_study",
    "marginal_effects",
    "predicted_probability",
    "trend_or_binscatter",
    "regression_or_balance_table",
}
PLACEMENTS = {"main", "appendix"}
ARGUMENT_ROLES = {
    "description",
    "measurement",
    "identification",
    "estimation",
    "heterogeneity",
    "mechanism",
    "robustness",
}
STYLE_PROFILES = {"cn-social-science", "international-polisci-econ"}
FORMATS = {"pdf", "svg", "png"}
DATA_ROLES = {"plot_data", "table_data"}
VISUAL_ROLES = {
    "main_figure",
    "appendix_figure",
    "figure_preview",
    "main_table",
    "appendix_table",
}
EXHIBIT_ROLES = DATA_ROLES | VISUAL_ROLES | {"render_log"}

REQUIRED_SPEC_FIELDS = (
    "schema_version",
    "exhibit_id",
    "kind",
    "placement",
    "argument_role",
    "source_result_ids",
    "quantity",
    "unit",
    "confidence_levels",
    "style_profile",
    "style_profile_sha256",
    "recipe_sha256",
    "formats",
    "caption_requirements",
)
REQUIRED_DATA_FIELDS = (
    "schema_version",
    "exhibit_id",
    "kind",
    "quantity",
    "estimate",
    "model_label",
    "group_label",
    "panel_label",
    "is_reference",
    "sample_n",
    "estimand",
    "unit",
    "vcov_type",
    "cluster_level",
    "source_result_id",
    "source_numeric_locator",
    "line_type",
    "marker",
)


@dataclass(frozen=True)
class ExhibitIssue:
    code: str
    severity: str
    message: str
    path: str = ""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item).upper() for item in value if _text(item)]


def _finite(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        token = value.strip()
        if not NUMBER_TOKEN_PATTERN.fullmatch(token):
            return None
        value = token
    elif not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _is_json_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and _finite(value) is not None


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    token = _text(value).casefold()
    if token in {"true", "1", "yes"}:
        return True
    if token in {"false", "0", "no"}:
        return False
    return None


def _same_number(left: Any, right: Any) -> bool:
    left_number = _finite(left)
    right_number = _finite(right)
    if left_number is None or right_number is None:
        return _text(left) == _text(right)
    tolerance = max(1e-12, 1e-9 * max(abs(left_number), abs(right_number), 1.0))
    return abs(left_number - right_number) <= tolerance


def canonical_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _safe_workspace_path(base: Path, raw: Any) -> Path | None:
    token = _text(raw).replace("\\", "/")
    if not token or token.startswith("/") or ":" in token.split("/", 1)[0]:
        return None
    candidate = (base.resolve() / Path(token)).resolve()
    try:
        candidate.relative_to(base.resolve())
    except ValueError:
        return None
    return candidate


def exhibit_spec(action: Mapping[str, Any]) -> Mapping[str, Any] | None:
    present, spec = _snapshot_exhibit_value(action)
    if not present or not isinstance(spec, Mapping):
        return None
    if _text(spec.get("schema_version")) != SPEC_SCHEMA_VERSION:
        return None
    return spec


def _snapshot_exhibit_value(action: Mapping[str, Any]) -> tuple[bool, Any]:
    snapshot = action.get("parameter_snapshot")
    if not isinstance(snapshot, Mapping):
        return False, None
    content = snapshot.get("content")
    if not isinstance(content, Mapping):
        return False, None
    if "exhibit_spec" not in content:
        return False, None
    return True, content.get("exhibit_spec")


def _issue(
    issues: list[ExhibitIssue],
    code: str,
    message: str,
    path: str,
    severity: str = "ERROR",
) -> None:
    candidate = ExhibitIssue(code=code, severity=severity, message=message, path=path)
    if candidate not in issues:
        issues.append(candidate)


def validate_spec(spec: Mapping[str, Any], path: str = "exhibit_spec") -> list[ExhibitIssue]:
    issues: list[ExhibitIssue] = []
    for field in REQUIRED_SPEC_FIELDS:
        if field not in spec or spec.get(field) in (None, "", []):
            _issue(
                issues,
                "EXHIBIT.SPEC.FIELD_MISSING",
                f"ExhibitSpec requires {field}",
                f"{path}.{field}",
            )
    schema_version = _text(spec.get("schema_version"))
    for field in (
        "schema_version",
        "exhibit_id",
        "kind",
        "placement",
        "argument_role",
        "quantity",
        "unit",
        "style_profile",
        "style_profile_sha256",
        "recipe_sha256",
        "x_scale",
        "x_label",
        "y_label",
    ):
        value = spec.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            _issue(
                issues,
                "EXHIBIT.SPEC.FIELD_INVALID",
                f"{field} must be a non-empty string",
                f"{path}.{field}",
            )
    if schema_version and schema_version != SPEC_SCHEMA_VERSION:
        _issue(
            issues,
            "EXHIBIT.SPEC.SCHEMA_INVALID",
            f"ExhibitSpec must use {SPEC_SCHEMA_VERSION}",
            f"{path}.schema_version",
        )
    kind = _text(spec.get("kind"))
    if kind and kind not in EXHIBIT_KINDS:
        _issue(issues, "EXHIBIT.SPEC.KIND_UNSUPPORTED", f"Unsupported exhibit kind {kind!r}", f"{path}.kind")
    placement = _text(spec.get("placement"))
    if placement and placement not in PLACEMENTS:
        _issue(issues, "EXHIBIT.SPEC.PLACEMENT_INVALID", "placement must be main or appendix", f"{path}.placement")
    role = _text(spec.get("argument_role"))
    if role and role not in ARGUMENT_ROLES:
        _issue(issues, "EXHIBIT.SPEC.ARGUMENT_ROLE_INVALID", f"Unsupported argument role {role!r}", f"{path}.argument_role")
    style = _text(spec.get("style_profile"))
    if style and style not in STYLE_PROFILES:
        _issue(issues, "EXHIBIT.SPEC.STYLE_UNKNOWN", f"Unknown style profile {style!r}", f"{path}.style_profile")

    raw_source_ids = spec.get("source_result_ids")
    source_ids = _ids(raw_source_ids)
    if not isinstance(raw_source_ids, list) or not source_ids:
        _issue(issues, "EXHIBIT.SPEC.SOURCE_INVALID", "source_result_ids must be a non-empty array", f"{path}.source_result_ids")
    elif (
        len(source_ids) != len(raw_source_ids)
        or any(not isinstance(value, str) for value in raw_source_ids)
        or any(not ID_PATTERN.fullmatch(value.strip()) for value in raw_source_ids)
    ):
        _issue(issues, "EXHIBIT.SPEC.SOURCE_INVALID", "source_result_ids must contain stable IDs", f"{path}.source_result_ids")
    if len(source_ids) != len(set(source_ids)):
        _issue(issues, "EXHIBIT.SPEC.SOURCE_DUPLICATE", "source_result_ids must be unique", f"{path}.source_result_ids")
    exhibit_id = _text(spec.get("exhibit_id"))
    if exhibit_id and not ID_PATTERN.fullmatch(exhibit_id):
        _issue(issues, "EXHIBIT.SPEC.ID_INVALID", "exhibit_id must be a stable ID", f"{path}.exhibit_id")
    confidence_levels = spec.get("confidence_levels")
    if not isinstance(confidence_levels, list):
        _issue(issues, "EXHIBIT.SPEC.CONFIDENCE_INVALID", "confidence_levels must be an array", f"{path}.confidence_levels")
    else:
        if len(confidence_levels) != len({_text(value) for value in confidence_levels}):
            _issue(issues, "EXHIBIT.SPEC.CONFIDENCE_INVALID", "confidence_levels must be unique", f"{path}.confidence_levels")
        for index, value in enumerate(confidence_levels):
            number = _finite(value) if _is_json_number(value) else None
            if number is None or not 0 < number < 1:
                _issue(issues, "EXHIBIT.SPEC.CONFIDENCE_INVALID", "Confidence levels must be between zero and one", f"{path}.confidence_levels[{index}]")

    raw_formats = spec.get("formats")
    if not isinstance(raw_formats, list):
        _issue(issues, "EXHIBIT.SPEC.FORMAT_UNSUPPORTED", "formats must be an array", f"{path}.formats")
        raw_formats = []
    formats = {_text(value) for value in raw_formats if isinstance(value, str) and _text(value)}
    if len(formats) != len(raw_formats) or len(formats) < 2:
        _issue(issues, "EXHIBIT.SPEC.FORMAT_UNSUPPORTED", "formats must contain at least two unique values", f"{path}.formats")
    if formats - FORMATS:
        _issue(issues, "EXHIBIT.SPEC.FORMAT_UNSUPPORTED", "formats may contain only pdf, svg, and png", f"{path}.formats")
    if formats and not formats & {"pdf", "svg"}:
        _issue(issues, "EXHIBIT.VISUAL.RASTER_ONLY", "An exhibit requires at least one vector output", f"{path}.formats")
    if formats and "png" not in formats:
        _issue(issues, "EXHIBIT.SPEC.PREVIEW_MISSING", "A PNG preview is required for document and QA workflows", f"{path}.formats")

    captions = spec.get("caption_requirements")
    if (
        not isinstance(captions, list)
        or not captions
        or any(not isinstance(value, str) or not value.strip() for value in captions)
        or len(captions) != len(set(captions))
    ):
        _issue(issues, "EXHIBIT.SPEC.CAPTION_INVALID", "caption_requirements must be a non-empty string array", f"{path}.caption_requirements")
    for field in ("style_profile_sha256", "recipe_sha256"):
        if not SHA256_PATTERN.fullmatch(_text(spec.get(field))):
            _issue(issues, "EXHIBIT.PROVENANCE.HASH_MISMATCH", f"{field} must be a SHA-256 digest", f"{path}.{field}")
    sample_n = spec.get("sample_n")
    if sample_n is not None and (
        not isinstance(sample_n, int) or isinstance(sample_n, bool) or sample_n < 1
    ):
        _issue(issues, "EXHIBIT.NUMERIC.SAMPLE_MISMATCH", "sample_n must be a positive integer", f"{path}.sample_n")

    if kind == "coefficient_forest":
        if not _is_json_number(spec.get("reference_value")):
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.REFERENCE_MISSING",
                "Coefficient forest requires a finite reference_value",
                f"{path}.reference_value",
            )
    if kind == "event_study":
        for field in ("reference_value", "reference_period", "treatment_boundary"):
            if spec.get(field) in (None, ""):
                _issue(issues, "EXHIBIT.SEMANTIC.REFERENCE_MISSING", f"Event study requires {field}", f"{path}.{field}")
        for field in ("reference_value", "treatment_boundary"):
            if spec.get(field) not in (None, "") and not _is_json_number(spec.get(field)):
                _issue(issues, "EXHIBIT.SPEC.FIELD_INVALID", f"{field} must be a finite number", f"{path}.{field}")
        reference_period = spec.get("reference_period")
        if reference_period not in (None, "") and not _is_json_number(reference_period):
            _issue(issues, "EXHIBIT.SPEC.FIELD_INVALID", "reference_period must be a finite number", f"{path}.reference_period")
    if kind in {"marginal_effects", "predicted_probability"} and not _text(spec.get("response_scale")):
        _issue(
            issues,
            "EXHIBIT.SEMANTIC.NONLINEAR_SCALE_UNDECLARED",
            "Nonlinear exhibits must declare the response scale",
            f"{path}.response_scale",
        )
    elif kind in {"marginal_effects", "predicted_probability"} and not isinstance(spec.get("response_scale"), str):
        _issue(issues, "EXHIBIT.SPEC.FIELD_INVALID", "response_scale must be a string", f"{path}.response_scale")
    if kind == "predicted_probability" and _text(spec.get("response_scale")).casefold() != "probability":
        _issue(
            issues,
            "EXHIBIT.SEMANTIC.NONLINEAR_SCALE_UNDECLARED",
            "Predicted-probability exhibits must declare probability response scale",
            f"{path}.response_scale",
        )
    x_scale = _text(spec.get("x_scale"))
    if kind in {"marginal_effects", "predicted_probability"}:
        if x_scale not in {"continuous", "ordered_category"}:
            _issue(
                issues,
                "EXHIBIT.SPEC.X_SCALE_INVALID",
                "Marginal-effects and predicted-probability exhibits require x_scale=continuous or ordered_category",
                f"{path}.x_scale",
            )
    elif kind == "trend_or_binscatter" and x_scale != "continuous":
        _issue(
            issues,
            "EXHIBIT.SPEC.X_SCALE_INVALID",
            "Trend/binscatter exhibits require x_scale=continuous",
            f"{path}.x_scale",
        )
    return issues


def read_exhibit_rows(
    base: Path,
    artifact: Mapping[str, Any],
    expected_exhibit_id: str = "",
) -> tuple[list[dict[str, Any]], str]:
    path = _safe_workspace_path(base, artifact.get("path"))
    if path is None or not path.is_file():
        return [], "companion data is missing or outside the workspace"
    try:
        if path.suffix.casefold() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames
                if (
                    not isinstance(fieldnames, list)
                    or not fieldnames
                    or any(not _text(field) for field in fieldnames)
                    or len(fieldnames) != len(set(fieldnames))
                ):
                    return [], "CSV companion data requires non-empty unique column names"
                rows = [dict(row) for row in reader]
                if any(None in row for row in rows):
                    return [], "CSV companion data rows must match the declared column count"
                return rows, ""
        if path.suffix.casefold() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, Mapping) or payload.get("schema_version") != DATA_SCHEMA_VERSION:
                return [], f"JSON companion data must use {DATA_SCHEMA_VERSION}"
            if set(payload) != {"schema_version", "exhibit_id", "rows"}:
                return [], "JSON companion data root must contain exactly schema_version, exhibit_id, and rows"
            if expected_exhibit_id:
                payload_exhibit_id = _text(payload.get("exhibit_id"))
                if (
                    not ID_PATTERN.fullmatch(payload_exhibit_id)
                    or payload_exhibit_id != expected_exhibit_id
                ):
                    return [], "JSON companion data exhibit_id differs from ExhibitSpec"
            rows = payload.get("rows")
            if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
                return [], "JSON companion data rows must be an array of objects"
            string_fields = {
                "schema_version", "exhibit_id", "kind", "quantity", "model_label",
                "group_label", "panel_label", "estimand", "unit", "vcov_type",
                "cluster_level", "source_result_id", "source_numeric_locator",
                "std_error_locator", "conf_low_locator", "conf_high_locator",
                "sample_n_locator", "line_type", "marker",
            }
            nullable_string_fields = {"term", "color"}
            numeric_fields = {"estimate", "std_error", "conf_low", "conf_high", "confidence_level"}
            for row_index, row in enumerate(rows):
                for field in string_fields:
                    if field in row and not isinstance(row.get(field), str):
                        return [], f"JSON companion data row {row_index} field {field} must be a string"
                for field in nullable_string_fields:
                    if field in row and row.get(field) is not None and not isinstance(row.get(field), str):
                        return [], f"JSON companion data row {row_index} field {field} must be a string or null"
                if "x" in row and row.get("x") is not None and not (
                    isinstance(row.get("x"), str) or _is_json_number(row.get("x"))
                ):
                    return [], f"JSON companion data row {row_index} field x has an invalid type"
                for field in numeric_fields:
                    if field in row and row.get(field) is not None and not _is_json_number(row.get(field)):
                        return [], f"JSON companion data row {row_index} field {field} must be a number or null"
                if "is_reference" in row and not isinstance(row.get("is_reference"), bool):
                    return [], f"JSON companion data row {row_index} field is_reference must be boolean"
                sample_value = row.get("sample_n")
                if "sample_n" in row and (
                    not isinstance(sample_value, int) or isinstance(sample_value, bool) or sample_value < 1
                ):
                    return [], f"JSON companion data row {row_index} field sample_n must be a positive integer"
            return [dict(row) for row in rows], ""
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        return [], f"cannot parse companion data: {exc}"
    return [], "companion data must be CSV or JSON"


def _style_profile(style_id: str) -> Mapping[str, Any]:
    root = Path(__file__).resolve().parents[2] / "references" / "exhibits" / "style-profiles"
    path = root / f"{style_id}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _recipe(kind: str) -> Mapping[str, Any]:
    path = _asset_path("recipe", kind)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _asset_path(kind: str, identifier: str) -> Path:
    root = Path(__file__).resolve().parents[2] / "references" / "exhibits"
    if kind == "style":
        return root / "style-profiles" / f"{identifier}.json"
    names = {
        "coefficient_forest": "coefficient-forest.json",
        "event_study": "event-study.json",
        "marginal_effects": "marginal-effects.json",
        "predicted_probability": "predicted-probability.json",
        "trend_or_binscatter": "trend-or-binscatter.json",
        "regression_or_balance_table": "regression-or-balance-table.json",
    }
    return root / "recipes" / names.get(identifier, "__missing__.json")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_file_format(path: Path, declared_format: str) -> bool:
    try:
        payload = path.read_bytes()
    except OSError:
        return False
    if declared_format == "pdf":
        if not payload.startswith(b"%PDF-"):
            return False
        match = re.search(br"startxref\s+(\d+)\s+%%EOF\s*$", payload[-4096:])
        if match is None:
            return False
        offset = int(match.group(1))
        if not 0 <= offset < len(payload):
            return False
        target = payload[offset:].lstrip()
        if target.startswith(b"xref"):
            trailer = re.search(br"\btrailer\s*<<(.*?)>>", target, flags=re.DOTALL)
            return trailer is not None and re.search(
                br"/Root\s+\d+\s+\d+\s+R\b", trailer.group(1)
            ) is not None
        stream = re.match(
            br"\d+\s+\d+\s+obj\s*<<(.*?)>>\s*stream\b",
            target,
            flags=re.DOTALL,
        )
        return (
            stream is not None
            and re.search(br"/Type\s*/XRef\b", stream.group(1)) is not None
            and re.search(br"/Root\s+\d+\s+\d+\s+R\b", stream.group(1)) is not None
        )
    if declared_format == "png":
        if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
            return False
        offset = 8
        saw_ihdr = False
        saw_idat = False
        idat_ended = False
        saw_iend = False
        idat_payload = bytearray()
        while offset + 12 <= len(payload):
            length = struct.unpack(">I", payload[offset : offset + 4])[0]
            end = offset + 12 + length
            if end > len(payload):
                return False
            chunk_type = payload[offset + 4 : offset + 8]
            chunk_data = payload[offset + 8 : offset + 8 + length]
            expected_crc = struct.unpack(">I", payload[offset + 8 + length : end])[0]
            if zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF != expected_crc:
                return False
            if offset == 8:
                if chunk_type != b"IHDR" or length != 13:
                    return False
                width, height, bit_depth, color_type, compression, filter_method, interlace = struct.unpack(
                    ">IIBBBBB", chunk_data
                )
                if width < 1 or height < 1:
                    return False
                valid_depths = {
                    0: {1, 2, 4, 8, 16},
                    2: {8, 16},
                    3: {1, 2, 4, 8},
                    4: {8, 16},
                    6: {8, 16},
                }
                if (
                    color_type not in valid_depths
                    or bit_depth not in valid_depths[color_type]
                    or compression != 0
                    or filter_method != 0
                    or interlace not in {0, 1}
                ):
                    return False
                saw_ihdr = True
            elif chunk_type == b"IHDR":
                return False
            if chunk_type == b"IDAT":
                if not saw_ihdr or idat_ended:
                    return False
                saw_idat = True
                idat_payload.extend(chunk_data)
            elif saw_idat and chunk_type != b"IEND":
                idat_ended = True
            if chunk_type == b"IEND":
                saw_iend = saw_idat and length == 0 and end == len(payload)
                break
            offset = end
        if not (saw_ihdr and saw_idat and saw_iend):
            return False
        try:
            return bool(zlib.decompress(bytes(idat_payload)))
        except zlib.error:
            return False
    if declared_format == "svg":
        try:
            root = ET.fromstring(payload)
        except ET.ParseError:
            return False
        return root.tag.rsplit("}", 1)[-1].casefold() == "svg"
    return True


def validate_spec_assets(spec: Mapping[str, Any], path: str = "exhibit_spec") -> list[ExhibitIssue]:
    issues: list[ExhibitIssue] = []
    style_path = _asset_path("style", _text(spec.get("style_profile")))
    recipe_path = _asset_path("recipe", _text(spec.get("kind")))
    for asset_path, field in ((style_path, "style_profile_sha256"), (recipe_path, "recipe_sha256")):
        declared = _text(spec.get(field)).casefold()
        if not asset_path.is_file() or declared != _file_sha256(asset_path):
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.HASH_MISMATCH",
                f"{field} does not bind the current resolved asset",
                f"{path}.{field}",
            )
    return issues


def _numeric_locator_map(
    result: Mapping[str, Any],
) -> dict[str, list[Mapping[str, Any]]]:
    registered: dict[str, list[Mapping[str, Any]]] = {}
    for item in result.get("numeric_values") or []:
        if not isinstance(item, Mapping):
            continue
        locator = _text(item.get("locator"))
        if locator:
            registered.setdefault(locator, []).append(item)
    return registered


def _validate_numeric_semantics(
    issues: list[ExhibitIssue],
    numeric: Mapping[str, Any],
    row: Mapping[str, Any],
    spec: Mapping[str, Any],
    path: str,
) -> None:
    semantics = numeric.get("exhibit_semantics")
    if not isinstance(semantics, Mapping):
        _issue(
            issues,
            "EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH",
            "A plotted numeric value requires source-registered exhibit_semantics",
            path,
        )
        return
    expected = {
        "quantity": _text(row.get("quantity")),
        "unit": _text(row.get("unit")),
        "estimand": _text(row.get("estimand")),
        "vcov_type": _text(row.get("vcov_type")),
        "cluster_level": _text(row.get("cluster_level")),
    }
    for field, observed in expected.items():
        if _text(semantics.get(field)) != observed:
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH",
                f"Row {field} differs from the source numeric registration",
                f"{path}.{field}",
            )
    row_level = _finite(row.get("confidence_level"))
    registered_level = _finite(semantics.get("confidence_level"))
    if row_level is None or registered_level is None or not _same_number(row_level, registered_level):
        _issue(
            issues,
            "EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH",
            "Row confidence_level differs from the source numeric registration",
            f"{path}.confidence_level",
        )
    if _text(spec.get("kind")) in {"marginal_effects", "predicted_probability"}:
        if _text(semantics.get("response_scale")) != _text(spec.get("response_scale")):
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.SEMANTIC_MISMATCH",
                "Exhibit response_scale differs from the source numeric registration",
                f"{path}.response_scale",
            )


def validate_data_rows(
    rows: Sequence[Mapping[str, Any]],
    spec: Mapping[str, Any],
    results: Mapping[str, Mapping[str, Any]],
    input_artifact_ids: set[str],
    path: str,
) -> list[ExhibitIssue]:
    issues: list[ExhibitIssue] = []
    if not rows:
        _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", "Companion data has no rows", path)
        return issues

    expected_exhibit = _text(spec.get("exhibit_id")).upper()
    expected_kind = _text(spec.get("kind"))
    expected_quantity = _text(spec.get("quantity"))
    expected_unit = _text(spec.get("unit"))
    expected_results = set(_ids(spec.get("source_result_ids")))
    raw_confidence_levels = spec.get("confidence_levels")
    expected_levels = {
        _finite(value)
        for value in raw_confidence_levels
    } if isinstance(raw_confidence_levels, list) else set()
    sample_n = spec.get("sample_n")
    style = _style_profile(_text(spec.get("style_profile")))
    recipe = _recipe(expected_kind)
    recipe_fields = tuple(
        _text(value) for value in recipe.get("required_fields") or [] if _text(value)
    )
    max_series = int(style.get("max_series") or 4)
    allowed_lines = {_text(value) for value in style.get("line_types") or []}
    allowed_markers = {_text(value) for value in style.get("markers") or []}
    allowed_colours = {_text(value).casefold() for value in style.get("palette") or []}
    series_styles: dict[tuple[str, str], tuple[str, str, str]] = {}
    panel_series: dict[str, set[tuple[str, str]]] = {}
    panel_presence: set[bool] = set()
    event_series: set[tuple[str, str, str]] = set()
    reference_series: Counter[tuple[str, str, str]] = Counter()
    observed_result_ids: set[str] = set()

    for index, row in enumerate(rows):
        row_path = f"{path}.rows[{index}]"
        is_reference = _boolean(row.get("is_reference"))
        for field in REQUIRED_DATA_FIELDS:
            if field not in row:
                _issue(issues, "EXHIBIT.DATA.FIELD_MISSING", f"ExhibitData row requires {field}", f"{row_path}.{field}")
        for field in recipe_fields:
            if row.get(field) in (None, "") and not (
                is_reference is True
                and expected_kind == "event_study"
                and field in {"conf_low", "conf_high", "std_error"}
            ):
                _issue(
                    issues,
                    "EXHIBIT.DATA.RECIPE_FIELD_MISSING",
                    f"{expected_kind} rows require {field}",
                    f"{row_path}.{field}",
                )
        if _text(row.get("schema_version")) != DATA_SCHEMA_VERSION:
            _issue(issues, "EXHIBIT.DATA.SCHEMA_INVALID", f"Rows must declare {DATA_SCHEMA_VERSION}", f"{row_path}.schema_version")
        raw_row_exhibit_id = _text(row.get("exhibit_id"))
        if not ID_PATTERN.fullmatch(raw_row_exhibit_id) or raw_row_exhibit_id != expected_exhibit:
            _issue(issues, "EXHIBIT.DATA.EXHIBIT_ID_MISMATCH", "Row exhibit_id differs from ExhibitSpec", f"{row_path}.exhibit_id")
        if _text(row.get("kind")) != expected_kind:
            _issue(issues, "EXHIBIT.DATA.KIND_MISMATCH", "Row kind differs from ExhibitSpec", f"{row_path}.kind")
        if _text(row.get("quantity")) != expected_quantity:
            _issue(issues, "EXHIBIT.DATA.QUANTITY_MISMATCH", "Row quantity differs from ExhibitSpec", f"{row_path}.quantity")
        if _text(row.get("unit")) != expected_unit:
            _issue(issues, "EXHIBIT.NUMERIC.UNIT_MISMATCH", "Row unit differs from ExhibitSpec", f"{row_path}.unit")

        raw_source_result_id = _text(row.get("source_result_id"))
        source_result_id = raw_source_result_id.upper()
        if raw_source_result_id and not ID_PATTERN.fullmatch(raw_source_result_id):
            _issue(issues, "EXHIBIT.PROVENANCE.RESULT_MISSING", "source_result_id must be a stable uppercase ID", f"{row_path}.source_result_id")
        if source_result_id:
            observed_result_ids.add(source_result_id)
        source_result = results.get(source_result_id)
        if source_result_id not in expected_results or source_result is None:
            _issue(issues, "EXHIBIT.PROVENANCE.RESULT_MISSING", f"Row references unavailable source Result {source_result_id!r}", f"{row_path}.source_result_id")

        estimate = _finite(row.get("estimate"))
        if estimate is None:
            _issue(issues, "EXHIBIT.NUMERIC.DRIFT", "estimate must be a finite number", f"{row_path}.estimate")
        if is_reference is None:
            _issue(issues, "EXHIBIT.DATA.REFERENCE_FLAG_INVALID", "is_reference must be boolean", f"{row_path}.is_reference")
            is_reference = False
        reference_period_match = (
            expected_kind == "event_study"
            and _same_number(row.get("x"), spec.get("reference_period"))
        )
        reference_value_match = _same_number(
            row.get("estimate"), spec.get("reference_value")
        )
        valid_reference = bool(
            is_reference and reference_period_match and reference_value_match
        )
        if is_reference and expected_kind != "event_study":
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.REFERENCE_INVALID",
                "Only an event-study row at the declared reference period may set is_reference=true",
                f"{row_path}.is_reference",
            )
        elif is_reference and not reference_period_match:
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.REFERENCE_INVALID",
                "Event-study reference rows must use the declared reference period",
                f"{row_path}.x",
            )
        elif is_reference and not reference_value_match:
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.BASELINE_MISMATCH",
                "Reference-period estimate differs from the declared reference value",
                f"{row_path}.estimate",
            )
        elif expected_kind == "event_study" and reference_period_match and not is_reference:
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.REFERENCE_INVALID",
                "The declared event-study reference-period row must set is_reference=true",
                f"{row_path}.is_reference",
            )

        locator = _text(row.get("source_numeric_locator"))
        registered = _numeric_locator_map(source_result) if source_result is not None else {}
        if not valid_reference and not locator:
            _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_MISSING", "Non-reference rows must bind a registered source numeric locator", f"{row_path}.source_numeric_locator")
        elif locator:
            if locator not in registered:
                _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_MISSING", "source_numeric_locator is absent from the source Result", f"{row_path}.source_numeric_locator")
            elif len(registered[locator]) != 1:
                _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_AMBIGUOUS", "source_numeric_locator is not unique within the source Result", f"{row_path}.source_numeric_locator")
            else:
                registered_numeric = registered[locator][0]
                registered_value = registered_numeric.get("value")
                registered_artifact_id = _text(registered_numeric.get("artifact_id")).upper()
                if registered_artifact_id not in input_artifact_ids:
                    _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", "Rendering Action does not consume the numeric Artifact bound to source_numeric_locator", f"{row_path}.source_numeric_locator")
                if estimate is not None and not _same_number(estimate, registered_value):
                    _issue(issues, "EXHIBIT.NUMERIC.DRIFT", "Plotted estimate differs from the registered source numeric value", f"{row_path}.estimate")
                _validate_numeric_semantics(issues, registered_numeric, row, spec, row_path)

        low = _finite(row.get("conf_low")) if row.get("conf_low") not in (None, "") else None
        high = _finite(row.get("conf_high")) if row.get("conf_high") not in (None, "") else None
        standard_error = _finite(row.get("std_error")) if row.get("std_error") not in (None, "") else None
        if row.get("std_error") not in (None, "") and (
            standard_error is None or standard_error < 0
        ):
            _issue(issues, "EXHIBIT.NUMERIC.CI_MISMATCH", "std_error must be a non-negative finite number", f"{row_path}.std_error")
        if (low is None) != (high is None):
            _issue(issues, "EXHIBIT.NUMERIC.CI_MISMATCH", "Confidence interval bounds must be present together", row_path)
        elif low is not None and high is not None and (low > high or (estimate is not None and not low <= estimate <= high)):
            _issue(issues, "EXHIBIT.NUMERIC.CI_MISMATCH", "Confidence interval does not contain its estimate", row_path)
        if expected_levels:
            level = _finite(row.get("confidence_level"))
            if level is None or not any(_same_number(level, expected) for expected in expected_levels if expected is not None):
                _issue(issues, "EXHIBIT.NUMERIC.CI_MISMATCH", "Row confidence level differs from ExhibitSpec", f"{row_path}.confidence_level")

        for value_field, locator_field, code in (
            ("std_error", "std_error_locator", "EXHIBIT.NUMERIC.DRIFT"),
            ("conf_low", "conf_low_locator", "EXHIBIT.NUMERIC.CI_MISMATCH"),
            ("conf_high", "conf_high_locator", "EXHIBIT.NUMERIC.CI_MISMATCH"),
            ("sample_n", "sample_n_locator", "EXHIBIT.NUMERIC.SAMPLE_MISMATCH"),
        ):
            value = row.get(value_field)
            if value in (None, ""):
                continue
            value_locator = _text(row.get(locator_field))
            if not value_locator:
                _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_MISSING", f"{value_field} requires {locator_field}", f"{row_path}.{locator_field}")
            elif value_locator not in registered:
                _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_MISSING", f"{locator_field} is absent from the source Result", f"{row_path}.{locator_field}")
            elif len(registered[value_locator]) != 1:
                _issue(issues, "EXHIBIT.PROVENANCE.NUMERIC_LOCATOR_AMBIGUOUS", f"{locator_field} is not unique within the source Result", f"{row_path}.{locator_field}")
            else:
                registered_numeric = registered[value_locator][0]
                registered_value = registered_numeric.get("value")
                registered_artifact_id = _text(registered_numeric.get("artifact_id")).upper()
                if registered_artifact_id not in input_artifact_ids:
                    _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", f"Rendering Action does not consume the numeric Artifact bound to {locator_field}", f"{row_path}.{locator_field}")
                if value_field == "sample_n":
                    value_number = _finite(value)
                    registered_number = _finite(registered_value)
                    values_match = (
                        value_number is not None
                        and registered_number is not None
                        and value_number.is_integer()
                        and registered_number.is_integer()
                        and int(value_number) == int(registered_number)
                    )
                else:
                    values_match = _same_number(value, registered_value)
                if not values_match:
                    _issue(issues, code, f"{value_field} differs from the registered source numeric value", f"{row_path}.{value_field}")
                _validate_numeric_semantics(issues, registered_numeric, row, spec, row_path)

        row_n = _finite(row.get("sample_n"))
        if row_n is None or row_n < 1 or not row_n.is_integer():
            _issue(issues, "EXHIBIT.NUMERIC.SAMPLE_MISMATCH", "sample_n must be a positive integer", f"{row_path}.sample_n")
        elif sample_n not in (None, ""):
            spec_n = _finite(sample_n)
            if spec_n is None or not spec_n.is_integer() or int(row_n) != int(spec_n):
                _issue(issues, "EXHIBIT.NUMERIC.SAMPLE_MISMATCH", "Row sample_n differs from ExhibitSpec", f"{row_path}.sample_n")

        if not _text(row.get("estimand")):
            _issue(issues, "EXHIBIT.SEMANTIC.ESTIMAND_UNDECLARED", "Every plotted row must declare its estimand", f"{row_path}.estimand")
        uncertainty_present = any(
            row.get(field) not in (None, "")
            for field in ("std_error", "conf_low", "conf_high")
        )
        if uncertainty_present and not _text(row.get("vcov_type")):
            _issue(issues, "EXHIBIT.SEMANTIC.UNCERTAINTY_UNDECLARED", "Rows with uncertainty values require vcov_type", f"{row_path}.vcov_type")
        if "cluster" in _text(row.get("vcov_type")).casefold() and not _text(row.get("cluster_level")):
            _issue(issues, "EXHIBIT.SEMANTIC.CLUSTER_LEVEL_MISSING", "Clustered uncertainty requires cluster_level", f"{row_path}.cluster_level")

        if expected_kind == "predicted_probability":
            for field_name, value in (("estimate", estimate), ("conf_low", low), ("conf_high", high)):
                if value is not None and not 0 <= value <= 1:
                    _issue(issues, "EXHIBIT.SEMANTIC.NONLINEAR_SCALE_UNDECLARED", "Predicted probabilities must stay within zero and one", f"{row_path}.{field_name}")
        x_scale = _text(spec.get("x_scale"))
        if expected_kind in {"event_study", "trend_or_binscatter"} or (
            expected_kind in {"marginal_effects", "predicted_probability"}
            and x_scale == "continuous"
        ):
            if _finite(row.get("x")) is None:
                _issue(
                    issues,
                    "EXHIBIT.DATA.RECIPE_FIELD_INVALID",
                    f"{expected_kind} with a continuous x scale requires finite numeric x values",
                    f"{row_path}.x",
                )
        elif (
            expected_kind in {"marginal_effects", "predicted_probability"}
            and x_scale == "ordered_category"
            and not _text(row.get("x"))
        ):
            _issue(
                issues,
                "EXHIBIT.DATA.RECIPE_FIELD_INVALID",
                f"{expected_kind} with an ordered-category x scale requires non-empty x labels",
                f"{row_path}.x",
            )

        panel = _text(row.get("panel_label"))
        panel_presence.add(bool(panel))
        series = (
            _text(row.get("model_label")),
            _text(row.get("group_label")),
        )
        event_series_key = (*series, panel)
        if expected_kind == "event_study":
            event_series.add(event_series_key)
            if valid_reference:
                reference_series[event_series_key] += 1
        colour = _text(row.get("color"))
        line_type = _text(row.get("line_type"))
        marker = _text(row.get("marker"))
        visual_key = (line_type, marker)
        declared_style = (colour, line_type, marker)
        if not all(visual_key):
            _issue(
                issues,
                "EXHIBIT.DATA.FIELD_MISSING",
                "Every row requires non-empty line_type and marker",
                row_path,
            )
        if line_type and allowed_lines and line_type not in allowed_lines:
            _issue(issues, "EXHIBIT.VISUAL.STYLE_INVALID", "line_type is not allowed by the selected style profile", f"{row_path}.line_type")
        if marker and allowed_markers and marker not in allowed_markers:
            _issue(issues, "EXHIBIT.VISUAL.STYLE_INVALID", "marker is not allowed by the selected style profile", f"{row_path}.marker")
        if colour and allowed_colours and colour.casefold() not in allowed_colours:
            _issue(issues, "EXHIBIT.VISUAL.STYLE_INVALID", "color is not allowed by the selected style profile", f"{row_path}.color")
        previous = series_styles.setdefault(series, declared_style)
        if previous != declared_style:
            _issue(issues, "EXHIBIT.VISUAL.STYLE_INVALID", "A model/group series changes color, line, or marker identity across rows or panels", row_path)
        panel_series.setdefault(panel, set()).add(series)

    if len(panel_presence) > 1:
        _issue(
            issues,
            "EXHIBIT.VISUAL.PANEL_LABEL_MIXED",
            "panel_label must be empty for every row or non-empty for every row",
            path,
        )
    excessive = {
        panel: len(series_set)
        for panel, series_set in panel_series.items()
        if len(series_set) > max_series
    }
    if excessive:
        details = ", ".join(f"{panel or '<default>'}={count}" for panel, count in sorted(excessive.items()))
        _issue(issues, "EXHIBIT.VISUAL.TOO_MANY_SERIES", f"Panels exceed the style limit of {max_series} series: {details}", path)
    for panel, series_set in panel_series.items():
        inverse: dict[tuple[str, str], tuple[str, str]] = {}
        for series in series_set:
            _colour, line_type, marker = series_styles[series]
            visual_key = (line_type, marker)
            if visual_key in inverse and inverse[visual_key] != series:
                _issue(issues, "EXHIBIT.VISUAL.GRAYSCALE_COLLISION", f"Distinct series in panel {panel or '<default>'} share the same line type and marker", path)
            inverse[visual_key] = series

    if expected_kind == "event_study":
        incomplete = {
            series_key: reference_series[series_key]
            for series_key in event_series
            if reference_series[series_key] != 1
        }
        if incomplete:
            detail = ", ".join(
                f"{model}/{group}/{panel or '<default>'}={count}"
                for (model, group, panel), count in sorted(incomplete.items())
            )
            _issue(
                issues,
                "EXHIBIT.SEMANTIC.REFERENCE_MISSING",
                "Every event-study model/group/panel series requires exactly one declared reference row: " + detail,
                path,
            )
    if observed_result_ids != expected_results:
        missing = sorted(expected_results - observed_result_ids)
        extra = sorted(observed_result_ids - expected_results)
        detail = "; ".join(
            part
            for part in (
                "missing rows for " + ", ".join(missing) if missing else "",
                "unexpected rows for " + ", ".join(extra) if extra else "",
            )
            if part
        )
        _issue(
            issues,
            "EXHIBIT.PROVENANCE.RESULT_MISSING",
            "Companion data source Result coverage differs from ExhibitSpec: " + detail,
            path,
        )
    return issues


def _validate_render_checks(
    artifact: Mapping[str, Any],
    spec: Mapping[str, Any],
    path: str,
) -> list[ExhibitIssue]:
    issues: list[ExhibitIssue] = []
    if _text(artifact.get("role")) not in VISUAL_ROLES:
        return issues
    checks = artifact.get("render_checks")
    if not isinstance(checks, Mapping):
        _issue(issues, "EXHIBIT.VISUAL.CHECKS_MISSING", "Visual Artifact requires deterministic render_checks", f"{path}.render_checks")
        return issues
    style = _style_profile(_text(spec.get("style_profile")))
    min_font = _finite(checks.get("font_min_pt"))
    required_font = _finite(style.get("min_font_pt")) or 9.0
    if min_font is None or min_font < required_font:
        _issue(issues, "EXHIBIT.VISUAL.FONT_TOO_SMALL", f"Configured font minimum must be at least {required_font:g} pt", f"{path}.render_checks.font_min_pt")
    if checks.get("requested_fonts_available") is not True:
        _issue(issues, "EXHIBIT.VISUAL.FONT_UNAVAILABLE", "A font family declared by the style profile (primary or fallback) must be available to the renderer", f"{path}.render_checks.requested_fonts_available")
    if not isinstance(checks.get("font_fallback_used"), bool):
        _issue(issues, "EXHIBIT.VISUAL.FONT_UNAVAILABLE", "render_checks must record font_fallback_used as a boolean", f"{path}.render_checks.font_fallback_used")
    if _text(artifact.get("format")).casefold() == "png":
        dpi = _finite(checks.get("dpi"))
        if dpi is None or dpi < 300:
            _issue(issues, "EXHIBIT.VISUAL.DPI_TOO_LOW", "PNG output must be at least 300 dpi", f"{path}.render_checks.dpi")
    return issues


def _valid_renderer_environment(
    snapshot: Any,
    spec: Mapping[str, Any],
) -> bool:
    if not isinstance(snapshot, Mapping):
        return False
    required = {
        "schema_version",
        "renderer",
        "R",
        "packages",
        "requested_fonts",
        "resolved_fonts",
        "backend_sha256",
        "style_profile_sha256",
        "recipe_sha256",
    }
    packages = snapshot.get("packages")
    fonts = snapshot.get("requested_fonts")
    resolved = snapshot.get("resolved_fonts")
    style = _style_profile(_text(spec.get("style_profile")))
    declared_families = {
        _text(family).casefold()
        for family in (
            _text((style.get("fonts") or {}).get("base")),
            *((style.get("font_fallbacks") or {}).get("base") or []),
        )
        if _text(family)
    }
    backend = Path(__file__).resolve().parent / "backends" / "r" / "render_exhibit.R"
    return (
        set(snapshot) == required
        and _text(snapshot.get("schema_version")) == RENDER_ENV_SCHEMA_VERSION
        and _text(snapshot.get("renderer")) == RENDERER_ID
        and bool(_text(snapshot.get("R")))
        and isinstance(packages, Mapping)
        and set(packages) == RENDERER_PACKAGES
        and all(bool(_text(value)) for value in packages.values())
        and isinstance(fonts, Mapping)
        and set(fonts) == {"base"}
        and bool(_text(fonts.get("base")))
        and fonts == style.get("fonts")
        and isinstance(resolved, Mapping)
        and set(resolved) == {"base"}
        and _text(resolved.get("base")).casefold() in declared_families
        and SHA256_PATTERN.fullmatch(_text(snapshot.get("backend_sha256"))) is not None
        and backend.is_file()
        and _text(snapshot.get("backend_sha256")).casefold() == _file_sha256(backend)
        and _text(snapshot.get("style_profile_sha256")).casefold()
        == _text(spec.get("style_profile_sha256")).casefold()
        and _text(snapshot.get("recipe_sha256")).casefold()
        == _text(spec.get("recipe_sha256")).casefold()
    )


def validate_run_exhibits(
    base: Path,
    run: Mapping[str, Any],
    *,
    actions: Mapping[str, Mapping[str, Any]],
    artifacts: Mapping[str, Mapping[str, Any]],
    results: Mapping[str, Mapping[str, Any]],
    operations: Mapping[str, Mapping[str, Any]],
    environments: Mapping[str, Mapping[str, Any]],
    path: str,
) -> list[ExhibitIssue]:
    """Validate every ExhibitSpec-bearing action in one execution run."""

    issues: list[ExhibitIssue] = []
    current_actions: dict[str, Mapping[str, Any]] = {}
    for candidate in actions.values():
        candidate_operation = _text(candidate.get("operation_id")).upper()
        candidate_attempt = candidate.get("attempt")
        if not candidate_operation or not isinstance(candidate_attempt, int):
            continue
        current = current_actions.get(candidate_operation)
        if current is None or candidate_attempt > int(current.get("attempt") or 0):
            current_actions[candidate_operation] = candidate
    current_action_ids = {
        _text(item.get("id")).upper()
        for item in current_actions.values()
        if _text(item.get("status")) == "accepted"
    }
    accepted_exhibit_ids: dict[str, str] = {}
    for action_id, action in actions.items():
        action_path = f"{path}.actions[{action_id}]"
        spec_path = f"{action_path}.parameter_snapshot.content.exhibit_spec"
        operation_id = _text(action.get("operation_id")).upper()
        operation = operations.get(operation_id)
        procedure = operation.get("procedure") if isinstance(operation, Mapping) else None
        exhibit_operation = (
            isinstance(procedure, Mapping)
            and _text(procedure.get("operation")) in {"exhibit_render", "exhibit_rendering"}
        )
        snapshot = action.get("parameter_snapshot")
        snapshot_content = snapshot.get("content") if isinstance(snapshot, Mapping) else None
        if exhibit_operation and (
            _text(procedure.get("parameters_ref"))
            != "Action.parameter_snapshot.content.exhibit_spec"
            or not isinstance(snapshot_content, Mapping)
            or _text(snapshot_content.get("operation"))
            != _text(procedure.get("operation"))
            or snapshot_content.get("procedure") != procedure
        ):
            _issue(
                issues,
                "EXHIBIT.CONTRACT.PARAMETER_BINDING_INVALID",
                "Exhibit STEP and Action must bind the exact ExhibitSpec parameter location and procedure snapshot",
                f"{action_path}.parameter_snapshot.content",
            )
        present, raw_spec = _snapshot_exhibit_value(action)
        if not present and not exhibit_operation:
            continue
        if not isinstance(raw_spec, Mapping):
            _issue(
                issues,
                "EXHIBIT.SPEC.FIELD_MISSING",
                "An exhibit rendering Action requires an ExhibitSpec object",
                spec_path,
            )
            continue
        spec = raw_spec
        issues.extend(validate_spec(spec, spec_path))
        issues.extend(validate_spec_assets(spec, spec_path))
        current_action_id = _text(action.get("id")).upper()
        exhibit_id = _text(spec.get("exhibit_id"))
        if current_action_id in current_action_ids and exhibit_id:
            previous_action = accepted_exhibit_ids.setdefault(
                exhibit_id, current_action_id
            )
            if previous_action != current_action_id:
                _issue(
                    issues,
                    "EXHIBIT.PROVENANCE.EXHIBIT_ID_DUPLICATE",
                    f"Current accepted rendering Actions {previous_action} and {current_action_id} reuse exhibit_id {exhibit_id}",
                    f"{spec_path}.exhibit_id",
                )
        if not exhibit_operation:
            _issue(issues, "EXHIBIT.CONTRACT.STEP_INVALID", "ExhibitSpec action must resolve to an exhibit_rendering STEP", f"{action_path}.operation_id")
        source_result_ids = set(_ids(spec.get("source_result_ids")))
        source_results: dict[str, Mapping[str, Any]] = {}
        source_action_ids: set[str] = set()
        source_artifact_sets: dict[str, set[str]] = {}
        for source_result_id in sorted(source_result_ids):
            source_result = results.get(source_result_id)
            if source_result is None:
                _issue(issues, "EXHIBIT.PROVENANCE.RESULT_MISSING", f"Unknown source Result {source_result_id}", f"{spec_path}.source_result_ids")
                continue
            source_results[source_result_id] = source_result
            status = _text(source_result.get("status"))
            claim_ids = set(_ids(source_result.get("claim_ids")))
            dispositions = {
                _text(item.get("claim_id")).upper(): _text(item.get("status"))
                for item in run.get("claim_dispositions") or []
                if isinstance(item, Mapping) and source_result_id in _ids(item.get("result_ids"))
            }
            eligible = (
                status in {"supported", "qualified"}
                and claim_ids
                and all(dispositions.get(claim_id) == "retained" for claim_id in claim_ids)
            ) or (
                status in {"null", "negative", "not-supported"}
                and claim_ids
                and all(dispositions.get(claim_id) in {"narrowed", "withdrawn"} for claim_id in claim_ids)
            )
            if not eligible:
                _issue(issues, "EXHIBIT.PROVENANCE.SOURCE_RESULT_INELIGIBLE", f"Source Result {source_result_id} is not eligible for downstream reporting", f"{spec_path}.source_result_ids")
            linked_actions = set(_ids(source_result.get("action_ids")))
            if action_id in linked_actions:
                _issue(issues, "EXHIBIT.PROVENANCE.SELF_SOURCE", "A rendering action cannot produce its own source Result", action_path)
            for linked_action_id in linked_actions:
                linked = actions.get(linked_action_id)
                if (
                    linked is None
                    or _text(linked.get("status")) != "accepted"
                    or linked_action_id not in current_action_ids
                    or source_result_id not in _ids(linked.get("result_ids"))
                ):
                    _issue(issues, "EXHIBIT.PROVENANCE.ACTION_NOT_ACCEPTED", f"Source Result depends on non-accepted Action {linked_action_id}", action_path)
                else:
                    source_action_ids.add(linked_action_id)
            source_artifact_sets[source_result_id] = set(_ids(source_result.get("artifact_ids")))

        if _text(action.get("status")) != "accepted":
            continue
        if _ids(action.get("result_ids")):
            _issue(
                issues,
                "EXHIBIT.CONTRACT.RESULT_FORBIDDEN",
                "A rendering Action projects existing Results and must not create a scientific Result",
                f"{action_path}.result_ids",
            )
        inputs = set(_ids(action.get("input_artifact_ids")))
        for source_result_id, required in sorted(source_artifact_sets.items()):
            if required and not inputs & required:
                _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", f"Rendering action consumes no hashed Artifact from source Result {source_result_id}", f"{action_path}.input_artifact_ids")

        output_ids = set(_ids(action.get("output_artifact_ids")))
        output_artifacts = {identifier: artifacts[identifier] for identifier in output_ids if identifier in artifacts and _text(artifacts[identifier].get("role")) in EXHIBIT_ROLES}
        if set(output_artifacts) != output_ids:
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.OUTPUT_DRIFT",
                "Every exhibit Action output must use a registered empirical-exhibit Artifact role",
                f"{action_path}.output_artifact_ids",
            )
        expected_artifacts = {
            _text(item.get("id")).upper(): item
            for item in (operation.get("expected_artifacts") if isinstance(operation, Mapping) else []) or []
            if isinstance(item, Mapping) and _text(item.get("id"))
        }
        if output_ids != set(expected_artifacts):
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.OUTPUT_DRIFT",
                "Accepted exhibit Action outputs must exactly match the design STEP expected artifacts",
                f"{action_path}.output_artifact_ids",
            )
        for artifact_id, artifact in output_artifacts.items():
            expected = expected_artifacts.get(artifact_id)
            if expected is None or _text(expected.get("path")).replace("\\", "/") != _text(artifact.get("path")).replace("\\", "/") or _text(expected.get("role")) != _text(artifact.get("role")):
                _issue(issues, "EXHIBIT.PROVENANCE.OUTPUT_DRIFT", "Exhibit output ID, path, and role must match the design STEP", f"{path}.artifacts[{artifact_id}]")
        spec_sha = canonical_digest(spec)
        raw_formats = spec.get("formats")
        expected_formats = {
            _text(value)
            for value in raw_formats
            if _text(value)
        } if isinstance(raw_formats, list) else set()
        observed_formats: Counter[str] = Counter()
        data_artifacts: dict[str, Mapping[str, Any]] = {}
        render_logs = {
            identifier: artifact
            for identifier, artifact in output_artifacts.items()
            if _text(artifact.get("role")) == "render_log"
        }
        render_log: Mapping[str, Any] = {}
        if len(render_logs) != 1:
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID",
                "Accepted exhibit Action requires exactly one render_log Artifact",
                f"{action_path}.output_artifact_ids",
            )
        else:
            log_id, log_artifact = next(iter(render_logs.items()))
            log_path = _safe_workspace_path(base, log_artifact.get("path"))
            try:
                loaded_log = json.loads(log_path.read_text(encoding="utf-8-sig")) if log_path is not None else None
            except (OSError, json.JSONDecodeError):
                loaded_log = None
            if (
                not isinstance(loaded_log, Mapping)
                or _text(loaded_log.get("schema_version")) != RENDER_LOG_SCHEMA_VERSION
                or _text(loaded_log.get("exhibit_id")) != _text(spec.get("exhibit_id"))
                or not isinstance(loaded_log.get("render_checks"), Mapping)
                or not _text(loaded_log.get("renderer"))
                or not isinstance(loaded_log.get("inputs"), Mapping)
                or not isinstance(loaded_log.get("outputs"), list)
            ):
                _issue(
                    issues,
                    "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID",
                    "render_log identity, renderer, or checks are invalid",
                    f"{path}.artifacts[{log_id}]",
                )
            else:
                render_log = loaded_log
        environment_id = _text(action.get("software_environment_id")).upper()
        environment = environments.get(environment_id)
        environment_snapshot = (
            environment.get("exhibit_renderer")
            if isinstance(environment, Mapping)
            else None
        )
        log_environment = render_log.get("software_environment") if render_log else None
        log_environment_sha = _text(render_log.get("software_environment_sha256")) if render_log else ""
        log_inputs = render_log.get("inputs") if render_log else None
        expected_log_inputs = {
            "spec_sha256": spec_sha,
            "style_sha256": _text(spec.get("style_profile_sha256")),
            "recipe_sha256": _text(spec.get("recipe_sha256")),
            "backend_sha256": (
                _file_sha256(Path(__file__).resolve().parent / "backends" / "r" / "render_exhibit.R")
            ),
        }
        if (
            not _valid_renderer_environment(environment_snapshot, spec)
            or not isinstance(log_environment, Mapping)
            or environment_snapshot != log_environment
            or _text(render_log.get("software_environment_id")).upper() != environment_id
            or log_environment_sha != canonical_digest(environment_snapshot)
            or _text(environment_snapshot.get("renderer")) != _text(render_log.get("renderer"))
            or _text(environment_snapshot.get("R")) != _text(render_log.get("R"))
            or environment_snapshot.get("packages") != render_log.get("packages")
            or environment_snapshot.get("requested_fonts") != render_log.get("requested_fonts")
            or environment_snapshot.get("resolved_fonts") != render_log.get("resolved_fonts")
            or not isinstance(log_inputs, Mapping)
            or set(log_inputs) != {*expected_log_inputs, "data_sha256"}
            or any(
                _text(log_inputs.get(field)).casefold() != expected.casefold()
                for field, expected in expected_log_inputs.items()
            )
            or not SHA256_PATTERN.fullmatch(_text(log_inputs.get("data_sha256")))
        ):
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.ENVIRONMENT_MISMATCH",
                "Rendering Action, software environment, and render_log must bind the same captured R renderer environment",
                f"{action_path}.software_environment_id",
            )
        for artifact_id, artifact in output_artifacts.items():
            artifact_path = f"{path}.artifacts[{artifact_id}]"
            role = _text(artifact.get("role"))
            if role in DATA_ROLES:
                data_artifacts[artifact_id] = artifact
                local_path = _safe_workspace_path(base, artifact.get("path"))
                artifact_format = _text(artifact.get("format"))
                if (
                    artifact_format not in {"csv", "json"}
                    or local_path is None
                    or local_path.suffix.casefold() != f".{artifact_format}"
                ):
                    _issue(
                        issues,
                        "EXHIBIT.FORMAT.INVALID",
                        "Companion data format must be csv or json and match its path",
                        f"{artifact_path}.format",
                    )
            if role == "render_log":
                local_path = _safe_workspace_path(base, artifact.get("path"))
                if (
                    _text(artifact.get("format")) != "json"
                    or local_path is None
                    or local_path.suffix.casefold() != ".json"
                ):
                    _issue(
                        issues,
                        "EXHIBIT.FORMAT.INVALID",
                        "render_log format must be json and match its path",
                        f"{artifact_path}.format",
                    )
            if role in VISUAL_ROLES:
                artifact_format = _text(artifact.get("format")).casefold()
                observed_formats[artifact_format] += 1
                placement = _text(spec.get("placement"))
                kind = _text(spec.get("kind"))
                if artifact_format == "png":
                    expected_role = "figure_preview"
                elif kind == "regression_or_balance_table":
                    expected_role = f"{placement}_table"
                else:
                    expected_role = f"{placement}_figure"
                if role != expected_role:
                    _issue(
                        issues,
                        "EXHIBIT.FORMAT.ROLE_MISMATCH",
                        f"{kind} {placement} output {artifact_format!r} requires role {expected_role}",
                        f"{artifact_path}.format",
                    )
                local_path = _safe_workspace_path(base, artifact.get("path"))
                if local_path is None or not local_path.is_file() or not _valid_file_format(local_path, artifact_format):
                    _issue(
                        issues,
                        "EXHIBIT.FORMAT.INVALID",
                        "Visual Artifact content does not match its declared format",
                        f"{artifact_path}.format",
                    )
            expected_fields = {
                "exhibit_id": _text(spec.get("exhibit_id")),
                "kind": _text(spec.get("kind")),
                "style_profile": _text(spec.get("style_profile")),
                "spec_sha256": spec_sha,
                "placement": _text(spec.get("placement")),
                "argument_role": _text(spec.get("argument_role")),
            }
            for field, expected in expected_fields.items():
                observed = _text(artifact.get(field))
                if observed != expected:
                    _issue(issues, "EXHIBIT.PROVENANCE.HASH_MISMATCH" if field == "spec_sha256" else "EXHIBIT.PROVENANCE.METADATA_MISMATCH", f"Artifact {field} differs from ExhibitSpec", f"{artifact_path}.{field}")
            for field in ("renderer", "native_adapter", "format"):
                if not _text(artifact.get(field)):
                    _issue(issues, "EXHIBIT.PROVENANCE.METADATA_MISMATCH", f"Artifact requires {field}", f"{artifact_path}.{field}")
            if render_log and _text(artifact.get("renderer")) != _text(render_log.get("renderer")):
                _issue(issues, "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID", "Artifact renderer differs from render_log", f"{artifact_path}.renderer")
            raw_artifact_result_ids = artifact.get("source_result_ids")
            if (
                not isinstance(raw_artifact_result_ids, list)
                or any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in raw_artifact_result_ids)
                or set(raw_artifact_result_ids) != source_result_ids
            ):
                _issue(issues, "EXHIBIT.PROVENANCE.RESULT_MISSING", "Artifact source_result_ids differ from ExhibitSpec", f"{artifact_path}.source_result_ids")
            raw_artifact_action_ids = artifact.get("source_action_ids")
            if (
                not isinstance(raw_artifact_action_ids, list)
                or any(not isinstance(item, str) or not ID_PATTERN.fullmatch(item) for item in raw_artifact_action_ids)
                or set(raw_artifact_action_ids) != source_action_ids
            ):
                _issue(issues, "EXHIBIT.PROVENANCE.ACTION_NOT_ACCEPTED", "Artifact source_action_ids must exactly match the current accepted source Actions", f"{artifact_path}.source_action_ids")
            if role in VISUAL_ROLES and render_log and artifact.get("render_checks") != render_log.get("render_checks"):
                _issue(issues, "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID", "Visual Artifact render_checks differ from the hash-bound render_log", f"{artifact_path}.render_checks")
            issues.extend(_validate_render_checks(artifact, spec, artifact_path))

        required_data_role = "table_data" if _text(spec.get("kind")) == "regression_or_balance_table" else "plot_data"
        matching_data = {identifier: artifact for identifier, artifact in data_artifacts.items() if _text(artifact.get("role")) == required_data_role}
        if len(matching_data) != 1:
            _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", f"Accepted exhibit action requires exactly one {required_data_role} Artifact", f"{action_path}.output_artifact_ids")
        else:
            data_id, data_artifact = next(iter(matching_data.items()))
            if (
                not isinstance(log_inputs, Mapping)
                or _text(log_inputs.get("data_sha256")).casefold()
                != _text(data_artifact.get("sha256")).casefold()
            ):
                _issue(
                    issues,
                    "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID",
                    "render_log input data SHA differs from the companion data Artifact",
                    f"{path}.artifacts[{data_id}].sha256",
                )
            rows, error = read_exhibit_rows(
                base,
                data_artifact,
                _text(spec.get("exhibit_id")),
            )
            if error:
                _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", error, f"{path}.artifacts[{data_id}]")
            else:
                issues.extend(
                    validate_data_rows(
                        rows,
                        spec,
                        source_results,
                        inputs,
                        f"{path}.artifacts[{data_id}]",
                    )
                )
            for artifact_id, artifact in output_artifacts.items():
                if _text(artifact.get("role")) in VISUAL_ROLES and _text(artifact.get("plot_data_artifact_id")).upper() != data_id:
                    _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", "Visual Artifact does not bind the companion data Artifact", f"{path}.artifacts[{artifact_id}].plot_data_artifact_id")

        observed_format_names = set(observed_formats)
        logged_outputs: dict[str, str] = {}
        raw_logged_outputs = render_log.get("outputs") if render_log else None
        if isinstance(raw_logged_outputs, list):
            for item in raw_logged_outputs:
                if (
                    not isinstance(item, Mapping)
                    or set(item) != {"format", "sha256"}
                    or _text(item.get("format")) in logged_outputs
                    or not SHA256_PATTERN.fullmatch(_text(item.get("sha256")))
                ):
                    logged_outputs = {}
                    break
                logged_outputs[_text(item.get("format"))] = _text(item.get("sha256")).casefold()
        registered_outputs = {
            _text(artifact.get("format")): _text(artifact.get("sha256")).casefold()
            for artifact in output_artifacts.values()
            if _text(artifact.get("role")) in VISUAL_ROLES
        }
        if logged_outputs != registered_outputs:
            _issue(
                issues,
                "EXHIBIT.PROVENANCE.RENDER_LOG_INVALID",
                "render_log output SHA inventory differs from the visual Artifacts",
                f"{action_path}.output_artifact_ids",
            )
        missing_formats = sorted(expected_formats - observed_format_names)
        if missing_formats:
            _issue(issues, "EXHIBIT.PROVENANCE.DATA_ARTIFACT_MISSING", "Accepted exhibit action lacks requested formats: " + ", ".join(missing_formats), f"{action_path}.output_artifact_ids")
        unexpected_formats = sorted(observed_format_names - expected_formats)
        duplicate_formats = sorted(
            name for name, count in observed_formats.items() if count != 1
        )
        if unexpected_formats or duplicate_formats:
            detail = "; ".join(
                part
                for part in (
                    "unexpected " + ", ".join(unexpected_formats)
                    if unexpected_formats
                    else "",
                    "not exactly one output for " + ", ".join(duplicate_formats)
                    if duplicate_formats
                    else "",
                )
                if part
            )
            _issue(
                issues,
                "EXHIBIT.FORMAT.ROLE_MISMATCH",
                "Visual outputs must contain exactly one Artifact per requested format: " + detail,
                f"{action_path}.output_artifact_ids",
            )
    return issues
