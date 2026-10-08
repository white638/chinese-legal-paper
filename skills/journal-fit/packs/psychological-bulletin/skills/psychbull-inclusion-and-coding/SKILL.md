---
name: psychbull-inclusion-and-coding
description: Use when presenting empirical-core eligibility, screening, coding, and extraction artifacts in a Psychological Bulletin review or meta-analysis. This venue overlay applies MARS/PRISMA placement; it does not choose coder staffing, reliability thresholds, effect-size inputs, dependence procedures, or exclusions.
---

# Inclusion & Coding Reporting (psychbull-inclusion-and-coding)

Use this skill after empirical-research has registered the review-family design. The core contract owns
eligibility, screening, codebook and construct rules, research-run provenance, disagreement handling,
reliability applicability, extraction fields, dependence structure, deviations, and exclusions.
Psychological Bulletin owns only transparent presentation of those records.

## Core boundary

- Report the registered eligibility and screening rules, protocol identity, amendments, and execution
  Artifacts from the core `review` family.
- Report codebook/construct versions, research-run manifests, validation Artifacts, disagreements, and
  dispositions under `CORE.MEASUREMENT.REGISTERED_VALIDATION`.
- Preserve metric and provenance semantics: register run/context, model revision, prompt hashes,
  parameters, repetitions, and output Artifacts. Independent model references support
  `reference_agreement`; same-model repetitions support `stability`; only external benchmarks support
  `external_accuracy`.
- Report extracted inputs, study/effect identifiers, and the registered effective-unit/dependence
  record under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`.
- Report every eligibility or coding deviation and its downstream inference consequence. Missing core
  records return to empirical-research; this venue skill cannot invent a staffing rule or repair.

Reference-run count, duplicate-review coverage, agreement statistic, and effect-input representation are
project-specific core decisions. The journal overlay reports what was registered and executed; it does
not impose a universal number, statistic, or threshold.

## Psychological Bulletin presentation pass

1. Map the frozen search and screening Artifacts to the PRISMA flow and exclusion-reason table.
2. Give the protocol, eligibility version, codebook version, annotation/extraction manifest, and
   disagreement log stable locators.
3. Place validation results and their applicability rationale where MARS readers can reconstruct the
   coding record.
4. Link every synthesis input to a stable study/effect identity and hashed output.
5. State how deviations or unresolved coding uncertainty constrain the observed inference ceiling.

## Reviewer-request handling

| Reviewer request | Core record to inspect | Venue response |
|---|---|---|
| Eligibility appears to drift | protocol/version/deviation ledger | disclose timestamps, rationale, affected records, and ceiling consequence |
| Coding cannot be reconstructed | codebook, run manifest, validation and disagreement Artifacts | add locators; return missing execution evidence to empirical-research |
| Effects appear dependent | effective-unit and dependence disposition | report the registered handling and diagnostic result; do not select a procedure here |

## Anti-patterns

- Adding or excluding studies through a venue-local rule
- Treating run count or one agreement statistic as a universal scientific threshold
- Letting the primary run validate itself or relabelling reference agreement as external accuracy
- Hiding unresolved disagreements or incomplete extraction
- Collapsing dependent inputs without reporting the core disposition

## Output format

```text
【Core contract】review family identity/revision
【Eligibility】protocol/rule version + amendment/deviation Artifact IDs
【Screening】manifest + PRISMA/exclusion locators
【Coding provenance】run/context/model/prompt/output records + codebook version
【Validation】core-selected evidence + disagreement/failure disposition
【Extraction/dependence】input identities + effective-unit record
【Inference ceiling】uncertainty/deviation consequence + matching prose
【Next】psychbull-meta-analysis-methods
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — screening/coding tool catalog; the core contract selects any actual procedure
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — current MARS/PRISMA reporting requirements
