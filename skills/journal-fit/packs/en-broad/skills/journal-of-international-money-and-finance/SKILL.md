---
name: journal-of-international-money-and-finance
description: Use when targeting Journal of International Money and Finance (JIMF) or deciding whether an international-finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of International Money and Finance (journal-of-international-money-and-finance)

## Journal positioning

The Journal of International Money and Finance is an Elsevier journal and a leading specialist outlet for international finance and open-economy questions: exchange rates, capital flows, international monetary policy, currency markets, and cross-border financial linkages. It sits in the strong field tier and is the natural home for serious open-economy finance work that need not have top-3 general-finance reach. The readership is international-finance and open-economy macro-finance researchers.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier / JIMF site and the editorial submission system.

## When to trigger

- The author names JIMF (or international-finance field venues) as the target venue.
- A paper studies exchange rates, capital flows, international monetary policy, or cross-border finance and the author wants a specialist home.
- A general finance or macro paper has an international/open-economy core that should be framed as such.
- The author needs JIMF's desk-reject risks and a credible international-finance / macro alternative list.

## Scope & topic fit

- Exchange-rate determination, currency markets, forward and carry-trade dynamics, and FX intervention.
- International capital flows, capital controls, sudden stops, and global financial cycles.
- International monetary policy, spillovers, transmission, and central-bank interactions across borders.
- Open-economy finance: international portfolio choice, sovereign risk, cross-border banking, and global imbalances.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the international-finance question, the mechanism, the identification or model, and the headline magnitude early.
- Distinguish the contribution from the nearest international-finance papers explicitly; "no one has run this for country set Y" is not a contribution.
- JIMF uses an unstructured abstract and JEL codes; an online appendix carries robustness and secondary results.
- Exhibits report economic magnitudes (not only t-stats); the central result should be readable from one table or figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of International Money and Finance guide for authors" and follow the current Elsevier version.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and the disclosure policy (data sources, conflicts, prior circulation).
- Re-check the current data/code and online-appendix requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters for international finance or open-economy policy.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the most recent international-finance work on this question.
- [ ] Disclosure, data sources, and the online appendix are ready.

## Common desk-reject triggers

- A domestic study with a thin "international" label and no open-economy mechanism.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Time-series work that ignores non-stationarity or cross-sectional dependence.
- A paper that is really general asset pricing, banking, or macro framed as international finance.

## Re-routing decision

- Top-3 international-finance importance → `journal-of-finance`, `journal-of-financial-economics`, `review-of-financial-studies`.
- Peer elite-field finance → `review-of-finance`, `journal-of-financial-and-quantitative-analysis`.
- Broad applied banking/finance, large volume → `journal-of-banking-and-finance`; markets/microstructure → `journal-of-financial-markets`; empirical-methods focus → `journal-of-empirical-finance`.
- International macro / trade core → `journal-of-international-economics`; monetary transmission → `journal-of-monetary-economics`, `journal-of-money-credit-and-banking`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of International Money and Finance
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the open-economy mechanism / identification clear the field bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / disclosure / online appendix / data>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
