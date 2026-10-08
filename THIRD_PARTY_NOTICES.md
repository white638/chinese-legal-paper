# Third-Party Notices

## PaperSpine

Selected algorithmic checks in `skills/cnki-paper/scripts/avereth_core/tools/`
were derived from PaperSpine 4.0.0 by WUBING2023 and subsequently modified for
the CNKI-Paper v6 local research engine. The upstream project is
<https://github.com/WUBING2023/PaperSpine> and is licensed under the MIT
License. The preserved copyright and license text is in
`licenses/PaperSpine-MIT.txt`.

The derived/localized files cover citation identity and traceability,
contribution and results checks, structured reviewer validation, LaTeX and Word
guards, optional section-economy review, and their neutral parsing utilities.
They do not preserve the upstream product, updater, UI, Skill, progress state
machine, or runtime control plane.

The following current files contain or incorporate substantial derived logic:

- `_engine_utils.py`
- `citation_bank_check.py`
- `citation_integrity_audit.py`
- `citation_quality_audit.py`
- `citation_verification_en.py`
- `citation_verification_zh.py`
- `contribution_check.py`
- `results_validation_check.py`
- `reviewer_audit_check.py`
- `structured_review.py`
- `latex_guard.py`
- `word_guard.py`
- `section_economy_check.py`

Historical source names may also appear in migration compatibility code and
the project changelog. Those references do not create a live dependency.

## PLOS source excerpts

`evals/novelty-regression/sources/plos-*.txt` contains short abstract excerpts
from twelve PLOS ONE articles distributed under Creative Commons Attribution
4.0 International: <https://creativecommons.org/licenses/by/4.0/>.
Each file preserves the authors, article citation, DOI, publisher link,
license link and excerpt locator. Extraction and publisher verification
records are in `evals/novelty-regression/sources/provenance.json`.
Candidate claims and control annotations are constructed evaluation material,
separate from the authors' findings.
