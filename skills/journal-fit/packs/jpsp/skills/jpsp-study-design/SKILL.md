---
name: jpsp-study-design
description: Use when presenting an empirical-core multi-study design in a Journal of Personality and Social Psychology manuscript. This venue overlay controls package narrative and JARS placement; it does not choose study sequence, sample size, power rule, design, diagnostics, thresholds, or repairs.
---

# Multi-study Design Reporting (jpsp-study-design)

## Authority boundary

Each study’s target, design, units, sample-size rationale, assumptions, diagnostics, deviations, and
inference ceiling belong to empirical-research. Cross-study synthesis and integration must likewise be
registered in core. JPSP may require a coherent package narrative and JARS disclosure, but it cannot
prescribe a universal study arc, power floor, effect-size threshold, or internal meta-analytic model.

## Report the registered package

- For each study, report its core contract/revision, role in the claim-evidence graph, target, units,
  `CORE.EXPERIMENT.REGISTERED_DESIGN` where applicable, diagnostics, deviations, and ceiling.
- Report sample-size rationale and decision Artifact IDs without a venue-wide numerical threshold.
- Preserve core registered/exploratory labels and report `CORE.INFERENCE.MULTIPLICITY_PLAN`.
- Report measurement-validation, dependence, sensitivity, and stochastic-identity Artifact IDs under
  their registered core requirements.
- Report the core cross-study integration/synthesis identity and disposition; a method change returns
  to empirical-research.

## JPSP presentation layer

Explain how the registered studies jointly bear on the personality/social-psychological theory, where
they converge or conflict, and which core ceiling governs the package claim. Put complete design and
diagnostic records in the supplement or repository locations required by JARS and current submission
instructions.

## Reviewer responses

| Concern | Venue-layer response |
|---|---|
| A study appears under-informative | show the core sample-size/precision rationale and ceiling |
| Studies seem redundant | show each study’s registered role in the claim-evidence graph |
| Mechanism or boundary looks post hoc | show core registration/deviation records |
| Results conflict | report the core integration/synthesis disposition and narrow the package claim if required |
| A redesign is requested | return it to empirical-research and report the new validated revision |

## Anti-patterns

- JPSP-local sample-size, power, effect-size, synthesis-model, or diagnostic rules
- Treating “multi-study” as automatic validation
- Hiding a failed study or changing its role after outcome access without a core deviation record

## Output format

```text
【Package claim】core claim ID + observed ceiling
【Study records】study → contract/revision → target → Artifact IDs → disposition
【Sample-size rationales】core decision artifacts (no venue threshold)
【Registered/exploratory】core labels and deviations
【Cross-study synthesis】core identity + output artifact + disposition
【JARS placement】main text / supplement / repository
【Next】jpsp-data-analysis
```

## Supplementary resources

- [`../../resources/official-source-map.md`](../../resources/official-source-map.md) — verify current JARS and submission requirements
