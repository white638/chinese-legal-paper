---
name: io-research-design
description: Use when presenting an empirical-core design in an International Organization (IO) manuscript. This venue overlay controls reviewer-facing disclosure and verification placement; it does not choose estimators, assumptions, diagnostics, thresholds, or repairs.
---

# Research Design (io-research-design)

IO accepts quantitative, formal, and qualitative IR work but is demanding about each. The design must
credibly connect the **IR theory** (`io-theory-building`) to evidence at or across the **international
level**, and rule out the strongest rival international explanation. This skill is mode-aware: pick the
section that matches your work.

## When to trigger

- Specifying identification, case selection, or experimental design for an IR question
- A reviewer questioned causal claims, the level of analysis, generalization, or a confound
- Preparing a pre-analysis plan for a foreign-policy experiment
- Justifying why the design adjudicates the rival IR account from `io-literature-positioning`

## Quantitative / causal inference reporting (often dyadic, TSCS, or network)
- Report the registered unit, estimand, counterfactual, assumptions, diagnostic Artifact IDs, and
  observed ceiling under `CORE.CAUSAL.ESTIMAND_BINDING` and
  `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- For event-time panels, show the cohort/comparison/timing records and diagnostic disposition from
  `CORE.PANEL.STAGGERED_DESIGN`; IO does not select a replacement estimator.
- Explain dyadic, network, spatial, or temporal dependence using the units and uncertainty artifacts
  registered under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- Report only core-bound sensitivity evidence under `CORE.INFERENCE.SENSITIVITY_BINDING`; return a
  missing requirement or proposed redesign to empirical-research.

## Qualitative / case-based reporting (international cases)
- Report the core-registered case-selection rationale, scope, competing mechanism, process-tracing
  evidence matrix, Artifact IDs, and observed inference ceiling; do not define IO-local tests.
- Put archive, diplomatic-record, and interview documentation where IO transparency policy requests it
  (see `io-transparency-and-data-policy`).

## Experiment reporting (survey / conjoint / lab on foreign-policy attitudes)
- Report the core-registered design, units, treatment, estimand, sampling/generalization ceiling,
  diagnostics, deviations, and disposition. An absent item returns to empirical-research.
- Explain the registered scope and ceiling when connecting survey responses to state behavior.

## Formal-empirical reporting
- Report the core-registered model-to-evidence mapping, rival account, proof/diagnostic Artifact IDs,
  and observed ceiling. Put the complete proof artifact in the appendix IO verifies.

## The adjudication test (IO-specific)

Present the strongest rival and its core-registered adjudication record. If either is absent, return the
design to empirical-research; IO only determines where and how clearly the record is shown.

## Worked design vignette (illustrative): a treaty-ratification design

Claim: ratifying an international monitoring treaty raises later compliance. The IO presentation names
the core contract and revision, reproduces its estimand, and links the timing, comparison, dependence,
selection, and sensitivity Artifact IDs with their dispositions. The prose explains how those registered
records adjudicate selection into membership and states the observed inference ceiling. It neither picks
an estimator nor invents a new diagnostic in the venue layer.

## Identification-threat table (IR-specific confounds and the design answer)

| Threat | Where it appears | Core record to report |
|--------|------------------|-----------------------|
| Selection into treaty/alliance/IO membership | compliance, cooperation studies | registered counterfactual, assumption diagnostics, and sensitivity disposition |
| Dyadic / network non-independence | dyad- or network-level outcome | `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` units and uncertainty artifacts |

## Anti-patterns

- Omitting a failed dependence, selection, or timing diagnostic from the core record
- A domestic-level design used to support an international-level claim (level mismatch)
- "Causal" language on a design that only supports association across states
- Convenience case selection dressed up as theory-driven
- Over-generalizing survey-experiment attitudes to real state behavior with no caveat
- Treating treaty membership as exogenous when ratification is plainly a choice

## Output format

```
【Mode】quant-causal / qualitative / experiment / formal-empirical
【Level of analysis】unit + why it matches the IR theory
【Core contract】id + revision + registered estimand/claim
【Core diagnostics】assumption/dependence/timing Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Inference ceiling / proof appendix】observed ceiling + verified artifact location
【Next】io-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — dyadic/network/gravity packages and CAQDAS for qualitative IR
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — formal-proof and quantitative-result verification policy
