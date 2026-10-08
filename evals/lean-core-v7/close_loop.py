"""Bind capture, paired diagnostics and acceptance checks into one local report."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from compare_runs import FACTUAL_CHECKS, compare
from decision_policy import PROSE_INTEGRITY_CHECKS
from diagnose_runs import diagnose
from execute_run import inside, load_json, sha, write_new
from run_records import evidence_valid
from trajectory_report import summarize


def read_content(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        with zipfile.ZipFile(path) as archive:
            document = ElementTree.fromstring(archive.read("word/document.xml"))
        return "\n".join(node.text or "" for node in document.iter() if node.tag.endswith("}t"))
    if path.suffix.lower() not in {".json", ".md", ".txt", ".csv", ".tsv", ".xml", ".html"}:
        raise ValueError("unsupported text extraction; supply a bound text version for " + path.name)
    return path.read_text(encoding="utf-8-sig")


def task_content(row: dict, root: Path, kind: str) -> tuple[str, dict]:
    record = row.get(kind)
    if not evidence_valid(record, root):
        raise ValueError("missing or changed " + kind)
    path = root / record["path"]
    bindings = {record["path"]: record["sha256"]}
    text = read_content(path)
    try:
        payload = json.loads(text)
    except ValueError:
        return text, bindings
    if not isinstance(payload, dict):
        return text, bindings
    if kind == "output" and payload.get("schema_version") == "avereth-workflow-output/v1":
        entries, content_root = payload.get("artifacts", []), path.parent / "workspace"
        if not entries:
            raise ValueError("workflow output has no actual endpoint artifacts")
    elif kind == "materials" and payload.get("schema_version") == "avereth-material-snapshot/v1":
        entries, content_root = payload.get("files", []), path.parent / "workspace/materials"
        if not entries:
            raise ValueError("material snapshot has no actual sources")
    else:
        return text, bindings
    parts = []
    for entry in entries:
        relative = entry["destination"] if kind == "materials" else entry["path"]
        actual = inside(content_root, relative)
        if not actual.is_file() or sha(actual) != entry.get("sha256"):
            raise ValueError("changed bound " + kind + " attachment: " + relative)
        bindings[actual.relative_to(root.resolve()).as_posix()] = entry["sha256"]
        parts.append("Source " + relative + "\n" + read_content(actual))
    return "\n\n".join(parts), bindings


def prepare_pairs(manifest: dict, left: dict, right: dict, left_root: Path, right_root: Path, diagnostic: dict) -> list:
    indexes = [{row["id"]: row for row in run.get("tasks", [])} for run in (left, right)]
    pairs = []
    for task in manifest["tasks"]:
        pair = {"id": task["id"], "task": task["task"], "materials": "", "baseline": "", "candidate": "",
                "hard_failures": [], "baseline_hard_failures": [], "uncertainties": [], "costs": {}, "bindings": {},
                "writer_context_ids": [], "completion": {}, "hard_checks_complete": True, "prose_checks_complete": False}
        declared = task.get("hard_checks", [])
        if not isinstance(declared, list) or any(not isinstance(code, str) or not code for code in declared):
            pair["uncertainties"].append("selected case hard checks must be explicit nonempty string codes")
            declared = []
        required_checks = sorted(set(FACTUAL_CHECKS) | set(declared))
        pair["required_hard_checks"], pair["hard_check_results"] = required_checks, {}
        if not diagnostic["comparison_valid"]:
            pair["uncertainties"].append("paired execution evidence or conditions are not comparable")
        material_texts = []
        for label, index, root in zip(("baseline", "candidate"), indexes, (left_root.resolve(), right_root.resolve())):
            row = index.get(task["id"], {})
            status = row.get("status")
            requirements = [(row.get("responsibility_coverage") or {}).get(check) for check in task.get("outcome_checks", [])]
            pair["completion"][label] = (False if status in {"failed", "interrupted", "refused"} or "fail" in requirements else
                                          True if status == "completed" and all(item == "pass" for item in requirements) else None)
            pair["hard_check_results"][label] = {check: (row.get("factual_checks") or {}).get(check, "unknown") for check in required_checks}
            for check in required_checks:
                verdict = (row.get("factual_checks") or {}).get(check)
                if verdict == "fail":
                    if label == "candidate":
                        pair["hard_failures"].append(check)
                    else:
                        pair["baseline_hard_failures"].append(check)
                elif verdict != "pass":
                    pair["hard_checks_complete"] = False
            pair["costs"][label] = row.get("cost") or {}
            try:
                output_bindings = {}
                if status == "completed":
                    pair[label], output_bindings = task_content(row, root, "output")
                material, material_bindings = task_content(row, root, "materials")
                material_texts.append(material)
                pair["bindings"][label] = {**output_bindings, **material_bindings}
                for key in ("trace", "assessment"):
                    if evidence_valid(row.get(key), root):
                        pair["bindings"][label][row[key]["path"]] = row[key]["sha256"]
                if evidence_valid(row.get("trace"), root):
                    trace = load_json(root / row["trace"]["path"])
                    context_id = (trace.get("run_context") or {}).get("context_id")
                    if context_id:
                        pair["writer_context_ids"].append(context_id)
            except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
                pair["uncertainties"].append(label + ": " + str(exc))
        if len(material_texts) == 2 and material_texts[0] == material_texts[1]:
            pair["materials"] = material_texts[0]
        else:
            pair["uncertainties"].append("actual paired material content is missing or differs")
        pair["prose_checks_complete"] = (not pair["uncertainties"] and pair["hard_checks_complete"] and
                                          PROSE_INTEGRITY_CHECKS.issubset(required_checks) and
                                          all(pair["completion"].get(side) is True and
                                              all(pair["hard_check_results"][side].get(code) == "pass" for code in required_checks)
                                              for side in ("baseline", "candidate")))
        pairs.append(pair)
    return pairs


def close_loop(baseline: Path, candidate: Path, experiment: Path, manifest: Path, output: Path, *, judge_config: Path | None = None) -> dict:
    frozen, left, right, registered = load_json(manifest), load_json(baseline), load_json(candidate), load_json(experiment)
    diagnostic = diagnose(frozen, registered, left, right, baseline.parent, candidate.parent,
                          manifest_sha256=sha(manifest), experiment_sha256=sha(experiment))
    acceptance = compare(frozen, left, right, baseline.parent, candidate.parent)
    bindings = {"baseline_sha256": sha(baseline), "candidate_sha256": sha(candidate), "experiment_sha256": sha(experiment), "manifest_sha256": sha(manifest)}
    bindings.update({name: {"path": str(path.resolve()), "sha256": sha(path)} for name, path in
                     (("baseline", baseline), ("candidate", candidate), ("experiment", experiment), ("manifest", manifest))})
    bindings["selection_sha256"] = (frozen.get("selection") or {}).get("selection_sha256")
    from paired_eval import evaluate_pairs
    pairs = prepare_pairs(frozen, left, right, baseline.parent, candidate.parent, diagnostic)
    paired = evaluate_pairs(pairs, load_json(judge_config) if judge_config else {}, output.with_name(output.name + ".judges"),
                            input_bindings=bindings, target=registered.get("target"),
                            synthetic=registered.get("synthetic") is True)
    eligible = bool(paired.get("auto_promotion_eligible")) and paired.get("verdict") == "KEEP" and not paired.get("synthetic") and diagnostic["comparison_valid"]
    paired_path = output.with_name(output.name + ".judges") / "paired-result.json"
    paired_artifact = {"path": str(paired_path.resolve()), "sha256": sha(paired_path)} if paired_path.is_file() else None
    report = {"schema_version": "avereth-evaluation-loop/v1", "purpose": "diagnostic_only", "release_authorized": False,
              "status": paired.get("verdict", "UNCERTAIN"), "auto_promotion_eligible": eligible,
              "decision_basis": paired.get("decision_basis"), "quality_improvement_proven": False,
              "target_metric": paired.get("target_metric"), "hard_regressions": paired.get("hard_regressions", []),
              "cost_delta": paired.get("cost_delta", {}), "soft_diagnostics": paired.get("soft_diagnostics", {}),
              "inputs": bindings, "acceptance": acceptance, "diagnostic": diagnostic, "paired": paired, "paired_artifact": paired_artifact,
              "trajectory": {"baseline": summarize(frozen, left, baseline.parent), "candidate": summarize(frozen, right, candidate.parent)}}
    write_new(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--experiment", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).with_name("manifest.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-config", type=Path)
    args = parser.parse_args()
    result = close_loop(args.baseline, args.candidate, args.experiment, args.manifest, args.output,
                        judge_config=args.judge_config)
    print(result["status"] + "; scientific receipts remain controlled by the workflow")
    return 0 if result["auto_promotion_eligible"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
