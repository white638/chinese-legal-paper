---
name: journal-of-risk-and-uncertainty
description: Use when targeting Journal of Risk and Uncertainty (JRU) or deciding whether a decision-under-risk manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Risk and Uncertainty (journal-of-risk-and-uncertainty)

## Journal positioning

The Journal of Risk and Uncertainty is the leading specialist journal on decision-making under risk and uncertainty. It publishes work on expected utility and its alternatives, ambiguity, behavioral decision theory, and the valuation of risks to life and health — spanning economics, psychology, and decision science. What wins here is a paper that advances how we model or measure choice under risk: a new theory of preferences, a clean test discriminating among models, or a credible valuation of risk. The readership is decision theorists, risk-and-insurance economists, and behavioral researchers.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Springer / journal site and the submission system.

## When to trigger

- The author names JRU as the target venue.
- A paper on risk preferences, ambiguity, or risk valuation needs a specialist decision-science home.
- A behavioral or experimental paper centers on choice under risk/uncertainty and needs re-framing toward the decision-theory contribution.
- The author needs JRU's desk-reject risks and a credible decision-science / behavioral alternative list.

## Scope & topic fit

- Expected utility theory and non-expected-utility alternatives (prospect theory, rank-dependent, etc.); axiomatic and behavioral models of risk preference.
- Ambiguity and decision under uncertainty: models, measurement, and experimental tests.
- Behavioral decision theory: framing, probability weighting, reference dependence, and anomalies.
- Valuation of risk, including value of statistical life, health and mortality risk, and risk-related insurance and policy questions.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should state the decision-theoretic question, what existing models miss, and how the paper resolves or tests it.
- Frame the contribution as a model, a discriminating test, or a valuation advance — situate it among the standard risk-preference models.
- Use an abstract and (where applicable) JEL codes; relegate proofs, instructions, and robustness to appendices.
- Exhibits should make the model comparison or valuation legible, with clear treatment of incentives and parameter estimates.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Risk and Uncertainty submission guidelines / instructions for authors" and follow the current Springer version.
- Re-check word/figure limits, abstract and JEL/keyword requirements, reference style, anonymization expectations, and disclosure.
- Re-check the current data and code availability policy, experimental-materials / pre-registration expectations, and ethics approval for human-subjects experiments.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating how this advances modeling or measurement of choice under risk/uncertainty.
- [ ] The contribution is stated as a preference model / discriminating test / valuation, not as a significant effect.
- [ ] The design genuinely discriminates among competing risk models or credibly identifies a valuation.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The paper is centrally about risk/uncertainty, not generic behavioral economics.

## Common desk-reject triggers

- A generic behavioral or applied paper with no specific decision-under-risk contribution.
- A new "anomaly" demonstration that does not discriminate among existing models or advance theory.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.

## Re-routing decision

- Broad behavioral / institutional / experimental economics → `journal-of-economic-behavior-and-organization`.
- Decision-theoretic results aimed at general theory audiences → `journal-of-economic-theory` or `games-and-economic-behavior`.
- Risk valuation as health policy → `journal-of-health-economics`; as public policy → `journal-of-public-economics`.
- Finance-risk / asset-pricing framing → `journal-of-finance`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Risk and Uncertainty
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the decision-under-risk contribution clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL-keywords / data-code / pre-registration / ethics>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
