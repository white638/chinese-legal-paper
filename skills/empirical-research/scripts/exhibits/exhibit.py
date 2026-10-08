#!/usr/bin/env python3
"""Validate empirical exhibits, render a bundle, or emit a three-line table projection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
METHOD_SCRIPTS = SCRIPT_DIR.parent
if str(METHOD_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(METHOD_SCRIPTS))

import method_execution  # noqa: E402
from exhibits.render_bundle import render  # noqa: E402
from exhibits.table_emit import TABLE_FORMATS, emit as emit_table  # noqa: E402


def _load_execution(outdir: Path) -> dict:
    path = outdir / "method_execution.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("method_execution.json root must be an object")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("outdir", type=Path)
    validate_parser.add_argument("--json", action="store_true")
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--spec", required=True, type=Path)
    render_parser.add_argument("--data", required=True, type=Path)
    render_parser.add_argument("--out", required=True, type=Path)
    render_parser.add_argument("--environment-id", required=True)
    render_parser.add_argument("--rscript")
    table_parser = subparsers.add_parser("table")
    table_parser.add_argument("--spec", required=True, type=Path)
    table_parser.add_argument("--data", required=True, type=Path)
    table_parser.add_argument("--out", required=True, type=Path)
    table_parser.add_argument("--format", choices=TABLE_FORMATS, default="md")
    table_parser.add_argument("--digits", type=int, default=3)
    args = parser.parse_args(argv)

    if args.command == "table":
        try:
            report = emit_table(args.spec, args.data, args.out, fmt=args.format, digits=args.digits)
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if args.command == "render":
        try:
            manifest = render(
                args.spec,
                args.data,
                args.out,
                args.environment_id,
                args.rscript,
            )
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            print(str(exc), file=sys.stderr)
            return 3
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    try:
        payload = _load_execution(args.outdir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"EXHIBIT.FILE.INVALID: {exc}", file=sys.stderr)
        return 2
    validation = method_execution.validate_payload(args.outdir, payload)
    exhibit_issues = [item for item in validation.issues if item.code.startswith("EXHIBIT.")]
    if args.command == "validate":
        blocking_issues = [item for item in validation.errors if not item.code.startswith("EXHIBIT.")]
        response = {
            "status": "PASS" if not validation.errors else "FAIL",
            "exhibit_issues": [item.__dict__ for item in exhibit_issues],
            "blocking_issues": [item.__dict__ for item in blocking_issues],
        }
        if args.json:
            print(json.dumps(response, ensure_ascii=False, indent=2))
        else:
            print(f"Empirical exhibit validation: {response['status']}")
            for issue in [*exhibit_issues, *blocking_issues]:
                print(f"- {issue.code} [{issue.path}]: {issue.message}")
        return 0 if response["status"] == "PASS" else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
