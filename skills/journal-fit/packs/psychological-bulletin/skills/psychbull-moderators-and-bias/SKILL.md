---
name: psychbull-moderators-and-bias
description: Use when presenting empirical-core moderator, heterogeneity, selective-reporting, and sensitivity artifacts in a Psychological Bulletin manuscript. This venue overlay applies MARS placement and reviewer-facing disclosure; it does not choose a moderator model, diagnostic battery, dependence procedure, threshold, or repair.
---

# Moderators & Bias Reporting (psychbull-moderators-and-bias)

Use this skill after empirical-research has registered and executed the synthesis contract. The core
`review` family owns moderator status, synthesis targets, model identity, dependence treatment,
selective-reporting diagnostics, sensitivity procedures, and the observed inference ceiling.
Psychological Bulletin owns only how those facts are disclosed and located in the manuscript.

## Core boundary

- Report the registered moderator family and confirmatory/exploratory labels under
  `CORE.INFERENCE.MULTIPLICITY_PLAN`.
- Report the dependence and uncertainty identity, diagnostic Artifact IDs, and disposition under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- Report the selective-reporting and robustness procedures actually selected by the core contract,
  their output Artifact IDs, failures, and inference consequences under
  `CORE.INFERENCE.SENSITIVITY_BINDING`.
- Report stochastic software, version, parameter, and seed identities under
  `CORE.REPRO.STOCHASTIC_IDENTITY`.
- If a requested procedure is absent from the registered core contract, return the change to
  empirical-research. Do not add a venue-local diagnostic or silently switch models.

No named diagnostic is mandatory merely because the target journal is Psychological Bulletin. The
core contract selects procedures in light of the research object, assumptions, and available data;
the venue overlay reports that selection transparently.

## Psychological Bulletin presentation pass

1. Give every registered moderator, including null and failed analyses, a stable manuscript or
   supplement locator.
2. Present the core target, estimate, uncertainty, diagnostic disposition, and inference ceiling in a
   reader-reconstructable order.
3. Explain disagreements among registered diagnostics without converting a sensitivity result into a
   replacement truth.
4. Cross-reference the relevant MARS items, exhibits, code, and hashed Artifacts.
5. Keep substantive interpretation inside the observed core inference ceiling.

## Reviewer-request handling

Convert each methodological request into a ledger row:

| Reviewer request | Core record to inspect | Venue response |
|---|---|---|
| Additional moderator | registered/exploratory identity and multiplicity disposition | report the existing record or return a contract amendment to empirical-research |
| Additional bias or sensitivity analysis | assumptions, selected diagnostic, Artifact IDs, failure disposition | report the core result and manuscript locator; do not select the repair here |
| Dependence concern | effective unit, dependence identity, diagnostics, ceiling | disclose the core disposition and any resulting scope reduction |

## Anti-patterns

- Choosing a synthesis model or diagnostic battery from a journal-specific checklist
- Treating an unregistered moderator as confirmatory
- Hiding a null, failed, or contradictory diagnostic
- Reporting a sensitivity estimate as the uniquely correct effect
- Widening the claim after a core diagnostic lowered the inference ceiling

## Output format

```text
【Core contract】review family identity/revision + synthesis target
【Moderators】registered/exploratory labels + Artifact IDs + multiplicity disposition
【Diagnostics】core-selected identities + output/failure Artifacts
【Dependence】effective unit + core disposition
【Sensitivity】assumption binding + what held/failed
【Inference ceiling】observed ceiling + matching manuscript language
【MARS placement】main text / table / figure / supplement locators
【Next】psychbull-theory-integration
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — tool catalog; use only the package already selected by the core contract
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — current MARS and submission-reporting requirements
