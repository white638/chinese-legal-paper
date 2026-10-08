#!/usr/bin/env python3
"""Optional manual/research 2x2 protocol for factor interaction analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

FACTORS = {"A": (False, False), "B": (False, True), "C": (True, False), "D": (True, True)}
METRICS = ("disciplinary_authenticity", "venue_fit", "generic_ai_phrase_density", "lexical_bundle_fit",
           "syntactic_distribution_distance", "citation_integration", "semantic_fidelity",
           "rare_single_source_overlap", "source_concentration", "target_corpus_similarity")
CONSTANTS = ("question_sha256", "evidence_sha256", "mir_sha256", "model_revision", "budget", "seed")


def bound_file(root: Path, binding: dict) -> Path:
    path = (root / binding["path"]).resolve()
    path.relative_to(root.resolve())
    if hashlib.sha256(path.read_bytes()).hexdigest() != binding["sha256"]:
        raise ValueError(f"artifact hash changed: {binding['path']}")
    return path


def validate_experiment(experiment: dict, root: Path) -> list[str]:
    issues = []
    try:
        if experiment.get("schema_version") != "avereth-commonplace-factorial/v1":
            raise ValueError("unsupported factorial experiment schema")
        if not isinstance(experiment.get("synthetic"), bool):
            raise ValueError("synthetic must explicitly identify development fixtures")
        cells = experiment["cells"]
        if set(cells) != set(FACTORS):
            raise ValueError("A/B/C/D cells are all required")
        baseline = cells["C"]
        output_hashes = set()
        for label, (deep, cp) in FACTORS.items():
            cell = cells[label]
            if cell.get("deep_reading") is not deep or cell.get("commonplace") is not cp:
                issues.append(f"{label}: factor assignment is wrong")
            for key in CONSTANTS:
                if key not in cell or cell[key] != baseline.get(key):
                    issues.append(f"{label}: matched condition differs or is absent: {key}")
            for key in ("question", "evidence", "mir"):
                binding = cell["inputs"][key]
                bound_file(root, binding)
                if binding["sha256"] != cell[key + "_sha256"]:
                    issues.append(f"{label}: {key} identity differs from the real input file")
            prompt = bound_file(root, cell["prompt"])
            output = bound_file(root, cell["output"])
            if not prompt.read_text(encoding="utf-8").strip() or not output.read_text(encoding="utf-8").strip():
                issues.append(f"{label}: prompt/output is empty")
            output_hashes.add(cell["output"]["sha256"])
            if not isinstance(cell.get("writer_context_id"), str) or not cell["writer_context_id"].strip():
                issues.append(f"{label}: actual writer context is required")
            if not isinstance(cell.get("model_revision"), str) or not cell["model_revision"].strip():
                issues.append(f"{label}: actual model revision is required")
            if not isinstance(cell.get("budget"), dict) or not cell["budget"]:
                issues.append(f"{label}: explicit matched budget is required")
            metrics = cell.get("metrics", {})
            if set(metrics) != set(METRICS) or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in metrics.values()):
                issues.append(f"{label}: all ten separate finite metrics are required")
            if metrics.get("semantic_fidelity") != 1:
                issues.append(f"{label}: semantic fidelity failed")
            for key in ("semantic_review", "borrowing_check"):
                assessment = json.loads(bound_file(root, cell[key]).read_text(encoding="utf-8"))
                if assessment.get("output_sha256") != cell["output"]["sha256"] or assessment.get("status") != "PASS":
                    issues.append(f"{label}: current {key} must PASS and bind actual output")
        if len({cell["writer_context_id"] for cell in cells.values()}) != 4:
            issues.append("each cell requires a distinct actual generation context")
        if len(output_hashes) < 2:
            issues.append("identical outputs cannot establish a writing contrast")
        blind = experiment.get("blind_review")
        if blind is None:
            return issues
        if set(blind["label_to_cell"].values()) != {"C", "D"} or len(blind["label_to_cell"]) != 2:
            issues.append("blind mapping must contain exactly C and D")
        review = json.loads(bound_file(root, blind["artifact"]).read_text(encoding="utf-8"))
        if review.get("preference") not in {*blind["label_to_cell"], "tie"}:
            issues.append("blind preference must use anonymous labels or tie")
        if (not review.get("reviewer_context_id") or review["reviewer_context_id"] in {c["writer_context_id"] for c in cells.values()}
                or review.get("input_scope") != "anonymous_C_D_outputs_only"
                or review.get("reviewer_kind") not in {"human", "human_domain_expert", "llm"}
                or not review.get("rationale")):
            issues.append("an optional blind review must identify its separate context, reviewer kind and rationale")
        if review.get("output_hashes") != {label: cells[cell]["output"]["sha256"] for label, cell in blind["label_to_cell"].items()}:
            issues.append("blind review does not bind current anonymous outputs")
    except (KeyError, ValueError, TypeError, OSError, AttributeError) as exc:
        issues.append(str(exc))
    return issues


def compare(experiment: dict, root: Path) -> dict:
    issues = validate_experiment(experiment, root)
    if issues:
        return {"status": "INCOMPLETE_OR_INVALID", "issues": issues, "default_promotion": False}
    cells = experiment["cells"]
    blind = experiment.get("blind_review")
    review = json.loads(bound_file(root, blind["artifact"]).read_text(encoding="utf-8")) if blind else None
    return {
        "status": "SYNTHETIC_CONTRACT_ONLY" if experiment["synthetic"] else "COMPARISON_READY_FOR_INTERPRETATION",
        "primary_contrast": "D minus C",
        "metric_deltas": {key: cells["D"]["metrics"][key] - cells["C"]["metrics"][key] for key in METRICS},
        "blind_preference": blind["label_to_cell"].get(review["preference"], "tie") if review else None,
        "default_promotion": False,
        "interpretation": "Manual factor analysis does not promote defaults. Use the automated paired evaluation for engineering decisions; human inspection is optional.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    result = compare(json.loads(args.experiment.read_text(encoding="utf-8")), args.experiment.resolve().parent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result["status"] == "INCOMPLETE_OR_INVALID" else 0)
