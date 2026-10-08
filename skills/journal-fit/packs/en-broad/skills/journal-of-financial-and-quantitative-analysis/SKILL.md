---
name: journal-of-financial-and-quantitative-analysis
description: Use when targeting Journal of Financial and Quantitative Analysis (JFQA) or deciding whether a finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Financial and Quantitative Analysis (journal-of-financial-and-quantitative-analysis)

## Journal positioning

The Journal of Financial and Quantitative Analysis is an elite field journal in finance, published with Cambridge University Press, known for quantitatively careful empirical corporate finance and asset pricing with attention to methodological soundness. It sits in the top elite tier just below the finance "top-3" (JF/JFE/RFS): JFQA rewards clean, well-measured, technically disciplined work rather than the broadest splash. The readership is the academic finance profession.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the JFQA / Cambridge site and the editorial submission system.

## When to trigger

- The author names JFQA (or the elite-field tier) as the target venue.
- A finance paper is quantitatively careful and well-identified but narrower than a top-3 contribution, and the author wants a strong field home.
- An applied paper using financial data needs re-framing as a methodologically clean finance contribution.
- The author needs JFQA's desk-reject risks and a credible top-3 / elite-field alternative list.

## Scope & topic fit

- Empirical asset pricing, cross-section of returns, factor models, with rigorous measurement and inference.
- Corporate finance, governance, M&A, capital structure, payout, with credible identification.
- Market microstructure, derivatives, fixed income, banking, and household finance with a quantitative bent.
- Methodologically careful empirical work where the measurement and econometrics are the point of pride.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the mechanism, the identification, and the headline magnitude early, and explains why it matters for finance.
- Distinguish the contribution from the nearest top-3 and JFQA papers explicitly; "no one has tested X" is not a contribution.
- JFQA uses an unstructured abstract and JEL codes; an online/Internet Appendix carries robustness and secondary results.
- Exhibits report economic magnitudes (not only t-stats); the central result should be readable from one table.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Financial and Quantitative Analysis submission guidelines" and follow the current Cambridge version.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and the disclosure policy (data sources, conflicts, prior circulation).
- Re-check the current data/code and online-appendix requirements and any replication expectations.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters to the academic finance profession.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the most recent top-3 and JFQA work on this question.
- [ ] Disclosure, data sources, and the online appendix are ready.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A paper that is really accounting or economics framed as finance, or a thin contribution better suited to a broad-volume outlet.

## Re-routing decision

- Top-3 importance → `journal-of-finance`, `journal-of-financial-economics`, `review-of-financial-studies`.
- Peer elite-field venues → `review-of-finance`, `journal-of-corporate-finance`, `journal-of-financial-intermediation`.
- Banking/markets/international → `journal-of-banking-and-finance`, `journal-of-financial-markets`, `journal-of-international-money-and-finance`.
- Pure empirical-methods focus → `journal-of-empirical-finance`; quantitative/derivatives theory → `mathematical-finance`; practitioner-relevant → `financial-management`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Financial and Quantitative Analysis
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the measurement / identification clear the elite-field bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / disclosure / online appendix / data>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
