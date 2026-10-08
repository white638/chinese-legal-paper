#!/usr/bin/env python3
"""Inspect source-specific borrowing; overlap is not a plagiarism probability."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

TOKEN = re.compile(r"[\u3400-\u9fff]|[^\W_\u3400-\u9fff]+", re.UNICODE)


def tokens(text: str) -> list[str]:
    return TOKEN.findall(unicodedata.normalize("NFKC", text).casefold())


def occurrences(haystack: list[str], needle: list[str]) -> list[tuple[int, int]]:
    if not needle:
        return []
    return [(i, i + len(needle)) for i in range(len(haystack) - len(needle) + 1)
            if haystack[i:i + len(needle)] == needle]


def _quote_ranges(draft: str, prose: dict, source_id: str) -> set[int]:
    """Only evidence-authorized quotations from this source exempt their own occurrence."""
    covered: set[int] = set()
    for item in prose.get("evidence_items", []):
        anchor = item.get("context_anchor") or {}
        if anchor.get("type") != "quotation" or anchor.get("authority_ref") != source_id:
            continue
        span = anchor.get("exact_span", "")
        citation = item.get("citation_key", "")
        if not span or not citation:
            continue
        for match in re.finditer(re.escape(span), draft):
            before, after = draft[:match.start()], draft[match.end():]
            marked = before.rstrip().endswith(('“', '"', '「', '«')) and after.lstrip().startswith(('”', '"', '」', '»'))
            if marked and re.search(r"(?<![\w])" + re.escape(citation) + r"(?![\w])", after[:120]):
                start = len(tokens(before))
                covered.update(range(start, start + len(tokens(span))))
    return covered


def check_overlap(draft: str, packet: dict, prose_packet: dict) -> dict[str, Any]:
    draft_tokens = tokens(draft)
    report: dict[str, Any] = {
        "schema_version": "avereth-commonplace-overlap/v1",
        "draft_sha256": hashlib.sha256(draft.encode("utf-8")).hexdigest(),
        "longest_source_matches": [], "rare_ngram_matches": [],
        "distinctive_span_matches": [], "allowed_bundle_matches": [],
        "quoted_matches": [], "single_source_concentration": {},
        "findings": [], "verdict": "PASS",
    }
    if not draft.strip():
        report["findings"].append({"id": "EMPTY", "severity": "FAIL", "reason": "draft is empty"})
    source_texts: dict[str, list[str]] = {}
    source_items: dict[str, list[dict]] = {}
    for exemplar in packet.get("exemplars", []):
        sid = exemplar["source_id"]
        source_items.setdefault(sid, []).append(exemplar)
        neighborhood = exemplar["neighborhood"]
        source_texts.setdefault(sid, []).append(" ".join(neighborhood[k] for k in ("before", "focus", "after")))
    for sid, texts in sorted(source_texts.items()):
        items = source_items[sid]
        quote_covered = _quote_ranges(draft, prose_packet, sid)
        allowed_covered: set[int] = set()
        allowed = {bundle for item in items for bundle in item.get("allowed_bundles", [])}
        for bundle in sorted(allowed):
            for start, end in occurrences(draft_tokens, tokens(bundle)):
                allowed_covered.update(range(start, end))
                report["allowed_bundle_matches"].append({"source_id": sid, "text": bundle, "draft_tokens": [start, end]})
        distinctive = {span for item in items for span in item.get("blocked_spans", [])}
        for span in sorted(distinctive):
            for start, end in occurrences(draft_tokens, tokens(span)):
                entry = {"source_id": sid, "text": span, "draft_tokens": [start, end]}
                if set(range(start, end)) <= quote_covered:
                    report["quoted_matches"].append(entry)
                    continue
                report["distinctive_span_matches"].append(entry)
                report["findings"].append({"id": f"{sid}:distinctive:{start}:{end}", "severity": "FAIL", **entry})
        matched: set[int] = set()
        uncovered: set[int] = set()
        longest: dict[str, Any] = {"source_id": sid, "length": 0}
        rare: list[dict] = []
        fragments: list[tuple[int, int]] = []
        fragment_positions: set[int] = set()
        for source in texts:
            st = tokens(source)
            chinese = sum(bool(re.fullmatch(r"[\u3400-\u9fff]", t)) for t in st) > len(st) / 2
            n = 8 if chinese else 5
            for match in SequenceMatcher(None, draft_tokens, st, autojunk=False).get_matching_blocks():
                if not match.size:
                    continue
                start, end = match.a, match.a + match.size
                matched.update(range(start, end))
                if match.size > longest["length"]:
                    longest = {"source_id": sid, "length": match.size, "draft_tokens": [start, end],
                               "tokens": draft_tokens[start:end]}
                remaining = set(range(start, end)) - allowed_covered - quote_covered
                if len(remaining) >= (4 if chinese else 3):
                    fragments.append((start, end))
                    fragment_positions.update(remaining)
                if match.size >= n and len(remaining) >= n:
                    uncovered.update(remaining)
                    rare.append({"source_id": sid, "draft_tokens": [start, end], "tokens": draft_tokens[start:end]})
        report["longest_source_matches"].append(longest)
        report["rare_ngram_matches"].extend(rare)
        report["single_source_concentration"][sid] = {
            "matched_tokens": len(matched), "unexempted_signal_tokens": len(uncovered),
            "draft_tokens": len(draft_tokens), "fraction": len(matched) / max(1, len(draft_tokens)),
        }
        if rare:
            report["findings"].append({"id": f"{sid}:source-overlap", "severity": "REVIEW", "source_id": sid,
                                       "reason": "Review source-specific wording and conceptual formulation in the recorded spans."})
        elif len(set(fragments)) >= 2 and len(fragment_positions) >= 10 and len(fragment_positions) / max(1, len(draft_tokens)) >= 0.5:
            report["findings"].append({"id": f"{sid}:fragment-concentration", "severity": "REVIEW", "source_id": sid,
                                       "draft_token_spans": [list(span) for span in sorted(set(fragments))],
                                       "reason": "Several short source fragments dominate this draft; assess source-specific patchwriting."})
    severities = {f["severity"] for f in report["findings"]}
    report["verdict"] = "FAIL" if "FAIL" in severities else "REVIEW" if "REVIEW" in severities else "PASS"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("packet", type=Path)
    parser.add_argument("prose_packet", type=Path)
    parser.add_argument("draft", type=Path)
    args = parser.parse_args()
    from commonplace_retrieve import validate_packet
    packet = json.loads(args.packet.read_text(encoding="utf-8-sig"))
    prose = json.loads(args.prose_packet.read_text(encoding="utf-8-sig"))
    issues = validate_packet(packet, prose_packet=prose)
    if issues:
        print(json.dumps({"verdict": "FAIL", "issues": issues}, ensure_ascii=False))
        return 1
    report = check_overlap(args.draft.read_text(encoding="utf-8-sig"), packet, prose)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {"PASS": 0, "REVIEW": 2, "FAIL": 1}[report["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
