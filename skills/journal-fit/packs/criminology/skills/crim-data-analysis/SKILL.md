---
name: crim-data-analysis
description: Use when reporting empirical-core analysis artifacts for a Criminology (ASC / Wiley) manuscript. This venue overlay does not select estimators, thresholds, or inferential repairs.
---

# Data Analysis (crim-data-analysis)

*Criminology* reviewers are methodologically sophisticated and increasingly expect that your results
can be reproduced from deposited materials (see `crim-data-and-transparency`). Analyze as if both are
true. This skill covers execution and reporting norms; design decisions live in `crim-research-design`.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, or alternative specifications
- Fitting a trajectory model, fixed-effects panel, count model, or survival model
- Making the analysis reproducible before deposit

## Analysis reporting norms Criminology expects

1. **Report uncertainty honestly.** Confidence/credible intervals, not just stars; the **magnitude and
   substantive meaning** (e.g., incident-rate ratios, predicted counts, change in offending), not just
   significance.
2. **Expose the registered model.** Report its outcome support, link/exposure treatment, assumptions,
   diagnostics, and observed disposition; do not select a model from a venue decision table.
3. **Within- vs. between-person.** Name the core estimand and state which contrast each displayed result
   represents; do not widen the registered inference ceiling.
4. **Trajectory models with discipline.** Report the registered solution, classification uncertainty,
   diagnostics, and sensitivity artifacts under `CORE.MEASUREMENT.CLASSIFICATION_DIAGNOSTICS`; no
   universal venue cutoff determines acceptability.
5. **Survival / recidivism.** Report the core event definition, censoring/competing-event assumptions,
   diagnostics, and the corresponding estimand rather than substituting a binary summary.
6. **Robustness that probes, not decorates.** Present the sensitivity analyses actually bound to core
   assumptions under `CORE.INFERENCE.SENSITIVITY_BINDING` and disclose failures.
7. **Dependence and uncertainty.** Report units and uncertainty artifacts registered under
   `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; the venue overlay does not choose a procedure.

## Crime-measurement specifics
- State whether the outcome is reported crime, victimization, or self-report, and how the **dark figure**,
  reporting, and recording changes (e.g., UCR→NIBRS transition) could bias trends.
- Report the registered scale/construct validation Artifacts, disposition, and inference consequence
  under `CORE.MEASUREMENT.REGISTERED_VALIDATION`; Criminology does not choose the validation procedure.

## Reproducibility while you work (not at the end)
- One **master script** regenerates every table and figure from the (raw or constructed) data.
- **Report stochastic identities** recorded under `CORE.REPRO.STOCHASTIC_IDENTITY` for every stochastic step.
- Pin software/package versions (`renv.lock`, `requirements.txt`, recorded `ssc`/`net`/`traj` installs).
- Keep table/figure numbers matched to script outputs; document restricted-data steps that others can't rerun.

## Anti-patterns

- OLS on raw, over-dispersed crime counts; ignoring exposure/offsets
- Stars-only tables with no rate ratios, effect sizes, or intervals
- Treating trajectory groups as literal offender types; cherry-picking the group count
- Reading a between-person coefficient as within-individual desistance
- "Robustness" that only reruns near-identical specs; p-hacking a significant interaction

## Core analysis record by crime outcome

*Criminology* reviewers will name a mismatch between an outcome and its model. Present the model already
registered and validated by empirical-research, its diagnostic artifacts, and its observed disposition.
Changing the model revises the core contract; this table only tells authors what to disclose.

| Outcome context | Core facts to report | Reviewer-facing interpretation |
|---------------|-------------------|---------------------|
| Offense counts or rates | registered support/link/exposure, diagnostics, estimate artifact | what the quantity means in crime terms |
| Excess zeros | registered zero-process construct and diagnostic disposition | avoid reifying a computational component |
| Repeated within-person offending | estimand and within-/between-person mapping | identify which contrast supports the claim |
| Time-to-recidivism | event, risk set, censoring/competing-event assumptions and diagnostics | interpret the registered time-to-event estimand |
| Developmental offending paths | model identity, class uncertainty, sensitivity, inference ceiling | treat groups as summaries rather than literal types |

## Worked micro-example: reading a within-person estimate (illustrative)

Suppose a hybrid model returns an incident-rate ratio of 0.62 on the within-person "employed" indicator
(illustrative): entering employment maps to roughly a 38% lower offending rate *for the same person*,
95% CI [0.49, 0.78], net of stable traits. The between-person column, IRR 0.80, is weaker and reading
it as desistance would conflate selection (people prone to desist also find work) with the within-person
change the life-course claim requires. Report both; tell the reader which identifies the mechanism.

## Analysis-stage referee pushback (with the Criminology fix)

- *"Official-records bias is unaddressed."* Fix: state whether the outcome is arrest, victimization, or self-report, and how the dark figure and UCR→NIBRS recording shifts could bias it.
- *"Between-person read as within-person."* Response: map each column to the registered estimand and
  keep the prose within the core inference ceiling.
- *"Robustness only decorates."* Response: report the core-bound sensitivity tests, including failures.

## Output format

```
【Main estimate】magnitude (IRR / predicted count / hazard) + interval + substantive meaning
【Crime measure】reported / victimization / self-report + dark-figure caveat
【Within vs between】isolated correctly? [Y/N/NA]
【Core diagnostics】outcome support / censoring / classification Artifact IDs + disposition
【Sensitivity】core-bound checks → what held/failed
【Reproducible】master script + stochastic identities + pinned versions? [Y/N]
【Next】crim-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — count, trajectory, survival, and spatial packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — transparency expectations and crime-data sources
