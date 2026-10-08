---
name: journal-of-public-economics
description: Use when targeting Journal of Public Economics (JPubE) or deciding whether a public-economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Public Economics (journal-of-public-economics)

## Journal positioning

The Journal of Public Economics (JPubE) is the field flagship for public economics, publishing the most consequential work on taxation, public goods, social insurance, redistribution, and political economy. The paper that wins here links a credibly identified effect or a public-finance model to a question about government policy and welfare — the contribution is a mechanism plus a welfare-relevant takeaway, not just a clean estimate. The readership is public economists who care about the design and consequences of public policy.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names JPubE (or a top public-economics outlet) as the target venue.
- A paper studies taxes, transfers, public goods, or government behavior and the author is choosing among public and applied-micro venues.
- An applied-micro paper needs re-framing so the public-finance mechanism and welfare relevance, not the dataset, is the contribution.
- The author needs JPubE's desk-reject risks and a credible public / applied-micro alternative list before submitting.

## Scope & topic fit

- Taxation: incidence, behavioral responses, optimal tax, evasion, and tax-policy design.
- Social insurance and transfers: unemployment, disability, health, pensions, and means-tested programs.
- Public goods, externalities, local public finance, and the economics of government provision.
- Political economy, public choice, and the determinants and effects of policy when framed around public-sector questions.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the policy question, the identification, the mechanism, the headline magnitude, and the welfare/policy implication, and says why it matters for public economics.
- Make the contribution explicit against the closest public-finance work; tie the empirical estimate to a welfare or optimal-policy framework where relevant.
- The journal uses an unstructured abstract and JEL codes; an online appendix carries robustness, derivations, and data construction.
- Exhibits report economic magnitudes, elasticities, and welfare-relevant quantities; the central result should be legible from one table or figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Public Economics guide for authors / submission guidelines" and follow the current Elsevier version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, the online-appendix policy, and the data & code / replication availability requirements.
- Re-check the current code-and-replication-package expectation and any structured-submission or pre-registration routes on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this changes how we think about a public policy and its welfare consequences.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current public-economics frontier on this question.
- [ ] The estimate connects to a welfare or optimal-policy reading and the replication package is ready.

## Common desk-reject triggers

- A clean estimate with no public-finance mechanism or welfare relevance.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A tax/transfer correlation with no source of exogenous variation and no welfare reading.
- A paper that is really labor, health, or development economics with no public-sector core framed as public.

## Re-routing decision

- General-interest public at top-5 ambition → `american-economic-review` or `aej-economic-policy`.
- Labor outcomes without a public-finance core → `journal-of-labor-economics`; health policy → `journal-of-health-economics`.
- Public policy in low/middle-income settings → `journal-of-development-economics`; broad applied micro → `aej-applied-economics` or `review-of-economics-and-statistics`.
- Optimal-tax or mechanism theory → `journal-of-economic-theory`; political-economy with a macro/growth core → `journal-of-economic-growth`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Public Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification + welfare relevance clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / online appendix / replication / pre-registration>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
