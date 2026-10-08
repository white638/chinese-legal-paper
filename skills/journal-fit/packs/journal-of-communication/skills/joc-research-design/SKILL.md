---
name: joc-research-design
description: Use when presenting an empirical-core research design in a Journal of Communication manuscript. This venue overlay controls communication-theory explanation and placement; it does not choose methods, diagnostics, thresholds, or repairs.
---

# Research Design (joc-research-design)

JoC accepts many methodologies but is demanding about each. The design must credibly connect the
argument (`joc-theory-building`) to evidence. This skill is mode-aware: pick the section that matches
your work and defend it against the strongest alternative explanation.

## When to trigger

- Specifying an experiment, survey, content-analysis protocol, computational pipeline, or fieldwork plan
- A reviewer questioned causal claims, sampling, coding reliability, validity, or a confound
- Preparing a **preregistration** / pre-analysis plan (note it in the cover letter)
- Justifying why your design adjudicates the rival account from `joc-literature-positioning`

## Experiment reporting (lab / online / survey / field)
- Report `CORE.EXPERIMENT.REGISTERED_DESIGN`: target, units/stimulus population, sampling/generalization
  ceiling, diagnostics, deviations, and Artifact IDs. Missing records return to empirical-research.
- Put ethics/IRB, consent, and debrief documentation where JoC policy requires it.

## Survey / panel reporting
- Report the core sampling/mode/weighting, measurement-validation, timing, diagnostic, and observed
  ceiling records under `CORE.MEASUREMENT.REGISTERED_VALIDATION` and applicable causal requirements.

## Content-analysis reporting
- Report the core corpus/unit, codebook/research-run provenance, validation/reliability Artifact IDs, sampling
  scope, and interpretation ceiling. No venue-wide metric or threshold is defined here.

## Computational / text-as-data reporting
- Report the core model/preprocessing/stochastic identity, frozen reference and validation Artifact IDs,
  stability/sensitivity disposition, and ceiling under `CORE.MEASUREMENT.REGISTERED_VALIDATION` and
  `CORE.REPRO.STOCHASTIC_IDENTITY`. Put platform/ToS and ethics disclosure where JoC requests it.

## Qualitative / critical reporting
- Report `CORE.QUAL.REGISTERED_SELECTION_EVIDENCE`, reflexivity/access metadata, negative or
  complicating evidence, claim-evidence Artifact IDs, and observed ceiling.

## The adjudication test (JoC-specific)

Present the strongest rival and its core-registered adjudication record. If either is absent, return the
design to empirical-research; JoC only determines placement and communication-theory explanation.

## Reviewer-pushback patterns and the JoC-specific fix

JoC referees at the ICA flagship rarely reject on a single statistic; they reject when the design
cannot bear the **theoretical** weight the paper puts on it. The recurring objections and their
venue-specific repairs:

| Reviewer objection | Why it lands at JoC | Design-stage fix |
|--------------------|---------------------|------------------|
| "Single-message confound" | one stimulus may not support the feature claim | report the core stimulus-population and dependence disposition |
| "Measurement validity of message features" | a coded frame may not equal the construct | report core reference/evidence/validation artifacts and ceiling |
| "Effect without mechanism" | the claim outruns the core target | report the registered mechanism/evidence record or narrow the prose |
| "Exposure is assumed, not measured" | exposure construct may be weak | report the core measurement disposition |
| "Cross-sectional process claim" | timing may not license a process claim | report the observed core inference ceiling |

## Worked micro-example: framing survey-experiment design (illustrative)

A planned study on vaccine-message framing names its core contract/revision and links the target,
stimulus-population, measurement, dependence, mechanism, and rival-adjudication Artifact IDs with their
dispositions. JoC prose explains how the registered evidence bears on framing theory and states the
observed ceiling; it does not choose sample size, estimator, diagnostic, or repair.

## Anti-patterns

- Causal language on a cross-sectional survey that only supports association
- Content analysis with no registered reliability/validation evidence or an unstated unit of analysis
- Automated text measures that self-validate or report reference agreement as external accuracy
- Convenience case/stimulus selection dressed up as theory-driven
- A single-message stimulus carrying a claim about a message *feature*
- A design that cannot distinguish your argument from the leading alternative

## Output format

```
【Mode】experiment / survey / content-analysis / computational / qualitative
【Estimand or claim】what is being identified/shown
【Key assumption(s)】and how each is defended (incl. reliability/validity)
【Rival ruled out】the adjudication sentence
【Robustness/sensitivity】planned checks
【Next】joc-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design, reliability, and text-as-data packages (R/SPSS/Mplus/Python) and CAQDAS for qualitative work
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — preregistration and Open Science Badge notes
