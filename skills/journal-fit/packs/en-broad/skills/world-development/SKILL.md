---
name: world-development
description: Use when targeting World Development or deciding whether a development-studies manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# World Development (world-development)

## Journal positioning

World Development is a leading multidisciplinary development-studies journal, not a pure economics journal. It publishes policy-engaged work on poverty, inequality, institutions, health, education, agriculture, environment, conflict, and governance across the global South, drawing on economics, political science, sociology, geography, and other social sciences. What wins here is a paper that advances understanding of a real development problem and speaks to policy and practice, whether the evidence is quantitative, qualitative, or mixed. The readership is interdisciplinary development scholars and practitioners, so a narrowly technical econ paper with no development substance is a poor fit.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier / journal site and the submission system.

## When to trigger

- The author names World Development as the target venue.
- A development paper sits between economics and the wider social sciences and the author is unsure whether to aim for an econ field journal or a development-studies venue.
- A general applied or qualitative manuscript needs re-framing around a development problem and a policy-relevant contribution.
- The author needs World Development's desk-reject risks and a credible development / field alternative list.

## Scope & topic fit

- Poverty, inequality, livelihoods, and human development outcomes in low- and middle-income countries.
- Institutions, governance, political economy of development, aid, and state capacity.
- Agriculture, food security, rural development, land, and natural-resource management.
- Health, education, gender, migration, and social policy in development contexts.
- Environment, climate, and sustainability as they intersect with development and poverty.
- Both rigorous quantitative work and serious qualitative / mixed-methods studies are in scope.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should frame a development problem, its policy stakes, and the specific gap the paper fills for a multidisciplinary audience.
- State the contribution in substantive development terms and connect findings to policy or practice without overclaiming causality.
- Engage literatures beyond economics where relevant; signpost the disciplinary lens clearly.
- Abstracts and keywords are used for an interdisciplinary readership; check current structured-abstract and keyword conventions.
- Online appendices carry secondary material; figures and tables should be legible to non-specialists.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "World Development submission guidelines / guide for authors" and follow the current Elsevier version, not a third-party copy.
- Re-check word/figure limits, abstract and keyword format, reference style, declaration of interests, and any structured-abstract requirement.
- Re-check the current research-data and code availability policy, ethics/IRB and informed-consent expectations for human-subjects fieldwork.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this paper matters to a multidisciplinary development readership, not just to economists.
- [ ] The contribution is stated as a development insight / mechanism / measurement, not as statistical significance.
- [ ] The introduction positions the paper against recent development-studies and field literature, including non-economics work where relevant.
- [ ] Methods are rigorous within their tradition and honest about limits; ethics and data policy are satisfied.
- [ ] Findings connect explicitly to policy or practice without overclaiming.

## Common desk-reject triggers

- A purely technical econometrics or theory paper with no development substance or policy relevance.
- "First study of X in country Y" with no conceptual, methodological, or policy advance.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A high-income-country paper with no global-development angle.
- Qualitative work without transparent design or that reads as anecdote.

## Re-routing decision

- Strong development economics with sharp identification → `journal-of-development-economics` or `world-bank-economic-review`; broader top-5 general interest → `american-economic-review`.
- Open-economy macro / crises / capital flows in developing countries → `imf-economic-review` or `journal-of-international-economics`.
- Public-policy-facing applied economics → `journal-of-public-economics` or `economic-policy`.
- Spatial / regional / agglomeration framing → `journal-of-economic-geography`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] World Development
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the development contribution and method rigor clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / abstract-keywords / data policy / ethics / limits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
