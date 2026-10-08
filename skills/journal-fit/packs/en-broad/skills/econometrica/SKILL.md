---
name: econometrica
description: Use when targeting Econometrica or deciding whether an economics manuscript fits this venue. Encodes the journal's fit, framing, core-contract reporting boundary, house style, official-submission re-check, and desk-reject heuristics.
---

# Econometrica (econometrica)

## Journal positioning

Econometrica is the journal of the Econometric Society and one of the economics "top-5" (with AER, QJE, JPE, REStud) — the most technical of the five. It publishes econometric theory, economic theory, and highly rigorous structural and empirical work, where the contribution is typically a new theorem, a new identification result, or a new estimator, established to the field's highest formal standard. The readership is technically expert; a paper succeeds on the depth and correctness of its formal contribution, not on topical interest alone.

This skill is a **fit / venue-selection / re-framing** tool. It does not replace the journal's current official submission guidelines. Before submitting, re-check the live author instructions on the Econometric Society / Wiley site and the editorial submission system.

## When to trigger

- The author names Econometrica (or the top-5 with a technical contribution) as the target venue.
- A paper proves new theorems, establishes new identification, or develops a new estimator with full asymptotic theory.
- A structural or empirical paper rests on a genuinely new methodological contribution that needs the most rigorous venue.
- The author needs Econometrica's desk-reject risks and a credible top-5 / methods-journal alternative list.

## Scope & topic fit

- Econometric theory: estimation, inference, identification, asymptotics, nonparametrics, time series, panel, and high-dimensional methods.
- Economic theory: decision theory, game theory, mechanism and market design, general equilibrium, with general theorems.
- Highly rigorous structural econometrics where the identification and estimation argument is itself a contribution.
- Empirical work only when paired with a genuine new method or identification result, not standard applied designs.

## Method & evidence reporting boundary

- Report the active `empirical-research` core contract ID and revision and, as applicable, its registered estimand or theoretical target, assumptions, diagnostic dispositions, hash-bound Artifact IDs, and observed inference ceiling.
- Explain why those already-registered records matter to this venue's audience. This venue profile does not select estimators, clustering levels, thresholds, diagnostics, or repairs.
- If a required core record is absent or failed, return the design to `empirical-research` and report the resulting narrowed or withdrawn inference; do not repair it in the venue layer.
- Keep the venue-specific placement, data/code, disclosure, and transparency requirements below.

## Structure & house style

- The introduction states the formal problem, the gap in existing theory, the precise contribution (theorem/estimator/identification result), and how it improves on prior results.
- Definitions, assumptions, propositions, and theorems are stated formally in the main text; long proofs and derivations move to appendices and supplementary material.
- Econometrica enforces a substantial supplementary material / proof appendix and replication standard; an unstructured abstract and JEL codes are standard.
- Notation must be consistent and economical; exhibits (where present) support a method's properties (size, power, coverage) rather than a topical narrative.

## Official-submission checklist

- Before giving submission-ready advice, read `../../resources/source-basis.md` and `../../resources/official-source-map.md`; start from the official source anchors for this journal family, then cite the current journal-specific page you checked.
- Search the live site for "Econometrica submission guidelines" / "information for authors" and the Econometric Society replication and supplementary-material policy, and follow the current versions.
- Re-check the submission fee, LaTeX/formatting requirements, abstract/JEL, anonymization, and supplementary-material/proof-appendix conventions on the submission system.
- Re-check the current data, code, and replication-package deposit policy and any computational-verification workflow before acceptance.
- If the live official instructions conflict with this skill, the official instructions win.

## Pre-submission self-check

- [ ] The applicable core contract ID/revision, hash-bound diagnostics, and observed inference ceiling are reported without venue-layer alteration.
- [ ] The contribution is stated as a formal result, not as an empirical finding or statistical significance.
- [ ] The introduction positions the paper against the precise prior theory/econometrics it generalizes or corrects.
- [ ] Supplementary material, proofs, and any replication package match the current official guide.

## Common desk-reject triggers

- Hiding, overriding, or rhetorically repairing a failed core diagnostic or observed inference ceiling instead of reporting the registered disposition.
- A theory result that is a narrow special case, lacks general proofs, or restates known results.
- Incomplete or incorrect proofs, hidden assumptions, or sloppy formal exposition.

## Re-routing decision

- Rigorous but more topical applied econometrics → `journal-of-econometrics`, `journal-of-applied-econometrics`, `journal-of-business-and-economic-statistics`, or `quantitative-economics`.
- General economic-theory results without the top-5 importance → `journal-of-economic-theory` or `aej-microeconomics`; game theory → `games-and-economic-behavior`.
- General-interest empirical or applied work → `american-economic-review`, `quarterly-journal-of-economics`, or `journal-of-political-economy`.
- Frontier theory/methods with novelty over generality → `review-of-economic-studies`.

## Output format

```text
[Fit] High / Medium / Low (one-line reason)
[Target] Econometrica
[Topic tags] <2–3 closest topics>
[Method/evidence] <does the formal contribution — theorem / estimator / identification — clear Econometrica's bar?>
[Top risk] <the single most likely reason for rejection>
[Official items to re-check] <submission system / fee / LaTeX / supplementary proofs / replication policy>
[Re-route suggestion] <if not a fit, a better-matched venue>
```
