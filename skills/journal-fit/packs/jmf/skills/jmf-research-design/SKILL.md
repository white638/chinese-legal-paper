---
name: jmf-research-design
description: Use when presenting an empirical-core research design in a Journal of Marriage and Family manuscript. This venue overlay controls family-science explanation and placement; it does not choose methods, diagnostics, thresholds, or repairs.
---

# Research Design (jmf-research-design)

JMF accepts quantitative, qualitative, and multi-method work but is demanding about each. The design
must connect the framework (`jmf-theory-and-conceptual-framework`) to evidence while respecting the
**unit of analysis** (individual, dyad, family, household, cohort) and the **non-independence** of
people who share a relationship. This skill is mode-aware: pick the section that fits your work.

## When to trigger

- Specifying the design, sample, measures, and identification strategy
- A reviewer questioned **selection**, causal claims, generalizability, or the handling of dyads
- Designing a longitudinal, dyadic, family-level, or comparative study
- Preparing a pre-analysis plan or planning a replication

## Quantitative — longitudinal / family-demography reporting
- Report the core target, unit, timing/event/risk-set definitions, counterfactual, selection assumptions,
  diagnostic and sensitivity Artifact IDs, dependence disposition, and observed ceiling. JMF does not
  choose the panel, event-history, demographic, or uncertainty procedure.

## Quantitative — dyadic & family-level reporting
- Report the core analysis/independence units, dyad/family dependence and measurement-validation
  records, diagnostic Artifact IDs, and dispositions under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` and
  `CORE.MEASUREMENT.REGISTERED_VALIDATION`.

## Experiment reporting (lab / survey / field)
- Report `CORE.EXPERIMENT.REGISTERED_DESIGN`, the dyad/family unit, diagnostics, deviations, Artifact
  IDs, and ceiling. Put ethics/IRB and consent materials where JMF policy requires them.

## Qualitative / multi-method reporting
- Report `CORE.QUAL.REGISTERED_SELECTION_EVIDENCE`, multi-perspective evidence mapping, integration
  records, Artifact IDs, and observed ceiling; do not define venue-local sampling or integration rules.

## The selection-and-interdependence test (JMF-specific)

Present the strongest rival, core-registered adjudication record, and dependence disposition. Missing
records return to empirical-research; JMF only determines placement and family-science interpretation.

## Design-defensibility table JMF referees apply

| Design feature | Vulnerable | Likely reviewer verdict |
|----------------|-----------|--------------------------|
| Unit of analysis | Person-rows for a couple-level question | "Unit mismatch — re-specify" |
| Selection rival | Asserted away | "Selection into family transitions" |
| Temporal structure | Cross-section for a dynamic process | "Cross-sectional claim about a dynamic process" |
| Non-independence | Independence assumed | "Dyadic dependence ignored" |

For the flagship journal of family science, the design section is judged on whether the *unit of analysis*
and *temporal leverage* fit the family process being theorized. JMF welcomes quantitative, qualitative, and
multi-method work, each on its own rigor bar.

## Worked micro-example (illustrative)

A study claims cohabitation "causes" lower relationship quality from one cross-sectional wave (illustrative).

- *Vulnerable:* a between-person snapshot where married respondents score 0.4 SD higher — read as selection
  (who marries) plus a cross-sectional claim about a process that unfolds over time.
- *Strengthened:* a panel tracking couples from cohabitation forward, using within-couple change as
  partners transition to marriage, the couple as the unit, members modeled via APIM. The estimand becomes
  *within-couple* change in dyadic quality (illustrative −0.08 SD). Adjudication: "If sorting drove this,
  gaps would predate cohabitation."

## Referee-pushback patterns and the design fix

- *"Selection into family transitions."* Show the core assumption/sensitivity disposition and ceiling.
- *"Dyadic dependence ignored."* Show `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; return a change to core.
- *"Cross-sectional claim about a dynamic process."* Show the core timing/target record and use prose
  within its observed ceiling.

*Calibration (hedged):* preregistration and unit-appropriate power are encouraged but evolving — confirm
against the journal's current author guidance.

## Anti-patterns

- Treating couple or family data as independent observations
- "Causal" language on an observational design with unaddressed selection
- Naive cross-sectional snapshots for inherently longitudinal family processes
- Ignoring panel attrition or differential dropout in family studies
- Convenience case selection dressed up as theory-driven

## Output format

```
【Mode】longitudinal-demographic / dyadic-family / experiment / qualitative-mixed
【Unit of analysis】individual / dyad / family / household / cohort
【Estimand or claim】what is being identified/shown
【Selection handled】the adjudication sentence
【Non-independence】how clustering/dyad structure is modeled
【Robustness/sensitivity】planned checks
【Next】jmf-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — dyadic/multilevel/survival packages and family datasets
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — JMF methods scope and replication guidance
