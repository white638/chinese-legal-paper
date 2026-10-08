---
name: sf-research-design
description: Use when presenting an empirical-core research design in a Social Forces manuscript. This venue overlay controls disclosure and reviewer-facing explanation; it does not choose methods, diagnostics, thresholds, or repairs.
---

# Research Design (sf-research-design)

Social Forces is known for **methodological rigor**, and its reviewers are demanding about each
tradition. The design must credibly connect the argument (`sf-theory-building`) to evidence and rule
out the strongest alternative. This skill is mode-aware: pick the section that matches your work and
defend it on its own terms.

## When to trigger

- Specifying identification, demographic design, case selection, or a network/computational pipeline
- A reviewer questioned causal claims, case choice, measurement, or a confound
- Deciding what design buys the cleanest test of your mechanism within a tight word budget
- Justifying why your design adjudicates the rival account from `sf-literature-positioning`

## Quantitative / causal inference reporting
- Report the registered target, counterfactual, assumptions, diagnostic Artifact IDs, and observed
  ceiling under `CORE.CAUSAL.ESTIMAND_BINDING` and `CORE.CAUSAL.ASSUMPTION_DIAGNOSTICS`.
- For event-time panels, show `CORE.PANEL.STAGGERED_DESIGN` records. Report dependence, multiplicity,
  and sensitivity dispositions under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`,
  `CORE.INFERENCE.MULTIPLICITY_PLAN`, and `CORE.INFERENCE.SENSITIVITY_BINDING`.

## Demographic reporting
- Report the core quantity, population/exposure, time scale, event/competing-event definitions,
  assumptions, diagnostic Artifact IDs, and observed ceiling.

## Comparative-historical / ethnographic reporting
- Report the core-registered case/site rationale, scope, competing account, process-tracing evidence
  matrix, negative evidence, Artifact IDs, and observed ceiling. Do not define venue-local tests.
- Put source documentation where `sf-data-and-transparency` requires it.

## Network / computational reporting
- Report the core boundary/tie/baseline identity, dependence and measurement-validation artifacts,
  stability disposition, and observed ceiling.

## The adjudication test (SF-specific)

Present the strongest rival and its core-registered adjudication record. If either is absent, return the
design to empirical-research; SF only determines placement and clarity.

## Anti-patterns

- Omitting a failed core timing, dependence, or measurement diagnostic
- "Causal" language on a design that only supports association
- Convenience case selection dressed up as theory-driven
- An unvalidated computational measure treated as ground truth
- A design that cannot distinguish your argument from the leading alternative

## What SF referees probe in the design

Because Social Forces built its standing on methodological rigor across a broad discipline, its referees
read the design for whether the strongest alternative is actually ruled out — not whether the method is
fashionable. A practical gate by mode:

| Design mode | The check an SF referee runs first | Common decline trigger |
|-------------|-----------------------------------|------------------------|
| Quant-causal | Core target, assumption diagnostics, and ceiling shown? | Core causal disposition omitted |
| Panel / event time | Core timing/comparison diagnostics shown? | Failed core diagnostic hidden |
| Demographic | Core period/cohort, exposure, and quantity records shown? | Population/quantity identity omitted |
| Comparative-historical | Core selection/scope/adjudication records shown? | Selection rationale omitted |
| Network / computational | Core boundary/dependence/validation records shown? | Core measurement disposition omitted |

Calibration (hedged): SF welcomes all these traditions, but the bar is rigor on the tradition's own
terms plus general-sociology significance — less theory-maximalist than AJS/ASR yet far stricter on
identification than a descriptive outlet. Confirm method-specific expectations against current practice.

## Worked vignette (illustrative)

A neighborhoods-and-attainment study names its core contract/revision, reproduces the registered target,
and links the selection, dependence, sensitivity, and rival-adjudication Artifact IDs with their
dispositions. SF prose explains their sociological meaning and reports the observed ceiling; it does not
add a diagnostic or choose a repair.

## Referee-pushback patterns and the SF fix

- "Selection threatens the inference" → show the core assumption/sensitivity disposition and ceiling.
- "Mechanism under-specified" → show the core rival-adjudication and diagnostic-evidence records.
- "Dependence is unclear" → show `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; return a method change to core.

## Output format

```
【Mode】quant-causal / demographic / comparative-historical / ethnographic / network-computational
【Core contract】id + revision + target/claim + ceiling
【Core diagnostics】assumption / selection / dependence / measurement Artifact IDs + disposition
【Rival adjudication】registered record + evidence locator
【Sensitivity】core-bound records + outcome
【Next】sf-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design/identification packages (R/Stata/Python), demography, networks, CAQDAS/QCA
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — SF rigor reputation and scope
