---
name: joc-data-analysis
description: Use when reporting empirical-core analysis artifacts for a Journal of Communication manuscript. This venue overlay controls presentation and transparency placement; it does not choose analysis, uncertainty, validation, or repair procedures.
---

# Data Analysis (joc-data-analysis)

JoC reviewers are methodologically sophisticated, and the journal **requires a Data Availability
Statement** so others can scrutinize how your numbers were produced (see
`joc-open-science-and-transparency`). Analyze as if both are true — because they are. This skill covers
execution and reporting norms; design decisions live in `joc-research-design`.

## When to trigger

- Running main and supporting analyses; building the results section
- A reviewer asked for robustness, heterogeneity, or alternative specifications
- Reconciling preregistered vs. exploratory analyses
- Making the analysis reproducible before deposit

## Analysis norms JoC expects

1. **Report uncertainty honestly.** Confidence/credible intervals and effect sizes, not just stars or
   p-values; the substantive magnitude and meaning of the estimate.
2. **Core-bound sensitivity.** Report `CORE.INFERENCE.SENSITIVITY_BINDING` Artifact IDs,
   dispositions, failures, and inference consequences.
3. **Heterogeneity and multiplicity disclosure.** Report the core registered/exploratory labels and
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition; JoC does not choose a correction.
4. **Mechanism/moderation disclosure.** Report the core target, timing/ordering assumptions, diagnostic
   artifacts, and observed ceiling.
5. **Measurement disclosure.** Report core validation/reliability/coding-sensitivity artifacts and
   disposition under `CORE.MEASUREMENT.REGISTERED_VALIDATION`.
6. **Registration/deviation disclosure.** Preserve the core registered/exploratory labels and deviations.

## Computational / text-as-data specifics
- Report core model/preprocessing/stochastic identities, validation Artifact IDs, stability disposition,
  and observed ceiling.

## Reproducibility while you work (not at the end)
- Report the core driver and hashed outputs that regenerate every exhibit.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` and stored toolchain/dependency identities.
- Keep table/figure numbers in the manuscript matched to script outputs.

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- "Robustness" that only reruns near-identical specs to manufacture stability
- p-hacking / fishing for a significant interaction; HARKing exploratory results into hypotheses
- Reporting a content analysis without intercoder reliability
- A results section whose numbers the code cannot reproduce


## Evidence pass for Journal of Communication

Treat this skill as an executable review pass, not a prose hint. First lock the communication process, platform/media setting, construct measurement, and study design; then judge whether the current manuscript answers the venue's real reader: communication reviewers who balance theory, media context, measurement, and social implications.

- **Do the pass:** Audit the research design before polishing prose: unit of analysis, comparison set, uncertainty, sensitivity, missingness, and reproducibility must be visible.
- **Return a ledger:** give `claim / evidence / risk / manuscript location` rows, so the next agent can edit rather than rediscover the issue.
- **Sibling guard:** compare against Communication Research for quantitative communication, New Media & Society for platform focus, Human Communication Research for theory testing; if a sibling owns the contribution, recommend re-routing before polishing format.
- **Stop condition:** do not give submission-ready advice until the pack's `resources/official-source-map.md` has been checked for volatile rules and the manuscript has one concrete fix for the largest venue-specific risk.

## Output format

```
【Main estimate】magnitude + interval + substantive meaning
【Identification/validity check】(per research-design) result
【Sensitivity】core-bound Artifact IDs → what held/failed
【Heterogeneity】core registered/exploratory + multiplicity disposition
【Reliability】scale / intercoder reliability reported?
【Registered vs exploratory】clearly separated?
【Reproducible】core driver + stochastic/toolchain identities? [Y/N]
【Next】joc-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, reliability, mediation/SEM, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — Data Availability Statement requirement
