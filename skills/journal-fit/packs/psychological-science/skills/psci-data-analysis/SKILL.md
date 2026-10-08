---
name: psci-data-analysis
description: Use when reporting empirical-core analysis artifacts in a Psychological Science manuscript. This venue overlay controls disclosure and open-science placement; it does not choose analysis, uncertainty, sensitivity, diagnostics, thresholds, or repairs.
---

# Data Analysis (psci-data-analysis)

Psychological Science holds analyses to high credibility standards: **effect sizes with confidence
intervals** for major results, **full disclosure** of how the data were handled, and a clean
**confirmatory vs. exploratory** separation. Analysis scripts and data are shared and can be checked.

## When to trigger

- Running and reporting the main and supporting analyses
- A reviewer asked for effect sizes, intervals, robustness, or disclosure
- Reconciling preregistered analyses with exploratory follow-ups
- Preparing analysis scripts and a data dictionary for deposit

## Reporting norms Psychological Science expects

1. **Magnitude and core uncertainty.** Report the registered quantity with the uncertainty procedure,
   Artifact IDs, and disposition stored by core execution.
2. **Full disclosure.** Report the core sample-size rationale identity,
   **all** data exclusions (and reasons), **all** manipulations/conditions, and **all** measures. Total
   excluded observations must be stated.
3. **Registration/deviation disclosure.** Preserve the core registered/exploratory labels and deviations.
4. **Core inference disclosure.** Report the registered model identity, assumption/diagnostic artifacts,
   and `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; this venue does not choose an alternative.
5. **Replicability disclosure.** Report the core driver, hashed outputs, data dictionary, and toolchain/
   stochastic identities (see `psci-open-science-and-transparency`).

## Robustness

- Report `CORE.INFERENCE.SENSITIVITY_BINDING` artifacts, failures, and their inference consequences.

## Worked micro-example (illustrative numbers)

A preregistered two-study package on selective attention. **Study 1** (N = 240, between-subjects)
tests whether a brief mindfulness induction reduces attentional capture by emotional distractors.
The confirmatory analysis is a single preregistered contrast on reaction-time cost.

```
Confirmatory (preregistered) — Study 1
  Effect: induction vs. control on capture cost (ms)
  d = 0.34, 95% CI [0.08, 0.59], t(238) = 2.66, p = .008
  Sensitivity: holds with/without the 6 preregistered RT-outlier exclusions
               (d shifts 0.34 → 0.31), and under log-RT (d = 0.33)
Exploratory (labeled) — Study 1
  Trait-anxiety × condition interaction surfaced post hoc; reported as
  exploratory, flagged for confirmation in Study 2's preregistration
Confirmatory (preregistered) — Study 2 (N = 300, direct + extension)
  Replicates direct effect (d = 0.29, 95% CI [0.06, 0.51]) and
  preregisters the anxiety moderation that was exploratory in Study 1
```

Why this passes Psychological Science scrutiny: every confirmatory number carries an effect size and a
CI; the anxiety interaction is honestly demoted to exploratory and then *promoted to confirmatory* only
after preregistration in Study 2; the sensitivity line pre-empts the "fragile-to-exclusions" reviewer.

## Analysis-stage reviewer pushback and the venue fix

| Reviewer pushback | What it signals here | Psychological Science fix |
|-------------------|----------------------|---------------------------|
| "p = .048 — too close to the line" | result may be fragile | report core uncertainty/sensitivity artifacts and observed ceiling; return redesign to core |
| "Which exclusions were preregistered?" | suspicion of undisclosed forking paths | give the disclosure table: rule, count, preregistered vs. post hoc, and the estimate with vs. without |
| "Means hide the distribution" | presentation obscures the registered quantity | display the core result artifact more transparently via `psci-tables-figures` |
| "Is this confirmatory?" | HARKing concern | point to the preregistration timestamp; relabel anything generated after data as exploratory |
| "Reviewer 2 could not rerun your code" | reproducibility gate | ship a fresh-session run log; see `psci-open-science-and-transparency` |

## Calibration anchors

- Present the core target quantity, uncertainty artifact, sensitivity disposition, and observed ceiling
  rather than a significance label alone.
- Report the core sample-size rationale and precision record without imposing a venue-wide threshold.

## Anti-patterns

- p-values and stars with no effect size or confidence interval
- Selectively reporting conditions, measures, or exclusions (undisclosed flexibility)
- HARKing exploratory findings into confirmatory hypotheses
- Optional-stopping / garden-of-forking-paths analyses presented as planned
- Analysis code that does not reproduce the reported numbers

## Output format

```
【Main result】effect size + confidence interval + meaning
【Disclosure】N-determination + all exclusions + all conditions + all measures reported? [Y/N]
【Confirmatory vs exploratory】clearly separated? [Y/N]
【Inference】core assumption/diagnostic Artifact IDs + multiplicity disposition
【Reproducible】scripts + data dictionary + fresh-session check? [Y/N]
【Next】psci-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — `effectsize`, `emmeans`, `metafor`, JASP/jamovi, reproducible-report tooling
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — statistical and disclosure requirements
