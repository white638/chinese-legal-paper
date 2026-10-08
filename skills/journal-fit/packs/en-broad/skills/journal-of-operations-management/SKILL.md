---
name: journal-of-operations-management
description: Use when targeting Journal of Operations Management (JOM) or deciding whether an empirical / survey-based / behavioral operations-and-supply-chain manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Operations Management (journal-of-operations-management)

## Journal positioning

The Journal of Operations Management (JOM) is a leading empirical home for operations and supply-chain management research, with a long tradition of survey-based, behavioral, and theory-driven empirical work. It is OM's empirical flagship in the way M&SOM anchors analytical OM: JOM rewards papers that test or build operations theory with strong primary or secondary data, and it takes construct measurement and research design seriously. This is the OM "JOM" — distinct from the management *Journal of Management*. The readership is the empirical OM and SCM community.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the publisher's JOM site and the editorial submission system.

## When to trigger

- The author names JOM (the operations-management journal, not the management *Journal of Management*) as the venue.
- An empirical, survey-based, behavioral, or theory-testing OM/SCM paper needs an empirical OM flagship.
- A modeling-heavy or descriptive operations paper needs re-framing around an empirical theoretical contribution.
- The author needs JOM's desk-reject risks and a credible OM / MS alternative list before submitting.

## Scope & topic fit

- Empirical operations and supply-chain management: sourcing, supplier relationships, operations strategy, quality, and process management.
- Survey-based research with rigorous construct development and measurement.
- Behavioral operations: experiments and field studies on operational decision-making.
- Theory-driven empirical work using secondary/archival data, with identification appropriate to the operations question.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The front end frames an operations theoretical gap and develops hypotheses or a grounded model with explicit logic.
- Methods sections are transparent about constructs, measurement, sampling, and identification; appendices carry scales and robustness.
- Results report operational magnitudes and effect sizes, not only significance; the discussion cashes in the theoretical and managerial contribution.
- Writing emphasizes the contribution to OM theory and practice.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Operations Management author guidelines / information for authors" and follow the current publisher version.
- Re-check word/length limits, abstract format, anonymization for double-blind review, reference style, and structured-abstract requirements if any.
- Re-check the current open-science, data/code availability, and AI-use disclosure policies.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the contribution to operations-management theory.
- [ ] Hypotheses (or the inductive model) follow from explicit theoretical logic.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] Results report operational magnitudes; the discussion states theory and practice contributions.
- [ ] Length, abstract, anonymization, references, and open-science policy match the current JOM guide.

## Common desk-reject triggers

- An atheoretical empirical study ("a survey of practice X in industry Y") with no OM theoretical contribution.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A purely analytical / optimization paper with no empirical OM contribution.
- Confusing JOM (operations) with the management *Journal of Management* in scope and framing.

## Re-routing decision

- Analytical OM theory and models (supply chain, inventory, service, revenue management) → `manufacturing-and-service-operations-management`.
- Broad OM with society audience, sustainability/healthcare operations, analytical or empirical → `production-and-operations-management`.
- Broad management insight or empirics across subfields → `management-science` (choose the right department).
- OR methodology / optimization for its own sake → `operations-research`; computational → `informs-journal-on-computing`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Operations Management
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the theory-driven empirical design clear JOM's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / length / blinding / open-science / data-code>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
