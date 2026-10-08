---
name: manufacturing-and-service-operations-management
description: Use when targeting Manufacturing and Service Operations Management (M&SOM) or deciding whether an operations-management theory / modeling / empirical manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Manufacturing and Service Operations Management (manufacturing-and-service-operations-management)

## Journal positioning

M&SOM is INFORMS's dedicated operations-management journal, the field's home for rigorous OM theory and models with a growing empirical wing. It publishes analytical work on supply chains, inventory, service operations, capacity, and revenue management, alongside increasingly prominent empirical and behavioral OM. Where Operations Research prizes OR methodology for its own sake and Management Science spans all of management, M&SOM is OM-first: the contribution must speak to operations management theory and practice. The readership is the OM research community, so the operational insight must be central, not incidental.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the INFORMS / M&SOM site and the editorial submission system.

## When to trigger

- The author names M&SOM (or the INFORMS / UTD24 OM elite) as the target venue.
- An analytical or empirical OM paper on supply chain, inventory, service, capacity, or revenue management needs an OM-flagship home.
- A modeling paper needs re-framing so the operational insight, not the math, is the contribution.
- The author needs M&SOM's desk-reject risks and a credible OM / OR / MS alternative list before submitting.

## Scope & topic fit

- Supply chain management: contracting, coordination, sourcing, information sharing, risk and disruption.
- Inventory and capacity management, production planning, and operations strategy.
- Service operations: queueing-based service design, healthcare operations, retail and online operations.
- Revenue management and pricing; behavioral operations and increasingly empirical OM using field data or experiments.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction frames an operations problem and states the managerial insight and method early; it situates the paper in the OM literature.
- Models lead with structure and intuition; full proofs and extensions go to an electronic companion / online appendix.
- Empirical papers report and interpret operational magnitudes (e.g., effects on lead time, fill rate, throughput, cost), not only significance.
- The discussion connects the result to OM theory and to operational decisions.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Manufacturing & Service Operations Management submission guidelines / author instructions" and follow the current INFORMS version, including area/department scope.
- Re-check formatting, abstract length, anonymization/double-blind policy, and reference style.
- Re-check the current data and code availability / reproducibility policy and electronic-companion rules.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the operations-management insight and why OM scholars should care.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] Modeling assumptions are operationally defensible; proofs are complete in the electronic companion.
- [ ] Abstract, anonymization, references, and data/code policy match the current M&SOM guide.

## Common desk-reject triggers

- A technically sound model with no operational insight or with operationally implausible assumptions.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A pure OR methodology paper with no OM payoff, or a broad-management paper not OM-centered.
- Significant coefficients without operational magnitude or mechanism.

## Re-routing decision

- Broad management insight across subfields → `management-science` (choose the right department).
- OR methodology / optimization / queueing theory for its own sake → `operations-research`; computational/algorithmic → `informs-journal-on-computing`.
- Broad OM including sustainability/healthcare operations and a society audience → `production-and-operations-management`.
- Survey-based, behavioral, or theory-testing empirical OM → `journal-of-operations-management`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Manufacturing and Service Operations Management
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the operational insight + rigor clear M&SOM's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / blinding / electronic companion / data-code>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
