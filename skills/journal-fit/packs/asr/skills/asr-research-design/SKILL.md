---
name: asr-research-design
description: Use when presenting an empirical-core research design in an American Sociological Review (ASR) manuscript. This venue overlay controls disclosure and reviewer-facing explanation; it does not choose method logic, diagnostics, thresholds, or repairs.
---

# Research Design (asr-research-design)

ASR welcomes many methods but is exacting about each. The design must credibly link the argument
(`asr-theory-building`) to evidence and rule out the leading alternative. Pick the section matching
your method.

## When to trigger

- Specifying identification, case selection, sampling, or site/informant logic
- A reviewer questioned causal claims, generalization, selection, or a confound
- Justifying why your design adjudicates the rival account from `asr-literature-positioning`

## Quantitative / demographic reporting
- Report the core claim capability, registered estimand or target, assumption statuses, diagnostic
  artifacts, and observed ceiling. Do not redefine them in ASR prose.
- For causal panel work, cite `CORE.PANEL.STAGGERED_DESIGN`; for other causal work cite
  `CORE.CAUSAL.ESTIMAND_BINDING` and `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- Show the registered sampling/dependence and uncertainty records under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`, plus any core sensitivity disposition.

## Comparative-historical reporting
- Report the core-registered case-selection rationale, comparison/counterfactual, causal form, competing
  account, diagnostic evidence matrix, Artifact IDs, provenance, and observed ceiling.
- Explain those records to ASR reviewers; an absent design or diagnostic returns to empirical-research.

## Ethnographic / interview reporting
- Report the core-registered site/informant rationale, scope, positionality/access metadata, negative or
  disconfirming evidence, claim-to-evidence map, Artifact IDs, and observed ceiling.
- Put ethics/IRB, consent, and confidentiality documentation where `asr-data-and-transparency` requires it.

## Network / computational reporting
- Report the core boundary, dependence/generative-process identity, missingness assumptions, diagnostics,
  measurement-validation Artifact IDs, stability disposition, and observed ceiling.

## The adjudication test (ASR-specific)

Present the strongest rival and the core-registered adjudication record. If either is absent, return the
design to empirical-research; ASR only determines where and how clearly the record is shown.

## What ASR referees demand of each design

ASR judges every tradition rigorously on its own logic — the unifying ASA standard is a design that
connects argument to evidence and rules out the leading rival.

| Design | Referee's first demand | Core record to present |
|--------|------------------------|------------------------|
| Quant / demographic | "What does this identify?" | estimand/target, assumption diagnostics, sensitivity, ceiling |
| Comparative-historical | "Why these cases?" | selection rationale, comparison, rival-adjudication artifacts |
| Ethnographic | "Why this site and informants?" | selection/scope, positionality, negative-evidence map |
| Network / computational | "Principled process?" | boundary/dependence and measurement-validation artifacts |

## Worked micro-example (illustrative)

A comparative-historical study argues that labor-incorporation timing shaped later union strength
across four countries and presents the following registered core records.

```
Core contract: process-tracing/v1 + revision
Selection/scope: registered case rationale and population scope
Adjudication: competing-mechanism record + diagnostic evidence Artifact IDs
Disposition: observed inference ceiling, including failed or missing traces
```

The venue prose explains the registered rationale and evidence disposition; it does not define a new
selection rule or diagnostic test.

## Referee pushback → ASR-specific fix

- *"Association dressed as causation."* → Report the core inference disposition and its supporting or
  failed diagnostics; the venue response cannot add a method repair.
- *"Your cases look hand-picked."* → Show the core selection/scope record and Artifact IDs; return an
  absent rationale to empirical-research.

## Calibration anchors

- **Method-appropriate rigor, one disciplinary bar.** ASR won't hold ethnography to a regression
  standard or vice versa — but every design must defeat its strongest rival.
- **The adjudication sentence is the test.** If you can't write "if the rival were true the evidence
  would look like ___," the design does not yet earn the contribution.
- **Identification honesty travels.** Stating plainly what observational data can and cannot establish
  reads as strength to a cross-method panel.

## Anti-patterns

- "Causal" language on a purely observational/associational design
- Hiding a failed panel, sampling, or dependence diagnostic from the reader
- Omitting core case/site selection, scope, or negative-evidence records
- A design that cannot distinguish your mechanism from the leading alternative

## Output format

```
【Method】quant/demographic / comparative-historical / ethnographic / network-computational
【Core contract】id + revision + registered claim/target and ceiling
【Core diagnostics】assumption / selection / negative-evidence Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Sensitivity】core-bound record + outcome
【Next】asr-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design/analysis packages and CAQDAS/QCA tooling
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — ASR methodological breadth
