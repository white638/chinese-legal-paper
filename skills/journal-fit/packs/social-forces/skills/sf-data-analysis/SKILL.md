---
name: sf-data-analysis
description: Use when reporting empirical-core analysis artifacts for a Social Forces manuscript. This venue overlay controls presentation and transparency placement; it does not choose analysis, uncertainty, multiplicity, diagnostics, or repairs.
---

# Data Analysis (sf-data-analysis)

Social Forces built its standing on **methodological rigor**, and its reviewers are sophisticated. The
analysis must report uncertainty honestly, probe robustness that could actually break the result, and
stay reproducible. This skill covers execution and reporting norms; design decisions live in
`sf-research-design`. Keep an eye on the exhibit budget — results must fit within **10 tables and
figure panels** (see `sf-tables-figures`).

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, or alternative specifications
- Reconciling confirmatory vs. exploratory analyses
- Making the analysis reproducible before drafting the data availability statement

## Analysis norms SF expects

1. **Report uncertainty honestly.** Confidence/credible intervals, not just stars; the magnitude and
   substantive meaning of the estimate, not just its significance.
2. **Core-bound sensitivity.** Report the Artifact IDs and dispositions stored under
   `CORE.INFERENCE.SENSITIVITY_BINDING`, including failures and inference consequences.
3. **Heterogeneity and multiplicity.** Preserve core registered/exploratory labels and report the
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition.
4. **Dependence and uncertainty.** Report units, sampling/weighting records, uncertainty artifacts,
   and disposition under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
5. **Measurement and missingness.** Report the core validation, scaling/source sensitivity, missingness
   assumptions, Artifact IDs, dispositions, and observed ceiling.

## Demographic / computational / network specifics
- Demographic: report core quantity/component/event identities and diagnostic dispositions.
- Computational/text: report model identity, `CORE.REPRO.STOCHASTIC_IDENTITY`, validation artifacts,
  and ceiling.
- Network: report the core boundary/tie/baseline, dependence, and sensitivity records.

## Reproducibility while you work (not at the end)
- Report the core driver and hashed outputs that regenerate every exhibit.
- Report stochastic/toolchain/dependency identities stored by core execution.
- Keep table/figure numbers matched to script outputs — and feed the **data availability statement**
  (see `sf-data-and-transparency`).

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- "Robustness" that only reruns near-identical specs to manufacture stability
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- Omitting a failed sampling/dependence diagnostic or narrowed ceiling
- A results section whose numbers the code cannot reproduce


## Evidence pass for Social Forces

Treat this skill as an executable review pass, not a prose hint. First lock the social mechanism, data scope, identification or interpretation, and contribution to a wider literature; then judge whether the current manuscript answers the venue's real reader: social-science reviewers who want generalizable social-process evidence across sociology, demography, and policy-adjacent topics.

- **Do the pass:** Audit the research design before polishing prose: unit of analysis, comparison set, uncertainty, sensitivity, missingness, and reproducibility must be visible.
- **Return a ledger:** give `claim / evidence / risk / manuscript location` rows, so the next agent can edit rather than rediscover the issue.
- **Sibling guard:** compare against ASR/AJS for top sociology theory stakes, Demography for population process, JMF for family-specific claims; if a sibling owns the contribution, recommend re-routing before polishing format.
- **Stop condition:** do not give submission-ready advice until the pack's `resources/official-source-map.md` has been checked for volatile rules and the manuscript has one concrete fix for the largest venue-specific risk.

## Output format

```
【Main estimate】magnitude + interval + substantive meaning
【Identification check】(per research-design) result
【Sensitivity】core-bound Artifact IDs → what held/failed
【Heterogeneity】core registered/exploratory + multiplicity disposition
【Inference】sampling/dependence Artifact IDs + disposition
【Reproducible】core driver + stochastic/toolchain identities? [Y/N]
【Next】sf-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, inference, demography, network, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — data availability statement requirement
