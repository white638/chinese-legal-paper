---
name: poq-data-analysis
description: Use when reporting empirical-core survey-analysis artifacts in a Public Opinion Quarterly manuscript. This venue overlay controls disclosure and replication placement; it does not choose estimators, weighting, missingness, uncertainty, diagnostics, or repairs.
---

# Data Analysis (poq-data-analysis)

POQ reviewers are methodologically sophisticated, and the journal requires replication materials that
**reproduce exactly all published tables and figures** (see `poq-transparency-and-data-policy`). This
overlay reports the sampling, weighting, dependence, and uncertainty facts already registered by
empirical-research; it does not decide how those facts enter an estimator. Design decisions live in the
core method contract.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for design-based SEs, robustness, or alternative weighting
- Reconciling preregistered vs. exploratory analyses
- Making the analysis reproducible before deposit

## Analysis norms POQ expects

1. **Sampling/dependence disclosure.** Report the core weight, strata/PSU/effective-unit, uncertainty
   implementation, diagnostic Artifact IDs, and disposition under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
2. **Report uncertainty honestly.** Confidence intervals, not just stars; the magnitude and
   substantive meaning of the estimate. For opinion shares, show the margin of error and the
   definition of precision.
3. **Weighting disposition.** Report the core weighting identity, diagnostics, sensitivity artifacts,
   and inference consequence.
4. **Core-bound sensitivity.** Report `CORE.INFERENCE.SENSITIVITY_BINDING` Artifact IDs, failures, and
   resulting ceiling.
5. **Heterogeneity and multiplicity disclosure.** Report the core registered/exploratory labels and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; POQ does not choose a correction.
6. **Measurement disclosure.** Report `CORE.MEASUREMENT.REGISTERED_VALIDATION` artifacts, source/scaling
   sensitivity, disposition, and observed ceiling.

## Missing data, nonresponse & trends
- Report the core missingness/nonresponse assumptions, implementation identity, sensitivity artifacts,
  and disposition. For trends, report the core wording/mode continuity record and any break.

## Reproducibility while you work (not at the end)
- Report the core driver and hashed outputs that regenerate every exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and stored toolchain/dependency identities.
- Keep table/figure numbers matched to script outputs — POQ re-runs the package against the exhibits.

## POQ replication reporting check

Before writing results prose, locate the following core records for journal disclosure:

| Gate | Required evidence |
|------|-------------------|
| Survey design record | Core weight/dependence/missingness identities and Artifact IDs. |
| Table/figure manifest | Every exhibit points to core inputs and hashed outputs. |
| Sensitivity disposition | Core-bound weighting/nonresponse/mode/multiplicity records, including failures. |
| Exact reproduction | Core reproduction command regenerates published numbers with matching rounding. |

Only claim reproducibility when these records and outputs match. A missing or failed scientific record
returns to empirical-research; this venue check cannot repair it.

## Anti-patterns

- Hiding a core dependence/uncertainty failure or omitting its ceiling consequence
- Stars-only tables with no effect sizes, intervals, or margins of error
- Describing weights/design without reporting their registered uncertainty disposition
- p-hacking / HARKing exploratory subgroup results into hypotheses
- A results section whose numbers the deposited code cannot reproduce

## Output format

```
【Core analysis】contract/revision + weight/strata/PSU/effective-unit identities
【Main estimate】magnitude + interval/MOE + substantive meaning
【Sampling/dependence】core identity + diagnostic disposition + Artifact IDs
【Sensitivity】core-bound Artifact IDs → what held/failed
【Heterogeneity】core registered/exploratory + multiplicity disposition
【Reproducible】core driver + stochastic/toolchain identities? [Y/N]
【Next】poq-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — complex-survey estimation, weighting, imputation packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — reproducibility / replication-archive policy
