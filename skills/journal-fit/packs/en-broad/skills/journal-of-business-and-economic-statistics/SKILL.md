---
name: journal-of-business-and-economic-statistics
description: Use when targeting Journal of Business and Economic Statistics (JBES) or deciding whether a manuscript at the statistics/econometrics interface fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Business and Economic Statistics (journal-of-business-and-economic-statistics)

## Journal positioning

JBES is an American Statistical Association journal at the interface of statistics and econometrics, publishing both methodological contributions and serious applications to business and economic data. Its territory is time series and forecasting, microeconometrics, and statistical methods applied to economic problems, with the dual standard of statistical soundness and economic relevance. The readership spans statisticians and econometricians, so a paper must be rigorous as method and meaningful as economics/business.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the ASA / Taylor & Francis site and the editorial submission system.

## When to trigger

- The author names JBES as the target venue, or wants a statistics/econometrics-interface home.
- A paper develops a statistical/econometric method with a clear business or economic application.
- A time-series, forecasting, or microeconometric paper needs re-framing so the methodological contribution and rigor are foregrounded.
- The author needs JBES's desk-reject risks and a credible methods-interface alternative list.

## Scope & topic fit

- Time series econometrics and forecasting, including volatility, macro/financial time series, and forecast evaluation.
- Microeconometrics applied to business and economic microdata.
- Statistical methodology developed for, or evaluated on, economic and business problems.
- Bayesian and computational methods with economic/business applications.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the problem, the methodological contribution, and the application early, and explains the statistical and economic relevance.
- Position against the relevant statistics/econometrics literature; relate properties and performance to existing methods explicitly.
- Uses an unstructured abstract; a supplement carries proofs, derivations, simulations, and replication materials.
- Exhibits report estimates/forecasts with proper inference and honest benchmark comparisons; simulation evidence supports method claims.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Business and Economic Statistics submission guidelines / instructions for authors" and follow the current ASA/Taylor & Francis version.
- Re-check formatting, abstract requirements, anonymization, and supplement/code standards on the submission system.
- Re-check the current data and code / reproducibility policy and supplementary-materials requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the methodological contribution and the business/economic problem it serves.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the relevant statistics/econometrics frontier.
- [ ] Code, data, and supplement are ready for the reproducibility policy.

## Common desk-reject triggers

- A method paper with no application or no demonstrated advantage over existing tools.
- An application with inappropriate or under-justified statistical methods.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Significance reported without method validation, magnitude, or relevance.

## Re-routing decision

- Pure econometric theory → `journal-of-econometrics`; methods-in-application with rich data and replication → `journal-of-applied-econometrics`.
- Technically heavy econometrics/theory → `international-economic-review`; general-interest applied result → `american-economic-review`.
- Quantitative-macro time series with a structural model → `review-of-economic-dynamics` or `journal-of-monetary-economics`; broad general field → `european-economic-review`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Business and Economic Statistics
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the method + application clear JBES's interface bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / abstract / supplement / reproducibility / code>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
