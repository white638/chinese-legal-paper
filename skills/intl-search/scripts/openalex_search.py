#!/usr/bin/env python3
"""Search OpenAlex (works) for international literature. Stdlib only.

Usage:
  python openalex_search.py "QUERY" [--per-page 15] [--pages 1] [--from-year 2020]
         [--sort cited|relevance|date] [--type article|review|book-chapter]
         [--language en] [--oa] [--json] [--mailto you@example.com]

Outputs a markdown table by default (title/authors/venue/year/cited/DOI),
or full JSON rows with reconstructed abstracts and OA pdf links via --json.
--pages N walks the cursor for N pages (per-page x N rows total).
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from resource_guard import require_resource_authorization

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://api.openalex.org/works"
SORT = {"cited": "cited_by_count:desc", "date": "publication_date:desc", "relevance": "relevance_score:desc"}


def rebuild_abstract(inv: dict | None, limit: int = 800) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    text = " ".join(pos[i] for i in sorted(pos))
    return text[:limit]


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "avereth-intl/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--per-page", type=int, default=15)
    ap.add_argument("--pages", type=int, default=1, help="cursor-walk N pages")
    ap.add_argument("--from-year", type=int)
    ap.add_argument("--to-year", type=int)
    ap.add_argument("--sort", choices=list(SORT), default="relevance")
    ap.add_argument("--type", dest="wtype")
    ap.add_argument("--language", help="e.g. en / zh")
    ap.add_argument("--oa", action="store_true", help="open-access works only")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mailto", default="")
    ap.add_argument("--workspace", type=Path, help="workspace used for F2 authorization when --pages exceeds 1")
    a = ap.parse_args()
    if a.pages > 1:
        try:
            require_resource_authorization(a.workspace, "directed_retrieval")
        except RuntimeError as exc:
            ap.error(str(exc))

    filters = []
    if a.from_year:
        filters.append(f"from_publication_date:{a.from_year}-01-01")
    if a.to_year:
        filters.append(f"to_publication_date:{a.to_year}-12-31")
    if a.wtype:
        filters.append(f"type:{a.wtype}")
    if a.language:
        filters.append(f"language:{a.language}")
    if a.oa:
        filters.append("open_access.is_oa:true")

    params = {"search": a.query, "per-page": str(a.per_page), "sort": SORT[a.sort]}
    if filters:
        params["filter"] = ",".join(filters)
    if a.mailto:
        params["mailto"] = a.mailto

    rows, cursor, count = [], "*", "?"
    for _ in range(max(1, a.pages)):
        if not cursor:
            break
        data = fetch(API + "?" + urllib.parse.urlencode({**params, "cursor": cursor}))
        count = data.get("meta", {}).get("count", "?")
        cursor = data.get("meta", {}).get("next_cursor")
        for w in data.get("results", []):
            auths = [x.get("author", {}).get("display_name", "") for x in w.get("authorships", [])]
            src = (w.get("primary_location") or {}).get("source") or {}
            rows.append({
                "title": w.get("title") or w.get("display_name", ""),
                "authors": auths[:3] + (["et al."] if len(auths) > 3 else []),
                "venue": src.get("display_name", ""),
                "year": w.get("publication_year"),
                "cited_by": w.get("cited_by_count", 0),
                "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
                "type": w.get("type", ""),
                "openalex": w.get("id", ""),
                "oa_pdf": ((w.get("best_oa_location") or {}).get("pdf_url")) or "",
                # True 是警示不是判决：OpenAlex 将 Crossref/Retraction Watch 的
                # 更正/关注表达也并入此布尔值，须回出版社页面核对真实状态
                "is_retracted": bool(w.get("is_retracted")),
                "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
            })

    if a.json:
        print(json.dumps({"count": count, "rows": rows},
                         ensure_ascii=False, indent=1))
    else:
        print(f"OpenAlex: {count} hits for {a.query!r} "
              f"(showing {len(rows)}, sort={a.sort})\n")
        print("| # | Title | Authors | Venue | Year | Cited | DOI |")
        print("|---|---|---|---|---|---|---|")
        for i, r in enumerate(rows, 1):
            print(f"| {i} | {r['title'][:70]} | {'; '.join(r['authors'])[:40]} | "
                  f"{r['venue'][:30]} | {r['year']} | {r['cited_by']} | {r['doi']} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
