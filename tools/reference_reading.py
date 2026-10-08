"""Read exact Markdown sections for reference-scope checks and byte accounting."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


def section_text(text: str, sections: list[str] | tuple[str, ...]) -> str:
    if not sections:
        return text
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, int, str]] = []
    fence = ""
    for index, line in enumerate(lines):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            continue
        if fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            headings.append((index, len(heading.group(1)), heading.group(2)))
    selected: set[int] = set()
    for name in sections:
        matches = [(offset, row) for offset, row in enumerate(headings) if row[2] == name]
        if len(matches) != 1:
            raise ValueError(f"reference section must resolve exactly once: {name!r}")
        offset, (start, level, _) = matches[0]
        end = next((row[0] for row in headings[offset + 1:] if row[1] <= level), len(lines))
        selected.update(range(start, end))
    return "".join(lines[index] for index in sorted(selected))


def reading_metrics(skills_dir: Path, requests: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for request in requests:
        path = skills_dir / request["path"]
        text = path.read_text(encoding="utf-8-sig")
        content = section_text(text, request["sections"])
        entries.append({
            **request,
            "file_bytes": path.stat().st_size,
            "selected_utf8_bytes": len(content.encode("utf-8")),
        })
    return {
        "measurement": "planned_reference_sections_not_model_tokens",
        "files": len(entries),
        "selected_utf8_bytes": sum(item["selected_utf8_bytes"] for item in entries),
        "entries": entries,
    }
