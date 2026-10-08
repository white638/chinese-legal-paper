"""Run selected paired workflows with a bounded, fully retained uncertainty repeat."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from execute_run import execute, preflight, sha, utc, write_new
from run_records import load_json, selection_bindings
from selection import digest, validate_selection, write_selection


def immutable_json(path: Path, payload: dict) -> None:
    if path.exists():
        if load_json(path) != payload:
            raise ValueError("existing experiment artifact differs: " + path.name)
    else:
        write_new(path, payload)


def revision(root: Path) -> str:
    result = subprocess.run(["git", "-c", "safe.directory=" + root.as_posix(), "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def run_pair(baseline_spec: Path, candidate_spec: Path, experiment: Path, bank: Path, output_root: Path, *,
             scope: str = "targeted", tags: list[str] | None = None, exclude_tags: list[str] | None = None,
             changed_paths: list[str] | None = None, max_cases: int | None = None, repeat_on_uncertain: int | None = None,
             baseline_code: Path | None = None, candidate_code: Path | None = None, baseline_ref: str | None = None,
             judge_config: Path | None = None, perform_execution: bool = False) -> dict:
    source_experiment = load_json(experiment)
    repeats = (source_experiment.get("execution") or {}).get("repeat_on_uncertain", 0) if repeat_on_uncertain is None else repeat_on_uncertain
    if not isinstance(repeats, int) or isinstance(repeats, bool) or not 0 <= repeats <= 2:
        raise ValueError("repeat_on_uncertain is limited to 0, 1 or 2 additional complete paired rounds")
    output_root = output_root.resolve()
    specifications = [baseline_spec.resolve(), candidate_spec.resolve()]
    code_roots = [path.resolve() if path else None for path in (baseline_code, candidate_code)]
    if baseline_ref and (not code_roots[0] or revision(code_roots[0]) != baseline_ref):
        raise ValueError("baseline_ref differs from the actual baseline checkout")
    bindings = {"baseline_spec_sha256": sha(specifications[0]), "candidate_spec_sha256": sha(specifications[1]),
                "source_experiment_sha256": sha(experiment), "bank_sha256": sha(bank),
                "judge_config_sha256": sha(judge_config) if judge_config else None,
                "options": {"scope": scope, "tags": tags or [], "exclude_tags": exclude_tags or [], "changed_paths": changed_paths or [],
                            "max_cases": max_cases, "repeat_on_uncertain": repeats, "code_roots": [str(path) if path else None for path in code_roots],
                            "code_revisions": [revision(path) if path else None for path in code_roots]}}
    output_root.mkdir(parents=True, exist_ok=True)
    immutable_json(output_root / "source-bindings.json", bindings)
    execution_key = digest(bindings)[:12]
    selected_path = output_root / "selected-manifest.json"
    if selected_path.exists():
        manifest = load_json(selected_path)
        validate_selection(manifest, selected_path.parent)
    else:
        manifest = write_selection(bank, selected_path, scope=scope, tags=tags, exclude_tags=exclude_tags,
                                   changed_paths=changed_paths, max_cases=max_cases)
    selection = selection_bindings(manifest)
    experiment_path = output_root / "experiment.json"
    if not experiment_path.exists():
        derived = {**source_experiment, "experiment_id": str(source_experiment.get("experiment_id", "paired")) + "-" + selection["selection_sha256"][:12],
                   "registered_at": utc(), "source_experiment_sha256": sha(experiment), "manifest_sha256": sha(selected_path), **selection,
                   "execution": {"repeat_on_uncertain": repeats}}
        write_new(experiment_path, derived)
    records, executed_rounds = [], 0
    for round_number in range(1, repeats + 2):
        round_root = output_root / f"round-{round_number:02d}"
        round_root.mkdir(exist_ok=True)
        loop_path = round_root / "paired-loop.json"
        if loop_path.exists():
            records.append({"path": str(loop_path), "sha256": sha(loop_path)})
            if load_json(loop_path).get("status") != "UNCERTAIN":
                break
            continue
        prepared = []
        for side, spec_path, code_root in zip(("baseline", "candidate"), specifications, code_roots):
            spec = load_json(spec_path)
            selected_ids = set(manifest["selection"]["selected_ids"])
            spec.update(side=side, run_id=f"{spec['run_id']}-{side}-{execution_key}-r{round_number:02d}", **selection)
            spec["tasks"] = [task for task in spec["tasks"] if task["id"] in selected_ids]
            if code_root:
                spec.update(code_root=str(code_root), code_revision=revision(code_root))
            prepared_path = spec_path.with_name(f"selected-{side}-{execution_key}-r{round_number:02d}.json")
            immutable_json(prepared_path, spec)
            prepared.append(prepared_path)
        checks = [preflight(path, experiment_path, selected_path) for path in prepared]
        immutable_json(round_root / "preflight.json", {"baseline": checks[0], "candidate": checks[1]})
        if any(check["status"] != "ready_for_execution" for check in checks) or not perform_execution:
            result = {"status": "UNCERTAIN" if executed_rounds or records else "NOT RUN", "reason": "preflight_only" if all(check["status"] == "ready_for_execution" for check in checks) else "preflight_blocked",
                      "selected_cases": len(manifest["tasks"]), "selection": selection, "model_calls": 0 if not executed_rounds else None, "rounds": records, "checks": checks,
                      "auto_promotion_eligible": False}
            immutable_json(output_root / ("not-run-execution.json" if perform_execution else "preflight-result.json"), result)
            return result
        outcomes = []
        for side, path in zip(("baseline", "candidate"), prepared):
            if any(row.get("operator_interrupted") for outcome in outcomes for row in outcome.get("records", [])):
                outcomes.append({"status": "interrupted", "records": [{"id": task["id"], "status": "interrupted", "failure_type": "not_started_after_operator_interruption"} for task in manifest["tasks"]]})
            else:
                outcomes.append(execute(path, experiment_path, selected_path, round_root / side))
        executed_rounds += 1
        if not all(outcome.get("captured_run") for outcome in outcomes):
            report = {"status": "UNCERTAIN", "verdict": "UNCERTAIN", "auto_promotion_eligible": False,
                      "reason": "incomplete paired capture", "outcomes": outcomes, "selection": selection}
            write_new(loop_path, report)
        else:
            from close_loop import close_loop
            close_loop(round_root / "baseline" / outcomes[0]["captured_run"], round_root / "candidate" / outcomes[1]["captured_run"],
                       experiment_path, selected_path, loop_path, judge_config=judge_config)
        records.append({"path": str(loop_path), "sha256": sha(loop_path)})
        if load_json(loop_path).get("status") != "UNCERTAIN" or any(row.get("operator_interrupted") for outcome in outcomes for row in outcome.get("records", [])):
            break
    from paired_eval import aggregate_repeats
    aggregate = aggregate_repeats(records, repeats + 1)
    aggregate["selected_cases"] = len(manifest["tasks"])
    aggregate["selection"] = selection
    immutable_json(output_root / "paired-result.json", aggregate)
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline_spec", type=Path)
    parser.add_argument("candidate_spec", type=Path)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--bank", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--scope", choices=("smoke", "targeted", "broader"), default="targeted")
    parser.add_argument("--tags", default="")
    parser.add_argument("--exclude-tags", default="")
    parser.add_argument("--changed-paths", type=Path)
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--repeat-on-uncertain", type=int)
    parser.add_argument("--baseline-code", type=Path)
    parser.add_argument("--candidate-code", type=Path)
    parser.add_argument("--baseline-ref")
    parser.add_argument("--judge-config", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    try:
        changed = json.loads(args.changed_paths.read_text(encoding="utf-8-sig")) if args.changed_paths else []
        result = run_pair(args.baseline_spec, args.candidate_spec, args.experiment, args.bank, args.output_root,
                          scope=args.scope, tags=[item.strip() for item in args.tags.split(",") if item.strip()],
                          exclude_tags=[item.strip() for item in args.exclude_tags.split(",") if item.strip()], changed_paths=changed,
                          max_cases=args.max_cases, repeat_on_uncertain=args.repeat_on_uncertain,
                          baseline_code=args.baseline_code, candidate_code=args.candidate_code, baseline_ref=args.baseline_ref,
                          judge_config=args.judge_config, perform_execution=args.execute)
        print(json.dumps({key: result.get(key) for key in ("status", "verdict", "selected_cases", "auto_promotion_eligible")}, ensure_ascii=False))
        return 0 if result.get("auto_promotion_eligible") else 2
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print("NOT RUN or interrupted before a complete report: " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
