#!/usr/bin/env python3
"""Runtime-backed adversarial evals for topic-portfolio divergence."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parents[1]
SCRIPTS_DIR = REPO_ROOT / "skills" / "cnki-paper" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import research_decision as rd  # noqa: E402
import test_research_decision as rd_fixtures  # noqa: E402
import topic_packet as topic_packet_runtime  # noqa: E402


INTAKE_WIZARD = SCRIPTS_DIR / "avereth_core" / "tools" / "intake_wizard.py"
TOPIC_PACKET = SCRIPTS_DIR / "topic_packet.py"
RESEARCH_DECISION = SCRIPTS_DIR / "research_decision.py"
TOPIC_PACKET_TESTS = SCRIPTS_DIR / "test_topic_packet.py"
CASES = EVAL_DIR / "cases.json"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class TopicPortfolioRuntimeEvals(unittest.TestCase):
    maxDiff = None

    def _run(
        self,
        *args: object,
        expected: int = 0,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, *(str(item) for item in args)],
            cwd=REPO_ROOT,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
            env=env,
        )
        self.assertEqual(
            expected,
            completed.returncode,
            f"command failed: {completed.args}\nstdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        return completed

    def _scheduler_seal(
        self,
        packet: dict[str, Any],
        seeds: list[dict[str, Any]],
        *,
        lane_id: str,
        run_id: str,
        context_id: str,
        dispatched_at: str,
        issued_at: str,
        sealed_at: str,
        key_store_path: Path,
        workspace_root: Path | None = None,
    ) -> dict[str, Any]:
        observed_inputs: list[dict[str, Any]] = []

        def runner(runner_input: object) -> str:
            self.assertIsInstance(runner_input, dict)
            assert isinstance(runner_input, dict)
            observed_inputs.append(copy.deepcopy(runner_input))
            return json.dumps(seeds, ensure_ascii=False)

        key_store = topic_packet_runtime.TopicSchedulerKeyStore(key_store_path)
        scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
            packet,
            test_capture=runner,
            key_store=key_store,
            workspace_root=workspace_root,
            test_run_id=run_id,
            test_model_revision="topic-portfolio-eval-v1",
            test_context_id=context_id,
        )
        receipt = scheduler.run(
            lane_id=lane_id,
            dispatched_at=dispatched_at,
            issued_at=issued_at,
        )
        self.assertEqual(1, len(observed_inputs))
        self.assertEqual(
            {
                "packet",
                "declared_material_projection",
                "prompt",
                "protocol",
            },
            set(observed_inputs[0]),
        )
        self.assertEqual(
            topic_packet_runtime.packet_projection(packet),
            observed_inputs[0]["packet"],
        )
        expected_material_projection = topic_packet_runtime.declared_material_projection(
            packet,
            workspace_root,
        )
        self.assertEqual(
            expected_material_projection,
            observed_inputs[0]["declared_material_projection"],
        )
        seal = scheduler.seal(
            generation_receipts=[receipt],
            sealed_at=sealed_at,
        )
        self.assertEqual(
            [],
            topic_packet_runtime.validate_seed_seal(
                packet,
                seal,
                key_store=key_store,
                material_projection=expected_material_projection,
            ),
        )
        return seal

    def _semantic_review_receipt(
        self,
        candidates: list[dict[str, Any]],
        presented_candidate_ids: list[str],
        seed_seal: dict[str, Any],
        screening_receipt: dict[str, Any],
        direction_contract: dict[str, Any],
        pair_reviews: list[dict[str, Any]],
        *,
        key_store_path: Path,
        context_id: str,
        issued_at: str,
    ) -> dict[str, Any]:
        observed_inputs: list[dict[str, Any]] = []

        def capture(bounded_input: object) -> str:
            self.assertIsInstance(bounded_input, dict)
            assert isinstance(bounded_input, dict)
            observed_inputs.append(copy.deepcopy(bounded_input))
            return json.dumps(pair_reviews, ensure_ascii=False)

        key_store = topic_packet_runtime.TopicSchedulerKeyStore(key_store_path)
        scheduler = rd.TopicSemanticReviewScheduler._for_test(
            test_capture=capture,
            key_store=key_store,
            test_run_id="RUN-SEMANTIC-REVIEW-001",
            test_model_revision="topic-portfolio-review-v1",
            test_context_id=context_id,
        )
        receipt = scheduler.run(
            candidates=candidates,
            presented_candidate_ids=presented_candidate_ids,
            direction_contract=direction_contract,
            issued_at=issued_at,
        )
        self.assertEqual(1, len(observed_inputs))
        self.assertEqual(
            {
                "portfolio",
                "direction_contract",
                "prompt",
                "protocol",
                "output_schema",
            },
            set(observed_inputs[0]),
        )
        review_issues, _ = rd.validate_semantic_review_receipt(
            candidates,
            presented_candidate_ids,
            seed_seal,
            screening_receipt,
            direction_contract,
            receipt,
        )
        self.assertEqual([], review_issues)
        return receipt

    def _screening_receipt(
        self,
        packet: dict[str, Any],
        seed_seal: dict[str, Any],
        output: dict[str, Any],
        *,
        key_store_path: Path,
        context_id: str,
        issued_at: str,
        workspace_root: Path | None = None,
    ) -> dict[str, Any]:
        observed_inputs: list[dict[str, Any]] = []

        def capture(bounded_input: object) -> str:
            self.assertIsInstance(bounded_input, dict)
            assert isinstance(bounded_input, dict)
            observed_inputs.append(copy.deepcopy(bounded_input))
            return json.dumps(output, ensure_ascii=False)

        key_store = topic_packet_runtime.TopicSchedulerKeyStore(key_store_path)
        scheduler = rd.TopicScreeningScheduler._for_test(
            packet,
            seed_seal,
            test_capture=capture,
            key_store=key_store,
            workspace_root=workspace_root,
            test_run_id="RUN-SCREENING-001",
            test_model_revision="topic-portfolio-screening-v1",
            test_context_id=context_id,
        )
        receipt = scheduler.run(issued_at=issued_at)
        self.assertEqual(1, len(observed_inputs))
        self.assertEqual(
            {"packet", "seed_seal", "prompt", "protocol", "output_schema"},
            set(observed_inputs[0]),
        )
        screening_issues, signed_cores = rd.validate_screening_receipt(
            packet,
            seed_seal,
            receipt,
        )
        self.assertEqual([], screening_issues)
        self.assertEqual(
            {
                item["candidate_id"]: item
                for item in output["candidate_cores"]
            },
            signed_cores,
        )
        return receipt

    def _make_workspace(self, base: Path, *, origin_mode: str = "direction_first") -> dict[str, Any]:
        material = base / "materials" / "opportunity.csv"
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_text("organization,wave,response\nA,2024,high\n", encoding="utf-8")
        self._run(
            INTAKE_WIZARD,
            "--output-dir",
            base,
            "--workflow",
            "build_from_materials",
            "--task-profile",
            "topic_selection",
            "--publication-track",
            "international-ssci",
            "--word-output",
            "none",
            "--pdf-output",
            "none",
            "--topic-origin-mode",
            origin_mode,
            "--brainstorm-depth",
            "focused",
            "--materials-dir",
            "materials",
            "--current-user-goal",
            "Build a comparative research agenda around accountability reforms",
            "--direction-field",
            "comparative political economy and public administration",
            "--core-problem",
            "Why equivalent accountability reforms produce divergent organizational responses",
            "--preferred-contribution",
            "mechanism explanation",
            "--object-scope",
            "public organizations undergoing comparable reforms",
            "--must-avoid",
            "dataset-led variable fishing",
            "--acceptable-adjacency",
            "medium",
            "--method-role",
            "open",
            "--no-interactive",
        )
        packet_path = base / "topic_packet.json"
        compile_args: list[object] = [
            TOPIC_PACKET,
            "compile",
            base,
            "--current-user-request",
            "Generate substantively different research problems before choosing methods",
            "--compiled-at",
            "2026-08-28T10:00:00+00:00",
            "--output",
            packet_path,
        ]
        if origin_mode == "material_opportunity":
            compile_args.extend(["--declared-workspace-scope", "materials/opportunity.csv"])
        else:
            recon_path = base / "recon-fixture.json"
            write_json(recon_path, rd_fixtures.synthetic_recon())
            compile_args.extend(["--recon", recon_path])
        self._run(*compile_args)

        seeds = [
            {
                "seed_id": "SEED-01",
                "candidate_family": "core-mechanism",
                "problem": "Equivalent formal reforms produce divergent organizational responses",
                "anomaly_or_unknown": "Common mandates do not explain the observed divergence",
                "why_it_matters": "The answer changes how institutional reform should be understood",
                "potential_disconfirmation": "Responses converge once enforcement discretion is measured",
            },
            {
                "seed_id": "SEED-02",
                "candidate_family": "boundary-comparison",
                "problem": "Accountability effects may reverse across administrative levels",
                "anomaly_or_unknown": "The same rule may centralize one level while decentralizing another",
                "why_it_matters": "The boundary determines whether the theory travels across levels",
                "potential_disconfirmation": "Comparable levels exhibit the same authority shift",
            },
        ]
        seal_path = base / "topic_seed_seal.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        key_store_path = base / ".avereth-state" / "topic_scheduler_keys.json"
        seal = self._scheduler_seal(
            packet,
            seeds,
            lane_id="core_mechanism_boundary",
            run_id="RUN-PORTFOLIO-001",
            context_id="CTX-PORTFOLIO-001",
            dispatched_at="2026-08-28T10:01:00+00:00",
            issued_at="2026-08-28T10:02:00+00:00",
            sealed_at="2026-08-28T10:05:00+00:00",
            key_store_path=key_store_path,
            workspace_root=base if origin_mode != "direction_first" else None,
        )
        write_json(seal_path, seal)

        (base / "problem_orientation.md").write_text(
            "# Problem Orientation\n\n| Field | Content |\n|---|---|\n"
            "| Orientation ID | PO-01 |\n"
            "| Practical encounter | Equivalent reforms produce divergent organizational responses. |\n",
            encoding="utf-8",
        )
        write_json(
            base / "reference_materials" / "literature_registry.json",
            {
                "schema_version": "cnki-acquisition/v2",
                "publication_track": "international-ssci",
                "queries": [],
                "sources": [],
            },
        )
        write_json(
            base / "literature_analysis.json",
            {"schema_version": "cnki-literature-analysis/v2", "syntheses": []},
        )

        candidate = self._candidate("CAND-01", "SEED-01")
        candidate["generation_lane"] = rd.generation_lane_for_origin(origin_mode)
        screening_receipt = self._screening_receipt(
            packet,
            seal,
            {
                "seed_dispositions": [
                    {
                        "seed_id": "SEED-01",
                        "disposition": "retain",
                        "candidate_id": "CAND-01",
                        "rationale": "This seed anchors the one surviving candidate core",
                    },
                    {
                        "seed_id": "SEED-02",
                        "disposition": "drop",
                        "candidate_id": None,
                        "rationale": "The boundary seed collapses under the narrow object scope",
                    },
                ],
                "candidate_cores": [rd.candidate_screened_core(candidate)],
            },
            key_store_path=key_store_path,
            context_id="CTX-PORTFOLIO-SCREENING-001",
            issued_at="2026-08-28T10:06:00+00:00",
            workspace_root=base if origin_mode != "direction_first" else None,
        )
        semantic_receipt = self._semantic_review_receipt(
            [candidate],
            ["CAND-01"],
            seal,
            screening_receipt,
            packet["direction_contract"],
            [],
            key_store_path=key_store_path,
            context_id="CTX-PORTFOLIO-SEMANTIC-001",
            issued_at="2026-08-28T10:08:00+00:00",
        )
        payload: dict[str, Any] = {
            "schema_version": rd.SCHEMA_VERSION,
            "decision_id": "RDEC-901",
            "decision_version": 1,
            "disposition": "pending",
            "selected_candidate_id": None,
            "no_automatic_replacement": True,
            "clearance_basis_digest": None,
            "selected_candidate_subgraph": {},
            "selected_candidate_subgraph_digest": rd.canonical_digest({}),
            "confirmed_motivation_ref": None,
            "soft_focus_confirmation": None,
            "hard_clearance_confirmation": None,
            "withdrawal_confirmation": None,
            "confirmation_archive": [],
            "historical_commitment_disposition": None,
            "candidates": [candidate],
            "question_challenges": [],
            "exploration": {
                "schema_version": "avereth-topic-exploration/v1",
                "topic_packet": packet,
                "seed_seal": seal,
                "screening_receipt": screening_receipt,
                "semantic_review_receipt": semantic_receipt,
                "workspace_materials_admitted_at": (
                    "2026-08-28T10:07:00+00:00"
                    if origin_mode == "direction_first"
                    else None
                ),
                "material_discovery_receipts": [],
                "narrow_direction_exemption": self._valid_exemption(),
                "attempted_families": ["core-mechanism", "boundary-comparison"],
                "presented_candidate_ids": ["CAND-01"],
                "material_opportunity_candidate_ids": [],
                "finalist_candidate_ids": ["CAND-01"],
                "portfolio_audit": {
                    "status": "PASS",
                    "audited_at": "2026-08-28T10:10:00+00:00",
                    "candidate_count": 1,
                    "family_count": 1,
                    "main_candidate_count": 1,
                    "material_branch_candidate_count": 0,
                    "semantic_signature_dimensions": list(rd.SIGNATURE_DIMENSIONS),
                    "semantic_review_receipt_sha256": semantic_receipt[
                        "receipt_sha256"
                    ],
                },
                "decision_roles": {
                    "most_robust": "CAND-01",
                    "most_balanced": "CAND-01",
                    "highest_originality": "CAND-01",
                    "reuse_rationale": (
                        "The valid narrow-direction exemption leaves one substantive candidate for all three decision roles"
                    ),
                },
            },
        }
        return payload

    @staticmethod
    def _valid_exemption() -> dict[str, Any]:
        return {
            "attempted_families": ["core-mechanism", "boundary-comparison"],
            "elimination_reasons": [
                "Boundary alternatives collapse after applying the user's narrow object scope",
            ],
            "rationale": (
                "Only one candidate remains substantively coherent; adding another would fabricate a companion"
            ),
            "highest_originality_absence_reason": (
                "No distinct high-risk candidate survives the authorized direction without fabricating a companion"
            ),
            "no_companion_candidates_fabricated": True,
        }

    @staticmethod
    def _direction_fit() -> dict[str, Any]:
        return {
            "topic": {
                "verdict": "strong",
                "basis": ["current_user_goal", "field"],
                "rationale": "The candidate remains inside the authorized comparative public-administration topic",
            },
            "problem": {
                "verdict": "strong",
                "basis": ["core_problem", "object_scope"],
                "rationale": "The question directly explains the contract's central organizational divergence",
            },
            "contribution": {
                "verdict": "strong",
                "basis": ["preferred_contribution", "publication_track"],
                "rationale": "The proposed answer supplies the requested mechanism contribution on the declared track",
            },
            "trajectory": {
                "verdict": "strong",
                "basis": ["acceptable_adjacency", "method_role"],
                "rationale": "The candidate advances the authorized research trajectory without material anchoring",
            },
        }

    def _controlled_screened_flow(
        self,
        base: Path,
        *,
        core_problem: str,
        material_marker: str,
    ) -> dict[str, Any]:
        material = base / "materials" / "counterfactual.txt"
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_text(material_marker, encoding="utf-8")

        config = rd_fixtures.topic_workflow_config()
        config["topic_selection"]["brainstorm_depth"] = "focused"
        config["direction_contract"]["core_problem"] = core_problem
        packet = topic_packet_runtime.build_packet(
            config,
            current_user_request="Generate and screen direction-led problem candidates",
            compiled_at="2026-08-28T13:00:00+00:00",
            literature_reconnaissance=rd_fixtures.synthetic_recon(),
        )
        climate = "climate" in core_problem.casefold()
        if climate:
            family = "intergovernmental adaptation authority"
            question = (
                "How does climate adaptation reorganize authority across levels of government?"
            )
            signature = {
                "research_object": "intergovernmental climate adaptation programs",
                "phenomenon": "redistribution of authority during adaptation",
                "mechanism_or_tension": "urgent coordination versus jurisdictional ownership",
                "unit_of_analysis": "intergovernmental adaptation program",
                "temporal_logic": "authority reallocation across adaptation phases",
                "contribution_type": "mechanism explanation of authority change",
                "evidence_logic": "comparative process evidence across programs",
            }
        else:
            family = "accountability response divergence"
            question = (
                "Why do equivalent accountability reforms produce divergent organizational responses?"
            )
            signature = {
                "research_object": "public organizations under accountability reform",
                "phenomenon": "divergent responses to equivalent formal reforms",
                "mechanism_or_tension": "formal mandates versus enforcement discretion",
                "unit_of_analysis": "public organization",
                "temporal_logic": "organizational adjustment after reform",
                "contribution_type": "mechanism explanation of response divergence",
                "evidence_logic": "matched institutional comparison",
            }
        seeds = [
            {
                "seed_id": "SEED-01",
                "candidate_family": family,
                "problem": question,
                "anomaly_or_unknown": "Comparable formal conditions still produce consequential divergence",
                "why_it_matters": "Resolving the divergence changes the governing theoretical explanation",
                "potential_disconfirmation": "The divergence disappears after the proposed mechanism is measured",
            },
            {
                "seed_id": "SEED-02",
                "candidate_family": family,
                "problem": f"Boundary conditions for {question.rstrip('?').casefold()}",
                "anomaly_or_unknown": "The proposed mechanism may reverse at an institutional boundary",
                "why_it_matters": "The boundary determines whether the explanation travels",
                "potential_disconfirmation": "The same relationship holds across every authorized boundary",
            },
        ]
        key_store_path = base / ".avereth-state" / "topic_scheduler_keys.json"
        seal = self._scheduler_seal(
            packet,
            seeds,
            lane_id="core_mechanism_boundary",
            run_id="RUN-CONTROLLED-DIRECTION-001",
            context_id="CTX-CONTROLLED-DIRECTION-001",
            dispatched_at="2026-08-28T13:01:00+00:00",
            issued_at="2026-08-28T13:02:00+00:00",
            sealed_at="2026-08-28T13:03:00+00:00",
            key_store_path=key_store_path,
        )
        candidate = self._candidate("CAND-01", "SEED-01")
        candidate.update(
            {
                "seed_ids": ["SEED-01", "SEED-02"],
                "candidate_family": family,
                "research_question": question,
                "semantic_signature": signature,
            }
        )
        screening = self._screening_receipt(
            packet,
            seal,
            {
                "seed_dispositions": [
                    {
                        "seed_id": "SEED-01",
                        "disposition": "retain",
                        "candidate_id": "CAND-01",
                        "rationale": "The seed anchors the selected substantive problem family",
                    },
                    {
                        "seed_id": "SEED-02",
                        "disposition": "merge",
                        "candidate_id": "CAND-01",
                        "rationale": "The boundary seed strengthens the same substantive candidate core",
                    },
                ],
                "candidate_cores": [rd.candidate_screened_core(candidate)],
            },
            key_store_path=key_store_path,
            context_id="CTX-CONTROLLED-SCREENING-001",
            issued_at="2026-08-28T13:04:00+00:00",
        )
        core = screening["candidate_cores"][0]
        return {
            "packet": packet,
            "seed_seal": seal,
            "screening_receipt": screening,
            "semantic_core": {
                "generation_lane": core["generation_lane"],
                "candidate_family": core["candidate_family"],
                "research_question": core["research_question"],
                "semantic_signature": core["semantic_signature"],
            },
        }

    def _attach_material_discovery(
        self,
        base: Path,
        payload: dict[str, Any],
        *,
        candidate_id: str = "CAND-02",
    ) -> tuple[dict[str, Any], Path]:
        material = base / "materials" / "discovery.txt"
        material.parent.mkdir(parents=True, exist_ok=True)
        material.write_text(
            "Comparable agencies with the same mandate split into persistent compliance and avoidance clusters.",
            encoding="utf-8",
        )
        candidate = self._candidate(candidate_id, "SEED-01")
        candidate.update(
            {
                "maturity": "screened",
                "c0_candidate_map": {
                    "disposition": "defer",
                    "rationale": "Keep this material-origin anomaly separate from the already selected direction-led candidate",
                },
                "seed_ids": [],
                "generation_lane": "material_discovery",
                "candidate_family": "compliance avoidance anomaly",
                "portfolio_bucket": "material-opportunity",
                "research_question": (
                    "Why do comparable agencies split into compliance and avoidance clusters under the same mandate?"
                ),
                "semantic_signature": {
                    "research_object": "agencies under a shared accountability mandate",
                    "phenomenon": "persistent compliance and avoidance clustering",
                    "mechanism_or_tension": "formal mandate versus defensive implementation routines",
                    "unit_of_analysis": "public agency",
                    "temporal_logic": "cluster persistence after common mandate adoption",
                    "contribution_type": "previously unseen implementation anomaly",
                    "evidence_logic": "material-bound comparative anomaly tracing",
                },
                "direction_fit": self._direction_fit(),
                "workspace_relation": {
                    "role": "support",
                    "ablation_result": "depends",
                    "anchor_risk": "medium",
                    "rationale": "The candidate exists only because the admitted material exposes this previously unseen anomaly",
                    "material_refs": [],
                },
            }
        )
        exploration = payload["exploration"]
        observed_inputs: list[dict[str, Any]] = []
        output = {
            "candidate_core": rd.candidate_screened_core(candidate),
            "anomaly": (
                "Equivalent mandates coincide with persistent compliance and avoidance clusters in the bound material"
            ),
            "previously_unseen": True,
            "comparison_rationale": (
                "No sealed seed or screened core asks why the common mandate produces this two-cluster implementation pattern"
            ),
        }

        def capture(bounded_input: object) -> str:
            self.assertIsInstance(bounded_input, dict)
            assert isinstance(bounded_input, dict)
            observed_inputs.append(copy.deepcopy(bounded_input))
            return json.dumps(output, ensure_ascii=False)

        key_store_path = base / ".avereth-state" / "topic_scheduler_keys.json"
        scheduler = rd.TopicMaterialDiscoveryScheduler._for_test(
            exploration["topic_packet"],
            exploration["seed_seal"],
            exploration["screening_receipt"],
            workspace_root=base,
            material_path="materials/discovery.txt",
            test_capture=capture,
            key_store=topic_packet_runtime.TopicSchedulerKeyStore(key_store_path),
            test_run_id="RUN-MATERIAL-DISCOVERY-001",
            test_model_revision="topic-material-discovery-v1",
            test_context_id="CTX-MATERIAL-DISCOVERY-001",
        )
        receipt = scheduler.run(issued_at="2026-08-28T13:09:00+00:00")
        self.assertEqual(1, len(observed_inputs))
        self.assertEqual(
            {"projection", "prompt", "protocol", "output_schema"},
            set(observed_inputs[0]),
        )
        projection = observed_inputs[0]["projection"]
        self.assertEqual(material.read_text(encoding="utf-8"), projection["material_text"])
        self.assertEqual(receipt["material_ref"], projection["material_ref"])
        self.assertEqual(rd.canonical_digest(projection), receipt["input_sha256"])
        candidate["workspace_relation"]["material_refs"] = [
            copy.deepcopy(receipt["material_ref"])
        ]
        payload["candidates"].append(candidate)
        exploration["material_opportunity_candidate_ids"].append(candidate_id)
        exploration["material_discovery_receipts"].append(receipt)

        visible_ids = [
            *exploration["presented_candidate_ids"],
            *exploration["material_opportunity_candidate_ids"],
        ]
        visible_candidates = [
            item
            for item in payload["candidates"]
            if item["id"] in visible_ids
        ]
        pair_reviews: list[dict[str, Any]] = []
        for left_index, left_id in enumerate(visible_ids):
            for right_id in visible_ids[left_index + 1 :]:
                pair_reviews.append(
                    {
                        "left_candidate_id": left_id,
                        "right_candidate_id": right_id,
                        "relation": "load-bearing-distinct",
                        "difference_dimensions": [
                            "phenomenon",
                            "mechanism_or_tension",
                        ],
                        "rationale": (
                            "The direction-led reform-divergence problem and the material-discovered compliance-cluster anomaly require different phenomena and mechanisms"
                        ),
                    }
                )
        for item in visible_candidates:
            nearest_id = next(
                (other for other in visible_ids if other != item["id"]),
                None,
            )
            item["distinctness"] = {
                "nearest_candidate_id": nearest_id,
                "difference_dimensions": (
                    ["phenomenon", "mechanism_or_tension"]
                    if nearest_id is not None
                    else []
                ),
                "rationale": (
                    "The nearest visible candidate differs in its load-bearing phenomenon and explanatory tension"
                    if nearest_id is not None
                    else "No second visible candidate requires a nearest-neighbour comparison"
                ),
            }
        semantic_receipt = self._semantic_review_receipt(
            visible_candidates,
            visible_ids,
            exploration["seed_seal"],
            exploration["screening_receipt"],
            exploration["topic_packet"]["direction_contract"],
            pair_reviews,
            key_store_path=key_store_path,
            context_id="CTX-MATERIAL-DISCOVERY-SEMANTIC-001",
            issued_at="2026-08-28T13:10:00+00:00",
        )
        exploration["semantic_review_receipt"] = semantic_receipt
        audit = exploration["portfolio_audit"]
        audit.update(
            {
                "audited_at": "2026-08-28T13:11:00+00:00",
                "candidate_count": len(visible_ids),
                "family_count": len(
                    {item["candidate_family"] for item in visible_candidates}
                ),
                "main_candidate_count": len(
                    exploration["presented_candidate_ids"]
                ),
                "material_branch_candidate_count": len(
                    exploration["material_opportunity_candidate_ids"]
                ),
                "semantic_review_receipt_sha256": semantic_receipt[
                    "receipt_sha256"
                ],
            }
        )
        if payload.get("disposition") == "cleared":
            payload["hard_clearance_confirmation"]["basis_sha256"] = None
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
            payload["hard_clearance_confirmation"]["basis_sha256"] = payload[
                "clearance_basis_digest"
            ]
            self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
        return receipt, material

    @staticmethod
    def _candidate(candidate_id: str, seed_id: str) -> dict[str, Any]:
        return {
            "id": candidate_id,
            "topic_option_id": f"O{int(candidate_id.split('-')[1])}",
            "status": "alternate",
            "provisional_title": (
                "Accountability mandates and divergent organizational responses"
                if candidate_id == "CAND-01"
                else "Why similar accountability rules yield different responses"
            ),
            "orientation_ids": ["PO-01"],
            "focus_rationale": "The candidate preserves a consequential unknown and a bounded comparison",
            "c0_candidate_map": None,
            "c1_collision_evidence": None,
            "c2_overlap_adjudication": None,
            "c3_novelty_clearance": None,
            "question_versions": [],
            "active_question_version_id": None,
            "maturity": "finalist",
            "seed_ids": [seed_id],
            "generation_lane": "direction_only",
            "candidate_family": "core-mechanism",
            "portfolio_bucket": "core-fit",
            "research_question": (
                "Why do equivalent accountability reforms produce divergent organizational responses?"
            ),
            "potential_contribution": (
                "Identify when enforcement discretion converts equivalent accountability mandates into divergent organizational responses"
            ),
            "largest_uncertainty_or_failure_risk": (
                "Observed divergence may reflect unmeasured implementation capacity rather than enforcement discretion"
            ),
            "why_worth_deep_review": (
                "The candidate can revise how accountability reforms are expected to travel across comparable public organizations"
            ),
            "direction_fit": TopicPortfolioRuntimeEvals._direction_fit(),
            "workspace_relation": {
                "role": "incidental",
                "ablation_result": "survives",
                "anchor_risk": "low",
                "rationale": "Admitted workspace material is incidental to the sealed direction-only problem",
                "material_refs": [],
            },
            "semantic_signature": {
                "research_object": "public accountability organizations",
                "phenomenon": "divergent responses to equivalent formal reforms",
                "mechanism_or_tension": "formal mandates versus enforcement discretion",
                "unit_of_analysis": "public organization",
                "temporal_logic": "post-reform organizational adjustment",
                "contribution_type": "mechanism explanation",
                "evidence_logic": "matched institutional comparison",
            },
            "distinctness": {
                "nearest_candidate_id": None,
                "difference_dimensions": [],
                "rationale": "No second candidate survives under the documented narrow-direction exemption",
            },
        }

    def _runtime_issues(self, base: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
        decision_path = base / "research_decision.json"
        write_json(decision_path, payload)
        completed = self._run(
            RESEARCH_DECISION,
            "validate",
            decision_path,
            "--json",
            expected=1,
            env={
                **os.environ,
                "AVERETH_TOPIC_SCHEDULER_KEY_STORE": str(
                    base / ".avereth-state" / "topic_scheduler_keys.json"
                ),
            },
        )
        report = json.loads(completed.stdout)
        self.assertEqual("FAIL", report["status"])
        issues = report["issues"]
        codes = {item["code"] for item in issues}
        self.assertIn(
            "RDEC.PRECLEAR.PROVISIONAL",
            codes,
            "the eval must have reached the real runtime validator, not a local keyword check",
        )
        return issues

    def _runtime_codes(self, base: Path, payload: dict[str, Any]) -> set[str]:
        return {item["code"] for item in self._runtime_issues(base, payload)}

    def _make_cleared_single_exemption_workspace(self, base: Path) -> dict[str, Any]:
        payload = rd_fixtures.make_workspace(base)
        config = rd_fixtures.workflow_config()
        config["topic_selection"] = {
            "origin_mode": "direction_first",
            "brainstorm_depth": "broad",
            "workspace_policy": "quarantine_until_divergence",
        }
        config["direction_contract"] = {
            "current_user_goal": "Explain divergent institutional responses to accountability reform",
            "field": "comparative political economy and public administration",
            "core_problem": "Why comparable governments make divergent public investment choices",
            "preferred_contribution": ["mechanism explanation"],
            "object_scope": "comparable local governments in the registered period",
            "must_preserve": ["bounded institutional comparison"],
            "must_avoid": ["dataset-led variable fishing"],
            "acceptable_adjacency": "narrow",
            "publication_track": "international-ssci",
            "method_role": "open",
            "workspace_role": "optional-after-divergence",
            "authority": "current-user-request",
        }
        write_json(base / "workflow_config.json", config)

        row = rd_fixtures.matrix_row(
            "O1",
            rd_fixtures.TITLE_1,
            rd_fixtures.QUESTION_1,
            "Bounded to observed local governments and the registered period.",
        )
        (base / "topic_induction_deduction_matrix.md").write_text(
            "\n".join(
                [
                    "# Topic Induction-Deduction Matrix",
                    "",
                    "| " + " | ".join(rd_fixtures.MATRIX_HEADERS) + " |",
                    "|" + "|".join("---" for _ in rd_fixtures.MATRIX_HEADERS) + "|",
                    "| " + " | ".join(row) + " |",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        packet = topic_packet_runtime.build_packet(
            config,
            current_user_request="Generate direction-first candidates before admitting workspace materials",
            compiled_at="2026-08-28T12:00:00+00:00",
            literature_reconnaissance=rd_fixtures.synthetic_recon(),
        )
        seed_families = ["institutional divergence", "reporting visibility"]
        key_store_path = base / ".avereth-state" / "topic_scheduler_keys.json"
        seal = self._scheduler_seal(
            packet,
            [
                {
                    "seed_id": "SEED-01",
                    "candidate_family": seed_families[0],
                    "problem": "Comparable governments make divergent public investment choices",
                    "anomaly_or_unknown": "Uniform incentives do not explain the observed divergence",
                    "why_it_matters": "The answer changes how institutional reform is evaluated",
                    "potential_disconfirmation": "Comparable choices converge after visibility is measured",
                },
                {
                    "seed_id": "SEED-02",
                    "candidate_family": seed_families[1],
                    "problem": "Reporting rules may alter which investment choices become visible",
                    "anomaly_or_unknown": "Formal disclosure does not create uniform public visibility",
                    "why_it_matters": "The distinction changes the expected accountability mechanism",
                    "potential_disconfirmation": "Visibility remains identical across reporting regimes",
                },
            ],
            lane_id="core_problem",
            run_id="RUN-CLEARED-001",
            context_id="CTX-CLEARED-001",
            dispatched_at="2026-08-28T12:01:00+00:00",
            issued_at="2026-08-28T12:02:00+00:00",
            sealed_at="2026-08-28T12:05:00+00:00",
            key_store_path=key_store_path,
        )

        candidate = payload["candidates"][0]
        payload["candidates"] = [candidate]
        payload["soft_focus_confirmation"]["alternate_candidate_ids"] = []
        candidate.update(
            {
                "maturity": "selected",
                "seed_ids": ["SEED-01"],
                "generation_lane": "direction_only",
                "candidate_family": seed_families[0],
                "portfolio_bucket": "core-fit",
                "research_question": candidate["question_versions"][0]["text"],
                "potential_contribution": (
                    "Explain when institutional visibility changes the effects of otherwise comparable public-investment incentives"
                ),
                "largest_uncertainty_or_failure_risk": (
                    "Available records may not distinguish visibility effects from correlated differences in local administrative capacity"
                ),
                "why_worth_deep_review": (
                    "The candidate preserves a consequential conditional explanation with observable implications and a bounded comparison"
                ),
                "direction_fit": self._direction_fit(),
                "workspace_relation": {
                    "role": "incidental",
                    "ablation_result": "survives",
                    "anchor_risk": "low",
                    "rationale": "The admitted workspace material is incidental to the independently consequential question",
                    "material_refs": [],
                },
                "semantic_signature": {
                    "research_object": "comparable local governments",
                    "phenomenon": "divergent public investment choices",
                    "mechanism_or_tension": "institutional visibility conditions incentive effects",
                    "unit_of_analysis": "local government",
                    "temporal_logic": "registered recent reform period",
                    "contribution_type": "mechanism explanation",
                    "evidence_logic": "matched institutional comparison",
                },
                "distinctness": {
                    "nearest_candidate_id": None,
                    "difference_dimensions": [],
                    "rationale": "No second candidate survived the documented narrow-direction screen",
                },
            }
        )
        screening_receipt = self._screening_receipt(
            packet,
            seal,
            {
                "seed_dispositions": [
                    {
                        "seed_id": "SEED-01",
                        "disposition": "retain",
                        "candidate_id": "CAND-01",
                        "rationale": "This seed anchors the one selected candidate core",
                    },
                    {
                        "seed_id": "SEED-02",
                        "disposition": "drop",
                        "candidate_id": None,
                        "rationale": "This seed collapses after the bounded comparison",
                    },
                ],
                "candidate_cores": [rd.candidate_screened_core(candidate)],
            },
            key_store_path=key_store_path,
            context_id="CTX-CLEARED-SCREENING-001",
            issued_at="2026-08-28T12:06:00+00:00",
        )
        semantic_receipt = self._semantic_review_receipt(
            [candidate],
            ["CAND-01"],
            seal,
            screening_receipt,
            packet["direction_contract"],
            [],
            key_store_path=key_store_path,
            context_id="CTX-CLEARED-SEMANTIC-001",
            issued_at="2026-08-28T12:08:00+00:00",
        )
        payload["exploration"] = {
            "schema_version": "avereth-topic-exploration/v1",
            "topic_packet": packet,
            "seed_seal": seal,
            "screening_receipt": screening_receipt,
            "semantic_review_receipt": semantic_receipt,
            "workspace_materials_admitted_at": "2026-08-28T12:07:00+00:00",
            "material_discovery_receipts": [],
            "attempted_families": seed_families,
            "presented_candidate_ids": ["CAND-01"],
            "material_opportunity_candidate_ids": [],
            "finalist_candidate_ids": ["CAND-01"],
            "portfolio_audit": {
                "status": "PASS",
                "audited_at": "2026-08-28T12:10:00+00:00",
                "candidate_count": 1,
                "family_count": 1,
                "main_candidate_count": 1,
                "material_branch_candidate_count": 0,
                "semantic_signature_dimensions": list(rd.SIGNATURE_DIMENSIONS),
                "semantic_review_receipt_sha256": semantic_receipt[
                    "receipt_sha256"
                ],
            },
            "decision_roles": {
                "most_robust": "CAND-01",
                "most_balanced": "CAND-01",
                "highest_originality": "CAND-01",
                "reuse_rationale": (
                    "The valid narrow-direction exemption leaves one substantive candidate for all three decision roles"
                ),
            },
            "narrow_direction_exemption": {
                "attempted_families": seed_families,
                "elimination_reasons": [
                    "The reporting-visibility family duplicates the survivor once object and contribution boundaries are fixed",
                ],
                "rationale": (
                    "Only one independently consequential candidate survives; additional companions would be fabricated quota fillers"
                ),
                "highest_originality_absence_reason": (
                    "No distinct high-risk candidate survives the authorized direction without inventing a quota filler"
                ),
                "no_companion_candidates_fabricated": True,
            },
        }
        payload["hard_clearance_confirmation"]["basis_sha256"] = None
        self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
        payload["hard_clearance_confirmation"]["basis_sha256"] = payload[
            "clearance_basis_digest"
        ]
        self.assertEqual([], rd.bind_selected_candidate_subgraph(base, payload))
        result = rd.validate_payload(base, payload)
        self.assertEqual([], result.errors)
        self.assertEqual([], rd.write_views(base, payload, result, allow_unmanaged_replace=True))
        write_json(base / "research_decision.json", payload)
        return payload

    @staticmethod
    def _portfolio_codes(base: Path, payload: dict[str, Any]) -> set[str]:
        return {item.code for item in rd.topic_portfolio_issues(base, payload)}

    def test_counterfactual_manifest_has_eleven_executable_handlers(self) -> None:
        manifest = json.loads(CASES.read_text(encoding="utf-8"))
        self.assertEqual("avereth-topic-portfolio-evals/v1", manifest["schema_version"])
        cases = manifest["cases"]
        self.assertEqual(
            {
                "irrelevant-material-invariance",
                "direction-sensitivity",
                "declared-material-origin-receipt",
                "explicit-material-opportunity",
                "title-pseudo-diversity",
                "strict-single-candidate-exemption",
                "forged-seed-lineage",
                "missing-seed-disposition",
                "four-layer-direction-fit-receipt",
                "material-discovery-receipt",
                "nonselected-material-stale-isolation",
            },
            {item["id"] for item in cases},
        )
        self.assertEqual(11, len(cases))
        discovered = set(unittest.defaultTestLoader.getTestCaseNames(type(self)))
        for item in cases:
            with self.subTest(case=item["id"]):
                handler = item.get("handler")
                self.assertIsInstance(handler, str)
                self.assertIn(handler, discovered)
                self.assertTrue(callable(getattr(type(self), handler, None)))
                self.assertTrue(str(item.get("runtime_boundary") or "").strip())
                self.assertTrue(str(item.get("expected") or "").strip())

    def test_direction_first_material_invariance_case(self) -> None:
        self._run(
            TOPIC_PACKET_TESTS,
            (
                "TopicPacketCounterfactualTests."
                "test_direction_first_intake_and_packet_ignore_conflicting_workspaces"
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            flow_a = self._controlled_screened_flow(
                root / "material-a",
                core_problem="Why equivalent accountability reforms produce divergent organizational responses",
                material_marker="UNRELATED_MATERIAL_ALPHA",
            )
            flow_b = self._controlled_screened_flow(
                root / "material-b",
                core_problem="Why equivalent accountability reforms produce divergent organizational responses",
                material_marker="CONFLICTING_MATERIAL_BETA",
            )
            self.assertEqual(flow_a["semantic_core"], flow_b["semantic_core"])
            self.assertEqual(
                flow_a["packet"]["direction_contract_digest"],
                flow_b["packet"]["direction_contract_digest"],
            )
            serialized = json.dumps(
                [flow_a, flow_b],
                ensure_ascii=False,
                sort_keys=True,
            )
            self.assertNotIn("UNRELATED_MATERIAL_ALPHA", serialized)
            self.assertNotIn("CONFLICTING_MATERIAL_BETA", serialized)

    def test_direction_change_sensitivity_case(self) -> None:
        self._run(
            TOPIC_PACKET_TESTS,
            (
                "TopicPacketCounterfactualTests."
                "test_changing_only_the_direction_changes_packet_semantics_and_sha"
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accountability = self._controlled_screened_flow(
                root / "accountability",
                core_problem="Why equivalent accountability reforms produce divergent organizational responses",
                material_marker="IDENTICAL_SHARED_MATERIAL",
            )
            climate = self._controlled_screened_flow(
                root / "climate",
                core_problem="How climate adaptation reorganizes intergovernmental authority",
                material_marker="IDENTICAL_SHARED_MATERIAL",
            )
            self.assertNotEqual(
                accountability["packet"]["direction_contract_digest"],
                climate["packet"]["direction_contract_digest"],
            )
            self.assertNotEqual(
                accountability["semantic_core"],
                climate["semantic_core"],
            )

    def test_declared_material_origins_bind_real_material_and_multiple_families(self) -> None:
        for origin_mode in ("material_opportunity", "workspace_extension"):
            with self.subTest(origin_mode=origin_mode), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp)
                material = base / "materials" / "declared.txt"
                material.parent.mkdir(parents=True, exist_ok=True)
                marker = f"DECLARED_{origin_mode.upper()}_ANOMALY"
                material.write_text(
                    f"{marker}: common rules coexist with response, boundary, sequence, and measurement anomalies.",
                    encoding="utf-8",
                )
                config = rd_fixtures.topic_workflow_config()
                config["topic_selection"] = {
                    "origin_mode": origin_mode,
                    "brainstorm_depth": "focused",
                    "workspace_policy": "declared_source_from_start",
                }
                config["direction_contract"]["workspace_role"] = {
                    "material_opportunity": "declared-material-source",
                    "workspace_extension": "declared-extension-source",
                }[origin_mode]
                packet = topic_packet_runtime.build_packet(
                    config,
                    current_user_request="Generate several material-grounded problem families",
                    compiled_at="2026-08-28T14:00:00+00:00",
                    declared_workspace_scope=["materials/declared.txt"],
                )
                seeds = [
                    {
                        "seed_id": "SEED-01",
                        "candidate_family": "response divergence",
                        "problem": "Why do common rules generate divergent organizational responses?",
                        "anomaly_or_unknown": "The material contains persistent response divergence under common rules",
                        "why_it_matters": "The answer changes the mechanism used to explain implementation",
                        "potential_disconfirmation": "The divergence disappears after capacity is measured",
                    },
                    {
                        "seed_id": "SEED-02",
                        "candidate_family": "boundary reversal",
                        "problem": "When do the effects of common rules reverse across institutional boundaries?",
                        "anomaly_or_unknown": "The material suggests an effect reversal rather than a level difference",
                        "why_it_matters": "The reversal defines where the explanation travels",
                        "potential_disconfirmation": "Effects remain directionally identical across boundaries",
                    },
                    {
                        "seed_id": "SEED-03",
                        "candidate_family": "historical sequence",
                        "problem": "How does reform sequence preserve divergence after formal convergence?",
                        "anomaly_or_unknown": "Common rules do not erase inherited implementation sequences",
                        "why_it_matters": "The answer changes the temporal logic of institutional convergence",
                        "potential_disconfirmation": "Earlier sequences have no association with later implementation",
                    },
                    {
                        "seed_id": "SEED-04",
                        "candidate_family": "measurement reconstruction",
                        "problem": "Which implementation burdens disappear in aggregate compliance measures?",
                        "anomaly_or_unknown": "Aggregate compliance conceals substantively different burden profiles",
                        "why_it_matters": "The hidden profiles change the construct being explained",
                        "potential_disconfirmation": "Disaggregated burden profiles reproduce the aggregate ranking",
                    },
                ]
                observed: list[dict[str, Any]] = []

                def capture(bounded_input: object) -> str:
                    self.assertIsInstance(bounded_input, dict)
                    assert isinstance(bounded_input, dict)
                    observed.append(copy.deepcopy(bounded_input))
                    return json.dumps(seeds, ensure_ascii=False)

                key_store = topic_packet_runtime.TopicSchedulerKeyStore(
                    base / ".avereth-state" / "topic_scheduler_keys.json"
                )
                scheduler = topic_packet_runtime.TopicGenerationScheduler._for_test(
                    packet,
                    test_capture=capture,
                    key_store=key_store,
                    workspace_root=base,
                    test_run_id=f"RUN-DECLARED-{origin_mode}",
                    test_model_revision="declared-material-generation-v1",
                    test_context_id=f"CTX-DECLARED-{origin_mode}",
                )
                receipt = scheduler.run(
                    lane_id="core_mechanism_boundary",
                    dispatched_at="2026-08-28T14:01:00+00:00",
                    issued_at="2026-08-28T14:02:00+00:00",
                )
                seal = scheduler.seal(
                    generation_receipts=[receipt],
                    sealed_at="2026-08-28T14:03:00+00:00",
                )
                self.assertEqual(1, len(observed))
                projection = observed[0]["declared_material_projection"]
                self.assertEqual(marker, projection[0]["text"].split(":", 1)[0])
                self.assertEqual(
                    topic_packet_runtime.canonical_digest(projection),
                    receipt["material_projection_sha256"],
                )
                self.assertEqual(
                    topic_packet_runtime.declared_material_refs(projection),
                    receipt["material_refs"],
                )
                self.assertEqual(
                    topic_packet_runtime.generation_input_digest(
                        packet,
                        projection,
                        "core_mechanism_boundary",
                    ),
                    receipt["input_sha256"],
                )
                self.assertEqual(
                    4,
                    len({item["candidate_family"] for item in receipt["seeds"]}),
                )
                self.assertEqual(4, len(seal["seeds"]))

                material.write_text(
                    f"{marker}_CHANGED: the bounded source content has materially changed.",
                    encoding="utf-8",
                )
                changed_projection = topic_packet_runtime.declared_material_projection(
                    packet,
                    base,
                )
                verification_key = key_store.verification_key(
                    key_id=receipt["scheduler_key_id"],
                    session_id=receipt["scheduler_session_id"],
                )
                stale_issues = topic_packet_runtime.validate_generation_receipt(
                    packet,
                    receipt,
                    verification_key=verification_key,
                    material_projection=changed_projection,
                )
                self.assertTrue(
                    any(
                        "material" in issue.casefold()
                        and ("digest" in issue.casefold() or "sha" in issue.casefold())
                        for issue in stale_issues
                    ),
                    stale_issues,
                )

    def test_runtime_rejects_forged_seed_lineage_against_signed_screening(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = self._make_workspace(base)
            payload["candidates"][0]["seed_ids"] = ["SEED-FORGED-99"]

            direct_codes = self._portfolio_codes(base, payload)
            self.assertIn("RDEC.CANDIDATE.SEED_LINEAGE", direct_codes)
            self.assertIn("RDEC.SCREENING.CANDIDATE_CORE", direct_codes)
            runtime_codes = self._runtime_codes(base, payload)
            self.assertIn("RDEC.CANDIDATE.SEED_LINEAGE", runtime_codes)
            self.assertIn("RDEC.SCREENING.CANDIDATE_CORE", runtime_codes)

    def test_screening_refuses_any_missing_seed_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            flow = self._controlled_screened_flow(
                base,
                core_problem="Why equivalent accountability reforms produce divergent organizational responses",
                material_marker="IRRELEVANT_MATERIAL",
            )
            valid_receipt = flow["screening_receipt"]
            incomplete_output = {
                "seed_dispositions": [
                    copy.deepcopy(valid_receipt["seed_dispositions"][0])
                ],
                "candidate_cores": copy.deepcopy(valid_receipt["candidate_cores"]),
            }
            scheduler = rd.TopicScreeningScheduler._for_test(
                flow["packet"],
                flow["seed_seal"],
                test_capture=lambda _bounded_input: json.dumps(
                    incomplete_output,
                    ensure_ascii=False,
                ),
                key_store=topic_packet_runtime.TopicSchedulerKeyStore(
                    base / ".avereth-state" / "topic_scheduler_keys.json"
                ),
                test_context_id="CTX-MISSING-DISPOSITION-001",
            )
            with self.assertRaisesRegex(
                ValueError,
                "account for every sealed seed exactly once",
            ):
                scheduler.run(issued_at="2026-08-28T13:05:00+00:00")

    def test_four_layer_direction_fit_self_report_cannot_replace_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = self._make_workspace(base)
            self.assertEqual(
                {"topic", "problem", "contribution", "trajectory"},
                set(payload["candidates"][0]["direction_fit"]),
            )
            payload["candidates"][0]["direction_fit"]["trajectory"]["rationale"] = (
                "The caller now self-reports a different but still structurally valid trajectory rationale"
            )
            codes = self._runtime_codes(base, payload)
            self.assertNotIn("RDEC.CANDIDATE.DIRECTION_FIT", codes)
            self.assertIn("RDEC.SCREENING.CANDIDATE_CORE", codes)

            no_receipt = copy.deepcopy(payload)
            no_receipt["exploration"]["screening_receipt"] = None
            no_receipt_codes = self._runtime_codes(base, no_receipt)
            self.assertIn("RDEC.SCREENING.RECEIPT", no_receipt_codes)

    def test_material_discovery_requires_material_bound_controlled_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = self._make_workspace(base)
            receipt, material = self._attach_material_discovery(base, payload)
            valid_codes = self._portfolio_codes(base, payload)
            self.assertFalse(
                {code for code in valid_codes if code.startswith("RDEC.MATERIAL_DISCOVERY")},
                valid_codes,
            )

            self_report = copy.deepcopy(payload)
            self_report["exploration"]["material_discovery_receipts"] = []
            self_report_codes = self._runtime_codes(base, self_report)
            self.assertIn("RDEC.MATERIAL_DISCOVERY.RECEIPT", self_report_codes)

            material.write_text(
                "The formerly observed compliance split has disappeared after correction.",
                encoding="utf-8",
            )
            stale_issues = rd.topic_portfolio_issues(base, payload)
            self.assertTrue(
                any(
                    item.code == "RDEC.WORKSPACE_RELATION.LOCAL_STALE"
                    and item.severity == "WARNING"
                    for item in stale_issues
                )
            )
            self.assertNotEqual(
                hashlib.sha256(material.read_bytes()).hexdigest(),
                receipt["material_ref"]["sha256"],
            )

    def test_nonselected_material_staleness_does_not_topple_selected_clearance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = self._make_cleared_single_exemption_workspace(base)
            _, material = self._attach_material_discovery(base, payload)
            before_graph = copy.deepcopy(payload["selected_candidate_subgraph"])
            before_digest = payload["selected_candidate_subgraph_digest"]

            before = rd.validate_payload(base, payload)
            self.assertEqual([], before.errors)
            material.write_text(
                "The non-selected material anomaly changed after the selected candidate was cleared.",
                encoding="utf-8",
            )
            after = rd.validate_payload(base, payload)
            self.assertEqual([], after.errors)
            self.assertTrue(
                any(
                    item.code == "RDEC.WORKSPACE_RELATION.LOCAL_STALE"
                    and item.severity == "WARNING"
                    for item in after.issues
                )
            )
            self.assertFalse(
                any(
                    item.code in {"RDEC.SUBGRAPH.STALE", "RDEC.CLEARANCE_BASIS.STALE"}
                    for item in after.issues
                )
            )
            self.assertEqual("cleared", payload["disposition"])
            self.assertEqual("CAND-01", payload["selected_candidate_id"])
            self.assertEqual(before_graph, payload["selected_candidate_subgraph"])
            self.assertEqual(before_digest, payload["selected_candidate_subgraph_digest"])

    def test_runtime_rejects_title_pseudo_diversity_with_identical_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            payload = self._make_workspace(base)
            payload["candidates"][0]["provisional_title"] = (
                "1. Accountability mandates and divergent organizational responses"
            )
            payload["candidates"][0]["research_question"] = (
                "1. Why do equivalent accountability reforms produce divergent organizational responses?"
            )
            second = self._candidate("CAND-02", "SEED-02")
            second["provisional_title"] = (
                "II. Why similar accountability rules yield different reactions"
            )
            second["research_question"] = (
                "II. How can similar accountability mandates generate different organizational reactions?"
            )
            second["semantic_signature"] = copy.deepcopy(
                payload["candidates"][0]["semantic_signature"]
            )
            payload["candidates"].append(second)
            payload["candidates"][0]["distinctness"] = {
                "nearest_candidate_id": "CAND-02",
                "difference_dimensions": ["evidence_logic"],
                "rationale": "The titles differ while the declared evidentiary wording changes",
            }
            payload["candidates"][1]["distinctness"] = {
                "nearest_candidate_id": "CAND-01",
                "difference_dimensions": ["evidence_logic"],
                "rationale": "The titles differ while the declared evidentiary wording changes",
            }
            exploration = payload["exploration"]
            exploration["presented_candidate_ids"] = ["CAND-01", "CAND-02"]
            exploration["finalist_candidate_ids"] = ["CAND-01", "CAND-02"]
            exploration["portfolio_audit"]["candidate_count"] = 2
            screening_receipt = self._screening_receipt(
                exploration["topic_packet"],
                exploration["seed_seal"],
                {
                    "seed_dispositions": [
                        {
                            "seed_id": "SEED-01",
                            "disposition": "retain",
                            "candidate_id": "CAND-01",
                            "rationale": "The first seed anchors the first wording variant",
                        },
                        {
                            "seed_id": "SEED-02",
                            "disposition": "retain",
                            "candidate_id": "CAND-02",
                            "rationale": "The second seed anchors the second wording variant",
                        },
                    ],
                    "candidate_cores": [
                        rd.candidate_screened_core(item)
                        for item in payload["candidates"]
                    ],
                },
                key_store_path=base
                / ".avereth-state"
                / "topic_scheduler_keys.json",
                context_id="CTX-PSEUDO-DIVERSITY-SCREENING-001",
                issued_at="2026-08-28T10:06:30+00:00",
            )
            exploration["screening_receipt"] = screening_receipt
            semantic_receipt = self._semantic_review_receipt(
                payload["candidates"],
                ["CAND-01", "CAND-02"],
                exploration["seed_seal"],
                screening_receipt,
                exploration["topic_packet"]["direction_contract"],
                [
                    {
                        "left_candidate_id": "CAND-01",
                        "right_candidate_id": "CAND-02",
                        "relation": "equivalent",
                        "difference_dimensions": [],
                        "rationale": "Numbering and synonymous wording do not create a load-bearing research difference",
                    }
                ],
                key_store_path=base
                / ".avereth-state"
                / "topic_scheduler_keys.json",
                context_id="CTX-PSEUDO-DIVERSITY-REVIEW-001",
                issued_at="2026-08-28T10:09:00+00:00",
            )
            exploration["semantic_review_receipt"] = semantic_receipt
            exploration["portfolio_audit"]["semantic_review_receipt_sha256"] = (
                semantic_receipt["receipt_sha256"]
            )

            direct_codes = self._portfolio_codes(base, payload)
            self.assertIn("RDEC.PORTFOLIO.PSEUDO_DIVERSITY", direct_codes)
            runtime_codes = self._runtime_codes(base, payload)
            self.assertIn("RDEC.PORTFOLIO.PSEUDO_DIVERSITY", runtime_codes)

    def test_runtime_rejects_missing_admission_and_unassessed_visible_relation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            missing_base = root / "missing-admission"
            missing = self._make_workspace(missing_base)
            missing["exploration"]["workspace_materials_admitted_at"] = None
            missing_issues = self._runtime_issues(missing_base, missing)
            self.assertTrue(
                any(
                    item["code"] == "RDEC.MATERIAL_ADMISSION.MISSING"
                    and item["path"] == "exploration.workspace_materials_admitted_at"
                    for item in missing_issues
                )
            )

            unassessed_base = root / "unassessed-relation"
            unassessed = self._make_workspace(unassessed_base)
            unassessed["candidates"][0]["workspace_relation"]["role"] = "not-yet-assessed"
            unassessed_issues = self._runtime_issues(unassessed_base, unassessed)
            self.assertTrue(
                any(
                    item["code"] == "RDEC.CANDIDATE.WORKSPACE_RELATION"
                    and item["path"] == "candidates[CAND-01].workspace_relation.role"
                    for item in unassessed_issues
                )
            )

    def test_runtime_rejects_non_incidental_relation_without_material_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "missing-binding"
            payload = self._make_workspace(base)
            relation = payload["candidates"][0]["workspace_relation"]
            relation["role"] = "support"
            relation["material_refs"] = []

            issues = self._runtime_issues(base, payload)
            self.assertTrue(
                any(
                    item["code"] == "RDEC.CANDIDATE.MATERIAL_REF"
                    and item["path"]
                    == "candidates[CAND-01].workspace_relation.material_refs"
                    for item in issues
                )
            )

            stale_base = root / "stale-binding"
            stale = self._make_workspace(stale_base)
            material_path = stale_base / "materials" / "opportunity.csv"
            material_sha = hashlib.sha256(material_path.read_bytes()).hexdigest()
            stale_relation = stale["candidates"][0]["workspace_relation"]
            stale_relation.update(
                {
                    "role": "support",
                    "material_refs": [
                        {
                            "path": "materials/opportunity.csv",
                            "sha256": material_sha,
                        }
                    ],
                }
            )
            material_path.write_text(
                "organization,wave,response\nA,2024,changed\n",
                encoding="utf-8",
            )
            stale_issues = self._runtime_issues(stale_base, stale)
            self.assertTrue(
                any(
                    item["code"] == "RDEC.WORKSPACE_RELATION.STALE"
                    and item["path"]
                    == "candidates[CAND-01].workspace_relation.material_refs[0]"
                    for item in stale_issues
                )
            )

    def test_single_candidate_exemption_is_complete_and_non_fabricating_or_it_fails(self) -> None:
        exemption_fields = {
            "attempted_families": ["core-mechanism"],
            "elimination_reasons": ["short"],
            "rationale": "too short",
            "highest_originality_absence_reason": "too short",
            "no_companion_candidates_fabricated": False,
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cleared_base = root / "cleared-single"
            cleared = self._make_cleared_single_exemption_workspace(cleared_base)
            self.assertEqual(set(), self._portfolio_codes(cleared_base, cleared))
            completed = self._run(
                RESEARCH_DECISION,
                "validate",
                cleared_base / "research_decision.json",
                "--json",
                env={
                    **os.environ,
                    "AVERETH_TOPIC_SCHEDULER_KEY_STORE": str(
                        cleared_base
                        / ".avereth-state"
                        / "topic_scheduler_keys.json"
                    ),
                },
            )
            cleared_report = json.loads(completed.stdout)
            self.assertEqual("PASS", cleared_report["status"])
            self.assertEqual([], cleared_report["issues"])

            base = root / "strict-mutations"
            valid = self._make_workspace(base)
            self.assertEqual(set(), self._portfolio_codes(base, valid))
            valid_runtime = self._runtime_codes(base, valid)
            self.assertNotIn("RDEC.PORTFOLIO.EXEMPTION", valid_runtime)
            self.assertNotIn("RDEC.PORTFOLIO.FAMILY_BREADTH", valid_runtime)
            self.assertNotIn("RDEC.PORTFOLIO.FINALIST_BREADTH", valid_runtime)

            missing = copy.deepcopy(valid)
            missing["exploration"]["narrow_direction_exemption"] = None
            missing_codes = self._runtime_codes(base, missing)
            self.assertIn("RDEC.PORTFOLIO.FAMILY_BREADTH", missing_codes)
            self.assertIn("RDEC.PORTFOLIO.FINALIST_BREADTH", missing_codes)

            for field, invalid_value in exemption_fields.items():
                with self.subTest(field=field):
                    invalid = copy.deepcopy(valid)
                    invalid["exploration"]["narrow_direction_exemption"][field] = invalid_value
                    direct_codes = self._portfolio_codes(base, invalid)
                    self.assertIn("RDEC.PORTFOLIO.EXEMPTION", direct_codes)
                    runtime_codes = self._runtime_codes(base, invalid)
                    self.assertIn("RDEC.PORTFOLIO.EXEMPTION", runtime_codes)
                    self.assertIn("RDEC.PORTFOLIO.FAMILY_BREADTH", runtime_codes)
                    self.assertIn("RDEC.PORTFOLIO.FINALIST_BREADTH", runtime_codes)

    def test_material_dependent_candidate_passes_only_under_explicit_material_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            material_base = root / "material-explicit"
            explicit = self._make_workspace(material_base, origin_mode="material_opportunity")
            material_path = material_base / "materials" / "opportunity.csv"
            material_ref = {
                "path": "materials/opportunity.csv",
                "sha256": hashlib.sha256(material_path.read_bytes()).hexdigest(),
            }
            explicit_candidate = explicit["candidates"][0]
            explicit_candidate["generation_lane"] = "material_opportunity"
            explicit_candidate["portfolio_bucket"] = "material-opportunity"
            explicit_candidate["workspace_relation"] = {
                "role": "support",
                "ablation_result": "depends",
                "anchor_risk": "medium",
                "rationale": "The user explicitly authorized this registered material as the problem source",
                "material_refs": [material_ref],
            }
            explicit_exploration = explicit["exploration"]
            explicit_screening = self._screening_receipt(
                explicit_exploration["topic_packet"],
                explicit_exploration["seed_seal"],
                {
                    "seed_dispositions": [
                        {
                            "seed_id": "SEED-01",
                            "disposition": "retain",
                            "candidate_id": "CAND-01",
                            "rationale": "This declared-material seed anchors the retained candidate",
                        },
                        {
                            "seed_id": "SEED-02",
                            "disposition": "drop",
                            "candidate_id": None,
                            "rationale": "This alternative seed does not survive the bounded screen",
                        },
                    ],
                    "candidate_cores": [
                        rd.candidate_screened_core(explicit_candidate)
                    ],
                },
                key_store_path=material_base
                / ".avereth-state"
                / "topic_scheduler_keys.json",
                context_id="CTX-EXPLICIT-MATERIAL-SCREENING-001",
                issued_at="2026-08-28T10:06:30+00:00",
                workspace_root=material_base,
            )
            explicit_exploration["screening_receipt"] = explicit_screening
            explicit_semantic = self._semantic_review_receipt(
                explicit["candidates"],
                ["CAND-01"],
                explicit_exploration["seed_seal"],
                explicit_screening,
                explicit_exploration["topic_packet"]["direction_contract"],
                [],
                key_store_path=material_base
                / ".avereth-state"
                / "topic_scheduler_keys.json",
                context_id="CTX-EXPLICIT-MATERIAL-SEMANTIC-001",
                issued_at="2026-08-28T10:08:30+00:00",
            )
            explicit_exploration["semantic_review_receipt"] = explicit_semantic
            explicit_exploration["portfolio_audit"][
                "semantic_review_receipt_sha256"
            ] = explicit_semantic["receipt_sha256"]
            self.assertEqual(set(), self._portfolio_codes(material_base, explicit))
            explicit_runtime = self._runtime_codes(material_base, explicit)
            self.assertNotIn("RDEC.PORTFOLIO.MATERIAL_DEPENDENCY", explicit_runtime)
            self.assertNotIn("RDEC.CANDIDATE.GENERATION_LANE", explicit_runtime)

            direction_base = root / "direction-default"
            direction_first = self._make_workspace(direction_base)
            direction_material = direction_base / "materials" / "opportunity.csv"
            direction_candidate = direction_first["candidates"][0]
            direction_candidate["generation_lane"] = "material_opportunity"
            direction_candidate["portfolio_bucket"] = "material-opportunity"
            direction_candidate["workspace_relation"] = {
                "role": "support",
                "ablation_result": "depends",
                "anchor_risk": "high",
                "rationale": "This material dependency conflicts with the direction-first generation boundary",
                "material_refs": [
                    {
                        "path": "materials/opportunity.csv",
                        "sha256": hashlib.sha256(direction_material.read_bytes()).hexdigest(),
                    }
                ],
            }
            direction_codes = self._runtime_codes(direction_base, direction_first)
            self.assertIn("RDEC.PORTFOLIO.MATERIAL_DEPENDENCY", direction_codes)
            self.assertIn("RDEC.CANDIDATE.GENERATION_LANE", direction_codes)


if __name__ == "__main__":
    unittest.main()
