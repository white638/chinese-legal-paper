"""Single typed registry for Avereth's public workflow contracts.

Every workspace artifact is declared exactly once.  Stage requirements,
receipt scope, rebuildable views, migration contracts and schema allow-lists
are projections of those rows; callers must not maintain parallel path lists.
The registry is declarative and performs no workspace I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Iterable, Mapping

from .config import (
    LEGACY_CONFIG_MD_REL,
    LEGACY_CONFIG_REL,
    WORKFLOW_CONFIG_MD_REL,
    WORKFLOW_CONFIG_REL,
)
from .models import ArtifactSpec
from .receipts import (
    LEGACY_AUDIT_MD_REL,
    LEGACY_AUDIT_REL,
    LEGACY_OUTPUT_MD_REL,
    LEGACY_OUTPUT_REL,
    LEGACY_STATUS_MD_REL,
    LEGACY_STATUS_REL,
)


STAGE_ORDER = (
    "intake",
    "acquisition",
    "research",
    "design",
    "execution",
    "build",
    "audit",
    "output",
)
SEMANTIC_PHASE_ORDER = (
    "scope",
    "evidence",
    "analysis",
    "manuscript",
    "verify",
)
LEGACY_STAGE_ALIASES = {
    "citation": "research",
    "motivation": "research",
    "contribution": "execution",
}
TASK_PROFILE_TERMINALS = {
    "full_paper": "output",
    "topic_selection": "research",
    "research_design": "design",
    "manuscript_audit": "audit",
    "manuscript_revision": "output",
}

ACQUISITION_SCHEMA_V1 = "cnki-acquisition/v1"
ACQUISITION_SCHEMA_V2 = "cnki-acquisition/v2"
ACQUISITION_SCHEMA_V3 = "cnki-acquisition/v3"
LITERATURE_ANALYSIS_SCHEMA_V1 = "cnki-literature-analysis/v1"
LITERATURE_ANALYSIS_SCHEMA_V2 = "cnki-literature-analysis/v2"
RESEARCH_DECISION_SCHEMA_V1 = "cnki-research-decision/v1"
RESEARCH_MATERIAL_SCHEMA_V1 = "avereth-research-material-registry/v1"
RESEARCH_FEASIBILITY_SCHEMA_V1 = "avereth-research-feasibility/v1"
DESIGN_SCHEMA_V1 = "cnki-research-design/v1"
DESIGN_SCHEMA_V2 = "cnki-research-design/v2"
DESIGN_SCHEMA_V3 = "cnki-research-design/v3"
DESIGN_SCHEMA_V4 = "cnki-research-design/v4"
EXECUTION_SCHEMA_V1 = "cnki-method-execution/v1"
EXECUTION_SCHEMA_V2 = "cnki-method-execution/v2"
EXECUTION_SCHEMA_V3 = "cnki-method-execution/v3"
REVISION_CONTRACT_SCHEMA_V1 = "cnki-manuscript-revision/v1"
REVISION_CONTRACT_SCHEMA_V2 = "cnki-manuscript-revision/v2"
REVISION_IMPACT_SCHEMA_V1 = "avereth-revision-impact/v1"
REVIEW_ASSURANCE_SCHEMA_V1 = "cnki-review-assurance/v1"
REVIEW_ASSURANCE_SCHEMA_V2 = "cnki-review-assurance/v2"
REVIEW_ASSURANCE_SCHEMA = REVIEW_ASSURANCE_SCHEMA_V2
REVIEW_FINDINGS_SCHEMA_V2 = "avereth-review-findings/v2"
REVIEW_FINDINGS_SCHEMA_V3 = "avereth-review-findings/v3"
REVIEW_RESOLUTION_SCHEMA_V1 = "avereth-review-resolution/v1"
REVIEW_RESOLUTION_SCHEMA_V2 = "avereth-review-resolution/v2"
ADAPTER_REGISTRY_SCHEMA = "cnki-method-adapter-registry/v3"

AUDIT_AND_OUTPUT = frozenset({"audit", "output"})
OUTPUT_ONLY = frozenset({"output"})


@dataclass(frozen=True)
class ArtifactDefinition:
    key: str
    path: str
    owner_stage: str
    writable_stages: frozenset[str] = frozenset()
    required_stages: frozenset[str] = frozenset()
    alternatives: tuple[str, ...] = ()
    authority: str = "supporting"
    description: str = ""
    report_must_pass: bool = False
    meaningful: bool = True
    receipt_bindings: frozenset[str] = frozenset()
    receipt_root: bool = False
    rebuildable_view: bool = False
    migration_contract: bool = False
    allowed_schemas: frozenset[str] = frozenset()
    variant: str = ""
    domain_profile: str = ""

    def as_spec(self) -> ArtifactSpec:
        return ArtifactSpec(
            self.path,
            self.alternatives,
            meaningful=self.meaningful,
            report_must_pass=self.report_must_pass,
            description=self.description,
        )


@dataclass(frozen=True)
class StageDefinition:
    key: str
    semantic_phase: str
    references: tuple[str, ...] = ()
    adapters: tuple[str, ...] = ()


def A(
    path: str | Path,
    owner: str,
    *,
    writable: Iterable[str] = (),
    required: Iterable[str] = (),
    alternatives: Iterable[str] = (),
    authority: str = "supporting",
    description: str = "",
    report: bool = False,
    bindings: frozenset[str] = frozenset(),
    receipt_root: bool | None = None,
    rebuildable: bool = False,
    migration: bool = False,
    schemas: Iterable[str] = (),
    variant: str = "",
    domain_profile: str = "",
) -> ArtifactDefinition:
    normalized = Path(path).as_posix()
    return ArtifactDefinition(
        key=normalized.replace("/", ".").replace("_", "-"),
        path=normalized,
        owner_stage=owner,
        writable_stages=frozenset(writable) or frozenset({owner}),
        required_stages=frozenset(required),
        alternatives=tuple(alternatives),
        authority=authority,
        description=description,
        report_must_pass=report,
        receipt_bindings=bindings,
        receipt_root=bool(bindings) if receipt_root is None else receipt_root,
        rebuildable_view=rebuildable,
        migration_contract=migration,
        allowed_schemas=frozenset(schemas),
        variant=variant,
        domain_profile=domain_profile,
    )


# One row per artifact.  Do not add a path to a second list elsewhere.
ARTIFACT_DEFINITIONS: tuple[ArtifactDefinition, ...] = (
    A("reference_materials/legal_sources.json", "acquisition", bindings=AUDIT_AND_OUTPUT, domain_profile="chinese-law-v1", authority="canonical", schemas={"legal-sources/v1"}),
    A("legal_analysis.json", "design", bindings=AUDIT_AND_OUTPUT, domain_profile="chinese-law-v1", authority="canonical", schemas={"legal-analysis/v1"}),
    A("legal_citations.json", "build", bindings=AUDIT_AND_OUTPUT, domain_profile="chinese-law-v1", authority="canonical", schemas={"legal-citations/v1"}),
    A("legal_review.json", "audit", bindings=AUDIT_AND_OUTPUT, domain_profile="chinese-law-v1", authority="canonical", schemas={"legal-review/v1"}),
    A(WORKFLOW_CONFIG_REL, "intake", required={"intake"}, alternatives={LEGACY_CONFIG_REL.as_posix()}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True),
    A(WORKFLOW_CONFIG_MD_REL, "intake", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A(LEGACY_CONFIG_REL, "intake", authority="legacy-config", bindings=AUDIT_AND_OUTPUT, migration=True),
    A(LEGACY_CONFIG_MD_REL, "intake", authority="legacy-config", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("migration/local_engine_v6/acquisition_handoff.json", "acquisition", authority="canonical", bindings=AUDIT_AND_OUTPUT),
    A("research_notes.md", "research", writable={"intake", "acquisition", "research", "design", "execution"}, authority="scratch", receipt_root=False, description="optional tentative reasoning; not evidence or Writer input"),
    A("problem_orientation.md", "intake", required={"intake"}, bindings=AUDIT_AND_OUTPUT, migration=True),
    A("problem_orientation_check.md", "intake", authority="report", bindings=AUDIT_AND_OUTPUT),
    A("reference_materials/literature_registry.json", "acquisition", required={"acquisition"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, receipt_root=False, migration=True, schemas={ACQUISITION_SCHEMA_V1, ACQUISITION_SCHEMA_V2, ACQUISITION_SCHEMA_V3}),
    A("reference_materials/research_material_registry.json", "acquisition", writable={"acquisition", "research"}, required={"acquisition"}, authority="canonical", receipt_root=False, migration=True, schemas={RESEARCH_MATERIAL_SCHEMA_V1}),
    A("reference_materials/integrations/exa_runs/manifest.json", "acquisition", authority="supporting", bindings=AUDIT_AND_OUTPUT),
    A("reference_materials/integrations/zotero_snapshot.json", "acquisition", authority="supporting", bindings=AUDIT_AND_OUTPUT),
    A("reference_materials/source_index.md", "acquisition", required={"acquisition"}, authority="derived", rebuildable=True),
    A("source_map.md", "acquisition", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("research_dossier.md", "research", required={"research"}, bindings=AUDIT_AND_OUTPUT),
    A("exemplar_learning_dossier.md", "research", required={"research"}, bindings=AUDIT_AND_OUTPUT),
    A("style_profile.md", "research", required={"research"}, bindings=AUDIT_AND_OUTPUT),
    A(".avereth-commonplace/bank.json", "research", writable={"research", "build"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True, description="optional full-text language examples; no scientific authority"),
    A(".avereth-commonplace/disciplinary_phraseology.json", "research", writable={"research", "build"}, authority="derived", rebuildable=True, description="cross-source language conventions projected from Commonplace Bank"),
    A(".avereth-prose/commonplace_runs.json", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True, description="optional active Move writing-run paths; no stage or completion authority"),
    A("sota_gap_map.md", "research", required={"research"}, bindings=AUDIT_AND_OUTPUT),
    A("literature_analysis.json", "research", required={"research"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={LITERATURE_ANALYSIS_SCHEMA_V1, LITERATURE_ANALYSIS_SCHEMA_V2}),
    A("critical_reading_report.md", "research", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("literature_synthesis_matrix.md", "research", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("literature_analysis_check.md", "research", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("topic_induction_deduction_matrix.md", "research", bindings=AUDIT_AND_OUTPUT),
    A("topic_reasoning_check.md", "research", authority="derived", rebuildable=True),
    A("motivation_options_after_research.md", "research", required={"research"}, bindings=AUDIT_AND_OUTPUT),
    A("citation_support_bank.md", "research", required={"research"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("research_decision.json", "research", required={"research"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={RESEARCH_DECISION_SCHEMA_V1}),
    A("research_feasibility.json", "research", required={"research"}, authority="canonical", receipt_root=False, migration=True, schemas={RESEARCH_FEASIBILITY_SCHEMA_V1}),
    A("confirmed_motivation.md", "research", authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True),
    A("novelty_clearance_check.md", "research", required={"research"}, authority="report", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("taste_judgement.json", "research", authority="report", description="pairwise branch taste judgement; signal-not-gate"),
    A("taste_judgement.md", "research", authority="derived", rebuildable=True),
    A("research_design.json", "design", required={"design"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={DESIGN_SCHEMA_V1, DESIGN_SCHEMA_V2, DESIGN_SCHEMA_V3, DESIGN_SCHEMA_V4}),
    A("knowledge_design_matrix.md", "design", required={"design"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("concept_register.md", "design", required={"design"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("claim_evidence_scope_matrix.md", "design", required={"design"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("method_route_matrix.md", "design", required={"design"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("research_integrity_check.md", "design", required={"design"}, authority="derived", report=True, bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("case_design_matrix.md", "design", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("operationalization_matrix.md", "design", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("execution_protocol.md", "design", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("research_design_check.json", "design", authority="derived", rebuildable=True),
    A("research_design_check.md", "design", authority="derived", rebuildable=True),
    A("terminology_register.md", "design", required={"design"}, bindings=AUDIT_AND_OUTPUT),
    A("method_execution.json", "execution", required={"execution"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={EXECUTION_SCHEMA_V1, EXECUTION_SCHEMA_V2, EXECUTION_SCHEMA_V3}),
    A("execution_record.md", "execution", required={"execution"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("next_action.md", "execution", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("method_pilot_report.md", "execution", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("action_result_trace.md", "execution", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("claim_disposition_report.md", "execution", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("results_validation.md", "execution", required={"execution"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("confirmed_contribution.md", "execution", required={"execution"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True),
    A("revision_contract.json", "intake", authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={REVISION_CONTRACT_SCHEMA_V1, REVISION_CONTRACT_SCHEMA_V2}),
    A("revision_impact.json", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("dialogic_argument_map.md", "build", required={"build"}, bindings=AUDIT_AND_OUTPUT),
    A("section_blueprints.md", "build", required={"build"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("writing_rationale_matrix.md", "build", required={"build"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("promise_delivery_matrix.md", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("claim_lifecycle_matrix.md", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("reader_state_report.md", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("cross_section_sync_report.md", "build", authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    # Closure root: audit/output receipts bind this trace directly. Its generated
    # child views remain rebuildable, but excluding the trace would hide a changed
    # Contract/MIR/stale or rebuild-proof closure from receipt currentness.
    A("manuscript_trace_manifest.json", "build", authority="derived", bindings=AUDIT_AND_OUTPUT),
    A("evidence_bank.md", "build", required={"build"}, bindings=AUDIT_AND_OUTPUT),
    A("academic_prose_audit.md", "build", required={"build"}, bindings=AUDIT_AND_OUTPUT),
    A("final_paper/main.tex", "build", required={"build"}, alternatives=("final_paper/main.md", "final_paper/main.docx", "final_paper/paper.md", "final_paper/manuscript.md", "final_paper/manuscript.docx"), authority="manuscript", description="canonical manuscript source", bindings=AUDIT_AND_OUTPUT, receipt_root=False),
    A("source_inventory.md", "build", bindings=AUDIT_AND_OUTPUT, variant="build_from_materials"),
    A("figure_asset_map.md", "build", bindings=AUDIT_AND_OUTPUT, variant="build_from_materials"),
    A("claim_register.md", "build", bindings=AUDIT_AND_OUTPUT, variant="build_from_materials"),
    A("original_logic_map.md", "build", bindings=AUDIT_AND_OUTPUT, variant="rewrite_existing"),
    A("rewrite_matrix.md", "build", bindings=AUDIT_AND_OUTPUT, variant="rewrite_existing"),
    A("logic_transfer_audit.md", "build", bindings=AUDIT_AND_OUTPUT, variant="rewrite_existing"),
    A("build_run.json", "build", authority="report", bindings=AUDIT_AND_OUTPUT),
    A("artifact_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("integrity_audit.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("dialogic_argument_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("academic_prose_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("citation_bank_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("citation_quality_audit.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("citation_integrity_audit.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("contribution_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("results_validation_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("review_findings.json", "audit", required={"audit"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={REVIEW_FINDINGS_SCHEMA_V2, REVIEW_FINDINGS_SCHEMA_V3}),
    A("review_resolution.json", "audit", required={"audit"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={REVIEW_RESOLUTION_SCHEMA_V1, REVIEW_RESOLUTION_SCHEMA_V2}),
    A("structured_review.md", "audit", required={"audit"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("reviewer_audit.md", "audit", required={"audit"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("revision_plan.md", "audit", required={"audit"}, authority="derived", bindings=AUDIT_AND_OUTPUT, rebuildable=True),
    A("reviewer_audit_check.md", "audit", required={"audit"}, authority="report", report=True, bindings=AUDIT_AND_OUTPUT),
    A("review_assurance.json", "audit", required={"audit"}, authority="canonical", bindings=AUDIT_AND_OUTPUT, migration=True, schemas={REVIEW_ASSURANCE_SCHEMA_V1, REVIEW_ASSURANCE_SCHEMA_V2}),
    A("audit_run.json", "audit", authority="report", bindings=AUDIT_AND_OUTPUT),
    A("references.bib", "build", authority="derived", bindings=AUDIT_AND_OUTPUT),
    A("final_artifact_manifest.md", "output", required={"output"}, authority="report", bindings=OUTPUT_ONLY),
    A("final_artifact_manifest.json", "output", authority="canonical", bindings=OUTPUT_ONLY),
    A("output_run.json", "output", authority="report", bindings=OUTPUT_ONLY),
    A("render_qa.json", "output", authority="canonical", bindings=OUTPUT_ONLY),
    A("output_artifact_check.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("word_report.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("word_report.zh.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("latex_report.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("latex_guard.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("section_economy_check.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("translation_guard.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("translation_word_report.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("submission_check.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A("respond_check.md", "output", authority="report", bindings=OUTPUT_ONLY),
    A(LEGACY_AUDIT_REL, "audit", authority="legacy-receipt", migration=True),
    A(LEGACY_AUDIT_MD_REL, "audit", authority="legacy-receipt", migration=True),
    A(LEGACY_OUTPUT_REL, "output", authority="legacy-receipt", migration=True),
    A(LEGACY_OUTPUT_MD_REL, "output", authority="legacy-receipt", migration=True),
    A(LEGACY_STATUS_REL, "intake", authority="legacy-receipt", migration=True),
    A(LEGACY_STATUS_MD_REL, "intake", authority="legacy-receipt", migration=True),
)

ARTIFACTS_BY_PATH: Mapping[str, ArtifactDefinition] = MappingProxyType(
    {definition.path: definition for definition in ARTIFACT_DEFINITIONS}
)


STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition("intake", "scope", ("cnki-paper/references/problem-led-research.md",)),
    StageDefinition("acquisition", "evidence", ("cnki-paper/references/acquisition-registry.md", "cnki-paper/references/research-material-feasibility.md", "cnki-paper/references/primary-source-citation.md", "cnki-paper/references/source-channels-cn.md"), ("publication-track-acquisition",)),
    StageDefinition("research", "evidence", ("cnki-paper/references/critical-reading-and-synthesis.md", "cnki-paper/references/research-gap-diagnosis.md", "cnki-paper/references/topic-induction-deduction.md", "cnki-paper/references/research-question-design.md", "cnki-paper/references/research-material-feasibility.md"), ("publication-track-acquisition",)),
    StageDefinition("design", "analysis", ("cnki-paper/references/research-design-spine.md", "cnki-paper/references/research-foundations.md", "cnki-paper/references/method-routing.md", "cnki-paper/references/measurement-inference.md", "cnki-paper/references/terminology-governance.md"), ("empirical-research",)),
    StageDefinition("execution", "analysis", ("empirical-research/references/method-execution-contract.md", "empirical-research/references/research-integrity.md"), ("empirical-research",)),
    StageDefinition("build", "manuscript", ("cnki-paper/references/engine/manuscript-compiler.md", "cnki-paper/references/academic-prose.md", "cnki-paper/references/anti-defensive-writing.md", "cnki-paper/references/dialogic-argument.md", "cnki-paper/references/cn-journal-conventions.md", "cnki-paper/references/primary-source-citation.md")),
    StageDefinition("audit", "verify", ("cnki-paper/references/academic-prose.md", "cnki-paper/references/anti-defensive-writing.md", "cnki-paper/references/dialogic-argument.md", "cnki-paper/references/top-journal-anatomy.md", "cnki-paper/references/engine/reviewer-audit.md", "cnki-paper/references/cn-journal-conventions.md", "cnki-paper/references/primary-source-citation.md"), ("structured-review", "page-evidence-if-required")),
    StageDefinition("output", "verify", ("cnki-paper/references/workflow-playbook.md", "cnki-paper/references/cn-journal-conventions.md"), ("local-renderers",)),
)
STAGES_BY_KEY: Mapping[str, StageDefinition] = MappingProxyType(
    {definition.key: definition for definition in STAGE_DEFINITIONS}
)
STAGE_TO_SEMANTIC_PHASE: Mapping[str, str] = MappingProxyType(
    {definition.key: definition.semantic_phase for definition in STAGE_DEFINITIONS}
)
PROFILE_REFERENCE_PATHS: Mapping[str, tuple[str, ...]] = MappingProxyType({
    "manuscript_revision": ("cnki-paper/references/controlled-revision.md",),
})

# Stage references are a discovery catalog. Action scopes determine actual reads;
# they never alter the artifact, receipt, or stage contracts above.
REFERENCE_ACTIONS = MappingProxyType({
    "scope": ("intake", (("cnki-paper/references/problem-led-research.md", ()),)),
    "discover": ("acquisition", (("cnki-paper/references/acquisition-registry.md", (
        "2. 获取闭环", "3. 注册表结构", "4. 查询记录", "6. 状态与证据等级",
    )),)),
    "register-source": ("acquisition", (("cnki-paper/references/acquisition-registry.md", (
        "3. 注册表结构", "5. 来源记录", "6. 状态与证据等级", "7. PDF 落盘闭环", "9. 命令",
    )),)),
    "synthesis": ("research", (("cnki-paper/references/critical-reading-and-synthesis.md", (
        "一、先分清三种产物", "四、按主张分级的全文规则", "五、从单篇裁决到跨文献综合", "七、硬门、语义复核与 AI 边界",
    )), ("cnki-paper/references/rhetorical-architecture.md", ("Problem Arc in literature analysis",)))),
    "critical-reading": ("research", (("cnki-paper/references/critical-reading-and-synthesis.md", (
        "二、三阶段七步批判性阅读", "三、按来源类型适配判准", "四、按主张分级的全文规则",
    )),)),
    "topic-portfolio": ("research", (("cnki-paper/references/topic-selection-protocol.md", ()),)),
    "gap-diagnosis": ("research", (("cnki-paper/references/research-gap-diagnosis.md", ()),)),
    "question-design": ("research", (
        ("cnki-paper/references/research-question-design.md", ()),
        ("cnki-paper/references/title-design.md", ("1. 标题的四要素", "2. 证据阶段决定标题功能", "3. 两步拟题法")),
    )),
    "feasibility": ("research", (("cnki-paper/references/research-material-feasibility.md", ()),)),
    "method-design": ("design", (
        ("cnki-paper/references/research-design-spine.md", ()),
        ("cnki-paper/references/method-routing.md", ()),
    )),
    "analysis": ("execution", (
        ("empirical-research/references/method-execution-contract.md", ()),
        ("empirical-research/references/research-integrity.md", ()),
    )),
    "manuscript": ("build", (
        ("cnki-paper/references/engine/manuscript-compiler.md", ()),
        ("cnki-paper/references/academic-prose.md", ("1. 定位与边界",)),
        ("cnki-paper/references/rhetorical-architecture.md", ("Thought Moves in the manuscript contract", "Throughline and Section responsibilities", "Epistemic hooks", "Context Anchors and scenes", "Title–body fulfillment")),
        ("cnki-paper/references/title-design.md", ("4. 共鸣—描述的组合方式", "5. 可用修辞及其边界", "7. 候选比较与定稿审计")),
    )),
    "prose": ("build", (("cnki-paper/references/academic-prose.md", ("1. 定位与边界", "2. 外至内改稿序列：前置审查 + 五遍")),)),
    "defensive-prose": ("build", (
        ("cnki-paper/references/academic-prose.md", ("1. 定位与边界",)),
        ("cnki-paper/references/anti-defensive-writing.md", ()),
    )),
    "audit": ("audit", (
        ("cnki-paper/references/workflow-playbook.md", ("阶段 6：audit — 审计、三方评审与 Finding 生命周期",)),
        ("cnki-paper/references/academic-prose.md", ("3. 工件模板：academic_prose_audit.md",)),
    )),
    "structured-review": ("audit", (("cnki-paper/references/engine/reviewer-audit.md", ()),)),
    "output": ("output", (("cnki-paper/references/workflow-playbook.md", ("阶段 7：output — 候选渲染、真实视觉复核与事务发布",)),)),
    "docx-format": ("output", (("cnki-paper/references/docx-format-fixes.md", ()),)),
})
DEFAULT_REFERENCE_ACTIONS = MappingProxyType({
    "intake": "scope", "acquisition": "discover", "research": "synthesis",
    "design": "method-design", "execution": "analysis", "build": "manuscript",
    "audit": "audit", "output": "output",
})


def artifact_definition(path: str | Path) -> ArtifactDefinition:
    normalized = Path(path).as_posix()
    try:
        return ARTIFACTS_BY_PATH[normalized]
    except KeyError as exc:
        raise KeyError(f"artifact is not registered: {normalized}") from exc


def stage_artifact_definitions(stage: str) -> tuple[ArtifactDefinition, ...]:
    if stage not in STAGES_BY_KEY:
        return ()
    return tuple(
        definition
        for definition in ARTIFACT_DEFINITIONS
        if stage in definition.required_stages and not definition.variant
    )


def stage_artifact_specs(stage: str) -> tuple[ArtifactSpec, ...]:
    return tuple(definition.as_spec() for definition in stage_artifact_definitions(stage))


def build_variant_specs(workflow: str) -> tuple[ArtifactSpec, ...]:
    return tuple(
        definition.as_spec()
        for definition in ARTIFACT_DEFINITIONS
        if definition.variant == workflow
    )


def receipt_bound_root_paths() -> frozenset[str]:
    return frozenset(
        definition.path
        for definition in ARTIFACT_DEFINITIONS
        if definition.receipt_bindings and definition.receipt_root
    )


def rebuildable_view_paths() -> frozenset[str]:
    return frozenset(
        definition.path
        for definition in ARTIFACT_DEFINITIONS
        if definition.rebuildable_view
    )


def migration_contracts() -> tuple[Path, ...]:
    return tuple(
        Path(definition.path)
        for definition in ARTIFACT_DEFINITIONS
        if definition.migration_contract
    )


def migration_schema_allowlist() -> dict[Path, set[str]]:
    return {
        Path(definition.path): set(definition.allowed_schemas)
        for definition in ARTIFACT_DEFINITIONS
        if definition.allowed_schemas
    }


RECEIPT_BOUND_ROOT_PATHS = receipt_bound_root_paths()
REBUILDABLE_VIEW_PATHS = rebuildable_view_paths()
MIGRATION_CONTRACT_PATHS = tuple(path.as_posix() for path in migration_contracts())


@dataclass(frozen=True)
class RuntimeComponentDefinition:
    path: str
    groups: frozenset[str] = frozenset()
    global_required: bool = True


def R(path: str, *groups: str, global_required: bool = True) -> RuntimeComponentDefinition:
    return RuntimeComponentDefinition(path, frozenset(groups), global_required)


# Runtime files are also one-row facts.  Profile-aware doctor projects groups;
# global doctor projects every row marked ``global_required``.
RUNTIME_COMPONENTS: tuple[RuntimeComponentDefinition, ...] = (
    R("chinese-legal-paper/SKILL.md", "legal", global_required=False),
    R("chinese-legal-paper/assets/method-profiles.json", "legal", global_required=False),
    R("chinese-legal-paper/references/citations.md", "legal", global_required=False),
    R("chinese-legal-paper/references/contracts.md", "legal", global_required=False),
    R("chinese-legal-paper/references/methods.md", "legal", global_required=False),
    R("chinese-legal-paper/references/providers.md", "legal", global_required=False),
    R("chinese-legal-paper/references/research.md", "legal", global_required=False),
    R("chinese-legal-paper/references/writing.md", "legal", global_required=False),
    R("chinese-legal-paper/schemas/legal-analysis-v1.schema.json", "legal", global_required=False),
    R("chinese-legal-paper/schemas/legal-citations-v1.schema.json", "legal", global_required=False),
    R("chinese-legal-paper/schemas/legal-review-v1.schema.json", "legal", global_required=False),
    R("chinese-legal-paper/schemas/legal-sources-v1.schema.json", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/__init__.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/citations.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/common.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/pkulaw.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/providers.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/templates.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_core/validation.py", "legal", global_required=False),
    R("chinese-legal-paper/scripts/legal_paper.py", "legal", global_required=False),
    R("cnki-paper/SKILL.md", "core", global_required=False),
    R("cnki-paper/scripts/avereth.py", "core"),
    R("cnki-paper/scripts/avereth_core/cli.py", "core"),
    R("cnki-paper/scripts/avereth_core/scientific_runtime.py", "core"),
    R("cnki-paper/scripts/avereth_core/stages.py", "core"),
    R("cnki-paper/scripts/avereth_core/workflow_registry.py", "core"),
    R("cnki-paper/scripts/avereth_core/gates/integration_gate.py", "core"),
    R("cnki-paper/scripts/avereth_core/infrastructure/integration_contracts.py", "core"),
    R("cnki-paper/scripts/avereth_core/infrastructure/locks.py", "core"),
    R("cnki-paper/scripts/avereth_core/infrastructure/legal_domain.py", "core"),
    R("cnki-paper/scripts/avereth_core/application/plan_service.py", "core"),
    R("cnki-paper/scripts/avereth_core/application/protocol_compiler.py", "core"),
    R("cnki-paper/scripts/avereth_core/audit/run_all.py", "core"),
    R("cnki-paper/scripts/avereth_core/build/manuscript.py", "core"),
    R("cnki-paper/scripts/avereth_core/build/manuscript_compiler.py", "core"),
    R("cnki-paper/scripts/avereth_core/build/run.py", "core"),
    R("cnki-paper/scripts/avereth_core/build/exhibit_map.py", "methods"),
    R("cnki-paper/references/engine/manuscript-compiler.md", "core"),
    R("cnki-paper/references/manuscript-profiles/empirical-social-science-v1.json", "core"),
    R("cnki-paper/references/manuscript-profiles/humanities-argument-v1.json", "core"),
    R("cnki-paper/references/cn-journal-conventions.md", "core"),
    R("cnki-paper/references/primary-source-citation.md", "core"),
    R("cnki-paper/references/source-channels-cn.md", "research"),
    R("cnki-paper/references/schemas/avereth-manuscript-contract-v1.schema.json", "core"),
    R("cnki-paper/references/schemas/avereth-manuscript-ir-v1.schema.json", "core"),
    R("cnki-paper/references/schemas/avereth-manuscript-rebuild-proof-v1.schema.json", "core"),
    R("cnki-paper/scripts/avereth_core/output/run.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/policy.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/render.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/guards.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/translation.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/submission.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/response.py", "core"),
    R("cnki-paper/scripts/avereth_core/output/word_render.ps1", "word"),
    R("cnki-paper/scripts/codex_cnki_gate.py", "core"),
    R("cnki-paper/scripts/research_design_v4.py", "methods"),
    R("cnki-paper/references/schemas/cnki-research-design-v4.schema.json", "methods"),
    R("empirical-research/references/schemas/cnki-method-execution-v3.schema.json", "methods"),
    R("empirical-research/references/schemas/avereth-exhibit-spec-v1.schema.json", "methods"),
    R("empirical-research/references/schemas/avereth-exhibit-data-v1.schema.json", "methods"),
    R("empirical-research/references/schemas/avereth-exhibit-renderer-environment-v1.schema.json", "methods"),
    R("empirical-research/references/schemas/avereth-exhibit-render-log-v1.schema.json", "methods"),
    R("empirical-research/references/exhibits/exhibit-contract.md", "methods"),
    R("empirical-research/references/exhibits/style-profiles/cn-social-science.json", "methods"),
    R("empirical-research/references/exhibits/style-profiles/international-polisci-econ.json", "methods"),
    R("empirical-research/references/exhibits/recipes/coefficient-forest.json", "methods"),
    R("empirical-research/references/exhibits/recipes/event-study.json", "methods"),
    R("empirical-research/references/exhibits/recipes/marginal-effects.json", "methods"),
    R("empirical-research/references/exhibits/recipes/predicted-probability.json", "methods"),
    R("empirical-research/references/exhibits/recipes/trend-or-binscatter.json", "methods"),
    R("empirical-research/references/exhibits/recipes/regression-or-balance-table.json", "methods"),
    R("empirical-research/scripts/exhibits/__init__.py", "methods"),
    R("empirical-research/scripts/exhibits/contract.py", "methods"),
    R("empirical-research/scripts/exhibits/exhibit.py", "methods"),
    R("empirical-research/scripts/exhibits/figure_map.py", "methods"),
    R("empirical-research/scripts/exhibits/render_bundle.py", "methods"),
    R("empirical-research/scripts/exhibits/smoke.py", "methods"),
    R("empirical-research/scripts/exhibits/table_emit.py", "methods"),
    R("empirical-research/scripts/exhibits/backends/r/render_exhibit.R", "methods"),
    R("empirical-research/scripts/researcher_dispatch.py", "methods"),
    R("empirical-research/references/schemas/method-operation-v1.schema.json", "methods"),
    R("empirical-research/references/schemas/failure-taxonomy-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/case-study-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/comparative-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/computational-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/conceptual-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/congruence-analysis-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/content-analysis-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/discourse-analysis-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/experiment-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/grounded-theory-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/historical-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/interpretive-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/normative-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/process-tracing-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/qca-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/quantitative-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/review-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/social-network-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/survey-v1.json", "methods"),
    R("empirical-research/references/operation-profiles/text-as-data-v1.json", "methods"),
    R("cnki-paper/scripts/problem_orientation_check.py", "core"),
    R("cnki-paper/references/problem-led-research.md", "core"),
    R("cnki-paper/references/research-material-feasibility.md", "research"),
    R("cnki-paper/references/quantitative-data-check.md", "quantitative-data", global_required=False),
    R("cnki-paper/references/schemas/avereth-workflow-config-v1.schema.json", "core"),
    R("cnki-paper/references/schemas/avereth-topic-packet-v1.schema.json", "research"),
    R("cnki-paper/scripts/cnki_acquisition.py", "research"),
    R("cnki-paper/scripts/literature_analysis.py", "research", "revision"),
    R("cnki-paper/scripts/research_gap_diagnosis.py", "research"),
    R("cnki-paper/scripts/literature_sufficiency.py", "research", "revision"),
    R("cnki-paper/scripts/citation_edges.py", "research", "revision"),
    R("cnki-paper/scripts/research_decision.py", "research"),
    R("cnki-paper/scripts/research_materials.py", "research"),
    R("cnki-paper/scripts/research_feasibility.py", "research"),
    R("cnki-paper/scripts/optional/quantitative_data/quantitative_data_check.py", "quantitative-data", global_required=False),
    R("cnki-paper/scripts/topic_reasoning_check.py", "research"),
    R("cnki-paper/scripts/topic_packet.py", "research"),
    R("cnki-paper/scripts/taste_cards.py", "research"),
    R("cnki-paper/scripts/taste_judge.py", "research"),
    R("cnki-paper/scripts/taste_exemplars.py", "research"),
    R("cnki-paper/references/taste/branch-taste-cards.json", "research"),
    R("cnki-paper/references/taste-judgement.md", "research"),
    R("cnki-paper/scripts/research_quality_check.py", "research"),
    R("cnki-paper/references/critical-reading-and-synthesis.md", "research"),
    R("cnki-paper/references/research-gap-diagnosis.md", "research"),
    R("cnki-paper/references/literature-sufficiency.md", "research"),
    R("cnki-paper/references/schemas/cnki-acquisition-v2.schema.json", "research"),
    R("cnki-paper/references/schemas/cnki-acquisition-v3.schema.json", "research"),
    R("cnki-paper/references/schemas/avereth-exa-run-v1.schema.json", "research"),
    R("cnki-paper/references/schemas/avereth-exa-manifest-v1.schema.json", "research"),
    R("cnki-paper/references/schemas/avereth-zotero-snapshot-v1.schema.json", "research"),
    R("cnki-paper/references/integrations/exa-zotero-integration.md", "research"),
    R("cnki-paper/references/schemas/cnki-literature-analysis-v2.schema.json", "research", "revision"),
    R("cnki-paper/references/schemas/cnki-research-decision-v1.schema.json", "research"),
    R("cnki-paper/references/schemas/avereth-research-material-registry-v1.schema.json", "research"),
    R("cnki-paper/references/schemas/avereth-research-feasibility-v1.schema.json", "research"),
    R("cnki-paper/scripts/revision_contract.py", "revision"),
    R("cnki-paper/references/schemas/cnki-manuscript-revision-v1.schema.json", "revision"),
    R("cnki-paper/references/schemas/cnki-manuscript-revision-v2.schema.json", "revision"),
    R("cnki-paper/references/schemas/avereth-revision-impact-v1.schema.json", "revision"),
    R("cnki-paper/references/controlled-revision.md", "revision"),
    R("cnki-paper/scripts/research_design.py", "methods"),
    R("cnki-paper/scripts/research_design_v3.py", "methods"),
    R("cnki-paper/scripts/research_design_v2.py", "methods"),
    R("cnki-paper/references/schemas/cnki-research-design-v2.schema.json", "methods"),
    R("cnki-paper/references/schemas/cnki-research-design-v3.schema.json", "methods"),
    R("empirical-research/scripts/method_execution.py", "methods"),
    R("empirical-research/scripts/method_contract_loader.py", "methods"),
    R("empirical-research/scripts/validate_method_artifacts.py", "methods"),
    R("empirical-research/scripts/validate_measurement.py", "methods"),
    R("empirical-research/scripts/migrate_method_contracts.py", "methods"),
    R("empirical-research/scripts/repro_pack.py", "methods"),
    R("empirical-research/scripts/validators/__init__.py", "methods"),
    R("empirical-research/scripts/validators/common.py", "methods"),
    R("empirical-research/references/method-adapter-registry.json", "methods"),
    R("empirical-research/references/schemas/cnki-method-execution-v1.schema.json"),
    R("empirical-research/references/schemas/cnki-method-execution-v2.schema.json", "methods"),
    R("intl-search/scripts/openalex_search.py", "international"),
    R("intl-search/scripts/openalex_snowball.py", "international"),
    R("intl-search/scripts/resource_guard.py", "international"),
    R("intl-search/scripts/s2_search.py", "international"),
    R("intl-search/scripts/scholar_search.py", "international"),
    R("intl-search/references/scholar-browser.md"),
    R("intl-export/scripts/doi_export.py", "international"),
    R("cnki-paper/scripts/avereth_core/tools/word_guard.py", "word", "output"),
    R("cnki-paper/scripts/avereth_core/tools/citation_integrity_audit.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/_engine_utils.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/citation_bank_check.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/citation_quality_audit.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/contribution_check.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/reviewer_audit_check.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/review_lifecycle.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/__init__.py", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/structured_review.py", "audit"),
    R("cnki-paper/references/schemas/cnki-review-assurance-v2.schema.json", "audit"),
    R("cnki-paper/references/schemas/avereth-review-findings-v2.schema.json", "audit"),
    R("cnki-paper/references/schemas/avereth-review-findings-v3.schema.json", "audit"),
    R("cnki-paper/references/schemas/avereth-review-resolution-v1.schema.json", "audit"),
    R("cnki-paper/references/schemas/avereth-review-resolution-v2.schema.json", "audit"),
    R("cnki-paper/references/schemas/avereth-review-cycle-v1.schema.json", "audit"),
    R("cnki-paper/scripts/avereth_core/tools/results_validation_check.py", "results"),
    R("cnki-paper/scripts/avereth_core/tools/latex_guard.py", "output", global_required=False),
    R("cnki-paper/scripts/avereth_core/tools/section_economy_check.py", "output", global_required=False),
    R("cnki-paper/scripts/dialogic_argument_check.py"),
    R("cnki-paper/scripts/academic_prose_check.py"),
    R("cnki-paper/scripts/prose_packet.py", "core"),
    R("cnki-paper/scripts/commonplace_bank.py", "core"),
    R("cnki-paper/scripts/commonplace_retrieve.py", "core"),
    R("cnki-paper/scripts/commonplace_overlap_check.py", "core"),
    R("cnki-paper/scripts/commonplace_writing.py", "core"),
    R("cnki-paper/references/commonplace-writing.md", "core"),
    R("cnki-paper/references/dialogic-argument.md"),
    R("cnki-paper/references/academic-prose.md"),
    R("cnki-paper/references/anti-defensive-writing.md"),
    R("cnki-paper/references/schemas/cnki-review-assurance-v1.schema.json"),
    R("page-evidence/scripts/page_evidence_audit.py", "page-evidence"),
)

RUNTIME_COMPONENTS_BY_PATH: Mapping[str, RuntimeComponentDefinition] = MappingProxyType(
    {definition.path: definition for definition in RUNTIME_COMPONENTS}
)
GLOBAL_RUNTIME_FILES = tuple(
    definition.path for definition in RUNTIME_COMPONENTS if definition.global_required
)


def runtime_files_for(groups: Iterable[str]) -> tuple[str, ...]:
    selected = set(groups)
    return tuple(
        sorted(
            definition.path
            for definition in RUNTIME_COMPONENTS
            if definition.groups & selected
        )
    )


_QUANTITATIVE_ROUTE_VALUES = frozenset(
    {
        "computational",
        "mixed",
        "mixed-methods",
        "mixed_methods",
        "quantitative",
        "survey",
        "text-as-data",
        "text_as_data",
    }
)


def quantitative_data_check_required(config: Mapping[str, object]) -> bool:
    """Route the optional data check only from explicit method/config facts."""

    if config.get("quantitative_data_check") is True or config.get("quantitative_data_required") is True:
        return True
    declared: list[str] = []
    for key in ("paper_type", "study_type", "method_family"):
        value = config.get(key)
        if isinstance(value, str):
            declared.append(value)
    families = config.get("method_families")
    if isinstance(families, (list, tuple, set, frozenset)):
        declared.extend(str(value) for value in families)
    return any(value.strip().lower() in _QUANTITATIVE_ROUTE_VALUES for value in declared)


CNKI_SEARCH_SKILLS = frozenset({"cnki-search", "cnki-advanced-search", "cnki-parse-results", "cnki-paper-detail", "cnki-navigate-pages", "cnki-download", "cnki-export", "cnki-journal-search", "cnki-journal-index", "cnki-journal-toc", "cnki-snowball"})
INTERNATIONAL_SEARCH_SKILLS = frozenset({"intl-search", "intl-export"})
REQUIRED_SKILLS = tuple(sorted({"empirical-research", *CNKI_SEARCH_SKILLS, *INTERNATIONAL_SEARCH_SKILLS, "page-evidence"}))


def registry_issues() -> list[str]:
    issues: list[str] = []
    if tuple(definition.key for definition in STAGE_DEFINITIONS) != STAGE_ORDER:
        issues.append("stage definition order differs from the public eight-stage spine")
    phases = tuple(definition.semantic_phase for definition in STAGE_DEFINITIONS)
    if set(phases) != set(SEMANTIC_PHASE_ORDER):
        issues.append("semantic phase projection differs from the public five-phase view")
    projected_order = tuple(dict.fromkeys(phases))
    if projected_order != SEMANTIC_PHASE_ORDER:
        issues.append("semantic phase projection is not monotonic over the eight-stage spine")
    artifact_paths = [definition.path for definition in ARTIFACT_DEFINITIONS]
    artifact_keys = [definition.key for definition in ARTIFACT_DEFINITIONS]
    if len(artifact_paths) != len(set(artifact_paths)):
        issues.append("artifact paths are not unique")
    if len(artifact_keys) != len(set(artifact_keys)):
        issues.append("artifact keys are not unique")
    runtime_paths = [definition.path for definition in RUNTIME_COMPONENTS]
    if len(runtime_paths) != len(set(runtime_paths)):
        issues.append("runtime component paths are not unique")
    for definition in ARTIFACT_DEFINITIONS:
        if definition.owner_stage not in STAGE_ORDER:
            issues.append(f"artifact has invalid owner stage: {definition.path}")
        if not definition.writable_stages or not definition.writable_stages <= set(STAGE_ORDER):
            issues.append(f"artifact has invalid writable stages: {definition.path}")
        if definition.owner_stage not in definition.writable_stages:
            issues.append(f"artifact owner cannot write its artifact: {definition.path}")
        if not definition.required_stages <= set(STAGE_ORDER):
            issues.append(f"artifact has invalid required stage: {definition.path}")
        if definition.receipt_root and not definition.receipt_bindings:
            issues.append(f"receipt-root artifact has no receipt binding: {definition.path}")
        if definition.allowed_schemas and definition.authority != "canonical":
            issues.append(f"schema-bearing artifact is not canonical: {definition.path}")
        if definition.required_stages and definition.owner_stage not in definition.required_stages:
            issues.append(f"required artifact is not owned by its producing stage: {definition.path}")
        if definition.variant and definition.owner_stage != "build":
            issues.append(f"non-build artifact declares a build variant: {definition.path}")
    if not set(PROFILE_REFERENCE_PATHS) <= set(TASK_PROFILE_TERMINALS):
        issues.append("profile reference map contains an unknown task profile")
    return issues


_REGISTRY_ISSUES = registry_issues()
if _REGISTRY_ISSUES:
    raise RuntimeError("invalid workflow registry: " + "; ".join(_REGISTRY_ISSUES))
