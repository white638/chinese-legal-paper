#!/usr/bin/env python3
"""Derive a small move-bound language packet from a private CommonplaceBank."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from commonplace_bank import (
    CommonplaceError, _keys, _locator, _positive, _read_json, _sha, _text,
    _texts, canonical_sha256, derive_phraseology, validate_bank,
)


SCHEMA_VERSION = "avereth-commonplace-packet/v1"
PACKET_KEYS = frozenset({"schema_version", "move_ref", "prose_packet_sha256", "conditioning_mode", "status", "target", "exemplars", "cross_source_conventions", "source_digest"})
TARGET_KEYS = frozenset({"section_role", "argument_action", "discourse_function", "citation_pattern", "discipline", "venue", "syntactic_architecture", "topic_terms", "limit", "max_total_excerpt_chars", "max_source_excerpt_chars"})
EXEMPLAR_KEYS = frozenset({"cp_id", "source_id", "source_sha256", "locator", "neighborhood", "rhetorical_skeleton", "citation_pattern", "syntactic_skeleton", "allowed_bundles", "blocked_spans", "reuse_class"})
CONVENTION_KEYS = frozenset({"text", "category", "source_ids"})


def _target(target: Any, prose_packet: dict, limit: int) -> dict:
    _keys(target, TARGET_KEYS, frozenset({"section_role", "argument_action"}), "target")
    if not isinstance(prose_packet, dict) or prose_packet.get("schema_version") != "avereth-prose-packet/v2":
        raise CommonplaceError("Commonplace conditioning requires avereth-prose-packet/v2")
    task = prose_packet.get("rhetorical_task")
    if not isinstance(task, dict) or not isinstance(task.get("argument_action"), str):
        raise CommonplaceError("current ProsePacket requires rhetorical_task.argument_action")
    if target["section_role"] != prose_packet.get("section_role") or target["argument_action"] != task["argument_action"]:
        raise CommonplaceError("target section/action does not match the current ProsePacket")
    result = {"section_role": target["section_role"], "argument_action": target["argument_action"], "discourse_function": "", "citation_pattern": [], "discipline": "", "venue": "", "syntactic_architecture": "", "topic_terms": [], "max_total_excerpt_chars": 6000, "max_source_excerpt_chars": 2000, **target, "limit": limit}
    for key in ("section_role", "argument_action"):
        _text(result[key], key)
    for key in ("discourse_function", "discipline", "venue", "syntactic_architecture"):
        if not isinstance(result[key], str):
            raise CommonplaceError(f"target.{key} must be text")
    for key in ("citation_pattern", "topic_terms"):
        _texts(result[key], f"target.{key}")
    for key in ("limit", "max_total_excerpt_chars", "max_source_excerpt_chars"):
        _positive(result[key], key)
    if result["limit"] > 5:
        raise CommonplaceError("Commonplace packets contain at most five exemplars")
    return result


def _score(entry: dict, source: dict, target: dict) -> int | None:
    if entry["argument_action"] != target["argument_action"]:
        return None
    section_match = entry["section_role"] == target["section_role"]
    function_match = bool(target["discourse_function"]) and entry["discourse_function"] == target["discourse_function"]
    if not section_match and not function_match:
        return None
    score = 100 + 50 * section_match + 60 * function_match
    score += 20 * bool(set(entry["citation_pattern"]) & set(target["citation_pattern"]))
    score += 12 * bool(target["venue"] and source["metadata"]["venue"] == target["venue"])
    score += 10 * bool(target["discipline"] and source["metadata"]["discipline"] == target["discipline"])
    score += 6 * bool(target["syntactic_architecture"] and entry["syntactic_skeleton"] == target["syntactic_architecture"])
    score += min(2, len(set(entry["topic_terms"]) & set(target["topic_terms"])))
    return score


def _excerpt_size(entry: dict) -> int:
    return sum(len(entry["neighborhood"][key]) for key in ("before", "focus", "after"))


def retrieve_packet(bank: dict, prose_packet: dict, move_ref: str, target: dict, *, limit: int = 5) -> dict:
    """Rank by argument use, preserve diversity, and return an explicit miss.

The caller remains responsible for full ProsePacket authority validation and
binding move_ref to the current MIR. This derivation verifies section/action,
binds the exact ProsePacket content hash, and reads no other manuscript context.
"""
    issues = validate_bank(bank)
    if issues:
        raise CommonplaceError("; ".join(issues))
    if re.fullmatch(r"MOVE-[A-Za-z0-9][A-Za-z0-9._-]*", _text(move_ref, "move_ref")) is None:
        raise CommonplaceError("move_ref must start with MOVE-")
    target = _target(target, prose_packet, limit)
    sources = {source["source_id"]: source for source in bank["sources"]}
    candidates = []
    for entry in bank["entries"]:
        score = _score(entry, sources[entry["source_id"]], target)
        if score is not None:
            candidates.append((score, entry))
    candidates.sort(key=lambda item: (-item[0], item[1]["cp_id"]))
    selected: list[dict] = []
    used_sources: set[str] = set()
    used_articles: set[str] = set()
    used_content: set[str] = set()
    used_authors: set[str] = set()
    total = 0
    while candidates and len(selected) < limit:
        # Independent authors are preferred among eligible move matches.
        candidates.sort(key=lambda item: (
            bool({name.casefold().strip() for name in sources[item[1]["source_id"]]["metadata"]["authors"]} & used_authors),
            -item[0], item[1]["cp_id"],
        ))
        _, entry = candidates.pop(0)
        source = sources[entry["source_id"]]
        article = source["metadata"]["article_id"].casefold()
        size = _excerpt_size(entry)
        if (entry["source_id"] in used_sources or article in used_articles or source["sha256"] in used_content
                or size > target["max_source_excerpt_chars"] or total + size > target["max_total_excerpt_chars"]):
            continue
        selected.append(entry)
        total += size
        used_sources.add(entry["source_id"])
        used_articles.add(article)
        used_content.add(source["sha256"])
        used_authors.update(name.casefold().strip() for name in source["metadata"]["authors"])
    phraseology = derive_phraseology(bank)
    expressions = phraseology["expressions"]
    exemplars = []
    conventions: dict[tuple[str, str], dict] = {}
    globally_blocked = {span for entry in bank["entries"] for span in entry["distinctive_spans"]}
    globally_blocked.update(bundle["text"] for entry in bank["entries"] for bundle in entry["lexical_bundles"] if bundle["category"] == "distinctive_expression")
    for entry in selected:
        allowed = set()
        for expression in expressions:
            if (expression["reuse_allowed"] and entry["cp_id"] in expression["cp_ids"]
                    and (not target["discourse_function"] or expression["discourse_function"] == target["discourse_function"])):
                allowed.add(expression["text"])
                key = (expression["text"], expression["category"])
                conventions[key] = {"text": expression["text"], "category": expression["category"], "source_ids": expression["source_ids"]}
        context = "".join(entry["neighborhood"][key] for key in ("before", "focus", "after"))
        blocked = set(entry["distinctive_spans"])
        blocked.update(span for span in globally_blocked if span in context)
        blocked.update(bundle["text"] for bundle in entry["lexical_bundles"] if bundle["text"] not in allowed)
        allowed.difference_update(blocked)
        exemplars.append({"cp_id": entry["cp_id"], "source_id": entry["source_id"], "source_sha256": sources[entry["source_id"]]["sha256"], "locator": dict(entry["locator"]), "neighborhood": {key: entry["neighborhood"][key] for key in ("before", "focus", "after")}, "rhetorical_skeleton": list(entry["rhetorical_skeleton"]), "citation_pattern": list(entry["citation_pattern"]), "syntactic_skeleton": entry["syntactic_skeleton"], "allowed_bundles": sorted(allowed), "blocked_spans": sorted(blocked), "reuse_class": "structural_exemplar"})
    allowed_all = {phrase for exemplar in exemplars for phrase in exemplar["allowed_bundles"]}
    return {"schema_version": SCHEMA_VERSION, "move_ref": move_ref, "prose_packet_sha256": canonical_sha256(prose_packet), "conditioning_mode": "commonplace", "status": "READY" if exemplars else "COMMONPLACE_MISS", "target": target, "exemplars": exemplars, "cross_source_conventions": [value for key, value in sorted(conventions.items()) if key[0] in allowed_all], "source_digest": bank["source_digest"]}


def validate_packet(packet: Any, *, prose_packet: dict | None = None, bank: dict | None = None, move_ref: str | None = None) -> list[str]:
    """Validate the whitelist; with bank + ProsePacket also rederive everything."""
    try:
        _keys(packet, PACKET_KEYS, PACKET_KEYS, "CommonplacePacket")
        if packet["schema_version"] != SCHEMA_VERSION or packet["conditioning_mode"] != "commonplace":
            raise CommonplaceError("unsupported CommonplacePacket schema or conditioning mode")
        if packet["status"] not in {"READY", "COMMONPLACE_MISS"}:
            raise CommonplaceError("invalid CommonplacePacket status")
        if re.fullmatch(r"MOVE-[A-Za-z0-9][A-Za-z0-9._-]*", _text(packet["move_ref"], "move_ref")) is None:
            raise CommonplaceError("invalid move_ref")
        if move_ref is not None and packet["move_ref"] != move_ref:
            raise CommonplaceError("CommonplacePacket binds a different Move")
        for key in ("prose_packet_sha256", "source_digest"):
            _sha(packet[key], key)
        _keys(packet["target"], TARGET_KEYS, TARGET_KEYS, "packet.target")
        binding = prose_packet if prose_packet is not None else {"schema_version": "avereth-prose-packet/v2", "section_role": packet["target"]["section_role"], "rhetorical_task": {"argument_action": packet["target"]["argument_action"]}}
        target = _target(packet["target"], binding, packet["target"]["limit"])
        if target != packet["target"]:
            raise CommonplaceError("packet target is not canonical")
        if prose_packet is not None and packet["prose_packet_sha256"] != canonical_sha256(prose_packet):
            raise CommonplaceError("CommonplacePacket ProsePacket hash is stale")
        if not isinstance(packet["exemplars"], list) or not isinstance(packet["cross_source_conventions"], list):
            raise CommonplaceError("exemplars and conventions must be lists")
        if len(packet["exemplars"]) > target["limit"] or bool(packet["exemplars"]) != (packet["status"] == "READY"):
            raise CommonplaceError("CommonplacePacket status or exemplar count is inconsistent")
        seen: set[str] = set()
        source_ids: set[str] = set()
        total = 0
        for exemplar in packet["exemplars"]:
            _keys(exemplar, EXEMPLAR_KEYS, EXEMPLAR_KEYS, "exemplar")
            for key in ("cp_id", "source_id", "syntactic_skeleton"):
                _text(exemplar[key], key)
            if exemplar["cp_id"] in seen or exemplar["source_id"] in source_ids:
                raise CommonplaceError("duplicate exemplar or source in packet")
            seen.add(exemplar["cp_id"])
            source_ids.add(exemplar["source_id"])
            _sha(exemplar["source_sha256"], "source_sha256")
            _locator(exemplar["locator"])
            keys = frozenset({"before", "focus", "after"})
            _keys(exemplar["neighborhood"], keys, keys, "neighborhood")
            for value in exemplar["neighborhood"].values():
                if not isinstance(value, str):
                    raise CommonplaceError("neighborhood values must be text")
            _text(exemplar["neighborhood"]["focus"], "focus")
            size = _excerpt_size(exemplar)
            total += size
            if size > target["max_source_excerpt_chars"] or total > target["max_total_excerpt_chars"]:
                raise CommonplaceError("packet exceeds configured excerpt character budget")
            for key in ("rhetorical_skeleton", "citation_pattern", "allowed_bundles", "blocked_spans"):
                _texts(exemplar[key], key, nonempty=key in {"rhetorical_skeleton", "citation_pattern"})
            if set(exemplar["allowed_bundles"]) & set(exemplar["blocked_spans"]):
                raise CommonplaceError("a blocked expression cannot be an allowed bundle")
            context = "".join(exemplar["neighborhood"][key] for key in ("before", "focus", "after"))
            if any(span not in context for span in exemplar["allowed_bundles"] + exemplar["blocked_spans"]):
                raise CommonplaceError("packet bundles/spans must occur in their excerpt")
            if exemplar["reuse_class"] != "structural_exemplar":
                raise CommonplaceError("packet cannot grant factual or verbatim reuse authority")
        convention_texts = set()
        for item in packet["cross_source_conventions"]:
            _keys(item, CONVENTION_KEYS, CONVENTION_KEYS, "convention")
            _text(item["text"], "convention.text")
            _texts(item["source_ids"], "convention.source_ids", nonempty=True)
            if len(item["source_ids"]) < 2 or item["category"] not in {"conventional_bundle", "discipline_specific_bundle", "technical_fixed_expression"}:
                raise CommonplaceError("convention requires multiple sources and an allowed category")
            convention_texts.add(item["text"])
        if any(set(item["allowed_bundles"]) - convention_texts for item in packet["exemplars"]):
            raise CommonplaceError("allowed bundles require cross-source conventions")
        if bank is not None:
            if prose_packet is None:
                raise CommonplaceError("authoritative packet validation requires the current ProsePacket")
            expected = retrieve_packet(bank, prose_packet, move_ref or packet["move_ref"], target, limit=target["limit"])
            if packet != expected:
                raise CommonplaceError("CommonplacePacket differs from its current deterministic bank derivation")
    except (CommonplaceError, OSError, TypeError, KeyError, ValueError) as exc:
        return [str(exc)]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--prose-packet", type=Path, required=True)
    parser.add_argument("--move-ref", required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        packet = retrieve_packet(_read_json(args.bank), _read_json(args.prose_packet), args.move_ref, _read_json(args.target), limit=args.limit)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": packet["status"], "output": str(args.output)}, ensure_ascii=False))
        return 0
    except (CommonplaceError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
