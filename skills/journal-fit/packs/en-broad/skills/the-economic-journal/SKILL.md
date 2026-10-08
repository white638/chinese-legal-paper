---
name: the-economic-journal
description: Use when targeting The Economic Journal (EJ) or deciding whether a general-interest economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# The Economic Journal (the-economic-journal)

## Journal positioning

The Economic Journal (EJ) is the long-established general-interest journal of the Royal Economic Society, publishing broad applied and theoretical economics just below the top-5 tier. The paper that wins here has a clear question, a sound method, and a result of general interest — accessible and consequential to a wide economics readership rather than only to one subfield. The audience is the broad profession, so the contribution should read as something an economist outside your field would want to know.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's own site or submission system.

## When to trigger

- The author names EJ (or a strong general-interest journal just below the top-5) as the target venue.
- A paper has a sound design and broad interest, and the author is choosing between EJ and a top field or general-interest venue.
- A solid field paper needs re-framing so the contribution reads as broadly interesting rather than niche.
- The author needs EJ's desk-reject risks and a credible general-interest / field-journal alternative list before submitting.

## Scope & topic fit

- Broad applied economics across fields — labor, public, development, macro, IO, micro — judged on general interest and sound execution.
- Theory papers whose results are interpretable and of wide interest, not narrow technical extensions.
- Policy-relevant applied work where the question matters to a general economics audience.
- Empirical regularities and well-identified effects that travel beyond a single context.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the contribution, the approach, and the headline result, and explains why a general economics reader should care.
- Make the contribution explicit against the relevant literature; "first to study X in context Y" is not enough on its own.
- The journal uses an abstract and JEL codes; an online appendix carries robustness, derivations, and secondary results.
- Exhibits are clean and self-contained; the central result should be legible from one table or figure.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "The Economic Journal submission guidelines / author instructions" and follow the current Royal Economic Society / Oxford University Press version, not a third-party broker's copy.
- Re-check formatting, abstract/JEL codes, reference style, anonymization expectations, the online-appendix policy, and the data & code availability requirements.
- Re-check the current replication/data-deposit expectation and any RES-membership or submission routes on the editorial system.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating why a general economics reader should care about this result.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the relevant literature and general-interest frontier.
- [ ] Data and code are ready for the availability and replication workflow.

## Common desk-reject triggers

- A narrow field paper with no broad-interest hook, better suited to a specialist outlet.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- Contribution framed as "first to study X in context Y" without a conceptual or methodological advance.
- Significance treated as the finding, with mechanism and generalizability left thin.

## Re-routing decision

- General-interest at near-top-5 / top-5 ambition → `journal-of-the-european-economic-association`, `american-economic-review`, or `journal-of-political-economy`.
- Strong applied micro → `aej-applied-economics` or `review-of-economics-and-statistics`.
- Field-leading specialist work → the relevant field journal (`journal-of-labor-economics`, `journal-of-public-economics`, `journal-of-development-economics`, `rand-journal-of-economics`).
- Macro mechanism → `journal-of-monetary-economics`; pure theory → `journal-of-economic-theory`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] The Economic Journal
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification / theory clear EJ's general-interest bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL / anonymization / online appendix / replication>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
