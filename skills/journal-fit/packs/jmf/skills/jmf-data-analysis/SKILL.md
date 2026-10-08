---
name: jmf-data-analysis
description: Use when reporting empirical-core analysis artifacts in a Journal of Marriage and Family manuscript. This venue overlay controls family-science interpretation and transparency placement; it does not choose analysis, dependence, missingness, diagnostics, or repairs.
---

# Data Analysis (jmf-data-analysis)

JMF reviewers are methodologically sophisticated and family data are tricky: complex-survey weights,
panel attrition, missingness, and the non-independence of partners and family members all bite. This
skill covers execution and reporting norms; design decisions live in `jmf-research-design`.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, selection checks, or alternative specifications
- Reconciling preregistered vs. exploratory analyses
- Making the analysis reproducible before deposit

## Analysis norms JMF expects

1. **Report uncertainty and magnitude honestly.** Confidence intervals and effect sizes (not stars
   alone); state the substantive size in family terms (months to divorce, percentage-point change in a
   transition, points on a relationship-quality scale).
2. **Selection disclosure.** Report the core target, selection assumptions, sensitivity Artifact IDs,
   dispositions, and observed ceiling.
3. **Dependence/event disclosure.** Report core weight/unit/dependence and event/risk-set identities,
   diagnostic Artifact IDs, and dispositions under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
4. **Missingness/attrition disclosure.** Report the core assumptions, implementation identity,
   sensitivity artifacts, disposition, and ceiling.
5. **Core-bound sensitivity.** Report `CORE.INFERENCE.SENSITIVITY_BINDING` records, including failures.
6. **Heterogeneity and multiplicity disclosure.** Report the core registered/exploratory labels and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; JMF does not choose a correction.

## Family-data specifics
- Report the analytic sample and how it was derived from the full dataset (eligibility, attrition,
  missingness) — reviewers will check the funnel.
- For dyadic or event-history routes, report the core target/unit/time/event/censoring records and
  diagnostics; JMF does not select the model.

## Reproducibility while you work (not at the end)
- Report the core driver and hashed outputs that regenerate every exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and stored toolchain/dependency identities.
- Keep table/figure numbers in the manuscript matched to script outputs.

## What JMF referees check in a results section

| Check | Passes review | Triggers a revision request |
|-------|---------------|------------------------------|
| Survey design | Core weight/strata/PSU identity, diagnostics, and disposition disclosed | Core sampling record or failure hidden |
| Non-independence | Core effective-unit/dependence identity and disposition disclosed | Partners' dependence record omitted |
| Selection | Core target, assumptions, sensitivity Artifacts, and ceiling disclosed | Claim language exceeds the core ceiling |
| Magnitude | Effect in family units (months to divorce) + CI | Stars only, no substantive size |

For the flagship journal of the National Council on Family Relations, the fastest desk-reject-adjacent
outcome is an analysis that ignores the survey design or the dependence built into couple and family data.

## Worked micro-example (illustrative)

A divorce-timing study reports the event-history contract selected by empirical-research. Its
illustrative results paragraph names the event/risk-set/censoring identities, the family effective
unit, the registered uncertainty and selection diagnostics, their Artifact IDs, and the observed
ceiling before interpreting the estimate in family-time units. The venue example does not select the
event model, dependence procedure, weighting implementation, or sensitivity repair.

## Referee-pushback patterns and the venue-specific fix

- *"Dyadic dependence ignored."* Report the core dependence failure and ceiling; return re-estimation to core.
- *"Selection into family transitions."* Report the core assumption/sensitivity disposition and ceiling.
- *"Survey design ignored."* Report the core sampling/dependence failure and return a method change to core.

*Calibration:* for family panels, cite provider documentation alongside the sampling, dependence, and
missingness identities selected by the core contract; no dataset name creates a venue-local default.

## Anti-patterns

- Stars-only tables with no effect sizes, intervals, or substantive interpretation
- Hiding the core sampling/dependence disposition or its inference-ceiling consequence
- Listwise deletion that silently changes the sample; ignoring attrition
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- A results section whose numbers the code cannot reproduce

## Output format

```
【Main estimate】magnitude + interval + substantive (family) meaning
【Selection check】(per research-design) result
【Data structure】weights/clusters/dyad-family non-independence handled? [Y/N]
【Missing data】MI/FIML + attrition probed? [Y/N]
【Robustness】specs that could break it → what held
【Reproducible】master script + seeds + pinned versions? [Y/N]
【Next】jmf-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, survey, dyadic, survival, and imputation packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — replication-detail and data expectations
