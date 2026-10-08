#!/usr/bin/env python3
"""Resolve, inspect, and validate the branch taste-card registry.

The registry (``references/taste/branch-taste-cards.json``) projects the four
flavours of academic taste (清味／厚味／雅味／趣味) onto political-science
branches.  It is a signal source for the pairwise taste judge and the
dual-reader test; it is never a stage gate.  ``direction_contract.field``
resolves to at most one card by alias, ``topic_selection.taste_card`` pins one
explicitly, and any ambiguity or miss keeps the taste features off so only the
existing validity gates run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "avereth-branch-taste-cards/v1"
SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = SKILL_ROOT / "references" / "taste" / "branch-taste-cards.json"
DEFAULT_ANATOMY = SKILL_ROOT / "references" / "top-journal-anatomy.md"
FLAVORS = ("clear", "thick", "elegant", "interesting")
FLAVOR_LABELS = {
    "clear": "清味",
    "thick": "厚味",
    "elegant": "雅味",
    "interesting": "趣味",
}
CITATION_RELIABILITY = frozenset({"high", "medium", "low"})
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESEARCH_MOVE_SCHEMA = "avereth-research-move/v1"
TEACHING_PROJECTION_SCHEMA = "avereth-teaching-projection/v1"
MAX_TEACHING_EXEMPLARS = 3
MAX_SOURCE_CHARS = 1200
MAX_MOVE_FIELD_CHARS = 400
_PUNCT_RE = re.compile(r"[\s\-_/·、，,。.：:；;（）()《》<>\"'“”‘’]+")


def normalize_text(value: Any) -> str:
    """Lower-case and strip spacing/punctuation so aliases match loosely but deterministically."""

    return _PUNCT_RE.sub("", str(value or "").strip().lower())


def _text(value: Any) -> str:
    return str(value or "").strip()


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else DEFAULT_REGISTRY
    payload = json.loads(target.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("taste-card registry must be one JSON object")
    return payload


def registry_sha256(path: Path | None = None) -> str:
    target = Path(path) if path else DEFAULT_REGISTRY
    return hashlib.sha256(target.read_bytes()).hexdigest()


def cards(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = registry.get("cards")
    return [dict(item) for item in raw if isinstance(item, Mapping)] if isinstance(raw, list) else []


def card_by_slug(registry: Mapping[str, Any], slug: str) -> dict[str, Any] | None:
    wanted = _text(slug)
    for card in cards(registry):
        if _text(card.get("slug")) == wanted:
            return card
    return None


def exemplar_counts(card: Mapping[str, Any]) -> tuple[int, int]:
    exemplars = card.get("exemplars")
    if not isinstance(exemplars, Mapping):
        return 0, 0
    positive = exemplars.get("positive")
    negative = exemplars.get("negative")
    return (
        len(positive) if isinstance(positive, list) else 0,
        len(negative) if isinstance(negative, list) else 0,
    )


def exemplar_calibration_status(card: Mapping[str, Any]) -> str:
    """Registration never establishes independently measured judgment quality."""
    selection = card.get("exemplar_selection")
    if isinstance(selection, Mapping) and selection.get("protocol") == "anonymous-mixed-pool/v2":
        return "unvalidated"
    return "legacy-unreviewed" if any(exemplar_counts(card)) else "not-assessed"


def card_status(card: Mapping[str, Any]) -> str:
    positive, negative = exemplar_counts(card)
    return "exemplars-registered" if positive + negative else "card-only"


def research_move_issues(exemplar: Mapping[str, Any]) -> list[str]:
    """Check a source-bounded teaching record; historical praise is not evidence."""
    move = exemplar.get("research_move")
    if not isinstance(move, Mapping):
        return ["research_move_missing"]
    issues: list[str] = []
    if move.get("schema_version") != RESEARCH_MOVE_SCHEMA:
        issues.append("research_move_schema_invalid")
    if not isinstance(move.get("version"), str) or not 1 <= len(move["version"]) <= 80:
        issues.append("research_move_version_missing")
    source = move.get("source")
    if not isinstance(source, Mapping):
        return issues + ["source_missing"]
    identifier = _text(exemplar.get("identifier"))
    if not identifier or len(identifier) > 400 or source.get("identifier") != identifier:
        issues.append("source_identity_mismatch")
    if len(_text(exemplar.get("title"))) > MAX_MOVE_FIELD_CHARS:
        issues.append("title_outside_budget")
    level = source.get("level")
    if level not in {"abstract", "inspected_excerpt", "full_text", "synthetic"}:
        issues.append("source_level_insufficient")
    expected_origin = "synthetic" if level == "synthetic" else "published_result"
    if source.get("origin") != expected_origin:
        issues.append("source_origin_mismatch")
    if level == "synthetic" and not identifier.startswith("SYN-"):
        issues.append("synthetic_identity_required")
    content = source.get("content")
    if not isinstance(content, str) or not 40 <= len(content) <= MAX_SOURCE_CHARS:
        issues.append("source_content_outside_budget")
    elif source.get("content_sha256") != hashlib.sha256(content.encode("utf-8")).hexdigest():
        issues.append("source_content_hash_mismatch")
    if not isinstance(source.get("locator"), str) or not 1 <= len(source["locator"]) <= MAX_MOVE_FIELD_CHARS:
        issues.append("source_locator_missing")
    for key, status in (("verification", "content-verified"), ("permission", "permitted")):
        record = source.get(key)
        if not isinstance(record, Mapping) or record.get("status") != status or not isinstance(record.get("basis"), str) or not 12 <= len(record["basis"]) <= MAX_MOVE_FIELD_CHARS:
            issues.append(f"source_{key}_missing")
    for key in ("prior_understanding", "move", "limits"):
        if not isinstance(move.get(key), str) or not 8 <= len(move[key]) <= MAX_MOVE_FIELD_CHARS:
            issues.append(f"{key}_outside_budget")
    support = move.get("support")
    allowed_basis = {"synthetic"} if level == "synthetic" else ({"author_claim"} if level == "abstract" else {"author_claim", "inspected_argument"})
    if not isinstance(support, Mapping) or support.get("basis") not in allowed_basis:
        issues.append("support_exceeds_source_level")
    if not isinstance(support, Mapping) or not isinstance(support.get("text"), str) or not 8 <= len(support["text"]) <= MAX_MOVE_FIELD_CHARS:
        issues.append("support_outside_budget")
    ablation = move.get("without_move")
    if not isinstance(ablation, Mapping) or ablation.get("kind") != "synthetic_ablation":
        issues.append("ablation_must_be_synthetic")
    if not isinstance(ablation, Mapping) or not isinstance(ablation.get("text"), str) or not 8 <= len(ablation["text"]) <= MAX_MOVE_FIELD_CHARS:
        issues.append("ablation_outside_budget")
    return issues


def teaching_projection(card: Mapping[str, Any], *, enabled: bool = False, limit: int = 2) -> dict[str, Any]:
    """Project at most three registered examples without promoting old selections."""
    if not 0 <= limit <= MAX_TEACHING_EXEMPLARS:
        raise ValueError(f"teaching limit must be between 0 and {MAX_TEACHING_EXEMPLARS}")
    projection: dict[str, Any] = {
        "schema_version": TEACHING_PROJECTION_SCHEMA,
        "enabled": enabled,
        "limit": limit,
        "purpose": "teaching-only",
        "examples": [],
        "excluded": [],
    }
    if not enabled or limit == 0:
        return projection
    exemplars = card.get("exemplars") or {}
    seen: set[str] = set()
    for role in ("positive", "negative"):
        for exemplar in exemplars.get(role) or []:
            identifier = _text(exemplar.get("identifier"))
            issues = research_move_issues(exemplar)
            if identifier in seen:
                issues.append("duplicate_exemplar_identity")
            seen.add(identifier)
            if issues:
                projection["excluded"].append({"identifier": identifier, "reasons": issues})
                continue
            if len(projection["examples"]) >= limit:
                projection["excluded"].append({"identifier": identifier, "reasons": ["teaching_budget"]})
                continue
            move = exemplar["research_move"]
            projection["examples"].append({
                "identifier": identifier,
                "title": _text(exemplar.get("title")),
                "schema_version": move["schema_version"],
                "version": move["version"],
                "source": {
                    **{key: move["source"][key] for key in ("identifier", "level", "origin", "content", "content_sha256", "locator")},
                    **{key: {field: move["source"][key][field] for field in ("status", "basis")} for key in ("verification", "permission")},
                },
                "prior_understanding": move["prior_understanding"],
                "move": move["move"],
                "support": {key: move["support"][key] for key in ("basis", "text")},
                "without_move": {key: move["without_move"][key] for key in ("kind", "text")},
                "limits": move["limits"],
            })
    return projection


EXEMPLAR_MAX_AGE_DAYS = 365


def _parse_stamp(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def exemplar_age_days(card: Mapping[str, Any], *, now: datetime | None = None) -> int | None:
    """Days since the oldest harvest behind the card's exemplars; None when nothing is registered."""

    exemplars = card.get("exemplars")
    if not isinstance(exemplars, Mapping):
        return None
    stamps: list[datetime] = []
    for role in ("positive", "negative"):
        for item in exemplars.get(role) or []:
            if isinstance(item, Mapping):
                stamp = _parse_stamp(item.get("harvested_at")) or _parse_stamp(item.get("selected_at"))
                if stamp:
                    stamps.append(stamp)
    if not stamps:
        return None
    current = now or datetime.now(timezone.utc)
    return max(0, (current - min(stamps)).days)


def stale_exemplar_warnings(registry: Mapping[str, Any], *, now: datetime | None = None) -> list[str]:
    warnings: list[str] = []
    for card in cards(registry):
        if card_status(card) != "exemplars-registered":
            continue
        age = exemplar_age_days(card, now=now)
        if age is None:
            warnings.append(f"{card.get('slug')}: exemplars carry no harvested_at/selected_at stamp")
        elif age > EXEMPLAR_MAX_AGE_DAYS:
            warnings.append(
                f"{card.get('slug')}: exemplars are {age} days old; rerun taste_exemplars.py harvest/shortlist/select"
            )
    return warnings


def hot_terms_for(registry: Mapping[str, Any], card: Mapping[str, Any]) -> list[str]:
    """Return generic plus branch hot terms, longest first so nested terms strip cleanly."""

    generic = registry.get("generic_hot_terms")
    branch = card.get("hot_terms")
    merged: list[str] = []
    for source in (branch, generic):
        if isinstance(source, list):
            for item in source:
                term = _text(item)
                if term and term not in merged:
                    merged.append(term)
    return sorted(merged, key=lambda item: (-len(item), item))


def _exemplar_issues(prefix: str, items: Any) -> list[str]:
    issues: list[str] = []
    if items is None:
        return [f"{prefix} is missing"]
    if not isinstance(items, list):
        return [f"{prefix} must be a list"]
    for index, item in enumerate(items):
        path = f"{prefix}[{index}]"
        if not isinstance(item, Mapping):
            issues.append(f"{path} must be an object")
            continue
        if len(_text(item.get("title"))) < 4:
            issues.append(f"{path}.title is missing")
        if len(_text(item.get("why"))) < 8:
            issues.append(f"{path}.why must say what makes it a positive or negative exemplar")
        has_identifier = len(_text(item.get("identifier"))) >= 6
        has_venue_year = bool(_text(item.get("venue"))) and isinstance(item.get("year"), int)
        if not (has_identifier or has_venue_year):
            issues.append(f"{path} needs an identifier or venue plus year")
    return issues


def registry_issues(registry: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    if _text(registry.get("schema_version")) != SCHEMA_VERSION:
        issues.append(f"schema_version must be {SCHEMA_VERSION}")
    generic = registry.get("generic_hot_terms")
    if not isinstance(generic, list) or any(not _text(item) for item in generic):
        issues.append("generic_hot_terms must be a list of non-empty strings")
    all_cards = cards(registry)
    if not all_cards:
        issues.append("registry has no cards")
        return issues
    slugs = [_text(card.get("slug")) for card in all_cards]
    seen_slugs: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for card, slug in zip(all_cards, slugs):
        path = f"cards[{slug or '?'}]"
        if not SLUG_RE.match(slug):
            issues.append(f"{path}.slug must be kebab-case ascii")
        if slug in seen_slugs:
            issues.append(f"{path}.slug is duplicated")
        seen_slugs.add(slug)
        names = card.get("names")
        if not isinstance(names, Mapping) or not _text(names.get("zh")) or not _text(names.get("en")):
            issues.append(f"{path}.names must carry zh and en")
        aliases = card.get("aliases")
        if not isinstance(aliases, list) or not aliases:
            issues.append(f"{path}.aliases must be a non-empty list")
        else:
            for alias in aliases:
                key = normalize_text(alias)
                if not key:
                    issues.append(f"{path}.aliases contains an empty alias")
                    continue
                owner = seen_aliases.get(key)
                if owner and owner != slug:
                    issues.append(f"{path}.aliases '{alias}' collides with card {owner}")
                seen_aliases[key] = slug
        flavors = card.get("flavors")
        if not isinstance(flavors, Mapping):
            issues.append(f"{path}.flavors is missing")
        else:
            for flavor in FLAVORS:
                if len(_text(flavors.get(flavor))) < 8:
                    issues.append(f"{path}.flavors.{flavor} ({FLAVOR_LABELS[flavor]}) must state a criterion")
            extra = sorted(set(flavors) - set(FLAVORS))
            if extra:
                issues.append(f"{path}.flavors has unknown keys: {', '.join(extra)}")
        smells = card.get("mediocrity_smells")
        if not isinstance(smells, list) or len([item for item in smells if _text(item)]) < 2:
            issues.append(f"{path}.mediocrity_smells needs at least two entries")
        signals = card.get("calibration_signals")
        if not isinstance(signals, Mapping):
            issues.append(f"{path}.calibration_signals is missing")
        else:
            cn = signals.get("cn_journals")
            en = signals.get("en_journals")
            if not (isinstance(cn, list) and cn) and not (isinstance(en, list) and en):
                issues.append(f"{path}.calibration_signals needs cn_journals or en_journals")
            if _text(signals.get("citation_reliability")) not in CITATION_RELIABILITY:
                issues.append(f"{path}.calibration_signals.citation_reliability must be high, medium, or low")
            non_citation = signals.get("non_citation_signals")
            if not isinstance(non_citation, list) or not non_citation:
                issues.append(f"{path}.calibration_signals.non_citation_signals must list at least one signal")
        hot = card.get("hot_terms")
        if not isinstance(hot, list) or any(not _text(item) for item in hot):
            issues.append(f"{path}.hot_terms must be a list of non-empty strings")
        adjacent = card.get("adjacent_branches")
        if not isinstance(adjacent, list) or not adjacent:
            issues.append(f"{path}.adjacent_branches must name at least one other card")
        else:
            for other in adjacent:
                if _text(other) == slug:
                    issues.append(f"{path}.adjacent_branches cannot include itself")
                elif _text(other) not in slugs:
                    issues.append(f"{path}.adjacent_branches references unknown card {other}")
        exemplars = card.get("exemplars")
        if not isinstance(exemplars, Mapping):
            issues.append(f"{path}.exemplars must be an object with positive and negative lists")
        else:
            issues.extend(_exemplar_issues(f"{path}.exemplars.positive", exemplars.get("positive")))
            issues.extend(_exemplar_issues(f"{path}.exemplars.negative", exemplars.get("negative")))
    return issues


@dataclass(frozen=True)
class Resolution:
    status: str
    slug: str | None
    matches: tuple[str, ...] = ()
    reason: str = ""
    matched_alias: str = ""

    @property
    def resolved(self) -> bool:
        return self.status in {"resolved", "explicit"} and bool(self.slug)


def resolve_card(
    registry: Mapping[str, Any],
    field_text: Any,
    *,
    explicit: Any = None,
) -> Resolution:
    """Map a free-text field to one card; ambiguity or no match keeps taste features off."""

    explicit_slug = _text(explicit)
    if explicit_slug:
        if card_by_slug(registry, explicit_slug) is None:
            return Resolution("unknown_explicit", None, reason=f"taste_card {explicit_slug} is not registered")
        return Resolution("explicit", explicit_slug, (explicit_slug,), "topic_selection.taste_card")
    haystack = normalize_text(field_text)
    if not haystack:
        return Resolution("no_card", None, reason="direction_contract.field is empty")
    best: list[tuple[int, str, str]] = []
    for card in cards(registry):
        slug = _text(card.get("slug"))
        aliases = card.get("aliases") if isinstance(card.get("aliases"), list) else []
        longest = 0
        longest_alias = ""
        for alias in aliases:
            key = normalize_text(alias)
            if key and key in haystack and len(key) > longest:
                longest = len(key)
                longest_alias = _text(alias)
        if longest:
            best.append((longest, slug, longest_alias))
    if not best:
        return Resolution("no_card", None, reason="no registered alias matches the field")
    best.sort(key=lambda item: (-item[0], item[1]))
    top = best[0][0]
    winners = [item for item in best if item[0] == top]
    if len(winners) > 1:
        return Resolution(
            "ambiguous",
            None,
            tuple(item[1] for item in winners),
            reason="several cards match with equal alias length; pin topic_selection.taste_card",
        )
    return Resolution("resolved", winners[0][1], (winners[0][1],), "direction_contract.field", winners[0][2])


def resolve_from_config(registry: Mapping[str, Any], payload: Mapping[str, Any]) -> Resolution:
    direction = payload.get("direction_contract")
    field_text = direction.get("field") if isinstance(direction, Mapping) else ""
    policy = payload.get("topic_selection")
    explicit = policy.get("taste_card") if isinstance(policy, Mapping) else None
    return resolve_card(registry, field_text, explicit=explicit)


def anatomy_issues(registry: Mapping[str, Any], anatomy_text: str) -> list[str]:
    """Every card must appear in the human projection table of top-journal-anatomy.md."""

    issues: list[str] = []
    if "分支品味卡" not in anatomy_text:
        return ["top-journal-anatomy.md has no 分支品味卡 section"]
    for card in cards(registry):
        slug = _text(card.get("slug"))
        names = card.get("names") if isinstance(card.get("names"), Mapping) else {}
        zh = _text(names.get("zh"))
        if f"`{slug}`" not in anatomy_text:
            issues.append(f"top-journal-anatomy.md does not list card slug `{slug}`")
        if zh and zh not in anatomy_text:
            issues.append(f"top-journal-anatomy.md does not name card {zh}")
    return issues


def _read_workspace_config(workspace: Path) -> dict[str, Any]:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from avereth_core.config import read_config  # noqa: WPS433 - local runtime import

    config_read = read_config(workspace)
    if config_read.path is None:
        raise ValueError("workflow configuration is missing")
    return dict(config_read.payload)


def render_card(registry: Mapping[str, Any], card: Mapping[str, Any]) -> str:
    names = card.get("names") if isinstance(card.get("names"), Mapping) else {}
    flavors = card.get("flavors") if isinstance(card.get("flavors"), Mapping) else {}
    signals = card.get("calibration_signals") if isinstance(card.get("calibration_signals"), Mapping) else {}
    positive, negative = exemplar_counts(card)
    lines = [
        f"{card.get('slug')}  {names.get('zh', '')} / {names.get('en', '')}  [{card_status(card)}]",
    ]
    for flavor in FLAVORS:
        lines.append(f"  {FLAVOR_LABELS[flavor]}: {flavors.get(flavor, '')}")
    lines.append("  平庸气味: " + "；".join(_text(item) for item in card.get("mediocrity_smells") or []))
    lines.append("  中文刊: " + "、".join(signals.get("cn_journals") or []))
    lines.append("  英文刊: " + "、".join(signals.get("en_journals") or []))
    lines.append("  非引用信号: " + "；".join(signals.get("non_citation_signals") or []))
    lines.append(f"  引用信号可靠性: {signals.get('citation_reliability', '')}")
    lines.append("  热词(含通用): " + "、".join(hot_terms_for(registry, card)))
    lines.append("  相邻分支: " + ", ".join(card.get("adjacent_branches") or []))
    lines.append(f"  范本: 正例 {positive} / 负例 {negative}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="list registered cards and their exemplar status")
    show_parser = subparsers.add_parser("show", help="print one card")
    show_parser.add_argument("slug")
    resolve_parser = subparsers.add_parser("resolve", help="resolve a field or workspace to one card")
    resolve_group = resolve_parser.add_mutually_exclusive_group(required=True)
    resolve_group.add_argument("--field", help="free-text direction_contract.field")
    resolve_group.add_argument("--workspace", type=Path, help="workspace with workflow_config.json")
    resolve_parser.add_argument("--taste-card", help="explicit slug that overrides alias matching")
    validate_parser = subparsers.add_parser("validate", help="validate the registry and its anatomy projection")
    validate_parser.add_argument("--anatomy", type=Path, default=DEFAULT_ANATOMY)
    validate_parser.add_argument("--skip-anatomy", action="store_true")
    args = parser.parse_args(argv)

    try:
        registry = load_registry(args.registry)
        if args.command == "list":
            for card in cards(registry):
                names = card.get("names") if isinstance(card.get("names"), Mapping) else {}
                age = exemplar_age_days(card)
                age_text = "-" if age is None else f"{age}d" + (" STALE" if age > EXEMPLAR_MAX_AGE_DAYS else "")
                print(f"{card.get('slug')}\t{names.get('zh', '')}\t{card_status(card)}\t{age_text}")
            return 0
        if args.command == "show":
            card = card_by_slug(registry, args.slug)
            if card is None:
                print(f"unknown card: {args.slug}")
                return 2
            print(render_card(registry, card))
            return 0
        if args.command == "resolve":
            if args.workspace is not None:
                payload = _read_workspace_config(args.workspace)
                if args.taste_card:
                    policy = dict(payload.get("topic_selection") or {})
                    policy["taste_card"] = args.taste_card
                    payload["topic_selection"] = policy
                resolution = resolve_from_config(registry, payload)
            else:
                resolution = resolve_card(registry, args.field, explicit=args.taste_card)
            if resolution.resolved:
                suffix = f" via {resolution.matched_alias}" if resolution.matched_alias else ""
                print(f"RESOLVED {resolution.slug} ({resolution.reason}{suffix})")
                return 0
            detail = ", ".join(resolution.matches) if resolution.matches else resolution.reason
            print(f"{resolution.status.upper()} {detail}")
            return 2
        if args.command == "validate":
            issues = registry_issues(registry)
            if not args.skip_anatomy:
                issues.extend(anatomy_issues(registry, args.anatomy.read_text(encoding="utf-8-sig")))
            if issues:
                print("FAIL")
                print("\n".join(f"- {item}" for item in issues))
                return 1
            print(f"PASS ({len(cards(registry))} cards)")
            for warning in stale_exemplar_warnings(registry):
                print(f"WARN {warning}")
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL\n- {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
