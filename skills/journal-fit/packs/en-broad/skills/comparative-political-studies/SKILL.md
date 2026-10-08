---
name: comparative-political-studies
description: Use when targeting Comparative Political Studies (CPS) or deciding whether a comparative-politics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, verified submission facts, official-submission re-check, and desk-reject heuristics.
---

# Comparative Political Studies (comparative-political-studies)

## Journal positioning

CPS is the leading specialist journal of comparative politics, published by SAGE at high volume (ten issues a year). It "publishes scholarly work on comparative politics at both the cross-national and intra-national levels" and states that it is "particularly interested in articles which have an innovative theoretical argument and are based on sound and original empirical research", while also encouraging comparative-methodology papers "when methodological arguments are closely linked with substantive issues in the field". Editorially it is even-handed between large-N cross-national work and case-based or subnational designs: what it tests is comparative leverage — whether the design isolates the mechanism, whether the argument travels across cases, and whether the paper engages comparativists beyond one region. Its readership is the comparative-politics profession worldwide, from democratisation and party politics to political economy and civil conflict.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the SAGE site and the ScholarOne submission system.

## When to trigger

- The author names Comparative Political Studies / CPS as the target venue, or wants the comparative-politics field flagship.
- A single-country or regional study needs re-framing so the comparative claim and the case's theoretical role are unmissable on page one.
- A cross-national quantitative paper is being weighed against a general journal (BJPS, APSR, AJPS) or a policy/institutions journal (Governance).
- The author needs CPS's desk-reject risks and a credible comparative-politics alternative list.

## Scope & topic fit

- Democracy and its reversals: democratisation, consolidation, backsliding, authoritarian institutions and resilience, competitive authoritarianism.
- Parties, elections, and representation across systems: electoral systems, party strategies and organisation, populism, clientelism, accountability.
- Comparative political economy: welfare states, labour markets and bargaining institutions, varieties of capitalism, development and redistribution, European integration and monetary politics.
- Identity, ethnicity, nationalism, migration, and contentious politics; civil–military relations; subnational and intra-national comparison of states, regions, or cities.
- Civil conflict and violence studied comparatively, and comparative methodology tied to a substantive comparative question.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the theoretical argument, the comparative design (which cases or which sample, and why), and the finding; it names what the case or sample is a case *of* and how the mechanism would show up elsewhere.
- Engage the comparative literature across regions, not only the area-studies literature of the cases; a regionally insular framing is the most common reviewer complaint.
- Cross-national measurement is handled transparently: sources, codings, and coverage are stated, and the substantive size of effects is interpreted in comparative terms.
- Case-based papers make the logic of the comparison explicit and document the evidentiary basis (sources, interviews, archives) so that a reader can audit the claim; mixed designs say which claim rests on which evidence.
- Robustness, alternative specifications, and case appendices go to supplementary material; the main text carries the argument and the decisive exhibits.
- Prepare for anonymous review with identifying material on a separate title page, and build the replication materials and data availability statement as the analysis is done rather than at acceptance.

## Verified submission facts (live-checked 2026-09-02; re-check before submitting)

- Publisher & submission system: SAGE; "Submit your manuscript today at https://mc.manuscriptcentral.com/comppolstud" (ScholarOne) (source: https://uk.sagepub.com/en-gb/eur/comparative-political-studies/journal200828). The SAGE submission-guidelines page is https://journals.sagepub.com/author-instructions/CPS (link verified from https://journals.sagepub.com/toc/cps/current), but its content could not be fetched by automated tools on 2026-09-02.
- Review model: not verified on 2026-09-02.
- Word limit: not verified on 2026-09-02.
- Fees / APC policy for standard submissions: not verified on 2026-09-02.
- Data / replication policy: not verified on 2026-09-02.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Open the live SAGE "Submission guidelines" page for Comparative Political Studies in a browser and follow the current version, not a cached or third-party copy.
- Re-check the peer-review model and anonymisation requirements, the word limit and what it counts, abstract and keyword requirements, reference style, and the title-page contents.
- Re-check the current research-data sharing policy, any Dataverse deposit requirement for quantitative papers, the data availability statement, and the fees or open-access terms.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the comparative claim and what the cases or sample are a case of.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the cross-regional comparative literature on this question.
- [ ] Cross-national measures and case evidence are documented well enough for a comparativist from another region to audit.
- [ ] Replication materials and the data availability statement are staged; the manuscript is anonymised per the live guidelines.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A single-case study with no comparative claim, or a regional paper that never says why comparativists elsewhere should care.
- Causal language draped over a cross-national correlation with no design that rules out the leading rival explanation.
- Methodology without a substantive comparative question, or a general-politics paper with no comparative leverage that belongs in BJPS or APSR.
- Opaque codings, unreproducible analysis, or a manuscript that ignores the journal's format and length rules.

## Re-routing decision

- General political-science significance beyond comparative politics → `british-journal-of-political-science` or the `apsr` / `ajps` / `jop` deep packs; grand comparative-historical or IR-inflected arguments → the `world-politics` deep pack.
- Policy, administration, and the organisation of the state → `governance-journal`; conflict and cooperation with a quantitative/formal core → `journal-of-conflict-resolution`.
- Method-first contributions or research notes → `political-science-research-and-methods`; European party and electoral politics → European Journal of Political Research, West European Politics, or Party Politics; area-focused work → a regional studies journal.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Comparative Political Studies
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the design and its registered reporting give real comparative leverage?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <ScholarOne / review model and anonymisation / word limit / abstract / data sharing and Dataverse / fees>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
