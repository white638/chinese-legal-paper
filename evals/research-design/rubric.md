# Research Design v3 Blind A/B Rubric

## Purpose

This rubric compares whether v3 produces a more defensible research answer than the frozen `556b1ec` baseline. It does not reward the presence of method keywords, longer templates, quantitative labels, hypotheses, or stricter-looking thresholds.

## Reviewer isolation

For each of 12 hidden tasks, generate two independent repetitions, producing 24 anonymous A/B pairs. Randomize labels per pair and reviewer. Three reviewers work independently and may see only the task materials and the two anonymous outputs. They must not see checker reports, golden answers, version labels, generation logs, or another review.

Every review must include:

- a 0–2 score for every dimension;
- one pair preference: `A`, `B`, or `TIE`;
- at least three substantive findings, each with a manuscript or design-artifact location;
- the strongest reason against the preferred output;
- any hard-failure observation, stated independently rather than copied from a checker.

Unicode-aware comparison is used after collection to detect renamed or lightly edited duplicate Chinese reviews.

## Scored dimensions

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| `design_answer_match` | Design cannot answer the confirmed question, or answers a different one | Main route is plausible but one essential link is weak or implicit | Question, concepts, materials, design, evidence, and answer form one explicit chain |
| `concept_measurement_link` | Core concept is undefined, circular, or unrelated to observation | Definition and indicators exist but boundaries or comparability remain weak | Boundaries, near-neighbor distinctions, indicators, errors, and comparison meaning are coherent |
| `evidence_traceability` | Sources, numbers, or evidence units are fabricated or untraceable | Main evidence is traceable but some load-bearing use is underspecified | Every load-bearing claim maps to registered Source IDs, evidence units, transformations, and limits |
| `inference_calibration` | Causal, predictive, mechanism, descriptive, or normative conclusion exceeds the design | Mostly calibrated with one material overstatement or hidden limitation | Claim type and wording consistently match identification strength, evidence quality, and uncertainty |
| `alternative_and_falsification` | No possible contrary observation or competing account is acknowledged | Alternatives are listed but not discriminated, or negative evidence is weakly handled | Relevant alternatives yield distinct expectations and falsification or revision conditions are explicit |
| `scope_and_transfer` | Population, case, corpus, period, or normative audience is missing or universalized | Scope is stated but transfer logic remains generic | Inclusion, exclusion, missingness, range conditions, and transfer target are explicit and defensible |
| `ethics_permission_reproduction` | Applicable ethics or permission is absent, or reproduction is falsely claimed | Status is present but a lawful review path or route artifact is incomplete | Ethics, lawful use, privacy, versions, codebooks/code, and restricted review paths match the materials |
| `research_value_and_contribution` | Output is mechanically complete but provides no identifiable research gain | Contribution is relevant but broad, derivative, or insufficiently tested | The design isolates a consequential unknown and supports a bounded, defensible contribution |

`design_answer_match` and `inference_calibration` may never score 0 in a passing output.

## Pair decision

Prefer the output with the higher median total across three reviewers, subject to:

1. Any confirmed hard error makes that output ineligible to win.
2. A score of 0 on `design_answer_match` or `inference_calibration` makes that output ineligible to pass.
3. More fields or longer prose do not break a tie.
4. If totals tie, prefer the output with the higher `design_answer_match`, then `inference_calibration`.
5. If still tied, record `TIE`; do not force a winner.

## Hard failures versus scholarly judgment

Hard failures are limited to objectively reproducible defects: fabricated or promoted sources, identity drift, absent material boundaries, undeclared causal route, undisclosed construction-validation leakage, cross-artifact contradiction, applicable ethics or permission omission, unregistered load-bearing numbers, selective reporting, future-schema unsafe acceptance, and non-independent reviews.

The following remain scholarly judgments and must be discussed rather than converted into keyword PASS/FAIL: problem value, concept quality, method fit, representativeness, plausibility of alternatives, mechanism credibility, transfer boundaries, and strength of normative reasoning.

No universal failure may be based on fixed sample size, a single significance/reliability/validity/QCA threshold, absence of hypotheses, use of a non-RCT design, or method-family labels.

## Release decision

Release requires all thresholds in `manifest.json`, including:

- 100% detection of designated hard-failure cases;
- at least 90% overall and 80% per-family automatic end-to-end pass rate, with zero hard errors;
- at least 16 v3 wins and no more than 3 v3 losses across 24 blind pairs;
- no method family with net regression;
- no 0 in design-answer match or inference calibration;
- the frozen-material workflow, lawful CNKI flash canary, and rendered Word acceptance.

Qualitative findings remain part of the release record even when numeric thresholds pass.
