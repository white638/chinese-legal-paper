"""Decide registered engineering targets without claiming overall paper quality."""
from __future__ import annotations

import math

CATEGORIES = {"integrity": "integrity_gain", "reliability": "reliability_gain",
              "efficiency": "efficiency_gain", "prose": "prose_gain"}
PROSE_INTEGRITY_CHECKS = frozenset({"claims_supported", "protected_facts_preserved", "citation_metadata_valid", "semantic_fidelity"})


def positive(value, *, fraction=False):
    return (not isinstance(value, bool) and isinstance(value, (int, float))
            and math.isfinite(value) and value > 0 and (not fraction or value <= 1))


def target_issues(target):
    if not isinstance(target, dict) or target.get("category") not in CATEGORIES:
        return ["a preregistered engineering target is required"]
    category, metric = target["category"], target.get("metric")
    direction = "increase" if category in {"reliability", "prose"} else "decrease"
    issues = []
    if target.get("direction") != direction:
        issues.append("registered target direction does not match its category")
    if not isinstance(metric, str) or not metric:
        issues.append("registered target metric is required")
    expected = {"reliability": "task_completion_rate", "integrity": "hard_failure_count", "prose": "pairwise_preference"}
    if category in expected and metric != expected[category]:
        issues.append("unsupported target metric for " + category)
    if category == "prose":
        margin = target.get("min_win_margin")
        if not positive(margin, fraction=True) or margin < .2:
            issues.append("prose requires a preregistered min_win_margin of at least 0.2")
        minimum = target.get("min_pairs", 1)
        if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 1:
            issues.append("prose min_pairs must be a positive integer")
    else:
        thresholds = [(key, key == "min_relative_improvement") for key in
                      ("min_absolute_improvement", "min_relative_improvement") if key in target]
        if not thresholds:
            issues.append("register a positive minimum improvement before execution")
        for key, fraction in thresholds:
            if not positive(target[key], fraction=fraction):
                issues.append("invalid registered threshold: " + key)
    return issues


def verified_new_failures(pair, row):
    added = set(row["hard_failures"]) - set(row["baseline_hard_failures"])
    if pair.get("hard_checks_complete") is True:
        return sorted(added)
    results = pair.get("hard_check_results", {})
    if not isinstance(results, dict):
        return []
    left, right = results.get("baseline", {}), results.get("candidate", {})
    if not isinstance(left, dict) or not isinstance(right, dict):
        return []
    return sorted(code for code in added if left.get(code) == "pass" and right.get(code) == "fail")


def decide(pairs: list[dict], report: dict, target) -> None:
    """Apply verified regressions first, then the registered measurable objective."""
    report.update(decision_basis=None, quality_improvement_proven=False,
                  target_metric=target.get("metric") if isinstance(target, dict) else None,
                  target=target, target_result=None, hard_regressions=[], completion_regressions=[],
                  cost_delta={key: item.get("delta") for key, item in report["costs"].items()},
                  soft_diagnostics={"pairwise": report["summary"], "interpretation": "diagnostic_only"})
    critical, untrusted = [], []
    for pair, row in zip(pairs, report["pairs"]):
        if pair.get("uncertainties") or not row.get("input_valid", False):
            untrusted.extend(row["issues"] or [str(pair.get("id")) + ": untrusted inputs"])
            continue
        added = verified_new_failures(pair, row)
        row["hard_regressions"] = added
        report["hard_regressions"].extend({"id": row["id"], "failure": code} for code in added)
        if pair.get("hard_checks_complete") is not True:
            critical.append(str(row["id"]) + ": hard checks are not complete")
        completion = pair.get("completion", {})
        a, b = completion.get("baseline"), completion.get("candidate")
        if not isinstance(a, bool) or not isinstance(b, bool):
            critical.append(str(row["id"]) + ": task completion is unknown")
        elif a and not b:
            report["completion_regressions"].append(row["id"])
        if row.get("review_requested") and (row.get("position_check") == "flip" or row["issues"] or
                                             row.get("preference") in {"UNCERTAIN", "NOT_RUN"}):
            critical.append(str(row["id"]) + ": requested review has unresolved failure or position disagreement")
    if untrusted:
        report["issues"].extend(untrusted)
        report["verdict"] = "UNCERTAIN"
        return
    if report["hard_regressions"] or report["completion_regressions"]:
        report["verdict"] = "REJECT"
        return
    critical.extend(target_issues(target))
    if not pairs:
        critical.append("no selected observations were evaluated")
    if critical:
        report["issues"].extend(critical)
        report["verdict"] = "UNCERTAIN"
        return
    category, metric = target["category"], target["metric"]
    if category == "prose":
        if any(pair.get("prose_checks_complete") is not True for pair in pairs):
            report["issues"].append("prose preference needs verified hard, protected, citation and semantic checks")
        if any(row["hard_failures"] for row in report["pairs"]):
            report["issues"].append("known unresolved hard errors cannot support prose promotion")
        if any(row["issues"] or row.get("position_check") == "flip" for row in report["pairs"]):
            report["issues"].append("unresolved judge failures, disagreement or position sensitivity")
        count = report["summary"]
        denominator = len(pairs)
        margin = (count["candidate_wins"] - count["baseline_wins"]) / denominator
        report["target_result"] = {"win_margin": margin, "required_margin": target["min_win_margin"],
                                   "pairs": denominator, "minimum_pairs": target.get("min_pairs", 1)}
        if count["uncertain"] or denominator < target.get("min_pairs", 1) or report["issues"]:
            report["verdict"] = "UNCERTAIN"
        elif margin >= target["min_win_margin"]:
            report["verdict"], report["decision_basis"] = "KEEP", "prose_gain"
        elif margin <= -target["min_win_margin"]:
            report["verdict"] = "REJECT"
        else:
            report["verdict"] = "UNCERTAIN"
        return
    if category == "efficiency":
        measurement = report["costs"].get(metric, {})
        a, b = measurement.get("baseline"), measurement.get("candidate")
        if not measurement.get("coverage_complete"):
            a = b = None
    elif category == "integrity":
        a = sum(len(set(row["baseline_hard_failures"])) for row in report["pairs"])
        b = sum(len(set(row["hard_failures"])) for row in report["pairs"])
    else:
        a = sum(pair["completion"]["baseline"] for pair in pairs) / len(pairs)
        b = sum(pair["completion"]["candidate"] for pair in pairs) / len(pairs)
    if a is None or b is None:
        report["issues"].append("registered target measurement is unknown: " + metric)
        report["verdict"] = "UNCERTAIN"
        return
    gain = a - b if target["direction"] == "decrease" else b - a
    relative = gain / abs(a) if a else None
    report["target_result"] = {"baseline": a, "candidate": b, "improvement": gain,
                               "relative_improvement": relative}
    thresholds = []
    if "min_absolute_improvement" in target:
        thresholds.append((gain, target["min_absolute_improvement"]))
    if "min_relative_improvement" in target:
        if relative is None:
            report["issues"].append("relative improvement is undefined for a zero baseline")
            report["verdict"] = "UNCERTAIN"
            return
        thresholds.append((relative, target["min_relative_improvement"]))
    if all(value >= minimum for value, minimum in thresholds):
        report["verdict"], report["decision_basis"] = "KEEP", CATEGORIES[category]
    elif all(value <= -minimum for value, minimum in thresholds):
        report["verdict"] = "REJECT"
    else:
        report["verdict"] = "UNCERTAIN"
