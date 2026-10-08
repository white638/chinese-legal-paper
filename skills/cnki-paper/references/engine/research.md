# Research Stage

This file is the local research protocol used by the single eight-stage controller.

## Purpose

Learn the target scene, index local references, study strong examples, map SOTA
gaps, and produce user-confirmable motivation options. Research must complete
before the user confirms the controlling motivation.

## Evidence Depth Rules

There is no universal literature quota. Select target-scene and field/SOTA
examples because they carry a real venue, comparison, theory, method,
counterargument, or boundary responsibility. Retrieval runs through the
`cnki-*` and `intl-search` skills and lands in `literature_registry.json`; the
controller computes the applicable dynamic venue baseline or task fallback
(`literature-sufficiency.md`) and rejects both under-reading and irrelevant
padding.

## Stage 1 — Index Local References

Create `paper_rewriting_output/reference_materials/source_index.md`:

| Source ID | Type | Title/Name | Origin/URL/Path | Why Included | Local File/Note | Used For |
|---|---|---|---|---|---|---|

Do not use a standalone reference-inventory writer. Register local materials in
`literature_registry.json` and rebuild this view from the single source truth:

```powershell
$Acq = Join-Path $AverethHome 'skills\cnki-paper\scripts\cnki_acquisition.py'
& $Python -X utf8 $Acq sync paper_rewriting_output
```

## Stage 2 — Three Parallel Specialist Sub-Agents

Launch all three simultaneously. Each agent gets only its own context.

### Agent A: Scene Analyst → `research_dossier.md`

Context: `scene`, `target_name`, `official_urls`, `source_index.md`, scene reference file.

Sections: Venue Requirements, Review Criteria, Accepted Paper Patterns, Constraints for This Paper.

### Agent B: Exemplar Learner → `exemplar_learning_dossier.md`

Context: `tier`, `source_index.md`, scene reference path.

Sections: Exemplar Inventory table, Structural Patterns, Rhetorical Patterns, Language Patterns.

### Agent C: SOTA Mapper → `sota_gap_map.md`

Context: `tier`, `source_index.md`, `user_motivation` (if set).

Table: Candidate Contribution | What SOTA Already Does | User Evidence | Real Gap | Claim Strength | Risk. Plus Gap Summary.

## Stage 3 — Merge

Produce `style_profile.md` and `motivation_options_after_research.md`. Stop for
user confirmation. Write `confirmed_motivation.md` only after the user chooses,
revises, or writes their own motivation.

When the task is routed through `cnki-paper`, every option must also have a
Dialogue Option Card with Response Target Type, Controlling Dispute/Unknown,
Position/Source IDs, Candidate Response, Strongest Countervoice, Who Cares,
So What, and Missing Voice. A response may address an explicit dispute, a
shared assumption, or a literature omission; never manufacture opposing camps
for rhetorical convenience.

## Required Outputs

- `reference_materials/source_index.md`
- `research_dossier.md`
- `exemplar_learning_dossier.md`
- `style_profile.md`
- `sota_gap_map.md`
- `motivation_options_after_research.md`
- `confirmed_motivation.md` (after user confirmation)
