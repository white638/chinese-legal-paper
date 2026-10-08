---
name: io-data-analysis
description: Use when reporting empirical-core analysis or formal-model artifacts for an International Organization (IO) manuscript. This venue overlay controls disclosure and verification placement, not estimator, uncertainty, multiplicity, or repair choices.
---

# Data Analysis (io-data-analysis)

Two facts shape how you analyze for IO. First, IO publishes **international-relations** work, so the
estimation problems are IR-specific — dyads are not independent, states select into treaties and wars,
trade follows a gravity structure, and many "variables" are estimated constructs. Second, IO's editorial
staff later **re-run your quantitative analyses and verify your formal proofs before final acceptance**
(see `io-transparency-and-data-policy`). This skill covers execution and reporting; identification choices
live in `io-research-design`.

## When to trigger

- Estimating the main international effect and supporting analyses; writing the results section
- A referee asked for robustness, heterogeneity by issue area, or an alternative estimator
- Deriving and presenting the results/comparative statics of a formal model
- Separating preregistered from exploratory analyses on a foreign-policy experiment

## IR-specific core records to expose

- **Dyadic, network, spatial, and temporal dependence.** Report the units, dependence structure,
  uncertainty implementation, diagnostic Artifact IDs, and disposition stored under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- **Selection at the international level.** Report the registered counterfactual, assumption diagnostics,
  core-bound sensitivity evidence, and observed ceiling.
- **Flows, zeros, and estimated constructs.** Report the core model identity, outcome/measurement
  contract, uncertainty artifacts, and diagnostics; IO does not choose the estimator or propagation rule.

## Reporting standards IO referees expect

1. **Substantive magnitude, not stars.** Give the size of the international effect with an interval and
   interpret it in IR terms (probability of conflict, change in trade, shift in compliance).
2. **Core-bound sensitivity.** Report the analyses and failures registered under
   `CORE.INFERENCE.SENSITIVITY_BINDING`, plus their inference consequences.
3. **Heterogeneity and multiplicity.** Preserve the core registered/exploratory labels and report the
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition.
4. **Construct validity.** Report the core measurement-validation and source-sensitivity Artifact IDs,
   including any failure and resulting ceiling.

## Formal-model results
- Present equilibrium results and comparative statics so a reader can map them to the empirics.
- Keep a **complete proof appendix** — IO staff verify proofs before final acceptance, so derivations
  must be checkable, not sketched.

## Verification-readiness (engineer it during analysis)
- A single driver script reproduces every reported number from the raw/constructed data in one run.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` for every stochastic step.
- Pin the toolchain (`renv.lock`, `requirements.txt`, logged `ssc`/`net install` lines) and the dataset
  versions (COW vX, V-Dem vY, UCDP release Z).
- The numbers printed in the manuscript must equal the script's output exactly — the IO re-run will compare them.

## Anti-patterns

- Omitting a failed dependence, selection, outcome-support, or measurement diagnostic
- Substituting a venue-preferred estimator for the implementation registered in the core contract
- A formal section with results stated but proofs left incomplete (verification will stall)

## Output format

```
【Estimand】the international effect + how identified (per io-research-design)
【Core analysis】model identity + dyadic/selection/outcome-support Artifact IDs and dispositions
【Magnitude】effect size + interval + IR interpretation
【Sensitivity】core-bound analyses → what held/failed
【Multiplicity】core registered/exploratory labels + disposition
【Formal proofs】complete + checkable appendix? [Y/N/NA]
【Verification-ready】one-run driver script, seeds, pinned data/toolchain? [Y/N]
【Next】io-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — dyadic/network/gravity estimation, few-cluster inference, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — verification of results and formal proofs before final acceptance
