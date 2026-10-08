"""Read-only page-evidence bindings to the existing source registry."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

BASE_COLUMNS = ("Evidence ID", "Work (Edition-locked)", "Locator", "Quote Snippet",
                "Tier", "Evidence Source", "Evidence File", "Status")
BINDING_COLUMNS = ("Source ID", "Source Record SHA256", "Artifact SHA256",
                   "Locator Kind", "PDF Pages", "Page Basis", "Raw Span")
KEYS = ("id", "work", "locator", "quote", "tier", "source", "file", "status",
        "source_id", "source_record_sha256", "artifact_sha256", "locator_kind",
        "pdf_pages", "page_basis", "raw_span")


def digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
    except OSError:
        return ""


def source_digest(source: dict) -> str:
    return hashlib.sha256(json.dumps(source, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def meaningful(value: object) -> bool:
    return isinstance(value, str) and value.strip() not in {"", "-", "VERIFY", "unknown"}


def strict_text(text: str) -> str:
    # Compatibility normalization would erase distinctions such as x² and x2.
    text = unicodedata.normalize("NFC", text)
    text = "".join(chr(ord(c) - 0xFEE0) if 0xFF01 <= ord(c) <= 0xFF5E else c for c in text)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"(?<=[\u3400-\u9fff]) (?=[\u3400-\u9fff])", "", text)


def cell(value: object) -> str:
    return str(value).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def parse_evidence(text: str) -> list[dict]:
    section = re.search(r"^#{2,4}\s*(?:Page Evidence|页码证据)\s*$", text, re.M | re.I)
    if not section:
        return []
    rows, header = [], list(BASE_COLUMNS)
    for line in text[section.end():].splitlines():
        line = line.strip()
        if line.startswith("#"):
            break
        if not line.startswith("|"):
            continue
        cells = [c.strip().replace("&#124;", "|") for c in line.strip("|").split("|")]
        if cells[0] == "Evidence ID":
            header = cells
            continue
        if not cells[0] or set(cells[0]) <= {"-", " ", ":"}:
            continue
        values = dict(zip(header, cells))
        row = {key: values.get(column, "") for key, column in zip(KEYS, (*BASE_COLUMNS, *BINDING_COLUMNS))}
        row["tier"] = row["tier"].upper()
        row["pages"] = locator_ranges(row["locator"])
        rows.append(row)
    return rows


def locator_ranges(text: str) -> list[tuple[int, int]]:
    matches = re.findall(r"(?:第\s*|\bpp?\.\s*)(\d+)(?:\s*[-–—至]\s*(\d+))?", text)
    return [(int(a), int(b or a)) for a, b in matches if int(b or a) >= int(a)]


def local_path(root: Path, raw: str) -> Path | None:
    if not meaningful(raw):
        return None
    path = (root / raw.replace("\\", "/")).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def load_sources(root: Path, registry: Path | None = None) -> list[dict]:
    path = registry or root / "reference_materials/literature_registry.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), list):
        raise ValueError("source registry must contain a sources array")
    return [source for source in data["sources"] if isinstance(source, dict)]


def source_keys(source: dict) -> list[str]:
    link = source.get("zotero_link") or {}
    return [str(v) for v in (source.get("source_id"), source.get("citation_key"),
                            link.get("citation_key") if isinstance(link, dict) else None) if v]


def token_present(text: str, token: str) -> bool:
    return bool(token and re.search(r"(?<![\w.-])" + re.escape(token) + r"(?![\w.-])", text))


def work_matches(text: str, source: dict) -> bool:
    metadata = source.get("metadata") or {}
    identity = source.get("identity") or {}
    if not isinstance(metadata, dict) or not isinstance(identity, dict):
        return False
    fields = [source.get("title"), source.get("publication_year") or source.get("year") or metadata.get("year")]
    if not all(fields):
        return False
    fields.extend(source.get(k) or identity.get(k) or metadata.get(k) for k in ("publisher", "edition", "isbn"))
    normalized = strict_text(text)
    return all((bool(re.search(r"(?<!\d)" + re.escape(str(value)) + r"(?!\d)", normalized))
                if str(value).isdigit() else token_present(normalized, strict_text(str(value))))
               for value in fields if value)


def bind_source(row: dict, sources: list[dict]) -> dict | None:
    key = row.get("source_id", "")
    matches = [s for s in sources if (key in source_keys(s) if meaningful(key) else work_matches(row.get("work", ""), s))]
    return matches[0] if len(matches) == 1 else None


def artifact_inputs(root: Path) -> list[dict]:
    bank = root / "evidence_bank.md"
    rows = parse_evidence(bank.read_text(encoding="utf-8-sig")) if bank.is_file() else []
    try:
        sources = load_sources(root)
    except (ValueError, OSError):
        sources = []
    paths = set()
    for row in rows:
        source = bind_source(row, sources)
        raw_paths = [row.get("file", "")]
        if source:
            raw_paths.append(str(source.get("local_file") or ""))
        if row.get("tier") == "B":
            raw_paths.append(row.get("source", "").split("#", 1)[0])
        for raw in raw_paths:
            if meaningful(raw) and not re.match(r"https?://", raw):
                paths.add(raw)
    result = []
    for raw in sorted(paths):
        target = local_path(root, raw)
        result.append({"path": raw, "sha256": digest(target) if target else "",
                       "state": "present" if target and target.is_file() else "missing_or_outside"})
    return result
