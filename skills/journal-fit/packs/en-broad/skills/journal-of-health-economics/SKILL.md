---
name: journal-of-health-economics
description: Use when targeting Journal of Health Economics (JHE) or deciding whether a health-economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Health Economics (journal-of-health-economics)

## Journal positioning

JHE is the field flagship for health economics, publishing the most consequential work on healthcare markets, insurance, provider behavior, health behaviors, and health policy. It rewards papers that answer a substantive health-economics question with credible identification and an economic mechanism, not just a health-services correlation. The readership is health economists and applied microeconomists, so the paper must combine policy relevance with state-of-the-art causal inference or structural modeling.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier site and the editorial submission system.

## When to trigger

- The author names JHE as the target venue, or wants the health-economics field flagship.
- A health-economics paper has credible identification but is narrower than a top-5 general-interest result.
- A health-services or health-policy paper needs re-framing so the contribution reads as economics — markets, incentives, behavior — rather than description.
- The author needs JHE's desk-reject risks and a credible health/applied-micro alternative list.

## Scope & topic fit

- Healthcare markets, provider and hospital behavior, competition, and pricing.
- Health insurance: design, selection, moral hazard, and reform evaluation.
- Health behaviors and the production of health (risky behaviors, prevention, addiction).
- Health policy and program evaluation, mortality/morbidity outcomes, and the economics of long-term care and aging.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the health-economics question, the data, the identification/structure, and the headline result early, and says why it matters for health markets or policy.
- Position against the relevant health-economics literature; "first to study X in healthcare setting Y" is not a contribution without an advance.
- Uses an unstructured abstract and JEL codes; an online appendix carries robustness, heterogeneity, and data detail.
- Exhibits report interpretable magnitudes and transparent identification (event studies, balance, first stages), not only point estimates.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Health Economics guide for authors / submission guidelines" and follow the current Elsevier version.
- Re-check formatting, abstract/JEL requirements, anonymization, and figure/table standards on the submission system.
- Re-check the current data and code availability / replication policy and any ethics/IRB and data-use disclosures for health data.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters for healthcare markets, insurance, or health policy.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current health-economics frontier on this question.
- [ ] Data, code, and any health-data disclosures are ready for the official policy.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- "First to study X in healthcare context Y" with no economic mechanism or methodological advance.
- A paper that is really clinical/epidemiological with no economics contribution.

## Re-routing decision

- General-interest at the top → `american-economic-review`; broad applied micro → the AEA applied outlet or `review-of-economics-and-statistics`.
- Labor/education/welfare-adjacent health → `journal-of-human-resources`; public-finance/insurance-policy core → `journal-of-public-economics`.
- Urban/regional health access → `journal-of-urban-economics`; technically heavy identification/structure → `international-economic-review` or `journal-of-applied-econometrics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Health Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / structure clear JHE's field bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / data-code policy / health-data ethics / exhibits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
