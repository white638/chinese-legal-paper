# Chinese Translation Package

Translation is an optional sub-action of `output`, not a separate state and
not a label applied to the English manuscript. Configure:

```json
{
  "output_language": "en",
  "translation_package": "zh",
  "translation_source": "package_sources/translation/full_paper.zh.md",
  "translation_coverage_source": "package_sources/translation/coverage.json"
}
```

`translation_source` must be a separately written, editable Chinese Markdown,
LaTeX, or DOCX file inside the workspace. `coverage.json` must use
`avereth-translation-coverage/v1`, have `status: confirmed`, bind the exact
audited-source and Chinese-source SHA-256 values, identify the actual reviewer,
and provide an exact `units` mapping. Every item names `kind` as `section`,
`table`, `figure`, `footnote`, or `appendix`, binds source and translation
anchors, and has `status: final`; the declared counts must exactly match both
documents' machine-extracted structural unit counts.

The output engine checks language, unresolved placeholders, DOI/URL plus the
configured numeric/author-year/footnote citation identities, and exact
structural coverage; renders
`translation_zh/paper.zh.docx`; creates
`render_qa/translation_preview.pdf`; runs the staged translation and Word
guards; and publishes everything only after all declared PDF targets have been
visually reviewed. Missing translation content is a blocker—rendering never
pretends to translate.

Use only the two-phase output protocol in `../workflow-playbook.md`. Never copy
files into `translation_zh/` manually or run a guard against durable output to
bypass the transaction.
