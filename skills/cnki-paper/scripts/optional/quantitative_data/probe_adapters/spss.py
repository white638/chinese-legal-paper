"""Fail-closed SPSS adapter boundary.

SAV is intentionally not parsed by a bespoke partial reader.  Supporting it
requires a pinned parser plus fixtures covering byte order, long names,
encodings, compression modes, missing values, and value labels.  Until that
contract exists, the stable result is UNSUPPORTED_FORMAT.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import unsupported_profile


def profile_sav(path: Path) -> dict[str, Any]:
    return unsupported_profile(
        path,
        format_name="SPSS SAV",
        dependency_requirement="a pinned and fixture-validated SPSS parser",
    )
