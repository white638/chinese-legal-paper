"""Describe paired experiments, including failures; never authorize a release.

Exit zero means only that a diagnostic report was written, even when its
comparison is invalid. This entry point cannot issue controller receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from compare_runs import CONDITIONS, EXTRA_COST_METRICS, FACTUAL_CHECKS
from run_records import evidence_valid, load_json, number, selection_bindings, selection_issues, required_hard_checks

CONTEXT_FIELDS = (*CONDITIONS, "host_version", "tool_versions", "prompt_version", "evaluation_mode")
DIAGNOSTICS = ("key_evidence_recall", "counterevidence_coverage", "claim_support_accuracy",
               "locator_accuracy", "protected_detail_fidelity")
TOKEN_COSTS = ("input_tokens", "output_tokens")
STATUSES = {"completed", "failed", "interrupted", "refused"}


def timestamp(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return parsed


def config_changes(left, right, prefix=""):
    if isinstance(left, dict) and isinstance(right, dict):
        result = set()
        for key in left.keys() | right.keys():
            path = prefix + "/" + key.replace("~", "~0").replace("/", "~1")
            result.update({path} if key not in left or key not in right else config_changes(left[key], right[key], path))
        return result
    return set() if type(left) is type(right) and left == right else {prefix or "/"}


def observed(value, *, quality=False, fraction=False):
    return value if number(value, quality=quality) and (not fraction or value <= 1) else None


def delta(left, right):
    return right - left if left is not None and right is not None else None


def diagnose(manifest: dict, experiment: dict, baseline: dict, candidate: dict,
             baseline_root: Path, candidate_root: Path, *, manifest_sha256: str,
             experiment_sha256: str):
    report = {"schema_version": "avereth-experiment-diagnostic/v1", "purpose": "diagnostic_only",
              "release_authorized": False, "receipt_issued": False, "comparison_valid": False,
              "issues": [], "pairs": [], "completion": {}, "unknown_measurements": []}
    issues = report["issues"]
    expected = {t["id"]: t for t in manifest["tasks"]}
    selected = selection_bindings(manifest)
    if selected:
        report.update(selected)
        if any(experiment.get(key) != value for key, value in selected.items()):
            issues.append("registered experiment does not bind the selected bank and task set")
    configs, indexes = [], []
    if experiment.get("schema_version") != "avereth-paired-experiment/v1" or not experiment.get("experiment_id"):
        issues.append("registered experiment identity is missing")
    if experiment.get("manifest_sha256") != manifest_sha256:
        issues.append("experiment does not bind the frozen task manifest")
    if experiment.get("evaluation_mode") not in {"offline_fixed_materials", "online_retrieval"}:
        issues.append("declare offline_fixed_materials or online_retrieval")
    try:
        registered = timestamp(experiment.get("registered_at"))
    except ValueError:
        registered = None
        issues.append("experiment registration time is invalid")
    for label, run, root in (("baseline", baseline, baseline_root), ("candidate", candidate, candidate_root)):
        issues.extend(label + ": " + issue for issue in selection_issues(manifest, run))
        if not run.get("run_id") or not run.get("code_revision"):
            issues.append(f"{label}: run ID and actual code revision are required")
        if run.get("experiment_sha256") != experiment_sha256:
            issues.append(f"{label}: experiment binding differs from the registered file")
        config = None
        if not evidence_valid(run.get("effective_config"), root):
            issues.append(f"{label}: effective configuration evidence is missing or changed")
        else:
            try:
                config = load_json(root / run["effective_config"]["path"])
            except (OSError, ValueError) as exc:
                issues.append(f"{label}: invalid configuration: {exc}")
            if run["effective_config"]["sha256"] != experiment.get(label + "_config_sha256"):
                issues.append(f"{label}: configuration was not registered")
        configs.append(config)
        records = run.get("tasks")
        records = records if isinstance(records, list) else []
        index = {r.get("id"): r for r in records if isinstance(r, dict) and isinstance(r.get("id"), str)}
        indexes.append(index)
        if len(index) != len(records) or set(index) != set(expected):
            issues.append(f"{label}: exactly the frozen task IDs are required; failures must remain present")
        report["completion"][label] = {"required": len(expected), **{s: sum(index.get(t, {}).get("status") == s for t in expected) for s in sorted(STATUSES)},
                                       "missing": len(set(expected) - set(index))}
        for task_id, task in expected.items():
            row = index.get(task_id, {})
            if row.get("status") not in STATUSES:
                issues.append(f"{label}/{task_id}: invalid or missing run status")
            keys = ["trace", "assessment", "materials"] + (["output"] if row.get("status") == "completed" else [])
            for key in keys:
                if not evidence_valid(row.get(key), root):
                    issues.append(f"{label}/{task_id}: missing or changed {key} evidence")
            if row.get("status") != "completed" and not row.get("failure_reason"):
                issues.append(f"{label}/{task_id}: failed/interrupted/refused runs need an explicit reason")
            if row.get("material_snapshot_sha256") != (row.get("materials") or {}).get("sha256"):
                issues.append(f"{label}/{task_id}: material snapshot binding differs")
            if row.get("task_prompt_sha256") != hashlib.sha256(task["task"].encode("utf-8")).hexdigest():
                issues.append(f"{label}/{task_id}: frozen task prompt changed")
            for key in CONTEXT_FIELDS:
                if not row.get(key):
                    issues.append(f"{label}/{task_id}: missing execution condition {key}")
            if row.get("evaluation_mode") != experiment.get("evaluation_mode"):
                issues.append(f"{label}/{task_id}: evaluation modes cannot be mixed")
            if evidence_valid(row.get("assessment"), root):
                try:
                    assessment = load_json(root / row["assessment"]["path"])
                    for key in ("quality", "factual_checks", "diagnostics", "responsibility_coverage"):
                        if (assessment.get(key) or {}) != (row.get(key) or {}):
                            issues.append(f"{label}/{task_id}: {key} differs from its assessment evidence")
                    if not assessment.get("evidence_notes"):
                        issues.append(f"{label}/{task_id}: assessment must retain original evidence and disagreements")
                    if assessment.get("trace_sha256") != (row.get("trace") or {}).get("sha256"):
                        issues.append(f"{label}/{task_id}: assessment does not bind the assessed trace")
                    if row.get("status") == "completed" and assessment.get("output_sha256") != (row.get("output") or {}).get("sha256"):
                        issues.append(f"{label}/{task_id}: assessment does not bind the assessed output")
                except (OSError, ValueError) as exc:
                    issues.append(f"{label}/{task_id}: invalid assessment: {exc}")
            if evidence_valid(row.get("trace"), root):
                try:
                    trace = load_json(root / row["trace"]["path"])
                    context = trace.get("run_context") or {}
                    if selected and any(context.get(key) != value or row.get(key) != value for key, value in selected.items()):
                        issues.append(f"{label}/{task_id}: selected task context differs")
                    if not trace.get("events"):
                        raise ValueError("raw trace events are missing")
                    if trace.get("status") != row.get("status") or trace.get("failure_reason") != row.get("failure_reason"):
                        issues.append(f"{label}/{task_id}: recorded outcome differs from the raw trace")
                    if (trace.get("measurements") or {}) != (row.get("cost") or {}):
                        issues.append(f"{label}/{task_id}: costs differ from recorded measurements")
                    if row.get("status") == "completed" and trace.get("output_sha256") != (row.get("output") or {}).get("sha256"):
                        issues.append(f"{label}/{task_id}: output differs from the execution trace")
                    for key in CONTEXT_FIELDS:
                        if context.get(key) != row.get(key):
                            issues.append(f"{label}/{task_id}: trace does not bind actual {key}")
                    for key in ("run_id", "code_revision"):
                        if context.get(key) != run.get(key):
                            issues.append(f"{label}/{task_id}: trace {key} differs")
                    if context.get("effective_config_sha256") != (run.get("effective_config") or {}).get("sha256"):
                        issues.append(f"{label}/{task_id}: trace does not bind effective configuration")
                    if registered is None or timestamp(context.get("started_at")) < registered:
                        issues.append(f"{label}/{task_id}: experiment was not registered before execution")
                except (OSError, ValueError, AttributeError) as exc:
                    issues.append(f"{label}/{task_id}: invalid execution trace: {exc}")
    allowed = experiment.get("allowed_config_changes")
    if not isinstance(allowed, list) or any(not isinstance(p, str) or not p.startswith("/") for p in allowed) or len(set(allowed)) != len(allowed):
        issues.append("allowed configuration changes must be unique JSON pointers")
    elif all(config is not None for config in configs):
        changed = config_changes(*configs)
        report["config_changes"] = sorted(changed)
        if changed != set(allowed):
            issues.append("actual configuration differences do not equal the registered variables")
        if baseline.get("code_revision") == candidate.get("code_revision") and not changed:
            issues.append("same-revision ablation requires a registered configuration difference")
    if baseline.get("run_id") == candidate.get("run_id"):
        issues.append("independent run IDs are required")
    for task_id, task in expected.items():
        left, right = indexes[0].get(task_id, {}), indexes[1].get(task_id, {})
        for key in CONTEXT_FIELDS:
            if left.get(key) != right.get(key):
                issues.append(f"{task_id}: unmatched execution condition {key}")
        if (left.get("trace") or {}).get("sha256") == (right.get("trace") or {}).get("sha256"):
            issues.append(f"{task_id}: distinct raw execution traces are required")
        pair = {"id": task_id, "status": [left.get("status", "missing"), right.get("status", "missing")],
                "failure_reasons": [left.get("failure_reason"), right.get("failure_reason")],
                "factual_checks": {}, "quality": {}, "cost": {}, "diagnostics": {}, "responsibility_coverage": []}
        for key in required_hard_checks(task, FACTUAL_CHECKS):
            a, b = [(row.get("factual_checks") or {}).get(key, "unknown") for row in (left, right)]
            change = "fixed" if (a, b) == ("fail", "pass") else "regressed" if (a, b) == ("pass", "fail") else "unchanged" if a == b and a in {"pass", "fail"} else "unknown"
            pair["factual_checks"][key] = {"baseline": a, "candidate": b, "change": change}
        for group, metrics in (("quality", manifest["quality_metrics"]),
                               ("cost", [*manifest["cost_metrics"], *EXTRA_COST_METRICS, *TOKEN_COSTS]),
                               ("diagnostics", DIAGNOSTICS)):
            for metric in metrics:
                a, b = [observed((row.get(group) or {}).get(metric), quality=group == "quality", fraction=group == "diagnostics") for row in (left, right)]
                pair[group][metric] = {"baseline": a, "candidate": b, "delta": delta(a, b)}
                if a is None or b is None:
                    report["unknown_measurements"].append(f"{task_id}/{group}/{metric}")
        requirements = task.get("outcome_checks", [])
        for row in (left, right):
            coverage = row.get("responsibility_coverage") or {}
            values = [coverage.get(requirement, "unknown") for requirement in requirements]
            pair["responsibility_coverage"].append({"required": len(requirements), "satisfied": values.count("pass"),
                                                     "failed": values.count("fail"), "unknown": sum(v not in {"pass", "fail"} for v in values)})
        report["pairs"].append(pair)
    report["comparison_valid"] = not issues
    if issues:
        # Observations remain visible, but untrusted pairs cannot imply a gain.
        for pair in report["pairs"]:
            for group in ("quality", "cost", "diagnostics"):
                for metric in pair[group].values():
                    metric["delta"] = None
            for check in pair["factual_checks"].values():
                check["change"] = "not_comparable"
    report["status"] = "diagnostic_ready" if not issues else "not_comparable"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from selection import validate_selection
    validate_selection(load_json(args.manifest), args.manifest.parent)
    result = diagnose(load_json(args.manifest), load_json(args.experiment), load_json(args.baseline), load_json(args.candidate),
                      args.baseline.parent, args.candidate.parent,
                      manifest_sha256=hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
                      experiment_sha256=hashlib.sha256(args.experiment.read_bytes()).hexdigest())
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Report written: {result['status']} (diagnostic only; no release authorization)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
