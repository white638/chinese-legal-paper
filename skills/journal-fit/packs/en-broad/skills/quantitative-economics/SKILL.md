---
name: quantitative-economics
description: Use when targeting Quantitative Economics (QE) or deciding whether a structural / quantitative manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Quantitative Economics (quantitative-economics)

## Journal positioning

Quantitative Economics is an Econometric Society open-access journal devoted to quantitative economics that combines structural and computational modeling with data. It publishes both methodological contributions and quantitatively rigorous applied work — the common thread is taking models seriously enough to confront them with data through estimation, calibration, or computation. What wins here is a paper where the economic model and the quantitative implementation are both first-rate. The readership is structural and quantitative economists across micro and macro who care about model-based inference.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Econometric Society / journal site and the submission system.

## When to trigger

- The author names QE as the target venue.
- A structural / computational paper has a serious model-meets-data contribution and the author is choosing among quantitative venues.
- A reduced-form or theory paper has a strong quantitative-modeling extension that needs re-framing toward QE's strengths.
- The author needs QE's desk-reject risks and a credible quantitative / econometrics alternative list.

## Scope & topic fit

- Structural estimation and quantitative modeling across micro and macro: dynamic models, heterogeneous agents, IO, labor, public, trade, macro.
- Computational and numerical methods for solving and estimating economic models.
- Econometric methods oriented toward structural / model-based inference and identification.
- Quantitatively rigorous applied work where the model carries the contribution, not only the reduced-form result.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should state the economic question, the model, the identification, and what the quantitative exercise delivers (counterfactuals, decompositions, estimates).
- Frame the contribution as a model-based advance — methodological, or an applied result that only a structural approach could deliver.
- Use an abstract and JEL codes; relegate derivations, computational detail, and robustness to a supplement / appendix.
- As an open-access journal, follow the current Econometric Society formatting; supplementary material and replication packages are expected.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Quantitative Economics submission guidelines / Econometric Society instructions for authors" and follow the current version.
- Re-check word/figure limits, abstract and JEL requirements, reference and math style, anonymization expectations, and any open-access / article-processing arrangements.
- Re-check the current replication / data and code archive policy (Econometric Society replication requirements).
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating what the quantitative / structural approach delivers that reduced-form work could not.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] Open-access / formatting and the replication archive requirements are satisfied.

## Common desk-reject triggers

- A reduced-form paper with no genuine structural / quantitative-modeling contribution.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Undocumented computational choices or results that are not robust.
- A pure-theory paper with no quantitative implementation, or applied work where the model is decorative.

## Re-routing decision

- Pure econometric theory / estimators with proofs → `econometric-theory` or `the-econometrics-journal`; applied-econometrics methods → `journal-of-econometrics`.
- General-interest structural work with broad ambition → `american-economic-review`; macro-structural → `aej-macroeconomics` or `journal-of-monetary-economics`.
- Theory-only contributions → `journal-of-economic-theory`; behavioral/experimental → `journal-of-economic-behavior-and-organization`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Quantitative Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <do the model and quantitative implementation clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / open-access / replication archive / computation docs>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
