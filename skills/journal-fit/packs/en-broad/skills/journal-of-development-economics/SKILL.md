---
name: journal-of-development-economics
description: Use when targeting Journal of Development Economics (JDE) or deciding whether a development-economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Development Economics (journal-of-development-economics)

## Journal positioning

The Journal of Development Economics (JDE) is the field flagship for development economics, publishing the most consequential micro-development work and the growth-and-institutions questions of low- and middle-income economies. The paper that wins here pairs a first-order development question with credible identification — an RCT, a natural experiment, or a structural model — in a low/middle-income setting, and draws a lesson that travels beyond the one context. The readership is development economists who care about poverty, growth, and policy in the developing world.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names JDE (or a top development outlet) as the target venue.
- A paper studies a development question in a low/middle-income setting and the author is choosing among development and applied-micro venues.
- An applied-micro or field-experiment paper needs re-framing so the development mechanism and external lesson, not the single-site result, is the contribution.
- The author needs JDE's desk-reject risks and a credible development / applied-micro alternative list before submitting.

## Scope & topic fit

- Micro-development: RCTs and quasi-experiments on health, education, credit, agriculture, firms, labor, and social programs in developing economies.
- Poverty, inequality, and the economic lives of the poor; risk, insurance, and informal institutions.
- Growth, structural transformation, and institutions in low/middle-income settings when framed for a development audience.
- Political economy, conflict, migration, and governance in developing contexts.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the development question, the design/identification, the mechanism, the headline magnitude, and the external lesson, and says why it matters for development.
- Make the contribution explicit against the closest development work; "first to run X intervention in country Y" is not enough — name the conceptual or policy advance.
- The journal uses an unstructured abstract and JEL codes; an online appendix carries the pre-analysis plan link, robustness, balance/attrition tables, and data construction.
- Exhibits report economic magnitudes, treatment effects with proper inference, and mechanism evidence; the central result should be legible from one table or figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Development Economics guide for authors / submission guidelines" and follow the current Elsevier version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, the online-appendix policy, the data & code / replication availability requirements, and any registered-report route.
- Re-check the current pre-registration / pre-analysis-plan and trial-registry expectations, ethics/IRB disclosure, and the replication-package requirement on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why a development economist should change their view, and what this teaches beyond the study site.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current micro-development / growth-and-institutions frontier.
- [ ] Pre-analysis plan, ethics/IRB, data, and the replication package are documented and ready.

## Common desk-reject triggers

- A single-site RCT with a significant effect but no mechanism and no argument for external relevance.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.

## Re-routing decision

- General-interest development at top-5 ambition → `american-economic-review` or `aej-applied-economics`.
- Long-run growth, deep roots, and cross-country development → `journal-of-economic-growth`.
- Labor outcomes in developing settings without a development core → `journal-of-labor-economics`; public programs/taxation → `journal-of-public-economics`.
- Broad development practice and policy → `world-development`; health interventions → `journal-of-health-economics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Development Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification + external lesson clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / pre-analysis plan / ethics / replication>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
