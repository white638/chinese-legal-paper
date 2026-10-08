#!/usr/bin/env python3
"""Verified citation edges between registered sources.

``literature_registry.json`` may carry an ``edges`` array. Each edge records one
verified relation between two registered Source IDs: who cites whom, which works
are co-cited or co-mentioned, and, when the citing text was actually read, the
stance of the citation. Edges are data, not prose: a foundational chain or a real
counter-position can then be checked instead of self-reported.

The module is shared by ``cnki_acquisition.py`` (structural validation and the
generated source index), ``literature_sufficiency.py`` (coverage gates) and
``literature_analysis.py`` (synthesis links). It has no third-party dependencies.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

EDGE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,63}$")
EDGE_RELATIONS = {"cites", "co-cited-with", "co-mentioned-with"}
SYMMETRIC_RELATIONS = {"co-cited-with", "co-mentioned-with"}
EDGE_EVIDENCE = {
    "openalex",
    "semantic-scholar",
    "crossref",
    "cnki-detail",
    "grobid-paragraph",
    "full-text-read",
    "other-index",
}
TEXT_EVIDENCE = {"grobid-paragraph", "full-text-read"}
EDGE_STANCES = {"supportive", "critical", "neutral", "unknown"}
EDGE_REQUIRED_FIELDS = ("edge_id", "from_source_id", "to_source_id", "relation", "evidence", "verified_at")
EDGE_OPTIONAL_FIELDS = ("stance", "context_quote", "context_locator", "via_source_id", "query_id", "note")
MIN_CONTEXT_QUOTE_CHARS = 10
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?$")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def registry_edges(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = registry.get("edges")
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def has_edges(registry: Mapping[str, Any]) -> bool:
    return bool(registry_edges(registry))


def edge_issues(
    registry: Mapping[str, Any],
    *,
    valid_source_ids: Iterable[str] | None = None,
    valid_query_ids: Iterable[str] | None = None,
) -> list[str]:
    """Return structural problems with ``registry['edges']`` (empty list when valid)."""

    raw = registry.get("edges")
    if raw is None:
        return []
    if not isinstance(raw, list):
        return ["registry edges must be a list of edge objects"]
    issues: list[str] = []
    source_ids = set(valid_source_ids) if valid_source_ids is not None else None
    query_ids = set(valid_query_ids) if valid_query_ids is not None else None
    seen_ids: set[str] = set()
    seen_pairs: set[tuple[str, str, str]] = set()
    for index, edge in enumerate(raw):
        path = f"edges[{index}]"
        if not isinstance(edge, Mapping):
            issues.append(f"{path} must be an object")
            continue
        edge_id = _text(edge.get("edge_id"))
        label = edge_id or path
        missing = [field for field in EDGE_REQUIRED_FIELDS if not _text(edge.get(field))]
        if missing:
            issues.append(f"{label} lacks fields: " + ", ".join(missing))
        extra = sorted(set(edge) - set(EDGE_REQUIRED_FIELDS) - set(EDGE_OPTIONAL_FIELDS))
        if extra:
            issues.append(f"{label} contains unsupported fields: " + ", ".join(str(item) for item in extra))
        if edge_id and not EDGE_ID_RE.fullmatch(edge_id):
            issues.append(f"{label} edge_id must be a stable uppercase ID")
        if edge_id in seen_ids:
            issues.append(f"{label} duplicates edge_id")
        seen_ids.add(edge_id)
        source = _text(edge.get("from_source_id"))
        target = _text(edge.get("to_source_id"))
        if source and target and source == target:
            issues.append(f"{label} cannot relate a source to itself")
        if source_ids is not None:
            for field, value in (("from_source_id", source), ("to_source_id", target), ("via_source_id", _text(edge.get("via_source_id")))):
                if value and value not in source_ids:
                    issues.append(f"{label}.{field} {value} is not a registered Source ID")
        relation = _text(edge.get("relation"))
        if relation and relation not in EDGE_RELATIONS:
            issues.append(f"{label} relation must be one of: " + ", ".join(sorted(EDGE_RELATIONS)))
        evidence = _text(edge.get("evidence"))
        if evidence and evidence not in EDGE_EVIDENCE:
            issues.append(f"{label} evidence must be one of: " + ", ".join(sorted(EDGE_EVIDENCE)))
        stance = _text(edge.get("stance")) or "unknown"
        if stance not in EDGE_STANCES:
            issues.append(f"{label} stance must be one of: " + ", ".join(sorted(EDGE_STANCES)))
        quote = _text(edge.get("context_quote"))
        if stance != "unknown":
            if relation and relation != "cites":
                issues.append(f"{label} stance is only meaningful on a cites edge")
            if evidence and evidence not in TEXT_EVIDENCE:
                issues.append(
                    f"{label} stance {stance} requires evidence from the citing text (" + ", ".join(sorted(TEXT_EVIDENCE)) + ")"
                )
            if len(quote) < MIN_CONTEXT_QUOTE_CHARS:
                issues.append(f"{label} stance {stance} requires a context_quote of at least {MIN_CONTEXT_QUOTE_CHARS} characters")
        if relation == "co-mentioned-with":
            if evidence and evidence not in TEXT_EVIDENCE:
                issues.append(f"{label} co-mentioned-with requires paragraph-level text evidence")
            if len(quote) < MIN_CONTEXT_QUOTE_CHARS:
                issues.append(f"{label} co-mentioned-with requires the co-mentioning context_quote")
        verified_at = _text(edge.get("verified_at"))
        if verified_at and not ISO_DATE_RE.fullmatch(verified_at):
            issues.append(f"{label} verified_at must be an ISO-8601 date")
        query_id = _text(edge.get("query_id"))
        if query_id and query_ids is not None and query_id not in query_ids:
            issues.append(f"{label}.query_id {query_id} is not a registered Query ID")
        if source and target and relation:
            pair = (relation, source, target)
            if relation in SYMMETRIC_RELATIONS:
                pair = (relation, *sorted((source, target)))
            if pair in seen_pairs:
                issues.append(f"{label} repeats an existing {relation} edge between {pair[1]} and {pair[2]}")
            seen_pairs.add(pair)
    return issues


def edges_by_id(registry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(edge.get("edge_id")): edge
        for edge in registry_edges(registry)
        if _text(edge.get("edge_id"))
    }


def cites_adjacency(edges: Iterable[Mapping[str, Any]]) -> dict[str, set[str]]:
    """Undirected adjacency over verified ``cites`` edges."""

    graph: dict[str, set[str]] = {}
    for edge in edges:
        if _text(edge.get("relation")) != "cites":
            continue
        source = _text(edge.get("from_source_id"))
        target = _text(edge.get("to_source_id"))
        if not source or not target or source == target:
            continue
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set()).add(source)
    return graph


def connected_through(graph: Mapping[str, set[str]], nodes: Iterable[str]) -> tuple[bool, list[str]]:
    """Whether ``nodes`` all sit in one connected component of ``graph``.

    Intermediate nodes may be any registered source. Returns the flag and the
    sorted list of nodes that are unreachable from the first node.
    """

    wanted = [node for node in dict.fromkeys(_text(node) for node in nodes) if node]
    if len(wanted) <= 1:
        return True, []
    start = wanted[0]
    seen = {start}
    frontier = [start]
    while frontier:
        current = frontier.pop()
        for neighbour in graph.get(current, ()):
            if neighbour not in seen:
                seen.add(neighbour)
                frontier.append(neighbour)
    unreachable = sorted(node for node in wanted[1:] if node not in seen)
    return not unreachable, unreachable


def edges_touching(edges: Iterable[Mapping[str, Any]], source_ids: Iterable[str]) -> list[dict[str, Any]]:
    wanted = {_text(item) for item in source_ids if _text(item)}
    return [
        dict(edge)
        for edge in edges
        if _text(edge.get("from_source_id")) in wanted or _text(edge.get("to_source_id")) in wanted
    ]


def critical_edges(edges: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(edge) for edge in edges if _text(edge.get("stance")) == "critical"]


def render_edges_markdown(registry: Mapping[str, Any]) -> str:
    """Generated view of registry edges for ``source_index.md``."""

    edges = registry_edges(registry)
    if not edges:
        return ""
    lines = [
        "## Citation Edges",
        "",
        "| Edge ID | From | Relation | To | Evidence | Stance | Verified | Context |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for edge in edges:
        quote = _text(edge.get("context_quote")).replace("|", "\\|").replace("\n", " ")
        if len(quote) > 80:
            quote = quote[:77] + "..."
        lines.append(
            "| "
            + " | ".join(
                [
                    _text(edge.get("edge_id")) or "-",
                    _text(edge.get("from_source_id")) or "-",
                    _text(edge.get("relation")) or "-",
                    _text(edge.get("to_source_id")) or "-",
                    _text(edge.get("evidence")) or "-",
                    _text(edge.get("stance")) or "unknown",
                    _text(edge.get("verified_at")) or "-",
                    quote or "-",
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)
