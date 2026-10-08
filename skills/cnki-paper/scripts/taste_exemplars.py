#!/usr/bin/env python3
"""Sample journal-year cohorts and collect anonymous, mixed-pool taste opinions.

Harvest signals choose high, low, and middle sampling strata. Readers see only
temporary identities, titles, and abstracts; every item may receive any label,
including uncertainty. Selection records provenance, not calibrated quality.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import taste_cards  # noqa: E402
from avereth_core.hosts import read_agent_capture, write_agent_capture_request  # noqa: E402

HARVEST_SCHEMA = "avereth-taste-harvest/v1"
SHORTLIST_SCHEMA = "avereth-taste-shortlist/v1"
OPENALEX_API = "https://api.openalex.org"
USER_AGENT = {"User-Agent": "avereth-taste/1.0"}
DEFAULT_YEARS = (2019, 2025)
MIN_ABSTRACT_CHARS = {"openalex": 200, "cnki": 60}
MIN_REFERENCES_OPENALEX = 5
MIN_COHORT = 15
CITATION_WINDOW_YEARS = 2
POSITIVE_PERCENTILE = 90.0
NEGATIVE_PERCENTILE = 25.0
DEFAULT_TOP = 12
DEFAULT_BOTTOM = 8
DEFAULT_PER_JOURNAL = 4
DEFAULT_PICK_POSITIVE = 5
DEFAULT_PICK_NEGATIVE = 3
SELECTED_BY = "cohort-signal+isolated-reading"
# Result-page rows that are not research articles (news, calls, editor notes, conference reports).
CNKI_NON_ARTICLE_RE = re.compile(r"简讯|投稿指南|征稿|启事|贺信|编者按|编者的话|会议综述|论坛综述|研讨会综述|年会综述|入选作品|总目录|目录索引|新书推介|书讯|更正|勘误|卷首语|发刊词|访谈$|访谈录")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc_now_stamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: Path, payload: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_years(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{4})\s*", value or "")
    if not match:
        raise ValueError("--years must look like 2019-2025")
    start, end = int(match.group(1)), int(match.group(2))
    if start > end:
        raise ValueError("--years start must not exceed end")
    return start, end


def record_id(source: str, identifier: str) -> str:
    return f"{source.upper()}-{sha256_text(identifier)[:12]}"


def hot_term_hits(text: str, terms: Sequence[str]) -> list[str]:
    lowered = text.lower()
    return [term for term in terms if term and term.lower() in lowered]


# --------------------------------------------------------------------------- harvest


def rebuild_abstract(inverted: Mapping[str, Sequence[int]] | None, limit: int = 2500) -> str:
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, indexes in inverted.items():
        for index in indexes:
            positions[int(index)] = word
    return " ".join(positions[index] for index in sorted(positions))[:limit]


def fetch_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=USER_AGENT)
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def resolve_openalex_source(name: str, *, mailto: str = "", fetch: Callable[[str], dict[str, Any]] = fetch_json) -> dict[str, Any] | None:
    query = {"search": name, "per-page": 5, "select": "id,display_name,issn_l,works_count,type"}
    if mailto:
        query["mailto"] = mailto
    payload = fetch(f"{OPENALEX_API}/sources?{urllib.parse.urlencode(query)}")
    wanted = taste_cards.normalize_text(name)
    journals = [item for item in payload.get("results") or [] if _text(item.get("type")) == "journal"]

    def as_source(result: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "name": name,
            "display_name": _text(result.get("display_name")),
            "source_id": _text(result.get("id")).rsplit("/", 1)[-1],
            "issn_l": _text(result.get("issn_l")),
            "works_count": int(result.get("works_count") or 0),
        }

    # Exact (or "The"-prefixed) match first; only then the shortest display name
    # that contains the wanted title, so "Public Administration" never resolves
    # to "Public Administration Review" when the exact journal exists.
    for result in journals:
        display = taste_cards.normalize_text(result.get("display_name"))
        if display == wanted or display == "the" + wanted:
            return as_source(result)
    containing = sorted(
        (result for result in journals if wanted in taste_cards.normalize_text(result.get("display_name"))),
        key=lambda result: len(taste_cards.normalize_text(result.get("display_name"))),
    )
    return as_source(containing[0]) if containing else None


def openalex_work_to_record(work: Mapping[str, Any], venue: str, hot_terms: Sequence[str]) -> dict[str, Any] | None:
    doi = _text(work.get("doi")).replace("https://doi.org/", "")
    identifier = doi or _text(work.get("id"))
    title = _text(work.get("title") or work.get("display_name"))
    if not identifier or len(title) < 8:
        return None
    if bool(work.get("is_retracted")):
        return None
    abstract = rebuild_abstract(work.get("abstract_inverted_index"))
    percentile = work.get("cited_by_percentile_year") if isinstance(work.get("cited_by_percentile_year"), Mapping) else {}
    return {
        "record_id": record_id("openalex", identifier),
        "source": "openalex",
        "identifier": identifier,
        "openalex_id": _text(work.get("id")),
        "title": title,
        "venue": venue,
        "year": int(work.get("publication_year") or 0),
        "cited_by": int(work.get("cited_by_count") or 0),
        "abstract": abstract,
        "language": _text(work.get("language")),
        "referenced_works_count": int(work.get("referenced_works_count") or 0),
        "openalex_percentile_year": {
            "min": percentile.get("min"),
            "max": percentile.get("max"),
        }
        if percentile
        else None,
        "fwci": work.get("fwci"),
        "hot_term_hits": hot_term_hits(f"{title} {abstract}", hot_terms),
    }


def harvest_openalex_journal(
    source: Mapping[str, Any],
    *,
    years: tuple[int, int],
    hot_terms: Sequence[str],
    mailto: str = "",
    max_records: int = 1500,
    fetch: Callable[[str], dict[str, Any]] = fetch_json,
    pause: float = 0.2,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cursor = "*"
    while cursor and len(records) < max_records:
        query = {
            "filter": (
                f"primary_location.source.id:{source['source_id']},"
                f"publication_year:{years[0]}-{years[1]},type:article,is_retracted:false"
            ),
            "per-page": 200,
            "cursor": cursor,
            "select": (
                "id,doi,title,display_name,publication_year,cited_by_count,"
                "cited_by_percentile_year,fwci,language,is_retracted,"
                "referenced_works_count,abstract_inverted_index"
            ),
        }
        if mailto:
            query["mailto"] = mailto
        payload = fetch(f"{OPENALEX_API}/works?{urllib.parse.urlencode(query)}")
        for work in payload.get("results") or []:
            record = openalex_work_to_record(work, source.get("display_name") or source["name"], hot_terms)
            if record:
                records.append(record)
        cursor = _text((payload.get("meta") or {}).get("next_cursor"))
        if pause:
            time.sleep(pause)
    return records


def empty_harvest(card: Mapping[str, Any], years: tuple[int, int]) -> dict[str, Any]:
    return {
        "schema_version": HARVEST_SCHEMA,
        "card_slug": _text(card.get("slug")),
        "years": list(years),
        "harvested_at": _utc_now_stamp(),
        "journals": [],
        "records": [],
    }


def merge_records(harvest: dict[str, Any], records: Sequence[Mapping[str, Any]]) -> int:
    existing = {item["record_id"]: index for index, item in enumerate(harvest["records"]) if isinstance(item, Mapping)}
    added = 0
    for record in records:
        key = record["record_id"]
        if key in existing:
            harvest["records"][existing[key]] = dict(record)
        else:
            harvest["records"].append(dict(record))
            existing[key] = len(harvest["records"]) - 1
            added += 1
    return added


def cnki_record(raw: Mapping[str, Any], hot_terms: Sequence[str]) -> dict[str, Any] | None:
    """Normalise one cnki-parse-results / cnki-paper-detail export row."""

    title = _text(raw.get("title"))
    url = _text(raw.get("url") or raw.get("identifier"))
    if len(title) < 6 or not url:
        return None
    if CNKI_NON_ARTICLE_RE.search(title):
        return None
    year_raw = raw.get("year")
    if year_raw is None:
        date = _text(raw.get("date") or raw.get("publication_date"))
        match = re.search(r"(19|20)\d{2}", date)
        year_raw = match.group(0) if match else 0
    citations_raw = _text(raw.get("cited_by") if raw.get("cited_by") is not None else raw.get("citations"))
    downloads_raw = _text(raw.get("downloads"))
    abstract = _text(raw.get("abstract"))
    reprints = [
        _text(item)
        for item in (raw.get("reprints") or raw.get("non_citation_signals") or [])
        if _text(item)
    ]
    venue = _text(raw.get("venue") or raw.get("journal"))
    year = int(year_raw or 0)
    # CNKI detail URLs carry a session-bound token, so identity is the stable
    # journal/year/title triple; the URL is kept alongside for retrieval.
    identifier = f"cnki:{venue}:{year}:{title}"
    return {
        "record_id": record_id("cnki", identifier),
        "source": "cnki",
        "identifier": identifier,
        "url": url,
        "title": title,
        "venue": venue,
        "year": year,
        "cited_by": int(re.sub(r"\D", "", citations_raw) or 0),
        "downloads": int(re.sub(r"\D", "", downloads_raw) or 0) if downloads_raw else None,
        "abstract": abstract,
        "language": "zh",
        "reprints": reprints,
        "hot_term_hits": hot_term_hits(f"{title} {abstract}", hot_terms),
    }


# --------------------------------------------------------------------------- shortlist


def cohort_percentiles(records: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    """Rank-based percentile of cited_by within each (venue, year) cohort, ties averaged."""

    cohorts: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
    for record in records:
        cohorts.setdefault((_text(record.get("venue")), int(record.get("year") or 0)), []).append(record)
    result: dict[str, float] = {}
    for members in cohorts.values():
        ordered = sorted(members, key=lambda item: int(item.get("cited_by") or 0))
        size = len(ordered)
        index = 0
        while index < size:
            end = index
            while end + 1 < size and int(ordered[end + 1].get("cited_by") or 0) == int(ordered[index].get("cited_by") or 0):
                end += 1
            average_rank = (index + end) / 2 + 1
            percentile = 100.0 * (average_rank - 0.5) / size if size > 1 else 100.0
            for item in ordered[index : end + 1]:
                result[item["record_id"]] = round(percentile, 2)
            index = end + 1
    return result


def eligible(record: Mapping[str, Any], *, latest_year: int) -> tuple[bool, str]:
    if int(record.get("year") or 0) > latest_year:
        return False, "citation-window-too-short"
    return True, ""


def _round_robin(items: Sequence[dict[str, Any]], *, limit: int, per_journal: int) -> list[dict[str, Any]]:
    """Take items venue by venue in their given order until the limit is reached."""

    queues: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for item in items:
        venue = _text(item.get("venue"))
        if venue not in queues:
            queues[venue] = []
            order.append(venue)
        queues[venue].append(item)
    chosen: list[dict[str, Any]] = []
    taken: dict[str, int] = {venue: 0 for venue in order}
    while len(chosen) < limit:
        progressed = False
        for venue in order:
            if taken[venue] >= per_journal or taken[venue] >= len(queues[venue]):
                continue
            chosen.append(queues[venue][taken[venue]])
            taken[venue] += 1
            progressed = True
            if len(chosen) >= limit:
                break
        if not progressed:
            break
    return chosen


def build_shortlist(
    harvest: Mapping[str, Any],
    *,
    top: int = DEFAULT_TOP,
    bottom: int = DEFAULT_BOTTOM,
    per_journal: int = DEFAULT_PER_JOURNAL,
    min_cohort: int = MIN_COHORT,
    now_year: int | None = None,
) -> dict[str, Any]:
    raw_records = [dict(item) for item in harvest.get("records") or [] if isinstance(item, Mapping)]
    if not raw_records:
        raise ValueError("harvest has no records")
    latest_year = (now_year or datetime.now(timezone.utc).year) - CITATION_WINDOW_YEARS
    excluded: dict[str, int] = {}
    # Cohorts are formed from research articles only: book reviews and other
    # reference-poor items would otherwise crowd the bottom of every cohort and
    # hide the genuinely low-cited articles.
    records: list[dict[str, Any]] = []
    for record in raw_records:
        source = _text(record.get("source"))
        if source == "openalex" and int(record.get("referenced_works_count") or 0) < MIN_REFERENCES_OPENALEX:
            excluded["too-few-references"] = excluded.get("too-few-references", 0) + 1
            continue
        if source == "openalex" and len(_text(record.get("abstract"))) < MIN_ABSTRACT_CHARS["openalex"]:
            excluded["no-abstract"] = excluded.get("no-abstract", 0) + 1
            continue
        if source == "cnki" and _text(record.get("abstract")).startswith("<正>"):
            # CNKI shows the opening paragraph instead of an abstract for notes,
            # editorials, book blurbs and other non-research items.
            excluded["no-formal-abstract"] = excluded.get("no-formal-abstract", 0) + 1
            continue
        records.append(record)
    percentiles = cohort_percentiles(records)
    cohort_sizes: dict[tuple[str, int], int] = {}
    for record in records:
        key = (_text(record.get("venue")), int(record.get("year") or 0))
        cohort_sizes[key] = cohort_sizes.get(key, 0) + 1
    positives: list[dict[str, Any]] = []
    negatives: list[dict[str, Any]] = []
    middle: list[dict[str, Any]] = []
    for record in records:
        key = (_text(record.get("venue")), int(record.get("year") or 0))
        record["cohort_size"] = cohort_sizes[key]
        record["cohort_percentile"] = percentiles[record["record_id"]]
        ok, reason = eligible(record, latest_year=latest_year)
        if not ok:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        if cohort_sizes[key] < min_cohort:
            excluded["cohort-too-small"] = excluded.get("cohort-too-small", 0) + 1
            continue
        if record["cohort_percentile"] >= POSITIVE_PERCENTILE:
            positives.append(record)
        elif record["cohort_percentile"] <= NEGATIVE_PERCENTILE:
            negatives.append(record)
        else:
            middle.append(record)

    def fwci(item: Mapping[str, Any]) -> float:
        value = item.get("fwci")
        return float(value) if isinstance(value, (int, float)) else 0.0

    positives.sort(key=lambda item: (-item["cohort_percentile"], -fwci(item), -int(item.get("cited_by") or 0), item["record_id"]))
    # Round-robin across journals so large cohorts (whose top percentiles sit
    # closer to 100) cannot crowd out smaller journals or the other language.
    chosen_positive = _round_robin(positives, limit=top, per_journal=per_journal)
    if not any(not item.get("hot_term_hits") for item in chosen_positive):
        cold = next((item for item in positives if not item.get("hot_term_hits") and item not in chosen_positive), None)
        if cold is not None:
            if len(chosen_positive) >= top:
                chosen_positive.pop()
            chosen_positive.append(cold)
    positive_cohorts = {(_text(item.get("venue")), int(item.get("year") or 0)) for item in chosen_positive}
    negatives.sort(
        key=lambda item: (
            0 if (_text(item.get("venue")), int(item.get("year") or 0)) in positive_cohorts else 1,
            sha256_text(item["record_id"]),
        )
    )
    chosen_negative = _round_robin(negatives, limit=bottom, per_journal=per_journal)
    middle.sort(key=lambda item: sha256_text(item["record_id"]))
    chosen_middle = _round_robin(middle, limit=max(1, (top + bottom) // 4), per_journal=per_journal)
    for pool, role in ((chosen_positive, "positive"), (chosen_negative, "negative"), (chosen_middle, "middle")):
        for item in pool:
            item["role"] = role
            minimum = MIN_ABSTRACT_CHARS.get(_text(item.get("source")), 60)
            item["abstract_missing"] = len(_text(item.get("abstract"))) < minimum
    return {
        "schema_version": SHORTLIST_SCHEMA,
        "card_slug": _text(harvest.get("card_slug")),
        "harvested_at": _text(harvest.get("harvested_at")),
        "built_at": _utc_now_stamp(),
        "latest_eligible_year": latest_year,
        "rules": {
            "positive_percentile": POSITIVE_PERCENTILE,
            "negative_percentile": NEGATIVE_PERCENTILE,
            "min_cohort": min_cohort,
            "per_journal_cap": per_journal,
            "cold_topic_guarantee": True,
        },
        "excluded": excluded,
        "positive": chosen_positive,
        "negative": chosen_negative,
        "middle": chosen_middle,
    }


# --------------------------------------------------------------------------- selection prompt


def selection_schema(pick_positive: int, pick_negative: int) -> dict[str, Any]:
    pick = {
        "type": "object",
        "required": ["record_id", "why"],
        "properties": {"record_id": {"type": "string"}, "why": {"type": "string", "minLength": 20}},
        "additionalProperties": False,
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["positive", "negative", "uncertain", "rejected"],
        "properties": {
            "positive": {"type": "array", "minItems": 0, "maxItems": pick_positive, "items": pick},
            "negative": {"type": "array", "minItems": 0, "maxItems": pick_negative, "items": pick},
            "uncertain": {"type": "array", "items": pick},
            "rejected": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_id", "reason"],
                    "properties": {"record_id": {"type": "string"}, "reason": {"type": "string", "minLength": 8}},
                    "additionalProperties": False,
                },
            },
        },
        "additionalProperties": False,
    }


def _card_block(card: Mapping[str, Any]) -> str:
    names = card.get("names") if isinstance(card.get("names"), Mapping) else {}
    flavors = card.get("flavors") if isinstance(card.get("flavors"), Mapping) else {}
    lines = [f"分支：{names.get('zh', '')}（{card.get('slug', '')}）"]
    for flavor in taste_cards.FLAVORS:
        lines.append(f"- {taste_cards.FLAVOR_LABELS[flavor]}（{flavor}）：{flavors.get(flavor, '')}")
    smells = [_text(item) for item in card.get("mediocrity_smells") or [] if _text(item)]
    lines.append("- 精致的平庸气味：" + "；".join(smells))
    return "\n".join(lines)


SELECTION_PROTOCOL = "anonymous-mixed-pool/v2"


def anonymous_pool(shortlist: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Keep sampling strata in the audit input, outside the reader projection."""
    records = {}
    for role in ("positive", "negative", "middle"):
        for item in shortlist.get(role) or []:
            rid = _text(item.get("record_id"))
            if not rid or rid in records:
                raise ValueError("shortlist record identities must be nonempty and unique")
            records[rid] = dict(item)
    salt = sha256_text(taste_judge_canonical(sorted(
        (rid, _text(item.get("title")), _text(item.get("abstract")))
        for rid, item in records.items()
    )))
    ordered = sorted(records, key=lambda rid: sha256_text(salt + rid))
    return {f"ITEM-{index:03d}": records[rid] for index, rid in enumerate(ordered, 1)}


def selection_prompt(card: Mapping[str, Any], shortlist: Mapping[str, Any], *, pick_positive: int, pick_negative: int) -> str:
    pool = anonymous_pool(shortlist)
    entries = [f"### {key}\n标题：{item['title']}\n摘要：{_text(item.get('abstract'))}" for key, item in pool.items()]
    return (
        "你是隔离的学术品味读者，只根据匿名材料中可观察的内容判断。\n"
        f"从整个混合池选择至多 {pick_positive} 个正例和至多 {pick_negative} 个负例。两类均可为空；"
        "每个条目都可以进入任一类别，不按题材冷热或术语判断。\n"
        "材料不足、不能理解或无法判断实际论证厚度时，标为 uncertain。不要为了凑数制造负例。"
        "标题和摘要只支持初步判断，不能证明全文的证据和论证质量。\n"
        "positive、negative、uncertain 每项写 record_id 和 why；rejected 写 record_id 和 reason。"
        "逐项覆盖整个池，每项只出现一次，并指出支持判断的具体文字。不得补写事实或检索。\n"
        "匿名化不能保证模型不识别熟悉的内容，意见仍须校准。\n\n"
        + _card_block(card) + "\n\n协议：" + SELECTION_PROTOCOL + "\n\n## 匿名混合池\n\n" + "\n\n".join(entries)
    )


def taste_judge_canonical(card: Mapping[str, Any]) -> str:
    return json.dumps(card, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def selection_issues(payload: Any, shortlist: Mapping[str, Any], *, pick_positive: int, pick_negative: int) -> list[str]:
    if not isinstance(payload, Mapping):
        return ["selection response must be one JSON object"]
    issues: list[str] = []
    pool = anonymous_pool(shortlist)
    seen: set[str] = set()
    if set(payload) != {"positive", "negative", "uncertain", "rejected"}:
        issues.append("selection must contain positive, negative, uncertain and rejected only")
    for role in ("positive", "negative", "uncertain", "rejected"):
        picks = payload.get(role)
        if not isinstance(picks, list):
            issues.append(f"{role} must be a list")
            continue
        limit = {"positive": pick_positive, "negative": pick_negative}.get(role)
        if limit is not None and len(picks) > limit:
            issues.append(f"{role} exceeds the maximum of {limit} picks")
        for pick in picks:
            if not isinstance(pick, Mapping):
                issues.append(f"{role} entries must be objects")
                continue
            rid = _text(pick.get("record_id"))
            reason_key = "reason" if role == "rejected" else "why"
            if set(pick) != {"record_id", reason_key}:
                issues.append(f"{role} entry has unexpected fields")
            if rid not in pool:
                issues.append(f"{role} pick {rid or '?'} is not in the anonymous shortlist")
            if rid in seen:
                issues.append(f"record {rid} picked twice")
            seen.add(rid)
            if len(_text(pick.get(reason_key))) < (8 if role == "rejected" else 20):
                issues.append(f"{role} pick {rid} needs a substantive reason")
    if set(pool) - seen:
        issues.append("every anonymous item must receive a disposition, including uncertain")
    return issues


def exemplar_entry(record: Mapping[str, Any], why: str, *, capture: Mapping[str, Any], harvested_at: str) -> dict[str, Any]:
    return {
        "title": _text(record.get("title")),
        "venue": _text(record.get("venue")),
        "year": int(record.get("year") or 0),
        "identifier": _text(record.get("identifier")),
        "why": _text(why),
        "signals": {
            "source": _text(record.get("source")),
            "cited_by": int(record.get("cited_by") or 0),
            "cohort_size": int(record.get("cohort_size") or 0),
            "cohort_percentile": record.get("cohort_percentile"),
            "openalex_percentile_year": record.get("openalex_percentile_year"),
            "fwci": record.get("fwci"),
            "reprints": list(record.get("reprints") or []),
            "hot_term_hits": list(record.get("hot_term_hits") or []),
        },
        "selected_by": SELECTED_BY,
        "selection_protocol": SELECTION_PROTOCOL,
        "calibration_status": "unvalidated",
        "harvested_at": harvested_at,
        "selected_at": _utc_now_stamp(),
        "selection_run_id": _text(capture.get("run_id")),
        "selection_context_id": _text(capture.get("context_id")),
        "selection_model_revision": _text(capture.get("model_revision")),
    }


# --------------------------------------------------------------------------- status


def render_status(cards_to_show: Sequence[Mapping[str, Any]], *, now: datetime | None = None) -> str:
    lines = ["| card | registration | calibration | positive/negative | locked | age | action |", "|---|---|---|---|---|---|---|"]
    for card in cards_to_show:
        positive, negative = taste_cards.exemplar_counts(card)
        exemplars = card.get("exemplars") if isinstance(card.get("exemplars"), Mapping) else {}
        locked = sum(1 for role in ("positive", "negative") for item in exemplars.get(role) or [] if isinstance(item, Mapping) and item.get("locked"))
        age = taste_cards.exemplar_age_days(card, now=now)
        if age is None:
            age_text, action = "-", "harvest-openalex -> ingest-cnki -> shortlist -> emit-select -> collect-select"
        elif age > taste_cards.EXEMPLAR_MAX_AGE_DAYS:
            age_text, action = f"{age}d STALE", "refresh: rerun harvest-openalex (citations update in place) and the CNKI capture, then shortlist/select"
        else:
            age_text, action = f"{age}d", "fresh"
        lines.append(f"| {card.get('slug')} | {taste_cards.card_status(card)} | {taste_cards.exemplar_calibration_status(card)} | {positive}/{negative} | {locked} | {age_text} | {action} |")
    return "\n".join(lines)


# --------------------------------------------------------------------------- plan


def render_plan(registry: Mapping[str, Any], card: Mapping[str, Any], years: tuple[int, int]) -> str:
    signals = card.get("calibration_signals") if isinstance(card.get("calibration_signals"), Mapping) else {}
    cn = list(signals.get("cn_journals") or [])
    en = list(signals.get("en_journals") or [])
    lines = [
        f"# 范本采集计划：{card.get('slug')}（{years[0]}–{years[1]}）",
        "",
        "队列规则：同刊同年为一个队列；引用百分位 ≥90 进入高引采样层、≤25 进入低引采样层，另取中间样本；近两年论文引用窗口不足，不进候选；",
        f"每刊最多 {DEFAULT_PER_JOURNAL} 篇；保留不含热词的高引样本；三个采样层混合匿名，读者只看标题摘要，允许跨层判断和全部弃判。",
        "",
        "## 英文刊（OpenAlex，自动）",
    ]
    for name in en:
        lines.append(f"- {name}")
    lines.append("")
    lines.append(f"命令：$Python -X utf8 <cnki-paper-skill-dir>/scripts/taste_exemplars.py harvest-openalex {card.get('slug')} --years {years[0]}-{years[1]} --out <harvest.json>")
    lines.extend(["", "## 中文刊（知网，浏览器技能采集后 ingest-cnki）"])
    for name in cn:
        lines.append(f"- {name}：cnki-advanced-search 文献来源=“{name}”，逐年 {years[0]}–{years[1] - CITATION_WINDOW_YEARS}，排序=被引，cnki-parse-results 抓全部结果页（含末页低引条目）")
    lines.extend(
        [
            "",
            "导出格式：JSON 数组，每条 {title, url, journal, date|year, citations|cited_by, downloads?, abstract?, reprints?}；",
            "先只抓结果页，shortlist 后再用 cnki-paper-detail 为入选条目补摘要（abstract_missing=true 的条目）。",
            f"命令：$Python -X utf8 <cnki-paper-skill-dir>/scripts/taste_exemplars.py ingest-cnki {card.get('slug')} --records <export.json> --harvest <harvest.json>",
            "",
            "热词（命中只作标记，不剔除）：" + "、".join(taste_cards.hot_terms_for(registry, card)),
        ]
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- cli


def _load_card(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = taste_cards.load_registry(args.registry)
    problems = taste_cards.registry_issues(registry)
    if problems:
        raise ValueError("taste-card registry invalid: " + "; ".join(problems))
    card = taste_cards.card_by_slug(registry, args.slug)
    if card is None:
        raise ValueError(f"unknown taste card {args.slug}")
    return registry, card


def main(argv: Sequence[str] | None = None, *, fetch: Callable[[str], dict[str, Any]] = fetch_json) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--registry", type=Path, default=taste_cards.DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="print the harvest plan for one card")
    plan_parser.add_argument("slug")
    plan_parser.add_argument("--years", default=f"{DEFAULT_YEARS[0]}-{DEFAULT_YEARS[1]}")

    harvest_parser = subparsers.add_parser("harvest-openalex", help="harvest the card's English journals from OpenAlex")
    harvest_parser.add_argument("slug")
    harvest_parser.add_argument("--out", type=Path, required=True)
    harvest_parser.add_argument("--years", default=f"{DEFAULT_YEARS[0]}-{DEFAULT_YEARS[1]}")
    harvest_parser.add_argument("--mailto", default="")
    harvest_parser.add_argument("--journal", action="append", help="restrict to these journal names; repeatable")
    harvest_parser.add_argument("--source-id", action="append", default=[], metavar="NAME=S123", help="pin an OpenAlex source id for a journal name")
    harvest_parser.add_argument("--max-per-journal", type=int, default=1500)

    ingest_parser = subparsers.add_parser("ingest-cnki", help="merge CNKI browser-skill exports into a harvest file")
    ingest_parser.add_argument("slug")
    ingest_parser.add_argument("--records", type=Path, required=True)
    ingest_parser.add_argument("--harvest", type=Path, required=True)
    ingest_parser.add_argument("--years", default=f"{DEFAULT_YEARS[0]}-{DEFAULT_YEARS[1]}")
    ingest_parser.add_argument("--replace", action="store_true", help="drop previously ingested CNKI records before merging (re-harvest)")

    shortlist_parser = subparsers.add_parser("shortlist", help="rank cohorts and build the candidate shortlist")
    shortlist_parser.add_argument("slug")
    shortlist_parser.add_argument("--harvest", type=Path, required=True)
    shortlist_parser.add_argument("--out", type=Path, required=True)
    shortlist_parser.add_argument("--top", type=int, default=DEFAULT_TOP)
    shortlist_parser.add_argument("--bottom", type=int, default=DEFAULT_BOTTOM)
    shortlist_parser.add_argument("--per-journal", type=int, default=DEFAULT_PER_JOURNAL)
    shortlist_parser.add_argument("--min-cohort", type=int, default=MIN_COHORT)
    shortlist_parser.add_argument("--drop-missing", action="store_true", help="drop candidates whose abstract is still missing instead of flagging them")

    emit_parser = subparsers.add_parser("emit-select", help="write the isolated reading prompt for the shortlist")
    emit_parser.add_argument("slug")
    emit_parser.add_argument("--shortlist", type=Path, required=True)
    emit_parser.add_argument("--out", type=Path, required=True)
    emit_parser.add_argument("--model-revision", required=True)
    emit_parser.add_argument("--pick-positive", type=int, default=DEFAULT_PICK_POSITIVE)
    emit_parser.add_argument("--pick-negative", type=int, default=DEFAULT_PICK_NEGATIVE)

    status_parser = subparsers.add_parser("status", help="report exemplar freshness per card and what to rerun")
    status_parser.add_argument("slug", nargs="?", help="one card; omit for all cards")

    collect_parser = subparsers.add_parser("collect-select", help="verify the reading response and write exemplars into the card")
    collect_parser.add_argument("slug")
    collect_parser.add_argument("--shortlist", type=Path, required=True)
    collect_parser.add_argument("--responses", type=Path, required=True)
    collect_parser.add_argument("--model-revision", required=True)
    collect_parser.add_argument("--pick-positive", type=int, default=DEFAULT_PICK_POSITIVE)
    collect_parser.add_argument("--pick-negative", type=int, default=DEFAULT_PICK_NEGATIVE)
    collect_parser.add_argument("--write", action="store_true", help="replace the card's exemplars in the registry")

    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            registry = taste_cards.load_registry(args.registry)
            targets = [taste_cards.card_by_slug(registry, args.slug)] if args.slug else taste_cards.cards(registry)
            if args.slug and targets[0] is None:
                raise ValueError(f"unknown taste card {args.slug}")
            print(render_status(targets))
            return 0
        registry, card = _load_card(args)
        hot_terms = taste_cards.hot_terms_for(registry, card)
        if args.command == "plan":
            print(render_plan(registry, card, parse_years(args.years)), end="")
            return 0

        if args.command == "harvest-openalex":
            years = parse_years(args.years)
            signals = card.get("calibration_signals") if isinstance(card.get("calibration_signals"), Mapping) else {}
            names = [name for name in signals.get("en_journals") or [] if not args.journal or name in args.journal]
            if not names:
                raise ValueError("card lists no English journals to harvest")
            pinned: dict[str, str] = {}
            for item in args.source_id:
                name, _, source_id = item.partition("=")
                if not name or not source_id:
                    raise ValueError("--source-id must look like NAME=S123")
                pinned[name.strip()] = source_id.strip()
            harvest = _read_json(args.out) if args.out.is_file() else empty_harvest(card, years)
            if _text(harvest.get("card_slug")) != _text(card.get("slug")):
                raise ValueError("harvest file belongs to another card")
            for name in names:
                if name in pinned:
                    source = {"name": name, "display_name": name, "source_id": pinned[name], "issn_l": "", "works_count": 0}
                else:
                    source = resolve_openalex_source(name, mailto=args.mailto, fetch=fetch)
                if source is None:
                    print(f"unresolved journal (pin it with --source-id): {name}")
                    continue
                records = harvest_openalex_journal(
                    source,
                    years=years,
                    hot_terms=hot_terms,
                    mailto=args.mailto,
                    max_records=args.max_per_journal,
                    fetch=fetch,
                    pause=0.0 if fetch is not fetch_json else 0.2,
                )
                added = merge_records(harvest, records)
                harvest["journals"] = [item for item in harvest["journals"] if _text(item.get("name")) != name]
                harvest["journals"].append({**source, "records": len(records), "harvested_at": _utc_now_stamp()})
                print(f"{name}: {len(records)} records ({added} new)")
            harvest["harvested_at"] = _utc_now_stamp()
            _write_json(args.out, harvest)
            print(f"wrote {args.out} ({len(harvest['records'])} records)")
            return 0

        if args.command == "ingest-cnki":
            years = parse_years(args.years)
            raw = _read_json(args.records)
            if not isinstance(raw, list):
                raise ValueError("--records must contain one JSON array")
            harvest = _read_json(args.harvest) if args.harvest.is_file() else empty_harvest(card, years)
            if _text(harvest.get("card_slug")) != _text(card.get("slug")):
                raise ValueError("harvest file belongs to another card")
            records = [record for record in (cnki_record(item, hot_terms) for item in raw if isinstance(item, Mapping)) if record]
            records = [record for record in records if years[0] <= int(record.get("year") or 0) <= years[1]]
            if args.replace:
                before = len(harvest["records"])
                harvest["records"] = [item for item in harvest["records"] if _text(item.get("source")) != "cnki"]
                print(f"dropped {before - len(harvest['records'])} previously ingested CNKI records")
            added = merge_records(harvest, records)
            venues = sorted({record["venue"] for record in records if record["venue"]})
            for venue in venues:
                harvest["journals"] = [item for item in harvest["journals"] if _text(item.get("name")) != venue]
                harvest["journals"].append({"name": venue, "display_name": venue, "source_id": "cnki", "records": sum(1 for r in records if r["venue"] == venue), "harvested_at": _utc_now_stamp()})
            harvest["harvested_at"] = _utc_now_stamp()
            _write_json(args.harvest, harvest)
            print(f"ingested {len(records)} CNKI records ({added} new) into {args.harvest}")
            return 0

        if args.command == "shortlist":
            harvest = _read_json(args.harvest)
            if _text(harvest.get("card_slug")) != _text(card.get("slug")):
                raise ValueError("harvest file belongs to another card")
            shortlist = build_shortlist(
                harvest, top=args.top, bottom=args.bottom, per_journal=args.per_journal, min_cohort=args.min_cohort
            )
            if args.drop_missing:
                dropped = 0
                for pool in ("positive", "negative", "middle"):
                    kept = [item for item in shortlist.get(pool, []) if not item.get("abstract_missing")]
                    dropped += len(shortlist[pool]) - len(kept)
                    shortlist[pool] = kept
                shortlist["dropped_missing_abstract"] = dropped
            _write_json(args.out, shortlist)
            missing = [item for pool in ("positive", "negative", "middle") for item in shortlist.get(pool, []) if item.get("abstract_missing")]
            print(
                f"shortlist: {len(shortlist['positive'])} positive / {len(shortlist['negative'])} negative candidates; "
                f"excluded {shortlist['excluded']}"
            )
            if missing:
                print("abstract missing (fetch with cnki-paper-detail before emit-select):")
                for item in missing:
                    print(f"  - {item['record_id']}  {item['identifier']}")
            return 0

        if args.command in {"emit-select", "collect-select"}:
            shortlist = _read_json(args.shortlist)
            if _text(shortlist.get("card_slug")) != _text(card.get("slug")):
                raise ValueError("shortlist belongs to another card")
            if args.pick_positive < 0 or args.pick_negative < 0:
                raise ValueError("pick limits cannot be negative")
            if not anonymous_pool(shortlist):
                raise ValueError("shortlist has no anonymous candidates")
            missing = [item["record_id"] for pool in ("positive", "negative", "middle") for item in shortlist.get(pool, []) if item.get("abstract_missing")]
            if missing:
                raise ValueError("shortlist entries lack abstracts: " + ", ".join(missing))
            prompt = selection_prompt(card, shortlist, pick_positive=args.pick_positive, pick_negative=args.pick_negative)
            schema = selection_schema(args.pick_positive, args.pick_negative)
            if args.command == "emit-select":
                prompt_path = write_agent_capture_request(
                    args.out, step=f"taste-exemplars-{card['slug']}", prompt=prompt, output_schema=schema, model_revision=args.model_revision
                )
                print(f"prompt emitted: {prompt_path}")
                print("spawn one fresh subagent, save its raw JSON reply and real context id, then run collect-select")
                return 0
            capture = read_agent_capture(args.responses, prompt=prompt, model_revision=args.model_revision)
            payload = json.loads(capture.raw_output.decode("utf-8"))
            issues = selection_issues(payload, shortlist, pick_positive=args.pick_positive, pick_negative=args.pick_negative)
            if issues:
                raise ValueError("selection response invalid: " + "; ".join(issues))
            by_id = anonymous_pool(shortlist)
            capture_info = {"run_id": capture.run_id, "context_id": capture.context_id, "model_revision": capture.model_revision}
            harvested_at = _text(shortlist.get("harvested_at"))
            exemplars = {
                role: [exemplar_entry(by_id[_text(pick["record_id"])], _text(pick["why"]), capture=capture_info, harvested_at=harvested_at) for pick in payload[role]]
                for role in ("positive", "negative")
            }
            # User-locked entries survive every refresh: they are the standing keep/veto.
            current = card.get("exemplars") if isinstance(card.get("exemplars"), Mapping) else {}
            for role in ("positive", "negative"):
                locked = [dict(item) for item in current.get(role) or [] if isinstance(item, Mapping) and item.get("locked")]
                locked_ids = {_text(item.get("identifier")) for item in locked}
                exemplars[role] = locked + [item for item in exemplars[role] if _text(item.get("identifier")) not in locked_ids]
                if locked:
                    print(f"kept {len(locked)} locked {role} exemplar(s)")
            preview = {**card, "exemplars": exemplars}
            preview["exemplar_selection"] = {"protocol": SELECTION_PROTOCOL, "calibration_status": "unvalidated", "dispositions": payload, "anonymous_map": {key: item["record_id"] for key, item in by_id.items()}, "shortlist_sha256": sha256_text(taste_judge_canonical(shortlist)), "capture": capture_info}
            trial = json.loads(json.dumps(registry, ensure_ascii=False))
            trial["cards"] = [preview if _text(item.get("slug")) == card["slug"] else item for item in trial["cards"]]
            problems = taste_cards.registry_issues(trial)
            if problems:
                raise ValueError("resulting registry invalid: " + "; ".join(problems))
            if args.write:
                _write_json(args.registry, trial)
                print(f"wrote {len(exemplars['positive'])} positive / {len(exemplars['negative'])} negative exemplars into {args.registry} ({taste_cards.card_status(preview)})")
            else:
                print(json.dumps(exemplars, ensure_ascii=False, indent=2))
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FAIL\n- {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
