# Novelty regression

This suite measures source-bound research behavior with automated references and constructed controls. Its default path is a bounded model run, an independent reversed-source-order run, deterministic evidence checks, and a report that preserves missing observations. A preregistered baseline/candidate comparison can establish an engineering proxy gain.

The bank contains 48 constructed controls derived from 12 published PLOS social-science papers. Each source supplies a repeated claim, a terminology change, an independent replication proposal, and an unresolved boundary or mechanism proposal. Candidate studies are hypothetical. References describe the construction rules and bind inspected publisher passages; `confidence` describes those rules, not confidence in absolute novelty. Four cases share each paper, so the 48 observations are dependent.

These are relatively easy controls, with natural candidate statements and construction metadata kept outside model prompts. They test whether a system respects known work, permits legitimate incremental research, and retains uncertainty. Performance on varied natural formulations, independently sourced real proposals, global nearest prior work, and intellectual significance remains unmeasured. `KEEP` does not prove general research quality or agreement with human experts.

## Run

From this directory, with an available model explicitly selected:

```powershell
python live_eval.py cases.json annotations.json --model MODEL --family FAMILY --max-cases 4 --max-calls 8 --output-root RUN
```

The live adapter preserves raw host output, actual context identities, request hashes, attempts and failures. Each selected case needs both source orders. Its output directory must be new. An optional secondary runner, model and declared family can inspect eligible uncertain cases within the same total call budget. A single execution produces measurements; promotion requires a registered comparison.

The offline interface consumes actual externally captured outputs and never starts a model:

```powershell
python run_eval.py export cases.json --max-cases 4 --output RUN/requests.json
python run_eval.py import RUN/requests.json RUN/responses.json --output RUN/predictions.json
python run_eval.py evaluate cases.json annotations.json RUN/predictions.json --output RUN/evaluation.json
```

`export` also accepts `--case-ids ID1,ID2` and `--seed`. The selected IDs are recorded explicitly. Each request includes the candidate claim and source passages, without reference labels. The exporter supplements the case's sources with deterministic distractors to six candidates when the bank permits it, shuffles them, and creates the exact reversed order in a separate request. With five or fewer sources, recall is marked `candidate_retrieval_not_tested`.

## Capture contract

Request bundles use `avereth-novelty-requests/v1`; each item in `requests` has `request_id`, `case_id`, `order`, `source_order`, `selected_source_ids`, `prompt`, `request_sha256`, and `output_schema`. The response schema is embedded in every request. Predictions rank zero to five prior-work IDs, classify the claim, describe its knowledge difference, and provide specific source evidence for any refutation.

External captures use this shape:

```json
{
  "schema_version": "avereth-novelty-responses/v1",
  "run_id": "actual-run-id",
  "model": "actual-model",
  "model_family": "declared-family",
  "captures": [{
    "request_id": "CASE:forward",
    "request_sha256": "actual-prompt-sha256",
    "context_id": "actual-independent-context",
    "model": "actual-model",
    "response": {},
    "trace": {"path": "capture-001.json", "sha256": "actual-trace-sha256"}
  }],
  "failures": []
}
```

The trace contains matching `context_id`, `model`, `request_sha256`, and `raw_output`, which is the original JSON response string. Import validates that the parsed host output equals `response`. The host array schema uses basic item types; local validation enforces at most five unique prior-work IDs. Every requested row remains in the imported denominator even if its capture is missing. Source and trace paths must remain inside their owning directory; scope is checked before bytes are read. Explicit top-level input bindings may name absolute files elsewhere. Outputs are created exclusively and cannot overwrite earlier evidence.

## Measurements and uncertainty

| Metric | Measured population and limitation |
| --- | --- |
| `false_novelty_proxy` | Registered non-novel controls incorrectly accepted as incremental or potentially novel. |
| `false_rejection_proxy` | Registered incremental or potentially novel references incorrectly rejected as non-novel. |
| `nearest_prior_recall_at_5` | Registered nearest sources recovered from more than five supplied candidates; bounded retrieval only. |
| `unsupported_refutation_rate` | All actual `can_refute` assertions, including secondary outputs. Invalid source/locator/quote/claim bindings are unsupported. Exact identical claims can establish redundancy; other semantic relations require a separately registered, anchored relation. |
| `pseudo_diversity_escape_rate` | Registered terminology-only controls accepted as substantive differences. |
| `order_swap_instability` | Disagreement across independently executed source orders. Missing orders remain unknown. |
| `delta_reference_agreement` | Optional independent automatic review of the actual delta statement against registered source anchors. Missing reviews remain unknown. |

Every counter reports its denominator, unknown observations, and unknown eligibility. A rate is `null` when required observations are missing. Explicitly ambiguous references are excluded from binary error populations and counted separately. Zero refutation opportunities produce `null`, not a fabricated zero error rate. Reference labels alone cannot validate a semantic refutation. Missing usable source-bound references yield `NOT RUN`; missing required captured orders yield `INCOMPLETE`. The `execution` record gives required and valid capture counts. Synthetic inputs yield `SYNTHETIC_CONTRACT_ONLY`, preserve the underlying `measurement_status`, and are never promotion eligible.

`evaluate --secondary-predictions SECONDARY.json` accepts an independently imported subset from a different model and declared family, with the same sources. Family names are declarations, not authenticated model-lineage evidence. Case records expose `secondary_eligible` and `secondary_reason` for bounded scheduling. A stable, low-confidence or unclear primary judgment can use two consistent, confident secondary outputs when their evidence binds and their classes do not conflict. Missing primary orders, primary order flips, fabricated refutation evidence, and conflicting judgments remain uncertain. Secondary failures and all refutation assertions remain in the report.

Optional `--delta-reviews REVIEWS.json` binds `predictions_sha256` and a `reviews` array. Each row needs `case_id`, the actual `delta_sha256`, an independent `context_id`, a different declared `model_family`, `confidence`, `verdict` (`agree`, `disagree`, or `unclear`), a rationale, and actual source anchors. This is automated reference agreement, not human agreement.

## Registered comparison

Write the experiment before exporting either run and pass it to both exports with `--experiment experiment.json`. Bind the exact bank, reference file and selected cases, and register one positive minimum improvement plus guardrails:

```json
{
  "schema_version": "avereth-novelty-experiment/v1",
  "cases_sha256": "actual-cases-sha256",
  "annotations_sha256": "actual-annotations-sha256",
  "selected_ids": ["CASE1", "CASE2"],
  "target": {
    "metric": "false_novelty_proxy",
    "direction": "decrease",
    "min_absolute_improvement": 0.1
  },
  "guardrails": {
    "false_novelty_proxy": {"max_increase": 0},
    "false_rejection_proxy": {"max_increase": 0},
    "unsupported_refutation_rate": {"maximum": 0},
    "pseudo_diversity_escape_rate": {"max_increase": 0},
    "order_swap_instability": {"maximum": 0}
  }
}
```

```powershell
python run_eval.py compare cases.json annotations.json BASE/predictions.json CANDIDATE/predictions.json --experiment experiment.json --output comparison.json
```

Both runs must use the same generation model, full registered selection, and independent run and context identities. Recall and delta agreement target an increase; error and instability targets require a decrease. Guardrails accept `maximum`, `minimum`, `max_increase` and `max_decrease`. Missing required measurements or invalid bindings produce `UNCERTAIN`; threshold-sized degradation or a measured guardrail violation produces `REJECT`; a sufficient measured gain with satisfied guardrails produces `KEEP` and `decision_basis=engineering_proxy_gain`. `absolute_novelty_proven` and `quality_improvement_proven` remain false.

CLI exit codes are `KEEP=0`, `REJECT=1`, and `UNCERTAIN` or invalid input `=2`. Successful export/import exits with 0. A single measured run retains `UNCERTAIN` because it is not a baseline/candidate improvement decision.

## Contract tests

```powershell
python -m unittest discover -s evals/novelty-regression -p "test_*.py" -v
```

Run tests from the repository root. Test sources and captured model outputs are synthetic, created locally, and marked accordingly. They validate evidence binding, uncertainty, denominator preservation, source-order behavior and decision rules; they do not measure real model quality.
