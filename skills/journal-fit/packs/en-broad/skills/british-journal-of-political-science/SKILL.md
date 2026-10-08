---
name: british-journal-of-political-science
description: Use when targeting British Journal of Political Science (BJPS / BJPolS) or deciding whether a political-science manuscript of general significance fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, verified submission facts, official-submission re-check, and desk-reject heuristics.
---

# British Journal of Political Science (british-journal-of-political-science)

## Journal positioning

BJPS is a top general political-science journal published by Cambridge University Press and run as an independent journal whose policy is set by its editorial team with the approval of its editorial board. Its editorial statement is unusually explicit: the journal is "committed to no methodological orthodoxy over and above the normal canons of scholarship", invites contributions in all fields of political science and political theory except the history of political thought, and publishes "innovative and authoritative work addressed to problems of general significance to students of politics" whatever period or place supplies the evidence. In practice it is the European counterpart to APSR/AJPS: comparative politics, political behaviour, institutions, political economy, and empirically engaged political theory all appear, with a taste for clear argument and general implications over subfield technique. It also runs a Letters format for short, big-point papers.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Cambridge Core site and the Editorial Manager submission system.

## When to trigger

- The author names BJPS / BJPolS as the target venue, or wants a general political-science journal with a European editorial base.
- A subfield paper (comparative, behaviour, institutions, IR, theory) needs re-framing so a generalist reader sees the "general significance to students of politics".
- A compact result with one sharp finding might fit the Letters format rather than a full article.
- The author needs BJPS's desk-reject risks and a credible alternative list (APSR, AJPS, JOP, CPS, PSRM, World Politics).

## Scope & topic fit

- Comparative politics and political institutions: elections and electoral systems, parties, legislatures, executives, federalism, democratisation and backsliding.
- Political behaviour and public opinion: voting, partisanship, polarisation, participation, political communication, survey and experimental studies across countries.
- Political economy of policy, redistribution, and representation; political sociology of class, identity, migration, and gender.
- International relations and conflict when the argument speaks to general political science rather than to an IR-internal debate.
- Empirical and analytical political theory, formal models with substantive payoff, and methodological contributions tied to a substantive question; history of political thought is excluded by editorial policy.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- Lead with the general question and the answer: the first pages should convince a reader from another subfield that the finding changes how they think about politics, not only how specialists think about the case.
- Choose the format deliberately: Research Articles are the default; Letters are short, highly accessible pieces "making a big point shortly and succinctly"; Comments respond to published BJPS work.
- The abstract is short and the reference style is in-text author–date; a LaTeX style file and an Overleaf template exist for authors who want them.
- Anonymise for double-anonymous review: remove names, affiliations, funding acknowledgements, thanks to audiences, and personal or institutional links; self-citations stay in the third person.
- Quantitative articles are written so that the deposited data, codebook, command files, and output files on the BJPolS Dataverse regenerate every table and figure; the journal is a DA-RT signatory and holds articles at copy-editing until the deposit is checked.
- Word counts are total counts (appendix and bibliography excepted), so long robustness sections and case appendices belong in the online appendix.

## Verified submission facts (live-checked 2026-09-02; re-check before submitting)

- Publisher & submission system: Cambridge University Press; submissions via Editorial Manager (https://www.editorialmanager.com/bjpols/default.aspx) (source: https://www.cambridge.org/core/journals/british-journal-of-political-science/information/author-instructions/preparing-your-materials).
- Review model: "This journal uses a double-anonymous peer review model", usually with a minimum of two independent peer reviewers (source: https://www.cambridge.org/core/journals/british-journal-of-political-science/information/journal-policies/publishing-ethics).
- Word limit: Research Articles "generally be between 4,000 and 10,000 words in length", with longer pieces considered only in exceptional circumstances; Letters up to 4,000 words; "All parts of the manuscript count towards the word count with the exception of the appendix and the bibliography"; abstract not exceeding 150 words (source: https://www.cambridge.org/core/journals/british-journal-of-political-science/information/author-instructions/preparing-your-materials).
- Fees / APC policy for standard submissions: no submission fee is stated; an APC applies only to open-access publication, may be covered by a Cambridge open-access agreement, and can be waived for authors without funding; Comments carry no APC (source: https://www.cambridge.org/core/journals/british-journal-of-political-science/information/author-instructions/preparing-your-materials).
- Data / replication policy: authors of accepted quantitative articles must deposit data, codebook, command files, and output files on the BJPolS Dataverse at Harvard Dataverse; "All analyses reported in the BJPolS are open and available to the scientific research community" (source: https://www.cambridge.org/core/journals/british-journal-of-political-science/information/author-instructions/preparing-your-materials; the Cambridge-hosted Instructions for Contributors at http://assets.cambridge.org/JPS/JPS_ifc.pdf gives the same policy and the editorial statement quoted above).

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "British Journal of Political Science author instructions / preparing your materials" and follow the current Cambridge Core version.
- Re-check article type (Research Article, Letter, Comment), the word ranges and what counts, the 150-word abstract and keyword count, anonymisation, ORCID for the corresponding author, and the funding and competing-interest declarations.
- Re-check the BJPolS Dataverse replication requirements and the citation sentence the journal asks authors to place after the acknowledgments.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] One sentence stating the problem of general significance to students of politics that this paper resolves.
- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the discipline-wide literature, not only the subfield or regional literature.
- [ ] Format chosen (article versus Letter) matches the size of the contribution, and the total word count is within range.
- [ ] Replication package is staged for the BJPolS Dataverse and the manuscript is fully anonymised.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A competent subfield or single-country paper with no argument for why it matters to political scientists in general.
- History of political thought, or a methods note with no substantive political question attached.
- A manuscript far outside the word range, or one whose anonymisation fails (acknowledgements, self-references in the first person, identifying links).
- No feasible replication deposit for a quantitative paper.

## Re-routing decision

- US-centred general journals with the same ambition → the `apsr`, `ajps`, or `jop` deep packs; comparative politics with a cross-national or subnational design → `comparative-political-studies`.
- Method-centred contributions or research notes → `political-science-research-and-methods`; conflict and cooperation → `journal-of-conflict-resolution`; international politics → the `international-organization` or `world-politics` deep packs.
- Policy, administration, and institutions of the state → `governance-journal`; shorter general pieces → Research & Politics or Political Studies.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] British Journal of Political Science
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the design and its registered reporting support a claim of general political-science significance?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <Editorial Manager / article vs Letter / word range / 150-word abstract / anonymisation / BJPolS Dataverse>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
