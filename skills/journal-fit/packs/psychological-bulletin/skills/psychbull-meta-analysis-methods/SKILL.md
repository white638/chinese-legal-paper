---
name: psychbull-meta-analysis-methods
description: Use when presenting an empirical-core research-synthesis contract in a Psychological Bulletin manuscript. This venue overlay applies MARS reporting and exhibit placement; it does not choose effect-size metrics, pooling models, dependence procedures, heterogeneity estimators, thresholds, or repairs.
---

# Meta-analysis Method Reporting (psychbull-meta-analysis-methods)

## Authority boundary

The empirical-research `systematic_review` family owns the synthesis target, eligibility/coding,
effect-size identity, dependence plan, synthesis model, heterogeneity/uncertainty procedures,
diagnostics, sensitivity analyses, and inference ceiling. Psychological Bulletin determines how those
core facts are reported under MARS. A missing or failed record returns to empirical-research.

## What to report

- Core family/profile and revision; synthesis target; effect-size and transformation identities.
- Study/effect dependence units, synthesis/weighting/heterogeneity procedure identities, software and
  version, and input/output Artifact IDs.
- Diagnostic, influence, sensitivity, missingness/bias, and moderator Artifact IDs with dispositions,
  including failures and the observed ceiling.
- `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`, `CORE.INFERENCE.MULTIPLICITY_PLAN`,
  `CORE.INFERENCE.SENSITIVITY_BINDING`, and `CORE.REPRO.STOCHASTIC_IDENTITY` where applicable.

## MARS presentation layer

Put the registered target, included-evidence identity, headline magnitude/uncertainty, key diagnostic
dispositions, and synthesis ceiling in the main text. Put complete coding, model, dependence,
heterogeneity, sensitivity, and reproduction records in the methods/supplement with exact Artifact
locators. The forest plot visualizes the core output; it does not select the model.

## Reviewer responses

| Concern | Venue-layer response |
|---|---|
| Effect-size metric is unclear | report the core metric/transformation identity and rationale record |
| Effects are dependent | report core dependence units, procedure, diagnostics, and disposition |
| Heterogeneity is hidden | report core heterogeneity outputs and inference consequence |
| Model change requested | return to empirical-research, revalidate, and cite the new revision |
| Sensitivity or bias concern | report the core-bound Artifact IDs, failures, and ceiling |

## Anti-patterns

- A Psychological Bulletin–local pooling model, effect-size rule, threshold, or repair
- Treating a forest plot or MARS checklist as scientific validation
- Omitting dependent effects, failed diagnostics, or a narrowed synthesis ceiling

## Output format

```text
【Core synthesis】family/profile + revision + target
【Effect identity】metric/transformation + Artifact IDs
【Dependence/model】registered identities + diagnostics/disposition
【Heterogeneity/sensitivity】core outputs + failures + ceiling
【Reproduction】driver + toolchain/stochastic identities
【MARS placement】main text / methods / supplement / repository
```

## Supplementary resources

- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — verify current MARS and submission requirements
