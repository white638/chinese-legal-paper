#!/usr/bin/env python3
"""Snowball citation chasing on OpenAlex. Stdlib only.

Seed one work (DOI / OpenAlex ID / --title), then chase the citation graph:
  backward = its reference list, resolved to full records (奠基文献从这里挖)
  forward  = works citing it via filter=cites: (最新对话对象从这里挖)
  related  = OpenAlex related_works (算法相关推荐)

Usage:
  python openalex_snowball.py 10.1162/isec_a_00351 [--direction all|back|forward|related]
         [--limit 30] [--from-year 2020] [--sort cited|date] [--type article]
         [--json] [--mailto you@example.com]
  python openalex_snowball.py --title "Weaponized Interdependence" --direction forward

Outputs one markdown table per direction (title/authors/venue/year/cited/DOI),
or full JSON with reconstructed abstracts and OA pdf links via --json.
"""
import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from resource_guard import require_resource_authorization

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

API = "https://api.openalex.org/works"
UA = {"User-Agent": "avereth-intl/1.0"}
MAX_REF_CHUNKS = 10  # resolve at most 10*50=500 references


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def rebuild_abstract(inv: dict | None, limit: int = 800) -> str:
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    text = " ".join(pos[i] for i in sorted(pos))
    return text[:limit]


def to_row(w: dict) -> dict:
    auths = [x.get("author", {}).get("display_name", "") for x in w.get("authorships", [])]
    src = (w.get("primary_location") or {}).get("source") or {}
    oa = w.get("best_oa_location") or {}
    return {
        "title": w.get("title") or w.get("display_name", ""),
        "authors": auths[:3] + (["et al."] if len(auths) > 3 else []),
        "venue": src.get("display_name", ""),
        "year": w.get("publication_year"),
        "cited_by": w.get("cited_by_count", 0),
        "doi": (w.get("doi") or "").replace("https://doi.org/", ""),
        "type": w.get("type", ""),
        "openalex": w.get("id", ""),
        "oa_pdf": oa.get("pdf_url") or "",
        "abstract": rebuild_abstract(w.get("abstract_inverted_index")),
    }


def resolve_seed(a, mailto: str) -> dict:
    q = {"mailto": mailto} if mailto else {}
    if a.title:
        params = {"search": a.title, "per-page": "1", **q}
        data = fetch(API + "?" + urllib.parse.urlencode(params))
        if not data.get("results"):
            sys.exit(f"No OpenAlex work found for title: {a.title!r}")
        return data["results"][0]
    seed = a.seed.strip()
    if seed.startswith("https://openalex.org/"):
        seed = seed.rsplit("/", 1)[-1]
    if seed.startswith(("W", "w")) and seed[1:].isdigit():
        ident = seed.upper()
    else:
        doi = seed.replace("https://doi.org/", "").removeprefix("doi:")
        ident = "doi:" + doi
    url = f"{API}/{ident}"
    if q:
        url += "?" + urllib.parse.urlencode(q)
    try:
        return fetch(url)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit(f"Seed not found on OpenAlex: {seed!r} (Chinese-only CNKI items "
                     "usually are not indexed; snowball is for foreign literature)")
        raise


def chase_backward(seed: dict, a, q: dict) -> list[dict]:
    ref_ids = [r.rsplit("/", 1)[-1] for r in seed.get("referenced_works", [])]
    if not ref_ids:
        return []
    chunks = [ref_ids[i:i + 50] for i in range(0, len(ref_ids), 50)]
    if len(chunks) > MAX_REF_CHUNKS:
        print(f"(reference list has {len(ref_ids)} items; resolving first "
              f"{MAX_REF_CHUNKS * 50} only)", file=sys.stderr)
        chunks = chunks[:MAX_REF_CHUNKS]
    rows = []
    for c in chunks:
        params = {"filter": "openalex:" + "|".join(c), "per-page": "50", **q}
        data = fetch(API + "?" + urllib.parse.urlencode(params))
        rows += [to_row(w) for w in data.get("results", [])]
        time.sleep(0.15)
    if a.from_year:
        rows = [r for r in rows if (r["year"] or 0) >= a.from_year]
    if a.wtype:
        rows = [r for r in rows if r["type"] == a.wtype]
    key = (lambda r: r["cited_by"]) if a.sort == "cited" else (lambda r: r["year"] or 0)
    rows.sort(key=key, reverse=True)
    return rows[:a.limit]


def chase_forward(seed_id: str, a, q: dict) -> tuple[int, list[dict]]:
    filters = [f"cites:{seed_id}"]
    if a.from_year:
        filters.append(f"from_publication_date:{a.from_year}-01-01")
    if a.wtype:
        filters.append(f"type:{a.wtype}")
    sort = "cited_by_count:desc" if a.sort == "cited" else "publication_date:desc"
    rows, cursor, total = [], "*", 0
    while len(rows) < a.limit and cursor:
        params = {"filter": ",".join(filters), "per-page": "50", "sort": sort,
                  "cursor": cursor, **q}
        data = fetch(API + "?" + urllib.parse.urlencode(params))
        total = data.get("meta", {}).get("count", 0)
        rows += [to_row(w) for w in data.get("results", [])]
        cursor = data.get("meta", {}).get("next_cursor")
        time.sleep(0.15)
    return total, rows[:a.limit]


def chase_related(seed: dict, q: dict) -> list[dict]:
    rel = [r.rsplit("/", 1)[-1] for r in seed.get("related_works", [])]
    if not rel:
        return []
    params = {"filter": "openalex:" + "|".join(rel), "per-page": "50", **q}
    data = fetch(API + "?" + urllib.parse.urlencode(params))
    rows = [to_row(w) for w in data.get("results", [])]
    rows.sort(key=lambda r: r["cited_by"], reverse=True)
    return rows


def disruption_index(seed: dict, seed_id: str, q: dict, *, window: int, sample: int) -> dict:
    """SciNet-style disruption index (n_i - n_j) / (n_i + n_j) from OpenAlex.

    n_i = citers of the seed that cite none of the seed's references (the seed
    displaced its predecessors); n_j = citers that also cite at least one
    reference (the seed is read alongside its predecessors). n_k is omitted
    (the full Funk & Owen-Smith CD index needs the citers of every reference).
    Screening signal for seed selection only; never load-bearing evidence.
    """
    refs = {r.rsplit("/", 1)[-1] for r in seed.get("referenced_works", [])}
    year = seed.get("publication_year")
    filters = [f"cites:{seed_id}"]
    if isinstance(year, int) and window > 0:
        filters.append(f"from_publication_date:{year}-01-01")
        filters.append(f"to_publication_date:{year + window}-12-31")
    n_i = n_j = scanned = total = 0
    cursor = "*"
    while scanned < sample and cursor:
        params = {"filter": ",".join(filters), "per-page": str(min(200, sample - scanned)),
                  "select": "id,referenced_works", "sort": "publication_date:asc",
                  "cursor": cursor, **q}
        data = fetch(API + "?" + urllib.parse.urlencode(params))
        total = data.get("meta", {}).get("count", 0)
        results = data.get("results", [])
        if not results:
            break
        for work in results:
            scanned += 1
            citer_refs = {r.rsplit("/", 1)[-1] for r in work.get("referenced_works", [])}
            if citer_refs & refs:
                n_j += 1
            else:
                n_i += 1
        cursor = data.get("meta", {}).get("next_cursor")
        time.sleep(0.15)
    denominator = n_i + n_j
    return {
        "n_i": n_i,
        "n_j": n_j,
        "cd": round((n_i - n_j) / denominator, 3) if denominator else None,
        "scanned_citers": scanned,
        "citers_in_window": total,
        "window_years": window,
        "seed_reference_count": len(refs),
        "definition": "(n_i - n_j) / (n_i + n_j); n_k omitted; -1 consolidating ... +1 disruptive; "
                      "screening signal only, not load-bearing evidence",
    }


def print_table(rows: list[dict]) -> None:
    print("| # | Title | Authors | Venue | Year | Cited | DOI |")
    print("|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        print(f"| {i} | {r['title'][:70]} | {'; '.join(r['authors'])[:40]} | "
              f"{r['venue'][:30]} | {r['year']} | {r['cited_by']} | {r['doi']} |")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("seed", nargs="?", help="DOI or OpenAlex ID (or use --title)")
    ap.add_argument("--title", help="resolve seed by title search (top hit)")
    ap.add_argument("--direction", choices=["all", "back", "forward", "related"],
                    default="all")
    ap.add_argument("--limit", type=int, default=30, help="per direction (default 30)")
    ap.add_argument("--from-year", type=int)
    ap.add_argument("--sort", choices=["cited", "date"], default="cited")
    ap.add_argument("--type", dest="wtype")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mailto", default="")
    ap.add_argument("--cd-index", action="store_true",
                    help="also compute the (n_i - n_j)/(n_i + n_j) disruption index of the seed")
    ap.add_argument("--cd-window", type=int, default=5,
                    help="citation window in years after publication for --cd-index (0 = all)")
    ap.add_argument("--cd-sample", type=int, default=200,
                    help="max citers scanned for --cd-index (default 200)")
    ap.add_argument("--workspace", type=Path, required=True,
                    help="workspace whose PASS F2 contract authorizes directed retrieval")
    a = ap.parse_args()
    if not a.seed and not a.title:
        ap.error("give a DOI/OpenAlex ID or --title")
    try:
        require_resource_authorization(a.workspace, "directed_retrieval")
    except RuntimeError as exc:
        ap.error(str(exc))

    q = {"mailto": a.mailto} if a.mailto else {}
    seed = resolve_seed(a, a.mailto)
    seed_row = to_row(seed)
    seed_id = seed["id"].rsplit("/", 1)[-1]

    out = {"seed": seed_row}
    if a.direction in ("all", "back"):
        out["backward"] = chase_backward(seed, a, q)
    if a.direction in ("all", "forward"):
        out["forward_total"], out["forward"] = chase_forward(seed_id, a, q)
    if a.direction in ("all", "related"):
        out["related"] = chase_related(seed, q)
    if a.cd_index:
        out["disruption"] = disruption_index(seed, seed_id, q, window=a.cd_window, sample=a.cd_sample)

    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0

    print(f"Seed: {seed_row['title']} ({seed_row['year']}, {seed_row['venue']}; "
          f"cited {seed_row['cited_by']}; DOI {seed_row['doi'] or '-'}; {seed_id})")
    if a.title:
        print("(resolved from --title top hit — confirm this is the intended work)")
    n_refs = len(seed.get("referenced_works", []))
    if "backward" in out:
        print(f"\n## Backward: {n_refs} references, top {len(out['backward'])} "
              f"by {a.sort}\n")
        print_table(out["backward"])
    if "forward" in out:
        print(f"\n## Forward: {out['forward_total']} citing works, top "
              f"{len(out['forward'])} by {a.sort}\n")
        print_table(out["forward"])
    if "related" in out:
        print(f"\n## Related: {len(out['related'])} algorithmic neighbors\n")
        print_table(out["related"])
    if "disruption" in out:
        d = out["disruption"]
        print()
        print(f"## Disruption index (window {d['window_years']}y, n_k omitted): "
              f"CD = {d['cd']} from n_i={d['n_i']}, n_j={d['n_j']} over "
              f"{d['scanned_citers']}/{d['citers_in_window']} citers; seed has {d['seed_reference_count']} references")
        print("(screening signal for seed selection only; consolidating reviews sit near -1, "
              "displacing works near +1; never cite it as evidence)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
