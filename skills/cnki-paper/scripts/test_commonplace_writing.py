"""Synthetic end-to-end checks against real MIR and ProsePacket validators."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

import commonplace_writing as writing
import prose_packet
from commonplace_bank import compile_bank
from avereth_core.build import test_manuscript_compiler as fixtures
from avereth_core.build import manuscript_compiler as compiler
from avereth_core.cli import artifact_manifest


class CommonplaceWritingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ManuscriptCompilerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.workspace = self.fixture.outdir
        self.config = {**self.fixture.config, "prose_conditioning": "commonplace"}
        writing.write(self.workspace / "workflow_config.json", self.config)
        contract = self.fixture._contract()
        self.task = {"argument_action": "PRESS", "problem_state_before": "The received account leaves a contrast unexplained.",
                     "problem_state_after": "The observed contrast narrows the received account."}
        for move in contract["moves"]:
            move.update(self.task)
        self.fixture._replace_contract(contract)
        self.compilation = compiler.compile_workspace(self.workspace, self.config)
        self.move = "MOVE-RESULTS-CORE"
        evidence = self.fixture._rebuild_pair(self.compilation, self.move)
        self.evidence = {kind: path for _, kind, path in evidence}
        self.packet_path = self.workspace / self.evidence["prose_packet"]
        pp = writing.read(self.packet_path)
        pp["rhetorical_task"] = self.task
        pp["source_digest"] = prose_packet._packet_source_digest(pp, {})
        writing.write(self.packet_path, pp)
        self.target = {"section_role": pp["section_role"], "argument_action": "PRESS", "discourse_function": "reframe"}
        source = self.workspace / "style.txt"
        source.write_text("Context about records. The archive is a clock with missing hands. Further archival context.", encoding="utf-8")
        metadata = self.workspace / "style.metadata.json"
        writing.write(metadata, {"source_id": "SRC-STYLE", "article_id": "synthetic-article", "title": "Synthetic style fixture",
                                 "authors": ["Synthetic author"], "discipline": "history", "venue": "Synthetic journal",
                                 "fulltext_sha256": writing.digest(source), "fulltext_verified": True,
                                 "permission_status": "permitted", "synthetic": True})
        full = source.read_text(encoding="utf-8")
        start, end = full.index("The archive"), full.index(" Further")
        entry = {"cp_id": "CP-ONE", "source_id": "SRC-STYLE", "locator": {"section": "results", "paragraph": 1},
                 "selection": {"before_start": 0, "start": start, "end": end, "after_end": len(full)},
                 "section_role": pp["section_role"], "argument_action": "PRESS", "discourse_function": "reframe",
                 "rhetorical_skeleton": ["compare an interpretation with an anomaly"], "citation_pattern": ["position", "reframe"],
                 "syntactic_skeleton": "[interpretation] meets [anomaly]", "lexical_bundles": [],
                 "distinctive_spans": ["clock with missing hands"], "reuse_class": "structural_exemplar"}
        bank = compile_bank({"sources": [{"source_id": "SRC-STYLE", "path": str(source), "sha256": writing.digest(source),
                                          "metadata_path": str(metadata), "metadata_sha256": writing.digest(metadata)}], "entries": [entry]})
        writing.write(self.workspace / writing.BANK, bank)

    def run_ready(self, **kwargs):
        result = writing.prepare(self.workspace, self.packet_path, self.move, self.target, **kwargs)
        self.assertEqual("READY", result["status"])
        manifest_path = self.workspace / result["dispatch"]
        for name in ("writer_draft", "clarity_draft"):
            text = (self.workspace / self.evidence[name]).read_text(encoding="utf-8")
            (manifest_path.parent / (name + ".md")).write_text(text, encoding="utf-8")
        self.make_pipeline(manifest_path)
        return manifest_path

    def use_auto(self):
        self.config["prose_conditioning"] = "auto"
        writing.write(self.workspace / "workflow_config.json", self.config)

    def make_miss(self, *, empty_bank=False):
        bank = writing.read(self.workspace / writing.BANK)
        bank["entries"] = []
        if empty_bank:
            bank["sources"] = []
        bank["source_digest"] = writing.canonical_sha256({key: value for key, value in bank.items() if key != "source_digest"})
        writing.write(self.workspace / writing.BANK, bank)

    def make_search_record(self, outcome="no_match"):
        pending = writing.prepare(self.workspace, self.packet_path, self.move, self.target)
        self.assertEqual("COMMONPLACE_SEARCH_REQUIRED", pending["status"])
        self.assertFalse((self.workspace / writing.INDEX).exists())
        request = self.workspace / "synthetic-search-request.json"
        response = self.workspace / "synthetic-search-response.json"
        writing.write(request, {"synthetic": True, "query": "archival contrast rhetorical PRESS", "source": "synthetic fixture provider"})
        writing.write(response, {"synthetic": True, "request_id": "search-fixture-001", "outcome": outcome,
                                 "results": [], "detail": "No function-matching verified full text" if outcome == "no_match" else "Provider access requires unavailable permission"})
        path = self.workspace / "synthetic-search-record.json"
        writing.write(path, {"schema_version": writing.SEARCH_SCHEMA, "move_ref": self.move,
                             "target": pending["target"], "bank_sha256": pending["bank_sha256"],
                             "attempts": [{"search_id": "search-fixture-001", "source": "synthetic fixture provider",
                                           "query": "archival contrast rhetorical PRESS", "outcome": outcome,
                                           "reason": "Synthetic retained request and response demonstrate the parser contract only.",
                                           "request": {"path": request.name, "sha256": writing.digest(request)},
                                           "response": {"path": response.name, "sha256": writing.digest(response)}}]})
        return path

    def make_locked_packet(self, *, legacy=False, text=None):
        original = writing.read(self.packet_path)
        claim = {key: original["claim"][key] for key in ("id", "canonical_proposition", "strength")}
        if text is not None:
            claim["canonical_proposition"] = text
        if not legacy:
            claim.update(realization_mode="verbatim", verbatim_reason="user_locked")
        packet = prose_packet.compile_prose_packet({
            "section_role": original["section_role"], "object": original["object"], "claim": claim,
            "evidence_items": [{"id": "EVD-001", "text": "Registered evidence supports the bounded association.",
                                "evidence_function": "supports the registered Claim"}],
            "warrant": original["warrant"], "reader_question": original["reader_question"],
            "plain_core": claim["canonical_proposition"], "explanation_path": original["explanation_path"],
            "reader_update": original["reader_update"],
        }, registered_ids=prose_packet.discover_registered_ids(self.workspace))
        writing.write(self.packet_path, packet)
        return packet

    def make_pipeline(self, path):
        directory = path.parent
        writing.write(directory / "clarity_ledger.json", {"schema_version": "avereth-clarity-edit-ledger/v1", "scope": "section", "actions": []})
        dispatch = prose_packet.dispatch_semantic_fidelity_review(
            self.workspace, directory / "prose_packet.json", directory / "clarity_draft.md",
            registered_ids=prose_packet.discover_registered_ids(self.workspace), writer_context_id="synthetic-writer",
            clarity_context_id="synthetic-clarity", output_dir=directory / "semantic")
        pp = writing.read(directory / "prose_packet.json")
        draft = (directory / "clarity_draft.md").read_text(encoding="utf-8")
        pp_hash, draft_hash = prose_packet.semantic_fidelity_digests(pp, draft)
        writing.write(self.workspace / dispatch["review_output"], {
            "schema_version": prose_packet.SEMANTIC_FIDELITY_REVIEW_SCHEMA_VERSION, "review_run_id": dispatch["review_run_id"],
            "packet_sha256": pp_hash, "draft_sha256": draft_hash,
            "dimensions": {key: {"status": "PASS", "reason": "Synthetic fixture preserves the registered " + key} for key in prose_packet.SEMANTIC_FIDELITY_DIMENSIONS},
            "overall_status": "PASS"})
        prose_packet.create_semantic_fidelity_assurance(self.workspace, self.workspace / dispatch["manifest"], reviewer_context_id="synthetic-independent-reviewer")

    def test_dual_packet_check_and_receipt_source_closure(self):
        path = self.run_ready()
        result = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("PASS", result["verdict"])
        manifest = artifact_manifest(self.workspace, excludes=set())
        self.assertIn("style.txt", manifest)
        self.assertIn("style.metadata.json", manifest)
        self.assertIn(path.relative_to(self.workspace).as_posix(), manifest)
        prompt = (path.parent / "writer_prompt.md").read_text(encoding="utf-8")
        self.assertNotIn("style.txt", prompt)

    def test_flag_off_is_default_and_prepare_rejects(self):
        writing.write(self.workspace / "workflow_config.json", self.fixture.config)
        with self.assertRaisesRegex(ValueError, "prose_conditioning"):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target)
        self.assertEqual([], writing.validate_workspace_runs(self.workspace, self.compilation.ir, self.fixture.config, ""))

    def test_no_match_preserves_no_active_index(self):
        target = {**self.target, "section_role": "discussion", "discourse_function": "other"}
        # A mismatched section cannot silently retarget the current Move.
        with self.assertRaisesRegex(ValueError, "section/action"):
            writing.prepare(self.workspace, self.packet_path, self.move, target)
        self.assertFalse((self.workspace / writing.INDEX).exists())

    def test_source_mutation_invalidates_current_run(self):
        path = self.run_ready()
        (self.workspace / "style.txt").write_text("Changed source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA"):
            writing.check_run(self.workspace, path)

    def test_packet_mutation_invalidates_current_run(self):
        path = self.run_ready()
        cp = writing.read(path.parent / "commonplace_packet.json")
        cp["exemplars"][0]["blocked_spans"] = []
        writing.write(path.parent / "commonplace_packet.json", cp)
        with self.assertRaisesRegex(ValueError, "stale Commonplace input"):
            writing.check_run(self.workspace, path)

    def test_wrong_move_rhetorical_action_fails(self):
        pp = writing.read(self.packet_path)
        pp["rhetorical_task"]["argument_action"] = "POSE"
        pp["source_digest"] = prose_packet._packet_source_digest(pp, {})
        writing.write(self.packet_path, pp)
        with self.assertRaisesRegex(ValueError, "rhetorical_task"):
            writing.prepare(self.workspace, self.packet_path, self.move, {**self.target, "argument_action": "POSE"})

    def test_distinctive_overlap_after_clarity_is_not_hidden(self):
        path = self.run_ready()
        with (path.parent / "clarity_draft.md").open("a", encoding="utf-8") as handle:
            handle.write(" A clock with missing hands.")
        result = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("FAIL", result["verdict"])
        self.assertEqual("FAIL", result["reports"]["clarity_draft"]["verdict"])

    def test_enabled_build_requires_current_runs_for_all_moves(self):
        compiler.render_workspace(self.workspace, self.config, baseline=True)
        issues = compiler.validate_workspace(self.workspace, self.config)
        self.assertTrue(any(i.code == "MS-COMMONPLACE" and "missing" in str(i) for i in issues))

    def test_checked_text_must_enter_manuscript_and_check_cannot_be_forged(self):
        path = self.run_ready()
        writing.check_run(self.workspace, path, persist=True)
        single_ir = copy.deepcopy(self.compilation.ir)
        single_ir["moves"] = [node for node in single_ir["moves"] if node["contract"]["move_id"] == self.move]
        text = (path.parent / "clarity_draft.md").read_text(encoding="utf-8")
        self.assertEqual([], writing.validate_workspace_runs(self.workspace, single_ir, self.config, text))
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir, self.config, "unrelated prose"))
        recorded = writing.read(path.parent / "borrowing_check.json")
        recorded["reports"] = {}
        writing.write(path.parent / "borrowing_check.json", recorded)
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir, self.config, text))

    def test_retry_keeps_previous_run_files(self):
        first = self.run_ready()
        second = self.run_ready()
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists())
        self.assertEqual(second.relative_to(self.workspace).as_posix(), writing.read(self.workspace / writing.INDEX)["moves"][self.move])

    def test_missing_semantic_review_cannot_pass_baseline(self):
        path = self.run_ready()
        (path.parent / "semantic" / "review.json").unlink()
        result = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(result["pipeline_issues"])

    def test_missing_clarity_ledger_cannot_pass(self):
        path = self.run_ready()
        (path.parent / "clarity_ledger.json").unlink()
        self.assertEqual("FAIL", writing.check_run(self.workspace, path)["verdict"])

    def test_alternate_semantic_review_cannot_escape_receipt_binding(self):
        path = self.run_ready()
        semantic_dir = path.parent / "semantic"
        dispatch = writing.read(semantic_dir / "dispatch.json")
        alternate = semantic_dir / "alternate-review.json"
        alternate.write_bytes((semantic_dir / "review.json").read_bytes())
        dispatch["review_output_path"] = alternate.relative_to(self.workspace).as_posix()
        writing.write(semantic_dir / "dispatch.json", dispatch)
        (semantic_dir / "assurance.json").unlink()
        prose_packet.create_semantic_fidelity_assurance(self.workspace, semantic_dir / "dispatch.json", reviewer_context_id="synthetic-independent-reviewer")
        result = writing.check_run(self.workspace, path)
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(any("canonical paths" in issue for issue in result["pipeline_issues"]))

    def test_semantic_failure_cannot_be_overridden_by_borrowing_review(self):
        path = self.run_ready()
        review = writing.read(path.parent / "semantic" / "review.json")
        review["overall_status"] = "FAIL"
        writing.write(path.parent / "semantic" / "review.json", review)
        self.assertEqual("FAIL", writing.check_run(self.workspace, path)["verdict"])

    def test_enabled_full_manuscript_baseline_closes_every_move(self):
        outputs = []
        for node in self.compilation.ir["moves"]:
            self.move = node["contract"]["move_id"]
            evidence = self.fixture._rebuild_pair(self.compilation, self.move)
            self.evidence = {kind: path for _, kind, path in evidence}
            self.packet_path = self.workspace / self.evidence["prose_packet"]
            pp = writing.read(self.packet_path)
            pp["rhetorical_task"] = self.task
            pp["source_digest"] = prose_packet._packet_source_digest(pp, {})
            writing.write(self.packet_path, pp)
            self.target = {"section_role": pp["section_role"], "argument_action": "PRESS", "discourse_function": "reframe"}
            path = self.run_ready()
            result = writing.check_run(self.workspace, path, persist=True)
            self.assertEqual("PASS", result["verdict"], result)
            outputs.append((path.parent / "clarity_draft.md").read_text(encoding="utf-8"))
        (self.workspace / "final_paper/main.md").write_text("\n\n".join(outputs), encoding="utf-8")
        compiler.render_workspace(self.workspace, self.config, baseline=True)
        self.assertEqual([], compiler.validate_workspace(self.workspace, self.config))

    def test_auto_ready_preserves_dual_packet_checks_and_single_move_closure(self):
        self.use_auto()
        path = self.run_ready()
        dispatch = writing.read(path)
        self.assertEqual(writing.AUTO_RUN_SCHEMA, dispatch["schema_version"])
        self.assertEqual("dual_packet", dispatch["run_mode"])
        result = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("PASS", result["verdict"])
        self.assertEqual({"writer_draft", "clarity_draft"}, set(result["reports"]))
        prompt = (path.parent / "writer_prompt.md").read_text(encoding="utf-8")
        self.assertIn("Read exactly these two files", prompt)
        self.assertIn("Do not force every opening", prompt)

    def test_auto_empty_bank_does_not_claim_a_search_or_create_index(self):
        self.use_auto()
        self.make_miss(empty_bank=True)
        result = writing.prepare(self.workspace, self.packet_path, self.move, self.target)
        self.assertEqual("COMMONPLACE_SEARCH_REQUIRED", result["status"])
        self.assertFalse((self.workspace / writing.INDEX).exists())

    def test_auto_no_match_single_packet_keeps_complete_semantic_chain_and_receipt(self):
        self.use_auto()
        self.make_miss()
        search = self.make_search_record()
        path = self.run_ready(search_record=search)
        dispatch = writing.read(path)
        self.assertEqual("evidence_only", dispatch["run_mode"])
        self.assertEqual("no_match", dispatch["gap_reason"])
        result = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("PASS", result["verdict"], result)
        self.assertEqual({}, result["reports"])  # No claim of a borrowing check without exemplars.
        self.assertTrue(result["pipeline_bindings"])
        prompt = (path.parent / "writer_prompt.md").read_text(encoding="utf-8")
        self.assertIn("Read exactly this file", prompt)
        self.assertNotIn("CommonplacePacket", prompt)
        self.assertNotIn("search", prompt)
        manifest = artifact_manifest(self.workspace, excludes=set())
        self.assertIn("synthetic-search-record.json", manifest)
        self.assertIn("synthetic-search-request.json", manifest)
        self.assertIn("synthetic-search-response.json", manifest)
        single_ir = copy.deepcopy(self.compilation.ir)
        single_ir["moves"] = [node for node in single_ir["moves"] if node["contract"]["move_id"] == self.move]
        draft = (path.parent / "clarity_draft.md").read_text(encoding="utf-8")
        self.assertEqual([], writing.validate_workspace_runs(self.workspace, single_ir, self.config, draft))
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir, self.config, draft + draft))
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir,
                                                      {**self.config, "prose_conditioning": "commonplace"}, draft))

    def test_auto_access_blocked_is_recorded_as_blocked_not_no_match(self):
        self.use_auto()
        self.make_miss()
        path = self.run_ready(search_record=self.make_search_record("access_blocked"))
        self.assertEqual("access_blocked", writing.read(path)["gap_reason"])
        self.assertEqual("PASS", writing.check_run(self.workspace, path)["verdict"])

    def test_auto_fallback_fails_on_search_evidence_change(self):
        self.use_auto()
        self.make_miss()
        path = self.run_ready(search_record=self.make_search_record())
        (self.workspace / "synthetic-search-response.json").write_text("Changed result", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "search evidence.*SHA"):
            writing.check_run(self.workspace, path)

    def test_auto_fallback_requires_real_nonempty_artifact_bindings(self):
        self.use_auto()
        self.make_miss(empty_bank=True)
        search = self.make_search_record()
        record = writing.read(search)
        for corrupted in (
            {**record, "attempts": []},
            {**record, "move_ref": "MOVE-OTHER"},
            {**record, "bank_sha256": "0" * 64},
        ):
            with self.subTest(corrupted=corrupted):
                writing.write(search, corrupted)
                with self.assertRaises(ValueError):
                    writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        writing.write(search, record)
        response = self.workspace / "synthetic-search-response.json"
        response.write_text("", encoding="utf-8")
        record["attempts"][0]["response"]["sha256"] = writing.digest(response)
        writing.write(search, record)
        with self.assertRaisesRegex(ValueError, "missing, empty or SHA"):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        self.assertFalse((self.workspace / writing.INDEX).exists())

    def test_auto_bank_missing_or_corrupt_source_cannot_be_a_gap(self):
        self.use_auto()
        self.make_miss()
        search = self.make_search_record()
        bank_file = self.workspace / writing.BANK
        bank_bytes = bank_file.read_bytes()
        bank_file.unlink()
        with self.assertRaises(OSError):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        bank_file.write_bytes(bank_bytes)
        (self.workspace / "style.txt").write_text("Changed source file", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA"):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        self.assertFalse((self.workspace / writing.INDEX).exists())

    def test_auto_fallback_revalidates_unselected_bank_sources(self):
        self.use_auto()
        self.make_miss()
        path = self.run_ready(search_record=self.make_search_record())
        (self.workspace / "style.txt").write_text("Changed unselected source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "SHA"):
            writing.check_run(self.workspace, path)

    def test_auto_illegal_or_outside_source_is_an_error_not_a_gap(self):
        self.use_auto()
        self.make_miss()
        search = self.make_search_record()
        original = writing.read(self.workspace / writing.BANK)
        denied = copy.deepcopy(original)
        denied["sources"][0]["metadata"]["permission_status"] = "denied"
        denied["source_digest"] = writing.canonical_sha256({key: value for key, value in denied.items() if key != "source_digest"})
        writing.write(self.workspace / writing.BANK, denied)
        with self.assertRaisesRegex(ValueError, "permitted use"):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        outside = copy.deepcopy(original)
        outside["sources"][0]["path"] = str(self.workspace.parent / "outside.txt")
        writing.write(self.workspace / writing.BANK, outside)
        with self.assertRaises(ValueError):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        writing.write(self.workspace / writing.BANK, original)
        (self.workspace / "style.metadata.json").unlink()
        with self.assertRaises(ValueError):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)
        self.assertFalse((self.workspace / writing.INDEX).exists())

    def test_auto_fallback_bank_change_invalidates_dispatch(self):
        self.use_auto()
        self.make_miss()
        path = self.run_ready(search_record=self.make_search_record())
        self.make_miss(empty_bank=True)
        with self.assertRaisesRegex(ValueError, "bank changed"):
            writing.check_run(self.workspace, path)

    def test_auto_fallback_cannot_skip_clarity_or_semantic_failure(self):
        self.use_auto()
        self.make_miss()
        path = self.run_ready(search_record=self.make_search_record())
        review = writing.read(path.parent / "semantic" / "review.json")
        review["overall_status"] = "FAIL"
        writing.write(path.parent / "semantic" / "review.json", review)
        self.assertEqual("FAIL", writing.check_run(self.workspace, path)["verdict"])
        (path.parent / "clarity_ledger.json").unlink()
        self.assertEqual("FAIL", writing.check_run(self.workspace, path)["verdict"])

    def test_auto_fallback_facts_and_packet_validation_cannot_be_bypassed(self):
        self.use_auto()
        self.make_miss()
        search = self.make_search_record()
        path = self.run_ready(search_record=search)
        writer = path.parent / "writer_draft.md"
        writer.write_text(writer.read_text(encoding="utf-8").replace("registered predictor", "unregistered actor"), encoding="utf-8")
        result = writing.check_run(self.workspace, path)
        self.assertEqual("FAIL", result["verdict"])
        self.assertTrue(result["fidelity_issues"]["writer_draft"])
        pp = writing.read(self.packet_path)
        pp["evidence_items"][0]["id"] = "EVD-UNREGISTERED"
        pp["source_digest"] = prose_packet._packet_source_digest(pp, {})
        writing.write(self.packet_path, pp)
        with self.assertRaises(ValueError):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=search)

    def test_auto_borrowing_failure_is_not_turned_into_fallback(self):
        self.use_auto()
        path = self.run_ready()
        with (path.parent / "writer_draft.md").open("a", encoding="utf-8") as handle:
            handle.write(" A clock with missing hands.")
        result = writing.check_run(self.workspace, path)
        self.assertEqual("FAIL", result["verdict"])
        self.assertEqual("dual_packet", result["run_mode"])
        self.assertEqual("FAIL", result["reports"]["writer_draft"]["verdict"])

    def test_failed_dual_run_cannot_be_relabelled_as_an_exemplar_gap(self):
        self.use_auto()
        path = self.run_ready()
        with (path.parent / "writer_draft.md").open("a", encoding="utf-8") as handle:
            handle.write(" A clock with missing hands.")
        self.assertEqual("FAIL", writing.check_run(self.workspace, path, persist=True)["verdict"])
        self.make_miss()
        pending = writing.prepare(self.workspace, self.packet_path, self.move, self.target)
        request, response = self.workspace / "request.json", self.workspace / "response.json"
        writing.write(request, {"synthetic": True, "query": "current function search"})
        writing.write(response, {"synthetic": True, "results": []})
        record = self.workspace / "gap.json"
        writing.write(record, {"schema_version": writing.SEARCH_SCHEMA, "move_ref": self.move,
                               "target": pending["target"], "bank_sha256": pending["bank_sha256"], "attempts": [{
                                   "search_id": "synthetic-retry", "source": "synthetic fixture", "query": "current function search",
                                   "outcome": "no_match", "reason": "Synthetic no-match cannot excuse a current borrowing failure.",
                                   "request": {"path": request.name, "sha256": writing.digest(request)},
                                   "response": {"path": response.name, "sha256": writing.digest(response)}}]})
        with self.assertRaisesRegex(ValueError, "already has selected exemplars"):
            writing.prepare(self.workspace, self.packet_path, self.move, self.target, search_record=record)
        self.assertEqual(path.relative_to(self.workspace).as_posix(), writing.read(self.workspace / writing.INDEX)["moves"][self.move])

    def test_auto_build_requires_all_current_move_records(self):
        self.use_auto()
        compiler.render_workspace(self.workspace, self.config, baseline=True)
        issues = compiler.validate_workspace(self.workspace, self.config)
        self.assertTrue(any(i.code == "MS-COMMONPLACE" and "missing" in str(i) for i in issues))

    def test_auto_locked_preserves_exact_text_and_does_not_require_semantic(self):
        self.use_auto()
        packet = self.make_locked_packet()
        result = writing.prepare(self.workspace, self.packet_path, self.move, {})
        self.assertEqual("locked_text", result["run_mode"])
        path = self.workspace / result["dispatch"]
        for label in ("writer_draft", "clarity_draft"):
            (path.parent / (label + ".md")).write_text(packet["claim"]["text"], encoding="utf-8")
        writing.write(path.parent / "clarity_ledger.json", {"schema_version": "avereth-clarity-edit-ledger/v1", "scope": "section", "actions": []})
        check = writing.check_run(self.workspace, path, persist=True)
        self.assertEqual("PASS", check["verdict"], check)
        self.assertFalse((path.parent / "semantic").exists())
        self.assertNotIn("bank_path", writing.read(path))
        self.assertIn(path.relative_to(self.workspace).as_posix(), artifact_manifest(self.workspace, excludes=set()))
        single_ir = copy.deepcopy(self.compilation.ir)
        single_ir["moves"] = [node for node in single_ir["moves"] if node["contract"]["move_id"] == self.move]
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir,
                                                      {**self.config, "prose_conditioning": "commonplace"}, packet["claim"]["text"]))
        for label in ("writer_draft", "clarity_draft"):
            (path.parent / (label + ".md")).write_text(packet["claim"]["text"] + " An unauthorized new conclusion.", encoding="utf-8")
        self.assertEqual("FAIL", writing.check_run(self.workspace, path)["verdict"])

    def test_auto_locked_cannot_substitute_another_claim_or_legacy_omission(self):
        self.use_auto()
        self.make_locked_packet(text="An unrelated statement cannot replace the registered authority.")
        with self.assertRaisesRegex(ValueError, "registered Claim authority"):
            writing.prepare(self.workspace, self.packet_path, self.move, {})
        # Produce a valid legacy exact packet; new auto runs cannot use omitted mode as an escape.
        self.make_locked_packet(legacy=True)
        with self.assertRaises(ValueError):
            writing.prepare(self.workspace, self.packet_path, self.move, {})

    def test_auto_reads_existing_v1_run_without_migration(self):
        path = self.run_ready()
        dispatch_before = path.read_bytes()
        writing.check_run(self.workspace, path, persist=True)
        check_before = (path.parent / "borrowing_check.json").read_bytes()
        self.use_auto()
        self.assertEqual("PASS", writing.check_run(self.workspace, path)["verdict"])
        self.assertEqual(dispatch_before, path.read_bytes())
        self.assertEqual(check_before, (path.parent / "borrowing_check.json").read_bytes())

    def test_none_keeps_validating_existing_auto_records(self):
        self.use_auto()
        path = self.run_ready()
        writing.check_run(self.workspace, path, persist=True)
        single_ir = copy.deepcopy(self.compilation.ir)
        single_ir["moves"] = [node for node in single_ir["moves"] if node["contract"]["move_id"] == self.move]
        text = (path.parent / "clarity_draft.md").read_text(encoding="utf-8")
        disabled = {**self.config, "prose_conditioning": "none"}
        self.assertEqual([], writing.validate_workspace_runs(self.workspace, single_ir, disabled, text))
        (self.workspace / "style.txt").write_text("Changed source", encoding="utf-8")
        self.assertTrue(writing.validate_workspace_runs(self.workspace, single_ir, disabled, text))

    def test_locked_stale_rebuild_uses_exact_fidelity_without_semantic_escape(self):
        self.use_auto()
        compiler.render_workspace(self.workspace, self.config, baseline=True)
        changed = self.fixture._drift_execution()
        self.assertIn(self.move, changed.stale["stale_move_refs"])
        packet = self.make_locked_packet()
        prepared = writing.prepare(self.workspace, self.packet_path, self.move, {})
        path = self.workspace / prepared["dispatch"]
        entries = [(self.move, "prose_packet", (path.parent / "prose_packet.json").relative_to(self.workspace).as_posix())]
        for kind in ("writer_draft", "clarity_draft"):
            target = path.parent / (kind + ".md")
            target.write_text(packet["claim"]["text"], encoding="utf-8")
            entries.append((self.move, kind, target.relative_to(self.workspace).as_posix()))
        ledger = path.parent / "clarity_ledger.json"
        writing.write(ledger, {"schema_version": "avereth-clarity-edit-ledger/v1", "scope": "section", "actions": []})
        entries.append((self.move, "clarity_ledger", ledger.relative_to(self.workspace).as_posix()))
        (self.workspace / "final_paper/main.md").write_text(packet["claim"]["text"], encoding="utf-8")
        self.assertTrue(compiler.record_rebuild_proofs(self.workspace, self.config, entries).exists())
        for kind in ("writer_draft", "clarity_draft"):
            (path.parent / (kind + ".md")).write_text(packet["claim"]["text"] + " An unauthorized conclusion.", encoding="utf-8")
        with self.assertRaises(compiler.ManuscriptCompilerError) as caught:
            compiler.record_rebuild_proofs(self.workspace, self.config, entries)
        self.assertTrue(any("locked Move" in issue.message for issue in caught.exception.issues))


if __name__ == "__main__":
    unittest.main()
