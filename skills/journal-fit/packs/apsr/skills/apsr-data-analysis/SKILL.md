---
name: apsr-data-analysis
description: Use when reporting core-validated analysis in an American Political Science Review (APSR) manuscript. It selects article, appendix, and transparency placement for registered results and diagnostics; it does not choose estimators, repairs, or validation rules.
---

# Data Analysis (apsr-data-analysis)

APSR reviewers are methodologically sophisticated and the editorial office may later verify deposited
materials against the manuscript (see `apsr-transparency-and-data-policy`). This overlay reports the
executed, hash-bound results accepted by `empirical-research`; method selection, diagnostics, and
inference disposition remain in the core contract and validator.

## When to trigger

- Building the results section from registered execution results
- A reviewer asked where robustness, heterogeneity, or diagnostic evidence is reported
- Reconciling preregistered vs. exploratory analyses
- Making the analysis reproducible before deposit

## APSR reporting overlay

1. **Result identity.** Give each main statement's registered Result, Claim, Evidence, and Artifact
   references; never retype a number that lacks a core locator.
2. **Uncertainty.** Report the uncertainty quantity produced by the registered route, its substantive
   scale, and its artifact location. This pack does not select the uncertainty procedure.
3. **Diagnostics and sensitivity.** Summarize the diagnostic and sensitivity artifacts required by
   the active core contract, including failures and the resulting inference disposition. It does not
   add a venue-specific robustness battery.
4. **Registered versus exploratory.** Preserve the core preregistration/deviation classification and
   make the distinction visible in the article or appendix.
5. **Heterogeneity and multiplicity.** If the core route registered these analyses, report their
   planned/exploratory identities and core outputs. APSR prose cannot choose a correction afterward.
6. **Measurement.** For a measurement route, report the frozen corpus, gold/reference data, category-
   level metrics, error analysis, sensitivity, and interpretation boundary already validated by core.

## Computational / text-as-data placement

Expose the registered model/version, environment, prompt or parameter identities, validation artifacts,
error analysis, stability/sensitivity results, and prohibited interpretations. Use the article for the
construct and result boundary and the supplement for the complete audit trail.

## Reproducibility reporting

- Point to the core reproduction command and environment record that regenerate each exhibit.
- Report registered seeds or repeated-run identities for stochastic steps when present.
- Report the pinned software/package record and map manuscript exhibit numbers to output artifacts.
- Place access restrictions, non-shareable inputs, and documented manual boundaries in the README.

## Core method-contract bridge

Use the executed, hash-bound results and diagnostics registered by `empirical-research`; this venue
overlay only decides which of them APSR readers need in the article or supplement. Relevant core
failure IDs include `ME.INFERENCE.DIAGNOSTIC_FAILED_NOT_NARROWED`,
`ME.INFERENCE.PARALLEL_TRENDS_FAILED`, `ME.INFERENCE.PSEUDO_REPLICATION`,
`ME.MEASUREMENT.SPLIT_OVERLAP`, and `ME.MEASUREMENT.METRIC_MISMATCH`. Their meaning and remedy
belong to core. APSR reporting must expose the resulting disposition, not override it.

## Anti-patterns

- Result prose without registered Result/Artifact IDs or reproducible locators
- Omitting a failed diagnostic, negative result, deviation, or narrowed inference disposition
- Relabeling exploratory output as registered or confirmatory
- Selecting a new estimator, sensitivity check, or correction inside the APSR pack
- Tables or figures that differ from the hash-bound output used by the core result

## Output format

```
【Core result】Result/Claim/Evidence/Artifact IDs + locator
【Uncertainty】registered output + substantive scale + article/appendix location
【Diagnostics/sensitivity】core statuses + failure codes + artifact locations
【Registered vs exploratory】core classification and deviations shown?
【Inference disposition】retained/narrowed/withdrawn + prohibited interpretation
【Reproducible】command/environment/exhibit map reported? [Y/N]
【Return】parent workflow owns the next action
```

## Reader-facing placement map

| Core record | Article | Appendix / reproducibility package |
|---|---|---|
| Main Result and observed ceiling | Magnitude/meaning and bounded interpretation | Full output and locator |
| Identification or measurement diagnostics | Decisive status and consequence | Complete artifacts and logs |
| Sensitivity/robustness registered by core | Material change or stability | Full registered set, including failures |
| Exploratory/heterogeneity results | Explicit label if discussed | Registration identity, deviations, full outputs |
| Negative findings | Consequence for argument | Complete inventory and artifact links |

## Referee-pushback patterns and the APSR-specific repair

- *"This reads as a subfield result, not a general one."* → Re-anchor the estimate to a
  discipline-wide stake (representation, accountability, institutional design) before the numbers.
- *"I cannot see the identifying evidence."* → Add the registered diagnostic status, artifact locator,
  and inference consequence; do not invent a new diagnostic in the response.
- *"Theory and empirics are loosely coupled."* → Show the registered Claim–Result–Evidence links and
  their scope conditions.
- *"I cannot tell registered from exploratory analyses."* → Surface the core classification and
  deviation records in separate article or appendix subsections.

## Calibration anchors (hedged)

- The bar is **general-political-science significance**, not within-subfield novelty: an effect that
  only a specialist would value rarely clears APSR review.
- APSR practices **methodological pluralism** — a rigorous qualitative or formal analysis is not
  second-class to a regression. Match the inference standard to the design.
- Transparency expectations follow **DA-RT / APSR Dataverse** norms: write the analysis so a
  conditionally-accepted package reproduces every printed number. Exact deposit mechanics can change —
  confirm against the journal's current submission and transparency guidelines.

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, inference, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — reproducibility-verification policy
