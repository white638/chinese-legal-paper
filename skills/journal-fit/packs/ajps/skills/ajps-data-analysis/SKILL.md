---
name: ajps-data-analysis
description: Use when executing and reporting the analysis for an American Journal of Political Science (AJPS) manuscript. AJPS will have a third-party verifier re-run your exact code against the numerical results in the main text before publication, so analyze reproducibly from the first line. Guides analysis and reporting norms; it does not fabricate results.
---

# Data Analysis (ajps-data-analysis)

AJPS reviewers are methodologically sophisticated, and after acceptance an **independent third-party
verifier re-runs your code** against the numbers in the main text before the article is published (see
`ajps-replication-and-verification`). Analyze as if both facts are true — because they are. This skill
covers execution and reporting; design choices live in `ajps-research-design`.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, or alternative specifications
- Reconciling preregistered vs. exploratory analyses
- Making the analysis reproducible so the verifier's re-run will match

## Analysis norms AJPS expects

1. **Report uncertainty and magnitude.** Confidence/credible intervals and substantive effect sizes,
   not just significance stars — say what the estimate *means*.
2. **Core robustness disposition.** Report the sensitivity artifacts already registered by the active
   method contract, including failures and the resulting inference consequence.
3. **Heterogeneity and multiplicity.** Preserve and report the core registered/exploratory labels and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; AJPS prose cannot choose a correction afterward.
4. **Dependence and uncertainty.** Report the unit and procedure recorded under
   `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; this pack does not select an inference procedure.
5. **Registration/deviation disclosure.** Show the core labels and deviation records for registered and
   exploratory analyses; do not create a venue-local classification.
6. **Measurement disclosure.** Report the core measurement-validation Artifact IDs, sensitivity
   disposition, and ceiling; return missing validation to empirical-research.

## Computational / text-as-data reporting
- Report model identity, parameters, `CORE.REPRO.STOCHASTIC_IDENTITY`, measurement-validation Artifact
  IDs, stability disposition, and inference ceiling from the core execution record.

## Reproducibility while you work (so the verifier's re-run matches)
- Identify the core driver and hashed artifacts that regenerate every reported table and figure.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` for every stochastic step.
- Report the software/toolchain identity and dependency lockfiles stored by the core execution record.
- Keep the manuscript's table/figure numbers matched to script outputs — the verifier checks the
  **numerical results in the main text** line by line.

## Analysis-decision checklist a quantitative AJPS referee runs

| Question the referee asks | Pass condition | Fix if it fails |
|---------------------------|----------------|-----------------|
| Does the execution match the registered estimand? | Core target, implementation identity, and disposition shown | Return drift to empirical core |
| Is dependence handled as registered? | `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` record shown | Report the failed core diagnostic |
| Will the verifier's re-run match the printed numbers? | Core driver and hashed artifacts regenerate every exhibit | Return a mismatch to the core execution/audit workflow |

## Worked micro-example (illustrative numbers)

A survey experiment tests whether a co-partisan endorsement raises policy support. The pre-analysis plan
names the estimand (ITT on a 0-100 scale), the primary contrast, and one moderator (political knowledge).
Result: **+7.4 points (95% CI 3.1-11.7), randomization-inference p = 0.004** *(illustrative)*. A knowledge
interaction that was *not* pre-specified as confirmatory goes to an exploratory subsection, flagged, with a
multiple-comparison note. Every number is emitted by one seeded master script, so the AJPS verifier's
re-run reproduces the main-text figures exactly.

## Referee-pushback patterns and the venue-specific fix

- *"Identification leans on selection-on-observables."* -> Report the core-bound sensitivity Artifact ID,
  disposition, and resulting inference ceiling; return a missing diagnostic to empirical-research.
- *"This interaction looks mined."* -> Show the core registration/deviation and multiplicity
  disposition; do not select a new correction in the response letter.
- *"I cannot reproduce Table 2 from your code."* -> Report the verification failure and return it to the
  core execution/audit workflow; venue prose cannot repair a broken artifact chain.

Calibration anchor: AJPS's independent verifier re-runs deposited code against the main-text numbers before
publication, so "it works on my machine" is not enough — confirm the live verification wording against the
journal's current guidelines.

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- "Robustness" that only reruns near-identical specs to manufacture stability
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- Omitting the registered dependence unit, diagnostic failure, or narrowed inference disposition
- Hand-edited numbers in the manuscript that the deposited code cannot regenerate (verification fails)

## Output format

```
【Main estimate】magnitude + interval + substantive meaning
【Identification check】(per research-design) result
【Robustness】specs that could break it -> what held
【Heterogeneity】core registered/exploratory and multiplicity disposition reported?
【Registered vs exploratory】clearly separated?
【Reproducible】master script + seeds + pinned versions, numbers match? [Y/N]
【Next】ajps-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, inference, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — third-party verification of numerical results
