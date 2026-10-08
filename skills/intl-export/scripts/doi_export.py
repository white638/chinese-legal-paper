#!/usr/bin/env python3
"""Export references for DOIs: BibTeX (via doi.org content negotiation)
plus GB/T 7714 foreign-literature strings (built from Crossref JSON).

Usage:
  python doi_export.py 10.1086/694845 10.1017/S0305741023001234 ...
  python doi_export.py --file dois.txt --out refs.md

Stdlib only. Retries once on transient failures.
"""
import argparse
import datetime as _dt
import json
import re
import sys
import time
import urllib.request

# Crossref ``type`` -> GB/T 7714-2015 document-type mark.  The template used to
# render each type is chosen by TYPE_FAMILY below; the mark is only the tag.
TYPE_MARK = {
    "journal-article": "J",
    "book": "M", "monograph": "M", "edited-book": "M", "reference-book": "M",
    "book-chapter": "M", "book-section": "M", "book-part": "M",
    "reference-entry": "M",
    "proceedings-article": "C",
    "dissertation": "D",
    "report": "R",
    "standard": "S",
    "posted-content": "EB/OL", "preprint": "EB/OL",
    "dataset": "DS/OL",
}

# Crossref ``type`` -> rendering family (which GB/T 7714-2015 template to use).
TYPE_FAMILY = {
    "journal-article": "journal",
    "book": "book", "monograph": "book", "edited-book": "book",
    "reference-book": "book", "standard": "book",
    "book-chapter": "chapter", "book-section": "chapter", "book-part": "chapter",
    "reference-entry": "chapter",
    "proceedings-article": "proceedings",
    "dissertation": "dissertation",
    "report": "report",
    "posted-content": "online", "preprint": "online",
    "dataset": "dataset",
}

YEAR_KEYS = ("published-print", "published-online", "issued", "posted", "created")


def get(url: str, accept: str) -> str:
    req = urllib.request.Request(url, headers={
        "Accept": accept, "User-Agent": "avereth-intl/1.0 (mailto:user@example.com)"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2)
    return ""


def _ws(text) -> str:
    """Collapse whitespace; Crossref titles often carry newlines."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _first(m: dict, key: str) -> str:
    """First element of a Crossref list field (or the scalar itself)."""
    value = m.get(key)
    if isinstance(value, list):
        return _ws(value[0]) if value and value[0] else ""
    return _ws(value)


def _date_parts(m: dict, keys=YEAR_KEYS) -> list:
    for k in keys:
        parts = (m.get(k) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            return [int(x) for x in parts[0] if x]
    return []


def _year(m: dict, keys=YEAR_KEYS) -> str:
    parts = _date_parts(m, keys)
    return str(parts[0]) if parts else ""


def _ymd(m: dict, keys) -> str:
    """YYYY-MM-DD when Crossref has a full date, YYYY-MM or YYYY otherwise."""
    parts = _date_parts(m, keys)
    if not parts:
        return ""
    if len(parts) >= 3:
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    if len(parts) == 2:
        return f"{parts[0]:04d}-{parts[1]:02d}"
    return str(parts[0])


def gbt_person(a: dict) -> str:
    """GB/T 7714-2015 foreign name: FAMILY in capitals + initials without dots.

    Corporate authors (Crossref ``name`` without family/given) are kept as-is.
    """
    if not (a.get("family") or a.get("given")):
        return _ws(a.get("name"))
    family = _ws(a.get("family")).upper()
    given = a.get("given") or ""
    # Split on whitespace/dots only: a hyphenated given name ("Ling-yuh") is
    # one name unit and yields one initial, as in the GB/T 7714-2015 examples.
    initials = " ".join(p[0].upper() for p in re.split(r"[\s.]+", given) if p)
    return f"{family} {initials}".strip()


def gbt_authors(authors: list, role: str = "") -> str:
    """<=3 responsible parties listed in full, >3 -> first three + ``et al``.

    ``role`` (e.g. ``ed``/``eds``/``trans``) is appended after a comma, the way
    GB/T 7714-2015 marks other responsibility (``译``/``编``) in Chinese entries.
    """
    names = [n for n in (gbt_person(a) for a in (authors or [])[:3]) if n]
    if len(authors or []) > 3 and names:
        names.append("et al")
    text = ", ".join(names)
    if text and role:
        text += f", {role}"
    return text


def _title(m: dict) -> str:
    """``title: subtitle`` (GB/T 7714-2015 other-title-information rule)."""
    title = _first(m, "title")
    sub = _first(m, "subtitle")
    if sub and sub.lower() not in title.lower():
        title = f"{title}: {sub}" if title else sub
    return title


def _edition(m: dict) -> str:
    """``2nd ed`` etc.; first editions are not recorded (GB/T 7714-2015 8.3)."""
    raw = _ws(m.get("edition-number"))
    if not raw:
        return ""
    if raw.isdigit():
        n = int(raw)
        if n < 2:
            return ""
        suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
        return f"{n}{suffix} ed"
    return raw if re.search(r"\bed", raw, re.I) else f"{raw} ed"


def _institution(m: dict) -> tuple:
    """(name, place) of the first Crossref ``institution`` entry, if any."""
    inst = m.get("institution")
    if isinstance(inst, list):
        inst = inst[0] if inst else {}
    if not isinstance(inst, dict):
        return "", ""
    place = inst.get("place")
    if isinstance(place, list):
        place = place[0] if place else ""
    return _ws(inst.get("name")), _ws(place)


def _imprint(place: str, publisher: str, year: str, pages: str = "") -> str:
    """``Place: Publisher, Year: pages`` with graceful omission of any part."""
    head = f"{place}: {publisher}" if place and publisher else (publisher or place)
    if head and year:
        head = f"{head}, {year}"
    else:
        head = head or year
    if pages:
        head = f"{head}: {pages}" if head else pages
    return head


def _assemble(head: str, *segments: str) -> str:
    """Join non-empty segments with ``. `` and close with a full stop."""
    parts = [head] + [s for s in segments if s]
    return ". ".join(parts) + "."


def gbt7714(meta: dict, accessed: str = None) -> str:
    """Render one Crossref work as a GB/T 7714-2015 foreign-literature entry.

    ``accessed`` is the citation date written as ``[YYYY-MM-DD]`` for online
    types (EB/OL, DS/OL); it defaults to today.  Templates by family:

      journal      AUTHOR. Title[J]. Container, Year, Vol(Issue): Pages. DOI: x.
      book         AUTHOR. Title[M]. TRANSLATOR, trans. 2nd ed. Place: Publisher, Year. DOI: x.
      chapter      AUTHOR. Chapter[M]//EDITOR, eds. Book. Place: Publisher, Year: Pages. DOI: x.
      proceedings  AUTHOR. Title[C]//Proceedings. Place: Publisher, Year: Pages. DOI: x.
      dissertation AUTHOR. Title[D]. Place: Institution, Year. DOI: x.
      report       AUTHOR|INSTITUTION. Title[R]. Place: Publisher, Year. DOI: x.
      online       AUTHOR. Title[EB/OL]. (YYYY-MM-DD)[accessed]. https://doi.org/x.
      dataset      AUTHOR. Title[DS/OL]. Place: Publisher, Year[accessed]. https://doi.org/x.
    """
    m = meta["message"]
    ctype = _ws(m.get("type")).lower()
    family = TYPE_FAMILY.get(ctype)
    if family is None:
        family = "journal" if _first(m, "container-title") else "book"
    mark = TYPE_MARK.get(ctype, "J" if family == "journal" else "Z")
    accessed = accessed or _dt.date.today().isoformat()

    authors = gbt_authors(m.get("author") or [])
    editors_raw = m.get("editor") or []
    translators = gbt_authors(m.get("translator") or [], role="trans")
    title = _title(m)
    container = _first(m, "container-title")
    year = _year(m)
    vol = _ws(m.get("volume"))
    issue = _ws(m.get("issue"))
    pages = _ws(m.get("page"))
    doi = _ws(m.get("DOI"))
    publisher = _ws(m.get("publisher"))
    place = _ws(m.get("publisher-location"))
    inst_name, inst_place = _institution(m)

    # Responsible party: personal authors > editors (for edited books) >
    # institution (reports/datasets).  If none is known GB/T 7714-2015 lets the
    # entry start with the title.
    if not authors and family == "book" and editors_raw:
        authors = gbt_authors(editors_raw, role="ed" if len(editors_raw) == 1 else "eds")
    if not authors and family in ("report", "dataset", "dissertation"):
        authors = inst_name
    head = f"{authors}. {title}[{mark}]" if authors else f"{title}[{mark}]"
    doi_tail = f"DOI: {doi}" if doi else ""

    if family == "journal":
        body = ""
        if container:
            body = container
        if year:
            body = f"{body}, {year}" if body else year
        if vol:
            body += f", {vol}" if body else vol
            if issue:
                body += f"({issue})"
        elif issue:
            body += f"({issue})"
        if pages:
            body = f"{body}: {pages}" if body else pages
        return _assemble(head, body, doi_tail)

    if family == "book":
        return _assemble(head, translators, _edition(m),
                         _imprint(place, publisher, year), doi_tail)

    if family == "chapter":
        editors = gbt_authors(editors_raw, role="ed" if len(editors_raw) == 1 else "eds")
        host = ". ".join(x for x in (editors, container) if x)
        head = f"{head}//{host}" if host else head
        return _assemble(head, translators, _edition(m),
                         _imprint(place, publisher, year, pages), doi_tail)

    if family == "proceedings":
        event = m.get("event") or {}
        proceedings = container or _ws(event.get("name"))
        head = f"{head}//{proceedings}" if proceedings else head
        venue = place or _ws(event.get("location"))
        return _assemble(head, _imprint(venue, publisher, year, pages), doi_tail)

    if family == "dissertation":
        grantor = inst_name or publisher
        return _assemble(head, _imprint(inst_place or place, grantor, year), doi_tail)

    if family == "report":
        issuer = publisher or (inst_name if inst_name != authors else "")
        return _assemble(head, _imprint(place or inst_place, issuer, year), doi_tail)

    url = f"https://doi.org/{doi}" if doi else _ws(m.get("URL"))
    if family == "online":
        posted = _ymd(m, ("posted", "published-online", "issued", "created"))
        stamp = f"({posted})[{accessed}]" if posted else f"[{accessed}]"
        return _assemble(head, stamp, url)

    # dataset
    imprint = _imprint(place, publisher, year)
    stamp = f"{imprint}[{accessed}]" if imprint else f"[{accessed}]"
    return _assemble(head, stamp, url)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("dois", nargs="*")
    ap.add_argument("--file")
    ap.add_argument("--out")
    a = ap.parse_args()

    dois = list(a.dois)
    if a.file:
        dois += [ln.strip() for ln in open(a.file, encoding="utf-8") if ln.strip()]
    if not dois:
        ap.error("no DOIs given")

    blocks = []
    for doi in dois:
        doi = doi.replace("https://doi.org/", "").strip()
        try:
            bib = get(f"https://doi.org/{doi}", "application/x-bibtex").strip()
        except Exception as e:
            bib = f"% BibTeX fetch failed: {e}"
        try:
            meta = json.loads(get(f"https://api.crossref.org/works/{doi}", "application/json"))
            gbt = gbt7714(meta)
        except Exception as e:
            gbt = f"(GB/T 7714 build failed: {e})"
        blocks.append(f"## {doi}\n\n**GB/T 7714:** {gbt}\n\n```bibtex\n{bib}\n```\n")
        time.sleep(1)

    text = "\n".join(blocks)
    if a.out:
        from pathlib import Path
        Path(a.out).write_text(text, encoding="utf-8")
        print(f"written {a.out} ({len(dois)} refs)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
