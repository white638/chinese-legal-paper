#!/usr/bin/env python3
"""Compile private, file-bound writing exemplars; this module grants no facts.

Harvest requests contain human-selected character offsets and human-supplied
rhetorical analysis. A local verified metadata sidecar binds each full text to
its article identity and permission decision. Validation checks those records
and files, rather than claiming to verify scholarly identity automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "avereth-commonplace-bank/v1"
PHRASEOLOGY_SCHEMA_VERSION = "avereth-disciplinary-phraseology/v1"
CATEGORIES = frozenset({"conventional_bundle", "discipline_specific_bundle", "technical_fixed_expression", "distinctive_expression"})
BANK_KEYS = frozenset({"schema_version", "sources", "entries", "limits", "source_digest"})
SOURCE_KEYS = frozenset({"source_id", "path", "sha256", "metadata_path", "metadata_sha256", "metadata", "fulltext"})
METADATA_KEYS = frozenset({"source_id", "article_id", "title", "authors", "discipline", "venue", "fulltext_sha256", "fulltext_verified", "permission_status", "synthetic"})
ENTRY_KEYS = frozenset({"cp_id", "source_id", "locator", "selection", "neighborhood", "section_role", "argument_action", "discourse_function", "rhetorical_skeleton", "citation_pattern", "syntactic_skeleton", "lexical_bundles", "distinctive_spans", "topic_terms", "reuse_class"})
SELECTION_KEYS = frozenset({"before_start", "start", "end", "after_end"})
LOCATOR_KEYS = frozenset({"section", "page", "paragraph", "label"})


class CommonplaceError(ValueError):
    pass


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _keys(value: Any, allowed: frozenset[str], required: frozenset[str], label: str) -> None:
    if not isinstance(value, dict):
        raise CommonplaceError(f"{label} must be an object")
    if set(value) - allowed:
        raise CommonplaceError(f"{label} has forbidden fields: {', '.join(sorted(set(value) - allowed))}")
    if required - set(value):
        raise CommonplaceError(f"{label} is missing: {', '.join(sorted(required - set(value)))}")


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommonplaceError(f"{label} must be nonempty text")
    return value


def _texts(value: Any, label: str, *, nonempty: bool = False) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise CommonplaceError(f"{label} must be a {'nonempty ' if nonempty else ''}list")
    for item in value:
        _text(item, label)
    if len(value) != len(set(value)):
        raise CommonplaceError(f"{label} contains duplicates")
    return value


def _sha(value: Any, label: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise CommonplaceError(f"{label} must be a lowercase SHA-256")


def _positive(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CommonplaceError(f"{label} must be a positive integer")
    return value


def _read_text(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise CommonplaceError(f"cannot read UTF-8 full text: {path}: {exc}") from exc


def _read_json(path: Path) -> dict:
    try:
        value = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise CommonplaceError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CommonplaceError(f"JSON document must be an object: {path}")
    return value


def _metadata(metadata: Any, source_id: str, digest: str) -> None:
    _keys(metadata, METADATA_KEYS, METADATA_KEYS, "metadata")
    for key in ("source_id", "article_id", "title", "discipline", "venue"):
        _text(metadata[key], f"metadata.{key}")
    _texts(metadata["authors"], "metadata.authors", nonempty=True)
    if metadata["source_id"] != source_id or metadata["fulltext_sha256"] != digest:
        raise CommonplaceError("metadata source identity/fulltext SHA mismatch")
    if metadata["fulltext_verified"] is not True or metadata["permission_status"] != "permitted":
        raise CommonplaceError("source requires recorded fulltext verification and permitted use")
    if not isinstance(metadata["synthetic"], bool):
        raise CommonplaceError("metadata.synthetic must explicitly identify synthetic fixtures")


def _locator(value: Any) -> None:
    _keys(value, LOCATOR_KEYS, frozenset({"section"}), "locator")
    _text(value["section"], "locator.section")
    if len(value) == 1:
        raise CommonplaceError("locator needs a page, paragraph, or precise label")
    for key in ("page", "paragraph"):
        if key in value:
            _positive(value[key], f"locator.{key}")
    if "label" in value:
        _text(value["label"], "locator.label")


def _neighborhood(fulltext: str, selection: Any) -> dict[str, str]:
    _keys(selection, SELECTION_KEYS, SELECTION_KEYS, "selection")
    values = [selection[key] for key in ("before_start", "start", "end", "after_end")]
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        raise CommonplaceError("selection offsets must be integers")
    before, start, end, after = values
    if not 0 <= before <= start < end <= after <= len(fulltext):
        raise CommonplaceError("selection offsets must identify an exact bounded fulltext span")
    if (start > 0 and before == start) or (end < len(fulltext) and after == end):
        raise CommonplaceError("selection must retain available before and after context")
    if start == 0 and end == len(fulltext):
        raise CommonplaceError("focus must be a local excerpt, not the entire full text")
    result = {"before": fulltext[before:start], "focus": fulltext[start:end], "after": fulltext[end:after]}
    _text(result["focus"], "focus")
    result["sha256"] = canonical_sha256(result)
    return result


def _entry(raw: Any, sources: dict[str, dict], limits: dict, *, compiled: bool) -> dict:
    allowed = ENTRY_KEYS if compiled else ENTRY_KEYS - {"neighborhood"}
    required = allowed - {"topic_terms"}
    _keys(raw, allowed, required, "entry")
    entry = json.loads(json.dumps(raw, ensure_ascii=False))
    if re.fullmatch(r"CP-[A-Za-z0-9][A-Za-z0-9._-]*", _text(entry["cp_id"], "cp_id")) is None:
        raise CommonplaceError("cp_id must start with CP-")
    if entry["source_id"] not in sources:
        raise CommonplaceError(f"unknown source_id: {entry['source_id']}")
    _locator(entry["locator"])
    neighborhood = _neighborhood(sources[entry["source_id"]]["fulltext"], entry["selection"])
    if compiled and entry["neighborhood"] != neighborhood:
        raise CommonplaceError("neighborhood does not match the selected fulltext span")
    if sum(len(neighborhood[key]) for key in ("before", "focus", "after")) > limits["max_excerpt_chars_per_entry"]:
        raise CommonplaceError("entry exceeds configured excerpt character budget")
    entry["neighborhood"] = neighborhood
    for key in ("section_role", "argument_action", "discourse_function", "syntactic_skeleton"):
        _text(entry[key], key)
    for key in ("rhetorical_skeleton", "citation_pattern"):
        _texts(entry[key], key, nonempty=True)
    _texts(entry["distinctive_spans"], "distinctive_spans")
    _texts(entry.setdefault("topic_terms", []), "topic_terms")
    if entry["reuse_class"] != "structural_exemplar":
        raise CommonplaceError("entries grant structural_exemplar reuse only")
    if not isinstance(entry["lexical_bundles"], list):
        raise CommonplaceError("lexical_bundles must be a list")
    seen: set[str] = set()
    for bundle in entry["lexical_bundles"]:
        _keys(bundle, frozenset({"text", "category"}), frozenset({"text", "category"}), "lexical_bundle")
        expression = _text(bundle["text"], "lexical_bundle.text")
        if expression not in neighborhood["focus"]:
            raise CommonplaceError("lexical bundle is absent from the selected focus")
        if len(expression) > 80 or len(expression.split()) > 12:
            raise CommonplaceError("lexical bundles must be short expressions, not sentence exemplars")
        if bundle["category"] not in CATEGORIES or expression in seen:
            raise CommonplaceError("lexical bundle category is invalid or text is duplicated")
        seen.add(expression)
    context = "".join(neighborhood[key] for key in ("before", "focus", "after"))
    if any(span not in context for span in entry["distinctive_spans"]):
        raise CommonplaceError("distinctive span is absent from the selected neighborhood")
    return entry


def _digest(bank: dict) -> str:
    return canonical_sha256({key: value for key, value in bank.items() if key != "source_digest"})


def compile_bank(request: dict, *, base_dir: Path | str = Path(".")) -> dict:
    """Read existing local full texts and metadata; never synthesize excerpts."""
    _keys(request, frozenset({"sources", "entries", "limits"}), frozenset({"sources", "entries"}), "request")
    limits = dict(request.get("limits", {"max_excerpt_chars_per_entry": 1600, "max_excerpt_chars_per_source": 4000}))
    _keys(limits, frozenset({"max_excerpt_chars_per_entry", "max_excerpt_chars_per_source"}), frozenset({"max_excerpt_chars_per_entry", "max_excerpt_chars_per_source"}), "limits")
    for key, value in limits.items():
        _positive(value, key)
    if not isinstance(request["sources"], list) or not isinstance(request["entries"], list):
        raise CommonplaceError("sources and entries must be lists")
    sources: dict[str, dict] = {}
    for raw in request["sources"]:
        keys = frozenset({"source_id", "path", "sha256", "metadata_path", "metadata_sha256"})
        _keys(raw, keys, keys, "source request")
        source_id = _text(raw["source_id"], "source_id")
        if source_id in sources:
            raise CommonplaceError("duplicate source_id")
        path = (Path(base_dir) / _text(raw["path"], "path")).resolve()
        metadata_path = (Path(base_dir) / _text(raw["metadata_path"], "metadata_path")).resolve()
        _sha(raw["sha256"], "sha256")
        _sha(raw["metadata_sha256"], "metadata_sha256")
        try:
            if file_sha256(path) != raw["sha256"] or file_sha256(metadata_path) != raw["metadata_sha256"]:
                raise CommonplaceError("source or metadata file SHA changed")
        except OSError as exc:
            raise CommonplaceError(f"source file unavailable: {exc}") from exc
        metadata = _read_json(metadata_path)
        _metadata(metadata, source_id, raw["sha256"])
        sources[source_id] = {**raw, "path": str(path), "metadata_path": str(metadata_path), "metadata": metadata, "fulltext": _read_text(path)}
    entries = [_entry(raw, sources, limits, compiled=False) for raw in request["entries"]]
    bank = {"schema_version": SCHEMA_VERSION, "sources": sorted(sources.values(), key=lambda item: item["source_id"]), "entries": sorted(entries, key=lambda item: item["cp_id"]), "limits": limits}
    bank["source_digest"] = _digest(bank)
    issues = validate_bank(bank)
    if issues:
        raise CommonplaceError("; ".join(issues))
    return bank


def validate_bank(bank: Any, *, verify_files: bool = True) -> list[str]:
    """Fail closed on altered source files, records, context, or bank contents."""
    try:
        _keys(bank, BANK_KEYS, BANK_KEYS, "bank")
        if bank["schema_version"] != SCHEMA_VERSION:
            raise CommonplaceError("unsupported CommonplaceBank schema")
        _keys(bank["limits"], frozenset({"max_excerpt_chars_per_entry", "max_excerpt_chars_per_source"}), frozenset({"max_excerpt_chars_per_entry", "max_excerpt_chars_per_source"}), "limits")
        for key, value in bank["limits"].items():
            _positive(value, key)
        if not isinstance(bank["sources"], list) or not isinstance(bank["entries"], list):
            raise CommonplaceError("sources and entries must be lists")
        sources: dict[str, dict] = {}
        for source in bank["sources"]:
            _keys(source, SOURCE_KEYS, SOURCE_KEYS, "source")
            source_id = _text(source["source_id"], "source_id")
            if source_id in sources:
                raise CommonplaceError("duplicate source_id")
            _sha(source["sha256"], "source.sha256")
            _sha(source["metadata_sha256"], "source.metadata_sha256")
            _text(source["fulltext"], "fulltext")
            _metadata(source["metadata"], source_id, source["sha256"])
            if verify_files:
                path = Path(source["path"])
                metadata_path = Path(source["metadata_path"])
                if not path.is_absolute() or not metadata_path.is_absolute():
                    raise CommonplaceError("compiled source paths must be absolute")
                if file_sha256(path) != source["sha256"] or file_sha256(metadata_path) != source["metadata_sha256"]:
                    raise CommonplaceError("source or metadata file SHA changed")
                if _read_text(path) != source["fulltext"] or _read_json(metadata_path) != source["metadata"]:
                    raise CommonplaceError("source text or metadata differs from its bound file")
            sources[source_id] = source
        seen: set[str] = set()
        totals: dict[str, int] = {}
        for raw in bank["entries"]:
            entry = _entry(raw, sources, bank["limits"], compiled=True)
            if entry["cp_id"] in seen:
                raise CommonplaceError("duplicate cp_id")
            seen.add(entry["cp_id"])
            source_id = entry["source_id"]
            totals[source_id] = totals.get(source_id, 0) + sum(len(entry["neighborhood"][key]) for key in ("before", "focus", "after"))
            if totals[source_id] > bank["limits"]["max_excerpt_chars_per_source"]:
                raise CommonplaceError("source exceeds configured cumulative excerpt character budget")
        if bank["source_digest"] != _digest(bank):
            raise CommonplaceError("bank source_digest is stale")
    except (CommonplaceError, OSError, TypeError, KeyError, ValueError) as exc:
        return [str(exc)]
    return []


def _author_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _independent(sources: list[dict]) -> bool:
    for index, left in enumerate(sources):
        a = left["metadata"]
        for right in sources[index + 1:]:
            b = right["metadata"]
            if (left["sha256"] != right["sha256"] and a["article_id"].casefold() != b["article_id"].casefold()
                    and not {_author_key(v) for v in a["authors"]}.intersection(_author_key(v) for v in b["authors"])):
                return True
    return False


def derive_phraseology(bank: dict) -> dict:
    """Derive short conventions only from independent, exact local occurrences."""
    issues = validate_bank(bank)
    if issues:
        raise CommonplaceError("; ".join(issues))
    sources = {item["source_id"]: item for item in bank["sources"]}
    grouped: dict[tuple[str, str, str], list[dict]] = {}
    blocked = {span for item in bank["entries"] for span in item["distinctive_spans"]}
    blocked.update(bundle["text"] for item in bank["entries"] for bundle in item["lexical_bundles"] if bundle["category"] == "distinctive_expression")
    for entry in bank["entries"]:
        for bundle in entry["lexical_bundles"]:
            key = (bundle["text"], bundle["category"], entry["discourse_function"])
            grouped.setdefault(key, []).append(entry)
    expressions = []
    for (phrase, requested, function), entries in sorted(grouped.items()):
        ids = sorted({item["source_id"] for item in entries})
        source_records = [sources[source_id] for source_id in ids]
        independent = _independent(source_records)
        disciplines = sorted({item["metadata"]["discipline"] for item in source_records})
        allowed = phrase not in blocked and independent and requested != "distinctive_expression"
        if requested == "discipline_specific_bundle" and len(disciplines) != 1:
            allowed = False
        expressions.append({"text": phrase, "category": "distinctive_expression" if phrase in blocked else requested, "discourse_function": function, "source_ids": ids, "cp_ids": sorted({item["cp_id"] for item in entries}), "disciplines": disciplines, "independent_support": independent, "reuse_allowed": allowed})
    return {"schema_version": PHRASEOLOGY_SCHEMA_VERSION, "source_digest": bank["source_digest"], "expressions": expressions}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--request", type=Path, required=True)
    compile_cmd.add_argument("--output", type=Path, required=True)
    for command in ("validate", "phraseology"):
        p = sub.add_parser(command)
        p.add_argument("--bank", type=Path, required=True)
        if command == "phraseology":
            p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "compile":
            result = compile_bank(_read_json(args.request), base_dir=args.request.resolve().parent)
        elif args.command == "phraseology":
            result = derive_phraseology(_read_json(args.bank))
        else:
            issues = validate_bank(_read_json(args.bank))
            print(json.dumps({"status": "FAIL" if issues else "PASS", "issues": issues}, ensure_ascii=False))
            return int(bool(issues))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "PASS", "output": str(args.output)}, ensure_ascii=False))
        return 0
    except (CommonplaceError, OSError) as exc:
        print(json.dumps({"status": "FAIL", "issues": [str(exc)]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
