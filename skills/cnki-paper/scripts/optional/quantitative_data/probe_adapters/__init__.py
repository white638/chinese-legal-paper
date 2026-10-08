"""Read-only metadata and bounded-row adapters for one quantitative input.

Adapters never return raw rows.  They expose only schema metadata and safe,
aggregated diagnostics so restricted files can remain outside a paper
workspace and outside model context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .archive import profile_archive
from .common import base_profile, path_error_profile
from .tabular import profile_tabular


MAX_BOUNDED_ROWS = 10_000
MAX_KEY_FIELDS = 64
MAX_KEY_FIELD_TEXT_CHARS = 4096
MAX_KEY_FIELDS_TOTAL_BYTES = 64 * 1024


def profile_path(
    path: Path,
    *,
    row_limit: int = 1000,
    key_fields: Sequence[str] = (),
    survey: bool = False,
    header_confirmed: bool = False,
) -> dict[str, Any]:
    """Profile one file without copying it or serializing row values."""

    path = Path(path)
    if not path.exists():
        return path_error_profile(
            path,
            code="FILE_NOT_FOUND",
            message="the requested local data file does not exist",
        )
    if not path.is_file():
        return path_error_profile(
            path,
            code="NOT_A_REGULAR_FILE",
            message="data adapters accept regular files, not directories or devices",
        )
    requested_row_limit = max(0, int(row_limit))
    effective_row_limit = min(requested_row_limit, MAX_BOUNDED_ROWS)
    normalized_keys: list[str] = []
    key_bytes = 0
    keys_exceeded = False
    for index, item in enumerate(key_fields):
        if index >= MAX_KEY_FIELDS:
            keys_exceeded = True
            break
        token = str(item).strip()
        if not token:
            continue
        if len(token) > MAX_KEY_FIELD_TEXT_CHARS:
            keys_exceeded = True
            break
        key_bytes += len(token.encode("utf-8"))
        if key_bytes > MAX_KEY_FIELDS_TOTAL_BYTES:
            keys_exceeded = True
            break
        normalized_keys.append(token)
    if keys_exceeded:
        profile = base_profile(path, adapter="policy/v1", backend="resource-guard")
        profile["parse_status"] = "BLOCKED"
        profile["profile_scope"] = "resource-policy"
        profile["errors"].append(
            {
                "code": "RESOURCE_LIMIT_EXCEEDED",
                "message": "requested key metadata exceeds the bounded adapter policy",
            }
        )
        profile["requested_row_limit"] = requested_row_limit
        profile["effective_row_limit"] = effective_row_limit
        return profile
    suffix = path.suffix.casefold()
    if suffix in {".zip", ".rar", ".7z", ".tar", ".gz", ".tgz"}:
        return profile_archive(path)
    profile = profile_tabular(
        path,
        row_limit=effective_row_limit,
        key_fields=tuple(normalized_keys),
        survey=bool(survey),
        header_confirmed=header_confirmed is True,
    )
    profile["requested_row_limit"] = requested_row_limit
    profile["effective_row_limit"] = effective_row_limit
    if requested_row_limit != effective_row_limit:
        profile["warnings"].append(
            f"ROW_LIMIT_CLAMPED: requested {requested_row_limit}, used {effective_row_limit}"
        )
    return profile


__all__ = [
    "MAX_BOUNDED_ROWS",
    "MAX_KEY_FIELDS",
    "profile_path",
]
