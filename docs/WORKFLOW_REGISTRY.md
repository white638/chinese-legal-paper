# Workflow Registry (generated)

This file is generated from `avereth_core/workflow_registry.py`. Do not edit its tables by hand.

## Public stages

| Stage | Required base artifacts | Terminal profiles |
|---|---:|---|
| intake | 2 | — |
| acquisition | 3 | — |
| research | 10 | topic_selection |
| design | 7 | research_design |
| execution | 4 | — |
| build | 6 | — |
| audit | 16 | manuscript_audit |
| output | 1 | full_paper, manuscript_revision |

## Contract projections

- Artifact definitions: 117
- Global doctor runtime files: 172
- Schema-bearing migration contracts: 15

## Schema allow-list

| Artifact | Accepted schemas during migration |
|---|---|
| `legal_analysis.json` | legal-analysis/v1 |
| `legal_citations.json` | legal-citations/v1 |
| `legal_review.json` | legal-review/v1 |
| `literature_analysis.json` | cnki-literature-analysis/v1, cnki-literature-analysis/v2 |
| `method_execution.json` | cnki-method-execution/v1, cnki-method-execution/v2, cnki-method-execution/v3 |
| `reference_materials/legal_sources.json` | legal-sources/v1 |
| `reference_materials/literature_registry.json` | cnki-acquisition/v1, cnki-acquisition/v2, cnki-acquisition/v3 |
| `reference_materials/research_material_registry.json` | avereth-research-material-registry/v1 |
| `research_decision.json` | cnki-research-decision/v1 |
| `research_design.json` | cnki-research-design/v1, cnki-research-design/v2, cnki-research-design/v3, cnki-research-design/v4 |
| `research_feasibility.json` | avereth-research-feasibility/v1 |
| `review_assurance.json` | cnki-review-assurance/v1, cnki-review-assurance/v2 |
| `review_findings.json` | avereth-review-findings/v2, avereth-review-findings/v3 |
| `review_resolution.json` | avereth-review-resolution/v1, avereth-review-resolution/v2 |
| `revision_contract.json` | cnki-manuscript-revision/v1, cnki-manuscript-revision/v2 |
