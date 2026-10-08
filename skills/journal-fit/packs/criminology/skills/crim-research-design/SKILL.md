---
name: crim-research-design
description: Use when presenting an empirical-core research design for a Criminology (ASC / Wiley) manuscript. This venue overlay controls reporting and reviewer-facing explanation only; empirical-research owns method validity and execution.
---

# Research Design (crim-research-design)

*Criminology* accepts many methodologies but is demanding about each. The design must credibly connect
the mechanism (`crim-theory-building`) to crime evidence. This skill is mode-aware: pick the section
that matches your work and defend it against the strongest rival explanation.

## When to trigger

- Specifying identification, a longitudinal design, case selection, or an experiment
- A reviewer questioned causal claims, selection, the dark figure, or a confound
- Choosing between a trajectory model, fixed-effects panel, or survival design
- Justifying why your design adjudicates the rival theory from `crim-literature-positioning`

## Quantitative / causal inference reporting
- Report the registered estimand, counterfactual, assumptions, and observed inference disposition from
  `CORE.CAUSAL.ESTIMAND_BINDING` and `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- For panel or event-time work, identify the registered cohort, comparison, timing, and diagnostic
  artifacts from `CORE.PANEL.STAGGERED_DESIGN`; the venue does not select or repair the estimator.
- Report the units and uncertainty artifacts recorded under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`, plus any core-bound sensitivity disposition under
  `CORE.INFERENCE.SENSITIVITY_BINDING`.
- **Crime-data validity**: state which construct you measure — reported crime (UCR/NIBRS), victimization
  (NCVS), or self-report — and how the **dark figure** and reporting/recording bias affect inference.

## Longitudinal / life-course / criminal careers
- **Within- vs. between-person**: report which contrast the core contract identifies and keep the prose
  within its registered inference ceiling.
- **Trajectory / group-based models (GBTM, growth mixture)**: report the registered model identity,
  diagnostics, classification uncertainty, and sensitivity disposition under
  `CORE.MEASUREMENT.CLASSIFICATION_DIAGNOSTICS`. No venue-wide numeric cutoff selects a solution.
- **Survival / recidivism**: handle right-censoring and competing risks; distinguish timing from prevalence.
- **Criminal-career parameters**: separate onset, frequency (λ), seriousness, and desistance; do not let
  prevalence masquerade as incidence.

## Place-based & experimental reporting
- Surface the registered design, treatment/analysis units, diagnostic Artifact IDs, deviations, and
  observed ceiling. Ethics/IRB documentation remains a venue submission requirement.
- Explain how the core contract represents spatial interference or displacement; if it does not, return
  the missing requirement to empirical-research rather than defining it here.

## Qualitative / case-based reporting
- Report the registered case-selection rationale, scope, process-tracing contract, competing mechanism,
  diagnostic evidence matrix, Artifact IDs, and observed inference ceiling.
- Explain those core records in crime-specific terms and point readers to source documentation (see
  `crim-data-and-transparency`); do not create a venue-local process-tracing test.

## The adjudication test (Criminology-specific)

For the **single strongest rival theory**, write one sentence: *"If the rival mechanism were operating
instead of mine, the crime data would look like ___; instead they look like ___."* If you cannot, the
design does not yet identify the contribution.

## Anti-patterns

- Hiding a failed core timing or dependence diagnostic in a limitation paragraph
- "Causal" language on a design that only supports association
- Reading trajectory groups as real, fixed offender types
- Ignoring the dark figure / reporting bias when using official counts
- Convenience case selection dressed up as theory-driven

## Core-design reporting table

A *Criminology* submission names the threat reviewers are trained to raise and points to the empirical
core record that adjudicates it. The venue overlay does not prescribe a universal repair.

| Design context | Reviewer-facing threat | Core record to report |
|--------|------------------------|------------------------|
| Hot-spot / policing experiment | spillover or contamination | registered counterfactual, interference assumption, and diagnostics |
| Staggered deterrence policy | timing and comparison validity | `CORE.PANEL.STAGGERED_DESIGN` disposition and artifacts |
| Life-course turning point | within-/between-person mismatch | registered estimand, unit, and sensitivity disposition |
| Sentencing threshold | discontinuity assumptions | `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS` evidence and inference ceiling |

## Worked micro-example: a deterrence-policy quasi-experiment (illustrative)

A state raises a sentencing penalty in some counties before others. The submission reports the core
contract's estimand, timing cohorts and comparison definition; links the registered pre-treatment and
dependence diagnostics; gives their disposition; and reproduces the estimate from a hashed artifact.
It also explains how an NIBRS transition could affect the construct. If a core diagnostic fails, the
prose adopts the core's narrowed inference ceiling instead of choosing a venue-specific fix.

## Design-stage referee pushback (with the Criminology fix)

- *"Selection into treatment/offending."* Response: cite the registered assumption, diagnostic artifact,
  and core disposition; return any proposed redesign to empirical-research.
- *"Association, not causation."* Response: report the registered estimand and observed inference ceiling,
  and narrow the prose when the core does not support a causal reading.
- *"Official-records bias unaddressed."* Fix: name reported vs. victimization vs. self-report and the dark-figure bias.
- *"Dependence is unaddressed."* Response: expose the units and uncertainty disposition stored under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; a method change is a core-contract revision.

## Output format

```
【Mode】quant-causal / longitudinal-life-course / place-experiment / qualitative
【Core contract】id + revision + registered estimand/claim (and within- vs. between-person)
【Crime measure】reported / victimization / self-report + dark-figure note
【Core diagnostics】assumption/dependence/measurement Artifact IDs + disposition
【Rival ruled out】the adjudication sentence
【Inference ceiling】observed ceiling + core-bound sensitivity disposition
【Next】crim-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — trajectory/survival/spatial packages and longitudinal datasets
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — Criminology scope and methodological breadth
