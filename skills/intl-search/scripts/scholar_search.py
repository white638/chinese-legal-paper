#!/usr/bin/env python3
"""Low-frequency Google Scholar discovery through the optional scholarly package.

The command returns registry-shaped candidates but never writes the CNKI-Paper
registry. Google Scholar metadata remains discovery evidence only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from itertools import islice
from typing import Any, Callable
from urllib.parse import urlencode, urljoin


MIN_INTERVAL_SECONDS = 5.0
MAX_SEARCHES_PER_SESSION = 5
MAX_FIRST_PAGE_RESULTS = 10
PURPOSES = {
    "venue",
    "target-exemplar",
    "sota",
    "collision",
    "terminology",
    "snowball",
    "citation",
    "other",
}


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


class ScholarDependencyMissing(RuntimeError):
    pass


class ScholarBlocked(RuntimeError):
    pass


class ScholarSearchSession:
    """Enforce the same low-frequency budget used by the Chrome route."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.clock = clock
        self.sleeper = sleeper
        self.searches = 0
        self.last_started: float | None = None

    def run(self, operation: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
        if self.searches >= MAX_SEARCHES_PER_SESSION:
            raise ScholarBlocked("Google Scholar session limit reached (maximum 5 searches)")
        if self.last_started is not None:
            remaining = MIN_INTERVAL_SECONDS - (self.clock() - self.last_started)
            if remaining > 0:
                self.sleeper(remaining)
        self.last_started = self.clock()
        self.searches += 1
        return operation()


def scholar_query_url(
    query: str,
    *,
    year_low: int | None = None,
    year_high: int | None = None,
    sort_by: str = "relevance",
) -> str:
    params: dict[str, str | int] = {"q": query, "hl": "en"}
    if year_low is not None:
        params["as_ylo"] = year_low
    if year_high is not None:
        params["as_yhi"] = year_high
    if sort_by == "date":
        params["scisbd"] = 1
    return "https://scholar.google.com/scholar?" + urlencode(params)


def author_names(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(" and ") if part.strip()]
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            item = item.get("name") or item.get("display_name") or item.get("family")
        text = str(item or "").strip()
        if text:
            names.append(text)
    return names


def citation_count(value: Any) -> int:
    match = re.search(r"\d[\d,]*", str(value or ""))
    return int(match.group(0).replace(",", "")) if match else 0


def extract_doi(publication: dict[str, Any]) -> str:
    candidates = [
        publication.get("pub_url"),
        publication.get("eprint_url"),
        publication.get("citedby_url"),
        json.dumps(publication.get("bib") or {}, ensure_ascii=False),
    ]
    pattern = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
    for value in candidates:
        match = pattern.search(str(value or ""))
        if match:
            return match.group(0).rstrip(".,;)")
    return ""


def stable_result_url(publication: dict[str, Any]) -> str:
    for key in (
        "pub_url",
        "eprint_url",
        "url_scholarbib",
        "citedby_url",
        "url_related_articles",
    ):
        value = str(publication.get(key) or "").strip()
        if value:
            return urljoin("https://scholar.google.com", value)
    return ""


def publication_to_candidate(
    publication: dict[str, Any],
    *,
    query_id: str,
    rank: int,
    collected_at: str,
) -> dict[str, Any]:
    bib = publication.get("bib") if isinstance(publication.get("bib"), dict) else {}
    title = str(bib.get("title") or publication.get("title") or "").strip()
    authors = author_names(bib.get("author"))
    year_match = re.search(r"(?<!\d)((?:19|20)\d{2})(?!\d)", str(bib.get("pub_year") or ""))
    year = int(year_match.group(1)) if year_match else None
    url = stable_result_url(publication)
    metadata = {
        "discovery_adapter": "scholarly",
        "scholar_result_rank": rank,
        "scholar_bibliographic_line": str(bib.get("citation") or "").strip(),
        "scholar_snippet": str(bib.get("abstract") or "").strip(),
        "scholar_cited_by": citation_count(publication.get("num_citations")),
    }
    source: dict[str, Any] = {
        "source_id": f"GS-CAND-{rank:03d}",
        "channel": "Google Scholar",
        "roles": ["citation-candidate"],
        "title": title,
        "authors": authors,
        "venue": str(bib.get("venue") or "").strip(),
        "url": url,
        "query_ids": [query_id],
        "state": "discovered",
        "verification": {},
        "citation_scope": "candidate-only",
        "reason": "Google Scholar discovery candidate pending DOI/publisher or lawful-OA verification",
        "used_for": ["screening", "collision", "doi-recovery"],
        "collected_at": collected_at,
        "metadata": metadata,
        "registration_status": "ready" if title and year and url else "needs-manual-review",
    }
    if year is not None:
        source["publication_year"] = year
    doi = extract_doi(publication)
    if doi:
        source["doi"] = doi
    return source


def load_scholarly() -> Any:
    try:
        from scholarly import scholarly  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ScholarDependencyMissing(
            "scholarly is not installed; use controlled Chrome or install requirements-optional.txt"
        ) from exc
    return scholarly


def looks_blocked(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        marker in text
        for marker in ("captcha", "maxtries", "blocked", "google scholar cannot", "/sorry")
    )


def search_publications(
    query: str,
    *,
    query_id: str,
    purpose: str,
    limit: int = MAX_FIRST_PAGE_RESULTS,
    year_low: int | None = None,
    year_high: int | None = None,
    sort_by: str = "relevance",
    api: Any | None = None,
    session: ScholarSearchSession | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    if not 1 <= limit <= MAX_FIRST_PAGE_RESULTS:
        raise ValueError("limit must be between 1 and 10 (first page only)")
    if purpose not in PURPOSES:
        raise ValueError(f"unsupported purpose: {purpose}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,63}", query_id):
        raise ValueError("query_id is invalid")
    api = api or load_scholarly()
    session = session or ScholarSearchSession()
    collected_at = collected_at or date.today().isoformat()

    def collect() -> list[dict[str, Any]]:
        iterator = api.search_pubs(
            query,
            year_low=year_low,
            year_high=year_high,
            sort_by=sort_by,
        )
        return list(islice(iterator, limit))

    try:
        publications = session.run(collect)
    except Exception as exc:
        if looks_blocked(exc):
            raise ScholarBlocked(
                "Google Scholar blocked the request; do not retry automatically or configure a proxy"
            ) from exc
        raise

    query_url = scholar_query_url(
        query,
        year_low=year_low,
        year_high=year_high,
        sort_by=sort_by,
    )
    sources = [
        publication_to_candidate(
            publication,
            query_id=query_id,
            rank=rank,
            collected_at=collected_at,
        )
        for rank, publication in enumerate(publications, start=1)
    ]
    return {
        "query": {
            "query_id": query_id,
            "channel": "Google Scholar",
            "purpose": purpose,
            "query": query,
            "filters": {
                "year_low": year_low,
                "year_high": year_high,
                "sort": sort_by,
                "first_page_only": True,
                "max_results": limit,
                "adapter": "scholarly",
                "proxy": "none",
            },
            "result_count": len(sources),
            "result_count_is_approximate": True,
            "result_count_basis": "first-page-extracted",
            "result_count_note": (
                "scholarly does not expose Scholar's approximate total; "
                "this is the first-page extracted count and not a database total"
            ),
            "url": query_url,
            "collected_at": collected_at,
            "status": "complete",
        },
        "sources": sources,
        "limitations": [
            "Discovery metadata only; snippets and cited-by counts are not content verification.",
            "The parent cnki-paper controller must deduplicate and write literature_registry.json.",
            "No proxy, cookie, account, CAPTCHA bypass, pagination, or full-text download is used.",
        ],
    }


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("query")
    cli.add_argument("--query-id", default="Q-GS-001")
    cli.add_argument("--purpose", choices=sorted(PURPOSES), default="citation")
    cli.add_argument("--limit", type=int, default=MAX_FIRST_PAGE_RESULTS)
    cli.add_argument("--from-year", type=int)
    cli.add_argument("--to-year", type=int)
    cli.add_argument("--sort", choices=("relevance", "date"), default="relevance")
    cli.add_argument("--pretty", action="store_true")
    return cli


def main(argv: list[str] | None = None) -> int:
    configure_console()
    args = parser().parse_args(argv)
    try:
        payload = search_publications(
            args.query,
            query_id=args.query_id,
            purpose=args.purpose,
            limit=args.limit,
            year_low=args.from_year,
            year_high=args.to_year,
            sort_by=args.sort,
        )
    except ScholarDependencyMissing as exc:
        print(json.dumps({"status": "dependency-missing", "error": str(exc)}, ensure_ascii=False))
        return 3
    except ScholarBlocked as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False))
        return 2
    except (ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1
    except Exception as exc:
        print(
            json.dumps(
                {"status": "error", "error": f"{type(exc).__name__}: {exc}"},
                ensure_ascii=False,
            )
        )
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
