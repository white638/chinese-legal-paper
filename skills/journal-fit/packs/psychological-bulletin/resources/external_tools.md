# External Tools & Resources for Psychological Bulletin-Style Research Synthesis

> **Tool catalog only.** Use a package here only when the empirical-core contract already selected its
> method and validator. This venue resource does not choose estimators, diagnostics, thresholds, or repairs.

Tools, software, and standards useful when preparing a *Psychological Bulletin* submission.
Psychological Bulletin publishes **research syntheses** — **systematic reviews, meta-analyses,
meta-reviews/meta-synthesis, and rigorous qualitative reviews** — **not** original primary studies.
So the toolchain is built around the **synthesis lifecycle**: protocol registration, systematic
searching, screening and coding, effect-size computation, random-effects modeling, moderator and
publication-bias analysis, and MARS/PRISMA/JARS-compliant reporting. Check licenses and current
access terms before use, and verify any Psychological Bulletin-specific policy in
[`official-source-map.md`](official-source-map.md).

## 1. Reporting standards & protocol registration

| Standard / venue | Provider | Use |
|------------------|----------|-----|
| **MARS** (Meta-Analysis Reporting Standards) | APA Style / JARS | Required items for reporting a meta-analysis |
| **PRISMA 2020** (statement + checklist + flow diagram) | PRISMA | Required for systematic reviews; the records-flow diagram |
| **JARS** (Journal Article Reporting Standards) | APA Style | Quantitative / mixed-methods reporting structure |
| **PRISMA extensions** (PRISMA-S search, PRISMA-P protocol, PRISMA-NMA) | PRISMA | Search reporting; protocol; network meta-analysis |
| **PROSPERO** | CRD, University of York | Prospective registration of the review protocol |
| **OSF Registries** | Center for Open Science | Preregister protocol/analysis plan; deposit materials |
| **TOP Guidelines** | Center for Open Science | Transparency/openness levels APA journals adopt |

## 2. Systematic search & screening

- **Databases:** APA **PsycINFO** / PsycNET, **MEDLINE/PubMed**, **Web of Science**, **Scopus**,
  **ERIC**, **EMBASE**, **ProQuest Dissertations & Theses** (grey literature) — search at least the
  core multidisciplinary + psychology databases and document each.
- **Grey literature & registries:** Google Scholar (supplementary), conference programs,
  preprint servers (PsyArXiv), trial/registry records, contacting authors for unpublished data.
- **Search building:** controlled vocabulary (MeSH / APA Thesaurus) + free-text; record the **exact
  string, database, date, and hit count per source** (PRISMA-S); deduplicate and log it.
- **Screening managers:** **Covidence**, **Rayyan**, **DistillerSR**, **EPPI-Reviewer**, or
  **abstractr** — implementations for the screening stages, identities, and reconciliation Artifacts
  already registered by the core review contract; this catalog does not set screener staffing.
- **Citation/reference managers:** **Zotero**, **EndNote**, **Mendeley** for dedup and PRISMA counts.

## 3. Coding and validation implementations

- Coding, validation, and disagreement tools implement only the codebook, identity, staffing, and
  validation plan registered by the empirical-core contract.
- Report the selected validation identity, Artifact IDs, and disposition under
  `CORE.MEASUREMENT.REGISTERED_VALIDATION`; this catalog sets no coder count, statistic, or threshold.

## 4. Effect sizes, meta-analytic models & diagnostics

### R (dominant for psychological meta-analysis)
- **`metafor`** — the workhorse: random/mixed-effects models, meta-regression, `escalc()` for
  effect-size computation (SMD/Hedges' g, log OR/RR, r → z), forest/funnel plots, influence diagnostics
- **`robumeta` / `clubSandwich`** — **robust variance estimation (RVE)** for dependent effect sizes
- **`metafor` rma.mv` + `clubSandwich`** — **multilevel / three-level** meta-analysis
- **`dmetar`** — companion functions, PET-PEESE, GOSH plots
- **`puniform`, `weightr`, `metasens`** — p-uniform, **selection models**, sensitivity to bias
- **`p-curve`** (p-curve.com app or scripts) — evidential value / p-hacking diagnostics
- **`netmeta` / `gemtc`** — network (multiple-treatments) meta-analysis

### Other software
- **Stata:** `meta` suite (`meta set`, `meta summarize`, `meta forestplot`, `meta regress`,
  `meta funnelplot`, `meta bias`, `meta trimfill`)
- **Comprehensive Meta-Analysis (CMA)** — point-and-click meta-analysis
- **Python:** `PythonMeta`, `statsmodels`; **JASP** / **jamovi** (MAJOR module) for GUI workflows
- **RevMan** (Cochrane) — common in health-adjacent syntheses

### Diagnostic implementations represented in this catalog
- Heterogeneity, selective-reporting, influence, and alternative-metric implementations are listed so
  authors can locate the package already named by the empirical-core contract.
- This list is not a required battery. Report the registered diagnostic identity, Artifact IDs,
  disposition, and inference consequence under `CORE.INFERENCE.SENSITIVITY_BINDING`.

## 5. Figures & exhibits Psychological Bulletin expects
- **PRISMA flow diagram** (records identified → screened → eligible → included, with exclusion reasons)
- **Forest plots** (study effects, weights, pooled estimate + CI and prediction interval)
- **Funnel plots** (with contour enhancement) and bias-diagnostic plots
- Moderator / meta-regression bubble plots; colorblind-safe palettes; vector output (PDF/EPS)

## 6. Writing, references & transparency package
- Format to **APA 7th edition**; **abstract ≤ 250 words**; reference managers (Zotero/BibTeX/EndNote)
- Prepare a **masked** manuscript (no author clues; neutralize self-citations) plus a separate title page
- Deposit the **database, codebook, and analysis scripts** to a trusted repository (OSF / institutional)
  with a persistent identifier; state availability per the journal's transparency policy

## 7. Cautions
1. **It is a synthesis, not a study.** Psychological Bulletin does not publish original primary data
   (those go elsewhere; original theory to *Psychological Review*). Build a review, not an experiment.
2. **Search must be systematic and reproducible.** Document every database, string, date, and count
   (PRISMA-S); another team should be able to re-run it.
3. **Disclose dependent inputs.** Report the effective unit, core-selected dependence procedure,
   diagnostic Artifacts, and disposition under `CORE.INFERENCE.DEPENDENCE_ALIGNMENT`; this catalog does
   not choose between available implementations.
4. **Disclose selective-reporting diagnostics.** Report the procedures selected by the core contract,
   including conflicting or failed results; this catalog does not prescribe a universal battery.
5. **Verify volatile specifics** (TOP level, abstract/length, accepted types, fee/APC) on the official
   APA page — they change; unverified items are marked 待核实.
