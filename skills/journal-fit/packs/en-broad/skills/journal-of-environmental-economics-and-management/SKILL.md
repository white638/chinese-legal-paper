---
name: journal-of-environmental-economics-and-management
description: Use when targeting Journal of Environmental Economics and Management (JEEM) or deciding whether an environmental- or resource-economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Environmental Economics and Management (journal-of-environmental-economics-and-management)

## Journal positioning

JEEM is the field flagship for environmental and resource economics, associated with the Association of Environmental and Resource Economists (the AERE). It publishes the most consequential work on valuation, externalities, climate and energy policy, and regulation, judged on whether the question and method advance the field. The readership is environmental and resource economists, so a paper must combine a substantive environmental question with credible identification, valuation, or structural modeling.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier site and the editorial submission system.

## When to trigger

- The author names JEEM as the target venue, or wants the environmental/resource-economics field flagship.
- An environmental-economics paper has credible identification or valuation but is narrower than a top-5 result.
- An energy, climate, or regulation paper needs re-framing so the contribution reads as environmental economics — externalities, valuation, policy — rather than engineering or pure policy.
- The author needs JEEM's desk-reject risks and a credible environmental/resource alternative list.

## Scope & topic fit

- Non-market valuation: revealed and stated preference, hedonics, recreation demand, ecosystem services.
- Externalities and pollution: emissions, abatement, environmental health, and damages.
- Climate and energy economics: climate policy, energy demand and markets, technology adoption.
- Environmental regulation and policy instruments: taxes, permits, standards, and their evaluation; natural-resource and fisheries/forestry economics.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the environmental question, the data or model, the identification/valuation strategy, and the headline result early, and says why it matters for environmental policy.
- Position against the relevant environmental-economics literature; "first to estimate X for resource/region Y" is not a contribution without an advance.
- Uses an unstructured abstract and JEL codes; an online appendix carries robustness, survey instruments, and modeling detail.
- Exhibits report interpretable magnitudes (willingness-to-pay, marginal damages, policy costs/benefits) with transparent identification.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Environmental Economics and Management guide for authors / submission guidelines" and follow the current Elsevier version.
- Re-check formatting, abstract/JEL requirements, anonymization, and figure/table standards on the submission system.
- Re-check the current data and code availability / replication policy and, for stated-preference work, survey-instrument and ethics requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why this result matters for valuation, externalities, or environmental policy.
- [ ] The contribution is stated as a credible value/externality/policy estimate + mechanism, not as statistical significance.
- [ ] The introduction positions the paper against the current environmental-economics frontier on this question.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A stated-preference study that ignores known design biases or lacks incentive compatibility.
- "First to study X for resource/region Y" with no economic mechanism or methodological advance.
- A paper that is really natural science / engineering / pure policy with no economics contribution.

## Re-routing decision

- General-interest at the top → `american-economic-review`; broad applied micro → the AEA applied outlet or `review-of-economics-and-statistics`.
- Energy/climate with strong policy-evaluation identification → `journal-of-public-economics`; spatial/urban environmental questions → `journal-of-urban-economics`.
- Health-and-pollution core → `journal-of-health-economics`; technically heavy structure/econometrics → `international-economic-review` or `journal-of-applied-econometrics`; broad general field → `european-economic-review`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Environmental Economics and Management
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / valuation clear JEEM's field bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / data-code policy / survey instruments / exhibits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
