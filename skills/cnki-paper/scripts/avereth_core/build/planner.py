"""Return the v6 build artifact contract for the active workflow."""

from __future__ import annotations

from typing import Any

from ..models import ArtifactSpec
from ..stages import stage_specs


def required_artifacts(config: dict[str, Any] | None = None) -> tuple[ArtifactSpec, ...]:
    return stage_specs("build", config)
