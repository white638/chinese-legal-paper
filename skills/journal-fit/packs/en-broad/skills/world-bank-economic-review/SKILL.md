---
name: world-bank-economic-review
description: Use when targeting World Bank Economic Review (WBER) or deciding whether a development-economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# World Bank Economic Review (world-bank-economic-review)

## Journal positioning

The World Bank Economic Review is one of the World Bank's flagship economics journals, focused on empirical, policy-relevant development economics for a development-policy audience. It publishes micro and macro development research whose results inform real policy choices in low- and middle-income countries — the contribution is judged on both econometric credibility and policy salience. The readership is development economists and policy analysts, including inside the Bank and other development institutions, so the paper must be rigorous economics and clearly relevant to development practice.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Oxford University Press / journal site and the submission system.

## When to trigger

- The author names WBER as the target venue.
- A development-economics paper has credible empirics and a clear policy reading, and the author is choosing between WBER and a generalist or field venue.
- A general applied paper needs re-framing around a development-policy question and audience.
- The author needs WBER's desk-reject risks and a credible development / field alternative list.

## Scope & topic fit

- Empirical microeconomics of development: poverty, human capital, health, education, labor, firms, credit, and program evaluation in developing countries.
- Macro and trade questions for developing economies with policy relevance.
- Impact evaluations and policy-relevant causal estimates, including RCTs and quasi-experimental designs.
- Measurement and data contributions on development outcomes when they advance policy understanding.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should state the development-policy question, the identification strategy, the headline magnitude, and the policy implication early.
- Frame the contribution as a policy-relevant causal or measurement advance, not as a generic empirical exercise.
- Use an abstract and JEL codes; relegate robustness and secondary results to an online appendix.
- Exhibits should report economically and policy-meaningful magnitudes, legible to a policy-analyst reader.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "World Bank Economic Review submission guidelines / instructions to authors" and follow the current OUP version.
- Re-check word/figure limits, abstract and JEL requirements, reference style, anonymization/double-blind expectations, and disclosure.
- Re-check the current data and code availability / replication policy and any pre-registration expectations for experimental work.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters for development policy, not only for the literature.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against recent development-economics work at this venue's tier.
- [ ] Data and code are ready for the replication / availability workflow.

## Common desk-reject triggers

- A high-income-country paper with no development angle.
- Correlational policy claims with no credible source of variation.
- A general applied-micro paper with no policy reading for a development audience.
- Significance reported without economic magnitude, mechanism, or external-validity discussion.

## Re-routing decision

- Top development-economics frontier with broad methodological ambition → `journal-of-development-economics`; general top-5 interest → `american-economic-review`.
- Multidisciplinary, policy-engaged, or qualitative development work → `world-development`.
- Open-economy macro / crises / capital flows in developing economies → `imf-economic-review`.
- Public-finance-core policy questions → `journal-of-public-economics`; European policy framing → `economic-policy`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] World Bank Economic Review
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification and policy relevance clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / blinding / JEL / data-code-replication / pre-registration>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
