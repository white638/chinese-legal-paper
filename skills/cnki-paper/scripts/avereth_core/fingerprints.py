"""Stable semantic fingerprints used by v6 receipts."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .artifacts import semantic_digest


def fingerprint(outdir: Path, relatives: Iterable[str]) -> str:
    return semantic_digest(outdir, relatives)
