---
name: jpsp-data-analysis
description: Use when reporting empirical-core multi-study analysis artifacts in a Journal of Personality and Social Psychology manuscript. This venue overlay applies JARS/TOP placement; it does not choose synthesis models, uncertainty, mediation, diagnostics, thresholds, or repairs.
---

# Data Analysis & Internal Meta-Analysis (jpsp-data-analysis)

JPSP reviewers are methodologically sophisticated and the journal requires **JARS** reporting and
**TOP Level 2** transparency. Multi-study submissions need an integrated reader-facing account, while
the empirical-core contract decides whether and how a cross-study synthesis is scientifically
warranted. This skill covers execution reporting; design lives in the core method contract.

## When to trigger

- Analyzing studies and building the results sections
- Pooling effects across your own studies (internal meta-analysis)
- A reviewer asked for robustness, mechanism, or alternative-explanation analyses
- Reconciling preregistered vs. exploratory analyses

## Analysis norms JPSP expects

1. **Effect sizes with uncertainty.** Report standardized effect sizes and **confidence (or credible)
   intervals**, not just p-values/stars; state the **substantive magnitude**, per JARS.
2. **Cross-study synthesis disclosure.** Report the core-registered synthesis identity, included studies,
   dependence/heterogeneity records, output Artifact IDs, disposition, and package ceiling. JPSP does
   not choose the synthesis model.
3. **Accessible results sections.** Write results for readers with **general statistical expertise**;
   relegate complex justification to tables, notes, or supplements (IRGP house rule; verify).
4. **Core-bound sensitivity.** Report registered sensitivity Artifact IDs, failures, and inference consequences.
5. **Mechanism/alternative-account disclosure.** Report the core target, assumptions, competing account,
   diagnostic evidence and observed ceiling; do not create a venue-local mediation test.
6. **Registration/deviation disclosure.** Preserve core registered/exploratory labels and deviations.
7. **Measurement disclosure.** Report core validation Artifact IDs and dispositions.

## Reproducibility while you work (not at the end)

- Report the core driver and hashed outputs that regenerate every exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and stored toolchain/dependency identities.
- Post data/code/materials to a **trusted repository** with a persistent identifier (TOP Level 2).

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- Omitting a cross-study synthesis Artifact that the core contract registered and executed
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- Over-claiming causal mediation from correlational designs
- Burying a failed study instead of pooling it honestly into the meta-analysis

## Reviewer-pushback patterns and the analysis-side fix

These are the recurring post-credibility-revolution objections a JPSP section reviewer raises about results, and the move that defuses each. The fix is an *analysis-and-reporting* fix — design lives in `jpsp-study-design`.

| Reviewer says | What they distrust | The JPSP-fit fix |
|---------------|--------------------|------------------|
| "Stars only — where are the effect sizes?" | You hid magnitude behind significance | Report d/r/β with **95% CIs** and a sentence on substantive meaning, per JARS |
| "Each study reads in isolation" | No cumulative claim | Show the core synthesis Artifact and package disposition |
| "This could be a confound" | Alternative causal account | Show the core competing-account diagnostic and ceiling |
| "Mediation is over-claimed" | Claim outruns the core target | Report the observed core ceiling and use matching prose |
| "Was this predicted?" | Suspected HARKing | A confirmatory/exploratory table mapping each test to the **preregistration**; flag deviations |

## Worked micro-example: pooling a preregistered three-study package

*Illustrative numbers — invented to show the reporting logic, not real results.*

Three ASC studies address the same registered target. The results section reports every per-study
Artifact, then presents the core-registered synthesis identity, included-study manifest,
dependence/heterogeneity diagnostics, output Artifact, and package ceiling. A discordant or null study
remains visible. The venue example does not select a pooling model or turn one study's significance
status into a rule for inclusion.

## Output format

```
【Per-study effects】effect size + CI + substantive meaning
【Cross-study synthesis】core identity + output Artifact + dependence/heterogeneity disposition
【Mechanism】core target + diagnostic artifacts + ceiling
【Sensitivity】core-bound records → what held/failed
【Registered vs exploratory】clearly separated?
【JARS + repository】reported to standard + data/code/materials posted? [Y/N]
【Next】jpsp-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — metafor (internal meta-analysis), lavaan/PROCESS, effect-size + reliability tools
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — JARS, TOP Level 2, and IRGP integrative-analysis expectation
