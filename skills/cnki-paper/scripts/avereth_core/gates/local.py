"""Local artifact gate without a parallel state machine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import GateResult
from ..stages import inspect_stage


def gate(outdir: Path, stage: str, config: dict[str, Any] | None = None) -> GateResult:
    return inspect_stage(outdir, stage, config)
