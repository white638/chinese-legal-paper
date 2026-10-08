"""Recompute and cross-check supervised text-measurement artifacts."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Mapping

from .common import (
    Finding,
    ValidationContext,
    artifact_path,
    finite_number,
    issue,
    read_json_artifact,
    read_rows_artifact,
    require_columns,
    require_fields,
    require_list,
    require_mapping,
    substantive,
    text,
)


VALIDITY_DIMENSIONS = (
    "content",
    "construct",
    "convergent",
    "discriminant",
    "known_groups",
    "temporal",
    "institutional",
    "language",
    "case",
)
VALIDITY_STATUSES = {"documented", "needs-independent-review", "not-applicable"}
REFERENCE_BASES = {
    "independent_model_review",
    "same_model_repeat",
    "external_benchmark",
    "rule_verified",
    "mixed_evidence",
}


def _row_id(row: Mapping[str, Any]) -> str:
    for key in ("item_id", "id", "claim_id", "sentence_id"):
        if substantive(row.get(key)):
            return text(row.get(key))
    return ""


def _label(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if substantive(row.get(key)):
            return text(row.get(key))
    return ""


def _time(value: Any) -> datetime | None:
    token = text(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = sorted(
        {
            _label(row, "reference_label")
            for row in rows
        }
        | {
            _label(row, "predicted", "predicted_label", "prediction")
            for row in rows
        }
    )
    labels = [label for label in labels if label]
    per_class: dict[str, dict[str, float | int]] = {}
    confusion_matrix = {
        gold: {predicted: 0 for predicted in labels}
        for gold in labels
    }
    correct = 0
    for row in rows:
        gold = _label(row, "reference_label")
        predicted = _label(row, "predicted", "predicted_label", "prediction")
        if gold in confusion_matrix and predicted in confusion_matrix[gold]:
            confusion_matrix[gold][predicted] += 1
    for label in labels:
        tp = fp = fn = support = 0
        for row in rows:
            gold = _label(row, "reference_label")
            predicted = _label(row, "predicted", "predicted_label", "prediction")
            correct += int(gold == predicted) if label == labels[0] else 0
            support += int(gold == label)
            tp += int(gold == label and predicted == label)
            fp += int(gold != label and predicted == label)
            fn += int(gold == label and predicted != label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    macro_f1 = sum(item["f1"] for item in per_class.values()) / len(per_class) if per_class else 0.0
    micro_tp = sum(confusion_matrix[label][label] for label in labels)
    micro_total = sum(sum(row.values()) for row in confusion_matrix.values())
    micro_f1 = micro_tp / micro_total if micro_total else 0.0
    return {
        "n": len(rows),
        "agreement_rate": correct / len(rows) if rows else 0.0,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "per_class": per_class,
        "confusion_matrix": confusion_matrix,
    }


def _compare_metric(
    findings: list[Finding], declared: Any, actual: float, path: str
) -> None:
    parsed = finite_number(declared)
    if parsed is None or abs(parsed - actual) > 1e-9:
        findings.append(
            issue(
                "ME.MEASUREMENT.METRIC_MISMATCH",
                f"Declared metric {declared!r} does not reproduce from predictions ({actual:.12g})",
                path,
            )
        )


def validate(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    contract = ctx.contract
    prefix = f"{ctx.path}.method_contract"

    construct = require_mapping(
        findings, contract.get("construct"), f"{prefix}.construct", "ME.MEASUREMENT.CONSTRUCT_MISSING"
    )
    require_fields(
        findings,
        construct,
        ("name", "definition", "unit", "codebook_version"),
        f"{prefix}.construct",
        "ME.MEASUREMENT.CONSTRUCT_MISSING",
    )
    interpretation = require_mapping(
        findings,
        contract.get("interpretation"),
        f"{prefix}.interpretation",
        "ME.MEASUREMENT.INTERPRETATION_MISSING",
    )
    require_fields(
        findings,
        interpretation,
        ("allowed", "prohibited"),
        f"{prefix}.interpretation",
        "ME.MEASUREMENT.INTERPRETATION_MISSING",
    )

    corpus = require_mapping(
        findings, contract.get("corpus"), f"{prefix}.corpus", "ME.MEASUREMENT.CORPUS_MISSING"
    )
    if corpus.get("frozen") is not True:
        findings.append(
            issue(
                "ME.MEASUREMENT.CORPUS_NOT_FROZEN",
                "Text measurement requires an explicitly frozen corpus",
                f"{prefix}.corpus.frozen",
            )
        )
    artifact_path(
        ctx,
        corpus.get("manifest_artifact_id"),
        f"{prefix}.corpus.manifest_artifact_id",
        findings,
    )
    artifact_path(
        ctx,
        contract.get("codebook_artifact_id"),
        f"{prefix}.codebook_artifact_id",
        findings,
    )

    reference = require_mapping(
        findings,
        contract.get("reference_standard"),
        f"{prefix}.reference_standard",
        "ME.MEASUREMENT.REFERENCE_MISSING",
    )
    require_fields(
        findings,
        reference,
        (
            "sampling_strategy",
            "reference_basis",
            "metric_semantics",
            "independence",
            "frozen_at",
            "run_manifest_artifact_id",
            "evidence_artifact_id",
            "review_artifact_id",
        ),
        f"{prefix}.reference_standard",
        "ME.MEASUREMENT.REFERENCE_MISSING",
    )
    run_count = finite_number(reference.get("run_count"))
    if run_count is None or run_count < 1 or int(run_count) != run_count:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_MISSING",
                "reference_standard.run_count must be a positive integer",
                f"{prefix}.reference_standard.run_count",
            )
        )
    reference_basis = text(reference.get("reference_basis"))
    if reference_basis not in REFERENCE_BASES:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_BASIS_INVALID",
                "Reference basis must be an independent model review, same-model repeat, external benchmark, rule-verified source, or mixed evidence",
                f"{prefix}.reference_standard.reference_basis",
            )
        )
    metric_semantics = text(reference.get("metric_semantics"))
    if metric_semantics not in {"reference_agreement", "external_accuracy", "stability"}:
        findings.append(
            issue(
                "ME.MEASUREMENT.METRIC_SEMANTICS_INVALID",
                "Metric semantics must distinguish reference agreement, external accuracy, or stability",
                f"{prefix}.reference_standard.metric_semantics",
            )
        )
    if metric_semantics == "external_accuracy" and reference_basis != "external_benchmark":
        findings.append(
            issue(
                "ME.MEASUREMENT.FALSE_ACCURACY",
                "Only an external benchmark may be reported with external_accuracy semantics",
                f"{prefix}.reference_standard.metric_semantics",
            )
        )
    if reference_basis == "independent_model_review" and metric_semantics == "external_accuracy":
        findings.append(
            issue(
                "ME.MEASUREMENT.FALSE_ACCURACY",
                "Model-constructed reference labels measure agreement, not external accuracy",
                f"{prefix}.reference_standard.metric_semantics",
            )
        )
    if reference_basis == "independent_model_review" and metric_semantics != "reference_agreement":
        findings.append(
            issue(
                "ME.MEASUREMENT.METRIC_SEMANTICS_INVALID",
                "Independent model references must be reported as reference_agreement",
                f"{prefix}.reference_standard.metric_semantics",
            )
        )
    if (reference_basis == "same_model_repeat") != (metric_semantics == "stability"):
        findings.append(
            issue(
                "ME.MEASUREMENT.METRIC_SEMANTICS_INVALID",
                "Only same-model repeat runs may be reported as stability, and they must use stability semantics",
                f"{prefix}.reference_standard.metric_semantics",
            )
        )
    frozen_at = _time(reference.get("frozen_at"))
    if frozen_at is None:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_TIME_INVALID",
                "reference_standard.frozen_at must be a timezone-aware ISO timestamp",
                f"{prefix}.reference_standard.frozen_at",
            )
        )
    reference_run_ids = {
        text(item)
        for item in require_list(
            findings,
            reference.get("reference_run_ids"),
            f"{prefix}.reference_standard.reference_run_ids",
            "ME.MEASUREMENT.REFERENCE_MISSING",
        )
        if substantive(item)
    }
    if run_count is not None and int(run_count) != len(reference_run_ids):
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_RUN_COUNT",
                "reference_standard.run_count must equal the number of distinct reference_run_ids",
                f"{prefix}.reference_standard.run_count",
            )
        )
    reference_rows = read_rows_artifact(
        ctx,
        reference.get("labels_artifact_id"),
        f"{prefix}.reference_standard.labels_artifact_id",
        findings,
    )
    require_columns(
        findings,
        reference_rows,
        (
            "item_id",
            "reference_label",
            "evidence_locator",
            "review_run_id",
            "confidence",
            "disagreement_status",
        ),
        f"{prefix}.reference_standard.labels_artifact_id",
        "ME.MEASUREMENT.REFERENCE_SCHEMA",
    )
    reference_identifiers = [_row_id(row) for row in reference_rows]
    duplicate_reference_ids = [
        item
        for item, count in Counter(reference_identifiers).items()
        if item and count > 1
    ]
    if duplicate_reference_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_DUPLICATE",
                f"Reference labels contain {len(duplicate_reference_ids)} duplicate item ID(s)",
                f"{prefix}.reference_standard.labels_artifact_id",
            )
        )
    reference_disposition_ids: set[str] = set()
    for index, row in enumerate(reference_rows):
        row_path = f"{prefix}.reference_standard.labels_artifact_id.rows[{index}]"
        confidence = finite_number(row.get("confidence"))
        if confidence is None or not 0 <= confidence <= 1:
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_CONFIDENCE_INVALID",
                    "Reference confidence must be a number from 0 through 1",
                    f"{row_path}.confidence",
                )
            )
        status = text(row.get("disagreement_status"))
        if status not in {"no-disagreement", "resolved"}:
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_REVIEW_UNRESOLVED",
                    "Each included reference item must be marked no-disagreement or resolved",
                    f"{row_path}.disagreement_status",
                )
            )
        if status == "resolved" or (confidence is not None and confidence < 0.8):
            reference_disposition_ids.add(_row_id(row))
    run_manifest = read_json_artifact(
        ctx,
        reference.get("run_manifest_artifact_id"),
        f"{prefix}.reference_standard.run_manifest_artifact_id",
        findings,
    )
    run_manifest_rows = (
        run_manifest.get("runs") if isinstance(run_manifest, Mapping) else None
    )
    if not isinstance(run_manifest_rows, list) or not run_manifest_rows:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID",
                "Reference-run manifest must contain a non-empty runs array",
                f"{prefix}.reference_standard.run_manifest_artifact_id",
            )
        )
        run_manifest_rows = []
    manifest_run_ids: set[str] = set()
    manifest_context_ids: set[str] = set()
    manifest_output_ids: set[str] = set()
    for index, row in enumerate(run_manifest_rows):
        row_path = f"{prefix}.reference_standard.run_manifest_artifact_id.runs[{index}]"
        if not isinstance(row, Mapping):
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID",
                    "Every reference-run record must be an object",
                    row_path,
                )
            )
            continue
        required_run_fields = (
            "run_id",
            "context_id",
            "model_name",
            "model_revision",
            "completed_at",
            "system_prompt_sha256",
            "user_prompt_sha256",
            "output_artifact_id",
            "blind_to_primary_output",
        )
        require_fields(
            findings,
            row,
            required_run_fields,
            row_path,
            "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID",
        )
        run_id = text(row.get("run_id"))
        context_id = text(row.get("context_id"))
        output_id = text(row.get("output_artifact_id")).upper()
        if run_id in manifest_run_ids or context_id in manifest_context_ids or output_id in manifest_output_ids:
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_RUN_NOT_INDEPENDENT",
                    "Reference runs require distinct run, context, and output identities",
                    row_path,
                )
            )
        manifest_run_ids.add(run_id)
        manifest_context_ids.add(context_id)
        manifest_output_ids.add(output_id)
        if row.get("blind_to_primary_output") is not True:
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_RUN_NOT_INDEPENDENT",
                    "Reference runs must be completed without access to the primary output",
                    f"{row_path}.blind_to_primary_output",
                )
            )
        completed_at = _time(row.get("completed_at"))
        if completed_at is None or (frozen_at is not None and completed_at >= frozen_at):
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_TIME_INVALID",
                    "Each reference run must complete before the reference standard is frozen",
                    f"{row_path}.completed_at",
                )
            )
        for digest_field in ("system_prompt_sha256", "user_prompt_sha256"):
            digest = text(row.get(digest_field))
            if len(digest) != 64 or any(character not in "0123456789abcdefABCDEF" for character in digest):
                findings.append(
                    issue(
                        "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID",
                        f"{digest_field} must be a SHA-256 digest",
                        f"{row_path}.{digest_field}",
                    )
                )
        artifact_path(
            ctx,
            output_id,
            f"{row_path}.output_artifact_id",
            findings,
        )
    if manifest_run_ids != reference_run_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_RUN_MANIFEST_INVALID",
                "Reference-run manifest IDs must exactly match reference_run_ids",
                f"{prefix}.reference_standard.run_manifest_artifact_id",
            )
        )
    evidence_rows = read_rows_artifact(
        ctx,
        reference.get("evidence_artifact_id"),
        f"{prefix}.reference_standard.evidence_artifact_id",
        findings,
    )
    require_columns(
        findings,
        evidence_rows,
        ("item_id", "source_artifact_id", "evidence_locator", "rationale", "codebook_version"),
        f"{prefix}.reference_standard.evidence_artifact_id",
        "ME.MEASUREMENT.REFERENCE_EVIDENCE_INVALID",
    )
    evidence_identifiers = [_row_id(row) for row in evidence_rows]
    duplicate_evidence_ids = [
        item
        for item, count in Counter(evidence_identifiers).items()
        if item and count > 1
    ]
    if duplicate_evidence_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_EVIDENCE_DUPLICATE",
                "Source-grounded evidence contains duplicate item IDs",
                f"{prefix}.reference_standard.evidence_artifact_id",
            )
        )
    expected_codebook_version = text(construct.get("codebook_version"))
    for index, row in enumerate(evidence_rows):
        if text(row.get("codebook_version")) != expected_codebook_version:
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_EVIDENCE_INVALID",
                    "Every evidence row must bind the frozen construct codebook version",
                    f"{prefix}.reference_standard.evidence_artifact_id.rows[{index}].codebook_version",
                )
            )
    review_payload = read_json_artifact(
        ctx,
        reference.get("review_artifact_id"),
        f"{prefix}.reference_standard.review_artifact_id",
        findings,
    )
    if not isinstance(review_payload, Mapping):
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_INVALID",
                "Independent review artifact must be a structured JSON object",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
        review_payload = {}
    require_fields(
        findings,
        review_payload,
        ("reviewed_item_ids", "resolution_rule", "unresolved_count", "adjudication_run_id"),
        f"{prefix}.reference_standard.review_artifact_id",
        "ME.MEASUREMENT.REFERENCE_REVIEW_INVALID",
    )
    dispositions = review_payload.get("item_dispositions")
    if not isinstance(dispositions, Mapping):
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_INVALID",
                "Independent review must contain an item_dispositions object",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
        dispositions = {}
    disposition_ids = {
        text(item_id)
        for item_id, disposition in dispositions.items()
        if substantive(item_id) and substantive(disposition)
    }
    if disposition_ids != reference_disposition_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_UNRESOLVED",
                "Resolved disagreements and low-confidence reference items require exact item-level dispositions",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
    unresolved_count = finite_number(review_payload.get("unresolved_count"))
    if unresolved_count != 0:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_UNRESOLVED",
                "Independent reference review must resolve or explicitly exclude every disagreement",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
    adjudication_run_id = text(review_payload.get("adjudication_run_id"))
    if adjudication_run_id and adjudication_run_id not in reference_run_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_INVALID",
                "adjudication_run_id must name a registered independent reference run",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
    for source_artifact_id in {
        text(row.get("source_artifact_id")).upper()
        for row in evidence_rows
        if substantive(row.get("source_artifact_id"))
    }:
        artifact_path(
            ctx,
            source_artifact_id,
            f"{prefix}.reference_standard.evidence_artifact_id.source_artifact_id",
            findings,
        )

    split = require_mapping(
        findings, contract.get("split"), f"{prefix}.split", "ME.MEASUREMENT.SPLIT_MISSING"
    )
    require_fields(
        findings,
        split,
        ("strategy", "grouping_unit"),
        f"{prefix}.split",
        "ME.MEASUREMENT.SPLIT_MISSING",
    )
    train_rows = read_rows_artifact(
        ctx,
        split.get("train_manifest_artifact_id"),
        f"{prefix}.split.train_manifest_artifact_id",
        findings,
    )
    test_rows = read_rows_artifact(
        ctx,
        split.get("test_manifest_artifact_id"),
        f"{prefix}.split.test_manifest_artifact_id",
        findings,
    )
    train_ids = {_row_id(row) for row in train_rows if _row_id(row)}
    test_ids = {_row_id(row) for row in test_rows if _row_id(row)}
    if not train_ids or not test_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.SPLIT_MISSING",
                "Training and independent test manifests must both contain item IDs",
                f"{prefix}.split",
            )
        )
    evidence_ids = {_row_id(row) for row in evidence_rows if _row_id(row)}
    if evidence_ids != test_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_EVIDENCE_COVERAGE",
                "Source-grounded evidence IDs must exactly match the independent test manifest",
                f"{prefix}.reference_standard.evidence_artifact_id",
            )
        )
    evidence_by_id = {
        _row_id(row): text(row.get("evidence_locator"))
        for row in evidence_rows
        if _row_id(row)
    }
    disconnected_evidence = [
        _row_id(row)
        for row in reference_rows
        if _row_id(row)
        and evidence_by_id.get(_row_id(row)) != text(row.get("evidence_locator"))
    ]
    if disconnected_evidence:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_EVIDENCE_MISMATCH",
                "Reference labels must bind the same evidence locators as the evidence trace",
                f"{prefix}.reference_standard.evidence_artifact_id",
            )
        )
    reviewed_raw = review_payload.get("reviewed_item_ids", [])
    reviewed_item_ids = {
        text(item)
        for item in reviewed_raw
        if substantive(item)
    } if isinstance(reviewed_raw, list) else set()
    if isinstance(reviewed_raw, list) and len(reviewed_raw) != len(reviewed_item_ids):
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_INVALID",
                "reviewed_item_ids must be unique and substantive",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
    if reviewed_item_ids != test_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_REVIEW_COVERAGE",
                "Independent review must cover every frozen test item",
                f"{prefix}.reference_standard.review_artifact_id",
            )
        )
    overlap = sorted(train_ids & test_ids)
    if overlap:
        findings.append(
            issue(
                "ME.MEASUREMENT.SPLIT_OVERLAP",
                f"Train and test manifests overlap on {len(overlap)} item ID(s)",
                f"{prefix}.split",
            )
        )
    group_key = text(split.get("grouping_unit"))
    if group_key:
        train_groups = {text(row.get(group_key)) for row in train_rows if substantive(row.get(group_key))}
        test_groups = {text(row.get(group_key)) for row in test_rows if substantive(row.get(group_key))}
        group_overlap = sorted(train_groups & test_groups)
        if group_overlap:
            findings.append(
                issue(
                    "ME.MEASUREMENT.GROUP_LEAKAGE",
                    f"Grouped split leaks {len(group_overlap)} {group_key} value(s) across train and test",
                    f"{prefix}.split.grouping_unit",
                )
            )

    validation = require_mapping(
        findings,
        contract.get("validation"),
        f"{prefix}.validation",
        "ME.MEASUREMENT.VALIDATION_MISSING",
    )
    prediction_rows = read_rows_artifact(
        ctx,
        validation.get("predictions_artifact_id"),
        f"{prefix}.validation.predictions_artifact_id",
        findings,
    )
    require_columns(
        findings,
        prediction_rows,
        ("item_id", "reference_label", "predicted"),
        f"{prefix}.validation.predictions_artifact_id",
        "ME.MEASUREMENT.PREDICTION_SCHEMA",
    )
    identifiers = [_row_id(row) for row in prediction_rows]
    duplicates = [item for item, count in Counter(identifiers).items() if item and count > 1]
    if duplicates:
        findings.append(
            issue(
                "ME.MEASUREMENT.PREDICTION_DUPLICATE",
                f"Predictions contain {len(duplicates)} duplicate item ID(s)",
                f"{prefix}.validation.predictions_artifact_id",
            )
        )
    if set(identifiers) != test_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.TEST_COUNT_MISMATCH",
                "Prediction IDs must exactly match the frozen independent test manifest",
                f"{prefix}.validation.predictions_artifact_id",
            )
        )
    reference_by_id = {
        _row_id(row): _label(row, "reference_label")
        for row in reference_rows
        if _row_id(row)
    }
    if set(reference_by_id) != test_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_COVERAGE",
                "Frozen reference-label IDs must exactly match the independent test manifest",
                f"{prefix}.reference_standard.labels_artifact_id",
            )
        )
    unknown_review_runs = {
        text(row.get("review_run_id"))
        for row in reference_rows
        if substantive(row.get("review_run_id"))
    } - reference_run_ids
    if unknown_review_runs:
        findings.append(
            issue(
                "ME.MEASUREMENT.REFERENCE_RUN_UNKNOWN",
                "Every reference row must name a registered independent reference run",
                f"{prefix}.reference_standard.labels_artifact_id",
            )
        )
    for row in prediction_rows:
        identifier = _row_id(row)
        if identifier in reference_by_id and reference_by_id[identifier] != _label(row, "reference_label"):
            findings.append(
                issue(
                    "ME.MEASUREMENT.REFERENCE_MISMATCH",
                    f"Prediction reference label differs from the frozen reference standard for {identifier}",
                    f"{prefix}.validation.predictions_artifact_id",
                )
            )
            break

    declared = read_json_artifact(
        ctx,
        validation.get("metrics_artifact_id"),
        f"{prefix}.validation.metrics_artifact_id",
        findings,
    )
    actual = _metrics(prediction_rows) if prediction_rows else {}
    if not isinstance(declared, Mapping):
        findings.append(
            issue(
                "ME.MEASUREMENT.METRIC_MISMATCH",
                "Metrics artifact must be a structured JSON object",
                f"{prefix}.validation.metrics_artifact_id",
            )
        )
    if isinstance(declared, Mapping) and prediction_rows:
        if text(declared.get("metric_semantics")) != metric_semantics:
            findings.append(
                issue(
                    "ME.MEASUREMENT.METRIC_SEMANTICS_INVALID",
                    "Metrics artifact semantics must match the frozen reference standard",
                    f"{prefix}.validation.metrics_artifact_id",
                )
            )
        if metric_semantics != "external_accuracy" and "accuracy" in declared:
            findings.append(
                issue(
                    "ME.MEASUREMENT.FALSE_ACCURACY",
                    "Model-reference agreement must not be reported as accuracy",
                    f"{prefix}.validation.metrics_artifact_id",
                )
            )
        if int(finite_number(declared.get("n")) or -1) != actual["n"]:
            findings.append(
                issue(
                    "ME.MEASUREMENT.METRIC_MISMATCH",
                    "Declared validation n does not match predictions",
                    f"{prefix}.validation.metrics_artifact_id",
                )
            )
        metric_key = "accuracy" if metric_semantics == "external_accuracy" else "agreement_rate"
        _compare_metric(findings, declared.get(metric_key), actual["agreement_rate"], f"{prefix}.validation.metrics_artifact_id")
        _compare_metric(findings, declared.get("macro_f1"), actual["macro_f1"], f"{prefix}.validation.metrics_artifact_id")
        _compare_metric(findings, declared.get("micro_f1"), actual["micro_f1"], f"{prefix}.validation.metrics_artifact_id")
        if declared.get("confusion_matrix") != actual["confusion_matrix"]:
            findings.append(
                issue(
                    "ME.MEASUREMENT.METRIC_MISMATCH",
                    "Declared confusion matrix does not reproduce from predictions",
                    f"{prefix}.validation.metrics_artifact_id",
                )
            )
        per_class = declared.get("per_class")
        if not isinstance(per_class, Mapping) or set(per_class) != set(actual["per_class"]):
            findings.append(
                issue(
                    "ME.MEASUREMENT.CLASS_METRICS_MISSING",
                    "Metrics must report every observed class, not a single overall score",
                    f"{prefix}.validation.metrics_artifact_id",
                )
            )
        else:
            for label, metrics in actual["per_class"].items():
                declared_class = per_class.get(label)
                if not isinstance(declared_class, Mapping):
                    continue
                if int(finite_number(declared_class.get("support")) or -1) != metrics["support"]:
                    findings.append(
                        issue(
                            "ME.MEASUREMENT.METRIC_MISMATCH",
                            f"Declared support for class {label!r} is not reproducible",
                            f"{prefix}.validation.metrics_artifact_id",
                        )
                    )
                for metric in ("precision", "recall", "f1"):
                    _compare_metric(
                        findings,
                        declared_class.get(metric),
                        float(metrics[metric]),
                        f"{prefix}.validation.metrics_artifact_id",
                    )

    error_path = artifact_path(
        ctx,
        validation.get("error_analysis_artifact_id"),
        f"{prefix}.validation.error_analysis_artifact_id",
        findings,
    )
    if error_path is not None and not error_path.read_text(encoding="utf-8-sig", errors="replace").strip():
        findings.append(
            issue(
                "ME.MEASUREMENT.ERROR_ANALYSIS_EMPTY",
                "Error analysis artifact is empty",
                f"{prefix}.validation.error_analysis_artifact_id",
            )
        )

    sensitivity = require_mapping(
        findings,
        contract.get("sensitivity"),
        f"{prefix}.sensitivity",
        "ME.MEASUREMENT.SENSITIVITY_MISSING",
    )
    dimensions = sensitivity.get("dimensions")
    if not isinstance(dimensions, list) or not any(substantive(item) for item in dimensions):
        findings.append(
            issue(
                "ME.MEASUREMENT.SENSITIVITY_MISSING",
                "At least one preprocessing or threshold sensitivity dimension is required",
                f"{prefix}.sensitivity.dimensions",
            )
        )
    artifact_path(
        ctx,
        sensitivity.get("artifact_id"),
        f"{prefix}.sensitivity.artifact_id",
        findings,
    )

    validity = require_mapping(
        findings,
        contract.get("validity"),
        f"{prefix}.validity",
        "ME.MEASUREMENT.VALIDITY_MISSING",
    )
    validity_payload = read_json_artifact(
        ctx,
        validity.get("artifact_id"),
        f"{prefix}.validity.artifact_id",
        findings,
    )
    validity_dimensions = (
        validity_payload.get("dimensions")
        if isinstance(validity_payload, Mapping)
        else None
    )
    if not isinstance(validity_dimensions, Mapping):
        findings.append(
            issue(
                "ME.MEASUREMENT.VALIDITY_MISSING",
                "Measurement validity artifact must contain a dimensions object",
                f"{prefix}.validity.artifact_id",
            )
        )
    else:
        for dimension in VALIDITY_DIMENSIONS:
            record = validity_dimensions.get(dimension)
            dimension_path = f"{prefix}.validity.dimensions.{dimension}"
            if not isinstance(record, Mapping):
                findings.append(
                    issue(
                        "ME.MEASUREMENT.VALIDITY_DIMENSION_MISSING",
                        f"Validity dimension {dimension!r} must be explicitly documented or marked not-applicable",
                        dimension_path,
                    )
                )
                continue
            status = text(record.get("status"))
            rationale = text(record.get("rationale"))
            if status not in VALIDITY_STATUSES or not rationale:
                findings.append(
                    issue(
                        "ME.MEASUREMENT.VALIDITY_DIMENSION_INVALID",
                        "Validity status must be documented, needs-independent-review, or not-applicable and include a rationale",
                        dimension_path,
                    )
                )
            evidence_ids = record.get("evidence_artifact_ids") or []
            if status != "not-applicable" and (
                not isinstance(evidence_ids, list) or not evidence_ids
            ):
                findings.append(
                    issue(
                        "ME.MEASUREMENT.VALIDITY_EVIDENCE_MISSING",
                        f"Validity dimension {dimension!r} requires at least one registered evidence artifact",
                        dimension_path,
                    )
                )
            if isinstance(evidence_ids, list):
                for evidence_index, identifier in enumerate(evidence_ids):
                    artifact_path(
                        ctx,
                        identifier,
                        f"{dimension_path}.evidence_artifact_ids[{evidence_index}]",
                        findings,
                    )

    researcher_run = require_mapping(
        findings,
        contract.get("researcher_run"),
        f"{prefix}.researcher_run",
        "ME.MEASUREMENT.RESEARCHER_RUN_INCOMPLETE",
    )
    require_fields(
        findings,
        researcher_run,
        (
            "run_id",
            "context_id",
            "model_name",
            "model_revision",
            "run_date",
            "system_prompt_sha256",
            "user_prompt_sha256",
            "temperature",
            "repeat_count",
            "output_schema",
            "retry_rule",
            "repeat_consistency",
            "reference_labels_artifact_id",
            "evidence_trace_artifact_id",
            "independent_review_artifact_id",
        ),
        f"{prefix}.researcher_run",
        "ME.MEASUREMENT.RESEARCHER_RUN_INCOMPLETE",
    )
    primary_run_id = text(researcher_run.get("run_id"))
    primary_context_id = text(researcher_run.get("context_id"))
    if primary_run_id and primary_run_id in reference_run_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REVIEW_NOT_INDEPENDENT",
                "The primary researcher run must not also serve as an independent reference run",
                f"{prefix}.researcher_run.run_id",
            )
        )
    if primary_context_id and primary_context_id in manifest_context_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.REVIEW_NOT_INDEPENDENT",
                "The primary researcher context must be distinct from every reference context",
                f"{prefix}.researcher_run.context_id",
            )
        )
    primary_run_date = _time(researcher_run.get("run_date"))
    if primary_run_date is None or (frozen_at is not None and primary_run_date <= frozen_at):
        findings.append(
            issue(
                "ME.MEASUREMENT.REVIEW_NOT_FROZEN",
                "The reference standard must be frozen before the primary evaluation run",
                f"{prefix}.researcher_run.run_date",
            )
        )
    for key in ("system_prompt_sha256", "user_prompt_sha256"):
        value = text(researcher_run.get(key))
        if len(value) != 64 or any(character not in "0123456789abcdefABCDEF" for character in value):
            findings.append(
                issue(
                    "ME.MEASUREMENT.RESEARCHER_RUN_INCOMPLETE",
                    f"{key} must be a SHA-256 digest",
                    f"{prefix}.researcher_run.{key}",
                )
            )
    for field in (
        "reference_labels_artifact_id",
        "evidence_trace_artifact_id",
        "independent_review_artifact_id",
    ):
        artifact_path(
            ctx,
            researcher_run.get(field),
            f"{prefix}.researcher_run.{field}",
            findings,
        )
    binding_pairs = (
        ("reference_labels_artifact_id", reference.get("labels_artifact_id")),
        ("evidence_trace_artifact_id", reference.get("evidence_artifact_id")),
        ("independent_review_artifact_id", reference.get("review_artifact_id")),
    )
    for field, expected in binding_pairs:
        if text(researcher_run.get(field)).upper() != text(expected).upper():
            findings.append(
                issue(
                    "ME.MEASUREMENT.RESEARCHER_BINDING_MISMATCH",
                    f"researcher_run.{field} must bind the corresponding frozen reference artifact",
                    f"{prefix}.researcher_run.{field}",
                )
            )
    primary_output_id = text(validation.get("predictions_artifact_id")).upper()
    protected_ids = {
        text(reference.get("labels_artifact_id")).upper(),
        text(reference.get("run_manifest_artifact_id")).upper(),
        text(reference.get("evidence_artifact_id")).upper(),
        text(reference.get("review_artifact_id")).upper(),
    }
    if protected_ids & manifest_output_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.PROVENANCE_OVERLAP",
                "Raw reference-run outputs must be distinct from synthesized labels, evidence, review, and manifest artifacts",
                f"{prefix}.reference_standard.run_manifest_artifact_id",
            )
        )
    if primary_output_id in protected_ids or primary_output_id in manifest_output_ids:
        findings.append(
            issue(
                "ME.MEASUREMENT.SELF_VALIDATION",
                "Primary predictions must be a distinct artifact from every reference and review artifact",
                f"{prefix}.validation.predictions_artifact_id",
            )
        )
    comparison_ids = {primary_output_id} | manifest_output_ids
    comparison_digests = [
        text((ctx.artifacts.get(identifier) or {}).get("sha256")).casefold()
        for identifier in comparison_ids
        if identifier
    ]
    if len(comparison_digests) != len(set(comparison_digests)):
        findings.append(
            issue(
                "ME.MEASUREMENT.SELF_VALIDATION",
                "Primary and independent reference outputs must not share the same registered content hash",
                f"{prefix}.reference_standard.run_manifest_artifact_id",
            )
        )
    return findings
