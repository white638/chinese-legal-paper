"""Pure projection from controller status to a bounded agent work plan."""

from __future__ import annotations

from typing import Any

from .delegation import project_delegation

from ..stages import stage_specs
from ..workflow_registry import (
    ARTIFACT_DEFINITIONS,
    ARTIFACTS_BY_PATH,
    PROFILE_REFERENCE_PATHS,
    DEFAULT_REFERENCE_ACTIONS,
    REFERENCE_ACTIONS,
    STAGE_TO_SEMANTIC_PHASE,
    STAGES_BY_KEY,
    quantitative_data_check_required,
)


PLAN_SCHEMA = "avereth-plan/v2"


def _reference_requests(
    stage: str,
    track: str,
    profile: str,
    config: dict[str, Any],
    action: str,
) -> list[dict[str, Any]]:
    if not stage:
        return []
    selected_stage, scopes = REFERENCE_ACTIONS[action]
    if selected_stage != stage:
        raise ValueError(f"reference action {action!r} is not available in stage {stage!r}")
    requests: dict[str, dict[str, Any]] = {}

    def add(path: str, sections: tuple[str, ...] = (), reason: str = action) -> None:
        requests[path] = {"path": path, "sections": list(sections), "reason": reason}

    for path, sections in scopes:
        if path.endswith("engine/manuscript-compiler.md") and profile not in {"full_paper", "manuscript_revision"}:
            continue
        add(path, sections)
    if config.get("prose_conditioning", "none") in {"commonplace", "auto"} and stage in {"research", "build", "audit"}:
        sections = {
            "research": ("1. 权威与启用", "2. 研究阶段摘录", "3.1 短语分类与来源支持"),
            "build": ("1. 权威与启用", "3. 共同体短语与检索", "4. 借用检查与现有正文链"),
            "audit": ("1. 权威与启用", "3.1 短语分类与来源支持", "4. 借用检查与现有正文链"),
        }[stage]
        add("cnki-paper/references/commonplace-writing.md", sections, "enabled Move-conditioned writing")
    if stage != "output":
        for path in PROFILE_REFERENCE_PATHS.get(profile, ()):
            sections = ()
            if path == "cnki-paper/references/controlled-revision.md":
                sections = ("适用范围与资格", "修改分类与最早重开阶段", "保证等级")
                if stage in {"intake", "build"}:
                    sections += ("命令入口",)
            add(path, sections, "controlled revision scope")
    if stage in {"acquisition", "research"} and track in {"cnki-cn", "mixed"}:
        if action in {"discover", "register-source", "topic-portfolio"}:
            sections = (
                "1. 验证码协议", "2. 检索与解析", "2a. 中文术语谱系与自创词撞车检索",
                "2b. 引文滚雪球（详情页六方向）", "6. PDF 下载与机构权限", "12. CNKI 之外的国内补充源",
            )
            if action == "register-source":
                sections = (
                    "1. 验证码协议", "4.1 已验证导出参数", "4.2 CNKI 非 DOI 证据链",
                    "5. 同源 fetch 批量抓摘要", "6. PDF 下载与机构权限",
                )
            add("cnki-paper/references/cnki-operations.md", sections, "CNKI source acquisition")
    if stage in {"acquisition", "research", "design", "execution"} and quantitative_data_check_required(config):
        add("cnki-paper/references/quantitative-data-check.md", reason="structured data required by the task")
    language = str(config.get("output_language") or config.get("language") or config.get("manuscript_language") or "").casefold()
    chinese = language in {"zh", "zh-cn", "chinese", "中文", "zh-hans"} or (not language and track == "cnki-cn")
    if chinese and stage in {"build", "audit", "output"}:
        sections = {
            "build": ("0. 如何使用", "1. 两大引注体系总览", "4. 摘要与关键词", "7. 标题层级", "9. 数字、标点、图表与注码"),
            "audit": ("6. 匿名评审去标识清单", "11. 投稿前体例自检清单", "12. 必须当次核验目标刊投稿须知的事项"),
            "output": ("5. 基金项目、作者简介、通讯作者", "6. 匿名评审去标识清单", "9. 数字、标点、图表与注码", "11. 投稿前体例自检清单"),
        }[stage]
        add("cnki-paper/references/cn-journal-conventions.md", sections, "Chinese manuscript conventions")
    method_signals = [config.get(key) for key in ("method_family", "paper_type", "study_type")]
    if isinstance(config.get("method_families"), list):
        method_signals.extend(config["method_families"])
    historical = any(str(value or "").casefold() in {"historical", "history", "historical_textual", "comparative_history"} for value in method_signals)
    if (historical or config.get("manuscript_profile") == "humanities-argument") and stage in {"acquisition", "research", "build", "audit"}:
        sections = {
            "acquisition": ("2. 史料层级判定", "3. 版本选择与著录", "5. 页码与定位符", "7. 转引规则"),
            "research": ("2. 史料层级判定", "8. 史料批判最小清单", "9. 一手史料在论证中的推断上限"),
            "build": ("4. 两种著录体例的完整示例", "5. 页码与定位符", "6. 引文忠实度核对规程", "7. 转引规则"),
            "audit": ("6. 引文忠实度核对规程", "10. 史料引用自检清单与 page-evidence 分级对应"),
        }[stage]
        add("cnki-paper/references/primary-source-citation.md", sections, "historical or primary-source argument")
    if config.get("legal_profile") == "chinese-law-v1":
        domain_ref = {
            "intake": "contracts", "acquisition": "research", "research": "research",
            "design": "methods", "execution": "methods", "build": "writing",
            "audit": "citations", "output": "citations",
        }.get(stage)
        if domain_ref:
            add(f"chinese-legal-paper/references/{domain_ref}.md", reason="enabled Chinese legal research overlay")
    return [requests[path] for path in sorted(requests)]


def _adapters(stage: str, track: str, config: dict[str, Any]) -> list[str]:
    definition = STAGES_BY_KEY.get(stage)
    if definition is None:
        return []
    adapters: list[str] = []
    for adapter in definition.adapters:
        if adapter == "publication-track-acquisition":
            if track in {"cnki-cn", "mixed"}:
                adapters.append("cnki-acquisition-adapters")
            if track in {"international-ssci", "mixed"}:
                adapters.extend(("intl-search", "intl-export"))
        elif adapter == "page-evidence-if-required":
            if bool(config.get("page_evidence_required")):
                adapters.append("page-evidence")
        else:
            adapters.append(adapter)
    if stage in {"acquisition", "research", "design", "execution"} and quantitative_data_check_required(config):
        adapters.append("quantitative-data-check")
    if config.get("legal_profile") == "chinese-law-v1":
        adapters.append("chinese-legal-paper")
    return sorted(dict.fromkeys(adapters))


def _allowed_writes(stage: str, config: dict[str, Any], profile: str) -> list[str]:
    """Project only paths the active stage contract permits this route to create."""

    if stage and stage != "build":
        paths = [
            definition.path
            for definition in ARTIFACT_DEFINITIONS
            if stage in definition.writable_stages
            and not definition.authority.startswith("legacy")
            and not definition.variant
            and (not definition.domain_profile or definition.domain_profile == config.get("legal_profile"))
        ]
        if stage == "intake" and profile != "manuscript_revision":
            paths = [path for path in paths if path != "revision_contract.json"]
        return sorted(dict.fromkeys(paths))
    paths: list[str] = []
    for spec in stage_specs(stage, config):
        definition = ARTIFACTS_BY_PATH.get(spec.path)
        if definition is not None and definition.authority.startswith("legacy"):
            continue
        paths.append(spec.path)
    if stage == "intake" and profile == "manuscript_revision":
        paths.append("revision_contract.json")
    return sorted(dict.fromkeys(paths))


def build_plan(
    status: dict[str, Any],
    config: dict[str, Any] | None = None,
    *,
    protocol: dict[str, Any] | None = None,
    granularity: str = "stage",
    reference_action: str | None = None,
    discovery_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a stable, read-only plan for the controller's earliest stage."""

    active = dict(config or {})
    next_stage = str(status.get("next_stage") or "intake")
    profile = str(status.get("task_profile") or active.get("task_profile") or "full_paper")
    track = str(status.get("publication_track") or active.get("publication_track") or "undeclared")
    active["task_profile"] = profile
    route_plan = status.get("route_plan") if isinstance(status.get("route_plan"), dict) else {}
    if route_plan.get("earliest_reopen_stage"):
        active["earliest_reopen_stage"] = route_plan["earliest_reopen_stage"]
    actionable_stage = next_stage if next_stage in STAGES_BY_KEY else ""
    action = reference_action or DEFAULT_REFERENCE_ACTIONS.get(actionable_stage, "")
    if not reference_action and actionable_stage == "research" and profile == "topic_selection":
        action = "topic-portfolio"
    if action and action not in REFERENCE_ACTIONS:
        raise ValueError(f"unknown reference action: {action!r}")
    reference_requests = _reference_requests(actionable_stage, track, profile, active, action)
    checkpoint = str(status.get("next_checkpoint") or "")
    user_decision_required = checkpoint in {
        "question_confirmation",
        "soft_focus_confirmation",
        "hard_clearance_confirmation",
        "withdrawal_confirmation",
        "problem_reopening",
        "problem_reappraisal",
    }
    plan = {
        "schema_version": PLAN_SCHEMA,
        "route": "workspace",
        "profile": profile,
        "publication_track": track,
        "terminal_stage": status.get("terminal_stage"),
        "next_stage": next_stage,
        "semantic_phase": STAGE_TO_SEMANTIC_PHASE.get(actionable_stage),
        "next_checkpoint": checkpoint or None,
        "research_decision_state": status.get("research_decision_state"),
        "preclearance_readiness": status.get("preclearance_readiness"),
        "feasibility_state": status.get("feasibility_state"),
        "resource_unlock_state": status.get("resource_unlock_state"),
        "resource_blocker": status.get("resource_blocker"),
        "reference_action": action or None,
        "available_reference_actions": [key for key, value in REFERENCE_ACTIONS.items() if value[0] == actionable_stage],
        "reference_requests": reference_requests,
        "required_references": [item["path"] for item in reference_requests],
        "required_adapters": _adapters(actionable_stage, track, active),
        "allowed_writes": _allowed_writes(actionable_stage, active, profile),
        "expected_outputs": (
            ["final_artifact_manifest.json", "output_receipt.json"]
            if actionable_stage == "output"
            else []
        ),
        "user_decision_required": user_decision_required,
        "can_run_gate": bool(actionable_stage) and not user_decision_required,
        "status_code": "complete" if next_stage == "complete" else "blocked" if next_stage == "blocked" else "actionable",
        "granularity": granularity,
        "next_executable_action": None,
        "work_items": [],
        "runnable_action_ids": [],
        "parallel_safe_groups": [],
        "protocol_issues": [],
        "researcher_dispatch_mode": "single",
    }
    if granularity == "operation" and actionable_stage == "execution":
        projection = protocol or {}
        plan["next_executable_action"] = projection.get("next_executable_action")
        plan["work_items"] = list(projection.get("work_items") or [])
        plan["runnable_action_ids"] = list(projection.get("runnable_action_ids") or [])
        plan["parallel_safe_groups"] = list(projection.get("parallel_safe_groups") or [])
        plan["protocol_issues"] = list(projection.get("issues") or [])
        next_action = str(plan.get("next_executable_action") or "")
        next_item = next(
            (
                item
                for item in plan["work_items"]
                if isinstance(item, dict) and str(item.get("id") or "") == next_action
            ),
            None,
        )
        dispatch = next_item.get("researcher_dispatch") if isinstance(next_item, dict) else None
        if isinstance(dispatch, dict) and dispatch.get("mode") in {"single", "isolated_multi"}:
            plan["researcher_dispatch_mode"] = dispatch["mode"]
        if projection and not bool(projection.get("valid")):
            plan["can_run_gate"] = False
            plan["status_code"] = "blocked"
    if next_stage == "complete":
        plan["allowed_writes"] = []
        plan["can_run_gate"] = False
    if next_stage == "blocked":
        plan["allowed_writes"] = []
        plan["can_run_gate"] = False
    plan.update(project_delegation(plan, active, protocol, discovery_context))
    if any(item.get("role") == "avereth_scout" for item in plan["delegation_requests"]):
        path = "cnki-paper/references/delegation.md"
        plan["reference_requests"].append({"path": path, "sections": ["Scout pilot"], "reason": "explicit Scout discovery"})
        plan["required_references"].append(path)
    return plan


def plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Avereth Work Plan",
        "",
        f"- route: {plan.get('route')}",
        f"- profile: {plan.get('profile')}",
        f"- publication_track: {plan.get('publication_track')}",
        f"- next_stage: {plan.get('next_stage')}",
        f"- semantic_phase: {plan.get('semantic_phase') or 'none'}",
        f"- next_checkpoint: {plan.get('next_checkpoint') or 'none'}",
        f"- research_decision_state: {plan.get('research_decision_state') or 'absent'}",
        f"- user_decision_required: {str(bool(plan.get('user_decision_required'))).lower()}",
        f"- can_run_gate: {str(bool(plan.get('can_run_gate'))).lower()}",
        f"- granularity: {plan.get('granularity') or 'stage'}",
        f"- next_executable_action: {plan.get('next_executable_action') or 'none'}",
        f"- researcher_dispatch_mode: {plan.get('researcher_dispatch_mode') or 'single'}",
    ]
    for label, key in (
        ("Required Adapters", "required_adapters"),
        ("Allowed Writes", "allowed_writes"),
        ("Expected Outputs", "expected_outputs"),
    ):
        lines.extend(["", f"## {label}", ""])
        values = list(plan.get(key) or [])
        lines.extend(f"- {value}" for value in values)
        if not values:
            lines.append("- none")
    lines.extend(["", "## Reference reading scopes", ""])
    for request in plan.get("reference_requests") or []:
        scope = "; ".join(request["sections"]) or "whole file"
        lines.append(f"- `{request['path']}` — {scope} ({request['reason']})")
    lines.append("Available reading actions: " + ", ".join(plan.get("available_reference_actions") or []))
    if plan.get("granularity") == "operation":
        lines.extend(["", "## Executable Work Items", ""])
        work_items = [item for item in plan.get("work_items") or [] if isinstance(item, dict)]
        for item in work_items:
            procedure = item.get("procedure") if isinstance(item.get("procedure"), dict) else {}
            lines.append(
                f"- `{item.get('id')}` [{item.get('run_kind')}] {procedure.get('operation')} "
                f"(status={item.get('execution_status')}, runnable={str(bool(item.get('runnable'))).lower()})"
            )
        if not work_items:
            lines.append("- none")
    lines.extend(["", "## Delegation", ""])
    for request in plan.get("delegation_requests") or []:
        lines.append(f"- {request['role']}: {request['action']} — {request['reason']} ({request['request_id']})")
    for decision in plan.get("delegation_decisions") or []:
        lines.append(f"- {decision['role']}: {decision['reason']}")
    lines.append("")
    return "\n".join(lines)
