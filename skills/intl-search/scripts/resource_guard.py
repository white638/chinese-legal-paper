"""Hard resource-fuse adapter shared by international retrieval commands."""

from __future__ import annotations

import sys
from pathlib import Path


def require_resource_authorization(
    workspace: Path | None,
    action: str,
    *,
    question_committed: bool = False,
) -> None:
    if workspace is None:
        raise RuntimeError(
            f"{action} requires --workspace so the F2 resource fuse can be checked"
        )
    skills_root = Path(__file__).resolve().parents[2]
    controller_scripts = skills_root / "cnki-paper" / "scripts"
    if str(controller_scripts) not in sys.path:
        sys.path.insert(0, str(controller_scripts))
    from research_feasibility import authorize_action

    report = authorize_action(
        workspace.resolve(),
        action,
        question_committed=question_committed,
    )
    if report.get("status") != "PASS":
        raise RuntimeError(
            f"resource fuse blocked {action}: {report.get('reason') or 'F2 feasibility has not passed'}"
        )
