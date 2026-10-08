---
name: aerj-data-analysis
description: Use when reporting empirical-core analysis artifacts in an American Educational Research Journal (AERJ) manuscript. This venue overlay applies AERA warrant/transparency placement; it does not choose analysis, diagnostics, thresholds, or repairs.
---

# Data Analysis (aerj-data-analysis)

AERJ analyses must be **warranted** (adequate evidence for the claim) and **transparent** (explicit
logic of inquiry), per the AERA reporting standards. Whatever the method, report enough that a reader
can judge — and a replicator could reproduce — the result.

## When to trigger

- Specifying the analytic strategy or writing the results section
- A reviewer questioned model specification, uncertainty, or coding rigor
- Reporting effect sizes, fit, robustness, or qualitative warrant
- Reconciling quantitative and qualitative results in a mixed-methods paper

## Quantitative reporting norms
- **Nesting and uncertainty.** Report the unit/dependence structure, procedure identity, diagnostics,
  and disposition stored under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- **Report effect sizes and uncertainty**, not just p-values: standardized effects, confidence
  intervals, and practical significance for education stakes.
- **Measurement and missingness.** Report the core model/measurement identity, assumptions, validation
  and missingness Artifact IDs, dispositions, and observed ceiling.
- **Multiplicity and sensitivity.** Report `CORE.INFERENCE.MULTIPLICITY_PLAN` and
  `CORE.INFERENCE.SENSITIVITY_BINDING` records, including failures. AERJ does not choose procedures.
- **Large-scale assessment data.** Expose the core sampling/weighting and uncertainty records.

## Qualitative reporting norms
- Present the core coding/interpretation identity, coder roles, negative evidence, reflexivity/access
  metadata, claim-to-evidence map, Artifact IDs, and observed ceiling.

## Mixed-method reporting
- Present the core strand and integration records, cross-strand evidence map, artifacts, and combined
  ceiling in the joint-display location required by AERA reporting.

## Anti-patterns

- OLS/single-level models on clustered data; ignoring ICC
- p-values with no effect sizes, CIs, or practical interpretation
- Listwise deletion treated as harmless; unreported attrition
- "Themes emerged" with no account of how, by whom, or with what reliability
- A mixed-methods results section that never integrates

## Warrant-and-transparency checklist by method (AERJ referees)

The AERA reporting standards apply to every tradition AERJ publishes, but referees probe different
things by design and evidentiary tradition. Audit your results section against the row that matches
your design.

| Design | Core records to report for warrant | Venue transparency placement |
|--------|-----------------------------------|------------------------------------------|
| Multilevel / growth | unit/dependence, model identity, diagnostics, ceiling | main result plus full artifacts in supplement |
| IRT / measurement | model identity, validation and sensitivity artifacts | concise validity disposition plus artifact locator |
| Quasi-experimental | estimand, assumptions, diagnostics, sensitivity, ceiling | decisive disposition in text; full records in supplement |
| Qualitative | coding identity, provenance, negative evidence, claim map | reflexivity and traceable evidence locations |
| Mixed | strand identities, integration map, combined ceiling | joint display and artifact locators |

## Worked analysis vignette (illustrative)

An AERJ evaluation names the core contract/revision, reproduces its target, and links its timing,
dependence, missingness, measurement, and sensitivity Artifact IDs with their dispositions. The text
reports magnitude and the observed ceiling; the supplement exposes the full records. A missing or failed
diagnostic returns to empirical-research rather than being repaired by venue prose.

## Referee pushback and the AERA-standard fix

- *"The uncertainty record does not match the nesting."* → Report the core dependence failure and
  ceiling; return any re-estimation decision to empirical-research.
- *"P-values with no practical meaning."* → Add standardized effect sizes and CIs interpreted against
  education stakes.
- *"'Themes emerged' tells me nothing."* → Show the core coding identity, claim-evidence map, and
  negative-evidence artifacts.
- *"The mixed strands never meet."* → Show the core integration record in an AERA-compatible joint display.

## Output format

```
【Method】multilevel / IRT-measurement / quasi-exp / qualitative / mixed
【Core analysis】contract/revision + model/coding identity + Artifact IDs
【Uncertainty / warrant】effect sizes + CIs (quant) or evidence + reflexivity (qual)
【Missingness / trustworthiness】core assumptions + disposition
【Sensitivity / negative evidence】core records + outcome
【Next】aerj-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — R / Stata / Mplus / HLM and CAQDAS by method
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — AERA reporting standards (warrant + transparency)
