"""Synthetic fixtures for evidence identity and read-only knowledge-change views."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import novelty_delta as nd
import research_decision as rd
from test_research_decision import make_workspace, write_json


def fixture(base: Path, count: int = 1) -> tuple[dict, dict, dict]:
    """All works, passages, and judgments in this fixture are synthetic."""
    payload = make_workspace(base)
    registry_path = base / "reference_materials/literature_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    analysis = json.loads((base / "literature_analysis.json").read_text(encoding="utf-8"))
    registry["sources"] = []
    analysis["syntheses"] = []
    candidate = payload["candidates"][0]
    c1 = candidate["c1_collision_evidence"]
    c1.update(source_ids=[], synthesis_ids=[], nearest_neighbors=[])
    for index in range(1, count + 1):
        source_id, synthesis_id = f"S-COLL-{index}", f"SYN-COLL-{index}"
        path = base / f"reference_materials/synthetic-{index}.txt"
        quote = f"Synthetic study {index} finds that reporting exposure changes observed investment choices."
        text = f"SYNTHETIC ORIGINAL FIXTURE\n{quote}\nThe sample covers two invented jurisdictions.\n"
        path.write_bytes(text.encode("utf-8"))
        source = {"source_id": source_id, "title": f"Synthetic collision study {index}", "channel": "publisher",
                  "state": "content-verified", "query_ids": ["Q-COLLISION-1"], "local_file": path.relative_to(base).as_posix(),
                  "verification": {"method": "pdf", "verified_at": "2026-08-16", "support_claim": quote}}
        registry["sources"].append(source)
        analysis["syntheses"].append({"synthesis_id": synthesis_id, "candidate_ids": ["CAND-01"],
                                      "source_links": [{"source_id": source_id}], "adjudication": "Synthetic comparison of reporting exposure and choice."})
        c1["source_ids"].append(source_id)
        c1["synthesis_ids"].append(synthesis_id)
        c1["nearest_neighbors"].append({"source_id": source_id, "collision_relevance": "direct",
            "relevance_rationale": "The synthetic study examines the same conditional investment question.",
            "synthesis_ids": [synthesis_id], "facets": {key: None for key in nd.FACETS},
            "refutation": {"status": "can_refute", "prior_claim": "Reporting exposure changes observed investment choices.",
                "candidate_claim": "Reporting exposure never changes observed investment choices.",
                "rationale": "The synthetic conditional result contradicts the synthetic universal negative claim.",
                "passage": {"path": path.relative_to(base).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "start": text.index(quote), "end": text.index(quote) + len(quote), "exact_quote": quote, "locator": "Synthetic section 1, paragraph 1"}}})
    candidate["c2_overlap_adjudication"]["knowledge_delta"] = {
        "current_facets": {key: None for key in nd.FACETS},
        "delta_statement": "Test whether an additional reporting condition changes the synthetic established comparison.",
    }
    write_json(registry_path, registry)
    write_json(base / "literature_analysis.json", analysis)
    write_json(base / rd.DECISION_REL, payload)
    return payload, {row["source_id"]: row for row in registry["sources"]}, {row["synthesis_id"]: row for row in analysis["syntheses"]}


def challenge(mode: str = "boundary-test") -> dict:
    return {"mode": mode, "assumption_source_ids": ["S-COLL-1"], "assumption_status": "contested",
            **{field: f"Synthetic bounded account for {field}." for field in nd.ASSUMPTION_FIELDS}}


class NoveltyDeltaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.payload, self.sources, self.syntheses = fixture(self.base)
        self.candidate = self.payload["candidates"][0]

    def issues(self, candidate: dict | None = None, *, finalist: bool = True) -> set[str]:
        return {code for code, _, _ in nd.candidate_delta_issues(self.base, candidate or self.candidate,
                                                               self.sources, self.syntheses, finalist=finalist)}

    def neighbor(self) -> dict:
        return self.candidate["c1_collision_evidence"]["nearest_neighbors"][0]

    def view(self) -> dict:
        return nd.build_novelty_delta_view(self.base, self.payload)

    def test_verified_passage_and_eight_facets_preserve_unknowns(self) -> None:
        self.assertEqual(set(), self.issues())
        view = self.view()
        self.assertEqual(1, len(view["neighbors"]))
        self.assertEqual(set(nd.FACETS), set(view["current_facets"]))
        self.assertEqual("can_refute", view["neighbors"][0]["refutation"]["status"])
        text = nd.render_novelty_delta_view(view)
        self.assertIn("unknown", text)
        self.assertEqual(1, text.count(self.candidate["c2_overlap_adjudication"]["knowledge_delta"]["delta_statement"]))
        self.assertNotIn(self.neighbor()["refutation"]["passage"]["exact_quote"], text)
        self.assertNotIn("reference_materials/synthetic-1.txt", text)

    def test_strong_verdict_requires_each_evidence_link(self) -> None:
        original = copy.deepcopy(self.candidate)
        for status in ("can_refute", "cannot_refute"):
            for field in ("prior_claim", "candidate_claim", "rationale", "passage"):
                with self.subTest(status=status, field=field):
                    candidate = copy.deepcopy(original)
                    refutation = candidate["c1_collision_evidence"]["nearest_neighbors"][0]["refutation"]
                    refutation["status"] = status
                    refutation[field] = None
                    self.assertTrue(self.issues(candidate))

    def test_source_verification_downgrade_rejected(self) -> None:
        self.sources["S-COLL-1"]["verification"]["support_claim"] = "short"
        self.assertIn("RDEC.DELTA.SOURCE_UNVERIFIED", self.issues())

    def test_cross_candidate_and_cross_source_synthesis_rejected(self) -> None:
        for field, value in (("candidate_ids", ["CAND-02"]), ("source_links", [{"source_id": "S-OTHER"}])):
            with self.subTest(field=field):
                original = copy.deepcopy(self.syntheses["SYN-COLL-1"])
                self.syntheses["SYN-COLL-1"][field] = value
                self.assertIn("RDEC.DELTA.SYNTHESIS", self.issues())
                self.syntheses["SYN-COLL-1"] = original

    def test_exact_quote_locator_hash_offsets_and_source_path_rejected(self) -> None:
        changes = {"exact_quote": "Fabricated content", "locator": "", "sha256": "0" * 64,
                   "start": True, "end": 999999, "path": "../outside.txt"}
        for field, value in changes.items():
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.candidate)
                candidate["c1_collision_evidence"]["nearest_neighbors"][0]["refutation"]["passage"][field] = value
                self.assertTrue(self.issues(candidate))

    def test_unclear_can_remain_unknown_without_invented_evidence(self) -> None:
        self.neighbor()["refutation"] = {"status": "unclear", "prior_claim": None, "candidate_claim": None, "rationale": None, "passage": None}
        self.assertEqual(set(), self.issues())
        self.assertEqual("unclear", self.view()["neighbors"][0]["refutation"]["status"])
        self.neighbor()["facets"]["main_answer"] = "A fabricated uninspected finding."
        self.assertIn("RDEC.DELTA.SHAPE", self.issues())

    def test_changed_file_degrades_view_and_invalidates_existing_hash(self) -> None:
        before, _ = rd.selected_candidate_subgraph(self.base, self.payload)
        path = self.base / self.neighbor()["refutation"]["passage"]["path"]
        path.write_text(path.read_text(encoding="utf-8") + "Changed source.", encoding="utf-8")
        after, _ = rd.selected_candidate_subgraph(self.base, self.payload)
        self.assertNotEqual(rd.canonical_digest(before), rd.canonical_digest(after))
        view = self.view()
        refutation = view["neighbors"][0]["refutation"]
        self.assertEqual("can_refute", refutation["declared_status"])
        self.assertEqual("unclear", refutation["status"])
        self.assertTrue(refutation["evidence_problem"])
        self.assertIn("RDEC.DELTA.PASSAGE_STALE", self.issues())

    def test_optional_scientific_fields_change_hash_without_changing_sealed_core(self) -> None:
        before, _ = rd.selected_candidate_subgraph(self.base, self.payload)
        core = rd.candidate_screened_core(self.candidate)
        self.candidate["assumption_challenge"] = challenge()
        self.candidate["knowledge_change_contract"] = {"schema_version": nd.CONTRACT_VERSION, "claim_level": "high"}
        after, _ = rd.selected_candidate_subgraph(self.base, self.payload)
        self.assertNotEqual(rd.canonical_digest(before), rd.canonical_digest(after))
        self.assertEqual(core, rd.candidate_screened_core(self.candidate))
        self.assertEqual(set(), self.issues())

    def test_legacy_record_does_not_gain_hash_fields_or_gate(self) -> None:
        self.candidate["c1_collision_evidence"].pop("nearest_neighbors")
        self.candidate["c2_overlap_adjudication"].pop("knowledge_delta")
        self.assertEqual(set(), self.issues())
        basis, _ = rd.selected_candidate_subgraph(self.base, self.payload)
        self.assertNotIn("knowledge_change_dependencies", basis)
        self.assertNotIn("knowledge_change_contract", str(basis))
        self.assertNotIn("assumption_challenge", str(basis))
        view = self.view()
        self.assertIsNone(view["delta_statement"])
        self.assertEqual("unclear", view["neighbors"][0]["refutation"]["status"])

    def test_high_claim_only_opted_in_finalist_requires_assumption(self) -> None:
        self.assertEqual(set(), self.issues())
        self.candidate["knowledge_change_contract"] = {"schema_version": nd.CONTRACT_VERSION, "claim_level": "high"}
        self.assertIn("RDEC.ASSUMPTION.REQUIRED", self.issues())
        self.assertNotIn("RDEC.ASSUMPTION.REQUIRED", self.issues(finalist=False))
        self.candidate["assumption_challenge"] = challenge()
        self.assertEqual(set(), self.issues())
        self.assertIn("RDEC.ASSUMPTION.SCOPE", self.issues(finalist=False))

    def test_not_applicable_requires_specific_reason(self) -> None:
        self.candidate["assumption_challenge"] = {"mode": "not-applicable", "assumption_source_ids": [],
            "assumption_status": "not-applicable", **{field: None for field in nd.ASSUMPTION_FIELDS}}
        self.assertIn("RDEC.ASSUMPTION.NA_REASON", self.issues())
        self.candidate["assumption_challenge"]["not_applicable_reason"] = "The bounded replication tests reproducibility without challenging a theoretical assumption."
        self.assertEqual(set(), self.issues())

    def test_rank_uses_collision_relevance_and_never_fills_quota(self) -> None:
        self.payload, self.sources, self.syntheses = fixture(self.base, 5)
        self.candidate = self.payload["candidates"][0]
        rows = self.candidate["c1_collision_evidence"]["nearest_neighbors"]
        for row in rows:
            row["collision_relevance"] = "contextual"
        rows[4]["collision_relevance"] = "direct"
        view = nd.build_novelty_delta_view(self.base, self.payload, limit=3)
        self.assertEqual("S-COLL-5", view["neighbors"][0]["source_id"])
        self.assertEqual(3, len(view["neighbors"]))
        self.assertEqual(2, view["omitted_neighbor_count"])
        rows.append(copy.deepcopy(rows[0]))
        self.assertIn("RDEC.DELTA.NEIGHBORS", self.issues())

    def test_unknown_and_malformed_records_render_without_endorsing_verdict(self) -> None:
        self.neighbor()["refutation"] = {"status": "can_refute"}
        view = self.view()
        self.assertEqual("unclear", view["neighbors"][0]["refutation"]["status"])
        self.assertIn("RDEC.DELTA.SHAPE", nd.render_novelty_delta_view(view))

    def test_runtime_validator_rejects_invalid_optional_refutation(self) -> None:
        self.neighbor()["refutation"]["prior_claim"] = None
        codes = {issue.code for issue in rd.validate_payload(self.base, self.payload).issues}
        self.assertIn("RDEC.DELTA.REFUTATION_BASIS", codes)

    def test_cli_stdout_is_read_only_and_explicit_write_rebuilds_only_view(self) -> None:
        before = {path.relative_to(self.base): path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, rd.main(["novelty-delta", str(self.base)]))
        after = {path.relative_to(self.base): path.read_bytes() for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(0, rd.main(["novelty-delta", str(self.base), "--write"]))
        view_path = self.base / nd.VIEW_REL
        first = view_path.read_bytes()
        self.assertEqual(0, rd.main(["novelty-delta", str(self.base), "--write"]))
        self.assertEqual(first, view_path.read_bytes())
        for relative, raw in before.items():
            self.assertEqual(raw, (self.base / relative).read_bytes())

    def test_cli_refuses_unmanaged_and_hardlinked_view(self) -> None:
        target = self.base / nd.VIEW_REL
        target.write_text("user-owned notes", encoding="utf-8")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, rd.main(["novelty-delta", str(self.base), "--write"]))
        target.unlink()
        authority = self.base / rd.DECISION_REL
        before = authority.read_bytes()
        os.link(authority, target)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, rd.main(["novelty-delta", str(self.base), "--write"]))
        self.assertEqual(before, authority.read_bytes())

    def test_predictable_tmp_alias_cannot_modify_authority(self) -> None:
        authority = self.base / rd.DECISION_REL
        before = authority.read_bytes()
        os.link(authority, self.base / "novelty_delta_view.md.tmp")
        self.assertEqual(0, rd.main(["novelty-delta", str(self.base), "--write"]))
        self.assertEqual(before, authority.read_bytes())

    def test_symlink_target_is_rejected_without_touching_authority(self) -> None:
        authority = self.base / rd.DECISION_REL
        before = authority.read_bytes()
        target = self.base / nd.VIEW_REL
        try:
            target.symlink_to(authority)
        except OSError as exc:
            self.skipTest(f"host does not permit test symlink: {exc}")
        with redirect_stderr(io.StringIO()):
            self.assertEqual(2, rd.main(["novelty-delta", str(self.base), "--write"]))
        self.assertEqual(before, authority.read_bytes())

    def test_schema_optional_fields_and_core_contract_are_registered(self) -> None:
        schema = json.loads(rd.SCHEMA_ASSET.read_text(encoding="utf-8"))
        defs = schema["$defs"]
        self.assertNotIn("assumption_challenge", defs["candidate"]["required"])
        self.assertIn("knowledge_change_contract", defs["candidate"]["properties"])
        self.assertEqual(5, defs["checkpoint_c1"]["properties"]["nearest_neighbors"]["maxItems"])
        self.assertEqual(set(nd.FACETS), set(defs["novelty_facets"]["required"]))

    def test_question_facet_cannot_redefine_active_question(self) -> None:
        canonical = self.candidate["question_versions"][0]["text"]
        self.candidate["c2_overlap_adjudication"]["knowledge_delta"]["current_facets"]["research_question"] = "A different unauthorized research question?"
        self.assertIn("RDEC.DELTA.QUESTION_DRIFT", self.issues())
        view = self.view()
        self.assertEqual(canonical, view["current_facets"]["research_question"])
        self.assertEqual("question_versions[CAND-01-RQ-V1].text", view["current_facet_origins"]["research_question"])

    def test_known_fields_are_copied_with_provenance_while_answers_remain_unknown(self) -> None:
        self.candidate["semantic_signature"] = {"phenomenon": "Synthetic visible choices", "unit_of_analysis": "Synthetic local governments", "evidence_logic": "Synthetic matched records"}
        view = self.view()
        self.assertEqual("Synthetic visible choices", view["current_facets"]["phenomenon_or_estimand"])
        self.assertEqual("semantic_signature.phenomenon", view["current_facet_origins"]["phenomenon_or_estimand"])
        self.assertIsNone(view["current_facets"]["main_answer"])


if __name__ == "__main__":
    unittest.main()
