from __future__ import annotations

import unittest
from pathlib import Path

from avereth_core import cli
from avereth_core import workflow_registry as registry
from avereth_core.stages import stage_specs


LEGACY_CORE_RUNTIME_FILES = {
    "cnki-paper/SKILL.md",
    "cnki-paper/scripts/avereth.py",
    "cnki-paper/scripts/avereth_core/cli.py",
    "cnki-paper/scripts/avereth_core/stages.py",
    "cnki-paper/scripts/avereth_core/audit/run_all.py",
    "cnki-paper/scripts/avereth_core/build/run.py",
    "cnki-paper/scripts/avereth_core/output/run.py",
    "cnki-paper/scripts/avereth_core/output/policy.py",
    "cnki-paper/scripts/avereth_core/output/render.py",
    "cnki-paper/scripts/avereth_core/output/guards.py",
    "cnki-paper/scripts/avereth_core/output/translation.py",
    "cnki-paper/scripts/avereth_core/output/submission.py",
    "cnki-paper/scripts/avereth_core/output/response.py",
    "cnki-paper/scripts/codex_cnki_gate.py",
    "cnki-paper/scripts/problem_orientation_check.py",
    "cnki-paper/references/problem-led-research.md",
    "cnki-paper/references/schemas/avereth-workflow-config-v1.schema.json",
}
NEW_CORE_RUNTIME_FILES = {
    "cnki-paper/scripts/avereth_core/infrastructure/legal_domain.py",
    "cnki-paper/scripts/commonplace_bank.py",
    "cnki-paper/scripts/commonplace_retrieve.py",
    "cnki-paper/scripts/commonplace_overlap_check.py",
    "cnki-paper/scripts/commonplace_writing.py",
    "cnki-paper/references/commonplace-writing.md",
    "cnki-paper/scripts/avereth_core/workflow_registry.py",
    "cnki-paper/scripts/avereth_core/scientific_runtime.py",
    "cnki-paper/scripts/avereth_core/infrastructure/locks.py",
    "cnki-paper/scripts/avereth_core/infrastructure/integration_contracts.py",
    "cnki-paper/scripts/avereth_core/gates/integration_gate.py",
    "cnki-paper/scripts/avereth_core/application/plan_service.py",
    "cnki-paper/scripts/avereth_core/application/protocol_compiler.py",
    "cnki-paper/scripts/avereth_core/build/manuscript.py",
    "cnki-paper/scripts/avereth_core/build/manuscript_compiler.py",
    "cnki-paper/references/engine/manuscript-compiler.md",
    "cnki-paper/references/manuscript-profiles/empirical-social-science-v1.json",
    "cnki-paper/references/manuscript-profiles/humanities-argument-v1.json",
    "cnki-paper/references/cn-journal-conventions.md",
    "cnki-paper/references/primary-source-citation.md",
    "cnki-paper/references/schemas/avereth-manuscript-contract-v1.schema.json",
    "cnki-paper/references/schemas/avereth-manuscript-ir-v1.schema.json",
    "cnki-paper/references/schemas/avereth-manuscript-rebuild-proof-v1.schema.json",
    "cnki-paper/scripts/prose_packet.py",
}
NEW_RESEARCH_RUNTIME_FILES = {
    "cnki-paper/scripts/citation_edges.py",
    "cnki-paper/references/research-material-feasibility.md",
    "cnki-paper/references/source-channels-cn.md",
    "cnki-paper/scripts/research_decision.py",
    "cnki-paper/scripts/topic_reasoning_check.py",
    "cnki-paper/scripts/topic_packet.py",
    "cnki-paper/scripts/taste_cards.py",
    "cnki-paper/scripts/taste_judge.py",
    "cnki-paper/scripts/taste_exemplars.py",
    "cnki-paper/references/taste/branch-taste-cards.json",
    "cnki-paper/references/taste-judgement.md",
    "cnki-paper/scripts/research_quality_check.py",
    "cnki-paper/references/schemas/cnki-research-decision-v1.schema.json",
    "cnki-paper/references/schemas/avereth-topic-packet-v1.schema.json",
    "cnki-paper/references/schemas/cnki-acquisition-v3.schema.json",
    "cnki-paper/references/schemas/avereth-exa-run-v1.schema.json",
    "cnki-paper/references/schemas/avereth-exa-manifest-v1.schema.json",
    "cnki-paper/references/schemas/avereth-zotero-snapshot-v1.schema.json",
    "cnki-paper/references/integrations/exa-zotero-integration.md",
    "cnki-paper/scripts/research_materials.py",
    "cnki-paper/scripts/research_feasibility.py",
    "cnki-paper/references/schemas/avereth-research-material-registry-v1.schema.json",
    "cnki-paper/references/schemas/avereth-research-feasibility-v1.schema.json",
}
LEGACY_RESEARCH_RUNTIME_FILES = {
    "cnki-paper/scripts/cnki_acquisition.py",
    "cnki-paper/scripts/literature_analysis.py",
    "cnki-paper/scripts/research_gap_diagnosis.py",
    "cnki-paper/scripts/literature_sufficiency.py",
    "cnki-paper/references/critical-reading-and-synthesis.md",
    "cnki-paper/references/research-gap-diagnosis.md",
    "cnki-paper/references/literature-sufficiency.md",
    "cnki-paper/references/schemas/cnki-acquisition-v2.schema.json",
    "cnki-paper/references/schemas/cnki-literature-analysis-v2.schema.json",
}
LEGACY_REVISION_RUNTIME_FILES = {
    "cnki-paper/scripts/revision_contract.py",
    "cnki-paper/scripts/literature_analysis.py",
    "cnki-paper/scripts/literature_sufficiency.py",
    "cnki-paper/references/schemas/cnki-literature-analysis-v2.schema.json",
    "cnki-paper/references/schemas/cnki-manuscript-revision-v1.schema.json",
    "cnki-paper/references/controlled-revision.md",
}
NEW_REVISION_RUNTIME_FILES = {
    "cnki-paper/scripts/citation_edges.py",
    "cnki-paper/references/schemas/cnki-manuscript-revision-v2.schema.json",
    "cnki-paper/references/schemas/avereth-revision-impact-v1.schema.json",
}
LEGACY_METHOD_RUNTIME_FILES = {
    "cnki-paper/scripts/research_design.py",
    "cnki-paper/references/schemas/cnki-research-design-v3.schema.json",
    "empirical-research/scripts/method_execution.py",
    "empirical-research/references/method-adapter-registry.json",
    "empirical-research/references/schemas/cnki-method-execution-v2.schema.json",
}
NEW_METHOD_RUNTIME_FILES = {
    "cnki-paper/scripts/research_design_v2.py",
    "cnki-paper/scripts/research_design_v3.py",
    "cnki-paper/references/schemas/cnki-research-design-v2.schema.json",
    "empirical-research/scripts/method_contract_loader.py",
    "empirical-research/scripts/validate_method_artifacts.py",
    "empirical-research/scripts/validate_measurement.py",
    "empirical-research/scripts/migrate_method_contracts.py",
    "empirical-research/scripts/repro_pack.py",
    "empirical-research/scripts/researcher_dispatch.py",
    "empirical-research/scripts/validators/__init__.py",
    "empirical-research/scripts/validators/common.py",
    "cnki-paper/scripts/research_design_v4.py",
    "cnki-paper/references/schemas/cnki-research-design-v4.schema.json",
    "empirical-research/references/schemas/cnki-method-execution-v3.schema.json",
    "empirical-research/references/schemas/method-operation-v1.schema.json",
    "empirical-research/references/schemas/failure-taxonomy-v1.json",
    "empirical-research/references/operation-profiles/case-study-v1.json",
    "empirical-research/references/operation-profiles/comparative-v1.json",
    "empirical-research/references/operation-profiles/computational-v1.json",
    "empirical-research/references/operation-profiles/conceptual-v1.json",
    "empirical-research/references/operation-profiles/congruence-analysis-v1.json",
    "empirical-research/references/operation-profiles/content-analysis-v1.json",
    "empirical-research/references/operation-profiles/discourse-analysis-v1.json",
    "empirical-research/references/operation-profiles/experiment-v1.json",
    "empirical-research/references/operation-profiles/grounded-theory-v1.json",
    "empirical-research/references/operation-profiles/historical-v1.json",
    "empirical-research/references/operation-profiles/interpretive-v1.json",
    "empirical-research/references/operation-profiles/normative-v1.json",
    "empirical-research/references/operation-profiles/process-tracing-v1.json",
    "empirical-research/references/operation-profiles/qca-v1.json",
    "empirical-research/references/operation-profiles/quantitative-v1.json",
    "empirical-research/references/operation-profiles/review-v1.json",
    "empirical-research/references/operation-profiles/social-network-v1.json",
    "empirical-research/references/operation-profiles/survey-v1.json",
    "empirical-research/references/operation-profiles/text-as-data-v1.json",
    "cnki-paper/scripts/avereth_core/build/exhibit_map.py",
    "empirical-research/references/schemas/avereth-exhibit-spec-v1.schema.json",
    "empirical-research/references/schemas/avereth-exhibit-data-v1.schema.json",
    "empirical-research/references/schemas/avereth-exhibit-renderer-environment-v1.schema.json",
    "empirical-research/references/schemas/avereth-exhibit-render-log-v1.schema.json",
    "empirical-research/references/exhibits/exhibit-contract.md",
    "empirical-research/references/exhibits/style-profiles/cn-social-science.json",
    "empirical-research/references/exhibits/style-profiles/international-polisci-econ.json",
    "empirical-research/references/exhibits/recipes/coefficient-forest.json",
    "empirical-research/references/exhibits/recipes/event-study.json",
    "empirical-research/references/exhibits/recipes/marginal-effects.json",
    "empirical-research/references/exhibits/recipes/predicted-probability.json",
    "empirical-research/references/exhibits/recipes/trend-or-binscatter.json",
    "empirical-research/references/exhibits/recipes/regression-or-balance-table.json",
    "empirical-research/scripts/exhibits/__init__.py",
    "empirical-research/scripts/exhibits/contract.py",
    "empirical-research/scripts/exhibits/exhibit.py",
    "empirical-research/scripts/exhibits/figure_map.py",
    "empirical-research/scripts/exhibits/render_bundle.py",
    "empirical-research/scripts/exhibits/smoke.py",
    "empirical-research/scripts/exhibits/table_emit.py",
    "empirical-research/scripts/exhibits/backends/r/render_exhibit.R",
}
LEGACY_INTERNATIONAL_RUNTIME_FILES = {
    "intl-search/scripts/openalex_search.py",
    "intl-search/scripts/openalex_snowball.py",
    "intl-search/scripts/s2_search.py",
    "intl-search/scripts/scholar_search.py",
    "intl-export/scripts/doi_export.py",
    "intl-search/scripts/resource_guard.py",
}
LEGACY_AUDIT_RUNTIME_FILES = {
    "cnki-paper/scripts/avereth_core/tools/citation_integrity_audit.py",
    "cnki-paper/scripts/avereth_core/tools/_engine_utils.py",
    "cnki-paper/scripts/avereth_core/tools/citation_bank_check.py",
    "cnki-paper/scripts/avereth_core/tools/citation_quality_audit.py",
    "cnki-paper/scripts/avereth_core/tools/contribution_check.py",
    "cnki-paper/scripts/avereth_core/tools/reviewer_audit_check.py",
    "cnki-paper/scripts/avereth_core/tools/structured_review.py",
}
NEW_AUDIT_RUNTIME_FILES = {
    "cnki-paper/scripts/avereth_core/tools/__init__.py",
    "cnki-paper/scripts/avereth_core/tools/review_lifecycle.py",
    "cnki-paper/references/schemas/cnki-review-assurance-v2.schema.json",
    "cnki-paper/references/schemas/avereth-review-findings-v2.schema.json",
    "cnki-paper/references/schemas/avereth-review-resolution-v1.schema.json",
    "cnki-paper/references/schemas/avereth-review-findings-v3.schema.json",
    "cnki-paper/references/schemas/avereth-review-resolution-v2.schema.json",
    "cnki-paper/references/schemas/avereth-review-cycle-v1.schema.json",
}
LEGACY_GLOBAL_RUNTIME_FILES = (
    LEGACY_CORE_RUNTIME_FILES
    | LEGACY_RESEARCH_RUNTIME_FILES
    | LEGACY_REVISION_RUNTIME_FILES
    | LEGACY_METHOD_RUNTIME_FILES
    | LEGACY_INTERNATIONAL_RUNTIME_FILES
    | LEGACY_AUDIT_RUNTIME_FILES
    | {
        "cnki-paper/scripts/avereth_core/output/word_render.ps1",
        "cnki-paper/scripts/avereth_core/tools/word_guard.py",
        "cnki-paper/scripts/avereth_core/tools/results_validation_check.py",
        "cnki-paper/scripts/research_design_v2.py",
        "cnki-paper/references/schemas/cnki-research-design-v2.schema.json",
        "empirical-research/references/schemas/cnki-method-execution-v1.schema.json",
        "intl-search/references/scholar-browser.md",
        "cnki-paper/scripts/dialogic_argument_check.py",
        "cnki-paper/scripts/academic_prose_check.py",
        "cnki-paper/references/dialogic-argument.md",
        "cnki-paper/references/academic-prose.md",
        "cnki-paper/references/anti-defensive-writing.md",
        "cnki-paper/references/schemas/cnki-review-assurance-v1.schema.json",
        "page-evidence/scripts/page_evidence_audit.py",
    }
) - {"cnki-paper/SKILL.md"}


def legacy_doctor_projection(
    config: dict[str, object],
    revision_contract: dict[str, object] | None = None,
) -> tuple[set[str], set[str]]:
    """Frozen copy of the v6.0 profile-aware dependency contract."""

    profile = str(config["task_profile"])
    track = str(config.get("publication_track") or "cnki-cn")
    revision_from = str((revision_contract or {}).get("earliest_reopen_stage") or "")
    revision_needs_research = profile == "manuscript_revision" and revision_from == "research"
    revision_needs_methods = profile == "manuscript_revision" and revision_from in {
        "research", "design", "execution",
    }
    acquisition_needed = profile != "manuscript_audit" and (
        profile != "manuscript_revision" or revision_needs_research
    )
    skills = {"cnki-paper"}
    if acquisition_needed and track in {"cnki-cn", "mixed"}:
        skills.update(registry.CNKI_SEARCH_SKILLS)
    if acquisition_needed and track in {"international-ssci", "mixed"}:
        skills.update(registry.INTERNATIONAL_SEARCH_SKILLS)
    if profile in {"full_paper", "research_design"} or revision_needs_methods:
        skills.add("empirical-research")
    page_evidence = bool(config.get("page_evidence_required"))
    if page_evidence and profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        skills.add("page-evidence")

    files = set(LEGACY_CORE_RUNTIME_FILES)
    if acquisition_needed:
        files.update(LEGACY_RESEARCH_RUNTIME_FILES)
        files.update(NEW_RESEARCH_RUNTIME_FILES)
    if profile == "manuscript_revision":
        files.update(LEGACY_REVISION_RUNTIME_FILES)
    if profile in {"full_paper", "research_design"} or revision_needs_methods:
        files.update(LEGACY_METHOD_RUNTIME_FILES)
        files.update(NEW_METHOD_RUNTIME_FILES)
    if acquisition_needed and track in {"international-ssci", "mixed"}:
        files.update(LEGACY_INTERNATIONAL_RUNTIME_FILES)
    word_requested = (
        str(config.get("word_output") or "docx") != "none"
        or str(config.get("translation_package") or "none").lower() == "zh"
    )
    if word_requested and profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        files.update({
            "cnki-paper/scripts/avereth_core/tools/word_guard.py",
            "cnki-paper/scripts/avereth_core/output/word_render.ps1",
        })
    if profile in {"full_paper", "manuscript_audit", "manuscript_revision"}:
        files.update(LEGACY_AUDIT_RUNTIME_FILES)
        if str(config.get("scene") or "").lower() in {"journal", "conference", "competition"}:
            files.add("cnki-paper/scripts/avereth_core/tools/results_validation_check.py")
    if profile in {"full_paper", "manuscript_revision"}:
        canonical = Path(str(config.get("canonical_manuscript") or "final_paper/main.tex"))
        if canonical.suffix.lower() == ".tex":
            files.add("cnki-paper/scripts/avereth_core/tools/latex_guard.py")
            if config.get("max_sections") is not None:
                files.add("cnki-paper/scripts/avereth_core/tools/section_economy_check.py")
        if word_requested:
            files.add("cnki-paper/scripts/avereth_core/tools/word_guard.py")
    if page_evidence:
        files.add("page-evidence/scripts/page_evidence_audit.py")
    return skills, files


class WorkflowRegistryTests(unittest.TestCase):
    def test_public_stage_projection_matches_v60_exactly(self) -> None:
        expected = {
            "intake": ["workflow_config.json", "problem_orientation.md"],
            "acquisition": ["reference_materials/literature_registry.json", "reference_materials/research_material_registry.json", "reference_materials/source_index.md"],
            "research": ["research_dossier.md", "exemplar_learning_dossier.md", "style_profile.md", "sota_gap_map.md", "literature_analysis.json", "motivation_options_after_research.md", "citation_support_bank.md", "research_decision.json", "research_feasibility.json", "novelty_clearance_check.md"],
            "design": ["research_design.json", "knowledge_design_matrix.md", "concept_register.md", "claim_evidence_scope_matrix.md", "method_route_matrix.md", "research_integrity_check.md", "terminology_register.md"],
            "execution": ["method_execution.json", "execution_record.md", "results_validation.md", "confirmed_contribution.md"],
            "build": ["dialogic_argument_map.md", "section_blueprints.md", "writing_rationale_matrix.md", "evidence_bank.md", "academic_prose_audit.md", "final_paper/main.tex", "original_logic_map.md", "rewrite_matrix.md", "logic_transfer_audit.md"],
            "audit": ["artifact_check.md", "integrity_audit.md", "dialogic_argument_check.md", "academic_prose_check.md", "citation_bank_check.md", "citation_quality_audit.md", "citation_integrity_audit.md", "contribution_check.md", "results_validation_check.md", "review_findings.json", "review_resolution.json", "structured_review.md", "reviewer_audit.md", "revision_plan.md", "reviewer_audit_check.md", "review_assurance.json"],
            "output": ["final_artifact_manifest.md"],
        }
        self.assertEqual(registry.STAGE_ORDER, tuple(expected))
        for stage, paths in expected.items():
            config = {"scene": "journal"} if stage == "audit" else None
            self.assertEqual(paths, [spec.path for spec in stage_specs(stage, config)])
        self.assertNotIn(
            "results_validation_check.md",
            [spec.path for spec in stage_specs("audit")],
        )

    def test_receipt_and_rebuildable_projections_preserve_scientific_authorities(self) -> None:
        expected_receipt = {
            "reference_materials/legal_sources.json", "legal_analysis.json", "legal_citations.json", "legal_review.json",
            ".avereth-commonplace/bank.json", ".avereth-prose/commonplace_runs.json",
            "workflow_config.json", "migration/local_engine_v6/acquisition_handoff.json", "workflow_config.md", "revision_contract.json", "revision_impact.json", "problem_orientation.md", "problem_orientation_check.md", "source_map.md", "citation_support_bank.md", "reference_materials/integrations/exa_runs/manifest.json", "reference_materials/integrations/zotero_snapshot.json", "research_dossier.md", "exemplar_learning_dossier.md", "sota_gap_map.md", "topic_induction_deduction_matrix.md", "style_profile.md", "literature_analysis.json", "critical_reading_report.md", "literature_synthesis_matrix.md", "literature_analysis_check.md", "motivation_options_after_research.md", "research_decision.json", "confirmed_motivation.md", "novelty_clearance_check.md", "research_design.json", "knowledge_design_matrix.md", "concept_register.md", "claim_evidence_scope_matrix.md", "method_route_matrix.md", "research_integrity_check.md", "case_design_matrix.md", "operationalization_matrix.md", "execution_protocol.md", "next_action.md", "terminology_register.md", "method_execution.json", "execution_record.md", "method_pilot_report.md", "action_result_trace.md", "claim_disposition_report.md", "results_validation.md", "results_validation_check.md", "confirmed_contribution.md", "contribution_check.md", "dialogic_argument_map.md", "dialogic_argument_check.md", "section_blueprints.md", "writing_rationale_matrix.md", "promise_delivery_matrix.md", "claim_lifecycle_matrix.md", "reader_state_report.md", "cross_section_sync_report.md", "manuscript_trace_manifest.json", "evidence_bank.md", "academic_prose_audit.md", "academic_prose_check.md", "source_inventory.md", "figure_asset_map.md", "claim_register.md", "original_logic_map.md", "rewrite_matrix.md", "logic_transfer_audit.md", "build_run.json", "integrity_audit.md", "artifact_check.md", "citation_bank_check.md", "citation_quality_audit.md", "citation_integrity_audit.md", "review_findings.json", "review_resolution.json", "structured_review.md", "reviewer_audit.md", "revision_plan.md", "reviewer_audit_check.md", "audit_run.json", "review_assurance.json", "final_artifact_manifest.md", "final_artifact_manifest.json", "output_run.json", "render_qa.json", "output_artifact_check.md", "word_report.md", "word_report.zh.md", "latex_report.md", "latex_guard.md", "section_economy_check.md", "translation_guard.md", "translation_word_report.md", "submission_check.md", "respond_check.md", "references.bib",
            registry.LEGACY_CONFIG_REL.as_posix(), registry.LEGACY_CONFIG_MD_REL.as_posix(),
        }
        expected_views = {
            ".avereth-commonplace/bank.json", ".avereth-commonplace/disciplinary_phraseology.json", ".avereth-prose/commonplace_runs.json",
            "workflow_config.md", "source_map.md", "reference_materials/source_index.md", "citation_support_bank.md", "critical_reading_report.md", "literature_synthesis_matrix.md", "literature_analysis_check.md", "topic_reasoning_check.md", "novelty_clearance_check.md", "knowledge_design_matrix.md", "concept_register.md", "claim_evidence_scope_matrix.md", "method_route_matrix.md", "research_integrity_check.md", "case_design_matrix.md", "operationalization_matrix.md", "execution_protocol.md", "next_action.md", "research_design_check.json", "research_design_check.md", "execution_record.md", "method_pilot_report.md", "action_result_trace.md", "claim_disposition_report.md", "results_validation.md", "revision_impact.json", "section_blueprints.md", "writing_rationale_matrix.md", "promise_delivery_matrix.md", "claim_lifecycle_matrix.md", "reader_state_report.md", "cross_section_sync_report.md", "structured_review.md", "reviewer_audit.md", "revision_plan.md", "taste_judgement.md",
            registry.LEGACY_CONFIG_MD_REL.as_posix(),
        }
        self.assertEqual(expected_receipt, set(registry.RECEIPT_BOUND_ROOT_PATHS))
        self.assertEqual(expected_views, set(registry.REBUILDABLE_VIEW_PATHS))
        self.assertIn("manuscript_trace_manifest.json", registry.RECEIPT_BOUND_ROOT_PATHS)
        with self.assertRaises(KeyError):
            registry.artifact_definition("reference_materials/integrations/data_asset_snapshot.json")

    def test_migration_and_schema_projections_match_v60_exactly(self) -> None:
        expected_contracts = {
            "workflow_config.json", "problem_orientation.md", "reference_materials/literature_registry.json", "reference_materials/research_material_registry.json", "literature_analysis.json", "research_decision.json", "research_feasibility.json", "confirmed_motivation.md", "research_design.json", "method_execution.json", "confirmed_contribution.md", "revision_contract.json", "review_findings.json", "review_resolution.json", "review_assurance.json",
            registry.LEGACY_CONFIG_REL.as_posix(),
            registry.LEGACY_AUDIT_REL.as_posix(), registry.LEGACY_AUDIT_MD_REL.as_posix(),
            registry.LEGACY_OUTPUT_REL.as_posix(), registry.LEGACY_OUTPUT_MD_REL.as_posix(),
            registry.LEGACY_STATUS_REL.as_posix(), registry.LEGACY_STATUS_MD_REL.as_posix(),
        }
        expected_schemas = {
            "reference_materials/legal_sources.json": {"legal-sources/v1"},
            "legal_analysis.json": {"legal-analysis/v1"},
            "legal_citations.json": {"legal-citations/v1"},
            "legal_review.json": {"legal-review/v1"},
            "reference_materials/literature_registry.json": {registry.ACQUISITION_SCHEMA_V1, registry.ACQUISITION_SCHEMA_V2, registry.ACQUISITION_SCHEMA_V3},
            "literature_analysis.json": {registry.LITERATURE_ANALYSIS_SCHEMA_V1, registry.LITERATURE_ANALYSIS_SCHEMA_V2},
            "research_decision.json": {registry.RESEARCH_DECISION_SCHEMA_V1},
            "reference_materials/research_material_registry.json": {registry.RESEARCH_MATERIAL_SCHEMA_V1},
            "research_feasibility.json": {registry.RESEARCH_FEASIBILITY_SCHEMA_V1},
            "research_design.json": {
                registry.DESIGN_SCHEMA_V1,
                registry.DESIGN_SCHEMA_V2,
                registry.DESIGN_SCHEMA_V3,
                registry.DESIGN_SCHEMA_V4,
            },
            "method_execution.json": {
                registry.EXECUTION_SCHEMA_V1,
                registry.EXECUTION_SCHEMA_V2,
                registry.EXECUTION_SCHEMA_V3,
            },
            "revision_contract.json": {registry.REVISION_CONTRACT_SCHEMA_V1, registry.REVISION_CONTRACT_SCHEMA_V2},
            "review_findings.json": {registry.REVIEW_FINDINGS_SCHEMA_V2, registry.REVIEW_FINDINGS_SCHEMA_V3},
            "review_resolution.json": {registry.REVIEW_RESOLUTION_SCHEMA_V1, registry.REVIEW_RESOLUTION_SCHEMA_V2},
            "review_assurance.json": {registry.REVIEW_ASSURANCE_SCHEMA_V1, registry.REVIEW_ASSURANCE_SCHEMA_V2},
        }
        expected_contract_order = (
            "workflow_config.json", registry.LEGACY_CONFIG_REL.as_posix(), "problem_orientation.md",
            "reference_materials/literature_registry.json", "reference_materials/research_material_registry.json", "literature_analysis.json", "research_decision.json", "research_feasibility.json", "confirmed_motivation.md",
            "research_design.json", "method_execution.json", "confirmed_contribution.md", "revision_contract.json", "review_findings.json", "review_resolution.json",
            "review_assurance.json", registry.LEGACY_AUDIT_REL.as_posix(), registry.LEGACY_AUDIT_MD_REL.as_posix(),
            registry.LEGACY_OUTPUT_REL.as_posix(), registry.LEGACY_OUTPUT_MD_REL.as_posix(),
            registry.LEGACY_STATUS_REL.as_posix(), registry.LEGACY_STATUS_MD_REL.as_posix(),
        )
        self.assertEqual(expected_contracts, set(registry.MIGRATION_CONTRACT_PATHS))
        self.assertEqual(expected_contract_order, registry.MIGRATION_CONTRACT_PATHS)
        actual_schemas = {path.as_posix(): values for path, values in registry.migration_schema_allowlist().items()}
        self.assertEqual(expected_schemas, actual_schemas)

    def test_all_machine_lists_are_projections_of_unique_rows(self) -> None:
        self.assertEqual([], registry.registry_issues())
        self.assertEqual(
            registry.RECEIPT_BOUND_ROOT_PATHS,
            frozenset(item.path for item in registry.ARTIFACT_DEFINITIONS if item.receipt_bindings and item.receipt_root),
        )
        self.assertEqual(
            registry.REBUILDABLE_VIEW_PATHS,
            frozenset(item.path for item in registry.ARTIFACT_DEFINITIONS if item.rebuildable_view),
        )
        self.assertEqual(
            set(registry.MIGRATION_CONTRACT_PATHS),
            {item.path for item in registry.ARTIFACT_DEFINITIONS if item.migration_contract},
        )
        self.assertEqual(
            {path.as_posix() for path in registry.migration_schema_allowlist()},
            {item.path for item in registry.ARTIFACT_DEFINITIONS if item.allowed_schemas},
        )
        orientation_check = registry.artifact_definition("problem_orientation_check.md")
        self.assertEqual("intake", orientation_check.owner_stage)

    def test_five_semantic_phases_are_a_read_only_projection_of_eight_stages(self) -> None:
        self.assertEqual(
            {
                "intake": "scope",
                "acquisition": "evidence",
                "research": "evidence",
                "design": "analysis",
                "execution": "analysis",
                "build": "manuscript",
                "audit": "verify",
                "output": "verify",
            },
            dict(registry.STAGE_TO_SEMANTIC_PHASE),
        )
        self.assertEqual(
            registry.SEMANTIC_PHASE_ORDER,
            tuple(dict.fromkeys(registry.STAGE_TO_SEMANTIC_PHASE.values())),
        )

    def test_retired_data_asset_layer_is_not_a_default_runtime_dependency(self) -> None:
        retired = {
            "cnki-paper/references/data-asset-awareness.md",
            "cnki-paper/scripts/data_catalog.py",
            "cnki-paper/scripts/data_matcher.py",
            "cnki-paper/references/data-catalog/public-opportunities-v1.json",
        }
        self.assertTrue(retired.isdisjoint(registry.GLOBAL_RUNTIME_FILES))
        self.assertTrue(retired.isdisjoint(registry.runtime_files_for({"research"})))
        self.assertIn(
            "cnki-paper/scripts/optional/quantitative_data/quantitative_data_check.py",
            registry.runtime_files_for({"quantitative-data"}),
        )

        base = {
            "task_profile": "research_design",
            "publication_track": "international-ssci",
            "word_output": "none",
        }
        _skills, ordinary_files = cli.doctor_requirements(base)
        self.assertNotIn(
            "cnki-paper/scripts/optional/quantitative_data/quantitative_data_check.py",
            ordinary_files,
        )
        _skills, quantitative_files = cli.doctor_requirements(
            {**base, "method_family": "quantitative"}
        )
        self.assertIn(
            "cnki-paper/scripts/optional/quantitative_data/quantitative_data_check.py",
            quantitative_files,
        )

    def test_global_doctor_inventory_is_registered_and_exists(self) -> None:
        skills_dir = Path(__file__).resolve().parents[3]
        self.assertEqual(len(registry.GLOBAL_RUNTIME_FILES), len(set(registry.GLOBAL_RUNTIME_FILES)))
        self.assertEqual(
            (
                LEGACY_GLOBAL_RUNTIME_FILES
                | NEW_CORE_RUNTIME_FILES
                | NEW_RESEARCH_RUNTIME_FILES
                | NEW_METHOD_RUNTIME_FILES
                | NEW_AUDIT_RUNTIME_FILES
                | NEW_REVISION_RUNTIME_FILES
            ),
            set(registry.GLOBAL_RUNTIME_FILES),
        )
        self.assertTrue(all((skills_dir / path).is_file() for path in registry.GLOBAL_RUNTIME_FILES))
        self.assertIn("cnki-paper/scripts/avereth_core/workflow_registry.py", registry.GLOBAL_RUNTIME_FILES)

    def test_profile_doctor_projections_match_v60_except_registered_core_modules(self) -> None:
        cases = {
            "full-paper-cnki": (
                {"task_profile": "full_paper", "publication_track": "cnki-cn", "word_output": "none", "canonical_manuscript": "final_paper/main.tex"},
                None,
            ),
            "full-paper-mixed-word-page": (
                {"task_profile": "full_paper", "publication_track": "mixed", "word_output": "docx", "page_evidence_required": True, "scene": "journal", "canonical_manuscript": "final_paper/main.tex", "max_sections": 8},
                None,
            ),
            "topic-selection": (
                {"task_profile": "topic_selection", "publication_track": "cnki-cn", "word_output": "none"},
                None,
            ),
            "research-design": (
                {"task_profile": "research_design", "publication_track": "international-ssci", "word_output": "none"},
                None,
            ),
            "manuscript-audit": (
                {"task_profile": "manuscript_audit", "publication_track": "mixed", "word_output": "docx", "page_evidence_required": True, "scene": "conference"},
                None,
            ),
            "revision-from-research": (
                {"task_profile": "manuscript_revision", "publication_track": "mixed", "word_output": "none", "canonical_manuscript": "final_paper/main.md"},
                {"earliest_reopen_stage": "research"},
            ),
            "revision-from-build": (
                {"task_profile": "manuscript_revision", "publication_track": "cnki-cn", "word_output": "docx", "canonical_manuscript": "final_paper/main.docx"},
                {"earliest_reopen_stage": "build"},
            ),
        }
        for label, (config, revision) in cases.items():
            with self.subTest(case=label):
                legacy_skills, legacy_files = legacy_doctor_projection(config, revision)
                actual_skills, actual_files = cli.doctor_requirements(config, revision)
                self.assertEqual(legacy_skills, set(actual_skills))
                expected_files = legacy_files | NEW_CORE_RUNTIME_FILES
                if str(config["task_profile"]) in {"full_paper", "manuscript_audit", "manuscript_revision"}:
                    expected_files |= NEW_AUDIT_RUNTIME_FILES
                if str(config["task_profile"]) == "manuscript_revision":
                    expected_files |= NEW_REVISION_RUNTIME_FILES
                self.assertEqual(expected_files, set(actual_files))

    def test_every_stage_reference_is_a_real_declared_skill_path(self) -> None:
        skills_dir = Path(__file__).resolve().parents[3]
        for stage in registry.STAGE_DEFINITIONS:
            for relative in stage.references:
                with self.subTest(stage=stage.key, reference=relative):
                    self.assertTrue((skills_dir / relative).is_file(), relative)
        for profile, references in registry.PROFILE_REFERENCE_PATHS.items():
            for relative in references:
                with self.subTest(profile=profile, reference=relative):
                    self.assertTrue((skills_dir / relative).is_file(), relative)


if __name__ == "__main__":
    unittest.main()
