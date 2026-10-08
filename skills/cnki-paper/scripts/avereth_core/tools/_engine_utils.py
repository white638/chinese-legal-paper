#!/usr/bin/env python3
"""Shared text and Markdown helpers for Avereth's local audit tools."""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


def read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def strip_tex_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        cut = None
        for match in re.finditer(r"(?<!\\)%", line):
            cut = match.start()
            break
        lines.append(line if cut is None else line[:cut])
    return "\n".join(lines)


def normalize_tex(text: str) -> str:
    text = strip_tex_comments(text)
    text = re.sub(r"\\(section|subsection|subsubsection)\*?\{([^{}]*)\}", r"\n\n\2\n\n", text)
    text = re.sub(r"\\(caption|label|includegraphics)(?:\[[^\]]*\])?\{[^{}]*\}", " ", text)
    text = re.sub(r"\\(cite\w*|ref|autoref|cref|Cref|eqref)\*?(?:\[[^\]]*\]){0,2}\{([^{}]*)\}", " [REF] ", text)
    text = re.sub(r"\\begin\{(figure|figure\*|table|table\*|equation|align|align\*)\}.*?\\end\{\1\}", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}]", " ", text)
    return text


def normalize_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"`[^`]*`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    return re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)


def split_paragraphs(text: str) -> list[str]:
    paragraphs: list[str] = []
    for part in re.split(r"\n\s*\n+", text):
        cleaned = re.sub(r"\s+", " ", part).strip()
        word_count = len(re.findall(r"[A-Za-z]+|\d+(?:\.\d+)?", cleaned))
        if word_count >= 8:
            paragraphs.append(cleaned)
    return paragraphs


@dataclass
class CanonParagraph:
    text: str
    canonical_text: str
    tokens: set[str]


def canonical(paragraph: str) -> str:
    paragraph = paragraph.lower()
    paragraph = re.sub(r"\[[^\]]+\]", " ", paragraph)
    paragraph = re.sub(r"[^a-z0-9]+", " ", paragraph)
    return re.sub(r"\s+", " ", paragraph).strip()


def make_canon(paragraph: str) -> CanonParagraph:
    text = canonical(paragraph)
    return CanonParagraph(text=paragraph, canonical_text=text, tokens=set(text.split()))


def similarity_canon(a: CanonParagraph, b: CanonParagraph) -> float:
    ca = a.canonical_text
    cb = b.canonical_text
    if not ca or not cb:
        return 0.0
    seq_score = SequenceMatcher(None, ca, cb).ratio()
    jaccard = len(a.tokens & b.tokens) / len(a.tokens | b.tokens) if a.tokens or b.tokens else 0.0
    return round((seq_score * 0.65) + (jaccard * 0.35), 4)


def preview(text: str, limit: int = 180) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def split_table_line(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_separator_row(cells: list[str]) -> bool:
    return bool(cells) and all(cell and set(cell) <= {"-", ":", " "} for cell in cells)


def table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = split_table_line(line)
        if not is_separator_row(cells):
            rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def markdown_tables(text: str) -> list[list[list[str]]]:
    tables: list[list[list[str]]] = []
    current: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("|") and line.endswith("|"):
            cells = split_table_line(line)
            if not is_separator_row(cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    if current:
        tables.append(current)
    return tables


def year_from_row(row: list[str]) -> int | None:
    years = [int(value) for value in re.findall(r"\b(19\d{2}|20\d{2})\b", " ".join(row))]
    return max(years) if years else None
