---
name: review-of-economic-studies
description: Use when targeting Review of Economic Studies (REStud) or deciding whether an economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Review of Economic Studies (review-of-economic-studies)

## Journal positioning

REStud is one of the economics "top-5" (with AER, QJE, JPE, Econometrica), European-leaning and run by an active scholarly board. It is strong in theory and frontier methods and is known for publishing ambitious, technically serious work — historically a natural home for outstanding junior-scholar papers. The editorial culture prizes novelty and rigor across fields: a paper that does something genuinely new, whether a new model, a new method, or a striking new result, for a discipline-wide readership.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the REStud / Oxford University Press site and the editorial submission system.

## When to trigger

- The author names REStud (or the top-5 with a novel theoretical/methodological angle) as the target venue.
- An ambitious paper — often by a junior scholar — pushes a frontier in theory, methods, or design and the author is choosing among the top-5.
- A technically serious paper needs re-framing so its novelty and rigor, not just its topic, lead the contribution.
- The author needs REStud's desk-reject risks and a credible top-5 / top-field alternative list.

## Scope & topic fit

- Frontier economic theory — micro theory, macro theory, dynamic models, mechanism and information economics — with general, novel results.
- Frontier empirical and structural work that introduces or pushes new methods or identification.
- Macro, labor, public, development, and IO papers when the contribution is methodologically or conceptually ambitious.
- Cross-field work that combines theory and evidence in a novel way and reads as broadly important.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the question, the novel contribution, the approach, and the result, and makes the case that the advance is new relative to the frontier.
- Lead with what is new — model, method, or result — and let the rest of the paper establish it rigorously.
- REStud uses an unstructured abstract and JEL codes; proofs, derivations, robustness, and secondary analyses move to appendices and online supplements.
- Exhibits and propositions should be self-contained; the central new result should be legible on its own.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Review of Economic Studies submission guidelines" / "information for authors" and the data and code availability policy, and follow the current OUP / editorial versions.
- Re-check the submission fee, formatting, abstract/JEL, anonymization, and figure/table standards on the submission system.
- Re-check the current data/code deposit and replication-verification workflow — confirm it is enforced before acceptance.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating what is genuinely new — the model, method, or result — relative to the frontier.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current top-5 / frontier work it advances.
- [ ] Data and code are ready for the availability + verification workflow.

## Common desk-reject triggers

- A competent paper with no genuine novelty — a standard application or incremental extension.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- "First to study X in context Y" framing without a new method, model, or conceptual advance.

## Re-routing decision

- More technical / formal than topical → `econometrica` (theorem or new estimator with full proofs); general theory → `journal-of-economic-theory`.
- General-interest empirical importance → `american-economic-review`, `quarterly-journal-of-economics`, or `journal-of-political-economy`.
- Excellent but narrower applied micro → `aej-applied-economics` or `review-of-economics-and-statistics`; micro theory → `aej-microeconomics`.
- Macro/growth/dynamics → `aej-macroeconomics`; one crisp single-result idea → `aer-insights`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Review of Economic Studies
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the novelty + rigor clear REStud's frontier bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / JEL / data-code policy / exhibits>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
