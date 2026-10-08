---
name: journal-of-the-european-economic-association
description: Use when targeting Journal of the European Economic Association (JEEA) or deciding whether a general-interest economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of the European Economic Association (journal-of-the-european-economic-association)

## Journal positioning

The Journal of the European Economic Association (JEEA) is the general-interest flagship of the European Economic Association, a broad, rigorous, near-top-5 outlet publishing the best work across all fields of economics. The paper that wins here has a first-order question, a clean method, and a result of interest beyond its subfield — the same general-interest bar as the top-5, with a strong European intellectual base and a global readership. The audience is the whole profession, so the contribution must read as important to economists outside your field.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names JEEA (or a near-top-5 general-interest outlet) as the target venue.
- A paper has a clean design and general interest, and the author is choosing between JEEA and the top-5 or a top field journal.
- A strong field paper needs re-framing so the contribution reads as discipline-wide rather than niche.
- The author needs JEEA's desk-reject risks and a credible general-interest / top-field alternative list before submitting.

## Scope & topic fit

- First-order questions across all fields of economics — micro, macro, labor, public, IO, trade, development, theory — judged on general interest.
- Empirical papers with a transparent, defensible identification strategy and a result that travels beyond one context.
- Theory papers whose results are general and consequential, not a narrow extension.
- High-quality work where the contribution is clear and the execution is rigorous, regardless of field or geography.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the contribution, the approach, and the headline result early, and says explicitly why a non-specialist should care.
- Make the marginal contribution non-overlapping and explicit against the current general-interest frontier; separate the method/identification advance from the empirical finding.
- The journal uses an unstructured abstract and JEL codes; an online appendix carries robustness and secondary results.
- Exhibits are publication-clean and self-contained; the headline result should be legible from one table or figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of the European Economic Association submission guidelines / author instructions" and follow the current EEA / Oxford University Press version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, anonymization expectations, the online-appendix policy, and the data & code availability requirements.
- Re-check the current replication/data-deposit expectation and any EEA-membership or submission routes on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why an economist outside your field should care about this result.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current general-interest / top-field frontier on this question.
- [ ] Data and code are ready for the availability and replication workflow.

## Common desk-reject triggers

- A well-executed but narrow field paper with no general-interest hook.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Contribution framed as "first to study X in context Y" without a methodological or conceptual advance.
- Significance treated as the finding, with mechanism and external validity left thin.

## Re-routing decision

- Top-5 ambition with a discipline-wide result → `american-economic-review`, `quarterly-journal-of-economics`, or `journal-of-political-economy`.
- Strong applied micro narrower than general interest → `aej-applied-economics` or `review-of-economics-and-statistics`.
- Field-leading specialist work → the relevant field journal (`journal-of-labor-economics`, `journal-of-public-economics`, `journal-of-international-economics`, `rand-journal-of-economics`).
- A broad European applied/theory paper just below this tier → `the-economic-journal`; pure theory → `journal-of-economic-theory`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of the European Economic Association
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / theory clear JEEA's general-interest bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / anonymization / online appendix / replication>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
