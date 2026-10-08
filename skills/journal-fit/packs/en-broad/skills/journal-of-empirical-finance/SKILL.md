---
name: journal-of-empirical-finance
description: Use when targeting Journal of Empirical Finance (JEF) or deciding whether an empirical-finance / financial-econometrics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Empirical Finance (journal-of-empirical-finance)

## Journal positioning

The Journal of Empirical Finance is an Elsevier journal specializing in empirical finance methods and applications: the econometrics of finance, asset pricing, volatility modeling, return predictability, and the careful empirical analysis of financial data. It sits in the strong field tier with a methods-aware identity, and is the natural home for papers where the empirical method or measurement is itself a contribution. The readership is empirical and financial-econometrics researchers.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier / JEF site and the editorial submission system.

## When to trigger

- The author names JEF (or empirical-finance / financial-econometrics venues) as the target.
- A paper's contribution is an empirical method, a measurement, or a careful empirical analysis of returns, volatility, or predictability.
- A general finance paper has a methods-of-empirical-finance core that should be framed as such.
- The author needs JEF's desk-reject risks and a credible empirical-finance / top-finance alternative list.

## Scope & topic fit

- Financial econometrics: estimation and testing for asset-pricing models, volatility, and dependence in financial data.
- Empirical asset pricing, the cross-section and time series of returns, and return predictability.
- Volatility modeling and forecasting (GARCH-family, realized/high-frequency measures, stochastic volatility) and risk measurement.
- Applied empirical finance where method, measurement, or evaluation is the central contribution.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the empirical question or method, the data, the evaluation strategy, and the headline result early.
- Distinguish the contribution from the nearest empirical-finance work explicitly; "a new dataset for an old test" is rarely enough alone.
- JEF uses an unstructured abstract and JEL codes; an online appendix carries robustness, derivations, and secondary results.
- Exhibits report economic and statistical magnitudes; out-of-sample and robustness evidence are expected for predictability claims.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Empirical Finance guide for authors" and follow the current Elsevier version.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and the disclosure policy (data sources, conflicts, prior circulation).
- Re-check the current data/code and online-appendix requirements and any replication expectations.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the empirical/methodological contribution and why it matters.
- [ ] The contribution is stated as method / measurement / honest empirical evaluation, not as an in-sample significant coefficient.
- [ ] The introduction positions the paper against the most recent empirical-finance work on this question.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] Disclosure, data sources, and the online appendix are ready.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A method paper with no analysis of the method's properties (theory or simulation).
- Re-running a standard test on a new sample with no methodological or substantive advance.
- A paper that is really general asset pricing (`journal-of-financial-economics`) or pure econometrics framed as empirical finance.

## Re-routing decision

- Top-3 empirical-finance importance → `journal-of-finance`, `journal-of-financial-economics`, `review-of-financial-studies`.
- Quantitatively careful empirical finance → `journal-of-financial-and-quantitative-analysis`; peer elite-field → `review-of-finance`.
- Microstructure/high-frequency empirics → `journal-of-financial-markets`; international empirics → `journal-of-international-money-and-finance`; broad applied, large volume → `journal-of-banking-and-finance`.
- Pricing/risk theory with proofs → `mathematical-finance`; general econometric methods → `journal-of-econometrics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Empirical Finance
[Topic tags] <2–3 closest topics>
[Method/evidence] <is the empirical method / evaluation sound and out-of-sample disciplined?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / disclosure / online appendix / data>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
