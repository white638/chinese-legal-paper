---
name: ajps-research-design
description: Use when presenting an empirical-research-validated design in an American Journal of Political Science (AJPS) manuscript. This venue overlay selects what reviewers must see; it does not choose estimators, assumptions, thresholds, or repairs.
---

# Research Design (ajps-research-design)

AJPS publishes many methods but holds identification and inference to a high standard. The design must
credibly connect the argument (`ajps-theory-building`) to evidence and rule out the strongest rival.
This skill is mode-aware: pick the section that matches your work and defend it on its own terms.

## When to trigger

- Specifying identification, sampling, case selection, or experimental design
- A reviewer questioned causal claims, a confound, external validity, or inference
- Preparing a **pre-analysis plan** before collecting/analyzing data
- Justifying why your design adjudicates the rival from `ajps-literature-positioning`

## Quantitative / causal inference reporting
- Report the registered estimand, counterfactual, assumptions, diagnostic statuses, sensitivity
  artifacts, and observed inference ceiling from `CORE.CAUSAL.ESTIMAND_BINDING` and
  `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- For panel or event-study work, identify the `CORE.PANEL.STAGGERED_DESIGN` contract and show its
  cohort, comparison, timing, diagnostic, and disposition records. AJPS does not select a replacement
  estimator inside this pack.
- Report the dependence and uncertainty records from `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`, and any
  registered multiplicity or sensitivity disposition from `CORE.INFERENCE.MULTIPLICITY_PLAN` and
  `CORE.INFERENCE.SENSITIVITY_BINDING`.

## Experiment reporting (lab / survey / field)
- Report the core-registered design, units, treatment, estimand, sampling/generalization ceiling,
  diagnostic Artifact IDs, deviations, and disposition. Missing design or diagnostic records return to
  empirical-research; AJPS does not define them here.
- Place human-subjects/IRB and consent documentation where the AJPS submission portal requests it (see
  `ajps-submission`). This is a venue policy, not a method-validity rule.

## Formal-empirical reporting
- State the core-registered target, model-to-evidence mapping, rival account, proof or diagnostic
  Artifact IDs, and observed ceiling. Explain that mapping to AJPS reviewers without adding a new test.

## Case-based / qualitative & multi-method reporting
- Report the core-registered case-selection rationale, scope, competing explanation, process-tracing
  evidence matrix, Artifact IDs, and observed inference ceiling. Do not define venue-local tests.
- Put source documentation in the locations required by `ajps-replication-and-verification`.

## The adjudication test (AJPS-specific)

Present the strongest rival explanation and the adjudication record already registered in the core
contract. If either is absent, return the design to empirical-research; the venue overlay only determines
where and how clearly the record is shown.

## Design-credibility reporting table

| Core record | Main text | Supplement / replication package |
|--------|--------------------------|-------------------------------------|
| Estimand and assumption identities | Exact registered target and bounded claim | Full typed contract |
| Diagnostic disposition | Decisive status and consequence | Hash-bound diagnostic artifacts |
| Dependence and uncertainty | Registered unit and reported uncertainty | Complete implementation record |
| Sensitivity or multiplicity | Material result and inference consequence | Full registered set, including failures |

## Worked reporting example

For a local-effect design, name the core contract and reproduce its registered estimand verbatim, then
show the assumption-diagnostic status, artifact locator, and resulting inference ceiling. The AJPS layer
may explain why those records matter to the rival account, but it cannot add a diagnostic or substitute
a different estimand.

## Referee-pushback patterns and the venue-specific fix

- *"Identification leans on selection-on-observables."* -> Surface the registered assumption,
  sensitivity artifact, and inference consequence; return an absent diagnostic to empirical core.
- *"Theory and empirics are not tightly linked."* -> Expose the core-registered model-to-evidence and
  rival-adjudication records; return a missing linkage to empirical-research.
- *"The panel implementation may not recover the registered target."* -> Cite the
  `CORE.PANEL.STAGGERED_DESIGN` disposition and its diagnostic artifacts; do not repair it in venue prose.

Calibration anchor: AJPS spans American, comparative, IR, theory, and methods, but applies a hard premium
on credible identification across all of them; confirm any human-subjects/IRB specifics against the
journal's current submission guidelines.

## Anti-patterns

- Hiding a failed panel or dependence diagnostic instead of reporting the core disposition
- "Causal" language on a design that supports only association
- Omitting the core case-selection or rival-adjudication record
- Survey/conjoint experiments over-generalized to real-world behavior with no caveat
- A design that cannot distinguish your argument from the leading alternative

## Output format

```
【Mode】quant-causal / experiment / formal-empirical / case-based
【Estimand or claim】what is being identified/shown
【Core assumption records】Artifact IDs + dispositions
【Rival adjudication】registered record + evidence locator
【Core inference records】dependence, uncertainty, multiplicity, sensitivity requirement IDs
【Diagnostics/disposition】Artifact IDs + retained/narrowed/withdrawn
【Next】ajps-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design/identification packages (R/Stata/Python) and CAQDAS for qualitative work
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — human-subjects / IRB requirements and submission policy
