# Venue-Configured Submission Package

Submission materials are an optional `output` sub-action. The engine does not
invent universal cover-letter, highlight-count, character-limit, paper-size,
or font rules. The target venue contract is the only package specification.

Configure:

```json
{
  "submission_package": "journal",
  "submission_source_dir": "package_sources/submission",
  "submission_contract": "package_sources/submission/contract.json",
  "submission_required_files": ["cover_letter.en.docx", "highlights.en.md"]
}
```

The contract must use `avereth-submission-contract/v1`, have
`status: confirmed`, name the same target as `workflow_config.json`, declare
`language` as `en`, `zh`, or `mixed`, identify the actual confirmer, and list
exactly the same required files. Every path stays inside the source directory;
missing, empty, extra-declared, or placeholder-bearing materials fail closed.
Every requested DOCX must be a valid editable OOXML package, pass the staged
Word structural/placeholder check, and produce its own PDF preview in the
render-QA target set. A filename or non-empty byte string is never sufficient.

During output, the engine stages the exact venue-declared materials together
with the current audited manuscript delivery, writes a package manifest and
guard report, and publishes them in the same transaction as the primary
deliveries. A Chinese translation request does not silently create Chinese
cover letters or highlights; those exist only when the venue contract requests
them.

Prepare source materials under `package_sources/submission/`. Do not write
directly to `submission_package/`; that directory is managed durable output.
