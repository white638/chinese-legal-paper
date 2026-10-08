#!/usr/bin/env python3
"""Emit a three-line (booktabs-style) table projection from exhibit companion data.

Chinese social-science journals require editable three-line tables, not pictures of
tables. This module projects the same ``avereth-exhibit-data/v1`` rows that feed the
R renderer into Markdown or LaTeX text that the manuscript pipeline can carry into
Word (``docx_normalize.py --tables``) or TeX. It needs no R. Numbers are copied from
the companion rows only; nothing is recomputed, so numeric authority stays with the
source Result and the hash-bound companion data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contract import (
    DATA_SCHEMA_VERSION,
    SPEC_SCHEMA_VERSION,
    _finite,
    _style_profile,
    _text,
    canonical_digest,
    validate_spec,
    validate_spec_assets,
)


TABLE_KINDS = {"regression_or_balance_table"}
TABLE_FORMATS = ("md", "tex")
DEFAULT_LABELS = {
    "term": "Variable",
    "observations": "Observations",
    "note": "Note",
    "series_separator": " / ",
    "estimand": "Estimand",
    "unit_label": "Unit",
    "vcov": "Standard errors",
    "cluster": "Clustered by",
    "ci": "Confidence level",
    "se_in_parentheses": "Standard errors in parentheses",
    "ci_in_brackets": "Confidence intervals in brackets",
}
_TEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_spec(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, Mapping) or payload.get("schema_version") != SPEC_SCHEMA_VERSION:
        raise ValueError(f"EXHIBIT.SPEC.SCHEMA_INVALID: spec must use {SPEC_SCHEMA_VERSION}")
    issues = [*validate_spec(payload), *validate_spec_assets(payload)]
    if any(item.severity == "ERROR" for item in issues):
        raise ValueError("; ".join(f"{item.code}@{item.path}" for item in issues))
    return payload


def load_rows(path: Path, spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    suffix = path.suffix.casefold()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if not fieldnames or any(not _text(field) for field in fieldnames) or len(fieldnames) != len(set(fieldnames)):
                raise ValueError("EXHIBIT.DATA.FIELD_MISSING: CSV companion data requires non-empty unique column names")
            rows = [dict(row) for row in reader]
    elif suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        raw_rows = payload.get("rows") if isinstance(payload, Mapping) else None
        if not isinstance(raw_rows, list):
            raise ValueError("EXHIBIT.DATA.FIELD_MISSING: JSON companion data requires a rows array")
        rows = [dict(row) for row in raw_rows if isinstance(row, Mapping)]
    else:
        raise ValueError("EXHIBIT.DATA.FIELD_MISSING: companion data must be CSV or JSON")
    if not rows:
        raise ValueError("EXHIBIT.DATA.FIELD_MISSING: companion data has no rows")
    expected_id = _text(spec.get("exhibit_id"))
    expected_kind = _text(spec.get("kind"))
    for index, row in enumerate(rows):
        if _text(row.get("schema_version")) != DATA_SCHEMA_VERSION:
            raise ValueError(f"EXHIBIT.DATA.SCHEMA_INVALID: row {index} must use {DATA_SCHEMA_VERSION}")
        if _text(row.get("exhibit_id")) != expected_id or _text(row.get("kind")) != expected_kind:
            raise ValueError(f"EXHIBIT.DATA.FIELD_MISSING: row {index} does not belong to {expected_id}/{expected_kind}")
    return rows


def _number(value: Any) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return _finite(value)
    try:
        return _finite(float(str(value).strip()))
    except ValueError:
        return None


def _format_number(value: float | None, digits: int) -> str:
    if value is None:
        return ""
    if float(value).is_integer() and abs(value) >= 1000:
        return f"{int(value):d}"
    return f"{value:.{digits}f}"


def _column_labels(rows: Sequence[Mapping[str, Any]], separator: str) -> list[tuple[tuple[str, str], str]]:
    keys: list[tuple[str, str]] = []
    for row in rows:
        key = (_text(row.get("model_label")), _text(row.get("group_label")))
        if key not in keys:
            keys.append(key)
    labels = [separator.join(part for part in key if part) or "series" for key in keys]
    if len(set(labels)) != len(labels):
        labels = [separator.join(key) for key in keys]
    return list(zip(keys, labels))


def _tex_escape(text: str) -> str:
    return "".join(_TEX_ESCAPES.get(char, char) for char in text)


def _md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _semantic_note(rows: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    def unique(field: str) -> list[str]:
        seen: list[str] = []
        for row in rows:
            value = _text(row.get(field))
            if value and value not in seen:
                seen.append(value)
        return seen

    parts: list[str] = []
    has_se = any(_number(row.get("std_error")) is not None for row in rows)
    has_ci = any(_number(row.get("conf_low")) is not None and _number(row.get("conf_high")) is not None for row in rows)
    if has_se:
        parts.append(labels["se_in_parentheses"])
    elif has_ci:
        parts.append(labels["ci_in_brackets"])
    vcov = unique("vcov_type")
    if vcov:
        parts.append(f"{labels['vcov']}: {', '.join(vcov)}")
    cluster = unique("cluster_level")
    if cluster:
        parts.append(f"{labels['cluster']}: {', '.join(cluster)}")
    levels = unique("confidence_level")
    if levels and (has_ci or has_se):
        rendered = ", ".join(_format_number(_number(level), 2) or level for level in levels)
        parts.append(f"{labels['ci']}: {rendered}")
    estimand = unique("estimand")
    if estimand:
        parts.append(f"{labels['estimand']}: {', '.join(estimand)}")
    unit = unique("unit")
    if unit:
        parts.append(f"{labels['unit_label']}: {', '.join(unit)}")
    return "; ".join(parts)


def build_table(
    spec: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    fmt: str = "md",
    digits: int = 3,
    data_sha256: str = "",
) -> str:
    kind = _text(spec.get("kind"))
    if kind not in TABLE_KINDS:
        raise ValueError(f"EXHIBIT.SPEC.KIND_UNSUPPORTED: table projection supports {sorted(TABLE_KINDS)}, not {kind!r}")
    if fmt not in TABLE_FORMATS:
        raise ValueError(f"EXHIBIT.FORMAT.INVALID: table format must be one of {TABLE_FORMATS}")
    if not rows:
        raise ValueError("EXHIBIT.DATA.FIELD_MISSING: companion data has no rows")
    style = _style_profile(_text(spec.get("style_profile")))
    labels = {**DEFAULT_LABELS, **{k: _text(v) for k, v in (style.get("labels") or {}).items() if _text(v)}}
    columns = _column_labels(rows, labels["series_separator"])
    terms: list[str] = []
    cells: dict[tuple[str, tuple[str, str]], Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        term = _text(row.get("term"))
        if not term:
            raise ValueError(f"EXHIBIT.DATA.FIELD_MISSING: row {index} requires a term")
        if term not in terms:
            terms.append(term)
        key = (term, (_text(row.get("model_label")), _text(row.get("group_label"))))
        if key in cells:
            raise ValueError(f"EXHIBIT.DATA.FIELD_MISSING: duplicate cell for term {term!r} in model/group {key[1]}")
        if _number(row.get("estimate")) is None:
            raise ValueError(f"EXHIBIT.DATA.FIELD_MISSING: row {index} requires a finite estimate")
        cells[key] = row

    body: list[tuple[str, list[str]]] = []
    for term in terms:
        first: list[str] = []
        second: list[str] = []
        for key, _label in columns:
            row = cells.get((term, key))
            if row is None:
                first.append("")
                second.append("")
                continue
            first.append(_format_number(_number(row.get("estimate")), digits))
            std_error = _number(row.get("std_error"))
            low = _number(row.get("conf_low"))
            high = _number(row.get("conf_high"))
            if std_error is not None:
                second.append(f"({_format_number(std_error, digits)})")
            elif low is not None and high is not None:
                second.append(f"[{_format_number(low, digits)}, {_format_number(high, digits)}]")
            else:
                second.append("")
        body.append((term, first))
        if any(second):
            body.append(("", second))

    observations: list[str] = []
    for key, _label in columns:
        sizes = {
            _text(row.get("sample_n"))
            for (term, row_key), row in cells.items()
            if row_key == key and _text(row.get("sample_n"))
        }
        if len(sizes) == 1:
            observations.append(_format_number(_number(next(iter(sizes))), 0))
        else:
            observations.append("—")
    note_text = _semantic_note(rows, labels)
    provenance = (
        f"avereth-exhibit {_text(spec.get('exhibit_id'))}; kind={kind}; "
        f"source_result_ids={','.join(_text(item) for item in spec.get('source_result_ids') or [])}; "
        f"spec_sha256={canonical_digest(spec)}"
        + (f"; data_sha256={data_sha256}" if data_sha256 else "")
    )
    header = [labels["term"], *[label for _key, label in columns]]

    if fmt == "md":
        lines = [f"<!-- {provenance} -->", ""]
        lines.append("| " + " | ".join(_md_cell(cell) for cell in header) + " |")
        lines.append("|" + "|".join(["---"] + ["---:"] * len(columns)) + "|")
        for label, values in body:
            lines.append("| " + " | ".join(_md_cell(cell) for cell in [label, *values]) + " |")
        lines.append("| " + " | ".join(_md_cell(cell) for cell in [labels["observations"], *observations]) + " |")
        if note_text:
            lines.extend(["", f"{labels['note']}: {note_text}"])
        return "\n".join(lines) + "\n"

    alignment = "l" + "r" * len(columns)
    lines = [f"% {provenance}", f"\\begin{{tabular}}{{{alignment}}}", "\\toprule"]
    lines.append(" & ".join(_tex_escape(cell) for cell in header) + " \\\\")
    lines.append("\\midrule")
    for label, values in body:
        lines.append(" & ".join(_tex_escape(cell) for cell in [label, *values]) + " \\\\")
    lines.append("\\midrule")
    lines.append(" & ".join(_tex_escape(cell) for cell in [labels["observations"], *observations]) + " \\\\")
    lines.extend(["\\bottomrule", "\\end{tabular}"])
    if note_text:
        lines.append(f"\\par\\noindent{{\\footnotesize {_tex_escape(labels['note'])}: {_tex_escape(note_text)}}}")
    return "\n".join(lines) + "\n"


def emit(spec_path: Path, data_path: Path, out_path: Path, *, fmt: str = "md", digits: int = 3) -> dict[str, Any]:
    spec = load_spec(spec_path)
    rows = load_rows(data_path, spec)
    data_bytes = data_path.read_bytes()
    text = build_table(spec, rows, fmt=fmt, digits=digits, data_sha256=_sha256_bytes(data_bytes))
    if out_path.exists():
        raise RuntimeError("EXHIBIT.RENDERER.OUTPUT_EXISTS: use a new output path so the projection cannot silently overwrite an author-edited table")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = text.encode("utf-8")
    out_path.write_bytes(payload)
    return {
        "schema_version": "avereth-exhibit-table-report/v1",
        "exhibit_id": _text(spec.get("exhibit_id")),
        "kind": _text(spec.get("kind")),
        "format": fmt,
        "path": str(out_path),
        "sha256": _sha256_bytes(payload),
        "spec_sha256": canonical_digest(spec),
        "data_sha256": _sha256_bytes(data_bytes),
        "rows": len(rows),
        "authority": "projection-only; numeric authority stays with the source Result and companion data",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--format", choices=TABLE_FORMATS, default="md")
    parser.add_argument("--digits", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        report = emit(args.spec, args.data, args.out, fmt=args.format, digits=args.digits)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
