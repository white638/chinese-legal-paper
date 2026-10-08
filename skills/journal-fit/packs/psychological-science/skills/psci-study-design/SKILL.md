---
name: psci-study-design
description: Use when presenting an empirical-core study design in a Psychological Science manuscript or Registered Report. This venue overlay controls disclosure and submission placement; it does not choose sample size, power rule, design, diagnostics, thresholds, or repairs.
---

# Study Design Reporting (psci-study-design)

## Authority boundary

The empirical-research core owns the target, design, units, sample-size rationale, assignment,
exclusions, multiplicity, diagnostics, deviations, and inference ceiling. Psychological Science may
require those facts to be disclosed or placed in a Registered Report, but it cannot define a universal
power floor, smallest-effect threshold, sample size, or repair.

## What to report

- `CORE.EXPERIMENT.REGISTERED_DESIGN`: core contract/revision, target, units, treatment/comparator,
  sample-size rationale identity, assignment/implementation records, diagnostic Artifact IDs,
  deviations, and observed ceiling.
- `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` and `CORE.INFERENCE.MULTIPLICITY_PLAN`: registered units,
  uncertainty and multiplicity dispositions.
- `CORE.REPRO.STOCHASTIC_IDENTITY`: identities for any random design or analysis step.
- The core registered/exploratory labels, exclusion/condition/measure records, and any deviation made
  before or after outcome access.

## Venue-specific placement

For a Registered Report, put the registered core target, design identity, diagnostics planned by the
core contract, and decision/deviation records in the Stage 1 materials; at Stage 2, report the executed
Artifact IDs and dispositions. For a regular article, disclose the same core facts in the methods,
transparency statement, and supplement as current journal instructions require.

## Reviewer responses

| Concern | Response allowed in the venue layer |
|---|---|
| Sample-size justification | Report the core rationale, inputs, version, and decision Artifact; no venue-wide numeric floor |
| Manipulation/implementation | Report core diagnostic Artifact IDs and disposition |
| Flexible exclusions | Report core registration and deviation records with timestamps |
| Confirmatory status | Preserve the core registered/exploratory label |
| Design failure | Report the narrowed/withdrawn core ceiling; return redesign to empirical-research |

## Anti-patterns

- A venue-local power target, SESOI, sample size, estimator, or diagnostic rule
- Treating a Registered Report label as evidence that the core design passed validation
- Repairing a failed design in prose without a revised, revalidated core contract

## Output format

```text
【Core design】contract/revision + CORE.EXPERIMENT.REGISTERED_DESIGN
【Target and units】registered facts
【Sample-size rationale】core Artifact ID + inputs/version (no venue threshold)
【Diagnostics/deviations】Artifact IDs + dispositions
【Inference ceiling】retained / narrowed / withdrawn
【Submission placement】regular article / Registered Report Stage 1 or 2
【Next】psci-data-analysis
```

## Supplementary resources

- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — verify current Registered Report and disclosure rules
