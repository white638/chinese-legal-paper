---
name: asr-data-analysis
description: Use when reporting empirical-core analysis artifacts for an American Sociological Review (ASR) manuscript. This venue overlay controls presentation and transparency placement; it does not choose analysis, diagnostic, uncertainty, or repair procedures.
---

# Data Analysis (asr-data-analysis)

ASR reviewers are methodologically demanding across very different traditions. Whether your evidence
is regression coefficients, life tables, archival sequences, or coded fieldnotes, the analysis must be
transparent, well-documented, and reproducible to the extent your data allow. Design decisions live in
`asr-research-design`.

## When to trigger

- Running main and supporting analyses; building the results/findings section
- A reviewer asked for robustness, heterogeneity, alternative specifications, or more evidence
- Documenting how qualitative claims are grounded in the data
- Making the analysis reproducible before sharing materials

## Analysis norms ASR expects

### Quantitative / demographic
1. **Report uncertainty and magnitude**, not just significance — show the registered dependence and
   uncertainty records under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` and explain magnitude.
2. **Core-bound sensitivity** — report the Artifact IDs and dispositions stored under
   `CORE.INFERENCE.SENSITIVITY_BINDING`, including failures and their inference consequences.
3. **Heterogeneity with discipline** — report the core registered/exploratory classification and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; ASR does not select a correction.
4. **Measurement** — report the core validation, reliability, source/scaling-sensitivity Artifact IDs,
   disposition, and observed ceiling.

### Comparative-historical / ethnographic
- Present the core claim-to-evidence graph, negative/disconfirming evidence, and Artifact IDs in tables,
  timelines, or excerpts that reviewers can trace.

### Computational / text-as-data
- Report the core model/preprocessing identity, `CORE.REPRO.STOCHASTIC_IDENTITY`, validation Artifact
  IDs, stability disposition, and inference ceiling.

## Reproducibility while you work
- Report the core driver and hashed outputs that regenerate every quantitative exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and the stored toolchain/dependency identities.
- For qualitative work, point to the core codebook, analytic-memo, and claim-evidence artifacts.

## What an ASR analyst-reviewer is checking

As the ASA's flagship, ASR draws referees who police analysis on each tradition's terms while asking
one disciplinary question — does the evidence warrant a claim that speaks to general sociological
theory? Use this table to pre-empt the masked reviewer.

| Reviewer probe | Clears the ASR bar | Triggers a revision flag |
|----------------|--------------------|---------------------------|
| "Just a significant coefficient?" | magnitude + interval tied to a mechanism | stars-only, no interpretation |
| "Survives a reasonable confounder?" | core sensitivity disposition reported | core diagnostic record omitted |
| "Does uncertainty match dependence?" | core unit/procedure/disposition shown | core dependence record omitted |
| "Where is disconfirming evidence?" | core negative-evidence records shown | only confirming evidence displayed |
| "Heterogeneity real or mined?" | core registration/deviation and multiplicity disposition shown | one fished interaction theorized post hoc |

## Worked micro-example (illustrative numbers)

A hypothetical ASR study links employer credit-checking to a Black-white callback gap using
administrative hiring records across 1,200 firms.

```
Main effect: callback gap 8.0 pp (95% CI 5.1–10.9) under firm + occupation FE
Mechanism: gap concentrated in customer-facing roles (11.2 pp) vs back-office (2.3 pp)
Sensitivity: a confounder must be ~1.7× the strongest covariate to nullify
Negative case: no gap where state law bans the practice (0.4 pp, CI −2.0–2.8) → boundary evidence
Reproducible: one master script, seed=2026, renv.lock pinned
```

The intervals carry the claim, the role contrast names a portable mechanism (statistical
discrimination via screening signals), and the law-ban null is reported as evidence, not buried.

## Referee pushback → ASR-specific fix

- *"Significant but does it matter?"* → Give a scenario magnitude and name what changes for inequality
  theory.
- *"Robustness agrees by construction."* → Show the core-bound sensitivity records and failures; return
  a missing diagnostic to empirical-research.
- *"This reads as a within-subfield exercise."* → State which general sociological debate the estimate
  adjudicates before the table, not after.

## Calibration anchors

- **Theory-forward, not table-forward.** ASR rewards an analysis that reads as a test of a mechanism;
  a results dump that defers the "why" under-performs.
- **The "so what for sociology" bar.** Each headline number should map to a sentence a generalist could
  repeat about how social processes work.
- **Breadth of admissible evidence.** Coefficients, life tables, coded fieldnotes, and validated model
  outputs all qualify — the standard is the claim-to-evidence link.

## Anti-patterns

- Stars-only tables with no effect sizes or intervals; ignoring survey weights
- "Robustness" that only reruns near-identical specs to manufacture stability
- p-hacking / HARKing exploratory results into hypotheses
- Qualitative claims with no traceable evidence or negative cases
- Computational outputs reported without validation

## Output format

```
【Main result】magnitude + interval (quant) OR evidence chain (qual)
【Identification/grounding check】(per research-design) result
【Sensitivity / negative cases】core Artifact IDs + dispositions
【Heterogeneity】core registration/deviation and multiplicity disposition reported? (quant)
【Reproducible】core driver + stochastic/toolchain identities OR core codebook? [Y/N]
【Next】asr-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, demography, networks, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — ASA data-sharing norms
