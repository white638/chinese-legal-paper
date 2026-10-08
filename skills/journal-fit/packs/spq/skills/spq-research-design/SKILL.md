---
name: spq-research-design
description: Use when presenting an empirical-core research design in a Social Psychology Quarterly manuscript. This venue overlay controls structure–individual explanation and placement; it does not choose methods, diagnostics, thresholds, or repairs.
---

# Research Design (spq-research-design)

SPQ accepts experiments, surveys, and observational/interpretive work, but is demanding about each. The
design must credibly connect the social-psychological argument (`spq-theory-building`) to evidence about
the **structure–individual link**. This skill is tradition-aware: pick the section that matches your work
and defend it against the strongest alternative explanation.

## When to trigger

- Specifying an experimental setting, a survey/measurement plan, or a fieldwork/interview design
- A reviewer questioned causal claims, construct validity, case/site selection, or a confound
- Justifying why your design adjudicates the rival account from `spq-literature-positioning`
- Deciding how the design operationalizes the social-psychological mechanism

## Experiment reporting (group processes, status, exchange)
- Report `CORE.EXPERIMENT.REGISTERED_DESIGN`: setting/construct mapping, target, units, diagnostics,
  deviations, Artifact IDs, and observed generalization ceiling.
- **Inference reporting**: show the core target, registered/exploratory labels, diagnostics,
  `CORE.INFERENCE.MULTIPLICITY_PLAN`, dependence disposition, and observed ceiling.
- Explain the core-registered scope and ceiling when moving from the setting to real contexts.

## Survey / secondary-data reporting
- Report the core measurement-validation, structural-variable role, sampling/dependence, sensitivity,
  diagnostic Artifact IDs, and observed ceiling under `CORE.MEASUREMENT.REGISTERED_VALIDATION` and
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.

## Observational / interpretive reporting
- Report `CORE.QUAL.REGISTERED_SELECTION_EVIDENCE`, reflexivity/access metadata, negative evidence,
  claim-to-evidence Artifact IDs, and observed ceiling. Put consent materials where venue policy requires.

## The adjudication test (SPQ-specific)

Present the strongest rival and its core-registered adjudication record. Missing records return to
empirical-research; SPQ only determines placement and structure–individual interpretation.

## Design stress ledger

Use a design stress ledger before committing to the analysis plan:

| Tradition | Stress test |
|-----------|-------------|
| Experiment | What manipulation failure, demand effect, group-composition imbalance, or dyadic dependence would overturn the status/process claim? |
| Survey / secondary data | Which omitted structural variable, measurement-invariance failure, weighting choice, or contextual clustering rule could flip the conclusion? |
| Observational / interpretive | Which negative case, deviant interaction, or access/reflexivity concern would force a narrower interpretation? |

For each row, report the diagnostic already registered in core, its Artifact ID, disposition, and
inference consequence. A new diagnostic is a core-contract revision.

## Anti-patterns

- A lab effect over-generalized to real-world structure with no caveat
- Treating structural variables as nuisance controls rather than theorized causes
- Convenience site selection dressed up as theory-driven
- "Causal" language on a cross-sectional survey that only supports association
- A design that cannot distinguish your social-psychological mechanism from the leading alternative

## Output format

```
【Tradition】experiment / survey-SSP / observation-interpretive
【Estimand or analytic claim】what is identified/shown about the structure–individual link
【Key assumption(s)】and how each is defended
【Rival ruled out】the adjudication sentence
【Measurement / setting validity】constructs validated or setting standardized? [Y/N]
【Robustness/sensitivity】planned checks
【Next】spq-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — experimental, survey, measurement, and CAQDAS tooling by tradition
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — SPQ scope and methods breadth
