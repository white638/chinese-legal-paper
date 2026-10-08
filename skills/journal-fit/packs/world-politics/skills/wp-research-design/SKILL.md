---
name: wp-research-design
description: Use when presenting an empirical-core research design in a World Politics manuscript. This venue overlay controls disclosure and reviewer-facing explanation only; it does not choose methods, diagnostics, thresholds, or repairs.
---

# Research Design (wp-research-design)

World Politics asks every article to "be explicit about its research design and use appropriate
methods," and applies separate expectations to quantitative and qualitative work. Because the journal
values **arguments that travel across cases**, the design must connect a portable argument
(`wp-theory-building`) to evidence in a way that **rules out the strongest cross-case rival**. This
skill is mode-aware: pick the section that matches your work.

## When to trigger

- Specifying case selection, identification, or experimental design for a cross-case question
- A reviewer questioned causal claims, case choice, external validity, or a confound
- Justifying why your design adjudicates the rival account from `wp-literature-positioning`

## Comparative-historical & case-based reporting
- Report the core-registered case-selection rationale, comparison logic, scope, competing explanation,
  process-tracing evidence matrix, Artifact IDs, and observed ceiling. Do not define venue-local tests.
- Explain how the registered evidence supports a claim that travels across cases; return a missing scope
  or diagnostic record to empirical-research.

## Quantitative / cross-national reporting
- Report the registered estimand, counterfactual, assumptions, diagnostic Artifact IDs, and observed
  ceiling under `CORE.CAUSAL.ESTIMAND_BINDING` and `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- For event-time panels, show the cohort/comparison/timing records and disposition from
  `CORE.PANEL.STAGGERED_DESIGN`; World Politics does not select a replacement estimator.
- Explain TSCS, network, or other dependence using the units and uncertainty artifacts registered under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`, and report core-bound sensitivity evidence under
  `CORE.INFERENCE.SENSITIVITY_BINDING`.

## Experiment & formal-empirical reporting
- Report the core-registered design/model-to-evidence mapping, units, target, diagnostics, deviations,
  Artifact IDs, and observed generalization ceiling. Missing records return to empirical-research.
- Put ethics documentation where the APSA and venue policies request it (`wp-review-process` and
  `wp-submission`).

## The adjudication test (World Politics–specific)

Present the strongest rival and its core-registered adjudication record. If either is absent, return the
design to empirical-research; this overlay only determines placement and clarity.

## Anti-patterns

- Convenience case selection dressed up as theory-driven; selecting on the dependent variable
- Omitting a failed timing or dependence diagnostic from the core record
- "Causal" language on a design that only supports cross-case association
- A within-case story over-generalized with no scope conditions
- A design that cannot distinguish your argument from the leading alternative

## Design-objection patterns and the venue-specific fix

World Politics judges each tradition on its own terms and prizes designs built to adjudicate, so
design objections cluster predictably across the comparative and IR styles it publishes.

| Referee objection | The fix this skill drives |
|-------------------|----------------------------|
| "Case selection unjustified" | Show the core-registered selection rationale and scope; return an absent record to empirical-research |
| "Selecting on the dependent variable" | Report the core selection diagnostic and resulting disposition; a redesign is a core revision |
| "Causal language on associational design" | Report the observed core inference ceiling and use matching prose |

## Worked micro-example (illustrative)

A hypothetical comparative study asks whether **electoral autocracies are more war-prone than closed
ones**. A weak version selects three war-fighting electoral autocracies and infers a tendency — a
selection-on-the-outcome flaw a referee will name immediately.

```text
Mode:      comparative-historical, structured-focused comparison
Estimand:  conflict propensity, electoral vs closed autocracy, holding capacity fixed
Selection: 2 electoral + 2 closed autocracies matched on GDP/region; varies on the OUTCOME
Adjudication: if the rival "capacity, not regime type" held, the matched closed cases would
  fight as often; instead the electoral cases initiate ~2x more disputes (illustrative).
Travel:    scope condition — holds where elections raise audience costs, not where they are sham
```

The venue presentation names the core contract, links the selection and adjudication Artifact IDs, and
states the observed inference ceiling. Any redesign is performed and revalidated in empirical-research.
(Counts and ratios are illustrative.)

## Output format

```
【Mode】comparative-historical / quant cross-national / qualitative / experiment / formal-empirical
【Core contract】id + revision + registered estimand/claim and scope
【Core diagnostics】case selection / assumptions / dependence Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Inference ceiling】observed ceiling + core-bound sensitivity disposition
【Next】wp-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — identification/TSCS packages, QCA, and CAQDAS for qualitative work
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — reviewer-guideline expectations for design and methods
