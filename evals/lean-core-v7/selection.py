"""Select and freeze a bounded experiment from a versioned capability bank."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_records import evidence_valid, load_json

SCHEMA = "avereth-eval-selection/v1"
METADATA = ("tags", "failure_mode", "risk", "hard_checks", "target_metrics", "lifecycle")
SCOPES = {"smoke": (1, 3, 2), "targeted": (3, 8, 6), "broader": (1, 10000, 10000)}
IMPACT_TAGS = {
    "reference": {"reference-loading", "context", "citation"},
    "prose": {"prose", "claim-evidence", "negative-result"},
    "writer": {"prose", "claim-evidence", "negative-result"},
    "commonplace": {"prose", "claim-evidence", "citation"},
    "citation": {"citation", "claim-evidence"},
    "topic": {"routing", "checkpoint", "method"},
    "config": {"routing", "checkpoint", "permissions"},
    "host": {"permissions", "context", "artifact"},
    "gate": {"artifact", "checkpoint", "claim-evidence"},
    "receipt": {"artifact", "checkpoint"},
    "manuscript": {"prose", "artifact", "claim-evidence"},
    "quant": {"quantitative", "method"},
    "research": {"method", "claim-evidence"},
    "novelty": {"novelty", "knowledge-change", "refutation"},
    "research_decision": {"novelty", "knowledge-change", "refutation", "checkpoint"},
}
INSTRUCTION_IMPACTS = {"routing", "context", "permissions", "checkpoint", "claim-evidence"}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_bank(bank: dict) -> None:
    tasks = bank.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("bank must contain task objects")
    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if len(ids) != len(tasks) or any(not isinstance(item, str) or not item for item in ids) or len(set(ids)) != len(ids):
        raise ValueError("bank task IDs must be nonempty and unique")
    if not isinstance(bank.get("bank_version"), int) or isinstance(bank.get("bank_version"), bool) or bank["bank_version"] < 1:
        raise ValueError("versioned selection requires a positive integer bank_version")
    for task in tasks:
        if not isinstance(task.get("task"), str) or not task["task"].strip():
            raise ValueError("task text is required")
        for key in ("tags", "hard_checks", "target_metrics"):
            values = task.get(key)
            if not isinstance(values, list) or not values or any(not isinstance(item, str) or not item for item in values) or len(set(values)) != len(values):
                raise ValueError(f"{task['id']}: {key} must be unique nonempty strings")
        if not task.get("failure_mode") or task.get("risk") not in {"low", "medium", "high"}:
            raise ValueError("case needs a failure mode and risk level")
        if (task.get("lifecycle") or {}).get("status") not in {"active", "archived", "infrequent"}:
            raise ValueError("case lifecycle must be active, infrequent or archived")


def select(bank: dict, bank_sha256: str, *, scope: str = "targeted", tags: list[str] | None = None,
           exclude_tags: list[str] | None = None, changed_paths: list[str] | None = None, max_cases: int | None = None) -> dict:
    validate_bank(bank)
    if scope not in SCOPES:
        raise ValueError("scope must be smoke, targeted or broader")
    minimum, maximum, default = SCOPES[scope]
    limit = default if max_cases is None else max_cases
    if not isinstance(limit, int) or isinstance(limit, bool) or not minimum <= limit <= maximum:
        raise ValueError(f"{scope} max_cases must be from {minimum} to {maximum}")
    tags, excluded, changed = sorted(set(tags or [])), sorted(set(exclude_tags or [])), sorted(set(changed_paths or []))
    if any(not isinstance(item, str) or not item for item in [*tags, *excluded, *changed]):
        raise ValueError("selection filters must be nonempty strings")
    impacted = set()
    for path in changed:
        normalized = path.replace("\\", "/").lower()
        if normalized in {"skills/cnki-paper/skill.source.md", "skills/cnki-paper/skill.md"} or normalized.startswith(("entrypoints/", "agent-specs/")):
            impacted.update(INSTRUCTION_IMPACTS)
        for token, values in IMPACT_TAGS.items():
            if token in path.lower():
                impacted.update(values)
    eligible = [task for task in bank["tasks"] if task["lifecycle"]["status"] != "archived"
                and (scope == "broader" or task["lifecycle"]["status"] == "active")
                and not set(task["tags"]) & set(excluded)
                and (not tags or set(task["tags"]) & set(tags))]
    if changed and not tags:
        eligible = [task for task in eligible if set(task["tags"]) & impacted]
    risk = {"high": 2, "medium": 1, "low": 0}
    eligible.sort(key=lambda task: (-len(set(task["tags"]) & (set(tags) | impacted)), -risk[task["risk"]], task["id"]))
    chosen = eligible[:limit]
    if len(chosen) < minimum:
        raise ValueError(f"NOT RUN: {scope} requires at least {minimum} matching cases; found {len(chosen)}")
    selection = {"schema_version": SCHEMA, "bank_sha256": bank_sha256, "bank_version": bank["bank_version"],
                 "scope": scope, "tags": tags, "exclude_tags": excluded, "changed_paths": changed,
                 "impacted_tags": sorted(impacted), "max_cases": limit, "selected_ids": [task["id"] for task in chosen],
                 "task_snapshots_sha256": digest(chosen)}
    selection["selection_sha256"] = digest(selection)
    return {**{key: value for key, value in bank.items() if key not in {"tasks", "selection", "source_bank"}},
            "tasks": chosen, "selection": selection}


def validate_selection(manifest: dict, root: Path | None = None) -> dict | None:
    selection = manifest.get("selection")
    if selection is None:
        return None
    if not isinstance(selection, dict) or selection.get("schema_version") != SCHEMA:
        raise ValueError("invalid selection identity")
    if selection.get("selection_sha256") != digest({key: value for key, value in selection.items() if key != "selection_sha256"}):
        raise ValueError("selection descriptor changed")
    if selection.get("selected_ids") != [task["id"] for task in manifest.get("tasks", [])] or selection.get("task_snapshots_sha256") != digest(manifest.get("tasks")):
        raise ValueError("selected task identity or snapshot changed")
    if root is not None:
        source = manifest.get("source_bank")
        if not evidence_valid(source, root) or source["sha256"] != selection["bank_sha256"]:
            raise ValueError("source bank snapshot is missing or changed")
        bank = load_json(root / source["path"])
        reproduced = select(bank, source["sha256"], scope=selection["scope"], tags=selection["tags"],
                            exclude_tags=selection["exclude_tags"], changed_paths=selection["changed_paths"], max_cases=selection["max_cases"])
        if reproduced["selection"] != selection or reproduced["tasks"] != manifest["tasks"]:
            raise ValueError("selection does not reproduce from its source bank")
    return selection


def write_selection(bank_path: Path, output: Path, **options) -> dict:
    manifest = select(load_json(bank_path), file_sha(bank_path), **options)
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = output.parent / ("bank-" + file_sha(bank_path) + ".json")
    if snapshot.exists():
        if file_sha(snapshot) != file_sha(bank_path):
            raise ValueError("existing bank snapshot differs")
    else:
        with snapshot.open("xb") as handle:
            handle.write(bank_path.read_bytes())
    manifest["source_bank"] = {"path": snapshot.name, "sha256": file_sha(snapshot)}
    with output.open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return manifest


def evolve(bank: dict, *, case: dict | None = None, archive_id: str | None = None, coverage: dict | None = None) -> dict:
    validate_bank(bank)
    result = json.loads(json.dumps(bank))
    if case is not None and archive_id is None:
        if case.get("id") in {task["id"] for task in bank["tasks"]}:
            raise ValueError("new case identity already exists")
        if (case.get("lifecycle") or {}).get("origin") == "observed_failure" and not case["lifecycle"].get("origin_evidence"):
            raise ValueError("observed failure cases need an original evidence reference")
        result["tasks"].append(case)
    elif archive_id and case is None:
        task = next((item for item in result["tasks"] if item["id"] == archive_id), None)
        if task is None:
            raise ValueError("archive case does not exist")
        if not coverage or not coverage.get("evidence") or not coverage.get("validator") or not coverage.get("reason") or not set(task["hard_checks"]) <= set(coverage.get("covers_hard_checks", [])):
            raise ValueError("archiving requires explicit deterministic coverage for every case hard check")
        task["lifecycle"] = {**task["lifecycle"], "status": "archived", "archive_coverage": coverage}
    else:
        raise ValueError("choose exactly one add or archive operation")
    result["bank_version"] += 1
    validate_bank(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bank", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scope", choices=SCOPES, default="targeted")
    parser.add_argument("--tags", default="")
    parser.add_argument("--exclude-tags", default="")
    parser.add_argument("--changed-paths", type=Path, help="JSON list of actual changed paths")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--add-case", type=Path)
    parser.add_argument("--archive-id")
    parser.add_argument("--coverage", type=Path)
    args = parser.parse_args()
    try:
        if args.add_case or args.archive_id:
            coverage = load_json(args.coverage) if args.coverage else None
            if coverage and not evidence_valid(coverage.get("evidence"), args.coverage.parent):
                raise ValueError("archive coverage must bind an actual deterministic validation record")
            case = load_json(args.add_case) if args.add_case else None
            if case and (case.get("lifecycle") or {}).get("origin") == "observed_failure" and not evidence_valid(case["lifecycle"].get("origin_evidence"), args.add_case.parent):
                raise ValueError("observed failure case must bind an actual original failure record")
            result = evolve(load_json(args.bank), case=case,
                            archive_id=args.archive_id, coverage=coverage)
            with args.output.open("x", encoding="utf-8") as handle:
                json.dump(result, handle, ensure_ascii=False, indent=2)
        else:
            changed = json.loads(args.changed_paths.read_text(encoding="utf-8-sig")) if args.changed_paths else []
            if not isinstance(changed, list):
                raise ValueError("changed paths must be a JSON list")
            result = write_selection(args.bank, args.output, scope=args.scope, tags=[s.strip() for s in args.tags.split(",") if s.strip()],
                                     exclude_tags=[s.strip() for s in args.exclude_tags.split(",") if s.strip()], changed_paths=changed, max_cases=args.max_cases)
        print(json.dumps({"status": "selected" if result.get("selection") else "bank_versioned", "cases": len(result["tasks"]), "bank_version": result["bank_version"]}))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("NOT RUN: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
