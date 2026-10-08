#!/usr/bin/env python3
"""Citation Quality Audit — teaching-oriented local citation analysis.

Goes beyond DOI verification.  Each citation is scored across three axes
(resolvability, recency, field relevance).  The report identifies diversity gaps,
recommends replacements for dead citations, and produces a scene-specific
citation strategy section that teaches the user *why* certain citation types
matter for their target venue.

Pattern: follows the writing_rationale_matrix philosophy — every analysis row
teaches the user something about citation strategy.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from _engine_utils import markdown_tables

DOI_RE = re.compile(
    r"\b(?:doi\s*[:=]\s*|https?://doi\.org/|https?://dx\.doi\.org/)?(10\.\d{4,}/[^\s,;)\]]+)",
    re.IGNORECASE,
)
ARXIV_RE = re.compile(r"\barxiv\s*:?\s*(\d{4}\.\d{4,5}(?:v\d+)?)\b", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)
CROSSREF_URL = "https://api.crossref.org/works/"
SEMANTIC_SCHOLAR_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:"
CURRENT_YEAR = date.today().year
# CNKI-PAPER CITATION-IDENTITY COMPAT: DOI resolution is not identity confirmation
USER_AGENT = "Avereth/6.0 (citation-quality; local research engine)"
VALID_VERIFICATION_VALUES = {"yes", "verified", "pass", "true"}
FINAL_CITATION_SCOPES = {"final-source", "final", "selected", "cited"}
# CNKI-PAPER CANDIDATE-SCOPE COMPAT: final-source audit only
EXTERNAL_CHANNEL_TOKENS = (
    "web",
    "mcp",
    "crossref",
    "pubmed",
    "scholar",
    "semantic scholar",
    "ieee",
    "cnki",
    "wos",
    "publisher",
    "journal",
    "conference",
    "proceedings",
    "arxiv",
    "preprint",
    "regulatory",
    "database",
)
MANUAL_VERIFICATION_TOKENS = (
    "confirmed",
    "verified",
    "accessed",
    "publisher",
    "official",
    "crossref",
    "pubmed",
    "arxiv",
    "database",
    "metadata",
    "proceedings",
    "repository",
    "website",
)


# ---------------------------------------------------------------------------
# citation-type taxonomy
# ---------------------------------------------------------------------------

CITATION_TYPES = {
    "sota": "direct task or state-of-the-art paper",
    "foundational": "foundational method or theory paper",
    "benchmark": "dataset, benchmark, or evaluation protocol paper",
    "survey": "survey, review, or meta-analysis",
    "application": "domain-application or impact paper",
    "critique": "limitation, robustness, reproducibility, or ethics paper",
}

SCENE_CITATION_GUIDANCE: dict[str, dict[str, str]] = {
    "journal": {
        "sota": "Must cite the 3-5 most recent competing methods. Missing these is a desk-reject risk.",
        "foundational": "Cite the 2-3 methods your work builds on. Explain inheritance clearly.",
        "benchmark": "Cite the datasets you evaluate on. Report dataset statistics.",
        "survey": "Cite 1-2 recent surveys to position your work in the broader landscape.",
        "application": "Optional unless your contribution is application-motivated.",
        "critique": "Include 1-2 limitation/robustness papers to show awareness of field challenges.",
    },
    "conference": {
        "sota": "Cite the 5-8 most recent competing methods. Conference reviewers check recency aggressively.",
        "foundational": "Cite the 2-3 methods you build on. Be specific about what you inherit vs. change.",
        "benchmark": "Cite all datasets used. Standard benchmarks are expected.",
        "survey": "Cite 1 recent survey if it helps position your work concisely.",
        "application": "Optional.",
        "critique": "Optional but helpful for discussion section.",
    },
    "report_review": {
        "sota": "Cite representative methods across the field. Breadth matters more than exhaustiveness.",
        "foundational": "Cite the key methods that define the field. Explain their contributions.",
        "benchmark": "Cite datasets if you use them.",
        "survey": "Essential: cite 3-5 surveys to establish the review's coverage.",
        "application": "Include application papers that show real-world relevance.",
        "critique": "Include limitation/robustness discussions to show balanced coverage.",
    },
    "competition": {
        "sota": "Cite the top-3 solutions from prior competitions or leaderboards.",
        "foundational": "Cite the base methods your solution extends.",
        "benchmark": "Cite the competition dataset and evaluation protocol.",
        "survey": "Optional.",
        "application": "Cite real-world applications if your solution targets practical deployment.",
        "critique": "Cite known limitations of competing approaches.",
    },
}


# ---------------------------------------------------------------------------
# data types
# ---------------------------------------------------------------------------

@dataclass
class CitationQualityEntry:
    candidate_id: str
    doi: str
    reference: str
    year: str
    source: str = ""
    source_channel: str = ""
    verified: str = ""
    verification_note: str = ""
    # verification
    doi_resolves: bool = False
    crossref_title: str | None = None
    crossref_author: str | None = None
    api_year: int | None = None
    title_similarity: float = 0.0
    author_matches: bool | None = None
    year_matches: bool = False
    # quality scores (0-100)
    resolvability_score: int = 0
    recency_score: int = 0
    # classification
    citation_type: str = "sota"
    # assessment
    status: str = "pending"     # verified | mismatched | dead | error
    issues: list[str] = field(default_factory=list)
    teaching_note: str = ""
    manual_identifier: str = ""


@dataclass
class CitationQualityReport:
    output_dir: str
    scene: str
    target_count: int
    entries: list[CitationQualityEntry] = field(default_factory=list)
    gap_analysis: dict[str, str] = field(default_factory=dict)
    replacement_recommendations: list[str] = field(default_factory=list)
    overall_score: int = 0
    doi_api_limit: int = 0
    doi_api_checked: int = 0
    not_checked_due_to_limit: int = 0

    @property
    def verified_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "verified")

    @property
    def dead_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "dead")

    @property
    def mismatched_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "mismatched")

    @property
    def error_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "error")

    @property
    def pending_count(self) -> int:
        return sum(1 for e in self.entries if e.status == "pending")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Citation quality audit for Avereth.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write citation_quality_audit.md")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-api", action="store_true", help="Skip API calls; analyze structure only")
    parser.add_argument("--max-dois", type=int, default=30, help="Maximum DOIs to verify via API (default: 30)")
    parser.add_argument("--min-score", type=int, default=60, help="Minimum overall score for PASS (default: 60)")
    parser.add_argument("--max-error-ratio", type=float, default=0.30, help="Maximum error ratio for PASS (default: 0.30)")
    parser.add_argument("--max-pending-ratio", type=float, default=0.50, help="Maximum pending ratio for PASS (default: 0.50)")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# DOI extraction and API verification
# ---------------------------------------------------------------------------

def extract_dois(text: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in DOI_RE.finditer(text):
        doi = match.group(1).rstrip(".")
        clean = doi.lower().strip()
        if clean not in seen:
            seen.add(clean)
            result.append(doi)
    return result


def parse_citation_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    header, rows = find_citation_table(text)
    if not rows:
        return []
    result: list[dict[str, str]] = []

    index = {normalize_header(cell): i for i, cell in enumerate(header)}

    def cell(row: list[str], *names: str, fallback: int | None = None) -> str:
        for name in names:
            idx = index.get(name)
            if idx is not None and idx < len(row):
                return row[idx]
        if fallback is not None and fallback < len(row):
            return row[fallback]
        return ""

    for row in rows:
        if len(row) < 6:
            continue
        joined = " ".join(row)
        dois = extract_dois(joined)
        result.append({
            "candidate_id": cell(row, "candidate id", "id", fallback=0),
            "reference": cell(row, "reference/bibtex", "reference", "citation", "bibtex", fallback=1),
            "year": cell(row, "year", fallback=2),
            "doi": dois[0] if dois else "",
            "source": cell(row, "source"),
            "source_channel": cell(row, "source channel"),
            "verified": cell(row, "verified"),
            "verification_note": cell(row, "verification note"),
            "citation_scope": cell(row, "citation scope", "scope"),
        })
    return result


def normalize_header(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"[*_`]", "", value)
    return re.sub(r"\s+", " ", value.strip().lower())


def find_citation_table(text: str) -> tuple[list[str], list[list[str]]]:
    for table in markdown_tables(text):
        if not table:
            continue
        header = table[0]
        header_text = " ".join(cell.lower() for cell in header)
        has_reference = any(term in header_text for term in ("citation", "reference", "bibtex"))
        has_claim = "claim" in header_text
        has_sentence = "sentence" in header_text
        if has_reference and has_claim and has_sentence:
            return header, table[1:]
    return [], []


def title_similarity(a: str, b: str) -> float:
    a_text = unicodedata.normalize("NFKC", a).casefold()
    b_text = unicodedata.normalize("NFKC", b).casefold()
    a_words = re.sub(r"[^\w]+", " ", a_text, flags=re.UNICODE).replace("_", " ").strip().split()
    b_words = re.sub(r"[^\w]+", " ", b_text, flags=re.UNICODE).replace("_", " ").strip().split()
    if not a_words or not b_words:
        return 0.0
    a_set = set(a_words)
    b_set = set(b_words)
    jaccard = len(a_set & b_set) / len(a_set | b_set)
    sm = SequenceMatcher(None, " ".join(a_words), " ".join(b_words))
    return round(jaccard * 0.5 + sm.ratio() * 0.5, 4)


def extract_reference_title(reference: str) -> str:
    """Extract the cited work title from a reference cell.

    The audit should compare Crossref's title against the paper title, not the
    whole reference string with authors, venue, pages, DOI, and notes.
    """
    if not reference:
        return ""
    bibtex = re.search(r"title\s*=\s*[\{\"]([^{}\"]+)[\}\"]", reference, re.IGNORECASE)
    if bibtex:
        return re.sub(r"\s+", " ", bibtex.group(1)).strip()

    quoted = re.search(r'["“”]([^"“”]{8,})["“”]', reference)
    if quoted:
        return re.sub(r"\s+", " ", quoted.group(1)).strip(" .")

    text = re.sub(r"\b(?:doi\s*[:=]\s*|https?://doi\.org/|https?://dx\.doi\.org/)?10\.\d{4,}/\S+", " ", reference, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    year_match = re.search(r"\((?:19|20)\d{2}\)\.\s+", text)
    if year_match:
        start = year_match.end()
        tail = text[start:]
        venue_match = re.search(r"\.\s+(?:\*|[A-Z][A-Za-z& ]{2,}[,;]|\barXiv:|\b[A-Z]{2,}\b)", tail)
        title = tail[: venue_match.start()] if venue_match else tail
        return title.strip(" \"'“”‘’.")

    # Fallback: remove obvious leading author/year fragments and stop before DOI.
    text = re.sub(r"^.*?\b(?:19|20)\d{2}\b[).,:]*\s*", "", text)
    text = re.sub(r"\s+(?:DOI|doi|https?://).*$", "", text).strip()
    return text.strip(" \"'“”‘’.")


def extract_reference_author(reference: str) -> str:
    """Extract a conservative first-author family name from a citation.

    Return an empty string rather than guessing from a title. Author identity
    is checked only when local and Crossref metadata are both comparable.
    """
    if not reference:
        return ""
    bibtex = re.search(r"author\s*=\s*[\{\"]([^{}\"]+)[\}\"]", reference, re.IGNORECASE)
    if bibtex:
        first = re.split(r"\s+and\s+", bibtex.group(1), maxsplit=1, flags=re.IGNORECASE)[0].strip()
        if "," in first:
            return first.split(",", 1)[0].strip()
        parts = first.split()
        return parts[-1].strip() if parts else ""

    prefix = re.split(r"\b(?:19|20)\d{2}\b", reference, maxsplit=1)[0]
    match = re.match(
        r"\s*(?:\[[^\]]+\]\s*)?([A-Z][A-Za-z'’\-]{2,})"
        r"(?:\s*,|\s+(?:[A-Z](?:\.|\b)|et\s+al\.?))",
        prefix,
    )
    return match.group(1) if match else ""


def normalize_author(value: str | None) -> str:
    if not value:
        return ""
    # Do not block on unreliable cross-script comparisons, such as Chinese
    # characters in the bank versus a romanised Crossref family name.
    if any(ord(char) > 127 for char in value):
        return ""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def authors_similar(local_author: str, crossref_author: str) -> bool | None:
    local = normalize_author(local_author)
    remote = normalize_author(crossref_author)
    if not local or not remote:
        return None
    if local == remote:
        return True
    return SequenceMatcher(None, local, remote).ratio() >= 0.85


def fetch_crossref(doi: str, timeout: int) -> dict | None:
    """Resolve a DOI while separating absence from temporary API failure."""
    try:
        req = Request(CROSSREF_URL + doi, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            msg = data.get("message", {})
            title_list = msg.get("title", [])
            year = msg.get("published-print", {}).get("date-parts", [[None]])[0][0]
            if year is None:
                year = msg.get("published-online", {}).get("date-parts", [[None]])[0][0]
            if year is None:
                year = msg.get("created", {}).get("date-parts", [[None]])[0][0]
            authors = msg.get("author", [])
            first_author = ""
            if authors and isinstance(authors[0], dict):
                first_author = str(authors[0].get("family") or authors[0].get("name") or "")
            return {
                "lookup_status": "resolved",
                "title": title_list[0] if title_list else None,
                "author": first_author or None,
                "year": year,
            }
    except HTTPError as exc:
        if exc.code == 404:
            return {"lookup_status": "not-found"}
        return {"lookup_status": "unavailable"}
    except (URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError, TypeError, IndexError):
        return {"lookup_status": "unavailable"}


def extract_manual_identifier(record: dict[str, str]) -> str:
    joined = " ".join(record.get(key, "") for key in ("reference", "source", "verification_note"))
    arxiv = ARXIV_RE.search(joined)
    if arxiv:
        return f"arXiv:{arxiv.group(1)}"
    url = URL_RE.search(joined)
    if url:
        return url.group(0).rstrip(".,;")
    return ""


def is_external_channel(source_channel: str, source: str = "") -> bool:
    text = f"{source_channel} {source}".lower()
    return any(token in text for token in EXTERNAL_CHANNEL_TOKENS)


def has_manual_verification(record: dict[str, str]) -> bool:
    verified = normalize_header(record.get("verified", ""))
    note = record.get("verification_note", "").strip()
    if verified not in VALID_VERIFICATION_VALUES or len(note) < 12:
        return False
    note_lower = note.lower()
    if any(token in note_lower for token in ("todo", "tbd", "pending", "[verify]", "unknown")):
        return False
    if any(token in note_lower for token in MANUAL_VERIFICATION_TOKENS):
        return True
    return bool(extract_manual_identifier(record))


def classify_citation_type(reference: str) -> str:
    text = reference.lower()
    if any(w in text for w in ("survey", "review", "meta-analysis", "综述", "回顾")):
        return "survey"
    if any(w in text for w in ("benchmark", "dataset", "corpus", "evaluation", "数据集")):
        return "benchmark"
    if any(w in text for w in ("limitation", "robustness", "reproducib", "bias", "fairness")):
        return "critique"
    if any(w in text for w in ("application", "real-world", "deployment", "clinical", "应用")):
        return "application"
    if any(w in text for w in ("foundation", "seminal", "classic", "theory", "theorem")):
        return "foundational"
    return "sota"


def compute_recency_score(year: str | None, current_year: int = CURRENT_YEAR) -> int:
    if year is None:
        return 30
    try:
        y = int(year)
    except (ValueError, TypeError):
        return 30
    if y >= current_year:
        return 100
    if y >= current_year - 2:
        return 90
    if y >= current_year - 4:
        return 70
    if y >= current_year - 7:
        return 50
    return 20


# ---------------------------------------------------------------------------
# main audit logic
# ---------------------------------------------------------------------------

def audit_citations(output_dir: Path, no_api: bool, timeout: int, delay: float, max_dois: int = 30) -> CitationQualityReport:
    config = {}
    config_path = output_dir / "workflow_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))

    scene = config.get("scene", "journal")
    requirement = config.get("citation_requirement")
    target_count = (
        int(requirement.get("minimum"))
        if isinstance(requirement, dict) and str(requirement.get("minimum") or "").isdigit()
        else 0
    )
    report = CitationQualityReport(str(output_dir), scene, target_count)

    bank_path = output_dir / "citation_support_bank.md"
    if not bank_path.exists():
        return report

    records = parse_citation_rows(bank_path)
    if not records:
        return report

    final_records = [
        record for record in records
        if normalize_header(record.get("citation_scope", "")) in FINAL_CITATION_SCOPES
    ]
    auditing_final_sources = bool(final_records)
    if auditing_final_sources:
        # Keep every final-source row visible in the report.  --max-dois caps
        # network identity checks, not report coverage; rows beyond the cap
        # are emitted as explicit NOT CHECKED failures below.
        records = final_records
    else:
        records = records[:max(0, max_dois)]
    report.doi_api_limit = max(0, max_dois)
    doi_api_checked = 0
    for record in records:
        entry = CitationQualityEntry(
            candidate_id=record["candidate_id"],
            doi=record["doi"],
            reference=record["reference"],
            year=record["year"],
            source=record.get("source", ""),
            source_channel=record.get("source_channel", ""),
            verified=record.get("verified", ""),
            verification_note=record.get("verification_note", ""),
            citation_type=classify_citation_type(record["reference"]),
            recency_score=compute_recency_score(record["year"]),
        )

        if not entry.doi:
            entry.manual_identifier = extract_manual_identifier(record)
            if has_manual_verification(record) and entry.manual_identifier:
                entry.status = "verified"
                entry.doi_resolves = True
                entry.resolvability_score = 80
                entry.teaching_note = (
                    "Citation verified through a non-DOI channel recorded in the citation bank. "
                    "This is acceptable for arXiv preprints, official policy pages, proceedings, "
                    "and publisher/database records when the verification note is specific."
                )
            elif has_manual_verification(record):
                # Verified flag is set, but no stable identifier (DOI/arXiv/URL)
                # was recorded — this is self-attestation without independent
                # evidence, so it must not reach verified status or a high score.
                entry.status = "pending"
                entry.resolvability_score = 35
                entry.issues.append(
                    "Verified flag set but no stable identifier (DOI, arXiv ID, or URL) "
                    "found in the row; self-attestation alone cannot confirm the citation"
                )
                entry.teaching_note = (
                    "A Verified=yes flag is not enough on its own. Record a stable identifier "
                    "(DOI, arXiv ID, or URL) in the reference, source, or verification note so the "
                    "citation can be independently re-checked. Until then this row stays unverified."
                )
            else:
                entry.status = "error"
                if is_external_channel(entry.source_channel, entry.source):
                    entry.issues.append(
                        "No DOI found and no sufficient external verification note was recorded"
                    )
                    entry.teaching_note = (
                        "Non-DOI sources are acceptable only when the bank records a stable identifier "
                        "(such as arXiv ID or URL), Verified=yes/verified/pass/true, and a concrete "
                        "verification note naming the official page, publisher, database, or metadata check."
                    )
                else:
                    entry.issues.append("No DOI or stable external identifier found in citation entry")
                    entry.teaching_note = (
                        "Every citation should include a DOI, URL, arXiv ID, or local metadata note. "
                        "Without one, the reference cannot be verified and readers cannot easily locate the source."
                    )
                entry.resolvability_score = 0
            report.entries.append(entry)
            continue

        if no_api:
            # A DOI string is a stable identifier, not proof that it names the
            # cited work. Keep offline checks explicitly indeterminate.
            entry.manual_identifier = entry.doi
            entry.status = "pending"
            entry.resolvability_score = 50
            entry.issues.append("NOT CHECKED: Crossref API disabled; DOI identity was not compared")
            entry.teaching_note = (
                "The DOI is recorded for later checking, but resolvability alone would not confirm "
                "the cited title or author. Re-run with API access or verify publisher metadata manually."
            )
            report.entries.append(entry)
            continue

        if "cnki" in f"{entry.source_channel} {entry.source}".lower():
            entry.manual_identifier = entry.source or extract_manual_identifier(record)
            if has_manual_verification(record) and entry.manual_identifier:
                entry.status = "verified"
                entry.resolvability_score = 80
                entry.teaching_note = (
                    "CNKI citation retained on its recorded database/detail-page verification chain; "
                    "Crossref identity matching is not applied to this Chinese-database source."
                )
            else:
                entry.status = "pending"
                entry.resolvability_score = 35
                entry.issues.append(
                    "NOT CHECKED: CNKI DOI row lacks a sufficient database/detail-page verification record"
                )
                entry.teaching_note = (
                    "Verify the title and author on the CNKI detail page and record the stable URL, date, "
                    "and concrete metadata/content check; do not infer identity from Crossref coverage."
                )
            report.entries.append(entry)
            continue

        if auditing_final_sources and doi_api_checked >= report.doi_api_limit:
            entry.manual_identifier = entry.doi
            entry.status = "pending"
            entry.resolvability_score = 50
            entry.issues.append(
                f"NOT CHECKED: DOI identity verification skipped because --max-dois={report.doi_api_limit} "
                "was reached"
            )
            entry.teaching_note = (
                "This final-source row remains in the audit coverage, but it was not identity-checked. "
                "Increase --max-dois or split the final-source set into explicit batches and re-run; "
                "do not treat an omitted API check as verification."
            )
            report.not_checked_due_to_limit += 1
            report.entries.append(entry)
            continue

        doi_api_checked += 1
        report.doi_api_checked = doi_api_checked

        crossref = fetch_crossref(entry.doi, timeout)
        time.sleep(delay)

        lookup_status = (crossref or {}).get("lookup_status", "resolved" if crossref else "unavailable")
        if lookup_status == "unavailable":
            entry.status = "pending"
            entry.resolvability_score = 50
            entry.issues.append("NOT CHECKED: Crossref API unavailable; DOI identity remains pending")
            entry.teaching_note = (
                "Crossref could not be reached, so this audit does not infer that the citation is false. "
                "Retain any publisher verification note and retry or check publisher metadata manually."
            )
            report.entries.append(entry)
            continue
        if lookup_status == "not-found":
            entry.status = "pending"
            entry.resolvability_score = 35
            entry.issues.append(
                f"NOT CHECKED: DOI {entry.doi} was not found in Crossref; other registrars or publisher metadata may apply"
            )
            entry.teaching_note = (
                "Crossref returned not found, which is insufficient to call the citation fabricated or dead. "
                "Check the DOI resolver, responsible registrar, and publisher metadata manually."
            )
            report.entries.append(entry)
            continue

        entry.doi_resolves = True
        assert crossref is not None
        entry.crossref_title = crossref.get("title")
        entry.crossref_author = crossref.get("author")
        entry.api_year = crossref.get("year")

        reference_title = extract_reference_title(entry.reference)
        reference_author = extract_reference_author(entry.reference)
        if entry.crossref_title and reference_title:
            sim = title_similarity(entry.crossref_title, reference_title)
            entry.title_similarity = sim
            if sim < 0.75:
                entry.status = "mismatched"
                entry.resolvability_score = 40 if sim >= 0.50 else 20
                entry.issues.append(
                    f"Title similarity {sim:.2f} below 0.75 threshold. "
                    f"Crossref title: '{entry.crossref_title[:100]}'"
                )
                entry.teaching_note = (
                    f"Title mismatch ({sim:.0%}). The DOI resolves, but it does not identify "
                    "the work named by the local citation. Correct the DOI or citation metadata."
                )
            else:
                entry.author_matches = authors_similar(reference_author, entry.crossref_author or "")
                if entry.author_matches is False:
                    entry.status = "mismatched"
                    entry.resolvability_score = 20
                    entry.issues.append(
                        f"First-author mismatch: bank={reference_author}, API={entry.crossref_author}"
                    )
                    entry.teaching_note = (
                        "The title matches, but the extractable first-author family name does not. "
                        "Treat the DOI identity as mismatched until manually corrected."
                    )
                else:
                    entry.status = "verified"
                    entry.resolvability_score = 100
                    entry.teaching_note = "Citation verified: DOI resolves and title identity matches."
                    if entry.author_matches is True:
                        entry.teaching_note += " First-author identity also matches."
                    else:
                        entry.teaching_note += " First author was not comparable, so no author verdict was inferred."
        else:
            entry.status = "pending"
            entry.resolvability_score = 50
            entry.issues.append("NOT CHECKED: insufficient title metadata for DOI identity comparison")
            entry.teaching_note = (
                "The DOI resolves, but the local or Crossref title is missing. Add or verify the title "
                "before treating this final-source citation as identity-confirmed."
            )

        if entry.api_year and entry.year:
            try:
                entry.year_matches = int(entry.year) == int(entry.api_year)
            except (ValueError, TypeError):
                pass
            if not entry.year_matches:
                entry.issues.append(f"Year warning: bank={entry.year}, API={entry.api_year}")
                entry.teaching_note += (
                    " Publication year differs; online/print dating can vary, so this remains a warning "
                    "and does not override the title/author identity verdict."
                )

        report.entries.append(entry)

    # ---- gap analysis ----
    type_counts: dict[str, int] = {k: 0 for k in CITATION_TYPES}
    for entry in report.entries:
        type_counts[entry.citation_type] = type_counts.get(entry.citation_type, 0) + 1
    total = len(report.entries) or 1

    for ctype, label in CITATION_TYPES.items():
        count = type_counts[ctype]
        ratio = count / total
        guidance = SCENE_CITATION_GUIDANCE.get(scene, {}).get(ctype, "")
        if ratio < 0.05 and ctype != "critique":
            report.gap_analysis[ctype] = (
                f"**Missing {label}s.** Only {count} of {total} entries ({ratio:.0%}). "
                f"{guidance} Consider adding 1-3 {label} references."
            )

    # ---- replacement recommendations for dead citations ----
    dead_entries = [e for e in report.entries if e.status == "dead"]
    if dead_entries:
        report.replacement_recommendations.append(
            f"{len(dead_entries)} dead DOIs detected. For each: (1) verify the paper exists via Google Scholar, "
            "(2) find the correct DOI, (3) update the citation bank, (4) re-run this audit."
        )

    # ---- overall score ----
    if report.entries:
        scores = [(e.resolvability_score + e.recency_score) / 2 for e in report.entries]
        report.overall_score = int(sum(scores) / len(scores))

    return report


# ---------------------------------------------------------------------------
# Markdown output
# ---------------------------------------------------------------------------

def to_markdown(report: CitationQualityReport, status: str = "") -> str:
    lines = [
        "# Citation Quality Audit",
        "",
        f"- Output directory: `{report.output_dir}`",
        f"- Scene: {report.scene}",
        f"- Target citation count: {report.target_count}",
        f"- Entries analyzed: {len(report.entries)}",
        f"- DOI API coverage: {report.doi_api_checked} checked; "
        f"{report.not_checked_due_to_limit} not checked due to --max-dois={report.doi_api_limit}",
        f"- Verified: {report.verified_count} | Mismatched: {report.mismatched_count} | Dead: {report.dead_count}",
        f"- Overall quality score: {report.overall_score}/100",
    ]
    if status:
        lines.append(f"- Status: {status}")
    lines.extend([
        "",
        "> Each entry below includes a teaching note explaining *why* the citation quality matters.",
        "",
        "## Per-Citation Analysis",
        "",
        "| ID | DOI | Type | Resolves | Title Match | Author Match | Year Match | Score | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for e in report.entries:
        identifier = e.doi[:30] if e.doi else (e.manual_identifier[:30] if e.manual_identifier else "-")
        lines.append(
            f"| {e.candidate_id} | {identifier} | {e.citation_type} | "
            f"{'yes' if e.doi_resolves else 'no'} | {e.title_similarity:.0%} | "
            f"{('yes' if e.author_matches else 'no') if e.author_matches is not None else 'not checked'} | "
            f"{'yes' if e.year_matches else 'no'} | {((e.resolvability_score + e.recency_score) // 2)} | "
            f"{e.status} |"
        )
    lines.append("")

    # detailed entries with teaching notes
    for e in report.entries:
        if e.status == "verified":
            continue
        lines.append(f"### {e.candidate_id} — {e.doi}")
        lines.append("")
        # Per-entry verification is diagnostic.  Reserve the terminal
        # ``Status:`` contract for the report-level hard gate.
        lines.append(f"Verification state: **{e.status}**")
        if e.issues:
            lines.append("")
            lines.extend(f"- {issue}" for issue in e.issues)
        if e.teaching_note:
            lines.append("")
            lines.append(f"> {e.teaching_note}")
        lines.append("")

    # gap analysis
    if report.gap_analysis:
        lines.append("## Citation Diversity Gaps")
        lines.append("")
        for analysis in report.gap_analysis.values():
            lines.append(analysis)
            lines.append("")
        lines.append("")

    # replacement recommendations
    if report.replacement_recommendations:
        lines.append("## Replacement Recommendations")
        lines.append("")
        for rec in report.replacement_recommendations:
            lines.append(f"- {rec}")
        lines.append("")

    # scene-specific guidance
    lines.append("## Scene-Specific Citation Strategy")
    lines.append("")
    lines.append(f"For **{report.scene}** papers, your citation strategy should:")
    lines.append("")
    guidance = SCENE_CITATION_GUIDANCE.get(report.scene, {})
    for ctype, guide in guidance.items():
        lines.append(f"- **{CITATION_TYPES[ctype]}**: {guide}")
    lines.append("")

    # top-level teaching
    lines.append("## Citation Strategy Principles")
    lines.append("")
    lines.append("- **Diversity over density.** A narrow citation pool makes your Introduction read as insular. "
                 "Mix SOTA, foundational, benchmark, survey, and application papers.")
    lines.append("- **Recency signals engagement.** Most citations should be from the last 3 years. "
                 "Older citations are fine for foundational work, but they need a reason to be there.")
    lines.append("- **Identity is non-negotiable.** A DOI lookup alone is insufficient: the cited title and, "
                 "when extractable, first author must identify the same work. Unavailable metadata stays "
                 "NOT CHECKED until a publisher or database record can be reviewed.")
    lines.append("- **Type matters by venue.** Journals expect deep SOTA coverage. Reports expect broad survey coverage. "
                 "Competitions expect benchmark and leaderboard coverage. Match your strategy to your scene.")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    out_dir = Path(args.output_dir)
    if not out_dir.is_dir():
        print(f"Output directory not found: {out_dir}", file=sys.stderr)
        return 2

    report = audit_citations(out_dir, args.no_api, args.timeout, args.delay, args.max_dois)

    total = len(report.entries) or 1
    error_ratio = report.error_count / total
    pending_ratio = report.pending_count / total
    failures: list[str] = []

    if report.dead_count:
        failures.append(f"Dead citations: {report.dead_count}; replace or remove every dead entry")
    if report.mismatched_count:
        failures.append(f"Mismatched citations: {report.mismatched_count}; correct every metadata mismatch")
    if report.not_checked_due_to_limit:
        failures.append(
            f"Final-source DOI coverage incomplete: {report.not_checked_due_to_limit} citation(s) were "
            f"NOT CHECKED because --max-dois={report.doi_api_limit}; increase the limit or audit explicit batches"
        )

    if report.overall_score < args.min_score:
        failures.append(f"Overall score {report.overall_score} below minimum {args.min_score}")
    if error_ratio > args.max_error_ratio:
        failures.append(f"Error ratio {error_ratio:.2f} exceeds maximum {args.max_error_ratio}")
    if pending_ratio > args.max_pending_ratio:
        failures.append(f"Pending ratio {pending_ratio:.2f} exceeds maximum {args.max_pending_ratio}")

    status = "PASS" if not failures else "FAIL"

    if args.json:
        print(json.dumps({
            "output_dir": str(out_dir), "scene": report.scene,
            "verified": report.verified_count, "mismatched": report.mismatched_count,
            "dead": report.dead_count, "overall_score": report.overall_score,
            "status": status, "error_count": report.error_count,
            "pending_count": report.pending_count,
            "doi_api_limit": report.doi_api_limit,
            "doi_api_checked": report.doi_api_checked,
            "not_checked_due_to_limit": report.not_checked_due_to_limit,
            "error_ratio": round(error_ratio, 4),
            "pending_ratio": round(pending_ratio, 4),
            "failures": failures,
            "gap_analysis": report.gap_analysis,
        }, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(to_markdown(report, status))

    if args.write:
        report_path = out_dir / "citation_quality_audit.md"
        report_path.write_text(to_markdown(report, status), encoding="utf-8")
        print(f"Wrote {report_path}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
