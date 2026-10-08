---
name: review-of-accounting-studies
description: Use when targeting Review of Accounting Studies (RAST) or deciding whether an accounting manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Review of Accounting Studies (review-of-accounting-studies)

## Journal positioning

RAST is a top-tier accounting journal known for rigorous analytical and empirical research, with particular depth in valuation, disclosure, and the information economics of accounting. It is receptive to both well-built analytical models and strong empirical work, and prizes methodological care. Its taste sits close to the economics-based accounting tradition while remaining open across financial-accounting topics. Readership is the research-active financial-accounting and accounting-finance community.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the RAST / Springer site and the submission system.

## When to trigger

- The author names RAST (or the analytical/empirical financial-accounting elite) as the venue.
- A valuation, disclosure, or information-economics accounting paper — analytical or empirical — needs positioning.
- An analytically grounded empirical paper whose strength is methods and modeling needs framing.
- The author needs RAST's desk-reject risks and a credible TAR / JAR / JAE / CAR alternative list.

## Scope & topic fit

- Equity valuation, fundamental analysis, forecasting, and the accounting–value link.
- Disclosure and information economics: voluntary disclosure, information asymmetry, analysts, and market consequences.
- Analytical accounting models with empirically relevant implications and the empirical tests that follow them.
- Earnings, reporting quality, and capital-markets questions with strong design.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the valuation/disclosure/information question, the model or design, and the contribution, distinguishing it from the closest prior work.
- A strong RAST paper integrates theory and evidence and treats methodological choices as load-bearing, not incidental.
- RAST expects an online appendix for derivations, variable detail, and robustness, with strong data/code transparency.
- Writing is precise and methods-aware; magnitudes and mechanisms lead over significance stars.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Review of Accounting Studies submission guidelines / author instructions" and follow the current Springer version.
- Re-check formatting, abstract conventions, anonymization, reference style, and the online-appendix/supplementary-materials requirement.
- Re-check current data and code availability / replication policies and disclosure/ethics requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the valuation/disclosure/information-economics contribution.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against recent RAST / top-accounting work.
- [ ] Derivations/online appendix and data/code transparency are ready per the current guide.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- An analytical model with no empirically relevant or testable implications.
- A methodologically careless valuation/disclosure paper.
- A descriptive paper with no clear contribution to the literature.

## Re-routing decision

- Economics-based archival capital-markets with the highest design bar → `journal-of-accounting-research`; contracting/disclosure with positive-theory emphasis → `journal-of-accounting-and-economics`.
- Broad accounting across methods → `the-accounting-review`; methodologically pluralistic elite → `contemporary-accounting-research`.
- Interpretive/critical/behavioral-in-context → `accounting-organizations-and-society`.
- Valuation work that is really asset pricing → `journal-of-finance` / `journal-of-financial-economics`; economics-core → a field economics venue.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Review of Accounting Studies
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the model / identification clear RAST's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / online appendix / data-code / disclosure>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
