---
name: spq-data-analysis
description: Use when reporting empirical-core analysis artifacts in a Social Psychology Quarterly manuscript. This venue overlay controls presentation and transparency placement; it does not choose analysis, measurement, uncertainty, or repair procedures.
---

# Data Analysis (spq-data-analysis)

SPQ reviewers are sophisticated about both social-psychological measurement and the methods of each
tradition. Analyze and report so an expert can trust the result and see the **structure–individual link**
in the numbers (or the interpretation). This skill covers execution and reporting norms; design decisions
live in `spq-research-design`.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, alternative measures, or model checks
- Reconciling preregistered (where used) vs. exploratory analyses
- Reporting measurement quality for latent social-psychological constructs

## Analysis norms SPQ expects

1. **Report uncertainty honestly.** Confidence/credible intervals, not just stars; the **magnitude** and
   substantive meaning of the estimate, in the metric of the construct, not just significance.
2. **Measurement disclosure.** Report `CORE.MEASUREMENT.REGISTERED_VALIDATION` Artifact IDs,
   dispositions, scaling/source sensitivity, and observed ceiling.
3. **Core-bound sensitivity.** Report `CORE.INFERENCE.SENSITIVITY_BINDING` records, including failures.
4. **Dependence and multiplicity.** Report `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` identities and dispositions.
5. **Heterogeneity/mechanism labels.** Preserve the core registered/exploratory classification and
   report target, assumptions, diagnostics, and inference ceiling.

## Interpretive / qualitative specifics
- Present the core coding identity, negative evidence, claim-evidence map, and Artifact IDs so reviewers
  can trace the interpretation.

## Structure-individual reporting check

For each main result, add one sentence that links the statistic or qualitative pattern back to the
structure-individual mechanism. SPQ results should not stop at "the coefficient is positive" or "a
theme appears"; they should say how status, identity, exchange, networks, institutions, or interaction
orders shape individual meaning or behavior. If that sentence cannot be written, the analysis has
drifted away from the journal's social-psychological core.

## Reproducibility while you work (good practice, not a gate)
- Report the core driver and hashed outputs that regenerate every exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and stored toolchain/dependency identities.
- Keep table/figure numbers matched to outputs. SPQ **encourages** sharing materials but does not require
  it (see `spq-data-and-transparency`) — still analyze reproducibly for your own sake and the reviewers'.

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- Reporting an effect on a construct whose reliability/validity is never shown
- "Robustness" that only reruns near-identical specs to manufacture stability
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- Hiding a failed core dependence/weighting diagnostic or its inference-ceiling consequence
- Quoting one vivid excerpt as if it established a pattern (interpretive work)

## Output format

```
【Main estimate / claim】magnitude + interval (or analytic claim) + substantive meaning
【Measurement】reliability/validity of key constructs reported? [Y/N]
【Core inference】dependence/multiplicity Artifact IDs + disposition
【Sensitivity】core-bound records → what held/failed
【Heterogeneity】core registered/exploratory + ceiling
【Reproducible】core driver + stochastic/toolchain identities? [Y/N]
【Next】spq-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, measurement (SEM/reliability), and CAQDAS packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — data-and-materials policy (encouraged, not required)
