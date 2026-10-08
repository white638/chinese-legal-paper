---
name: journal-of-public-administration-research-and-theory
description: Use when targeting Journal of Public Administration Research and Theory (JPART) or deciding whether a public-management manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, verified submission facts, official-submission re-check, and desk-reject heuristics.
---

# Journal of Public Administration Research and Theory (journal-of-public-administration-research-and-theory)

## Journal positioning

JPART is the official journal of the Public Management Research Association (PMRA), published by Oxford University Press, and the field's most theory-driven, research-first outlet. The journal states that it publishes "the highest quality theoretical and empirical work" and is "committed to developing diverse and rigorous research that extends and builds public administration theory"; its scope is multidisciplinary and includes organizational, administrative, managerial, and policy-based research on the public sector. What wins here is a paper whose contribution is an advance in public-management theory, demonstrated with a design that credibly supports the claim, whether that is an experiment, a well-identified observational study, or rigorous qualitative work. The readership is academic public-management scholars; practitioner relevance is welcome but is not the entry ticket it is at PAR.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the OUP site and the Editorial Express submission system.

## When to trigger

- The author names JPART as the target venue, or wants the PMRA research flagship.
- A public-management paper has a strong design but the theoretical contribution is implicit; it needs re-framing so the abstract's "implications for theory" slot is not empty.
- A PAR-style practice-facing paper is being reconsidered for a theory-first venue.
- The author needs JPART's desk-reject risks and a credible alternative list (PAR, Public Administration, PMR, IPMJ, Governance).

## Scope & topic fit

- Public-management theory: bureaucratic behavior, discretion, red tape and administrative burden, representative bureaucracy, accountability, and organizational performance.
- Behavioral public administration: citizen and public-employee decision-making studied with survey, lab, and field experiments, and the theory they are meant to refine.
- Public personnel and motivation (public service motivation, leadership, turnover), collaboration and networks, contracting and hybrid delivery, nonprofit and cross-sector management.
- Policy-based research when the mechanism is administrative or organizational rather than political-institutional.
- Rigorous qualitative and comparative work that builds theory, and replications or re-examinations of influential findings.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The abstract follows the journal's own template: theoretical approach, method and data, results, and findings and implications for theory. Reviewers read an empty theory slot as a red flag.
- The introduction states the theoretical puzzle, the design, and the contribution to public-management theory in the first pages; positioning is against the public-management literature, not only against a policy domain.
- Length is generous but inclusive: the cap counts abstract, tables, and references, so put robustness and measurement detail in an online appendix.
- Author–date OUP style with DOIs in the reference list; 3–5 keywords chosen to signal theory, research theme, and method.
- Data and code release is a condition of publication where ethically possible; a Data Availability Statement is required, and the manuscript should be written so the deposited package reproduces every reported figure.
- Prepare the manuscript for anonymous review: the Editorial Express portal strips PDF metadata and instructs authors to purge identifying information from the file, including the cover page.

## Verified submission facts (live-checked 2026-09-02; re-check before submitting)

- Publisher & submission system: Oxford University Press for the Public Management Research Association; submissions via Editorial Express (http://editorialexpress.com/jpart) (sources: https://academic.oup.com/jpart/pages/Instructions_To_Authors; https://academic.oup.com/jpart/pages/About).
- Review model: the OUP instructions page does not label the model as single- or double-anonymous; the Editorial Express submission page states that anonymity is maintained when the submission is transmitted to referees and that author names and identifying information must be purged from the file (source: https://editorialexpress.com/cgi-bin/e-editor/e-submit.cgi?dbase=jpart). Treat as author-anonymous review and confirm live.
- Word limit: "no longer than 12,000 words, including abstract, tables, and references, in 12-point font and with double spacing" (source: https://academic.oup.com/jpart/pages/Instructions_To_Authors).
- Fees / APC policy for standard submissions: no submission or publication fee is stated for standard submissions; an open access charge applies only if publishing under an open access licence (source: https://academic.oup.com/jpart/pages/Instructions_To_Authors).
- Data / replication policy: JPART "requires all authors, where ethically possible, to publicly release all data and software code underlying any published paper as a condition of publication"; exemptions need editor approval; a Data Availability Statement is required (source: https://academic.oup.com/jpart/pages/Instructions_To_Authors).

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Public Administration Research and Theory instructions to authors" and follow the current OUP/PMRA version.
- Re-check the inclusive word cap, abstract template, keyword count, OUP reference style with DOIs, anonymisation, and the alt-text requirement for figures.
- Re-check the current data-and-code release policy, the Data Availability Statement wording, and any AI-use disclosure required at submission.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating which public-management theory this paper extends, refines, or overturns.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the current JPART-tier conversation on this mechanism.
- [ ] The abstract fills all four template slots, including implications for theory.
- [ ] Data, code, and the Data Availability Statement are ready for public release or a documented ethical exemption.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A finding with no theoretical mechanism: "we document that X correlates with Y in agency Z" without saying what it changes in public-management theory.
- A practice-oriented or policy-evaluation paper whose contribution is advice rather than theory (a PAR or JPAM paper in JPART clothing).
- Comparative-institutional or executive-politics work better suited to Governance, or a manuscript that exceeds the inclusive word cap.
- No credible plan to release data and code, or an under-anonymised submission.

## Re-routing decision

- Rigorous but practice-facing public administration → `public-administration-review`; European, interpretive, or critical administrative scholarship → `public-administration-journal`.
- Public-service reform, co-production, and management practice → `public-management-review`; cross-national management comparisons → `international-public-management-journal`.
- Institutions, executive politics, and the state → `governance-journal`; policy analysis proper → Journal of Policy Analysis and Management or Policy Studies Journal.
- Theory pieces without data → Perspectives on Public Management and Governance (PMRA's companion journal).

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Public Administration Research and Theory
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the design and its registered reporting clear JPART's theory-plus-rigor bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <Editorial Express / anonymisation / inclusive word cap / abstract template / data-code release / DOIs>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
