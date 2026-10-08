#!/usr/bin/env python3
"""Locate full quote candidates without granting page-evidence verification.

Exit 0 means every quote has one faithful candidate, 2 means review is needed,
and 1 means invalid input. Neither a hit nor exit 0 certifies source identity.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

from evidence_contract import (BASE_COLUMNS, BINDING_COLUMNS, cell, digest,
                               load_sources, source_digest, strict_text)


def normalize_map(text: str) -> tuple[str, list[int]]:
    chars, offsets = [], []
    for i, char in enumerate(text):
        for normalized in unicodedata.normalize("NFKC", char).casefold():
            if normalized.isalnum():
                chars.append(normalized)
                offsets.append(i)
    return "".join(chars), offsets


def normalize(text: str) -> str:
    """Loose candidate retrieval only; never use this for fidelity."""
    return normalize_map(text)[0]


class PdfIndex:
    def __init__(self, path: Path):
        import fitz

        self.path = path
        with fitz.open(path) as doc:
            self.texts = [page.get_text("text") for page in doc]
            self.labels = [page.get_label() or "" for page in doc]
        self._index()

    @classmethod
    def from_pages(cls, texts: list[str], labels: list[str] | None = None):
        obj = cls.__new__(cls)
        obj.path = Path("test-only.pdf")
        obj.texts, obj.labels = texts, labels or [""] * len(texts)
        obj._index()
        return obj

    def _index(self):
        self.raw, self.raw_page, self.page_ends = "", [], []
        for pno, text in enumerate(self.texts):
            self.raw += text + "\n"
            self.raw_page.extend([pno] * (len(text) + 1))
            self.page_ends.append((self.page_ends[-1] if self.page_ends else 0) + len(normalize(text)))
        self.norm, self.offsets = normalize_map(self.raw)
        self.page_of = [self.raw_page[i] for i in self.offsets]
        self.has_labels = any(self.labels)

    def printed(self, pdf_index: int, start_page: int | None):
        if self.labels[pdf_index]:
            return self.labels[pdf_index], "labels"
        if start_page is not None:
            return str(start_page + pdf_index), "start-page"
        return None, "pdf-index"

    def _spans(self, nq: str):
        if not nq:
            return []
        hits, start = [], 0
        while True:
            i = self.norm.find(nq, start)
            if i < 0:
                return hits
            hits.append((i, i + len(nq)))
            start = i + 1

    def find(self, norm_quote: str):
        return [(self.page_of[a], self.page_of[b - 1]) for a, b in self._spans(norm_quote)]

    def _cross_spans(self, nq: str, max_gap: int = 80, min_part: int = 6):
        spans = set()
        for end in self.page_ends[:-1]:
            for split in range(min_part, len(nq) - min_part + 1):
                a, b = nq[:split], nq[split:]
                for left, stop in self._spans(a):
                    if stop > end or end - stop > max_gap:
                        continue
                    for right, finish in self._spans(b):
                        if end <= right <= end + max_gap:
                            spans.add((left, finish))
        return sorted(spans)

    def find_across_pages(self, nq: str, max_gap: int = 80, min_part: int = 6):
        return [(self.page_of[a], self.page_of[b - 1])
                for a, b in self._cross_spans(nq, max_gap, min_part)]

    def candidates(self, quote: str, *, min_len: int = 8, start_page: int | None = None):
        nq = normalize(quote)
        if len(nq) < max(8, min_len):
            return []
        direct = self._spans(nq)
        spans = direct or self._cross_spans(nq)
        qnorm, qmap = normalize_map(quote)
        prefix, suffix = qmap[0], len(quote) - qmap[-1] - 1
        result = []
        for a, b in spans:
            left = max(0, self.offsets[a] - prefix)
            right = min(len(self.raw), self.offsets[b - 1] + 1 + suffix)
            raw = self.raw[left:right]
            faithful = strict_text(raw) == strict_text(quote)
            # A substring of a signed number is not the same quoted quantity.
            before, after = self.raw[:left].rstrip(), self.raw[right:].lstrip()
            if quote.lstrip()[:1].isdigit() and before and before[-1] in "+-−±<>=≤≥0123456789.":
                faithful = False
            if quote.rstrip()[-1:].isdigit() and after and (after[0] in "%‰²³⁰¹₀₁₂₃0123456789" or
                    (after[0] == "." and after[1:2].isdigit()) or
                    (self.raw[right:right + 1].isalpha())):
                faithful = False
            p1, p2 = self.page_of[a], self.page_of[b - 1]
            pr1, how1 = self.printed(p1, start_page)
            pr2, how2 = self.printed(p2, start_page)
            result.append({
                "file": str(self.path), "artifact_sha256": digest(self.path),
                "pdf_page_start": p1 + 1, "pdf_page_end": p2 + 1,
                "printed_start": pr1, "printed_end": pr2,
                "page_source": how1 if how1 == how2 else "mixed",
                "raw_start": left, "raw_end": right, "raw_text": raw,
                "context": self.raw[max(0, left - 80):min(len(self.raw), right + 80)],
                "fidelity": "exact_layout" if faithful else "review_required",
                "cross_page": p1 != p2, "retrieval": "full" if direct else "cross_page_candidate",
            })
        return result


def fmt_locator(p1, p2, *, pdf=False):
    prefix = "PDF " if pdf else ""
    return f"{prefix}第{p1}页" if p1 == p2 else f"{prefix}第{p1}-{p2}页"


def locate(indexes, quote, *, min_len=8, start_page=None):
    candidates = [hit for idx in indexes for hit in idx.candidates(quote, min_len=min_len, start_page=start_page)]
    return {"quote": quote, "found": bool(candidates), "candidates": candidates,
            "occurrences": len(candidates),
            "status": ("located" if len(candidates) == 1 and candidates[0]["fidelity"] == "exact_layout"
                       else "VERIFY"),
            "warning": "quote must contain at least 8 normalized characters" if len(normalize(quote)) < max(8, min_len) else ""}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--quote", action="append")
    ap.add_argument("--quotes-file")
    ap.add_argument("--start-page", type=int)
    ap.add_argument("--work", default="-")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--min-len", type=int, default=8)
    ap.add_argument("--registry", type=Path)
    ap.add_argument("--source-id")
    ap.add_argument("--page-basis", default="-", help="observed basis for publication-page mapping")
    ap.add_argument("--select-hit", type=int, help="one-based candidate choice; requires one quote")
    args = ap.parse_args()
    try:
        quotes = list(args.quote or [])
        if args.quotes_file:
            raw = Path(args.quotes_file).read_text(encoding="utf-8-sig")
            values = json.loads(raw) if args.quotes_file.lower().endswith(".json") else raw.splitlines()
            quotes.extend(item["quote"] if isinstance(item, dict) else item for item in values)
        if not quotes or not all(isinstance(q, str) for q in quotes) or (args.select_hit is not None and len(quotes) != 1):
            raise ValueError("supply quotes; --select-hit requires exactly one quote")
        pdfs = set()
        for value in args.pdfs:
            path = Path(value).resolve()
            if not path.exists():
                raise ValueError(f"missing input: {path}")
            pdfs.update(path.rglob("*.pdf") if path.is_dir() else [path])
        if not pdfs:
            raise ValueError("no PDFs supplied")
        indexes = [PdfIndex(p) for p in sorted(pdfs)]
        source, root = None, None
        if args.registry:
            root = args.registry.resolve().parent.parent
            sources = [s for s in load_sources(root, args.registry) if s.get("source_id") == args.source_id]
            if len(sources) != 1:
                raise ValueError("--source-id must identify exactly one registered source")
            source = sources[0]
        results = []
        for number, quote in enumerate(quotes, 1):
            rec = locate(indexes, quote, min_len=args.min_len, start_page=args.start_page)
            rec["id"] = f"PE-{number:02d}"
            if args.select_hit is not None:
                if not 1 <= args.select_hit <= len(rec["candidates"]):
                    raise ValueError("--select-hit is outside the candidate list")
                rec["selected_hit"] = args.select_hit
            results.append(rec)
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        rows = []
        for rec in results:
            print(f"[{rec['status']}] {rec['id']}: {rec['occurrences']} candidate(s)")
            for n, hit in enumerate(rec["candidates"], 1):
                print(f"  {n}. {hit['file']} PDF {hit['pdf_page_start']}-{hit['pdf_page_end']}: {hit['fidelity']}")
            selected = rec.get("selected_hit", 1 if len(rec["candidates"]) == 1 else None)
            if selected is None:
                continue
            hit = rec["candidates"][selected - 1]
            mapped = hit["printed_start"] is not None and hit["printed_end"] is not None and args.page_basis != "-"
            loc = fmt_locator(hit["printed_start"], hit["printed_end"]) if mapped else fmt_locator(hit["pdf_page_start"], hit["pdf_page_end"], pdf=True)
            path = Path(hit["file"])
            local = path.relative_to(root).as_posix() if root and path.is_relative_to(root) else str(path)
            values = [rec["id"], args.work, loc, rec["quote"], "B", f"{local}#p{hit['pdf_page_start']}-{hit['pdf_page_end']}",
                      local, "VERIFY", args.source_id or "-", source_digest(source) if source else "-",
                      hit["artifact_sha256"], "publication" if mapped else "pdf",
                      f"{hit['pdf_page_start']}-{hit['pdf_page_end']}",
                      f"{hit['page_source']}{'=' + str(args.start_page) if hit['page_source'] == 'start-page' else ''}: {args.page_basis}",
                      f"{hit['raw_start']}:{hit['raw_end']}"]
            rows.append("| " + " | ".join(cell(v) for v in values) + " |")
        if args.markdown:
            print("\n## Page Evidence\n")
            print("| " + " | ".join((*BASE_COLUMNS, *BINDING_COLUMNS)) + " |")
            print("|" + "---|" * (len(BASE_COLUMNS) + len(BINDING_COLUMNS)))
            print("\n".join(rows))
    return 0 if all(r["status"] == "located" for r in results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
