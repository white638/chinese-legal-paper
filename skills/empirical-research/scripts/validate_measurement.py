#!/usr/bin/env python3
"""Run the artifact validator and retain only text-measurement findings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from validate_method_artifacts import validate_workspace


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    findings = [
        item for item in validate_workspace(args.path) if item.code.startswith("ME.MEASUREMENT.")
    ]
    payload = {
        "status": "FAIL" if any(item.severity == "ERROR" for item in findings) else "PASS",
        "quality_score": None,
        "findings": [item.__dict__ for item in findings],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
