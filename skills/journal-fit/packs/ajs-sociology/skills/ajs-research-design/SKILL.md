---
name: ajs-research-design
description: Use when presenting an empirical-core research design in an American Journal of Sociology manuscript. This venue overlay controls cross-method explanation and placement; it does not choose method logic, diagnostics, thresholds, or repairs.
---

# Research Design (ajs-research-design)

AJS is method-pluralist: it publishes leading quantitative, **comparative-historical**, ethnographic,
network, and formal work, and it judges each by the standards of *its own tradition*. The job here is
to make the design defensible to a generalist, possibly cross-method, double-blind reviewer — and to
show the design actually supports the theoretical claim from `ajs-theory-building`.

## When to trigger

- Choosing or justifying the design before data collection or analysis
- A reader questioned identification, case selection, sampling, or evidentiary warrant
- Aligning the design with the mechanism and observable implications
- Mixed-methods work that must defend each component on its own terms

## Report the registered design (by tradition)

### Quantitative / observational
- Report the core target/estimand, assumptions, sampling, measurement, diagnostic Artifact IDs,
  dispositions, and observed ceiling. AJS does not select a model or diagnostic.

### Comparative-historical
- Report `CORE.QUAL.REGISTERED_SELECTION_EVIDENCE`, comparison/scope records, source-to-claim Artifact
  IDs, rival-adjudication disposition, and observed ceiling.

### Ethnographic / interview
- Report the core access/selection/scope/positionality metadata and claim-evidence Artifact IDs without
  exposing informants; return an absent record to empirical-research.

### Network / computational
- Report `CORE.NETWORK.REGISTERED_BOUNDARY`, core model/measurement identity, missingness and validation
  artifacts, dispositions, and observed ceiling.

### Formal
- Report the core model-to-evidence mapping, assumptions, proof/diagnostic artifacts, rival record, and ceiling.

## Match design to claim

The single most common AJS reviewer objection is that the design cannot bear the theoretical claim.
Walk the core claim–mechanism–evidence graph and report its observed ceiling. If a record is absent or
fails, return it to empirical-research; the venue layer does not strengthen the design itself.

## Referee-pushback patterns by tradition (the modal AJS objection)

The most common AJS design rejection is "the design cannot bear the theoretical claim." Recurring objections by tradition; confirm method expectations against the journal's current submission guidelines.

| Referee writes… | Tradition | The AJS-appropriate fix |
|-----------------|-----------|------------------------|
| "Selecting on the outcome." | comparative-historical | show the core selection diagnostic and disposition |
| "Representativeness asserted." | ethnographic | show the core scope/selection record and ceiling |
| "Identification overclaimed." | quantitative | report the observed core ceiling and use matching prose |

## Calibration with a quick example (hedged)

AJS judges each tradition by its own standard, not a single template; unlike a parsimony-first sibling that privileges a clean causal estimate, it accepts a richly defended interpretive or comparative design when it bears the claim. Illustrative: an author selecting four states that all underwent revolution, then theorizing "state breakdown causes revolution," is flagged for selecting on the outcome; the fix adds two negative cases (comparable fiscal crises that did *not* break down) so the comparison can see the mechanism fail as well as fire. Confirm method guidance against the journal's current submission guidelines.

## Anti-patterns

- Borrowing a quantitative identification template for work that is interpretive or comparative
- Case selection that quietly guarantees the result (selecting on the outcome without acknowledging it)
- Ethnography that asserts representativeness it cannot support
- Overclaiming causality from an associational design
- A design that tests something adjacent to, but not, the stated theoretical claim
- Designing only to confirm the mechanism, with no case where it could be seen to fail


## Design pass for American Journal of Sociology

Treat this skill as an executable review pass, not a prose hint. First lock the social process, data leverage, causal or interpretive warrant, and theoretical payoff; then judge whether the current manuscript answers the venue's real reader: sociology reviewers who value deep theory, durable empirical leverage, and careful social-mechanism claims.

- **Do the pass:** Lock the unit, scope, comparison, validity threat, and minimum decisive evidence before recommending collection, analysis, or submission.
- **Return a ledger:** give `claim / evidence / risk / manuscript location` rows, so the next agent can edit rather than rediscover the issue.
- **Sibling guard:** compare against ASR for broader empirical sociology, Social Forces for wider substantive range, Demography for population mechanisms; if a sibling owns the contribution, recommend re-routing before polishing format.
- **Stop condition:** do not give submission-ready advice until the pack's `resources/official-source-map.md` has been checked for volatile rules and the manuscript has one concrete fix for the largest venue-specific risk.

## Output format

```
【Tradition】quantitative / comparative-historical / ethnographic / network / formal / mixed
【Claim it must support】from theory-building
【Design leverage】how this design bears on the claim
【Key assumptions / threats】identification, selection, access, boundary, etc.
【Evidentiary trail】sources → claims is legible? [Y/N]
【Verdict】supports the claim / needs tightening / overclaims (fix)
【Next】ajs-data-analysis
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — design and method tooling by tradition
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — AJS method-pluralism and reviewer-matching policy
