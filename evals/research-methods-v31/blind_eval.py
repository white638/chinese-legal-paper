#!/usr/bin/env python3
"""Package and score local, anonymized v3.0/v3.1 paired evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping


TASK_SCHEMA = "cnki-v31-hidden-tasks/v1"
OUTPUT_SCHEMA = "cnki-v31-generated-outputs/v1"
PACKAGE_SCHEMA = "cnki-v31-blind-package/v1"
DECODE_SCHEMA = "cnki-v31-blind-decode/v1"
REVIEW_SCHEMA = "cnki-v31-blind-review/v1"
SUMMARY_SCHEMA = "cnki-v31-blind-summary/v1"
DIMENSIONS = (
    "question_answer_match",
    "concept_boundary_clarity",
    "method_executability",
    "evidence_claim_traceability",
    "inference_calibration",
    "ethics_transparency_reproducibility",
    "researcher_usefulness",
)
PREFERENCES = {"A", "B", "tie"}
FORBIDDEN_REVIEW_METADATA = (
    "checker_seen",
    "golden_seen",
    "version_labels_seen",
    "other_reviews_seen",
)


class BlindEvalError(RuntimeError):
    """Raised when an evaluation artifact violates the blind protocol."""


def _load(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise BlindEvalError(f"file not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise BlindEvalError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise BlindEvalError(f"top-level JSON must be an object: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _digest(payload: Any) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _task_map(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    if payload.get("schema_version") != TASK_SCHEMA:
        raise BlindEvalError(f"tasks must use {TASK_SCHEMA}")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 20:
        raise BlindEvalError("the hidden task set must contain exactly 20 tasks")
    result: dict[str, Mapping[str, Any]] = {}
    for item in tasks:
        if not isinstance(item, Mapping):
            raise BlindEvalError("each task must be an object")
        task_id = str(item.get("id") or "").strip()
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]{2,31}", task_id) or task_id in result:
            raise BlindEvalError(f"invalid or duplicate task id: {task_id!r}")
        if not str(item.get("family") or "").strip() or not str(item.get("prompt") or "").strip():
            raise BlindEvalError(f"{task_id} is missing family or prompt")
        result[task_id] = item
    return result


def _output_map(
    payload: Mapping[str, Any],
    *,
    task_ids: set[str],
    label: str,
) -> dict[tuple[str, int], str]:
    if payload.get("schema_version") != OUTPUT_SCHEMA:
        raise BlindEvalError(f"{label} outputs must use {OUTPUT_SCHEMA}")
    records = payload.get("records")
    output_field = "output"
    if records is None:
        records = payload.get("outputs")
        output_field = "text"
    if not isinstance(records, list):
        raise BlindEvalError(
            f"{label} outputs must provide a records/output or outputs/text array"
        )
    result: dict[tuple[str, int], str] = {}
    for item in records:
        if not isinstance(item, Mapping):
            raise BlindEvalError(f"{label} record must be an object")
        task_id = str(item.get("task_id") or "").strip()
        repeat = item.get("repeat")
        output = str(item.get(output_field) or "").strip()
        key = (task_id, repeat) if isinstance(repeat, int) else (task_id, -1)
        if task_id not in task_ids or repeat not in {1, 2}:
            raise BlindEvalError(f"{label} has an unknown task/repeat: {task_id}/{repeat}")
        if key in result:
            raise BlindEvalError(f"{label} repeats a task/repeat: {task_id}/{repeat}")
        if len(output) < 200:
            raise BlindEvalError(f"{label} output {task_id}/{repeat} is too short for blind review")
        result[key] = output
    expected = {(task_id, repeat) for task_id in task_ids for repeat in (1, 2)}
    missing = sorted(expected - set(result))
    extra = sorted(set(result) - expected)
    if missing or extra:
        raise BlindEvalError(
            f"{label} must contain exactly two outputs per task; missing={missing}, extra={extra}"
        )
    return result


def pack(
    tasks_path: Path,
    baseline_path: Path,
    candidate_path: Path,
    package_path: Path,
    decode_path: Path,
    *,
    seed: int,
) -> Mapping[str, Any]:
    tasks_payload = _load(tasks_path)
    tasks = _task_map(tasks_payload)
    baseline_payload = _load(baseline_path)
    candidate_payload = _load(candidate_path)
    baseline = _output_map(baseline_payload, task_ids=set(tasks), label="baseline")
    candidate = _output_map(candidate_payload, task_ids=set(tasks), label="candidate")

    rng = random.Random(seed)
    keys = [(task_id, repeat) for task_id in sorted(tasks) for repeat in (1, 2)]
    rng.shuffle(keys)
    pairs: list[dict[str, Any]] = []
    decode_rows: list[dict[str, Any]] = []
    for number, (task_id, repeat) in enumerate(keys, start=1):
        pair_id = f"P{number:03d}"
        candidate_label = rng.choice(("A", "B"))
        baseline_label = "B" if candidate_label == "A" else "A"
        outputs = {
            candidate_label: candidate[(task_id, repeat)],
            baseline_label: baseline[(task_id, repeat)],
        }
        task = tasks[task_id]
        pairs.append(
            {
                "pair_id": pair_id,
                "task_id": task_id,
                "repeat": repeat,
                "family": task["family"],
                "task": task["prompt"],
                "outputs": {"A": outputs["A"], "B": outputs["B"]},
            }
        )
        decode_rows.append(
            {
                "pair_id": pair_id,
                "task_id": task_id,
                "repeat": repeat,
                "family": task["family"],
                "candidate_label": candidate_label,
                "baseline_label": baseline_label,
            }
        )

    public_package = {
        "schema_version": PACKAGE_SCHEMA,
        "protocol": {
            "pair_count": 40,
            "reviewer_count": 3,
            "dimensions": list(DIMENSIONS),
            "scores_per_output": True,
            "output_labels": ["A", "B"],
            "preference_values": sorted(PREFERENCES),
            "preference_aggregation": "plurality_non_tie",
            "minimum_located_findings": 3,
            "withheld": [
                "checker output",
                "golden answer",
                "framework version labels",
                "other reviewer results",
                "candidate-label decode",
            ],
        },
        "task_set_sha256": _digest(tasks_payload),
        "pairs": pairs,
    }
    decode = {
        "schema_version": DECODE_SCHEMA,
        "package_sha256": _digest(public_package),
        "seed": seed,
        "rows": decode_rows,
    }
    _write(package_path, public_package)
    _write(decode_path, decode)
    return {
        "package": str(package_path),
        "decode": str(decode_path),
        "pair_count": len(pairs),
        "package_sha256": decode["package_sha256"],
    }


def _review_entries(
    payload: Mapping[str, Any],
    *,
    pair_ids: set[str],
) -> tuple[str, dict[str, Mapping[str, Any]]]:
    if payload.get("schema_version") != REVIEW_SCHEMA:
        raise BlindEvalError(f"review must use {REVIEW_SCHEMA}")
    reviewer_id = str(payload.get("reviewer_id") or "").strip()
    if not reviewer_id:
        raise BlindEvalError("reviewer_id is required")
    isolation = payload.get("isolation_declaration")
    if not isinstance(isolation, Mapping):
        raise BlindEvalError(f"{reviewer_id}: isolation_declaration is required")
    contaminated = [field for field in FORBIDDEN_REVIEW_METADATA if isolation.get(field) is not False]
    if contaminated:
        raise BlindEvalError(
            f"{reviewer_id}: blind isolation was not affirmed for {', '.join(contaminated)}"
        )
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise BlindEvalError(f"{reviewer_id}: entries must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for item in entries:
        if not isinstance(item, Mapping):
            raise BlindEvalError(f"{reviewer_id}: every entry must be an object")
        pair_id = str(item.get("pair_id") or "").strip()
        if pair_id not in pair_ids or pair_id in result:
            raise BlindEvalError(f"{reviewer_id}: unknown or duplicate pair {pair_id!r}")
        preference = str(item.get("preference") or "").strip()
        if preference not in PREFERENCES:
            raise BlindEvalError(f"{reviewer_id}/{pair_id}: invalid preference")
        scores = item.get("scores")
        if not isinstance(scores, Mapping) or set(scores) != {"A", "B"}:
            raise BlindEvalError(
                f"{reviewer_id}/{pair_id}: scores for both anonymous outputs A and B are required"
            )
        for label in ("A", "B"):
            output_scores = scores[label]
            if not isinstance(output_scores, Mapping) or set(output_scores) != set(DIMENSIONS):
                raise BlindEvalError(
                    f"{reviewer_id}/{pair_id}/{label}: all seven scores are required"
                )
            if any(
                not isinstance(output_scores[name], int)
                or not 0 <= output_scores[name] <= 4
                for name in DIMENSIONS
            ):
                raise BlindEvalError(
                    f"{reviewer_id}/{pair_id}/{label}: scores must be integers from 0 to 4"
                )
        findings = item.get("findings")
        if not isinstance(findings, list) or len(findings) < 3:
            raise BlindEvalError(f"{reviewer_id}/{pair_id}: at least three findings are required")
        for finding in findings:
            if not isinstance(finding, Mapping):
                raise BlindEvalError(f"{reviewer_id}/{pair_id}: finding must be an object")
            if not str(finding.get("location") or "").strip() or not str(finding.get("text") or "").strip():
                raise BlindEvalError(f"{reviewer_id}/{pair_id}: each finding needs location and text")
        result[pair_id] = item
    if set(result) != pair_ids:
        missing = sorted(pair_ids - set(result))
        raise BlindEvalError(f"{reviewer_id}: missing pair entries {missing}")
    return reviewer_id, result


def score(
    package_path: Path,
    decode_path: Path,
    review_paths: list[Path],
) -> Mapping[str, Any]:
    package = _load(package_path)
    decode = _load(decode_path)
    if package.get("schema_version") != PACKAGE_SCHEMA:
        raise BlindEvalError(f"package must use {PACKAGE_SCHEMA}")
    if decode.get("schema_version") != DECODE_SCHEMA:
        raise BlindEvalError(f"decode must use {DECODE_SCHEMA}")
    if decode.get("package_sha256") != _digest(package):
        raise BlindEvalError("package content no longer matches the sealed decode")
    pairs = package.get("pairs")
    rows = decode.get("rows")
    if not isinstance(pairs, list) or len(pairs) != 40:
        raise BlindEvalError("package must contain exactly 40 pairs")
    if not isinstance(rows, list) or len(rows) != 40:
        raise BlindEvalError("decode must contain exactly 40 rows")
    pair_ids = {str(pair.get("pair_id") or "") for pair in pairs if isinstance(pair, Mapping)}
    if len(pair_ids) != 40:
        raise BlindEvalError("pair identifiers are missing or duplicated")
    decode_map = {
        str(row.get("pair_id") or ""): row
        for row in rows
        if isinstance(row, Mapping)
    }
    if set(decode_map) != pair_ids:
        raise BlindEvalError("decode rows do not match the public package")
    if len(review_paths) != 3:
        raise BlindEvalError("exactly three isolated review files are required")

    reviewers: dict[str, dict[str, Mapping[str, Any]]] = {}
    for path in review_paths:
        reviewer_id, entries = _review_entries(_load(path), pair_ids=pair_ids)
        if reviewer_id in reviewers:
            raise BlindEvalError(f"duplicate reviewer_id: {reviewer_id}")
        reviewers[reviewer_id] = entries

    outcomes: list[dict[str, Any]] = []
    overall = Counter()
    by_family: dict[str, Counter] = defaultdict(Counter)
    zero_score_events: list[dict[str, Any]] = []
    score_totals = {
        "candidate": Counter(),
        "baseline": Counter(),
    }
    score_counts = {
        "candidate": Counter(),
        "baseline": Counter(),
    }
    for pair_id in sorted(pair_ids):
        row = decode_map[pair_id]
        candidate_label = str(row.get("candidate_label") or "")
        baseline_label = str(row.get("baseline_label") or "")
        if {candidate_label, baseline_label} != {"A", "B"}:
            raise BlindEvalError(f"{pair_id}: invalid decode labels")
        for reviewer_id in sorted(reviewers):
            output_scores = reviewers[reviewer_id][pair_id]["scores"]
            for version, label in (
                ("candidate", candidate_label),
                ("baseline", baseline_label),
            ):
                for dimension in DIMENSIONS:
                    score_totals[version][dimension] += output_scores[label][dimension]
                    score_counts[version][dimension] += 1
            for dimension in ("question_answer_match", "inference_calibration"):
                if output_scores[candidate_label][dimension] == 0:
                    zero_score_events.append(
                        {
                            "reviewer_id": reviewer_id,
                            "pair_id": pair_id,
                            "candidate_label": candidate_label,
                            "dimension": dimension,
                        }
                    )
        votes = Counter(
            reviewers[reviewer_id][pair_id]["preference"]
            for reviewer_id in sorted(reviewers)
        )
        candidate_votes = votes[candidate_label]
        baseline_votes = votes[baseline_label]
        if candidate_votes > baseline_votes:
            outcome = "win"
        elif baseline_votes > candidate_votes:
            outcome = "loss"
        else:
            outcome = "tie"
        family = str(row.get("family") or "")
        overall[outcome] += 1
        by_family[family][outcome] += 1
        outcomes.append(
            {
                "pair_id": pair_id,
                "task_id": row.get("task_id"),
                "repeat": row.get("repeat"),
                "family": family,
                "candidate_label": candidate_label,
                "votes": dict(votes),
                "outcome": outcome,
            }
        )

    family_regressions = sorted(
        family
        for family, counts in by_family.items()
        if counts["loss"] > counts["win"]
    )
    checks = {
        "blind_wins_at_least_27": overall["win"] >= 27,
        "blind_losses_at_most_5": overall["loss"] <= 5,
        "no_family_net_regression": not family_regressions,
        "no_zero_question_or_inference_score": not zero_score_events,
        "three_isolated_complete_reviews": len(reviewers) == 3,
    }
    summary = {
        "schema_version": SUMMARY_SCHEMA,
        "package_sha256": _digest(package),
        "preference_aggregation": "plurality_non_tie",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "reviewers": sorted(reviewers),
        "counts": {
            "pairs": 40,
            "wins": overall["win"],
            "losses": overall["loss"],
            "ties": overall["tie"],
        },
        "checks": checks,
        "family_counts": {
            family: {
                "wins": counts["win"],
                "losses": counts["loss"],
                "ties": counts["tie"],
            }
            for family, counts in sorted(by_family.items())
        },
        "family_regressions": family_regressions,
        "zero_score_events": zero_score_events,
        "score_averages": {
            version: {
                dimension: round(
                    score_totals[version][dimension]
                    / score_counts[version][dimension],
                    3,
                )
                for dimension in DIMENSIONS
            }
            for version in ("candidate", "baseline")
        },
        "outcomes": outcomes,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    pack_parser = subparsers.add_parser("pack")
    pack_parser.add_argument("--tasks", type=Path, required=True)
    pack_parser.add_argument("--baseline", type=Path, required=True)
    pack_parser.add_argument("--candidate", type=Path, required=True)
    pack_parser.add_argument("--package", type=Path, required=True)
    pack_parser.add_argument("--decode", type=Path, required=True)
    pack_parser.add_argument("--seed", type=int, default=20260729)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--package", type=Path, required=True)
    score_parser.add_argument("--decode", type=Path, required=True)
    score_parser.add_argument("--review", type=Path, action="append", required=True)
    score_parser.add_argument("--out", type=Path)

    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            result = pack(
                args.tasks,
                args.baseline,
                args.candidate,
                args.package,
                args.decode,
                seed=args.seed,
            )
        else:
            result = score(args.package, args.decode, args.review)
            if args.out:
                _write(args.out, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except BlindEvalError as exc:
        print(f"blind-eval error: {exc}", file=sys.stderr)
        return 2
    return 0 if result.get("status", "PASS") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
