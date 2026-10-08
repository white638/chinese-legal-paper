# Commonplace writing evaluation

The engineering default compares production C with candidate D on 5–10 frozen real writing tasks. Both retain deep reading; D enables Commonplace. A preregistered prose target makes this a bounded exception to Lean Core's diagnostic-only use of general writing preferences. After verified hard, protected-fact, citation and semantic checks, the evaluator compares anonymous outputs and reports `KEEP / REJECT / UNCERTAIN`, regressions and measured costs. Human inspection is optional; `quality_improvement_proven` remains false.

## Automatic paired evaluation

Freeze each task's question, final evidence set, MIR, model revision, seed and equal total generation budget. Generate C and D through the writing workflow in separate actual contexts, preserving their complete prompts and outputs. Keep the semantic and borrowing check artifacts that assess those outputs. The comparison command consumes these recorded runs and invokes automatic judges; it does not manufacture generation records or substitute for the writing workflow's hard gates.

Create an `avereth-commonplace-paired/v1` JSON file with:

- `synthetic: false`, an explicit preregistered `target`, and `tasks`, a frozen array of 5–10 records;
- each task's unique `id`, actual `task` instruction, and exactly two `cells`, `C` and `D`;
- each cell's `deep_reading: true`, `commonplace: false` for C or `true` for D;
- matched `question_sha256`, `evidence_sha256`, `mir_sha256`, `model_revision`, `budget` and `seed`;
- `writer_context_id`, unique across every generation, and the actual `prompt` and `output`;
- `inputs: {question, evidence, mir}`, `semantic_review` and `borrowing_check` bindings;
- `hard_checks` bindings for `claims_supported`, `protected_facts_preserved`, `citation_metadata_valid` and `task_completion`. The existing bound `semantic_review` artifact supplies the canonical `semantic_fidelity` result; it must contain the actual assessment, and missing evidence stays unknown.

Register the minimum improvement before generating either side. The real Commonplace target requires at least five pairs and a minimum win margin of 0.2 or greater:

```json
{
  "category": "prose",
  "metric": "pairwise_preference",
  "direction": "increase",
  "min_win_margin": 0.2,
  "min_pairs": 5
}
```

Win margin is `(candidate wins - baseline wins) / all selected pairs`. A close split such as 16:14 remains uncertain. `KEEP` reports `decision_basis: prose_gain`; it identifies the registered engineering benefit and does not prove overall scholarly quality. A missing target, unknown required check or unverified output prevents promotion.

Every binding is `{ "path": "workspace-relative-file", "sha256": "actual-file-sha256" }`, relative to the experiment file. Each assessment JSON binds `output_sha256` and its real `status`. `PASS` is required before prose judging. A verified new hard failure or task-completion regression rejects the candidate. Matching old hard failures remain visible without being mislabeled as new regressions, but unresolved hard errors cannot support a prose promotion. `REVIEW` or unknown status remains uncertain. Untrusted bindings take precedence over purported failures and cannot establish a rejection. Preserve detailed findings and actual review provenance inside the bound files. Hash verification establishes artifact consistency; it cannot authenticate a judgment that never occurred.

Additional schema or authorization checks may be supplied alongside the four required `hard_checks`, using the same output binding and status contract. A `trace` binding may provide `output_sha256` and actual `measurements`: `input_tokens`, `output_tokens`, `tool_calls`, `files_read`, `wall_time_seconds`, `retries`. Missing or invalid cost measurements remain `null`. Optional `metrics` may retain the ten research measures listed in `factorial.py`; none is required for engineering comparison, and none offsets a hard failure.

Choose the installed judge hosts and actual models in `judges.json`:

```json
{
  "primary": {"runner": "codex", "model": "YOUR_PRIMARY_MODEL", "family": "PRIMARY_FAMILY"},
  "secondary": {"runner": "claude", "model": "YOUR_SECONDARY_MODEL", "family": "DIFFERENT_FAMILY"},
  "swap_check_rate": 0.2
}
```

Replace the model and family placeholders with actual available settings. The secondary can use either supported host, but escalation requires a different model family. Hosts use their existing local authentication. The primary receives anonymous, randomly ordered outputs and may return either preference, `TIE` or `UNCERTAIN`. Swap checks sample position sensitivity; close, uncertain or flipped judgments escalate to the secondary. Position flips, inconsistent secondary judgments and recorded review failures remain uncertain even if another review prefers the candidate. Judge requests, raw responses, models, context IDs and telemetry are retained alongside the report.

```text
python evals/commonplace-writing/evaluate.py runs/commonplace.json --judge-config judges.json --output reports/commonplace-01.json
```

The shared decision logic is in `evals/lean-core-v7/paired_eval.py`. Reports bind the experiment and all validated question/evidence/MIR/prompt/output/assessment files. Existing report paths are preserved. The paired CLI exits with `0` for `KEEP`, `1` for `REJECT`, and `2` for `UNCERTAIN`, including invalid or unreadable inputs. `auto_promotion_eligible` can be true only for a real, bound comparison with a `KEEP` verdict; synthetic `KEEP` results still cannot promote. Automation must check eligibility before promotion. The command does not change production defaults or scientific gates.

## Optional manual/research experiment

Use the four-cell protocol only to investigate deep-reading/Commonplace interactions: A has neither factor, B only Commonplace, C only deep reading, D both. Keep final evidence identical across cells; deep-reading OFF changes the documented reading treatment, not the final evidence identity.

The `avereth-commonplace-factorial/v1` record retains all four `cells`, their matched conditions, bound artifacts and ten separate finite research metrics from `factorial.py`. Units and collection procedures should be fixed before running. It reports D-minus-C metric deltas for interpretation without granting promotion.

`blind_review` is optional. If supplied, preserve `label_to_cell` for anonymous C/D labels and a bound `artifact` with `preference` (anonymous label or `tie`), `reviewer_context_id`, `reviewer_kind` (`human`, `human_domain_expert` or `llm`), `input_scope: anonymous_C_D_outputs_only`, `rationale`, and `output_hashes` keyed by the anonymous labels. Keep the mapping out of the review context. The declaration must describe the actual assessment.

```text
python evals/commonplace-writing/evaluate.py research/factorial.json --manual-research --output reports/factorial-01.json
```

The manual/research CLI retains its validation exit codes: `0` for a valid report and `1` for incomplete or invalid input. These research exit codes do not authorize promotion.

## Offline regression

```text
python -m unittest discover -s skills/cnki-paper/scripts -p "test_commonplace*.py"
python -m unittest discover -s evals/commonplace-writing -p "test_*.py"
```

Tests use original synthetic material and injected synthetic judges. They verify the automatic engineering contract, hard failures, unchanged evidence, optional human review and retained manual protocol. Synthetic records can validate an implementation but are never eligible for promotion. Real model comparisons remain pending until actual recorded tasks and automatic judgments are collected; Commonplace remains off by default.
