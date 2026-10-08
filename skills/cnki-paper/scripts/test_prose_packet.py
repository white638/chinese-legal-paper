#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import prose_packet


REGISTERED = {
    "CLM-12",
    "EVD-31",
    "EVD-42",
    "DESIGN-07",
    "SRC-09",
    "ETH-02",
    "RESP-03",
}


def canonical_result_record(
    result_id: str = "RES-001",
    *,
    claim_id: str = "CLM-12",
    allowed_use: str = "claim_support",
    text: str = "共享权限组与逐级审批组呈现已登记的响应差异。",
    artifact_sha256: str = "a" * 64,
    disposition: str = "retained",
) -> dict:
    return {
        "result_id": result_id,
        "run_id": "EXE-001",
        "run_status": "qualified",
        "status": "supported" if allowed_use == "claim_support" else "negative",
        "text": text,
        "type": "comparison",
        "claim_ids": [claim_id],
        "action_ids": ["ACT-001"],
        "artifact_ids": ["ART-001"],
        "claim_dispositions": {claim_id: disposition},
        "claim_allowed_uses": {claim_id: [allowed_use]},
        "allowed_uses": [allowed_use],
        "artifact_sha256": {"ART-001": artifact_sha256},
        "current_action_attempts": [
            {
                "action_id": "ACT-001",
                "operation_id": "STEP-MVMR-001",
                "attempt": 1,
                "status": "accepted",
                "parameter_snapshot_sha256": "b" * 64,
                "output_artifact_ids": ["ART-001"],
                "check_results": [{"id": "CHK-001", "status": "pass"}],
            }
        ],
        "numeric_values": [],
        "minimum_viable_run_status": "accepted",
        "authority_digest": "c" * 64,
    }


def canonical_claims(
    records: dict[str, dict], *, allowed_use: str = "claim_support"
) -> prose_packet.CanonicalResultClaims:
    values = {
        result_id: {
            claim_id
            for claim_id, uses in record.get("claim_allowed_uses", {}).items()
            if allowed_use in uses
        }
        for result_id, record in records.items()
        if allowed_use in record.get("allowed_uses", [])
    }
    values = {result_id: claim_ids for result_id, claim_ids in values.items() if claim_ids}
    return prose_packet.CanonicalResultClaims(
        values,
        authority={
            "schema_version": "cnki-method-downstream-eligibility/v1",
            "status": "PASS",
            "issues": [],
            "design_sha256": "d" * 64,
            "adapter_registry_sha256": "e" * 64,
            "execution_claim_ids": ["CLM-12"],
            "results": records,
        },
    )


def request() -> dict:
    return {
        "section_role": "results",
        "object": "同一平台下不同部门的响应差异",
        "claim": {
            "id": "CLM-12",
            "text": "平台效果取决于责任配置，而非接入本身",
            "strength": "associational",
        },
        "evidence_items": [
            {
                "id": "EVD-31",
                "text": "共享权限组的中位响应时间为 14 小时",
                "locator": "结果表 2，第 3 行",
                "citation_key": "local-results-table-2",
            },
            {
                "id": "EVD-42",
                "text": "逐级审批组的中位响应时间为 31 小时",
                "locator": "结果表 2，第 4 行",
            },
        ],
        "warrant": "共享权限改变了工单流转中的等待环节",
        "reader_update": "平台接入不能被直接等同于治理能力提升",
        "target_length": 220,
        "boundaries": [
            {
                "boundary_id": "B-01",
                "manuscript_action": "omit",
                "reason": "审稿人可能质疑，因此希望更全面",
            },
            {
                "boundary_id": "B-02",
                "anchor_type": "design",
                "anchor_id": "DESIGN-07",
                "materiality": "load_bearing",
                "claim_id": "CLM-12",
                "claim_delta": "causal -> associational",
                "manuscript_action": "state_once",
                "activation_reason": "横截面设计没有构造反事实，因而改变因果谓词",
                "full_statement_location": "results_after_claim",
                "statement": "横截面设计未构造反事实，因此该关系不支持因果效应判断。",
            },
        ],
        "countervoices": [],
    }


def semantic_request() -> dict:
    payload = request()
    payload["claim"] = {
        "id": "CLM-12",
        "text": "平台效果取决于责任配置，而非接入本身",
        "strength": "associational",
        "realization_mode": "semantic",
        "protected_atoms": {
            "subject": "责任配置",
            "relation": "响应时间",
            "direction": "conditional",
            "polarity": "affirmative",
            "inferential_strength": "associational",
            "scope": "同一平台内两个部门组",
            "protected_literals": ["责任配置"],
            "protected_numbers": ["14", "31"],
            "citation_anchors": ["local-results-table-2"],
        },
    }
    for item in payload["evidence_items"]:
        item["evidence_function"] = "compare response timing"
    payload.update(
        {
            "reader_question": "为何同一平台内不同部门的响应时间不同？",
            "plain_core": "责任配置差异解释同一平台内的响应时间差异",
            "explanation_path": [
                {
                    "order": 1,
                    "function": "claim",
                    "content": "责任配置与部门响应时间相关",
                    "anchor_id": "CLM-12",
                },
                {
                    "order": 2,
                    "function": "evidence_role",
                    "content": "两组中位响应时间形成对照",
                    "anchor_id": "EVD-31",
                },
                {
                    "order": 3,
                    "function": "warrant",
                    "content": "权限共享改变工单流转的等待环节",
                },
            ],
        }
    )
    return payload


def context_anchor() -> dict:
    return {
        "anchor_id": "ANCHOR-ARCHIVE-01",
        "authority_ref": "SRC-09",
        "type": "quotation",
        "locator": "档案卷 2，第 4 页",
        "exact_span": "权限共享仅改变等待环节",
        "original_problem": "平台接入是否足以改变治理能力",
        "logical_context": "该句限定权限共享所能解释的流程环节",
        "protected_qualifiers": ["仅"],
        "manuscript_function": "以来源声音限定机制解释的范围",
        "status": "content-verified",
    }


def valid_writer_draft() -> str:
    return (
        "平台效果取决于责任配置，而非接入本身。"
        "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
        "local-results-table-2），逐级审批组的中位响应时间为 31 小时"
        "（结果表 2，第 4 行）。"
        "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
    )


def valid_semantic_draft() -> str:
    return (
        "在同一平台内，责任配置使两组响应时间呈现差异。"
        "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
        "local-results-table-2），逐级审批组为 31 小时（结果表 2，第 4 行）。"
        "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
    )


def passing_semantic_review(
    packet: dict,
    draft: str,
    review_run_id: str = "SEM-0000000000000001",
) -> dict:
    packet_sha256, draft_sha256 = prose_packet.semantic_fidelity_digests(packet, draft)
    return {
        "schema_version": prose_packet.SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION,
        "review_run_id": review_run_id,
        "packet_sha256": packet_sha256,
        "draft_sha256": draft_sha256,
        "dimensions": {
            name: {
                "status": "PASS",
                "reason": f"The isolated comparison preserves {name} without semantic drift.",
            }
            for name in prose_packet.SEMANTIC_FIDELITY_DIMENSIONS
        },
        "overall_status": "PASS",
    }


def prepare_semantic_run(
    base: Path, packet: dict, draft: str, review_run_id: str
) -> tuple[Path, Path]:
    packet_path = base / "packet.json"
    draft_path = base / "draft.md"
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    draft_path.write_text(draft, encoding="utf-8")
    result = prose_packet.dispatch_semantic_fidelity_review(
        base,
        packet_path,
        draft_path,
        registered_ids=REGISTERED,
        writer_context_id="writer-context-001",
        clarity_context_id="clarity-context-001",
        review_run_id=review_run_id,
    )
    return base / Path(result["manifest"]), base / Path(result["review_output"])


def load_execution_v3_fixtures():
    scripts = Path(__file__).resolve().parents[2] / "empirical-research" / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "test_method_execution_v3.py"
    name = "prose_packet_method_execution_v3_fixtures"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load v3 execution fixtures from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class ProsePacketTests(unittest.TestCase):
    def test_compiler_filters_omitted_risks_and_emits_minimal_packet(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        self.assertEqual(prose_packet.SCHEMA_VERSION, packet["schema_version"])
        self.assertEqual(["B-02"], [item["id"] for item in packet["required_boundaries"]])
        self.assertEqual([], packet["material_countervoices"])
        self.assertEqual("EVD-31", packet["evidence_items"][0]["id"])
        self.assertIn("14 小时", packet["evidence_items"][0]["text"])
        self.assertNotIn("evidence_ids", packet)
        self.assertEqual("legacy_exact", packet["claim"]["realization_mode"])
        self.assertFalse(packet["expression_budget"]["semantic_fidelity_gate_required"])
        self.assertEqual(
            ["BRIDGE", "DEFINE"],
            packet["expression_budget"]["clarity_growth"]["positive_growth_actions"],
        )
        self.assertEqual(
            0,
            packet["expression_budget"]["claim_latency"]["max_sentences_before_claim"],
        )
        self.assertFalse(prose_packet.FORBIDDEN_PACKET_KEYS & set(packet))
        self.assertEqual([], prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED))

    def test_activated_boundary_requires_registered_material_anchor(self) -> None:
        payload = request()
        payload["boundaries"][1]["anchor_id"] = "DESIGN-999"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "not registered"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_evidence_payload_requires_registered_id_and_selected_text(self) -> None:
        payload = request()
        payload["evidence_items"][0]["id"] = "EVD-999"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "not registered"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

        payload = request()
        payload["evidence_items"][0]["text"] = ""
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "selected evidence"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_context_anchor_and_rhetorical_task_round_trip_in_v2_packet(self) -> None:
        payload = semantic_request()
        payload["evidence_items"][0]["text"] = "档案指出：“权限共享仅改变等待环节”。"
        payload["evidence_items"][0]["context_anchor"] = context_anchor()
        payload["rhetorical_task"] = {
            "argument_action": "DISTINGUISH",
            "problem_state_before": "平台接入似乎能够直接解释治理能力提升",
            "problem_state_after": "责任配置限定了平台接入能够改变的流程环节",
        }
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        self.assertEqual("DISTINGUISH", packet["rhetorical_task"]["argument_action"])
        self.assertEqual(
            "ANCHOR-ARCHIVE-01",
            packet["evidence_items"][0]["context_anchor"]["anchor_id"],
        )
        self.assertEqual([], prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED))

    def test_direct_quotation_requires_a_content_verified_context_anchor(self) -> None:
        payload = request()
        payload["evidence_items"][0]["text"] = "档案指出：“权限共享仅改变等待环节”。"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "AP.QUOTE.CONTEXT_MISSING"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

        payload["evidence_items"][0]["context_anchor"] = context_anchor()
        payload["evidence_items"][0]["context_anchor"]["locator"] = ""
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "AP.QUOTE.LOCATOR_MISSING"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_context_anchor_qualifiers_and_locator_are_deterministically_protected(self) -> None:
        payload = semantic_request()
        payload["evidence_items"][0]["text"] = "档案指出：“权限共享仅改变等待环节”。"
        payload["evidence_items"][0]["context_anchor"] = context_anchor()
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        draft = valid_semantic_draft() + "档案称权限共享改变等待环节。"
        issues = prose_packet.validate_draft_fidelity(
            packet,
            draft,
            registered_ids=REGISTERED,
        )
        self.assertTrue(any("AP.QUOTE.LOCATOR_MISSING" in issue for issue in issues))
        self.assertTrue(any("AP.QUOTE.QUALIFIER_LOSS" in issue for issue in issues))

    def test_cli_compile_binds_context_anchor_to_evidence_bank_projection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            payload = semantic_request()
            payload["evidence_items"][0]["text"] = "档案指出：“权限共享仅改变等待环节”。"
            payload["evidence_items"][0]["context_anchor"] = context_anchor()
            request_path = workspace / "request.json"
            request_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            (workspace / "research_design.json").write_text(
                json.dumps({"registered_ids": sorted(REGISTERED)}),
                encoding="utf-8",
            )
            (workspace / "evidence_bank.md").write_text(
                "| Anchor ID | Authority Ref | Type | Locator | Exact Span/Known Details | Original Problem | Logical Context | Protected Qualifiers | Manuscript Function | Status |\n"
                "|---|---|---|---|---|---|---|---|---|---|\n"
                "| ANCHOR-ARCHIVE-01 | SRC-09 | quotation | 档案卷 2，第 4 页 | 权限共享仅改变等待环节 | 平台接入是否足以改变治理能力 | 该句限定权限共享所能解释的流程环节 | 仅 | 以来源声音限定机制解释的范围 | content-verified |\n",
                encoding="utf-8",
            )
            argv = ["prose_packet.py", "compile", str(workspace), str(request_path)]
            with mock.patch.object(sys, "argv", argv), mock.patch("builtins.print"):
                self.assertEqual(0, prose_packet.main())

            payload["evidence_items"][0]["context_anchor"]["logical_context"] = "伪造的逻辑上下文"
            request_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8",
            )
            with mock.patch.object(sys, "argv", argv), mock.patch("builtins.print"):
                self.assertEqual(1, prose_packet.main())

    def test_rhetorical_task_must_record_a_real_problem_state_change(self) -> None:
        payload = semantic_request()
        payload["rhetorical_task"] = {
            "argument_action": "PRESS",
            "problem_state_before": "平台接入似乎能够直接解释治理能力提升",
            "problem_state_after": "平台接入似乎能够直接解释治理能力提升",
        }
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "AP.MOTION.NO_ADVANCE"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_evidence_payload_rejects_full_bank_or_audit_fields(self) -> None:
        payload = request()
        payload["evidence_items"][0]["audit_status"] = "PASS"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

        payload = request()
        payload["evidence_bank"] = [{"all": "workspace evidence"}]
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_draft_fidelity_protects_numbers_traceability_and_boundary_once(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        draft = (
            "平台效果取决于责任配置，而非接入本身。"
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
            "local-results-table-2），逐级审批组为 31 小时（结果表 2，第 4 行）。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
        )
        self.assertEqual(
            [],
            prose_packet.validate_draft_fidelity(
                packet, draft, registered_ids=REGISTERED
            ),
        )

        damaged = draft.replace("31 小时", "较长").replace(
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。", ""
        )
        issues = prose_packet.validate_draft_fidelity(
            packet, damaged, registered_ids=REGISTERED
        )
        self.assertTrue(any("protected number 31" in issue for issue in issues))
        self.assertTrue(any("boundary B-02" in issue for issue in issues))

    def test_draft_fidelity_rejects_control_plane_leak(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        draft = (
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
            "local-results-table-2），逐级审批组为 31 小时（结果表 2，第 4 行）。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
            "为避免误解，审稿人可能仍会质疑。"
        )
        issues = prose_packet.validate_draft_fidelity(
            packet, draft, registered_ids=REGISTERED
        )
        self.assertTrue(any("control-plane" in issue for issue in issues))
        for leak in (
            "根据评审意见补充如下。",
            "根据匿名评议意见调整该段。",
            "按第二轮意见补充如下。",
            "The referee requested this addition.",
            "Peer review suggested this addition.",
            "The editor asked us to add this sentence.",
        ):
            with self.subTest(leak=leak):
                issues = prose_packet.validate_draft_fidelity(
                    packet,
                    valid_writer_draft() + leak,
                    registered_ids=REGISTERED,
                )
                self.assertTrue(any("control-plane" in issue for issue in issues), issues)

    def test_draft_fidelity_enforces_claim_latency(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        delayed = (
            "首先交代一个与结果无关的背景句。"
            "平台效果取决于责任配置，而非接入本身。"
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
            "local-results-table-2），逐级审批组的中位响应时间为 31 小时"
            "（结果表 2，第 4 行）。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
        )
        issues = prose_packet.validate_draft_fidelity(
            packet, delayed, registered_ids=REGISTERED
        )
        self.assertTrue(any("claim latency" in issue for issue in issues))

    def test_draft_fidelity_rejects_boundary_before_claim(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        draft = (
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
            "平台效果取决于责任配置，而非接入本身。"
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
            "local-results-table-2），逐级审批组的中位响应时间为 31 小时"
            "（结果表 2，第 4 行）。"
        )
        issues = prose_packet.validate_draft_fidelity(
            packet, draft, registered_ids=REGISTERED
        )
        self.assertTrue(any("appears before" in issue for issue in issues))

    def test_packet_validation_rejects_any_expression_budget_tampering(self) -> None:
        for field, value in (
            ("semantic_fidelity_gate_required", True),
            ("untriggered_objection_sentences", 1),
            ("boundary_before_main_claim", 1),
            ("full_boundary_occurrences_per_id", 2),
            ("clarity_growth", {"positive_growth_actions": ["ADD"]}),
        ):
            with self.subTest(field=field):
                packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
                packet["expression_budget"][field] = value
                issues = prose_packet.validate_prose_packet(
                    packet, registered_ids=REGISTERED
                )
                self.assertTrue(any("canonical prose-cost" in issue for issue in issues))

    def test_callable_compression_gate_rejects_positive_net_growth(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        writer = (
            "平台效果取决于责任配置，而非接入本身。"
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；"
            "local-results-table-2），逐级审批组的中位响应时间为 31 小时"
            "（结果表 2，第 4 行）。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
        )
        self.assertEqual(
            [],
            prose_packet.validate_compression(
                packet, writer, writer, registered_ids=REGISTERED
            ),
        )
        expanded = writer + "这是一句没有新增证据的写作扩张。"
        issues = prose_packet.validate_compression(
            packet, writer, expanded, registered_ids=REGISTERED
        )
        self.assertTrue(any("net prose growth" in issue for issue in issues))

    def test_imagined_reviewer_cannot_activate_prose(self) -> None:
        payload = request()
        payload["boundaries"][1]["activation_reason"] = "审稿人可能质疑，保持谨慎"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "imagined objection"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_material_countervoice_is_conditional_and_source_bound(self) -> None:
        payload = request()
        payload["countervoices"] = [
            {
                "id": "CV-01",
                "source_ids": ["SRC-09"],
                "claim_id": "CLM-12",
                "materiality": "load_bearing",
                "same_result": True,
                "same_stage": True,
                "claim_delta": "single mechanism -> two compatible mechanisms",
                "manuscript_action": "state_once",
                "activation_reason": "该来源解释同一响应差异并改变机制归因",
                "position": "资源增量而非责任配置解释响应差异",
                "discriminating_evidence": "等待环节只在权限共享后消失",
                "full_statement_location": "discussion_after_evidence",
            }
        ]
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        self.assertEqual(["SRC-09"], packet["material_countervoices"][0]["source_ids"])

    def test_firewall_rejects_control_plane_context(self) -> None:
        payload = request()
        payload["gate_failures"] = ["audit incomplete"]
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_firewall_rejects_integration_caches_and_full_bibliography(self) -> None:
        for key in ("exa_manifest", "exa_run", "zotero_snapshot", "zotero_library", "references_bib"):
            with self.subTest(key=key):
                payload = request()
                payload[key] = {"external": "control-plane payload"}
                with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
                    prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_registered_id_discovery_uses_authoritative_support_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "reference_materials").mkdir()
            (workspace / "reference_materials" / "literature_registry.json").write_text(
                '{"source_id":"SRC-09"}', encoding="utf-8"
            )
            (workspace / "research_design.json").write_text(
                '{"design_id":"DESIGN-07","claim_id":"CLM-12"}', encoding="utf-8"
            )
            self.assertEqual(
                frozenset({"SRC-09", "DESIGN-07", "CLM-12"}),
                prose_packet.discover_registered_ids(workspace),
            )

    def test_incomplete_v3_execution_fails_closed_at_result_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            execution = {
                "schema_version": "cnki-method-execution/v3",
                "runs": [
                    {
                        "actions": [
                            {
                                "id": "ACT-001",
                                "status": "accepted",
                                "check_results": [{"id": "CHK-001", "status": "pass"}],
                                "result_ids": ["RES-001"],
                            },
                            {
                                "id": "ACT-002",
                                "status": "failed",
                                "check_results": [{"id": "CHK-002", "status": "fail"}],
                                "result_ids": ["RES-002"],
                            },
                        ],
                        "results": [
                            {
                                "id": "RES-001",
                                "claim_ids": ["CLM-12"],
                                "action_ids": ["ACT-001"],
                            },
                            {
                                "id": "RES-002",
                                "claim_ids": ["CLM-12"],
                                "action_ids": ["ACT-002"],
                            },
                        ],
                    }
                ],
            }
            (workspace / "method_execution.json").write_text(
                json.dumps(execution), encoding="utf-8"
            )
            accepted = prose_packet.discover_accepted_result_claims(workspace)
            self.assertEqual({}, accepted)
            registered = prose_packet.discover_registered_ids(workspace)
            self.assertNotIn("RES-001", registered)
            self.assertNotIn("RES-002", registered)

            payload = request()
            payload["result_ids"] = ["RES-001"]
            with self.assertRaisesRegex(prose_packet.ProsePacketError, "not registered"):
                prose_packet.compile_prose_packet(
                    payload,
                    registered_ids=REGISTERED | set(registered),
                    accepted_result_claims=accepted,
                )

    def test_canonical_projection_distinguishes_support_from_negative_reporting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "method_execution.json").write_text("{}", encoding="utf-8")
            projection = {
                "schema_version": "cnki-method-downstream-eligibility/v1",
                "status": "PASS",
                "issues": [],
                "design_sha256": "d" * 64,
                "adapter_registry_sha256": "e" * 64,
                "execution_claim_ids": ["CLM-12"],
                "results": {
                    "RES-001": {
                        "allowed_uses": ["claim_support", "result_report"],
                        "claim_dispositions": {"CLM-12": "retained"},
                        "claim_allowed_uses": {"CLM-12": ["claim_support"]},
                    },
                    "RES-NEG": {
                        "allowed_uses": ["negative_or_null_report"],
                        "claim_dispositions": {"CLM-12": "withdrawn"},
                        "claim_allowed_uses": {
                            "CLM-12": ["negative_or_null_report"]
                        },
                    },
                },
            }
            authority = mock.Mock()
            authority.downstream_eligibility.return_value = projection
            with mock.patch.object(
                prose_packet, "_method_execution_module", return_value=authority
            ):
                support = prose_packet.discover_accepted_result_claims(workspace)
                negative = prose_packet.discover_accepted_result_claims(
                    workspace, allowed_use="negative_or_null_report"
                )
                registered = prose_packet.discover_registered_ids(workspace)
            self.assertEqual({"RES-001": frozenset({"CLM-12"})}, support)
            self.assertEqual({"RES-NEG": frozenset({"CLM-12"})}, negative)
            self.assertEqual(frozenset({"RES-001", "RES-NEG"}), registered)

            negative_request = request()
            negative_request["result_ids"] = ["RES-NEG"]
            negative_request["result_use"] = "negative_or_null_report"
            packet = prose_packet.compile_prose_packet(
                negative_request,
                registered_ids=REGISTERED | set(registered),
                accepted_result_claims=negative,
            )
            self.assertEqual("negative_or_null_report", packet["result_use"])
            with self.assertRaisesRegex(
                prose_packet.ProsePacketError, "canonical execution eligibility"
            ):
                prose_packet.compile_prose_packet(
                    negative_request,
                    registered_ids=REGISTERED | set(registered),
                    accepted_result_claims=support,
                )

    def test_results_packet_requires_accepted_result_bound_to_same_claim(self) -> None:
        payload = request()
        payload["result_ids"] = ["RES-001"]
        registered = REGISTERED | {"RES-001"}
        accepted = canonical_claims({"RES-001": canonical_result_record()})
        packet = prose_packet.compile_prose_packet(
            payload,
            registered_ids=registered,
            accepted_result_claims=accepted,
        )
        self.assertEqual(["RES-001"], packet["result_ids"])
        self.assertEqual(
            [],
            prose_packet.validate_prose_packet(
                packet,
                registered_ids=registered,
                accepted_result_claims=accepted,
            ),
        )

        without_result = request()
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "require an eligible"):
            prose_packet.compile_prose_packet(
                without_result,
                registered_ids=registered,
                accepted_result_claims=accepted,
            )

        with self.assertRaisesRegex(prose_packet.ProsePacketError, "not bound"):
            wrong_claim = prose_packet.CanonicalResultClaims(
                {"RES-001": {"CLM-999"}}, authority=accepted.authority
            )
            prose_packet.compile_prose_packet(
                payload,
                registered_ids=registered,
                accepted_result_claims=wrong_claim,
            )

    def test_execution_claim_section_role_matrix_requires_selected_result(self) -> None:
        accepted = canonical_claims({"RES-001": canonical_result_record()})
        registered = REGISTERED | {"RES-001"}
        for role in ("abstract", "introduction", "results", "discussion", "conclusion"):
            with self.subTest(role=role):
                without_result = request()
                without_result["section_role"] = role
                with self.assertRaisesRegex(prose_packet.ProsePacketError, "eligible result_id"):
                    prose_packet.compile_prose_packet(
                        without_result,
                        registered_ids=registered,
                        accepted_result_claims=accepted,
                    )
                with_result = copy.deepcopy(without_result)
                with_result["result_ids"] = ["RES-001"]
                packet = prose_packet.compile_prose_packet(
                    with_result,
                    registered_ids=registered,
                    accepted_result_claims=accepted,
                )
                self.assertEqual(["RES-001"], packet["result_ids"])

        unknown = request()
        unknown["section_role"] = "custom_empirical_summary"
        unknown["result_ids"] = ["RES-001"]
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "unsupported section_role"):
            prose_packet.compile_prose_packet(
                unknown,
                registered_ids=registered,
                accepted_result_claims=accepted,
            )

    def test_non_execution_theory_claim_does_not_require_result(self) -> None:
        payload = request()
        payload["section_role"] = "theory"
        payload["claim"]["id"] = "CLM-THEORY"
        for boundary in payload["boundaries"]:
            if boundary.get("claim_id"):
                boundary["claim_id"] = "CLM-THEORY"
        authority = canonical_claims({"RES-001": canonical_result_record()}).authority
        accepted = prose_packet.CanonicalResultClaims({}, authority=authority)
        packet = prose_packet.compile_prose_packet(
            payload,
            registered_ids=REGISTERED | {"CLM-THEORY"},
            accepted_result_claims=accepted,
        )
        self.assertNotIn("result_ids", packet)

    def test_caller_built_result_map_cannot_mint_execution_authority(self) -> None:
        payload = request()
        payload["result_ids"] = ["RES-001"]
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "caller-built"):
            prose_packet.compile_prose_packet(
                payload,
                registered_ids=REGISTERED | {"RES-001"},
                accepted_result_claims={"RES-001": {"CLM-12"}},
            )

    def test_source_digest_rejects_tampering_and_selected_authority_drift(self) -> None:
        payload = request()
        payload["result_ids"] = ["RES-001"]
        registered = REGISTERED | {"RES-001"}
        records = {"RES-001": canonical_result_record()}
        accepted = canonical_claims(records)
        packet = prose_packet.compile_prose_packet(
            payload,
            registered_ids=registered,
            accepted_result_claims=accepted,
        )

        tampered = copy.deepcopy(packet)
        tampered["source_digest"] = "0" * 64
        self.assertTrue(
            any(
                "source_digest" in issue
                for issue in prose_packet.validate_prose_packet(
                    tampered,
                    registered_ids=registered,
                    accepted_result_claims=accepted,
                )
            )
        )

        for field, value in (
            ("text", "同一结果身份下，当前 canonical 结果文本已经改变。"),
            ("artifact_sha256", {"ART-001": "f" * 64}),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(records)
                changed["RES-001"][field] = value
                issues = prose_packet.validate_prose_packet(
                    packet,
                    registered_ids=registered,
                    accepted_result_claims=canonical_claims(changed),
                )
                self.assertTrue(any("source_digest" in issue for issue in issues), issues)

    def test_unrelated_result_change_does_not_invalidate_selected_packet(self) -> None:
        payload = request()
        payload["result_ids"] = ["RES-001"]
        records = {
            "RES-001": canonical_result_record(),
            "RES-OTHER": canonical_result_record(
                "RES-OTHER", text="未被本包选择的其他结果。"
            ),
        }
        registered = REGISTERED | set(records)
        packet = prose_packet.compile_prose_packet(
            payload,
            registered_ids=registered,
            accepted_result_claims=canonical_claims(records),
        )
        changed = copy.deepcopy(records)
        changed["RES-OTHER"]["text"] = "未选结果发生变化，不应误伤本包。"
        self.assertEqual(
            [],
            prose_packet.validate_prose_packet(
                packet,
                registered_ids=registered,
                accepted_result_claims=canonical_claims(changed),
            ),
        )

    def test_derived_markdown_cannot_register_claim_or_result_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "results_validation.md").write_text(
                "| Result ID | Claim ID |\n|---|---|\n| RES-FAKE | CLM-FAKE |\n",
                encoding="utf-8",
            )
            (workspace / "claim_register.md").write_text(
                "CLM-ALSO-FAKE", encoding="utf-8"
            )
            registered = prose_packet.discover_registered_ids(workspace)
            self.assertNotIn("RES-FAKE", registered)
            self.assertNotIn("CLM-FAKE", registered)
            self.assertNotIn("CLM-ALSO-FAKE", registered)

    def test_real_v4_v3_workspace_invalidates_packet_after_result_drift(self) -> None:
        fixtures = load_execution_v3_fixtures()
        temporary, workspace, _, execution = fixtures.v3_workspace()
        try:
            execution_path = workspace / "method_execution.json"
            execution_path.write_text(
                json.dumps(execution, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            accepted = prose_packet.discover_accepted_result_claims(workspace)
            self.assertIsInstance(accepted, prose_packet.CanonicalResultClaims)
            self.assertEqual("PASS", accepted.authority.get("status"))
            claim_id = execution["runs"][0]["claim_ids"][0]
            payload = request()
            payload["claim"]["id"] = claim_id
            payload["result_ids"] = ["RES-001"]
            for boundary in payload["boundaries"]:
                if boundary.get("claim_id"):
                    boundary["claim_id"] = claim_id
            registered = set(prose_packet.discover_registered_ids(workspace)) | REGISTERED
            registered.add(claim_id)
            packet = prose_packet.compile_prose_packet(
                payload,
                registered_ids=registered,
                accepted_result_claims=accepted,
            )

            changed = copy.deepcopy(execution)
            changed["runs"][0]["results"][0]["text"] = (
                "同一 RES 身份下的当前 canonical 结果文本已经改变。"
            )
            execution_path.write_text(
                json.dumps(changed, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            current = prose_packet.discover_accepted_result_claims(workspace)
            self.assertEqual("PASS", current.authority.get("status"))
            issues = prose_packet.validate_prose_packet(
                packet,
                registered_ids=registered,
                accepted_result_claims=current,
            )
            self.assertTrue(any("source_digest" in issue for issue in issues), issues)
        finally:
            temporary.cleanup()

    def test_semantic_claim_may_be_reworded_but_protected_items_are_exact(self) -> None:
        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        self.assertEqual("semantic", packet["claim"]["realization_mode"])
        self.assertTrue(packet["expression_budget"]["semantic_fidelity_gate_required"])
        draft = valid_semantic_draft()
        self.assertNotIn(packet["claim"]["text"], draft)
        self.assertEqual(
            [], prose_packet.validate_draft_fidelity(packet, draft, registered_ids=REGISTERED)
        )
        damaged = draft.replace("责任配置", "部门安排").replace("31 小时", "较长").replace(
            "local-results-table-2", ""
        )
        issues = prose_packet.validate_draft_fidelity(
            packet, damaged, registered_ids=REGISTERED
        )
        self.assertTrue(any("protected literal" in issue for issue in issues))
        self.assertTrue(any("protected claim number" in issue for issue in issues))
        self.assertTrue(any("citation" in issue for issue in issues))

    def test_new_explicit_modes_have_functional_order_without_sentence_caps(self) -> None:
        for mode in ("semantic", "verbatim"):
            for role in ("abstract", "introduction", "results", "discussion", "conclusion"):
                with self.subTest(mode=mode, role=role):
                    payload = semantic_request() if mode == "semantic" else request()
                    payload["section_role"] = role
                    if mode == "verbatim":
                        payload["claim"].update(realization_mode="verbatim", verbatim_reason="user_locked")
                    packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
                    budget = packet["expression_budget"]
                    self.assertEqual("argument_function", budget["surface_order_policy"])
                    self.assertIsNone(budget["claim_latency"]["max_sentences_before_claim"])
                    self.assertIsNone(budget["boundary_before_main_claim"])
                    self.assertEqual(mode == "verbatim", budget["claim_latency"]["exact_claim_text_required"])
                    self.assertEqual(mode == "semantic", budget["semantic_fidelity_gate_required"])
                    self.assertEqual([], prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED))

    def test_new_semantic_material_first_and_long_reasoning_keep_protected_facts(self) -> None:
        payload = semantic_request()
        # Argument dependencies may be registered in an evidence-first order.
        steps = payload["explanation_path"]
        payload["explanation_path"] = [steps[1], steps[2], steps[0]]
        for number, step in enumerate(payload["explanation_path"], start=1):
            step["order"] = number
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        draft = (
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；local-results-table-2）。"
            "逐级审批组的中位响应时间为 31 小时（结果表 2，第 4 行）。"
            "两组中位响应时间形成对照。共享权限改变了工单流转中的等待环节。"
            "同一平台内两个部门组的责任配置与响应时间存在关联。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
        )
        self.assertEqual("evidence_role", packet["explanation_path"][0]["function"])
        self.assertEqual([], prose_packet.validate_draft_fidelity(packet, draft, registered_ids=REGISTERED))
        damaged = draft.replace("31 小时", "较长时间")
        self.assertTrue(any("protected" in issue for issue in prose_packet.validate_draft_fidelity(
            packet, damaged, registered_ids=REGISTERED)))
        # Flexible order does not turn deterministic fidelity into semantic assurance.
        self.assertTrue(packet["expression_budget"]["semantic_fidelity_gate_required"])

    def test_new_verbatim_preserves_exact_words_without_forcing_them_first(self) -> None:
        payload = request()
        payload["claim"].update(realization_mode="verbatim", verbatim_reason="user_locked")
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        draft = (
            "共享权限组的中位响应时间为 14 小时（结果表 2，第 3 行；local-results-table-2）。"
            "逐级审批组的中位响应时间为 31 小时（结果表 2，第 4 行）。"
            "共享权限改变了工单流转中的等待环节。"
            "平台效果取决于责任配置，而非接入本身。"
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。"
        )
        self.assertEqual([], prose_packet.validate_draft_fidelity(packet, draft, registered_ids=REGISTERED))
        damaged = draft.replace("平台效果取决于责任配置，而非接入本身", "责任配置影响平台效果")
        self.assertTrue(any("claim text is missing" in issue for issue in prose_packet.validate_draft_fidelity(
            packet, damaged, registered_ids=REGISTERED)))
        historical = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED, _legacy_surface_order=True)
        self.assertTrue(any("claim latency" in issue for issue in prose_packet.validate_draft_fidelity(
            historical, draft, registered_ids=REGISTERED)))

    def test_new_boundary_order_follows_registered_location_and_preserves_full_statement(self) -> None:
        payload = semantic_request()
        payload["boundaries"][1]["full_statement_location"] = "at_materiality_point"
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        boundary = packet["required_boundaries"][0]["statement"]
        body = valid_semantic_draft().replace(boundary, "")
        before = boundary + body
        self.assertEqual([], prose_packet.validate_draft_fidelity(packet, before, registered_ids=REGISTERED))
        for damaged in (body, boundary + before):
            self.assertTrue(any("exactly once" in issue for issue in prose_packet.validate_draft_fidelity(
                packet, damaged, registered_ids=REGISTERED)))
        for location, draft, expected_issue in (
            ("results_after_claim", before, "appears before"),
            ("results_before_claim", body + boundary, "must precede"),
        ):
            with self.subTest(location=location):
                payload["boundaries"][1]["full_statement_location"] = location
                current = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
                self.assertTrue(any(expected_issue in issue for issue in prose_packet.validate_draft_fidelity(
                    current, draft, registered_ids=REGISTERED)))
        payload["boundaries"][1]["full_statement_location"] = "results_before_claim"
        current = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        self.assertEqual([], prose_packet.validate_draft_fidelity(current, before, registered_ids=REGISTERED))

    def test_historical_v2_budgets_and_digests_remain_byte_stable_on_read(self) -> None:
        # Captured from the unmodified compiler before functional ordering was added.
        golden = {
            "semantic": ("df602b231bb9974193ce60b53c57ab23a346b48193dcf2f6207d6c80ae1990af", "29c9608fad54c4d6d7496791762a9506d15786a882347519b85d1a63d1e1d1b6"),
            "verbatim": ("545b90adb26be171b1109abc43fba88dbf67bf0fc1749edb31f15a9d875d43c3", "4a595f2eb2ad44e6050ea234c1d40df18bfb24d47031430888dd969540a3888a"),
            "legacy_exact": ("dc17d878794c2e65086293b58674c9012a7b4bf2fdf261464e8cb7b3d1ca04e4", "2ba3f7845ef4eb7aaad42c45290ac94593c689dc973d30cfd1b3c482f9ce72b7"),
        }
        for mode, (source_digest, json_digest) in golden.items():
            with self.subTest(mode=mode):
                payload = semantic_request() if mode == "semantic" else request()
                if mode == "verbatim":
                    payload["claim"].update(realization_mode="verbatim", verbatim_reason="user_locked")
                packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED, _legacy_surface_order=True)
                original = json.dumps(packet, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                self.assertEqual(source_digest, packet["source_digest"])
                self.assertEqual(json_digest, hashlib.sha256(original.encode("utf-8")).hexdigest())
                self.assertNotIn("surface_order_policy", packet["expression_budget"])
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / "historic-packet.json"
                    path.write_text(original, encoding="utf-8")
                    before = path.read_bytes()
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual([], prose_packet.validate_prose_packet(loaded, registered_ids=REGISTERED))
                    self.assertEqual(before, path.read_bytes())
                    self.assertEqual(packet, loaded)
                if mode == "legacy_exact":
                    self.assertEqual(packet, prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED))

    def test_new_surface_order_marker_cannot_authorize_arbitrary_budget_or_digest(self) -> None:
        mutations = (
            lambda budget: budget.update(surface_order_policy="arbitrary"),
            lambda budget: budget.pop("surface_order_policy"),
            lambda budget: budget["claim_latency"].update(max_sentences_before_claim=100),
            lambda budget: budget["claim_latency"].update(exact_claim_text_required=True),
            lambda budget: budget.update(boundary_before_main_claim=50),
            lambda budget: budget.update(full_boundary_occurrences_per_id=0),
            lambda budget: budget.update(semantic_fidelity_gate_required=False),
        )
        for mutate in mutations:
            packet = prose_packet.compile_prose_packet(semantic_request(), registered_ids=REGISTERED)
            mutate(packet["expression_budget"])
            # Even a recalculated outer digest cannot bless a noncanonical budget.
            packet["source_digest"] = prose_packet._packet_source_digest(packet, {})
            issues = prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED)
            self.assertTrue(any("canonical prose-cost" in issue for issue in issues), issues)
        historical = prose_packet.compile_prose_packet(semantic_request(), registered_ids=REGISTERED, _legacy_surface_order=True)
        historical["expression_budget"] = prose_packet.canonical_expression_budget("results", "semantic")
        self.assertTrue(any("source_digest" in issue for issue in prose_packet.validate_prose_packet(
            historical, registered_ids=REGISTERED)))

    def test_verbatim_budget_cannot_disable_literal_preservation(self) -> None:
        payload = request()
        payload["claim"].update(realization_mode="verbatim", verbatim_reason="user_locked")
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        packet["expression_budget"]["claim_latency"]["exact_claim_text_required"] = False
        packet["source_digest"] = prose_packet._packet_source_digest(packet, {})
        self.assertTrue(any("canonical prose-cost" in issue for issue in prose_packet.validate_prose_packet(
            packet, registered_ids=REGISTERED)))

    def test_historical_v2_semantic_assurance_reads_without_packet_migration(self) -> None:
        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED, _legacy_surface_order=True)
        draft = valid_semantic_draft()
        run_id = "SEM-0000000000000017"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dispatch, review_path = prepare_semantic_run(base, packet, draft, run_id)
            review_path.write_text(json.dumps(passing_semantic_review(packet, draft, run_id), ensure_ascii=False), encoding="utf-8")
            result = prose_packet.create_semantic_fidelity_assurance(
                base, dispatch, reviewer_context_id="historic-independent-context")
            assurance = base / result["assurance"]
            frozen = {path: path.read_bytes() for path in (base / "packet.json", dispatch, review_path, assurance)}
            self.assertEqual([], prose_packet.validate_semantic_fidelity_review(
                base, dispatch, assurance, registered_ids=REGISTERED))
            self.assertTrue(all(path.read_bytes() == contents for path, contents in frozen.items()))

    def test_semantic_fidelity_review_is_digest_bound_and_bidirectional(self) -> None:
        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        draft = valid_semantic_draft()
        run_id = "SEM-0000000000000001"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest_path, review_path = prepare_semantic_run(
                base, packet, draft, run_id
            )
            review = passing_semantic_review(packet, draft, run_id)
            review_path.write_text(
                json.dumps(review, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            assurance_result = prose_packet.create_semantic_fidelity_assurance(
                base,
                manifest_path,
                reviewer_context_id="semantic-reviewer-context-001",
            )
            assurance_path = base / Path(assurance_result["assurance"])
            self.assertEqual(
                [],
                prose_packet.validate_semantic_fidelity_review(
                    base,
                    manifest_path,
                    assurance_path,
                    registered_ids=REGISTERED,
                ),
            )

            stale = copy.deepcopy(review)
            stale["draft_sha256"] = "0" * 64
            review_path.write_text(
                json.dumps(stale, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            issues = prose_packet.validate_semantic_fidelity_review(
                base, manifest_path, assurance_path, registered_ids=REGISTERED
            )
            self.assertTrue(any("raw review output" in issue for issue in issues))
            self.assertTrue(any("draft_sha256" in issue for issue in issues))

            one_way_only = copy.deepcopy(review)
            one_way_only["dimensions"]["draft_to_canonical"]["status"] = "FAIL"
            review_path.write_text(
                json.dumps(one_way_only, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            issues = prose_packet.validate_semantic_fidelity_review(
                base, manifest_path, assurance_path, registered_ids=REGISTERED
            )
            self.assertTrue(any("draft_to_canonical" in issue for issue in issues))

    def test_semantic_fidelity_review_rejects_exact_mode_and_incomplete_receipt(self) -> None:
        exact_packet = prose_packet.compile_prose_packet(
            request(), registered_ids=REGISTERED
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(prose_packet.ProsePacketError, "semantic packet"):
                prepare_semantic_run(
                    Path(tmp),
                    exact_packet,
                    valid_writer_draft(),
                    "SEM-0000000000000002",
                )

        semantic_packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        run_id = "SEM-0000000000000003"
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            manifest_path, review_path = prepare_semantic_run(
                base, semantic_packet, valid_semantic_draft(), run_id
            )
            incomplete = passing_semantic_review(
                semantic_packet, valid_semantic_draft(), run_id
            )
            incomplete["dimensions"].pop("scope")
            review_path.write_text(
                json.dumps(incomplete, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            assurance_result = prose_packet.create_semantic_fidelity_assurance(
                base,
                manifest_path,
                reviewer_context_id="semantic-reviewer-context-003",
            )
            issues = prose_packet.validate_semantic_fidelity_review(
                base,
                manifest_path,
                base / Path(assurance_result["assurance"]),
                registered_ids=REGISTERED,
            )
            self.assertTrue(any("missing dimensions" in issue for issue in issues))

    def test_semantic_dispatch_rejects_causal_strengthening_and_reused_context(self) -> None:
        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        strengthened = valid_semantic_draft().replace(
            "责任配置使两组响应时间呈现差异",
            "责任配置直接导致两组响应时间呈现差异",
        )
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(prose_packet.ProsePacketError, "causal assertion"):
                prepare_semantic_run(
                    Path(tmp), packet, strengthened, "SEM-0000000000000004"
                )

        appended_strengthening = (
            valid_semantic_draft() + "责任配置直接导致响应时间下降。"
        )
        self.assertTrue(
            any(
                "causal assertion" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    packet, appended_strengthening, registered_ids=REGISTERED
                )
            )
        )
        negated_boundary = valid_semantic_draft().replace(
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。",
            "责任配置与响应时间不能据此被证明为因果关系。",
        )
        self.assertFalse(
            any(
                "causal assertion" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    packet, negated_boundary, registered_ids=REGISTERED
                )
            )
        )
        no_evidence_boundary = valid_semantic_draft().replace(
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。",
            "没有证据证明责任配置导致响应时间差异。",
        )
        self.assertFalse(
            any(
                "causal assertion" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    packet, no_evidence_boundary, registered_ids=REGISTERED
                )
            )
        )
        governed_no_evidence_boundary = valid_semantic_draft().replace(
            "横截面设计未构造反事实，因此该关系不支持因果效应判断。",
            "尚无证据表明责任配置导致响应时间差异。",
        )
        self.assertFalse(
            any(
                "causal assertion" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    packet,
                    governed_no_evidence_boundary,
                    registered_ids=REGISTERED,
                )
            )
        )
        adversarial_turn = (
            valid_semantic_draft() + "没有证据但责任配置直接导致响应时间下降。"
        )
        self.assertTrue(
            any(
                "causal assertion" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    packet, adversarial_turn, registered_ids=REGISTERED
                )
            )
        )
        for double_negative in (
            "责任配置不能不导致响应时间下降。",
            "责任配置不得不导致响应时间下降。",
            "责任配置并非不会导致响应时间下降。",
            "责任配置 cannot not cause 响应时间下降。",
        ):
            with self.subTest(double_negative=double_negative):
                issues = prose_packet.validate_draft_fidelity(
                    packet,
                    valid_semantic_draft() + double_negative,
                    registered_ids=REGISTERED,
                )
                self.assertTrue(
                    any("causal assertion" in issue for issue in issues),
                    issues,
                )

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            run_id = "SEM-0000000000000005"
            manifest_path, review_path = prepare_semantic_run(
                base, packet, valid_semantic_draft(), run_id
            )
            review_path.write_text(
                json.dumps(
                    passing_semantic_review(packet, valid_semantic_draft(), run_id),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(prose_packet.ProsePacketError, "distinct"):
                prose_packet.create_semantic_fidelity_assurance(
                    base,
                    manifest_path,
                    reviewer_context_id="writer-context-001",
                )

    def test_protected_numbers_and_citation_keys_require_exact_tokens(self) -> None:
        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        for number, citation in (
            ("314", "local-results-table-20"),
            ("14%", "local-results-table-2/supp"),
            ("314", "LOCAL-RESULTS-TABLE-2"),
        ):
            with self.subTest(number=number, citation=citation):
                widened = valid_semantic_draft().replace("14", number, 1).replace(
                    "local-results-table-2", citation
                )
                issues = prose_packet.validate_draft_fidelity(
                    packet, widened, registered_ids=REGISTERED
                )
                self.assertTrue(any("number" in issue and "14" in issue for issue in issues))
                self.assertTrue(any("citation" in issue for issue in issues))

        payload = semantic_request()
        payload["claim"]["protected_atoms"]["protected_literals"].append("GovTech")
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        issues = prose_packet.validate_draft_fidelity(
            packet,
            valid_semantic_draft() + " govtech",
            registered_ids=REGISTERED,
        )
        self.assertTrue(any("protected literal" in issue for issue in issues))

    def test_verbatim_claim_requires_allowed_reason_and_exact_text(self) -> None:
        payload = request()
        payload["claim"]["realization_mode"] = "verbatim"
        payload["claim"]["verbatim_reason"] = "direct_quote"
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        issues = prose_packet.validate_draft_fidelity(
            packet,
            valid_writer_draft().replace(
                "平台效果取决于责任配置，而非接入本身", "责任配置影响平台效果"
            ),
            registered_ids=REGISTERED,
        )
        self.assertTrue(any("claim text is missing" in issue for issue in issues))
        english = request()
        english["claim"].update(
            {
                "text": "Direct Quotation Must Keep Case",
                "realization_mode": "verbatim",
                "verbatim_reason": "direct_quote",
            }
        )
        packet = prose_packet.compile_prose_packet(english, registered_ids=REGISTERED)
        issues = prose_packet.validate_draft_fidelity(
            packet,
            valid_writer_draft().replace(
                "平台效果取决于责任配置，而非接入本身",
                "direct quotation must keep case",
            ),
            registered_ids=REGISTERED,
        )
        self.assertTrue(any("claim text is missing" in issue for issue in issues))
        payload["claim"]["verbatim_reason"] = "style_preference"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "verbatim_reason"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_semantic_claim_rejects_invalid_atoms_and_unregistered_citation_anchor(self) -> None:
        for field, value, message in (
            ("polarity", "uncertain", "polarity"),
            ("direction", "", "direction"),
            ("scope", "all", "bounded scope"),
            ("citation_anchors", ["not-selected"], "not registered"),
        ):
            with self.subTest(field=field):
                payload = semantic_request()
                payload["claim"]["protected_atoms"][field] = value
                with self.assertRaisesRegex(prose_packet.ProsePacketError, message):
                    prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_semantic_reader_fields_and_ordered_explanation_path_are_required(self) -> None:
        for mutation, message in (
            (lambda value: value.pop("reader_question"), "reader_question"),
            (
                lambda value: value["explanation_path"][1].update({"order": 3}),
                "consecutive",
            ),
            (
                lambda value: value["explanation_path"][1].update(
                    {"function": "answer_reviewer"}
                ),
                "function",
            ),
            (
                lambda value: value["evidence_items"][0].pop("evidence_function"),
                "evidence_function",
            ),
        ):
            payload = semantic_request()
            mutation(payload)
            with self.assertRaisesRegex(prose_packet.ProsePacketError, message):
                prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_recursive_firewall_rejects_nested_reviewer_metadata_in_request_and_packet(self) -> None:
        payload = semantic_request()
        payload["claim"]["reviewer_comment"] = "Please hedge this claim"
        with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
            prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

        packet = prose_packet.compile_prose_packet(
            semantic_request(), registered_ids=REGISTERED
        )
        packet["required_boundaries"][0]["reviewer_note"] = "requested in round two"
        issues = prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED)
        self.assertTrue(any("prose firewall" in issue for issue in issues))

        for leaked in (
            "workflow_status PASS 后再显化这一解释",
            "avereth-prose-packet/v2 已经通过",
            ".avereth-prose/prose_packet.json 已生成",
            "Materiality Compiler says PASS",
        ):
            with self.subTest(leaked=leaked):
                payload = semantic_request()
                payload["warrant"] = leaked
                with self.assertRaisesRegex(prose_packet.ProsePacketError, "prose firewall"):
                    prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

    def test_boundary_legacy_action_maps_to_preferred_realization(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        boundary = packet["required_boundaries"][0]
        self.assertEqual("single_full_statement", boundary["action"])
        self.assertEqual("single_full_statement", boundary["preferred_realization"])

    def test_legacy_v1_packet_remains_exact_and_validation_readable(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        legacy = copy.deepcopy(packet)
        legacy["schema_version"] = prose_packet.LEGACY_SCHEMA_VERSION
        legacy["claim"] = {
            "id": legacy["claim"]["id"],
            "text": legacy["claim"]["text"],
            "strength": legacy["claim"]["strength"],
        }
        legacy.pop("reader_question")
        legacy.pop("plain_core")
        legacy.pop("explanation_path")
        for item in legacy["evidence_items"]:
            item.pop("evidence_function", None)
        for boundary in legacy["required_boundaries"]:
            boundary["action"] = "state_once"
            boundary.pop("preferred_realization", None)
        legacy["expression_budget"] = prose_packet.legacy_expression_budget("results")
        self.assertEqual([], prose_packet.validate_prose_packet(legacy, registered_ids=REGISTERED))
        missing_claim = valid_writer_draft().replace(
            "平台效果取决于责任配置，而非接入本身", "责任配置影响平台效果"
        )
        self.assertTrue(
            any(
                "claim text is missing" in issue
                for issue in prose_packet.validate_draft_fidelity(
                    legacy, missing_claim, registered_ids=REGISTERED
                )
            )
        )

    def test_clarity_positive_growth_requires_grounded_bridge_or_define_ledger(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        writer = valid_writer_draft()
        edited = writer + "这组差异由权限共享减少流转等待环节来解释。"
        delta = prose_packet.prose_units(edited) - prose_packet.prose_units(writer)
        ledger = {
            "schema_version": prose_packet.CLARITY_LEDGER_SCHEMA_VERSION,
            "scope": "paragraph",
            "actions": [
                {
                    "action": "BRIDGE",
                    "prose_delta": delta,
                    "claim_id": "CLM-12",
                    "source_kind": "warrant",
                    "source_anchor": "warrant",
                    "reader_understanding": "读者能够连接响应差异与等待环节",
                    "no_new_fact": True,
                    "no_new_citation": True,
                    "no_inference_strengthening": True,
                }
            ],
        }
        result = prose_packet.check_clarity(
            packet, writer, edited, ledger, registered_ids=REGISTERED
        )
        self.assertTrue(result.ok, result.issues)
        self.assertTrue(result.warnings)

        invalid = copy.deepcopy(ledger)
        invalid["actions"][0]["action"] = "REPLACE"
        issues = prose_packet.validate_clarity(
            packet, writer, edited, invalid, registered_ids=REGISTERED
        )
        self.assertTrue(any("only BRIDGE or DEFINE" in issue for issue in issues))

        mismatch = copy.deepcopy(ledger)
        mismatch["actions"][0]["prose_delta"] = delta - 1
        issues = prose_packet.validate_clarity(
            packet, writer, edited, mismatch, registered_ids=REGISTERED
        )
        self.assertTrue(any("does not match actual delta" in issue for issue in issues))

    def test_clarity_positive_growth_without_ledger_fails_but_soft_ratio_does_not(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        writer = valid_writer_draft()
        edited = writer + "这一连接帮助读者理解责任配置为何改变等待环节。"
        issues = prose_packet.validate_clarity(
            packet, writer, edited, None, registered_ids=REGISTERED
        )
        self.assertTrue(any("without a valid ledger" in issue for issue in issues))

    def test_clarity_growth_soft_limits_are_configurable_diagnostics(self) -> None:
        payload = request()
        payload["clarity_growth_soft_limits"] = {
            "section_ratio": 0.50,
            "paragraph_ratio": 0.75,
        }
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        growth_budget = packet["expression_budget"]["clarity_growth"]
        self.assertEqual(0.50, growth_budget["section_soft_ratio"])
        self.assertEqual(0.75, growth_budget["paragraph_soft_ratio"])
        self.assertEqual(
            [], prose_packet.validate_prose_packet(packet, registered_ids=REGISTERED)
        )

        writer = valid_writer_draft()
        edited = writer + "这组差异由权限共享减少流转等待环节来解释。"
        delta = prose_packet.prose_units(edited) - prose_packet.prose_units(writer)
        ledger = {
            "schema_version": prose_packet.CLARITY_LEDGER_SCHEMA_VERSION,
            "scope": "paragraph",
            "actions": [
                {
                    "action": "BRIDGE",
                    "prose_delta": delta,
                    "claim_id": "CLM-12",
                    "source_kind": "warrant",
                    "source_anchor": "warrant",
                    "reader_understanding": "读者能够连接响应差异与等待环节",
                    "no_new_fact": True,
                    "no_new_citation": True,
                    "no_inference_strengthening": True,
                }
            ],
        }
        result = prose_packet.check_clarity(
            packet, writer, edited, ledger, registered_ids=REGISTERED
        )
        self.assertTrue(result.ok, result.issues)
        self.assertEqual((), result.warnings)

    def test_clarity_growth_soft_limits_reject_malformed_configuration(self) -> None:
        invalid_limits = (
            {"section_ratio": 0.05},
            {"section_ratio": True, "paragraph_ratio": 0.15},
            {"section_ratio": 0.40, "paragraph_ratio": 0.30},
        )
        for limits in invalid_limits:
            with self.subTest(limits=limits):
                payload = request()
                payload["clarity_growth_soft_limits"] = limits
                with self.assertRaises(prose_packet.ProsePacketError):
                    prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)

        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        packet["expression_budget"]["clarity_growth"]["paragraph_soft_ratio"] = 0
        self.assertTrue(
            any(
                "paragraph_ratio" in issue
                for issue in prose_packet.validate_prose_packet(
                    packet, registered_ids=REGISTERED
                )
            )
        )

    def test_clarity_ledger_cannot_self_certify_new_numbers_citations_or_quotes(self) -> None:
        packet = prose_packet.compile_prose_packet(request(), registered_ids=REGISTERED)
        writer = valid_writer_draft()
        edited = writer + r"另一个未登记样本报告 99 小时 \cite{fabricated}，并称其为“新机制”。"
        delta = prose_packet.prose_units(edited) - prose_packet.prose_units(writer)
        ledger = {
            "schema_version": prose_packet.CLARITY_LEDGER_SCHEMA_VERSION,
            "scope": "paragraph",
            "actions": [
                {
                    "action": "BRIDGE",
                    "prose_delta": delta,
                    "claim_id": "CLM-12",
                    "source_kind": "warrant",
                    "source_anchor": "warrant",
                    "reader_understanding": "读者能够连接响应差异与等待环节",
                    "no_new_fact": True,
                    "no_new_citation": True,
                    "no_inference_strengthening": True,
                }
            ],
        }
        result = prose_packet.check_clarity(
            packet, writer, edited, ledger, registered_ids=REGISTERED
        )
        self.assertFalse(result.ok)
        self.assertTrue(any("number(s)" in issue and "99" in issue for issue in result.issues))
        self.assertTrue(any("citation-like" in issue for issue in result.issues))
        self.assertTrue(any("quotation(s)" in issue for issue in result.issues))

    def test_clarity_delta_preserves_literal_citation_and_quotation_identity(self) -> None:
        cases = (
            (r"Prior \cite{Known}.", r"Prior \cite{Known}. Added \cite{KNOWN}.", "citation-like"),
            ("Prior [@Known].", "Prior [@Known]. Added [@KNOWN].", "citation-like"),
            ("Prior prose.", "Prior prose. @fabricated argues this.", "citation-like"),
            ("There was 1 group.", "There was 1 group [1].", "citation-like"),
            ("Prior prose.", "Prior prose [Smith 2020].", "citation-like"),
            ("Prior prose.", r"Prior prose. \parencite{fabricated}.", "citation-like"),
            ("Prior prose.", r"Prior prose. \Parencite{fabricated}.", "citation-like"),
            ("Prior prose.", r"Prior prose. \textcite{fabricated}.", "citation-like"),
            ("Prior prose.", r"Prior prose. \nocite{fabricated}.", "citation-like"),
            ("Prior prose.", r"Prior prose. \pvolcite{fabricated}.", "citation-like"),
            ("Prior prose.", "Prior prose. ‘new mechanism’", "quotation(s)"),
            ("new mechanism", "‘new mechanism’", "quotation(s)"),
            ("Prior prose.", "Prior prose.\n> new mechanism", "quotation(s)"),
        )
        for writer, edited, expected in cases:
            with self.subTest(edited=edited):
                issues = prose_packet.validate_clarity_delta_content(writer, edited)
                self.assertTrue(any(expected in issue for issue in issues), issues)

    def test_positive_scope_boundary_statement_is_enforced_once_after_claim(self) -> None:
        payload = request()
        payload["boundaries"][1]["manuscript_action"] = "positive_scope"
        packet = prose_packet.compile_prose_packet(payload, registered_ids=REGISTERED)
        statement = packet["required_boundaries"][0]["statement"]
        self.assertTrue(packet["required_boundaries"][0]["full_statement_once"])
        self.assertEqual(
            [],
            prose_packet.validate_draft_fidelity(
                packet, valid_writer_draft(), registered_ids=REGISTERED
            ),
        )
        duplicated = valid_writer_draft() + statement
        issues = prose_packet.validate_draft_fidelity(
            packet, duplicated, registered_ids=REGISTERED
        )
        self.assertTrue(any("exactly once; found 2" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
