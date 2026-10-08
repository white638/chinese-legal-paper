---
name: journal-of-political-economy
description: Use when targeting Journal of Political Economy (JPE) or deciding whether an economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Political Economy (journal-of-political-economy)

## Journal positioning

JPE is the Chicago-edited general-interest journal and one of the economics "top-5" (with AER, QJE, Econometrica, REStud). It carries the price-theory tradition: papers that take economic logic, incentives, and equilibrium seriously, whether the contribution is rigorous theory or careful empirics. The editorial culture rewards a disciplined economic argument — a question framed in clean economic terms with a model or mechanism behind the result — for a discipline-wide readership.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the JPE / University of Chicago Press site and the editorial submission system.

## When to trigger

- The author names JPE (or JPE as a top-5 swing) as the target venue.
- A paper has tight economic logic — a model, a price/incentive mechanism, or theory-disciplined empirics — and the author is choosing among JPE / AER / QJE.
- An empirical paper needs re-framing so the economic mechanism, not just the reduced-form effect, becomes the contribution.
- The author needs JPE's desk-reject risks and a credible top-5 / top-field alternative list.

## Scope & topic fit

- First-order questions across economics with an explicit economic-theory backbone — price theory, incentives, equilibrium, market structure, human capital, growth, public economics.
- Rigorous theory papers whose results are general and economically consequential.
- Empirical papers disciplined by a model: structural work, or reduced-form designs whose interpretation rests on a clear mechanism.
- Work that bridges theory and evidence — testing a sharp theoretical prediction with credible data.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the economic question, the mechanism or model, the approach, and the headline result, and motivates why the economics is interesting and general.
- Make the theoretical and empirical contributions distinct and mutually reinforcing; let the model discipline the interpretation of the evidence.
- JPE uses an unstructured abstract and JEL codes; proofs, derivations, and secondary results belong in an appendix or online supplement.
- Exhibits and propositions should be self-contained; the central result — theorem or estimate — should be legible on its own.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Political Economy submission guidelines" and the data and code availability policy, and follow the current UChicago Press / editorial versions.
- Re-check the submission fee, formatting, abstract/JEL requirements, anonymization expectations, and figure/table standards on the submission system.
- Re-check the current data/code deposit and verification workflow (replication package archive) — confirm it is enforced before acceptance.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the economic mechanism or model that makes this a JPE-style contribution.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current top-5 frontier and the economic question it advances.
- [ ] Data and code are ready for the availability + verification workflow.

## Common desk-reject triggers

- A reduced-form empirical paper with no economic mechanism or model behind the result.
- A theory paper that is a narrow extension with no general or surprising implication.
- "First to study X in context Y" framing without a disciplined economic argument or conceptual advance.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.

## Re-routing decision

- General-interest but a better fit elsewhere in the top-5 → `american-economic-review` (broad importance) or `quarterly-journal-of-economics` (big question + clean experiment).
- Pure theory / mechanism design → `econometrica` (theorem with proofs) or `aej-microeconomics` / `journal-of-economic-theory`.
- Excellent but narrower applied micro → `aej-applied-economics` or `review-of-economics-and-statistics`; macro/growth → `aej-macroeconomics`.
- Policy-facing applied economics → `aej-economic-policy` or `journal-of-public-economics`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Political Economy
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the economic argument + identification/theory clear JPE's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / JEL / data-code policy / exhibits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
