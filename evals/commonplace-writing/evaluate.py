#!/usr/bin/env python3
"""Evaluate frozen production C versus candidate D writing tasks automatically."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

from factorial import CONSTANTS, METRICS, bound_file

SCHEMA = "avereth-commonplace-paired/v1"
COSTS = ("input_tokens", "output_tokens", "tool_calls", "files_read", "wall_time_seconds", "retries")
PROSE_CHECKS = {"claims_supported", "protected_facts_preserved", "citation_metadata_valid", "task_completion"}


def _text(root: Path, binding: dict) -> str:
    value = bound_file(root, binding).read_text(encoding="utf-8")
    if not value.strip():
        raise ValueError(f"empty artifact: {binding['path']}")
    return value


def _measurement(value):
    return value if (not isinstance(value, bool) and isinstance(value, (int, float))
                     and math.isfinite(value) and value >= 0) else None


def _cell(root: Path, cell: dict, *, label: str) -> dict:
    if cell.get("deep_reading") is not True or cell.get("commonplace") is not (label == "D"):
        raise ValueError(f"{label}: paired comparison requires deep reading ON and Commonplace {'ON' if label == 'D' else 'OFF'}")
    context = cell.get("writer_context_id")
    if not isinstance(context, str) or not context.strip():
        raise ValueError(f"{label}: actual writer context is required")
    if not isinstance(cell.get("model_revision"), str) or not cell["model_revision"].strip():
        raise ValueError(f"{label}: actual model revision is required")
    if not isinstance(cell.get("budget"), dict) or not cell["budget"]:
        raise ValueError(f"{label}: explicit matched budget is required")
    inputs = {}
    for key in ("question", "evidence", "mir"):
        binding = cell["inputs"][key]
        inputs[key] = _text(root, binding)
        if binding["sha256"] != cell.get(key + "_sha256"):
            raise ValueError(f"{label}: {key} does not bind its real input")
    _text(root, cell["prompt"])
    output = _text(root, cell["output"])
    failures, uncertainties = [], []
    assessments = {key: cell[key] for key in ("semantic_review", "borrowing_check")}
    extra = cell.get("hard_checks", {})
    if not isinstance(extra, dict) or set(extra) & (set(assessments) | {"semantic_fidelity"}):
        raise ValueError(f"{label}: additional hard checks must have unique names")
    assessments.update(extra)
    statuses = {}
    for key, binding in assessments.items():
        assessment = json.loads(_text(root, binding))
        if assessment.get("output_sha256") != cell["output"]["sha256"]:
            raise ValueError(f"{label}: {key} does not bind current output")
        status = assessment.get("status")
        statuses[key] = status
        if status == "FAIL":
            failures.append("semantic_fidelity" if key == "semantic_review" else key)
    costs = dict.fromkeys(COSTS)
    if cell.get("trace") is not None:
        trace = json.loads(_text(root, cell["trace"]))
        if trace.get("output_sha256") != cell["output"]["sha256"]:
            raise ValueError(f"{label}: trace does not bind current output")
        measurements = trace.get("measurements", {})
        if not isinstance(measurements, dict):
            raise ValueError(f"{label}: trace measurements must be an object")
        costs = {key: _measurement(measurements.get(key)) for key in COSTS}
    metrics = cell.get("metrics", {})
    if not isinstance(metrics, dict):
        raise ValueError(f"{label}: optional metrics must be an object")
    return {"text": output, "inputs": inputs, "failures": failures, "uncertainties": uncertainties,
            "hard_checks_complete": PROSE_CHECKS.issubset(statuses) and all(value in {"PASS", "FAIL"} for value in statuses.values()),
            "hard_check_results": {"semantic_fidelity" if key == "semantic_review" else key: {"PASS": "pass", "FAIL": "fail"}.get(value, "unknown") for key, value in statuses.items()},
            "prose_checks_complete": PROSE_CHECKS.issubset(statuses) and all(value == "PASS" for value in statuses.values()),
            "completion": {"PASS": True, "FAIL": False}.get(statuses.get("task_completion")),
            "costs": costs, "metrics": {key: _measurement(metrics.get(key)) for key in METRICS},
            "bindings": {"inputs": cell["inputs"], "prompt": cell["prompt"], "output": cell["output"],
                         "assessments": assessments, "trace": cell.get("trace")}}


def prepare_pairs(experiment: dict, root: Path) -> tuple[list[dict], list[str]]:
    """Check trusted material and condition bindings before spending judge calls."""
    pairs, issues = [], []
    if not isinstance(experiment, dict) or experiment.get("schema_version") != SCHEMA:
        return [], ["unsupported paired experiment schema; factorial files require --manual-research"]
    synthetic = experiment.get("synthetic")
    if not isinstance(synthetic, bool):
        issues.append("synthetic must explicitly identify development fixtures")
    tasks = experiment.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return [], issues + ["tasks must be a nonempty frozen list"]
    if len(tasks) > 10 or (synthetic is False and len(tasks) < 5):
        issues.append("production comparisons require 5 to 10 frozen tasks; synthetic contracts allow 1 to 10")
    target = experiment.get("target")
    if target is not None and (not isinstance(target, dict) or target.get("category") != "prose"):
        issues.append("Commonplace comparisons require an explicit prose target")
    if isinstance(target, dict) and synthetic is False and (not isinstance(target.get("min_pairs"), int) or target["min_pairs"] < 5):
        issues.append("real Commonplace prose targets require min_pairs of at least 5")
    seen_ids, contexts = set(), set()
    for index, task in enumerate(tasks):
        try:
            task_id = task["id"]
            if not isinstance(task_id, str) or not task_id.strip() or task_id in seen_ids:
                raise ValueError("task IDs must be nonempty and unique")
            seen_ids.add(task_id)
            if not isinstance(task.get("task"), str) or not task["task"].strip():
                raise ValueError("actual frozen task instruction is required")
            cells = task["cells"]
            if set(cells) != {"C", "D"}:
                raise ValueError("paired tasks require exactly C and D")
            for key in CONSTANTS:
                if key not in cells["C"] or key not in cells["D"] or cells["C"][key] != cells["D"][key]:
                    raise ValueError(f"unmatched or absent condition: {key}")
            baseline, candidate = (_cell(root, cells[label], label=label) for label in ("C", "D"))
            current_contexts = [cells[label]["writer_context_id"] for label in ("C", "D")]
            if len(set(current_contexts)) != 2 or contexts.intersection(current_contexts):
                raise ValueError("each generation requires a distinct actual writer context")
            contexts.update(current_contexts)
            pairs.append({"id": task_id, "task": task["task"],
                          "materials": "\n\n".join(f"{key.upper()}\n{value}" for key, value in baseline["inputs"].items()),
                          "baseline": baseline["text"], "candidate": candidate["text"],
                          "hard_failures": candidate["failures"], "baseline_hard_failures": baseline["failures"],
                          "uncertainties": baseline["uncertainties"] + candidate["uncertainties"],
                          "completion": {"baseline": baseline["completion"], "candidate": candidate["completion"]},
                          "hard_checks_complete": baseline["hard_checks_complete"] and candidate["hard_checks_complete"],
                          "required_hard_checks": sorted(PROSE_CHECKS | {"semantic_fidelity", "borrowing_check"}),
                          "hard_check_results": {"baseline": baseline["hard_check_results"], "candidate": candidate["hard_check_results"]},
                          "prose_checks_complete": baseline["prose_checks_complete"] and candidate["prose_checks_complete"],
                          "costs": {"baseline": baseline["costs"], "candidate": candidate["costs"]},
                          "metrics": {"baseline": baseline["metrics"], "candidate": candidate["metrics"]},
                          "bindings": {"baseline": baseline["bindings"], "candidate": candidate["bindings"],
                                       "matched_conditions": {key: cells["C"][key] for key in CONSTANTS},
                                       "task_sha256": hashlib.sha256(task["task"].encode("utf-8")).hexdigest()},
                          "writer_context_ids": current_contexts})
        except (KeyError, TypeError, ValueError, OSError, AttributeError) as exc:
            issues.append(f"task[{index}]: {exc}")
    return pairs, issues


def compare(experiment: dict, root: Path, output_root: Path, *, judge_config: dict | None = None,
            input_bindings: dict | None = None, judge=None, evaluator=None) -> dict:
    pairs, issues = prepare_pairs(experiment, root)
    if issues:
        return {"schema_version": "avereth-automated-paired-eval/v1", "status": "INCOMPLETE_OR_INVALID",
                "verdict": "UNCERTAIN", "issues": issues, "auto_promotion_eligible": False,
                "decision_basis": None, "quality_improvement_proven": False, "hard_regressions": [],
                "target_metric": None, "cost_delta": {}, "soft_diagnostics": {},
                "synthetic": experiment.get("synthetic") if isinstance(experiment, dict) else None,
                "task_count": len(experiment.get("tasks", [])) if isinstance(experiment, dict) and isinstance(experiment.get("tasks"), list) else 0}
    if evaluator is None:
        lean = str(Path(__file__).resolve().parents[1] / "lean-core-v7")
        if lean not in sys.path:
            sys.path.insert(0, lean)
        from paired_eval import evaluate_pairs
        evaluator = evaluate_pairs
    bindings = dict(input_bindings or {})
    if bindings:
        artifacts = {pair["id"]: pair["bindings"] for pair in pairs}
        bindings["validated_artifacts"] = artifacts
        bindings["validated_artifacts_sha256"] = hashlib.sha256(
            json.dumps(artifacts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    result = evaluator(pairs, judge_config if judge_config is not None else experiment.get("judge_config", {}), output_root,
                       synthetic=experiment["synthetic"], input_bindings=bindings or None, judge=judge, target=experiment.get("target"))
    result["commonplace_comparison"] = {"primary_contrast": "candidate D versus production C",
                                      "tasks": [pair["id"] for pair in pairs], "human_review": "optional",
                                      "manual_factorial": False,
                                      "metrics": {pair["id"]: pair["metrics"] for pair in pairs}}
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--output", type=Path, help="Report path; judge requests and responses are retained alongside it")
    parser.add_argument("--judge-config", type=Path, help="Primary/secondary automatic judge configuration")
    parser.add_argument("--manual-research", action="store_true", help="Optional A/B/C/D factor interaction protocol")
    args = parser.parse_args(argv)
    path = args.experiment.resolve()
    try:
        raw = path.read_bytes()
        experiment = json.loads(raw.decode("utf-8"))
        destination = (args.output or path.with_name(path.stem + "-evaluation.json")).resolve()
        if destination == path or (args.judge_config and destination == args.judge_config.resolve()):
            raise ValueError("report path must not overwrite experiment or judge configuration")
        if destination.exists():
            raise ValueError("report path already exists; use a new path to preserve recorded artifacts")
        if args.manual_research:
            from factorial import compare as compare_factorial
            result = compare_factorial(experiment, path.parent)
        else:
            config = json.loads(args.judge_config.read_text(encoding="utf-8")) if args.judge_config else None
            bindings = {"experiment": {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}}
            if args.judge_config:
                bindings["judge_config"] = {"path": str(args.judge_config.resolve()),
                                             "sha256": hashlib.sha256(args.judge_config.read_bytes()).hexdigest()}
            result = compare(experiment, path.parent, destination.with_name(destination.name + ".artifacts"), judge_config=config,
                             input_bindings=bindings)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.manual_research:
            return 1 if result.get("status") == "INCOMPLETE_OR_INVALID" else 0
        return {"KEEP": 0, "REJECT": 1, "UNCERTAIN": 2}.get(result.get("verdict"), 2)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print(json.dumps({"status": "INCOMPLETE_OR_INVALID", "verdict": "UNCERTAIN",
                          "auto_promotion_eligible": False, "issues": [str(exc)]}, ensure_ascii=False))
        return 1 if args.manual_research else 2


if __name__ == "__main__":
    raise SystemExit(main())
