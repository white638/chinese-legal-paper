---
name: journal-of-money-credit-and-banking
description: Use when targeting Journal of Money, Credit and Banking (JMCB) or deciding whether a money / banking / monetary-policy / macro-finance manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Money, Credit and Banking (journal-of-money-credit-and-banking)

## Journal positioning

The Journal of Money, Credit and Banking (JMCB) is a leading field outlet for monetary economics, banking, and macro-finance, with a strong emphasis on applied and policy-relevant work. The paper that wins here addresses a question about money, credit, banks, or monetary policy and answers it with disciplined empirics or a quantitative model that speaks to central-bank and financial-stability concerns. The readership includes monetary and financial economists, central-bank researchers, and policy analysts, so policy relevance and credible empirics matter as much as theoretical novelty.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names JMCB (or a money/banking field outlet) as the target venue.
- A paper studies monetary policy, banking, or credit and the author is choosing among macro, monetary, and finance field venues.
- An empirical-macro or banking paper needs re-framing so the money/credit mechanism and policy relevance, not just the regression, is the contribution.
- The author needs JMCB's desk-reject risks and a credible monetary / banking / macro-finance alternative list before submitting.

## Scope & topic fit

- Monetary policy: transmission, central-bank behavior, inflation, interest rates, and unconventional policy.
- Banking and financial intermediation: bank lending, capital, liquidity, regulation, and financial stability.
- Credit markets, the credit channel, and the interaction of the financial sector with the macroeconomy.
- Macro-finance and applied monetary macro where the question connects money, credit, and aggregate or policy outcomes.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the money/credit/policy question, the identification or model, the mechanism, the headline, and the policy implication, and says why it matters for monetary or banking economics.
- Make the contribution explicit against the closest monetary/banking work; tie the empirical or quantitative result to a policy reading where relevant.
- The journal uses an abstract and JEL codes; an online/supplementary appendix carries derivations, additional specifications, and robustness.
- Exhibits report magnitudes, impulse responses, and policy-relevant quantities; the central result should be legible from a key figure or table.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Money, Credit and Banking submission guidelines / author instructions" and follow the current Ohio State / Wiley version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, anonymization expectations, the supplementary-appendix policy, and the data & code availability requirements.
- Re-check the current replication/data-deposit expectation and any structured-submission requirements on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why a monetary or banking economist (or policymaker) should care about this result.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current monetary/banking frontier on this question.
- [ ] Data, code, and the replication package are documented and ready.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A quantitative model with one extra feature and no new mechanism or policy-relevant insight.
- An empirical result with statistical significance but no economic magnitude, mechanism, or policy reading.
- A general macro or corporate-finance paper with no money/credit/banking core framed for this venue.

## Re-routing decision

- Field-leading quantitative macro and monetary mechanism → `journal-of-monetary-economics`; general-interest macro → `american-economic-review` or `aej-macroeconomics`.
- Macro-finance asset pricing and intermediation at the finance top-3 → `journal-of-finance`.
- Long-run growth and development → `journal-of-economic-growth`; international monetary and capital flows → `journal-of-international-economics`.
- Quantitative dynamics → `review-of-economic-dynamics`; pure monetary theory mechanism → `journal-of-economic-theory`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Money, Credit and Banking
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / quantitative model + policy relevance clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / supplementary appendix / replication / formatting>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
