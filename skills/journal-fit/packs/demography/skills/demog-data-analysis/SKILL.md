---
name: demog-data-analysis
description: Use when reporting empirical-core demographic analysis artifacts for a Demography (PAA / Duke University Press) manuscript. This venue overlay controls presentation and reproducibility placement; it does not choose models, uncertainty procedures, diagnostics, thresholds, or repairs.
---

# Data Analysis (demog-data-analysis)

Demography reviewers are expert demographers and the journal expects **reproducible code** behind the
results (see `demog-data-and-reproducibility`). Analyze as if a methodologist will re-derive your rates
and re-run your decomposition — because they may. This skill covers execution and reporting norms;
method choice lives in `demog-research-design`.

## When to trigger

- Constructing rates and life tables; building the results section
- Running a decomposition, event-history, APC, or projection analysis
- A reviewer asked for robustness, sensitivity, or alternative specifications
- Making the analysis reproducible before deposit

## Analysis norms Demography expects

1. **Expose denominator construction.** Report the core population, exposure, time-alignment, build
   artifacts, diagnostics, and disposition.
2. **Report registered uncertainty.** Show magnitude and intervals with the procedure identity,
   Artifact IDs, and disposition stored under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
3. **Decomposition records.** State what each core-registered component means and report the internal
   reconciliation diagnostic and result artifact.
4. **APC records.** Report the core constraint/assumption identity, sensitivity artifacts, disposition,
   and ceiling; do not imply uniqueness beyond the core contract.
5. **Event-history records.** Report the core event, risk set, time scale, censoring/truncation/competing-
   event assumptions, diagnostics, and target quantity.
6. **Sampling and dependence.** Report the core weighting, unit, dependence, and uncertainty records;
   Demography does not choose an inferential procedure.

## Demographic computation specifics
- Document data version/vintage (e.g., HMD/HFD release), harmonization steps, and any smoothing/
  graduation applied to rates.
- For microsimulation/projection: report `CORE.REPRO.STOCHASTIC_IDENTITY`, run identity, convergence
  artifacts, and core-bound sensitivity disposition.

## Reproducibility while you work (not at the end)
- Report the core driver and hashed outputs that regenerate every exhibit and derived quantity.
- Report stochastic/toolchain/dependency identities stored by the core execution record.
- Keep table/figure numbers in the manuscript matched to script outputs (Demography expects runnable,
  commented code — see `demog-data-and-reproducibility`).

## Anti-patterns

- Mismatched numerator/denominator or wrong exposure (the classic demographic error)
- Point estimates of life expectancy or decomposition components with no uncertainty
- An APC model presented as the uniquely correct partition
- Ignoring censoring/competing risks in survival analysis
- A results section whose rates and decompositions the code cannot reproduce


## Evidence pass for Demography

Run this as a concrete capability pass. First lock the demographic process, data source, time scale, selection/migration/mortality issue, and uncertainty; then test whether the manuscript addresses population-science reviewers who inspect demographic process, measurement, cohort/period logic, and population validity.

- **Primary move:** Audit unit, comparison, uncertainty, missingness, sensitivity, and reproducibility before making any prose or submission recommendation.
- **Decision ledger:** return `claim / evidence / blocker / next edit` rows so the next pass can patch the manuscript directly.
- **Sibling comparison:** compare against Population and Development Review for policy synthesis, JMF for family process, Social Forces for broader sociology; if the neighboring outlet has the stronger audience claim, recommend re-routing before polishing.
- **Verification floor:** before submission-ready advice, re-open `resources/official-source-map.md` for volatile rules and name the one unresolved fact that could change the recommendation.

## Output format

```
【Main quantity】rate / e0 / decomposition / hazard + magnitude + interval
【Exposure / denominator check】correctly constructed? [Y/N]
【Decomposition】components defined + sum to total? [Y/N/NA]
【APC】core constraint + sensitivity Artifact IDs + disposition [Y/N/NA]
【Inference】sampling/dependence/event diagnostics + disposition [Y/N]
【Reproducible】core driver + stochastic/toolchain identities? [Y/N]
【Next】demog-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — life-table, decomposition, survival, APC, and simulation packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — data-availability and reproducible-code expectations
