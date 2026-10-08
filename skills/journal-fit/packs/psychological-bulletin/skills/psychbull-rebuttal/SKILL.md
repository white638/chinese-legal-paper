---
name: psychbull-rebuttal
description: Use when writing the response to a Psychological Bulletin revise-and-resubmit. It maps reviewer requests to empirical-core contract amendments and reports regenerated Artifacts without choosing new methods in the venue layer. Structures the response letter; it does not fabricate results or run analyses.
---

# R&R Rebuttal (psychbull-rebuttal)

A Psychological Bulletin **R&R** on a synthesis is distinctive: reviewer requests often touch the
**search, eligibility, coding, model, or bias analyses** — any of which can ripple through every
downstream estimate, table, and figure. The response letter must convert each reviewer and keep the
editor confident **without breaking the synthesis's internal consistency** or its deposited package.

Any request that changes search, eligibility, coding, model, moderator, dependence, or diagnostics first
returns to empirical-research for a core-contract amendment and validation. This venue skill only reports
the resulting revision, hashed Artifacts, dispositions, and ceiling.

## When to trigger

- An R&R decision arrived and you are planning the revision + response letter
- A reviewer wants the search expanded, studies added, or eligibility changed
- A reviewer requests a different model, more moderators, or more bias diagnostics
- Reviewers disagree and you must reconcile their demands

## Strategy

1. **Read the editor's letter as the rubric.** The editor flags the decisive points; solve those first.
2. **One point-by-point response, every comment addressed.** Quote each comment, then respond; never
   skip one — silence reads as non-compliance.
3. **Propagate approved core changes consistently.** Return any scientific change to empirical-research;
   after validation, report the regenerated downstream Artifacts and update all affected exhibits.
4. **Concede or rebut with evidence.** Did what was asked (say where, with new numbers/exhibit numbers),
   or push back respectfully on methodological grounds (e.g., why an unplanned moderator stays
   exploratory, why a bias test is uninformative under high heterogeneity).
5. **Reconcile conflicting reviewers openly.** Record conflicting requests, the core-contract
   disposition, and its rationale; do not choose an inclusion or analysis rule in the venue layer.
6. **Protect the contribution.** Add robustness and clarification; resist changes that dilute the
   synthesis or over-claim beyond the evidence and heterogeneity.
7. **Keep it masked and update the package.** The revised manuscript stays masked; **update the
   deposited database, codebook, and scripts** so new estimates remain reproducible.

## Response-letter format

For each reviewer comment:

```
> [Quoted reviewer comment]

Response: [What we did / why we respectfully disagree].
Change: [Section/page; new k; table/figure number; updated estimate].
```

Open with a short **summary of the main changes** to the editor (especially any change in study count
or model); group by reviewer; end each entry with the location of every change for quick verification.

## Anti-patterns

- Adding studies but leaving stale estimates/figures from the old pool (inconsistent synthesis)
- Ignoring or silently merging a comment
- Capitulating to a request that breaks eligibility logic just to please a reviewer
- Reporting a new bias test without acknowledging it changes the bottom line
- Letting the revised manuscript drift out of sync with the deposited package
- Reintroducing author clues while editing (breaks masking)

## Worked vignette — propagating an R&R through the synthesis

*Illustrative routing only.* Reviewers request a broader search, a moderator-status review, and an
additional diagnostic. Each request becomes a proposed core-contract amendment. The response letter
then cites the core disposition, regenerated Artifact IDs, affected manuscript/exhibit locators, and any
lowered inference ceiling. The venue skill neither adds the diagnostic nor changes eligibility itself.

## Reviewer pushback → response move (Bulletin-specific)

| Reviewer comment | Response move |
|------------------|---------------|
| "Search not exhaustive / PRISMA gaps" | Return the proposed search change to core; report its disposition and regenerated Artifacts |
| "Moderators are post-hoc fishing" | Report the core registration/deviation identity and matching label |
| "Only one bias test" | Return the requested diagnostic to core; report the validated disposition and ceiling |
| "Reviewers disagree on inclusion" | Report the conflict and core-contract disposition; do not choose a venue-local rule |
| "No integration beyond tallying" | Strengthen the contribution per `psychbull-theory-integration` |

## Output format

```
【Editor's decisive points】addressed first? [list]
【Coverage】every reviewer comment answered? [Y/N]
【Re-run propagated】new k; all estimates/exhibits consistent? [Y/N]
【Concede vs rebut】each tagged with evidence + change location
【Reviewer conflicts】reconciled and explained? [Y/N]
【Masked + package updated】[Y/N]
【Next】resubmit via Editorial Manager
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — re-running the search/analysis; keeping the package in sync
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — masked review and transparency policy behind the response
