---
name: wp-data-analysis
description: Use when reporting empirical-core analysis artifacts for a World Politics manuscript. This venue overlay controls disclosure, triangulation narrative, and Dataverse placement; it does not choose estimators, uncertainty procedures, multiplicity corrections, or repairs.
---

# Data Analysis (wp-data-analysis)

World Politics reviewers are methodologically demanding, and authors who **rely on quantitative data
must deposit replication materials in the World Politics Dataverse** that let others reproduce the
**exact numerical results** (see `wp-transparency-and-data-policy`). Analyze as if both are true —
because they are. This skill covers execution and reporting norms; design decisions live in
`wp-research-design`.

## When to trigger

- Running main and supporting analyses; building the results/findings section
- A reviewer asked for robustness, heterogeneity, or alternative specifications
- Reconciling the cross-case pattern with within-case evidence (mixed methods)
- Making the analysis reproducible before deposit

## Analysis norms World Politics expects

1. **Report uncertainty honestly.** Confidence/credible intervals, not just stars; the magnitude and
   substantive meaning of the estimate across cases, not just its significance.
2. **Core-bound sensitivity.** Report the analyses and failures registered under
   `CORE.INFERENCE.SENSITIVITY_BINDING`, plus their inference consequences.
3. **Cross-national dependence.** Report the units, dependence structure, uncertainty Artifact IDs, and
   disposition stored under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
4. **Measurement that travels.** Report the core measurement-validation and source-sensitivity Artifact
   IDs, including any failure and resulting ceiling.
5. **Heterogeneity and multiplicity.** Preserve the core registered/exploratory labels and report the
   `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition.
6. **Triangulation.** Where the design is mixed-method, show the within-case process evidence and the
   cross-case statistics point the same way, and reconcile where they don't.

## Qualitative / comparative-historical specifics
- Make the **evidentiary basis explicit** — which sources support which inferential step; link claims
  to documents/interviews via evidence tables (see `wp-tables-figures`).
- For process tracing, report the tests passed/failed and what would have disconfirmed the argument.

## Reproducibility while you work (not at the end)
- One **master script** regenerates every table and figure from the (raw or constructed) data.
- Report `CORE.REPRO.STOCHASTIC_IDENTITY` for each stochastic step.
- Pin software/package versions (`renv.lock`, `requirements.txt`, recorded `ssc`/`net` installs).
- Keep table/figure numbers matched to script outputs — the Dataverse package must reproduce them.

## Anti-patterns

- Stars-only tables with no effect sizes or intervals
- "Robustness" that only reruns near-identical specs to manufacture stability
- Results that hinge on one data source or one coding choice without showing alternatives
- Omitting a failed dependence diagnostic or narrowed inference ceiling
- A findings section whose numbers the deposited code cannot reproduce

## Referee-pushback patterns and the World Politics fix

World Politics referees span a methodologically plural community, so each tradition is judged on its
own terms. The recurring objections, and the answering move, are stable.

| Referee objection | The fix this skill drives |
|-------------------|----------------------------|
| "Robustness only reruns near-identical specs" | Show the core-bound sensitivity artifacts and their dispositions, including failures |
| "Stars but no magnitudes" | Lead with effect size + interval + substantive meaning across cases |
| "Quant and case evidence diverge" | State it, adjudicate with within-case evidence, narrow the scope condition |

A frequent risk is the **fishing concern**. Report the core registered/exploratory label, deviation
record, and `CORE.INFERENCE.MULTIPLICITY_PLAN` disposition. The venue layer does not choose a correction.

## Worked micro-example (illustrative numbers)

A hypothetical mixed-method study asks whether **fiscal decentralization dampens ethnic conflict
onset** across ~120 countries, paired with two within-case process-tracing narratives.

```text
Main estimate (illustrative): 1-SD rise in decentralization → onset HR 0.72, CI [0.58, 0.90]
  reading: ~28% lower onset risk at the mean, not just "p < 0.05"
Robustness:  swap V-Dem for OECD measure → HR 0.79 [0.61, 1.02] (weaker, crosses 1)
Dependence diagnostic → report the registered Artifact ID, procedure identity, and disposition
Triangulation: HR and both case narratives agree on a budgetary-bargain mechanism; the lone case
  where decentralization did NOT dampen conflict had centrally appointed governors → scope condition.
```

The honest reading: the effect is real but **scope-conditioned on genuine fiscal autonomy**, with
the weaker interval reported, not suppressed. Figures illustrative only.

## Output format

```
【Main estimate】magnitude + interval + substantive meaning across cases
【Core diagnostics】identification/dependence Artifact IDs + disposition
【Sensitivity】core-bound analyses / alternative-source artifacts → what held/failed
【Measurement】validation Artifact IDs + observed ceiling
【Triangulation】within-case + cross-case agree? reconciled?
【Reproducible】master script + seeds + pinned versions? [Y/N]
【Next】wp-tables-figures
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — estimation, TSCS/panel, survival, and text-as-data packages
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — Dataverse replication requirement
