---
name: journal-of-marketing-research
description: Use when targeting Journal of Marketing Research (JMR) or deciding whether a marketing manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Marketing Research (journal-of-marketing-research)

## Journal positioning

JMR is an American Marketing Association FT50 journal and the field's standard-bearer for methodological and substantive rigor. It publishes work that advances marketing knowledge through strong research design — quantitative modeling, measurement, and behavioral experiments — and is unusually demanding about the methods bar. JMR is the home for both the modeling/quantitative and the behavioral wings of marketing, judged on whether the design is sound and the substantive insight is real. Readership is the research-active marketing professoriate.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the AMA / SAGE site and the submission system.

## When to trigger

- The author names JMR (or the AMA / FT50 rigorous-methods marketing tier) as the venue.
- A quantitative-modeling, measurement, or behavioral-experiment marketing paper needs positioning for a venue that prizes design rigor.
- A substantive paper whose strength is its identification, measurement, or experimental control needs framing for the right audience.
- The author needs JMR's desk-reject risks and a credible JM / Marketing Science / JCR / JCP alternative list.

## Scope & topic fit

- Quantitative marketing: choice models, econometrics of marketing, pricing, advertising response, customer analytics, measurement and psychometrics.
- Behavioral marketing: consumer judgment and decision-making tested with rigorous lab/field experiments and process evidence.
- Methodology papers that give marketing researchers a better tool (estimation, measurement, experimental design) with a marketing payoff.
- Substantive findings that depend on, and showcase, a strong research design.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The front end states the substantive question and why the design is the right way to answer it; the contribution is design + insight, not significance.
- Behavioral papers report a study chain that builds from effect to process to boundary conditions; modeling papers foreground identification and model fit.
- JMR uses a structured/abstract format and an online/web appendix for additional studies, robustness, and technical detail.
- Writing keeps method detail rigorous but legible; the substantive takeaway is never buried under technique.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Marketing Research submission guidelines / manuscript preparation" and follow the current AMA/SAGE version.
- Re-check abstract format, word/length limits, anonymization, reference style, and the web-appendix / supplementary-materials requirement.
- Re-check current data/code/materials transparency, pre-registration, ethics/IRB, and AI-use disclosure policies.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the substantive marketing insight and why the design is the right vehicle for it.
- [ ] The contribution is stated as design + insight, not as a p-value or a single effect.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against recent JMR / JM / Marketing Science work.
- [ ] Abstract, web appendix, materials, and transparency disclosures match the current JMR guide.

## Common desk-reject triggers

- A single-study behavioral effect with no process evidence or ruled-out alternatives.
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A substantively thin paper that is "rigorous" but answers a question no one is asking.
- A method demonstration with no marketing payoff.

## Re-routing decision

- Broad substantive/strategic contribution with managerial reach → `journal-of-marketing`.
- Heavy analytical/structural IO modeling → `marketing-science`.
- Consumer-behavior theory for an interdisciplinary audience → `journal-of-consumer-research`; psychological-process consumer work → `journal-of-consumer-psychology`.
- Strong but narrower marketing-strategy / B2B work → `journal-of-the-academy-of-marketing-science`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Marketing Research
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the design rigor clear JMR's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / abstract / length / web appendix / pre-registration / transparency>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
