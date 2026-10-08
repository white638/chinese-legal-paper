---
name: journal-of-consumer-research
description: Use when targeting Journal of Consumer Research (JCR) or deciding whether a consumer-behavior manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Consumer Research (journal-of-consumer-research)

## Journal positioning

JCR is the premier interdisciplinary outlet for consumer-behavior research and an FT50 venue. It publishes work that builds a theory of consumption, drawing on psychology, sociology, economics, anthropology, and other lenses, judged on the depth and generality of the theoretical contribution. The signature JCR paper offers multi-study process evidence for a consumer-behavior theory — establishing an effect, demonstrating the underlying process (mediation), and bounding it (moderation). Readership is the interdisciplinary consumer-research community across business schools and the social sciences.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the JCR / Oxford University Press site and the submission system.

## When to trigger

- The author names JCR (or the interdisciplinary consumer-behavior elite) as the venue.
- A consumer-behavior paper with a theoretical advance and a multi-study process design needs positioning.
- A qualitative/CCT (consumer culture theory) or economics/sociology-of-consumption paper needs framing for JCR's interdisciplinary taste.
- The author needs JCR's desk-reject risks and a credible JCP / JMR / JM alternative list.

## Scope & topic fit

- Substantive consumer phenomena explained by a portable theory: judgment, choice, affect, identity, social influence, well-being, consumption meaning.
- Multiple lenses welcome: cognitive/social psychology, behavioral decision research, sociology and anthropology of consumption (CCT), and economic approaches.
- Method-pluralistic: lab/field experiments, surveys, qualitative/ethnographic, and secondary-data designs — unified by theoretical contribution.
- Questions about why and how consumers think, feel, and behave, framed as theory, not as a single applied finding.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The front end develops a theoretical tension or puzzle and the conceptual contribution before any study is reported.
- A strong JCR paper integrates a study sequence into a coherent theoretical narrative and closes with a general-discussion that states the contribution to consumer theory and (briefly) practice.
- JCR expects a web/online appendix for additional studies, stimuli, and robustness, and takes openness/transparency seriously.
- Writing is conceptual and accessible across disciplines; the theory, not the method, leads.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Consumer Research submission guidelines / author instructions" and follow the current JCR/OUP version.
- Re-check abstract format, length, anonymization for masked review, reference style, and the web-appendix / supplementary-materials requirement.
- Re-check current open-science, pre-registration, data/materials transparency, ethics/IRB, and AI-use disclosure policies.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the novel, portable theoretical contribution to consumer behavior.
- [ ] The empirical chain establishes effect, process, and boundary conditions (or, for qualitative work, builds theory rigorously).
- [ ] Alternative explanations are ruled out and the mechanism is evidenced, not assumed.
- [ ] The introduction positions the paper against recent JCR / consumer-behavior theory.
- [ ] Web appendix, stimuli, pre-registration, and transparency disclosures match the current JCR guide.

## Common desk-reject triggers

- A single-study effect with no process evidence and no theoretical contribution.
- A robust but atheoretical applied finding ("does X increase purchase of Y").
- Mediation claimed without adequate evidence, or alternative explanations left open.
- A modeling or substantive-strategy paper with no consumer-theory contribution.

## Re-routing decision

- Psychological-theory and process-mechanism focus, consumer-psychology audience → `journal-of-consumer-psychology`.
- Behavioral or modeling rigor as the headline → `journal-of-marketing-research`; analytical/structural modeling → `marketing-science`.
- Broad substantive/managerial marketing reach → `journal-of-marketing`; marketing-strategy / relationship work → `journal-of-the-academy-of-marketing-science`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Consumer Research
[Topic tags] <2–3 closest topics>
[Method/evidence] <is the theory + multi-study process at JCR's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / abstract / web appendix / pre-registration / transparency>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
