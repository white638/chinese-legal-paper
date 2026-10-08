---
name: journal-of-financial-economics
description: Use when targeting Journal of Financial Economics (JFE) or deciding whether a finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Financial Economics (journal-of-financial-economics)

## Journal positioning

The Journal of Financial Economics is an Elsevier journal and, with JF and RFS, one of the finance "top-3." It publishes the most consequential empirical and theoretical work across asset pricing, corporate finance, banking/intermediation, and household finance, with a long-standing reputation for quantitatively serious, often structural, analysis and an unusually high robustness-and-identification bar. The readership is the whole finance profession, so a paper must clear a top-3 importance threshold and not merely a field-journal one.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier / JFE site and the editorial submission system.

## When to trigger

- The author names JFE (or the finance top-3) as the target venue.
- A finance paper has a tight research design, a structural model, or a genuinely new asset-pricing/corporate-finance result, and the author is choosing among JF / JFE / RFS.
- An applied paper using financial data needs re-framing into a finance contribution rather than an economics or accounting one.
- The author needs JFE's desk-reject risks and a credible top-3 / top-field alternative list.

## Scope & topic fit

- Asset pricing (empirical and theoretical), cross-section of returns, factor models, intermediary and macro-finance asset pricing — with a very high bar for "new factor / new anomaly" claims.
- Corporate finance, governance, M&A, capital structure, payout, ownership, with credible identification.
- Financial intermediation, banking, liquidity, market microstructure, household and behavioral finance.
- Structural and quantitative work where a model is estimated or calibrated and confronted with data.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the economic mechanism, the identification or model, and the headline magnitude early, and explains why it matters for finance broadly.
- Distinguish the contribution from the nearest JF/JFE/RFS papers explicitly; "no one has tested X" is not a contribution.
- JFE uses an unstructured abstract and JEL codes; an Internet Appendix carries robustness, derivations, and secondary results.
- Exhibits report economic magnitudes (not only t-stats); the central result should be readable from one table or one figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Financial Economics guide for authors" and follow the current Elsevier/JFE version.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and the disclosure policy (data sources, conflicts, prior circulation).
- Re-check the current data/code and Internet Appendix requirements and any replication expectations.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters to the broad finance profession.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the most recent JF/JFE/RFS work on this question.
- [ ] Disclosure, data sources, and the Internet Appendix are ready.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A structural model that is calibrated arbitrarily or not confronted with data.
- A paper that is really accounting (`the-accounting-review`, `journal-of-accounting-and-economics`) or economics (`journal-of-political-economy`) framed as finance.

## Re-routing decision

- Equally strong but more methodologically innovative / theory-forward → `review-of-financial-studies`; broad top-3 importance → `journal-of-finance`.
- Second-tier-elite finance → `review-of-finance`, `journal-of-financial-and-quantitative-analysis`, `journal-of-corporate-finance`.
- Banking/intermediation, markets, or international → `journal-of-financial-intermediation`, `journal-of-financial-markets`, `journal-of-international-money-and-finance`; large-volume applied → `journal-of-banking-and-finance`.
- Pure quantitative/derivatives theory → `mathematical-finance`; econometrics-of-finance methods → `journal-of-empirical-finance`; macro-finance → `journal-of-monetary-economics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Financial Economics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / model / mechanism clear the finance top-3 bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / disclosure / Internet Appendix / data>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
