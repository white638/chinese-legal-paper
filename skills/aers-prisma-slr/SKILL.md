---
name: aers-prisma-slr
description: "Use for systematic-review eligibility, search and screening records, PRISMA counts, extraction, appraisal or checklist audits. Excludes meta-analysis and statistical pooling."
---

# PRISMA 2020 systematic review support

## {{HOST_DISPLAY_NAME}} integration

When called by `empirical-research` or `cnki-paper`, execute only the delegated
method action. Read `empirical-research/references/{{METHOD_ADAPTER_FILE}}` and,
when applicable, `cnki-paper/references/{{SUBSKILL_ADAPTER_FILE}}` for the host
contract. The parent's stage, allowed writes, accepted sources, research question,
method choices and requested deliverables govern this action.

Reuse the supplied protocol, source records and analytic decisions. Ask only for
missing information that changes the requested analysis. Deliver the requested
screening log, extraction table, coding record, theme map or quality audit in the
parent's declared directory. A complete paper or Word file is produced only when
explicitly requested by the parent contract or user. Method outputs do not advance
the parent stage or replace its receipts. Use its canonical design and execution
records instead of creating a second authority.

Citation and prose style follow the current user and target-journal contract.
Resolve document and citation tools through the active host; only load a renderer
when the requested output requires it. Parent manuscript production follows its
ProsePacket and output QA contracts. Preserve source locators, raw excerpts,
missing values, negative findings and unresolved VERIFY status; do not invent
counts, sources, participants or completed checks.

## Read for the current action

- `references/prisma-2020-checklist.md`: PRISMA reporting items for the current section or audit.
- `references/flow-diagram.md`: flow diagrams built from verified identification and screening counts.

For an explicitly requested standalone review or write-up, use the relevant
sections of `references/standalone-workflow.md`. Its interview and document
examples do not create additional parent-workflow requirements.

Reconcile records, reports and studies separately; bind inclusion/exclusion
reasons and each PRISMA count to actual logs. PRISMA is a reporting guideline,
not proof of methodological quality or permission to infer missing results.

Author: Chuah Kee Man. Source, adaptation and license: `PROVENANCE.md` and `LICENSE`.
