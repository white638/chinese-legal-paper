---
name: apsr-research-design
description: Use when presenting and defending an already registered core research design in an American Political Science Review (APSR) manuscript. This venue overlay determines what readers and reviewers need to see; it does not choose, repair, or validate the method.
---

# Research Design (apsr-research-design)

APSR accepts many methodologies. This overlay translates the confirmed `empirical-research` contract,
its diagnostic artifacts, and its observed inference ceiling into an APSR-facing design account. It
does not create an APSR-specific estimand, estimator, identification rule, robustness battery, or
method exception.

## When to trigger

- Preparing the manuscript or appendix account of a confirmed design
- A reviewer questioned causal claims, case choice, external validity, or a confound
- Reporting a **pre-analysis plan** or **Registered Report** link and its registered deviations
- Showing how the registered design bears on the rival account from `apsr-literature-positioning`

## Quantitative / causal inference reporting

- Name the registered core contract ID/revision and report its estimand, unit fields, counterfactual,
  identification-assumption statuses, inference disposition, and artifact locators.
- For `causal-panel/v1`, report the registered treatment cohorts, comparison group, pre-treatment
  window, parallel-trends result, clustering plan, timing checks, placebo plan, and diagnostic
  locations. Do not use this overlay to choose or replace an estimator.
- Surface core failures rather than repairing them in prose. Relevant core requirement/failure IDs
  include `ME.INFERENCE.ESTIMAND_MISSING`, `ME.INFERENCE.COUNTERFACTUAL_MISSING`,
  `ME.INFERENCE.ASSUMPTIONS_MISSING`, `ME.INFERENCE.PANEL_CONTRACT_INCOMPLETE`,
  `ME.INFERENCE.PARALLEL_TRENDS_FAILED`, and
  `ME.INFERENCE.DIAGNOSTIC_FAILED_NOT_NARROWED`.
- Put concise design identity and the observed inference ceiling in the article; put full diagnostics,
  sensitivity artifacts, and registered deviations in the appendix or reproducibility package.

## Qualitative / case-based reporting

- Report the registered case universe, selection rationale, scope conditions, comparison identity,
  and any deviations from the confirmed `case_design` record.
- For `process-tracing/v1`, show the registered mechanism, strongest rival, predicted traces,
  diagnostic matrix, source-independence artifact, negative evidence, and inference boundary.
  `ME.PROCESS_TRACING.RIVAL_UNTESTED` or another failed core diagnostic must remain visible.
- Use `apsr-transparency-and-data-policy` only to decide how archives, interviews, fieldnotes, access
  restrictions, and evidence tables are presented or deposited.

## Experiment reporting

Report the core experiment route's assignment mechanism, verification artifact, outcome timing,
attrition/noncompliance/interference records, preregistration identity, ethics record, deviations, and
observed inference ceiling. Whether any diagnostic is scientifically sufficient remains a core method
and evidence-backed researcher judgment, not an APSR overlay decision.

## Formal-empirical linkage reporting

Map each manuscript prediction to the registered Claim, Evidence, route, result, and scope identities.
Explain which links are shared with rivals and which are discriminating, without inventing a new
validation rule in this pack.

## Rival-account presentation

Summarize the strongest rival and discriminating observation already registered by the core design.
If that record is missing or unresolved, return the issue to the parent workflow; do not manufacture an
APSR-only adjudication test.

## Core method-contract bridge

The venue-facing document may require the reader to see core fields and diagnostics, but this overlay
does not choose an estimator, define an assumption, set a diagnostic threshold, or execute an engine.
Bind every statement to the confirmed typed contract and hashed artifact. If the core validator lowers
the observed inference ceiling, the APSR-facing claim narrows with it.

## Anti-patterns

- Omitting the core contract ID/revision, inference disposition, or failed diagnostic
- Restating an estimand or assumption differently from the registered core value
- Naming a preferred estimator or repair in the venue pack instead of returning to the core contract
- Hiding case changes, negative evidence, preregistration deviations, or scope revisions in prose
- Using APSR preference to restore a Claim that exceeds the observed inference ceiling

## Output format

```
【Core contract】ID + revision + route/result IDs
【Estimand or claim】exact registered value/reference
【Assumptions/diagnostics】statuses + Artifact IDs + article/appendix locations
【Rival account】registered rival + discriminating evidence reference
【Inference disposition】retained/narrowed/withdrawn + observed ceiling
【Transparency】deviations, negative evidence, scope changes, deposit location
【Return】parent workflow owns the next action
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design/identification packages (R/Stata/Python) and CAQDAS for qualitative work
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — preregistration and Registered Reports notes
