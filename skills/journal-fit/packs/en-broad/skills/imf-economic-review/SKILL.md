---
name: imf-economic-review
description: Use when targeting IMF Economic Review or deciding whether an international macro / finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# IMF Economic Review (imf-economic-review)

## Journal positioning

IMF Economic Review is the official research journal of the International Monetary Fund and its flagship outlet for international macroeconomics and finance. It publishes open-economy macro, exchange rates, capital flows, sovereign debt, financial crises, and global imbalances, with a policy-relevant slant aimed at the international monetary and financial system. What wins here is rigorous theory or empirics on cross-border macro-financial questions that also speaks to policy. The readership is international-macro economists and policy researchers, including central banks and international institutions.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Springer / journal site and the submission system.

## When to trigger

- The author names IMF Economic Review as the target venue.
- An international-macro or macro-finance paper has a global / open-economy question and a policy reading, and the author is choosing among macro-finance venues.
- A domestic macro or finance paper needs re-framing around an open-economy or international-system angle.
- The author needs this venue's desk-reject risks and a credible international-macro alternative list.

## Scope & topic fit

- Open-economy macroeconomics: exchange rates, current accounts, global imbalances, international transmission.
- Capital flows, capital controls, the international monetary system, and global financial cycles.
- Financial and currency crises, sovereign debt, banking and macro-financial linkages across borders.
- Monetary and fiscal policy in open economies, spillovers, and international coordination.
- Empirical and theoretical contributions are both welcome when the question is international and policy-relevant.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should state the international macro-financial question, the mechanism or identification, and the policy stakes for the global system early.
- Frame the contribution against the open-economy macro and international-finance literature, not domestic macro alone.
- Use an abstract and JEL codes; relegate technical derivations, robustness, and additional results to an appendix.
- Exhibits should communicate magnitudes relevant to policy and the international system.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "IMF Economic Review submission guidelines / instructions for authors" and follow the current Springer version.
- Re-check word/figure limits, abstract and JEL requirements, reference style, anonymization expectations, and disclosure.
- Re-check the current data and code / replication policy and any associated archiving requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this matters for the international monetary and financial system.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against recent open-economy macro and international-finance work.
- [ ] Data and code are ready for the replication / availability workflow.

## Common desk-reject triggers

- A closed-economy or purely domestic paper with no international dimension.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A finance microstructure or corporate-finance paper with no macro / international angle.
- Policy claims unsupported by the model or data.

## Re-routing decision

- Domestic monetary / business-cycle macro → `journal-of-monetary-economics` or `aej-macroeconomics`; money and banking → `journal-of-money-credit-and-banking`.
- Trade and real open-economy questions → `journal-of-international-economics`.
- Core finance (asset pricing / corporate / banking) → `journal-of-finance`.
- Development-focused macro-financial questions → `world-bank-economic-review` or `world-development`; European policy debate → `economic-policy`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] IMF Economic Review
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the international macro-finance contribution clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / blinding / JEL / data-code / archiving>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
