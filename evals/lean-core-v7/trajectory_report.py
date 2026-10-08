"""Aggregate observed workflow events without assigning causal gate value."""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from run_records import evidence_valid, load_json, number


def summarize(manifest: dict, run: dict, root: Path) -> dict:
    required = {task["id"] for task in manifest["tasks"]}
    rows = {row["id"]: row for row in run.get("tasks", []) if row.get("id") in required}
    failures, phases, gates = Counter(), Counter(), defaultdict(Counter)
    reads, planned, issues = [], set(), []
    read_tasks, plan_tasks, gate_tasks = set(), set(), set()
    for task_id in sorted(required):
        row = rows.get(task_id, {})
        if row.get("status") != "completed":
            failures[row.get("failure_type") or row.get("status") or "not_started"] += 1
        if not evidence_valid(row.get("trace"), root):
            issues.append({"id": task_id, "issue": "trace_missing_or_changed"})
            continue
        trace = load_json(root / row["trace"]["path"])
        if trace.get("failure_type") and row.get("status") != "completed":
            failures[row.get("failure_type") or row.get("status") or "not_started"] -= 1
            failures[str(trace["failure_type"])] += 1
        for event in trace.get("events", []):
            if not isinstance(event, dict):
                continue
            kind = event.get("type")
            if kind == "phase.failure" and event.get("phase"):
                phases[str(event["phase"])] += 1
            if kind == "reference_plan" and isinstance(event.get("reference_requests"), list):
                plan_tasks.add(task_id)
                planned.update((task_id, row["path"]) for row in event["reference_requests"] if isinstance(row, dict) and isinstance(row.get("path"), str))
            if kind == "reference.plan" and isinstance(event.get("paths"), list):
                plan_tasks.add(task_id)
                planned.update((task_id, path) for path in event["paths"] if isinstance(path, str))
            if kind == "file.read" and isinstance(event.get("path"), str) and number(event.get("bytes_read")):
                read_tasks.add(task_id)
                reads.append((task_id, event["path"], event.get("sha256"), event["bytes_read"]))
            if kind in {"gate.executed", "audit.action"} and isinstance(event.get("gate"), str):
                gate_tasks.add(task_id)
                counter = gates[event["gate"]]
                counter["observed_calls"] += 1
                counter["status:exit_" + str(event.get("exit_code", "unknown")) + "_ungraded"] += 1
            if kind == "gate.result" and isinstance(event.get("gate_id"), str):
                gate_tasks.add(task_id)
                counter = gates[event["gate_id"]]
                counter["observed_calls"] += 1
                counter["status:" + str(event.get("status", "unknown"))] += 1
                # Defect IDs are observations; a reviewer decides whether they are true defects.
                ids = event.get("defect_ids")
                if isinstance(ids, list):
                    for defect in set(value for value in ids if isinstance(value, str)):
                        counter["defect:" + task_id + "/" + defect] += 1
    counts = Counter((task_id, path, sha) for task_id, path, sha, _ in reads if sha)
    actual = {(task_id, path) for task_id, path, _, _ in reads}
    defect_owners = defaultdict(set)
    for gate, counts_by_gate in gates.items():
        for key in counts_by_gate:
            if key.startswith("defect:"):
                defect_owners[key].add(gate)
    return {
        "schema_version": "avereth-trajectory-diagnostic/v1", "purpose": "diagnostic_only",
        "release_authorized": False, "required_tasks": len(required),
        "completed_tasks": sum(row.get("status") == "completed" for row in rows.values()),
        "failure_clusters": dict(sorted((key, value) for key, value in failures.items() if value)),
        "observed_failure_phases": dict(phases), "issues": issues,
        "reads": {"tasks_with_observations": len(read_tasks), "tasks_with_plans": len(plan_tasks),
                  "observed_bytes": sum(item[3] for item in reads) if reads else None,
                  "repeated_same_content_reads": sum(value - 1 for value in counts.values()) if counts else None,
                  "planned_but_unobserved": len(planned - actual) if plan_tasks and read_tasks >= plan_tasks else None,
                  "unplanned_observed": len({pair for pair in actual - planned if pair[0] in plan_tasks}) if plan_tasks else None},
        "gates": [{"gate_id": gate, "observed_calls": counter["observed_calls"],
                   "statuses": {key[7:]: value for key, value in counter.items() if key.startswith("status:")},
                   "reported_defects": sum(key.startswith("defect:") for key in counter),
                   "defects_reported_only_by_this_gate": sum(len(defect_owners[key]) == 1 for key in counter if key.startswith("defect:")),
                   "verified_marginal_quality_gain": None, "false_positive_rate": None}
                  for gate, counter in sorted(gates.items())],
        "gate_tasks_observed": len(gate_tasks),
        "interpretation": "Observed events support investigation. Missing event coverage is unknown; repeated reads and unique defect reports do not establish waste or justify deleting a gate.",
    }
