"""Optional domain checks; no additional workflow states or receipts."""
from __future__ import annotations

from pathlib import Path
import sys

from ..config import read_config
from ..workflow_registry import ARTIFACT_DEFINITIONS, STAGE_ORDER, TASK_PROFILE_TERMINALS

LEGAL_BRIDGE_VERSION = 1


def _active(outdir, config):
    return ("legal_profile" in config or any(
        (Path(outdir) / row.path).exists()
        for row in ARTIFACT_DEFINITIONS if row.domain_profile == "chinese-law-v1"))


def _module():
    scripts = Path(__file__).resolve().parents[4] / "chinese-legal-paper" / "scripts"
    if not (scripts / "legal_core" / "validation.py").is_file():
        raise ImportError("chinese-legal-paper runtime is missing")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from legal_core import validation
    return validation


def checks(outdir, stage, config=None):
    config = read_config(Path(outdir)).payload if config is None else config
    if not _active(outdir, config):
        return {"status": "NOT_APPLICABLE", "issues": []}
    try:
        return _module().check_workspace(outdir, stage=stage, config=config)
    except (ImportError, OSError, ValueError) as exc:
        return {"status": "FAIL", "issues": [{
            "stage": "intake", "code": "LEGAL.RUNTIME_UNAVAILABLE",
            "message": f"Legal checks unavailable ({type(exc).__name__}); reinstall matching runtime",
            "artifact": "workflow_config.json", "severity": "error",
        }]}


def apply_status(payload, outdir):
    next_stage = payload.get("next_stage", "intake")
    if next_stage not in {*STAGE_ORDER, "complete"}:
        return
    config = read_config(Path(outdir)).payload
    terminal = TASK_PROFILE_TERMINALS.get(config.get("task_profile"), "output")
    declared_terminal = payload.get("terminal_stage")
    if declared_terminal in STAGE_ORDER and STAGE_ORDER.index(declared_terminal) < STAGE_ORDER.index(terminal):
        terminal = declared_terminal
    limit = terminal if next_stage == "complete" else next_stage
    result = checks(outdir, limit, config)
    if result["status"] == "NOT_APPLICABLE":
        return
    payload["legal_checks"] = result
    if result["issues"]:
        earliest = min(result["issues"], key=lambda issue: STAGE_ORDER.index(issue["stage"]))["stage"]
        payload.update(next_stage=earliest, next_checkpoint="legal_contract", is_complete=False,
                       audit_gate="pending", output_gate="pending")


def receipt_paths(outdir):
    if not _active(outdir, read_config(Path(outdir)).payload):
        return []
    try:
        return _module().receipt_paths(outdir)
    except (ImportError, OSError, ValueError):
        # The always-bound metadata remains in the manifest. Gates fail closed.
        return []
