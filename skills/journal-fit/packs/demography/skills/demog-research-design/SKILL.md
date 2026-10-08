---
name: demog-research-design
description: Use when presenting an empirical-core demographic design in a Demography (PAA / Duke University Press) manuscript. This venue overlay controls disclosure and reviewer-facing explanation; it does not choose demographic methods, assumptions, diagnostics, thresholds, or repairs.
---

# Research Design (demog-research-design)

Demography accepts a wide variety of methodological approaches but is demanding about each. The design
must credibly connect the argument (`demog-theory-building`) to the demographic evidence. This skill is
method-aware: pick the section that matches your question and defend it against the strongest rival
explanation.

## When to trigger

- Choosing the demographic method that actually answers the question
- A reviewer questioned the rate construction, the identification, or the projection assumptions
- Specifying an age-period-cohort, multistate, or microsimulation design
- Justifying why your design adjudicates the rival account from `demog-literature-positioning`

## Report how the registered method matches the question

- For life-table, decomposition, event-history, APC, multistate, simulation, or projection work, report
  the core contract ID/revision, target quantity, time scale, population/exposure, component or event
  definitions, assumptions, diagnostic/sensitivity Artifact IDs, and observed ceiling.
- Explain period/cohort, competing-event, transition, constraint, or base-population records in
  demographic terms. A missing design or diagnostic returns to empirical-research.

## When the registered question is causal
- Report the core estimand, counterfactual, assumptions, diagnostic dispositions, and ceiling under
  `CORE.CAUSAL.ESTIMAND_BINDING` and `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- Explain mortality/migration selection and differential exposure through the registered assumption
  and sensitivity artifacts. Report units and uncertainty under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`
  and core-bound sensitivity under `CORE.INFERENCE.SENSITIVITY_BINDING`.

## The adjudication test (Demography-specific)

Present the strongest rival and its core-registered adjudication record. If either is absent, return the
design to empirical-research; Demography only determines placement and clarity.

## Anti-patterns

- Omitting the core target/method-match record or an identifying constraint
- Period rates read as cohort experience (or vice versa) without justification
- Ignoring mortality/migration selection in a survival or panel design
- Projections whose assumptions are buried instead of varied and reported

## Output format

```
【Method】life table / decomposition / event history / APC / multistate / microsim / projection / causal
【Core contract】id + revision + target quantity/estimand + population/time scale
【Core diagnostics】assumption / exposure / event / constraint Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Inference ceiling】observed ceiling + core-bound sensitivity disposition
【Next】demog-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — life-table, decomposition, survival, APC, and microsimulation packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — Demography scope and methodological breadth
