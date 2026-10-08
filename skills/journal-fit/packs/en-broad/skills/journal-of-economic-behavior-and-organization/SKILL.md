---
name: journal-of-economic-behavior-and-organization
description: Use when targeting Journal of Economic Behavior and Organization (JEBO) or deciding whether a behavioral / institutional economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Economic Behavior and Organization (journal-of-economic-behavior-and-organization)

## Journal positioning

The Journal of Economic Behavior and Organization is a broad, pluralistic journal at the intersection of behavioral and institutional economics. It publishes work on bounded rationality, experiments, evolutionary and organizational economics, and the behavioral and institutional foundations of economic activity. Its hallmark is methodological breadth: theory, experiments, field and lab evidence, and computational and evolutionary modeling all appear, united by an interest in how real agents, institutions, and organizations behave. The readership is behavioral, experimental, and institutional economists, plus those in adjacent organizational and evolutionary traditions.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Elsevier / journal site and the submission system.

## When to trigger

- The author names JEBO as the target venue.
- A behavioral, experimental, or institutional paper needs a broad, pluralistic home and the author is choosing among behavioral venues.
- An economics paper foregrounds bounded rationality, organizations, or evolutionary dynamics and needs re-framing toward JEBO's interests.
- The author needs JEBO's desk-reject risks and a credible behavioral / institutional alternative list.

## Scope & topic fit

- Bounded rationality, heuristics, and behavioral foundations of economic decision-making.
- Lab and field experiments on individual and strategic behavior, cooperation, social preferences, and markets.
- Evolutionary economics, learning, agent-based and computational modeling of economic dynamics.
- Organizational economics: incentives, firms, institutions, and the behavioral side of organizations.
- Pluralistic in method, but every paper needs a clear economic contribution.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction should state the behavioral / institutional question, the approach, and what the result teaches about how agents or organizations behave.
- Frame the contribution in behavioral / institutional terms and connect to the relevant model or theory; situate among the standard behavioral and institutional literatures.
- Use an abstract and JEL codes; relegate instructions, robustness, and additional treatments to an online appendix.
- Exhibits should make treatment effects, mechanisms, or model dynamics legible.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Economic Behavior and Organization guide for authors" and follow the current Elsevier version.
- Re-check word/figure limits, abstract and JEL/keyword requirements, reference style, declaration of interests, and anonymization expectations.
- Re-check the current research-data and code availability policy, experimental-materials / pre-registration expectations, and ethics approval for human-subjects experiments.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating what this teaches about behavior, institutions, or organizations.
- [ ] The contribution is stated as a behavioral / institutional mechanism or advance, not as a significant effect.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The finding connects to a model or theory; ethics and data/materials policy are satisfied.
- [ ] The economic contribution is clear despite the pluralistic method.

## Common desk-reject triggers

- An isolated behavioral anomaly with no model, mechanism, or economic interpretation.
- An underpowered or weakly incentivized experiment.
- A paper with no behavioral, institutional, or organizational angle (pure applied micro with no behavioral content).
- Computational / agent-based work with opaque assumptions and no testable implications.

## Re-routing decision

- Core decision-under-risk / risk-preference theory and valuation → `journal-of-risk-and-uncertainty`.
- Decision theory / game theory for general-theory audiences → `journal-of-economic-theory` or `games-and-economic-behavior`.
- Top-5 general-interest behavioral results → `american-economic-review`; narrower applied micro → `aej-applied-economics`.
- Behavioral work centered on organizations / management theory → `organization-science` or `academy-of-management-journal`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Economic Behavior and Organization
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the behavioral / institutional contribution clear this venue's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / JEL-keywords / data-code / pre-registration / ethics>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
