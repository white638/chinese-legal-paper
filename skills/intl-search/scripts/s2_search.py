#!/usr/bin/env python3
"""Semantic Scholar channel. Stdlib only. OpenAlex stays primary — use S2 only for
its unique assets: TLDR summaries, citation contexts, and paper recommendations.

Shared-pool 429s are NORMAL without a key; set env S2_API_KEY (free to request)
for stable access. On persistent 429 this exits with code 2 — fall back to OpenAlex.

Usage:
  python s2_search.py search "weaponized interdependence" [--limit 10] [--year 2019-]
  python s2_search.py cites 10.1162/isec_a_00351 [--limit 20] [--influential]
  python s2_search.py refs  10.1162/isec_a_00351 [--limit 20]
  python s2_search.py recommend 10.1162/isec_a_00351 [--limit 10]
All subcommands accept --json. IDs: bare DOI, DOI:..., ARXIV:..., or S2 paperId.

NOTE: `cites`/`refs` contexts are sentences from OTHER papers citing/being cited.
They are leads for locating claims, not verified support sentences — always verify
against the original text before entering the citation bank.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GRAPH = "https://api.semanticscholar.org/graph/v1"
RECO = "https://api.semanticscholar.org/recommendations/v1"
PAPER_FIELDS = "title,year,venue,citationCount,influentialCitationCount,externalIds"


def get(url: str) -> dict:
    headers = {"User-Agent": "avereth-intl/1.0"}
    key = os.environ.get("S2_API_KEY", "").strip()
    if key:
        headers["x-api-key"] = key
    for i, wait in enumerate((15, 30, 45)):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"429 rate-limited (shared pool), retry in {wait}s "
                      f"({i + 1}/3)...", file=sys.stderr)
                time.sleep(wait)
                continue
            if e.code == 404:
                sys.exit("Paper not found on Semantic Scholar for this ID.")
            raise
    print("Still 429 after 3 retries. Set S2_API_KEY or use OpenAlex "
          "(openalex_search.py / openalex_snowball.py) instead.", file=sys.stderr)
    sys.exit(2)


def norm_id(s: str) -> str:
    s = s.strip().replace("https://doi.org/", "")
    if ":" in s.split("/")[0]:  # DOI:, ARXIV:, PMID:, CorpusId:
        return s
    if s.startswith("10.") and "/" in s:
        return "DOI:" + s
    return s  # assume S2 paperId hash


def doi_of(p: dict) -> str:
    return (p.get("externalIds") or {}).get("DOI", "") or ""


def print_papers(papers: list[dict], with_tldr: bool = False) -> None:
    print("| # | Title | Year | Venue | Cited | Infl. | DOI |")
    print("|---|---|---|---|---|---|---|")
    for i, p in enumerate(papers, 1):
        print(f"| {i} | {(p.get('title') or '')[:70]} | {p.get('year')} | "
              f"{(p.get('venue') or '')[:30]} | {p.get('citationCount', 0)} | "
              f"{p.get('influentialCitationCount', 0)} | {doi_of(p)} |")
    if with_tldr:
        for i, p in enumerate(papers, 1):
            t = (p.get("tldr") or {}).get("text")
            if t:
                print(f"\nTLDR {i}: {t}")


def cmd_search(a) -> dict:
    params = {"query": a.query, "limit": str(a.limit),
              "fields": PAPER_FIELDS + ",tldr,abstract"}
    if a.year:
        params["year"] = a.year
    if a.fos:
        params["fieldsOfStudy"] = a.fos
    data = get(f"{GRAPH}/paper/search?" + urllib.parse.urlencode(params))
    papers = data.get("data", [])
    if not a.json:
        print(f"Semantic Scholar: {data.get('total', '?')} hits for {a.query!r} "
              f"(showing {len(papers)})\n")
        print_papers(papers, with_tldr=True)
    return {"total": data.get("total"), "rows": papers}


def cmd_edges(a, kind: str) -> dict:
    inner = "citingPaper" if kind == "citations" else "citedPaper"
    fields = ",".join(f"{inner}.{f}" for f in PAPER_FIELDS.split(","))
    fields += ",contexts,intents,isInfluential"
    params = {"fields": fields, "limit": str(a.limit)}
    data = get(f"{GRAPH}/paper/{norm_id(a.id)}/{kind}?" + urllib.parse.urlencode(params))
    edges = data.get("data", [])
    if getattr(a, "influential", False):
        edges = [e for e in edges if e.get("isInfluential")]
    rows = []
    for e in edges:
        p = e.get(inner) or {}
        rows.append({**p, "contexts": e.get("contexts") or [],
                     "intents": e.get("intents") or [],
                     "isInfluential": e.get("isInfluential", False)})
    if not a.json:
        label = "citing" if kind == "citations" else "referenced"
        print(f"{len(rows)} {label} papers for {a.id} "
              "(contexts are from citing papers — verify in the original before use)\n")
        print_papers(rows)
        for i, r in enumerate(rows, 1):
            for c in r["contexts"][:2]:
                print(f'\n[{i}] context: "{c[:300]}"')
    return {"rows": rows}


def cmd_recommend(a) -> dict:
    params = {"fields": PAPER_FIELDS, "limit": str(a.limit)}
    data = get(f"{RECO}/papers/forpaper/{norm_id(a.id)}?" + urllib.parse.urlencode(params))
    papers = data.get("recommendedPapers", [])
    if not a.json:
        print(f"{len(papers)} recommendations for {a.id}\n")
        print_papers(papers)
    return {"rows": papers}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="keyword search with TLDR")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--year", help='e.g. "2019-" or "2019-2024"')
    s.add_argument("--fos", help='fieldsOfStudy, e.g. "Political Science"')
    s.add_argument("--json", action="store_true")

    for name, help_ in (("cites", "papers citing ID, with citation contexts"),
                        ("refs", "papers referenced by ID, with contexts")):
        c = sub.add_parser(name, help=help_)
        c.add_argument("id")
        c.add_argument("--limit", type=int, default=20)
        c.add_argument("--influential", action="store_true",
                       help="keep only isInfluential edges")
        c.add_argument("--json", action="store_true")

    r = sub.add_parser("recommend", help="S2 recommendations for a seed paper")
    r.add_argument("id")
    r.add_argument("--limit", type=int, default=10)
    r.add_argument("--json", action="store_true")

    a = ap.parse_args()
    if a.cmd == "search":
        out = cmd_search(a)
    elif a.cmd == "cites":
        out = cmd_edges(a, "citations")
    elif a.cmd == "refs":
        out = cmd_edges(a, "references")
    else:
        out = cmd_recommend(a)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
