#!/usr/bin/env python3
"""Compare source and installed skill runtime trees by SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

try:
    from .legacy_runtime_retirement import retired_top_levels
except ImportError:  # Direct script execution puts tools/ on sys.path.
    from legacy_runtime_retirement import retired_top_levels


EXCLUDED_DIRS = {"__pycache__", ".pytest_cache", "node_modules"}


def is_runtime_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in {".pyc", ".pyo"}:
        return False
    if path.name.startswith("test_") and path.suffix.lower() == ".py":
        return False
    return path.is_file()


def digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def inventory(root: Path, *, top_levels: set[str] | None = None) -> dict[str, str]:
    if not root.is_dir():
        return {}
    return {
        path.relative_to(root).as_posix(): digest_file(path)
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if is_runtime_file(path, root)
        and (
            top_levels is None
            or (path.relative_to(root).parts and path.relative_to(root).parts[0] in top_levels)
        )
    }


def forbidden_runtime_files(root: Path, *, top_levels: set[str]) -> list[str]:
    """Find repository-only tests or caches accidentally shipped into managed skills."""
    if not root.is_dir():
        return []
    forbidden: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] not in top_levels:
            continue
        if "node_modules" in relative.parts:
            continue
        if any(part in {"__pycache__", ".pytest_cache"} for part in relative.parts):
            forbidden.add(relative.as_posix())
        elif path.is_file() and (
            (path.name.startswith("test_") and path.suffix.lower() == ".py")
            or path.suffix.lower() in {".pyc", ".pyo"}
        ):
            forbidden.add(relative.as_posix())
    return sorted(forbidden)


def compare(source: Path, installed: Path) -> dict[str, object]:
    source_files = inventory(source)
    managed_top_levels = {path.name for path in source.iterdir() if path.is_dir()} if source.is_dir() else set()
    installed_files = inventory(installed, top_levels=managed_top_levels)
    forbidden = forbidden_runtime_files(installed, top_levels=managed_top_levels)
    missing = sorted(source_files.keys() - installed_files.keys())
    extra = sorted(installed_files.keys() - source_files.keys())
    mismatch = sorted(
        relative
        for relative in source_files.keys() & installed_files.keys()
        if source_files[relative] != installed_files[relative]
    )
    retired = retired_top_levels(installed)
    return {
        "status": "PASS" if not (missing or extra or mismatch or forbidden or retired) else "FAIL",
        "source_files": len(source_files),
        "installed_files": len(installed_files),
        "missing": missing,
        "extra": extra,
        "mismatch": mismatch,
        "forbidden": forbidden,
        "retired": retired,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Repository skills directory")
    parser.add_argument("installed", type=Path, help="Installed skills directory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    payload = compare(args.source.resolve(), args.installed.resolve())
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("# Runtime Parity")
        print()
        print(f"Status: {payload['status']}")
        print(f"- source_files: {payload['source_files']}")
        print(f"- installed_files: {payload['installed_files']}")
        for label in ("missing", "extra", "mismatch", "forbidden", "retired"):
            values = payload[label]
            print(f"- {label}: {len(values)}")
            for relative in values[:20]:
                print(f"  - {relative}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
