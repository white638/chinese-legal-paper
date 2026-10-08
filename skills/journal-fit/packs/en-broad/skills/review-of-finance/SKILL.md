---
name: review-of-finance
description: Use when targeting Review of Finance or deciding whether a finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Review of Finance (review-of-finance)

## Journal positioning

Review of Finance is the flagship journal of the European Finance Association and the leading European top-tier finance journal, broad and rigorous across the major subfields. It sits just below the finance "top-3" (JF/JFE/RFS) in the elite tier: it wants serious, well-identified contributions to asset pricing, corporate finance, banking, and microstructure, and is a natural home for excellent work that is one notch narrower than a top-3 paper. The readership is international and spans the whole finance profession.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the EFA / Review of Finance / Oxford site and the editorial submission system.

## When to trigger

- The author names Review of Finance (or the elite European/field tier) as the target venue.
- A finance paper is strong and well-identified but narrower than a JF/JFE/RFS contribution, and the author wants a top elite-tier home.
- An applied paper using financial data needs re-framing into a finance contribution with a clear mechanism.
- The author needs Review of Finance's desk-reject risks and a credible top-3 / elite-field alternative list.

## Scope & topic fit

- Asset pricing (empirical and theoretical), cross-section of returns, factor models, with credible robustness.
- Corporate finance, governance, M&A, capital structure, payout, ownership, with credible identification.
- Banking/intermediation, liquidity, market microstructure, household and behavioral finance.
- Internationally oriented finance questions and well-executed work across the field's core paradigms.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the economic mechanism, the identification, and the headline magnitude early, and explains why it matters for finance.
- Distinguish the contribution from the nearest top-3 and Review of Finance papers explicitly; "no one has tested X" is not a contribution.
- Review of Finance uses an unstructured abstract and JEL codes; an Internet Appendix carries robustness and secondary results.
- Exhibits report economic magnitudes (not only t-stats); the central result should be readable from one table.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Review of Finance submission guidelines" and follow the current EFA/Oxford version.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and the disclosure policy (data sources, conflicts, prior circulation).
- Re-check the current data/code and Internet Appendix requirements and any replication expectations.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters to the broad finance profession.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the most recent top-3 and Review of Finance work on this question.
- [ ] Disclosure, data sources, and the Internet Appendix are ready.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Significant coefficients reported without economic magnitude or mechanism.
- A paper that is really accounting or economics framed as finance, or a thin contribution better suited to a broad-volume outlet.

## Re-routing decision

- Top-3 importance → `journal-of-finance`, `journal-of-financial-economics`, `review-of-financial-studies`.
- Peer elite-field venues → `journal-of-financial-and-quantitative-analysis`, `journal-of-corporate-finance`, `journal-of-financial-intermediation`.
- Banking/markets/international → `journal-of-banking-and-finance`, `journal-of-financial-markets`, `journal-of-international-money-and-finance`.
- Quantitative/derivatives theory → `mathematical-finance`; econometrics-of-finance → `journal-of-empirical-finance`; practitioner-relevant corporate finance → `financial-management`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Review of Finance
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / mechanism clear the elite-finance bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / disclosure / Internet Appendix / data>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
