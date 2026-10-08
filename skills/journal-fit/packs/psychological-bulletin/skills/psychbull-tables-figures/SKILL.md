---
name: psychbull-tables-figures
description: Use when presenting empirical-core review and synthesis Artifacts as Psychological Bulletin tables and figures. This venue overlay applies MARS/PRISMA and APA 7th formatting; it does not require a diagnostic, select an exhibit-generating model, or create estimates.
---

# Tables & Figures (psychbull-tables-figures)

Build exhibits only from the hashed outputs returned by the executed empirical-core contract. The core
`review` family owns the synthesis, dependence, diagnostic, and sensitivity procedures; this skill owns
captioning, placement, accessibility, and cross-references.

## Core boundary

- Use the frozen search/screening Artifacts for a PRISMA records-flow exhibit when that reporting
  standard applies.
- Present a study-level or synthesis exhibit only when the core contract produced the corresponding
  estimate, uncertainty, weight, grouping, or diagnostic fields.
- Present diagnostic or sensitivity plots only for procedures registered and executed under
  `CORE.INFERENCE.SENSITIVITY_BINDING`.
- Preserve the core effective-unit/dependence disposition under
  `CORE.INFERENCE.DEPENDENCE_ALIGNMENT` and the observed inference ceiling in captions or notes.
- If a requested plot needs a new estimate, diagnostic, threshold, or repair, return the request to
  empirical-research. Do not compute it in this venue skill.

No named plot or statistic is a universal venue method requirement. MARS/PRISMA determines disclosure
and placement; the core contract determines which scientific quantities exist.

## Exhibit mapping

| Core Artifact | Venue presentation |
|---|---|
| Search/screening manifest and reconciled counts | PRISMA flow with stable input/output locators |
| Study/effect manifest and registered synthesis output | self-contained study/synthesis table or plot using only returned fields |
| Moderator or diagnostic output | clearly labeled exhibit with registration status and disposition |
| Sensitivity and failure outputs | comparison exhibit that preserves failed/contradictory results and ceiling consequence |
| Reproduction manifest | caption or supplement locator for the command and hashed inputs/outputs |

## APA 7th and accessibility

- Number and title every exhibit; define abbreviations, identities, units, uncertainty, and the core
  Artifact locator in notes.
- Use colorblind-safe, grayscale-legible presentation and vector output where supported.
- Regenerate each exhibit from the deposited core driver and verify it against the result registry.
- Keep manuscript numbers, exhibit fields, and inference language synchronized with the same Artifacts.

## Anti-patterns

- Adding a statistic or diagnostic solely because a familiar plot template expects it
- Omitting a failed or contradictory core result from an otherwise favorable exhibit
- Presenting one diagnostic image as proof beyond the observed core ceiling
- Re-keying numbers by hand or using a caption that no longer matches the result registry
- Letting a reviewer-requested scientific change bypass empirical-research

## Output format

```text
【Core inputs】contract/revision + Artifact IDs
【Exhibit mapping】each table/figure → registered output fields
【Disposition】diagnostic/sensitivity failures visible? [Y/N]
【Inference ceiling】caption and prose match core ceiling? [Y/N]
【MARS/PRISMA placement】applicable items and locators
【APA/accessibility】numbered, defined, grayscale-safe, vector where supported
【Reproducible】core driver regenerates exact exhibit? [Y/N]
【Next】psychbull-writing-style
```

## Supplementary resources

- [`../../resources/external_tools.md`](../../resources/external_tools.md) — rendering catalog; the core contract selects any scientific procedure
- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — current MARS/PRISMA and APA 7th presentation requirements
