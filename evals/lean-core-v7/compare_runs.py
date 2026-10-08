"""Compare evidence-backed paired model runs without trading facts for cost."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from run_records import evidence_valid as _evidence_valid, load_json, number as _number, selection_issues, required_hard_checks


FACTUAL_CHECKS = (
    "no_fabricated_sources", "no_inference_strengthening",
    "negative_results_preserved", "authorization_respected",
)
EXTRA_COST_METRICS = ("wall_time_seconds", "unnecessary_user_interruptions")
CONDITIONS = ("model", "reasoning_effort", "material_snapshot_sha256", "task_prompt_sha256")


def compare(manifest: dict, baseline: dict, candidate: dict, baseline_root: Path, candidate_root: Path) -> dict:
    expected = {task["id"]: task for task in manifest["tasks"]}
    quality_metrics = manifest["quality_metrics"]
    cost_metrics = [*manifest["cost_metrics"], *EXTRA_COST_METRICS]
    report = {"schema_version": "avereth-paired-evaluation/v1", "status": "review_required", "issues": [], "pairs": []}
    runs = []
    for label, run, root in (("baseline", baseline, baseline_root), ("candidate", candidate, candidate_root)):
        report["issues"].extend(label + ": " + issue for issue in selection_issues(manifest, run))
        records = run.get("tasks") or []
        index = {item.get("id"): item for item in records if isinstance(item, dict)}
        runs.append(index)
        if len(index) != len(records) or set(index) != set(expected):
            report["issues"].append(f"{label}: exactly the frozen task IDs are required")
        if not run.get("code_revision") or not run.get("run_id"):
            report["issues"].append(f"{label}: code revision and actual run ID are required")
        for task_id, item in index.items():
            if task_id not in expected:
                continue
            if item.get("status") != "completed":
                report["issues"].append(f"{label}/{task_id}: model run is incomplete")
            for evidence_key in ("trace", "assessment", "materials"):
                if not _evidence_valid(item.get(evidence_key), root):
                    report["issues"].append(f"{label}/{task_id}: missing or changed {evidence_key} evidence")
            if item.get("material_snapshot_sha256") != (item.get("materials") or {}).get("sha256"):
                report["issues"].append(f"{label}/{task_id}: material snapshot is not bound to its evidence")
            for condition in CONDITIONS:
                if not item.get(condition):
                    report["issues"].append(f"{label}/{task_id}: missing {condition}")
            prompt_sha = hashlib.sha256(expected[task_id]["task"].encode("utf-8")).hexdigest()
            if item.get("task_prompt_sha256") != prompt_sha:
                report["issues"].append(f"{label}/{task_id}: frozen task prompt changed")
            for metric in quality_metrics:
                if not _number((item.get("quality") or {}).get(metric), quality=True):
                    report["issues"].append(f"{label}/{task_id}: unassessed quality metric {metric}")
            for metric in cost_metrics:
                if not _number((item.get("cost") or {}).get(metric)):
                    report["issues"].append(f"{label}/{task_id}: unmeasured cost metric {metric}")
            for check in required_hard_checks(expected[task_id], FACTUAL_CHECKS):
                verdict = (item.get("factual_checks") or {}).get(check)
                if verdict != "pass":
                    report["issues"].append(f"{label}/{task_id}: factual check {check} is {verdict or 'unknown'}")
    if report["issues"]:
        report["status"] = "incomplete_or_rejected"
        return report
    if baseline["run_id"] == candidate["run_id"] or baseline["code_revision"] == candidate["code_revision"]:
        report["issues"].append("two distinct runs and code revisions are required")
    for task_id in expected:
        left, right = runs[0][task_id], runs[1][task_id]
        for condition in CONDITIONS:
            if left[condition] != right[condition]:
                report["issues"].append(f"{task_id}: unmatched {condition}")
        if left["trace"]["sha256"] == right["trace"]["sha256"]:
            report["issues"].append(f"{task_id}: distinct raw model traces are required")
        quality_delta = {key: right["quality"][key] - left["quality"][key] for key in quality_metrics}
        report["pairs"].append({
            "id": task_id, "quality_delta": quality_delta,
            "cost_delta": {key: right["cost"][key] - left["cost"][key] for key in cost_metrics},
        })
    if report["issues"]:
        report["status"] = "not_comparable"
    elif any(value < 0 for pair in report["pairs"] for value in pair["quality_delta"].values()):
        report["status"] = "quality_regression"
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    args = parser.parse_args()
    manifest = load_json(args.manifest)
    from selection import validate_selection
    validate_selection(manifest, args.manifest.parent)
    result = compare(
        manifest, load_json(args.baseline), load_json(args.candidate),
        args.baseline.parent, args.candidate.parent,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["status"])
    return 0 if result["status"] == "review_required" else 1


if __name__ == "__main__":
    raise SystemExit(main())
