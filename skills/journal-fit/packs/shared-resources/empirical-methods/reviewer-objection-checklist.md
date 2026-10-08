# The Objections Referees Actually Raise, by Identification Strategy

Shared hub resource for the journal-fit English packs. Each entry is an objection in the form a referee report phrases it, followed by the preemption: what to put where (main text section, exhibit, or appendix) so the objection is answered before it is raised. Use it before drafting tables, then again as the pre-submission stress test at the end.

Reporting conventions the preemptions rely on are in [`reporting-standards.md`](reporting-standards.md); the Chinese source of record for table layout and qualitative reporting is [`../../../../empirical-research/references/reporting-standards.md`](../../../../empirical-research/references/reporting-standards.md). Every exhibit named below must be generated from an accepted-action result in `method_execution.json`; an exhibit you cannot regenerate is not a preemption.

Format: **Objection** → *Preempt:* what · where.

## How to use

1. Before the first table: read the section for every identification strategy or evidence strand in the design and list which preemptions you can already produce from `method_execution.json` artifacts.
2. While building results: each preemption names an exhibit; generate the exhibit before writing the paragraph that leans on it.
3. Before submission: fill the stress-test table at the end. Every row needs a location; "will add if asked" is a hole.
4. On receiving reports: map each referee comment to an entry here; a comment that maps to nothing is either a new objection worth adding to the pack or a misunderstanding to answer with the existing exhibit.


## 1. Difference-in-differences

1. **"Staggered TWFE with heterogeneous effects makes forbidden comparisons; your estimate is a weighted average of nothing interpretable."** → *Preempt:* the headline must be whatever the core method contract registered for staggered adoption (see `empirical-research` and `quant-causal-inference/references/did-staggered.md`, which cover Callaway & Sant'Anna 2021, Sun & Abraham 2021, Borusyak, Jaravel & Spiess 2024); if TWFE is also shown, put the Goodman-Bacon (2021) decomposition beside it and say why the contract treats it as secondary · design section + main table + appendix decomposition table.
2. **"Parallel trends is asserted, not argued; the pre-trend test is underpowered."** → *Preempt:* an institutional reason why trends would be parallel, the event-study plot, the joint pre-period p-value with Roth 2022 acknowledged, and HonestDiD bounds (Rambachan & Roth 2023) with the breaking point · identification subsection + Figure (event study) + appendix sensitivity.
3. **"The policy was announced earlier than your treatment date; anticipation contaminates the baseline."** → *Preempt:* define the treatment date from the legal/administrative record, show robustness to shifting it and to dropping the announcement window · data section + robustness table.
4. **"Other policies hit the same units at the same time."** → *Preempt:* a policy timeline table for the treated units; controls or exclusion for overlapping reforms; a triple-difference where a within-unit untreated group exists · background section + appendix timeline.
5. **"Timing of adoption is endogenous to the outcome's trajectory."** → *Preempt:* regress adoption timing on pre-period levels and trends of the outcome and show no relation; use not-yet-treated comparisons · appendix table + one sentence in design.
6. **"Wrong clustering / too few clusters."** → *Preempt:* cluster at the treatment-assignment level, print the cluster count, and give wild cluster bootstrap p-values when clusters are few · every table note.
7. **"Spillovers to controls violate SUTVA."** → *Preempt:* exclude geographic or network neighbors and show the estimate moves the right way; distance-ring estimates · robustness table + appendix figure.
8. **"Outcome measurement changed with the treatment."** → *Preempt:* document measurement constancy across the treatment date; a placebo outcome measured the same way that should not respond · data appendix + placebo row.
9. **"Treatment is continuous or has dose variation, but you treat it as binary."** → *Preempt:* state the dose-response assumption; use the continuous-treatment DiD framework (Callaway, Goodman-Bacon & Sant'Anna 2024) or show that the binary cut is not driving the result · design section + robustness table.

## 2. Instrumental variables

1. **"The exclusion restriction is implausible: the instrument affects the outcome through channel Z."** → *Preempt:* name the channels a skeptic would list, argue each from institutions, and run the reduced form in a subsample where the first stage is zero (Conley, Hansen & Rossi 2012 for "plausibly exogenous" bounds) · identification subsection + appendix placebo table.
2. **"The instrument is weak."** → *Preempt:* effective F (Montiel Olea & Pflueger 2013), tF-adjusted CI for the just-identified case (Lee et al. 2022), and an Anderson–Rubin confidence set · main table rows + note.
3. **"Monotonicity fails; there are defiers."** → *Preempt:* argue why the instrument cannot push anyone the wrong way; show first-stage signs are the same across subgroups · appendix table.
4. **"The LATE is not the policy-relevant parameter."** → *Preempt:* profile compliers on observables (Marbach & Hangartner 2020) and state for whom the estimate applies · results subsection + appendix table.
5. **"The instrument is itself an outcome of the confounder (shift-share, historical instruments, weather-as-instrument)."** → *Preempt:* say which exogeneity assumption you use (shares vs shocks), report Rotemberg weights, and test balance of the instrument on pre-determined covariates · design section + appendix.
6. **"You cite Hansen J as proof of validity."** → *Preempt:* cite it as necessary-not-sufficient; never as evidence for the excluded instrument · one sentence.
7. **"You put 2SLS predicted values into a nonlinear second stage."** → *Preempt:* linear 2SLS as headline; control-function estimates only as a labeled robustness check · robustness table.
8. **"Instrument balance is never shown."** → *Preempt:* regress the instrument on pre-determined covariates and show the coefficients are small relative to the first stage; report the instrument's own distribution · appendix balance table.

## 3. Regression discontinuity

1. **"Units manipulate the running variable."** → *Preempt:* density test (McCrary 2008; Cattaneo, Jansson & Ma 2020) and an account of who assigns the score and whether they can see the cutoff · design section + appendix figure.
2. **"The bandwidth is cherry-picked."** → *Preempt:* CCT MSE-optimal bandwidth (Calonico, Cattaneo & Titiunik 2014) as headline; a bandwidth-sensitivity plot with CIs · main table + appendix figure.
3. **"Global high-order polynomials drive the jump."** → *Preempt:* local linear with a triangular kernel; Gelman & Imbens 2019 cited; polynomial order varied in the appendix · method paragraph + robustness table.
4. **"Covariates also jump at the cutoff."** → *Preempt:* continuity plots and estimates for every pre-determined covariate · appendix figure + table.
5. **"Another rule uses the same cutoff (compound treatment)."** → *Preempt:* list every program keyed to the threshold and either net it out or state the bundle as the treatment · background section.
6. **"The running variable is discrete or heaped."** → *Preempt:* donut RD; honest CIs for discrete scores (Kolesár & Rothe 2018) · robustness table.
7. **"Fuzzy RD with a weak first stage at the cutoff."** → *Preempt:* report the first-stage jump with its CI and the compliance rate · main table row.
8. **"The effect is local to the cutoff and irrelevant elsewhere."** → *Preempt:* say so; use multi-cutoff or covariate-based extrapolation only with explicit assumptions (Cattaneo, Keele, Titiunik & Vazquez-Bare 2021) · discussion.
9. **"This is a kink, not a jump, and you are estimating the wrong object."** → *Preempt:* if the rule changes a slope rather than a level, estimate a regression kink design (Card, Lee, Pei & Weber 2015) and report the first-stage kink · design section.

## 4. Double machine learning and ML-derived measures

1. **"Predictive fit is presented as causal identification."** → *Preempt:* state the estimand and the identifying assumption (usually selection on observables); DML with cross-fitting (Chernozhukov et al. 2018) estimates a parameter, it does not create identification · design section.
2. **"No cross-fitting; nuisance models overfit."** → *Preempt:* report folds, repetitions, learners, and hyperparameters · method paragraph + appendix.
3. **"Tuning choices are undisclosed and results are seed-dependent."** → *Preempt:* seeds, tuning grids, and a table of estimates across seeds · appendix.
4. **"Heterogeneity from causal forests is read as policy targeting."** → *Preempt:* calibration test of heterogeneity (Chernozhukov, Demirer, Duflo & Fernández-Val 2018 BLP/GATES) before any targeting claim · results + appendix.
5. **"Unobserved confounding is untouched by the ML step."** → *Preempt:* sensitivity analysis (Cinelli & Hazlett 2020) exactly as for OLS · robustness section.
6. **"Text- or LLM-derived treatment or outcome is unvalidated."** → *Preempt:* a human-coded validation set with precision/recall by class, and an errors-in-variables correction or bound (Grimmer, Roberts & Stewart 2022; Egami, Hinck, Stewart & Wei 2023) · measurement section + appendix.
7. **"Lasso-selected controls without post-selection inference."** → *Preempt:* double selection (Belloni, Chernozhukov & Hansen 2014) · method paragraph.
8. **"Heterogeneous effects are estimated and evaluated on the same sample."** → *Preempt:* honest sample splitting for any CATE ranking or subgroup claim (Athey & Imbens 2016; Wager & Athey 2018) · method paragraph + appendix.

## 5. Matching and weighting

1. **"Balance is shown with t-tests."** → *Preempt:* standardized mean differences and variance ratios in a Love plot (Austin 2009; Stuart 2010) · Figure + appendix table.
2. **"Matching does nothing about unobservables."** → *Preempt:* state selection on observables explicitly; Rosenbaum bounds or Cinelli & Hazlett 2020 robustness values · robustness section.
3. **"Pruning changed the estimand."** → *Preempt:* report common support, the number pruned, and whether the estimate is ATT or ATE for the retained population · results paragraph.
4. **"Post-treatment variables are in the propensity model."** → *Preempt:* a covariate timing table; only pre-treatment covariates enter · data appendix.
5. **"Propensity-score matching is the wrong tool (King & Nielsen 2019)."** → *Preempt:* coarsened exact or Mahalanobis matching, entropy balancing (Hainmueller 2012), or CBPS as alternatives · robustness table.
6. **"Standard errors ignore the matching step."** → *Preempt:* Abadie & Imbens 2006/2016 SEs or an appropriate bootstrap · table note.
7. **"Matching plus DiD without stating conditional parallel trends."** → *Preempt:* name the assumption; use a doubly robust DiD estimator (Sant'Anna & Zhao 2020; Callaway & Sant'Anna 2021) · design section.
8. **"Extreme weights drive the weighted estimate."** → *Preempt:* report the weight distribution, the effective sample size, and results with trimmed or stabilized weights · appendix table + robustness row.

## 6. Mechanism and mediation

1. **"Mediation analysis with an observational mediator assumes sequential ignorability."** → *Preempt:* name the assumption, run the Imai, Keele & Tingley 2010 sensitivity analysis, and report the value at which the indirect effect vanishes · mechanism section + appendix.
2. **"Baron–Kenny three-step is not causal mediation."** → *Preempt:* report ACME/ADE with sensitivity, or controlled direct effects (Acharya, Blackwell & Sen 2016) · mechanism section.
3. **"Heterogeneity is presented as proof of mechanism."** → *Preempt:* state the mechanism's distinguishing predictions and show which rival mechanisms make different predictions; heterogeneity is consistent-with, not proof · mechanism section.
4. **"Rival mechanisms are never adjudicated."** → *Preempt:* a mechanism × prediction × evidence table with each rival's discriminating test · Table + text.
5. **"Controlling for the mediator induces post-treatment bias (Montgomery, Nyhan & Torres 2018)."** → *Preempt:* keep post-treatment variables out of the main specification; show them only in a labeled mechanism specification · robustness section.
6. **"Mechanism evidence comes from a different sample or period."** → *Preempt:* align the mechanism sample with the effect sample or explain the mismatch · data section.
7. **"Qualitative mechanism evidence is cherry-picked."** → *Preempt:* an evidence ledger (evidence, source, test type, update) with the disconfirming pieces included · appendix table.
8. **"The mediator is measured after the outcome, or at the same time."** → *Preempt:* a measurement-timing table showing treatment → mediator → outcome ordering; if the order cannot be established, present the mediation result as descriptive · data section.

## 7. Measurement

1. **"The key variable does not measure the concept."** → *Preempt:* an Adcock & Collier 2001 style validation: conceptual definition, indicators, convergent validity against an external benchmark, and results with an alternative measure · measurement section + robustness.
2. **"Measurement error is correlated with treatment."** → *Preempt:* argue non-differential error or bound the bias; show results with the least error-prone subsample · robustness.
3. **"No coder reliability."** → *Preempt:* Krippendorff's α per variable with the reliability sample size (Hayes & Krippendorff 2007) · method paragraph + appendix.
4. **"Automated or LLM measures are unvalidated."** → *Preempt:* human validation set, precision/recall/F1 by class, separate reporting of model–human agreement and model–model stability · appendix.
5. **"The index weights are arbitrary."** → *Preempt:* component-level results and an alternative weighting · appendix table.
6. **"Winsorizing and logs hide the raw pattern."** → *Preempt:* raw-scale results and the share affected by trimming · appendix.
7. **"Self-reported survey measures suffer from social desirability or acquiescence."** → *Preempt:* list experiment or indirect measure where feasible; reverse-coded items; attention checks and their exclusion rate · survey appendix.
8. **"Aggregate data are used to make claims about individuals (or the reverse)."** → *Preempt:* state the level at which the claim is made and the level at which the variable is measured; where they differ, bound the ecological inference or drop the individual-level language · measurement section.

## 8. External validity

1. **"The sample is not the population of interest."** → *Preempt:* define the target population, compare sample and population moments, and reweight where possible · data section + appendix table.
2. **"The estimate is local (LATE, cutoff, compliers)."** → *Preempt:* say whose effect it is and characterize that group; do not generalize in the abstract · results + discussion.
3. **"This is a context-specific finding (single country, single institution)."** → *Preempt:* scope conditions stated as variables, not as apologies; a mechanism argument about what would have to hold elsewhere (Egami & Hartman 2023) · discussion.
4. **"The period is idiosyncratic."** → *Preempt:* effects by sub-period; a statement of which structural features of the period the mechanism depends on · heterogeneity table.
5. **"Scale-up would change prices, behavior, or general-equilibrium responses."** → *Preempt:* a paragraph on which channels are partial-equilibrium and what a scaled program would change · discussion.
6. **"Survey-experiment realism."** → *Preempt:* manipulation check, comparison to observational benchmarks where they exist, and a statement of what the experiment does not identify · design + discussion.
7. **"Multi-site heterogeneity hidden by pooling."** → *Preempt:* distribution of site-level estimates and a heterogeneity test · appendix figure.
8. **"Elite, student, or online-panel subjects are not the population the theory is about."** → *Preempt:* say which population the theory addresses, compare the sample to it on the moderators the theory names, and report effects by those moderators · design + heterogeneity table.

## 9. Qualitative and case-based designs

1. **"Cases were selected on the dependent variable / it is unclear why these cases."** → *Preempt:* the role of each case in Seawright & Gerring 2008 terms (typical, diverse, deviant, most-similar…) and how the roles map to the claims · design section + case table.
2. **"Evidence is assembled to fit; rivals are not tested."** → *Preempt:* an evidence ledger with test types (Collier 2011) and rival hypotheses, including the tests the favored explanation failed or barely passed; formal Bayesian updating where the weight of evidence is contested (Fairfield & Charman 2017) · appendix table + mechanism section.
3. **"Who was interviewed, how many, and why should we trust them?"** → *Preempt:* an interview methods table (Bleich & Pekkanen 2013): informant type, number, selection, refusal rate, saturation criterion, anonymization protocol · appendix + one paragraph in methods.
4. **"The evidence cannot be verified."** → *Preempt:* DA-RT/ATI style annotated citations (Moravcsik 2014), a source table with archive or document identifiers, and a statement of what is deposited (QDR or equivalent) · appendix + data statement.
5. **"QCA thresholds are arbitrary and there is no robustness."** → *Preempt:* calibration anchors with substantive justification; the Oana & Schneider 2021 robustness protocol (fit- and case-oriented); the Marx & Dușa 2011 benchmark for conditions vs cases · calibration table + robustness section.
6. **"The QCA solution is read as net effects."** → *Preempt:* configurational language throughout; Fiss 2011 solution table with raw/unique coverage, consistency, PRI; separate necessity table with RoN; typical and deviant case returns (Schneider & Rohlfing 2013) · results section.
7. **"The process-tracing narrative has no mechanism steps or timeline."** → *Preempt:* a timeline table; mechanism decomposed into steps with predicted traces and the observed trace for each · appendix + results.
8. **"You generalize from one case."** → *Preempt:* scope conditions; say what kind of case this is (typical vs deviant) and what the case can and cannot establish · discussion.
9. **"Quotes are presented as representative without saying how many informants said the same thing."** → *Preempt:* tag each quoted informant with the informant code and state how many of the relevant informants expressed the view; report the dissenting view · results section.

## 10. Cross-cutting: numbers, selection, and transparency

1. **"N changes across tables without explanation."** → *Preempt:* a sample-construction table from raw observations to each analysis sample, with the reason for every drop; the same N reported in every table note that uses that sample · data appendix.
2. **"The robustness section reports only the checks that passed."** → *Preempt:* a fixed robustness sequence (measurement → sample → model → placebo → sensitivity bounds) announced in the design section and run in full; failed or marginal checks stated in the text · robustness section.
3. **"The abstract claims more than the results support."** → *Preempt:* every abstract number appears in the main table; inference language in the abstract matches the estimand (ATT, LATE, local effect, configuration) · abstract audit.
4. **"The replication package does not run."** → *Preempt:* run the package from raw data on a clean machine before submission; README with run order and expected run time; versions and seeds pinned · replication package.
5. **"Coefficient stability across columns is presented as evidence against confounding."** → *Preempt:* Oster 2019 bounds with the R-max assumption stated, or Cinelli & Hazlett 2020 robustness values; stability alone is not the argument · robustness section.
6. **"A borderline p-value became significant after a specification change."** → *Preempt:* the pre-registered or design-stated headline specification stays the headline; report the borderline result as borderline · results section.
7. **"The number in the text does not match the table."** → *Preempt:* every text number is generated from the same accepted-action result as the table; no hand-typed statistics · build gate.

## Pre-submission stress test

Fill one row per identification strategy or evidence strand in the paper. A row without an exhibit is a hole; two holes on the headline strategy mean the draft is not ready.

| Strategy / strand | Kill-shot objection (from the sections above) | Exhibit that answers it | Location (section / table / figure / appendix) | Status (answered / fix / n.a. with reason) |
|---|---|---|---|---|
| Headline DiD | forbidden comparisons under staggered timing | robust estimator + Bacon decomposition | Table 2 cols 1–2; App. B1 | |
| Headline DiD | parallel trends | event-study figure + HonestDiD bound | Fig. 2; App. B2 | |
| IV strand | exclusion | channel-by-channel argument + zero-first-stage placebo | §4.2; App. C1 | |
| IV strand | weak instrument | effective F / tF / AR set | Table 3 rows | |
| RDD strand | manipulation | density test + assignment account | §4.3; App. D1 | |
| Matching strand | unobservables | Rosenbaum / robustness value | §5.1 | |
| Mechanism | rival mechanisms | mechanism × prediction × evidence table | Table 5 | |
| Measurement | construct validity | validation against benchmark; alternative measure | §3.1; App. A2 | |
| External validity | local estimate | complier profile; scope conditions | §6 | |
| Qualitative strand | selection / rivals / verifiability | case-role table; evidence ledger; source table | App. E | |
| Cross-cutting | sample construction / selective robustness / package runs | sample-flow table; full robustness sequence; clean-machine run | App. A1; §5; package README | |

Each exhibit named in the Location column must exist as a generated artifact before the paper is drafted around it.

## Sources

Abadie & Imbens 2006, 2016; Acharya, Blackwell & Sen 2016; Adcock & Collier 2001; Athey & Imbens 2016; Austin 2009; Belloni, Chernozhukov & Hansen 2014; Bleich & Pekkanen 2013; Borusyak, Jaravel & Spiess 2024; Callaway & Sant'Anna 2021; Callaway, Goodman-Bacon & Sant'Anna 2024; Calonico, Cattaneo & Titiunik 2014; Card, Lee, Pei & Weber 2015; Cattaneo, Jansson & Ma 2020; Cattaneo, Keele, Titiunik & Vazquez-Bare 2021; Chernozhukov et al. 2018; Chernozhukov, Demirer, Duflo & Fernández-Val 2018; Cinelli & Hazlett 2020; Collier 2011; Conley, Hansen & Rossi 2012; Egami & Hartman 2023; Egami, Hinck, Stewart & Wei 2023; Fairfield & Charman 2017; Fiss 2011; Gelman & Imbens 2019; Goodman-Bacon 2021; Grimmer, Roberts & Stewart 2022; Hainmueller 2012; Hayes & Krippendorff 2007; Imai, Keele & Tingley 2010; King & Nielsen 2019; Kolesár & Rothe 2018; Lee, McCrary, Moreira & Porter 2022; Marbach & Hangartner 2020; Marx & Dușa 2011; McCrary 2008; Montgomery, Nyhan & Torres 2018; Montiel Olea & Pflueger 2013; Moravcsik 2014; Oana & Schneider 2021; Rambachan & Roth 2023; Roth 2022; Sant'Anna & Zhao 2020; Schneider & Rohlfing 2013; Seawright & Gerring 2008; Stuart 2010; Sun & Abraham 2021; Wager & Athey 2018.
