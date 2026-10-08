"""Internal local research engine for CNKI-Paper.

The package is intentionally not a Skill.  ``cnki-paper`` remains the only
public control plane; this package owns its state, gates, receipts, audits and
delivery actions.
"""

from .models import ArtifactSpec, Finding, GateResult, GateStatus, WorkflowStatus
from .stages import LEGACY_STAGE_ALIASES, STAGES

__all__ = [
    "ArtifactSpec",
    "Finding",
    "GateResult",
    "GateStatus",
    "LEGACY_STAGE_ALIASES",
    "STAGES",
    "WorkflowStatus",
]

from .version import VERSION

__version__ = VERSION
