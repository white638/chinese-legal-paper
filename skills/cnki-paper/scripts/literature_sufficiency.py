#!/usr/bin/env python3
"""Evidence-backed researcher literature accumulation contract for CNKI-Paper v5.

The module deliberately separates numerical sufficiency from scholarly coverage.
A paper passes only when it has enough *eligible* scholarly works and has mapped
the main intellectual responsibilities of the review.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable
from urllib.parse import urlsplit, urlunsplit

import citation_edges


COVERAGE_KEYS = (
    "major_positions",
    "counterarguments",
    "foundational_chain",
    "recent_developments",
    "method_responsibilities",
)
SCHOLARLY_CHANNELS = {
    "cnki",
    "doi",
    "publisher",
    "publisher-official",
    "scholarly-publisher",
    "lawful-oa",
    "legal-oa",
    "lawful-institutional-repository",
    "academic-journal",
    "university-press",
}
NON_SCHOLARLY_CHANNELS = {
    "official",
    "official-web",
    "government",
    "government-web",
    "institutional-primary",
    "official-record",
    "news",
    "news-media",
    "media",
    "archive",
    "raw-data",
    "dataset",
    "web",
    "public-web",
    "open-web",
    "blog",
    "social-media",
}
PRIMARY_MATERIAL_ROLES = {
    "official-primary",
    "historical-primary",
    "archive",
    "archival",
    "raw-data",
    "dataset",
    "news",
    "original-material",
}
RESPONSIBILITY_KEYS = {
    "problem",
    "position",
    "claim",
    "theory",
    "method",
    "counterargument",
}
COVERAGE_RESPONSIBILITY_KEYS = {
    "major_positions": {"position", "theory"},
    "counterarguments": {"counterargument"},
    "foundational_chain": {"theory"},
    "recent_developments": {"position", "claim", "theory"},
    "method_responsibilities": {"method"},
}
CHANGE_BLOCKING_STAGES = {"research", "design", "execution", "build", "audit", "output"}


def canonical(value: Any) -> str:
    return str(value or "").strip().lower().replace("_", "-").replace(" ", "-")


def normalized_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def nearest_rank_percentile(values: Iterable[int], percentile: float) -> int:
    """Return a percentile using the nearest-rank definition.

    The nearest-rank position is ``ceil(p * n)`` with one-based indexing.
    """
    ordered = sorted(int(value) for value in values)
    if not ordered:
        raise ValueError("nearest-rank percentile requires at least one value")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True)
class ComparableSelection:
    samples: list[dict[str, Any]]
    window_years: int
    p25: int | None
    issues: list[str] = field(default_factory=list)


def select_comparable_samples(
    samples: Iterable[dict[str, Any]],
    *,
    target_venue: str,
    article_type: str,
    target_word_count: int,
    current_year: int | None = None,
) -> ComparableSelection:
    """Select same-venue, same-type articles within 70%-130% target length.

    The three-year window is preferred. It is expanded to five years only when
    fewer than five otherwise-comparable articles are available.
    """
    now_year = current_year or date.today().year
    target_venue_key = normalized_text(target_venue)
    target_type_key = normalized_text(article_type)
    issues: list[str] = []
    if not target_venue_key:
        issues.append("target venue is missing")
    if not target_type_key:
        issues.append("article type is missing")
    if not isinstance(target_word_count, int) or target_word_count < 1:
        issues.append("target word count must be a positive integer")
        return ComparableSelection([], 5, None, issues)

    lower = target_word_count * 0.70
    upper = target_word_count * 1.30
    comparable: list[dict[str, Any]] = []
    for item in samples:
        if not isinstance(item, dict):
            continue
        try:
            year = int(item.get("publication_year"))
            length = int(item.get("word_count"))
            references = int(item.get("scholarly_reference_count"))
        except (TypeError, ValueError):
            continue
        if normalized_text(item.get("venue")) != target_venue_key:
            continue
        if normalized_text(item.get("article_type")) != target_type_key:
            continue
        if not lower <= length <= upper:
            continue
        if references < 0 or year > now_year or year < now_year - 4:
            continue
        comparable.append(dict(item))

    recent = [item for item in comparable if int(item["publication_year"]) >= now_year - 2]
    if len(recent) >= 5:
        selected = recent
        window = 3
    else:
        selected = comparable
        window = 5
    if len(selected) < 5:
        issues.append(
            f"only {len(selected)} comparable target-venue articles were verified; at least 5 are required"
        )
        return ComparableSelection(selected, window, None, issues)
    p25 = nearest_rank_percentile(
        [int(item["scholarly_reference_count"]) for item in selected],
        0.25,
    )
    return ComparableSelection(selected, window, p25, issues)


def fallback_floor(profile: str, scene: str) -> int:
    profile_key = canonical(profile)
    scene_key = canonical(scene)
    if profile_key == "topic-selection":
        return 12
    if profile_key == "research-design":
        return 20
    if scene_key in {
        "conference",
        "conference-paper",
        "report",
        "report-review",
        "research-report",
        "competition",
    }:
        return 15
    return 25


def validate_citation_requirement(requirement: Any) -> list[str]:
    if requirement in (None, {}):
        return []
    if not isinstance(requirement, dict):
        return ["citation_requirement must be an object"]
    issues: list[str] = []
    authority = canonical(requirement.get("authority"))
    if authority not in {"user", "venue"}:
        issues.append("citation_requirement.authority must be user or venue")
    minimum = requirement.get("minimum")
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
        issues.append("citation_requirement.minimum must be a positive integer")
    evidence = str(
        requirement.get("evidence")
        or requirement.get("confirmation_evidence")
        or requirement.get("official_basis")
        or ""
    ).strip()
    if not evidence:
        issues.append("citation_requirement must retain user confirmation or an official venue basis")
    return issues


@dataclass(frozen=True)
class FloorDecision:
    hard_minimum: int
    controlling_source: str
    benchmark_minimum: int | None
    fallback_minimum: int
    external_minimum: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "hard_minimum": self.hard_minimum,
            "controlling_source": self.controlling_source,
            "benchmark_minimum": self.benchmark_minimum,
            "fallback_minimum": self.fallback_minimum,
            "external_minimum": self.external_minimum,
        }


def compute_floor(
    *,
    profile: str,
    scene: str,
    benchmark_count: int | None,
    citation_requirement: dict[str, Any] | None,
) -> FloorDecision:
    fallback = fallback_floor(profile, scene)
    benchmark = int(benchmark_count) if benchmark_count is not None else None
    if benchmark is not None and benchmark < 0:
        raise ValueError("benchmark_count cannot be negative")
    external: int | None = None
    authority = ""
    if citation_requirement:
        problems = validate_citation_requirement(citation_requirement)
        if problems:
            raise ValueError("; ".join(problems))
        external = int(citation_requirement["minimum"])
        authority = canonical(citation_requirement["authority"])
    base_value = benchmark if benchmark is not None else fallback
    controlling = "target-venue-benchmark" if benchmark is not None else "task-fallback"
    if external is not None and external >= base_value:
        return FloorDecision(external, authority, benchmark, fallback, external)
    return FloorDecision(base_value, controlling, benchmark, fallback, external)


def canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw.lower()
    if parts.scheme.lower() not in {"http", "https"}:
        return raw.lower()
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def source_dedup_key(source: dict[str, Any]) -> str:
    identity = source.get("identity") if isinstance(source.get("identity"), dict) else {}
    doi = canonical(source.get("doi") or identity.get("doi"))
    if doi:
        return "doi:" + doi.removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    authors = source.get("authors")
    if isinstance(authors, list):
        author = normalized_text(authors[0] if authors else "")
    else:
        author = normalized_text(source.get("author") or authors)
    title = normalized_text(source.get("title"))
    year = normalized_text(source.get("publication_year") or source.get("year"))
    # CNKI and several publisher platforms reuse one abstract endpoint and put
    # the record identity in short-lived query parameters.  Comparing the
    # query-stripped URL first would collapse distinct works into one.  A
    # verified scholarly identity therefore takes precedence over its access
    # route; the year is retained when available but is not required because
    # many migrated records identify the work by title and author only.
    if title and author:
        return "work:" + "|".join((title, author, year))
    local_digest = canonical(
        source.get("sha256")
        or source.get("file_sha256")
        or source.get("local_sha256")
    )
    if re.fullmatch(r"[0-9a-f]{64}", local_digest):
        return "sha256:" + local_digest
    url = canonical_url(source.get("url"))
    if url:
        return "url:" + url
    return "work:" + "|".join((title, author, year))


def source_identity_verified(source: dict[str, Any]) -> bool:
    """Require a work identity that can actually be deduplicated and audited."""
    if not str(source.get("source_id") or "").strip():
        return False
    identity = source.get("identity") if isinstance(source.get("identity"), dict) else {}
    if str(source.get("doi") or identity.get("doi") or "").strip():
        return True
    if canonical_url(source.get("url")):
        return True
    digest = str(
        source.get("sha256")
        or source.get("file_sha256")
        or source.get("local_sha256")
        or ""
    ).strip().lower()
    if re.fullmatch(r"[0-9a-f]{64}", digest):
        return True
    authors = source.get("authors")
    author = authors[0] if isinstance(authors, list) and authors else source.get("author") or authors
    return bool(
        normalized_text(source.get("title"))
        and normalized_text(author)
        and normalized_text(source.get("publication_year") or source.get("year"))
    )


def content_verified(source: dict[str, Any]) -> bool:
    state = canonical(source.get("state"))
    if state not in {"content-verified", "pdf-downloaded"}:
        return False
    verification = source.get("verification")
    if not isinstance(verification, dict):
        return False
    method = canonical(verification.get("method"))
    return method in {"abstract", "detail", "full-text", "pdf"}


def relevance_mapped(source: dict[str, Any]) -> bool:
    relevance = source.get("relevance")
    if not isinstance(relevance, dict) or canonical(relevance.get("status")) != "mapped":
        return False
    responsibilities = relevance.get("responsibilities")
    if not isinstance(responsibilities, list) or not responsibilities:
        return False
    return any(canonical(item) in RESPONSIBILITY_KEYS for item in responsibilities)


def scholarly_source(source: dict[str, Any]) -> bool:
    channel = canonical(source.get("channel"))
    material_role = canonical(source.get("material_role") or source.get("document_role"))
    credibility = source.get("credibility")
    source_class = canonical(credibility.get("source_class")) if isinstance(credibility, dict) else ""
    if channel in NON_SCHOLARLY_CHANNELS or material_role in PRIMARY_MATERIAL_ROLES:
        return False
    if source_class in {"official-primary", "news-media"}:
        return False
    return (
        channel in SCHOLARLY_CHANNELS
        or source_class == "scholarly-publisher"
        or source.get("academic_work") is True
    )


def source_ineligibility_reasons(source: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not source_identity_verified(source):
        reasons.append("identity-not-verifiable")
    if canonical(source.get("citation_scope")) != "final-source":
        reasons.append("not-final-source")
    if not content_verified(source):
        reasons.append("not-content-verified")
    if not relevance_mapped(source):
        reasons.append("not-relevance-mapped")
    if not scholarly_source(source):
        reasons.append("not-scholarly-literature")
    return reasons


def count_eligible_scholarly_sources(
    sources: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    counted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: dict[str, str] = {}
    for raw in sources:
        if not isinstance(raw, dict):
            rejected.append({"source_id": "", "reasons": ["invalid-record"]})
            continue
        reasons = source_ineligibility_reasons(raw)
        key = source_dedup_key(raw)
        if key in seen:
            reasons.append(f"duplicate-of:{seen[key]}")
        if reasons:
            rejected.append(
                {
                    "source_id": str(raw.get("source_id") or ""),
                    "reasons": sorted(set(reasons)),
                }
            )
            continue
        seen[key] = str(raw.get("source_id") or "")
        counted.append(raw)
    return counted, rejected


def empty_sufficiency_contract() -> dict[str, Any]:
    return {
        "mode": "fallback",
        "screened_source_ids": [],
        "final_source_ids": [],
        "core_reading_source_ids": [],
        "benchmark": {
            "target_venue": "",
            "article_type": "article",
            "target_word_count": None,
            "samples": [],
        },
        "coverage": {
            key: {
                "status": "unresolved",
                "source_ids": [],
                "synthesis_ids": [],
                "rationale": "",
            }
            for key in COVERAGE_KEYS
        },
        "saturation_rounds": [],
        "exhaustive_corpus_exception": {"requested": False},
    }


def validate_coverage_and_saturation(
    contract: dict[str, Any],
    *,
    valid_source_ids: set[str] | None = None,
    valid_synthesis_ids: set[str] | None = None,
    core_source_ids: set[str] | None = None,
    source_responsibilities: dict[str, set[str]] | None = None,
    valid_query_ids: set[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    coverage = contract.get("coverage")
    if not isinstance(coverage, dict):
        issues.append("literature coverage map is missing")
    else:
        for key in COVERAGE_KEYS:
            entry = coverage.get(key)
            if not isinstance(entry, dict):
                issues.append(f"literature coverage {key} must be an evidence-mapped object")
                continue
            if canonical(entry.get("status")) != "covered":
                issues.append(f"literature coverage {key} is unresolved")
            source_ids = entry.get("source_ids")
            if not isinstance(source_ids, list) or not source_ids or any(
                not str(item).strip() for item in source_ids
            ):
                issues.append(f"literature coverage {key} must cite at least one final-source identity")
                source_ids = []
            normalized_sources = [str(item).strip() for item in source_ids]
            if len(normalized_sources) != len(set(normalized_sources)):
                issues.append(f"literature coverage {key} repeats a source identity")
            if valid_source_ids is not None:
                unknown = sorted(set(normalized_sources) - valid_source_ids)
                if unknown:
                    issues.append(
                        f"literature coverage {key} cites sources that are not eligible scholarly final sources: {', '.join(unknown)}"
                    )
            if core_source_ids is not None and not set(normalized_sources).intersection(
                core_source_ids
            ):
                issues.append(
                    f"literature coverage {key} must be anchored by at least one core reading"
                )
            if source_responsibilities is not None and core_source_ids is not None:
                required = COVERAGE_RESPONSIBILITY_KEYS[key]
                responsible_core = {
                    source_id
                    for source_id in normalized_sources
                    if source_id in core_source_ids
                    and source_responsibilities.get(source_id, set()).intersection(required)
                }
                if not responsible_core:
                    issues.append(
                        f"literature coverage {key} needs a core reading explicitly mapped to "
                        + "/".join(sorted(required))
                    )
            synthesis_ids = entry.get("synthesis_ids")
            if not isinstance(synthesis_ids, list) or not synthesis_ids or any(
                not str(item).strip() for item in synthesis_ids
            ):
                issues.append(
                    f"literature coverage {key} must cite at least one synthesis identity"
                )
                synthesis_ids = []
            normalized_syntheses = [str(item).strip() for item in synthesis_ids]
            if len(normalized_syntheses) != len(set(normalized_syntheses)):
                issues.append(f"literature coverage {key} repeats a synthesis identity")
            if valid_synthesis_ids is not None:
                unknown = sorted(set(normalized_syntheses) - valid_synthesis_ids)
                if unknown:
                    issues.append(
                        f"literature coverage {key} cites unknown syntheses: {', '.join(unknown)}"
                    )
            if not str(entry.get("rationale") or "").strip():
                issues.append(f"literature coverage {key} needs a substantive rationale")
    rounds = contract.get("saturation_rounds")
    if not isinstance(rounds, list) or len(rounds) < 2:
        issues.append("at least two consecutive focused saturation rounds are required")
    else:
        round_query_sets: list[set[str]] = []
        for index, round_record in enumerate(rounds[-2:], start=len(rounds) - 1):
            if not isinstance(round_record, dict):
                issues.append(f"saturation round {index} is invalid")
                continue
            query_ids = round_record.get("query_ids")
            if not isinstance(query_ids, list) or not query_ids or any(not str(item).strip() for item in query_ids):
                issues.append(f"saturation round {index} must retain query IDs")
                normalized_query_ids: set[str] = set()
            else:
                normalized_query_ids = {str(item).strip() for item in query_ids}
                if len(normalized_query_ids) != len(query_ids):
                    issues.append(f"saturation round {index} repeats a query ID")
                if valid_query_ids is not None:
                    unknown = sorted(normalized_query_ids - valid_query_ids)
                    if unknown:
                        issues.append(
                            f"saturation round {index} cites missing or incomplete queries: {', '.join(unknown)}"
                        )
            round_query_sets.append(normalized_query_ids)
            if not str(round_record.get("purpose") or "").strip():
                issues.append(f"saturation round {index} must state its focused purpose")
            if round_record.get("new_major_position") is not False:
                issues.append(f"saturation round {index} still reveals a new major position")
            if round_record.get("new_decisive_evidence_type") is not False:
                issues.append(f"saturation round {index} still reveals a decisive evidence type")
            if canonical(round_record.get("new_sources_role")) not in {
                "verification",
                "boundary",
                "known-gap",
                "none",
            }:
                issues.append(
                    f"saturation round {index} must classify new sources as verification, boundary, known-gap, or none"
                )
        if len(round_query_sets) == 2 and round_query_sets[0].intersection(
            round_query_sets[1]
        ):
            issues.append(
                "the final two saturation rounds must use distinct recorded query executions"
            )
    return issues


def validate_exhaustive_exception(exception: Any, *, fallback_minimum: int) -> list[str]:
    if not isinstance(exception, dict) or exception.get("requested") is not True:
        return ["exhaustive-corpus exception was not requested"]
    issues: list[str] = []
    if not str(exception.get("search_boundary") or "").strip():
        issues.append("exhaustive-corpus exception must disclose the complete search boundary")
    query_ids = exception.get("query_ids")
    if not isinstance(query_ids, list) or not query_ids or any(
        not str(item).strip() for item in query_ids
    ):
        issues.append("exhaustive-corpus exception must retain every exhaustive-search query ID")
    if not str(exception.get("eligibility_rule") or "").strip():
        issues.append("exhaustive-corpus exception must state the corpus eligibility rule")
    if not str(exception.get("exhaustion_evidence") or "").strip():
        issues.append("exhaustive-corpus exception must retain evidence that the eligible corpus is exhausted")
    try:
        eligible_total = int(exception.get("eligible_total"))
        if eligible_total < 0 or eligible_total >= fallback_minimum:
            raise ValueError
    except (TypeError, ValueError):
        issues.append("eligible_total must be non-negative and below the applicable fallback minimum")
        eligible_total = -1
    included = exception.get("included_source_ids")
    if not isinstance(included, list) or len(set(map(str, included))) != eligible_total:
        issues.append("included_source_ids must enumerate the entire eligible corpus exactly once")
    if exception.get("all_eligible_included") is not True:
        issues.append("all_eligible_included must be true")
    if exception.get("user_confirmed") is not True or not str(
        exception.get("confirmation_evidence") or ""
    ).strip():
        issues.append("the user must explicitly confirm the exhaustive-corpus exception")
    reason = canonical(exception.get("reason"))
    if reason != "closed-corpus-exhausted":
        issues.append("only a demonstrably exhausted closed corpus can justify the exception")
    return issues


@dataclass
class SufficiencyResult:
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.issues


def _identity_verified(sample: dict[str, Any]) -> bool:
    return bool(
        str(sample.get("source_id") or "").strip()
        and (
            str(sample.get("doi") or "").strip()
            or str(sample.get("url") or "").strip()
            or str(sample.get("local_sha256") or "").strip()
        )
    )



def evaluate_citation_edges(
    registry: dict[str, Any],
    contract: dict[str, Any],
    *,
    counted_ids: set[str],
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Check coverage claims against verified citation edges.

    Structural edge problems and an unconnected foundational chain are issues.
    A registry without edges, or a counter-position with no critical-stance edge,
    only warns: the coverage is then self-reported rather than machine-checked.
    """

    issues: list[str] = []
    warnings: list[str] = []
    sources = registry.get("sources") if isinstance(registry.get("sources"), list) else []
    registered_ids = {
        str(item.get("source_id") or "").strip()
        for item in sources
        if isinstance(item, dict) and str(item.get("source_id") or "").strip()
    }
    structural = citation_edges.edge_issues(registry, valid_source_ids=registered_ids)
    issues.extend("citation edge " + item for item in structural)
    records = citation_edges.registry_edges(registry)
    known_edge_ids = set(citation_edges.edges_by_id(registry))
    coverage = contract.get("coverage") if isinstance(contract.get("coverage"), dict) else {}

    def entry_ids(key: str, field: str) -> list[str]:
        entry = coverage.get(key)
        raw = entry.get(field) if isinstance(entry, dict) else None
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    for key in ("foundational_chain", "counterarguments"):
        entry = coverage.get(key)
        if isinstance(entry, dict) and entry.get("edge_ids") is not None:
            raw = entry.get("edge_ids")
            if not isinstance(raw, list) or not raw or any(not str(item).strip() for item in raw):
                issues.append(f"literature coverage {key} edge_ids must be a non-empty list of edge identities")
            else:
                unknown = sorted({str(item).strip() for item in raw} - known_edge_ids)
                if unknown:
                    issues.append(
                        f"literature coverage {key} cites unknown citation edges: " + ", ".join(unknown)
                    )
    summary: dict[str, Any] = {
        "count": len(records),
        "foundational_chain": "self-reported",
        "counterarguments": "self-reported",
    }
    if not records:
        warnings.append(
            "literature_registry.json records no citation edges; foundational_chain connectivity and "
            "counter-position stance are self-reported (register edges from snowball results or full-text reading)"
        )
        return issues, warnings, summary
    if structural:
        return issues, warnings, summary
    chain_ids = entry_ids("foundational_chain", "source_ids")
    if chain_ids:
        graph = citation_edges.cites_adjacency(records)
        if len(chain_ids) == 1:
            touching = [
                edge
                for edge in citation_edges.edges_touching(records, chain_ids)
                if str(edge.get("relation") or "").strip() == "cites"
            ]
            if not touching:
                issues.append(
                    f"literature coverage foundational_chain source {chain_ids[0]} has no verified cites edge; "
                    "a chain needs at least one verified citation link"
                )
            else:
                summary["foundational_chain"] = "verified"
        else:
            connected, unreachable = citation_edges.connected_through(graph, chain_ids)
            if not connected:
                issues.append(
                    "literature coverage foundational_chain is not connected by verified cites edges; "
                    "unreachable from " + chain_ids[0] + ": " + ", ".join(unreachable)
                )
            else:
                summary["foundational_chain"] = "verified"
    counter_ids = entry_ids("counterarguments", "source_ids")
    if counter_ids:
        critical = citation_edges.edges_touching(citation_edges.critical_edges(records), counter_ids)
        critical = [
            edge
            for edge in critical
            if str(edge.get("from_source_id") or "").strip() in counted_ids
            or str(edge.get("to_source_id") or "").strip() in counted_ids
        ]
        if critical:
            summary["counterarguments"] = "verified"
        else:
            warnings.append(
                "literature coverage counterarguments has no critical-stance citation edge touching its sources; "
                "the counter-position is self-reported until a citing passage is read and registered"
            )
    return issues, warnings, summary


def evaluate_literature_sufficiency(
    *,
    config: dict[str, Any],
    registry: dict[str, Any],
    analysis: dict[str, Any],
    profile: str,
    stage: str,
    current_year: int | None = None,
) -> SufficiencyResult:
    result = SufficiencyResult()
    contract = analysis.get("literature_sufficiency")
    if not isinstance(contract, dict):
        result.issues.append("literature_sufficiency contract is missing")
        return result

    sources = registry.get("sources") if isinstance(registry.get("sources"), list) else []
    registry_by_id = {
        str(item.get("source_id") or ""): item
        for item in sources
        if isinstance(item, dict) and str(item.get("source_id") or "")
    }
    valid_query_ids = {
        str(item.get("query_id") or "").strip()
        for item in registry.get("queries") or []
        if isinstance(item, dict)
        and str(item.get("query_id") or "").strip()
        and canonical(item.get("status")) == "complete"
    }
    layers: dict[str, list[str]] = {}
    for key in ("screened_source_ids", "final_source_ids", "core_reading_source_ids"):
        raw = contract.get(key)
        if not isinstance(raw, list) or any(not str(item).strip() for item in raw):
            result.issues.append(f"{key} must be a list of non-empty source identities")
            layers[key] = []
            continue
        values = [str(item).strip() for item in raw]
        if len(values) != len(set(values)):
            result.issues.append(f"{key} contains duplicate source identities")
        unknown = sorted(set(values) - set(registry_by_id))
        if unknown:
            result.issues.append(f"{key} contains unknown source identities: {', '.join(unknown)}")
        layers[key] = values

    screened = set(layers.get("screened_source_ids", []))
    final_ids = set(layers.get("final_source_ids", []))
    core_ids = set(layers.get("core_reading_source_ids", []))
    registry_final_ids = {
        source_id
        for source_id, source in registry_by_id.items()
        if canonical(source.get("citation_scope")) == "final-source"
    }
    if not final_ids.issubset(screened):
        result.issues.append("every final-source identity must also appear in screened")
    if final_ids != registry_final_ids:
        missing = sorted(registry_final_ids - final_ids)
        extra = sorted(final_ids - registry_final_ids)
        detail: list[str] = []
        if missing:
            detail.append("missing " + ", ".join(missing))
        if extra:
            detail.append("not registered as final-source " + ", ".join(extra))
        result.issues.append(
            "final_source_ids must exactly match the registry final-source layer"
            + (": " + "; ".join(detail) if detail else "")
        )
    if not core_ids.issubset(final_ids):
        result.issues.append("every core-reading identity must also appear in final-source")

    selected_sources = [registry_by_id[item] for item in layers.get("final_source_ids", []) if item in registry_by_id]
    counted, rejected = count_eligible_scholarly_sources(selected_sources)
    counted_ids = [str(item.get("source_id") or "") for item in counted]

    mode = canonical(contract.get("mode"))
    benchmark_count: int | None = None
    benchmark_summary: dict[str, Any] = {"mode": mode or "missing"}
    if mode in {"target-venue", "target-venue-benchmark", "dynamic"}:
        benchmark = contract.get("benchmark")
        if not isinstance(benchmark, dict):
            result.issues.append("target-venue benchmark record is missing")
        else:
            samples = benchmark.get("samples")
            if not isinstance(samples, list):
                samples = []
            try:
                target_word_count = int(
                    benchmark.get("target_word_count") or config.get("target_word_count")
                )
            except (TypeError, ValueError):
                target_word_count = 0
            selection = select_comparable_samples(
                samples,
                target_venue=str(benchmark.get("target_venue") or config.get("target_name") or ""),
                article_type=str(benchmark.get("article_type") or config.get("article_type") or "article"),
                target_word_count=target_word_count,
                current_year=current_year,
            )
            result.issues.extend(selection.issues)
            identity_failures = [
                str(item.get("source_id") or f"sample-{index}")
                for index, item in enumerate(selection.samples, start=1)
                if not isinstance(item, dict) or not _identity_verified(item)
            ]
            if identity_failures:
                result.issues.append(
                    "selected benchmark samples lack verifiable DOI, URL, or local hash: "
                    + ", ".join(identity_failures)
                )
            benchmark_count = selection.p25
            benchmark_summary.update(
                {
                    "sample_count": len(selection.samples),
                    "window_years": selection.window_years,
                    "p25": selection.p25,
                    "sample_source_ids": [str(item.get("source_id") or "") for item in selection.samples],
                }
            )
    elif mode != "fallback":
        result.issues.append("literature_sufficiency.mode must be target-venue-benchmark or fallback")

    requirement = config.get("citation_requirement")
    requirement_issues = validate_citation_requirement(requirement)
    result.issues.extend(requirement_issues)
    try:
        floor = compute_floor(
            profile=profile,
            scene=str(config.get("scene") or "journal"),
            benchmark_count=benchmark_count,
            citation_requirement=requirement if isinstance(requirement, dict) and not requirement_issues else None,
        )
    except ValueError as exc:
        result.issues.append(str(exc))
        floor = compute_floor(
            profile=profile,
            scene=str(config.get("scene") or "journal"),
            benchmark_count=benchmark_count,
            citation_requirement=None,
        )

    effective_minimum = floor.hard_minimum
    exception = contract.get("exhaustive_corpus_exception")
    exception_valid = False
    if isinstance(exception, dict) and exception.get("requested") is True:
        exception_issues = validate_exhaustive_exception(
            exception,
            fallback_minimum=floor.fallback_minimum,
        )
        if exception_issues:
            result.issues.extend(exception_issues)
        else:
            unknown_exception_queries = sorted(
                {
                    str(item).strip()
                    for item in exception.get("query_ids") or []
                    if str(item).strip()
                }
                - valid_query_ids
            )
            if unknown_exception_queries:
                result.issues.append(
                    "exhaustive-corpus exception cites missing or incomplete queries: "
                    + ", ".join(unknown_exception_queries)
                )
            included_ids = {
                str(item).strip() for item in exception.get("included_source_ids") or []
            }
            counted_id_set = set(counted_ids)
            if included_ids != counted_id_set:
                result.issues.append(
                    "exhaustive-corpus included_source_ids must exactly equal the eligible scholarly final sources"
                )
            else:
                exception_valid = True
                effective_minimum = int(exception["eligible_total"])

    numeric_gap = max(0, effective_minimum - len(counted))
    accumulation_issues: list[str] = []
    if numeric_gap:
        accumulation_issues.append(
            f"eligible scholarly literature is {len(counted)}; minimum is {effective_minimum}; gap is {numeric_gap}"
        )
    if rejected:
        rejected_ids = [str(item.get("source_id") or "<unknown>") for item in rejected]
        result.warnings.append(
            "listed final sources retained for fact/material roles but not counted toward the scholarly floor: "
            + ", ".join(rejected_ids)
        )

    syntheses = analysis.get("syntheses") if isinstance(analysis.get("syntheses"), list) else []
    synthesis_ids = {
        str(item.get("synthesis_id") or "").strip()
        for item in syntheses
        if isinstance(item, dict) and str(item.get("synthesis_id") or "").strip()
    }
    coverage_issues = validate_coverage_and_saturation(
        contract,
        valid_source_ids=set(counted_ids),
        valid_synthesis_ids=synthesis_ids,
        core_source_ids=core_ids.intersection(counted_ids),
        source_responsibilities={
            str(source.get("source_id") or ""): {
                canonical(item)
                for item in (
                    (source.get("relevance") or {}).get("responsibilities")
                    if isinstance(source.get("relevance"), dict)
                    else []
                )
                if str(item).strip()
            }
            for source in counted
        },
        valid_query_ids=valid_query_ids,
    )
    edge_issues, edge_warnings, edge_summary = evaluate_citation_edges(
        registry,
        contract,
        counted_ids=set(counted_ids),
    )
    coverage_issues.extend(edge_issues)
    result.warnings.extend(edge_warnings)
    readings = analysis.get("source_readings") if isinstance(analysis.get("source_readings"), list) else []
    reading_by_source = {
        str(item.get("source_id") or ""): item for item in readings if isinstance(item, dict)
    }
    for source_id in sorted(core_ids):
        reading = reading_by_source.get(source_id)
        if not isinstance(reading, dict):
            accumulation_issues.append(f"core source {source_id} has no critical reading record")
        elif canonical(reading.get("status")) != "complete" or canonical(
            reading.get("evidence_level")
        ) != "full-text":
            accumulation_issues.append(
                f"core source {source_id} requires a complete full-text critical reading"
            )
    synthesis_linked_ids = {
        str(link.get("source_id") or "").strip()
        for synthesis in syntheses
        if isinstance(synthesis, dict)
        for link in (synthesis.get("source_links") or [])
        if isinstance(link, dict) and str(link.get("source_id") or "").strip()
    }
    core_without_synthesis = sorted(core_ids - synthesis_linked_ids)
    if core_without_synthesis:
        accumulation_issues.append(
            "core readings must enter at least one synthesis: " + ", ".join(core_without_synthesis)
        )

    audit_only = canonical(profile) == "manuscript-audit"
    if audit_only:
        result.warnings.extend(accumulation_issues)
        result.warnings.extend(coverage_issues)
    else:
        result.issues.extend(accumulation_issues)
        result.issues.extend(coverage_issues)

    recorded_count = contract.get("current_qualified_count")
    if recorded_count is None:
        result.issues.append("current_qualified_count is required")
    else:
        try:
            if int(recorded_count) != len(counted):
                result.issues.append(
                    f"current_qualified_count={recorded_count} does not match computed count {len(counted)}"
                )
        except (TypeError, ValueError):
            result.issues.append("current_qualified_count must be an integer when provided")

    result.summary = {
        "status": "pass" if not result.issues and not numeric_gap else ("gap-reported" if audit_only else "fail"),
        "profile": profile,
        "stage": stage,
        "screened_count": len(screened),
        "listed_final_count": len(final_ids),
        "qualified_scholarly_count": len(counted),
        "qualified_source_ids": counted_ids,
        "rejected_final_sources": rejected,
        "core_reading_count": len(core_ids),
        "floor": floor.as_dict(),
        "effective_minimum": effective_minimum,
        "gap": numeric_gap,
        "benchmark": benchmark_summary,
        "coverage_complete": not coverage_issues,
        "citation_edges": edge_summary,
        "saturation_round_count": len(contract.get("saturation_rounds") or []),
        "exhaustive_exception_valid": exception_valid,
    }
    return result
