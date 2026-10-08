"""Canonical receipt names and conservative legacy lookup."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AUDIT_SCHEMA = "avereth-audit-receipt/v1"
OUTPUT_SCHEMA = "avereth-output-receipt/v1"
AUDIT_REL = Path("audit_receipt.json")
AUDIT_MD_REL = Path("audit_receipt.md")
OUTPUT_REL = Path("output_receipt.json")
OUTPUT_MD_REL = Path("output_receipt.md")
STATUS_REL = Path("workflow_status.json")
STATUS_MD_REL = Path("workflow_status.md")

LEGACY_AUDIT_REL = Path("cnki_paperspine_audit_gate.json")
LEGACY_AUDIT_MD_REL = Path("cnki_paperspine_audit_gate.md")
LEGACY_OUTPUT_REL = Path("cnki_paperspine_output_gate.json")
LEGACY_OUTPUT_MD_REL = Path("cnki_paperspine_output_gate.md")
LEGACY_STATUS_REL = Path("cnki_paperspine_status.json")
LEGACY_STATUS_MD_REL = Path("cnki_paperspine_status.md")


@dataclass(frozen=True)
class ReceiptRead:
    payload: dict[str, Any]
    path: Path | None
    legacy: bool = False


def read_receipt(outdir: Path, kind: str) -> ReceiptRead:
    if kind not in {"audit", "output"}:
        raise ValueError(f"unsupported receipt kind: {kind}")
    current = AUDIT_REL if kind == "audit" else OUTPUT_REL
    legacy = LEGACY_AUDIT_REL if kind == "audit" else LEGACY_OUTPUT_REL
    for relative, is_legacy in ((current, False), (legacy, True)):
        path = outdir / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return ReceiptRead({}, path, is_legacy)
        return ReceiptRead(payload if isinstance(payload, dict) else {}, path, is_legacy)
    return ReceiptRead({}, None, False)


def is_legacy_gate_view(relative: str) -> bool:
    """Return whether a path belongs to the retired receipt-view namespace."""

    return relative.startswith("cnki_paperspine_gate_")
