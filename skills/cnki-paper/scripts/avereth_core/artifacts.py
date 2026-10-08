"""Artifact identity and lightweight report checks."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable


STATUS_LINE_RE = re.compile(
    r"^[ \t]*(?:[-*+][ \t]+)?(?:Status|Result|Conclusion|Overall|Outcome)[ \t]*:[ \t]*(.*?)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)


def meaningful_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def report_passed(path: Path) -> bool:
    """Return true only for a readable report with one unambiguous PASS.

    Hard audit reports are contracts, not best-effort prose.  Missing, empty,
    undecodable, contradictory, pending, or unknown reports therefore fail
    closed.
    """

    if not meaningful_file(path):
        return False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeError:
        try:
            text = path.read_text(encoding="utf-16")
        except (OSError, UnicodeError):
            return False
    except OSError:
        return False
    text = re.sub(r"```[^\n]*\n[\s\S]*?```", "", text)
    preamble_match = re.search(r"(?m)^##\s+", text)
    preamble = text[: preamble_match.start()] if preamble_match else text

    def values(block: str) -> list[str]:
        return [
            re.sub(r"^[*_`]+|[*_`]+$", "", value.strip()).upper()
            for value in STATUS_LINE_RE.findall(block)
        ]

    top_level = values(preamble)
    all_values = values(text)
    return top_level == ["PASS"] and bool(all_values) and all(value == "PASS" for value in all_values)


def report_failed(path: Path) -> bool:
    """Compatibility inverse used by older callers."""

    return not report_passed(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_digest(outdir: Path, relatives: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(relatives)):
        path = outdir / relative
        if not meaningful_file(path):
            continue
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
