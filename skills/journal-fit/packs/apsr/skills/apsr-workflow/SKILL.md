---
name: apsr-workflow
description: Use as the APSR venue-overlay entry point. Selects the relevant APSR reporting/fit lens and track while inheriting workspace state from cnki-paper and method validity from empirical-research. It does not own stages, execute methods, or draft content.
---

# APSR Venue Overlay Router (apsr-workflow)

This router selects an APSR **track** and the venue lens relevant to the parent workspace's current
question. APSR is a **discipline-wide generalist** journal, so the first fit check asks whether the
paper speaks to the whole discipline rather than only a subfield.

## When to trigger

- Comparing APSR tracks or deciding which venue lens applies to an existing workspace
- Revising APSR-facing reporting, transparency, presentation, or submission materials
- Deciding which of the **five tracks** fits the paper
- Returning with a decision letter (route to `apsr-rebuttal`)

## First question: which track?

| Situation | Track | Route to |
|-----------|-------|----------|
| Full original study, broad significance | **Regular Article** (< 11,000 words) | combine applicable lenses below |
| Focused single contribution | **Research Note** (< 7,000 words) | combine applicable lenses with tighter scope |
| Re-running / reassessing a published finding | **Replications and Reappraisals** | `apsr-research-design` + `apsr-transparency-and-data-policy` |
| Consolidating a literature or debate | **Synthesis** | `apsr-literature-positioning` + `apsr-theory-building` |
| Design finished, data **not yet collected/analyzed** | **Registered Report** | `apsr-review-process` (Stage 1) early |

> If the design is prospective, decide on Registered Reports **before** collecting data — that is the
> whole point of the track.

## Venue-lens map (concern → overlay skill)

```text
Idea / fit?                      → apsr-topic-selection
Where does it sit in the field?  → apsr-literature-positioning
What's the argument?             → apsr-theory-building
Is the design defensible?        → apsr-research-design
Are the analyses sound?          → apsr-data-analysis
Are the exhibits clear?          → apsr-tables-figures
Does it read for the discipline? → apsr-writing-style
Repro package & transparency?    → apsr-transparency-and-data-policy
How will it be judged?           → apsr-review-process
Ready to submit?                 → apsr-submission
Got an R&R / decision?           → apsr-rebuttal
```

These lenses are not a lifecycle or state machine. Select only what the parent workflow currently
needs, then return the result; `cnki-paper` decides the next workspace action.

## Discipline-wide routing check

Before selecting an overlay lens, run a one-minute APSR fit check:

| Check | Pass condition | Route if weak |
|-------|----------------|---------------|
| Audience | A reader outside the author's subfield can state why the question matters to political science. | `apsr-topic-selection` |
| Track | The manuscript clearly fits Regular Article, Research Note, Replication/Reappraisal, Synthesis, or Registered Report. | track table above |
| Method pluralism | The chosen method is defended on its own terms rather than forced into a quantitative template. | `apsr-research-design` |
| Transparency | Data, code, qualitative evidence, formal proof, or interpretive materials have an explicit verification plan. | `apsr-transparency-and-data-policy` |

If the paper fails the audience check, do not route to writing-style. It needs a theory or fit repair,
because APSR reviewers reject well-executed subfield papers that never become discipline-wide claims.

## Anti-patterns

- Treating APSR like a subfield journal — the contribution must reach the whole discipline
- Forcing a quantitative template onto qualitative, formal, or interpretive work (APSR judges each on its own terms)
- Choosing Registered Reports *after* seeing results (impossible — Stage 1 precedes data)
- Skipping the reproducibility package until acceptance — it is verified by the editorial office

## Control-plane boundary

- Workspace stages, gates, status, receipts, writes, and completion remain with `cnki-paper`.
- Claim capability, estimand, inference ceiling, typed contracts, validators, and method execution
  remain with `empirical-research`.
- APSR skills may request that a core field or diagnostic be reported, but cannot define or override it.
- This router never directly calls a statistical, NLP, browser, or submission engine.

## Output format

```
【Track】Regular Article / Research Note / Replication / Synthesis / Registered Report
【Overlay lens】apsr-<skill>
【Why】one line
【Return】parent workflow owns the next action
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — political-science data + software by method
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — official APSR URLs behind every fact in this pack
