---
name: journal-of-human-resources
description: Use when targeting Journal of Human Resources (JHR) or deciding whether an applied-microeconomics manuscript on labor, education, health, or welfare fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Human Resources (journal-of-human-resources)

## Journal positioning

JHR is a leading field journal for applied microeconomics on human capital and well-being — labor, education, health, and welfare/poverty — with a strong taste for microdata and credible, policy-relevant identification. It rewards careful empirical work that answers a question people care about with a research design the reader can trust. The readership is applied micro and labor/education/health economists, so the paper must combine a substantive question with state-of-the-art causal inference.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the journal/University of Wisconsin Press site and the editorial submission system.

## When to trigger

- The author names JHR as the target venue, or wants a strong applied-micro home for a labor/education/health/welfare paper.
- A microdata empirical paper has credible identification but is narrower than a top-5 general-interest result.
- A policy-evaluation paper needs re-framing so the contribution reads as a credible causal estimate with mechanism and policy relevance.
- The author needs JHR's desk-reject risks and a credible applied-micro alternative list.

## Scope & topic fit

- Labor economics: employment, wages, human capital, family, immigration, discrimination.
- Education: schooling, returns, interventions, teacher/school effects, early childhood.
- Health economics and health behaviors, especially with a human-capital or well-being angle.
- Welfare, poverty, inequality, and the evaluation of social programs and transfers.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the data, the identification strategy, and the headline estimate early, and says why the answer matters for policy or human capital.
- Position against the relevant applied-micro literature; "no one has estimated X for group Y" is not a contribution without a design or conceptual advance.
- Uses an unstructured abstract and JEL codes; an online appendix carries robustness, heterogeneity, and data detail.
- Exhibits should report interpretable magnitudes and clear identification (e.g., event-study plots, balance tables), not only point estimates.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Human Resources submission guidelines / instructions for authors" and follow the current version.
- Re-check submission fee, formatting, abstract/JEL requirements, anonymization, and figure/table standards on the submission system.
- Re-check the current data and code availability / replication policy and any deposit requirement.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this labor/education/health/welfare result matters for policy or human capital.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current applied-micro frontier on this question.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- "First to study X for population Y" with no design or conceptual advance.
- Significance reported without magnitude, mechanism, or policy interpretation.

## Re-routing decision

- General-interest at the top → `american-economic-review`; broad applied micro → the AEA applied outlet or `review-of-economics-and-statistics`.
- Labor-core and field-leading → `journal-of-labor-economics`; health-core → `journal-of-health-economics`; public/welfare-policy core → `journal-of-public-economics`.
- Urban/regional labor markets → `journal-of-urban-economics`; technically heavier econometric identification → `international-economic-review` or `journal-of-applied-econometrics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Human Resources
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification clear JHR's applied-micro bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / JEL / data-code policy / exhibits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
