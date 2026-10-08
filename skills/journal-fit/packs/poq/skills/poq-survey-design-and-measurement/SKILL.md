---
name: poq-survey-design-and-measurement
description: Use when presenting an empirical-core survey design in a Public Opinion Quarterly manuscript. This venue overlay applies AAPOR disclosure and placement rules; it does not choose sampling, measurement, weighting, experiment, diagnostic, threshold, or repair procedures.
---

# Survey Design & Measurement Reporting (poq-survey-design-and-measurement)

## Authority boundary

Survey population, frame, recruitment, mode, instrument, missingness, weighting, measurement error,
experiment design, diagnostics, and inference ceiling belong to the empirical-research core registry,
contracts, and Artifact chain. POQ determines what must be disclosed and where. A missing record returns
to empirical-research; it is not repaired in venue prose.

## When to trigger

- Presenting a validated survey or survey-experiment design in a POQ manuscript
- Building the AAPOR disclosure appendix from core records
- Responding to reviewer questions about coverage, nonresponse, measurement, mode, or weighting

## Report the registered Total Survey Error records

- **Coverage and sampling:** core target population, frame, eligibility, selection/recruitment,
  effective unit, scope ceiling, and Artifact IDs.
- **Nonresponse and missingness:** core response/disposition data, missingness assumptions, diagnostics,
  sensitivity disposition, and inference consequence.
- **Measurement and mode:** core wording/instrument version, codebook, construct validation, pretest,
  mode records, error diagnostics, and observed interpretation ceiling under
  `CORE.MEASUREMENT.REGISTERED_VALIDATION`.
- **Weighting and dependence:** core weight identity, sampling/dependence units, uncertainty Artifact IDs,
  and disposition under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- **Survey experiments:** `CORE.EXPERIMENT.REGISTERED_DESIGN`, deviations, diagnostic Artifact IDs,
  multiplicity disposition, and ceiling. POQ does not choose the experiment or correction.

## AAPOR disclosure overlay

Build “Appendix A: Disclosure Elements” by locating the following core facts: funding; exact question
wording; population and frame; sample/recruitment design; collection mode/dates; response/disposition
records; sample/effective-unit counts; uncertainty; weighting/dependence; deviations; and public or
restricted Artifact locators. Current AAPOR labels and submission details must be verified against the
official source map; these are reporting requirements, not method-validation authority.

## Reviewer-facing audit

| Reviewer concern | Core fact to show | Venue placement |
|---|---|---|
| Coverage | population/frame/scope record + diagnostics | methods summary + Appendix A |
| Nonresponse | response/disposition and sensitivity artifacts | methods + supplement |
| Measurement/mode | instrument/version and validation disposition | methods + instrument appendix |
| Weighting/dependence | weight, unit, uncertainty identity and disposition | methods + analysis appendix |
| Survey experiment | registered target/design/deviation/diagnostic records | main text + preregistration locator |

## Anti-patterns

- Substituting POQ preferences for a core survey or experiment contract
- Reporting a response-rate label without the core disposition data and calculation locator
- Naming a diagnostic, correction, threshold, or weighting repair that is absent from core execution
- Hiding a failed coverage, measurement, missingness, or dependence diagnostic in limitations

## Output format

```text
【Core contract】family/profile + revision
【Population/frame】core identities + scope ceiling
【Survey diagnostics】coverage/nonresponse/measurement/mode Artifact IDs + dispositions
【Weight/dependence】core identities + uncertainty disposition
【Experiment, if any】CORE.EXPERIMENT.REGISTERED_DESIGN + deviations + ceiling
【AAPOR Appendix A】core fact → manuscript/supplement location
【Next】poq-data-analysis
```

## Supplementary resources

- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — verify current AAPOR/POQ disclosure and submission rules
