#!/usr/bin/env python3
"""Refresh the build-owned machine section of figure_asset_map.md."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


SKILLS_DIR = Path(__file__).resolve().parents[4]
METHOD_SCRIPTS = SKILLS_DIR / "empirical-research" / "scripts"
if str(METHOD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(METHOD_SCRIPTS))

import method_execution  # noqa: E402
from exhibits.figure_map import render_prefill, update_document  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    temporary.replace(path)


def refresh(outdir: Path, *, write: bool = False) -> str:
    config_path = outdir / "workflow_config.json"
    execution_path = outdir / "method_execution.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or config.get("workflow") != "build_from_materials":
        raise ValueError("EXHIBIT.MANUSCRIPT.MAP_NOT_APPLICABLE: figure_asset_map.md is build_from_materials-only")
    payload = json.loads(execution_path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("method_execution.json root must be an object")
    validation = method_execution.validate_payload(outdir, payload, stage="build")
    if validation.errors:
        detail = "; ".join(f"{item.code}@{item.path}" for item in validation.errors)
        raise ValueError("EXHIBIT.MANUSCRIPT.EXECUTION_BLOCKED: " + detail)
    rendered_section = render_prefill(payload, execution_sha256=_sha256(execution_path))
    map_path = outdir / "figure_asset_map.md"
    if map_path.is_file():
        with map_path.open("r", encoding="utf-8", newline="") as handle:
            existing = handle.read()
    else:
        existing = ""
    rendered = update_document(existing, rendered_section)
    if write:
        _atomic_text(map_path, rendered)
    return rendered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outdir", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    try:
        rendered = refresh(args.outdir, write=args.write)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.write:
        print(f"wrote {args.outdir / 'figure_asset_map.md'}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
