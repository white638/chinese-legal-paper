---
name: journal-of-management-en
description: Use when targeting Journal of Management (JOM, SAGE) or deciding whether a broad management / organizational behavior manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Management (journal-of-management-en)

## Journal positioning

Journal of Management (JOM), published by SAGE, is a broad, top-tier outlet for management and organizational research and a member of the FT50. It spans the full management field — organizational behavior, human resource management, strategy, entrepreneurship, and organizational theory — and is known for publishing strong empirical studies as well as high-impact meta-analyses and reviews. JOM rewards a clear theoretical contribution backed by rigorous, well-identified empirics; it is broad in topic but demanding in execution. The audience is management scholars across subfields, so the contribution should travel beyond a single specialty.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the SAGE / JOM site and the submission system.

## When to trigger

- The author names Journal of Management / JOM (the SAGE FT50 management outlet) as the venue.
- A broad management or OB empirical paper, or a meta-analysis/review, needs a high-impact generalist home.
- A paper near AMJ's bar but slightly less theory-forward, or a rigorous meta-analysis, needs the right outlet.
- The author needs JOM's desk-reject risks and a credible `academy-of-management-journal` / `journal-of-management-studies` / `human-resource-management` alternative list.

## Scope & topic fit

- Broad management and organizational behavior: leadership, motivation, teams, HRM, careers, organizational behavior, and micro-OB phenomena.
- Strategy, entrepreneurship, and organizational theory when framed for a general management audience.
- Meta-analyses and quantitative or systematic reviews — a recognized JOM strength.
- Empirical work (survey/SEM, field, multi-source, archival) with a clear theoretical contribution.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The front end frames a theoretical gap and develops hypotheses with explicit logic.
- A strong JOM paper states a theoretical contribution that generalizes across management, plus bounded practical implications.
- Reviews/meta-analyses lead with a synthesizing framework and a research agenda, not just pooled effects.
- Expect theory-method-results-discussion flow; APA-style writing and clear exhibits.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Management submission guidelines / SAGE author guidelines" and follow the current version.
- Re-check word/length limits, abstract format, anonymization for double-blind review, reference style (APA), and any structured-abstract or article-type rules (e.g., review vs. empirical).
- Re-check current open-science, data-availability, transparency, and AI-use disclosure policies.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the theoretical contribution and why it travels across management subfields.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] For meta-analyses: comprehensive, transparent coding and current bias diagnostics.
- [ ] The discussion states contributions to theory first, practice second.
- [ ] Article type, framing, references, and anonymization match the current JOM guide.

## Common desk-reject triggers

- A descriptive or atheoretical empirical study ("a study of X in sample Y").
- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A meta-analysis that pools effects without a theoretical framework or bias diagnostics.
- A niche specialty paper that does not travel beyond one subfield.

## Re-routing decision

- A more theory-forward, top-bar empirical paper → `academy-of-management-journal`; pure theory, no data → `academy-of-management-review`; integrative agenda-setting review → `academy-of-management-annals`.
- HRM-specialist work → `human-resource-management`; strategy/firm performance → `strategic-management-journal`; organization theory → `organization-science` or `administrative-science-quarterly`.
- European theory-method tradition → `journal-of-management-studies` or `organization-studies`; interdisciplinary work-and-organization → `human-relations`.
- Entrepreneurship → `journal-of-business-venturing` / `entrepreneurship-theory-and-practice`; international → `journal-of-international-business-studies`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Management
[Topic tags] <2–3 closest topics>
[Method/evidence] <is the theoretical contribution + method/meta-analytic rigor at JOM's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / length / APA / article type / open-science>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
