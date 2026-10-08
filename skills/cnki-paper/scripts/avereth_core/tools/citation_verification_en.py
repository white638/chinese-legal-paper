#!/usr/bin/env python3
"""Verify English citations in citation_support_bank.md against Crossref API.

Self-contained — standard library only.  Queries the public Crossref REST API
(no key required) to confirm that each candidate citation resolves to a real
published work.

Crossref is an enhancement, not a hard dependency.  When the API is unreachable
citations are marked SKIPPED rather than failing the check.

Use ``--delay`` to throttle requests (in seconds) to be polite to the
Crossref API; ``--no-api`` skips network access entirely.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

CROSSREF_QUERY_URL = "https://api.crossref.org/works"
USER_AGENT = "Avereth/6.0 (citation-en; local research engine)"

# Title similarity threshold for a "matched" verdict
MIN_TITLE_SIMILARITY = 0.6
YEAR_TOLERANCE = 1  # ±1 year
# CNKI-PAPER CITATION-IDENTITY COMPAT: DOI resolution is not identity confirmation
FINAL_CITATION_SCOPES = {"final-source", "final", "selected", "cited"}
CANDIDATE_CITATION_SCOPES = {"candidate-only", "candidate", "screened", "not-for-citation"}


# ---------------------------------------------------------------------------
# table helpers (self-contained, same idiom as humanize_check.py)
# ---------------------------------------------------------------------------

def _split_table_line(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _is_sep(cells: list[str]) -> bool:
    return bool(cells) and all(c and set(c) <= {"-", ":", " "} for c in cells)


def _table_rows(text: str) -> tuple[list[str], list[list[str]]]:
    rows: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = _split_table_line(line)
        if _is_sep(cells):
            continue
        rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def _col_index(header: list[str], *names: str) -> int | None:
    """Return the 0-based index of the first header cell matching any name."""
    lower = [h.lower() for h in header]
    for name in names:
        for idx, h in enumerate(lower):
            if name.lower() in h:
                return idx
    return None


# ---------------------------------------------------------------------------
# metadata extraction from reference text
# ---------------------------------------------------------------------------

def _extract_doi(text: str) -> str | None:
    """Extract a DOI from a text field."""
    doi_pattern = re.compile(r"\b(10\.\d{4,}/[^\s\"'<>]+)", re.IGNORECASE)
    match = doi_pattern.search(text)
    if match:
        doi = re.sub(r"[.,;:)\]]+$", "", match.group(1))
        return doi
    return None


def _extract_year(text: str) -> str | None:
    """Extract a plausible publication year (1900–2030) from reference text."""
    years = re.findall(r"\b((?:19|20)\d{2})\b", text)
    if years:
        for y in years:
            year_int = int(y)
            if 1900 <= year_int <= 2030:
                return y
    return None


def _extract_author(text: str) -> str:
    """Extract a conservative first-author family name.

    Citation keys and arbitrary capitalised words are not treated as authors;
    returning an empty string is safer than manufacturing an identity mismatch.
    """
    bibtex = re.search(r"author\s*=\s*[\{\"]([^{}\"]+)[\}\"]", text, re.IGNORECASE)
    if bibtex:
        first = re.split(r"\s+and\s+", bibtex.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if "," in first:
            return first.split(",", 1)[0].strip().lower()
        parts = first.split()
        return parts[-1].strip().lower() if parts else ""

    prefix = re.split(r"\b(?:19|20)\d{2}\b", text, maxsplit=1)[0]
    match = re.match(
        r"\s*(?:\[[^\]]+\]\s*)?([A-Z][A-Za-z'’\-]{2,})"
        r"(?:\s*,|\s+(?:[A-Z](?:\.|\b)|et\s+al\.?))",
        prefix,
    )
    return match.group(1).lower() if match else ""


def _extract_title_query(text: str) -> str:
    """Extract a plausible title substring for bibliographic query.

    Looks for a quoted title, or text between year and a journal marker,
    or the longest sentence-like fragment.
    """
    # Explicit BibTeX title field
    bibtex = re.search(r"title\s*=\s*[\{\"]([^{}\"]+)[\}\"]", text, re.IGNORECASE)
    if bibtex:
        return re.sub(r"\s+", " ", bibtex.group(1)).strip()

    # Quoted title
    quoted = re.findall(r'"([^"]{25,250})"', text)
    if quoted:
        return quoted[0]

    # Remove leading author/year/DOI noise
    cleaned = text
    # Strip DOI
    doi_match = _extract_doi(cleaned)
    if doi_match:
        cleaned = cleaned.replace(doi_match, "")
    # Strip URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)

    # Try to find text between a year and a journal marker
    year_match = re.search(r"\b(19|20)\d{2}\b", cleaned)
    journal_markers = [
        "Journal of", "Proceedings of", "IEEE", "ACM Trans",
        "Nature", "Science", "Cell", "Lancet", "BMJ", "PLOS",
        "Springer", "Elsevier", "vol.", "Vol.",
    ]
    if year_match:
        after_year = cleaned[year_match.end():].strip(" .,;:()[]")
        for marker in journal_markers:
            idx = after_year.find(marker)
            if idx > 15:
                candidate = after_year[:idx].strip(" .,;:")
                if len(candidate) >= 25:
                    return candidate

    # Fallback: longest sentence-like fragment
    fragments = re.split(r"[.!?]\s+", cleaned)
    long_enough = [f.strip() for f in fragments if len(f.strip()) >= 25]
    if long_enough:
        return max(long_enough, key=len)[:250]

    # Last resort: return a cleaned chunk of the text
    words = cleaned.split()
    if len(words) >= 6:
        return " ".join(words[:50])
    return cleaned[:250]


# ---------------------------------------------------------------------------
# Crossref API (extracted for testability)
# ---------------------------------------------------------------------------

def _fetch_crossref_json(url: str, timeout: int = 15) -> dict | None:
    """Fetch JSON from a Crossref API URL.

    Extracted as a module-level function so tests can mock it without
    touching ``urllib.request.urlopen`` internals.  Returns the parsed
    JSON dict on success, or ``None`` on any network / parse error.
    """
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        json.JSONDecodeError,
        OSError,
        ValueError,
    ):
        return None


def _crossref_doi_lookup(doi: str) -> dict | None:
    """Query Crossref by DOI. Returns parsed JSON or None on failure."""
    url = f"{CROSSREF_QUERY_URL}/{urllib.parse.quote(doi, safe='')}"
    return _fetch_crossref_json(url)


def _crossref_bibliographic_query(query: str) -> dict | None:
    """Query Crossref by bibliographic metadata. Returns parsed JSON or None."""
    params = urllib.parse.urlencode({
        "query.bibliographic": query[:200],
        "rows": 3,
    })
    url = f"{CROSSREF_QUERY_URL}?{params}"
    return _fetch_crossref_json(url)


# ---------------------------------------------------------------------------
# matching logic
# ---------------------------------------------------------------------------

def _crossref_year(msg: dict) -> str:
    """Extract a publication year from a Crossref message.

    Prefers the actual publication date fields (``issued``,
    ``published-print``, ``published-online``) over ``created``, which
    records the *registration* date and can differ from the publication
    year for older or back-filled works.
    """
    for key in ("issued", "published-print", "published-online", "published"):
        field_val = msg.get(key)
        if isinstance(field_val, dict):
            parts = field_val.get("date-parts") or [[0]]
            try:
                year = parts[0][0]
            except (IndexError, TypeError):
                year = 0
            if year:
                return str(year)
    # Fall back to the registration date only if nothing else is available.
    created = msg.get("created")
    if isinstance(created, dict):
        parts = created.get("date-parts") or [[0]]
        try:
            year = parts[0][0]
        except (IndexError, TypeError):
            year = 0
        if year:
            return str(year)
    return ""


def _titles_similar(local_title: str, crossref_title: str) -> bool:
    """Return True when *local_title* is similar enough to *crossref_title*."""
    if not local_title or not crossref_title:
        return False
    a = re.sub(
        r"[^\w]+", " ", unicodedata.normalize("NFKC", local_title).casefold(), flags=re.UNICODE
    ).replace("_", " ").strip()
    b = re.sub(
        r"[^\w]+", " ", unicodedata.normalize("NFKC", crossref_title).casefold(), flags=re.UNICODE
    ).replace("_", " ").strip()
    if not a or not b:
        return False
    # Direct substring in either direction → definitely similar
    if a[:40] in b or b[:40] in a:
        return True
    ratio = difflib.SequenceMatcher(None, a[:200], b[:200]).ratio()
    return ratio >= MIN_TITLE_SIMILARITY


def _years_close(local_year: str, crossref_year: str) -> bool:
    """Return True when years match within ±YEAR_TOLERANCE."""
    if not local_year or not crossref_year:
        return True  # can't judge, be permissive
    try:
        ly = int(local_year)
        cy = int(crossref_year)
        return abs(ly - cy) <= YEAR_TOLERANCE
    except (ValueError, TypeError):
        return True


def _crossref_first_author(msg: dict) -> str:
    authors = msg.get("author", [])
    if not isinstance(authors, list) or not authors or not isinstance(authors[0], dict):
        return ""
    return str(authors[0].get("family") or authors[0].get("name") or "").strip()


def _authors_similar(local_author: str, crossref_author: str) -> bool | None:
    """Compare family names only when both sides are safely comparable."""
    if not local_author or not crossref_author:
        return None
    if any(ord(char) > 127 for char in local_author + crossref_author):
        return None
    local = re.sub(r"[^a-z0-9]+", "", local_author.casefold())
    remote = re.sub(r"[^a-z0-9]+", "", crossref_author.casefold())
    if not local or not remote:
        return None
    if local == remote:
        return True
    return difflib.SequenceMatcher(None, local, remote).ratio() >= 0.85


# ---------------------------------------------------------------------------
# data classes
# ---------------------------------------------------------------------------

@dataclass
class VerificationEntry:
    candidate_id: str
    reference_text: str = ""
    doi: str = ""
    status: str = "unchecked"   # matched | unmatched | skipped | not-checked
    citation_scope: str = ""
    crossref_title: str = ""
    crossref_author: str = ""
    crossref_year: str = ""
    crossref_doi: str = ""
    author_match: bool | None = None
    note: str = ""


@dataclass
class CitationVerificationResult:
    path: str
    ok: bool
    total_candidates: int = 0
    checked_count: int = 0
    matched_count: int = 0
    unmatched_count: int = 0
    skipped_count: int = 0
    entries: list[VerificationEntry] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify English citations in citation_support_bank.md against Crossref."
    )
    parser.add_argument(
        "bank_path", nargs="?",
        default="paper_rewriting_output/citation_support_bank.md",
    )
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Write citation_verification_en.md")
    parser.add_argument("--max-checks", type=int, default=30,
                        help="Maximum citations to check (default: 30).")
    parser.add_argument("--delay", type=float, default=0.0,
                        help="Seconds to sleep between Crossref requests "
                             "(default: 0).")
    parser.add_argument("--no-api", action="store_true",
                        help="Skip all Crossref calls; mark checkable "
                             "citations as skipped instead of querying.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# main verification logic
# ---------------------------------------------------------------------------

def verify_citation(
    bank_path: Path,
    max_checks: int = 30,
    *,
    delay: float = 0.0,
    no_api: bool = False,
    _fetcher: object | None = None,
) -> CitationVerificationResult:
    """Verify citations in *bank_path* against Crossref.

    The *_fetcher* parameter exists for testing: pass a callable with the
    same signature as ``_fetch_crossref_json`` to mock the network layer.

    When *no_api* is True no network calls are made: every citation that
    would otherwise be queried is marked ``skipped``.  *delay* controls the
    sleep (in seconds) between Crossref requests.
    """
    fetch = _fetcher if _fetcher is not None else _fetch_crossref_json  # type: ignore[assignment]

    result = CitationVerificationResult(str(bank_path), ok=True)

    if not bank_path.exists():
        result.ok = False
        result.findings.append(f"Bank file not found: {bank_path}")
        return result

    text = bank_path.read_text(encoding="utf-8", errors="ignore")
    header, rows = _table_rows(text)
    if not header:
        result.ok = False
        result.findings.append("No parseable table found in citation_support_bank.md")
        return result

    id_col = _col_index(header, "candidate id", "id")
    ref_col = _col_index(header, "reference", "bibtex")
    source_channel_col = _col_index(header, "source channel")
    citation_scope_col = _col_index(header, "citation scope", "scope")

    if id_col is None:
        result.findings.append(
            "Missing Candidate ID / ID column — cannot map verifications."
        )
        result.ok = False
        return result

    result.total_candidates = len(rows)

    for row_index, row in enumerate(rows):
        candidate_id = (
            row[id_col].strip() if id_col < len(row) else f"row{row_index + 1}"
        )

        citation_scope = ""
        if citation_scope_col is not None and citation_scope_col < len(row):
            citation_scope = row[citation_scope_col].strip().lower()
        entry = VerificationEntry(candidate_id=candidate_id, citation_scope=citation_scope)

        # --- read reference text ---
        if ref_col is not None and ref_col < len(row):
            entry.reference_text = row[ref_col].strip()
        else:
            entry.reference_text = " ".join(row)

        # --- read source channel ---
        channel = ""
        if source_channel_col is not None and source_channel_col < len(row):
            channel = row[source_channel_col].strip().lower()

        # Screening-only rows are not load-bearing references and must not
        # block a final-source identity audit.
        if citation_scope in CANDIDATE_CITATION_SCOPES:
            entry.status = "skipped"
            entry.note = "candidate-only source — not checked as a final citation"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # Local and CNKI records are not judged by Crossref coverage. They
        # retain their existing publisher/database verification chain.
        if channel == "local" or "cnki" in channel:
            entry.status = "skipped"
            entry.note = f"{channel or 'local'} source — not checked against Crossref"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # respect max-checks cap
        if result.checked_count >= max_checks:
            entry.status = "skipped"
            entry.note = f"max-checks limit ({max_checks}) reached"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --- extract metadata from the reference text ---
        doi = _extract_doi(entry.reference_text)
        extracted_author = _extract_author(entry.reference_text)
        extracted_year = _extract_year(entry.reference_text)
        extracted_title = _extract_title_query(entry.reference_text)

        # Build a bibliographic query string from what we have
        bib_parts = []
        if extracted_author:
            bib_parts.append(extracted_author)
        if extracted_title:
            bib_parts.append(extracted_title[:150])
        bib_query = " ".join(bib_parts) if bib_parts else entry.reference_text[:200]

        if not bib_query.strip() or len(bib_query.strip()) < 10:
            entry.status = "not-checked"
            entry.note = "NOT CHECKED: insufficient metadata to query Crossref; manual review required"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --no-api: never touch the network, just record what we extracted
        if no_api:
            if doi:
                entry.doi = doi
            entry.status = "not-checked"
            entry.note = "NOT CHECKED: API disabled (--no-api); manual review required"
            result.skipped_count += 1
            result.entries.append(entry)
            continue

        # --- query Crossref ---
        if delay > 0:
            time.sleep(delay)
        result.checked_count += 1

        # Prefer DOI lookup when a DOI is available
        if doi:
            entry.doi = doi

            # Use the injected fetcher for DOI lookup
            doi_url = f"{CROSSREF_QUERY_URL}/{urllib.parse.quote(doi, safe='')}"
            data = fetch(doi_url)  # type: ignore[call-arg]

            if data is None:
                # Network failure and absent metadata are both indeterminate
                # here; do not infer fabrication from a failed API call.
                entry.status = "not-checked"
                entry.note = "NOT CHECKED: Crossref DOI lookup unavailable; manual review required"
                result.skipped_count += 1
                result.entries.append(entry)
                continue

            if data.get("status") == "ok":
                msg = data.get("message", {})
                if not isinstance(msg, dict):
                    entry.status = "not-checked"
                    entry.note = "NOT CHECKED: Crossref returned incomplete DOI metadata"
                    result.skipped_count += 1
                    result.entries.append(entry)
                    continue
                crossref_title = " ".join(
                    str(t).strip() for t in msg.get("title", [""])
                )[:200]
                crossref_author = _crossref_first_author(msg)
                crossref_year = _crossref_year(msg)
                crossref_doi = msg.get("DOI", "")
                entry.crossref_title = crossref_title[:120]
                entry.crossref_author = crossref_author
                entry.crossref_year = crossref_year
                entry.crossref_doi = crossref_doi

                if not extracted_title or not crossref_title:
                    entry.status = "not-checked"
                    entry.note = (
                        "NOT CHECKED: DOI resolved but title metadata is insufficient for identity comparison"
                    )
                    result.skipped_count += 1
                else:
                    title_ok = _titles_similar(extracted_title, crossref_title)
                    entry.author_match = _authors_similar(extracted_author, crossref_author)
                    year_differs = bool(
                        extracted_year and crossref_year and extracted_year != crossref_year
                    )

                    mismatches = []
                    if not title_ok:
                        mismatches.append("title differs from local metadata")
                    if entry.author_match is False:
                        mismatches.append(
                            f"first author differs (local={extracted_author}, crossref={crossref_author})"
                        )

                    if mismatches:
                        entry.status = "unmatched"
                        entry.note = (
                            "DOI resolved, but citation identity is mismatched: "
                            + "; ".join(mismatches)
                        )
                        result.unmatched_count += 1
                    else:
                        entry.status = "matched"
                        entry.note = "DOI resolved — title identity matches"
                        if entry.author_match is True:
                            entry.note += "; first-author identity matches"
                        else:
                            entry.note += "; first author not comparable"
                        if year_differs:
                            year_qualifier = (
                                "within one-year tolerance"
                                if _years_close(extracted_year or "", crossref_year)
                                else "beyond one-year tolerance; manual date review required"
                            )
                            entry.note += (
                                f"; WARNING year differs (local={extracted_year}, "
                                f"crossref={crossref_year}; {year_qualifier})"
                            )
                        result.matched_count += 1
            else:
                entry.status = "not-checked"
                entry.note = "NOT CHECKED: Crossref returned an unexpected DOI response"
                result.skipped_count += 1
        else:
            # Bibliographic query
            bib_url = (
                f"{CROSSREF_QUERY_URL}?"
                f"{urllib.parse.urlencode({'query.bibliographic': bib_query[:200], 'rows': 3})}"
            )
            data = fetch(bib_url)  # type: ignore[call-arg]

            if data is None:
                entry.status = "not-checked"
                entry.note = "NOT CHECKED: Crossref bibliographic query unavailable; manual review required"
                result.skipped_count += 1
                result.entries.append(entry)
                continue

            if data.get("status") == "ok":
                items = data.get("message", {}).get("items", [])
                if items:
                    # Try each returned item for a conservative match
                    best = items[0]
                    crossref_title = " ".join(
                        str(t).strip() for t in best.get("title", [""])
                    )[:200]
                    crossref_author = _crossref_first_author(best)
                    crossref_year = _crossref_year(best)
                    crossref_doi = best.get("DOI", "")

                    # Check all returned items for matching title and, when
                    # extractable on both sides, the first-author family name.
                    matched_item = None
                    for item in items:
                        item_title = " ".join(
                            str(t).strip() for t in item.get("title", [""])
                        )[:200]
                        item_author = _crossref_first_author(item)
                        item_year = _crossref_year(item)
                        author_match = _authors_similar(extracted_author, item_author)
                        if _titles_similar(extracted_title, item_title) and author_match is not False:
                            matched_item = item
                            crossref_title = item_title
                            crossref_author = item_author
                            crossref_year = item_year
                            crossref_doi = item.get("DOI", "")
                            entry.author_match = author_match
                            break

                    if matched_item is not None:
                        entry.status = "matched"
                        entry.crossref_title = crossref_title[:120]
                        entry.crossref_author = crossref_author
                        entry.crossref_year = crossref_year
                        entry.crossref_doi = crossref_doi
                        entry.note = "Bibliographic query matched — title identity matches"
                        if entry.author_match is True:
                            entry.note += "; first-author identity matches"
                        else:
                            entry.note += "; first author not comparable"
                        if extracted_year and crossref_year and extracted_year != crossref_year:
                            year_qualifier = (
                                "within one-year tolerance"
                                if _years_close(extracted_year, crossref_year)
                                else "beyond one-year tolerance; manual date review required"
                            )
                            entry.note += (
                                f"; WARNING year differs (local={extracted_year}, "
                                f"crossref={crossref_year}; {year_qualifier})"
                            )
                        result.matched_count += 1
                    else:
                        first_author_match = _authors_similar(extracted_author, crossref_author)
                        entry.crossref_title = crossref_title[:120]
                        entry.crossref_author = crossref_author
                        entry.crossref_year = crossref_year
                        entry.crossref_doi = crossref_doi
                        if not extracted_title or not crossref_title:
                            entry.status = "not-checked"
                            entry.note = "NOT CHECKED: Crossref results lacked comparable title metadata"
                            result.skipped_count += 1
                        else:
                            entry.status = "unmatched"
                            mismatch = "title does not match local metadata"
                            if _titles_similar(extracted_title, crossref_title) and first_author_match is False:
                                mismatch = (
                                    f"first author differs (local={extracted_author}, "
                                    f"crossref={crossref_author})"
                                )
                            entry.note = f"Crossref returned results, but citation identity is mismatched: {mismatch}"
                            result.unmatched_count += 1
                else:
                    entry.status = "not-checked"
                    entry.note = "NOT CHECKED: no Crossref bibliographic result; manual review required"
                    result.skipped_count += 1
            else:
                entry.status = "not-checked"
                entry.note = "NOT CHECKED: Crossref query returned an unexpected response"
                result.skipped_count += 1

        result.entries.append(entry)

    # --- synthesise findings ---
    if result.checked_count == 0 and result.skipped_count > 0:
        result.findings.append(
            f"No citations checked: {result.skipped_count} skipped "
            f"(local sources, API unavailable, or insufficient metadata)."
        )

    if result.unmatched_count > 0:
        unmatched_ids = [
            e.candidate_id for e in result.entries if e.status == "unmatched"
        ]
        result.findings.append(
            f"{result.unmatched_count} citation(s) could not be matched in Crossref: "
            f"{unmatched_ids[:10]}. Review these entries for typos or incomplete metadata."
        )
        result.ok = False

    identity_checked_count = result.matched_count + result.unmatched_count
    if result.matched_count == 0 and identity_checked_count > 0:
        result.findings.append(
            f"All {identity_checked_count} conclusively checked citations failed to match Crossref. "
            "Check that reference text includes complete titles and author names."
        )
        result.ok = False

    if identity_checked_count > 0:
        match_rate = result.matched_count / identity_checked_count
        if match_rate < 0.5:
            result.ok = False
            result.findings.append(
                f"Low match rate: {result.matched_count}/{identity_checked_count} "
                f"({match_rate:.0%}) — most citations could not be confirmed."
            )

    return result


# ---------------------------------------------------------------------------
# output formatting
# ---------------------------------------------------------------------------

def to_markdown(result: CitationVerificationResult) -> str:
    lines = [
        "# Citation Verification Report (Crossref)",
        "",
        f"- Bank path: `{result.path}`",
        f"- Total candidates: {result.total_candidates}",
        f"- Checked: {result.checked_count}",
        f"- Matched: {result.matched_count}",
        f"- Unmatched: {result.unmatched_count}",
        f"- Skipped: {result.skipped_count}",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        "",
        "## Verification Results",
        "",
    ]

    if result.entries:
        lines.extend([
            "| Candidate ID | Status | DOI Queried | Crossref Title | Crossref Author | Crossref Year | Note |",
            "|---|---|---|---|---|---|---|",
        ])
        for entry in result.entries:
            c_title = entry.crossref_title[:60] if entry.crossref_title else "-"
            c_author = entry.crossref_author or "-"
            c_year = entry.crossref_year or "-"
            lines.append(
                f"| {entry.candidate_id} | {entry.status} | {entry.doi or '-'} | "
                f"{c_title} | {c_author} | {c_year} | {entry.note} |"
            )
        lines.append("")
    else:
        lines.append("- No entries to report.")
        lines.append("")

    lines.extend([
        "## Findings",
        "",
    ])
    if result.findings:
        lines.extend(f"- {f}" for f in result.findings)
    else:
        lines.append("- No issues found.")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # parity with citation_quality_audit on Windows
    args = parse_args()
    bank_path = Path(args.bank_path)
    result = verify_citation(
        bank_path,
        max_checks=args.max_checks,
        delay=args.delay,
        no_api=args.no_api,
    )

    if args.json:
        print(json.dumps({
            "ok": result.ok,
            "total_candidates": result.total_candidates,
            "checked_count": result.checked_count,
            "matched_count": result.matched_count,
            "unmatched_count": result.unmatched_count,
            "skipped_count": result.skipped_count,
            "findings": result.findings,
            "entries": [
                {
                    "candidate_id": e.candidate_id,
                    "status": e.status,
                    "doi": e.doi,
                    "crossref_title": e.crossref_title,
                    "crossref_author": e.crossref_author,
                    "crossref_year": e.crossref_year,
                    "author_match": e.author_match,
                    "note": e.note,
                }
                for e in result.entries
            ],
        }, ensure_ascii=False, indent=2))
    elif args.markdown or not args.json:
        print(to_markdown(result))

    if args.write:
        report_path = bank_path.parent / "citation_verification_en.md"
        report_path.write_text(to_markdown(result), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
