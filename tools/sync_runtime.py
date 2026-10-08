#!/usr/bin/env python3
"""Safely synchronize generated, repository-managed skill runtimes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path


PRESERVED_DIRS = {"node_modules"}
IGNORED_DIRS = {"__pycache__", ".pytest_cache"}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def runtime_file(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in PRESERVED_DIRS | IGNORED_DIRS for part in relative.parts):
        return False
    if path.suffix.lower() in {".pyc", ".pyo"}:
        return False
    if path.name.startswith("test_") and path.suffix.lower() == ".py":
        return False
    return path.is_file()


def backup(path: Path, installed: Path, backup_root: Path) -> None:
    relative = path.relative_to(installed)
    target = backup_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def sync(source: Path, installed: Path, backup_root: Path) -> dict[str, object]:
    source = source.resolve()
    installed = installed.resolve()
    backup_root = backup_root.resolve()
    if source == installed or source in installed.parents or installed in source.parents:
        raise ValueError("source, installed, and backup trees must be distinct")
    source_top = sorted(path for path in source.iterdir() if path.is_dir())
    managed = {path.name for path in source_top}
    desired: dict[str, Path] = {}
    for top in source_top:
        for path in top.rglob("*"):
            if runtime_file(path, source):
                desired[path.relative_to(source).as_posix()] = path

    installed.mkdir(parents=True, exist_ok=True)
    changed = 0
    removed = 0
    backed_up = 0
    for relative, source_path in sorted(desired.items()):
        destination = installed / relative
        if destination.is_file() and digest(destination) == digest(source_path):
            continue
        if destination.is_file():
            backup(destination, installed, backup_root)
            backed_up += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        changed += 1

    for top_name in sorted(managed):
        top = installed / top_name
        if not top.is_dir():
            continue
        for path in sorted((item for item in top.rglob("*") if item.is_file()), reverse=True):
            relative = path.relative_to(installed)
            if any(part in PRESERVED_DIRS for part in relative.parts):
                continue
            key = relative.as_posix()
            if key in desired:
                continue
            if not any(part in IGNORED_DIRS for part in relative.parts):
                backup(path, installed, backup_root)
                backed_up += 1
            path.unlink()
            removed += 1
        for directory in sorted((item for item in top.rglob("*") if item.is_dir()), reverse=True):
            if directory.name in PRESERVED_DIRS or any(
                part in PRESERVED_DIRS for part in directory.relative_to(top).parts
            ):
                continue
            try:
                directory.rmdir()
            except OSError:
                pass
    return {
        "status": "PASS",
        "managed_skills": sorted(managed),
        "runtime_files": len(desired),
        "changed": changed,
        "removed": removed,
        "backed_up": backed_up,
        "backup_root": str(backup_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("installed", type=Path)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    payload = sync(args.source, args.installed, args.backup)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Status: {payload['status']}")
        print(f"Changed: {payload['changed']}; removed: {payload['removed']}; backup: {payload['backup_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
