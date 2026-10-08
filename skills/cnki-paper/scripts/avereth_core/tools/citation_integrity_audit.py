#!/usr/bin/env python3
"""Audit the citations actually used by a final manuscript.

The audit is deliberately conservative.  It proves key-based parity when the
format exposes stable keys, checks final-source scope against the citation bank,
and verifies work identity without treating an unavailable index or a missing
DOI as evidence of fabrication.
"""

from __future__ import annotations

# CNKI-PAPER CODEX COMPAT: final-manuscript citation integrity audit

import argparse
import json
import re
import sys
import urllib.parse
import zipfile
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree


USER_AGENT = "Avereth-CitationIntegrity/6.0 (local research engine)"
FINAL_SCOPES = {"final-source", "final", "selected", "cited"}
FORBIDDEN_SCOPES = {"candidate-only", "candidate", "screened", "screening", "not-for-citation"}
DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>;,\]\)]+)", re.IGNORECASE)
FetchJSON = Callable[[str], dict | None]


@dataclass
class ReferenceEntry:
    key: str
    raw: str = ""
    title: str = ""
    author: str = ""
    year: str = ""
    doi: str = ""
    source_kind: str = "bibliography"


@dataclass
class BankRow:
    row_id: str
    aliases: set[str] = field(default_factory=set)
    scope: str = ""
    channel: str = ""
    source: str = ""
    verified: str = ""
    note: str = ""
    support_claim: str = ""
    reference: str = ""


@dataclass
class IdentityResult:
    key: str
    status: str
    note: str
    first_pass: str = ""
    second_pass: str = "not-required"


@dataclass
class AuditReport:
    manuscript: str
    status: str = "PASS"
    format: str = ""
    citation_keys: list[str] = field(default_factory=list)
    printed_reference_keys: list[str] = field(default_factory=list)
    unused_library_keys: list[str] = field(default_factory=list)
    identity: list[IdentityResult] = field(default_factory=list)
    blocking: list[str] = field(default_factory=list)
    recommended: list[str] = field(default_factory=list)
    minor: list[str] = field(default_factory=list)
    style: list[str] = field(default_factory=list)
    unresolved: list[str] = field(default_factory=list)
    coverage_notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.blocking


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", "", value).strip().casefold()


def normalize_text(value: str) -> str:
    value = re.sub(r"[{}\\]", " ", value)
    value = re.sub(r"[^\w\u3400-\u9fff]+", " ", value.casefold(), flags=re.UNICODE)
    return " ".join(value.split())


def title_similarity(left: str, right: str) -> float:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    aset, bset = set(a.split()), set(b.split())
    overlap = len(aset & bset) / max(1, len(aset | bset))
    return 0.45 * overlap + 0.55 * SequenceMatcher(None, a, b).ratio()


def first_author(value: str) -> str:
    if not value:
        return ""
    first = re.split(r"\s+and\s+|;|，", value, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    if "," in first:
        first = first.split(",", 1)[0]
    elif re.search(r"[A-Za-z]", first):
        parts = re.findall(r"[A-Za-z'’\-]+", first)
        first = parts[-1] if parts else ""
    return normalize_text(first).replace(" ", "")


def authors_match(local: str, remote: str) -> bool | None:
    a, b = first_author(local), first_author(remote)
    if not a or not b:
        return None
    # Cross-script romanisation comparisons are not safe enough to block.
    if bool(re.search(r"[\u3400-\u9fff]", a)) != bool(re.search(r"[\u3400-\u9fff]", b)):
        return None
    return a == b or SequenceMatcher(None, a, b).ratio() >= 0.85


def strip_tex_comments(text: str) -> str:
    return re.sub(r"(?<!\\)%.*", "", text)


def extract_tex_citations(text: str) -> tuple[set[str], set[str], bool]:
    text = strip_tex_comments(text)
    keys: set[str] = set()
    pattern = re.compile(
        r"\\(?!nocite\b)(?:[A-Za-z]*cite[A-Za-z]*|cite)\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^{}]+)\}",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        keys.update(normalize_key(item) for item in match.group(1).split(",") if item.strip())
    nocite_keys: set[str] = set()
    nocite_all = False
    for match in re.finditer(r"\\nocite\s*\{([^{}]+)\}", text, re.IGNORECASE):
        for item in match.group(1).split(","):
            item = item.strip()
            if item == "*":
                nocite_all = True
            elif item:
                nocite_keys.add(normalize_key(item))
    return keys, nocite_keys, nocite_all


def extract_markdown_citations(text: str) -> set[str]:
    keys: set[str] = set()
    for group in re.findall(r"\[([^\]]*@[A-Za-z0-9_.:\-]+[^\]]*)\]", text):
        keys.update(normalize_key(item) for item in re.findall(r"(?<![\w.])@([A-Za-z0-9_.:\-]+)", group))
    # An explicit bare Pandoc key is safe; e-mail-like strings are excluded.
    keys.update(normalize_key(item) for item in re.findall(r"(?<![\w.])@([A-Za-z][A-Za-z0-9_.:\-]+)", text))
    return keys


def extract_markdown_references(text: str) -> dict[str, ReferenceEntry]:
    entries: dict[str, ReferenceEntry] = {}
    for match in re.finditer(
        r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)?\[([A-Za-z0-9_.:\-]+)\](?::)?\s+(.+)$",
        text,
    ):
        key, raw = normalize_key(match.group(1)), match.group(2).strip()
        entries[key] = reference_from_raw(key, raw, "markdown")
    return entries


def extract_docx_text_and_keys(path: Path) -> tuple[str, set[str], bool]:
    keys: set[str] = set()
    chunks: list[str] = []
    unkeyed_zotero = False
    try:
        with zipfile.ZipFile(path) as archive:
            names = [
                name for name in archive.namelist()
                if name in {"word/document.xml", "word/footnotes.xml", "word/endnotes.xml"}
            ]
            for name in names:
                data = archive.read(name)
                root = ElementTree.fromstring(data)
                for node in root.iter():
                    if node.text:
                        chunks.append(node.text)
                xml_text = data.decode("utf-8", errors="ignore")
                keys.update(
                    normalize_key(item)
                    for item in re.findall(r"\bCITATION\s+([A-Za-z0-9_.:\-]+)", xml_text, re.IGNORECASE)
                )
                zotero_ids = re.findall(r'&quot;id&quot;\s*:\s*&quot;([^&]+)&quot;', xml_text)
                if zotero_ids:
                    unkeyed_zotero = True
    except (OSError, zipfile.BadZipFile, ElementTree.ParseError, KeyError) as exc:
        raise ValueError(f"cannot parse DOCX: {exc}") from exc
    return "\n".join(chunks), keys, unkeyed_zotero


def _balanced_bibtex_records(text: str) -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    start_re = re.compile(r"@(\w+)\s*([({])\s*([^,\s]+)\s*,", re.IGNORECASE)
    position = 0
    while True:
        match = start_re.search(text, position)
        if not match:
            break
        opener = match.group(2)
        closer = "}" if opener == "{" else ")"
        depth, quoted, escaped = 1, False, False
        index = match.end()
        while index < len(text) and depth:
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted and char == opener:
                depth += 1
            elif not quoted and char == closer:
                depth -= 1
            index += 1
        if depth:
            raise ValueError(f"unterminated BibTeX record: {match.group(3)}")
        records.append((match.group(1).lower(), match.group(3).strip(), text[match.end(): index - 1]))
        position = index
    return records


def _bib_field(body: str, name: str) -> str:
    match = re.search(
        rf"(?is)(?:^|,)\s*{re.escape(name)}\s*=\s*(?:\{{([^{{}}]*(?:\{{[^{{}}]*\}}[^{{}}]*)*)\}}|\"([^\"]*)\"|([^,\r\n]+))",
        body,
    )
    if not match:
        return ""
    return re.sub(r"\s+", " ", next((item for item in match.groups() if item is not None), "")).strip()


def parse_bibtex(path: Path) -> dict[str, ReferenceEntry]:
    if not path.is_file():
        raise ValueError(f"bibliography file does not exist: {path}")
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    entries: dict[str, ReferenceEntry] = {}
    for kind, original_key, body in _balanced_bibtex_records(text):
        if kind in {"comment", "preamble", "string"}:
            continue
        key = normalize_key(original_key)
        if key in entries:
            raise ValueError(f"duplicate BibTeX key: {original_key}")
        doi = _bib_field(body, "doi")
        if not doi:
            match = DOI_RE.search(body)
            doi = match.group(1) if match else ""
        entries[key] = ReferenceEntry(
            key=key,
            raw=body,
            title=_bib_field(body, "title"),
            author=_bib_field(body, "author"),
            year=_bib_field(body, "year"),
            doi=doi.rstrip("."),
            source_kind="bibtex",
        )
    return entries


def reference_from_raw(key: str, raw: str, source_kind: str) -> ReferenceEntry:
    doi_match = DOI_RE.search(raw)
    year_match = re.search(r"\b((?:19|20)\d{2})\b", raw)
    title = ""
    year_end = re.search(r"\((?:19|20)\d{2}\)\.?\s*", raw)
    if year_end:
        title = re.split(r"\.\s+(?=[A-Z\u3400-\u9fff])", raw[year_end.end():], maxsplit=1)[0]
    return ReferenceEntry(
        key=normalize_key(key), raw=raw.strip(), title=title.strip(" ."),
        author=re.split(r"\b(?:19|20)\d{2}\b", raw, maxsplit=1)[0].strip(" .,("),
        year=year_match.group(1) if year_match else "",
        doi=doi_match.group(1).rstrip(".") if doi_match else "", source_kind=source_kind,
    )


def parse_bibitems(text: str) -> dict[str, ReferenceEntry]:
    entries: dict[str, ReferenceEntry] = {}
    for match in re.finditer(
        r"\\bibitem(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\}|\Z)",
        strip_tex_comments(text), re.DOTALL,
    ):
        key = normalize_key(match.group(1))
        if key in entries:
            raise ValueError(f"duplicate \\bibitem key: {match.group(1)}")
        entries[key] = reference_from_raw(key, re.sub(r"\s+", " ", match.group(2)), "bibitem")
    return entries


def infer_bib_path(manuscript: Path, text: str) -> Path | None:
    direct = manuscript.parent / "references.bib"
    if direct.is_file():
        return direct
    match = re.search(r"\\bibliography\s*\{([^}]+)\}", text)
    if match:
        candidate = manuscript.parent / (match.group(1).split(",")[0].strip() + ".bib")
        if candidate.is_file():
            return candidate
    return None


def split_markdown_row(line: str) -> list[str]:
    placeholder = "\0PIPE\0"
    return [cell.strip().replace(placeholder, "|") for cell in line.strip().strip("|").replace(r"\|", placeholder).split("|")]


def parse_bank(path: Path) -> list[BankRow]:
    if not path.is_file():
        raise ValueError(f"citation bank does not exist: {path}")
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    rows: list[BankRow] = []
    for index in range(len(lines) - 1):
        if "|" not in lines[index] or not re.match(r"^\s*\|?\s*:?-{3,}", lines[index + 1]):
            continue
        headers = [normalize_text(cell).replace(" ", "") for cell in split_markdown_row(lines[index])]
        if not any(name in headers for name in ("candidateid", "sourceid", "id", "候选id", "来源id")):
            continue
        if not any(name in headers for name in ("referencebibtex", "reference", "bibtex", "完整参考文献")):
            continue
        cursor = index + 2
        while cursor < len(lines) and "|" in lines[cursor] and not re.match(r"^\s*#", lines[cursor]):
            cells = split_markdown_row(lines[cursor])
            cells += [""] * max(0, len(headers) - len(cells))
            record = dict(zip(headers, cells))
            reference = next((record.get(name, "") for name in ("referencebibtex", "reference", "bibtex", "完整参考文献") if record.get(name)), "")
            row_id = next((record.get(name, "") for name in ("candidateid", "sourceid", "id", "候选id", "来源id") if record.get(name)), f"row-{cursor + 1}")
            aliases = {normalize_key(row_id)}
            for name in ("citationkey", "bibtexkey", "citekey", "key"):
                if record.get(name):
                    aliases.add(normalize_key(record[name]))
            aliases.update(normalize_key(item) for item in re.findall(r"@\w+\s*[({]\s*([^,\s]+)", reference))
            rows.append(BankRow(
                row_id=row_id, aliases=aliases,
                scope=next((record.get(name, "") for name in ("citationscope", "scope", "引用范围") if record.get(name)), "").strip().casefold(),
                channel=next((record.get(name, "") for name in ("sourcechannel", "channel", "来源渠道") if record.get(name)), ""),
                source=record.get("source", "") or record.get("来源", ""),
                verified=record.get("verified", "") or record.get("已核验", ""),
                note=record.get("verificationnote", "") or record.get("核验说明", ""),
                support_claim=record.get("supportclaimsentence", "") or record.get("supportclaim", "") or record.get("支持主张", ""),
                reference=reference,
            ))
            cursor += 1
        if rows:
            break
    return rows


def _fetch_json(url: str) -> dict | None:
    try:
        request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as exc:
        return {"_http_status": exc.code}
    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return None


def _crossref_work(data: dict | None) -> dict | None:
    if not data or data.get("_http_status"):
        return None
    message = data.get("message", {})
    return message if isinstance(message, dict) else None


def _openalex_work(data: dict | None) -> dict | None:
    if not data or data.get("_http_status"):
        return None
    if isinstance(data.get("results"), list):
        return data["results"][0] if data["results"] else None
    return data if data.get("id") or data.get("title") or data.get("display_name") else None


def _remote_metadata(work: dict, provider: str) -> tuple[str, str, str]:
    if provider == "crossref":
        titles = work.get("title") or []
        title = titles[0] if isinstance(titles, list) and titles else str(titles or "")
        authors = work.get("author") or []
        author = ""
        if authors and isinstance(authors[0], dict):
            author = str(authors[0].get("family") or authors[0].get("name") or "")
        parts = (work.get("issued") or work.get("published") or {}).get("date-parts", [[""]])
        year = str(parts[0][0]) if parts and parts[0] else ""
        return title, author, year
    title = str(work.get("title") or work.get("display_name") or "")
    authorships = work.get("authorships") or []
    author = ""
    if authorships and isinstance(authorships[0], dict):
        author = str((authorships[0].get("author") or {}).get("display_name") or "")
    return title, author, str(work.get("publication_year") or "")


def _identity_verdict(entry: ReferenceEntry, work: dict, provider: str, *, doi_lookup: bool) -> tuple[str, str]:
    remote_title, remote_author, remote_year = _remote_metadata(work, provider)
    if not entry.title or not remote_title:
        return "NEEDS AUTHOR VERIFICATION", f"{provider} record lacks comparable title metadata"
    similarity = title_similarity(entry.title, remote_title)
    author_match = authors_match(entry.author, remote_author)
    if similarity < 0.78:
        label = "DOI RESOLVES TO DIFFERENT WORK" if doi_lookup else "IDENTITY MISMATCH"
        return label, f"{provider} title differs (similarity={similarity:.2f})"
    if author_match is False:
        return "IDENTITY MISMATCH", f"{provider} first author differs"
    if author_match is None:
        return "NEEDS AUTHOR VERIFICATION", f"{provider} title matches but first-author identity is not safely comparable"
    note = f"{provider} title identity matches"
    if author_match is True:
        note += "; first author matches"
    else:
        note += "; first author not safely comparable"
    if entry.year and remote_year and entry.year != remote_year:
        note += f"; year warning local={entry.year}, index={remote_year}"
    return "VERIFIED", note


def verify_identity(
    entry: ReferenceEntry,
    *,
    bank_row: BankRow | None,
    verify_online: bool,
    publication_mode: bool,
    fetcher: FetchJSON,
) -> IdentityResult:
    channel = normalize_text(bank_row.channel if bank_row else "")
    stable_source = bool(bank_row and (bank_row.source or bank_row.note) and bank_row.scope in FINAL_SCOPES)
    if "cnki" in channel or "知网" in channel:
        if stable_source:
            return IdentityResult(entry.key, "SOURCE CHAIN VERIFIED", "CNKI final-source chain retained; DOI is not required")
        return IdentityResult(entry.key, "NEEDS AUTHOR VERIFICATION", "CNKI source lacks a stable final-source verification trail")
    if not verify_online:
        if stable_source and not entry.doi:
            return IdentityResult(entry.key, "SOURCE CHAIN VERIFIED", "recorded official/database source chain retained")
        return IdentityResult(entry.key, "NOT CHECKED", "online identity verification was not requested")

    first_paths: list[str] = []
    unavailable = False
    conclusive_empty = 0
    if entry.doi:
        crossref_url = "https://api.crossref.org/works/" + urllib.parse.quote(entry.doi, safe="")
        data = fetcher(crossref_url)
        first_paths.append("Crossref DOI")
        if data is None:
            unavailable = True
        elif data.get("_http_status") == 404:
            conclusive_empty += 1
        else:
            work = _crossref_work(data)
            if work:
                status, note = _identity_verdict(entry, work, "crossref", doi_lookup=True)
                if status != "NEEDS AUTHOR VERIFICATION":
                    return IdentityResult(entry.key, status, note, ", ".join(first_paths))
        oa_url = "https://api.openalex.org/works/https://doi.org/" + urllib.parse.quote(entry.doi, safe="")
        data = fetcher(oa_url)
        first_paths.append("OpenAlex DOI")
        if data is None:
            unavailable = True
        elif data.get("_http_status") == 404:
            conclusive_empty += 1
        else:
            work = _openalex_work(data)
            if work:
                status, note = _identity_verdict(entry, work, "openalex", doi_lookup=True)
                if status != "NEEDS AUTHOR VERIFICATION":
                    return IdentityResult(entry.key, status, note, ", ".join(first_paths))

    if entry.title:
        query = urllib.parse.quote(entry.title)
        crossref_query = f"https://api.crossref.org/works?query.title={query}&rows=3"
        data = fetcher(crossref_query)
        first_paths.append("Crossref title")
        if data is None:
            unavailable = True
        else:
            items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
            matched = next((item for item in items if title_similarity(entry.title, _remote_metadata(item, "crossref")[0]) >= 0.90), None)
            if matched:
                status, note = _identity_verdict(entry, matched, "crossref", doi_lookup=False)
                if status == "VERIFIED":
                    return IdentityResult(entry.key, status, note, ", ".join(first_paths))
            elif data.get("_http_status") is None:
                conclusive_empty += 1
        oa_query = f"https://api.openalex.org/works?search={query}&per-page=5"
        data = fetcher(oa_query)
        first_paths.append("OpenAlex title")
        if data is None:
            unavailable = True
        else:
            items = data.get("results") or [] if isinstance(data, dict) else []
            matched = next((item for item in items if title_similarity(entry.title, _remote_metadata(item, "openalex")[0]) >= 0.90), None)
            if matched:
                status, note = _identity_verdict(entry, matched, "openalex", doi_lookup=False)
                if status == "VERIFIED":
                    return IdentityResult(entry.key, status, note, ", ".join(first_paths))
            elif data.get("_http_status") is None:
                conclusive_empty += 1

    first_pass = ", ".join(first_paths) or "no queryable metadata"
    if not publication_mode:
        status = "NOT CHECKED" if unavailable and not conclusive_empty else "UNRESOLVED"
        return IdentityResult(entry.key, status, "no authoritative identity match was established", first_pass)

    # Publication mode requires a differently framed, independent second pass
    # for suspect rows.  Only two completed empty responses justify the final
    # high-risk label; an unavailable service remains NOT CHECKED.
    if not entry.title:
        return IdentityResult(entry.key, "NOT CHECKED", "second pass cannot run without a title", first_pass, "incomplete")
    author_query = " ".join(item for item in (entry.author, entry.title) if item)
    q = urllib.parse.quote(author_query)
    second_urls = (
        f"https://api.openalex.org/works?filter=title.search:{urllib.parse.quote(entry.title)}&search={q}&per-page=5",
        f"https://api.crossref.org/works?query.bibliographic={q}&rows=5",
    )
    completed_empty = 0
    for url in second_urls:
        data = fetcher(url)
        if data is None or data.get("_http_status"):
            continue
        if "openalex" in url:
            items = data.get("results") or [] if isinstance(data, dict) else []
            provider = "openalex"
        else:
            items = ((data.get("message") or {}).get("items") or []) if isinstance(data, dict) else []
            provider = "crossref"
        matched = next((item for item in items if title_similarity(entry.title, _remote_metadata(item, provider)[0]) >= 0.90), None)
        if matched:
            status, note = _identity_verdict(entry, matched, provider, doi_lookup=False)
            return IdentityResult(entry.key, status, note, first_pass, f"completed via {provider}")
        completed_empty += 1
    if completed_empty == len(second_urls):
        if stable_source or (not entry.doi and bool(re.search(r"[\u3400-\u9fff]", entry.title))):
            return IdentityResult(
                entry.key,
                "NEEDS AUTHOR VERIFICATION",
                "external indexes returned no match, but a recorded primary source chain or non-DOI Chinese work must be checked through its own database/publisher; absence is not fabrication evidence",
                first_pass,
                "completed-empty",
            )
        return IdentityResult(entry.key, "LIKELY FABRICATED", "two independent query framings returned no matching work; author review required before publication", first_pass, "completed-empty")
    return IdentityResult(entry.key, "NOT CHECKED", "independent publication second pass was incomplete because an index was unavailable", first_pass, "incomplete")


def _bank_index(rows: list[BankRow]) -> tuple[dict[str, BankRow], set[str]]:
    index: dict[str, BankRow] = {}
    ambiguous: set[str] = set()
    for row in rows:
        for alias in row.aliases:
            if alias in index and index[alias].row_id != row.row_id:
                ambiguous.add(alias)
            else:
                index[alias] = row
    return index, ambiguous


def _duplicates(entries: dict[str, ReferenceEntry], used: set[str]) -> list[str]:
    seen_doi: dict[str, str] = {}
    seen_title: dict[str, str] = {}
    findings: list[str] = []
    for key in sorted(used & set(entries)):
        entry = entries[key]
        doi = entry.doi.casefold().strip()
        title = normalize_text(entry.title)
        if doi and doi in seen_doi and seen_doi[doi] != key:
            findings.append(f"duplicate DOI under keys {seen_doi[doi]} and {key}: {entry.doi}")
        elif doi:
            seen_doi[doi] = key
        if title and title in seen_title and seen_title[title] != key:
            findings.append(f"duplicate normalized title under keys {seen_title[title]} and {key}")
        elif title:
            seen_title[title] = key
    return findings


def audit(
    manuscript: Path,
    *,
    bib: Path | None = None,
    bank: Path | None = None,
    publication_mode: bool = False,
    verify_online: bool = False,
    fetcher: FetchJSON | None = None,
) -> AuditReport:
    manuscript = Path(manuscript)
    if not manuscript.is_file():
        raise ValueError(f"manuscript does not exist: {manuscript}")
    suffix = manuscript.suffix.casefold()
    report = AuditReport(str(manuscript), format=suffix.lstrip("."))
    external_bib = False
    nocite_keys: set[str] = set()
    nocite_all = False
    unkeyed_zotero = False
    if suffix == ".tex":
        text = manuscript.read_text(encoding="utf-8-sig", errors="replace")
        citations, nocite_keys, nocite_all = extract_tex_citations(text)
        entries = parse_bibitems(text)
        if bib is None:
            bib = infer_bib_path(manuscript, text)
        if bib is not None:
            entries = parse_bibtex(Path(bib))
            external_bib = True
    elif suffix in {".md", ".markdown", ".txt"}:
        text = manuscript.read_text(encoding="utf-8-sig", errors="replace")
        citations = extract_markdown_citations(text)
        entries = parse_bibtex(Path(bib)) if bib else extract_markdown_references(text)
        external_bib = bib is not None
    elif suffix == ".docx":
        text, citations, unkeyed_zotero = extract_docx_text_and_keys(manuscript)
        entries = parse_bibtex(Path(bib)) if bib else extract_markdown_references(text)
        external_bib = bib is not None
    else:
        raise ValueError(f"unsupported manuscript format: {suffix or '(none)'}")

    if unkeyed_zotero:
        report.coverage_notes.append("DOCX contains Zotero citation fields whose item IDs cannot be safely mapped without an exported bibliography; those fields remain NOT CHECKED")
    if not citations:
        report.coverage_notes.append("no stable citation keys were extracted; unkeyed author-year, numeric, or footnote citations are NOT CHECKED")
        if suffix == ".docx" or publication_mode:
            report.blocking.append("no stable in-text citation keys could be extracted for DOCX/publication-mode audit")
        elif entries:
            report.blocking.append("bibliography entries exist but no stable in-text citation keys could be mapped")

    all_entry_keys = set(entries)
    if external_bib:
        requested_printed = citations | nocite_keys
        printed = set(all_entry_keys) if nocite_all else requested_printed & all_entry_keys
        unused = all_entry_keys - printed
        report.unused_library_keys = sorted(unused)
        if unused:
            report.recommended.append(f"{len(unused)} BibTeX library entries are unused by the actual manuscript; they are reported but are not treated as printed references")
    else:
        printed = all_entry_keys

    missing = citations - all_entry_keys
    missing_nocite = nocite_keys - all_entry_keys
    orphaned = printed - citations
    if missing:
        report.blocking.append("in-text citation keys missing from the bibliography: " + ", ".join(sorted(missing)))
    if missing_nocite:
        report.blocking.append("\\nocite keys missing from the bibliography: " + ", ".join(sorted(missing_nocite)))
    if orphaned:
        report.blocking.append("printed bibliography entries not cited in the manuscript: " + ", ".join(sorted(orphaned)))
    if nocite_all:
        report.recommended.append("\\nocite{*} prints the whole library; verify that this is intentional")

    duplicate_findings = _duplicates(entries, printed)
    report.style.extend(duplicate_findings)
    report.blocking.extend(duplicate_findings)

    bank_rows = parse_bank(Path(bank)) if bank else []
    bank_index, ambiguous = _bank_index(bank_rows)
    for key in sorted(printed):
        if key in ambiguous:
            report.blocking.append(f"printed reference key {key} maps to multiple citation-bank rows")
            continue
        row = bank_index.get(key)
        if bank is not None and row is None:
            report.blocking.append(f"printed reference {key} is absent from the citation bank")
            continue
        if row is not None:
            if row.scope in FORBIDDEN_SCOPES:
                report.blocking.append(f"printed reference {key} uses forbidden scope {row.scope} ({row.row_id})")
            elif row.scope not in FINAL_SCOPES:
                report.blocking.append(f"printed reference {key} is not marked final-source ({row.row_id})")
            if not row.support_claim.strip():
                report.blocking.append(f"printed reference {key} has no support-claim sentence in the citation bank")

    fetch = fetcher or _fetch_json
    for key in sorted(printed & all_entry_keys):
        row = bank_index.get(key)
        result = verify_identity(
            entries[key], bank_row=row, verify_online=verify_online,
            publication_mode=publication_mode, fetcher=fetch,
        )
        report.identity.append(result)
        if result.status in {"DOI RESOLVES TO DIFFERENT WORK", "IDENTITY MISMATCH", "LIKELY FABRICATED"}:
            report.blocking.append(f"{key}: {result.status} — {result.note}")
        elif result.status in {"NOT CHECKED", "UNRESOLVED", "NEEDS AUTHOR VERIFICATION"}:
            report.unresolved.append(f"{key}: {result.status} — {result.note}")
            if publication_mode:
                report.blocking.append(f"{key}: publication-mode identity review is incomplete ({result.status})")

    report.citation_keys = sorted(citations)
    report.printed_reference_keys = sorted(printed)
    report.status = "PASS" if report.ok else "FAIL"
    return report


def markdown_report(report: AuditReport) -> str:
    lines = [
        "# Citation Integrity Audit", "", f"Status: {report.status}", "",
        "## Summary", "",
        f"- Manuscript: `{report.manuscript}`",
        f"- Format: `{report.format}`",
        f"- Actual citation keys: {len(report.citation_keys)}",
        f"- Actual printed/reference keys: {len(report.printed_reference_keys)}",
        f"- Unused external-library keys: {len(report.unused_library_keys)}", "",
        "## Actual Citation / Reference Parity", "",
        "| Set | Keys |", "|---|---|",
        f"| In text | {', '.join(report.citation_keys) or '-'} |",
        f"| Printed / final reference set | {', '.join(report.printed_reference_keys) or '-'} |",
        f"| Unused library only | {', '.join(report.unused_library_keys) or '-'} |", "",
        "## Source Identity and Existence", "",
        "| Key | Status | First pass | Independent second pass | Note |", "|---|---|---|---|---|",
    ]
    for item in report.identity:
        note = item.note.replace("|", "\\|")
        lines.append(f"| {item.key} | {item.status} | {item.first_pass or '-'} | {item.second_pass} | {note} |")
    if not report.identity:
        lines.append("| - | NOT CHECKED | - | - | No key-addressable reference identity was available. |")
    sections = (
        ("Claim Use and Final-Source Scope — Blocking", report.blocking),
        ("Recommended", report.recommended),
        ("Style / Duplicate Diagnostics", report.style),
        ("Minor", report.minor),
        ("Unresolved / Author Verification", report.unresolved),
        ("Coverage Notes", report.coverage_notes),
    )
    for heading, items in sections:
        lines.extend(["", f"## {heading}", ""])
        lines.extend(f"- {item}" for item in items) if items else lines.append("- None")
    lines.extend([
        "", "## Interpretation Boundary", "",
        "- A missing DOI or an absent Crossref/OpenAlex result is not, by itself, evidence that a work is fabricated.",
        "- CNKI, publisher, institutional, ISBN, archival, or local full-text chains remain valid when recorded as final-source evidence.",
        "- `LIKELY FABRICATED` is reserved for publication mode after two completed, differently framed checks return no matching work; it still requires author review.", "",
    ])
    return "\n".join(lines)


def report_output_path(manuscript: Path) -> Path:
    parent = manuscript.resolve().parent
    if parent.name.casefold() == "final_paper":
        return parent.parent / "citation_integrity_audit.md"
    for ancestor in parent.parents:
        if ancestor.name.casefold() == "paper_rewriting_output":
            return ancestor / "citation_integrity_audit.md"
    return parent / "citation_integrity_audit.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manuscript", type=Path)
    parser.add_argument("--bib", type=Path, help="BibTeX file; inferred for main.tex when possible")
    parser.add_argument("--bank", type=Path, help="citation_support_bank.md")
    parser.add_argument("--publication-mode", action="store_true", help="require an independent second pass for suspect entries")
    parser.add_argument("--verify-online", action="store_true", help="query Crossref and OpenAlex")
    parser.add_argument("--write", action="store_true", help="write citation_integrity_audit.md beside the workflow root")
    parser.add_argument("--output", type=Path, help="Explicit report path; required by the local audit runner")
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        result = audit(
            args.manuscript, bib=args.bib, bank=args.bank,
            publication_mode=args.publication_mode, verify_online=args.verify_online,
        )
    except ValueError as exc:
        if args.json:
            print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"Status: BLOCKED\n\n{exc}", file=sys.stderr)
        return 2
    rendered = markdown_report(result)
    if args.write:
        destination = args.output or report_output_path(args.manuscript)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    if args.json:
        payload = asdict(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(rendered)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
