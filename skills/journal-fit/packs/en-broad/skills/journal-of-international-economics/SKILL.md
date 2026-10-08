---
name: journal-of-international-economics
description: Use when targeting Journal of International Economics (JIE) or deciding whether an international trade or international macro/finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of International Economics (journal-of-international-economics)

## Journal positioning

The Journal of International Economics (JIE) is the field flagship for both international trade and international macro/finance, publishing the most consequential theory and empirics on the international economy. The paper that wins here advances how the field understands trade flows, gains from trade, exchange rates, capital flows, or global imbalances — through a quantitative trade model, an open-economy macro model, or a credibly identified empirical study. The readership spans trade and open-economy macro economists, so the contribution must matter to one of those communities, not merely apply a familiar method to international data.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names JIE (or a top international outlet) as the target venue.
- A paper studies trade, exchange rates, or capital flows and the author is choosing among international and general/field venues.
- An applied or theory paper needs re-framing so the international mechanism — trade gains, transmission, openness — is the contribution.
- The author needs this venue's desk-reject risks and a credible trade / international-macro alternative list before submitting.

## Scope & topic fit

- International trade: theory and empirics of trade flows, gains from trade, firms and exporters, global value chains, trade policy, and tariffs.
- Quantitative trade models: gravity, Eaton-Kortum / Melitz-class frameworks, and counterfactual analysis of trade and policy.
- International macro and finance: exchange rates, current accounts, capital flows, global imbalances, sovereign debt, and international transmission.
- Open-economy mechanisms studied with discipline, whether through structural quantitative models or credible empirical identification.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the international question, the model or identification, the mechanism, and the quantitative headline, and says why it matters for trade or open-economy macro.
- Make the contribution explicit against the closest quantitative-trade or international-macro work; connect the model to the empirical or counterfactual design.
- The journal uses an unstructured abstract and JEL codes; an online appendix carries derivations, additional counterfactuals, and robustness.
- Exhibits report magnitudes, gravity estimates, impulse responses, or counterfactual effects; the central mechanism should be legible from a key figure or table.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of International Economics guide for authors / submission guidelines" and follow the current Elsevier version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, the online-appendix policy, and the data & code / replication availability requirements.
- Re-check the current code-and-replication-package expectation and any structured-submission requirements on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why a trade or international-macro economist should change their view because of this paper.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current quantitative-trade / international-macro frontier.
- [ ] The replication package (code, data, calibration/estimation targets) is ready and reproducible.

## Common desk-reject triggers

- A quantitative trade or open-economy model with one extra feature and no new mechanism or counterfactual insight.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A calibration that hits targets without a transparent mechanism or defensible counterfactual.
- A domestic applied or macro paper with no genuine international dimension framed as international economics.

## Re-routing decision

- General-interest international at top-5 ambition → `american-economic-review` or `aej-macroeconomics`.
- Closed-economy quantitative macro and monetary transmission → `journal-of-monetary-economics`; money/banking-international → `journal-of-money-credit-and-banking`.
- Long-run growth and cross-country development → `journal-of-economic-growth`; trade-and-development in low/middle-income settings → `journal-of-development-economics`.
- IO of firms/markets without an international core → `rand-journal-of-economics`; pure trade theory mechanism → `journal-of-economic-theory`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of International Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the quantitative model / identification clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / online appendix / replication package / formatting>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
