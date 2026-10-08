"""Build one compact feasibility card for an already obtained data file.

This is deliberately not a catalog, crawler, matcher, or source registry. It
profiles one file selected for a quantitative task and returns only bounded
metadata, aggregate diagnostics, and a content identity. Raw rows and local
paths never enter the card.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .probe_adapters import profile_path
except ImportError:
    if __package__:
        raise
    from probe_adapters import profile_path


SCHEMA_VERSION = "avereth-quantitative-data-check/v1"
ACCESS_ROUTES = {
    "local_file",
    "public_download",
    "public_api",
    "registration",
    "application",
    "institutional_subscription",
    "commercial",
    "unavailable",
    "unknown",
}


def _identity(path: Path, metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        int(metadata.st_dev),
        int(metadata.st_ino),
        int(metadata.st_size),
        int(metadata.st_mtime_ns),
    )


def _stable_sha256(path: Path, expected: tuple[int, int, int, int]) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        before = _identity(path, os.fstat(handle.fileno()))
        if before != expected:
            raise OSError("data file changed before hashing")
        while block := handle.read(1024 * 1024):
            digest.update(block)
        after = _identity(path, os.fstat(handle.fileno()))
    if after != before or _identity(path, path.stat()) != before:
        raise OSError("data file changed during hashing")
    return digest.hexdigest()


def _messages(items: Any) -> list[str]:
    messages: list[str] = []
    if not isinstance(items, list):
        return messages
    for item in items:
        if isinstance(item, dict):
            code = str(item.get("code") or "CHECK").strip()
            message = str(item.get("message") or "").strip()
            value = f"{code}: {message}" if message else code
        else:
            value = str(item).strip()
        if value and value not in messages:
            messages.append(value)
    return messages


def _required_variable_records(
    required_variables: Iterable[str], observed_variables: Iterable[str]
) -> list[dict[str, str]]:
    observed = {str(item).strip().casefold(): str(item).strip() for item in observed_variables}
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in required_variables:
        name = str(item).strip()
        key = name.casefold()
        if not name or key in seen:
            continue
        seen.add(key)
        records.append(
            {
                "name": name,
                "status": "observed" if key in observed else "missing",
            }
        )
    return records


def build_data_feasibility_card(
    path: Path,
    *,
    source_name: str,
    access_route: str = "local_file",
    official_or_user_source: str = "user",
    required_variables: Sequence[str] = (),
    unit_of_analysis: str = "",
    temporal_coverage: str = "",
    spatial_coverage: str = "",
    variation_or_identification_requirements: str = "",
    linkage_or_panel_requirements: str = "",
    legal_ethics_and_license: str = "",
    row_limit: int = 1000,
    key_fields: Sequence[str] = (),
    survey: bool = False,
    header_confirmed: bool = False,
) -> dict[str, Any]:
    """Return one evidence-bounded feasibility card without persisting state."""

    route = str(access_route).strip().casefold()
    if route not in ACCESS_ROUTES:
        raise ValueError(f"unsupported access_route: {access_route}")
    path = Path(path)
    risks: list[str] = []
    file_sha256 = ""
    expected_identity: tuple[int, int, int, int] | None = None
    try:
        if path.is_file():
            expected_identity = _identity(path, path.stat())
    except OSError:
        expected_identity = None

    profile = profile_path(
        path,
        row_limit=row_limit,
        key_fields=key_fields,
        survey=survey,
        header_confirmed=header_confirmed,
    )
    risks.extend(_messages(profile.get("errors")))
    risks.extend(_messages(profile.get("warnings")))

    if expected_identity is not None:
        try:
            if _identity(path, path.stat()) != expected_identity:
                raise OSError("data file changed during profiling")
            file_sha256 = _stable_sha256(path, expected_identity)
        except OSError:
            risks.append("FILE_IDENTITY_CHANGED: reacquire and re-run the probe")

    observed_names = [
        str(item.get("name") or "").strip()
        for item in profile.get("variables") or []
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    ]
    variable_records = _required_variable_records(required_variables, observed_names)
    missing = [item["name"] for item in variable_records if item["status"] == "missing"]
    if missing:
        risks.append("REQUIRED_VARIABLES_MISSING: " + ", ".join(missing))

    parse_pass = str(profile.get("parse_status") or "").upper() == "PASS"
    observed_rows = int(profile.get("observed_rows") or 0)
    if not parse_pass or not file_sha256 or missing:
        status = "unverified"
    elif variable_records and observed_rows > 0:
        status = "sample_verified"
    else:
        status = "metadata_verified"

    if status == "unverified":
        next_test = "obtain a readable sample and verify the required fields"
    elif not variable_records:
        next_test = "state the required variables and verify them against the codebook or sample"
    elif linkage_or_panel_requirements and not key_fields:
        next_test = "name the linkage keys and test uniqueness and coverage on the obtained sample"
    else:
        next_test = "verify design-specific variation, linkage, and inference requirements before execution"

    risks = list(dict.fromkeys(item for item in risks if item))
    source_record = {
        "name": str(source_name).strip() or path.name or "unnamed source",
        "access_route": route,
        "official_or_user_source": str(official_or_user_source).strip() or "unknown",
        "verification_status": status,
        "format": str(profile.get("format") or "unknown"),
        "file_sha256": file_sha256 or None,
        "file_size_bytes": profile.get("file_size_bytes"),
        "file_row_count": profile.get("file_row_count"),
        "observed_rows": observed_rows,
        "column_count": int(profile.get("column_count") or 0),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "data_feasibility": {
            "status": status,
            "candidate_sources": [source_record],
            "unit_of_analysis": str(unit_of_analysis).strip(),
            "temporal_and_spatial_coverage": {
                "temporal": str(temporal_coverage).strip(),
                "spatial": str(spatial_coverage).strip(),
            },
            "required_variables": variable_records,
            "variation_or_identification_requirements": str(
                variation_or_identification_requirements
            ).strip(),
            "linkage_or_panel_requirements": str(linkage_or_panel_requirements).strip(),
            "legal_ethics_and_license": str(legal_ethics_and_license).strip(),
            "main_risks": risks,
            "next_cheapest_verification": next_test,
            "claim_boundary": (
                "metadata_verified and sample_verified do not establish design feasibility; "
                "ready requires design-specific validation and actual execution evidence"
            ),
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a compact data feasibility card for one obtained file."
    )
    parser.add_argument("path", type=Path)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--access-route", choices=sorted(ACCESS_ROUTES), default="local_file")
    parser.add_argument("--official-or-user-source", default="user")
    parser.add_argument("--required-variable", action="append", default=[])
    parser.add_argument("--unit-of-analysis", default="")
    parser.add_argument("--temporal-coverage", default="")
    parser.add_argument("--spatial-coverage", default="")
    parser.add_argument("--variation-or-identification-requirements", default="")
    parser.add_argument("--linkage-or-panel-requirements", default="")
    parser.add_argument("--legal-ethics-and-license", default="")
    parser.add_argument("--row-limit", type=int, default=1000)
    parser.add_argument("--key-field", action="append", default=[])
    parser.add_argument("--survey", action="store_true")
    parser.add_argument("--header-confirmed", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    card = build_data_feasibility_card(
        args.path,
        source_name=args.source_name,
        access_route=args.access_route,
        official_or_user_source=args.official_or_user_source,
        required_variables=args.required_variable,
        unit_of_analysis=args.unit_of_analysis,
        temporal_coverage=args.temporal_coverage,
        spatial_coverage=args.spatial_coverage,
        variation_or_identification_requirements=args.variation_or_identification_requirements,
        linkage_or_panel_requirements=args.linkage_or_panel_requirements,
        legal_ethics_and_license=args.legal_ethics_and_license,
        row_limit=args.row_limit,
        key_fields=args.key_field,
        survey=args.survey,
        header_confirmed=args.header_confirmed,
    )
    print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0 if card["data_feasibility"]["status"] != "unverified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
