---
name: journal-of-accounting-research
description: Use when targeting Journal of Accounting Research (JAR) or deciding whether an accounting manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Journal of Accounting Research (journal-of-accounting-research)

## Journal positioning

JAR, published out of Chicago Booth, is one of accounting's "big three" and the standard-bearer for economics-based, empirically rigorous accounting research. Its core is archival capital-markets and analytical work judged on the strength of the research design and identification, with a famously high empirical bar. JAR runs an annual conference issue that publishes new, discussant-vetted research. Readership is the economics-oriented accounting and accounting-finance community.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the JAR / Chicago Booth / Wiley site and the submission system.

## When to trigger

- The author names JAR (or the economics-based accounting top tier) as the target venue.
- An archival capital-markets or analytical accounting paper with a clean design and strong identification needs positioning.
- An accounting paper whose strength is its identification strategy needs framing for the highest empirical bar.
- The author needs JAR's desk-reject risks and a credible JAE / TAR / RAST alternative list, or wants to consider the annual conference issue.

## Scope & topic fit

- Capital-markets accounting: information content of disclosure, earnings, analysts, market efficiency, and price formation.
- Economics of disclosure and reporting, contracting, and the consequences of regulation and standards.
- Analytical accounting theory with empirically relevant implications.
- Auditing, tax, and managerial questions when framed with an economics lens and strong identification.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the economic question, the identification strategy, and the contribution up front, distinguishing it from the closest prior work.
- A strong JAR paper foregrounds the research design and treats robustness/falsification as central, not appendix afterthoughts.
- JAR expects an online appendix for additional tests and a strong data/code transparency posture.
- Writing is spare and economics-flavored; magnitudes and mechanisms matter more than significance stars.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Journal of Accounting Research submission guidelines / author instructions" and follow the current version, including any conference-issue call.
- Re-check submission fee, formatting, abstract conventions, anonymization, reference style, and the online-appendix requirement.
- Re-check current data and code availability / replication policies and disclosure/ethics requirements.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The introduction positions the paper against the closest recent JAR / JAE work.
- [ ] Data/code transparency and the online appendix are ready per the current guide.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A paper that is really finance or economics with no distinct accounting contribution.

## Re-routing decision

- Economics-based accounting with contracting/disclosure/positive-theory emphasis → `journal-of-accounting-and-economics`.
- Broad accounting across methods → `the-accounting-review`; analytical/empirical valuation and information economics → `review-of-accounting-studies`.
- Methodologically pluralistic elite → `contemporary-accounting-research`; interpretive/critical → `accounting-organizations-and-society`.
- Capital-markets work that is really finance → `journal-of-finance` / `journal-of-financial-economics`; economics-core → a field economics venue.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Journal of Accounting Research
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the identification clear JAR's empirical bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / conference issue / online appendix / data-code>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
