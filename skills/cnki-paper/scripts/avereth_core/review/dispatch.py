"""Resolve the bundled structured-review implementation."""

from pathlib import Path


def script_path() -> Path:
    return Path(__file__).resolve().parents[1] / "tools" / "structured_review.py"
