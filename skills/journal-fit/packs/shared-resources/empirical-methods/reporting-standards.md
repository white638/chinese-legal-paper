# Modern Inference and Reporting: Table Stakes for Empirical Submissions

Shared hub resource for the English journal packs (APSR, AJPS, JOP, IO, ASR/AJS, AER-style economics, AERJ, and the rest). It lists what a referee at these venues assumes is *already there* before reading the argument. Venue-specific limits (word counts, blinding, data policy wording) stay in each pack's `official-source-map.md`; this file is venue-neutral.

Companion and source of record: the Chinese reporting standard at [`../../../../empirical-research/references/reporting-standards.md`](../../../../empirical-research/references/reporting-standards.md) (table layout, Chinese journal conventions, QCA / process-tracing / content-analysis / interview / survey reporting, 20-item self-check). This file adds what English-language top journals additionally expect on inference; where the two differ, the Chinese file governs table format and the target pack governs venue rules.

Non-negotiable across both: every number in text, tables, figures, and abstract traces to an accepted-action result and hashed artifact in `method_execution.json` (see `empirical-research/references/method-execution-contract.md`). Hand-typed statistics have no locator and do not survive the build gate.

What lives in the Chinese source and is not repeated here: three-line table layout and note order, the M1→M5 progressive-controls column design, DV-mean and fixed-effect row conventions, the star convention for Chinese journals, figure typography, the QCA solution-table notation (Fiss 2011) with necessity/RoN and truth-table appendix rules, the process-tracing evidence ledger, content-analysis reliability reporting, interview citation and saturation rules, survey response-rate and scale-reliability reporting, the variable-definition and data-source appendix tables, and the 20-item self-check.

## 1. Standard errors and clustering

- Cluster at the level at which treatment was assigned or sampling was clustered, and say why in the table note (Abadie, Athey, Imbens & Wooldridge 2023; Cameron & Miller 2015). "We cluster by province" without a reason reads as a guess.
- Panels with serially correlated outcomes: cluster by unit, not unit-year (Bertrand, Duflo & Mullainathan 2004).
- Few clusters (roughly < 30–50): report wild cluster bootstrap p-values (Cameron, Gelbach & Miller 2008; MacKinnon & Webb 2018; Roodman et al. 2019 `boottest`). Print the number of clusters in every table.
- Two-way clustering only with a stated reason and enough clusters in both dimensions. Geographic treatments: spatial HAC (Conley 1999) with the cutoff distance reported and varied.
- Every table note states: SE type, clustering level, number of clusters. If the stars change under the bootstrap, the stars in the table change.

## 2. Weak-instrument diagnostics

- Report the first stage (coefficient, SE) in the main table or immediately below it, plus the reduced form.
- Use the effective F (Montiel Olea & Pflueger 2013) under heteroskedasticity or clustering, not the homoskedastic Stock–Yogo critical values; Kleibergen–Paap rk F only as a fallback. Say which one you report.
- Just-identified single instrument: F > 10 does not deliver nominal coverage; report the tF-adjusted confidence interval (Lee, McCrary, Moreira & Porter 2022).
- Always add an Anderson–Rubin confidence set (Anderson & Rubin 1949; Andrews, Stock & Sun 2019). It stays valid when the instrument is weak; a paper with only a 2SLS CI is exposed.
- Exclusion restriction: an institutional argument plus a placebo where the first stage should be zero. Hansen J is necessary-not-sufficient and only exists for overidentified models.
- Characterize compliers (Angrist & Pischke 2009; Marbach & Hangartner 2020) and say whose LATE you estimated. Explain the direction of the OLS–IV gap.
- Shift-share / Bartik designs: state which exogeneity you rely on (shares: Goldsmith-Pinkham, Sorkin & Swift 2020; shocks: Borusyak, Hull & Jaravel 2022) and report Rotemberg weights.

## 3. Multiple testing

- Define hypothesis families before estimation; pre-register when feasible and list deviations from the PAP.
- Within a family: Romano–Wolf stepdown (Romano & Wolf 2005; Clarke, Romano & Wolf 2020) or List, Shaikh & Xu 2019. Across many outcomes: summary indices (Kling, Liebman & Katz 2007; Anderson 2008) or Benjamini–Hochberg FDR (Benjamini & Hochberg 1995).
- Report adjusted and unadjusted p-values side by side; label exploratory subgroup cuts as exploratory and keep them out of the abstract.
- Twelve heterogeneity cuts with two reported is the pattern referees look for first.

## 4. Difference-in-differences with staggered adoption

- Name the estimator: Callaway & Sant'Anna 2021, Sun & Abraham 2021, de Chaisemartin & D'Haultfœuille 2020, Borusyak, Jaravel & Spiess 2024, or Gardner 2022. Name the comparison group (never-treated vs not-yet-treated) and why.
- If two-way fixed effects is shown, add the Goodman-Bacon (2021) decomposition and put the heterogeneity-robust estimate next to it.
- Event-study figure: reference period (t = −1) normalized to zero and labeled; 95% CI on every coefficient; pre/post divider; y-axis units; binned endpoints stated; weighting stated.
- Pre-trends: report the joint test, acknowledge its low power (Roth 2022), and add HonestDiD sensitivity (Rambachan & Roth 2023) with the relative-magnitude bound at which the conclusion breaks.
- Cohort × N timing table, a no-anticipation statement with the treatment date defined, and a timeline of concurrent policies.
- State-of-practice survey to cite when justifying choices: Roth, Sant'Anna, Bilinski & Poe 2023.

## 5. Regression discontinuity

- Local linear with a triangular kernel and the CCT MSE-optimal bandwidth (Calonico, Cattaneo & Titiunik 2014); report conventional and bias-corrected robust CIs and make the robust CI the headline. No global high-order polynomials (Gelman & Imbens 2019).
- Density test at the cutoff (McCrary 2008; Cattaneo, Jansson & Ma 2020) plus an institutional account of who controls the score.
- Covariate continuity at the cutoff (plots and estimates), placebo cutoffs, and a bandwidth-sensitivity plot (estimate with CI across bandwidths).
- Effective N on each side; the RD plot states its binning rule (Calonico, Cattaneo & Titiunik 2015).
- Discrete or heaped running variables: donut RD and honest CIs for discrete scores (Kolesár & Rothe 2018).
- Fuzzy RD: report the first stage at the cutoff. Practical reference: Cattaneo, Idrobo & Titiunik 2020.

## 6. Matching and weighting

- Balance by standardized mean differences and variance ratios, shown as a Love plot; t-test p-values are not balance evidence (Austin 2009; Stuart 2010).
- Report common support, the number of units pruned, and whether the estimand after pruning is ATT or ATE.
- Method details: algorithm, calipers, replacement, the propensity model or balancing approach (entropy balancing, Hainmueller 2012; CBPS, Imai & Ratkovic 2014).
- SEs that account for matching (Abadie & Imbens 2006, 2016).
- Sensitivity to unobservables: Rosenbaum bounds, Cinelli & Hazlett 2020 robustness values, or Oster 2019.
- Never write "matching eliminates selection bias"; write "selection on observables" and defend it.

## 7. Experiments, survey experiments, and synthetic control

- Experiments: pre-registration link and a deviations list; randomization check as a balance table with SMDs, not a paragraph of p-values; attrition by arm with a differential-attrition test and Lee (2009) bounds when attrition differs; manipulation and attention checks with exclusion rules fixed before unblinding and the exclusion rate reported; ITT as headline, CACE/LATE for compliers with the compliance rate.
- Survey experiments: the sample frame and quota or weighting scheme; the exact wording of every treatment arm in the appendix; a placebo or pure-control arm; multiple-comparison handling across arms (Section 3).
- Synthetic control (Abadie 2021): donor pool and exclusion rules; pre-treatment fit (RMSPE) and the weights table; in-space and in-time placebos with the permutation p-value or RMSPE ratio; leave-one-out donor sensitivity.
- Panel fixed effects without an exogenous shock: say so; report within-R² and the identifying variation that remains after the fixed effects; do not write "causal effect".

## 8. Effect-size language

- Every headline effect carries a point estimate, SE or CI, N, and a base (dependent-variable mean or SD).
- Translate: "0.118 log points, about 12% of the sample mean"; "one SD of X moves Y by 0.09 SD"; "equivalent to moving a county from the median to the 75th percentile".
- Binary and count models: report average marginal effects, not raw coefficients; interactions in nonlinear models need computed marginal effects (Ai & Norton 2003).
- Banned: "significantly increases" as a substitute for a magnitude; "highly significant" as a substitute for a large effect.
- Inference language matches design: LATE for the compliers, ATT for the treated, local effect at the cutoff; a separate paragraph for any external-validity claim.

## 9. Null results

- "Not significant" is not "no effect". Choose one: an equivalence test against a stated smallest effect of interest (Lakens 2017; Rainey 2014); the minimum detectable effect at 80% power; or a substantive reading of both CI bounds.
- When a null contradicts prior work, show that your design had power to detect the previously reported magnitude.
- Nulls go through the same robustness sequence as positive results and stay in the main text.

## 10. Tables and figures: minima

- Table notes, in order: data and sample; SE type, clustering level, number of clusters; significance convention. Rows at the bottom: controls, one row per fixed-effect dimension, N, R² (say which), dependent-variable mean.
- Stars: two-tier (5%/1%) or none-with-CIs, by venue; consistent across the paper and the appendix. Multiple-testing-adjusted inference in its own column or note.
- Columns ≤ 6–7; progressive controls M1→M5 to show coefficient stability, not to pick a column.
- Robustness order: measurement → sample → model → placebo → sensitivity bounds; one change per column. More than ~20 specifications: a specification curve (Simonsohn, Simmons & Nelson 2020) with the share of same-sign and CI-excluding-zero specs.
- Figures: coefficient plots with CIs instead of bar charts of point estimates; grayscale-legible; vector output; axis units.

## 11. Replication package norms

- DA-RT (Lupia & Elman 2014): data access, analytic transparency, production transparency.
- In general terms: AJPS requires replication materials and has them verified by a third party before publication (quantitative and qualitative); JOP requires deposit of replication materials as a condition of publication; APSR expects Dataverse deposit; AEA journals run Data Editor verification. Check the target pack's `official-source-map.md` for current wording before citing a policy in a cover letter.
- Package contents: a README with run order and expected run time; scripts from raw data to every table and figure; software and package versions; seeds; a codebook; a data availability statement naming the source and the access route. Restricted data need a documented access path, not "available upon request".
- Qualitative strands: annotated citations / ATI where feasible, an interview methods table (Bleich & Pekkanen 2013), and the anonymization protocol.
- The package mirrors the `method_execution.json` result chain; numbers that are not in that chain are not in the package.

## 12. Pre-submission inference audit

1. Clustering level justified in words; number of clusters printed; bootstrap p-values if clusters are few.
2. IV: first stage shown; effective F or tF; AR confidence set; exclusion argued and placebo-tested; compliers characterized.
3. Multiple testing: families defined; adjusted p-values reported; exploratory cuts labeled.
4. Staggered DiD: estimator and comparison group named; Bacon decomposition if TWFE shown; event-study figure complete; HonestDiD bound reported.
5. RDD: CCT bandwidth; robust CI; density test; covariate continuity; bandwidth sensitivity; placebo cutoffs.
6. Matching: SMD balance plot; common support; matching-aware SEs; sensitivity to unobservables.
7. Every headline effect has a magnitude in interpretable units and a CI.
8. Null results stated as equivalence, MDE, or CI bounds.
9. Tables: notes complete; DV mean row; FE rows; ≤ 7 columns; stars consistent.
10. Robustness ordered and one change per column; specification curve if many specs.
11. Figures grayscale-legible with units and CIs.
12. Replication package runs end-to-end from raw data; data availability statement executable.
13. Every reported number traces to an accepted-action result and hashed artifact.
14. Inference language matches the design and the estimand.

## Sources

Abadie 2021; Abadie & Imbens 2006, 2016; Abadie, Athey, Imbens & Wooldridge 2023; Ai & Norton 2003; Anderson 2008; Anderson & Rubin 1949; Andrews, Stock & Sun 2019; Angrist & Pischke 2009; Austin 2009; Benjamini & Hochberg 1995; Bertrand, Duflo & Mullainathan 2004; Bleich & Pekkanen 2013; Borusyak, Hull & Jaravel 2022; Borusyak, Jaravel & Spiess 2024; Callaway & Sant'Anna 2021; Calonico, Cattaneo & Titiunik 2014, 2015; Cameron, Gelbach & Miller 2008; Cameron & Miller 2015; Cattaneo, Idrobo & Titiunik 2020; Cattaneo, Jansson & Ma 2020; Cinelli & Hazlett 2020; Clarke, Romano & Wolf 2020; Conley 1999; de Chaisemartin & D'Haultfœuille 2020; Gardner 2022; Gelman & Imbens 2019; Goldsmith-Pinkham, Sorkin & Swift 2020; Goodman-Bacon 2021; Hainmueller 2012; Imai & Ratkovic 2014; Kling, Liebman & Katz 2007; Kolesár & Rothe 2018; Lakens 2017; Lee 2009; Lee, McCrary, Moreira & Porter 2022; List, Shaikh & Xu 2019; Lupia & Elman 2014; MacKinnon & Webb 2018; Marbach & Hangartner 2020; McCrary 2008; Montiel Olea & Pflueger 2013; Oster 2019; Rainey 2014; Rambachan & Roth 2023; Romano & Wolf 2005; Roodman, Nielsen, MacKinnon & Webb 2019; Roth 2022; Roth, Sant'Anna, Bilinski & Poe 2023; Simonsohn, Simmons & Nelson 2020; Stuart 2010; Sun & Abraham 2021.
