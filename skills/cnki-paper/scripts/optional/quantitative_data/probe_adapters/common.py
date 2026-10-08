"""Shared helpers for privacy-preserving data profile adapters."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ADAPTER_VERSION = "avereth-data-profile-adapter/v1"
VARIABLE_STATES = {"DISCOVERED", "DOCUMENTED", "OBSERVED", "HARMONIZED"}
MAX_SURVEY_FIELD_MATCHES = 64
WEIGHT = re.compile(r"(?:^|_)(?:weight|weights|wgt|wt|pweight|fweight|aweight|w_l|swgt)(?:$|_)|权重", re.I)
PSU = re.compile(r"(?:^|_)(?:psu|primary_sampling_unit)(?:$|_)|初级抽样|一级抽样", re.I)
STRATA = re.compile(r"(?:^|_)(?:strata|stratum|strat)(?:$|_)|分层|层变量", re.I)


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def decode_text(value: bytes) -> str:
    raw = value.rstrip(b"\x00 ")
    if not raw:
        return ""
    for encoding in ("utf-8", "gb18030", "utf-16-le", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def safe_value(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def variable_record(
    name: str,
    *,
    label: str = "",
    storage_type: str = "unknown",
    value_labels: Mapping[Any, Any] | None = None,
    state: str = "OBSERVED",
) -> dict[str, Any]:
    labels = []
    for index, (value, text) in enumerate((value_labels or {}).items()):
        if index >= 200:
            break
        labels.append({"value": safe_value(value), "label": str(text or "")})
    return {
        "name": str(name),
        "label": str(label or ""),
        "storage_type": str(storage_type or "unknown"),
        "value_labels": labels,
        "state": state if state in VARIABLE_STATES else "OBSERVED",
    }


def survey_design(variables: Iterable[Mapping[str, Any]], *, expected: bool) -> dict[str, Any]:
    rows = list(variables)

    def matches(pattern: re.Pattern[str]) -> list[str]:
        return sorted(
            {
                str(row.get("name") or "")
                for row in rows
                if pattern.search(
                    " ".join(
                        (str(row.get("name") or ""), str(row.get("label") or ""))
                    ).strip()
                )
            }
        )

    all_weights = matches(WEIGHT)
    all_psu = matches(PSU)
    all_strata = matches(STRATA)
    weights = all_weights[:MAX_SURVEY_FIELD_MATCHES]
    psu = all_psu[:MAX_SURVEY_FIELD_MATCHES]
    strata = all_strata[:MAX_SURVEY_FIELD_MATCHES]
    risks: list[str] = []
    if expected:
        if not weights:
            risks.append("SURVEY_WEIGHT_NOT_OBSERVED")
        if not psu:
            risks.append("SURVEY_PSU_NOT_OBSERVED")
        if not strata:
            risks.append("SURVEY_STRATA_NOT_OBSERVED")
    return {
        "expected": expected,
        "weight_fields": weights,
        "psu_fields": psu,
        "strata_fields": strata,
        "weight_field_count": len(all_weights),
        "psu_field_count": len(all_psu),
        "strata_field_count": len(all_strata),
        "fields_truncated": any(
            len(values) > MAX_SURVEY_FIELD_MATCHES
            for values in (all_weights, all_psu, all_strata)
        ),
        "risks": risks,
    }


def key_diagnostics(frame: Any, key_fields: Sequence[str]) -> dict[str, Any]:
    """Return aggregate key diagnostics for a bounded in-memory frame."""

    columns_value = getattr(frame, "columns", ())
    columns = list(columns_value) if columns_value is not None else []
    mapping_rows: list[Mapping[str, Any]] | None = None
    if isinstance(frame, Sequence) and not isinstance(frame, (str, bytes, bytearray)):
        mapping_rows = [row for row in frame if isinstance(row, Mapping)]
        columns = sorted({str(key) for row in mapping_rows for key in row})
    fields = [field for field in key_fields if field in columns]
    missing = [field for field in key_fields if field not in columns]
    sample_rows = len(mapping_rows) if mapping_rows is not None else int(len(frame))
    result: dict[str, Any] = {
        "requested_fields": list(key_fields),
        "observed_fields": fields,
        "missing_fields": missing,
        "sample_rows": sample_rows,
        "nonmissing_key_rows": 0,
        "duplicate_key_rows": 0,
        "unique_in_bounded_sample": False,
        "claim_boundary": "bounded-sample diagnostic only; not a panel-validity determination",
    }
    if not fields or len(fields) != len(key_fields) or sample_rows == 0:
        return result
    if mapping_rows is not None:
        def present(value: Any) -> bool:
            return value is not None and not (isinstance(value, float) and math.isnan(value))

        def hashable_value(value: Any) -> Any:
            try:
                hash(value)
                return value
            except TypeError:
                return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

        complete_keys = [
            tuple(hashable_value(row.get(field)) for field in fields)
            for row in mapping_rows
            if all(present(row.get(field)) for field in fields)
        ]
        counts: dict[tuple[Any, ...], int] = {}
        for key in complete_keys:
            counts[key] = counts.get(key, 0) + 1
        duplicates = sum(count for count in counts.values() if count > 1)
        result.update(
            {
                "nonmissing_key_rows": len(complete_keys),
                "duplicate_key_rows": duplicates,
                "unique_in_bounded_sample": bool(
                    len(complete_keys) == sample_rows and duplicates == 0
                ),
            }
        )
        return result
    subset = frame[fields]
    complete = subset.dropna()
    duplicates = int(complete.duplicated(keep=False).sum())
    result.update(
        {
            "nonmissing_key_rows": int(len(complete)),
            "duplicate_key_rows": duplicates,
            "unique_in_bounded_sample": bool(len(complete) == len(frame) and duplicates == 0),
        }
    )
    return result


def base_profile(path: Path, *, adapter: str, backend: str) -> dict[str, Any]:
    stat = path.stat()
    return {
        "adapter": adapter,
        "adapter_version": ADAPTER_VERSION,
        "parser_backend": backend,
        "format": path.suffix.casefold().lstrip(".") or "binary",
        "parse_status": "PASS",
        "file_size_bytes": int(stat.st_size),
        "file_mtime_ns": int(stat.st_mtime_ns),
        "file_row_count": None,
        "observed_rows": 0,
        "column_count": 0,
        "data_label": "",
        "variables": [],
        "key_diagnostics": {},
        "survey_design": {},
        "archive_manifest": [],
        "warnings": [],
        "errors": [],
        "raw_rows_embedded": False,
    }


def path_error_profile(path: Path, *, code: str, message: str) -> dict[str, Any]:
    """Return a stable profile shape when a path cannot be opened as a file."""

    exists = path.exists()
    stat = path.stat() if exists else None
    return {
        "adapter": "filesystem/v1",
        "adapter_version": ADAPTER_VERSION,
        "parser_backend": "path-guard",
        "format": path.suffix.casefold().lstrip(".") or "binary",
        "parse_status": "BLOCKED",
        "file_size_bytes": int(stat.st_size) if stat and path.is_file() else None,
        "file_mtime_ns": int(stat.st_mtime_ns) if stat else None,
        "file_row_count": None,
        "observed_rows": 0,
        "column_count": 0,
        "data_label": "",
        "variables": [],
        "key_diagnostics": {},
        "survey_design": {},
        "archive_manifest": [],
        "warnings": [],
        "errors": [{"code": code, "message": message}],
        "raw_rows_embedded": False,
        "profile_scope": "path-validation",
    }


def unsupported_profile(
    path: Path,
    *,
    format_name: str,
    dependency_requirement: str,
) -> dict[str, Any]:
    """Fail closed when a reproducible, pinned parser is not part of the runtime."""

    profile = base_profile(path, adapter="unsupported/v1", backend="none")
    profile["parse_status"] = "BLOCKED"
    profile["profile_scope"] = "capability-check"
    profile["capabilities"] = {
        "format": format_name,
        "available": False,
        "full_file_fallback_allowed": False,
    }
    profile["errors"].append(
        {
            "code": "UNSUPPORTED_FORMAT",
            "message": (
                f"{format_name} requires {dependency_requirement}; "
                "no unpinned or full-file fallback was attempted"
            ),
        }
    )
    return profile
