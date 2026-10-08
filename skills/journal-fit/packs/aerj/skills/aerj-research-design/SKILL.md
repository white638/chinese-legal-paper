---
name: aerj-research-design
description: Use when presenting an empirical-core research design in an American Educational Research Journal (AERJ) manuscript. This venue overlay applies AERA reporting and placement rules; it does not select methods, diagnostics, thresholds, or repairs.
---

# Research Design (aerj-research-design)

AERJ accepts many methodologies but is demanding about each. The design must credibly connect the
framework (`aerj-theory-and-framework`) to evidence and meet the relevant **AERA reporting standards**.
This skill is mode-aware: name the dominant education-research lens and defend it against the strongest
alternative explanation.

## When to trigger

- Specifying sampling, measurement, identification, case selection, or an integration plan
- A reviewer questioned causal claims, generalizability, trustworthiness, or measurement validity
- Preparing a **pre-analysis plan** / preregistration for a prospective design
- Justifying how the design addresses the rival account from `aerj-literature-positioning`

## Quantitative reporting
- Report the core-registered unit/nesting structure, target, measurement contract, assumptions,
  diagnostic Artifact IDs, uncertainty disposition, and observed ceiling under
  `CORE.CAUSAL.ESTIMAND_BINDING`, `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`, and
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` as applicable.
- For event-time panels, show `CORE.PANEL.STAGGERED_DESIGN` records. Report core measurement-validation
  and sampling/weighting records; AERJ does not choose an estimator or diagnostic.

## Qualitative reporting
- Report the core-registered case/site/participant rationale, scope, positionality/access metadata,
  competing account, negative evidence, claim-to-evidence map, Artifact IDs, and observed ceiling.
- Put the registered generation/coding/provenance records where AERA reporting standards request them;
  an absent record returns to empirical-research.

## Mixed-method reporting
- State the core-registered strand identities, integration rationale/point, cross-strand evidence map,
  Artifact IDs, and combined inference ceiling. AERJ controls the joint-display location, not the design.

## The adjudication test (AERJ-specific)

Present the strongest rival and core-registered adjudication record. If either is absent, return the
design to empirical-research; this overlay only determines placement and clarity.

## Anti-patterns

- Omitting a failed core nesting/dependence diagnostic or narrowed ceiling
- "Causal"/"effect" language on a descriptive or associational design
- Convenience sampling dressed up as theoretical sampling
- Mixed methods that never actually integrate
- Treating measurement validity or trustworthiness as boilerplate

## Design-credibility matrix (what each tradition must defend)

AERJ judges each methodology on its own terms, so the credibility bar differs by mode. Use this matrix
to locate the assumption a referee will press hardest.

| Mode | Core record to show | Reviewer-facing concern |
|------|---------------------|-------------------------|
| Experiment | target, units, deviations, diagnostics, ceiling | implementation and generalization |
| Quasi-experimental | counterfactual, assumption diagnostics, ceiling | whether the core supports the causal wording |
| Multilevel descriptive | nesting/dependence and measurement records | unit or construct mismatch |
| Qualitative | selection/scope and claim-evidence records | provenance and negative evidence |
| Mixed | strand and integration records | whether evidence is actually integrated |

## Worked design vignette (illustrative)

An AERJ team evaluating a peer-tutoring program names the core contract/revision, reproduces its target,
links its assumption and measurement Artifact IDs, reports each disposition and the observed ceiling,
and explains how the registered rival-adjudication record matters educationally. Missing evidence is
returned to empirical-research; the venue example does not prescribe a diagnostic or estimator.

## Referee pushback and the venue fix

- *"Causal language on an associational design."* → Report the observed core ceiling and use matching prose.
- *"Your sampling is convenience, not theoretical."* → Show the core selection/scope record; return an
  absent rationale to empirical-research.
- *"The mixed design is two papers stapled together."* → Show the core integration record and evidence map.

## Output format

```
【Mode】quant / qualitative / mixed
【Core contract】id + revision + registered target/claim and ceiling
【Core diagnostics】assumption / dependence / selection Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Standards】which AERA reporting standard the design meets
【Next】aerj-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — multilevel/IRT/causal packages and CAQDAS for qualitative work
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — AERA reporting standards + preregistration notes
