"""Collect existing execution exports; do not run models or invent measurements."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from diagnose_runs import CONTEXT_FIELDS
from run_records import bind_file, load_json, selection_bindings


def capture(spec: dict, root: Path, experiment: Path):
    config = bind_file(root, spec["effective_config"])
    result = {"schema_version": "avereth-experiment-run/v1", "effective_config": config,
              "experiment_sha256": hashlib.sha256(experiment.read_bytes()).hexdigest(), "tasks": []}
    selected = spec.get("selection_bindings") or {}
    if selected:
        if not spec.get("manifest"):
            raise ValueError("selected capture needs the actual selected manifest")
        manifest_record = bind_file(root, spec["manifest"])
        from selection import validate_selection
        manifest_path = root / manifest_record["path"]
        manifest = load_json(manifest_path)
        validate_selection(manifest, manifest_path.parent)
        if selection_bindings(manifest) != selected:
            raise ValueError("capture selection differs from frozen selected manifest")
        if {item["id"] for item in spec["tasks"]} != {task["id"] for task in manifest["tasks"]} or len(spec["tasks"]) != len(manifest["tasks"]):
            raise ValueError("capture must retain exactly the selected denominator")
        result.update(selected)
    for item in spec["tasks"]:
        bindings = {key: bind_file(root, item[key]) for key in ("trace", "assessment", "materials")}
        if item.get("output"):
            bindings["output"] = bind_file(root, item["output"])
        trace = load_json(root / bindings["trace"]["path"])
        assessment = load_json(root / bindings["assessment"]["path"])
        context = trace["run_context"]
        if selected and any(context.get(key) != value for key, value in selected.items()):
            raise ValueError("task trace does not bind the selected experiment")
        for key in ("run_id", "code_revision"):
            if key in result and result[key] != context[key]:
                raise ValueError(f"task traces disagree about {key}")
            result[key] = context[key]
        if context.get("effective_config_sha256") != config["sha256"]:
            raise ValueError("trace does not bind the supplied effective configuration")
        row = {"id": item["id"], **bindings, **{key: context.get(key) for key in CONTEXT_FIELDS},
               "status": trace.get("status"), "failure_reason": trace.get("failure_reason"),
               "cost": trace.get("measurements") or {}}
        row.update(selected)
        for key in ("quality", "factual_checks", "diagnostics", "responsibility_coverage"):
            row[key] = assessment.get(key) or {}
        result["tasks"].append(row)
    if not result["tasks"]:
        raise ValueError("capture needs actual task traces")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve().parent != args.spec.resolve().parent:
        raise ValueError("output must share the run root with the capture specification")
    result = capture(load_json(args.spec), args.spec.parent, args.experiment)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Collected {len(result['tasks'])} existing traces; unmeasured costs remain unknown")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
